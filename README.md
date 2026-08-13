# Realtime Dubber

📖 [فارسی](README.fa.md)

> **⚠️ Status: early prototype, built almost entirely with AI assistance (Claude).**
> The core pipeline works end-to-end, but it's had limited real-world testing
> (one user, one machine, one audio setup). It needs testing across different
> hardware/games, code review from people who know Windows audio internals
> and asyncio well, and the unfinished features below built out.
> **Contributions, bug reports, and even full rewrites of rough parts are
> very welcome** -- see [CONTRIBUTING.md](CONTRIBUTING.md).

A Windows desktop app that captures your system's audio in real time and
translates it live using Google's **Gemini Live Translate** model
(`gemini-3.5-live-translate-preview`). The model does speech-to-speech
translation directly -- audio in, translated audio out -- so there's no
separate STT → translate → TTS pipeline to manage.

**Use case this was built for:** understanding a game or app that's speaking
a language you don't know, without alt-tabbing to a translator. It captures
whatever's coming out of your speakers, translates it, and plays the
translation back (while briefly ducking the original audio's volume).

## How it works

```
System audio (loopback capture, 16kHz mono)
    -> streamed continuously to Gemini Live over a WebSocket
    -> translated audio comes back (24kHz mono)
    -> played back with a jitter buffer + catch-up speedup
    -> original audio volume ducked while translation plays
```

Key design points, in case you're picking this up cold:

- **Capture and network I/O are decoupled.** Audio capture runs in its own
  PortAudio callback thread and just fills a queue; sending to the network
  happens independently. This avoids audio getting silently dropped if the
  network is briefly slow (see `audio_io.py`).
- **Playback is also decoupled**, with a size-bounded jitter buffer and a
  "catch-up" mechanism: if translated audio arrives faster than it's being
  played (common -- the model can burst several chunks at once), the
  playback callback gently speeds up (up to 30% faster) to ease back toward
  real-time instead of drifting further and further behind, or jarringly
  skipping audio.
- **The WebSocket session auto-reconnects.** Gemini Live sessions cap out
  around 10-15 minutes; the app uses `session_resumption` and
  `context_window_compression` so it can run indefinitely, reconnecting
  transparently when the server closes the connection.
- **Audio feedback loop avoidance.** Because this captures system-wide
  loopback audio, if translated speech played through the same device being
  captured, it would get captured and re-translated forever. The README's
  setup section covers routing translated audio to a separate virtual
  device (VoiceMeeter or VB-Cable) to avoid this.

## Setup

1. Windows 10/11, Python 3.10+.
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your Gemini API key:
   ```
   GEMINI_API_KEY=your-key-here
   ```
   If you're behind a restrictive network/firewall, uncomment the
   `HTTPS_PROXY` line and point it at your proxy.

## ⚠️ Required step: avoiding the audio feedback loop

Since this app captures **all** system output audio, if translated speech
plays through the same device being captured, it gets captured again and
re-translated -- an infinite loop that causes runaway lag and duplicate
translations.

### Option A: You use VoiceMeeter (Banana/Potato)

No extra install needed -- VoiceMeeter already has virtual devices for this:

1. Make sure your game/app's audio is routed into `VoiceMeeter Input`
   (either as your Windows default playback device, or selected directly in
   the app).
2. Run `python list_devices.py`. Find the exact name of `VoiceMeeter Input`
   under "LOOPBACK-CAPTURABLE devices", and `VoiceMeeter AUX Input` under
   "OUTPUT devices".
3. In `.env`:
   ```
   INPUT_DEVICE_NAME=VoiceMeeter Input
   OUTPUT_DEVICE_NAME=VoiceMeeter Aux Input
   ```
4. In VoiceMeeter itself, on the `Voicemeeter AUX Input` strip, enable only
   the `A1` output button (not `B1`) -- so only you hear the translation,
   and it doesn't leak into your mic bus.

This way `A1` (your headset) mixes game audio + translated audio for you to
hear, but capture only ever sees the pre-mix game audio -- no loop.

### Option B: No mixer installed

1. Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (free).
2. Run `python list_devices.py`, find `CABLE Input`.
3. In `.env`: `OUTPUT_DEVICE_NAME=CABLE Input`
4. To hear it: **Sound Control Panel > Recording tab > double-click
   `CABLE Output` > Listen tab > check "Listen to this device" > pick your
   real headphones/speakers.**

## Running

```
python main.py
```

## Configuration (`config.py`)

| Setting | What it does |
|---|---|
| `TARGET_LANGUAGE_CODE` | BCP-47 target language code (e.g. `"fa"` for Persian). See [supported languages](https://ai.google.dev/gemini-api/docs/live-api/live-translate#supported-languages). |
| `ECHO_TARGET_LANGUAGE` | Whether the model repeats audio that's already in the target language. |
| `INPUT_DEVICE_NAME` | Substring match for the loopback-capturable device to capture from. `None` = default output device. |
| `OUTPUT_DEVICE_NAME` | Substring match for where translated audio plays. **Must differ from the captured device** (see above). |
| `DUCK_VOLUME_FACTOR` | How much to lower system volume while translated speech plays. |
| `CATCHUP_START_MS` / `CATCHUP_MAX_SPEED` / `HARD_DROP_MS` | Tuning for the playback catch-up mechanism described above. |

## Known limitations / what needs work

This is where contributors would help most:

- **Whole-system capture, not per-app.** Currently captures everything
  going through the target device, not just one game/app. Windows has a
  [Process Loopback Capture API](https://learn.microsoft.com/en-us/windows/win32/coreaudio/process-loopback-capture) (Win10 2004+) that could isolate a single
  process's audio -- unimplemented, would be a solid contribution.
- **System-wide volume ducking, not per-app.** `volume_control.py` lowers
  the Windows master volume, not a specific app's/process's volume. Doesn't
  interact well with mixers like VoiceMeeter, where the "real" volume
  control is the mixer's own faders. Per-process ducking via
  `AudioSessionManager2` (through `pycaw`) would fix this, and would pair
  naturally with per-app capture above.
- **Preview model.** `gemini-3.5-live-translate-preview` is, as the name
  says, a preview -- expect quota limits, behavior changes, or the model
  name changing over time. Check [Google's model list](https://ai.google.dev/gemini-api/docs/models)
  if you hit a 404 on the model name.
- **Resampling quality.** `audio_io.py` uses simple linear interpolation
  (numpy) for resampling instead of a proper resampling library (e.g.
  `scipy.signal.resample_poly` or `soxr`). Good enough for speech, but a
  quality upgrade would be easy to add without much architectural change.
- **No GUI.** It's a console app right now. A simple system-tray app with a
  language picker and mute toggle would make this far more usable day-to-day.
- **No automated tests.** None of the audio pipeline, reconnect logic, or
  device resolution has test coverage. Given the amount of Windows-specific
  audio/COM code, this would need either mocking PyAudio/pycaw or
  integration tests that only run on Windows CI.
- **Windows/WASAPI only.** Everything here is Windows-specific
  (`pyaudiowpatch`, `pycaw`, COM). A cross-platform capture backend is a
  bigger undertaking and probably a separate effort.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started on any of these.

## License

MIT -- see [LICENSE](LICENSE).
