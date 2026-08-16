#!/usr/bin/env python3
"""Band profile of a one-shot — now a thin front end onto `oneshot_bank.py`.

This used to hold a TARGETS dict: hand-written band-share percentages for
"kick", "hat" and "perc" that somebody guessed. Two things were wrong with it.

  1. It could not answer the question it existed for. "Nothing tells me whether
     forged_metal_bell is a good bell" — and a target table with three roles in
     it never could.
  2. The numbers were wrong anyway. The shares were summed linear STFT
     magnitude, which hands wide bands a structural advantage (20-60 Hz is 4
     bins at n_fft=4096, 2-6 kHz is 371). Under that measure a real Drumcode
     kick reads 18.6% sub / 31.7% high; measured as ENERGY it is 74.5% sub /
     2.2% high. The old kick target of "30% sub, 4% high" was fitted to the
     artefact.

`oneshot_bank.py` replaces both: it cuts real kicks, hats and percussion out of
the reference drum stems and reports a candidate as z-scores against them.
Everything below just keeps the old command line working.

    tools/profile_sample.py [--role=kick] sample.wav [more.wav ...]
"""
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import oneshot_bank  # noqa: E402

# Kept so old callers importing BANDS keep working; the live definition of the
# bands is ears.BANDS, which oneshot_bank uses.
import ears  # noqa: E402
BANDS = ears.BANDS


def main():
    role, paths, clap = None, [], False
    for a in sys.argv[1:]:
        if a.startswith("--role="):
            role = a.split("=", 1)[1]
        elif a == "--clap":
            clap = True
        else:
            paths.append(a)
    if not paths:
        sys.exit(__doc__)

    bank = oneshot_bank.load()
    if bank is None:
        sys.exit("no one-shot bank — run:\n"
                 "  .venv-listen/bin/python tools/oneshot_bank.py build")

    ear = None
    if clap:
        import semantic_ear
        ear = semantic_ear.SemanticEar()
        ear = ear if ear.available else None

    for i, p in enumerate(paths):
        if i:
            print("\n" + "=" * 72 + "\n")
        oneshot_bank.profile(p, bank, role=role, clap_ear=ear)


if __name__ == "__main__":
    main()
