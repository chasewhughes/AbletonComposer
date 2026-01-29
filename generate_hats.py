#!/usr/bin/env python3
"""Generate 8 humanized hi-hat patterns for techno track."""

import json
import random

def add_note(notes, start_time, velocity, pitch=60, duration=0.2, mute=False):
    """Add a note to the notes list."""
    notes.append({
        "pitch": pitch,
        "start_time": round(start_time, 4),
        "duration": duration,
        "velocity": max(1, min(127, int(velocity))),
        "mute": mute
    })

def vary(base_min, base_max, variation=5):
    """Return a random velocity within range plus variation."""
    base = random.randint(base_min, base_max)
    return base + random.randint(-variation, variation)

def get_beat_type(beat_pos):
    """Determine beat type from position within bar (0-3.75)."""
    pos_in_beat = beat_pos % 1.0
    beat_num = int(beat_pos) % 4

    # Downbeats (beat 1 and 3)
    if pos_in_beat == 0 and beat_num in [0, 2]:
        return "downbeat"
    # Offbeats (the "and" of each beat)
    elif pos_in_beat == 0.5:
        return "offbeat"
    # Weak positions (beats 2 and 4)
    elif pos_in_beat == 0:
        return "weak"
    # Weakest (16th notes between)
    else:
        return "weakest"

# ============== S1: Tight ==============
def generate_s1():
    notes = []
    total_beats = 128

    for i in range(total_beats * 4):  # 16th notes
        beat_pos = i * 0.25
        bar = int(beat_pos // 4) + 1

        beat_type = get_beat_type(beat_pos)

        if beat_type == "downbeat":
            vel = vary(95, 105, 5)
        elif beat_type == "weak":
            vel = vary(70, 80, 5)
        elif beat_type == "offbeat":
            vel = vary(80, 90, 5)
        else:  # weakest
            vel = vary(65, 75, 5)

        add_note(notes, beat_pos, vel)

    # Ghost notes: sparse, every 4 bars
    for bar in range(1, 33):
        if bar % 4 == 0:
            # Add a couple ghost notes in that bar
            bar_start = (bar - 1) * 4
            ghost_positions = [0.125, 0.875, 2.375]
            for gp in random.sample(ghost_positions, 2):
                add_note(notes, bar_start + gp, random.randint(30, 40))

    # 8-bar fills: subtle 32nd runs at bars 8, 16, 24, 32
    fill_bars = [8, 16, 24, 32]
    for bar in fill_bars:
        fill_start = (bar - 1) * 4 + 3.5  # Last half beat of bar
        for j in range(4):  # 4 32nd notes
            add_note(notes, fill_start + j * 0.125, random.randint(50, 60))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S2: Drive ==============
def generate_s2():
    notes = []
    total_beats = 128

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        beat_type = get_beat_type(beat_pos)

        if beat_type == "downbeat":
            vel = vary(100, 110, 5)
        elif beat_type == "weak":
            vel = vary(75, 85, 5)
        elif beat_type == "offbeat":
            vel = vary(85, 95, 5)
        else:
            vel = vary(70, 80, 5)

        add_note(notes, beat_pos, vel)

    # Ghost notes every 2 bars
    for bar in range(1, 33):
        if bar % 2 == 0:
            bar_start = (bar - 1) * 4
            ghost_positions = [0.125, 0.375, 0.875, 1.625, 2.125, 2.875, 3.375]
            for gp in random.sample(ghost_positions, 3):
                add_note(notes, bar_start + gp, random.randint(25, 45))

    # More intense fills at bars 8 and 16
    for bar in [8, 16]:
        fill_start = (bar - 1) * 4 + 3.0
        for j in range(8):  # 8 32nd notes
            add_note(notes, fill_start + j * 0.125, random.randint(55, 70))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S3: Intense ==============
def generate_s3():
    notes = []
    total_beats = 128
    total_bars = 32

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        bar = int(beat_pos // 4) + 1
        beat_type = get_beat_type(beat_pos)

        # Linear velocity increase from bar 1 to 32
        progress = (bar - 1) / (total_bars - 1)
        vel_offset = progress * 20  # 20 velocity increase over the track

        if beat_type == "downbeat":
            vel = vary(85, 95, 5) + vel_offset
        elif beat_type == "weak":
            vel = vary(70, 80, 5) + vel_offset
        elif beat_type == "offbeat":
            vel = vary(75, 85, 5) + vel_offset
        else:
            vel = vary(65, 75, 5) + vel_offset

        add_note(notes, beat_pos, vel)

    # Ghost notes every bar in second half (bars 17-32)
    for bar in range(17, 33):
        bar_start = (bar - 1) * 4
        ghost_positions = [0.125, 0.375, 0.875, 1.125, 1.875, 2.125, 2.875, 3.125, 3.375]
        for gp in random.sample(ghost_positions, random.randint(2, 4)):
            add_note(notes, bar_start + gp, random.randint(30, 45))

    # 32nd note rolls before bars 17, 25, 32
    roll_before_bars = [17, 25, 32]
    for bar in roll_before_bars:
        roll_start = (bar - 2) * 4 + 3.5
        for j in range(4):
            add_note(notes, roll_start + j * 0.125, random.randint(60, 75))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S4: Vacuum (Breakdown) ==============
def generate_s4():
    notes = []
    total_beats = 128

    for i in range(total_beats * 4):
        beat_pos = i * 0.25

        # Skip every other 16th for sparse pattern
        sixteenth_index = i % 4
        if sixteenth_index in [1, 3]:  # Skip positions 2 and 4 of each beat
            if random.random() > 0.3:  # 70% chance to skip
                continue

        vel = vary(50, 70, 5)
        add_note(notes, beat_pos, vel)

    # Very few ghost notes - maybe 4-5 total
    ghost_beats = random.sample(range(8, 120, 8), 4)
    for gb in ghost_beats:
        add_note(notes, gb + 0.125, random.randint(25, 35))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S5: False Drop ==============
def generate_s5():
    notes = []
    total_beats = 128

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        beat_type = get_beat_type(beat_pos)

        # First half subdued, second half opens up
        if beat_pos < 64:
            if beat_type == "downbeat":
                vel = vary(60, 80, 5)
            elif beat_type == "weak":
                vel = vary(50, 65, 5)
            elif beat_type == "offbeat":
                vel = vary(55, 70, 5)
            else:
                vel = vary(45, 60, 5)
        else:
            if beat_type == "downbeat":
                vel = vary(95, 105, 5)
            elif beat_type == "weak":
                vel = vary(75, 85, 5)
            elif beat_type == "offbeat":
                vel = vary(85, 95, 5)
            else:
                vel = vary(70, 80, 5)

        add_note(notes, beat_pos, vel)

    # Transition fill at beat 64
    fill_start = 63.0
    for j in range(8):
        vel = 50 + j * 8  # Rising velocity
        add_note(notes, fill_start + j * 0.125, vel)

    # Ghost notes in second half
    for bar in range(17, 33):
        bar_start = (bar - 1) * 4
        ghost_positions = [0.125, 0.875, 2.125]
        for gp in random.sample(ghost_positions, 2):
            add_note(notes, bar_start + gp, random.randint(30, 45))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S6: Peak ==============
def generate_s6():
    notes = []
    total_beats = 192

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        bar = int(beat_pos // 4) + 1
        beat_type = get_beat_type(beat_pos)

        if beat_type == "downbeat":
            vel = vary(115, 127, 5)
        elif beat_type == "weak":
            vel = vary(100, 110, 5)
        elif beat_type == "offbeat":
            vel = vary(105, 115, 5)
        else:
            vel = vary(95, 105, 5)

        add_note(notes, beat_pos, vel)

    # Lots of ghost notes - potential on every beat
    for beat in range(total_beats):
        if random.random() > 0.4:  # 60% chance per beat
            ghost_pos = beat + random.choice([0.125, 0.375, 0.625, 0.875])
            add_note(notes, ghost_pos, random.randint(35, 50))

    # 32nd note rolls every 8 bars
    for bar in range(8, 49, 8):
        roll_start = (bar - 1) * 4 + 3.0
        for j in range(8):
            add_note(notes, roll_start + j * 0.125, random.randint(70, 90))

    # Occasional doubles (two hits close together)
    double_beats = random.sample(range(16, 180, 4), 15)
    for db in double_beats:
        add_note(notes, db + 0.0625, random.randint(60, 80))  # 64th note after

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S7: Evolve ==============
def generate_s7():
    notes = []
    total_beats = 192

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        beat_type = get_beat_type(beat_pos)

        if beat_type == "downbeat":
            vel = vary(110, 122, 5)
        elif beat_type == "weak":
            vel = vary(95, 105, 5)
        elif beat_type == "offbeat":
            vel = vary(100, 112, 5)
        else:
            vel = vary(90, 100, 5)

        add_note(notes, beat_pos, vel)

    # Polyrhythmic ghost notes - every 5 16ths instead of 4
    ghost_interval = 5 * 0.25  # 1.25 beats
    ghost_time = 0.125
    while ghost_time < total_beats:
        add_note(notes, ghost_time, random.randint(35, 50))
        ghost_time += ghost_interval

    # Different fill patterns - triplet-based fills
    for bar in range(8, 49, 8):
        fill_start = (bar - 1) * 4 + 3.0
        # Triplet feel (6 notes in 1 beat)
        for j in range(6):
            add_note(notes, fill_start + j * (1.0/6), random.randint(65, 85))

    # Different doubles pattern
    for beat in range(0, total_beats, 7):  # Every 7 beats
        if beat < total_beats - 1:
            add_note(notes, beat + 0.5 + 0.0625, random.randint(55, 75))

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== S8: Minimal (Outro) ==============
def generate_s8():
    notes = []
    total_beats = 128

    for i in range(total_beats * 4):
        beat_pos = i * 0.25
        beat_type = get_beat_type(beat_pos)

        # Steady, professional velocities
        if beat_type == "downbeat":
            vel = vary(95, 100, 3)  # Less variation
        elif beat_type == "weak":
            vel = vary(85, 90, 3)
        elif beat_type == "offbeat":
            vel = vary(90, 95, 3)
        else:
            vel = vary(82, 88, 3)

        add_note(notes, beat_pos, vel)

    # No ghost notes - clean for DJ mixout

    return {"notes": sorted(notes, key=lambda x: x["start_time"])}

# ============== Main ==============
def main():
    random.seed(42)  # For reproducibility, remove for true random

    patterns = [
        ("hats_s1.json", "S1-Hats-Tight", generate_s1),
        ("hats_s2.json", "S2-Hats-Drive", generate_s2),
        ("hats_s3.json", "S3-Hats-Intense", generate_s3),
        ("hats_s4.json", "S4-Hats-Vacuum", generate_s4),
        ("hats_s5.json", "S5-Hats-FalseDrop", generate_s5),
        ("hats_s6.json", "S6-Hats-Peak", generate_s6),
        ("hats_s7.json", "S7-Hats-Evolve", generate_s7),
        ("hats_s8.json", "S8-Hats-Minimal", generate_s8),
    ]

    base_path = "/Users/chasehughes/Documents/AbletonComposer"

    for filename, name, generator in patterns:
        data = generator()
        filepath = f"{base_path}/{filename}"

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        note_count = len(data["notes"])
        print(f"Generated {name}: {note_count} notes -> {filepath}")

    print("\nAll 8 hi-hat patterns generated successfully!")

if __name__ == "__main__":
    main()
