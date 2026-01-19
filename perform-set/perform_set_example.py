#!/usr/bin/env python3
import argparse
import random
import threading
import time
import math

from client.client import AbletonOSCClient

# --- PROJECT SETTINGS ---
BPM = 132.0
SECONDS_PER_BEAT = 60.0 / BPM
BAR_DURATION = 4.0

# --- TRACK MAP ---
TRACK_INDEX = {
    "1_KICK": 0,
    "2_BASS_ROLL": 1,
    "3_RUMBLE_TOPS": 2,
    "4_HATS_CLOSED": 3,
    "5_HATS_OPEN": 4,
    "6_SYNTH_STAB": 5,
    "7_ATMOS": 6,
    "8_VOCAL": 7,
    "9_RIDE": 8,
    "10_STAB": 9,
    "11_RUMBLE": 10,
    "12_VOX_TEXTURE": 11,
    "13_SWING": 12,
    "14_CRACKLE": 13,
    "15_NOISE": 14
}

SCENE_INDEX = {
    "INTRO": 0, "BUILD_1": 1, "BUILD_2": 2, 
    "TENSION": 3, "DROP": 4, "PEAK": 5, 
    "COOL_DWN": 6, "OUTRO": 7
}

# --- UTILITIES ---
def db_to_vol(db: float) -> float:
    if db <= -70.0: return 0.0
    return max(0.0, min(10 ** (db / 20.0), 1.0))

def sleep_beats(beats: float):
    time.sleep(beats * SECONDS_PER_BEAT)

def set_vol(client, track_key, db):
    val = db_to_vol(db)
    client.send_message("/live/track/set/volume", [TRACK_INDEX[track_key], val])

def set_send(client, track_key, send_id, val):
    # send_id 0 = Reverb A (The Glue)
    client.send_message("/live/track/set/send", [TRACK_INDEX[track_key], send_id, val])

def active_wait(duration_bars, action_func=None):
    total_beats = int(duration_bars * BAR_DURATION)
    for i in range(total_beats):
        if action_func: action_func(i, total_beats)
        sleep_beats(1.0)

def fade_track(client, track_key, start_db, end_db, duration_beats):
    steps = int(duration_beats * 4) 
    for i in range(steps):
        prog = i / steps
        current_db = start_db + (prog * (end_db - start_db))
        set_vol(client, track_key, current_db)
        time.sleep(SECONDS_PER_BEAT / 4)

# --- MIX FIX FUNCTIONS ---

def humanize_groove(client, beat):
    """
    Fixes 'Static' percussion by modulating velocity/volume.
    Target: Swing (13) and Open Hats (5).
    """
    # 1. Swing Layer Drift
    if beat % 2 != 0:
        drift = (random.random() * 1.5) - 0.75
        set_vol(client, "13_SWING", -10.0 + drift)
    
    # 2. Open Hat Movement (Fixes 'Static Sample' critique)
    # Every off-beat, slightly change Open Hat volume
    if (beat + 0.5) % 1 == 0: 
        hat_drift = (random.random() * 1.0) - 0.5
        set_vol(client, "5_HATS_OPEN", -9.0 + hat_drift)

def apply_glue(client):
    """
    Sends elements to Reverb A to fix 'Dry/Detached' Mids.
    """
    print("   > Applying Reverb Glue (placing instruments in the room)...")
    # Send Hats and Stabs to Reverb (0.15 - 0.25 amount)
    set_send(client, "4_HATS_CLOSED", 0, 0.15)
    set_send(client, "5_HATS_OPEN", 0, 0.20)
    set_send(client, "13_SWING", 0, 0.10)
    set_send(client, "6_SYNTH_STAB", 0, 0.25)

# --- ARRANGEMENT ---
def run_set(client):
    print("   ! Initializing Drumcode Protocol v11 (Mix Fix)...")
    
    # 1. INTRO
    print("\n[1] INTRO")
    client.send_message("/live/song/start_playing", [])
    client.send_message("/live/scene/fire", [SCENE_INDEX["INTRO"]])
    
    # Levels
    set_vol(client, "1_KICK", -8.5)
    set_vol(client, "11_RUMBLE", -6.0)
    set_vol(client, "8_VOCAL", -7.0)
    set_vol(client, "14_CRACKLE", -12.0)
    
    # Apply The Glue (Reverb Sends)
    apply_glue(client)
    
    # Ghost Stabs
    set_vol(client, "10_STAB", -70.0) 
    set_send(client, "10_STAB", 0, 1.0)
    set_vol(client, "13_SWING", -70.0)
    
    def intro_ev(beat, total):
        prog = beat / total
        set_vol(client, "7_ATMOS", -25.0 + (prog * 10.0))
        if beat > 16 and beat % 32 == 0:
            set_vol(client, "10_STAB", -15.0)
            threading.Timer(0.5, lambda: set_vol(client, "10_STAB", -70.0)).start()
            
    active_wait(32, intro_ev)

    # 2. BUILD 1 (Alive Transition)
    print("\n[2] BUILD 1: Swing & Glue.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["BUILD_1"]])
    
    threading.Thread(target=fade_track, args=(client, "7_ATMOS", -15.0, -25.0, 16)).start()
    threading.Thread(target=fade_track, args=(client, "13_SWING", -70.0, -10.0, 16)).start()
    
    # Noise Sweep
    set_vol(client, "15_NOISE", -6.0)
    threading.Timer(4.0, lambda: set_vol(client, "15_NOISE", -70.0)).start()
    
    set_vol(client, "12_VOX_TEXTURE", -12.0)
    set_vol(client, "4_HATS_CLOSED", -14.0)
    
    active_wait(16, lambda b, t: humanize_groove(client, b))

    # 3. BUILD 2 (The Lift)
    print("\n[3] BUILD 2: Melody.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["BUILD_2"]])
    set_vol(client, "12_VOX_TEXTURE", -70.0)
    
    # Synth Smooth Entry
    set_vol(client, "6_SYNTH_STAB", -25.0)
    client.send_message("/live/device/set/parameter/value", [TRACK_INDEX["6_SYNTH_STAB"], 1, 1, 0])
    
    def build_ramp(beat, total):
        prog = beat / total
        set_vol(client, "6_SYNTH_STAB", -25.0 + (prog * 17.0))
        client.send_message("/live/device/set/parameter/value", [TRACK_INDEX["6_SYNTH_STAB"], 1, 1, (prog**2)*100])
        humanize_groove(client, beat)
        
    active_wait(32, build_ramp)

    # 4. TENSION (Filtering & Thinning)
    print("\n[4] TENSION: Thinning the Mix.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["TENSION"]])
    
    set_vol(client, "15_NOISE", -6.0)
    threading.Timer(4.0, lambda: set_vol(client, "15_NOISE", -70.0)).start()
    
    def tension_wash(beat, total):
        prog = beat / total
        set_send(client, "8_VOCAL", 0, 0.3 + (prog * 0.7))
        
        # --- MIX FIX: TENSION THINNING ---
        # Instead of High-Pass Filter (which needs mapping), we fade volume
        # of the Low End elements over the last 2 bars.
        if beat > (total - 8):
            # Fade Kick & Rumble to simulate HPF
            fade = 1.0 - ((beat - (total-8)) / 8.0)
            set_vol(client, "1_KICK", -8.5 + (math.log10(max(fade, 0.01)) * 20))
            set_vol(client, "11_RUMBLE", -6.0 + (math.log10(max(fade, 0.01)) * 20))
            
        # THE SILENCE GAP (Absolute Silence at very end)
        if beat >= total - 1:
            set_vol(client, "1_KICK", -70.0)
            set_vol(client, "11_RUMBLE", -70.0)
            set_vol(client, "6_SYNTH_STAB", -70.0)
            set_vol(client, "8_VOCAL", -70.0)
            set_vol(client, "13_SWING", -70.0)
            
    active_wait(16, tension_wash)

    # 5. DROP (Slam it back in)
    print("\n[5] DROP: Impact.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["DROP"]])
    
    # Restore Levels (Bass slams back in after being thinned)
    set_vol(client, "1_KICK", -8.5)
    set_vol(client, "11_RUMBLE", -6.0)
    set_vol(client, "13_SWING", -10.0)
    
    set_vol(client, "8_VOCAL", -70.0)
    set_send(client, "8_VOCAL", 0, 0.0)
    
    active_wait(32, lambda b, t: humanize_groove(client, b))

    # 6. PEAK
    print("\n[6] PEAK: Energy.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["PEAK"]])
    set_vol(client, "9_RIDE", -70.0)
    threading.Thread(target=fade_track, args=(client, "9_RIDE", -70.0, -7.5, 16)).start()
    
    def ride_mod(beat, total):
        if beat > 16:
            cycle = math.sin(beat * math.pi)
            set_vol(client, "9_RIDE", -7.5 + (cycle * 1.5))
        humanize_groove(client, beat)
        
    active_wait(32, ride_mod)

    # 7. COOL DOWN
    print("\n[7] COOL DOWN.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["COOL_DWN"]])
    set_vol(client, "9_RIDE", -70.0)
    set_vol(client, "5_HATS_OPEN", -70.0)
    threading.Thread(target=fade_track, args=(client, "8_VOCAL", -70.0, -7.0, 8)).start()
    
    active_wait(16)

    # 8. OUTRO
    print("\n[8] OUTRO.")
    client.send_message("/live/scene/fire", [SCENE_INDEX["OUTRO"]])
    
    def outro_fade(beat, total):
        prog = beat / total
        vol = -8.5 - (prog * 60.0)
        set_vol(client, "1_KICK", vol)
        set_vol(client, "11_RUMBLE", vol)
        
    active_wait(32, outro_fade)
    print("\nSession Complete.")

if __name__ == "__main__":
    client = AbletonOSCClient("127.0.0.1", 11000)
    run_set(client)