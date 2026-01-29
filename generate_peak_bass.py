#!/usr/bin/env python3
"""
Generate two high-energy 192-beat rolling bass patterns in G minor for peak techno scenes.
"""

import json
import random

# G minor scale pitches
G1 = 31
A = 33
Bb = 34
C = 36
D = 38
Eb = 39
F = 41
G2 = 43

# Pattern constants
TOTAL_BEATS = 192
NOTES_PER_BEAT = 4
TOTAL_NOTES = TOTAL_BEATS * NOTES_PER_BEAT  # 768 notes
DURATION = 0.25

def generate_s6_peak_bass():
    """
    Pattern 1: S6-Bass-Peak - Maximum energy
    - Velocities 110-127 (high energy)
    - Primary motion: G1(31) → D(38) → F(41), with A(33), Bb(34), C(36) accents
    - Octave jump to G2(43) every 8 bars (32 beats)
    - Build fills using ascending scale every 16 bars
    """
    notes = []

    # Primary pitches for the rolling pattern
    primary_sequence = [G1, G1, D, G1, F, G1, D, G1]  # 8-note rolling pattern
    accent_pitches = [A, Bb, C]
    ascending_scale = [G1, A, Bb, C, D, Eb, F, G2]

    for i in range(TOTAL_NOTES):
        start_time = i * DURATION
        beat = i // NOTES_PER_BEAT
        bar = beat // 4
        position_in_bar = i % 16  # 16 sixteenth notes per bar
        position_in_8bars = beat % 32
        position_in_16bars = beat % 64

        # Determine pitch
        # Check for octave jump (every 8 bars = 32 beats, on the downbeat)
        if position_in_8bars == 0 and i % 4 == 0:
            pitch = G2
        # Check for ascending fill (last 2 beats of every 16 bars)
        elif position_in_16bars >= 62:  # Last 2 beats of 16-bar phrase
            fill_position = (beat - (bar // 16 * 64 + 62)) * 4 + (i % 4)
            if fill_position < 0:
                fill_position = i % 8
            pitch = ascending_scale[fill_position % len(ascending_scale)]
        # Regular rolling pattern with occasional accents
        else:
            base_pitch = primary_sequence[i % len(primary_sequence)]
            # Add accent pitches on certain 16th note positions for variation
            if position_in_bar in [5, 11, 13] and random.random() < 0.4:
                pitch = random.choice(accent_pitches)
            else:
                pitch = base_pitch

        # Velocity: 110-127 range, with emphasis on downbeats
        if i % 4 == 0:  # Downbeat
            velocity = random.randint(120, 127)
        elif i % 4 == 2:  # Off-beat
            velocity = random.randint(115, 124)
        else:
            velocity = random.randint(110, 120)

        notes.append({
            "pitch": pitch,
            "start_time": start_time,
            "duration": DURATION,
            "velocity": velocity,
            "mute": False
        })

    return notes


def generate_s7_evolve_bass():
    """
    Pattern 2: S7-Bass-Evolve - Evolved variation
    - Velocities 105-120 (slightly varied)
    - DIFFERENT rhythmic grouping: alternate between 5/16 feel and regular
    - More chromatic movement using Eb(39) and Bb(34)
    - Different fill patterns than Pattern 1
    """
    notes = []

    # Chromatic-heavy sequence for evolved feel
    chromatic_sequence = [G1, Bb, G1, Eb, G1, D, Bb, G1, Eb, G1]  # 10-note pattern for 5/16 feel
    regular_sequence = [G1, D, Bb, G1, F, Eb, D, G1]  # 8-note pattern

    # Descending fill (different from Pattern 1's ascending)
    descending_fill = [G2, F, Eb, D, C, Bb, A, G1]

    # Syncopated accent pattern
    syncopated_accents = [Eb, Bb, D, Eb, F, Bb]

    for i in range(TOTAL_NOTES):
        start_time = i * DURATION
        beat = i // NOTES_PER_BEAT
        bar = beat // 4
        position_in_bar = i % 16
        position_in_8bars = beat % 32
        position_in_16bars = beat % 64

        # Alternate between 5/16 feel (bars 0-3, 8-11, etc.) and regular (bars 4-7, 12-15, etc.)
        use_five_feel = (bar % 8) < 4

        # Determine pitch
        # Different octave jump pattern: every 8 bars but on beat 2, not beat 1
        if position_in_8bars == 2 and i % 4 == 0:
            pitch = G2
        # Different fill: descending on last 3 beats of every 16 bars
        elif position_in_16bars >= 61:  # Last 3 beats
            fill_idx = (i - ((bar // 16) * 256 + 244)) % len(descending_fill)
            if fill_idx < 0:
                fill_idx = i % len(descending_fill)
            pitch = descending_fill[fill_idx % len(descending_fill)]
        # 5/16 feel section
        elif use_five_feel:
            # Use 10-note pattern creating 5/16 groupings
            pitch = chromatic_sequence[i % len(chromatic_sequence)]
            # Extra chromatic accents
            if position_in_bar in [3, 7, 9, 14]:
                pitch = syncopated_accents[i % len(syncopated_accents)]
        # Regular section with chromatic movement
        else:
            pitch = regular_sequence[i % len(regular_sequence)]
            # Chromatic passing tones
            if position_in_bar in [2, 6, 10, 14] and random.random() < 0.5:
                pitch = random.choice([Eb, Bb])

        # Velocity: 105-120 range with different accent pattern
        if i % 5 == 0:  # 5/16 accent feel
            velocity = random.randint(115, 120)
        elif i % 4 == 0:  # Regular downbeat
            velocity = random.randint(112, 118)
        elif i % 3 == 0:  # Syncopated accent
            velocity = random.randint(110, 117)
        else:
            velocity = random.randint(105, 115)

        notes.append({
            "pitch": pitch,
            "start_time": start_time,
            "duration": DURATION,
            "velocity": velocity,
            "mute": False
        })

    return notes


def main():
    # Set seed for reproducibility while still having variation
    random.seed(42)

    # Generate Pattern 1: S6-Bass-Peak
    s6_notes = generate_s6_peak_bass()
    s6_data = {
        "name": "S6-Bass-Peak",
        "description": "Maximum energy rolling bass - G minor - 192 beats",
        "total_beats": TOTAL_BEATS,
        "total_notes": len(s6_notes),
        "scale": "G minor",
        "notes": s6_notes
    }

    # Generate Pattern 2: S7-Bass-Evolve
    random.seed(43)  # Different seed for variation
    s7_notes = generate_s7_evolve_bass()
    s7_data = {
        "name": "S7-Bass-Evolve",
        "description": "Evolved variation rolling bass - G minor - 192 beats",
        "total_beats": TOTAL_BEATS,
        "total_notes": len(s7_notes),
        "scale": "G minor",
        "notes": s7_notes
    }

    # Save files
    s6_path = "/Users/chasehughes/Documents/AbletonComposer/peak_bass_s6.json"
    s7_path = "/Users/chasehughes/Documents/AbletonComposer/peak_bass_s7.json"

    with open(s6_path, 'w') as f:
        json.dump(s6_data, f, indent=2)
    print(f"Saved S6-Bass-Peak to {s6_path}")
    print(f"  Total notes: {len(s6_notes)}")

    with open(s7_path, 'w') as f:
        json.dump(s7_data, f, indent=2)
    print(f"Saved S7-Bass-Evolve to {s7_path}")
    print(f"  Total notes: {len(s7_notes)}")

    # Verify note counts
    print(f"\nVerification:")
    print(f"  Expected notes per pattern: {TOTAL_NOTES}")
    print(f"  S6 actual: {len(s6_notes)}")
    print(f"  S7 actual: {len(s7_notes)}")

    # Sample output for verification
    print(f"\nS6 first 8 notes (first 2 beats):")
    for note in s6_notes[:8]:
        print(f"  pitch={note['pitch']}, start={note['start_time']}, vel={note['velocity']}")

    print(f"\nS7 first 8 notes (first 2 beats):")
    for note in s7_notes[:8]:
        print(f"  pitch={note['pitch']}, start={note['start_time']}, vel={note['velocity']}")


if __name__ == "__main__":
    main()
