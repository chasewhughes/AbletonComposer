#!/usr/bin/env python3
"""Harmony ear — does the music agree with itself?

Nothing else in the listening loop hears pitch. A render can pass every mix
check while the acid sits on A, the bell rings at 220 Hz and a drone hums at
98 Hz — three roots that do not belong to one chord. That is invisible to a
band-energy metric and glaring to a listener, so it needs its own ear.

What it reads, and why it reads it that way:

  notes       The sounding root, tracked frame by frame and histogrammed into
              pitch classes. Chroma is the textbook answer and it is useless
              here: on dense techno its entropy sits at ~0.98, i.e. every
              pitch class is "present". Tracking the harmonic-sum root instead
              answers which note is being PLAYED, which on a monophonic acid
              line or bass is the question that matters.
  tuning      Percussive sources get the same reading, but it means something
              different: a kick is tuned, not tonal. Measured on the Drumcode
              references the kick lands on a single pitch class 94% of the
              time — so "kick tuned to A +47 cents" is a real, checkable fact,
              and a kick a semitone off the bass is a real, common fault.
  key         Chroma against Krumhansl-Kessler profiles, kept honest by two
              things: a confidence margin measured against the best key with a
              DIFFERENT tonic, and a threshold below which it says "unclear"
              instead of guessing. Validated on the reference corpus by
              agreement between two windows of the same record (4/5); mode
              (major vs minor) flips often enough that it is reported as a
              hint, not a fact.
  agreement   Intervals between the dominant notes of each source, named
              musically, with semitone and tritone pairings flagged — plus
              cents-level detuning between sources sharing a pitch class,
              which is in tune on paper and beats in the room.

Usage:
  .venv-listen/bin/python tools/harmony_ear.py <audio.wav> [--stems] [--json]
"""
import numpy as np
import librosa

PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler key profiles (perceived stability of each scale degree).
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52,
                     5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54,
                     4.75, 3.98, 2.69, 3.34, 3.17])
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# Interval names by semitone distance, and whether the pairing is harsh.
# In techno a minor 7th or a 5th between roots is normal; a semitone or a
# tritone between two sustained roots is the thing that sounds wrong.
INTERVALS = {
    0: ("same pitch class", False), 1: ("minor 2nd", True),
    2: ("major 2nd", False), 3: ("minor 3rd", False), 4: ("major 3rd", False),
    5: ("perfect 4th", False), 6: ("tritone", True), 7: ("perfect 5th", False),
    8: ("minor 6th", False), 9: ("major 6th", False), 10: ("minor 7th", False),
    11: ("major 7th", True),
}

# Sources whose pitch is tuning, not tonality.
PERCUSSIVE_NAMES = {"drums", "drum", "kick", "perc", "hats", "hat", "clap",
                    "snare", "ride", "cymbal", "chat", "ohat"}
MIXTURE_NAMES = {"mix", "master", "full", "render"}

KEY_CONF_MIN = 0.05       # below this the chroma key is reported as unclear
NOTE_SHARE_MIN = 0.20     # a pitch class must hold this much to count as played
CONC_PITCHED_MIN = 0.35   # root tracking must find *some* focus to be usable
# A source this far under the loudest one is inaudible in the room. Reading
# its pitch is fine; letting it raise a CLASH against a part 35 dB louder is
# not — that is a fault nobody can hear, reported with total confidence.
AUDIBLE_DB = 30.0


def hz_to_note(f):
    """(name, octave, cents-off-equal-temperament) for a frequency in Hz."""
    if not f or f <= 0:
        return None, None, 0.0
    midi = 69 + 12 * np.log2(f / 440.0)
    nearest = int(round(midi))
    cents = (midi - nearest) * 100
    return PC_NAMES[nearest % 12], nearest // 12 - 1, float(cents)


def role_of(name):
    n = name.lower()
    if any(p in n for p in PERCUSSIVE_NAMES):
        return "percussive"
    if n in MIXTURE_NAMES:
        return "mixture"
    return "pitched"


def tonalness(y, sr):
    """Fraction of energy that is harmonic rather than percussive (0-1).

    Reported for context, NOT used as a gate: on a mastered techno mix it
    reads 0.7 for the drum stem, because a tuned kick and its rumble are
    genuinely harmonic. Root-tracking concentration is the gate that works.
    """
    if len(y) < sr // 2:
        return 0.0
    h, p = librosa.effects.hpss(y)
    hr = float(np.sqrt(np.mean(h ** 2)))
    pr = float(np.sqrt(np.mean(p ** 2)))
    return float(hr / (hr + pr + 1e-12))


def chroma_vector(y, sr):
    """Energy-weighted, L1-normalized 12-vector of pitch-class content."""
    if len(y) < sr // 4 or float(np.max(np.abs(y))) < 1e-5:
        return np.zeros(12)
    c = librosa.feature.chroma_cqt(y=y, sr=sr, bins_per_octave=36)
    v = c.mean(axis=1)
    return v / (v.sum() + 1e-12)


def detect_key(chroma):
    """(tonic_pc, mode, confidence, ranked) from a chroma vector.

    Confidence is the margin against the best key with a *different* tonic —
    relative and parallel keys share a chroma, so scoring against the overall
    runner-up would always read as uncertain even when the tonic is solid.
    """
    if chroma.sum() <= 0:
        return None, None, 0.0, []
    c = chroma - chroma.mean()
    scored = []
    for pc in range(12):
        for mode, prof in (("major", KK_MAJOR), ("minor", KK_MINOR)):
            p = np.roll(prof, pc)          # profile[0] is the tonic degree
            p = p - p.mean()
            r = float((c @ p) / (np.linalg.norm(c) * np.linalg.norm(p) + 1e-12))
            scored.append((r, pc, mode))
    scored.sort(reverse=True)
    best_r, best_pc, best_mode = scored[0]
    other = next((s for s in scored if s[1] != best_pc), (0.0, 0, ""))
    conf = float(max(0.0, best_r - other[0]))
    ranked = [(f"{PC_NAMES[pc]} {mode}", round(r, 3)) for r, pc, mode in scored[:4]]
    return best_pc, best_mode, conf, ranked


def root_hz(y, sr, fmin=30.0, fmax=1200.0, n_harm=5):
    """Sounding fundamental via harmonic summation over the spectrum.

    A plain spectral peak picks whichever partial is loudest — on a bass with
    a scooped fundamental that is the 2nd harmonic, an octave wrong. Summing
    each candidate's harmonic series instead votes for the true root.
    """
    if len(y) < sr // 8 or float(np.max(np.abs(y))) < 1e-5:
        return 0.0, 0.0
    n_fft = 16384 if len(y) >= 16384 else 4096
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=n_fft // 4))
    mag = S.mean(axis=1)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    lo = np.searchsorted(freqs, fmin)
    hi = np.searchsorted(freqs, fmax)
    if hi <= lo:
        return 0.0, 0.0
    scores = np.zeros(hi - lo)
    for k in range(1, n_harm + 1):
        idx = np.clip(np.searchsorted(freqs, freqs[lo:hi] * k), 0, len(mag) - 1)
        scores += mag[idx] / k          # decay weight: high partials count less
    i = int(np.argmax(scores))
    f0 = float(freqs[lo + i])
    if 0 < i < len(scores) - 1:         # parabolic refine for sub-bin accuracy
        a, b, c = scores[i - 1], scores[i], scores[i + 1]
        d = (a - c) / (2 * (a - 2 * b + c) + 1e-12)
        f0 = float(freqs[lo + i] + d * (freqs[1] - freqs[0]))
    strength = float(scores[i] / (scores.mean() + 1e-12))
    return f0, strength


def root_track(y, sr, hop_s=0.25, fmin=30.0, fmax=1200.0, min_strength=3.0):
    """Follow the sounding root frame by frame and histogram the result."""
    hop = max(1, int(hop_s * sr))
    win = min(len(y), max(hop * 2, int(0.4 * sr)))
    hist = np.zeros(12)
    frames = []
    for s in range(0, max(1, len(y) - win + 1), hop):
        seg = y[s:s + win]
        w = float(np.sqrt(np.mean(seg ** 2)))
        if w < 1e-5:
            continue
        f0, strength = root_hz(seg, sr, fmin=fmin, fmax=fmax)
        if f0 <= 0 or strength < min_strength:
            continue
        name, octv, cents = hz_to_note(f0)
        if name is None:
            continue
        hist[PC_NAMES.index(name)] += w
        frames.append({"t": round(s / sr, 2), "hz": round(f0, 2),
                       "note": f"{name}{octv}", "cents": round(cents, 1)})
    total = hist.sum()
    if total <= 0 or not frames:
        return {"hist": [0.0] * 12, "concentration": 0.0, "top": [],
                "n_frames": 0, "median_cents": 0.0, "frames": []}
    hist /= total
    order = np.argsort(-hist)
    # concentration: share held by the two strongest pitch classes. A
    # monophonic line lands near 1.0; unpitched noise spreads across twelve.
    conc = float(hist[order[0]] + hist[order[1]])
    top_pc = int(order[0])
    cents_top = [f["cents"] for f in frames
                 if PC_NAMES.index(f["note"][:-1]) == top_pc]
    med_cents = float(np.median(cents_top)) if cents_top else 0.0
    spread = float(np.percentile(cents_top, 75) - np.percentile(cents_top, 25)) \
        if len(cents_top) > 3 else 0.0
    # A pitch-swept kick has no single pitch: its root walks a semitone during
    # the decay, so the rounded pitch class flips between neighbours and any
    # interval built on it is fiction. Both guards below have to pass before
    # this source is allowed to participate in a clash claim.
    reliable = abs(med_cents) <= 40 and spread <= 60
    return {
        "hist": [round(float(v), 3) for v in hist],
        "concentration": round(conc, 3),
        "top": [(PC_NAMES[i], round(float(hist[i]), 3))
                for i in order[:4] if hist[i] > 0.02],
        "top_pc": top_pc,
        "n_frames": len(frames),
        "median_cents": round(med_cents, 1),
        "cents_spread": round(spread, 1),
        "pitch_reliable": bool(reliable),
        "frames": frames[:64],
    }


def out_of_key_share(chroma, tonic_pc, mode):
    """Fraction of pitch-class energy outside the detected diatonic scale."""
    if tonic_pc is None or chroma.sum() <= 0:
        return 0.0
    scale = MAJOR_SCALE if mode == "major" else MINOR_SCALE
    members = {(tonic_pc + s) % 12 for s in scale}
    return float(sum(chroma[i] for i in range(12) if i not in members))


def read_source(y, sr, name="mix", role=None):
    """Every pitch reading for one audio source."""
    role = role or role_of(name)
    if float(np.max(np.abs(y))) < 1e-4:
        return {"name": name, "role": role, "silent": True}
    fmin = 30.0 if role in ("mixture", "percussive") or "bass" in name.lower() \
        else 45.0
    notes = root_track(y, sr, fmin=fmin)
    ch = chroma_vector(y, sr)
    tonic, mode, conf, ranked = detect_key(ch)
    f0, f0_strength = root_hz(y, sr, fmin=fmin)
    note, octv, cents = hz_to_note(f0)
    usable = notes["concentration"] >= CONC_PITCHED_MIN and notes["n_frames"] >= 4
    return {
        "name": name,
        "role": role,
        "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)), 1),
        "tonalness": round(tonalness(y, sr), 3),
        "usable_pitch": bool(usable),
        "key": f"{PC_NAMES[tonic]} {mode}" if tonic is not None and
               conf >= KEY_CONF_MIN and role != "percussive" else None,
        "key_confidence": round(conf, 3),
        "key_alternatives": ranked,
        "out_of_key": round(out_of_key_share(ch, tonic, mode), 3),
        "root_hz": round(f0, 2),
        "root_note": f"{note}{octv}" if note else None,
        "root_strength": round(f0_strength, 2),
        "cents_off": round(cents, 1),
        "notes": notes,
        "chroma": [round(float(v), 3) for v in ch],
    }


def played_notes(r):
    """Pitch classes a source actually plays, as [(pc, share)] — the basis of
    every interval check. One dominant class for a bassline, several for a
    chord part; empty when the source has no usable pitch."""
    if r.get("silent") or not r.get("usable_pitch"):
        return []
    if not r["notes"].get("pitch_reliable", True):
        return []
    hist = r["notes"]["hist"]
    return [(i, hist[i]) for i in range(12) if hist[i] >= NOTE_SHARE_MIN]


def audible(readings, floor_db=AUDIBLE_DB):
    """Names of the sources loud enough to be worth judging against."""
    levels = [r.get("rms_db", -99.0) for r in readings if not r.get("silent")]
    if not levels:
        return set()
    top = max(levels)
    return {r["name"] for r in readings
            if not r.get("silent") and r.get("rms_db", -99.0) > top - floor_db}


def agreement(readings):
    """Interval relations between the sources that actually play notes."""
    loud = audible(readings)
    voices = [r for r in readings
              if r.get("role") == "pitched" and played_notes(r)
              and r["name"] in loud]
    perc = [r for r in readings
            if r.get("role") == "percussive" and played_notes(r)
            and r["notes"]["concentration"] >= 0.6 and r["name"] in loud]
    pairs = []

    def relate(a, b, kind):
        an, bn = played_notes(a), played_notes(b)
        if not an or not bn:
            return
        harsh = []
        for pa, sa in an:
            for pb, sb in bn:
                semis = (pa - pb) % 12
                if INTERVALS[semis][1]:
                    harsh.append((PC_NAMES[pa], PC_NAMES[pb],
                                  INTERVALS[semis][0], round(sa * sb, 3)))
        top_a, top_b = a["notes"]["top_pc"], b["notes"]["top_pc"]
        semis = (top_a - top_b) % 12
        detune = None
        if semis == 0:
            detune = round(a["notes"]["median_cents"] -
                           b["notes"]["median_cents"], 1)
        pairs.append({
            "kind": kind, "a": a["name"], "b": b["name"],
            "a_note": PC_NAMES[top_a], "b_note": PC_NAMES[top_b],
            "a_root": a["root_note"], "b_root": b["root_note"],
            "interval": INTERVALS[semis][0], "semitones": semis,
            "harsh": bool(INTERVALS[semis][1]),
            "harsh_pairs": harsh, "detune_cents": detune,
        })

    for i in range(len(voices)):
        for j in range(i + 1, len(voices)):
            relate(voices[i], voices[j], "voices")
    # Kick tuning is only checked against voices in the same register. A kick
    # fundamental at 47 Hz and a pad at 233 Hz are two octaves apart: whatever
    # the interval names say, nothing rubs up there.
    for p in perc:
        for v in voices:
            if v.get("root_hz", 0) and v["root_hz"] <= 250.0:
                relate(p, v, "tuning")
    return pairs


def consensus_key(readings):
    """Tonic of the whole piece.

    Two votes: the pitch classes actually played (weighted by how focused each
    source is) and the chroma key. The played-note vote wins when it is
    decisive, because in techno the bass root is the tonic far more reliably
    than a Krumhansl correlation on a limiter-flattened mix is.
    """
    played = np.zeros(12)
    for r in readings:
        if r.get("role") != "pitched":
            continue
        for pc, share in played_notes(r):
            played[pc] += share * r["notes"]["concentration"]
    chroma_tot = np.zeros(12)
    for r in readings:
        if r.get("silent") or not r.get("chroma") or r.get("role") == "mixture":
            continue
        chroma_tot += np.array(r["chroma"]) * r.get("tonalness", 0.0)
    tonic, mode, conf, ranked = (None, None, 0.0, [])
    if chroma_tot.sum() > 0:
        tonic, mode, conf, ranked = detect_key(chroma_tot / chroma_tot.sum())
    root_tonic = int(np.argmax(played)) if played.sum() > 0 else None
    root_conf = float(played.max() / (played.sum() + 1e-12)) \
        if played.sum() > 0 else 0.0
    return {
        "tonic": PC_NAMES[root_tonic] if root_tonic is not None else
                 (PC_NAMES[tonic] if tonic is not None else None),
        "from": "played notes" if root_tonic is not None else "chroma",
        "root_tonic": PC_NAMES[root_tonic] if root_tonic is not None else None,
        "root_confidence": round(root_conf, 3),
        "chroma_key": f"{PC_NAMES[tonic]} {mode}" if tonic is not None and
                      conf >= KEY_CONF_MIN else None,
        "chroma_confidence": round(conf, 3),
        "alternatives": ranked,
    }


def analyze(sources, sr):
    """sources: {name: mono array}. Returns the full harmonic reading."""
    readings = [read_source(y, sr, name=n) for n, y in sources.items()]
    cons = consensus_key(readings)
    pairs = agreement(readings)
    problems = []

    for p in pairs:
        if p["kind"] == "tuning":
            # Only a semitone is unambiguously wrong between a drum and a
            # bass. A kick a tritone from the root shows up on released
            # Drumcode records; flagging it would be inventing a fault.
            # Check every note the bass plays, not just its most common one: a
            # line that sits on G 47% of the time and G# 27% still puts a
            # semitone under a kick tuned to A for a quarter of the bar.
            semis = [h for h in p["harsh_pairs"]
                     if h[2] == "minor 2nd" and h[3] >= 0.05]
            if p["semitones"] in (1, 11) or semis:
                note = PC_NAMES[[r for r in readings
                                 if r["name"] == p["b"]][0]["notes"]["top_pc"]] \
                    if p["semitones"] in (1, 11) else semis[0][1]
                problems.append(
                    f"KICK/BASS RUB: {p['a']} is tuned to {p['a_note']} "
                    f"({p['a_root']}), {p['b']} plays {note} — a semitone "
                    f"apart in the same octave. Retune the drum or move the "
                    f"part; a sidechain will duck it, not fix it.")
        elif p["harsh"]:
            problems.append(
                f"CLASH: {p['a']} plays {p['a_note']} against {p['b']} "
                f"{p['b_note']} — a {p['interval']} between two sustained "
                f"roots.")
        elif p["harsh_pairs"] and p["kind"] == "voices":
            worst = max(p["harsh_pairs"], key=lambda h: h[3])
            if worst[3] >= 0.10:
                problems.append(
                    f"CLASH (secondary): {p['a']} {worst[0]} against {p['b']} "
                    f"{worst[1]} — a {worst[2]}, present {worst[3]:.0%} of "
                    f"the time.")
        if p["detune_cents"] is not None and abs(p["detune_cents"]) > 25:
            problems.append(
                f"DETUNED: {p['a']} and {p['b']} are both {p['a_note']} but "
                f"{abs(p['detune_cents']):.0f} cents apart — they will beat.")

    loud = audible(readings)
    tonic = cons.get("root_tonic")
    if tonic:
        tonic_pc = PC_NAMES.index(tonic)
        for r in readings:
            if r.get("role") != "pitched" or not played_notes(r) or \
                    r["name"] not in loud:
                continue
            outside = [PC_NAMES[pc] for pc, _ in played_notes(r)
                       if (pc - tonic_pc) % 12 not in MINOR_SCALE and
                       (pc - tonic_pc) % 12 not in MAJOR_SCALE]
            if outside:
                problems.append(
                    f"OUT OF SCALE: {r['name']} plays {', '.join(outside)} — "
                    f"outside any diatonic scale on {tonic}.")
    for r in readings:
        if r.get("silent") or not r.get("usable_pitch") or \
                r["name"] not in loud:
            continue
        n = r["notes"]
        c, spread = n["median_cents"], n.get("cents_spread", 0.0)
        if spread > 60:
            continue                 # a pitch-swept source has no one pitch
        if abs(c) > 30:
            problems.append(
                f"OFF PITCH: {r['name']} sits {c:+.0f} cents from "
                f"{PC_NAMES[n['top_pc']]} — retune the sample.")
    return {"sources": readings, "consensus": cons, "pairs": pairs,
            "problems": problems}


def render_table(h):
    """The harmonic reading as text for the report."""
    L = []
    c = h.get("consensus") or {}
    if c.get("tonic"):
        L.append(f"tonic **{c['tonic']}** (from {c['from']}, confidence "
                 f"{c['root_confidence']:.2f}); chroma key "
                 f"{c.get('chroma_key') or 'unclear'} "
                 f"(margin {c['chroma_confidence']:.2f})")
    L.append(f"{'source':8s}{'role':>11s}{'plays':>22s}{'root':>8s}"
             f"{'Hz':>9s}{'cents':>7s}{'focus':>7s}")
    for r in h["sources"]:
        if r.get("silent"):
            L.append(f"{r['name']:8s}{'silent':>11s}")
            continue
        plays = ", ".join(f"{PC_NAMES[pc]} {s:.0%}" for pc, s in played_notes(r))
        if not plays:
            plays = "swept/unstable" if r["notes"].get("n_frames") and \
                not r["notes"].get("pitch_reliable", True) else "-"
        L.append(f"{r['name']:8s}{r['role']:>11s}{plays[:22]:>22s}"
                 f"{str(r['root_note']):>8s}{r['root_hz']:9.1f}"
                 f"{r['notes']['median_cents']:+7.0f}"
                 f"{r['notes']['concentration']:7.2f}")
    for p in h["pairs"]:
        extra = f"  ({p['detune_cents']:+.0f} cents apart)" \
            if p["detune_cents"] is not None else ""
        mark = "  <-- harsh" if p["harsh"] else ""
        tag = "tuning" if p["kind"] == "tuning" else "voices"
        L.append(f"  [{tag}] {p['a']} {p['a_note']} -> {p['b']} {p['b_note']}: "
                 f"{p['interval']}{extra}{mark}")
    return "\n".join(L)


def main():
    import argparse
    import json
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--stems", action="store_true",
                    help="separate first and read each stem (cached)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    sr = 44100
    y, _ = librosa.load(a.audio, sr=sr, mono=True)
    sources = {"mix": y}
    if a.stems:
        import stems as stems_mod
        s = stems_mod.separate(a.audio, sr=sr)
        s["other"] = s.get("other", 0) + s.pop("vocals", 0)
        sources.update({k: s[k] for k in ("drums", "bass", "other")})
    h = analyze(sources, sr)
    if a.json:
        print(json.dumps(h, indent=1))
        return
    print(render_table(h))
    if h["problems"]:
        print("\nproblems:")
        for p in h["problems"]:
            print(f"  - {p}")
    else:
        print("\nno harmonic conflicts detected.")


if __name__ == "__main__":
    main()
