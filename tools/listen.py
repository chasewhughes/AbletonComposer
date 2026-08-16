#!/usr/bin/env python3
"""listen.py — the listening loop. Turns a render into everything a deaf
composer needs to iterate like a hearing one.

One command runs five ears and writes a report directory:

  ears       mix diagnostics in dB (ears.py) — master and per-stem
  critic     reference-anchored core/novelty score (critic.py)
  semantic   CLAP: quality axes, subgenre character, moods, similarity to the
             actual reference records, and a per-10s quality timeline
  groove     the rhythm reconstructed as a 32-step text grid per instrument
  structure  section timeline: what enters, exits, and changes, bar by bar
  visual     spectrograms (overview / stems / 4-bar loop zoom) as PNGs

Output: listen-reports/<name>/report.md (+ report.json + *.png).
The report is written to be READ by the composer model: verdicts first,
then the pattern, then the mix table, then the images to open.

Usage:
  .venv-listen/bin/python tools/listen.py <render.wav|aif> [--quick] [--out DIR]
  .venv-listen/bin/python tools/listen.py refs     # (re)build CLAP reference cache

--quick skips stem separation and CLAP (pure-DSP pass, ~15 s).
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

import librosa  # noqa: E402
import ears  # noqa: E402
import groove_ear  # noqa: E402
import structure_ear  # noqa: E402
import spectro  # noqa: E402

SR = 44100


def _try(label, fn, log):
    t0 = time.time()
    try:
        out = fn()
        log.append(f"ok   {label} ({time.time() - t0:.1f}s)")
        return out
    except Exception as e:
        log.append(f"FAIL {label}: {type(e).__name__}: {e}")
        return None


def stem_mix_facts(stems, sr):
    """Per-stem level, congestion, movement — the per-instrument mix table."""
    rows = {}
    for name, y in stems.items():
        if float(np.max(np.abs(y))) < 1e-4:
            rows[name] = {"rms_db": -99.0, "silent": True}
            continue
        rms = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)
        cong = ears.congestion(y, sr)
        trans = ears.transient_density(y, sr)
        rows[name] = {
            "rms_db": round(float(rms), 1),
            "congestion_db": {k: round(float(v), 1) for k, v in cong.items()},
            "transients_per_s": {k: round(float(v), 1) for k, v in trans.items()},
        }
    return rows


def build_report(name, data, out_dir, cal=None):
    """report.md — composed for an LLM reader, verdicts first."""
    L = []
    add = L.append
    add(f"# Listening report — {name}")
    add(f"duration {data['duration_s']:.1f}s · analyzed {data['analyzed_at']}")
    ctx = data.get("context", "mix")
    add(f"judged as **{ctx}**" +
        (f", calibrated against {cal.contexts[cal.resolve(ctx)]['n']} reference "
         f"excerpts" if data.get("calibrated") and cal else
         ", **uncalibrated** — run `tools/calibrate.py build`"))

    # ---- 1. what a listener would notice ----
    add("\n## 1. What a listener would notice (worst first)")
    problems = list(data.get("ears_verdict") or [])
    problems += list((data.get("harmony") or {}).get("problems") or [])
    sem = data.get("semantic") or {}
    if sem.get("available"):
        for axis, score in sem["quality"].items():
            bad = {a: b for a, b, _ in _axis_poles()}[axis]
            st = cal.stat(ctx, f"clap.{axis}") if cal else None
            if st:
                # flag only what real records do NOT do. A fixed 0.40 cutoff
                # reported lowend_control as a fault on every render for
                # months; the Drumcode masters score 0.07 on it themselves.
                if score < st["p10"] and st["p10"] - score > 0.05:
                    problems.append(
                        f"SEMANTIC {axis.upper()} ({score:.2f}): below every "
                        f"reference (median {st['median']:.2f}, "
                        f"p10 {st['p10']:.2f}) — CLAP hears this closer to "
                        f"'{bad}' than any of the records do.")
            elif score < 0.40:
                problems.append(f"SEMANTIC {axis.upper()} ({score:.2f}): CLAP "
                                f"hears this closer to '{bad}' than the good "
                                f"pole. (uncalibrated — build a calibration to "
                                f"know whether real records do this too)")
    if problems:
        for i, p in enumerate(problems, 1):
            add(f"{i}. {p}")
    else:
        add("Nothing structurally wrong — judge it on taste, not repair.")

    # ---- 2. scores ----
    add("\n## 2. Scores")
    c = data.get("critic")
    if c:
        add(f"- critic: core **{c['techno_core']}** · novelty **{c['novelty']}** "
            f"→ **{c['verdict']}** (nearest: {c['nearest_neighbor']})")
        if c.get("core_outliers"):
            add(f"  - core outliers (z>1.5): {c['core_outliers']}")
    if sem.get("available"):
        q = sem["quality"]
        # A CLAP axis is only readable beside what real records score on it:
        # lowend_control reads 0.07 median on Drumcode masters, so a render's
        # 0.01 is not a fault to chase. Axes whose references cluster tighter
        # than 0.03 carry no gradient and are marked as such.
        if cal and cal.has_context(ctx):
            add("- semantic quality vs the reference records "
                "(0=bad pole, 1=good pole):")
            for k, v in q.items():
                st = cal.stat(ctx, f"clap.{k}")
                if not st:
                    add(f"  - {k} **{v:.2f}** (no reference)")
                    continue
                spread = st["p90"] - st["p10"]
                if spread < 0.03:
                    note = ("references all score "
                            f"{st['median']:.2f} — no gradient, ignore this axis"
                            if abs(v - st["median"]) < 0.05 else
                            f"every reference scores {st['median']:.2f}; you are "
                            f"the outlier")
                elif v < st["p10"]:
                    note = (f"BELOW all references "
                            f"({st['median']:.2f} [{st['p10']:.2f}..{st['p90']:.2f}])")
                elif v > st["p90"]:
                    note = (f"above the references "
                            f"({st['median']:.2f} [{st['p10']:.2f}..{st['p90']:.2f}])")
                else:
                    note = (f"in range ({st['median']:.2f} "
                            f"[{st['p10']:.2f}..{st['p90']:.2f}])")
                add(f"  - {k} **{v:.2f}** — {note}")
        else:
            add("- semantic quality (0=bad pole, 1=good pole): " +
                " · ".join(f"{k} **{v:.2f}**" for k, v in q.items()))
        ch = ", ".join(f"{n} {p:.0%}" for n, p in sem["character"][:4])
        add(f"- character: {ch}")
        add(f"- evokes: {', '.join(m for m, _ in sem['moods'][:5])}")
        r = sem.get("references")
        if r:
            add(f"- vs reference records: semantic core {r['semantic_core']:.3f}, "
                f"max sim {r['semantic_max_sim']:.3f} "
                f"(novelty {r['semantic_novelty']:.3f})")
            for lbl, s in r["nearest"]:
                add(f"  - {s:.3f}  {lbl}")
    elif sem:
        add(f"- semantic ear unavailable: {sem.get('reason')}")

    # ---- 3. the groove ----
    g = data.get("groove_grid")
    if g:
        add("\n## 3. The groove (folded to one 2-bar cycle)")
        src = data.get("groove_source", "full mix")
        add(f"from {src}:")
        add("```")
        add(g)
        add("```")

    if data.get("groove_ab_text"):
        add("\n### Your groove beside the records'")
        add("```")
        add(data["groove_ab_text"])
        add("```")

    # ---- 4. arrangement ----
    s = data.get("sections")
    if s:
        add("\n## 4. Arrangement")
        add("```")
        add(structure_ear.render_table(s))
        add("```")
    if data.get("bars_text"):
        add("\n### Bar by bar (what CLAP's 10 s windows cannot resolve)")
        add("```")
        add(data["bars_text"])
        add("```")

    if data.get("harmony_table"):
        add("\n### Harmony")
        add("```")
        add(data["harmony_table"])
        add("```")
        hp = (data.get("harmony") or {}).get("problems")
        if hp:
            for p in hp:
                add(f"- {p}")

    if data.get("ab_table"):
        add("\n### Every metric against the reference corpus")
        add("```")
        add(data["ab_table"])
        add("```")

    # ---- 5. mix table ----
    er = data.get("ears")
    if er:
        Ld, p = er["loudness"], er["pulse"]
        add("\n## 5. Mix (master)")
        add(f"{Ld['lufs']:.1f} LUFS · peak {Ld['true_peak_db']:.1f} dBFS · "
            f"crest {Ld['crest_db']:.1f} dB · clips {Ld['clip_runs']} · "
            f"stereo corr {Ld['stereo_corr']:+.2f} · mono loss {Ld['mono_loss_db']:.1f} dB")
        add(f"pulse {p['tempo']:.1f} BPM · beat confidence {p['beat_confidence']:.2f} · "
            f"kick/median {p['kick_beat_ratio']:.2f}x · "
            f"low-high {p['low_to_high_ratio_db']:+.1f} dB")
        add("\n| band | level dB | vs ref | congestion | trans/s |")
        add("|---|---|---|---|---|")
        for band, _, _ in ears.BANDS:
            d = er.get("tonal_delta_db", {}).get(band)
            add(f"| {band} | {er['tonal_db'][band]:.1f} | "
                f"{f'{d:+.1f}' if d is not None else '-'} | "
                f"{er['congestion_db'].get(band, 0):.1f} | "
                f"{er['transients_per_s'].get(band, 0):.1f} |")
    sm = data.get("stem_mix")
    if sm:
        add("\n### Per stem")
        for nm, row in sm.items():
            if row.get("silent"):
                add(f"- **{nm}**: silent")
                continue
            worst_cong = max(row["congestion_db"].items(), key=lambda kv: kv[1])
            add(f"- **{nm}**: {row['rms_db']} dB RMS · most congested band "
                f"{worst_cong[0]} ({worst_cong[1]} dB) · "
                f"transients/s {row['transients_per_s']}")

    # ---- 6. semantic timeline ----
    if sem.get("available") and len(sem.get("timeline", [])) > 2:
        add("\n## 6. Quality over time (CLAP, 10 s windows)")
        tl = sem["timeline"]
        axes = [k for k in tl[0] if k != "t"]
        add("| t | " + " | ".join(axes) + " |")
        add("|" + "---|" * (len(axes) + 1))
        for row in tl:
            add(f"| {row['t']:.0f}s | " +
                " | ".join(f"{row[a]:.2f}" for a in axes) + " |")

    # ---- 7. images ----
    add("\n## 7. Look at these (Read the PNGs)")
    for img in data.get("images", []):
        add(f"- `{out_dir / img}`")
    add("\nOverview: full-track mel spec, bar grid, RMS lane, section marks. "
        "Stems: who owns which band, masking. Loop zoom: 16th-grid transient "
        "detail — kick decay, hat placement, mud between hits.")

    (out_dir / "report.md").write_text("\n".join(L))


def _axis_poles():
    import semantic_ear
    return [(n, b[0], g[0]) for n, g, b in semantic_ear.QUALITY_AXES]


def listen(render, quick=False, out_root=None):
    render = pathlib.Path(render).expanduser().resolve()
    name = render.stem.replace(" ", "_")
    out_dir = pathlib.Path(out_root) if out_root else REPO / "listen-reports" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    log = []
    data = {"file": str(render), "analyzed_at": time.strftime("%Y-%m-%d %H:%M"),
            "quick": quick}

    y, _ = librosa.load(str(render), sr=SR, mono=True)
    data["duration_s"] = len(y) / SR

    # tempo + downbeat once, shared by every ear
    tempo0, beats = librosa.beat.beat_track(y=y, sr=SR, trim=False)
    tempo = groove_ear.fold_tempo(tempo0)
    beats_t = librosa.frames_to_time(beats, sr=SR)
    downbeat = groove_ear.find_downbeat(y, SR, tempo, beats_t)

    # stems
    stems = None
    if not quick:
        def _sep():
            import stems as stems_mod
            s = stems_mod.separate(str(render), sr=SR)
            s["other"] = s.get("other", 0) + s.pop("vocals", 0)  # fold leakage
            return s
        stems = _try("stems (demucs)", _sep, log)

    # ears + critic
    def _ears():
        cache = ears.REF_DIR / "tonal_reference.json"
        bal = json.loads(cache.read_text()) if cache.exists() else None
        rep = ears.analyze(str(render), bal)
        return rep
    # Calibration decides the thresholds AND which reference distribution to
    # judge against. Guessing the context is how a drums-only loop got flagged
    # MUDDY for being compared with full commercial masters.
    import calibrate
    cal = calibrate.load()
    context = calibrate.infer_context(stems) if stems else "mix"
    data["context"] = context
    data["calibrated"] = bool(cal and cal.has_context(context))

    data["ears"] = _try("ears", _ears, log)
    if data["ears"]:
        data["ears_verdict"] = ears.verdict(data["ears"], calib=cal,
                                            context=context)
        if cal:
            data["ab_table"] = _try("reference A/B", lambda: calibrate.compare_table(
                cal, calibrate.flatten(data["ears"]), context), log)

    def _critic():
        import critic
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            return critic.score(str(render))
    if (ears.REF_DIR / "fingerprints.json").exists():
        data["critic"] = _try("critic", _critic, log)

    # groove — prefer the drum stem
    def _groove():
        src = stems["drums"] if stems is not None and \
            float(np.max(np.abs(stems["drums"]))) > 1e-4 else y
        lab = None if src is not y else ("LOW", "MID", "HIGH")
        g = groove_ear.analyze(src, SR, tempo_hint=tempo, labels=lab,
                               full_mix=src is y)
        data["groove_source"] = "drum stem" if src is not y else \
            "full mix (LOW row includes the bassline, not just kick)"
        data["groove_json"] = groove_ear.to_json(g)
        return groove_ear.render_grid(g)
    data["groove_grid"] = _try("groove", _groove, log)

    # structure
    def _structure():
        st = {k: v for k, v in (stems or {}).items()} or None
        return structure_ear.describe(y, SR, tempo, stems=st)
    data["sections"] = _try("structure", _structure, log)

    # per-stem mix table
    if stems:
        data["stem_mix"] = _try("stem mix facts",
                                lambda: stem_mix_facts(stems, SR), log)

    # harmony — the only ear that hears pitch
    def _harmony():
        import harmony_ear
        srcs = {"mix": y}
        if stems:
            srcs.update({k: stems[k] for k in ("drums", "bass", "other")
                         if k in stems})
        h = harmony_ear.analyze(srcs, SR)
        data["harmony_table"] = harmony_ear.render_table(h)
        return h
    data["harmony"] = _try("harmony", _harmony, log)

    # bar-scale localization — CLAP's 10 s windows cannot resolve a 1.8 s bar
    def _bars():
        import bar_ear
        # levels from the mix, patterns from the drum stem — same reason the
        # groove ear prefers the stem: on a mix the KICK row is really a LOW row
        dr = stems["drums"] if stems is not None and \
            float(np.max(np.abs(stems["drums"]))) > 1e-4 else None
        r = bar_ear.analyze(y, SR, tempo, downbeat, beats_t, drums=dr)
        data["bars_text"] = bar_ear.describe(r)
        return {k: v for k, v in r.items() if k != "bars"}
    data["bars"] = _try("bar ear", _bars, log)

    # groove A/B against the reference grids
    def _groove_ab():
        import groove_ref
        refs = cal.groove_refs() if cal else []
        if not refs or not data.get("groove_json"):
            return None
        res = groove_ref.analyze(data["groove_json"], refs)
        data["groove_ab_text"] = groove_ref.render_report(
            data["groove_json"], res, {r["label"]: r for r in refs})
        return {k: v for k, v in res.items() if k != "top"}
    data["groove_ab"] = _try("groove A/B", _groove_ab, log)

    # semantic (CLAP)
    if not quick:
        def _semantic():
            import semantic_ear
            return semantic_ear.analyze(str(render))
        data["semantic"] = _try("semantic (CLAP)", _semantic, log)

    # images
    images = []

    def _imgs():
        spectro.overview(y, SR, tempo, downbeat, data.get("sections"),
                         out_dir / "overview.png", title=name)
        images.append("overview.png")
        spectro.loop_zoom(y, SR, tempo, downbeat, out_dir / "loop.png")
        images.append("loop.png")
        if stems:
            ordered = {k: stems[k] for k in ("drums", "bass", "other") if k in stems}
            ordered["FULL"] = y
            spectro.stems_figure(ordered, SR, tempo, downbeat,
                                 out_dir / "stems.png")
            images.append("stems.png")
        return True
    _try("images", _imgs, log)
    data["images"] = images
    data["log"] = log

    (out_dir / "report.json").write_text(json.dumps(
        {k: v for k, v in data.items() if k != "groove_grid"}, indent=1,
        default=str))
    build_report(name, data, out_dir, cal=cal)

    print(f"\nreport -> {out_dir / 'report.md'}")
    for line in log:
        print(f"  {line}")
    return out_dir


def compare(dir_a, dir_b):
    """Diff two listen reports (older first): did the last change help?"""
    def load(d):
        return json.loads((pathlib.Path(d) / "report.json").read_text())
    A, B = load(dir_a), load(dir_b)
    print(f"A = {pathlib.Path(dir_a).name}\nB = {pathlib.Path(dir_b).name}\n")

    rows = []
    for label, path in [
            ("critic core", ("critic", "techno_core")),
            ("critic novelty", ("critic", "novelty")),
            ("LUFS", ("ears", "loudness", "lufs")),
            ("crest dB", ("ears", "loudness", "crest_db")),
            ("kick/median", ("ears", "pulse", "kick_beat_ratio")),
            ("beat confidence", ("ears", "pulse", "beat_confidence"))]:
        va, vb = A, B
        try:
            for k in path:
                va, vb = va[k], vb[k]
            rows.append((label, float(va), float(vb)))
        except (KeyError, TypeError):
            continue
    for sem_key in (A.get("semantic") or {}).get("quality", {}):
        try:
            rows.append((f"sem {sem_key}",
                         A["semantic"]["quality"][sem_key],
                         B["semantic"]["quality"][sem_key]))
        except (KeyError, TypeError):
            continue
    print(f"{'metric':>18s} {'A':>8s} {'B':>8s}   delta")
    for label, va, vb in rows:
        d = vb - va
        arrow = "→" if abs(d) < 1e-3 else ("▲" if d > 0 else "▼")
        print(f"{label:>18s} {va:8.2f} {vb:8.2f}   {arrow} {d:+.2f}")

    for name, rep in (("A", A), ("B", B)):
        v = rep.get("ears_verdict") or []
        print(f"\n{name} problems ({len(v)}):")
        for line in v:
            print(f"  - {line.split(':')[0]}")
    gone = {p.split(":")[0] for p in (A.get("ears_verdict") or [])} - \
           {p.split(":")[0] for p in (B.get("ears_verdict") or [])}
    new = {p.split(":")[0] for p in (B.get("ears_verdict") or [])} - \
          {p.split(":")[0] for p in (A.get("ears_verdict") or [])}
    if gone:
        print(f"\nfixed since A: {', '.join(sorted(gone))}")
    if new:
        print(f"NEW problems in B: {', '.join(sorted(new))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render", help="audio file, 'refs' to build CLAP cache, "
                                   "or 'compare'")
    ap.add_argument("other", nargs="*", default=[],
                    help="for compare: [older-report-dir newer-report-dir] "
                         "(defaults to the two most recent)")
    ap.add_argument("--quick", action="store_true",
                    help="skip stems + CLAP (DSP only, fast)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.render == "refs":
        import semantic_ear
        semantic_ear.build_reference_cache(semantic_ear.SemanticEar())
    elif a.render == "compare":
        dirs = sorted((REPO / "listen-reports").iterdir(),
                      key=lambda p: (p / "report.json").stat().st_mtime
                      if (p / "report.json").exists() else 0)
        if len(a.other) == 2:
            compare(a.other[0], a.other[1])
        elif len(dirs) >= 2:
            compare(dirs[-2], dirs[-1])       # two most recent reports
        else:
            sys.exit("need two reports to compare")
    else:
        listen(a.render, quick=a.quick, out_root=a.out)


if __name__ == "__main__":
    main()
