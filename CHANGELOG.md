# Changelog

## v0.1.0 -- Initial release (2026-08-13)

First public release. This is an early prototype, built almost entirely
with AI assistance -- see [CONTRIBUTING.md](CONTRIBUTING.md) for context on
what that means for code quality and what still needs work.

### What works
- Real-time system audio capture (WASAPI loopback) via `pyaudiowpatch`
- Live speech-to-speech translation via Gemini Live API
  (`gemini-3.5-live-translate-preview`)
- Decoupled capture/network/playback pipeline (no audio drops from network
  jitter)
- Playback catch-up (gentle speedup) instead of jarring skips when
  translated audio arrives faster than real-time
- Automatic reconnect with session resumption (sessions no longer die after
  ~10-15 minutes)
- System volume ducking while translated speech plays
- Configurable input/output device targeting, for routing through
  VoiceMeeter or VB-Cable to avoid audio feedback loops

### Known limitations (see README for full list)
- Whole-system audio capture only, not per-application
- System-wide volume ducking only, not per-application
- Console app only, no GUI
- Windows/WASAPI only
- Uses a preview model (`gemini-3.5-live-translate-preview`), subject to
  Google changing quotas/behavior/naming over time
- Tested on exactly one machine/audio setup so far

### Installation
See [README.md](README.md) (or [README.fa.md](README.fa.md) for Persian) --
this release ships as source code; you'll need Python 3.10+ and the
dependencies in `requirements.txt`.
