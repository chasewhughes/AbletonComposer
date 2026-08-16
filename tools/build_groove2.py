#!/usr/bin/env python3
"""Phase 3 groove: the resampled signature kit, arranged.

Supersedes build_groove.py (kept for A/B against the v2 baseline). Every drum
voice here is a Forged2 sample — Splice raw material run through a Live chain
and re-captured by tools/resample_engine.py. Drift stays as the acid voice.

Mix philosophy comes from the known seesaw: pulse hierarchy beats limiter gain.
The kick is unambiguously the loudest onset so the beat tracker locks to 133
instead of aliasing to ~178, and the off-8th open hat sits well under it. The
band balance is aimed at the reference centroid measured from fingerprints.json
(sub .11 / bass .13 / lowmid .14 / mid .23 / highmid .23 / high .17), which
needs more top end than intuition suggests.

Usage: python3 tools/build_groove2.py [--bars 16] [--seed 707]
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_mcp import LiveMCP  # noqa: E402
from live_bridge import db_to_live_fader, LiveQuery, OSC_SEND_PORT  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402
from live_params import ParamSetter, N, V, E  # noqa: E402
import patterns as P  # noqa: E402

BPM = 133.0
FORGED2 = "query:UserLibrary#Samples:Forged2:{}.wav"
ROOT = 60

# Simpler plays one-shots in Trigger mode: the whole sample sounds regardless
# of note length. Retriggering a long sample faster than it decays stacks it
# into a continuous drone, which is what buried the first v3 render (ears.py
# read the low band as -2.7 dB congestion and the kick at 0.94x the median).
# So every voice declares how long its sample actually is, and the patterns
# below never retrigger faster than that.
# A voice whose sample outlasts its own retrigger interval smears into a drone:
# kick_ox is 0.72 s but a beat at 133 BPM is 0.451 s, so it overlapped itself
# 1.6 deep and the "kick" stopped reading as a transient at all (ears.py:
# kick/median 0.99x). `max_len` clamps playback via Simpler's S Length so every
# voice finishes before it is asked to speak again.
#   name -> (forged stem, mix dB, sample length s, max playback s or None)
VOICES = {
    # Kick clamped tighter than before. At 0.40 s against a 0.451 s beat the
    # sample's subharmonic bloom re-peaked inside its own decay: the 25-100 Hz
    # band fired 7.1 times a second where the Drumcode drum stems fire 2.2.
    # The kick has to be a transient, not an event that fills the beat.
    "KICK":   ("forged_kick_anvil",       -4.5, 0.48, 0.30),
    "SUB":    ("forged_sub_anchor",      -18.0, 0.64, 0.34),
    "RUMBLE": ("forged_rumble_tectonic", -27.0, 4.38, 1.60),
    "CHAT":   ("forged_hat_static",       -8.0, 0.14, None),
    "OHAT":   ("forged_hat_wide",        -11.0, 1.43, 0.30),
    # +3 dB: 25.4% of its energy is 350-2000 Hz and it plays 36 times a loop,
    # so it is the only voice that can add SUSTAINED mid rather than 3 hits.
    "PERC":   ("forged_metal_slag",       -9.0, 1.77, 1.20),
    "TICK":   ("forged_metal_tick",       -9.0, 0.24, None),
    "BELL":   ("forged_metal_bell",      -16.0, 1.24, None),
    "WOOD":   ("forged_wood_bone",       -13.0, 0.54, None),
    "SCRAPE": ("forged_scrape_grain",    -14.0, 1.70, None),
    # The wildcard, and the only voice in the kit that is mostly midrange
    # (65.9% of its energy in 350-2000 Hz, where the next best is 32.7%). It
    # sat at -20 dB playing once in sixteen bars, which is why the mix
    # measured a scooped mid -4.6 dB under every reference AND why the one
    # deliberately strange sound in the kit was inaudible. Raising it fixes a
    # measured hole and commits to the odd axis at the same time.
    "THROAT": ("forged_throat_spectral", -11.0, 4.32, None),
    "HAZE":   ("forged_haze_bed",        -26.0, 4.21, None),
}
ACID_DB = -10.0
# References run their bass stem ~8 dB under the DRUMS STEM (-17.1 vs -9.1
# measured across the 9 Drumcode singles). The trap: that is a stem-to-stem
# ratio, and the drums stem is ten voices summed, not the kick track alone.
# Setting the bass 8 dB under the kick FADER put it 24 dB under the drums bus
# and it measured -40.4 dB in the render — still inaudible. A synth this far
# below a dense drum bus needs real gain, and a Live fader stops at +6 dB, so
# the make-up lives in a Utility. Set from the measured gap: drums stem -13.7,
# bass stem -40.4, target -8 => +18.7 dB.
BASS_DB = -12.5
BASS_GAIN_DB = 18.0

# Per-voice reverb sends, as (device, dry/wet). The render measured CLAP
# `space` at 0.06 — "a dry flat cramped mix" — because reverb only ever existed
# baked inside individual samples. Tails are also what makes a loop roll rather
# than tick, so this is aimed at `groove` as much as at `space`. The kick and
# sub stay bone dry; everything decorative gets air.
SPACE = {
    # CHAT gets a little air because the sample decays in 29 ms against a
    # corpus median of 75 ms — it reads as a tick rather than a hi-hat.
    "CHAT":   ("Reverb", 0.11),
    "PERC":   ("Reverb", 0.20), "TICK": ("Reverb", 0.26),
    "BELL":   ("Reverb", 0.30), "WOOD": ("Reverb", 0.16),
    "SCRAPE": ("Reverb", 0.34), "OHAT": ("Reverb", 0.14),
    "THROAT": ("Reverb", 0.38),
}

# Which bars each voice plays. 16 bars that never change read as a broken loop;
# the structure ear reported "no audible change" across every render so far.
# Entries are (first_bar, last_bar) inclusive, 1-based.
SECTIONS = {
    "KICK":   (1, 16), "SUB": (1, 16), "CHAT": (1, 16),
    "OHAT":   (3, 16), "PERC": (5, 16), "TICK": (9, 16),
    "WOOD":   (7, 14), "BELL": (9, 16), "SCRAPE": (11, 16),
    "RUMBLE": (1, 16), "THROAT": (5, 16), "HAZE": (1, 16),
    "ACID":   (5, 16), "BASS": (1, 16),
}


def gate(notes, span, bars):
    """Keep only notes inside a (first_bar, last_bar) inclusive window."""
    if not span:
        return notes
    lo = (span[0] - 1) * 4
    hi = min(span[1], bars) * 4
    return [n for n in notes if lo <= n["start_time"] < hi]
# Everything is written with headroom, then trimmed as a block so the limiter
# shapes rather than arranges. Tuned so LUFS lands near the reference -11.5.
MASTER_TRIM_DB = 8.0


class Builder:
    def __init__(self):
        self.live = LiveMCP(timeout=30)
        self.osc = SimpleUDPClient("127.0.0.1", OSC_SEND_PORT)
        self._names = None

    def track_names(self):
        if self._names is None:
            info = self.live.cmd("get_session_info")
            self._names = [self.live.cmd("get_track_info", track_index=i)["name"]
                           for i in range(info["track_count"])]
        return self._names

    def track_by_name(self, name):
        names = self.track_names()
        return names.index(name) if name in names else None

    def ensure_track(self, name, uri, want_device):
        """MIDI track `name` whose device 0 is `want_device`, loaded from uri."""
        idx = self.track_by_name(name)
        if idx is None:
            idx = len(self.track_names())
            self.live.cmd("create_midi_track", index=-1)
            self.live.cmd("set_track_name", track_index=idx, name=name)
            self._names.append(name)
        devices = self.live.cmd("get_track_info", track_index=idx).get("devices", [])
        if not devices or want_device not in devices[0]["name"]:
            for _ in devices:
                self.live.cmd("delete_device", track_index=idx, device_index=0)
            self.live.cmd("load_browser_item", track_index=idx, item_uri=uri)
            time.sleep(0.9)
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
        self.live.cmd("set_device_parameter", track_index=track, device_index=device,
                      parameter_index=matches[0].get("index"),
                      value=max(0.0, min(1.0, norm)))
        return matches[0]["name"]

    def write_clip(self, track, notes, bars, name):
        self.live.cmd("delete_clip", track_index=track, clip_index=0)
        self.live.cmd("create_clip", track_index=track, clip_index=0,
                      length=float(bars * 4))
        if notes:
            self.live.cmd("add_notes_v2", track_index=track, clip_index=0, notes=notes)
        self.live.cmd("set_clip_name", track_index=track, clip_index=0, name=name)

    def ensure_effect(self, track, name):
        """Append an audio effect to a track once, returning its device index.

        The master (-1) has no get_track_info, so its devices are probed and
        identified by a signature parameter instead of by name.
        """
        if track == -1:
            count = self.master_device_count()
            for i in range(count):
                names = {p["name"] for p in self.params(-1, i).values()
                         } if False else {
                    p["name"] for p in self.live.cmd(
                        "get_device_parameters", track_index=-1,
                        device_index=i, show_all=True)["parameters"]}
                if name == "Utility" and "Bass Mono" in names:
                    return i
            uris = {i["name"]: i["uri"] for i in self.live.cmd(
                "get_browser_items_at_path", path="audio_effects").get("items", [])}
            if name not in uris:
                print(f"  !! {name} not in browser audio_effects")
                return None
            self.live.cmd("load_browser_item", track_index=-1, item_uri=uris[name])
            time.sleep(0.7)
            return count

        devices = self.live.cmd("get_track_info", track_index=track).get("devices", [])
        for i, d in enumerate(devices):
            if name.split()[0] in d["name"]:
                return i
        fx = self.live.cmd("get_browser_items_at_path", path="audio_effects")
        uris = {i["name"]: i["uri"] for i in fx.get("items", [])}
        if name not in uris:
            print(f"  !! {name} not in browser audio_effects")
            return None
        self.live.cmd("load_browser_item", track_index=track, item_uri=uris[name])
        time.sleep(0.7)
        return len(devices)

    def master_device_count(self):
        """Number of devices on the master.

        get_track_info rejects track_index=-1 ("Track index out of range")
        even though device commands accept it, so the count has to be probed.
        Relying on get_track_info here silently returned "no devices" and made
        this function re-add the whole chain on every run — three stacked
        limiters by the third build, which is what crushed the render.
        """
        i = 0
        while i < 32:
            try:
                self.live.cmd("get_device_parameters", track_index=-1,
                              device_index=i, show_all=False)
            except Exception:
                break
            i += 1
        return i

    def ensure_master_chain(self):
        """Exactly one EQ Eight -> Glue Compressor -> Limiter, never stacked."""
        want = ["EQ Eight", "Glue Compressor", "Limiter"]
        have = self.master_device_count()
        if have >= len(want):
            # >= not ==: a Utility gets appended later, and demanding an exact
            # count here would tear the chain down and rebuild it every run.
            print(f"  master chain already present ({have} devices)")
            return
        for i in range(have - 1, -1, -1):
            self.live.cmd("delete_device", track_index=-1, device_index=i)
        if have:
            print(f"  master: cleared {have} stale device(s)")
        fx = self.live.cmd("get_browser_items_at_path", path="audio_effects")
        uris = {i["name"]: i["uri"] for i in fx.get("items", [])}
        for name in want:
            if name not in uris:
                print(f"  !! {name} not in browser audio_effects")
                continue
            self.live.cmd("load_browser_item", track_index=-1, item_uri=uris[name])
            time.sleep(0.6)
            print(f"  master += {name}")

    def silence_track(self, name):
        """Mute a leftover working track (FORGE) so it cannot leak into a render."""
        idx = self.track_by_name(name)
        if idx is not None:
            self.osc.send_message("/live/track/set/mute", [idx, 1])
        return idx


# ------------------------------------------------------------------ patterns
def kick_pattern(bars, rng):
    """Four on the floor, beat 1 strongest. No ghosts: the tracker needs a
    clean, unambiguous pulse (this is what the 178 BPM misread punishes)."""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            vel = 127 if beat == 0 else 121
            notes.append(P.note(ROOT, bar * 4 + beat, 0.9, vel))
    return notes


def sub_pattern(bars):
    """Silent. This voice was a one-shot doubling the kick on 1 and 3, and it
    was the wrong instrument for the job twice over: it added two more
    percussive low-band transients per bar to a band already firing three
    times too often, and because it is a SAMPLE, demucs files it under drums.
    So the render measured a drums stem holding 97% of the energy and a bass
    stem 34.6 dB down — the low end read as controlled because there was
    nothing in it. BASS below does this properly, as a synth, in the gaps."""
    return []


# Simpler pitch-shifts a sample, so the note number sets the sounding pitch.
# Measured at ROOT (C3): forged_throat_spectral sounds A# (98% concentration)
# and forged_metal_bell sounds G#. The track is in A minor (A C D E G), so
# both sat exactly a semitone above a scale tone — the harmony ear caught the
# throat as "bass A against other A#, a major 7th, present 24% of the time"
# the moment it was loud enough to matter. -1 puts the throat on A and the
# bell on G, and their second notes on C.
TUNE = {"THROAT": -1, "BELL": -1}

A1 = 33          # 55.0 Hz — the kick measures A1 +6 cents, so the bass agrees
G1 = 31          # the acid's other degree, an octave down


def bass_pattern(bars):
    """The bassline the render never had: off-8ths, in the kick's gaps.

    Every reference record carries a bass stem about 8 dB under its drums;
    this render measured 34.6 dB down, because the acid was high-passed at
    165 Hz to clear the mud and nothing was put back underneath. That is the
    single reason the low end read as 'controlled' and the groove read as
    stiff — there was no second low-frequency voice to roll against the kick.

    Off-8ths rather than 16ths: the note has to start and finish between two
    kicks (0.226 s at 133 BPM), which is what makes a loop roll instead of
    drone, and it means no sidechain is needed to keep the two apart.
    """
    notes = []
    for bar in range(bars):
        for beat in range(4):
            # bar 2 of each pair drops to G on the last off-8th — the acid's
            # other degree, so the two voices agree instead of merely coexist
            pitch = G1 if (bar % 2 == 1 and beat == 3) else A1
            vel = 108 if beat == 0 else 98
            notes.append(P.note(pitch, bar * 4 + beat + 0.5, 0.44, vel, vdev=-4))
    return notes


def rumble_pattern(bars):
    """Rumble every 4 bars only. The sample is 4.4 s — at 133 BPM that is
    2.4 bars, so anything tighter overlaps itself into a drone."""
    return [P.note(ROOT, bar * 4, 2.0, 100) for bar in range(0, bars, 4)]


def _steps(bars, vels, dur=0.12, cycle=1):
    """Lay a fixed velocity row over the 16th grid. 0 = rest.

    `vels` is one bar (16 entries) or `cycle` bars concatenated. Deterministic
    on purpose: the earlier patterns dropped notes at random, so no two bars
    were alike and CLAP read the result as clutter rather than a groove
    (semantic groove 0.04). Hypnotic depends on the ear predicting the next
    bar, so repetition is the feature and dynamics carry the interest.
    """
    notes = []
    per = 16 * cycle
    for bar in range(bars):
        for i in range(16):
            v = vels[(bar % cycle) * 16 + i] if len(vels) == per else vels[i]
            if v:
                notes.append(P.note(ROOT, bar * 4 + i * 0.25, dur, v))
    return notes


def chat_pattern(bars, rng):
    """Closed hat on every 16th, accented into a roll.

    The accent shape (weak / medium / strong / medium) is what makes 16ths
    read as forward motion instead of a wash; swing_58 then pushes the even
    16ths late so it rolls rather than marches.
    """
    # Accent FLOOR raised from 38 to 66. The old range put three of every four
    # 16ths so far under the open hat that they did not survive a local
    # prominence test — which is roughly what an ear does in a dense mix. The
    # render measured 8.8 hat onsets/s written (16ths) but only 8 hits per 2
    # bars heard, against 16 in the references, and its high-band congestion
    # sat 7 dB below every reference: gaps where the records have continuity.
    # Written notes nobody hears are not a groove. 66/100 keeps the accent
    # shape while clearing the gate.
    bar_vels = [66, 84, 100, 84] * 4
    return _steps(bars, bar_vels, dur=0.10)


def ohat_pattern(bars):
    """Open hat on the off-8ths, identical every bar, under the kick."""
    return [P.note(ROOT, bar * 4 + beat + 0.5, 0.4, 92, vdev=-6)
            for bar in range(bars) for beat in range(4)]


def perc_pattern(bars, rng):
    """A fixed two-bar industrial-metal phrase — the thing you remember.

    Syncopated against the kick (lands on 16ths 7, 11, 14 / 7, 10, 15) so the
    two bars answer each other instead of repeating flat.
    """
    b1 = [0] * 16
    for i, v in ((6, 104), (10, 78), (13, 96)):
        b1[i] = v
    b2 = [0] * 16
    for i, v in ((6, 104), (9, 82), (14, 110)):
        b2[i] = v
    return _steps(bars, b1 + b2, dur=0.4, cycle=2)


def bell_pattern(bars):
    """Tuned metal motif every 2 bars: the hypnotic hook."""
    notes = []
    for bar in range(0, bars, 2):
        t = TUNE["BELL"]
        notes.append(P.note(ROOT + t, bar * 4 + 2.5, 1.0, 104, vdev=-8))
        notes.append(P.note(ROOT + 5 + t, bar * 4 + 3.75, 0.8, 92, vdev=-8))
    return notes


def wood_pattern(bars, rng):
    """Organic 3-against-4: a dotted-8th cycle that walks around the bar.

    Fixed, not random — the phase relationship against the 4/4 is the interest,
    and it only reads if it repeats predictably across a 3-bar cycle.
    """
    notes = []
    for bar in range(bars):
        for i, pos in enumerate((0.75, 1.5, 3.0)):
            if True:
                notes.append(P.note(ROOT, bar * 4 + pos, 0.3,
                                    (88, 74, 96)[i], vdev=-6))
    return notes


def tick_pattern(bars, rng):
    """Bright metal accents off the grid — carries high-band movement."""
    notes = []
    for bar in range(bars):
        for pos, vel in ((0.875, 96), (2.375, 104), (3.625, 88)):
            notes.append(P.note(ROOT, bar * 4 + pos, 0.2, vel, vdev=-8))
    return notes


def scrape_pattern(bars, rng):
    """Textural scrape every other bar — air and grain, never on a downbeat."""
    return [P.note(ROOT, bar * 4 + 2.75, 0.6, 92, vdev=-8)
            for bar in range(0, bars, 2)]


def throat_pattern(bars):
    """The wildcard tonal hook. 4.3 s is 2.4 bars at 133 BPM, so every 4 bars
    is the tightest spacing that never stacks it into a drone."""
    notes = []
    for i, bar in enumerate(range(0, bars, 4)):
        pitch = ROOT + TUNE["THROAT"] + (0 if i % 2 == 0 else 3)
        notes.append(P.note(pitch, bar * 4 + 3.0, 3.0, 96, vdev=-6))
    return notes


def haze_pattern(bars):
    """Atmosphere bed, once per 16 bars — it is 4.2 s and must not pile up."""
    return [P.note(ROOT, bar * 4, 8.0, 84) for bar in range(0, bars, 16)]


# ------------------------------------------------------------------ main
def main(bars, seed):
    rng = random.Random(seed)
    b = Builder()
    b.live.cmd("set_tempo", tempo=BPM)
    b.osc.send_message("/live/song/stop_all_clips", [])
    time.sleep(0.2)

    forge_idx = b.silence_track("FORGE")
    if forge_idx is not None:
        print(f"muted FORGE track {forge_idx}")

    ps = ParamSetter(b.live)
    tracks = {}
    for name, (stem, _, length, max_len) in VOICES.items():
        idx = b.ensure_track(name, FORGED2.format(stem), stem)
        tracks[name] = idx
        if max_len:
            # S Length is a fraction of the sample; Fade Out keeps the cut clean.
            ps.set_many(idx, 0, {"S Length": (N, min(1.0, max_len / length)),
                                 "Fade Out": (N, 0.12)},
                        label=f"{name} clamp {max_len:.2f}s")
    acid = b.ensure_track("ACID", "query:Synths#Drift", "Drift")
    bass = b.ensure_track("BASS", "query:Synths#Drift", "Drift")
    print("tracks: " + " ".join(f"{k}={v}" for k, v in tracks.items()) +
          f" ACID={acid} BASS={bass}")

    # ---- bass voice: a clean sub, no resonance, nothing above the low mids.
    # The acid owns everything over 165 Hz; this owns everything under it, so
    # the two never compete for the same register the way the old drone did.
    bt = b.params(bass)
    for frag, v in [("Osc 1 Shape", 0.0), ("LP Freq", 0.30), ("LP Res", 0.05),
                    ("Env 1 Attack", 0.0), ("Env 1 Decay", 0.30),
                    ("Env 1 Sustain", 0.55), ("Env 1 Release", 0.10),
                    ("Legato On", 0.0), ("Glide Time", 0.0)]:
        b.set_param(bass, frag, v, table=bt)
    b.ensure_effect(bass, "EQ Eight")
    ps.set_many(bass, 1, {
        # keep the sub, drop everything that would fight the acid or the hats
        "1 Filter On A": (E, "On"), "1 Filter Type A": (E, "High Pass 48dB"),
        "1 Frequency A": (V, 32.0),
        "8 Filter On A": (E, "On"), "8 Filter Type A": (E, "Low Pass 48dB"),
        "8 Frequency A": (V, 220.0),
    }, label="BASS EQ")
    du_bass = b.ensure_effect(bass, "Utility")
    if du_bass is not None:
        # Utility's gain parameter is called "Output", and it is normalized
        # 0..1 across -35..+35 dB (verified by read-back: 0.757 -> 18.0 dB).
        ps.set_many(bass, du_bass,
                    {"Output": (N, 0.5 + BASS_GAIN_DB / 70.0)},
                    label=f"BASS make-up {BASS_GAIN_DB:+.0f} dB")

    # ---- acid voice
    # The loop-zoom spectrogram showed this as an unbroken harmonic comb from
    # 100 Hz to 2 kHz across all 16 bars — it was not a bassline, it was a
    # drone sitting exactly where the kick lives, and it is what drove CLAP's
    # lowend_control to 0.01 and groove to 0.11. Three changes: play it an
    # octave up, shorten the envelope so notes stop, and high-pass the track so
    # the bottom two octaves belong to the kick alone.
    at = b.params(acid)
    for frag, v in [("Osc 1 Shape", 1.0), ("LP Freq", 0.42), ("LP Res", 0.55),
                    ("LP Mod Amt 1", 0.45), ("Env 2 Decay", 0.22),
                    ("Legato On", 1.0), ("Glide Time", 0.18),
                    ("Env 1 Decay", 0.22), ("Env 1 Sustain", 0.0)]:
        b.set_param(acid, frag, v, table=at)
    b.ensure_effect(acid, "EQ Eight")
    ps.set_many(acid, 1, {
        **{"1 Filter On A": (E, "On"), "1 Filter Type A": (E, "High Pass 48dB"),
           "1 Frequency A": (V, 165.0)},
        **{"6 Filter On A": (E, "On"), "6 Filter Type A": (E, "Bell"),
           "6 Frequency A": (V, 900.0), "6 Gain A": (V, 2.5), "6 Q A": (V, 1.2)},
    }, label="ACID EQ")

    # ---- patterns. Grooves are deliberately tight on everything that defines
    # the pulse and looser on the ornamental voices.
    G = P.GROOVES
    parts = {
        "KICK":   (P.apply_groove(kick_pattern(bars, rng), G["straight"], BPM, 0.6, rng)),
        "SUB":    (P.apply_groove(sub_pattern(bars), G["straight"], BPM, 0.6, rng)),
        "RUMBLE": (P.apply_groove(rumble_pattern(bars), G["straight"], BPM, 0.8, rng)),
        "BASS":   (P.apply_groove(bass_pattern(bars), G["straight"], BPM, 0.5, rng)),
        "CHAT":   (P.apply_groove(chat_pattern(bars, rng), G["swing_58"], BPM, 0.8, rng)),
        "OHAT":   (P.apply_groove(ohat_pattern(bars), G["tight"], BPM, 0.8, rng)),
        "PERC":   (P.apply_groove(perc_pattern(bars, rng), G["tight"], BPM, 1.2, rng)),
        "TICK":   (P.apply_groove(tick_pattern(bars, rng), G["push_pull"], BPM, 1.5, rng)),
        "BELL":   (P.apply_groove(bell_pattern(bars), G["tight"], BPM, 1.0, rng)),
        "WOOD":   (P.apply_groove(wood_pattern(bars, rng), G["push_pull"], BPM, 1.5, rng)),
        "SCRAPE": (P.apply_groove(scrape_pattern(bars, rng), G["tight"], BPM, 1.2, rng)),
        "THROAT": (P.apply_groove(throat_pattern(bars), G["straight"], BPM, 1.0, rng)),
        "HAZE":   (haze_pattern(bars)),
    }

    # A2, an octave up from the old A1 — out of the kick's register entirely.
    # Rests are the point: 7 sounding steps out of 16, so the line breathes
    # instead of filling every 16th.
    A2 = 45
    steps = [
        {"deg": 0, "acc": True}, None, None, {"deg": 0, "slide": True},
        None, None, {"deg": 12}, None,
        {"deg": 0, "acc": True}, None, {"deg": 10, "slide": True}, None,
        None, {"deg": 3}, None, None,
    ]
    parts["ACID"] = P.apply_groove(P.acid_line(steps, A2, BPM, bars, rng=rng),
                                   G["tight"], BPM, 1.5, rng)

    tracks["ACID"] = acid
    tracks["BASS"] = bass
    parts = {k: gate(v, SECTIONS.get(k), bars) for k, v in parts.items()}
    for name, notes in parts.items():
        b.write_clip(tracks[name], notes, bars, f"P3-{name}")
    print("notes: " + " ".join(f"{k}={len(v)}" for k, v in parts.items()))
    print("sections: " + " ".join(f"{k}{SECTIONS[k]}" for k in SECTIONS
                                  if SECTIONS[k] != (1, 16)))

    # ---- closed hat: move its energy up an octave.
    # The reference-derived one-shot bank puts forged_hat_static 2.8 sigma
    # BELOW the corpus on 6-12 kHz (16.5% against 61.2%) and 3.1 sigma above
    # on 2-6 kHz, with its peak at 3.0 kHz where reference hats sit at 6.8.
    # The mix says the same thing from the other end: high -1.9 z while
    # highmid rides the top of the range. Transposing the sample up would fix
    # the spectrum and shorten a decay that is already 8 sigma too short, so
    # this is EQ instead.
    dq = b.ensure_effect(tracks["CHAT"], "EQ Eight")
    if dq is not None:
        ps.set_many(tracks["CHAT"], dq, {
            "4 Filter On A": (E, "On"), "4 Filter Type A": (E, "Bell"),
            "4 Frequency A": (V, 3000.0), "4 Gain A": (V, -5.0),
            "4 Q A": (V, 0.9),
            # A BELL, not a shelf. The first attempt used a +7.5 dB shelf at
            # 7 kHz: highmid landed exactly on the reference median (z 0.0)
            # but a shelf lifts everything above it, so air went to z +1.9 and
            # the extra HF ate 2.6 dB of limiter headroom (LUFS -8.1 -> -10.7).
            # A bell puts the gain in 6-12 kHz where the corpus says hats live
            # and leaves 12-20 kHz alone.
            "8 Filter On A": (E, "On"), "8 Filter Type A": (E, "Bell"),
            "8 Frequency A": (V, 8000.0), "8 Gain A": (V, 5.5),
            "8 Q A": (V, 0.7),
        }, label="CHAT brighten")

    # ---- space: a real reverb per decorative voice
    for name, (dev, wet) in SPACE.items():
        di = b.ensure_effect(tracks[name], dev)
        if di is None:
            continue
        ps.set_many(tracks[name], di, {
            "Room Size": (N, 0.42), "Decay Time": (V, 1400.0),
            "Predelay": (V, 8.0), "Dry/Wet": (N, wet),
            "Cut On": (E, "On"), "In Hi Cut On": (E, "On"),
            "In Lo Cut On": (E, "On"), "Input Freq": (V, 1500.0),
            "Input Width": (N, 0.85), "Stereo Image": (V, 110.0),
        })
    print("space: " + " ".join(f"{k}={int(v[1] * 100)}%" for k, v in SPACE.items()))

    # ---- acid movement
    total = bars * 4
    sweep = [[t, 0.22 + 0.60 * (t / total) ** 1.2] for t in range(0, total)]
    sweep += [[total - 0.5, 0.30]]
    b.live.cmd("set_clip_envelope", track_index=acid, clip_index=0,
               parameter_name="LP Freq", points=sweep, normalized=True)
    res = [[t, 0.55 + 0.25 * ((t // 8) % 2)] for t in range(0, total, 4)]
    b.live.cmd("set_clip_envelope", track_index=acid, clip_index=0,
               parameter_name="LP Res", points=res, normalized=True)

    # ---- master chain + mix
    print("master chain:")
    b.ensure_master_chain()

    # EQ Eight: clear the DC/subsonic, carve the lowmid buildup that buried the
    # first render, and shelf the top back up toward the reference balance.
    ps.set_many(-1, 0, {
        **{"1 Filter On A": (E, "On"), "1 Filter Type A": (E, "High Pass 48dB"),
           "1 Frequency A": (V, 24.0)},
        **{"2 Filter On A": (E, "On"), "2 Filter Type A": (E, "Low Shelf"),
           "2 Frequency A": (V, 78.0), "2 Gain A": (V, -4.5)},
        **{"4 Filter On A": (E, "On"), "4 Filter Type A": (E, "Bell"),
           "4 Frequency A": (V, 260.0), "4 Gain A": (V, -3.5), "4 Q A": (V, 0.9)},
        **{"8 Filter On A": (E, "On"), "8 Filter Type A": (E, "High Shelf"),
           "8 Frequency A": (V, 6500.0), "8 Gain A": (V, 2.0)},
    }, label="EQ Eight")

    # Glue: glue, not squash. Ratio/Attack/Release are stepped indices here,
    # not enums; Range caps how much it is ever allowed to pull down.
    ps.set_many(-1, 1, {"Threshold": (V, -12.0), "Ratio": (N, 0.0),
                        "Attack": (N, 0.6), "Release": (N, 0.5),
                        "Range": (V, 6.0), "Output": (V, 0.0),
                        "Dry/Wet": (N, 1.0)}, label="Glue Compressor")

    # Limiter: a safety ceiling only. Input Gain stays at unity — level comes
    # from the track trims, because driving this is what flattened crest to 6.5.
    # Bass below 120 Hz to mono — stereo sub reads as uncontrolled low end and
    # collapses unpredictably on club systems.
    du = b.ensure_effect(-1, "Utility")
    if du is not None:
        ps.set_many(-1, du, {"Bass Mono": (E, "On"), "Bass Freq": (V, 120.0)},
                    label="Utility (bass mono)")

    # Input Gain was held at unity because driving it once flattened crest to
    # 6.5 dB. That fear was calibrated against a hand-written "crest 10-14"
    # target. The corpus says the Drumcode masters sit at 8.4 dB [7.6..11.1]
    # and -7.3 LUFS; this render sits at 12.3 dB and -12.5. It is not too
    # dynamic to be good, it is unmastered — so the limiter should be driven,
    # and the track trims cannot do it (KICK is already at +3.5 dB and a Live
    # fader stops at +6).
    # 7.0, not 5.0: brightening the closed hat added HF the limiter has to
    # hold down, and LUFS fell -8.1 -> -10.7 with the EQ in. This buys it back
    # without touching the balance the corpus now agrees with.
    ps.set_many(-1, 2, {"Ceiling": (V, -0.6), "Input Gain": (V, 7.0),
                        "Release": (V, 200.0), "Auto": (E, "On"), "Mode": (E, "Standard")},
                label="Limiter")

    # Stereo placement. The render measured +0.98 channel correlation — very
    # nearly mono — which is most of why CLAP scored `space` at 0.03. The pulse
    # voices stay centred; the ornaments spread out around them.
    PAN = {"TICK": -0.55, "WOOD": 0.45, "SCRAPE": -0.35, "BELL": 0.30,
           "PERC": 0.20, "OHAT": -0.20, "CHAT": 0.12, "HAZE": -0.40,
           "THROAT": 0.25}
    for name, pan in PAN.items():
        b.live.cmd("set_track_panning", track_index=tracks[name], panning=pan)
    print("panned: " + " ".join(f"{k}{v:+.2f}" for k, v in PAN.items()))

    for name, (_, db, _, _) in VOICES.items():
        b.live.cmd("set_track_volume", track_index=tracks[name],
                   volume=db_to_live_fader(db + MASTER_TRIM_DB))
    b.live.cmd("set_track_volume", track_index=acid,
               volume=db_to_live_fader(ACID_DB + MASTER_TRIM_DB))
    b.live.cmd("set_track_volume", track_index=bass,
               volume=db_to_live_fader(BASS_DB + MASTER_TRIM_DB))

    for name in list(VOICES) + ["ACID", "BASS"]:
        b.live.cmd("fire_clip", track_index=tracks[name], clip_index=0)
    print("groove v3 firing.")
    return [tracks[n] for n in list(VOICES) + ["ACID", "BASS"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--seed", type=int, default=707)
    a = ap.parse_args()
    main(a.bars, a.seed)
