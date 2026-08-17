#!/usr/bin/env python3
"""Producer ear — a model that actually hears the render, used the only way it
proved trustworthy: A/B against a real record.

Why this is comparative and not "give me feedback"
--------------------------------------------------
Every other ear in this repo is DSP: it measures the signal and cannot form an
opinion. A multimodal model can hear, so the obvious move is to hand it a
render and ask what is wrong. Measured 2026-08-17, that does not work.

Asked absolute questions about our own renders, with ground truth we had
already measured:

    question              truth              gemini-3.7-flash   gemini-2.5-pro
    tempo                 133 BPM            110 / 140          138 / 128
    kick first enters     3.6 s              "0 s"              -
    kick stops at         21.7 s             "no, continuous"   -
    bass subdivision      offbeat 8ths       "16ths"            -
    top end               air -40.6 dB       "bright and crisp" 3/10 (right)

gemini-3.1-pro-preview called that same -40.6 dB render "8/10, bright,
piercing" at 200 BPM. The arrangement answers came back INVERTED: it denied
the breakdown in the track that has one and invented one in the track that is
thirteen voices flat for sixteen bars. Audio genuinely arrives (the usage
block bills ~744 audio tokens) — the perception is just not reliable enough
to steer by, and it is expressed in fluent, confident production prose that
looks exactly like real feedback.

Paired comparison, same models, same clips, with the position swapped to catch
a model that simply always answers "A":

    which clip is brighter?          2.5-pro 2/2      flash 2/2
    which is the commercial record?  2.5-pro 2/2      flash 1/2 (always "A")

So: gemini-2.5-pro, comparative, position-randomised, is a real signal.
Anything absolute is not, and `--absolute` exists only to re-run that
demonstration rather than to be used.

What it reports
---------------
    identified   how many trials picked the Drumcode record as the professional
                 one. n/n means we are still obviously amateur; n/2 means the
                 model cannot tell, which is the win condition.
    giveaways    the reason it gave each time it picked correctly. This is the
                 actionable half — "the giveaway is X" is a note, where a
                 1-10 score is not.

Usage
-----
    tools/producer_ear.py <render.wav> [--trials 6] [--model ...]
    tools/producer_ear.py <render.wav> --brief          # one-line verdict
    tools/producer_ear.py --validate                    # re-run the controls
    tools/producer_ear.py <a.wav> --vs <b.wav>          # our own A/B
"""
import argparse
import base64
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
REF_EXCERPTS = REPO / ".cache" / "refexcerpt"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# 2.5-pro is the one that survived the position-swapped control. flash is
# cheaper and passed brightness but showed position bias on the harder
# question, so it is not the default.
DEFAULT_MODEL = "google/gemini-2.5-pro"
KEY_FILES = [
    pathlib.Path.home() / "Developer/github/endcap/.env",
    REPO / ".env",
]


def api_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for f in KEY_FILES:
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if line.strip().startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no OPENROUTER_API_KEY in env or " + ", ".join(str(f) for f in KEY_FILES))


def to_wav16(src, dst, seconds=None):
    """16-bit stereo WAV. The API path takes wav or mp3, and afconvert is the
    only encoder guaranteed present on macOS."""
    cmd = ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@44100", str(src), str(dst)]
    subprocess.run(cmd, capture_output=True, check=True)
    return dst


def clip_b64(path, cache={}):
    p = str(path)
    if p not in cache:
        tmp = pathlib.Path(tempfile.gettempdir()) / f"pe_{abs(hash(p))}.wav"
        if not tmp.exists():
            to_wav16(path, tmp)
        cache[p] = base64.b64encode(tmp.read_bytes()).decode()
    return cache[p]


def ask(model, key, parts, timeout=300):
    body = {"model": model, "messages": [{"role": "user", "content": parts}]}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    msg = r["choices"][0]["message"]["content"].strip()
    return msg, r.get("usage", {}).get("cost")


def audio_part(path):
    return {"type": "input_audio",
            "input_audio": {"data": clip_b64(path), "format": "wav"}}


PRO_QUESTION = (
    "You are a world-class techno producer and mix engineer. One of these two "
    "clips is a commercially released techno record; the other is an amateur "
    "work in progress. Reply in exactly two lines:\n"
    "LINE 1: 'A' or 'B' — which is the commercial release.\n"
    "LINE 2: the single most obvious thing that gives the amateur one away, "
    "stated as a specific fault a producer would fix (name the element and the "
    "problem, e.g. 'the clap is 6dB too loud and has no room around it'). Do "
    "not hedge and do not list more than one thing.")


def reference_clips():
    refs = sorted(REF_EXCERPTS.glob("*__*.wav"))
    if not refs:
        sys.exit(f"no reference excerpts in {REF_EXCERPTS} — run calibrate.py build")
    return refs


def trial(model, key, ours, ref, ours_first):
    a, b = (ours, ref) if ours_first else (ref, ours)
    parts = [{"type": "text", "text": "CLIP A:"}, audio_part(a),
             {"type": "text", "text": "CLIP B:"}, audio_part(b),
             {"type": "text", "text": PRO_QUESTION}]
    msg, cost = ask(model, key, parts)
    if msg is None:
        return None, cost, None
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    pick = ""
    for ch in lines[0].upper() if lines else "":
        if ch in "AB":
            pick = ch
            break
    reason = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
    # the model picked the REFERENCE = it can still tell us apart
    caught = (pick == "B") if ours_first else (pick == "A")
    return caught, cost, reason


def judge(render, trials=6, model=DEFAULT_MODEL, verbose=True):
    key = api_key()
    refs = reference_clips()
    rng = random.Random(0xBEEF)
    picks, reasons, spend, failed = [], [], 0.0, 0
    for i in range(trials):
        ref = refs[i % len(refs)] if trials <= len(refs) else rng.choice(refs)
        ours_first = (i % 2 == 0)          # swap position every trial
        caught, cost, reason = trial(model, key, render, ref, ours_first)
        spend += cost or 0.0
        if caught is None:
            failed += 1
            if verbose:
                print(f"  trial {i+1}: FAILED ({cost})")
            continue
        picks.append(caught)
        if caught and reason:
            reasons.append(reason)
        if verbose:
            mark = "caught" if caught else "FOOLED"
            print(f"  trial {i+1} ({'ours=A' if ours_first else 'ours=B'}, "
                  f"vs {ref.name[:26]}): {mark}")
            if reason:
                print(f"      {reason[:150]}")
    n = len(picks)
    return {"render": str(render), "model": model, "trials": n, "failed": failed,
            "identified_as_amateur": sum(picks),
            "fooled": n - sum(picks), "cost_usd": round(spend, 4),
            "giveaways": reasons}


def render_verdict(res):
    n, k = res["trials"], res["identified_as_amateur"]
    if n == 0:
        return "producer ear: every trial failed"
    L = [f"producer ear ({res['model']}, {n} trials, "
         f"position swapped, ${res['cost_usd']}):",
         f"  identified as the amateur track {k} of {n} times."]
    if k == n:
        L.append("  Still unmistakable. The giveaways below are the work list.")
    elif k <= n / 2:
        L.append("  It can no longer reliably tell this from a released record. "
                 "That is the win condition — treat the remaining notes as taste.")
    else:
        L.append("  Mostly still identifiable, but not every time.")
    if res["giveaways"]:
        L.append("  what gave it away:")
        for g in res["giveaways"]:
            L.append(f"    - {g}")
    return "\n".join(L)


def validate(model=DEFAULT_MODEL):
    """Re-run the controls that decided this tool's design.

    Two clips with known ground truth, each asked in both orders. A model that
    always answers 'A' scores 1/2 and is caught here rather than in a report.
    """
    key = api_key()
    renders = REPO / "output" / "renders"
    dark, bright = renders / "v3a_iter1_BROKEN.wav", renders / "v5a_final.wav"
    if not (dark.exists() and bright.exists()):
        sys.exit("validation needs v3a_iter1_BROKEN.wav and v5a_final.wav")
    q = ("Which clip has MORE high-frequency content (hats, cymbals, air)? "
         "Answer 'A' or 'B' then five words.")
    print(f"control 1 — brightness (truth: {bright.name} is +15.8 dB of air)")
    ok = 0
    for first, label in ((dark, "dark=A"), (bright, "bright=A")):
        second = bright if first is dark else dark
        parts = [{"type": "text", "text": "CLIP A:"}, audio_part(first),
                 {"type": "text", "text": "CLIP B:"}, audio_part(second),
                 {"type": "text", "text": q}]
        msg, _ = ask(model, key, parts)
        pick = next((c for c in (msg or "").upper() if c in "AB"), "?")
        want = "B" if first is dark else "A"
        ok += pick == want
        print(f"  {label}: said {pick}, wanted {want}  {'ok' if pick == want else 'WRONG'}")
    print(f"\ncontrol 2 — pro vs amateur, both orders")
    ref = reference_clips()[0]
    c2 = 0
    for ours_first in (True, False):
        caught, _, reason = trial(model, key, bright, ref, ours_first)
        c2 += bool(caught)
        print(f"  ours={'A' if ours_first else 'B'}: "
              f"{'ok' if caught else 'WRONG (picked ours as the record)'}")
        if reason:
            print(f"      {reason[:120]}")
    print(f"\nbrightness {ok}/2 · pro-vs-amateur {c2}/2")
    if ok + c2 < 4:
        print("NOT SAFE TO STEER BY. A model that fails a position-swapped "
              "control is answering from priors, not from the audio.")
    else:
        print("Both controls pass in both orders — comparative use is sound. "
              "Absolute questions are still unreliable; see the docstring.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render", nargs="?")
    ap.add_argument("--vs", default=None, help="A/B two of our own renders")
    ap.add_argument("--trials", type=int, default=6)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.validate:
        validate(a.model)
        return
    if not a.render:
        sys.exit("give a render, or --validate")
    if a.vs:
        key = api_key()
        q = ("Both clips are works in progress by the same producer, B is the "
             "newer revision. Reply in two lines: LINE 1 'A' or 'B' — which is "
             "the better record. LINE 2 — the one thing the worse one does "
             "wrong that the better one fixes.")
        parts = [{"type": "text", "text": "CLIP A:"}, audio_part(a.render),
                 {"type": "text", "text": "CLIP B:"}, audio_part(a.vs),
                 {"type": "text", "text": q}]
        msg, cost = ask(a.model, key, parts)
        print(msg or f"failed: {cost}")
        return

    res = judge(a.render, trials=a.trials, model=a.model, verbose=not a.brief)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print()
        print(render_verdict(res))


if __name__ == "__main__":
    main()
