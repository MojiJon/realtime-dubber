"""
Manages the Gemini Live Translate connection.

IMPORTANT: A single WebSocket connection to the Live API only lasts about
10 minutes, and audio-only sessions are capped around 12-15 minutes without
context compression -- after that, the server closes the connection on its
own (this is a documented Google limit, not a bug). For an app meant to run
for a whole gaming session, that means we MUST reconnect automatically.

Two features make this work without losing context or restarting the
conversation from scratch:
  - session_resumption: the server periodically hands us a "resumption
    handle". If the connection drops, we open a NEW connection and pass that
    handle back, and the server picks up where it left off.
  - context_window_compression: lets a session live indefinitely by
    summarizing/discarding older parts of the conversation once the context
    grows past a threshold, instead of hitting a hard token limit and dying.

So the outer run() loop is a "keep reconnecting forever" loop, not a single
one-shot connection.
"""

import asyncio

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from websockets.exceptions import ConnectionClosed

import config
from audio_io import LoopbackSource, SpeakerOutput
from volume_control import duck, restore


def _build_client() -> genai.Client:
    http_options = None
    if config.PROXY_URL:
        http_options = types.HttpOptions(client_args={"proxy": config.PROXY_URL})
    return genai.Client(api_key=config.GEMINI_API_KEY, http_options=http_options)


def _build_live_config(resumption_handle):
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        translation_config=types.TranslationConfig(
            target_language_code=config.TARGET_LANGUAGE_CODE,
            echo_target_language=config.ECHO_TARGET_LANGUAGE,
        ),
        session_resumption=types.SessionResumptionConfig(handle=resumption_handle),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow(),
        ),
    )


async def run():
    client = _build_client()
    source = LoopbackSource(device_name_substring=config.INPUT_DEVICE_NAME)
    source.open()
    speaker = SpeakerOutput(device_name_substring=config.OUTPUT_DEVICE_NAME)

    # Tracks whether we've currently ducked the volume, so we duck once per
    # utterance (not once per audio chunk) and reliably restore it after.
    state = {"ducked_level": None}
    resumption_handle = None

    try:
        while True:
            live_config = _build_live_config(resumption_handle)

            try:
                async with client.aio.live.connect(
                    model=config.GEMINI_MODEL, config=live_config
                ) as session:
                    if resumption_handle:
                        print("[reconnected -- session resumed, no context lost]")
                    else:
                        print(f"Live translation session started -> {config.TARGET_LANGUAGE_CODE}")
                        print("Press Ctrl+C to stop.\n")

                    loop = asyncio.get_event_loop()

                    async def send_loop():
                        while True:
                            # Blocks on the queue, not the network -- capture
                            # keeps running even if this is momentarily behind.
                            chunk = await loop.run_in_executor(None, source.get_chunk)
                            await session.send_realtime_input(
                                audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                            )

                    async def receive_loop():
                        nonlocal resumption_handle
                        async for response in session.receive():
                            update = response.session_resumption_update
                            if update and update.resumable and update.new_handle:
                                resumption_handle = update.new_handle

                            if response.go_away:
                                print(
                                    f"[server closing connection in {response.go_away.time_left}] "
                                    "will reconnect automatically"
                                )

                            sc = response.server_content
                            if not sc:
                                continue

                            if sc.input_transcription and sc.input_transcription.text:
                                print(f"[in]  {sc.input_transcription.text}")
                            if sc.output_transcription and sc.output_transcription.text:
                                print(f"[out] {sc.output_transcription.text}")

                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        if state["ducked_level"] is None:
                                            state["ducked_level"] = duck()
                                        # write() is non-blocking now (just
                                        # queues the chunk), so no need to
                                        # offload it -- doing so previously
                                        # forced us to wait out each chunk's
                                        # playback duration before reading
                                        # the next server message, adding
                                        # latency for no reason.
                                        speaker.write(part.inline_data.data)

                            if sc.turn_complete and state["ducked_level"] is not None:
                                restore(state["ducked_level"])
                                state["ducked_level"] = None

                    await asyncio.gather(send_loop(), receive_loop())

            except (ConnectionClosed, genai_errors.APIError) as exc:
                if state["ducked_level"] is not None:
                    restore(state["ducked_level"])
                    state["ducked_level"] = None
                print(f"[connection dropped: {exc}] reconnecting in 1s...")
                await asyncio.sleep(1)
                continue
    finally:
        if state["ducked_level"] is not None:
            restore(state["ducked_level"])
        source.close()
        speaker.close()
