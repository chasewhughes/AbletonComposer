#!/usr/bin/env python3
"""Band profile of a one-shot, against the target for its role.

Forging a sample is only half the job; the other half is checking that the
chain moved energy the way it was supposed to. A kick that gains 120-350 Hz is
a worse kick no matter how good the chain looked on paper.
"""
import os
import sys

import librosa
import numpy as np

BANDS = [("sub", 20, 60), ("bass", 60, 120), ("lowmid", 120, 350),
         ("mid", 350, 2000), ("himid", 2000, 6000), ("high", 6000, 16000)]
# role -> target share % per band, from the raw-source and reference survey
TARGETS = {
    "kick": {"sub": 30, "bass": 22, "lowmid": 16, "mid": 20, "himid": 8, "high": 4},
    "hat": {"sub": 1, "bass": 1, "lowmid": 3, "mid": 15, "himid": 35, "high": 45},
    "perc": {"sub": 2, "bass": 4, "lowmid": 12, "mid": 40, "himid": 27, "high": 15},
}


def profile(path):
    y, sr = librosa.load(path, sr=44100, mono=True)
    S = np.abs(librosa.stft(y, n_fft=4096))
    fr = librosa.fft_frequencies(sr=sr, n_fft=4096)
    m = S.sum(axis=1)
    tot = m.sum() + 1e-9
    return ({n: 100 * m[(fr >= lo) & (fr < hi)].sum() / tot for n, lo, hi in BANDS},
            float(fr[m.argmax()]), len(y) / sr)


def main():
    role = None
    paths = []
    for a in sys.argv[1:]:
        if a.startswith("--role="):
            role = a.split("=", 1)[1]
        else:
            paths.append(a)
    tgt = TARGETS.get(role)
    hdr = f"{'sample':30s}" + "".join(f"{b[0]:>9s}" for b in BANDS) + f"{'peak':>8s}{'dur':>7s}"
    print(hdr)
    if tgt:
        print(f"{'TARGET (' + role + ')':30s}" +
              "".join(f"{tgt.get(b[0], 0):8.0f}%" for b in BANDS))
    for p in paths:
        bands, peak, dur = profile(p)
        row = "".join(f"{bands[b[0]]:8.1f}%" for b in BANDS)
        print(f"{os.path.basename(p)[:29]:30s}{row}{peak:8.0f}{dur:7.2f}")
        if tgt:
            dev = "".join(f"{bands[b[0]] - tgt.get(b[0], 0):+8.1f} " for b in BANDS)
            print(f"{'  delta vs target':30s}{dev}")


if __name__ == "__main__":
    main()
