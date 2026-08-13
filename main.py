"""
Entry point. Run this with:  python main.py

Unlike the old chunk-based pipeline, there's no manual silence-detection or
separate translate/TTS steps here -- the Live API handles the whole
audio-in -> translated-audio-out pipeline internally. This script just wires
up the audio devices and keeps the session alive.
"""

import asyncio
import sys

import comtypes

import config
from live_translator import run


def main():
    print(f"Realtime Dubber v{config.__version__}\n")

    if not config.GEMINI_API_KEY:
        print(
            "GEMINI_API_KEY environment variable is not set. "
            "See README.md for how to set it (via a .env file).",
            file=sys.stderr,
        )
        sys.exit(1)

    # COM must be initialized on this thread before pycaw (volume ducking)
    # can be used. Everything in this app runs on the main thread via
    # asyncio, so one call here covers the whole session.
    comtypes.CoInitialize()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopping...")


if __name__ == "__main__":
    main()
