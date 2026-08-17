#!/usr/bin/env python3
"""Audition Splice candidates BEFORE spending a credit on them.

The problem this exists for
--------------------------
`mcp__splice__describe_a_sound` returns filename, pack, tags, duration and
sometimes key/BPM. It does not return audio. That is not enough information to
choose, and the catalogue makes it obvious: a search for a techno kick returned
27,157 hits whose top ten were

    rdt_kick_one_shot_synthetic_low_smashed / _master / _real / _counter
                                    _boss / _gogo / _blast / _older / _word
    tags (all identical): synth, drums, kicks, techno, tech house, minimal techno
    duration (all): 0.5s

Nine samples from one pack, indistinguishable metadata, told apart only by a
suffix somebody picked at random. Choosing from that response is a coin flip on
how suggestive a filename looks — and every flip costs one download credit,
because the repo's measuring tools (`oneshot_bank`, `ears`, `calibrate`) only
ever saw a sample AFTER it was bought. All 14 Phase 3 sources were picked that
way.

What this does instead
----------------------
Splice's public sample page embeds a presigned preview MP3 for that exact
sample: free, no credit, no auth. So the whole measuring stack can run before
the purchase decision.

What a preview actually is, measured 2026-08-17 rather than assumed:

  * HALF the catalogue length, one-shots and loops alike: 2.11 -> 1.06 s,
    2.01 -> 0.99, 1.00 -> 0.52, 0.5 -> 0.26, 0.4 -> 0.183, 7.2 -> 3.60.
    (An earlier note in this file claimed one-shot previews arrive complete.
    That was byte-math on a stereo file read as mono, and it was wrong.)
  * with a floor. A 0.1 s hat's preview is 5.5 ms — 241 frames, not 50% —
    which is below the 20 ms `oneshot_bank` needs. Anything under roughly 0.3 s
    in the catalogue may be un-auditionable, and the report says so per
    candidate instead of dropping it.
  * assembled from two segments. The 3.60 s loop preview is a clean 2.013 bars
    at its labelled 134 BPM with 28 onsets and no silent gaps — but its largest
    spectral discontinuity sits at exactly its midpoint, ranking at the 92.6 to
    99.7 percentile of all frame transitions across seven loops tested. Each
    half is real audio; the sequence across the seam is not the sample's
    arrangement. Judge timbre from a loop preview, not groove. `seam_pct`
    reports this per candidate.
  * NOT a faithful excerpt. `--ab` puts a bought WAV over its own preview:
    Plattenbau's WAV is a 2.11 s kick with its transient at 0 ms reaching
    14 kHz, and the preview is 1.06 s, onset at 42 ms, with nothing above
    ~2 kHz. Best normalised cross-correlation 0.44 at a 68 ms offset; against
    the head of the file, 0.11. The URL says `-scrambled` and it means it.
  * lossy unevenly. `--control=preview` pairs each already-bought Phase 3
    sample with its own preview and measures per-feature drift. Peak frequency
    moves 0.00 sigma; crest +6.5 and noisiness -7.7, and the whole-sample
    verdict string changed on 3 of 3 controlled kicks.

So ranking runs on `AUDITION_STABLE` filtered by `usable_stable` — the features
that both survive the trip AND carry information for the role in question. That
second filter matters more than it looks: `share.high` and `share.air` are
beautifully stable for a kick because reference kicks hold 0.00-0.08% of their
power up there, so a z-score on them is amplified floor. They were contributing
a fixed 1.68 and 0.50 to all ten candidates of the first probe and making the
aggregate look better-founded than it was. Dropped for kicks, kept for hats.

What survives for a kick is centroid and peak frequency, and `peak_hz` is
quantised to FFT bins — two distinct values across ten candidates. Which is to
say: a preview can sort dark-and-subby from bright-and-clicky, and it cannot
rank near-identical siblings from one pack. The `discrimination` block prints
which axes are actually separating a shortlist so that limit is visible in
every run, and the measured noise floor on full oddity is ~0.37, so candidates
within 0.4 of each other are not separable here at all.

The honest summary: this tool stops credits being spent on filename roulette
and it does not replace hearing the sample. Use it to shortlist three from
thirty, buy those, then measure the WAVs and let your ears pick.

Usage
-----
Search with the MCP tool, then paste its markdown straight in:

    .venv-analysis/bin/python tools/audition.py --role=kick < results.md
    .venv-analysis/bin/python tools/audition.py --loop --context=drums < results.md

or name pages explicitly:

    .venv-analysis/bin/python tools/audition.py --role=hat \\
        https://splice.com/sounds/sample/<hash>/<slug> ...

Output: a ranked table, `audition.json`, cached preview WAVs, and a contact
sheet PNG of mel spectrograms for the top N — that last one matters, because a
spectrogram is the part of a sound Claude can actually look at.

Ranking
-------
One-shots are scored against the reference bank cut from the Drumcode drum
stems — 1408 real kicks, 797 hats, 1505 percussion hits. Two columns print:
`stable` (mean |z| over the preview-usable features, which is what the order
uses) and `full` (`oneshot_bank.oddity`, all ten core features, correct for a
bought WAV and optimistic-to-wrong for a preview). Low = behaves like the role.

That default is deliberate and it is worth saying why, because this repo's goal
is to invent a genre, not to average one. The signature is supposed to come
from the resampling chains in `resample_engine.py`, not from buying a weird
kick — raw material that does not behave like a kick makes every downstream
chain fight it. But the novelty axis is real, so `--prefer=odd` inverts the
ranking for when a deliberate outlier is the point. Either way `n_outside` and
the named axes print, so an odd pick is a choice instead of an accident.

Loops have no one-shot bank to score against, so they go to `calibrate.json`:
every `ears` metric as a z against the reference distribution for a context
(drums / bass / other / mix), ranked by median |z|, plus whether the detected
tempo agrees with the catalogue BPM.
"""
import argparse
import concurrent.futures as futures
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

import numpy as np

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import ears            # noqa: E402
import oneshot_bank    # noqa: E402
import calibrate       # noqa: E402

SR = oneshot_bank.SR
CACHE = REPO / ".cache" / "audition"
OUT_ROOT = REPO / "listen-reports" / "audition"

# A browser UA is required — the sample page returns a shell without the
# embedded player JSON otherwise, and the preview URL lives in that JSON.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

SAMPLE_RE = re.compile(
    r"https://splice\.com/sounds/sample/(?P<hash>[0-9a-f]{64})/(?P<slug>[a-z0-9\-]+)")
PREVIEW_RE = re.compile(r"https://spliceproduction\.s3[^\"'\\ <>]+")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")

BANK_ROLES = set(oneshot_bank.BANK_ROLES)     # kick, hat, perc


# ------------------------------------------------------------------ parsing

def parse_candidates(text):
    """Pull candidates out of whatever `describe_a_sound` printed.

    The MCP tool's markdown is parsed positionally: each `### n. name` heading
    opens a block, and the metadata lines that follow it up to the next heading
    belong to it. Bare URLs with no surrounding markdown work too, which is
    what the `argv` path produces.
    """
    blocks, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s*\d+\.\s*(?P<name>.+?)\s*$", line)
        if m:
            cur = {"name": m.group("name").strip()}
            blocks.append(cur)
            continue
        if cur is None:
            # A URL before any heading (argv or a bare list) is its own block.
            u = SAMPLE_RE.search(line)
            if u:
                blocks.append({"name": u.group("slug"), "page": u.group(0)})
            continue
        u = SAMPLE_RE.search(line)
        if u and "page" not in cur:
            cur["page"] = u.group(0)
        for key, pat, cast in (
                ("bpm", r"BPM:\s*([0-9]+)", int),
                ("catalog_s", r"Duration:\s*([0-9.]+)s", float),
                ("type", r"Type:\s*(loop|oneshot)", str),
                ("key", r"Key:\s*([A-Ga-g][#b]?m?(?:aj|in)?)\b", str),
                ("pack", r"\*\*Pack:\*\*\s*(.+?)\s*$", str),
                ("tags", r"\*\*Tags:\*\*\s*(.+?)\s*$", str)):
            if key not in cur:
                mm = re.search(pat, line)
                if mm:
                    cur[key] = cast(mm.group(1))
        if "uuid" not in cur:
            mm = re.search(r"Asset UUID:\*{0,2}\s*(" + UUID_RE.pattern + ")",
                           line)
            if mm:
                cur["uuid"] = mm.group(1)

    out = []
    seen = set()
    for b in blocks:
        if "page" not in b:
            continue                       # a heading we could not resolve
        h = SAMPLE_RE.search(b["page"]).group("hash")
        if h in seen:
            continue
        seen.add(h)
        b["hash"] = h
        out.append(b)
    return out


# ------------------------------------------------------------------ fetching

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def preview_url(page_url, want_hash=None):
    """The presigned preview MP3 for one sample page.

    A pack page also embeds `sample_pack_demos/*.mp3` on a different bucket —
    those are multi-minute pack demos, not this sample, so only the
    `spliceproduction` audio_samples bucket is accepted. When several match,
    the one whose path carries this sample's hash wins.
    """
    html = _get(page_url).decode("utf8", "ignore")
    urls = [u.replace("\\u0026", "&") for u in PREVIEW_RE.findall(html)]
    if not urls:
        raise LookupError("no preview URL embedded in the page")
    if want_hash:
        for u in urls:
            if want_hash in u:
                return u
    return urls[0]


def _decode_to_wav(mp3_path, wav_path):
    """MP3 -> 44.1k WAV. afconvert first (it is on every Mac and does not care
    what librosa's backend situation is), soundfile/librosa as the fallback."""
    try:
        subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{SR}",
                        str(mp3_path), str(wav_path)],
                       check=True, capture_output=True)
        if wav_path.exists() and wav_path.stat().st_size > 44:
            return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    import librosa
    import soundfile as sf
    y, sr = librosa.load(str(mp3_path), sr=SR, mono=True)
    sf.write(str(wav_path), y, sr)


def acquire(cand, keep_mp3=False, refetch=False):
    """Preview WAV for one candidate, cached by sample hash.

    Cached on the hash rather than the presigned URL on purpose: the URL
    carries `X-Amz-Expires=21600`, so it dies in 6 hours while the sample does
    not. A second run of the same shortlist costs no network at all.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    wav = CACHE / f"{cand['hash'][:16]}.wav"
    if wav.exists() and wav.stat().st_size > 44 and not refetch:
        cand["wav"] = str(wav)
        cand["cached"] = True
        return cand
    mp3 = CACHE / f"{cand['hash'][:16]}.mp3"
    try:
        url = preview_url(cand["page"], cand["hash"])
        data = _get(url)
        # A 0.1 s hat halves to ~0.05 s, which is a legitimate ~1 KB MP3 — the
        # first threshold here was 512 bytes and silently dropped exactly those
        # short one-shots from the control. Only an error page is smaller.
        if len(data) < 200:
            raise LookupError(f"preview was only {len(data)} bytes")
        mp3.write_bytes(data)
        _decode_to_wav(mp3, wav)
        cand["wav"] = str(wav)
        cand["preview_bytes"] = len(data)
        cand["cached"] = False
    except (urllib.error.HTTPError, urllib.error.URLError, LookupError,
            OSError) as e:
        cand["error"] = f"{type(e).__name__}: {e}"
    finally:
        if mp3.exists() and not keep_mp3:
            mp3.unlink()
    return cand


# ----------------------------------------------------------------- measuring

# Which features survive the trip through a Splice preview, measured by
# `--control=preview` on 2026-08-17 over kicks and hats that were actually
# bought (drift = preview z minus bought-WAV z, median over pairs):
#
#     peak_hz        +0.00      share.air       +0.00
#     share.high     -0.01      zcr             -0.01
#     centroid_hz    -0.88      share.highmid   -0.08
#     ---- above are usable, below are not ----
#     rolloff85_hz   -1.26      root_hz         -1.33
#     share.lowmid   -1.39      decay20_ms      +1.39
#     share.mid      -1.54      share.sub       +2.46
#     share.bass     -2.73      peak_offset_ms  -3.00
#     crest_db       +6.54      noisiness_db    -7.74
#
# The two worst are not as catastrophic as the sigma suggests — `crest_db` and
# `noisiness_db` have their corpus sigma floored at 0.5 dB, so 6-8 sigma is
# 3-4 dB of real change — but relative to the spread this repo scores against,
# they are unusable from a preview.
#
# Note what this is NOT: truncation. All three control kicks kept more than the
# 300 ms the kick window measures (1.06 s, 0.99 s, 0.52 s), so the compared
# window held identical content. The drift is the codec (and whatever Splice
# does to previews), which is why it lands on the noise/envelope features that
# MP3 time-smearing touches and leaves peak frequency and the top bands alone.
# The kick control alone would allow `share.highmid` (-0.08) and `zcr` (-0.01),
# but the hat control moves them -2.26 and -1.77, so they are out. What is left
# is what held across BOTH roles — four features, which is a coarse reading and
# is meant to be. Widening this set without re-running --control=preview on more
# bought pairs (hats are n=1 so far) would be fitting to one sample.
AUDITION_STABLE = ["peak_hz", "centroid_hz", "share.high", "share.air"]


# A band share this small is not a measurement of the sample, it is the floor.
# Reference kicks hold 0.00-0.08% of their POWER above 6 kHz, so a z-score on
# `share.high` for a kick is amplified nothing — and it was silently making the
# aggregate look better-founded than it was: on the ten-kick probe `share.high`
# and `share.air` contributed a fixed 1.68 and 0.50 to every candidate.
DEAD_SHARE_PCT = 0.5


def usable_stable(bank, role):
    """The preview-stable features that also carry information for THIS role.

    Stability and informativeness are different questions and both have to be
    asked. `share.air` survives a preview intact for a kick — because it is
    zero before and after. Hats and percussion do live up there, so the set is
    role-dependent rather than fixed.
    """
    stats = bank.stats(role) or {}
    keep, dropped = [], []
    for k in AUDITION_STABLE:
        st = stats.get(k)
        if st is None:
            dropped.append((k, "no reference stat"))
            continue
        if k.startswith("share.") and oneshot_bank.disp(st, k) < DEAD_SHARE_PCT:
            dropped.append((k, f"reference {role}s hold "
                               f"{oneshot_bank.disp(st, k):.2f}% here"))
            continue
        keep.append(k)
    return keep, dropped


def stable_zs(bank, role, f, keys=None):
    """{feature: |z|} over the preview-stable, role-informative features."""
    stats = bank.stats(role) or {}
    keys = keys if keys is not None else usable_stable(bank, role)[0]
    out = {}
    for k in keys:
        if k in f and k in stats:
            z = abs(oneshot_bank.zscore(stats.get(k), f[k]))
            if np.isfinite(z):
                out[k] = float(z)
    return out


def stable_oddity(bank, role, f):
    """Aggregate the preview-stable |z| into one number — as a MEAN, not the
    median `oneshot_bank.oddity` uses.

    That looks like an inconsistency and is a deliberate one. The median is
    right for `oddity` because it aggregates ten features, several with almost
    no spread, where extreme-sensitive statistics develop runaway tails. Here
    there are four, and the two features the median lands between
    (`share.high`, `share.air`) turned out to be nearly constant across a
    candidate pool: on the ten-kick probe they read 1.68 and 0.50 for every
    single candidate, so the median returned three distinct values for ten
    samples and tied eight of them. The mean at least propagates the axis that
    does vary.

    It also means this number is only as good as the spread underneath it,
    which is what `discrimination` exists to expose.
    """
    zs = stable_zs(bank, role, f)
    return float(np.mean(list(zs.values()))) if zs else float("nan")


def discrimination(cands):
    """Which axes are actually separating this shortlist?

    A rank order is worthless if every candidate scores the same on three of
    four axes — the tool would be sorting by the fourth while looking like it
    weighed all of them. On the ten-kick probe exactly that happened:
    `share.high` spread 0.01 sigma and `share.air` 0.01 across all ten, and
    `peak_hz` took two values because it is quantised to FFT bins. The order
    was `centroid_hz` alone, which is also the stable axis with the most
    preview drift (-0.88 sigma). Worth knowing before spending a credit on rank
    number one.
    """
    rows = {}
    for c in cands:
        for k, v in (c.get("stable_z") or {}).items():
            rows.setdefault(k, []).append(v)
    out = []
    for k, vals in rows.items():
        v = np.array(vals, dtype=float)
        out.append((k, float(v.max() - v.min()), len(set(np.round(v, 2)))))
    out.sort(key=lambda t: -t[1])
    return out


def measure_oneshot(cand, role, bank, rank_on="stable"):
    """Score against the reference one-shot bank."""
    rep = oneshot_bank.profile(cand["wav"], bank, role=role, verbose=False)
    if "error" in rep:
        cand["error"] = rep["error"]
        return cand
    cand.update({
        "preview_s": rep.get("duration_s"),
        "auto_role": rep.get("auto_role"),
        "oddity": rep.get("oddity"),
        "oddity_percentile": rep.get("oddity_percentile"),
        "n_outside": rep.get("n_outside"),
        "outside_axes": rep.get("outside_axes", []),
        "verdict": rep.get("verdict", ""),
        "in_bank": rep.get("in_bank", False),
        "z": rep.get("z", {}),
        "features": rep.get("features", {}),
        "report": rep.get("report", ""),
    })
    f = rep.get("features", {})
    so = stable_oddity(bank, role, f) if f else float("nan")
    cand["stable_oddity"] = None if not np.isfinite(so) else round(so, 3)
    cand["stable_z"] = {k: round(v, 2)
                        for k, v in stable_zs(bank, role, f).items()} if f else {}
    # Which of the outside axes are ones a preview can actually see. The rest
    # stay in the report, flagged, rather than being deleted — a bought WAV can
    # confirm them later.
    cand["outside_stable"] = [k for k in cand["outside_axes"]
                              if k in AUDITION_STABLE]
    key = (cand["stable_oddity"] if rank_on == "stable" else cand["oddity"])
    cand["rank_key"] = key if key is not None else float("inf")
    return cand


# Loop metrics worth ranking on. Deliberately not every flattened `ears` key:
# the point is tonal balance, transient behaviour and pulse, and a median over
# thirty correlated keys stops discriminating. `loudness.lufs` is excluded on
# purpose — see `align_loudness`, which pins it.
LOOP_METRICS = [
    "tonal_db.sub", "tonal_db.bass", "tonal_db.lowmid", "tonal_db.mid",
    "tonal_db.highmid", "tonal_db.high", "tonal_db.air",
    "loudness.crest_db",
    "pulse.kick_beat_ratio", "pulse.low_to_high_ratio_db",
    "transients_per_s.high", "transients_per_s.mid",
]


# What a real record scores on the loop path, measured by `--control=loop` over
# the 18 Drumcode reference excerpts on 2026-08-17: (median, p90).
#
# 'mix' is the plumbing check — those excerpts ARE the mix corpus, and 0.71 is
# almost exactly the 0.67 sigma you expect when drawing a sample from its own
# distribution, so the alignment, key names and context resolution are sound.
# 'drums' is the number that matters for auditioning a drum loop, and it is
# higher (1.12) because a full-mix excerpt is not a drum stem.
LOOP_REF = {"mix": (0.71, 1.04), "drums": (1.12, 1.61)}


def align_loudness(y, cal, ctx):
    """Gain the preview to the corpus's median LUFS before measuring it.

    Without this the loop scoring measures gain staging and calls it tone.
    `ears.tonal_db` is absolute dB per band, and a raw Splice loop sits around
    -20 LUFS while the reference corpus is mastered club techno at -7.3 — so
    every band of every candidate reads 12 dB low, all seven z-scores go
    strongly negative, and the ranking sorts by how hot the sample was
    exported rather than by what it sounds like. This repo has already paid for
    that confusion once: three level raises totalling +17 dB were read as tonal
    findings, and +5 dB of limiter drive moved CLAP groove 0.49 -> 0.83 on its
    own.

    Gain is also the one property that genuinely does not matter here. The
    sample is going into a Simpler and a chain that sets its own level.

    Returns (aligned_y, applied_db, original_lufs).
    """
    loud = ears.loudness_array(y, SR)
    lufs = loud["lufs"]
    target = None
    if cal is not None:
        st = cal.stat(ctx, "loudness.lufs")
        if st:
            target = st["median"]
    if target is None or not np.isfinite(lufs) or lufs <= -70:
        return y, 0.0, lufs
    gain_db = float(target - lufs)
    g = 10 ** (gain_db / 20.0)
    out = y * g
    # Aligning up can push a normalised loop past full scale. Peak-limit by
    # scaling back rather than clipping: clipping would manufacture exactly the
    # high-frequency transient content the transient metrics are reading.
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 0.999:
        out = out * (0.999 / peak)
        gain_db += 20 * np.log10(0.999 / peak)
    return out, round(gain_db, 2), lufs


def seam_percentile(y):
    """Where the midpoint's spectral jump ranks among all frame transitions.

    Splice serves previews from a path with `-scrambled` in it, and on loops the
    contact sheet shows a vertical line at exactly half way. Measured over seven
    134 BPM percussion loops, the midpoint transition ranked at the 92.6, 97.6,
    98.9, 99.0, 99.2, 99.7 and 92.6 percentile of every adjacent-frame cosine
    distance in the file — i.e. the single biggest spectral discontinuity in the
    preview sits at its own midpoint, every time.

    So a loop preview is two segments joined, not the first half of the sample.
    The timbre of each segment is real; the sequence ACROSS the seam is not the
    sample's arrangement, which is exactly the thing you would otherwise judge
    groove from. High values here mean 'trust the sound, not the pattern'.
    """
    import librosa
    if len(y) < 4096:
        return None
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=256))
    S = S / (np.linalg.norm(S, axis=0, keepdims=True) + 1e-12)
    dist = 1 - np.sum(S[:, 1:] * S[:, :-1], axis=0)
    if len(dist) < 16:
        return None
    mid = len(y) // 2 // 256
    peak = float(dist[max(0, mid - 3):mid + 4].max())
    return round(100.0 * float((dist < peak).mean()), 1)


def measure_loop(cand, context, cal, align=True):
    """Score a loop against the calibration corpus for one context."""
    import librosa
    y, _ = librosa.load(cand["wav"], sr=SR, mono=True)
    if len(y) < int(0.2 * SR):
        cand["error"] = "preview shorter than 200 ms"
        return cand
    ctx = cal.resolve(context) if cal else context
    if align:
        y, cand["align_db"], cand["lufs_raw"] = align_loudness(y, cal, ctx)
    else:
        cand["lufs_raw"] = ears.loudness_array(y, SR)["lufs"]
    rep = ears.analyze_array(y, SR, loud=ears.loudness_array(y, SR))
    flat = calibrate.flatten(rep)

    zs, per = [], {}
    for k in LOOP_METRICS:
        if k not in flat or not cal:
            continue
        # `Calibration.z` returns 0.0 when it has no stat for a key, which would
        # enter the median as a perfect match. Check for the stat first.
        if cal.stat(ctx, k) is None:
            continue
        z = cal.z(ctx, k, flat[k])
        if np.isfinite(z):
            per[k] = round(float(z), 2)
            zs.append(abs(float(z)))
    cand["preview_s"] = round(len(y) / SR, 3)
    cand["context"] = ctx
    cand["z"] = per
    cand["median_abs_z"] = round(float(np.median(zs)), 3) if zs else None
    cand["n_outside"] = sum(1 for v in per.values() if abs(v) >= 2.5)
    cand["outside_axes"] = [k for k, v in per.items() if abs(v) >= 2.5]

    # Tempo: the catalogue BPM is the ground truth here, so this is a check on
    # the loop, not on the detector. A disagreement usually means the loop is
    # half/double-time against its label or its pulse is ambiguous — and note
    # that this kit already has a documented 4:3 alias (off-8th hats reading as
    # 178 against a real 134), so a mismatch is a flag to look at, not a fail.
    tempo = rep.get("pulse", {}).get("tempo")
    cand["detected_tempo"] = round(float(tempo), 1) if tempo else None
    if tempo and cand.get("bpm"):
        r = float(tempo) / float(cand["bpm"])
        cand["tempo_ratio"] = round(r, 3)
        # Named aliases rather than a pass/fail. On seven percussion loops all
        # labelled 134 BPM the detector returned 178.2 (the 4:3 alias this kit
        # already knows about, from hits on off-8ths) or 107.7 (4:5), and a flag
        # that fires on 7 of 7 is one nobody reads. The bar count below is the
        # trustworthy check: it comes from duration and the label, not from beat
        # tracking, and it read 1.01 / 2.01 / 4.00 bars for these same loops.
        aliases = {0.5: "half-time", 0.75: "3:4", 0.8: "4:5", 1.0: "matches",
                   1.25: "5:4", 4 / 3: "4:3", 1.5: "3:2", 2.0: "double-time"}
        near = [name for m, name in aliases.items() if abs(r - m) < 0.04]
        cand["tempo_alias"] = near[0] if near else None
    onsets = librosa.onset.onset_detect(y=y, sr=SR, units="time",
                                        backtrack=True)
    cand["onsets"] = int(len(onsets))
    cand["seam_pct"] = seam_percentile(y)
    if cand.get("bpm"):
        bars = (len(y) / SR) / (4 * 60.0 / float(cand["bpm"]))
        cand["preview_bars"] = round(bars, 2)
        # Does the label survive arithmetic? A loop whose length is not a clean
        # bar count at its stated BPM is either mislabelled or not a loop, and
        # that is worth knowing before it goes into a Simpler at that tempo.
        cand["bars_ok"] = any(abs(bars - m) < 0.06
                              for m in (0.5, 1, 2, 3, 4, 6, 8, 12, 16))
    cand["rank_key"] = (cand["median_abs_z"]
                        if cand["median_abs_z"] is not None else float("inf"))
    return cand


def flag_truncation(cand):
    """Preview length vs the catalogue, which is how a halved loop announces
    itself. 0.9 rather than 1.0 because MP3 framing and silence trimming move
    the last few milliseconds around."""
    cs, ps = cand.get("catalog_s"), cand.get("preview_s")
    if not cs or not ps:
        return
    frac = ps / cs
    cand["preview_fraction"] = round(frac, 3)
    if frac < 0.9:
        cand["truncated"] = True


# ------------------------------------------------------------------ controls
#
# METHOD RULE (learned the hard way on 2026-08-16, when a "sub collision"
# detector flagged a render, looked compelling, then flagged 15/19 real
# Drumcode excerpts harder and turned out to be reading FFT bin spacing):
# no number this tool prints is a finding until it has been run over the
# reference corpus as a control. There are two new things to control for here.

def _norm_name(stem):
    """Filename down to its letters and digits.

    Local copies do not always keep the catalogue's name: the bought
    `RU_TD_closed_hat_analog_low.wav` is `RU_TD_drums_closed_hat_analog_low.wav`
    upstream. Normalising and then testing containment both ways catches that
    without inventing fuzzy matches between genuinely different samples.
    """
    return re.sub(r"[^a-z0-9]", "", stem.lower())


def _tokens(stem):
    return {t for t in re.split(r"[^a-z0-9]+", stem.lower()) if t}


def _match_bought(catalog_name, have):
    """Bought file for a catalogue name, or None if it is not unambiguous.

    Containment on the normalised string is not enough: the local
    `RU_TD_closed_hat_analog_low` differs from the catalogue's
    `RU_TD_drums_closed_hat_analog_low` in the MIDDLE, so neither string
    contains the other. Token subset handles it, and requiring a unique match
    keeps it from silently pairing two samples from the same pack.
    """
    stem = pathlib.Path(catalog_name).stem
    key = _norm_name(stem)
    if key in have:
        return have[key]
    ct = _tokens(stem)
    hits = []
    for k, p in have.items():
        if len(k) > 8 and (k in key or key in k):
            hits.append(p)
            continue
        bt = _tokens(p.stem)
        if len(bt & ct) >= 3 and (bt <= ct or ct <= bt):
            hits.append(p)
    uniq = {str(p): p for p in hits}
    return next(iter(uniq.values())) if len(uniq) == 1 else None


def control_preview(cands, bought_dir, role, bank, refetch=False):
    """Does the preview give the same verdict as the WAV you would have bought?

    This is the question the whole tool rests on, and it can be answered
    exactly rather than by proxy, because 14 Splice sources were already bought
    for Phase 3 and are sitting in the User Library. Pair each bought WAV with
    its own preview, profile both, and the delta is the ENTIRE cost of
    auditioning early: lossy codec, whatever length Splice serves, and any
    processing they apply to previews, all in one number.

    (A synthetic control was the first design — encode a WAV to 128 kbps and
    back. It was dropped because this machine has no MP3 encoder: no lame, no
    ffmpeg, and macOS `afconvert` decodes MP3 but will not write it. Pairing
    real files is the better experiment anyway, since it also catches
    truncation and any preview-side normalisation, which a local round trip
    cannot see.)

    Pass search markdown covering the bought names on stdin; matching is by
    filename stem, case-insensitive.
    """
    bought_dir = pathlib.Path(bought_dir).expanduser()
    files = sorted(bought_dir.glob("*.wav"))
    if not files:
        print(f"no WAVs in {bought_dir}")
        return []
    have = {_norm_name(p.stem): p for p in files}

    rows, dz = [], {}
    for c in cands:
        p = _match_bought(c["name"], have)
        if p is None:
            continue
        acquire(c, refetch=refetch)
        if not c.get("wav"):
            print(f"  no preview for {c['name']}: {c.get('error')}",
                  file=sys.stderr)
            continue
        a = oneshot_bank.profile(str(p), bank, role=role, verbose=False)
        b = oneshot_bank.profile(c["wav"], bank, role=role, verbose=False)
        if a.get("oddity") is None or b.get("oddity") is None:
            # Do not drop these silently. The 0.1 s hat is the reason: its
            # preview is 5.5 ms of audio, and a pair vanishing without a word
            # is how a control quietly stops controlling anything.
            why = (b.get("error") or a.get("error")
                   or "no oddity (role not in bank?)")
            print(f"  SKIPPED {p.name}: {why}"
                  f"  (preview {b.get('duration_s') or '?'} s)")
            continue
        rows.append({"name": p.name, "role": role,
                     "bought_s": a.get("duration_s"),
                     "preview_s": b.get("duration_s"),
                     "bought_oddity": a["oddity"], "preview_oddity": b["oddity"],
                     "d_oddity": round(b["oddity"] - a["oddity"], 3),
                     "bought_out": a.get("n_outside", 0),
                     "preview_out": b.get("n_outside", 0),
                     "bought_verdict": a.get("verdict", "")[:28],
                     "preview_verdict": b.get("verdict", "")[:28]})
        # Per-feature drift is the useful part: it says WHICH axes a preview
        # cannot be trusted on, instead of leaving it to a guess about which
        # ones "feel" tail-sensitive.
        za, zb = a.get("z", {}), b.get("z", {})
        for k in set(za) & set(zb):
            dz.setdefault(k, []).append(zb[k] - za[k])

    if not rows:
        print("no bought/preview pairs matched — check that the search markdown "
              "covers\nthe filenames in " + str(bought_dir))
        return rows

    d = np.array([r["d_oddity"] for r in rows])
    print(f"\npreview control — {len(rows)} samples that were actually bought, "
          f"role={role}")
    print(f"{'file':40s}{'bought':>8s}{'preview':>8s}{'delta':>8s}"
          f"{'out':>8s}{'len s':>12s}")
    for r in rows:
        outs = f"{r['bought_out']}->{r['preview_out']}"
        lens = f"{r['bought_s']:.2f}->{r['preview_s']:.2f}"
        print(f"{r['name'][:39]:40s}{r['bought_oddity']:>8.2f}"
              f"{r['preview_oddity']:>8.2f}{r['d_oddity']:>+8.2f}"
              f"{outs:>8s}{lens:>12s}")
    same = sum(1 for r in rows
               if r["bought_verdict"] == r["preview_verdict"])
    print(f"\nmedian |delta oddity| = {np.median(np.abs(d)):.3f}   "
          f"worst = {d[np.argmax(np.abs(d))]:+.3f}")
    print(f"same verdict string: {same}/{len(rows)}")

    if dz:
        print("\nper-feature drift, preview minus bought, in sigma "
              "(the axes to distrust):")
        order = sorted(dz.items(),
                       key=lambda kv: -float(np.median(np.abs(kv[1]))))
        for k, vals in order:
            v = np.array(vals, dtype=float)
            bias = float(np.median(v))
            print(f"  {k:22s}median {bias:+6.2f}   "
                  f"|median| {float(np.median(np.abs(v))):5.2f}   "
                  f"n={len(v)}")
        worst = [k for k, vals in order
                 if float(np.median(np.abs(vals))) >= 1.0]
        if worst:
            print("  distrust on a preview (>= 1 sigma of drift): "
                  + ", ".join(worst))
            print("  set AUDITION_UNSAFE to these if the list has changed.")
    print("Read the delta against the spread of the candidates being ranked. "
          "If your top\nand fifth pick sit closer together than this number, "
          "the preview cannot separate\nthem — shortlist several and judge the "
          "bought WAVs.")
    return rows


def control_loop(context, cal, limit=18):
    """What does a REAL record score on the loop path?

    `median_abs_z` is meaningless until this runs. The reference excerpts are
    the same 60 s windows `calibrate build` measured, so they should score near
    zero by construction — this is a sanity check on the plumbing (alignment,
    key names, context resolution), and it establishes the p90 that makes a
    candidate's 1.8 readable as good or bad.
    """
    excerpts = sorted(calibrate.EXCERPT_DIR.glob("*__*s_*s.wav"))[:limit]
    if not excerpts:
        print(f"no reference excerpts in {calibrate.EXCERPT_DIR} — run "
              f"`calibrate.py build` first")
        return []
    rows = []
    for p in excerpts:
        c = {"name": p.name, "wav": str(p)}
        measure_loop(c, context, cal)
        if c.get("median_abs_z") is not None:
            rows.append(c)
    if not rows:
        return rows
    vals = np.array([r["median_abs_z"] for r in rows])
    outs = np.array([r["n_outside"] for r in rows])
    print(f"\nloop control — {len(rows)} reference excerpts as context "
          f"'{cal.resolve(context) if cal else context}'")
    for r in rows:
        print(f"  {r['name'][:52]:54s}med|z| {r['median_abs_z']:>5.2f}"
              f"   out {r['n_outside']}   align {r.get('align_db', 0):+.1f} dB")
    print(f"\nreal records score: median {np.median(vals):.2f}, "
          f"p90 {np.percentile(vals, 90):.2f}, worst {vals.max():.2f}")
    print(f"axes outside: median {np.median(outs):.0f}, "
          f"worst {outs.max():.0f}")
    print("A candidate is only 'off' relative to these numbers, never on its "
          "own.")
    return rows


# ------------------------------------------------------------------- picture

def ab_figure(bought, cand, out_path):
    """Bought WAV over its own preview, plus how well they line up.

    This is the diagnostic that corrected this tool's own premise. Plattenbau's
    bought WAV is a 2.11 s kick with a transient at 0 ms reaching 14 kHz; its
    preview is 1.06 s, onset at 42 ms, with nothing above ~2 kHz. Best
    normalised cross-correlation is 0.44 at a 68 ms offset, and 0.11 against
    the head of the file — so the preview is NOT the first half of the sample.
    Run this before trusting a preview on any new role.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import librosa
    import spectro

    yb, _ = librosa.load(str(bought), sr=SR, mono=True)
    yp, _ = librosa.load(cand["wav"], sr=SR, mono=True)

    def onset_ms(y):
        env = np.abs(y)
        above = np.nonzero(env > 0.02 * float(env.max()))[0]
        return (int(above[0]) if len(above) else 0) / SR * 1000

    nb, npv = yb / (np.linalg.norm(yb) + 1e-12), yp / (np.linalg.norm(yp) + 1e-12)
    corr = np.correlate(nb, npv, "valid") if len(yb) >= len(yp) else np.array([0.0])
    head = yb[:len(yp)]
    head_corr = float(np.dot(head / (np.linalg.norm(head) + 1e-12), npv))
    stats = {"best_offset_ms": round(float(np.argmax(np.abs(corr))) / (SR / 1000), 1),
             "best_corr": round(float(np.max(np.abs(corr))), 3),
             "head_corr": round(head_corr, 3),
             "bought_s": round(len(yb) / SR, 3), "preview_s": round(len(yp) / SR, 3),
             "bought_onset_ms": round(onset_ms(yb), 1),
             "preview_onset_ms": round(onset_ms(yp), 1)}

    fig, axes = plt.subplots(2, 1, figsize=(11, 5.5))
    fig.patch.set_facecolor("#101014")
    for ax, (y, lab) in zip(axes, [(yb, f"BOUGHT {stats['bought_s']:.2f}s "
                                       f"onset {stats['bought_onset_ms']:.0f}ms"),
                                   (yp, f"PREVIEW {stats['preview_s']:.2f}s "
                                        f"onset {stats['preview_onset_ms']:.0f}ms")]):
        spectro._draw_mel(ax, spectro._mel(y, SR), SR, len(y) / SR)
        spectro._style_ax(ax)
        ax.set_title(lab, color="#d8d8e0", fontsize=9)
    fig.suptitle(f"{pathlib.Path(bought).name}   best corr "
                 f"{stats['best_corr']:.2f} at {stats['best_offset_ms']:.0f} ms, "
                 f"vs head {stats['head_corr']:.2f}",
                 color="#f0f0f4", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    return stats


def contact_sheet(cands, out_path, title):
    """One PNG, one mel spectrogram per candidate.

    This is the half of the tool that is not a number. Claude cannot hear a
    preview, but it can read a spectrogram, and twelve of them side by side in
    one image is one image-read instead of twelve.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import spectro

    keep = [c for c in cands if c.get("wav") and not c.get("error")]
    if not keep:
        return None
    import librosa
    cols = 3 if len(keep) > 4 else min(len(keep), 2)
    rows = int(np.ceil(len(keep) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 2.5 * rows),
                             squeeze=False)
    fig.patch.set_facecolor("#101014")
    for i, ax in enumerate(axes.flat):
        if i >= len(keep):
            ax.axis("off")
            continue
        c = keep[i]
        y, _ = librosa.load(c["wav"], sr=SR, mono=True)
        dur = len(y) / SR
        M = spectro._mel(y, SR)
        spectro._draw_mel(ax, M, SR, dur)
        spectro._style_ax(ax)
        score = c.get("oddity", c.get("median_abs_z"))
        head = f"{i + 1}. {c['name'][:38]}"
        sub = (f"{dur:.2f}s  score {score:.2f}" if score is not None
               else f"{dur:.2f}s")
        if c.get("truncated"):
            sub += "  [half]"
        if c.get("n_outside"):
            sub += f"  {c['n_outside']} axes out"
        ax.set_title(f"{head}\n{sub}", color="#d8d8e0", fontsize=7.5, pad=4)
    fig.suptitle(title, color="#f0f0f4", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


# -------------------------------------------------------------------- report

def render_table(cands, role, loop, prefer):
    L = []
    ok = [c for c in cands if not c.get("error")]
    bad = [c for c in cands if c.get("error")]

    if loop:
        L.append(f"{'#':>2} {'candidate':40s}{'med|z|':>7s}{'out':>4s}"
                 f"{'bars':>6s}{'tempo':>7s}{'':2s}{'notes'}")
        for i, c in enumerate(ok, 1):
            mz = c.get("median_abs_z")
            notes = []
            if c.get("truncated"):
                notes.append(f"half ({c['preview_s']:.1f}/{c['catalog_s']:.1f}s)")
            if c.get("bars_ok") is False:
                notes.append(f"NOT a clean bar count at {c.get('bpm')} BPM "
                             f"({c.get('preview_bars')} bars)")
            elif c.get("tempo_alias") and c["tempo_alias"] != "matches":
                notes.append(f"pulse reads {c['tempo_alias']}")
            if (c.get("seam_pct") or 0) >= 90:
                notes.append(f"seam at midpoint (p{c['seam_pct']:.0f})")
            if c.get("outside_axes"):
                notes.append("out: " + ",".join(
                    a.split(".")[-1] for a in c["outside_axes"][:4]))
            bars = c.get("preview_bars")
            tempo = c.get("detected_tempo")
            L.append(f"{i:>2} {c['name'][:39]:40s}"
                     f"{(f'{mz:.2f}' if mz is not None else '-'):>7s}"
                     f"{c.get('n_outside', 0):>4d}"
                     f"{(f'{bars:.2f}' if bars else '-'):>6s}"
                     f"{(f'{tempo:.0f}' if tempo else '-'):>7s}"
                     f"  {'; '.join(notes)}")
    else:
        L.append(f"{'#':>2} {'candidate':38s}{'stable':>7s}{'full':>6s}"
                 f"{'>refs':>7s}{'out':>4s}{'role?':>7s}  "
                 f"{'axes outside (* = preview-stable)'}")
        for i, c in enumerate(ok, 1):
            od, so = c.get("oddity"), c.get("stable_oddity")
            pct = c.get("oddity_percentile")
            # oneshot_bank stores the candidate's PERCENTILE among reference
            # hits, so the share of real hits further out is 100 - pct.
            further = None if pct is None else max(0.0, 100.0 - float(pct))
            axes = [(a.split(".")[-1] + ("*" if a in AUDITION_STABLE else ""))
                    for a in c.get("outside_axes", [])[:5]]
            auto = c.get("auto_role", "?")
            mark = "" if auto == role else f"->{auto}"
            note = ",".join(axes) or (c.get("verdict", "")[:38])
            if c.get("truncated"):
                note = f"[half] {note}"
            L.append(f"{i:>2} {c['name'][:37]:38s}"
                     f"{(f'{so:.2f}' if so is not None else '-'):>7s}"
                     f"{(f'{od:.2f}' if od is not None else '-'):>6s}"
                     f"{(f'{further:.0f}%' if further is not None else '-'):>7s}"
                     f"{c.get('n_outside', 0):>4d}"
                     f"{(role + mark):>7s}  {note}")

    if bad:
        L.append("")
        L.append("could not audition:")
        for c in bad:
            L.append(f"   {c['name'][:50]:52s}{c['error']}")
    return "\n".join(L)


def footer(cands, loop, prefer, dropped=()):
    ok = [c for c in cands if not c.get("error")]
    L = ["", "how to read this"]
    if loop:
        L.append("  med|z|  median |z| over tonal balance, crest, pulse and "
                 "transient density")
        L.append("          vs the calibration corpus for this context, after "
                 "gain-matching to it.")
        L.append(f"          Real records through this same path score "
                 f"{LOOP_REF['mix'][0]:.2f} median / "
                 f"{LOOP_REF['mix'][1]:.2f} p90 in")
        L.append(f"          'mix' and {LOOP_REF['drums'][0]:.2f} / "
                 f"{LOOP_REF['drums'][1]:.2f} in 'drums' "
                 f"(--control=loop). Below ~1.6 is")
        L.append("          indistinguishable from a real record on these "
                 "axes; 4+ is not close.")
        L.append("  bars    preview length in bars at the labelled BPM. This "
                 "is the trustworthy")
        L.append("          tempo check; the `tempo` column is a beat tracker "
                 "and it aliases.")
    else:
        L.append("  stable  mean |z| over the four features a preview "
                 "preserves: peak_hz,")
        L.append("          centroid_hz, share.high, share.air. The ranking "
                 "column — see the")
        L.append("          discrimination block for whether it earned the "
                 "right to rank.")
        L.append("  full    oddity over all ten core features. Includes "
                 "crest and noisiness,")
        L.append("          which a preview shifts 6-8 sigma, so read it as "
                 "context not verdict.")
        L.append("          Held-out reference hits score ~0.72 median, 1.48 "
                 "at p90 on `full`.")
        L.append("  >refs   share of real reference hits sitting FURTHER from "
                 "the corpus centre")
        L.append("          than this candidate. 2% = only 2 in 100 real hits "
                 "are this unusual.")
    L.append("  out     axes >= 2.5 sigma outside. One number cannot say "
             "'typical overall'")
    L.append("          and 'extreme on the two axes that define it', so both "
             "print.")
    L.append(f"  ranked  {'least' if prefer == 'typical' else 'MOST'} typical "
             f"first (--prefer={prefer}).")
    L.append("")
    L.append("what a preview cannot tell you (measured, --control=preview)")
    L.append("  * previews arrive at HALF the catalogue length, one-shots and "
             "loops alike.")
    L.append("    Nothing here can see the back half of any sample.")
    if loop:
        n_seam = sum(1 for c in ok if (c.get("seam_pct") or 0) >= 90)
        if n_seam:
            L.append(f"  * {n_seam} of {len(ok)} previews put their biggest "
                     f"spectral jump at their own")
            L.append("    midpoint: the preview is two segments joined, so the "
                     "pattern across the")
            L.append("    seam is not the sample's arrangement. Judge timbre "
                     "here, not groove.")
    L.append("  * the codec moves crest by ~+6.5 sigma and noisiness by ~-7.7 "
             "sigma, and the")
    L.append("    whole-sample verdict changed on 3 of 3 controlled kicks. "
             "Never quote those")
    L.append("    axes from a preview — that is what the `stable` column "
             "exists to avoid.")
    L.append("  * measured noise floor on `full` oddity is ~0.37, so "
             "candidates inside 0.4")
    L.append("    of each other are not distinguishable here. Shortlist them "
             "and let the")
    L.append("    bought WAVs and your ears decide.")
    if not loop and len(ok) > 1:
        spread = [c.get("stable_oddity") for c in ok
                  if c.get("stable_oddity") is not None]
        if len(spread) > 1:
            L.append(f"  * this run's `stable` spread: {min(spread):.2f} to "
                     f"{max(spread):.2f}"
                     + ("  — wide enough to choose on."
                        if max(spread) - min(spread) > 0.8 else
                        "  — TIGHT. Treat as one group, not a ranking."))
        disc = discrimination(ok)
        if disc:
            L.append("")
            if dropped:
                L.append("features dropped as uninformative for this role:")
                for k, why in dropped:
                    L.append(f"  {k:16s}{why}")
            L.append("what is actually separating these candidates")
            for k, sp, n in disc:
                bar = "#" * min(28, int(sp * 6))
                L.append(f"  {k:16s}spread {sp:5.2f} sigma over "
                         f"{n:2d} distinct values  {bar}")
            # An axis needs spread AND more than a couple of distinct values to
            # count as separating anything: `peak_hz` reads 1.27 sigma of
            # spread on the kick probe while taking exactly two values, because
            # it is quantised to FFT bins. Two values do not order ten samples.
            live = [k for k, sp, n in disc if sp >= 0.3 and n >= 3]
            if len(live) <= 1:
                only = live[0] if live else "nothing"
                L.append(f"  WARNING: the order above rests on {only} alone; "
                         f"the other axes are flat")
                L.append(f"  across this shortlist. That is one measurement, "
                         f"and if it is centroid_hz")
                L.append(f"  it is also the stable axis with the most preview "
                         f"drift. Read the")
                L.append(f"  spectrograms and treat the ranking as a hint.")
    if ok:
        top = ok[0]
        L.append("")
        L.append("to buy the top pick:")
        uuid = top.get("uuid")
        if uuid:
            L.append(f"  mcp__splice__download_asset  asset_uuid={uuid}")
            L.append(f"  # {top['name']}")
        else:
            L.append(f"  # {top['name']} — no UUID was parsed; take it from "
                     f"the search output")
    return "\n".join(L)


# ----------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(
        description="Audition Splice previews before spending a credit.")
    ap.add_argument("pages", nargs="*",
                    help="sample page URLs; omit to read search markdown on stdin")
    ap.add_argument("--role", default=None,
                    help="kick | hat | perc (scored against the one-shot bank)")
    ap.add_argument("--loop", action="store_true",
                    help="score as loops against the calibration corpus")
    ap.add_argument("--context", default="drums",
                    help="loop context: drums | bass | other | mix")
    ap.add_argument("--prefer", default="typical", choices=("typical", "odd"),
                    help="rank most role-typical first, or most extreme first")
    ap.add_argument("--rank", default="stable", choices=("stable", "full"),
                    help="one-shots: rank on the preview-stable features "
                         "(default) or on all core features")
    ap.add_argument("--top", type=int, default=12,
                    help="candidates to draw into the contact sheet")
    ap.add_argument("--limit", type=int, default=0,
                    help="audition only the first N candidates (0 = all)")
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel preview fetches (be gentle, it is a scrape)")
    ap.add_argument("--out", default=None, help="report directory")
    ap.add_argument("--name", default=None, help="label for this audition")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--ab", metavar="WAV",
                    help="A/B a bought WAV against its own preview as one PNG "
                         "(pass the page URL as the only positional)")
    ap.add_argument("--keep-mp3", action="store_true")
    ap.add_argument("--refetch", action="store_true",
                    help="ignore the preview cache")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable results on stdout")
    ap.add_argument("--full", type=int, default=0,
                    help="also print the full per-sample report for the top N")
    ap.add_argument("--no-align", action="store_true",
                    help="loops: do NOT gain-match to the corpus before "
                         "measuring (then tonal z-scores read gain, not tone)")
    ap.add_argument("--control", choices=("preview", "loop"), default=None,
                    help="preview: bought WAV vs its own preview (needs "
                         "--bought-dir). loop: what real records score.")
    ap.add_argument("--bought-dir",
                    default="~/Music/Ableton/User Library/Samples/Splice",
                    help="already-purchased WAVs, for --control=preview")
    a = ap.parse_args()

    if a.ab:
        text = "\n".join(a.pages) if a.pages else sys.stdin.read()
        cands = parse_candidates(text)
        if not cands:
            sys.exit("--ab needs the sample's page URL as a positional")
        c = acquire(cands[0], refetch=a.refetch)
        if not c.get("wav"):
            sys.exit(f"no preview: {c.get('error')}")
        out = pathlib.Path(a.out or OUT_ROOT / "ab") / (
            pathlib.Path(a.ab).stem + "_ab.png")
        st = ab_figure(pathlib.Path(a.ab).expanduser(), c, out)
        for k, v in st.items():
            print(f"  {k:20s}{v}")
        print(f"\nwrote {out}")
        return

    if a.control == "loop":
        cal = calibrate.load()
        if cal is None:
            sys.exit("no calibration.json — run tools/calibrate.py build")
        control_loop(a.context, cal)
        return
    if a.control == "preview":
        if not a.role:
            sys.exit("--control=preview needs --role=kick|hat|perc")
        bank = oneshot_bank.load()
        if bank is None:
            sys.exit("no one-shot bank — run tools/oneshot_bank.py build")
        text = "\n".join(a.pages) if a.pages else sys.stdin.read()
        control_preview(parse_candidates(text), a.bought_dir, a.role, bank,
                        refetch=a.refetch)
        return

    if a.role and a.loop:
        sys.exit("--role scores one-shots and --loop scores loops; pick one")
    if not a.role and not a.loop:
        sys.exit("pass --role=kick|hat|perc for one-shots, or --loop")
    if a.role and a.role not in BANK_ROLES:
        sys.exit(f"--role must be one of {sorted(BANK_ROLES)} — the bank is cut "
                 f"from drum stems and contains nothing else")

    text = "\n".join(a.pages) if a.pages else sys.stdin.read()
    cands = parse_candidates(text)
    if not cands:
        sys.exit("no splice.com/sounds/sample/... links found in the input")
    if a.limit:
        cands = cands[:a.limit]

    label = a.name or (f"{a.role or 'loop'}-{cands[0]['hash'][:8]}")
    out_dir = pathlib.Path(a.out) if a.out else OUT_ROOT / label

    bank = cal = None
    dropped = ()
    if a.role:
        bank = oneshot_bank.load()
        if bank is None:
            sys.exit("no one-shot bank — run:\n"
                     "  .venv-listen/bin/python tools/oneshot_bank.py build")
        if not bank.has(a.role):
            sys.exit(f"the bank has no '{a.role}' — it holds {bank.roles}")
        keep, dropped = usable_stable(bank, a.role)
        if not keep:
            sys.exit(f"no preview-stable feature carries information for "
                     f"'{a.role}' — nothing to rank on")
    else:
        cal = calibrate.load()
        if cal is None:
            print("WARNING: no calibration.json — loops will be measured but "
                  "not scored.\n  build it with: "
                  ".venv-listen/bin/python tools/calibrate.py build\n",
                  file=sys.stderr)

    print(f"auditioning {len(cands)} candidates "
          f"({'loop' if a.loop else a.role})", file=sys.stderr)

    # Network first and in parallel, analysis after and serially: the fetches
    # are latency-bound and the librosa work is CPU-bound, so mixing them just
    # makes both slower.
    with futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        cands = list(pool.map(
            lambda c: acquire(c, keep_mp3=a.keep_mp3, refetch=a.refetch),
            cands))

    got = sum(1 for c in cands if c.get("wav"))
    fresh = sum(1 for c in cands if c.get("cached") is False)
    print(f"previews: {got}/{len(cands)} ({fresh} fetched, {got - fresh} cached)",
          file=sys.stderr)

    for c in cands:
        if not c.get("wav"):
            continue
        try:
            if a.role:
                measure_oneshot(c, a.role, bank, rank_on=a.rank)
            else:
                measure_loop(c, a.context, cal, align=not a.no_align)
            flag_truncation(c)
        except Exception as e:                      # one bad file must not end the run
            c["error"] = f"analysis failed: {type(e).__name__}: {e}"

    ok = [c for c in cands if not c.get("error")]
    ok.sort(key=lambda c: c.get("rank_key", float("inf")),
            reverse=(a.prefer == "odd"))
    ordered = ok + [c for c in cands if c.get("error")]

    sheet = None
    if not a.no_sheet and ok:
        try:
            sheet = contact_sheet(ok[:a.top], out_dir / "contact_sheet.png",
                                  f"{label}  —  {'loop' if a.loop else a.role}"
                                  f", ranked ({a.prefer} first)")
        except Exception as e:
            print(f"contact sheet failed: {type(e).__name__}: {e}",
                  file=sys.stderr)

    table = render_table(ordered, a.role, a.loop, a.prefer)
    text_out = table + "\n" + footer(ordered, a.loop, a.prefer, dropped)

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"label": label, "role": a.role, "loop": a.loop,
               "context": a.context if a.loop else None,
               "prefer": a.prefer, "candidates": ordered,
               "sheet": str(sheet) if sheet else None}
    (out_dir / "audition.json").write_text(json.dumps(payload, indent=1,
                                                      default=str))
    (out_dir / "audition.txt").write_text(text_out)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
    else:
        print(text_out)
        if a.full:
            for c in ok[:a.full]:
                if c.get("report"):
                    print("\n" + "=" * 72 + "\n")
                    print(c["report"])
        print(f"\nwrote {out_dir}/audition.json + audition.txt")
        if sheet:
            print(f"contact sheet: {sheet}   (Read it — the spectrograms are "
                  f"the part that is not a number)")


if __name__ == "__main__":
    main()
