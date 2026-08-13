# Building a standalone Windows executable

This is optional -- most users can just run `python main.py` after
`pip install -r requirements.txt` (see README.md). This doc is only for
producing a `.exe` that doesn't require Python installed, e.g. for a GitHub
Release asset.

**Note:** this must be done on an actual Windows machine (not this repo's
dev container/CI) since it bundles Windows-specific binaries.

## Steps

1. Install PyInstaller in your virtual environment:
   ```
   pip install pyinstaller
   ```

2. Build:
   ```
   pyinstaller --onefile --console --name RealtimeDubber ^
       --hidden-import=pyaudiowpatch ^
       --hidden-import=pycaw.pycaw ^
       --collect-all comtypes ^
       main.py
   ```

   Notes on why these flags exist:
   - `--hidden-import=pyaudiowpatch` / `pycaw.pycaw`: PyInstaller's static
     analysis sometimes misses these because of how they're imported
     dynamically internally. If the built .exe crashes immediately with a
     `ModuleNotFoundError`, that's the fix.
   - `--collect-all comtypes`: `comtypes` generates Python wrapper modules
     for COM interfaces at runtime (a "gen cache") that PyInstaller doesn't
     know about ahead of time. Missing this is the most common cause of the
     built .exe failing on `comtypes.CoInitialize()` or pycaw calls even
     though it worked fine with `python main.py`.

3. Test the built exe BEFORE uploading it anywhere:
   ```
   cd dist
   RealtimeDubber.exe
   ```
   Test on a clean-ish setup if you can (a VM, or at least closing
   VoiceMeeter/other audio tools first) -- a build that only works on the
   exact machine it was built on isn't a useful release.

4. Package for release: the `.exe` alone isn't enough -- users still need
   `.env.example` (to know what to configure) and ideally `list_devices.py`
   isn't usable anymore without Python, so document device-listing some
   other way, or keep `list_devices.py` as a separate small `.exe` too
   (`pyinstaller --onefile list_devices.py`).

   Suggested release zip contents:
   ```
   RealtimeDubber-v0.1.0-windows/
     RealtimeDubber.exe
     ListDevices.exe          (built the same way from list_devices.py)
     .env.example
     README.md
     LICENSE
   ```

## Known risks / things to watch for

- **Antivirus false positives are common** for PyInstaller-built exes,
  especially `--onefile` ones (they self-extract at runtime, which looks
  similar to malware behavior to some heuristic scanners). Warn users about
  this in the release notes, and consider `--onedir` instead of `--onefile`
  if it becomes a recurring complaint (onedir is less prone to false
  positives, at the cost of shipping a folder instead of a single file).
- **This hasn't been done yet for this project** -- the steps above are
  best-effort guidance based on known PyInstaller + comtypes/pycaw pitfalls,
  not a verified working build. If you build this, please open a PR to fix
  anything wrong here and remove this note.
