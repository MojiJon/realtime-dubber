"""
Run this once to see the exact names of your audio devices:

    python list_devices.py

For OUTPUT_DEVICE_NAME (.env): use a name from "OUTPUT (playback) devices".
For INPUT_DEVICE_NAME (.env): use a name from "LOOPBACK-CAPTURABLE devices"
-- this is the list that matters if you're routing audio through a mixer
like VoiceMeeter, since it shows what CAN be loopback-captured, which isn't
always the same list as plain playback devices.
"""

import pyaudiowpatch as pyaudio

pa = pyaudio.PyAudio()

print("=== OUTPUT (playback) devices ===")
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}")

print("\n=== INPUT (recording) devices ===")
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")

print("\n=== LOOPBACK-CAPTURABLE devices (use these for INPUT_DEVICE_NAME) ===")
for loopback in pa.get_loopback_device_info_generator():
    print(f"  [{loopback['index']}] {loopback['name']}")

pa.terminate()
