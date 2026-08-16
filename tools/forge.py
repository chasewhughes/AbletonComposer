#!/usr/bin/env python3
"""Sample forge: synthesize one-of-a-kind drum/texture samples in raw DSP.

No 909 clones. Each generator makes deliberate non-classic choices so the
palette has its own DNA:

  kick   — dual-stage pitch drop (fast knee then slow settle), a SUBHARMONIC
           an octave down that blooms mid-decay, tanh drive with its own
           envelope, and a resonant 'crack' ping instead of a click.
  hat    — inharmonic partial stack at custom irrational ratios ring-modded
           with noise, then bandpassed; closed/open are the same voice with
           different decay + tilt, so they sound related (a real kit trait).
  perc   — a struck-metal FM voice with two carriers detuned by a golden-ratio
           factor; reads as 'ping' but pitches like nothing standard.
  air    — slow filtered-noise swell for texture beds.

Every voice is deterministic given (name, seed): the identity is reproducible
and mutatable. Output: 44.1k mono WAV, peak -1 dBFS, into Live's User Library
so the browser can load them onto Simpler.

Usage: .venv-analysis/bin/python tools/forge.py [--seed 707] [--out DIR]
"""
import argparse
import os

import numpy as np
import soundfile as sf

SR = 44100
OUT_DEFAULT = os.path.expanduser("~/Music/Ableton/User Library/Samples/Forged")


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _norm(x, peak_db=-1.0):
    p = np.max(np.abs(x)) + 1e-9
    return x / p * (10 ** (peak_db / 20))


def _env(t, attack, decay, curve=4.0):
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-np.maximum(t - attack, 0) / decay * curve)
    return a * d


def _bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def kick(seed=0, dur=0.5, f_start=170.0, f_knee=74.0, f_end=56.0,
         knee_ms=28.0, sub_bloom=0.16, drive=3.2, crack_hz=1170.0):
    rng = np.random.default_rng(seed)
    t = _t(dur)
    # dual-stage pitch: fast exponential to the knee, then slow settle
    k = knee_ms / 1000.0
    f = np.where(t < k,
                 f_knee + (f_start - f_knee) * np.exp(-t / (k / 3)),
                 f_end + (f_knee - f_end) * np.exp(-(t - k) / 0.12))
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * _env(t, 0.0005, 0.26)
    # subharmonic an octave down, blooming after the transient
    sub = np.sin(phase / 2) * _env(t, 0.05, 0.30) * sub_bloom
    # drive with its own decaying envelope: bite up front, clean tail
    d_env = 1 + (drive - 1) * np.exp(-t / 0.06)
    x = np.tanh((body + sub) * d_env)
    # resonant crack instead of a noise click
    ping = np.sin(2 * np.pi * crack_hz * t) * _env(t, 0.0002, 0.004) * 0.5
    ping += rng.normal(0, 0.08, len(t)) * _env(t, 0.0002, 0.002)
    return _norm(x + ping)


HAT_RATIOS = [1.0, 1.4142, 1.7321, 2.2361, 2.6458, 3.3166]  # sqrt-primes


def hat(seed=0, dur=0.35, base=413.0, decay=0.055, tilt=0.5, open_=False):
    rng = np.random.default_rng(seed)
    t = _t(dur)
    x = np.zeros_like(t)
    for i, r in enumerate(HAT_RATIOS):
        f = base * r * (1 + rng.uniform(-0.004, 0.004))
        w = np.sign(np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)))  # square
        x += w * (1.0 - tilt * i / len(HAT_RATIOS))
    noise = rng.normal(0, 1, len(t))
    x = x * (0.65 + 0.35 * noise)                     # ring-mod with noise
    x = _bandpass(x, 5200, 11800)
    d = decay * (4.5 if open_ else 1.0)
    return _norm(x * _env(t, 0.0008, d, curve=5.0))


PHI = 1.6180339887


def perc(seed=0, dur=0.5, f0=520.0, fm_ratio=None, index=7.0, decay=0.12):
    rng = np.random.default_rng(seed)
    t = _t(dur)
    fm_ratio = fm_ratio or (PHI + rng.uniform(-0.05, 0.05))
    mod = np.sin(2 * np.pi * f0 * fm_ratio * t) * index * np.exp(-t / (decay * 0.6))
    c1 = np.sin(2 * np.pi * f0 * t + mod)
    c2 = np.sin(2 * np.pi * f0 * PHI * 0.5 * t + mod * 0.7)
    x = (c1 + 0.6 * c2) * _env(t, 0.0008, decay)
    return _norm(np.tanh(x * 1.6))


def air(seed=0, dur=2.0, lo=800, hi=6000):
    rng = np.random.default_rng(seed)
    x = _bandpass(rng.normal(0, 1, int(SR * dur)), lo, hi)
    t = _t(dur)
    swell = np.sin(np.pi * t / dur) ** 2
    return _norm(x * swell, peak_db=-6)


VOICES = {
    "kick": kick,
    "hat_closed": lambda seed: hat(seed, open_=False),
    "hat_open": lambda seed: hat(seed, dur=1.0, open_=True),
    "perc": perc,
    "air": air,
}


def forge_kit(seed, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for name, fn in VOICES.items():
        y = fn(seed=seed)
        path = os.path.join(out_dir, f"forged_{name}_{seed}.wav")
        sf.write(path, y.astype(np.float32), SR, subtype="PCM_24")
        paths[name] = path
        print(f"forged {name:11s} -> {path}  ({len(y)/SR:.2f}s)")
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=707)
    ap.add_argument("--out", default=OUT_DEFAULT)
    forge_kit(ap.parse_args().seed, ap.parse_args().out)
