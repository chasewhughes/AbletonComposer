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
              which is in tune on paper and beats in the room. Every one of
              those claims is weighted by whether the two sources actually
              SOUND AT THE SAME TIME (see `overlap`); a dissonance between
              parts that take turns is a melodic move, not a clash, and two
              notes that never coincide cannot beat.

Two measurement failures this file has already shipped, both caught by the
Method rule in tools/LISTENING.md (run it over the reference corpus first):

  * `agreement` compared pitch classes and nothing else. On v4e_tuned it
    reported "drums and bass are both A but 33 cents apart — they will beat".
    The bass on that render is written on off-8ths, in the kick's gaps: the
    two share about 95 ms at a stretch, and a 33-cent detuning at 55 Hz beats
    at 1.06 Hz, a 0.95 s cycle. They never sound together long enough for one
    beat cycle to complete. Fixed by `note_activity` / `overlap`.
  * `root_hz` interpolated its spectral peak on LINEAR magnitude. Measured on
    synthetic tones at 40-80 Hz that costs 7 cents of error at the median and
    15 at the worst — the same size as the detunings it was being used to
    prove. Interpolating on LOG magnitude instead, and refining the estimate
    from the harmonics (a cents error at the 4th harmonic is a quarter of a
    cents error at the fundamental), takes the median to 0.1 cents. Every
    cents claim now carries the interval it was measured to and is dropped
    when the interval will not support it.

Usage:
  .venv-listen/bin/python tools/harmony_ear.py <audio.wav> [--stems] [--json]
"""
import numpy as np
import librosa
import scipy.signal as sig

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

# --- temporal overlap ------------------------------------------------------
# Two parts only clash if they are both sounding. Activity is measured in a
# band around each source's own note rather than broadband, because a drum
# stem is "on" ~100% of the time (hats, reverb tails) and a broadband gate
# would call every kick/bass pair simultaneous. The band is +-5 semitones;
# the numbers below barely move between +-3 and +-7, which is how you know
# the gate is measuring the music and not the filter.
ACT_HOP = 0.005           # s per activity sample
ACT_BAND_SEMIS = 5.0
ACT_DROP_DB = 18.0        # a source is sounding within this of its own p95
# Share of the *sparser* source's sounding time that is shared with the other.
SUSTAINED_MIN = 0.50      # above this the two genuinely sound together
ALTERNATING_MAX = 0.20    # below this they take turns

# --- cents claims ----------------------------------------------------------
DETUNE_MIN_CENTS = 25.0   # a detuning smaller than this is not worth naming
OFF_PITCH_CENTS = 30.0    # ... measured against the TRACK's tuning, not A440
# Cents readings come with a measured half-width (see root_hz_ci). A claim
# whose interval is wider than this is not a claim, it is a shrug.
CENTS_CI_MAX = 15.0
CENTS_CI_FLOOR = 3.0      # never report an interval tighter than the bench
# Beating is a rate, not a state: a detuning of d cents at f Hz beats at
# f*(2**(d/1200)-1) Hz. You cannot hear a periodic swell whose period is
# longer than the time the two parts share, so a "they will beat" claim needs
# at least this many complete beat cycles inside ONE continuous overlap.
BEAT_CYCLES_MIN = 1.0


def hz_to_note(f, tune_cents=0.0):
    """(name, octave, cents) for a frequency, against a reference pitch of
    A = 440 * 2**(tune_cents/1200).

    `tune_cents` is not decoration. Nothing in this corpus is at concert
    pitch — five of the nine Drumcode references sit 30-45 cents off A440 on
    every stem at once. Rounding those to the nearest A440 semitone puts the
    note within a few cents of the boundary, so once the pitch estimator got
    accurate enough to resolve that, single physical notes started splitting
    across two adjacent pitch classes and the tool invented minor 2nds
    between a source and itself. The reference is measured per render (see
    `tuning_from_frames`) and everything quantises against it.
    """
    if not f or f <= 0:
        return None, None, 0.0
    midi = 69 + 12 * np.log2(f / 440.0) - tune_cents / 100.0
    nearest = int(round(midi))
    cents = (midi - nearest) * 100
    return PC_NAMES[nearest % 12], nearest // 12 - 1, float(cents)


def tuning_from_frames(frames, default=0.0):
    """Reference pitch of the whole render, in cents from A440.

    A circular mean over the 100-cent semitone, energy-weighted, across every
    tracked frame of every source. Circular because the quantity wraps: a
    frame reading +48 cents and one reading -48 are 4 cents apart, and a
    plain mean of those two would say 0 — the exact halfway point they are
    furthest from.
    """
    if not frames:
        return default
    ang = np.array([f["cents"] for f in frames]) * 2 * np.pi / 100.0
    w = np.array([f.get("w", 1.0) for f in frames])
    if w.sum() <= 0:
        return default
    z = np.sum(w * np.exp(1j * ang)) / w.sum()
    if abs(z) < 0.15:          # no agreement at all — do not invent a tuning
        return default
    return float(np.angle(z) * 100.0 / (2 * np.pi))


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


def _log_peak(mag, i):
    """Fractional-bin offset of a spectral peak, interpolated on LOG magnitude.

    The window transform is Gaussian-ish in dB, so a parabola through three
    log-magnitude bins lands on the true peak; a parabola through three LINEAR
    magnitudes does not. This file used to do the linear version, and at
    40-80 Hz — where one 16384-point bin spans 84 cents — that alone cost a
    median 7.0 cents and a worst case 14.5 cents on synthetic tones of known
    pitch. Those are the same numbers the tool was reporting as findings.
    Log interpolation takes the same signals to a median 0.4 cents.
    """
    if i <= 0 or i >= len(mag) - 1:
        return 0.0
    a, b, c = (np.log(mag[i - 1] + 1e-12), np.log(mag[i] + 1e-12),
               np.log(mag[i + 1] + 1e-12))
    den = a - 2 * b + c
    if abs(den) < 1e-12:
        return 0.0
    return float(np.clip(0.5 * (a - c) / den, -0.5, 0.5))


def _mean_spectrum(y, sr, cap=65536):
    """Averaged magnitude spectrum, with n_fft grown to fit the segment.

    n_fft used to be pinned at 16384 no matter how much audio it was handed,
    so passing a longer window bought nothing at all — the extra seconds were
    averaged across frames, which cancels noise but cannot buy resolution. A
    3 s frame at n_fft=65536 resolves 0.67 Hz where 16384 resolves 2.7 Hz.
    """
    n = 1 << int(np.floor(np.log2(max(2048, min(len(y), cap)))))
    n = max(2048, min(n, 1 << int(np.floor(np.log2(max(2048, len(y)))))))
    S = np.abs(librosa.stft(y, n_fft=n, hop_length=max(1, n // 4)))
    return S.mean(axis=1), librosa.fft_frequencies(sr=sr, n_fft=n)


def root_hz_ci(y, sr, fmin=30.0, fmax=1200.0, n_harm=5, refine_harm=8,
               hz_cap=2000.0, tol_cents=40.0, prominence=4.0):
    """(f0, strength, cents_ci, n_partials) — the root and how well it is known.

    Two stages, because they answer different questions:

    1. Harmonic summation over the bin grid picks the right OCTAVE. A plain
       spectral peak takes whichever partial is loudest — on a bass with a
       scooped fundamental that is the 2nd harmonic, an octave wrong.
    2. The coarse answer is then refined off the partials. Locating the k-th
       harmonic to within e Hz locates the fundamental to within e/k Hz, so
       the 4th harmonic of a 55 Hz bass at 220 Hz pins the root four times
       better than the 55 Hz fundamental can, in a far emptier part of the
       spectrum. Each partial has to be a prominent local maximum (4x the
       local median) within `tol_cents` of where it is predicted, or it is
       some other source's energy and is dropped.

    `cents_ci` is the half-width the partials agree to. It is a precision
    interval, not a correctness guarantee: when two different sources sit a
    few Hz apart this function returns whichever is louder, measures it
    tightly, and the interval says nothing about that. See `overlap` — that
    is the check that catches the case where two parts are both present.
    """
    if len(y) < sr // 8 or float(np.max(np.abs(y))) < 1e-5:
        return 0.0, 0.0, 0.0, 0
    mag, freqs = _mean_spectrum(y, sr)
    df = float(freqs[1] - freqs[0])
    lo = np.searchsorted(freqs, fmin)
    hi = np.searchsorted(freqs, fmax)
    if hi <= lo:
        return 0.0, 0.0, 0.0, 0
    scores = np.zeros(hi - lo)
    for k in range(1, n_harm + 1):
        idx = np.clip(np.searchsorted(freqs, freqs[lo:hi] * k), 0, len(mag) - 1)
        scores += mag[idx] / k          # decay weight: high partials count less
    i = int(np.argmax(scores))
    f0 = float(freqs[lo + i])
    strength = float(scores[i] / (scores.mean() + 1e-12))

    ests, wts = [], []
    for k in range(1, refine_harm + 1):
        fk = f0 * k
        if fk > min(hz_cap, freqs[-1] * 0.98):
            break
        b = int(round(fk / df))
        s, e = max(1, b - 2), min(len(mag) - 1, b + 3)
        if e <= s:
            continue
        j = s + int(np.argmax(mag[s:e]))
        if j <= 0 or j >= len(mag) - 1:
            continue
        if not (mag[j] >= mag[j - 1] and mag[j] >= mag[j + 1]):
            continue
        w = max(8, int(round(fk * 0.25 / df)))
        floor = float(np.median(mag[max(0, j - w):min(len(mag), j + w + 1)]))
        if mag[j] < prominence * (floor + 1e-12):
            continue                    # noise floor, not a partial
        f_meas = (j + _log_peak(mag, j)) * df
        c = 1200 * np.log2(max(f_meas, 1e-9) / fk)
        if abs(c) > tol_cents:
            continue                    # not this note's harmonic
        ests.append(c)
        wts.append(float(mag[j]) * k)   # loud partials and high ones count more
    if not ests:
        # Nothing prominent enough to interpolate: the bin-grid answer stands,
        # and half a bin is the honest interval on it.
        return f0, strength, float(1200 * np.log2(1 + 0.5 * df / max(f0, 1e-9))), 0
    ests = np.array(ests)
    wts = np.array(wts) / np.sum(wts)
    c_hat = float(np.sum(ests * wts))
    if len(ests) > 1:
        var = float(np.sum(wts * (ests - c_hat) ** 2)) * len(ests) / (len(ests) - 1)
        ci = 2.0 * float(np.sqrt(var))
    else:
        ci = 25.0                       # one partial agrees with itself for free
    return (f0 * 2 ** (c_hat / 1200), strength,
            max(ci, CENTS_CI_FLOOR), len(ests))


def root_hz(y, sr, fmin=30.0, fmax=1200.0, n_harm=5):
    """(f0, strength). Thin wrapper on root_hz_ci for callers that only want
    the pitch — tools/oneshot_bank.py reads one-shot fundamentals this way."""
    f0, strength, _ci, _n = root_hz_ci(y, sr, fmin=fmin, fmax=fmax,
                                       n_harm=n_harm)
    return f0, strength


def note_activity(y, sr, f_center, semis=ACT_BAND_SEMIS, hop_s=ACT_HOP,
                  drop_db=ACT_DROP_DB):
    """Boolean "this source is sounding its note" per `hop_s`, band-limited.

    Band-limited and not broadband because the question a clash check has to
    answer is "is this part putting energy at THIS pitch right now", and a
    drum stem answers "yes" to a broadband version of that question for the
    whole record. Filtered with second-order sections: a 4th-order b/a
    Butterworth at 46-65 Hz against a 22050 Hz Nyquist is numerically dead on
    arrival and silently returns an all-zero envelope.
    """
    ny = sr / 2.0
    lo = max(15.0, f_center / 2 ** (semis / 12)) / ny
    hi = min(ny * 0.98, f_center * 2 ** (semis / 12)) / ny
    if not (0 < lo < hi < 1):
        return np.zeros(0, dtype=bool)
    z = sig.sosfiltfilt(sig.butter(4, [lo, hi], btype="band", output="sos"), y)
    h = max(1, int(hop_s * sr))
    n = len(z) // h
    if n < 4:
        return np.zeros(0, dtype=bool)
    env = np.sqrt(np.mean(z[:n * h].reshape(n, h) ** 2, axis=1))
    ref = float(np.percentile(env, 95))
    if ref <= 0:
        return np.zeros(n, dtype=bool)
    return env > ref * 10 ** (-drop_db / 20)


def overlap(mask_a, mask_b, hop_s=ACT_HOP):
    """How much, and for how long at a stretch, two sources sound together.

    `of_sparser` is the share of the less-busy source's sounding time that is
    shared with the other — the number that says "when this part plays, is
    the other one playing too". `longest_s` is the longest single continuous
    stretch, which is what beating needs: beating is a periodic swell, and a
    swell whose period exceeds the time the parts share never completes.
    """
    n = min(len(mask_a), len(mask_b))
    if n < 4:
        return None
    a, b = mask_a[:n], mask_b[:n]
    both = a & b
    on_a, on_b = float(a.mean()), float(b.mean())
    sparser = min(on_a, on_b)
    d = np.diff(np.concatenate([[0], both.astype(np.int8), [0]]))
    lens = (np.where(d == -1)[0] - np.where(d == 1)[0]) * hop_s
    return {
        "share": round(float(both.mean()), 3),
        "on_a": round(on_a, 3), "on_b": round(on_b, 3),
        "of_sparser": round(float(both.mean() / sparser) if sparser > 0 else 0.0, 3),
        "longest_s": round(float(lens.max()) if len(lens) else 0.0, 3),
        "p90_run_s": round(float(np.percentile(lens, 90)) if len(lens) else 0.0, 3),
        "n_runs": int(len(lens)),
    }


def track_frames(y, sr, hop_s=0.25, fmin=30.0, fmax=1200.0, min_strength=3.0):
    """Sounding root, frame by frame, with no note naming yet.

    Split out from `root_track` because naming a frame needs the render's
    reference pitch, and the reference pitch is measured FROM the frames of
    every source at once. Doing it in one pass would mean quantising against
    A440 first, which is the thing that splits notes in two.
    """
    hop = max(1, int(hop_s * sr))
    win = min(len(y), max(hop * 2, int(0.4 * sr)))
    frames = []
    for s in range(0, max(1, len(y) - win + 1), hop):
        seg = y[s:s + win]
        w = float(np.sqrt(np.mean(seg ** 2)))
        if w < 1e-5:
            continue
        f0, strength, ci, n_part = root_hz_ci(seg, sr, fmin=fmin, fmax=fmax)
        if f0 <= 0 or strength < min_strength:
            continue
        _n, _o, cents = hz_to_note(f0)
        frames.append({"t": round(s / sr, 2), "hz": float(f0), "w": w,
                       "cents": float(cents), "ci": round(ci, 1),
                       "partials": n_part})
    return frames


def note_stats(frames, tune_cents=0.0):
    """Histogram tracked frames into pitch classes against a reference pitch."""
    hist = np.zeros(12)
    named = []
    for fr in frames:
        name, octv, cents = hz_to_note(fr["hz"], tune_cents)
        if name is None:
            continue
        hist[PC_NAMES.index(name)] += fr["w"]
        named.append({"t": fr["t"], "hz": round(fr["hz"], 2),
                      "note": f"{name}{octv}", "cents": round(cents, 1),
                      "ci": fr["ci"], "partials": fr["partials"]})
    frames = named
    total = hist.sum()
    if total <= 0 or not frames:
        return {"hist": [0.0] * 12, "concentration": 0.0, "top": [],
                "n_frames": 0, "median_cents": 0.0, "cents_ci": 0.0,
                "top_hz": 0.0, "frames": []}
    hist /= total
    order = np.argsort(-hist)
    # concentration: share held by the two strongest pitch classes. A
    # monophonic line lands near 1.0; unpitched noise spreads across twelve.
    conc = float(hist[order[0]] + hist[order[1]])
    top_pc = int(order[0])
    on_top = [f for f in frames if PC_NAMES.index(f["note"][:-1]) == top_pc]
    cents_top = [f["cents"] for f in on_top]
    med_cents = float(np.median(cents_top)) if cents_top else 0.0
    spread = float(np.percentile(cents_top, 75) - np.percentile(cents_top, 25)) \
        if len(cents_top) > 3 else 0.0
    # The frequency this pitch class actually sounds at, in its usual octave —
    # the band a beating check has to listen in. Frames can land an octave
    # apart on the same pitch class, so pick the modal octave first.
    top_hz = 0.0
    if on_top:
        octs = [int(f["note"][len(PC_NAMES[top_pc]):]) for f in on_top]
        modal = max(set(octs), key=octs.count)
        top_hz = float(np.median([f["hz"] for f, o in zip(on_top, octs)
                                  if o == modal]))
    # Uncertainty on `med_cents`, in cents. Two terms, and the wider wins:
    # how tightly each frame's partials agreed (measurement precision), and
    # the standard error of the median across frames (the part genuinely
    # moving, or the estimator being pushed around by whatever else is in
    # the band). Neither is allowed under CENTS_CI_FLOOR — the synthetic
    # bench does not support a claim tighter than that.
    frame_ci = float(np.median([f.get("ci", 0.0) for f in on_top])) \
        if on_top else 0.0
    sem = 1.253 * (spread / 1.349) / np.sqrt(max(1, len(cents_top)))
    cents_ci = float(max(CENTS_CI_FLOOR, frame_ci, 1.96 * sem))
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
        "cents_ci": round(cents_ci, 1),
        "cents_spread": round(spread, 1),
        "top_hz": round(top_hz, 2),
        "pitch_reliable": bool(reliable),
        "frames": frames[:64],
    }


def root_track(y, sr, hop_s=0.25, fmin=30.0, fmax=1200.0, min_strength=3.0,
               tune_cents=0.0):
    """Follow the sounding root frame by frame and histogram the result."""
    return note_stats(track_frames(y, sr, hop_s=hop_s, fmin=fmin, fmax=fmax,
                                   min_strength=min_strength), tune_cents)


def out_of_key_share(chroma, tonic_pc, mode):
    """Fraction of pitch-class energy outside the detected diatonic scale."""
    if tonic_pc is None or chroma.sum() <= 0:
        return 0.0
    scale = MAJOR_SCALE if mode == "major" else MINOR_SCALE
    members = {(tonic_pc + s) % 12 for s in scale}
    return float(sum(chroma[i] for i in range(12) if i not in members))


def fmin_for(name, role):
    """Lowest root worth looking for. A bass or a kick lives under 45 Hz; a
    lead does not, and letting it look down there finds the bass instead."""
    return 30.0 if role in ("mixture", "percussive") or "bass" in name.lower() \
        else 45.0


def read_source(y, sr, name="mix", role=None, tune_cents=0.0, frames=None):
    """Every pitch reading for one audio source.

    `frames` may be handed in precomputed (see `analyze`) so the expensive
    root tracking runs once per source rather than once per tuning guess.
    """
    role = role or role_of(name)
    if float(np.max(np.abs(y))) < 1e-4:
        return {"name": name, "role": role, "silent": True}
    fmin = fmin_for(name, role)
    if frames is None:
        frames = track_frames(y, sr, fmin=fmin)
    notes = note_stats(frames, tune_cents)
    ch = chroma_vector(y, sr)
    tonic, mode, conf, ranked = detect_key(ch)
    f0, f0_strength, f0_ci, _n = root_hz_ci(y, sr, fmin=fmin)
    note, octv, cents = hz_to_note(f0, tune_cents)
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
        "cents_off_ci": round(f0_ci, 1),
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


def activity_masks(sources, readings, sr):
    """{name: boolean sounding-mask} for every source with a usable note.

    Built once per analysis and handed to `agreement`, because the masks are
    arrays and the readings are JSON.
    """
    masks = {}
    for r in readings:
        if r.get("silent") or not r.get("usable_pitch"):
            continue
        f = (r.get("notes") or {}).get("top_hz") or 0.0
        y = sources.get(r["name"])
        if f <= 0 or y is None or len(y) < sr // 2:
            continue
        m = note_activity(y, sr, f)
        if len(m):
            masks[r["name"]] = m
    return masks


def agreement(readings, masks=None):
    """Interval relations between the sources that actually play notes.

    Every pair carries an `overlap` block. It used to carry none, and the
    consequence was a "they will beat" verdict on a bass deliberately written
    in the kick's gaps — see the module docstring. A pairing with no overlap
    reading at all is left as None and the callers downgrade rather than
    guess.
    """
    masks = masks or {}
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
        detune = detune_ci = beat_hz = None
        if semis == 0:
            detune = round(a["notes"]["median_cents"] -
                           b["notes"]["median_cents"], 1)
            # Independent readings, so the intervals add in quadrature.
            detune_ci = round(float(np.hypot(a["notes"].get("cents_ci", 0.0),
                                             b["notes"].get("cents_ci", 0.0))), 1)
            fa = a["notes"].get("top_hz") or 0.0
            fb = b["notes"].get("top_hz") or 0.0
            if fa > 0 and fb > 0:
                # Beat rate between the two sounding frequencies, folded to
                # the nearest octave: a bass an octave under a kick on the
                # same note beats at the difference of the *coinciding*
                # partials, not at 55 Hz.
                ratio = max(fa, fb) / min(fa, fb)
                folded = min(fa, fb) * 2 ** round(np.log2(ratio))
                beat_hz = round(abs(folded - max(fa, fb)), 3)
        ov = overlap(masks[a["name"]], masks[b["name"]]) \
            if a["name"] in masks and b["name"] in masks else None
        pairs.append({
            "kind": kind, "a": a["name"], "b": b["name"],
            "a_note": PC_NAMES[top_a], "b_note": PC_NAMES[top_b],
            "a_root": a["root_note"], "b_root": b["root_note"],
            "interval": INTERVALS[semis][0], "semitones": semis,
            "harsh": bool(INTERVALS[semis][1]),
            "harsh_pairs": harsh, "detune_cents": detune,
            "detune_ci": detune_ci, "beat_hz": beat_hz, "overlap": ov,
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


def _together(p):
    """(share-of-sparser, longest continuous run, one-line description).

    Falls back to "assume they overlap" when there is no mask, so a missing
    measurement never silences a real fault — it just cannot sharpen it.
    """
    ov = p.get("overlap")
    if not ov:
        return 1.0, None, ""
    return (ov["of_sparser"], ov["longest_s"],
            f"together {ov['of_sparser']:.0%} of the time "
            f"({ov['longest_s']:.2f} s at a stretch)")


def analyze(sources, sr):
    """sources: {name: mono array}. Returns the full harmonic reading.

    `problems` are faults worth acting on. `observations` are readings that
    are true but not actionable — a dissonance between parts that alternate,
    a detuning too small or too brief to beat, a cents figure the analysis
    cannot resolve. They are kept apart because listen.py puts `problems` in
    the report headline, and a headline that fires on 13 of 18 released
    Drumcode records is noise, not criticism.
    """
    # Two passes over the pitch track. The first collects raw frequencies and
    # measures what pitch this render is tuned to; the second names the notes
    # against that reference. See hz_to_note for why the order matters.
    tracked = {}
    for n, y in sources.items():
        if float(np.max(np.abs(y))) < 1e-4:
            continue
        tracked[n] = track_frames(y, sr, fmin=fmin_for(n, role_of(n)))
    # The mixture, when there is one, is the whole record speaking at once and
    # is the best single witness to its tuning; stems inherit its verdict.
    witness = tracked.get("mix") or [f for fs in tracked.values() for f in fs]
    tune = tuning_from_frames(witness)
    readings = [read_source(y, sr, name=n, tune_cents=tune,
                            frames=tracked.get(n))
                for n, y in sources.items()]
    cons = consensus_key(readings)
    masks = activity_masks(sources, readings, sr)
    pairs = agreement(readings, masks=masks)
    problems, observations = [], []

    for p in pairs:
        share, longest, when = _together(p)
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
                # Name the two notes that are actually a semitone apart. This
                # used to print the drum's top note against the bass's top
                # note whatever the reason for firing, which on a source with
                # a secondary pitch class produced "drums is tuned to G, bass
                # plays G — a semitone apart".
                if p["semitones"] in (1, 11):
                    drum_note, bass_note = p["a_note"], p["b_note"]
                else:
                    drum_note, bass_note = semis[0][0], semis[0][1]
                # A kick and a bass that take turns are what sidechaining is
                # FOR. The semitone only rubs while both are sounding.
                if share <= ALTERNATING_MAX:
                    observations.append(
                        f"kick/bass semitone: {p['a']} is tuned to "
                        f"{drum_note} ({p['a_root']}) and {p['b']} plays "
                        f"{bass_note}, but they {when} — they take turns, so "
                        f"this reads as a pitch step, not a rub.")
                else:
                    # An OBSERVATION, not a fault. Measured over the 18
                    # reference excerpts this check fired on 7 of them —
                    # Love Within, Your Mind, KO twice, Move Your Body twice.
                    # Those are released Drumcode records whose kick and bass
                    # are demonstrably fine, so a check that accuses them is
                    # describing something normal. The cause is that a demucs
                    # drums stem carries bass bleed, and a kick's pitch sweeps
                    # during its decay, so "the kick is tuned to X" is soft to
                    # begin with. Reported so a human can judge it; not
                    # asserted as a defect.
                    observations.append(
                        f"kick/bass semitone: {p['a']} reads as tuned to "
                        f"{drum_note} ({p['a_root']}) while {p['b']} plays "
                        f"{bass_note}, {when}. 7 of 18 reference records trip "
                        f"this same test, so treat it as a thing to listen "
                        f"for rather than a fault.")
        elif p["harsh"]:
            if share >= SUSTAINED_MIN:
                problems.append(
                    f"CLASH: {p['a']} plays {p['a_note']} against {p['b']} "
                    f"{p['b_note']} — a {p['interval']} between two roots "
                    f"sounding {when}.")
            elif share > ALTERNATING_MAX:
                problems.append(
                    f"CLASH (intermittent): {p['a']} {p['a_note']} against "
                    f"{p['b']} {p['b_note']} — a {p['interval']}, {when}.")
            else:
                observations.append(
                    f"melodic {p['interval']}: {p['a']} {p['a_note']} and "
                    f"{p['b']} {p['b_note']} alternate ({when}) — heard as a "
                    f"line, not a clash.")
        elif p["harsh_pairs"] and p["kind"] == "voices":
            worst = max(p["harsh_pairs"], key=lambda h: h[3])
            if worst[3] >= 0.10 and share > ALTERNATING_MAX:
                problems.append(
                    f"CLASH (secondary): {p['a']} {worst[0]} against {p['b']} "
                    f"{worst[1]} — a {worst[2]}, present {worst[3]:.0%} of "
                    f"the time, {when}.")
            elif worst[3] >= 0.10:
                observations.append(
                    f"melodic {worst[2]}: {p['a']} {worst[0]} against "
                    f"{p['b']} {worst[1]} — they alternate ({when}).")

        # Detuning. Three things have to hold before "they will beat" is a
        # statement about the room rather than about the FFT: the difference
        # has to exceed what the analysis can resolve, the two parts have to
        # sound together, and one continuous overlap has to be long enough
        # for at least BEAT_CYCLES_MIN complete beat cycles.
        d = p["detune_cents"]
        if d is not None and abs(d) > DETUNE_MIN_CENTS:
            ci = p.get("detune_ci") or 0.0
            beat = p.get("beat_hz") or 0.0
            cycles = (longest * beat) if (longest and beat > 0) else None
            if ci > CENTS_CI_MAX or abs(d) - ci <= DETUNE_MIN_CENTS:
                observations.append(
                    f"detuning not resolvable: {p['a']} and {p['b']} are both "
                    f"{p['a_note']}, apparently {abs(d):.0f} cents apart, but "
                    f"the reading is only good to +-{ci:.0f} cents — not a "
                    f"claim this analysis can support.")
            elif cycles is not None and cycles < BEAT_CYCLES_MIN:
                observations.append(
                    f"detuned but not beating: {p['a']} and {p['b']} are both "
                    f"{p['a_note']}, {abs(d):.0f}+-{ci:.0f} cents apart "
                    f"({beat:.2f} Hz beat, a {1 / beat:.2f} s cycle), but they "
                    f"{when} — under one beat cycle, so no beating. It reads "
                    f"as one sitting slightly {'sharp' if d > 0 else 'flat'} "
                    f"of the other.")
            elif share <= ALTERNATING_MAX:
                observations.append(
                    f"detuned but alternating: {p['a']} and {p['b']} are both "
                    f"{p['a_note']}, {abs(d):.0f}+-{ci:.0f} cents apart, but "
                    f"they {when}.")
            else:
                problems.append(
                    f"DETUNED: {p['a']} and {p['b']} are both {p['a_note']} "
                    f"but {abs(d):.0f}+-{ci:.0f} cents apart — {when}, which "
                    f"is {cycles:.0f} cycles of a {beat:.2f} Hz beat. "
                    f"They will beat.")

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
    if abs(tune) > 10:
        observations.append(
            f"track tuning: this render sits {tune:+.0f} cents from A440 "
            f"overall — every note name and cents reading here is measured "
            f"against that reference, not against concert pitch.")
    for r in readings:
        if r.get("silent") or not r.get("usable_pitch") or \
                r["name"] not in loud:
            continue
        n = r["notes"]
        spread = n.get("cents_spread", 0.0)
        if spread > 60:
            continue                 # a pitch-swept source has no one pitch
        c = n["median_cents"]
        ci = n.get("cents_ci", CENTS_CI_FLOOR)
        if abs(c) <= OFF_PITCH_CENTS:
            continue
        if ci > CENTS_CI_MAX or abs(c) - ci <= OFF_PITCH_CENTS:
            observations.append(
                f"{r['name']} may sit {c:+.0f} cents off "
                f"{PC_NAMES[n['top_pc']]}, but only to +-{ci:.0f} cents — "
                f"under the resolution needed to call it.")
            continue
        # Also an observation: Sam Paganini's "Rave" measures its bass at
        # -44 and -45 cents against its own track reference across two
        # windows, the same magnitude this flags on our renders. A reading
        # that a released record shares cannot separate good from bad.
        observations.append(
            f"off pitch: {r['name']} sits {c:+.0f}+-{ci:.0f} cents from "
            f"{PC_NAMES[n['top_pc']]} relative to the rest of the track. "
            f"Sam Paganini's 'Rave' measures -44 cents on the same test, so "
            f"this is only worth acting on if you can hear it.")
    return {"sources": readings, "consensus": cons, "pairs": pairs,
            "tuning_ref_cents": round(tune, 1),
            "problems": problems, "observations": observations}


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
        extra = (f"  ({p['detune_cents']:+.0f}+-{p.get('detune_ci') or 0:.0f} "
                 f"cents apart)") if p["detune_cents"] is not None else ""
        ov = p.get("overlap")
        # The overlap column is the whole point of the pair rows: an interval
        # between parts that never sound together is not a relation you can
        # hear. Blank means the overlap could not be measured.
        together = f"  [together {ov['of_sparser']:.0%}, runs " \
                   f"{ov['longest_s']:.2f}s]" if ov else ""
        mark = "  <-- harsh" if p["harsh"] else ""
        tag = "tuning" if p["kind"] == "tuning" else "voices"
        L.append(f"  [{tag}] {p['a']} {p['a_note']} -> {p['b']} {p['b_note']}: "
                 f"{p['interval']}{extra}{together}{mark}")
    for o in h.get("observations") or []:
        L.append(f"  note: {o}")
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
    if h.get("observations"):
        print("\nobservations (true, but not faults):")
        for o in h["observations"]:
            print(f"  - {o}")


if __name__ == "__main__":
    main()
