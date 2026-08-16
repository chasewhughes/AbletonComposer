#!/usr/bin/env python3
"""Groove A/B — your pattern beside the pattern of records that groove.

The CLAP groove axis moved 0.11 -> 0.09 -> 0.04 across iterations while
top_end genuinely improved, and nothing corroborated it. It is a relative
score against two text prompts: it can say "closer to stiff than to rolling"
and it cannot say what to change. This module answers the same question with
something checkable — the reference records' own step grids.

Three readings:

  similarity  Per role, F1 between your hit set and the reference's, plus
              velocity-profile correlation, after aligning on the kick. One
              number per reference; the best match names a record.
  calibration The references' similarity TO EACH OTHER. This is the part that
              makes the score mean anything: if two Drumcode records only
              agree 0.55 with each other, your 0.52 is normal and the axis is
              not telling you to change anything. Reported as a percentile.
  deltas      Which steps you play that no reference plays, which steps every
              reference plays that you miss, density per bar, and swing —
              stated in steps and milliseconds, which are editable.

Usage:
  .venv-listen/bin/python tools/groove_ref.py <render.wav>
"""
import numpy as np

HIT = 0.40          # prob above which a folded step counts as a played hit
ROLE_WEIGHT = {"KICK": 1.0, "PERC": 0.8, "HATS": 1.0}


def _hits(role, thresh=HIT):
    return np.array(role["prob"], dtype=float) >= thresh


def _f1(a, b):
    tp = float(np.sum(a & b))
    if tp == 0:
        return 0.0
    prec = tp / max(1.0, float(np.sum(a)))
    rec = tp / max(1.0, float(np.sum(b)))
    return float(2 * prec * rec / (prec + rec + 1e-12))


def _corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def best_rotation(a_roles, b_roles, n_steps):
    """Align two folded cycles on the kick before comparing anything else.

    Both grids place step 0 at a downbeat found from low-band weight, but a
    render whose kick is buried can land a beat off. Rotating in whole-beat
    steps only — a half-step rotation would manufacture agreement that no
    listener would hear.
    """
    ka = _hits(a_roles["KICK"]) if "KICK" in a_roles else None
    kb = _hits(b_roles["KICK"]) if "KICK" in b_roles else None
    if ka is None or kb is None or not ka.any() or not kb.any():
        return 0
    best, best_score = 0, -1.0
    for r in range(0, n_steps, 4):
        s = _f1(np.roll(ka, r), kb)
        if s > best_score:
            best, best_score = r, s
    return best


def compare_one(render, ref):
    """Similarity of one folded grid to one reference grid."""
    r_roles, b_roles = render["roles"], ref["roles"]
    roles = [k for k in r_roles if k in b_roles]
    if not roles:
        return None
    n = len(r_roles[roles[0]]["prob"])
    rot = best_rotation(r_roles, b_roles, n)
    per_role, weights = {}, []
    for name in roles:
        a, b = r_roles[name], b_roles[name]
        ah, bh = np.roll(_hits(a), rot), _hits(b)
        av = np.roll(np.array(a["vel"], float), rot)
        bv = np.array(b["vel"], float)
        f1 = _f1(ah, bh)
        vc = _corr(av, bv)
        per_role[name] = {
            "f1": round(f1, 3),
            "vel_corr": round(vc, 3),
            "hits_render": int(ah.sum()),
            "hits_ref": int(bh.sum()),
            "missing": [int(i) for i in np.where(bh & ~ah)[0]],
            "extra": [int(i) for i in np.where(ah & ~bh)[0]],
        }
        # velocity correlation is a tiebreaker, not half the score: a pattern
        # on the right steps with flat dynamics is still the right pattern
        per_role[name]["score"] = round(0.75 * f1 + 0.25 * max(0.0, vc), 3)
        weights.append(ROLE_WEIGHT.get(name, 0.5))
    total = float(np.average([per_role[k]["score"] for k in roles],
                             weights=weights))
    return {"label": ref.get("label", "?"), "similarity": round(total, 3),
            "rotation_steps": rot, "roles": per_role,
            "swing_delta_ms": (round(render["swing_ms"] - ref["swing_ms"], 1)
                               if render.get("swing_ms") is not None and
                               ref.get("swing_ms") is not None else None)}


def self_similarity(refs):
    """How much the references agree with EACH OTHER — the yardstick.

    Without this a similarity of 0.5 is another uninterpretable number. With
    it, 0.5 is either normal for the genre or an outlier, and only one of
    those is a reason to change the pattern.
    """
    scores = []
    for i in range(len(refs)):
        best = None
        for j in range(len(refs)):
            if i == j or refs[i].get("label") == refs[j].get("label"):
                continue                   # same record, other window
            c = compare_one(refs[i], refs[j])
            if c and (best is None or c["similarity"] > best):
                best = c["similarity"]
        if best is not None:
            scores.append(best)
    if not scores:
        return None
    a = np.array(scores)
    return {"n": len(a), "median": round(float(np.median(a)), 3),
            "p10": round(float(np.percentile(a, 10)), 3),
            "p90": round(float(np.percentile(a, 90)), 3),
            "min": round(float(a.min()), 3), "max": round(float(a.max()), 3)}


def role_density_stats(refs):
    """Hits per 2-bar cycle per role across the references, and swing."""
    out = {}
    for r in refs:
        for name, role in r["roles"].items():
            out.setdefault(name, []).append(int(_hits(role).sum()))
    stats = {k: {"median": float(np.median(v)),
                 "p10": float(np.percentile(v, 10)),
                 "p90": float(np.percentile(v, 90)), "n": len(v)}
             for k, v in out.items()}
    sw = [r["swing_ms"] for r in refs if r.get("swing_ms") is not None] or [0.0]
    stats["_swing_ms"] = {"median": float(np.median(sw)),
                          "p10": float(np.percentile(sw, 10)),
                          "p90": float(np.percentile(sw, 90)), "n": len(sw)}
    return stats


def _row(bits, rot=0):
    b = np.roll(np.asarray(bits), rot)
    s = "".join("X" if v else "." for v in b)
    return "|".join(" ".join(s[i + j:i + j + 4] for j in range(0, 16, 4))
                    for i in range(0, len(s), 16))


def analyze(render_grid, refs, top_k=3):
    """Full groove A/B: nearest references, calibration, per-role deltas."""
    if not refs:
        return {"available": False, "reason": "no reference grids in calibration"}
    scored = [c for c in (compare_one(render_grid, r) for r in refs) if c]
    if not scored:
        return {"available": False, "reason": "no comparable roles"}
    scored.sort(key=lambda c: -c["similarity"])
    calib = self_similarity(refs)
    best = scored[0]
    verdict = None
    if calib:
        if best["similarity"] >= calib["p10"]:
            verdict = (f"normal for the genre — references agree with each "
                       f"other {calib['median']:.2f} "
                       f"[{calib['p10']:.2f}..{calib['p90']:.2f}]")
        else:
            verdict = (f"outside the reference spread: the records agree with "
                       f"each other {calib['p10']:.2f} at worst, you reach "
                       f"{best['similarity']:.2f}")
    return {"available": True, "best": best, "top": scored[:top_k],
            "calibration": calib, "density": role_density_stats(refs),
            "verdict": verdict}


def render_report(render_grid, result, refs_by_label=None):
    """The groove A/B as text: your row above the reference's row."""
    if not result.get("available"):
        return f"groove A/B unavailable: {result.get('reason')}"
    best = result["best"]
    L = [f"nearest reference groove: **{best['label']}** "
         f"(similarity {best['similarity']:.2f}"
         f"{', aligned +' + str(best['rotation_steps']) + ' steps' if best['rotation_steps'] else ''})"]
    if result.get("verdict"):
        L.append(result["verdict"])
    L.append("runners-up: " + ", ".join(
        f"{c['label'][:32]} {c['similarity']:.2f}" for c in result["top"][1:]))

    ref = (refs_by_label or {}).get(best["label"])
    dens = result.get("density", {})
    L.append("")
    for name, r in best["roles"].items():
        L.append(f"{name}:  F1 {r['f1']:.2f} · vel corr {r['vel_corr']:+.2f} · "
                 f"you {r['hits_render']} hits / 2 bars, this record "
                 f"{r['hits_ref']}" +
                 (f" · all refs {dens[name]['median']:.0f} "
                  f"[{dens[name]['p10']:.0f}..{dens[name]['p90']:.0f}]"
                  if name in dens else ""))
        if ref and name in ref["roles"]:
            L.append(f"  you  |{_row(_hits(render_grid['roles'][name]), best['rotation_steps'])}|")
            L.append(f"  ref  |{_row(_hits(ref['roles'][name]))}|")
        if r["missing"]:
            L.append(f"  steps the reference plays and you do not: "
                     f"{r['missing']}")
        if r["extra"]:
            L.append(f"  steps you play and it does not: {r['extra']}")
    sw = dens.get("_swing_ms")
    mine = render_grid.get("swing_ms")
    if sw and mine is not None:
        L.append("")
        L.append(f"swing: you {mine:+.0f} ms · references {sw['median']:+.0f} ms "
                 f"[{sw['p10']:+.0f}..{sw['p90']:+.0f}]")
    elif sw:
        L.append("")
        L.append("swing: unmeasurable on this render (the hat row has no "
                 "on-beat hits, so detector bias cannot be cancelled)")
    return "\n".join(L)


def main():
    import argparse
    import pathlib
    import sys
    TOOLS = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(TOOLS))
    import librosa
    import calibrate
    import groove_ear
    import stems as stems_mod

    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("--no-stems", action="store_true")
    a = ap.parse_args()

    cal = calibrate.load()
    if cal is None:
        sys.exit("no calibration — run `calibrate.py build` first")
    refs = cal.groove_refs()

    y, sr = librosa.load(a.render, sr=44100, mono=True)
    src = y
    if not a.no_stems:
        try:
            st = stems_mod.separate(a.render, sr=sr, verbose=False)
            if float(np.max(np.abs(st["drums"]))) > 1e-4:
                src = st["drums"]
        except Exception as e:
            print(f"(stems unavailable, using full mix: {e})")
    # role names have to stay KICK/PERC/HATS to line up with the reference
    # grids, but on a full mix the KICK row is a low-band row: say so by
    # turning the attack gate off rather than pretending it is a kick channel
    g = groove_ear.to_json(groove_ear.analyze(src, sr, full_mix=src is y))
    res = analyze(g, refs)
    print(render_report(g, res, {r["label"]: r for r in refs}))


if __name__ == "__main__":
    main()
