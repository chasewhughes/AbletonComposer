#!/usr/bin/env python3
"""Perceptual analysis — the part of listening that can be measured.

critic.py answers "is this techno, and is it new?" against the reference
corpus. It does NOT answer "does this sound broken?", which is how a render
scoring a respectable core can still sound like a blown speaker playing a
cellphone. This module is that second question, and it reports in the units a
mix decision is actually made in: dB, not z-scores.

What it checks, and why each one exists:

  loudness    LUFS / true peak / crest / PLR. A crest under ~8 dB on techno
              means the limiter is doing the arranging.
  tonal       Octave-band energy vs the reference corpus, as dB deltas. This
              is the "no top end" detector, and it prints the EQ move.
  congestion  Per band, the ratio of quiet-moment energy to median energy. A
              rhythmic element leaves gaps; an overlapping one-shot drone does
              not. This catches long samples retriggered faster than they
              decay — the failure that muddied groove v3.
  pulse       Tempo, beat confidence, and whether the kick is actually the
              loudest onset (the pulse-hierarchy seesaw).
  presence    Transient density per band: proves the hats are audible in the
              mix rather than merely present in the session.
  artifacts   Clipping runs, DC offset, mono-compatibility, silence.

Usage:
  .venv-analysis/bin/python tools/ears.py <render.wav> [--ref-corpus]
"""
import argparse
import json
import pathlib
import sys

import librosa
import numpy as np
import pyloudnorm
import soundfile as sf

REPO = pathlib.Path(__file__).resolve().parent.parent
REF_DIR = REPO / "reference-audio"
DB_PATH = REF_DIR / "fingerprints.json"
SR = 44100

# Octave-ish bands that map to how people talk about a mix.
BANDS = [
    ("sub", 20, 60), ("bass", 60, 120), ("lowmid", 120, 350),
    ("mid", 350, 2000), ("highmid", 2000, 6000), ("high", 6000, 12000),
    ("air", 12000, 20000),
]
# Reference tonal balance, measured from the Drumcode full-length masters.
# Filled by --ref-corpus; these defaults come from that measurement.
REF_BALANCE_DB = None


def band_db(y, sr):
    """Energy per band in dB relative to total."""
    S = np.abs(librosa.stft(y, n_fft=4096))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
    mag = S.sum(axis=1)
    total = mag.sum() + 1e-12
    out = {}
    for name, lo, hi in BANDS:
        share = mag[(freqs >= lo) & (freqs < hi)].sum() / total
        out[name] = 20 * np.log10(share + 1e-9)
    return out


def congestion(y, sr):
    """Per band: how much energy is present even in the quiet moments.

    For each band, take a short-time envelope and compare its 10th percentile
    to its median. A kick leaves near-silence between hits (very negative dB);
    an overlapping drone never gets out of its own way (approaching 0 dB).
    """
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    out = {}
    for name, lo, hi in BANDS:
        sel = (freqs >= lo) & (freqs < hi)
        if not sel.any():
            continue
        env = S[sel].sum(axis=0)
        med = np.median(env) + 1e-12
        p10 = np.percentile(env, 10) + 1e-12
        out[name] = 20 * np.log10(p10 / med)
    return out


def transient_density(y, sr):
    """Onsets per second detected within each band — 'can you hear it move'."""
    out = {}
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=256))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    for name, lo, hi in BANDS:
        if hi <= lo:
            continue
        sel = (freqs >= lo) & (freqs < hi)
        if not sel.any():
            out[name] = 0.0
            continue
        env = S[sel].sum(axis=0)
        env = np.maximum(0, np.diff(env, prepend=env[0]))
        if env.max() <= 0:
            out[name] = 0.0
            continue
        peaks = librosa.util.peak_pick(env, pre_max=4, post_max=4, pre_avg=8,
                                       post_avg=8, delta=env.std() * 0.6, wait=6)
        out[name] = len(peaks) / (len(y) / sr)
    return out


def pulse(y, sr):
    """Tempo, tracker confidence, and whether the downbeat owns the low end."""
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    folded = tempo
    while folded < 100:
        folded *= 2
    while folded > 180:
        folded /= 2

    hop_t = 512 / sr
    beat_lag = int(round((60.0 / folded) / hop_t))
    env = onset_env - onset_env.mean()
    ac = librosa.autocorrelate(env)
    ac = ac / (ac[0] + 1e-12)
    confidence = float(ac[beat_lag]) if beat_lag < len(ac) else 0.0

    # kick dominance: low-band peak at beat positions vs everywhere else
    yl = librosa.effects.hpss(y)[0] if False else y
    S = np.abs(librosa.stft(yl, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = S[(freqs >= 30) & (freqs < 120)].sum(axis=0)
    high = S[(freqs >= 2000) & (freqs < 12000)].sum(axis=0)
    beat_frames = np.clip(beats, 0, len(low) - 1)
    on_beat = low[beat_frames].mean() if len(beat_frames) else 0.0
    off = np.median(low) + 1e-12
    return {"tempo": folded, "raw_tempo": tempo, "beat_confidence": confidence,
            "kick_beat_ratio": float(on_beat / off),
            "low_to_high_ratio_db": float(20 * np.log10((low.mean() + 1e-12) /
                                                        (high.mean() + 1e-12)))}


def loudness(path):
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return loudness_array(data, sr)


def loudness_array(data, sr):
    """data: (N, channels) float. Mono input is accepted as (N,) or (N, 1)."""
    data = np.atleast_2d(np.asarray(data, dtype=np.float32))
    if data.shape[0] < data.shape[1]:
        data = data.T                      # (channels, N) -> (N, channels)
    mono = data.mean(axis=1)
    meter = pyloudnorm.Meter(sr)
    try:
        lufs = float(meter.integrated_loudness(data))
    except Exception:
        lufs = -70.0
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(mono ** 2))) + 1e-12
    crest = 20 * np.log10(peak / rms + 1e-12)

    # clipping: runs of >=3 consecutive samples within 0.05 dB of full scale
    at_fs = np.abs(mono) >= 0.9995
    runs, run = 0, 0
    for v in at_fs:
        run = run + 1 if v else 0
        if run == 3:
            runs += 1
    dc = float(np.mean(mono))
    if data.shape[1] >= 2:
        l, r = data[:, 0], data[:, 1]
        corr = float(np.corrcoef(l, r)[0, 1]) if l.std() > 0 and r.std() > 0 else 1.0
        mono_sum = (l + r) / 2
        mono_loss = 20 * np.log10((np.sqrt(np.mean(mono_sum ** 2)) + 1e-12) /
                                  (np.sqrt(np.mean(mono ** 2)) + 1e-12))
    else:
        corr, mono_loss = 1.0, 0.0
    return {"lufs": lufs, "true_peak_db": 20 * np.log10(peak + 1e-12),
            "crest_db": crest, "plr_db": 20 * np.log10(peak + 1e-12) - lufs,
            "clip_runs": runs, "dc_offset": dc, "stereo_corr": corr,
            "mono_loss_db": mono_loss}


def reference_balance():
    """Measure the tonal balance of the Drumcode full-length masters."""
    files = sorted((REF_DIR / "Drumcode").glob("*.mp3"))
    if not files:
        return None
    rows = []
    for f in files:
        y, sr = librosa.load(str(f), sr=SR, mono=True, duration=120.0, offset=60.0)
        rows.append(band_db(y, sr))
    keys = [b[0] for b in BANDS]
    return {k: (float(np.mean([r[k] for r in rows])),
                float(np.std([r[k] for r in rows]))) for k in keys}


def analyze(path, ref_bal=None):
    y, sr = librosa.load(path, sr=SR, mono=True)
    rep = analyze_array(y, sr, loud=loudness(path), ref_bal=ref_bal)
    rep["file"] = str(path)
    return rep


def analyze_array(y, sr, loud=None, ref_bal=None):
    """Same reading as analyze(), from an in-memory signal.

    Stems and reference excerpts never exist as files on disk; every metric
    below is computed from the array, and `loud` may carry the stereo-aware
    loudness measured on the original file when there is one.
    """
    rep = {
        "duration_s": len(y) / sr,
        "loudness": loud if loud is not None else loudness_array(y, sr),
        "tonal_db": band_db(y, sr),
        "congestion_db": congestion(y, sr),
        "transients_per_s": transient_density(y, sr),
        "pulse": pulse(y, sr),
    }
    if ref_bal:
        rep["tonal_delta_db"] = {k: rep["tonal_db"][k] - ref_bal[k][0]
                                 for k in rep["tonal_db"] if k in ref_bal}
        rep["reference_balance_db"] = {k: round(v[0], 1) for k, v in ref_bal.items()}
    return rep


# What a band being over / under the reference actually sounds like. Naming
# the symptom beats printing a signed number: "+6 dB sub" is a fact, "MUDDY"
# is the thing a listener would say.
BAND_HIGH_TAG = {"sub": "MUDDY", "bass": "MUDDY", "lowmid": "BOXY",
                 "mid": "HONKY", "highmid": "HARSH", "high": "BRIGHT",
                 "air": "HISSY"}
BAND_LOW_TAG = {"sub": "THIN", "bass": "THIN", "lowmid": "HOLLOW",
                "mid": "SCOOPED", "highmid": "DULL", "high": "DARK",
                "air": "AIRLESS"}

# Calibrated checks. Each is compared against the SAME measurement taken on
# the reference corpus in the SAME context — a drums-only render is judged
# against reference drum stems, never against full commercial masters. That
# context match is the whole point: the old fixed thresholds reported a
# drums-only loop as MUDDY +6.7 dB sub, which was an artifact of comparing a
# stem to a mix.
#   (metric path, direction, min meaningful delta, unit, contexts)
CALIBRATED_CHECKS = (
    [(("tonal_db", b), "both", 2.5, "dB", None) for b, _, _ in BANDS] +
    [(("congestion_db", b), "high", 3.0, "dB", None)
     for b in ("sub", "bass", "lowmid", "mid")] +
    [(("loudness", "crest_db"), "low", 1.5, "dB", None),
     (("loudness", "lufs"), "both", 1.5, "LUFS", ("mix",)),
     (("pulse", "kick_beat_ratio"), "low", 0.15, "x", ("mix", "drums")),
     (("pulse", "beat_confidence"), "low", 0.08, "", ("mix", "drums")),
     (("transients_per_s", "high"), "low", 0.8, "/s", None),
     (("pulse", "low_to_high_ratio_db"), "both", 3.0, "dB", None)])

# Plain-language tag per metric when it goes out of range.
METRIC_TAG = {
    ("congestion_db", "high"): "CONGESTED",
    ("loudness.crest_db", "low"): "CRUSHED",
    ("loudness.lufs", "high"): "TOO LOUD",
    ("loudness.lufs", "low"): "TOO QUIET",
    ("pulse.kick_beat_ratio", "low"): "KICK NOT DOMINANT",
    ("pulse.beat_confidence", "low"): "WEAK PULSE",
    ("transients_per_s.high", "low"): "NO HIGH-END MOVEMENT",
    ("pulse.low_to_high_ratio_db", "high"): "LOW-HEAVY",
    ("pulse.low_to_high_ratio_db", "low"): "TOP-HEAVY",
}


def _get(rep, path):
    v = rep
    for k in path:
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _tag_for(path, side):
    if path[0] in ("tonal_db",):
        table = BAND_HIGH_TAG if side == "high" else BAND_LOW_TAG
        return f"{table.get(path[1], 'BALANCE')} {path[1]}"
    if path[0] == "congestion_db":
        return f"CONGESTED {path[1]}"
    return METRIC_TAG.get((".".join(path), side), f"{'.'.join(path)} {side}")


def calibrated_verdict(rep, calib, context="mix"):
    """Problems stated as deltas against the reference corpus in `context`.

    Returns [] when the calibration has no data for the context — the caller
    falls back to fixed thresholds rather than inventing an opinion.
    """
    out = []
    for path, direction, min_delta, unit, ctxs in CALIBRATED_CHECKS:
        if ctxs and context not in ctxs:
            continue
        v = _get(rep, path)
        st = calib.stat(context, ".".join(path))
        if v is None or st is None:
            continue
        z = calib.z(context, ".".join(path), v)
        delta = v - st["median"]
        side = "high" if delta > 0 else "low"
        if direction != "both" and direction != side:
            continue
        if abs(z) < 2.5 or abs(delta) < min_delta:
            continue
        out.append((abs(z), f"{_tag_for(path, side)}: {v:.2f}{unit} vs "
                            f"{context} references {st['median']:.2f} "
                            f"(range {st['p10']:.2f}..{st['p90']:.2f}, n={st['n']}) "
                            f"— {delta:+.2f}{unit}, z={z:+.1f}."))
    out.sort(reverse=True)                 # worst deviation first
    return [line for _, line in out]


def absolute_verdict(rep):
    """Faults that are wrong in any context and need no reference at all."""
    out = []
    L = rep["loudness"]
    if L["clip_runs"] > 0:
        out.append(f"CLIPPING: {L['clip_runs']} full-scale runs.")
    if abs(L["dc_offset"]) > 0.001:
        out.append(f"DC OFFSET: {L['dc_offset']:.4f}")
    if L["mono_loss_db"] < -3:
        out.append(f"MONO PROBLEM: {L['mono_loss_db']:.1f} dB lost folding to mono.")
    return out


def verdict(rep, calib=None, context="mix"):
    """Plain-language problems, worst first — each with the fix.

    With a calibration loaded, every threshold comes from the reference
    corpus measured in the same context. Without one, fall back to the fixed
    thresholds below, which are only valid for a full mix.
    """
    if calib is not None:
        cal = calibrated_verdict(rep, calib, context)
        if cal or calib.has_context(context):
            return absolute_verdict(rep) + cal
    if context != "mix":
        return absolute_verdict(rep) + [
            f"NO CALIBRATION for context '{context}': the fixed thresholds are "
            f"mix-only and would misfire on a stem. Run "
            f"`tools/calibrate.py build` to judge this in context."]
    return absolute_verdict(rep) + _fixed_verdict(rep)


def _fixed_verdict(rep):
    """Mix-only fallback thresholds, used when no calibration is built."""
    out = []
    L = rep["loudness"]
    if L["crest_db"] < 8:
        out.append(f"CRUSHED: crest {L['crest_db']:.1f} dB (want 10-14). The "
                   f"limiter is doing the arranging — cut gain into it.")
    if L["lufs"] > -8:
        out.append(f"TOO LOUD: {L['lufs']:.1f} LUFS (reference ~-11.5). "
                   f"Pull master gain down {L['lufs'] + 11.5:.1f} dB.")

    d = rep.get("tonal_delta_db", {})
    for band in ("high", "air", "highmid"):
        if d.get(band, 0) < -6:
            out.append(f"DARK: {band} is {d[band]:.1f} dB under reference — "
                       f"the mix will read as muffled/broken.")
    for band in ("lowmid", "sub", "bass"):
        if d.get(band, 0) > 5:
            out.append(f"MUDDY: {band} is +{d[band]:.1f} dB over reference.")

    c = rep["congestion_db"]
    for band in ("sub", "bass", "lowmid"):
        if c.get(band, -99) > -6:
            out.append(f"CONGESTED {band}: quiet moments only {c[band]:.1f} dB "
                       f"below median — something is droning, not playing. "
                       f"A one-shot is retriggering before it decays.")

    t = rep["transients_per_s"]
    if t.get("high", 0) < 1.0:
        out.append(f"NO HIGH-END MOVEMENT: {t.get('high', 0):.1f} transients/s "
                   f"above 6 kHz — hats are inaudible in the mix.")

    p = rep["pulse"]
    if p["beat_confidence"] < 0.3:
        out.append(f"WEAK PULSE: beat confidence {p['beat_confidence']:.2f}.")
    if p["kick_beat_ratio"] < 1.3:
        out.append(f"KICK NOT DOMINANT: on-beat low energy only "
                   f"{p['kick_beat_ratio']:.2f}x the median.")
    if p["low_to_high_ratio_db"] > 14:
        out.append(f"LOW-HEAVY: low band is {p['low_to_high_ratio_db']:.1f} dB "
                   f"over the highs.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("--ref-corpus", action="store_true",
                    help="re-measure reference tonal balance (slow)")
    ap.add_argument("--context", default="mix",
                    choices=("mix", "drums", "bass", "other", "loop"),
                    help="what this audio IS — thresholds come from the "
                         "reference corpus measured the same way")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cache = REF_DIR / "tonal_reference.json"
    if a.ref_corpus or not cache.exists():
        bal = reference_balance()
        if bal:
            cache.write_text(json.dumps(bal, indent=1))
    bal = json.loads(cache.read_text()) if cache.exists() else None

    rep = analyze(a.render, bal)
    if a.json:
        print(json.dumps(rep, indent=1))
        return

    L, p = rep["loudness"], rep["pulse"]
    print(f"\n=== {pathlib.Path(rep['file']).name}  ({rep['duration_s']:.1f}s)")
    print(f"loudness  {L['lufs']:.1f} LUFS   peak {L['true_peak_db']:.1f} dBFS   "
          f"crest {L['crest_db']:.1f} dB   PLR {L['plr_db']:.1f} dB"
          f"   clips {L['clip_runs']}")
    print(f"stereo    corr {L['stereo_corr']:+.2f}   mono loss {L['mono_loss_db']:.1f} dB")
    print(f"pulse     {p['tempo']:.1f} BPM (raw {p['raw_tempo']:.1f})   "
          f"confidence {p['beat_confidence']:.2f}   kick/median {p['kick_beat_ratio']:.2f}x"
          f"   low-high {p['low_to_high_ratio_db']:+.1f} dB")

    print(f"\n{'band':10s}{'level dB':>10s}{'vs ref':>9s}{'congest':>9s}{'trans/s':>9s}")
    for name, _, _ in BANDS:
        delta = rep.get("tonal_delta_db", {}).get(name)
        ds = f"{delta:+.1f}" if delta is not None else "   -"
        print(f"{name:10s}{rep['tonal_db'][name]:10.1f}{ds:>9s}"
              f"{rep['congestion_db'].get(name, 0):9.1f}"
              f"{rep['transients_per_s'].get(name, 0):9.1f}")

    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import calibrate
        cal = calibrate.load()
    except Exception:
        cal = None
    v = verdict(rep, calib=cal, context=a.context)
    src = f"calibrated vs {a.context} references" if cal and \
        cal.has_context(a.context) else "fixed mix-only thresholds"
    print(f"\n--- what a listener would notice ({src}) ---")
    if not v:
        print("  nothing structurally wrong.")
    for i, line in enumerate(v, 1):
        print(f"  {i}. {line}")


if __name__ == "__main__":
    main()
