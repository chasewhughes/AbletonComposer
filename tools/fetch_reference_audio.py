#!/usr/bin/env python3
"""Fetch reference audio for style fingerprinting.

Pulls official 30s iTunes preview clips (legal, public API) for a curated
set of techno tracks chosen to span distinct corners of the genre map --
minimal, industrial, Detroit, hypnotic, peak-time, broken. The point is a
MAP of existing techno, not a single target cluster: genre invention needs
to know where "occupied territory" is in feature space.

Usage: python3 tools/fetch_reference_audio.py
Output: reference-audio/previews/<slug>.m4a + manifest.json
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

# (search term, corner of the map it represents)
TRACKS = [
    ("Plastikman Spastik", "minimal-hypnotic"),
    ("Plastikman Consumed", "minimal-deep"),
    ("Richie Hawtin Minus Orange", "minimal"),
    ("Amelie Lens Higher", "peak-time-driving"),
    ("Amelie Lens In My Mind", "peak-time-driving"),
    ("Charlotte de Witte Doppler", "peak-time-dark"),
    ("Robert Hood Minimal Nation", "minimal-detroit"),
    ("Jeff Mills The Bells", "detroit-classic"),
    ("Surgeon Badger Bite", "birmingham-industrial"),
    ("Blawan Why They Hide Their Bodies", "broken-ebm"),
    ("Donato Dozzy Gol", "hypnotic-ambient"),
    ("Oscar Mulero Black Propaganda", "industrial-spanish"),
    ("Dax J Escape The System", "hard-fast"),
    ("Rrose Waterfall", "experimental-hypnotic"),
]

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "reference-audio" / "previews"
ITUNES = "https://itunes.apple.com/search?media=music&limit=1&term="


def slugify(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest, failures = [], []
    for term, corner in TRACKS:
        url = ITUNES + urllib.parse.quote(term)
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                results = json.load(r).get("results", [])
            if not results or not results[0].get("previewUrl"):
                failures.append(term)
                continue
            hit = results[0]
            dest = OUT_DIR / f"{slugify(term)}.m4a"
            urllib.request.urlretrieve(hit["previewUrl"], dest)
            manifest.append({
                "query": term,
                "corner": corner,
                "artist": hit.get("artistName"),
                "track": hit.get("trackName"),
                "album": hit.get("collectionName"),
                "file": dest.name,
            })
            print(f"ok   {term:45s} -> {hit.get('artistName')} - {hit.get('trackName')}")
        except Exception as e:
            failures.append(term)
            print(f"FAIL {term:45s} {e}", file=sys.stderr)
        time.sleep(1)  # be polite to the API
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n{len(manifest)} downloaded, {len(failures)} failed: {failures or 'none'}")
    return 0 if manifest else 1


if __name__ == "__main__":
    sys.exit(main())
