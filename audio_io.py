"""
Handles the two audio streams the Live API needs:

  INPUT  (what we capture and send):  16-bit PCM, 16kHz, mono
  OUTPUT (what we receive and play):  16-bit PCM, 24kHz, mono

IMPORTANT DESIGN NOTE:
Capturing audio and sending it over the network are decoupled on purpose.
LoopbackSource runs its own background callback thread (driven by PortAudio,
not by us) that continuously reads audio and pushes resampled chunks into a
queue -- no matter what else is happening. Whatever consumes from that queue
(the network send loop) can lag behind without causing any audio to be
dropped or skipped, because capture never waits on it.

Earlier version of this file used a manual "read N frames, await network
send, repeat" loop. That's fragile: if the network send took even slightly
longer than the chunk duration, PortAudio's internal buffer would overflow
and silently drop audio -- which is exactly what caused choppy, cut-off
translations (gaps in input make the model think the speaker paused).
"""

import queue
import threading

import numpy as np
import pyaudiowpatch as pyaudio

import config

INPUT_RATE = 16000
OUTPUT_RATE = 24000
SAMPLE_WIDTH = 2  # bytes per sample (16-bit PCM)
CHUNK_MS = 100  # matches the Live API's recommended input chunk size

# How many chunks we're willing to buffer if sending falls behind.
# 50 chunks * 100ms = 5 seconds of headroom before we start dropping the
# OLDEST audio (better than growing latency forever).
MAX_QUEUED_CHUNKS = 50


def _resample(samples: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    if orig_rate == target_rate or len(samples) == 0:
        return samples
    duration = len(samples) / orig_rate
    target_len = max(1, int(duration * target_rate))
    orig_idx = np.linspace(0, len(samples) - 1, num=len(samples))
    target_idx = np.linspace(0, len(samples) - 1, num=target_len)
    return np.interp(target_idx, orig_idx, samples)


class LoopbackSource:
    """Captures system output audio (what you hear) as 16kHz mono PCM16.

    Uses PortAudio's callback mode: PortAudio itself calls _callback() on a
    dedicated internal thread at the hardware's own pace, so capture timing
    is never at the mercy of our Python/network code.
    """

    def __init__(self, device_name_substring: str | None = None):
        self._pa = pyaudio.PyAudio()
        self._device = self._find_loopback_device(device_name_substring)
        self.native_rate = int(self._device["defaultSampleRate"])
        self.channels = self._device["maxInputChannels"]
        self._stream = None
        self.queue: "queue.Queue[bytes]" = queue.Queue(maxsize=MAX_QUEUED_CHUNKS)

    def _find_loopback_device(self, name_substring):
        if name_substring:
            # Capture a SPECIFIC device by name (e.g. "VoiceMeeter Input")
            # instead of whatever Windows currently considers "default".
            # Useful when routing audio through a mixer, so we grab the
            # pre-mix signal instead of the final speaker output.
            name_substring = name_substring.lower()
            for loopback in self._pa.get_loopback_device_info_generator():
                if name_substring in loopback["name"].lower():
                    return loopback
            raise RuntimeError(
                f'No loopback-capable device found matching "{name_substring}". '
                "Run list_devices.py to see available loopback device names."
            )

        wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = self._pa.get_device_info_by_index(
            wasapi_info["defaultOutputDevice"]
        )

        if not default_speakers.get("isLoopbackDevice", False):
            for loopback in self._pa.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                raise RuntimeError(
                    "Could not find a loopback device matching your default "
                    "speakers. Make sure you're on Windows 10/11 and that "
                    "PyAudioWPatch is installed correctly."
                )

        return default_speakers

    def _callback(self, in_data, frame_count, time_info, status):
        samples = np.frombuffer(in_data, dtype=np.int16)
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels).mean(axis=1)

        resampled = _resample(samples, self.native_rate, INPUT_RATE).astype(np.int16)
        chunk = resampled.tobytes()

        try:
            self.queue.put_nowait(chunk)
        except queue.Full:
            # We've fallen more than 5s behind. Drop the OLDEST chunk to
            # make room -- this bounds latency instead of letting it grow
            # forever, at the cost of losing a little audio in the worst case.
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            self.queue.put_nowait(chunk)

        return (None, pyaudio.paContinue)

    def open(self):
        frames_per_buffer = int(self.native_rate * CHUNK_MS / 1000)
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.native_rate,
            input=True,
            input_device_index=self._device["index"],
            frames_per_buffer=frames_per_buffer,
            stream_callback=self._callback,
        )
        self._stream.start_stream()

    def get_chunk(self) -> bytes:
        """Blocks until the next resampled audio chunk is available."""
        return self.queue.get()

    def close(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()


def _resample_to_length(samples: np.ndarray, target_len: int) -> np.ndarray:
    """Stretches/compresses `samples` to exactly `target_len` samples.

    Used for playback catch-up: reading MORE input samples than the output
    callback asked for, then compressing them down to the requested length,
    plays that audio back faster than real-time (with a slight pitch rise).
    """
    if len(samples) == 0 or target_len <= 0:
        return np.zeros(max(target_len, 0), dtype=np.int16)
    if len(samples) == target_len:
        return samples
    orig_idx = np.linspace(0, len(samples) - 1, num=len(samples))
    target_idx = np.linspace(0, len(samples) - 1, num=target_len)
    return np.interp(target_idx, orig_idx, samples).astype(np.int16)


class SpeakerOutput:
    """Plays back 24kHz mono PCM16 audio (the Live API's output format).

    Uses PortAudio's callback (output) mode with an internal jitter buffer,
    for the same reason LoopbackSource uses callback mode for capture:
    audio chunks arrive from the network in bursts, not at a perfectly
    steady pace. Feeding them straight into a blocking write() ties
    playback timing to network timing, which causes audible stutter and
    adds latency.

    CATCH-UP BEHAVIOR: if the buffered backlog grows past
    config.CATCHUP_START_MS (meaning audio is arriving faster than we're
    playing it), the callback reads slightly more audio than it needs and
    compresses it down to the requested output length -- effectively
    playing faster until the backlog shrinks back down. This eases back
    toward real-time smoothly. As an absolute last resort (see
    config.HARD_DROP_MS), if the backlog keeps growing anyway, we drop the
    oldest excess outright.

    IMPORTANT: this should NOT play through the same device being captured
    by LoopbackSource, or you get a feedback loop. See config.OUTPUT_DEVICE_NAME.
    """

    def __init__(self, device_name_substring: str | None = None):
        self._pa = pyaudio.PyAudio()
        device_index = self._resolve_device_index(device_name_substring)
        self._lock = threading.Lock()
        self._buffer = bytearray()
        self._hard_drop_bytes = int(OUTPUT_RATE * config.HARD_DROP_MS / 1000) * SAMPLE_WIDTH

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=OUTPUT_RATE,
            output=True,
            output_device_index=device_index,
            stream_callback=self._callback,
        )
        self._stream.start_stream()

    def _speed_factor_for_backlog(self, buffered_bytes: int) -> float:
        buffered_ms = (buffered_bytes / SAMPLE_WIDTH) / OUTPUT_RATE * 1000
        if buffered_ms <= config.CATCHUP_START_MS:
            return 1.0

        # Ramp linearly from 1.0x at CATCHUP_START_MS up to CATCHUP_MAX_SPEED
        # at HARD_DROP_MS, so speed increases smoothly as backlog grows.
        span = max(config.HARD_DROP_MS - config.CATCHUP_START_MS, 1)
        progress = min((buffered_ms - config.CATCHUP_START_MS) / span, 1.0)
        return 1.0 + progress * (config.CATCHUP_MAX_SPEED - 1.0)

    def _callback(self, in_data, frame_count, time_info, status):
        with self._lock:
            # Hard safety net: never let the backlog grow unbounded.
            if len(self._buffer) > self._hard_drop_bytes:
                del self._buffer[: len(self._buffer) - self._hard_drop_bytes]

            speed = self._speed_factor_for_backlog(len(self._buffer))
            input_frames_needed = int(frame_count * speed)
            needed_bytes = input_frames_needed * SAMPLE_WIDTH

            if len(self._buffer) < needed_bytes:
                # Not even enough for normal-speed playback -- take
                # whatever's there and pad the rest with silence.
                raw = bytes(self._buffer)
                self._buffer.clear()
                speed = 1.0  # no catch-up possible when we're this starved
            else:
                raw = bytes(self._buffer[:needed_bytes])
                del self._buffer[:needed_bytes]

        samples = np.frombuffer(raw, dtype=np.int16)

        if speed != 1.0 and len(samples) > 0:
            out_samples = _resample_to_length(samples, frame_count)
        else:
            out_samples = samples

        if len(out_samples) < frame_count:
            out_samples = np.concatenate(
                [out_samples, np.zeros(frame_count - len(out_samples), dtype=np.int16)]
            )

        return (out_samples.tobytes(), pyaudio.paContinue)

    def _resolve_device_index(self, name_substring):
        if not name_substring:
            return None  # None = use system default output device

        name_substring = name_substring.lower()
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0 and name_substring in info["name"].lower():
                return i

        raise RuntimeError(
            f'No output device found matching "{name_substring}". '
            "Run list_devices.py to see available device names."
        )

    def write(self, pcm_bytes: bytes):
        """Non-blocking: queues audio for the callback to play. Returns immediately."""
        with self._lock:
            self._buffer.extend(pcm_bytes)

    def close(self):
        self._stream.stop_stream()
        self._stream.close()
