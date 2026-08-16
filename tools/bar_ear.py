#!/usr/bin/env python3
"""Bar ear — localize a problem to the bar that causes it.

The CLAP timeline runs on 10-second windows. A bar at 132 BPM is 1.8 seconds,
so a window smears five and a half bars together: it can say the second half
is worse than the first and it can never say "bar 9 is where it falls apart".
That sentence is the one worth having, because a bar number is something a
generator can go and fix.

This ear is pure DSP and works at exactly bar resolution. It reconstructs the
loop the piece is repeating — the steps that fire in most bars — and then
reports each bar as a deviation from that loop:

  level       Bar RMS and per-band energy against the median bar, in dB.
  pattern     Which loop steps this bar drops, and which steps it adds, per
              role. A dropped kick on step 8 of bar 9 is a fact you can act
              on; "groove got worse" is not.
  novelty     One number per bar combining both, so the report can point at
              the worst bars without printing thirty-two rows.

Nothing here is a judgement about whether variation is good: a techno track
SHOULD deviate at bar 17. It reports where the deviations are and leaves the
verdict to the reader, who knows whether a drop was intended.

Usage:
  .venv-listen/bin/python tools/bar_ear.py <render.wav>
"""
import numpy as np
import librosa

HOP = 256
ROLES = [("KICK", 25, 100), ("PERC", 150, 2000), ("HATS", 5000, 16000)]
BANDS = [("sub", 20, 60), ("low", 60, 200), ("mid", 200, 2000),
         ("high", 2000, 8000), ("air", 8000, 18000)]
LOOP_STEP_MIN = 0.5      # a step is part of the loop if it fires in half the bars


def bar_times(y, sr, tempo, downbeat, beats_t=None):
    """Bar boundaries in seconds, anchored to the TRACKED beats.

    A grid laid down as downbeat + n * (4 * 60 / tempo) drifts: a 0.5% tempo
    error walks most of a 16th over eight bars, and the drift shows up as a
    phantom event — early bars reporting every hat one step off the loop,
    which is a fault in the ruler, not in the music. Stepping along the
    tracked beats instead keeps the grid locked no matter how the tempo
    estimate rounds.
    """
    dur = len(y) / sr
    bar_len = 4 * 60.0 / tempo
    if beats_t is None or len(beats_t) < 8:
        edges = np.arange(downbeat, dur + 1e-6, bar_len)
        return (edges if len(edges) >= 2 else np.array([0.0, dur])), bar_len
    i0 = int(np.argmin(np.abs(np.asarray(beats_t) - downbeat)))
    edges = list(np.asarray(beats_t)[i0::4])
    if len(edges) < 2:
        return np.array([0.0, dur]), bar_len
    if dur - edges[-1] > bar_len * 0.75:      # trailing partial bar worth keeping
        edges.append(min(dur, edges[-1] + bar_len))
    return np.array(edges), float(np.median(np.diff(edges)))


def band_levels(y, sr, edges):
    """Per-bar dB per band — one STFT, sliced by bar."""
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    times = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=512)
    out = []
    for i in range(len(edges) - 1):
        sel = (times >= edges[i]) & (times < edges[i + 1])
        if not sel.any():
            out.append(None)
            continue
        blk = S[:, sel]
        row = {}
        for name, lo, hi in BANDS:
            f = (freqs >= lo) & (freqs < hi)
            row[name] = float(20 * np.log10(blk[f].mean() + 1e-12))
        out.append(row)
    return out


def role_steps(y, sr, edges, bar_len, attack=True):
    """{role: (n_bars, 16) bool} — which 16th of which bar each onset lands on."""
    import groove_ear
    out = {}
    n_bars = len(edges) - 1
    tempo = 4 * 60.0 / bar_len
    for name, lo, hi in ROLES:
        grid = np.zeros((n_bars, 16), dtype=bool)
        times, _ = groove_ear.band_onsets(y, sr, lo, hi, tempo=tempo, role=name,
                                          attack=attack)
        for t in times:
            b = int(np.searchsorted(edges, t) - 1)
            if b < 0 or b >= n_bars:
                continue
            # each bar is measured against ITS OWN length, so a bar that runs
            # a few ms long does not push its hits onto the next step
            this_bar = edges[b + 1] - edges[b]
            step = int(round((t - edges[b]) / max(this_bar, 1e-6) * 16))
            if step >= 16:                     # landed on the next downbeat
                b, step = b + 1, 0
                if b >= n_bars:
                    continue
            grid[b, step] = True
        out[name] = grid
    return out


def analyze(y, sr, tempo, downbeat, beats_t=None, drums=None):
    """Per-bar deviation from the loop the piece is repeating.

    Levels come from `y` (the mix — a bar that loses its bass is a bar-scale
    event and has to show up), patterns from `drums` when a drum stem is
    available. They have to come from different sources: groove_ear's KICK
    detector only tells a kick from a bass note by its attack, and on a mix
    with a loud sustained sub there is nothing in 25-100 Hz to tell them apart
    with, so a mix-fed KICK row is a low-band row wearing the kick's name.
    """
    edges, bar_len = bar_times(y, sr, tempo, downbeat, beats_t)
    n_bars = len(edges) - 1
    if n_bars < 2:
        return {"available": False, "reason": "shorter than two bars"}

    rms = []
    for i in range(n_bars):
        a, b = int(edges[i] * sr), int(edges[i + 1] * sr)
        seg = y[a:min(b, len(y))]
        rms.append(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12))
                   if len(seg) else -99.0)
    rms = np.array(rms)
    levels = band_levels(y, sr, edges)
    pattern_src = y if drums is None else drums
    steps = role_steps(pattern_src, sr, edges, bar_len, attack=drums is not None)

    # the loop: steps that fire in at least half the bars
    loop = {name: grid.mean(axis=0) >= LOOP_STEP_MIN for name, grid in steps.items()}

    med_rms = float(np.median(rms))
    band_med = {name: float(np.median([lv[name] for lv in levels if lv]))
                for name, _, _ in BANDS}

    bars = []
    for i in range(n_bars):
        row = {"bar": i + 1, "t": round(float(edges[i]), 2),
               "rms_db": round(float(rms[i]), 1),
               "rms_delta_db": round(float(rms[i] - med_rms), 1)}
        if levels[i]:
            row["band_delta_db"] = {n: round(levels[i][n] - band_med[n], 1)
                                    for n, _, _ in BANDS}
        miss, extra, pattern_cost = {}, {}, 0.0
        for name, grid in steps.items():
            m = [int(s) for s in np.where(loop[name] & ~grid[i])[0]]
            e = [int(s) for s in np.where(grid[i] & ~loop[name])[0]]
            if m:
                miss[name] = m
            if e:
                extra[name] = e
            denom = max(1, int(loop[name].sum()))
            pattern_cost += (len(m) + 0.5 * len(e)) / denom
        row["missing_steps"] = miss
        row["extra_steps"] = extra
        # novelty: pattern damage plus level deviation, in comparable units
        row["deviation"] = round(float(pattern_cost / max(1, len(steps)) +
                                       abs(rms[i] - med_rms) / 6.0), 3)
        bars.append(row)

    devs = np.array([b["deviation"] for b in bars])
    thresh = float(np.median(devs) + 2.5 * (np.median(np.abs(devs - np.median(devs)))
                                            * 1.4826 + 1e-9))
    outliers = [b for b in bars if b["deviation"] > max(thresh, 0.15)]
    return {"available": True, "pattern_source": "drum stem" if drums is not None
            else "full mix (KICK row includes the bassline)",
            "tempo": round(tempo, 1), "bar_len_s": round(bar_len, 3),
            "n_bars": n_bars, "median_rms_db": round(med_rms, 1),
            "loop": {k: [int(s) for s in np.where(v)[0]] for k, v in loop.items()},
            "bars": bars, "outlier_bars": [b["bar"] for b in outliers],
            "deviation_threshold": round(thresh, 3)}


def describe(res, max_rows=8):
    """The bars that differ, said in words. Silent when the loop is uniform."""
    if not res.get("available"):
        return f"bar ear unavailable: {res.get('reason')}"
    L = [f"{res['n_bars']} bars of {res['bar_len_s']:.2f}s at {res['tempo']} BPM; "
         f"loop steps " + ", ".join(f"{k} {v}" for k, v in res["loop"].items())]
    outliers = sorted((b for b in res["bars"]
                       if b["bar"] in res["outlier_bars"]),
                      key=lambda b: -b["deviation"])[:max_rows]
    if not outliers:
        L.append("every bar matches the loop within tolerance — no bar-scale "
                 "event, and no arrangement either.")
        return "\n".join(L)
    L.append(f"{'bar':>4s}{'t':>7s}{'rms':>7s}  what differs")
    for b in outliers:
        what = []
        for role, s in b["missing_steps"].items():
            what.append(f"{role} missing {s}")
        for role, s in b["extra_steps"].items():
            what.append(f"{role} extra {s}")
        if b.get("band_delta_db"):
            worst = max(b["band_delta_db"].items(), key=lambda kv: abs(kv[1]))
            if abs(worst[1]) >= 3:
                what.append(f"{worst[0]} {worst[1]:+.1f} dB")
        L.append(f"{b['bar']:>4d}{b['t']:>7.1f}{b['rms_delta_db']:>+7.1f}  "
                 + "; ".join(what or ["level only"]))
    return "\n".join(L)


def main():
    import argparse
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import groove_ear

    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-stems", action="store_true")
    a = ap.parse_args()

    y, sr = librosa.load(a.render, sr=44100, mono=True)
    tempo0, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    tempo = groove_ear.fold_tempo(tempo0)
    beats_t = librosa.frames_to_time(beats, sr=sr)
    downbeat = groove_ear.find_downbeat(y, sr, tempo, beats_t)
    drums = None
    if not a.no_stems:                      # the KICK row is only a kick row here
        try:
            import stems as stems_mod
            st = stems_mod.separate(a.render, sr=sr, verbose=False)
            if float(np.max(np.abs(st["drums"]))) > 1e-4:
                drums = st["drums"]
        except Exception as e:
            print(f"(stems unavailable, patterns from the full mix: {e})")
    res = analyze(y, sr, tempo, downbeat, beats_t, drums=drums)
    if a.json:
        import json
        print(json.dumps(res, indent=1))
        return
    print(describe(res, max_rows=16))


if __name__ == "__main__":
    main()
