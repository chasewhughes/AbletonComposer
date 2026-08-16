#!/usr/bin/env python3
"""Hybrid resampling engine: pro raw material -> Live processing -> signature kit.

The v1 forge synthesized samples from raw DSP and they came out rudimentary.
This engine takes the other road: real recorded source material (Splice), runs
it through a deliberately-designed device chain inside Live, plays one hit, and
RE-CAPTURES the result through the render loop as a new sample. Feed a captured
sample back in with a different chain and you get generation 2 — the point at
which the kit stops sounding like anyone's pack and starts sounding like ours.

Pipeline per (source, recipe):
  1. FORGE track: Simpler loaded with the source sample (browser URI).
  2. Chain: audio effects loaded from the browser, every parameter set
     explicitly and read back by display value (nothing set blind).
  3. One note (pitch 60 — Simpler root) into a 2-bar clip.
  4. Solo FORGE, bypass the master chain, capture master via render.Renderer.
  5. Trim silence, fade, normalize, write 24-bit WAV to Samples/Forged2/.

Parameter specs are ("n", norm) | ("v", native) | ("e", "EnumName"). Native and
enum values are converted using the device's own min/max reported by Live, so
recipes read in real units (Hz, dB, semitones) instead of magic 0-1 numbers.

Usage:
  python3 tools/resample_engine.py list
  python3 tools/resample_engine.py run [--only kick_iron,rumble] [--gen 1,2]
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from live_mcp import LiveMCP  # noqa: E402
from live_bridge import LiveQuery, OSC_SEND_PORT  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402
from render import Renderer  # noqa: E402

USER_SAMPLES = os.path.expanduser("~/Music/Ableton/User Library/Samples")
SPLICE_DIR = os.path.join(USER_SAMPLES, "Splice")
OUT_DIR = os.path.join(USER_SAMPLES, "Forged2")
SPLICE_URI = "query:UserLibrary#Samples:Splice:{}"
FORGED2_URI = "query:UserLibrary#Samples:Forged2:{}"
FORGE_TRACK = "FORGE"
ROOT_NOTE = 60  # Simpler root

# ---------------------------------------------------------------- recipes
# Each recipe: source file (Splice name, or Forged2 name when gen=2), the
# chain, and optional Simpler tweaks (sample start/length for long sources).

N, V, E = "n", "v", "e"


def eq_hp(band, hz, slope48=True):
    """EQ Eight band as a highpass at hz."""
    kind = "High Pass 48dB" if slope48 else "High Pass 12dB"
    return {f"{band} Filter On A": (E, "On"), f"{band} Filter Type A": (E, kind),
            f"{band} Frequency A": (V, hz)}


def eq_lp(band, hz, slope48=False):
    kind = "Low Pass 48dB" if slope48 else "Low Pass 12dB"
    return {f"{band} Filter On A": (E, "On"), f"{band} Filter Type A": (E, kind),
            f"{band} Frequency A": (V, hz)}


def eq_bell(band, hz, gain_db, q=1.0):
    return {f"{band} Filter On A": (E, "On"), f"{band} Filter Type A": (E, "Bell"),
            f"{band} Frequency A": (V, hz), f"{band} Gain A": (V, gain_db),
            f"{band} Q A": (V, q)}


def eq(*blocks):
    out = {}
    for b in blocks:
        out.update(b)
    return out


RECIPES = {
    # kick_iron/kick_ox below are kept for reference but are NOT the kit kick:
    # measured against the raw sources they moved energy the wrong way, from
    # sub into the 120-350 Hz mud band (ox: 18.6% sub / 30.2% lowmid, versus
    # 31.4% / 16.2% for the untouched Plattenbau source). Roar's drive was
    # manufacturing harmonics exactly where a kick must stay out of the way.
    # This one is designed against those numbers instead: keep the fundamental,
    # cut the mud hard, and buy presence with a click rather than with drive.
    "kick_anvil": dict(
        gen=1, src="shs_mtl_kick_Plattenbau.wav",
        note="kit kick: sub preserved, 120-350 Hz scooped, click added",
        simpler={"S Start": (N, 0.0), "S Length": (N, 0.17)},
        chain=[
            ("EQ Eight", eq(eq_hp(1, 30.0),
                            eq_bell(3, 190.0, -6.0, q=1.1),
                            eq_bell(4, 320.0, -8.0, q=1.3),
                            eq_bell(5, 620.0, -4.0, q=1.5))),
            ("Drum Buss", {"Drive": (N, 0.12), "Drive Type": (E, "Soft"),
                           "Crunch": (N, 0.05), "Transients": (V, 0.62),
                           "Damping Freq": (V, 14000.0), "Boom Amt": (N, 0.34),
                           "Boom Freq": (V, 52.0), "Boom Decay": (N, 0.30),
                           "Compressor On": (E, "On"), "Dry/Wet": (N, 1.0)}),
            ("EQ Eight", eq(eq_bell(7, 3600.0, 5.0, q=0.8),
                            eq_bell(2, 58.0, 2.5, q=0.7))),
        ]),

    # ---------------- KICKS: weight, bite, and a tail that is ours
    "kick_iron": dict(
        gen=1, src="FO4_INT_kick_oni.wav", note="industrial kick -> transient + body",
        chain=[
            ("EQ Eight", eq(eq_hp(1, 27.0), eq_bell(4, 330.0, -5.0, q=1.4),
                            eq_bell(2, 62.0, 3.5, q=0.9))),
            ("Drum Buss", {"Drive": (N, 0.38), "Drive Type": (E, "Soft"),
                           "Crunch": (N, 0.14), "Transients": (V, 0.45),
                           "Damping Freq": (V, 9000.0), "Boom Amt": (N, 0.30),
                           "Boom Freq": (V, 58.0), "Boom Decay": (N, 0.42),
                           "Compressor On": (E, "On"), "Dry/Wet": (N, 1.0)}),
            ("Saturator", {"Drive": (V, 7.0), "Type": (E, "Soft Sine"),
                           "Dry/Wet": (N, 1.0), "Output": (V, -3.0)}),
        ]),
    "kick_ox": dict(
        gen=2, src="forged_kick_iron.wav", note="gen2: Roar color + micro-room",
        chain=[
            ("Roar", {"Drive": (V, 8.0), "Shaper 1 Amt": (N, 0.55),
                      "Tone Amt": (N, 0.35), "Tone Freq": (V, 220.0),
                      "Color On": (E, "On"), "Comp Amt": (N, 0.30),
                      "Dry/Wet": (N, 0.78), "Output": (V, -3.0)}),
            ("Reverb", {"Room Size": (N, 0.12), "Decay Time": (V, 340.0),
                        "Dry/Wet": (N, 0.11), "Predelay": (V, 3.0),
                        "Cut On": (E, "On"), "In Hi Cut On": (E, "On"),
                        "Input Freq": (V, 4200.0)}),
            ("EQ Eight", eq(eq_hp(1, 30.0), eq_bell(5, 480.0, -3.0, q=1.2))),
        ]),

    # ---------------- SUB / RUMBLE: the hypnotic-techno rumble is reverb on sub
    "rumble_tectonic": dict(
        gen=1, src="RKU_HV_BIA_twisty_sub_kick.wav",
        note="sub through a long room, filtered back to sub = rumble bed",
        chain=[
            ("Reverb", {"Room Size": (N, 0.82), "Decay Time": (V, 4200.0),
                        "Dry/Wet": (N, 0.52), "Predelay": (V, 12.0),
                        "In Hi Cut On": (E, "On"), "Input Freq": (V, 900.0),
                        "Diffusion": (N, 0.72), "Stereo Image": (V, 60.0)}),
            ("EQ Eight", eq(eq_hp(1, 24.0), eq_lp(8, 190.0),
                            eq_bell(3, 95.0, 2.5, q=0.8))),
            ("Saturator", {"Drive": (V, 5.0), "Type": (E, "Soft Sine"),
                           "Dry/Wet": (N, 0.75), "Output": (V, -4.0)}),
        ]),
    "sub_anchor": dict(
        gen=1, src="ff_at_kick_one_shot_bass.wav", note="clean sub layer, tightened",
        chain=[
            ("EQ Eight", eq(eq_hp(1, 26.0), eq_lp(8, 140.0))),
            ("Drum Buss", {"Drive": (N, 0.22), "Transients": (V, 0.30),
                           "Boom Amt": (N, 0.42), "Boom Freq": (V, 48.0),
                           "Boom Decay": (N, 0.55), "Dry/Wet": (N, 1.0)}),
            ("Saturator", {"Drive": (V, 4.0), "Type": (E, "Soft Sine"),
                           "Dry/Wet": (N, 0.6), "Output": (V, -3.0)}),
        ]),

    # ---------------- METAL PERC: junkyard steel, made rhythmic
    "metal_slag": dict(
        gen=1, src="SPLC-4088_Junkyard_Metal_Low_Hit.wav",
        note="junkyard steel -> aggressive industrial perc",
        simpler={"S Start": (N, 0.0), "S Length": (N, 0.55)},
        chain=[
            ("Roar", {"Drive": (V, 13.0), "Shaper 1 Amt": (N, 0.62),
                      "Tone Amt": (N, 0.42), "Tone Freq": (V, 1800.0),
                      "Comp Amt": (N, 0.35), "Dry/Wet": (N, 0.85),
                      "Output": (V, -4.0)}),
            ("Drum Buss", {"Drive": (N, 0.20), "Transients": (V, 0.60),
                           "Damping Freq": (V, 7500.0), "Boom Amt": (N, 0.0),
                           "Dry/Wet": (N, 1.0)}),
            ("Hybrid Reverb", {"Decay": (N, 0.28), "Size": (N, 0.30),
                               "Predelay": (V, 6.0), "Dry/Wet": (N, 0.22),
                               "Damping": (N, 0.55)}),
        ]),
    "metal_bell": dict(
        gen=2, src="forged_metal_slag.wav",
        note="gen2: Corpus turns steel into a tuned, inharmonic bell-perc",
        chain=[
            ("Corpus", {"Resonance Type": (E, "Tube"), "Tune": (V, 220.0),
                        "Decay": (N, 0.52), "Material": (N, 0.62),
                        "Brightness": (N, 0.58), "Inharmonics": (N, 0.68),
                        "Ratio": (N, 0.45), "Dry Wet": (N, 0.62),
                        "Gain": (V, -3.0)}),
            ("Saturator", {"Drive": (V, 6.0), "Type": (E, "Soft Sine"),
                           "Dry/Wet": (N, 0.8), "Output": (V, -4.0)}),
            ("EQ Eight", eq(eq_hp(1, 180.0), eq_bell(6, 3400.0, 2.5, q=1.1))),
        ]),
    "metal_tick": dict(
        gen=1, src="TL_PT_Percussion_Metal_Hits.wav",
        note="short metal tick -> bright off-grid accent",
        chain=[
            ("Redux", {"Bit Depth": (N, 0.55), "Sample Rate": (N, 0.62),
                       "Jitter": (N, 0.18), "Dry/Wet": (N, 0.6)}),
            ("Roar", {"Drive": (V, 7.0), "Shaper 1 Amt": (N, 0.48),
                      "Dry/Wet": (N, 0.7), "Output": (V, -4.0)}),
            ("EQ Eight", eq(eq_hp(1, 420.0), eq_bell(6, 5200.0, 3.0, q=1.0))),
        ]),

    # ---------------- ORGANIC: wood + foley scrape, given a body
    "wood_bone": dict(
        gen=1, src="KREAEM_sharp_wood_stick.wav",
        note="wood stick -> resonant tuned body (organic half of the kit)",
        chain=[
            ("Corpus", {"Resonance Type": (E, "Marimba"), "Tune": (V, 165.0),
                        "Decay": (N, 0.44), "Material": (N, 0.48),
                        "Brightness": (N, 0.52), "Inharmonics": (N, 0.42),
                        "Dry Wet": (N, 0.55), "Gain": (V, -2.0)}),
            ("Dynamic Tube", {"Drive": (N, 0.45), "Bias": (N, 0.55),
                              "Tone": (N, 0.6), "Dry/Wet": (N, 0.8),
                              "Tube Type": (E, "B")}),
            ("Reverb", {"Room Size": (N, 0.25), "Decay Time": (V, 700.0),
                        "Dry/Wet": (N, 0.16), "Cut On": (E, "On")}),
        ]),
    "scrape_grain": dict(
        gen=1, src="ESM_metal_lid_taps_scrapes.wav",
        note="foley scrape -> textural mid perc",
        simpler={"S Start": (N, 0.06), "S Length": (N, 0.30)},
        chain=[
            ("Erosion", {"Amount": (N, 0.62), "Frequency": (V, 5200.0),
                         "Filter Width": (N, 0.5), "Noise Blend": (N, 0.55)}),
            ("Roar", {"Drive": (V, 6.0), "Shaper 1 Amt": (N, 0.50),
                      "Dry/Wet": (N, 0.72), "Output": (V, -4.0)}),
            ("Hybrid Reverb", {"Decay": (N, 0.35), "Size": (N, 0.40),
                               "Dry/Wet": (N, 0.26)}),
        ]),

    # ---------------- HATS: digital grit rather than 909 clones
    "hat_static": dict(
        gen=1, src="RU_TD_closed_hat_analog_short.wav",
        note="closed hat -> bit-crushed static tick",
        chain=[
            ("Erosion", {"Amount": (N, 0.55), "Frequency": (V, 8200.0),
                         "Noise Blend": (N, 0.62), "Filter Width": (N, 0.45)}),
            ("Redux", {"Bit Depth": (N, 0.48), "Sample Rate": (N, 0.58),
                       "Dry/Wet": (N, 0.55)}),
            ("EQ Eight", eq(eq_hp(1, 620.0), eq_bell(7, 9000.0, 3.5, q=0.9))),
        ]),
    "hat_wide": dict(
        gen=1, src="RU_TD_closed_hat_analog_low.wav",
        note="darker hat -> open/offbeat voice with air",
        chain=[
            ("Drum Buss", {"Drive": (N, 0.18), "Transients": (V, 0.10),
                           "Damping Freq": (V, 11000.0), "Boom Amt": (N, 0.0),
                           "Dry/Wet": (N, 1.0)}),
            ("Hybrid Reverb", {"Decay": (N, 0.34), "Size": (N, 0.45),
                               "Dry/Wet": (N, 0.30), "Damping": (N, 0.40)}),
            ("EQ Eight", eq(eq_hp(1, 480.0), eq_bell(6, 6200.0, 2.0, q=1.0))),
        ]),

    # ---------------- TEXTURE
    "haze_bed": dict(
        gen=1, src="ORBIT_DMT_136_perc_noise_texture_dark.wav",
        note="noise texture -> atmosphere bed",
        simpler={"S Start": (N, 0.0), "S Length": (N, 0.5)},
        chain=[
            ("Roar", {"Drive": (V, 3.0), "Shaper 1 Amt": (N, 0.40),
                      "Dry/Wet": (N, 0.6), "Output": (V, -6.0)}),
            ("Erosion", {"Amount": (N, 0.40), "Frequency": (V, 3800.0),
                         "Noise Blend": (N, 0.45)}),
            ("Hybrid Reverb", {"Decay": (N, 0.62), "Size": (N, 0.70),
                               "Dry/Wet": (N, 0.45), "Damping": (N, 0.5)}),
        ]),

    # ---------------- WILDCARD: a reed drone made metallic. The genre signature.
    "throat_spectral": dict(
        gen=1, src="MNT_MW_duduk_drone_G.wav",
        note="WILDCARD: duduk reed -> Spectral Resonator -> alien tonal hook",
        simpler={"S Start": (N, 0.12), "S Length": (N, 0.22)},
        chain=[
            ("Spectral Resonator", {"Freq. Hz": (V, 98.0), "Decay": (N, 0.62),
                                    "Harmonics": (N, 0.45), "Stretch": (N, 0.62),
                                    "Shift": (N, 0.52), "High Damp": (N, 0.45),
                                    "Dry Wet": (N, 0.78), "Unison Amount": (N, 0.30)}),
            ("Roar", {"Drive": (V, 7.0), "Shaper 1 Amt": (N, 0.52),
                      "Tone Amt": (N, 0.3), "Dry/Wet": (N, 0.7),
                      "Output": (V, -5.0)}),
            ("Hybrid Reverb", {"Decay": (N, 0.48), "Size": (N, 0.55),
                               "Dry/Wet": (N, 0.32)}),
        ]),
}


# ---------------------------------------------------------------- engine
class ResampleEngine:
    def __init__(self, bars=2, verbose=True):
        self.live = LiveMCP(timeout=30)
        self.q = LiveQuery()
        self.osc = SimpleUDPClient("127.0.0.1", OSC_SEND_PORT)
        self.renderer = Renderer()
        self.bars = bars
        self.verbose = verbose
        self._fx_uris = None

    def log(self, msg):
        if self.verbose:
            print(msg)

    # -- browser ---------------------------------------------------------
    def fx_uri(self, name):
        if self._fx_uris is None:
            items = self.live.cmd("get_browser_items_at_path",
                                  path="audio_effects").get("items", [])
            self._fx_uris = {i["name"]: i["uri"] for i in items}
        if name not in self._fx_uris:
            raise RuntimeError(f"audio effect {name!r} not in browser")
        return self._fx_uris[name]

    def wait_for_browser(self, folder, filename, timeout=25):
        """Live indexes the User Library asynchronously; wait for a new file."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            items = self.live.cmd("get_browser_items_at_path",
                                  path=f"user_library/Samples/{folder}").get("items", [])
            if any(i["name"] == filename for i in items):
                return True
            time.sleep(2.0)
        return False

    # -- track / device --------------------------------------------------
    def track_by_name(self, name):
        info = self.live.cmd("get_session_info")
        for i in range(info["track_count"]):
            if self.live.cmd("get_track_info", track_index=i)["name"] == name:
                return i
        return None

    def ensure_forge_track(self):
        idx = self.track_by_name(FORGE_TRACK)
        if idx is None:
            idx = self.live.cmd("get_session_info")["track_count"]
            self.live.cmd("create_midi_track", index=-1)
            self.live.cmd("set_track_name", track_index=idx, name=FORGE_TRACK)
            self.log(f"[engine] created {FORGE_TRACK} track at {idx}")
        return idx

    def clear_devices(self, track):
        devices = self.live.cmd("get_track_info", track_index=track).get("devices", [])
        for _ in devices:
            self.live.cmd("delete_device", track_index=track, device_index=0)
        return len(devices)

    def param_table(self, track, device):
        r = self.live.cmd("get_device_parameters", track_index=track,
                          device_index=device, show_all=True)
        return {p["name"]: p for p in r.get("parameters", [])}

    def _apply(self, track, device, p, norm):
        """Push a normalized value and return Live's display string."""
        res = self.live.cmd("set_device_parameter", track_index=track,
                            device_index=device, parameter_index=p["index"],
                            value=max(0.0, min(1.0, norm)))
        return res.get("display_value")

    def _calibrate(self, track, device, p, target, iters=14, tol=0.005):
        """Bisect the normalized value until Live's DISPLAY hits `target`.

        Many Live parameters report a 0-1 range while displaying Hz/dB/ms on a
        nonlinear curve, so arithmetic on min/max cannot reach a musical target
        (a 27 Hz request lands on 22 kHz). Live tells us the real value after
        every set, so we search against that instead of trusting the range.
        Display is monotonic in the normalized value for the frequency, time,
        gain and Q parameters this engine targets.
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

    def set_param(self, track, device, name, spec, table):
        """Set one parameter from a ('n'|'v'|'e', value) spec, verified."""
        p = table.get(name)
        if p is None:
            # tolerate minor naming drift across Live versions
            cands = [k for k in table if k.lower() == name.lower()]
            p = table[cands[0]] if cands else None
        if p is None:
            self.log(f"    !! no param {name!r} on device {device}")
            return None
        kind, val = spec
        lo, hi = float(p["min"]), float(p["max"])

        if kind == N:
            return self._apply(track, device, p, float(val))

        if kind == E:
            items = [str(i) for i in (p.get("value_items") or [])]
            want = str(val).lower()
            match = next((i for i, it in enumerate(items) if it.lower() == want), None)
            if match is None:  # fall back to a substring match before giving up
                match = next((i for i, it in enumerate(items) if want in it.lower()), None)
            if match is None:
                self.log(f"    !! {name}: no enum {val!r} in {items}")
                return None
            norm = 0.0 if hi == lo else (match - lo) / (hi - lo)
            return self._apply(track, device, p, norm)

        if kind == V:
            target = float(val)
            # A genuinely native range (Transpose -48..48, EQ gain -15..15) can
            # be hit arithmetically; a 0-1 range means the display is a curve.
            native = not (lo == 0.0 and hi == 1.0)
            if native and lo <= target <= hi:
                return self._apply(track, device, p, (target - lo) / (hi - lo))
            return self._calibrate(track, device, p, target)

        raise ValueError(f"bad spec kind {kind!r}")

    def build_chain(self, track, chain):
        """Load each effect in order and set its parameters, reporting values."""
        for dev_name, params in chain:
            self.live.cmd("load_browser_item", track_index=track,
                          item_uri=self.fx_uri(dev_name))
            time.sleep(0.9)
            devices = self.live.cmd("get_track_info", track_index=track).get("devices", [])
            di = len(devices) - 1
            if di < 0 or dev_name.split()[0] not in devices[di]["name"]:
                raise RuntimeError(f"{dev_name} failed to load "
                                   f"(devices: {[d['name'] for d in devices]})")
            table = self.param_table(track, di)
            shown = []
            for pname, spec in params.items():
                disp = self.set_param(track, di, pname, spec, table)
                if disp is not None:
                    shown.append(f"{pname}={disp}")
            self.log(f"    {dev_name}: " + ", ".join(shown))

    # -- capture ---------------------------------------------------------
    def master_devices(self):
        try:
            return self.live.cmd("get_track_info", track_index=-1).get("devices", [])
        except Exception:
            return []

    def set_master_enabled(self, enabled):
        for i, _ in enumerate(self.master_devices()):
            try:
                self.live.cmd("set_device_enabled", track_index=-1,
                              device_index=i, enabled=enabled)
            except Exception as e:
                self.log(f"    !! master device {i} enable={enabled}: {e}")

    def solo(self, track, on):
        self.osc.send_message("/live/track/set/solo", [int(track), 1 if on else 0])
        time.sleep(0.15)

    def capture_hit(self, track):
        self.osc.send_message("/live/song/stop_all_clips", [])
        time.sleep(0.2)
        self.set_master_enabled(False)
        self.solo(track, True)
        try:
            return self.renderer.capture(self.bars, play_tracks=(track,))
        finally:
            self.solo(track, False)
            self.set_master_enabled(True)
            self.osc.send_message("/live/song/stop_all_clips", [])

    # -- one forge pass --------------------------------------------------
    def forge(self, key, recipe):
        gen = recipe.get("gen", 1)
        src = recipe["src"]
        folder = "Splice" if gen == 1 else "Forged2"
        uri = (SPLICE_URI if gen == 1 else FORGED2_URI).format(src)
        out_name = f"forged_{key}.wav"
        out_path = os.path.join(OUT_DIR, out_name)

        self.log(f"\n=== {key} (gen {gen}) — {recipe.get('note','')}")
        self.log(f"    source: {folder}/{src}")

        if gen == 2 and not self.wait_for_browser("Forged2", src):
            raise RuntimeError(f"gen2 source {src} never appeared in Live's browser")

        track = self.ensure_forge_track()
        self.clear_devices(track)
        self.live.cmd("load_browser_item", track_index=track, item_uri=uri)
        time.sleep(1.2)
        devices = self.live.cmd("get_track_info", track_index=track).get("devices", [])
        if not devices:
            raise RuntimeError(f"sample {src} did not load onto {FORGE_TRACK}")
        self.log(f"    simpler: {devices[0]['name']}")

        simpler_tweaks = recipe.get("simpler") or {}
        if simpler_tweaks:
            table = self.param_table(track, 0)
            shown = []
            for pname, spec in simpler_tweaks.items():
                disp = self.set_param(track, 0, pname, spec, table)
                if disp is not None:
                    shown.append(f"{pname}={disp}")
            self.log("    simpler tweaks: " + ", ".join(shown))

        self.build_chain(track, recipe["chain"])

        # One hit at the Simpler root. The clip is made twice as long as the
        # capture window: a clip exactly the capture length loops and stamps a
        # second hit into the tail of the take.
        self.live.cmd("delete_clip", track_index=track, clip_index=0)
        self.live.cmd("create_clip", track_index=track, clip_index=0,
                      length=float(self.bars * 4 * 2))
        self.live.cmd("add_notes_v2", track_index=track, clip_index=0, notes=[
            {"pitch": ROOT_NOTE, "start_time": 0.0, "duration": 1.0,
             "velocity": 118, "probability": 1.0, "velocity_deviation": 0}])
        self.live.cmd("set_clip_name", track_index=track, clip_index=0, name=f"F-{key}")

        take = self.capture_hit(track)
        info = trim_and_write(take, out_path)
        self.log(f"    -> {out_path}  ({info['dur']:.3f}s, peak {info['peak_db']:.1f} dBFS, "
                 f"trimmed {info['trimmed_ms']:.0f} ms of lead-in)")
        return out_path


_DISPLAY_RE = re.compile(r"^\s*(-?[\d.]+)\s*(kHz|Hz|ms|s|dB|%)?")
_UNIT_SCALE = {"kHz": 1000.0, "s": 1000.0}  # canonical units: Hz and ms


def parse_display(disp):
    """Turn Live's display string into a number ('22.0 kHz' -> 22000.0).

    Returns None for non-numeric displays (enum names), which tells the
    calibrator to stop rather than search on nonsense.
    """
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


# ---------------------------------------------------------------- audio post
def trim_and_write(src_path, out_path, floor_db=-60.0, tail_db=-52.0,
                   pad_ms=25.0, fade_ms=18.0, peak_db=-1.0):
    """Trim capture lead-in/tail, fade out, normalize, write 24-bit WAV."""
    data, sr = sf.read(src_path, dtype="float32", always_2d=True)
    amp = np.max(np.abs(data), axis=1)
    peak = float(amp.max())
    if peak < 1e-5:
        raise RuntimeError(f"capture is silent: {src_path}")

    start_thr = peak * (10 ** (floor_db / 20))
    end_thr = peak * (10 ** (tail_db / 20))
    above = np.nonzero(amp > start_thr)[0]
    if len(above) == 0:
        raise RuntimeError(f"capture never crosses the noise floor: {src_path}")
    start = int(above[0])
    above_tail = np.nonzero(amp > end_thr)[0]
    end = int(above_tail[-1]) + int(pad_ms / 1000 * sr)
    end = min(end, len(data))
    trimmed = data[start:end].copy()

    fade = int(fade_ms / 1000 * sr)
    if fade > 0 and len(trimmed) > fade:
        trimmed[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    # de-click the very start too (capture can begin mid-cycle)
    lead = min(int(0.002 * sr), len(trimmed))
    if lead > 0:
        trimmed[:lead] *= np.linspace(0.0, 1.0, lead)[:, None]

    p = float(np.max(np.abs(trimmed))) + 1e-9
    trimmed *= (10 ** (peak_db / 20)) / p

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sf.write(out_path, trimmed, sr, subtype="PCM_24")
    return {"dur": len(trimmed) / sr, "peak_db": peak_db,
            "trimmed_ms": start / sr * 1000, "sr": sr}


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "run"])
    ap.add_argument("--only", default="", help="comma-sep recipe keys")
    ap.add_argument("--gen", default="1,2", help="generations to run")
    ap.add_argument("--bars", type=int, default=2)
    a = ap.parse_args()

    if a.cmd == "list":
        for k, r in RECIPES.items():
            devs = " -> ".join(d for d, _ in r["chain"])
            print(f"{k:18s} gen{r['gen']}  {r['src']}\n{'':20s}{devs}\n"
                  f"{'':20s}{r.get('note','')}")
        return

    gens = {int(g) for g in a.gen.split(",") if g.strip()}
    only = {k.strip() for k in a.only.split(",") if k.strip()}
    eng = ResampleEngine(bars=a.bars)
    todo = [(k, r) for k, r in RECIPES.items()
            if r["gen"] in gens and (not only or k in only)]
    # generation 1 must finish before generation 2 reads its output
    todo.sort(key=lambda kv: kv[1]["gen"])

    made, failed = [], []
    for k, r in todo:
        try:
            made.append(eng.forge(k, r))
        except Exception as e:
            failed.append((k, str(e)))
            print(f"    !! {k} FAILED: {e}")
    print(f"\n=== forged {len(made)}/{len(todo)} into {OUT_DIR}")
    for f, err in failed:
        print(f"    FAILED {f}: {err}")


if __name__ == "__main__":
    main()
