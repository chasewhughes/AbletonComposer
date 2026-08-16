#!/usr/bin/env python3
"""Semantic ear — CLAP audio-text embeddings turn a render into words.

Three readings, all from one embedding model:

  quality axes    Contrastive prompt pairs ("punchy powerful kick" vs "weak
                  flabby kick"). Softmax over pole similarities gives a 0-1
                  score per axis — the closest thing to an opinion a
                  measurement can have.
  character       Multiclass over techno subgenre / mood prompts: what does
                  this actually sound LIKE, in words.
  reference sims  Cosine similarity to the embedded reference corpus. This is
                  the perceptual version of critic.py's core/novelty: high
                  mean sim = reads as techno; high max sim = sounds like a
                  specific existing record (occupied territory).

Windowed variants of the quality axes give a timeline: "the kick reads weak
from 1:20" is a sentence a mix decision can act on.

The CLAP model (LAION music checkpoint) lives in .models/; reference
embeddings are cached in reference-audio/clap_refs.npz (rebuild with
`listen.py refs`).
"""
import json
import pathlib

import numpy as np

REPO = pathlib.Path(__file__).resolve().parent.parent
REF_DIR = REPO / "reference-audio"
REFS_CACHE = REF_DIR / "clap_refs.npz"
CKPT = REPO / ".models" / "music_audioset_epoch_15_esc_90.14.pt"
CLAP_SR = 48000

# Diagnostic axes: (name, good-pole prompts, bad-pole prompts).
# Multiple phrasings per pole make the score robust to prompt wording.
QUALITY_AXES = [
    ("kick_power",
     ["a powerful punchy techno kick drum with deep sub weight",
      "a heavy pounding four on the floor kick drum"],
     ["a weak thin flabby kick drum",
      "a quiet muffled kick drum buried in the mix"]),
    ("lowend_control",
     ["tight controlled deep sub bass",
      "a clean powerful low end with punch and definition"],
     ["muddy boomy uncontrolled low frequencies",
      "a blurry droning bass that masks everything"]),
    ("groove",
     ["a hypnotic rolling techno groove that makes you dance",
      "an infectious driving rhythm with momentum and swing"],
     ["a stiff lifeless mechanical drum loop",
      "a rigid quantized beat with no feel"]),
    ("production",
     ["an expensive professionally produced and mastered club record",
      "a polished powerful club mix with clarity and depth"],
     ["a cheap amateur demo with stock preset sounds",
      "a rough unmixed bedroom production"]),
    ("space",
     ["a deep spacious mix with atmosphere, reverb and depth",
      "a wide immersive soundscape with foreground and background"],
     ["a dry flat cramped mix with no sense of space",
      "a narrow lifeless recording with everything upfront"]),
    ("top_end",
     ["crisp detailed hi-hats and shimmering airy highs",
      "bright sparkling percussion with presence"],
     ["dull muffled high frequencies with no air",
      "dark smeared top end, hats lost in the mix"]),
    ("energy",
     ["driving peak-time techno energy, relentless and intense",
      "a high energy club track building tension"],
     ["sleepy low-energy background music",
      "a flat static loop going nowhere"]),
]

# What does it sound like — subgenre map (multiclass, reported as distribution)
CHARACTER_PROMPTS = {
    "industrial techno": "harsh industrial techno with distorted metallic percussion",
    "peak-time techno": "big-room peak-time techno with a pounding kick and dark synth stabs",
    "hypnotic techno": "hypnotic loop-driven techno, repetitive and trance-inducing",
    "acid techno": "acid techno with a squelchy resonant 303 bassline",
    "dub techno": "deep dub techno with echoing chords and tape delay",
    "minimal techno": "stripped-back minimal techno with subtle micro-details",
    "hard techno": "fast aggressive hard techno with a rumbling distorted kick",
    "melodic techno": "melodic techno with emotional synth leads and chords",
    "ambient techno": "atmospheric ambient techno with pads and slow evolution",
    "broken techno": "experimental broken-beat techno with syncopated drums",
    "electro": "electro with crisp 808 drum machine syncopation",
    "house": "groovy house music with a swung beat",
    "trance": "uplifting trance with arpeggiated melodies",
    "dubstep": "half-time dubstep with wobble bass",
    "noise": "harsh noise, static and distortion, not music",
}

# Free descriptors: scored raw, top-K reported — the evocation wordfield.
MOOD_PROMPTS = [
    "dark and menacing", "euphoric and uplifting", "cold and mechanical",
    "warm and organic", "cavernous warehouse space", "claustrophobic and dense",
    "metallic and abrasive", "smooth and liquid", "cosmic and vast",
    "underground and raw", "clinical and precise", "chaotic and unhinged",
    "playful and bouncy", "ominous and tense", "meditative and hypnotic",
    "futuristic and alien", "nostalgic and analog", "aggressive and confrontational",
]


class SemanticEar:
    """Lazy-loading CLAP wrapper. Import cost is zero; first use loads torch."""

    def __init__(self, ckpt=CKPT):
        self.ckpt = pathlib.Path(ckpt)
        self._model = None
        self._text_cache = {}

    @property
    def available(self):
        try:
            import laion_clap  # noqa: F401
        except Exception:
            return False
        return self.ckpt.exists()

    def _load(self):
        if self._model is None:
            import laion_clap
            self._model = laion_clap.CLAP_Module(enable_fusion=False,
                                                 amodel="HTSAT-base")
            self._model.load_ckpt(str(self.ckpt), verbose=False)
        return self._model

    def embed_text(self, texts):
        """(N, D) L2-normalized text embeddings, cached per prompt."""
        missing = [t for t in texts if t not in self._text_cache]
        if missing:
            emb = self._load().get_text_embedding(missing, use_tensor=False)
            emb = np.asarray(emb, dtype=np.float32)
            emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
            for t, e in zip(missing, emb):
                self._text_cache[t] = e
        return np.stack([self._text_cache[t] for t in texts])

    def embed_audio_batch(self, clips):
        """clips: list of float32 mono arrays at 48 kHz -> (N, D) normalized."""
        n = max(len(c) for c in clips)
        x = np.zeros((len(clips), n), dtype=np.float32)
        for i, c in enumerate(clips):
            x[i, :len(c)] = c
        emb = self._load().get_audio_embedding_from_data(x=x, use_tensor=False)
        emb = np.asarray(emb, dtype=np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        return emb

    # ---- readings -----------------------------------------------------

    def quality_axes(self, audio_emb):
        """audio_emb (D,) -> {axis: score 0..1}; 0.5 = ambiguous."""
        out = {}
        for name, good, bad in QUALITY_AXES:
            g = self.embed_text(good) @ audio_emb
            b = self.embed_text(bad) @ audio_emb
            # softmax between pole means; CLAP sims are small, temperature
            # sharpens the contrast into a usable 0-1 range
            gm, bm = g.mean(), b.mean()
            out[name] = float(np.exp(gm / 0.03) /
                              (np.exp(gm / 0.03) + np.exp(bm / 0.03)))
        return out

    def character(self, audio_emb, top_k=5):
        names = list(CHARACTER_PROMPTS)
        sims = self.embed_text([CHARACTER_PROMPTS[n] for n in names]) @ audio_emb
        p = np.exp(sims / 0.03)
        p /= p.sum()
        order = np.argsort(-p)
        return [(names[i], float(p[i])) for i in order[:top_k]]

    def moods(self, audio_emb, top_k=6):
        sims = self.embed_text(MOOD_PROMPTS) @ audio_emb
        order = np.argsort(-sims)
        return [(MOOD_PROMPTS[i], float(sims[i])) for i in order[:top_k]]

    def reference_sims(self, audio_emb, top_k=3):
        """Similarity to the embedded reference corpus. None if cache missing."""
        if not REFS_CACHE.exists():
            return None
        z = np.load(REFS_CACHE, allow_pickle=True)
        embs, labels = z["embs"], list(z["labels"])
        sims = embs @ audio_emb
        order = np.argsort(-sims)
        return {
            "semantic_core": float(np.mean(sims)),        # reads-as-techno
            "semantic_max_sim": float(sims.max()),        # sounds-like-a-record
            "semantic_novelty": float(1.0 - sims.max()),
            "nearest": [(str(labels[i]), float(sims[i])) for i in order[:top_k]],
        }


def load_windows(path, win_s=10.0, hop_s=5.0):
    """Yield (t_start, clip48k) windows plus the full-track mean clip list."""
    import librosa
    y, _ = librosa.load(str(path), sr=CLAP_SR, mono=True)
    win, hop = int(win_s * CLAP_SR), int(hop_s * CLAP_SR)
    if len(y) <= win:
        return y, [(0.0, y)]
    starts = list(range(0, len(y) - win + 1, hop))
    return y, [(s / CLAP_SR, y[s:s + win]) for s in starts]


def build_reference_cache(ear, verbose=True):
    """Embed the reference corpus (same file set critic.py uses) -> npz."""
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    from critic import reference_files  # reuse the corpus definition
    import librosa

    embs, labels = [], []
    for path, corner, offset, duration in reference_files():
        try:
            y, _ = librosa.load(str(path), sr=CLAP_SR, mono=True,
                                offset=offset, duration=min(duration or 60.0, 60.0))
        except Exception as e:
            if verbose:
                print(f"SKIP {path.name}: {e}")
            continue
        if len(y) < CLAP_SR * 5:
            continue
        # embed up to 3 windows per reference for coverage
        clips, win = [], CLAP_SR * 10
        for frac in (0.1, 0.45, 0.8):
            s = int(frac * max(0, len(y) - win))
            clips.append(y[s:s + win])
        e = ear.embed_audio_batch(clips).mean(axis=0)
        e /= np.linalg.norm(e) + 1e-9
        embs.append(e)
        labels.append(f"{path.name} ({corner})")
        if verbose:
            print(f"ok  {labels[-1]}")
    np.savez(REFS_CACHE, embs=np.stack(embs), labels=np.array(labels))
    if verbose:
        print(f"\n{len(embs)} reference embeddings -> {REFS_CACHE}")


def analyze(path, ear=None):
    """Full semantic reading of one render. Returns a JSON-able dict."""
    ear = ear or SemanticEar()
    if not ear.available:
        return {"available": False,
                "reason": "laion_clap not importable or checkpoint missing"}
    y, windows = load_windows(path)
    clips = [c for _, c in windows]
    times = [t for t, _ in windows]
    embs = ear.embed_audio_batch(clips)
    track_emb = embs.mean(axis=0)
    track_emb /= np.linalg.norm(track_emb) + 1e-9

    timeline = []
    for t, e in zip(times, embs):
        qa = ear.quality_axes(e)
        timeline.append({"t": round(t, 1), **{k: round(v, 2) for k, v in qa.items()}})

    return {
        "available": True,
        "quality": {k: round(v, 3) for k, v in ear.quality_axes(track_emb).items()},
        "character": ear.character(track_emb),
        "moods": ear.moods(track_emb),
        "references": ear.reference_sims(track_emb),
        "timeline": timeline,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "refs":
        build_reference_cache(SemanticEar())
    elif len(sys.argv) > 1:
        print(json.dumps(analyze(sys.argv[1]), indent=1))
    else:
        sys.exit(__doc__)
