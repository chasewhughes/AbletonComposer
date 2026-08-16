#!/usr/bin/env python3
"""Stem separation (demucs htdemucs) with content-addressed caching.

Separation on CPU costs minutes; a re-listen of the same render must not pay
twice. Stems are cached under .cache/stems/<sha1[:12]>/ keyed by file content.

separate() returns {"drums"|"bass"|"other"|"vocals": mono float32 at `sr`}.
For techno the "vocals" stem is usually leakage; callers typically fold it
into "other" or ignore it.
"""
import hashlib
import pathlib

import numpy as np

REPO = pathlib.Path(__file__).resolve().parent.parent
CACHE = REPO / ".cache" / "stems"
MODEL = "htdemucs"
STEM_NAMES = ["drums", "bass", "other", "vocals"]


def _key(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def separate(path, sr=44100, verbose=True):
    """Return stems dict, cached. Raises ImportError if demucs missing."""
    import soundfile as sf
    import librosa

    cdir = CACHE / _key(path)
    if all((cdir / f"{n}.wav").exists() for n in STEM_NAMES):
        out = {}
        for n in STEM_NAMES:
            y, file_sr = sf.read(cdir / f"{n}.wav", dtype="float32", always_2d=True)
            y = y.mean(axis=1)
            if file_sr != sr:
                y = librosa.resample(y, orig_sr=file_sr, target_sr=sr)
            out[n] = y
        return out

    import torch
    from demucs.api import Separator

    # mps is ~1.3x cpu on an M3 and identical in output; fall back silently
    # because a torch built without it raises only at separate time.
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    if verbose:
        print(f"  separating stems ({MODEL}, {device}) — first pass on this "
              f"file, cached afterwards ...")
    try:
        sep = Separator(model=MODEL, device=device, progress=verbose)
        _, separated = sep.separate_audio_file(str(path))
    except Exception:
        if device == "cpu":
            raise
        sep = Separator(model=MODEL, device="cpu", progress=verbose)
        _, separated = sep.separate_audio_file(str(path))

    cdir.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, tensor in separated.items():
        y = tensor.detach().cpu().numpy()          # (channels, samples)
        mono = y.mean(axis=0).astype(np.float32)
        sf.write(cdir / f"{name}.wav", mono, sep.samplerate)
        if sep.samplerate != sr:
            mono = librosa.resample(mono, orig_sr=sep.samplerate, target_sr=sr)
        out[name] = mono
    return out


if __name__ == "__main__":
    import sys
    stems = separate(sys.argv[1])
    for k, v in stems.items():
        rms = float(np.sqrt(np.mean(v ** 2)))
        print(f"{k:8s} rms={20 * np.log10(rms + 1e-12):6.1f} dB  {len(v)} samples")
