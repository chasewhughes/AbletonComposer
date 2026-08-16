#!/usr/bin/env python3
"""Calibration — run the whole listening pipeline over the reference records
and keep the numbers, so every later reading is a delta against real music
instead of a delta against a hand-written target.

Why this exists. The listening loop measured plenty and could not say how far
off anything was. A CLAP groove score of 0.04 and one of 0.14 both just meant
"bad", because nothing said what a record that actually grooves scores. The
tonal targets were guesses. Worse, the guesses were mix-shaped: a drums-only
render got flagged MUDDY +6.7 dB sub for the crime of being a drum stem
compared against full commercial masters.

Both problems have one fix — measure the references the same way, in the same
context, and store the distribution:

  contexts    Every reference excerpt is separated into stems, and every
              metric is recorded per context: mix / drums / bass / other. A
              drums-only render is then judged against reference DRUM STEMS.
  spread      Each metric keeps median, robust sigma (1.4826*MAD), p10/p90 and
              n. `z()` says how far outside real records a render sits, which
              is a steering signal; a raw score is not.
  clap        The same CLAP quality axes the semantic ear reports, measured on
              the references. This is what turns "groove 0.04" into "groove
              0.04, where the Drumcode records sit at 0.55 (0.31..0.78)".
  groove      Reference step grids, so a render's pattern can be diffed
              against the pattern of a record that grooves.
  harmony     Reference key/tonalness distributions.

Usage:
  .venv-listen/bin/python tools/calibrate.py build [--windows 2] [--dur 60]
  .venv-listen/bin/python tools/calibrate.py show [context]
  .venv-listen/bin/python tools/calibrate.py compare <render.wav> [--context X]
"""
import argparse
import json
import pathlib
import sys
import time

import numpy as np

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

REF_DIR = REPO / "reference-audio"
CAL_PATH = REF_DIR / "calibration.json"
EXCERPT_DIR = REPO / ".cache" / "refexcerpt"
SR = 44100

# Where in a reference track to sample. Techno intros and outros are DJ tools
# and are not what a loop render is trying to be; these fractions land in the
# body of the arrangement.
WINDOW_FRACTIONS = (0.35, 0.62)
CONTEXTS = ("mix", "drums", "bass", "other")
# A 16-bar loop render has no arrangement, but its tonal balance and mix
# behaviour are still those of a full mix, so it borrows that distribution.
CONTEXT_ALIASES = {"loop": "mix", "full": "mix", "master": "mix"}
# A stem this far below the loudest one is not part of the arrangement.
PRESENCE_DB = 25.0


# ---------------------------------------------------------------- measuring

def flatten(rep, prefix=""):
    """Nested reading dict -> {"tonal_db.sub": -22.3, ...} for stat lookup."""
    out = {}
    for k, v in rep.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, prefix=f"{key}."))
        elif isinstance(v, (int, float, np.floating, np.integer)) and \
                not isinstance(v, bool):
            # np.float32 is NOT a float subclass — band_db and congestion come
            # back as float32 from librosa and silently vanished without this.
            out[key] = float(v)
    return out


METRIC_SKIP = ("duration_s", "loudness.dc_offset", "pulse.raw_tempo")


def measure_source(y, sr, name):
    """Every scalar the calibrated checks can reference, for one source."""
    import ears
    rep = ears.analyze_array(y, sr)
    flat = {k: v for k, v in flatten(rep).items()
            if not k.startswith(METRIC_SKIP)}
    return rep, flat


def excerpt_path(track, offset, dur):
    """Reference excerpts are written to disk so demucs caching (which is
    content-addressed on the file) works across rebuilds."""
    EXCERPT_DIR.mkdir(parents=True, exist_ok=True)
    return EXCERPT_DIR / f"{track.stem[:60]}__{int(offset)}s_{int(dur)}s.wav"


def reference_tracks():
    """The full-length singles. DJ mixes are deliberately excluded: they are
    two records crossfaded plus a DJ's EQ, which is not what a single sounds
    like and would widen every distribution for no gain."""
    return sorted((REF_DIR / "Drumcode").glob("*.mp3"))


def build(windows=WINDOW_FRACTIONS, dur=60.0, do_clap=True, verbose=True):
    import librosa
    import soundfile as sf
    import stems as stems_mod
    import groove_ear
    import harmony_ear

    tracks = reference_tracks()
    if not tracks:
        sys.exit(f"no reference tracks in {REF_DIR / 'Drumcode'}")

    samples = {c: [] for c in CONTEXTS}      # context -> [{label, metrics}]
    groove_refs, harmony_refs = [], []
    clap_clips = []                          # (context, label, [48k clips])

    for track in tracks:
        try:
            total = librosa.get_duration(path=str(track))
        except Exception as e:
            print(f"SKIP {track.name}: {e}")
            continue
        for frac in windows:
            offset = max(0.0, min(total - dur, total * frac - dur / 2))
            label = f"{track.stem[:40]}@{int(offset)}s"
            wav = excerpt_path(track, offset, dur)
            if not wav.exists():
                y, _ = librosa.load(str(track), sr=SR, mono=False,
                                    offset=offset, duration=dur)
                sf.write(wav, y.T if y.ndim > 1 else y, SR)
            if verbose:
                print(f"\n=== {label}")

            data, _ = sf.read(wav, dtype="float32", always_2d=True)
            mono = data.mean(axis=1)
            sources = {"mix": mono}
            try:
                st = stems_mod.separate(str(wav), sr=SR, verbose=False)
                st["other"] = st.get("other", 0) + st.pop("vocals", 0)
                sources.update({k: st[k] for k in ("drums", "bass", "other")})
            except Exception as e:
                print(f"  stems failed: {e}")

            for ctx, y in sources.items():
                t0 = time.time()
                rep, flat = measure_source(y, SR, ctx)
                if ctx == "mix":                 # stereo facts only exist here
                    import ears
                    flat.update({k: v for k, v in flatten(
                        {"loudness": ears.loudness_array(data, SR)}).items()
                        if not k.startswith(METRIC_SKIP)})
                samples[ctx].append({"label": label, "metrics": flat})
                if verbose:
                    print(f"  {ctx:6s} measured in {time.time() - t0:.1f}s")

            # groove grid from the drum stem — the pattern to diff against
            if "drums" in sources:
                try:
                    g = groove_ear.analyze(sources["drums"], SR)
                    groove_refs.append({"label": label, **groove_ear.to_json(g)})
                except Exception as e:
                    print(f"  groove failed: {e}")

            try:
                h = harmony_ear.analyze(sources, SR)
                harmony_refs.append({
                    "label": label,
                    "consensus": h["consensus"],
                    "problems": h["problems"],
                    "pairs": [{k: p[k] for k in
                               ("kind", "a", "b", "a_note", "b_note",
                                "interval", "semitones")} for p in h["pairs"]],
                    "sources": {r["name"]: dict(
                        {k: r.get(k) for k in ("tonalness", "key",
                                               "key_confidence", "root_note",
                                               "root_hz", "out_of_key")},
                        concentration=r.get("notes", {}).get("concentration"),
                        median_cents=r.get("notes", {}).get("median_cents"),
                        pitch_reliable=r.get("notes", {}).get("pitch_reliable"),
                        top=r.get("notes", {}).get("top"))
                        for r in h["sources"] if not r.get("silent")},
                })
            except Exception as e:
                print(f"  harmony failed: {e}")

            if do_clap:
                for ctx, y in sources.items():
                    clap_clips.append((ctx, label, y))

    clap = {}
    if do_clap and clap_clips:
        clap = _clap_axes(clap_clips, verbose=verbose)

    cal = {
        "built_at": time.strftime("%Y-%m-%d %H:%M"),
        "corpus": [t.name for t in tracks],
        "window_s": dur,
        "window_fractions": list(windows),
        "contexts": {},
        "groove_refs": groove_refs,
        "harmony_refs": harmony_refs,
    }
    for ctx in CONTEXTS:
        rows = samples[ctx]
        if not rows:
            continue
        keys = sorted({k for r in rows for k in r["metrics"]})
        stats = {}
        for k in keys:
            vals = np.array([r["metrics"][k] for r in rows if k in r["metrics"]],
                            dtype=float)
            vals = vals[np.isfinite(vals)]
            if len(vals) < 3:
                continue
            stats[k] = _stat(vals)
        for axis, vals in (clap.get(ctx) or {}).items():
            stats[f"clap.{axis}"] = _stat(np.array(vals, dtype=float))
        cal["contexts"][ctx] = {"n": len(rows), "stats": stats,
                                "samples": rows}

    CAL_PATH.write_text(json.dumps(cal, indent=1))
    print(f"\ncalibration -> {CAL_PATH}")
    for ctx, blk in cal["contexts"].items():
        print(f"  {ctx:6s} n={blk['n']:3d}  {len(blk['stats'])} metrics")
    return cal


def _stat(vals):
    """Median + robust sigma. MAD, not std: with n~18 one atypical record
    should not be able to widen the range until nothing ever looks wrong."""
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) * 1.4826
    return {"median": round(med, 4),
            "sigma": round(mad if mad > 1e-9 else float(np.std(vals)) + 1e-9, 4),
            "mean": round(float(np.mean(vals)), 4),
            "std": round(float(np.std(vals)), 4),
            "p10": round(float(np.percentile(vals, 10)), 4),
            "p90": round(float(np.percentile(vals, 90)), 4),
            "min": round(float(np.min(vals)), 4),
            "max": round(float(np.max(vals)), 4),
            "n": int(len(vals))}


def _clap_axes(clips, verbose=True):
    """CLAP quality axes for every (context, excerpt) — one model load."""
    import semantic_ear
    import librosa
    ear = semantic_ear.SemanticEar()
    if not ear.available:
        print("  CLAP unavailable, skipping semantic calibration")
        return {}
    out = {c: {} for c in CONTEXTS}
    if verbose:
        print(f"\nCLAP over {len(clips)} reference sources ...")
    for i, (ctx, label, y) in enumerate(clips):
        y48 = librosa.resample(y, orig_sr=SR, target_sr=semantic_ear.CLAP_SR)
        win = semantic_ear.CLAP_SR * 10
        if len(y48) < win:
            y48 = np.pad(y48, (0, win - len(y48)))
        starts = [int(f * (len(y48) - win)) for f in (0.05, 0.5, 0.9)]
        embs = ear.embed_audio_batch([y48[s:s + win] for s in starts])
        e = embs.mean(axis=0)
        e /= np.linalg.norm(e) + 1e-9
        for axis, score in ear.quality_axes(e).items():
            out[ctx].setdefault(axis, []).append(float(score))
        if verbose and (i + 1) % 8 == 0:
            print(f"  {i + 1}/{len(clips)}")
    return out


# ---------------------------------------------------------------- using it

class Calibration:
    """Read side: turn a raw number into 'how far outside real records is it'."""

    def __init__(self, data):
        self.data = data
        self.contexts = data.get("contexts", {})

    def resolve(self, context):
        return CONTEXT_ALIASES.get(context, context)

    def has_context(self, context):
        return self.resolve(context) in self.contexts

    def stat(self, context, key):
        blk = self.contexts.get(self.resolve(context))
        return (blk or {}).get("stats", {}).get(key)

    def z(self, context, key, value):
        st = self.stat(context, key)
        if not st:
            return 0.0
        return float((value - st["median"]) / max(st["sigma"], 1e-9))

    def describe(self, context, key, value, unit="", fmt="{:.2f}"):
        """'0.04 (refs 0.55, range 0.31..0.78, z=-6.2)' — a steering signal."""
        st = self.stat(context, key)
        v = fmt.format(value)
        if not st:
            return f"{v}{unit} (no reference for {self.resolve(context)})"
        return (f"{v}{unit} · refs {fmt.format(st['median'])}"
                f" [{fmt.format(st['p10'])}..{fmt.format(st['p90'])}]"
                f" · z={self.z(context, key, value):+.1f}")

    def groove_refs(self):
        return self.data.get("groove_refs", [])

    def harmony_refs(self):
        return self.data.get("harmony_refs", [])


def load(path=CAL_PATH):
    """Calibration or None. Every caller treats None as 'stay uncalibrated'."""
    p = pathlib.Path(path)
    if not p.exists():
        return None
    try:
        return Calibration(json.loads(p.read_text()))
    except Exception:
        return None


def infer_context(stems, full=None):
    """What IS this render — a mix, or one stem's worth of it?

    Guessing wrong is how the MUDDY false alarm happened, and the render
    itself carries the answer: if separation puts essentially all the energy
    in one stem, the render is that stem.
    """
    if not stems:
        return "mix"
    db = {k: float(20 * np.log10(np.sqrt(np.mean(np.asarray(v, float) ** 2))
                                 + 1e-12))
          for k, v in stems.items() if k in CONTEXTS}
    if not db:
        return "mix"
    loudest = max(db.values())
    # Presence is a level question, not a share question. Drums hold ~59% of
    # the linear energy on the reference records, so any share threshold low
    # enough to catch a real drums-only render also catches every full mix.
    # A stem within 25 dB of the loudest is audible; below that it is not
    # going to survive a club system, whatever percentage it owns.
    present = [k for k, v in db.items() if v > loudest - PRESENCE_DB]
    return present[0] if len(present) == 1 else "mix"


# ---------------------------------------------------------------- reporting

REPORT_METRICS = [
    ("loudness.lufs", "LUFS", "{:.1f}"),
    ("loudness.crest_db", "crest dB", "{:.1f}"),
    ("pulse.kick_beat_ratio", "kick/median", "{:.2f}"),
    ("pulse.beat_confidence", "beat conf", "{:.2f}"),
    ("pulse.low_to_high_ratio_db", "low-high dB", "{:.1f}"),
    ("transients_per_s.high", "trans/s high", "{:.1f}"),
]


def compare_table(cal, flat, context, clap=None):
    """The A/B: every metric of a render beside the reference distribution."""
    ctx = cal.resolve(context)
    L = [f"context: {ctx}  (references: {cal.contexts.get(ctx, {}).get('n', 0)} "
         f"excerpts from {len(cal.data.get('corpus', []))} records)",
         f"{'metric':24s}{'render':>9s}{'refs':>9s}{'p10':>8s}{'p90':>8s}{'z':>7s}"]

    def row(key, label, fmt):
        if key not in flat:
            return
        st = cal.stat(ctx, key)
        v = flat[key]
        if not st:
            L.append(f"{label:24s}{fmt.format(v):>9s}{'-':>9s}")
            return
        z = cal.z(ctx, key, v)
        mark = "   <--" if abs(z) >= 2.5 else ""
        L.append(f"{label:24s}{fmt.format(v):>9s}{fmt.format(st['median']):>9s}"
                 f"{fmt.format(st['p10']):>8s}{fmt.format(st['p90']):>8s}"
                 f"{z:>+7.1f}{mark}")

    import ears
    for band, _, _ in ears.BANDS:
        row(f"tonal_db.{band}", f"balance {band}", "{:.1f}")
    L.append("")
    for band, _, _ in ears.BANDS:
        row(f"congestion_db.{band}", f"congestion {band}", "{:.1f}")
    L.append("")
    for key, label, fmt in REPORT_METRICS:
        row(key, label, fmt)
    if clap:
        L.append("")
        for axis, score in clap.items():
            flat[f"clap.{axis}"] = score
            row(f"clap.{axis}", f"CLAP {axis}", "{:.2f}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("build", "show", "compare"))
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--windows", type=int, default=len(WINDOW_FRACTIONS))
    ap.add_argument("--dur", type=float, default=60.0)
    ap.add_argument("--no-clap", action="store_true")
    ap.add_argument("--context", default=None)
    a = ap.parse_args()

    if a.cmd == "build":
        fr = WINDOW_FRACTIONS if a.windows == len(WINDOW_FRACTIONS) else \
            tuple(np.linspace(0.3, 0.7, a.windows))
        build(windows=fr, dur=a.dur, do_clap=not a.no_clap)
        return

    cal = load()
    if cal is None:
        sys.exit("no calibration — run `calibrate.py build` first")

    if a.cmd == "show":
        ctx = a.arg or "mix"
        blk = cal.contexts.get(cal.resolve(ctx))
        if not blk:
            sys.exit(f"no context '{ctx}'; have {list(cal.contexts)}")
        print(f"{cal.resolve(ctx)}  n={blk['n']}  built {cal.data['built_at']}")
        print(f"{'metric':30s}{'median':>10s}{'sigma':>9s}{'p10':>9s}{'p90':>9s}")
        for k, s in sorted(blk["stats"].items()):
            print(f"{k:30s}{s['median']:10.3f}{s['sigma']:9.3f}"
                  f"{s['p10']:9.3f}{s['p90']:9.3f}")
        return

    # compare
    import librosa
    import ears
    y, _ = librosa.load(a.arg, sr=SR, mono=True)
    rep = ears.analyze_array(y, SR, loud=ears.loudness(a.arg))
    print(compare_table(cal, flatten(rep), a.context or "mix"))


if __name__ == "__main__":
    main()
