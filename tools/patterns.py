"""Expression engine: articulation transforms that make patterns breathe.

Everything the old generators couldn't say: microtiming (real offsets baked
into start_time), velocity contours, accents, ghosts (probability < 1),
per-repeat variation (velocity_deviation), and 303 slides (note overlap).

All functions take/return lists of note dicts compatible with add_notes_v2:
  {pitch, start_time, duration, velocity, probability, velocity_deviation}
Times are in beats.
"""
import random


def note(pitch, start, dur, vel, prob=1.0, vdev=0):
    return {"pitch": int(pitch), "start_time": round(float(start), 4),
            "duration": round(float(dur), 4), "velocity": int(vel),
            "probability": float(prob), "velocity_deviation": int(vdev)}


def ms_to_beats(ms, bpm):
    return ms / 1000.0 * bpm / 60.0


# Groove templates: microtiming offset in ms for each 16th position in a bar.
# Positive = late (laid back), negative = early (pushed).
GROOVES = {
    "straight": [0] * 16,
    # classic MPC-style swing: off-16ths land late
    "swing_58": [0, 14, 0, 14] * 4,
    # pushed hats: off-8ths slightly early, off-16ths late — nervous drive
    "push_pull": [0, 10, -8, 12] * 4,
    # hawtin-tight: nearly straight, hair of lateness on 2nd 16th
    "tight": [0, 5, 0, 3] * 4,
}


def apply_groove(notes, groove, bpm, jitter_ms=2.0, rng=None):
    """Bake groove offsets (+ small human jitter) into start times."""
    rng = rng or random
    out = []
    for n in notes:
        pos16 = int(round(n["start_time"] * 4)) % 16
        off = groove[pos16] + rng.uniform(-jitter_ms, jitter_ms)
        t = max(0.0, n["start_time"] + ms_to_beats(off, bpm))
        out.append({**n, "start_time": round(t, 4)})
    return out


def accent(notes, positions, boost=22):
    """Boost velocity on given 16th positions (per bar)."""
    out = []
    for n in notes:
        pos16 = int(round(n["start_time"] * 4)) % 16
        v = n["velocity"] + (boost if pos16 in positions else 0)
        out.append({**n, "velocity": max(1, min(127, v))})
    return out


def acid_line(steps, root, bpm, bars, slide_overlap=0.06, base_vel=88,
              accent_vel=124, rng=None):
    """303-style line from a 16-step pattern, repeated with evolution.

    steps: list of 16 entries, each None (rest) or a dict:
      {deg: semitone offset from root, acc: bool, slide: bool, oct: -1/0/1}
    Slides are real note OVERLAP — the next note starts before this one ends,
    which triggers legato glide on a mono synth with glide time > 0.
    """
    rng = rng or random
    notes = []
    grid = 0.25
    for bar in range(bars):
        for i, st in enumerate(steps):
            if st is None:
                continue
            t = bar * 4 + i * grid
            pitch = root + st.get("deg", 0) + 12 * st.get("oct", 0)
            vel = accent_vel if st.get("acc") else base_vel
            dur = grid * 0.55
            if st.get("slide"):
                # find next sounding step to overlap into
                j = next((k for k in range(i + 1, i + 5)
                          if steps[k % 16] is not None), i + 1)
                dur = (j - i) * grid + slide_overlap
            notes.append(note(pitch, t, dur, vel,
                              vdev=rng.choice([0, 0, -6, -10])))
    return notes


def four_floor(bpm, bars, vel=127, ghost_prob=0.0, pitch=60):
    """Kick on every beat; optional ghost kick (probability) on 4a."""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            notes.append(note(pitch, bar * 4 + beat, 0.95, vel if beat == 0 else vel - 7))
        if ghost_prob > 0:
            notes.append(note(pitch, bar * 4 + 3.75, 0.2, 70, prob=ghost_prob))
    return notes


def offbeat_hats(bpm, bars, vel=96, sixteenth_fill=True):
    """Open-hat off-8ths + quieter 16th ticks with per-repeat variation."""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            t = bar * 4 + beat
            notes.append(note(42, t + 0.5, 0.18, vel, vdev=-8))       # off-8th
            if sixteenth_fill:
                notes.append(note(42, t + 0.25, 0.09, vel - 34, prob=0.85, vdev=-12))
                notes.append(note(42, t + 0.75, 0.09, vel - 28, prob=0.92, vdev=-12))
    return notes


def open_offbeats(bpm, bars, vel=98, pitch=60):
    """Open hat on every off-8th — the techno pulse-widener."""
    return [note(pitch, bar * 4 + beat + 0.5, 0.45, vel, vdev=-8)
            for bar in range(bars) for beat in range(4)]


def closed_ticks(bpm, bars, vel=64, pitch=60):
    """Quiet 16th ticks with dropout probability — motion, not wall."""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            t = bar * 4 + beat
            notes.append(note(pitch, t + 0.25, 0.12, vel, prob=0.85, vdev=-14))
            notes.append(note(pitch, t + 0.75, 0.12, vel + 6, prob=0.92, vdev=-14))
    return notes


def sparse_perc(bpm, bars, pitch=60, density=0.35, rng=None):
    """Signature perc hits on odd 16ths, sparse and probabilistic."""
    rng = rng or random
    notes = []
    for bar in range(bars):
        for pos in (1.75, 2.25, 3.25):
            if rng.random() < density:
                notes.append(note(pitch, bar * 4 + pos, 0.4,
                                  rng.randint(70, 108), prob=0.9, vdev=-10))
    return notes
