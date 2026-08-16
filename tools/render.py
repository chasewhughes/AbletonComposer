#!/usr/bin/env python3
"""Programmatic render loop: capture Live's master bus to a file on disk.

Mechanism (no GUI, no export dialog):
  1. Ensure a dedicated audio track named RESAMPLE exists, input = "Resampling"
     (records whatever the master outputs), monitoring off, armed.
  2. Start transport + session record for N bars: the take is written to disk
     by Live itself (temp recordings folder for unsaved sets, or the project's
     Samples/Recorded/ once the set is saved).
  3. Stop, locate the newest .aif/.wav recording, return its path.

Usage:
  python3 tools/render.py capture --bars 16 [--scene 0]
  python3 tools/render.py find          # just locate the newest recording
"""
import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_bridge import LiveQuery, OSC_SEND_PORT  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402

RESAMPLE_TRACK_NAME = "RESAMPLE"
RECORD_SEARCH_DIRS = [
    os.path.expanduser("~/Music/Ableton/Live Recordings"),
    os.path.expanduser("~/Music/Ableton"),
    "/tmp",
]


class Renderer:
    def __init__(self, host="127.0.0.1"):
        self.osc = SimpleUDPClient(host, OSC_SEND_PORT)
        self.q = LiveQuery(host)

    def send(self, addr, *args):
        self.osc.send_message(addr, list(args))

    def _track_names(self):
        n = self.q.query("/live/song/get/num_tracks")
        if not n:
            raise RuntimeError("Live is not answering OSC queries — is it running?")
        names = []
        for i in range(int(n[0])):
            r = self.q.query("/live/track/get/name", i)
            names.append(r[1] if r and len(r) > 1 else f"track{i}")
        return names

    def ensure_resample_track(self):
        names = self._track_names()
        if RESAMPLE_TRACK_NAME in names:
            idx = names.index(RESAMPLE_TRACK_NAME)
        else:
            idx = len(names)
            self.send("/live/song/create_audio_track", idx)
            time.sleep(0.5)
            self.send("/live/track/set/name", idx, RESAMPLE_TRACK_NAME)
        avail = self.q.query("/live/track/get/available_input_routing_types", idx) or []
        if not any("Resampling" in str(a) for a in avail):
            raise RuntimeError(f"track {idx} has no Resampling input; got {avail}")
        self.send("/live/track/set/input_routing_type", idx, "Resampling")
        time.sleep(0.2)
        self.send("/live/track/set/current_monitoring_state", idx, 2)  # monitoring off
        self.send("/live/track/set/arm", idx, 1)
        time.sleep(0.2)
        routing = self.q.query("/live/track/get/input_routing_type", idx)
        print(f"[render] RESAMPLE track {idx}, input routing = {routing}")
        return idx

    def capture(self, bars, scene=None, tail_beats=2, play_tracks=()):
        from live_mcp import LiveMCP
        mcp = LiveMCP()
        tempo = float(self.q.query("/live/song/get/tempo")[0])
        idx = self.ensure_resample_track()
        before = newest_recording()
        # clear the take slot (MCP delete is reliable), ensure armed, settle
        mcp.cmd("delete_clip", track_index=idx, clip_index=0)
        self.send("/live/track/set/arm", idx, 1)
        time.sleep(0.5)
        if scene is not None:
            self.send("/live/scene/fire", int(scene))
        for t in play_tracks:
            mcp.cmd("fire_clip", track_index=t, clip_index=0)
        # firing the EMPTY armed slot starts recording into it
        self.send("/live/clip_slot/fire", idx, 0)
        self.send("/live/song/start_playing")
        seconds = (bars * 4 + tail_beats) * 60.0 / tempo
        print(f"[render] recording {bars} bars @ {tempo:.1f} BPM (~{seconds:.0f}s)...")
        time.sleep(seconds)
        self.send("/live/clip/stop", idx, 0)  # finalize the take file
        self.send("/live/song/stop_playing")
        self.send("/live/track/set/arm", idx, 0)
        # ask Live for the take's exact path, then wait for a stable file
        path = None
        for _ in range(30):
            time.sleep(1.0)
            r = self.q.query("/live/clip/get/file_path", idx, 0)
            if r and len(r) > 2 and r[2]:
                path = r[2]
                break
        if not path:
            raise RuntimeError("recorded clip reports no file_path")
        last_size = -1
        for _ in range(90):
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 0 and size == last_size:
                    print(f"[render] captured: {path}")
                    return path
                last_size = size
            time.sleep(1.0)
        raise RuntimeError(f"take file never stabilized: {path}")


def newest_recording():
    candidates = []
    for base in RECORD_SEARCH_DIRS:
        for ext in ("aif", "aiff", "wav"):
            candidates += glob.glob(os.path.join(base, "**", f"*.{ext}"), recursive=True)
    fresh = [(os.path.getmtime(p), p) for p in candidates if time.time() - os.path.getmtime(p) < 3600 * 24]
    return max(fresh)[1] if fresh else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["capture", "find"])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--scene", type=int, default=None)
    ap.add_argument("--play", type=str, default="", help="comma-sep track indices to fire")
    args = ap.parse_args()
    if args.cmd == "find":
        print(newest_recording())
    else:
        tracks = [int(t) for t in args.play.split(",") if t.strip()]
        print(Renderer().capture(args.bars, scene=args.scene, play_tracks=tracks))
