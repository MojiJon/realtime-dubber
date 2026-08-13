"""
Central config. Change values here instead of hunting through the code.
"""

import os

from dotenv import load_dotenv

load_dotenv()

__version__ = "0.1.0"

# --- Gemini ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Live speech-to-speech translation model -- audio in, translated audio out,
# no separate STT/translate/TTS steps needed.
GEMINI_MODEL = "gemini-3.5-live-translate-preview"

# --- Network / proxy ---
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

# --- Translation ---
# BCP-47 language code. Persian = "fa". Full list:
# https://ai.google.dev/gemini-api/docs/live-api/live-translate#supported-languages
TARGET_LANGUAGE_CODE = "fa"

# If the game/app is ALREADY speaking Persian, should the model repeat it
# back (True) or stay silent (False)? False avoids a weird double-audio
# effect when the source is already in your target language.
ECHO_TARGET_LANGUAGE = False

# --- Volume ducking ---
DUCK_VOLUME_FACTOR = 0.35   # multiply current system volume by this while translated speech plays

# --- Playback buffer / catch-up ---
# If translated audio arrives faster than real-time (common -- the model can
# send several chunks in a quick burst), it queues up and playback slowly
# drifts further and further behind the live transcript.
#
# Instead of just dropping audio when that happens (which sounds like a
# jarring skip), we gently SPEED UP playback once the backlog crosses
# CATCHUP_START_MS, scaling up to CATCHUP_MAX_SPEED as the backlog grows.
# A 10-20% speed change is barely noticeable; it lets playback ease back
# toward real-time smoothly instead of jumping.
CATCHUP_START_MS = 400     # backlog (ms) at which we start speeding up
CATCHUP_MAX_SPEED = 1.3    # never play more than 30% faster (keeps pitch shift subtle)

# Absolute safety net: if the backlog somehow keeps growing even with
# catch-up speedup (e.g. a long burst that outpaces even max speed), drop
# the oldest excess once it passes this point so latency can't grow forever.
HARD_DROP_MS = 3000

# --- Input device for CAPTURING the source audio (e.g. the game) ---
# If you route app audio through a mixer like VoiceMeeter before it reaches
# your speakers, leave this pointing at the mixer's virtual INPUT (the
# pre-mix point), not your physical speakers/headset. That way we capture
# only the original game audio -- not our own translated speech mixed back in.
#   INPUT_DEVICE_NAME=VoiceMeeter Input
# Leave as None to just loopback-capture your default Windows output device.
INPUT_DEVICE_NAME = os.environ.get("INPUT_DEVICE_NAME")

# --- Output device for TRANSLATED speech ---
# CRITICAL: if this stays None, translated audio plays through your default
# speakers -- which are also what we're capturing via loopback. That means
# our own translated speech gets captured and re-translated, creating a
# feedback loop (you'll see repeated/duplicate translations and growing lag).
#
# Fix: install VB-Audio Virtual Cable (https://vb-audio.com/Cable/), then set
# this to a substring of its device name so translated speech goes there
# instead of your real speakers. Run list_devices.py to see exact names.
#   OUTPUT_DEVICE_NAME=CABLE Input
OUTPUT_DEVICE_NAME = os.environ.get("OUTPUT_DEVICE_NAME")

