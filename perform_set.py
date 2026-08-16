#!/usr/bin/env python3
"""
Drop It (Charlotte de Witte Rework) - Live Performance Script
Uses AbletonOSC for live scene triggering and automation.

BPM: 136
Style: Hard Techno

Scenes:
0 - Main Drop
1 - Buildup
2 - Breakdown
3 - Build
4 - Drop 2
5 - Outro
"""

import sys
import time
import math
import threading

# live_bridge puts the vendored AbletonOSC/pythonosc on sys.path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_bridge import db_to_live_fader

from pythonosc.udp_client import UDPClient
from pythonosc.osc_message_builder import OscMessageBuilder

# --- PROJECT SETTINGS ---
BPM = 136.0
SECONDS_PER_BEAT = 60.0 / BPM
BAR_DURATION = 4.0  # beats per bar

# --- TRACK MAP ---
TRACK_INDEX = {
    "KICK": 0,
    "SNARE": 1,
    "FX": 2,
    "ATMOS": 3,
    "HIHAT": 4,
    "BASS": 5,
    "SYNTH": 6,
}

# --- SCENE MAP ---
SCENE_INDEX = {
    "MAIN_DROP": 0,
    "BUILDUP": 1,
    "BREAKDOWN": 2,
    "BUILD": 3,
    "DROP_2": 4,
    "OUTRO": 5,
}

# --- OSC CLIENT WRAPPER ---
class AbletonOSCClient:
    def __init__(self, host="127.0.0.1", port=11000):
        self.client = UDPClient(host, port)

    def send_message(self, address, args=None):
        """Send an OSC message to Ableton Live."""
        if args is None:
            args = []
        builder = OscMessageBuilder(address=address)
        for arg in args:
            builder.add_arg(arg)
        msg = builder.build()
        self.client.send(msg)


# --- UTILITIES ---
def db_to_vol(db: float) -> float:
    """Convert dB to Ableton's 0.0-1.0 fader value (Live taper, 0.85 = 0 dB)."""
    return db_to_live_fader(db)


def sleep_beats(beats: float):
    """Sleep for a duration measured in beats."""
    time.sleep(beats * SECONDS_PER_BEAT)


def sleep_bars(bars: float):
    """Sleep for a duration measured in bars."""
    time.sleep(bars * BAR_DURATION * SECONDS_PER_BEAT)


def set_vol(client, track_key, db):
    """Set track volume in dB."""
    val = db_to_vol(db)
    client.send_message("/live/track/set/volume", [TRACK_INDEX[track_key], val])


def set_send(client, track_key, send_id, val):
    """Set track send level (0-1)."""
    client.send_message("/live/track/set/send", [TRACK_INDEX[track_key], send_id, val])


def mute_track(client, track_key, muted=True):
    """Mute or unmute a track."""
    client.send_message("/live/track/set/mute", [TRACK_INDEX[track_key], 1 if muted else 0])


def fire_scene(client, scene_key):
    """Fire a scene by name."""
    client.send_message("/live/scene/fire", [SCENE_INDEX[scene_key]])


def active_wait(duration_bars, action_func=None):
    """Wait for a duration while optionally executing an action each beat."""
    total_beats = int(duration_bars * BAR_DURATION)
    for i in range(total_beats):
        if action_func:
            action_func(i, total_beats)
        sleep_beats(1.0)


def fade_track(client, track_key, start_db, end_db, duration_beats):
    """Fade a track volume over time."""
    steps = int(duration_beats * 4)
    for i in range(steps):
        prog = i / steps
        current_db = start_db + (prog * (end_db - start_db))
        set_vol(client, track_key, current_db)
        time.sleep(SECONDS_PER_BEAT / 4)


# --- PERFORMANCE MACROS ---

def intro_sequence(client):
    """
    INTRO: Sparse buildup with atmospheric elements.
    Duration: 16 bars
    """
    print("\n[1] INTRO - Sparse Buildup")
    fire_scene(client, "BUILDUP")

    # Initial levels
    set_vol(client, "KICK", -12.0)
    set_vol(client, "BASS", -10.0)
    set_vol(client, "HIHAT", -14.0)
    mute_track(client, "SNARE", True)
    mute_track(client, "SYNTH", True)

    # Add reverb send to hats
    set_send(client, "HIHAT", 0, 0.25)

    def intro_automation(beat, total):
        prog = beat / total
        # Gradually increase kick volume
        set_vol(client, "KICK", -12.0 + (prog * 4.0))
        # Bring in bass
        set_vol(client, "BASS", -10.0 + (prog * 3.0))

    active_wait(16, intro_automation)


def buildup_sequence(client):
    """
    BUILDUP: Add more elements, increase energy.
    Duration: 16 bars
    """
    print("\n[2] BUILDUP - Rising Energy")

    # Unmute snare and synth
    mute_track(client, "SNARE", False)
    set_vol(client, "SNARE", -15.0)

    def buildup_automation(beat, total):
        prog = beat / total
        # Bring snare up
        set_vol(client, "SNARE", -15.0 + (prog * 7.0))
        # Increase hi-hat
        set_vol(client, "HIHAT", -14.0 + (prog * 6.0))

    active_wait(16, buildup_automation)


def main_drop_sequence(client):
    """
    MAIN DROP: Full energy, all elements.
    Duration: 32 bars
    """
    print("\n[3] MAIN DROP - Full Energy")
    fire_scene(client, "MAIN_DROP")

    # Full levels
    set_vol(client, "KICK", -8.0)
    set_vol(client, "SNARE", -8.0)
    set_vol(client, "HIHAT", -8.0)
    set_vol(client, "BASS", -7.0)

    # Unmute synth
    mute_track(client, "SYNTH", False)
    set_vol(client, "SYNTH", -10.0)
    set_send(client, "SYNTH", 0, 0.30)  # Reverb
    set_send(client, "SYNTH", 1, 0.15)  # Delay

    def drop_groove(beat, total):
        # Add subtle volume movement for "alive" mix
        if beat % 8 == 0:
            set_vol(client, "SYNTH", -10.0 + (math.sin(beat * 0.5) * 1.5))

    active_wait(32, drop_groove)


def breakdown_sequence(client):
    """
    BREAKDOWN: Strip back elements for tension.
    Duration: 8 bars
    """
    print("\n[4] BREAKDOWN - Tension")
    fire_scene(client, "BREAKDOWN")

    # Strip back
    mute_track(client, "KICK", True)
    mute_track(client, "SNARE", True)
    set_vol(client, "HIHAT", -20.0)
    set_vol(client, "BASS", -15.0)
    set_vol(client, "SYNTH", -12.0)

    # Increase reverb
    set_send(client, "SYNTH", 0, 0.50)
    set_send(client, "BASS", 0, 0.20)

    active_wait(8)


def build_sequence(client):
    """
    BUILD: Rising tension before drop.
    Duration: 8 bars
    """
    print("\n[5] BUILD - Rising Tension")
    fire_scene(client, "BUILD")

    # Start bringing elements back
    mute_track(client, "KICK", False)
    mute_track(client, "SNARE", False)

    set_vol(client, "KICK", -15.0)
    set_vol(client, "SNARE", -18.0)

    def build_automation(beat, total):
        prog = beat / total
        # Rising kick
        set_vol(client, "KICK", -15.0 + (prog * 7.0))
        # Rising snare
        set_vol(client, "SNARE", -18.0 + (prog * 10.0))
        # Rising bass
        set_vol(client, "BASS", -15.0 + (prog * 8.0))
        # Rising hats
        set_vol(client, "HIHAT", -20.0 + (prog * 12.0))
        # Reduce reverb
        set_send(client, "SYNTH", 0, 0.50 - (prog * 0.20))

    active_wait(8, build_automation)


def drop2_sequence(client):
    """
    DROP 2: Second drop, peak energy.
    Duration: 32 bars
    """
    print("\n[6] DROP 2 - Peak Energy")
    fire_scene(client, "DROP_2")

    # Full levels
    set_vol(client, "KICK", -7.0)
    set_vol(client, "SNARE", -7.0)
    set_vol(client, "HIHAT", -7.0)
    set_vol(client, "BASS", -6.0)
    set_vol(client, "SYNTH", -9.0)

    # Normal reverb
    set_send(client, "SYNTH", 0, 0.30)
    set_send(client, "BASS", 0, 0.10)

    active_wait(32)


def outro_sequence(client):
    """
    OUTRO: Fade out elements.
    Duration: 16 bars
    """
    print("\n[7] OUTRO - Fade Out")
    fire_scene(client, "OUTRO")

    def outro_fade(beat, total):
        prog = beat / total
        fade_db = prog * 60.0  # Fade to silence

        set_vol(client, "KICK", -7.0 - fade_db)
        set_vol(client, "SNARE", -7.0 - fade_db)
        set_vol(client, "HIHAT", -7.0 - fade_db)
        set_vol(client, "BASS", -6.0 - fade_db)
        set_vol(client, "SYNTH", -9.0 - fade_db)

    active_wait(16, outro_fade)


# --- MAIN PERFORMANCE ---
def run_set(client):
    """Run the full performance set."""
    print("=" * 50)
    print("Drop It (Charlotte de Witte Rework)")
    print("Live Performance Script")
    print("BPM:", BPM)
    print("=" * 50)

    # Start playback
    client.send_message("/live/song/start_playing", [])

    # Run through the arrangement
    intro_sequence(client)
    buildup_sequence(client)
    main_drop_sequence(client)
    breakdown_sequence(client)
    build_sequence(client)
    drop2_sequence(client)
    outro_sequence(client)

    # Stop playback
    client.send_message("/live/song/stop_playing", [])

    print("\n" + "=" * 50)
    print("Performance Complete!")
    print("=" * 50)


if __name__ == "__main__":
    print("Connecting to Ableton Live via OSC...")
    client = AbletonOSCClient("127.0.0.1", 11000)

    try:
        run_set(client)
    except KeyboardInterrupt:
        print("\nPerformance interrupted by user.")
        client.send_message("/live/song/stop_playing", [])
