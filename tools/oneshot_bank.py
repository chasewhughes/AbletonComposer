#!/usr/bin/env python3
"""One-shot bank — judge a forged sample against the hits in the reference
records instead of against a hand-written target.

Why this exists. `profile_sample.py` printed a candidate's band shares beside a
TARGETS dict somebody guessed ("a kick should be 30% sub, 22% bass, ..."). Every
other reading in this project moved to `calibrate.py`, which measures the nine
Drumcode singles and stores median / robust-sigma / p10 / p90 per metric per
context. One-shots were the last thing still judged by a guess, and the guess
could not answer the actual question: "is forged_metal_bell a good bell?"

The fix is the same fix calibrate.py applied to mixes — go get the real
distribution. The reference drum stems contain thousands of real kicks, hats and
percussion hits. Cut them out, measure them, and a candidate one-shot becomes a
z-score against a corpus rather than a delta against an opinion.

  build     For every cached reference excerpt: demucs drum stem -> onsets per
            role band (groove_ear's detector, prominence gate and all) -> a
            ~300 ms slice per onset -> features -> `reference-audio/oneshot_bank.json`.
  show      The distribution per role, so you can read the corpus directly.
  profile   A candidate one-shot as z-scores against its role, in plain language.

Three findings from building it, recorded so they are not re-discovered:

1. BAND SHARES MUST BE POWER, NOT MAGNITUDE. profile_sample.py summed linear
   STFT magnitude per band. Bands are wildly unequal in bin count (20-60 Hz is
   4 bins at n_fft=4096, 2-6 kHz is 371), so summing magnitude hands the wide
   bands a structural advantage. A textbook Drumcode kick — 77% of its ENERGY
   below 60 Hz, spectral peak 53.8 Hz — measured 18.6% "sub" and 31.7% "high"
   under the old method. The hand-written TARGETS were fitted to that distorted
   measure, which is why "kick sub 30%" looked plausible. This module uses power
   shares, and a reference kick reads sub ~77%.

2. THE DETECTING BAND AND THE SLICE MUST AGREE. Every role band fires on a
   four-on-the-floor kick, because a kick transient is broadband: the HATS
   detector found 549 "hats" across six excerpts that were kicks. So a hit is
   kept only when the slice's own band dominance classifies it as the role of
   the band that detected it. Disagreement means the slice is a mixture, and a
   mixture is not a sample. This throws away real hats that land on a kick, and
   that is the correct trade: purity over recall.

3. THE BANK ONLY CONTAINS WHAT THE RECORDS CONTAIN. Kicks, hats, percussion.
   There is no bell, no duduk, no vocal in a Drumcode drum stem. `profile` says
   so out loud for anything outside the three roles, and refuses to score a bell
   against the percussion distribution just because that is the nearest bin.
"""
import argparse
import collections
import json
import pathlib
import sys
import time

import numpy as np

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

BANK_PATH = REPO / "reference-audio" / "oneshot_bank.json"
CLAP_PATH = REPO / "reference-audio" / "oneshot_clap.npz"
EXCERPT_DIR = REPO / ".cache" / "refexcerpt"
SR = 44100

# One-shot geometry.
#
# A drum stem is CONTINUOUS, and that sets the window length. At 130 BPM a 16th
# is 115 ms, so a 300 ms "hat sample" cut from a record contains two more hats
# and possibly a kick — it is a bar of music, not a one-shot. The first version
# of this module used 300 ms for everything and the hat bank came out bimodal
# (peak frequency p10 161 Hz, median 6815 Hz): the only hats that survived the
# purity filter were ones that happened to sit in a kick-free gap, which is a
# selection bias, not a distribution.
#
# So: window per role, sized to what that role can own alone at techno tempos.
# A kick gets 300 ms (its period is 430-500 ms, and a 16th-note hat inside the
# window is negligible against its sub power); hats and percussion get windows
# short enough to end before the next 16th.
ROLE_WINDOW = {"kick": 0.300, "hat": 0.100, "perc": 0.180}
# Role is decided on a short common window instead, so the decision is about
# the hit itself and not about whatever follows it.
CLASSIFY_S = 0.100
# 15 ms of pre-roll keeps the attack transient, which is most of what
# distinguishes a hat from a tick.
PRE_S = 0.015
N_FFT = 4096

BANK_ROLES = ("kick", "hat", "perc")
ROLE_OF_BAND = {"KICK": "kick", "PERC": "perc", "HATS": "hat"}

# A hit has to stand out from whatever is already ringing, or the "sample" is
# really a sample of the previous hit's tail with a bump on it. 6 dB over the
# 60 ms before the onset, measured in the detecting band's own envelope.
PROM_DB = 6.0
# Two flux peaks can anchor to the same envelope maximum; without this the same
# physical kick enters the bank twice and narrows its own sigma.
DEDUPE_S = 0.050

# Frequency and time features are ratio-scaled: 50 -> 100 Hz is the same
# perceptual step as 400 -> 800 Hz, and a robust sigma in raw Hz would make
# every hat's peak frequency look like a 30-sigma event next to a kick's.
# Stats for these are computed in log2 space and inverted for display.
LOG_FEATURES = {"peak_hz", "centroid_hz", "rolloff85_hz", "root_hz",
                "decay20_ms", "attack_ms", "peak_offset_ms"}

# Minimum robust sigma per feature — the resolution below which a difference is
# not a difference. Without these the bank is unusable at the extremes: the
# reference hats agree on sub share to within 0.007 percentage points (they all
# have none), so a hat with 0.2% sub scored z = +28, and a held-out REAL hat
# reached max|z| = 569. Any "how far out is the strangest axis" statistic then
# just reports which feature has the most degenerate sigma. The floors are set
# at roughly the audible resolution of each quantity: half a percentage point of
# band energy, half a dB, 6% in frequency or time (0.08 in log2).
SIGMA_FLOOR_LOG = 0.08
SIGMA_FLOOR = {"noisiness_db": 0.5, "crest_db": 0.5, "zcr": 0.01,
               "root_strength": 0.2, "flatness": 0.005,
               "decay_censored": 0.1}


# ------------------------------------------------------------------ features

def features(seg, sr):
    """Everything measurable about one ~300 ms hit, level-invariant.

    Level is deliberately absent: a one-shot's gain is the user's business and
    varies by 20 dB across a sample folder. Shape is what the corpus can judge.
    """
    import librosa
    import harmony_ear
    import ears

    S = np.abs(librosa.stft(seg, n_fft=N_FFT))
    fr = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    p = (S ** 2).mean(axis=1)                 # POWER — see finding 1
    tot = float(p.sum()) + 1e-20
    f = {f"share.{n}": float(100 * p[(fr >= lo) & (fr < hi)].sum() / tot)
         for n, lo, hi in ears.BANDS}
    f["peak_hz"] = float(fr[int(p.argmax())])

    # amplitude envelope at ~2.9 ms resolution: fine enough for a hat's decay
    hop = 128
    rms = librosa.feature.rms(y=seg, frame_length=512, hop_length=hop)[0]
    pk = int(rms.argmax())
    peak = float(rms[pk]) + 1e-12
    # decay to -20 dB. If the tail never gets there inside the slice the value
    # is censored at the slice length, and `decay_censored` says so rather than
    # the bank quietly recording "300 ms" as if it were measured.
    after = rms[pk:]
    below = np.nonzero(after < peak * 0.1)[0]
    f["decay20_ms"] = float((below[0] if len(below) else len(after)) * hop / sr * 1000)
    f["decay_censored"] = float(0.0 if len(below) else 1.0)
    # attack: -20 dB point before the peak up to the peak
    before = rms[:pk + 1]
    lo_idx = np.nonzero(before < peak * 0.1)[0]
    f["attack_ms"] = float(((pk - lo_idx[-1]) if len(lo_idx) else pk)
                           * hop / sr * 1000)
    f["attack_ms"] = max(f["attack_ms"], hop / sr * 1000)   # one frame floor

    # How long the hit takes to reach full level. forged_kick_iron peaks 460 ms
    # into its own file — a swell, not a kick — and no band-share or decay
    # number says that. This one does.
    f["peak_offset_ms"] = float(pk * hop / sr * 1000)

    f["centroid_hz"] = float(np.sum(fr * p) / tot)
    f["rolloff85_hz"] = float(fr[int(np.searchsorted(np.cumsum(p), 0.85 * tot))]
                              if tot > 0 else 0.0)
    # flatness: geometric/arithmetic mean of the power spectrum. 1 = white
    # noise, 0 = a pure tone. This is the axis that separates a hat (noise)
    # from a bell (tone), and it is the axis TARGETS had no way to express.
    pp = p + 1e-20
    f["flatness"] = float(np.exp(np.mean(np.log(pp))) / np.mean(pp))
    f["noisiness_db"] = float(10 * np.log10(f["flatness"] + 1e-20))
    f["zcr"] = float(np.mean(np.abs(np.diff(np.sign(seg))) > 0))
    f["crest_db"] = float(20 * np.log10((np.max(np.abs(seg)) + 1e-12) /
                                        (np.sqrt(np.mean(seg ** 2)) + 1e-12)))

    # Pitched content. harmony_ear.root_hz sums each candidate's harmonic
    # series instead of taking the loudest partial — a plain spectral peak on a
    # kick with a scooped fundamental lands an octave high.
    r, strength = harmony_ear.root_hz(seg, sr, fmin=25.0, fmax=4000.0)
    f["root_hz"] = float(r) if r > 0 else float("nan")
    f["root_strength"] = float(strength)
    return f


def classify(f):
    """Which role does this slice's own energy say it is?

    Deliberately crude and deliberately fixed: this is the label the bank is
    built on, so it has to be the same rule at build time and at profile time.
    Always fed the CLASSIFY_S window, never the role window, or the label would
    depend on the answer.

    The hat test is strict (almost nothing below 350 Hz) because the loose
    version — top >= 55%, low < 15% — let through hats riding a kick tail and
    made the hat bank bimodal in peak frequency.
    """
    low = f["share.sub"] + f["share.bass"]
    top = f["share.highmid"] + f["share.high"] + f["share.air"]
    if low >= 50:
        return "kick"
    if top >= 60 and low < 5 and f["share.lowmid"] < 10:
        return "hat"
    return "perc"


# ------------------------------------------------------------- extracting hits

def excerpt_hits(path, verbose=False, keep_audio=False):
    """Every clean, unambiguous drum hit in one reference excerpt.

    Reuses groove_ear's band-flux detector and its validated ROLE_GATE
    prominence rule — the gate that took the reference kick rows from 4-5
    hits/s down to the real 2.2/s. Writing a second onset detector here would
    mean re-earning that fix.
    """
    import librosa
    import groove_ear
    import stems as stems_mod

    st = stems_mod.separate(str(path), sr=SR, verbose=False)
    d = st["drums"]

    onset_env = librosa.onset.onset_strength(y=d, sr=SR)
    _, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=SR,
                                       trim=False)
    bt = librosa.frames_to_time(beats, sr=SR)
    if len(bt) < 8:
        return []
    tempo = groove_ear.fold_tempo(60.0 / float(np.median(np.diff(bt))))

    hop = groove_ear.HOP
    out = []
    for band, lo, hi in groove_ear.ROLES:
        role = ROLE_OF_BAND[band]
        env, flux, peaks = groove_ear.band_flux(d, SR, lo, hi)
        peaks = groove_ear.prominence_gate(flux, peaks, SR, tempo,
                                           *groove_ear.ROLE_GATE[band])
        last_anchor = -1
        win = int(ROLE_WINDOW[role] * SR)
        for pk in peaks:
            # Anchor on the FLUX peak, not the envelope maximum. Flux peaks at
            # the fastest rise, i.e. essentially at the onset; the envelope
            # peaks later, at the body — and anchoring on the body cuts the
            # attack off the front of the sample. The 15 ms pre-roll then also
            # covers the STFT window's own lag.
            if pk - last_anchor < DEDUPE_S * SR / hop:
                continue
            # prominence is a body-vs-what-came-before question, so it uses the
            # envelope maximum just after the onset
            w = int(0.030 * SR / hop)
            a = int(np.argmax(env[max(0, pk - 1):pk + w + 1])) + max(0, pk - 1)
            pre = env[max(0, pk - int(0.060 * SR / hop)):
                      max(1, pk - int(0.012 * SR / hop))]
            prom = 20 * np.log10((env[a] + 1e-12) /
                                 (float(pre.mean()) + 1e-12)) if len(pre) else 0.0
            if prom < PROM_DB:
                continue
            i0 = int(pk * hop) - int(PRE_S * SR)
            if i0 < int(0.08 * SR) or i0 + int(0.300 * SR) > len(d):
                continue
            cls_seg = np.ascontiguousarray(d[i0:i0 + int(CLASSIFY_S * SR)])
            if float(np.max(np.abs(cls_seg))) < 1e-4:
                continue
            if classify(features(cls_seg, SR)) != role:
                continue                 # see finding 2 — mixture, not a sample
            seg = np.ascontiguousarray(d[i0:i0 + win])
            last_anchor = pk
            hit = {"role": role, "t": round(pk * hop / SR, 3),
                   "prom_db": round(float(prom), 1), "f": features(seg, SR)}
            if keep_audio:
                hit["audio"] = seg
            out.append(hit)
    if verbose:
        c = collections.Counter(h["role"] for h in out)
        print(f"  {path.name[:52]:52s} " +
              " ".join(f"{r}={c.get(r, 0):4d}" for r in BANK_ROLES))
    return out


def track_of(label):
    """Excerpt filename -> the record it came from. Two excerpts of one track
    share the same kick SAMPLE, so hold-out has to be per track, not per
    excerpt, or it validates memorisation."""
    return label.split("__")[0]


# ---------------------------------------------------------------- statistics

def _stat_values(key, vals):
    """calibrate._stat, in log2 space for the ratio-scaled features."""
    import calibrate
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) < 3:
        return None
    if key in LOG_FEATURES:
        vals = vals[vals > 0]
        if len(vals) < 3:
            return None
        st = calibrate._stat(np.log2(vals))
        st["log"] = True
        floor = SIGMA_FLOOR_LOG
    else:
        st = calibrate._stat(vals)
        st["log"] = False
        floor = SIGMA_FLOOR.get(key, 0.5 if key.startswith("share.") else 0.0)
    st["sigma"] = round(max(st["sigma"], floor), 4)
    return st


def stats_for(hits):
    """{feature: stat} over a list of hits of one role."""
    keys = sorted({k for h in hits for k in h["f"]})
    out = {}
    for k in keys:
        st = _stat_values(k, [h["f"][k] for h in hits if k in h["f"]])
        if st:
            out[k] = st
    return out


def zscore(st, value):
    if st is None or not np.isfinite(value):
        return float("nan")
    v = np.log2(value) if st.get("log") and value > 0 else value
    if st.get("log") and value <= 0:
        return float("nan")
    return float((v - st["median"]) / max(st["sigma"], 1e-9))


def disp(st, key, which="median"):
    """Stat back in display units."""
    v = st[which]
    return 2 ** v if st.get("log") else v


# The features `profile` scores and prints, in reading order. `decay_censored`
# and `root_strength` are bank bookkeeping, not verdict material.
REPORT_FEATURES = [
    ("share.sub", "sub 20-60 Hz", "{:6.1f}%"),
    ("share.bass", "bass 60-120", "{:6.1f}%"),
    ("share.lowmid", "lowmid 120-350", "{:6.1f}%"),
    ("share.mid", "mid 350-2k", "{:6.1f}%"),
    ("share.highmid", "highmid 2-6k", "{:6.1f}%"),
    ("share.high", "high 6-12k", "{:6.1f}%"),
    ("share.air", "air 12-20k", "{:6.1f}%"),
    ("peak_hz", "peak freq", "{:6.0f}Hz"),
    ("root_hz", "fundamental", "{:6.0f}Hz"),
    ("centroid_hz", "centroid", "{:6.0f}Hz"),
    ("rolloff85_hz", "rolloff 85%", "{:6.0f}Hz"),
    ("decay20_ms", "decay to -20dB", "{:6.0f}ms"),
    ("attack_ms", "attack", "{:6.1f}ms"),
    ("peak_offset_ms", "onset->peak", "{:6.1f}ms"),
    ("noisiness_db", "noisiness", "{:6.1f}dB"),
    ("crest_db", "crest", "{:6.1f}dB"),
    ("zcr", "zero-cross rate", "{:6.3f}  "),
]
# Which features decide "is this hit typical of the corpus". Frequency shape,
# envelope and noise character — the things a sample designer controls. Band
# shares are left out of the aggregate because they are seven correlated views
# of one fact and would swamp everything else.
CORE_FEATURES = ["peak_hz", "centroid_hz", "rolloff85_hz", "decay20_ms",
                 "attack_ms", "peak_offset_ms", "noisiness_db", "crest_db",
                 "share.sub", "share.mid", "share.high"]


OUTSIDE_Z = 2.5


def oddity(stats, f):
    """How far outside its own role does a hit sit — one number.

    Median |z| over CORE_FEATURES, not mean and not max. That is not an
    aesthetic preference, it is what survived the control: mean, RMS, top-3 and
    max were all measured on held-out reference hits and all have runaway tails
    (a real Drumcode hat reached max|z| = 569 before the sigma floors, and 27
    after), because a few features have almost no spread and dominate any
    extreme-sensitive statistic. The median is stable — held-out reference hits
    sit at 0.65-0.83 with p99 around 2.

    The cost of that robustness is real and is why `n_outside` exists too: a
    sound can match its role on most axes and differ on the two or three that
    define it. forged_metal_bell scores oddity 0.86 against reference
    percussion — genuinely typical on band shares, peak frequency and attack —
    while sitting 4-5 sigma out on noisiness, crest and rolloff. One number
    cannot say both things, so the report prints both.
    """
    zs = [abs(zscore(stats.get(k), f[k])) for k in CORE_FEATURES if k in f]
    zs = [z for z in zs if np.isfinite(z)]
    return float(np.median(zs)) if zs else float("nan")


def n_outside(stats, f):
    """How many reported axes sit >= 2.5 sigma outside the role, and which.

    The extreme-sensitive half of the reading. Calibrated the same way as
    oddity — `build` measures it on held-out reference hits — because "4 axes
    are outside" means nothing until you know that real records manage 2.
    """
    keys = [k for k, _, _ in REPORT_FEATURES if k in f]
    out = [k for k in keys
           if abs(zscore(stats.get(k), f[k])) >= OUTSIDE_Z]
    return len(out), out


# -------------------------------------------------------------------- build

def build(clap=False, verbose=True):
    excerpts = sorted(EXCERPT_DIR.glob("*__*s_*s.wav"))
    if not excerpts:
        sys.exit(f"no reference excerpts in {EXCERPT_DIR} — run "
                 f"`calibrate.py build` first")

    if verbose:
        print(f"extracting hits from {len(excerpts)} reference excerpts")
    all_hits = []
    keep_audio = bool(clap)
    for p in excerpts:
        t0 = time.time()
        try:
            hits = excerpt_hits(p, verbose=verbose, keep_audio=keep_audio)
        except Exception as e:
            print(f"  SKIP {p.name}: {e}")
            continue
        for h in hits:
            h["excerpt"] = p.stem
            h["track"] = track_of(p.stem)
        all_hits += hits
        if verbose:
            print(f"    ({time.time() - t0:.1f}s)")

    by_role = collections.defaultdict(list)
    for h in all_hits:
        by_role[h["role"]].append(h)

    bank = {
        "built_at": time.strftime("%Y-%m-%d %H:%M"),
        "excerpts": [p.stem for p in excerpts],
        "tracks": sorted({track_of(p.stem) for p in excerpts}),
        "role_window_s": ROLE_WINDOW, "classify_s": CLASSIFY_S,
        "pre_s": PRE_S, "sr": SR,
        "roles": {},
    }
    for role in BANK_ROLES:
        hits = by_role.get(role, [])
        if len(hits) < 20:
            print(f"  role '{role}': only {len(hits)} hits — not enough to be "
                  f"a distribution, omitted")
            continue
        bank["roles"][role] = {
            "n": len(hits),
            "n_tracks": len({h["track"] for h in hits}),
            "stats": stats_for(hits),
            "hits": [{k: h[k] for k in ("excerpt", "track", "t", "prom_db", "f")}
                     for h in hits],
        }

    # ---- hold-out control. THE method rule of this project: a detector that
    # flags real records is a bug. Rebuild the stats without one record, score
    # that record's hits, and see whether the corpus calls its own members
    # abnormal. If it does, the bank is too tight to be used on anything.
    if verbose:
        print("\nleave-one-record-out control")
    for role in bank["roles"]:
        hits = by_role[role]
        odd, nout, flagged = [], [], 0
        for track in sorted({h["track"] for h in hits}):
            held = [h for h in hits if h["track"] == track]
            rest = [h for h in hits if h["track"] != track]
            if len(rest) < 20 or not held:
                continue
            st = stats_for(rest)
            for h in held:
                o = oddity(st, h["f"])
                if np.isfinite(o):
                    odd.append(o)
                    nout.append(n_outside(st, h["f"])[0])
                    flagged += o > 2.0
        if not odd:
            continue
        odd = np.array(odd)
        nout = np.array(nout, dtype=float)
        bank["roles"][role]["holdout"] = {
            "n": int(len(odd)),
            "oddity_median": round(float(np.median(odd)), 3),
            "oddity_p90": round(float(np.percentile(odd, 90)), 3),
            "oddity_p99": round(float(np.percentile(odd, 99)), 3),
            "flag_rate_at_2": round(float(flagged / len(odd)), 4),
            # The whole held-out curve at 1% resolution. p90/p99 alone force a
            # three-bucket verdict; with this, `profile` can say "your kick is
            # further out than 94% of real Drumcode kicks", which is the
            # sentence that actually answers the question.
            "oddity_q": [round(float(v), 4)
                         for v in np.percentile(odd, np.arange(0, 101))],
            "n_outside_median": float(np.median(nout)),
            "n_outside_p90": float(np.percentile(nout, 90)),
            "n_outside_p99": float(np.percentile(nout, 99)),
            "n_outside_max": float(nout.max()),
        }
        if verbose:
            hb = bank["roles"][role]["holdout"]
            print(f"  {role:5s} n={hb['n']:5d}  oddity median "
                  f"{hb['oddity_median']:.2f}  p90 {hb['oddity_p90']:.2f}  "
                  f"p99 {hb['oddity_p99']:.2f}  "
                  f"flagged@2.0 {100 * hb['flag_rate_at_2']:.1f}%   "
                  f"axes>={OUTSIDE_Z}sigma: median {hb['n_outside_median']:.0f} "
                  f"p90 {hb['n_outside_p90']:.0f} p99 {hb['n_outside_p99']:.0f}")

    # ---- how much is an INSIDE verdict worth, per role?
    #
    # This control exists because forged_metal_bell scored INSIDE the perc
    # distribution on every statistic. Before believing the bank was wrong, ask
    # what "inside perc" even means: feed the OTHER roles' hits to each role's
    # own test. A distribution that accepts kicks as percussion is not
    # evidence of anything, and the report has to say so instead of printing a
    # confident verdict.
    for role, blk in bank["roles"].items():
        hb = blk.get("holdout")
        if not hb:
            continue
        st = blk["stats"]
        acc = {}
        for other in bank["roles"]:
            if other == role:
                continue
            oh = by_role[other]
            inside = sum(1 for h in oh
                         if oddity(st, h["f"]) <= hb["oddity_p90"])
            acc[other] = round(inside / max(1, len(oh)), 4)
        blk["cross_role_accept"] = acc
        if verbose:
            print(f"  {role:5s} test also accepts " +
                  ", ".join(f"{100 * v:.0f}% of {k}s" for k, v in acc.items()))

    if clap:
        _build_clap(by_role, bank, verbose=verbose)

    BANK_PATH.write_text(json.dumps(bank, indent=1))
    if verbose:
        print(f"\nbank -> {BANK_PATH}")
        for role, blk in bank["roles"].items():
            print(f"  {role:5s} {blk['n']:5d} hits from {blk['n_tracks']} records")
    return bank


# ------------------------------------------------------------------ CLAP side

# What CLAP is asked about a one-shot. Not "is this good" — CLAP has no
# reference for a good bell either. Only "what material/instrument does this
# read as", which is a question it can answer and the DSP features cannot.
MATERIAL_PROMPTS = [
    "a kick drum", "a hi-hat cymbal", "a snare drum", "a clap",
    "a tom drum", "a ride cymbal", "a metallic bell", "a struck metal object",
    "a wooden percussion block", "a bowed string instrument", "a wind instrument",
    "a human voice", "white noise", "a synthesizer tone", "a bass note",
]
CLAP_PAD_S = 1.0        # CLAP was trained on seconds, not on 300 ms


def _clap_clip(seg, sr):
    """One hit as a CLAP-shaped 48 kHz clip.

    A 300 ms slice zero-padded to 1 s is what both the bank and the candidate
    get, so the padding is a constant and cancels out of every comparison.
    """
    import librosa
    import semantic_ear
    y = librosa.resample(np.asarray(seg, dtype=np.float32), orig_sr=sr,
                         target_sr=semantic_ear.CLAP_SR)
    n = int(CLAP_PAD_S * semantic_ear.CLAP_SR)
    out = np.zeros(n, dtype=np.float32)
    out[:min(n, len(y))] = y[:n]
    peak = float(np.max(np.abs(out)))
    return out / peak if peak > 0 else out     # gain-invariant, like the DSP side


def _build_clap(by_role, bank, per_role=120, verbose=True):
    """Embed a sample of reference hits so an out-of-bank sound has something
    real to be compared against, and record what the material prompts score on
    hits we KNOW are kicks/hats/perc — otherwise 'CLAP says bell 0.31' is
    another uncalibrated number."""
    import semantic_ear
    ear = semantic_ear.SemanticEar()
    if not ear.available:
        print("  CLAP unavailable (checkpoint or laion_clap missing) — skipped")
        return
    if verbose:
        print(f"\nCLAP over up to {per_role} hits per role (model load ~40 s)")
    embs, labels, roles = [], [], []
    for role in BANK_ROLES:
        hits = [h for h in by_role.get(role, []) if "audio" in h]
        if not hits:
            continue
        idx = np.linspace(0, len(hits) - 1, min(per_role, len(hits))).astype(int)
        chosen = [hits[i] for i in sorted(set(idx))]
        clips = [_clap_clip(h["audio"], SR) for h in chosen]
        for i in range(0, len(clips), 32):
            embs.append(ear.embed_audio_batch(clips[i:i + 32]))
        for h in chosen:
            labels.append(f"{role}:{h['excerpt'][:28]}@{h['t']}")
            roles.append(role)
        if verbose:
            print(f"  {role:5s} {len(chosen)} embedded")
    if not embs:
        return
    E = np.concatenate(embs, axis=0)
    np.savez(CLAP_PATH, embs=E, labels=np.array(labels), roles=np.array(roles))

    txt = ear.embed_text(MATERIAL_PROMPTS)          # (P, D)
    sims = E @ txt.T                                # (N, P)
    roles_arr = np.array(roles)
    clap_stats = {}
    for role in BANK_ROLES:
        m = roles_arr == role
        if not m.any():
            continue
        clap_stats[role] = {
            "n": int(m.sum()),
            "prompt": {p: {"median": round(float(np.median(sims[m, j])), 4),
                           "p10": round(float(np.percentile(sims[m, j], 10)), 4),
                           "p90": round(float(np.percentile(sims[m, j], 90)), 4)}
                       for j, p in enumerate(MATERIAL_PROMPTS)},
        }
    # How similar is a reference hit to OTHER reference hits? This is the
    # yardstick that makes "your bell scores 0.31 to the corpus" readable.
    nn = []
    for i in range(len(E)):
        s = E[i] @ E.T
        s[i] = -1
        nn.append(float(s.max()))
    bank["clap"] = {
        "path": CLAP_PATH.name,
        "prompts": MATERIAL_PROMPTS,
        "pad_s": CLAP_PAD_S,
        "roles": clap_stats,
        "self_nn": {"median": round(float(np.median(nn)), 4),
                    "p10": round(float(np.percentile(nn, 10)), 4),
                    "p90": round(float(np.percentile(nn, 90)), 4)},
    }
    if verbose:
        print(f"  reference hit -> nearest other reference hit: "
              f"{bank['clap']['self_nn']['median']:.3f} "
              f"[{bank['clap']['self_nn']['p10']:.3f}.."
              f"{bank['clap']['self_nn']['p90']:.3f}]")


# ------------------------------------------------------------------- reading

class Bank:
    def __init__(self, data):
        self.data = data
        self.roles = data.get("roles", {})

    def stats(self, role):
        return (self.roles.get(role) or {}).get("stats")

    def holdout(self, role):
        return (self.roles.get(role) or {}).get("holdout")

    def has(self, role):
        return role in self.roles


def load(path=BANK_PATH):
    p = pathlib.Path(path)
    if not p.exists():
        return None
    try:
        return Bank(json.loads(p.read_text()))
    except Exception:
        return None


def _plain(key, z):
    """z -> the sentence a producer would say."""
    if not np.isfinite(z):
        return ""
    a = abs(z)
    if a < 1.5:
        return ""
    # every phrase below is a bare comparative so the strength adverb can be
    # glued on the front without producing "far a shorter tail"
    strength = "much " if a >= 4 else ("clearly " if a >= 2.5 else "")
    hi = z > 0
    words = {
        "share.sub": ("more sub weight", "less sub weight"),
        "share.bass": ("more low-body", "less low-body"),
        "share.lowmid": ("more boxy lowmid", "less lowmid"),
        "share.mid": ("more midrange", "less midrange"),
        "share.highmid": ("more presence bite", "less presence"),
        "share.high": ("more top end", "less top end"),
        "share.air": ("more air", "less air"),
        "peak_hz": ("higher-pitched", "lower-pitched"),
        "root_hz": ("higher in fundamental", "lower in fundamental"),
        "centroid_hz": ("brighter", "darker"),
        "rolloff85_hz": ("more extended in the highs", "more rolled-off"),
        "decay20_ms": ("longer-tailed", "shorter-tailed"),
        "attack_ms": ("slower to attack", "faster to attack"),
        "peak_offset_ms": ("slower to reach full level", "quicker to peak"),
        "noisiness_db": ("noisier / less tonal", "more tonal / less noisy"),
        "crest_db": ("peakier", "more sustained"),
        "zcr": ("more high-frequency content", "less high-frequency content"),
    }.get(key)
    if not words:
        return ""
    return f"{strength}{words[0] if hi else words[1]} than the reference {{role}}s"


def profile(path, bank, role=None, clap_ear=None, verbose=True):
    """One candidate one-shot against the bank. Returns a dict; prints a report."""
    import librosa
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    if len(y) < int(0.02 * SR):
        return {"path": str(path), "error": "shorter than 20 ms"}

    # Cut the candidate the same way the bank was cut, or the comparison is
    # between a 300 ms window and a 4 s file — decay and shares would both lie.
    #
    # The anchor is the ONSET, not the loudest sample. The first version used
    # argmax|y| and got forged_kick_iron badly wrong: that sample swells and its
    # loudest point is 460 ms in, so the tool measured the last 120 ms of its
    # tail and reported a 52 ms decay for a 580 ms kick. A one-shot file begins
    # at its own onset, so find the first sample that is meaningfully above
    # silence and back off the same 15 ms of pre-roll the bank uses.
    env = np.abs(y)
    above = np.nonzero(env > 0.02 * float(env.max()))[0]
    onset = int(above[0]) if len(above) else 0
    i0 = max(0, onset - int(PRE_S * SR))

    def cut(seconds):
        s = y[i0:i0 + int(seconds * SR)]
        return np.pad(s, (0, max(0, int(seconds * SR) - len(s))))

    auto = classify(features(cut(CLASSIFY_S), SR))
    role_used = role or auto
    # An unknown role gets the widest window, which is the most informative
    # thing to print when there is nothing to compare against anyway.
    seg = cut(ROLE_WINDOW.get(role_used, max(ROLE_WINDOW.values())))
    f = features(seg, SR)
    full_s = len(y) / SR

    out = {"path": str(path), "name": pathlib.Path(path).name,
           "duration_s": round(full_s, 3), "auto_role": auto,
           "role": role_used, "features": f, "in_bank": bank.has(role_used)}

    win_ms = len(seg) / SR * 1000
    out["window_ms"] = round(win_ms, 1)
    L = [f"{pathlib.Path(path).name}   {full_s:.2f} s file, "
         f"{win_ms:.0f} ms measured from the onset "
         f"({onset / SR * 1000:.0f} ms in)"]

    if not bank.has(role_used):
        # The honest branch. There is no bell in a Drumcode drum stem.
        known = ", ".join(bank.roles)
        L.append("")
        L.append(f"NO REFERENCE DATA for role '{role_used}'.")
        L.append(f"  The bank was cut from reference DRUM STEMS and contains "
                 f"only: {known}.")
        L.append(f"  Its own band-dominance rule reads this sample as "
                 f"'{auto}', but that is a bin, not a judgement — this tool "
                 f"cannot tell you whether it is a good {role_used}, because "
                 f"no {role_used} exists in the corpus.")
        L.append("  Raw measurements below; no z-scores, because there is "
                 "nothing to be z against.")
        L.append("")
        L.append(f"{'feature':20s}{'value':>10s}")
        for key, label, fmt in REPORT_FEATURES:
            if key in f and np.isfinite(f[key]):
                L.append(f"{label:20s}{fmt.format(f[key]):>10s}")
        ff = file_facts(y, SR)
        out["file_facts"] = ff
        L.append(f"{'whole file length':20s}{ff['duration_s'] * 1000:6.0f}ms")
        L.append(f"{'  -20 dB at':20s}{ff['t20_ms']:6.0f}ms")
        L.append(f"{'  -40 dB at':20s}{ff['t40_ms']:6.0f}ms")
        out["report"] = "\n".join(L)
        if clap_ear is not None:
            cl = clap_reading(seg, bank, clap_ear)
            if cl:
                out["clap"] = cl
                out["report"] += "\n\n" + cl["report"]
        if verbose:
            print(out["report"])
        return out

    st = bank.stats(role_used)
    hb = bank.holdout(role_used) or {}
    blk = bank.roles[role_used]
    L.append(f"role: {role_used}" +
             ("" if role else " (auto-detected from band dominance)") +
             f"   corpus: {blk['n']} hits cut from {blk['n_tracks']} records")
    if not role:
        # Being explicit about this is the whole point of the exercise. The
        # auto role is a spectral BIN, and 'perc' is the bin for everything
        # that is neither a kick nor a hat — claps, toms, rims, rides, noise.
        # A bell lands in it. Landing in it is not evidence of being a bell.
        L.append(f"  ('{role_used}' is where this sample's band balance puts "
                 f"it, not an identification. " +
                 ("'perc' in particular is the catch-all bin for everything "
                  "that is neither kick nor hat.)"
                  if role_used == "perc" else ")"))
    L.append("")
    L.append(f"{'feature':20s}{'sample':>10s}{'refs':>10s}{'p10':>9s}"
             f"{'p90':>9s}{'z':>7s}")
    notes = []
    zs = {}
    for key, label, fmt in REPORT_FEATURES:
        if key not in f:
            continue
        v = f[key]
        s = st.get(key)
        if not np.isfinite(v):
            continue
        if not s:
            L.append(f"{label:20s}{fmt.format(v):>10s}{'-':>10s}")
            continue
        z = zscore(s, v)
        zs[key] = z
        mark = "  <--" if abs(z) >= 2.5 else ""
        L.append(f"{label:20s}{fmt.format(v):>10s}"
                 f"{fmt.format(disp(s, key)):>10s}"
                 f"{fmt.format(disp(s, key, 'p10')):>9s}"
                 f"{fmt.format(disp(s, key, 'p90')):>9s}"
                 f"{z:>+7.1f}{mark}")
        msg = _plain(key, z)
        if msg:
            notes.append(f"  - {label}: " + msg.format(role=role_used))

    od = oddity(st, f)
    n_out, out_keys = n_outside(st, f)
    out["z"] = {k: round(v, 2) for k, v in zs.items() if np.isfinite(v)}
    out["oddity"] = round(od, 3)
    out["n_outside"] = n_out
    out["outside_axes"] = out_keys
    L.append("")
    if hb:
        q = hb.get("oddity_q")
        pct = min(float(np.searchsorted(q, od)), 100.0) if q else float("nan")
        L.append(f"typicality (median |z| over {len(CORE_FEATURES)} core "
                 f"features): {od:.2f}")
        L.append(f"  held-out reference {role_used}s score "
                 f"{hb['oddity_median']:.2f} median, {hb['oddity_p90']:.2f} at "
                 f"p90, {hb['oddity_p99']:.2f} at p99 (n={hb['n']})")
        if q:
            rest = 100 - pct
            L.append(f"  {'fewer than 1' if rest < 1 else f'{rest:.0f}'}% of "
                     f"real Drumcode {role_used}s are further from the corpus "
                     f"centre than this one")
            out["oddity_percentile"] = pct
        if od <= hb["oddity_p90"]:
            v = f"INSIDE the corpus — this reads as a normal reference {role_used}."
        elif od <= hb["oddity_p99"]:
            v = (f"EDGE of the corpus — unusual for a {role_used}, but real "
                 f"records do reach here.")
        else:
            v = (f"OUTSIDE the corpus — no held-out reference {role_used} in "
                 f"{hb['n']} is this far out. Either it is a deliberately "
                 f"strange {role_used}, or it is not a {role_used}.")
        L.append(f"  verdict: {v}")
        out["verdict"] = v

        # The other half of the reading. A median cannot see three defining
        # axes being far out inside a wide distribution; this can.
        L.append(f"axes {OUTSIDE_Z} sigma or more outside: {n_out}"
                 + (f"  ({', '.join(out_keys)})" if out_keys else ""))
        L.append(f"  held-out reference {role_used}s: "
                 f"{hb['n_outside_median']:.0f} at the median, "
                 f"{hb['n_outside_p90']:.0f} at p90, "
                 f"{hb['n_outside_p99']:.0f} at p99, "
                 f"{hb['n_outside_max']:.0f} worst case")
        # How specific is this role's test at all? Measured at build time by
        # feeding it the other roles' hits.
        acc = blk.get("cross_role_accept") or {}
        if acc:
            worst = max(acc.values())
            L.append("how much that verdict is worth: the " + role_used +
                     " test also calls " +
                     ", ".join(f"{100 * v:.0f}% of reference {k}s"
                               for k, v in acc.items()) + " 'inside'")
            if worst >= 0.5:
                L.append(f"  -> this distribution is too wide to be an "
                         f"identity test. An INSIDE verdict here means 'not "
                         f"obviously broken', NOT 'this is a good "
                         f"{role_used}'. Read the per-axis z above instead.")
            out["cross_role_accept"] = acc

        if n_out > hb["n_outside_p99"]:
            L.append(f"  -> more axes are far out than in 99% of real "
                     f"{role_used}s, even though the median says it is typical."
                     f" That combination — normal on most axes, extreme on a "
                     f"few — is what a DIFFERENT INSTRUMENT looks like here.")
            out["verdict"] += " (but see axes-outside: extreme on a few axes)"
    if notes:
        L.append("")
        L.append("what is different:")
        L += notes
    elif hb:
        L.append("  nothing on any axis is more than 1.5 sigma from the corpus.")

    if f.get("decay_censored", 0) > 0.5:
        L.append("")
        L.append(f"  note: the tail never falls 20 dB inside the {win_ms:.0f} ms "
                 f"window, so decay is censored at that value, not measured. "
                 f"The reference hits carry the same censoring, so the "
                 f"comparison is still like-for-like.")

    # Facts about the whole file that the bank structurally cannot judge: the
    # reference hits were cut out of a continuous stem, so their true total
    # decay is unknowable — the next hit arrives first. Printed without a
    # comparison rather than silently dropped, because "this bell rings for
    # 1.2 s" is exactly the thing a sample designer wants to know.
    ff = file_facts(y, SR)
    L.append("")
    L.append(f"whole file (NO reference — the corpus is cut from continuous "
             f"stems and cannot measure this):")
    L.append(f"  length {ff['duration_s'] * 1000:.0f} ms, "
             f"-20 dB at {ff['t20_ms']:.0f} ms, -40 dB at {ff['t40_ms']:.0f} ms")
    out["file_facts"] = ff

    out["report"] = "\n".join(L)
    if clap_ear is not None:
        cl = clap_reading(seg, bank, clap_ear)
        if cl:
            out["clap"] = cl
            out["report"] += "\n\n" + cl["report"]
    if verbose:
        print(out["report"])
    return out


def file_facts(y, sr):
    """Envelope facts over the entire file, uncalibrated by design."""
    import librosa
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    pk = int(rms.argmax())
    peak = float(rms[pk]) + 1e-12

    def t_below(frac):
        below = np.nonzero(rms[pk:] < peak * frac)[0]
        return float((below[0] if len(below) else len(rms) - pk) * 256 / sr * 1000)

    return {"duration_s": round(len(y) / sr, 3),
            "t20_ms": round(t_below(0.1), 1),
            "t40_ms": round(t_below(0.01), 1)}


def clap_reading(seg, bank, ear):
    """What does CLAP call this, next to what it calls hits we know the role of.

    Stated limits, because they matter: this answers "what material/instrument
    does it read as" and "how close is it to anything in the reference drums".
    It does NOT answer "is this a good bell" — the corpus has no bell to be
    good relative to.
    """
    meta = bank.data.get("clap")
    if not meta or not CLAP_PATH.exists() or not ear.available:
        return None
    z = np.load(CLAP_PATH, allow_pickle=True)
    E, labels, roles = z["embs"], list(z["labels"]), list(z["roles"])
    e = ear.embed_audio_batch([_clap_clip(seg, SR)])[0]
    sims = E @ e
    order = np.argsort(-sims)
    prompts = meta["prompts"]
    tsims = ear.embed_text(prompts) @ e
    top = np.argsort(-tsims)[:5]

    self_nn = meta["self_nn"]
    nn = float(sims.max())
    L = ["CLAP reading (what it sounds LIKE — not whether it is good)"]
    L.append(f"  nearest reference drum hit: {nn:.3f} "
             f"({labels[int(order[0])]})")
    L.append(f"    a reference hit's nearest OTHER reference hit scores "
             f"{self_nn['median']:.3f} [{self_nn['p10']:.3f}.."
             f"{self_nn['p90']:.3f}]")
    if nn < self_nn["p10"]:
        L.append("    -> below the range real drum hits reach with each other: "
                 "this is not a sound the reference drums contain.")
    L.append("  reads as:")
    for j in top:
        p = prompts[int(j)]
        ref = (meta["roles"].get("kick", {}).get("prompt", {}) or {}).get(p)
        band = ""
        if ref:
            band = (f"   (reference kicks {ref['median']:+.3f}, hats "
                    f"{meta['roles']['hat']['prompt'][p]['median']:+.3f}, perc "
                    f"{meta['roles']['perc']['prompt'][p]['median']:+.3f})"
                    if all(r in meta["roles"] for r in BANK_ROLES) else "")
        L.append(f"    {p:28s}{float(tsims[int(j)]):+.3f}{band}")
    return {"nearest_sim": round(nn, 4),
            "nearest": labels[int(order[0])],
            "top_prompts": [(prompts[int(j)], round(float(tsims[int(j)]), 4))
                            for j in top],
            "report": "\n".join(L)}


# ---------------------------------------------------------------------- CLI

def cmd_show(bank, role=None):
    print(f"one-shot bank  built {bank.data['built_at']}  "
          f"{len(bank.data['excerpts'])} excerpts / "
          f"{len(bank.data['tracks'])} records")
    for r, blk in bank.roles.items():
        if role and r != role:
            continue
        hb = blk.get("holdout", {})
        print(f"\n{r.upper()}  n={blk['n']} hits from {blk['n_tracks']} records"
              + (f"   held-out oddity median {hb['oddity_median']:.2f}, "
                 f"p90 {hb['oddity_p90']:.2f}, flagged@2.0 "
                 f"{100 * hb['flag_rate_at_2']:.1f}%" if hb else ""))
        print(f"  {'feature':20s}{'median':>10s}{'p10':>10s}{'p90':>10s}"
              f"{'sigma':>9s}")
        for key, label, fmt in REPORT_FEATURES:
            s = blk["stats"].get(key)
            if not s:
                continue
            print(f"  {label:20s}{fmt.format(disp(s, key)):>10s}"
                  f"{fmt.format(disp(s, key, 'p10')):>10s}"
                  f"{fmt.format(disp(s, key, 'p90')):>10s}"
                  f"{s['sigma']:>9.3f}" + ("  (log2)" if s.get("log") else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("build", "show", "profile"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--role", default=None,
                    help="force the role instead of auto-detecting")
    ap.add_argument("--clap", action="store_true",
                    help="build: embed reference hits. profile: CLAP reading "
                         "(~40 s model load)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.cmd == "build":
        build(clap=a.clap)
        return

    bank = load()
    if bank is None:
        sys.exit("no one-shot bank — run `oneshot_bank.py build` first")

    if a.cmd == "show":
        cmd_show(bank, a.args[0] if a.args else None)
        return

    ear = None
    if a.clap:
        import semantic_ear
        ear = semantic_ear.SemanticEar()
        if not ear.available:
            print("CLAP unavailable — continuing without it\n")
            ear = None

    results = []
    for i, p in enumerate(a.args):
        if i:
            print("\n" + "=" * 72 + "\n")
        results.append(profile(p, bank, role=a.role, clap_ear=ear,
                               verbose=not a.json))
    if a.json:
        print(json.dumps([{k: v for k, v in r.items() if k != "report"}
                          for r in results], indent=1, default=float))


if __name__ == "__main__":
    main()
