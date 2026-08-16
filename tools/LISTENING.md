# The listening loop

`tools/listen.py` is how the composer model hears a render. One command, every
ear, one report directory the model Reads before deciding the next move.

```
.venv-listen/bin/python tools/calibrate.py build              # ONCE, first
.venv-listen/bin/python tools/calibrate.py regroove           # after ANY onset-detector change
.venv-listen/bin/python tools/listen.py "<render.wav|aif>"    # full pass
.venv-listen/bin/python tools/listen.py "<render>" --quick    # DSP only, ~5 s
.venv-listen/bin/python tools/listen.py refs                  # rebuild CLAP ref cache
```

Output: `listen-reports/<name>/report.md` + `report.json` + PNGs.
**The iteration protocol is: render → listen → Read report.md → Read the PNGs
→ decide → change one thing → render again.**

## Build the calibration first

Nothing else is trustworthy without it. `calibrate.py build` runs the whole
pipeline over the reference records and stores what THEY measure, per context
(mix / drums / bass / other), in `reference-audio/calibration.json`. Every
threshold in the report then comes from real music instead of a guess.

Why it matters, in the two failures that motivated it:

- A drums-only render was reported `MUDDY +6.7 dB sub`. It was being compared
  against full commercial masters. `listen.py` now infers what the render IS
  (`calibrate.infer_context`) and judges a drum loop against reference drum
  stems.
- `lowend_control 0.01` looked like a fault worth chasing for weeks. The
  Drumcode masters score **0.07** on that axis themselves. It carries no
  gradient and the report now says so instead of flagging it.

Measured on the 9 Drumcode singles (18 × 60 s windows):

| CLAP axis | mix median [p10..p90] | verdict |
|---|---|---|
| groove | 1.00 [0.98..1.00] | discriminative — a low score is real |
| kick_power | 0.98 [0.91..1.00] | discriminative |
| top_end | 0.48 [0.26..0.79] | discriminative |
| space | 0.11 [0.05..0.40] | weak, low by nature |
| lowend_control | 0.07 [0.02..0.41] | **pinned to the bad pole — ignore** |
| production / energy | 1.00 [1.00..1.00] | **saturated — no gradient** |

Reference crest is **8.4 dB [7.6..11.1]** and LUFS **−7.3 [−8.5..−5.6]**. The
old hand-written "crest 10–14, LUFS −11.5" targets were wrong in both
directions.

## The ears

| ear | tool | what it hears |
|---|---|---|
| mix | `ears.py` | crushed / dark / muddy / congested / kick dominance — thresholds from the corpus, in the render's own context |
| critic | `critic.py` | techno_core, novelty, verdict vs 38 fingerprints |
| semantic | `semantic_ear.py` (CLAP) | quality axes **beside what real records score**, subgenre character, moods, cosine to the reference records |
| groove | `groove_ear.py` | the pattern as a 32-step text grid per role, swing, microtiming |
| groove A/B | `groove_ref.py` | your grid vs the reference grids: per-role F1, which steps you miss, and how much the records agree with **each other** (~0.94 since the kick rows stopped counting bass) so the number is readable |
| harmony | `harmony_ear.py` | key, the notes each stem actually plays, kick tuning, clashes, detuning in cents |
| bar | `bar_ear.py` | per-bar deviation from the loop — localizes "bar 9", which CLAP's 10 s windows cannot |
| structure + visual | `structure_ear.py`, `spectro.py` | section timeline, overview/stems/loop-zoom PNGs |
| one-shot | `oneshot_bank.py` | a forged sample vs the real kicks/hats/perc cut out of the reference drum stems |

## One-shots

```
.venv-listen/bin/python tools/oneshot_bank.py build [--clap]   # ~15 s, +4 min with CLAP
.venv-listen/bin/python tools/oneshot_bank.py show [role]
.venv-listen/bin/python tools/oneshot_bank.py profile [--role=kick] [--clap] a.wav b.wav
```

`build` slices every onset out of the 18 reference drum stems, keeps the ones
whose own band balance agrees with the band that detected them, and stores
median / robust-sigma / p10 / p90 per feature per role — the same shape
`calibrate.py` stores for mixes. 1408 kicks, 797 hats, 1505 perc from 9 records.
`profile_sample.py` is now a front end onto it; its hand-written `TARGETS` are
gone.

The corpus, measured (this is what a Drumcode kick actually is):

| | kick | hat | perc |
|---|---|---|---|
| sub 20-60 Hz | **74.5%** | 0.0% | 0.1% |
| high 6-12k | 2.2% | **57.8%** | 12.5% |
| peak freq | 43 Hz | 6.8 kHz | 191 Hz |
| decay to −20 dB | 221 ms | 34 ms | 81 ms |
| crest | 7.2 dB | 18.8 dB | 14.2 dB |

Note band shares are **power**, not summed magnitude. The old `TARGETS`
("kick = 30% sub, 4% high") were fitted to summed magnitude, which gives wide
bands a structural bin-count advantage; the same kick reads 18.6% sub / 31.7%
high that way. That is why the old targets looked plausible and were wrong.

### What it can and cannot answer

Leave-one-**record**-out control (per excerpt would validate memorisation — two
excerpts of one track share the same kick sample):

| role | n | typicality median | p90 | p99 | axes ≥2.5σ p90 |
|---|---|---|---|---|---|
| kick | 1408 | 0.73 | 1.50 | 6.07 | 4 |
| hat | 797 | 0.81 | 1.47 | 1.83 | 4 |
| perc | 1505 | 0.66 | 1.17 | 2.21 | 5 |

No record is systematically flagged; the widest is the DNA record's kicks.

**Honest limits, all measured:**

- No bell, no duduk, no vocal exists in a drum stem. `--role=bell` returns
  NO REFERENCE DATA and raw numbers, not a score against the nearest bin.
- `perc` is a catch-all and its distribution is huge: the perc test also calls
  **97% of reference HATS** "inside perc". An INSIDE-perc verdict means "not
  obviously broken". The kick test is specific (0% of hats, 0% of percs).
- The DSP layer cannot tell a tonal bell from a tonal tom. `forged_metal_bell`
  scores 0.77 typicality against reference percussion while sitting 4-5σ out on
  noisiness, crest and rolloff — and real percussion hits reach 5 outside axes
  at p90, so neither statistic catches it.
- The CLAP nearest-neighbour score separates "cut from a mastered record" from
  "synthesised here" and nothing finer: **all 14** Forged2 samples fall below
  the reference range, the good ones included. Only the per-prompt deltas carry
  a gradient. CLAP's raw prompt ranking is not readable either — reference
  hi-hats score +0.253 on "a wooden percussion block" and +0.136 on "a hi-hat
  cymbal" — which is exactly why the deltas are calibrated on reference hits.

## Reading the groove grid

```
KICK |X... X... X... X...|X... X... X... X...|
HATS |..X. ..X. ..X. ..X.|..X. ..X. ..X. ..X.|
```
Each char = one 16th, 2 bars folded across the whole render. X strong, x weak,
o intermittent (probability hit), · rare. On the drum stem rows are
KICK/PERC/HATS; on a full-mix fallback they are LOW/MID/HIGH because the
bassline lives in the low band. Upper rows are kick-bleed-suppressed by a
self-calibrating flux-ratio test — trust X, treat isolated · as noise.

The KICK row is a 25-100 Hz band, so a sub bass sits in it. What keeps it a
kick row is `groove_ear.ATTACK_GATE`: a kick lifts that band 4-50x in ~35 ms,
while a sub-bass note and the swell in a kick tail arrive on top of energy
that is already there and lift it under 2.2x. It is a ratio, so it does not
care how loud anything is and it works with no bassline at all. It is only
valid on a **kick channel** — `groove_ear.analyze(..., full_mix=True)` and
`bar_ear.analyze(..., drums=None)` turn it off, because on a mix with a loud
sustained sub there is nothing in 25-100 Hz left to separate kick from bass,
and gating there empties the row instead of cleaning it.

Sanity check: on the reference drum stems the KICK row lands on exactly **8
hits per 2 bars** in 15 of 18 excerpts, at 1.0-2.2 onsets/s. If your
references read busier than that, the onset detector has regressed.

## Method rule

**Run every new metric over the reference corpus as a control before believing
it.** A "sub collision" detector written here flagged a render convincingly,
then flagged 15 of 19 real Drumcode excerpts harder — and its beat frequencies
turned out to be exact multiples of the FFT bin spacing. It was measuring the
analysis window, not the music. It was deleted. Anything that fires on most
real records is a bug, not a finding.

## Environment

- venv: `.venv-listen` (torch, demucs, laion_clap on numpy 2.x — do NOT
  `pip install laion-clap` here, it was installed `--no-deps` deliberately).
- CLAP checkpoint: `.models/music_audioset_epoch_15_esc_90.14.pt` (2.35 GB).
- Stems cache: `.cache/stems/<sha1>/`; reference excerpts `.cache/refexcerpt/`.
- Reference embeddings: `reference-audio/clap_refs.npz` (rebuild via
  `listen.py refs`, then `critic.py build`).
- The calibration and CLAP caches are gitignored: they are derived from
  copyrighted reference audio and are regenerated by `calibrate.py build`.

## Gotchas

- laion_clap pins numpy<2 in metadata but runs fine on numpy 2.5; reinstalling
  it normally will downgrade numpy and break librosa/numba.
- CLAP embeddings of >10 s clips are non-deterministic (random 10 s crop);
  `semantic_ear` always slices exact 10 s windows for reproducibility.
- Demucs always outputs 44.1 kHz regardless of input rate; renders are 48 k.
  It runs on `mps` when available, falling back to cpu.
- CLAP model load is ~40 s per process — batch listens in one process when
  scoring many renders.
- Any groove reference grid built before the `ROLE_GATE` prominence fix or the
  `ATTACK_GATE` kick/bass fix is invalid (kick rows were ~3× too busy). The
  stored grids ARE the old detector's output, so a new detector gets diffed
  against an old ruler. **Every change to the onset detector must be followed
  by `calibrate.py regroove`** — it rebuilds only `groove_refs` off the cached
  excerpts and stems in seconds, instead of the tens of minutes `build` spends
  re-running CLAP.
