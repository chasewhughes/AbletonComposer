#!/usr/bin/env python3
"""Structure ear — the arrangement as a narrative, not a number.

Segments the render at bar-snapped novelty peaks, then describes each section
in terms a composer uses: how loud, what's playing (per-stem activity), and
what CHANGED at the boundary (entered / exited / got brighter). The output is
a timeline table — the difference between "novelty_std 0.24" and "bars 1-16
are identical, the hats never open up, nothing enters at bar 17".
"""
import numpy as np
import librosa


def segment_boundaries(y, sr, tempo, max_sections=12):
    """Bar-snapped section boundaries from an MFCC+chroma novelty curve."""
    hop = 512
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    X = np.vstack([librosa.util.normalize(mfcc, axis=1),
                   librosa.util.normalize(chroma, axis=1)])
    bar_frames = max(1, int(round((60.0 / tempo * 4) / (hop / sr))))
    # bar-synchronous feature means -> self-similarity -> checkerboard novelty
    n_bars = X.shape[1] // bar_frames
    if n_bars < 4:
        return [0.0, len(y) / sr]
    Xb = np.stack([X[:, i * bar_frames:(i + 1) * bar_frames].mean(axis=1)
                   for i in range(n_bars)], axis=1)
    Xb = librosa.util.normalize(Xb, axis=0)
    ssm = Xb.T @ Xb
    k = 4  # bars of context on each side
    nov = np.zeros(n_bars)
    for i in range(k, n_bars - k):
        a = ssm[i - k:i, i - k:i].mean() + ssm[i:i + k, i:i + k].mean()
        b = 2 * ssm[i - k:i, i:i + k].mean()
        nov[i] = a - b
    if nov.max() > 0:
        nov /= nov.max()
    peaks = [i for i in range(k, n_bars - k)
             if nov[i] > 0.35 and nov[i] == nov[max(0, i - 2):i + 3].max()]
    peaks = peaks[:max_sections - 1]
    bar_s = 60.0 / tempo * 4
    bounds = [0.0] + [p * bar_s for p in peaks] + [len(y) / sr]
    return sorted(set(round(b, 3) for b in bounds))


def describe(y, sr, tempo, stems=None, bounds=None):
    """Per-section stats + per-stem activity. stems: {name: mono array at sr}."""
    bounds = bounds or segment_boundaries(y, sr, tempo)
    bar_s = 60.0 / tempo * 4
    bands = [("low", 25, 120), ("mid", 350, 2000), ("high", 5000, 16000)]

    def section_stats(sig, a, b):
        seg = sig[int(a * sr):int(b * sr)]
        if len(seg) < sr:
            return None
        return float(np.sqrt(np.mean(seg ** 2)) + 1e-12)

    sections = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = y[int(a * sr):int(b * sr)]
        if len(seg) < sr:
            continue
        S = np.abs(librosa.stft(seg, n_fft=2048))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        tot = S.sum() + 1e-12
        band_share = {n: float(S[(freqs >= lo) & (freqs < hi)].sum() / tot)
                      for n, lo, hi in bands}
        sec = {"start_s": round(a, 1), "end_s": round(b, 1),
               "bars": f"{int(round(a / bar_s)) + 1}-{int(round(b / bar_s))}",
               "rms_db": round(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12), 1),
               "band_share": {k: round(v, 3) for k, v in band_share.items()}}
        if stems:
            act = {}
            for name, s in stems.items():
                r = section_stats(s, a, b)
                peak = float(np.sqrt(np.mean(s ** 2)) + 1e-12)
                act[name] = round(r / peak, 2) if r else 0.0
            sec["stem_activity"] = act
        sections.append(sec)

    # boundary diffs: what changed
    for i in range(1, len(sections)):
        prev, cur = sections[i - 1], sections[i]
        notes = []
        d_rms = cur["rms_db"] - prev["rms_db"]
        if abs(d_rms) >= 2:
            notes.append(f"{'louder' if d_rms > 0 else 'quieter'} {abs(d_rms):.0f} dB")
        for k in cur["band_share"]:
            d = cur["band_share"][k] - prev["band_share"][k]
            if abs(d) > 0.06:
                notes.append(f"{k} {'up' if d > 0 else 'down'}")
        if "stem_activity" in cur:
            for name in cur["stem_activity"]:
                a0 = prev.get("stem_activity", {}).get(name, 0)
                a1 = cur["stem_activity"][name]
                if a0 < 0.25 <= a1:
                    notes.append(f"{name} enters")
                elif a1 < 0.25 <= a0:
                    notes.append(f"{name} exits")
        cur["change"] = ", ".join(notes) if notes else "no audible change"
    if sections:
        sections[0]["change"] = "start"
    return sections


def render_table(sections):
    lines = [f"{'bars':>9s} {'time':>11s} {'rms':>7s}  what changed"]
    for s in sections:
        t = f"{s['start_s']:.0f}-{s['end_s']:.0f}s"
        lines.append(f"{s['bars']:>9s} {t:>11s} {s['rms_db']:>6.1f}  {s.get('change', '')}")
    if len(sections) <= 1:
        lines.append("  (one section: the arrangement never changes — that is "
                     "itself the finding)")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    y, sr = librosa.load(sys.argv[1], sr=44100, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    t = float(np.atleast_1d(tempo)[0])
    while t < 100:
        t *= 2
    while t > 180:
        t /= 2
    print(render_table(describe(y, sr, t)))
