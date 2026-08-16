#!/usr/bin/env python3
"""Groove ear — reconstruct the rhythm as a readable step grid.

Techno is loop music: fold every onset across the whole render into one 2-bar
(32 x 16th-note) cycle and you get the canonical pattern — hit probability,
velocity, and timing offset per step, per instrument role. Printed as text:

    KICK  |X...X...X...X...|X...X...X...X...|
    HATS  |..x...x...x...x.|..x...x...x...x.|  swing 8ms late

'X' = hits nearly every cycle, 'x' = sometimes (ghost/probability), '.' = no.
That grid IS the groove, in a form a language model can actually read, compare
against references, and edit.

Roles are frequency-band proxies (kick 25-100 Hz, snare/perc 150-2 kHz, hats
5 kHz+). Run it on the demucs drum stem when available — on the full mix the
bass bleeds into the kick row; pass full_mix=True there and the KICK band is
reported as raw low-band activity (label it LOW) instead of pretending to be a
kick channel. On a drum stem the KICK row is kept honest by ATTACK_GATE below,
which is what stops a sub bass from being counted as kicks.
"""
import numpy as np
import librosa

HOP = 256
ROLES = [("KICK", 25, 100), ("PERC", 150, 2000), ("HATS", 5000, 16000)]

# Local-prominence gate per role: (window in beats, fraction of the local max).
# A bare peak-pick with a std-relative threshold reported 4-5 kicks/s on the
# Drumcode drum stems, where four-on-the-floor is 2.2/s — it was calling every
# ripple in a decaying kick a new hit, which smeared the folded grid and made
# every pattern look busier than it is. Requiring a peak to hold most of the
# local maximum fixes it: at these settings the references land on 1.8-2.7
# kicks/s and their 8th-note hats survive intact. The window has to be role-
# sized — half a beat around a kick, a 16th around hats, or the gate deletes
# every offbeat hat as the "weaker" of its pair.
#
# Left at 0.6 for KICK on purpose. Once ATTACK_GATE below took over tail
# rejection, dropping this to 0.4 recovered one more reference (Love Within
# @101s, whose quiet kicks were being eaten as "the weaker of the pair", 6 ->
# 8 hits, 15/18 -> 16/18). It was not worth it: on a full mix, where the
# bassline is still in this band, 0.4 let an offbeat sub bass through and a
# synthetic 4-on-the-floor + offbeat-sub loop read 15 hits instead of 8. One
# extra reference is not worth a false kick on every mix with a staccato bass.
ROLE_GATE = {"KICK": (0.5, 0.6), "PERC": (0.25, 0.5), "HATS": (0.25, 0.5)}

# Attack gate, KICK only: (min rise ratio, frames before, frames after).
#
# The failure that motivated it. The KICK row is a 25-100 Hz band-energy
# proxy, which was fine while the music was drums-only. Add a sub bass at A1
# (55 Hz) and the row counts bass notes as kicks: v4b_bass_level read 22 hits
# per 2-bar cycle against a true four-on-the-floor 8, folding to
# |X.X. XXX. XXX. XXX.|. The same row also counted the swell in a long kick
# tail — the drum-only v3g read 19 — because a ripple riding a decaying tail
# can carry as much absolute flux as the attack that started it.
#
# Both are the same physical fact: a kick is a fast, near-silence-to-full rise;
# a sub-bass note and a tail ripple are comparatively sustained, arriving on
# top of energy that is already there. So compare the band envelope just after
# the peak against the ~35 ms before it and require an actual jump. Measured on
# the 18 reference drum stems and four renders, true kicks rise 4-50x while
# ripples and leaked bass notes rise 0.9-2.2x — a gap wide enough that anything
# in 1.75..3.0 scores identically on the corpus, so this is a plateau, not a
# tuned knob. Deliberately a RATIO, not a level: it does not care how loud the
# kick is, so it survives a breakdown, and it does not care what else is
# playing, so it still works when there is no bassline at all.
#
# What it costs: a kick roll faster than the pre-window cannot clear its own
# predecessor's tail. 35 ms is under a 16th note at any techno tempo, and
# synthetic 8th- and 16th-note kick rolls still come back 16/16 and 32/32.
ATTACK_GATE = {"KICK": (2.5, 6, 3)}


def fold_tempo(t):
    t = float(np.atleast_1d(t)[0])
    while t < 100:
        t *= 2
    while t > 180:
        t /= 2
    return t


def band_flux(y, sr, lo, hi):
    """Band envelope, positive spectral flux, and onset peak frames."""
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    sel = (freqs >= lo) & (freqs < hi)
    if not sel.any():
        return np.array([]), np.array([]), np.array([], dtype=int)
    env = S[sel].sum(axis=0)
    flux = np.maximum(0, np.diff(env, prepend=env[0]))
    if flux.max() <= 0:
        return env, flux, np.array([], dtype=int)
    peaks = librosa.util.peak_pick(flux, pre_max=4, post_max=4, pre_avg=12,
                                   post_avg=12, delta=flux.std() * 0.7, wait=8)
    return env, flux, peaks


def prominence_gate(flux, peaks, sr, tempo, window_beats, frac):
    """Keep peaks that hold `frac` of the largest flux within a local window.

    Threshold-only peak picking cannot tell a second hit from the ripple in
    the first one's decay; comparing against the neighbourhood can.
    """
    if not len(peaks) or not tempo or frac <= 0:
        return peaks
    w = max(1, int((60.0 / tempo * window_beats) * sr / HOP))
    keep = [p for p in peaks
            if flux[p] >= frac * flux[max(0, p - w):p + w + 1].max()]
    return np.array(keep, dtype=int)


def attack_gate(env, peaks, rise, pre, post):
    """Keep peaks whose band envelope actually JUMPS — transient, not swell.

    `flux` is a difference, so it is large whenever a loud thing gets a little
    louder; that is exactly what a sub-bass note and a ripple in a kick tail
    do. The ratio of the envelope after the peak to the envelope just before it
    is not: it asks whether the band went from quiet to loud, which only an
    attack does.
    """
    if not len(peaks) or rise <= 0:
        return peaks
    keep = []
    for p in peaks:
        before = env[max(0, p - pre):p]
        b = float(before.mean()) if before.size else 0.0
        if float(env[p:p + post].max()) >= rise * (b + 1e-9):
            keep.append(p)
    return np.array(keep, dtype=int)


def role_gate(env, flux, peaks, sr, tempo, role, attack=True):
    """Both per-role peak gates, in the order they have to run.

    Prominence first (it is the cheap one and removes most of the tail
    ripple), attack second on what survives. band_onsets and analyze must
    apply exactly the same gates or bar_ear's per-bar grid and groove_ear's
    folded grid disagree about which hits exist.

    `attack=False` is for the full-mix fallback, where the low band is a
    bassline as much as a kick and this row is honestly labelled LOW. Gating
    it for transients there does not recover the kick — measured on
    v4b_bass_level's full mix the sub is loud enough that a real kick only
    lifts 25-100 Hz by 2.2x, under the threshold — it just empties the row and
    reports "no kick" where the truthful answer is "low-band activity".
    """
    if not tempo or not role:
        return peaks
    if role in ROLE_GATE:
        peaks = prominence_gate(flux, peaks, sr, tempo, *ROLE_GATE[role])
    if attack and role in ATTACK_GATE:
        peaks = attack_gate(env, peaks, *ATTACK_GATE[role])
    return peaks


def band_onsets(y, sr, lo, hi, tempo=None, role=None, attack=True):
    """Onset times + strengths from one band's spectral flux."""
    env, flux, peaks = band_flux(y, sr, lo, hi)
    peaks = role_gate(env, flux, peaks, sr, tempo, role, attack)
    if not len(peaks):
        return np.array([]), np.array([])
    t = librosa.frames_to_time(peaks, sr=sr, hop_length=HOP)
    return t, flux[peaks]


def find_downbeat(y, sr, tempo, beats_t):
    """Pick the beat phase (0-3) where the low band hits hardest = beat 1."""
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = S[(freqs >= 25) & (freqs < 100)].sum(axis=0)
    frames = np.clip(librosa.time_to_frames(beats_t, sr=sr, hop_length=512),
                     0, len(low) - 1)
    if len(frames) < 8:
        return beats_t[0] if len(beats_t) else 0.0
    best, best_e = 0, -1
    for phase in range(4):
        e = low[frames[phase::4]].mean() if len(frames[phase::4]) else 0
        if e > best_e:
            best, best_e = phase, e
    return beats_t[best]


def analyze(y, sr, cycle_bars=2, tempo_hint=None, labels=None, full_mix=False):
    """Fold onsets into a cycle_bars-long 16th grid. Returns dict per role.

    The grid is BEAT-SYNCHRONOUS: onsets are placed relative to the tracked
    beat times, not a global tempo scalar. A 0.5% tempo estimation error
    drifts a fixed grid by most of a step over 8 bars and smears every fold;
    tracked beats adapt locally and don't drift.

    Pass full_mix=True when `y` is a mix rather than a drum stem: it turns off
    the KICK attack gate, which assumes the low band is a kick channel. Callers
    that set it should also pass labels=("LOW","MID","HIGH").
    """
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_est, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr,
                                               trim=False)
    beats_t = librosa.frames_to_time(beats, sr=sr)
    if len(beats_t) < 8:
        raise ValueError("too few beats tracked for a groove grid")
    beat_len = float(np.median(np.diff(beats_t)))
    tempo = tempo_hint or fold_tempo(60.0 / beat_len)

    # downbeat phase: which beat (0-3) carries the low-band weight
    t0 = find_downbeat(y, sr, tempo, beats_t)
    phase = int(np.argmin(np.abs(beats_t - t0))) % 4

    n_steps = cycle_bars * 16
    beats_per_cycle = cycle_bars * 4
    n_cycles = max(1, (len(beats_t) - phase) // beats_per_cycle)

    def grid_position(t):
        """(step index in cycle, offset ms) or None if off-grid/outside."""
        i = int(np.searchsorted(beats_t, t)) - 1
        if i < 0 or i >= len(beats_t):
            return None
        local = beats_t[i + 1] - beats_t[i] if i + 1 < len(beats_t) else beat_len
        sub = (t - beats_t[i]) / local * 4.0          # 16ths within this beat
        near = round(sub)
        off = (sub - near) * local / 4.0
        if abs(off) > local / 4.0 * 0.35:             # not on the 16th grid
            return None
        beat_num = i - phase + near // 4
        step_in_beat = int(near) % 4
        idx = (beat_num % beats_per_cycle) * 4 + step_in_beat
        return int(idx % n_steps), off * 1000.0

    # bleed suppression: a kick transient is broadband, so it fires the PERC
    # and HATS detectors too — and in four-on-the-floor the clap lands ON a
    # kick, so time proximity can't discriminate. Self-calibrate instead: for
    # kick-coincident onsets, the ratio own-band-flux / kick-flux clusters at
    # a floor (pure bleed, e.g. the kick's midrange body) with real claps/hats
    # sitting well above it. Estimate the floor from the 25th percentile and
    # keep only coincident onsets that clear ~1.7x that.
    fluxes = {}
    for name, lo, hi in ROLES:
        env, flux, peaks = band_flux(y, sr, lo, hi)
        fluxes[name] = (env, flux, role_gate(env, flux, peaks, sr, tempo, name,
                                             attack=not full_mix))
    kick_flux = fluxes["KICK"][1]
    kick_peaks = fluxes["KICK"][2]

    raw = {}
    for name, lo, hi in ROLES:
        env, flux, peaks = fluxes[name]
        if not len(peaks):
            raw[name] = (np.array([]), np.array([]))
            continue
        if name != "KICK" and len(kick_peaks):
            near = {}
            for p in peaks:
                j = kick_peaks[np.argmin(np.abs(kick_peaks - p))]
                if abs(int(j) - int(p)) <= 2:
                    near[int(p)] = flux[p] / (kick_flux[j] + 1e-12)
            if len(near) >= 4:
                floor = np.percentile(list(near.values()), 25)
                keep = np.array([int(p) not in near or
                                 near[int(p)] > 1.7 * floor for p in peaks])
                peaks = peaks[keep]
            else:  # too few coincidences to calibrate: sustain test fallback
                keep = []
                for p in peaks:
                    if int(p) not in near:
                        keep.append(True)
                        continue
                    onset_e = env[p:p + 2].max() + 1e-12
                    sus = env[p + 2:p + 8].mean() if p + 8 <= len(env) else 0.0
                    keep.append(sus / onset_e >= 0.15)
                peaks = peaks[np.array(keep)]
        raw[name] = (librosa.frames_to_time(peaks, sr=sr, hop_length=HOP),
                     flux[peaks])

    roles = {}
    for name, lo, hi in ROLES:
        times, strengths = raw[name]
        hits = np.zeros(n_steps)
        vel = np.zeros(n_steps)
        offs = [[] for _ in range(n_steps)]
        for t, s in zip(times, strengths):
            pos = grid_position(t)
            if pos is None:
                continue
            idx, off_ms = pos
            hits[idx] += 1
            vel[idx] += s
            offs[idx].append(off_ms)
        prob = hits / n_cycles
        vmax = vel.max() + 1e-9
        roles[name] = {
            "prob": np.clip(prob, 0, 1),
            "vel": vel / vmax,
            "offset_ms": [float(np.median(o)) if o else 0.0 for o in offs],
            "onsets_total": int(len(times)),
        }

    # swing: offbeat-16th timing minus same-role onbeat timing, so systematic
    # onset-detection bias (filter delay, hop quantization) cancels out
    hats = roles.get("HATS", {})
    swing = None
    if hats:
        offbeat = [hats["offset_ms"][i] for i in range(n_steps)
                   if i % 4 == 2 and hats["prob"][i] > 0.3]
        onbeat = [hats["offset_ms"][i] for i in range(n_steps)
                  if i % 4 == 0 and hats["prob"][i] > 0.3]
        # Both halves are required. Without on-beat hits there is nothing to
        # subtract the detector's own bias against, and the raw offbeat offset
        # gets reported as swing: a pattern that plays ONLY off-8ths read as
        # "-17 ms swing" purely from onset-detection lag, and comparing that to
        # references (which do have on-beat hats, so their bias cancels) is
        # comparing a biased number to an unbiased one.
        if offbeat and onbeat:
            swing = float(np.median(offbeat)) - float(np.median(onbeat))

    if labels:  # e.g. ("LOW","MID","HIGH") when analyzing a full mix, where
        # the bass line lives in the kick band and role names would overclaim
        roles = {new: roles[old] for (old, _, _), new in zip(ROLES, labels)}

    return {"tempo": round(tempo, 1), "downbeat_s": round(float(t0), 3),
            "cycle_bars": cycle_bars, "n_cycles": n_cycles,
            "swing_ms": round(swing, 1) if swing is not None else None,
            "roles": roles}


def render_grid(g):
    """The groove as text. Bars separated by |, beats by spaces."""
    n = g["cycle_bars"] * 16
    sw = g.get("swing_ms")
    lines = [f"tempo {g['tempo']} BPM   {g['n_cycles']} cycles folded   " +
             (f"offbeat-16th swing {sw:+.0f} ms" if sw is not None else
              "swing unmeasurable (no on-beat hats to cancel detector bias)")]
    for name, r in g["roles"].items():
        chars = []
        for i in range(n):
            p, v = r["prob"][i], r["vel"][i]
            if p >= 0.65:
                chars.append("X" if v >= 0.5 else "x")
            elif p >= 0.25:
                chars.append("o")                 # ghost / probabilistic hit
            elif p > 0.08:
                chars.append("·")
            else:
                chars.append(".")
        row = "".join(chars)
        bars = "|".join(row[i:i + 16] for i in range(0, n, 16))
        # per-bar beat spacing for readability: group into 4s
        bars = "|".join(" ".join(b[j:j + 4] for j in range(0, 16, 4))
                        for b in bars.split("|"))
        lines.append(f"{name:5s}|{bars}|")
    lines.append("      X=strong x=weak o=sometimes ·=rare  "
                 "(each char = one 16th note)")
    return "\n".join(lines)


def to_json(g):
    return {"tempo": g["tempo"], "swing_ms": g.get("swing_ms"),
            "n_cycles": g["n_cycles"],
            "roles": {k: {"prob": [round(float(p), 2) for p in r["prob"]],
                          "vel": [round(float(v), 2) for v in r["vel"]],
                          "offset_ms": [round(o, 1) for o in r["offset_ms"]],
                          "onsets_total": r["onsets_total"]}
                      for k, r in g["roles"].items()}}


if __name__ == "__main__":
    import sys
    y, sr = librosa.load(sys.argv[1], sr=44100, mono=True)
    print(render_grid(analyze(y, sr)))
