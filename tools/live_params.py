"""Setting Live device parameters in units you can reason about.

`set_device_parameter` takes a normalized 0-1 value and denormalizes it against
the parameter's reported min/max. That works for parameters whose range really
is native (Transpose -48..48, EQ gain -15..15), but a great many Live
parameters report 0..1 while DISPLAYING Hz, dB or ms on a nonlinear curve. Ask
such a parameter for "27" and you land on 22 kHz.

Live returns the resulting display string after every set, so the reliable move
is to search against that instead of trusting the range. Specs are:

    (N, 0.65)      normalized, when the parameter really is a 0-1 amount
    (V, 27.0)      native/display units — Hz, dB, ms, %, whatever it shows
    (E, "Bell")    enum by name (exact, then substring)
"""
import re

N, V, E = "n", "v", "e"

_DISPLAY_RE = re.compile(r"^\s*(-?[\d.]+)\s*(kHz|Hz|ms|s|dB|%)?")
_UNIT_SCALE = {"kHz": 1000.0, "s": 1000.0}  # canonical units: Hz and ms


def parse_display(disp):
    """'22.0 kHz' -> 22000.0. None for enum names, which stops the search."""
    if not disp:
        return None
    m = _DISPLAY_RE.match(str(disp))
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return val * _UNIT_SCALE.get(m.group(2), 1.0)


class ParamSetter:
    """Calibrated parameter setting against a LiveMCP connection."""

    def __init__(self, live, log=print):
        self.live = live
        self._log = log

    def table(self, track, device):
        r = self.live.cmd("get_device_parameters", track_index=track,
                          device_index=device, show_all=True)
        return {p["name"]: p for p in r.get("parameters", [])}

    def _apply(self, track, device, p, norm):
        res = self.live.cmd("set_device_parameter", track_index=track,
                            device_index=device, parameter_index=p["index"],
                            value=max(0.0, min(1.0, norm)))
        return res.get("display_value")

    def _calibrate(self, track, device, p, target, iters=14, tol=0.005):
        """Bisect the normalized value until Live's display reaches `target`.

        Display is monotonic in the normalized value for the frequency, time,
        gain and Q parameters this is used on.
        """
        lo_n, hi_n, disp = 0.0, 1.0, None
        for _ in range(iters):
            mid = (lo_n + hi_n) / 2
            disp = self._apply(track, device, p, mid)
            got = parse_display(disp)
            if got is None:
                return disp
            if abs(got - target) <= max(tol * abs(target), 1e-9):
                return disp
            if got < target:
                lo_n = mid
            else:
                hi_n = mid
        return disp

    def set(self, track, device, name, spec, table=None):
        table = table if table is not None else self.table(track, device)
        p = table.get(name)
        if p is None:
            cands = [k for k in table if k.lower() == name.lower()]
            p = table[cands[0]] if cands else None
        if p is None:
            self._log(f"    !! no param {name!r} on track {track} device {device}")
            return None

        kind, val = spec
        lo, hi = float(p["min"]), float(p["max"])

        if kind == N:
            return self._apply(track, device, p, float(val))

        if kind == E:
            items = [str(i) for i in (p.get("value_items") or [])]
            want = str(val).lower()
            match = next((i for i, it in enumerate(items) if it.lower() == want), None)
            if match is None:
                match = next((i for i, it in enumerate(items) if want in it.lower()), None)
            if match is None:
                self._log(f"    !! {name}: no enum {val!r} in {items}")
                return None
            return self._apply(track, device, p, 0.0 if hi == lo else (match - lo) / (hi - lo))

        if kind == V:
            target = float(val)
            native = not (lo == 0.0 and hi == 1.0)
            if native and lo <= target <= hi:
                return self._apply(track, device, p, (target - lo) / (hi - lo))
            return self._calibrate(track, device, p, target)

        raise ValueError(f"bad spec kind {kind!r}")

    def set_many(self, track, device, params, label=None):
        """Apply a {name: spec} dict, returning the display values it achieved."""
        table = self.table(track, device)
        shown = []
        for pname, spec in params.items():
            disp = self.set(track, device, pname, spec, table)
            if disp is not None:
                shown.append(f"{pname}={disp}")
        if label:
            self._log(f"    {label}: " + ", ".join(shown))
        return shown
