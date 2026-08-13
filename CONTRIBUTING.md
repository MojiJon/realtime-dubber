# Contributing

Thanks for considering contributing. A bit of context first:

## This project was built almost entirely with AI assistance

The original author is learning frontend/full-stack development and used
Claude (Anthropic's AI) to build essentially this whole codebase through an
iterative, conversational process -- describe the goal, get code, run it,
report the error, get a fix, repeat. That means:

- The architecture reflects reasonable-but-not-expert decisions made
  incrementally, not a from-scratch design by someone with deep Windows
  audio or asyncio experience.
- It has been tested on exactly one machine, one audio setup (VoiceMeeter
  Banana + a Rapoo headset), and a handful of English-to-Persian sessions.
  It has NOT been tested with per-app audio routing edge cases, different
  Windows versions, other languages, or under sustained multi-hour use.
- Some fixes were reactive (fix whatever error showed up in the terminal)
  rather than the result of a full design review. There's a decent chance
  some of these fixes are papering over a better underlying fix.

None of that is a reason to distrust the code -- it works, and the reasoning
behind each decision is documented in comments -- but it IS a reason more
eyes on it would help a lot. If you spot something that was clearly the
"quick fix" rather than the "right fix," a PR (or even just an issue
explaining what's better) is very welcome.

## Ways to help

Roughly in order of impact, see the "Known limitations" section in
[README.md](README.md) for details on each:

1. **Test it on your own setup** and file issues for anything that breaks.
   This is genuinely the most valuable contribution right now -- the app
   has had very limited real-world exposure.
2. **Per-app audio capture** using Windows' Process Loopback Capture API,
   so the app can target one specific game/application instead of all
   system audio.
3. **Per-app volume ducking** via `AudioSessionManager2` / `pycaw`, to pair
   with the above.
4. **A GUI** (system tray app, at minimum) instead of the current console
   script.
5. **Better resampling** (swap the numpy linear interpolation for
   `scipy.signal.resample_poly` or similar).
6. **Tests.** Even basic unit tests around device-name resolution, the
   catch-up speed calculation, or the reconnect logic would help a lot,
   given how much of this is otherwise only verified by manually running it.

## Reporting bugs

Please include:
- Your Windows version, Python version, and audio setup (VoiceMeeter? plain
  VB-Cable? neither?)
- The exact contents of your `config.py` overrides / `.env` (**redact your
  API key**)
- Full terminal output/traceback, not just the last line

## Code style

Nothing formal is enforced yet. Match the existing style: docstrings/comments
explain *why* a decision was made, not just what the code does -- this
project leans on that heavily since a lot of the non-obvious tradeoffs
(decoupled capture/playback, catch-up speedup, session resumption) aren't
self-explanatory from the code alone.
