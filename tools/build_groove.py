#!/usr/bin/env python3
"""Phase 2/3 proving ground: expressive techno groove from code, v2.

v2: the drum palette is OURS — samples synthesized by tools/forge.py (no
stock devices, no packs) loaded onto Simpler tracks. Drift remains only as
the acid voice (mono+glide for real slides). A master chain (EQ / Glue /
Limiter) makes renders comparable to the mastered reference tracks.

Usage: python3 tools/build_groove.py [--bars 16] [--seed 707]
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_mcp import LiveMCP  # noqa: E402
from live_bridge import db_to_live_fader  # noqa: E402
import patterns as P  # noqa: E402

BPM = 133.0


class Builder:
    def __init__(self):
        self.live = LiveMCP()

    def track_by_name(self, name):
        info = self.live.cmd("get_session_info")
        for i in range(info["track_count"]):
            if self.live.cmd("get_track_info", track_index=i)["name"] == name:
                return i
        return None

    def ensure_track(self, name, uri, want_device):
        """MIDI track named `name` whose device 0 is `want_device` (loaded from uri)."""
        idx = self.track_by_name(name)
        if idx is None:
            n = self.live.cmd("get_session_info")["track_count"]
            self.live.cmd("create_midi_track", index=-1)
            idx = n
            self.live.cmd("set_track_name", track_index=idx, name=name)
        devices = self.live.cmd("get_track_info", track_index=idx).get("devices", [])
        if not devices or want_device not in devices[0]["name"]:
            for _ in devices:
                self.live.cmd("delete_device", track_index=idx, device_index=0)
            self.live.cmd("load_browser_item", track_index=idx, item_uri=uri)
            time.sleep(0.8)
        return idx

    def params(self, track, device=0):
        r = self.live.cmd("get_device_parameters", track_index=track,
                          device_index=device, show_all=True)
        return {p["name"]: p for p in r.get("parameters", [])}

    def set_param(self, track, fragment, norm, device=0, table=None):
        table = table if table is not None else self.params(track, device)
        matches = [p for n, p in table.items() if fragment.lower() in n.lower()]
        if not matches:
            print(f"  !! no param matching {fragment!r} on track {track}")
            return None
        # set_device_parameter takes NORMALIZED 0-1 and scales internally
        self.live.cmd("set_device_parameter", track_index=track, device_index=device,
                      parameter_index=matches[0].get("index"),
                      value=max(0.0, min(1.0, norm)))
        return matches[0]["name"], norm

    def write_clip(self, track, notes, bars, name):
        self.live.cmd("delete_clip", track_index=track, clip_index=0)
        self.live.cmd("create_clip", track_index=track, clip_index=0,
                      length=float(bars * 4))
        self.live.cmd("add_notes_v2", track_index=track, clip_index=0, notes=notes)
        self.live.cmd("set_clip_name", track_index=track, clip_index=0, name=name)

    def ensure_master_chain(self):
        """EQ Eight -> Glue Compressor -> Limiter on the master track."""
        try:
            have = [d["name"] for d in
                    self.live.cmd("get_track_info", track_index=-1).get("devices", [])]
        except Exception:
            have = []
        fx = self.live.cmd("get_browser_items_at_path", path="audio_effects")
        uris = {i["name"]: i["uri"] for i in fx.get("items", [])}
        for name in ["EQ Eight", "Glue Compressor", "Limiter"]:
            if name in have:
                continue
            uri = uris.get(name)
            if not uri:
                print(f"  !! {name} not in browser audio_effects")
                continue
            self.live.cmd("load_browser_item", track_index=-1, item_uri=uri)
            time.sleep(0.6)
            print(f"  master += {name}")


FORGE = "query:UserLibrary#Samples:Forged:forged_{}_{}.wav"


def main(bars, seed):
    rng = random.Random(seed)
    b = Builder()
    b.live.cmd("set_tempo", tempo=BPM)

    kick = b.ensure_track("KICK", FORGE.format("kick", seed), "Simpler")
    chat = b.ensure_track("CHAT", FORGE.format("hat_closed", seed), "Simpler")
    ohat = b.ensure_track("OHAT", FORGE.format("hat_open", seed), "Simpler")
    perc = b.ensure_track("PERC", FORGE.format("perc", seed), "Simpler")
    acid = b.ensure_track("ACID", "query:Synths#Drift", "Drift")
    print(f"tracks: KICK={kick} CHAT={chat} OHAT={ohat} PERC={perc} ACID={acid}")

    print("ACID (Drift):")
    at = b.params(acid)
    for frag, v in [("Osc 1 Shape", 1.0), ("LP Freq", 0.24), ("LP Res", 0.66),
                    ("LP Mod Amt 1", 0.60), ("Env 2 Decay", 0.30),
                    ("Legato On", 1.0), ("Glide Time", 0.22),
                    ("Env 1 Decay", 0.40), ("Env 1 Sustain", 0.35)]:
        b.set_param(acid, frag, v, table=at)

    # ---- patterns (forged samples: root note = 60)
    kick_notes = P.apply_groove(
        P.four_floor(BPM, bars, ghost_prob=0.22, pitch=60),
        P.GROOVES["straight"], BPM, jitter_ms=1.0, rng=rng)
    ohat_notes = P.apply_groove(
        P.open_offbeats(BPM, bars, vel=82, pitch=60),
        P.GROOVES["tight"], BPM, jitter_ms=2.5, rng=rng)
    chat_notes = P.apply_groove(
        P.closed_ticks(BPM, bars, pitch=60),
        P.GROOVES["swing_58"], BPM, jitter_ms=2.0, rng=rng)
    perc_notes = P.apply_groove(
        P.sparse_perc(BPM, bars, pitch=60, rng=rng),
        P.GROOVES["tight"], BPM, jitter_ms=3.0, rng=rng)

    A1 = 33
    steps = [
        {"deg": 0, "acc": True}, {"deg": 0}, None, {"deg": 0, "slide": True},
        {"deg": 12}, None, {"deg": 0}, {"deg": 3, "acc": True, "slide": True},
        {"deg": 0}, None, {"deg": 10, "slide": True}, {"deg": 12, "acc": True},
        None, {"deg": 0}, {"deg": -2, "slide": True}, None,
    ]
    acid_notes = P.apply_groove(
        P.acid_line(steps, A1, BPM, bars, rng=rng),
        P.GROOVES["tight"], BPM, jitter_ms=1.5, rng=rng)

    for t, notes, nm in [(kick, kick_notes, "Kick"), (chat, chat_notes, "CHat"),
                         (ohat, ohat_notes, "OHat"), (perc, perc_notes, "Perc"),
                         (acid, acid_notes, "Acid")]:
        b.write_clip(t, notes, bars, f"P2-{nm}")
    print(f"clips: kick {len(kick_notes)} chat {len(chat_notes)} "
          f"ohat {len(ohat_notes)} perc {len(perc_notes)} acid {len(acid_notes)}")

    # ---- acid movement: cutoff sweep + resonance blocks as real envelopes
    total = bars * 4
    sweep = [[t, 0.22 + 0.60 * (t / total) ** 1.2] for t in range(0, total)]
    sweep += [[total - 0.5, 0.30]]
    print("cutoff env:", b.live.cmd("set_clip_envelope", track_index=acid,
                                    clip_index=0, parameter_name="LP Freq",
                                    points=sweep, normalized=True))
    res = [[t, 0.55 + 0.25 * ((t // 8) % 2)] for t in range(0, total, 4)]
    b.live.cmd("set_clip_envelope", track_index=acid, clip_index=0,
               parameter_name="LP Res", points=res, normalized=True)

    # ---- master chain + mix
    print("master chain:")
    b.ensure_master_chain()
    mt = b.params(-1, device=1)  # Glue Compressor
    b.set_param(-1, "Threshold", 0.38, device=1, table=mt)
    b.set_param(-1, "Output", 0.62, device=1, table=mt)
    b.set_param(-1, "Ratio", 0.5, device=1, table=mt)

    for t, db in [(kick, -6), (chat, -12), (ohat, -9), (perc, -12), (acid, -8)]:
        b.live.cmd("set_track_volume", track_index=t, volume=db_to_live_fader(db))

    for t in (kick, chat, ohat, perc, acid):
        b.live.cmd("fire_clip", track_index=t, clip_index=0)
    print("groove v2 firing.")
    return [kick, chat, ohat, perc, acid]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--seed", type=int, default=707)
    a = ap.parse_args()
    main(a.bars, a.seed)
