#!/usr/bin/env python3
"""Reference-anchored audio critic for the genre-invention loop.

Two jobs:
1. `build` — fingerprint every reference file into reference-audio/fingerprints.json.
   References define OCCUPIED territory: the corners of existing techno.
2. `score <render.wav>` — score a render on two axes:
     techno_core: closeness to the shared core all corners have in common
                  (kick-anchored pulse, club spectral balance, loudness)
     novelty:     distance from the NEAREST occupied corner on style axes.
   A great genre-invention render scores HIGH on both. Generic = high core,
   low novelty. Broken = low core.

Full tracks (Drumcode singles) are fingerprinted whole; DJ mixes (Hawtin) are
sampled at 25/50/75% in 90 s windows — they inform groove/texture corners, not
single-track arrangement.

Usage:
  .venv-analysis/bin/python tools/critic.py build
  .venv-analysis/bin/python tools/critic.py score path/to/render.wav
"""
import json
import pathlib
import sys

import numpy as np
import librosa
import pyloudnorm
import soundfile as sf

REPO = pathlib.Path(__file__).resolve().parent.parent
REF_DIR = REPO / "reference-audio"
DB_PATH = REF_DIR / "fingerprints.json"

SR = 22050
BANDS = {  # Hz edges; band balance is the club-system signature
    "sub": (20, 60), "bass": (60, 120), "lowmid": (120, 350),
    "mid": (350, 2000), "highmid": (2000, 6000), "high": (6000, 10500),
}
# Features that define the shared techno core (a render must be close on these)
CORE_KEYS = ["four_floor_strength", "tempo", "onset_rate", "lufs",
             "bal_sub", "bal_bass", "bal_mid", "bal_high"]
# Features that define stylistic identity (novelty = distance on these)
STYLE_KEYS = ["centroid_mean", "centroid_std", "flatness_mean", "crest",
              "microtiming_ms", "sync_offgrid", "rep_1bar", "rep_4bar",
              "novelty_std", "bal_lowmid", "bal_highmid", "onset_rate"]


def band_energies(S, freqs):
    total = S.sum() + 1e-9
    return {f"bal_{name}": float(S[(freqs >= lo) & (freqs < hi)].sum() / total)
            for name, (lo, hi) in BANDS.items()}


def extract(path, offset=0.0, duration=None):
    y, sr = librosa.load(path, sr=SR, mono=True, offset=offset, duration=duration)
    if len(y) < SR * 10:
        raise ValueError(f"too short: {path}")
    feat = {}

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    # techno lives 120-150; fold octave errors toward that range
    while tempo < 100:
        tempo *= 2
    while tempo > 180:
        tempo /= 2
    feat["tempo"] = tempo

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")
    dur = len(y) / sr
    feat["onset_rate"] = float(len(onsets) / dur)

    # four-on-the-floor strength: autocorrelation of onset envelope at the beat lag
    hop_t = 512 / sr
    beat_lag = int(round((60.0 / tempo) / hop_t))
    env = onset_env - onset_env.mean()
    ac = librosa.autocorrelate(env)
    ac = ac / (ac[0] + 1e-9)
    feat["four_floor_strength"] = float(ac[beat_lag]) if beat_lag < len(ac) else 0.0

    # microtiming: onset deviation from a rigid 16th grid at detected tempo
    if len(onsets) > 8:
        grid = 60.0 / tempo / 4.0
        dev = np.array([min(t % grid, grid - (t % grid)) for t in onsets])
        feat["microtiming_ms"] = float(np.median(dev) * 1000)
        feat["sync_offgrid"] = float(np.mean(dev > grid * 0.25))  # share of notes far off-grid
    else:
        feat["microtiming_ms"], feat["sync_offgrid"] = 0.0, 0.0

    S = np.abs(librosa.stft(y, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    feat.update(band_energies(S.sum(axis=1), freqs))
    feat["centroid_mean"] = float(librosa.feature.spectral_centroid(S=S, sr=sr).mean())
    feat["centroid_std"] = float(librosa.feature.spectral_centroid(S=S, sr=sr).std())
    feat["flatness_mean"] = float(librosa.feature.spectral_flatness(S=S).mean())

    # repetition signature: MFCC self-similarity at 1-bar and 4-bar lags
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    bar_frames = int(round((60.0 / tempo * 4) / hop_t))
    feat["rep_1bar"] = _lag_similarity(mfcc, bar_frames)
    feat["rep_4bar"] = _lag_similarity(mfcc, bar_frames * 4)

    # arrangement movement: novelty (spectral flux) variability over 8-bar windows
    flux = onset_env
    win = bar_frames * 8
    if win > 0 and len(flux) > 2 * win:
        blocks = [flux[i:i + win].mean() for i in range(0, len(flux) - win, win)]
        feat["novelty_std"] = float(np.std(blocks) / (np.mean(blocks) + 1e-9))
    else:
        feat["novelty_std"] = 0.0

    # loudness/dynamics on the raw file (native sr, first 4 min max)
    native_sr = sf.info(path).samplerate
    data, native_sr = sf.read(path, frames=-1 if duration is None else int(duration * native_sr), start=int(offset * native_sr), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    try:
        feat["lufs"] = float(pyloudnorm.Meter(native_sr).integrated_loudness(data))
    except Exception:
        feat["lufs"] = -70.0
    rms = np.sqrt(np.mean(mono ** 2)) + 1e-9
    feat["crest"] = float(20 * np.log10(np.max(np.abs(mono)) / rms))
    return feat


def _lag_similarity(mfcc, lag):
    if lag <= 0 or mfcc.shape[1] < 2 * lag:
        return 0.0
    a, b = mfcc[:, :-lag], mfcc[:, lag:]
    a = (a - a.mean(axis=1, keepdims=True))
    b = (b - b.mean(axis=1, keepdims=True))
    num = (a * b).sum()
    den = np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-9
    return float(num / den)


def reference_files():
    """Yield (path, corner_tag, offset, duration) tuples."""
    manifest = {}
    mpath = REF_DIR / "previews" / "manifest.json"
    if mpath.exists():
        manifest = {e["file"]: e["corner"] for e in json.loads(mpath.read_text())}
    for f in sorted((REF_DIR / "previews-wav").glob("*.wav")):
        yield f, manifest.get(f.stem + ".m4a", "unknown"), 0.0, None
    for f in sorted((REF_DIR / "Drumcode").glob("*.mp3")):
        yield f, "drumcode-peaktime", 0.0, None
    for f in sorted((REF_DIR / "Richie_Hawtin_Minimalist").glob("*.mp3")):
        try:
            total = sf.info(str(f)).duration
        except Exception:
            total = 3600
        for frac in (0.25, 0.5, 0.75):
            yield f, "hawtin-minimal-mix", max(0.0, total * frac - 45), 90.0


def build():
    db = []
    for path, corner, offset, duration in reference_files():
        label = f"{path.name}" + (f"@{int(offset)}s" if offset else "")
        try:
            feat = extract(str(path), offset=offset, duration=duration)
        except Exception as e:
            print(f"SKIP {label}: {e}", file=sys.stderr)
            continue
        db.append({"file": path.name, "corner": corner, "offset": offset, "features": feat})
        print(f"ok {label:70s} corner={corner} tempo={feat['tempo']:.0f}")
    DB_PATH.write_text(json.dumps(db, indent=1))
    print(f"\n{len(db)} fingerprints -> {DB_PATH}")


def _matrix(db, keys):
    return np.array([[e["features"].get(k, 0.0) for k in keys] for e in db])


def score(render_path):
    db = json.loads(DB_PATH.read_text())
    feat = extract(render_path)
    core_ref = _matrix(db, CORE_KEYS)
    mu, sigma = core_ref.mean(axis=0), core_ref.std(axis=0) + 1e-9
    core_z = np.abs((np.array([feat[k] for k in CORE_KEYS]) - mu) / sigma)
    techno_core = float(np.exp(-core_z.mean()))  # 1 = dead center, ->0 = not techno

    style_ref = _matrix(db, STYLE_KEYS)
    s_mu, s_sigma = style_ref.mean(axis=0), style_ref.std(axis=0) + 1e-9
    style_ref_z = (style_ref - s_mu) / s_sigma
    render_z = (np.array([feat[k] for k in STYLE_KEYS]) - s_mu) / s_sigma
    dists = np.linalg.norm(style_ref_z - render_z, axis=1)
    novelty = float(dists.min() / np.sqrt(len(STYLE_KEYS)))  # distance to NEAREST occupied corner

    nearest = db[int(np.argmin(dists))]
    report = {
        "techno_core": round(techno_core, 3),
        "novelty": round(novelty, 3),
        "verdict": ("BROKEN (not techno)" if techno_core < 0.35 else
                    "GENERIC (occupied territory)" if novelty < 0.8 else
                    "NEW TERRITORY" if techno_core >= 0.5 else "RISKY"),
        "nearest_neighbor": f"{nearest['file']} ({nearest['corner']})",
        "core_outliers": {k: round(float(z), 2) for k, z in zip(CORE_KEYS, core_z) if z > 1.5},
        "features": {k: round(v, 3) for k, v in feat.items()},
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("build", "score"):
        sys.exit(__doc__)
    if sys.argv[1] == "build":
        build()
    else:
        score(sys.argv[2])
