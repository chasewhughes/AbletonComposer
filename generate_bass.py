import json

def generate_bass_line():
    """
    Generate a half-time techno bass line in G minor
    128 beats total, 8th notes (0.5 duration each)
    This creates 256 total note events (but some are rests)
    """
    notes_list = []

    # Patterns for first half (sparse, building energy)
    patterns_first_half = [
        [31, 0, 38, 0, 31, 0, 41, 0],      # Pattern 1: root focus (sparse)
        [31, 38, 31, 0, 38, 41, 31, 0],    # Pattern 2: adding more movement
        [38, 0, 31, 38, 41, 0, 31, 38],    # Pattern 3: variation with fifths
        [31, 0, 38, 0, 31, 38, 41, 0],     # Pattern 4: transition toward density
    ]

    # Patterns for second half (denser, higher energy)
    patterns_second_half = [
        [31, 38, 31, 38, 41, 31, 38, 41],  # Dense 1: full movement
        [38, 31, 38, 31, 38, 41, 38, 31],  # Dense 2: fifth-focused
        [31, 41, 31, 38, 31, 41, 38, 31],  # Dense 3: fourth variations
        [31, 38, 41, 38, 31, 38, 31, 41],  # Dense 4: complex fills
    ]

    fill_pitches = [31, 33, 34, 36, 38]  # Ascending fill: G→G#→A→Bb→D

    # Process each eighth note position
    for eighth_note_idx in range(256):
        beat_position = eighth_note_idx / 2.0  # Convert to beat position (0.0, 0.5, 1.0, 1.5...)
        beat_num = eighth_note_idx // 2  # Which "beat" (0-127)
        bar_num = beat_num // 8  # Which bar (0-15)
        eighth_in_bar = beat_num % 8  # Position within bar (0-7)
        bar_position = bar_num % 16  # Position in 16-bar cycle (0-15)

        # Check if this is a fill bar (every 16 bars at position 15 = beat 120-127)
        is_fill_bar = (bar_position == 15)

        if is_fill_bar:
            # Fill: ascending sequence G→G#→A→Bb→D
            if eighth_in_bar < len(fill_pitches):
                pitch = fill_pitches[eighth_in_bar]
                velocity = 110 if beat_num < 64 else 115
                notes_list.append({
                    "pitch": pitch,
                    "start_time": beat_position,
                    "duration": 0.5,
                    "velocity": velocity,
                    "mute": False
                })
        else:
            # Regular pattern (not a fill)
            if beat_num < 64:  # First half (beats 0-64): sparse, low velocity
                pattern = patterns_first_half[(bar_num // 2) % len(patterns_first_half)]
                # Gradually increase velocity from 90 to 105
                velocity = 90 + (bar_num // 2) * 2
                velocity = min(velocity, 105)
            else:  # Second half (beats 64-128): dense, higher velocity
                pattern = patterns_second_half[((bar_num - 64) // 2) % len(patterns_second_half)]
                # Gradually increase velocity from 105 to 120
                velocity = 105 + ((bar_num - 64) // 2) * 2
                velocity = min(velocity, 120)

            note = pattern[eighth_in_bar]
            if note > 0:  # 0 represents a rest (skip)
                notes_list.append({
                    "pitch": note,
                    "start_time": beat_position,
                    "duration": 0.5,
                    "velocity": velocity,
                    "mute": False
                })

    return notes_list


if __name__ == "__main__":
    bass_notes = generate_bass_line()

    # Output as JSON
    json_output = json.dumps(bass_notes, indent=2)

    # Print to console
    print(json_output)

    # Also save to file
    with open('/Users/chasehughes/Documents/AbletonComposer/half_time_bass.json', 'w') as f:
        f.write(json_output)

    print(f"\n# Generated {len(bass_notes)} notes total", file=__import__('sys').stderr)
    first_half = [n for n in bass_notes if n['start_time'] < 32]
    second_half = [n for n in bass_notes if n['start_time'] >= 32]
    print(f"# First half (0-64 beats): {len(first_half)} notes", file=__import__('sys').stderr)
    print(f"# Second half (64-128 beats): {len(second_half)} notes", file=__import__('sys').stderr)
    print(f"# Velocity range first half: {min(n['velocity'] for n in first_half)}-{max(n['velocity'] for n in first_half)}", file=__import__('sys').stderr)
    print(f"# Velocity range second half: {min(n['velocity'] for n in second_half)}-{max(n['velocity'] for n in second_half)}", file=__import__('sys').stderr)
