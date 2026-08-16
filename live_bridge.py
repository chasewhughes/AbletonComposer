"""Shared helpers for talking to Ableton Live via AbletonOSC.

Fixes two long-standing silent no-ops in the perform scripts:

1. dB -> mixer volume. Live's track fader is a perceptual taper, not linear
   amplitude: 1.0 = +6 dB, 0.85 = 0 dB, 0.0 = -inf. The old code used
   10**(db/20), which put every track ~12 dB low and compressed the mix.

2. Device parameter units. Live's DeviceParameter.value is in the parameter's
   OWN native range (e.g. a filter frequency in Hz), not 0-1. The old code
   sent normalized 0-1 values raw, which pinned filters shut. LiveQuery asks
   AbletonOSC for each device's parameter names/min/max (cached) so callers
   can set parameters by normalized position.
"""
import os
import select
import socket
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "AbletonOSC"))  # vendored pythonosc

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

OSC_SEND_PORT = 11000
OSC_RESPONSE_PORT = 11001  # AbletonOSC always replies to (sender_host, 11001)


def db_to_live_fader(db):
    """Map dB to Live's 0-1 mixer fader value.

    Piecewise-linear fit through Live's published anchors (+6 dB = 1.0,
    0 dB = 0.85, ~40 dB per fader-unit down to -18 dB = 0.4), then a linear
    tail to -70 dB = 0. Close enough that intended mix levels land within
    a fraction of a dB, vs. the ~12 dB error of the old linear-amplitude math.
    """
    if db <= -70.0:
        return 0.0
    if db >= -18.0:
        return max(0.0, min(1.0, 0.85 + db / 40.0))
    return (db + 70.0) / 130.0


class LiveQuery:
    """Blocking OSC query client for AbletonOSC get-endpoints.

    Binds the fixed response port (11001). If Live isn't running or the port
    is taken, queries fail loudly once and callers fall back to raw sends --
    never silently.
    """

    def __init__(self, host="127.0.0.1", timeout=2.0):
        self.host = host
        self.timeout = timeout
        self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._recv_sock = None
        self._recv_error = None

    def _ensure_recv(self):
        if self._recv_sock is None and self._recv_error is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(("0.0.0.0", OSC_RESPONSE_PORT))
                s.setblocking(False)
                self._recv_sock = s
            except OSError as e:
                self._recv_error = e
                print(f"[live_bridge] WARNING: cannot bind response port "
                      f"{OSC_RESPONSE_PORT} ({e}); OSC queries disabled")
        return self._recv_sock

    def query(self, address, *args):
        """Send an OSC get-request and return the reply args, or None."""
        if self._ensure_recv() is None:
            return None
        builder = OscMessageBuilder(address=address)
        for a in args:
            builder.add_arg(a)
        # drain any stale datagrams before sending
        while select.select([self._recv_sock], [], [], 0)[0]:
            self._recv_sock.recvfrom(65536)
        self._send_sock.sendto(builder.build().dgram, (self.host, OSC_SEND_PORT))
        remaining = self.timeout
        while remaining > 0:
            ready = select.select([self._recv_sock], [], [], remaining)[0]
            if not ready:
                break
            data, _ = self._recv_sock.recvfrom(65536)
            try:
                msg = OscMessage(data)
            except Exception:
                continue
            if msg.address == address:
                return list(msg.params)
            remaining -= 0.01
        print(f"[live_bridge] WARNING: no reply to {address} "
              f"(is Live running with AbletonOSC loaded?)")
        return None


class DeviceParams:
    """Cached name/min/max tables per (track, device), for normalized sets."""

    def __init__(self, live_query):
        self._q = live_query
        self._cache = {}
        self._failed = set()

    def lookup(self, track, device):
        key = (track, device)
        if key in self._cache:
            return self._cache[key]
        if key in self._failed:
            return None
        names = self._q.query("/live/device/get/parameters/name", track, device)
        mins = self._q.query("/live/device/get/parameters/min", track, device)
        maxs = self._q.query("/live/device/get/parameters/max", track, device)
        if not names or not mins or not maxs:
            self._failed.add(key)
            return None
        # replies echo (track, device, *values)
        table = {
            str(name): (float(lo), float(hi), idx)
            for idx, (name, lo, hi) in enumerate(zip(names[2:], mins[2:], maxs[2:]))
        }
        self._cache[key] = table
        return table

    def scale(self, track, device, param, norm):
        """Resolve param (name or index) and map norm 0-1 into native range.

        Returns (param_index, native_value), or None if Live is unreachable.
        """
        table = self.lookup(track, device)
        if table is None:
            return None
        norm = max(0.0, min(1.0, norm))
        if isinstance(param, str):
            if param not in table:
                print(f"[live_bridge] WARNING: no param named {param!r} on "
                      f"track {track} device {device}; have: {sorted(table)}")
                return None
            lo, hi, idx = table[param]
        else:
            idx = int(param)
            entry = next((v for v in table.values() if v[2] == idx), None)
            if entry is None:
                return None
            lo, hi, _ = entry
        return idx, lo + norm * (hi - lo)
