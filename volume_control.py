"""
Controls the SYSTEM MASTER volume (not per-app) via Windows Core Audio.

Why system-wide and not per-app for this MVP?
Ducking a single application's volume requires enumerating per-process audio
sessions (AudioSessionManager2), which only makes sense once we're also doing
per-app CAPTURE. Since this MVP captures the whole system's output, ducking
the whole system's output is the consistent choice. Phase 2 (per-app capture)
will pair with per-app ducking.
"""

from pycaw.pycaw import AudioUtilities

import config


def _get_volume_interface():
    # AudioUtilities.GetSpeakers() returns an AudioDevice wrapper (pycaw
    # 2023+), not a raw COM pointer -- so we go through its .EndpointVolume
    # property instead of manually calling .Activate() ourselves.
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


def duck() -> float:
    """Lowers system volume, returns the original level so it can be restored."""
    vol = _get_volume_interface()
    original_level = vol.GetMasterVolumeLevelScalar()
    vol.SetMasterVolumeLevelScalar(original_level * config.DUCK_VOLUME_FACTOR, None)
    return original_level


def restore(original_level: float):
    vol = _get_volume_interface()
    vol.SetMasterVolumeLevelScalar(original_level, None)
