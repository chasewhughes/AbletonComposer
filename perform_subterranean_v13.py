#!/usr/bin/env python3
"""
Subterranean v13 - "Accelerator"
Ben Klock / Marcel Dettmann / Surgeon / Regis Style

BPM: 133 | Key: G minor
Total: ~4:30 runtime (faster than v12)

v13 - ACCELERATED BUILDUP + HARDER DROP:

1. FASTER BUILDUP
   - INTRO: 24 -> 16 bars (compressed)
   - LAYER 1: 24 -> 16 bars (faster layering)
   - BUILD: Steeper energy ramp
   - BREAK: 12 -> 8 bars (tighter)
   - GAP: 1-bar silence before drop

2. HARDER DROP
   - Brief silence before impact (maximum contrast)
   - DROP_CRASH @ -4dB (was -6dB)
   - FX_HITS @ -2dB (was -4dB)
   - STAB + PEAK_LEAD both fire at drop
   - KICK @ -6dB (was -7dB)
   - SUB_BASS @ -8dB (was -10dB)
   - Faster element stacking

All v12 features retained:
- Alpha/Beta spectral carving
- Collision detection
- Track-specific tightness
"""

import os
import sys
import time
import math
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from live_bridge import LiveQuery, DeviceParams, db_to_live_fader  # noqa: E402 (also puts vendored pythonosc on sys.path)
from pythonosc.udp_client import SimpleUDPClient

# =============================================================================
# PROJECT SETTINGS
# =============================================================================
BPM = 133.0
SECONDS_PER_BEAT = 60.0 / BPM
BEATS_PER_BAR = 4.0
MS_PER_BEAT = SECONDS_PER_BEAT * 1000

# =============================================================================
# POLYMETRIC CONSTANTS
# =============================================================================
POLY = {
    "STAB": 7,
    "RIDE": 5,
    "DING": 11,
    "ARPEGGIO": 13,
    "TEXTURE": 9,
    "HATS": 3,
    "SPECTRAL": 4,
    "DEGRADE": 17,
    "VOCAL": 5,
    "VOCAL_ALT": 7,
    "NOISE_RISER": 6,
    "FX_HITS": 11,
    "ATMOSPHERE": 13,
    "STAB_SWAP": 8,
    "DARK_TEXTURE": 9,
}

# =============================================================================
# TRACK MAP
# =============================================================================
T = {
    "KICK": 0,
    "BASS": 1,
    "CLOSED_HATS": 2,
    "DRIVING_HATS": 3,
    "OPEN_HATS": 4,
    "PERCUSSION": 5,
    "STAB": 6,
    "RIDE": 7,
    "ATMOSPHERE": 8,
    "DING": 16,
    "PEAK_LEAD": 19,
    "SUB_BASS": 20,
    "ARPEGGIO": 21,
    "FX_RISER": 9,
    "FX_HITS": 10,
    "FX_DOWNLIFT": 11,
    "NOISE_SWEEP": 14,
    "NOISE_RISER": 17,
    "VOCAL": 12,
    "VOCAL_2": 13,
    "INDUSTRIAL": 15,
    "DARK_TEXTURE": 18,
    "DROP_CRASH": 22,
}

# =============================================================================
# TRACK TIGHTNESS CATEGORIES
# =============================================================================
RIGID_TRACKS = {T["KICK"], T["BASS"], T["SUB_BASS"]}
TIGHT_TRACKS = {T["STAB"], T["PEAK_LEAD"], T["DING"]}

# Scene indices
S = {
    "INTRO": 0,
    "LAYER1": 1,
    "BUILD": 2,
    "BREAK": 3,
    "GAP": 4,
    "PEAK": 5,
    "EVOLVE": 6,
    "OUTRO": 7,
}

# =============================================================================
# DEVICE INDICES
# =============================================================================
DEVICE = {
    "DARK_TEXTURE_EQ": 1,
    "INDUSTRIAL_FILTER": 1,
    "SIMPLER_VOLUME": 30,
    "SIMPLER_FILTER_FREQ": 51,
    "SIMPLER_FILTER_RES": 52,
    "SIMPLER_FILTER_DRIVE": 54,
    "SIMPLER_ATTACK": 36,
    "SIMPLER_DECAY": 37,
    "SIMPLER_RELEASE": 39,
    "SIMPLER_S_START": 3,
    "SIMPLER_S_LENGTH": 4,
    "SATURATOR_DRIVE": 1,
    "SATURATOR_OUTPUT": 6,
    "FILTER_FREQ": 4,
    "FILTER_RES": 5,
    "EQ_HP_FREQ": 1,
    "REVERB_DECAY": 4,
    "REVERB_SIZE": 5,
}

# =============================================================================
# EQ EIGHT PARAMETER NAMES
# =============================================================================
EQ8 = {
    "BAND2_GAIN": "2 Gain A",
    "BAND2_FREQ": "2 Frequency A",
    "BAND2_ON": "2 Filter On A",
    "BAND3_GAIN": "3 Gain A",
    "BAND3_FREQ": "3 Frequency A",
    "BAND3_ON": "3 Filter On A",
}


# =============================================================================
# SPECTRAL CARVER - From v12
# =============================================================================
class SpectralCarver:
    """Alpha/Beta frequency collision management."""

    def __init__(self):
        self._peak_lead_active = False
        self._vocal_active = False
        self._texture_active = False
        self._texture_level_db = -70
        self._industrial_active = False
        self._industrial_level_db = -70
        self._texture_carved_for_lead = False
        self._texture_carved_for_vocal = False
        self._industrial_carved = False
        self._lead_texture_carve = -5.0
        self._vocal_texture_carve = -4.0
        self._vocal_industrial_carve = -3.0
        self._texture_restore_progress = 1.0
        self._industrial_restore_progress = 1.0
        self._kick_hitting = False
        self._subbass_ducked = False

    def set_peak_lead_active(self, active):
        was_active = self._peak_lead_active
        self._peak_lead_active = active
        if was_active and not active:
            self._texture_restore_progress = 0.0

    def set_vocal_active(self, active):
        was_active = self._vocal_active
        self._vocal_active = active
        if was_active and not active:
            self._texture_restore_progress = 0.0
            self._industrial_restore_progress = 0.0

    def set_texture_active(self, active, level_db=-70):
        self._texture_active = active and level_db > -20
        self._texture_level_db = level_db

    def set_industrial_active(self, active, level_db=-70):
        self._industrial_active = active and level_db > -18
        self._industrial_level_db = level_db

    def get_texture_level_threshold(self):
        return -12.0

    def check_vocal_collision(self, texture_level_db):
        if texture_level_db > self.get_texture_level_threshold():
            return False
        return True

    def process_spectral_carving(self, ctl, bar=0):
        if self._peak_lead_active and self._texture_active:
            if not self._texture_carved_for_lead:
                try:
                    ctl.set_param_norm(
                        T["DARK_TEXTURE"],
                        DEVICE["DARK_TEXTURE_EQ"],
                        EQ8["BAND2_FREQ"],
                        0.35
                    )
                    ctl.set_device_param(
                        T["DARK_TEXTURE"],
                        DEVICE["DARK_TEXTURE_EQ"],
                        EQ8["BAND2_GAIN"],
                        self._lead_texture_carve
                    )
                    print(f"    [Spectral] CARVING: PEAK_LEAD active - cutting TEXTURE 400Hz by {self._lead_texture_carve}dB")
                except Exception as e:
                    print(f"    [Spectral] EQ error: {e}")
                self._texture_carved_for_lead = True
                self._texture_restore_progress = 0.0

        elif self._vocal_active and self._texture_active:
            if not self._texture_carved_for_vocal:
                try:
                    ctl.set_param_norm(
                        T["DARK_TEXTURE"],
                        DEVICE["DARK_TEXTURE_EQ"],
                        EQ8["BAND2_FREQ"],
                        0.30
                    )
                    ctl.set_device_param(
                        T["DARK_TEXTURE"],
                        DEVICE["DARK_TEXTURE_EQ"],
                        EQ8["BAND2_GAIN"],
                        self._vocal_texture_carve
                    )
                    print(f"    [Spectral] CARVING: VOCAL active - cutting TEXTURE 300Hz by {self._vocal_texture_carve}dB")
                except Exception as e:
                    print(f"    [Spectral] EQ error: {e}")
                self._texture_carved_for_vocal = True
                self._texture_restore_progress = 0.0

        else:
            if self._texture_carved_for_lead or self._texture_carved_for_vocal:
                self._texture_restore_progress += 0.5
                if self._texture_restore_progress >= 1.0:
                    try:
                        ctl.set_device_param(
                            T["DARK_TEXTURE"],
                            DEVICE["DARK_TEXTURE_EQ"],
                            EQ8["BAND2_GAIN"],
                            0.0
                        )
                        print("    [Spectral] RESTORED: TEXTURE body at 0dB")
                    except Exception as e:
                        print(f"    [Spectral] Restore error: {e}")
                    self._texture_carved_for_lead = False
                    self._texture_carved_for_vocal = False
                    self._texture_restore_progress = 1.0
                else:
                    try:
                        current_cut = self._lead_texture_carve * (1.0 - self._texture_restore_progress)
                        ctl.set_device_param(
                            T["DARK_TEXTURE"],
                            DEVICE["DARK_TEXTURE_EQ"],
                            EQ8["BAND2_GAIN"],
                            current_cut
                        )
                    except:
                        pass

        if self._vocal_active and self._industrial_active:
            if not self._industrial_carved:
                try:
                    ctl.set_param_norm(
                        T["INDUSTRIAL"],
                        DEVICE["INDUSTRIAL_FILTER"],
                        "Frequency",
                        0.4
                    )
                    print(f"    [Spectral] CARVING: VOCAL vs INDUSTRIAL - lowering filter")
                except Exception as e:
                    print(f"    [Spectral] Filter error: {e}")
                self._industrial_carved = True
        else:
            if self._industrial_carved:
                try:
                    ctl.set_param_norm(
                        T["INDUSTRIAL"],
                        DEVICE["INDUSTRIAL_FILTER"],
                        "Frequency",
                        0.6
                    )
                    print("    [Spectral] RESTORED: INDUSTRIAL filter at 0.6")
                except:
                    pass
                self._industrial_carved = False

    def process_sidechain_breathing(self, ctl, kick_level_db):
        if kick_level_db > -8:
            if not self._subbass_ducked:
                try:
                    ctl.set_param_norm(T["SUB_BASS"], 1, "Drive", 0.3)
                except:
                    pass
                self._subbass_ducked = True
        else:
            if self._subbass_ducked:
                try:
                    ctl.set_param_norm(T["SUB_BASS"], 1, "Drive", 0.5)
                except:
                    pass
                self._subbass_ducked = False

    def reset(self):
        self._peak_lead_active = False
        self._vocal_active = False
        self._texture_active = False
        self._industrial_active = False
        self._texture_carved_for_lead = False
        self._texture_carved_for_vocal = False
        self._industrial_carved = False
        self._subbass_ducked = False
        self._texture_restore_progress = 1.0
        self._industrial_restore_progress = 1.0


# =============================================================================
# VOCAL MANGLER
# =============================================================================
class VocalMangler:
    PHASE_PRESETS = {
        "intro": {
            "filter_freq": 0.28,
            "filter_res": 0.6,
            "filter_drive": 12.0,
            "presence": 0.55,
            "fire_interval": 6,  # v13: Faster firing
            "reverb_send": 0.6,
            "description": "Ghost in the machine"
        },
        "layer1": {
            "filter_freq": 0.4,
            "filter_res": 0.5,
            "filter_drive": 14.0,
            "presence": 0.7,
            "fire_interval": 4,  # v13: Faster
            "reverb_send": 0.45,
            "description": "Rhythm element"
        },
        "build": {
            "filter_freq": 0.5,
            "filter_res": 0.55,
            "filter_drive": 16.0,
            "presence": 0.8,
            "fire_interval": 3,  # v13: More urgent
            "reverb_send": 0.3,
            "description": "Rising tension"
        },
        "break": {
            "filter_freq": 0.62,
            "filter_res": 0.7,
            "filter_drive": 10.0,
            "presence": 0.95,
            "fire_interval": 4,  # v13: Tighter
            "reverb_send": 0.5,
            "description": "Exposed alien"
        },
        "gap": {
            "filter_freq": 0.55,
            "filter_res": 0.6,
            "filter_drive": 14.0,
            "presence": 0.85,
            "fire_interval": 3,
            "reverb_send": 0.25,
            "description": "Anticipation"
        },
        "peak": {
            "filter_freq": 0.38,
            "filter_res": 0.45,
            "filter_drive": 18.0,
            "presence": 0.55,
            "fire_interval": 10,
            "reverb_send": 0.2,
            "description": "Textural presence"
        },
        "evolve": {
            "filter_freq": 0.45,
            "filter_res": 0.65,
            "filter_drive": 20.0,
            "presence": 0.65,
            "fire_interval": 5,
            "reverb_send": 0.35,
            "description": "Damaged re-emergence"
        },
        "outro": {
            "filter_freq": 0.25,
            "filter_res": 0.5,
            "filter_drive": 8.0,
            "presence": 0.4,
            "fire_interval": 8,
            "reverb_send": 0.75,
            "description": "Fading memory"
        }
    }

    def __init__(self):
        self._current_phase = "intro"
        self._degradation = 0.0
        self._bars_since_last_fire = 0
        self._total_fires = 0
        self._is_playing = False
        self._load_preset("intro")

    def _load_preset(self, phase):
        preset = self.PHASE_PRESETS.get(phase, self.PHASE_PRESETS["intro"])
        self._filter_freq = preset["filter_freq"]
        self._filter_res = preset["filter_res"]
        self._filter_drive = preset["filter_drive"]
        self._presence = preset["presence"]
        self._fire_interval = preset["fire_interval"]
        self._reverb_send = preset["reverb_send"]
        self._current_phase = phase

    def set_phase(self, phase, ctl=None):
        if phase not in self.PHASE_PRESETS:
            return
        self._load_preset(phase)
        preset = self.PHASE_PRESETS[phase]
        print(f"    [Vocal] === Phase: {phase.upper()} === '{preset['description']}' (presence: {preset['presence']})")
        if ctl:
            self.apply_settings(ctl, T["VOCAL"], 0)
            ctl.set_send(T["VOCAL"], 0, self._reverb_send)

    def set_presence(self, level):
        self._presence = max(0.0, min(1.0, level))

    def increment_degradation(self, amount=0.01):
        self._degradation = min(1.0, self._degradation + amount)

    def get_volume_db(self, base_db=-3):
        presence_cut = (1.0 - self._presence) * 6
        return base_db - presence_cut

    def is_playing(self):
        return self._is_playing

    def set_playing(self, playing):
        self._is_playing = playing
        SC.set_vocal_active(playing)

    def apply_settings(self, ctl, track_idx, device_idx=0):
        freq_wobble = random.uniform(-0.02, 0.02)
        freq = max(0.15, min(0.75, self._filter_freq + freq_wobble))
        drive = self._filter_drive + (self._degradation * 3)
        ctl.set_param_norm(track_idx, device_idx, "Filter Freq", freq)
        ctl.set_param_norm(track_idx, device_idx, "Filter Res", self._filter_res)
        ctl.set_param_native(track_idx, device_idx, "Filter Drive", min(24, drive))

    def mangle_formant(self, ctl, track_idx, device_idx=0, intensity=0.5):
        t = time.time()
        formant_lfo = math.sin(t * 0.7) * 0.12 * intensity
        formant_lfo += math.sin(t * 1.3) * 0.06 * intensity
        target_freq = max(0.15, min(0.75, self._filter_freq + formant_lfo))
        target_res = max(0.3, min(0.9, self._filter_res + (formant_lfo * 0.3)))
        ctl.set_param_norm(track_idx, device_idx, "Filter Freq", target_freq)
        ctl.set_param_norm(track_idx, device_idx, "Filter Res", target_res)

    def should_fire(self, bar):
        self._bars_since_last_fire += 1
        if self._bars_since_last_fire >= self._fire_interval:
            if random.random() < 0.8:
                return True
        return False

    def safe_fire(self, ctl, scene_idx, texture_level_db=-70):
        if not SC.check_vocal_collision(texture_level_db):
            print(f"    [Collision Avoided] Texture @ {texture_level_db:.1f}dB - holding Vocal")
            return False
        return self.fire(ctl, scene_idx)

    def fire(self, ctl, scene_idx):
        ctl.stop_track(T["VOCAL"])
        time.sleep(MT.slop(0.25, T["VOCAL"]))
        ctl.fire_clip(T["VOCAL"], scene_idx)
        ctl.set_volume_db(T["VOCAL"], self.get_volume_db())
        self._bars_since_last_fire = 0
        self._total_fires += 1
        self.set_playing(True)
        print(f"    [Vocal] Fire #{self._total_fires} @ {self.get_volume_db():.1f}dB")
        return True

    def mark_stopped(self):
        self.set_playing(False)

    def process_bar(self, ctl, bar):
        self.apply_settings(ctl, T["VOCAL"], 0)
        ctl.set_volume_db(T["VOCAL"], self.get_volume_db())

    def set_chop_mode(self, mode):
        mode_to_phase = {"sparse": "intro", "rhythmic": "layer1", "percussive": "build", "full": "gap"}
        if mode in mode_to_phase:
            self._load_preset(mode_to_phase[mode])


# =============================================================================
# HUMANIZER
# =============================================================================
class Humanizer:
    def __init__(self, seed=None):
        if seed:
            random.seed(seed)
        self._drift = 0.0
        self._momentum = 0.0

    def lfo(self, bar, frequency=0.2, amplitude=2.0, jitter=0.5):
        base = math.sin(bar * frequency) * amplitude
        error = random.uniform(-jitter, jitter)
        self._momentum += random.uniform(-0.1, 0.1)
        self._momentum *= 0.95
        self._drift += self._momentum
        self._drift = max(-1.0, min(1.0, self._drift))
        return base + error + (self._drift * jitter)

    def drunk_walk(self, current_value, target, step_size=0.02, wobble=0.01):
        direction = 1 if target > current_value else -1
        step = step_size * direction
        noise = random.uniform(-wobble, wobble)
        new_value = current_value + step + noise
        return min(new_value, target) if direction > 0 else max(new_value, target)

    def jitter(self, value, amount=0.05):
        return value + random.uniform(-amount, amount)

    def chance(self, probability=0.5):
        return random.random() < probability

    def vary(self, base_value, variance_percent=10):
        variance = base_value * (variance_percent / 100.0)
        return base_value + random.uniform(-variance, variance)


# =============================================================================
# MICRO-TIMER with Track-Specific Tightness
# =============================================================================
class MicroTimer:
    def __init__(self, max_slop_ms=12):
        self.max_slop_ms = max_slop_ms
        self._last_slop = 0

    def slop(self, intensity=1.0, track_idx=None):
        if track_idx is not None:
            if track_idx in RIGID_TRACKS:
                return 0.0
            elif track_idx in TIGHT_TRACKS:
                max_ms = 2.0 * intensity
            else:
                max_ms = self.max_slop_ms * intensity
        else:
            max_ms = self.max_slop_ms * intensity

        slop_ms = random.uniform(-max_ms * 0.3, max_ms)
        self._last_slop = slop_ms
        return max(0, slop_ms / 1000.0)

    def humanize_fire(self, ctl, track, clip, slop_intensity=0.5):
        delay = self.slop(slop_intensity, track)
        if delay > 0:
            time.sleep(delay)
        ctl.fire_clip(track, clip)

    def rigid_fire(self, ctl, track, clip):
        ctl.fire_clip(track, clip)


# =============================================================================
# SPECTRAL BREATHER
# =============================================================================
class SpectralBreather:
    def __init__(self):
        self._filter_states = {}
        self._kick_intensity = 0.5

    def set_kick_intensity(self, intensity):
        self._kick_intensity = max(0.0, min(1.0, intensity))

    def breathe(self, ctl, track_name, track_idx, device_idx, base_cutoff=0.1):
        kick_influence = self._kick_intensity * 0.4
        movement = H.lfo(time.time(), frequency=0.3, amplitude=0.05, jitter=0.02)
        target_cutoff = base_cutoff + kick_influence + movement
        target_cutoff = max(0.0, min(0.8, target_cutoff))
        current = self._filter_states.get(track_name, base_cutoff)
        new_cutoff = H.drunk_walk(current, target_cutoff, step_size=0.03, wobble=0.01)
        self._filter_states[track_name] = new_cutoff
        ctl.set_param_norm(track_idx, device_idx, "Filter Freq", new_cutoff)
        return new_cutoff


# =============================================================================
# DENSITY MANAGER
# =============================================================================
class DensityManager:
    def __init__(self):
        self._current_levels = {}
        self._density_target = 0.7
        self._db_weights = {
            "KICK": 1.5, "BASS": 1.4, "SUB_BASS": 1.3,
            "STAB": 1.0, "PEAK_LEAD": 1.0, "DING": 0.9, "ARPEGGIO": 0.8, "VOCAL": 1.1,
            "CLOSED_HATS": 0.6, "DRIVING_HATS": 0.5, "OPEN_HATS": 0.7, "RIDE": 0.6, "PERCUSSION": 0.7,
            "ATMOSPHERE": 0.8, "INDUSTRIAL": 0.7, "DARK_TEXTURE": 0.9, "NOISE_SWEEP": 0.5,
        }

    def register_level(self, track_name, level_db):
        self._current_levels[track_name] = level_db

    def get_level(self, track_name):
        return self._current_levels.get(track_name, -70)

    def get_density(self, track_group=None):
        if track_group:
            tracks = track_group
        else:
            tracks = list(self._current_levels.keys())

        total_weighted = 0.0
        max_possible = 0.0

        for track_name in tracks:
            db_level = self._current_levels.get(track_name, -70)
            weight = self._db_weights.get(track_name, 1.0)
            if db_level <= -70:
                linear = 0.0
            else:
                linear = (db_level + 70) / 70.0
                linear = max(0, min(1, linear))
            total_weighted += linear * weight
            max_possible += weight

        if max_possible == 0:
            return 0.0
        return total_weighted / max_possible

    def check_equilibrium(self, ctl):
        suggestions = {}
        groups = {
            "highs": ["CLOSED_HATS", "DRIVING_HATS", "OPEN_HATS", "RIDE"],
            "mids": ["STAB", "DING", "ARPEGGIO", "PEAK_LEAD"],
            "lows": ["KICK", "BASS", "SUB_BASS"],
            "textures": ["ATMOSPHERE", "INDUSTRIAL", "DARK_TEXTURE", "NOISE_SWEEP"],
        }
        thresholds = {
            "highs": {"reduce": 0.75, "increase": 0.15},
            "mids": {"reduce": 0.65, "increase": 0.2},
            "lows": {"reduce": 0.55, "increase": 0.25},
            "textures": {"reduce": 0.6, "increase": 0.15},
        }
        for group_name, tracks in groups.items():
            density = self.get_density(tracks)
            thresh = thresholds.get(group_name, {"reduce": 0.6, "increase": 0.2})
            if density > thresh["reduce"]:
                suggestions[group_name] = "reduce"
            elif density < thresh["increase"]:
                suggestions[group_name] = "increase"
        return suggestions


# =============================================================================
# CHAOS ENGINE
# =============================================================================
class ChaosEngine:
    def __init__(self):
        self._degradation_level = 0.0
        self._hat_degradation = 0.0
        self._chaos_seed = random.random()

    def set_degradation(self, level):
        self._degradation_level = max(0.0, min(1.0, level))

    def increment_degradation(self, amount=0.01):
        self._degradation_level = min(1.0, self._degradation_level + amount)

    def increment_hat_degradation(self, amount=0.005):
        self._hat_degradation = min(1.0, self._hat_degradation + amount)

    def degrade_signal(self, ctl, track_idx, device_idx, intensity=None):
        if intensity is None:
            intensity = self._degradation_level
        drive = intensity * 0.6
        drive_jitter = H.jitter(drive, 0.05)
        ctl.set_param_native(track_idx, device_idx, "Filter Drive", drive_jitter * 24)

    def degrade_hats(self, ctl, hat_tracks, device_idx=1):
        drive = self._hat_degradation * 0.5
        for track_idx in hat_tracks:
            drive_val = H.jitter(drive, 0.03)
            ctl.set_param_native(track_idx, device_idx, "Filter Drive", drive_val * 24)
            if self._hat_degradation > 0.5:
                filter_close = (self._hat_degradation - 0.5) * 0.3
                ctl.set_param_norm(track_idx, 0, "Filter Freq", 1.0 - filter_close)

    def glitch(self, ctl, track_idx, probability=0.05):
        if H.chance(probability * self._degradation_level):
            ctl.set_volume(track_idx, 0.0)
            time.sleep(random.uniform(0.01, 0.05))


# =============================================================================
# BREATHING ARRANGEMENT MANAGER
# =============================================================================
class BreathingArrangement:
    def __init__(self):
        self._active_stab = "stab"
        self._arpeggio_started = False
        self._arpeggio_start_bar = 0
        self._dark_texture_active = False
        self._dark_texture_level = -70

    def get_active_stab(self):
        return self._active_stab

    def get_texture_level(self):
        return self._dark_texture_level

    def swap_stab(self, ctl, scene_idx, bar):
        if self._active_stab == "stab":
            ctl.stop_track(T["STAB"])
            ctl.set_volume(T["STAB"], 0)
            MT.rigid_fire(ctl, T["PEAK_LEAD"], scene_idx)
            ctl.set_volume_db(T["PEAK_LEAD"], -10)
            self._active_stab = "peak_lead"
            SC.set_peak_lead_active(True)
            print(f"    [Breathe] Bar {bar}: STAB -> PEAK-LEAD @ -10dB")
        else:
            ctl.stop_track(T["PEAK_LEAD"])
            ctl.set_volume(T["PEAK_LEAD"], 0)
            SC.set_peak_lead_active(False)
            MT.humanize_fire(ctl, T["STAB"], scene_idx, slop_intensity=0.3)
            ctl.set_volume_db(T["STAB"], -8)
            self._active_stab = "stab"
            print(f"    [Breathe] Bar {bar}: PEAK-LEAD -> STAB @ -8dB")

    def start_arpeggio(self, ctl, scene_idx, bar):
        if not self._arpeggio_started:
            ctl.fire_clip(T["ARPEGGIO"], scene_idx)
            ctl.set_volume_db(T["ARPEGGIO"], -14)
            self._arpeggio_started = True
            self._arpeggio_start_bar = bar
            print(f"    [Breathe] Bar {bar}: ARPEGGIO started (128-beat evolution)")

    def update_arpeggio_volume(self, ctl, bar):
        if self._arpeggio_started:
            bars_elapsed = bar - self._arpeggio_start_bar
            progress = min(1.0, bars_elapsed / 24.0)
            vol = -14 + (progress * 4)
            vol += H.lfo(bar, 0.2, 1, 0.3)
            ctl.set_volume_db(T["ARPEGGIO"], max(-16, min(-8, vol)))

    def dark_texture_swell(self, ctl, scene_idx, bar):
        if not self._dark_texture_active:
            ctl.fire_clip(T["DARK_TEXTURE"], scene_idx)
            ctl.set_volume_db(T["DARK_TEXTURE"], -12)
            self._dark_texture_active = True
            self._dark_texture_level = -12
            SC.set_texture_active(True, -12)
            DM.register_level("DARK_TEXTURE", -12)
            print(f"    [Breathe] Bar {bar}: DARK-TEXTURE drone swell @ -12dB")

    def dark_texture_fade(self, ctl):
        if self._dark_texture_active:
            ctl.stop_track(T["DARK_TEXTURE"])
            ctl.set_volume(T["DARK_TEXTURE"], 0)
            self._dark_texture_active = False
            self._dark_texture_level = -70
            SC.set_texture_active(False)
            DM.register_level("DARK_TEXTURE", -70)

    def climax_both_stabs(self, ctl, scene_idx, bar):
        MT.rigid_fire(ctl, T["STAB"], scene_idx)
        ctl.set_volume_db(T["STAB"], -8)
        MT.rigid_fire(ctl, T["PEAK_LEAD"], scene_idx)
        ctl.set_volume_db(T["PEAK_LEAD"], -10)
        SC.set_peak_lead_active(True)
        self._active_stab = "both"
        print(f"    [Breathe] Bar {bar}: *** CLIMAX - BOTH STABS ***")

    def reset(self):
        self._active_stab = "stab"
        self._arpeggio_started = False
        self._arpeggio_start_bar = 0
        self._dark_texture_active = False
        self._dark_texture_level = -70


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================
H = Humanizer()
MT = MicroTimer(max_slop_ms=12)
SB = SpectralBreather()
DM = DensityManager()
CE = ChaosEngine()
SC = SpectralCarver()
VM = VocalMangler()
BA = BreathingArrangement()

HAT_TRACKS = [T["CLOSED_HATS"], T["DRIVING_HATS"], T["OPEN_HATS"], T["RIDE"]]


# =============================================================================
# OSC CLIENT
# =============================================================================
class AbletonController:
    def __init__(self, host="127.0.0.1", port=11000):
        self.client = SimpleUDPClient(host, port)
        self.params = DeviceParams(LiveQuery(host))

    def send(self, address, *args):
        self.client.send_message(address, list(args))

    def start(self):
        self.send("/live/song/start_playing")

    def stop(self):
        self.send("/live/song/stop_playing")

    def fire_clip(self, track, clip):
        self.send("/live/clip/fire", track, clip)

    def stop_clip(self, track, clip):
        self.send("/live/clip/stop", track, clip)

    def stop_track(self, track):
        self.send("/live/track/stop_all_clips", track)

    def fire_scene(self, scene):
        self.send("/live/scene/fire", scene)

    def set_volume(self, track, vol):
        self.client.send_message("/live/track/set/volume", [track, max(0.0, min(1.0, vol))])

    def set_volume_db(self, track, db):
        self.set_volume(track, db_to_live_fader(db))

    def set_send(self, track, send_idx, level):
        self.send("/live/track/set/send", track, send_idx, max(0.0, min(1.0, level)))

    def set_param_native(self, track, device, param, value):
        """Set a device parameter in its own native units (Hz, dB, ...)."""
        if isinstance(param, str):
            self.send("/live/device/set/parameter/value_by_name", track, device, param, value)
        else:
            self.send("/live/device/set/parameter/value", track, device, param, value)

    def set_param_norm(self, track, device, param, norm):
        """Set a device parameter by normalized 0-1 position of its range.

        Queries and caches the device's min/max via AbletonOSC. Falls back to
        a raw send (old, likely-wrong behavior) only if Live is unreachable,
        and warns when it does.
        """
        scaled = self.params.scale(track, device, param, norm)
        if scaled is None:
            self.set_param_native(track, device, param, norm)
            return
        idx, value = scaled
        self.send("/live/device/set/parameter/value", track, device, idx, value)

    # Back-compat alias: legacy call sites that pass native-unit values.
    set_device_param = set_param_native

    def kill_reverb(self, track, send_idx=0):
        self.set_send(track, send_idx, 0.0)

    def restore_reverb(self, track, send_idx=0, level=0.3):
        self.set_send(track, send_idx, level)


# =============================================================================
# SAFE VOLUME DEFAULTS
# =============================================================================
DEFAULT_VOLUMES_DB = {
    "KICK": -8, "BASS": -10, "CLOSED_HATS": -10, "DRIVING_HATS": -12,
    "OPEN_HATS": -10, "PERCUSSION": -12, "STAB": -10, "RIDE": -12,
    "ATMOSPHERE": -6, "DING": -10, "PEAK_LEAD": -14, "SUB_BASS": -12,
    "ARPEGGIO": -14, "FX_RISER": -16, "FX_HITS": -4, "FX_DOWNLIFT": -14,
    "NOISE_SWEEP": -16, "NOISE_RISER": -8, "VOCAL": -3, "VOCAL_2": -6,
    "INDUSTRIAL": -12, "DARK_TEXTURE": -14, "DROP_CRASH": -8,
}


# =============================================================================
# UTILITIES
# =============================================================================
def sleep_beats(beats):
    time.sleep(beats * SECONDS_PER_BEAT)


def sleep_bars(bars):
    time.sleep(bars * BEATS_PER_BAR * SECONDS_PER_BEAT)


def print_section(name, bars=None):
    print(f"\n{'='*60}")
    print(f"  {name}" + (f" ({bars} bars)" if bars else ""))
    print('='*60)


def print_bar(current, total, msg=""):
    print(f"  Bar {current}/{total} {msg}")


def reset_volumes(ctl, quiet=False):
    if not quiet:
        print("\n  Resetting all track volumes to defaults...")
    for track_name, db_level in DEFAULT_VOLUMES_DB.items():
        if track_name in T:
            ctl.set_volume_db(T[track_name], db_level)
    time.sleep(0.1)
    if not quiet:
        print("  Volumes reset complete.")


def silence_tracks(ctl, tracks_to_silence):
    for track_name in tracks_to_silence:
        if track_name in T:
            ctl.set_volume(T[track_name], 0.0)


def silence_all(ctl):
    """Kill all tracks for maximum contrast before drop."""
    for track_name in T:
        ctl.set_volume(T[track_name], 0.0)
        ctl.stop_track(T[track_name])


# =============================================================================
# PHASE 1: INTRO - COMPRESSED (16 bars, was 24)
# =============================================================================
def phase_intro(ctl):
    print_section("PHASE 1: INTRO - Compressed Build", 16)

    intro_silent = [
        "KICK", "DRIVING_HATS", "OPEN_HATS", "PERCUSSION",
        "STAB", "RIDE", "ATMOSPHERE", "PEAK_LEAD", "SUB_BASS", "ARPEGGIO",
        "FX_RISER", "FX_HITS", "FX_DOWNLIFT", "NOISE_SWEEP", "NOISE_RISER",
        "DARK_TEXTURE", "DROP_CRASH"
    ]
    silence_tracks(ctl, intro_silent)
    silence_tracks(ctl, ["INDUSTRIAL", "DING", "CLOSED_HATS", "BASS"])
    time.sleep(0.1)

    VM.set_phase("intro", ctl)
    SB.set_kick_intensity(0.0)
    SC.reset()

    # --- 2 bars: INDUSTRIAL only (faster!) ---
    print("  [1/4] INDUSTRIAL - Quick texture bed...")
    ctl.fire_clip(T["INDUSTRIAL"], S["INTRO"])
    ctl.set_volume_db(T["INDUSTRIAL"], -14)
    SC.set_industrial_active(True, -14)

    for bar in range(2):
        industrial_vol = -14 + (bar * 2)
        ctl.set_volume_db(T["INDUSTRIAL"], industrial_vol)
        DM.register_level("INDUSTRIAL", industrial_vol)
        SC.process_spectral_carving(ctl, bar)
        sleep_bars(1)
        print_bar(bar + 1, 16, "INDUSTRIAL")

    # --- 2 bars: Add DING + CLOSED-HATS together ---
    print("  [2/4] Adding DING + CLOSED-HATS...")
    ctl.fire_clip(T["DING"], S["INTRO"])
    ctl.set_volume_db(T["DING"], -14)
    MT.humanize_fire(ctl, T["CLOSED_HATS"], S["INTRO"], slop_intensity=0.5)
    ctl.set_volume_db(T["CLOSED_HATS"], -12)

    for bar in range(2):
        ctl.set_volume_db(T["DING"], -14 + (bar * 2))
        ctl.set_volume_db(T["CLOSED_HATS"], -12 + (bar * 1))
        SC.process_spectral_carving(ctl, bar)
        sleep_bars(1)
        print_bar(bar + 3, 16, "INDUSTRIAL + DING + HATS")

    # --- 4 bars: Add BASS + first vocal ---
    print("  [3/4] Adding BASS + distant vocal...")
    MT.rigid_fire(ctl, T["BASS"], S["INTRO"])
    ctl.set_volume_db(T["BASS"], -14)

    texture_level = BA.get_texture_level()
    VM.safe_fire(ctl, S["INTRO"], texture_level)

    for bar in range(4):
        bass_vol = -14 + (bar * 1.5)
        ctl.set_volume_db(T["BASS"], bass_vol)
        DM.register_level("BASS", bass_vol)
        SB.set_kick_intensity(bar / 8)
        VM.process_bar(ctl, bar)
        SC.process_spectral_carving(ctl, bar)
        sleep_bars(1)
        if bar % 2 == 0:
            print_bar(bar + 5, 16, "Bass entering")

    VM.mark_stopped()

    # --- 8 bars: KICK enters with energy ---
    print("  [4/4] >>> KICK ENTERS <<<")

    ctl.set_volume_db(T["KICK"], -9)
    MT.rigid_fire(ctl, T["KICK"], S["INTRO"])
    SB.set_kick_intensity(0.8)

    for bar in range(8):
        kick_vol = H.jitter(-8, 0.3)
        ctl.set_volume_db(T["KICK"], max(-9, min(-7, kick_vol)))
        DM.register_level("KICK", kick_vol)
        SB.breathe(ctl, "INDUSTRIAL", T["INDUSTRIAL"], 0, base_cutoff=0.15)
        VM.process_bar(ctl, bar)

        SC.process_sidechain_breathing(ctl, kick_vol)
        SC.process_spectral_carving(ctl, bar)

        if VM.should_fire(bar):
            texture_level = BA.get_texture_level()
            VM.safe_fire(ctl, S["INTRO"], texture_level)

        sleep_bars(1)
        if bar % 4 == 0:
            print_bar(bar + 9, 16, "FULL INTRO")


# =============================================================================
# PHASE 2: LAYER 1 - COMPRESSED (16 bars, was 24)
# =============================================================================
def phase_layer1(ctl):
    print_section("PHASE 2: LAYER 1 - Fast Layering", 16)

    VM.set_phase("layer1", ctl)

    print("  Adding DRIVING-HATS + OPEN-HATS...")
    MT.humanize_fire(ctl, T["DRIVING_HATS"], S["LAYER1"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["OPEN_HATS"], S["LAYER1"], slop_intensity=0.6)
    ctl.set_volume_db(T["DRIVING_HATS"], -12)
    ctl.set_volume_db(T["OPEN_HATS"], -11)

    print("  >>> NOISE RISER early <<<")
    ctl.fire_clip(T["NOISE_RISER"], S["LAYER1"])
    ctl.set_volume_db(T["NOISE_RISER"], -10)

    for bar in range(4):
        ctl.set_volume_db(T["DRIVING_HATS"], -12 + (bar * 0.5))
        DM.register_level("DRIVING_HATS", -12 + (bar * 0.5))
        DM.register_level("OPEN_HATS", -11)

        if bar == 2:
            ctl.set_volume_db(T["NOISE_RISER"], -6)
            print("    [NOISE_RISER] Swell peak @ -6dB")
        elif bar == 3:
            ctl.stop_track(T["NOISE_RISER"])

        VM.process_bar(ctl, bar)
        SC.process_spectral_carving(ctl, bar)

        if VM.should_fire(bar):
            texture_level = BA.get_texture_level()
            VM.safe_fire(ctl, S["LAYER1"], texture_level)

        sleep_bars(1)
        print_bar(bar + 1, 16, f"Density: {DM.get_density():.2f}")

    print("  >>> Adding STAB + SUB-BASS <<<")

    MT.humanize_fire(ctl, T["STAB"], S["LAYER1"], slop_intensity=0.3)
    ctl.set_volume_db(T["STAB"], -8)
    print("    [STAB] Fired @ -8dB (tight timing)")

    MT.rigid_fire(ctl, T["SUB_BASS"], S["LAYER1"])
    ctl.set_volume_db(T["SUB_BASS"], -11)
    DM.register_level("SUB_BASS", -11)

    for bar in range(8):
        VM.process_bar(ctl, bar + 4)
        SC.process_spectral_carving(ctl, bar)

        if VM.should_fire(bar + 4):
            texture_level = BA.get_texture_level()
            VM.safe_fire(ctl, S["LAYER1"], texture_level)

        sleep_bars(1)
        if bar % 4 == 0:
            print_bar(bar + 5, 16, "Full Layer 1")

    # Fire another riser at end
    print("  >>> NOISE RISER - exit ramp <<<")
    ctl.fire_clip(T["NOISE_RISER"], S["LAYER1"])
    ctl.set_volume_db(T["NOISE_RISER"], -8)

    for bar in range(4):
        riser_vol = -8 + (bar * 2)
        ctl.set_volume_db(T["NOISE_RISER"], riser_vol)
        VM.process_bar(ctl, bar + 12)
        sleep_bars(1)
        print_bar(bar + 13, 16, "Exit ramp")


# =============================================================================
# PHASE 3: BUILD - AGGRESSIVE (12 bars)
# =============================================================================
def phase_build(ctl):
    print_section("PHASE 3: BUILD - Aggressive Tension", 12)

    VM.set_phase("build", ctl)
    CE.set_degradation(0.0)

    print("  >>> CHAOS ENGINE ACTIVATED - FAST RAMP <<<")

    MT.rigid_fire(ctl, T["KICK"], S["BUILD"])
    MT.rigid_fire(ctl, T["BASS"], S["BUILD"])
    MT.humanize_fire(ctl, T["CLOSED_HATS"], S["BUILD"], slop_intensity=0.4)
    MT.humanize_fire(ctl, T["DRIVING_HATS"], S["BUILD"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["OPEN_HATS"], S["BUILD"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["STAB"], S["BUILD"], slop_intensity=0.3)
    MT.rigid_fire(ctl, T["SUB_BASS"], S["BUILD"])

    ctl.set_volume_db(T["KICK"], -7)
    ctl.set_volume_db(T["BASS"], -9)
    ctl.set_volume_db(T["STAB"], -8)
    DM.register_level("KICK", -7)
    DM.register_level("BASS", -9)

    ctl.fire_clip(T["NOISE_RISER"], S["BUILD"])
    ctl.fire_clip(T["FX_RISER"], S["BUILD"])
    ctl.fire_clip(T["DING"], S["BUILD"])
    ctl.set_volume_db(T["NOISE_RISER"], -14)
    ctl.set_volume_db(T["FX_RISER"], -12)
    print("    [RISERS] NOISE_RISER + FX_RISER building...")

    SB.set_kick_intensity(0.9)

    for bar in range(12):
        prog = bar / 12

        # Steeper riser curve (exponential)
        riser_vol = -14 + (prog ** 1.5 * 14)
        ctl.set_volume_db(T["NOISE_RISER"], riser_vol)
        ctl.set_volume_db(T["FX_RISER"], riser_vol + 2)

        # Faster degradation
        CE.increment_degradation(0.03)
        VM.increment_degradation(0.02)

        if bar % 4 == 0:
            CE.degrade_signal(ctl, T["INDUSTRIAL"], 1)
            print(f"    [Chaos] Degradation: {CE._degradation_level:.2f}")

        VM.process_bar(ctl, bar)
        SC.process_spectral_carving(ctl, bar)

        if VM.should_fire(bar):
            texture_level = BA.get_texture_level()
            VM.safe_fire(ctl, S["BUILD"], texture_level)

        sleep_bars(1)
        if bar % 4 == 0:
            print_bar(bar + 1, 12, f"TENSION {int(prog*100)}%")

    print("  >>> TENSION MAXED - PREPARE FOR IMPACT <<<")


# =============================================================================
# PHASE 4: BREAK - TIGHT (8 bars, was 12)
# =============================================================================
def phase_break(ctl):
    print_section("PHASE 4: BREAK - Exposed Alien (TIGHT)", 8)

    print("  >>> KICK OUT - VOCAL EXPOSED <<<")
    ctl.stop_track(T["KICK"])
    ctl.stop_track(T["NOISE_RISER"])
    ctl.stop_track(T["FX_RISER"])
    ctl.set_volume(T["KICK"], 0)

    SB.set_kick_intensity(0.0)

    VM.set_phase("break", ctl)

    MT.rigid_fire(ctl, T["BASS"], S["BREAK"])
    ctl.fire_clip(T["DING"], S["BREAK"])
    ctl.fire_clip(T["NOISE_SWEEP"], S["BREAK"])

    ctl.set_volume_db(T["DING"], -6)
    ctl.set_volume_db(T["NOISE_SWEEP"], -16)
    ctl.set_volume_db(T["BASS"], -12)

    VM.fire(ctl, S["BREAK"])

    for bar in range(8):
        prog = bar / 8

        if bar == 3:
            ctl.fire_clip(T["ATMOSPHERE"], S["BREAK"])
            ctl.set_volume_db(T["ATMOSPHERE"], -6)
            print("    [Ear Candy] ATMOSPHERE swell @ bar 3")
        elif bar == 5:
            ctl.stop_track(T["ATMOSPHERE"])

        VM.process_bar(ctl, bar)
        VM.mangle_formant(ctl, T["VOCAL"], 0, intensity=0.7)
        SC.process_spectral_carving(ctl, bar)

        if VM.should_fire(bar):
            VM.fire(ctl, S["BREAK"])

        sweep_vol = -16 + (prog * 12)
        ctl.set_volume_db(T["NOISE_SWEEP"], sweep_vol)

        sleep_bars(1)
        if bar % 4 == 0:
            print_bar(bar + 1, 8, "Break - Exposed alien")


# =============================================================================
# PHASE 5: GAP - SILENCE BEFORE IMPACT (2 bars)
# =============================================================================
def phase_gap(ctl):
    print_section("PHASE 5: GAP - SILENCE TO IMPACT", 2)

    VM.set_phase("gap", ctl)

    # Fire risers first
    ctl.fire_clip(T["FX_RISER"], S["GAP"])
    ctl.fire_clip(T["NOISE_RISER"], S["GAP"])
    ctl.set_volume_db(T["FX_RISER"], -4)
    ctl.set_volume_db(T["NOISE_RISER"], -2)
    print("    [RISERS] FX_RISER @ -4dB, NOISE_RISER @ -2dB")

    print("  Riser PEAK...")
    sleep_beats(3)

    # === SILENCE FOR MAXIMUM CONTRAST ===
    print("  >>> TOTAL SILENCE - 1 BEAT <<<")
    silence_all(ctl)
    sleep_beats(1)

    # === THE DROP ===
    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("  ║                    >>> D R O P <<<                        ║")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    # DROP_CRASH first - LOUD
    ctl.fire_clip(T["DROP_CRASH"], S["PEAK"])
    ctl.set_volume_db(T["DROP_CRASH"], -4)
    print("  >>> DROP_CRASH @ -4dB <<<")

    # FX_HITS - MASSIVE
    ctl.fire_clip(T["FX_HITS"], S["PEAK"])
    ctl.set_volume_db(T["FX_HITS"], -2)
    print("  >>> FX_HITS @ -2dB <<<")

    # KICK - HARD
    ctl.set_volume_db(T["KICK"], -6)
    MT.rigid_fire(ctl, T["KICK"], S["PEAK"])
    print("  >>> KICK RIGID @ -6dB <<<")

    # BASS - immediately
    MT.rigid_fire(ctl, T["BASS"], S["PEAK"])
    ctl.set_volume_db(T["BASS"], -8)
    DM.register_level("KICK", -6)
    DM.register_level("BASS", -8)

    # SUB_BASS - HEAVY
    MT.rigid_fire(ctl, T["SUB_BASS"], S["PEAK"])
    ctl.set_volume_db(T["SUB_BASS"], -8)
    print("  >>> SUB_BASS @ -8dB (HEAVY) <<<")

    # BOTH STABS at once for maximum impact
    MT.rigid_fire(ctl, T["STAB"], S["PEAK"])
    ctl.set_volume_db(T["STAB"], -7)
    MT.rigid_fire(ctl, T["PEAK_LEAD"], S["PEAK"])
    ctl.set_volume_db(T["PEAK_LEAD"], -9)
    BA._active_stab = "both"
    SC.set_peak_lead_active(True)
    print("  >>> STAB @ -7dB + PEAK-LEAD @ -9dB (BOTH!) <<<")

    # Hats
    MT.humanize_fire(ctl, T["CLOSED_HATS"], S["PEAK"], slop_intensity=0.4)
    MT.humanize_fire(ctl, T["DRIVING_HATS"], S["PEAK"], slop_intensity=0.5)
    ctl.set_volume_db(T["CLOSED_HATS"], -9)
    ctl.set_volume_db(T["DRIVING_HATS"], -10)

    time.sleep(0.3)
    ctl.stop_track(T["FX_HITS"])

    print("  >>> DROP FIRED - Maximum intensity <<<")

    sleep_bars(1)


# =============================================================================
# PHASE 6: PEAK - Full Power
# =============================================================================
def phase_peak(ctl):
    print_section("PHASE 6: *** PEAK *** - FULL POWER", 48)

    print("  >>> SPECTRAL CARVING ACTIVE <<<")

    VM.set_phase("peak", ctl)
    BA.reset()
    BA._active_stab = "both"
    SC.reset()
    SC.set_peak_lead_active(True)

    ctl.kill_reverb(T["STAB"], 0)
    ctl.kill_reverb(T["RIDE"], 0)
    ctl.kill_reverb(T["DING"], 0)
    ctl.kill_reverb(T["ATMOSPHERE"], 0)

    SB.set_kick_intensity(1.0)

    MT.humanize_fire(ctl, T["PERCUSSION"], S["PEAK"], slop_intensity=0.6)
    MT.humanize_fire(ctl, T["RIDE"], S["PEAK"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["OPEN_HATS"], S["PEAK"], slop_intensity=0.6)
    ctl.fire_clip(T["DING"], S["PEAK"])
    ctl.fire_clip(T["INDUSTRIAL"], S["PEAK"])
    SC.set_industrial_active(True, -12)

    BA.start_arpeggio(ctl, S["PEAK"], 0)

    ctl.set_volume_db(T["KICK"], -6)
    ctl.set_volume_db(T["BASS"], -8)
    ctl.set_volume_db(T["CLOSED_HATS"], -9)
    ctl.set_volume_db(T["DRIVING_HATS"], -10)
    ctl.set_volume_db(T["OPEN_HATS"], -10)
    ctl.set_volume_db(T["PERCUSSION"], -10)
    ctl.set_volume_db(T["RIDE"], -11)
    ctl.set_volume_db(T["DING"], -10)
    ctl.set_volume_db(T["SUB_BASS"], -8)
    ctl.set_volume_db(T["INDUSTRIAL"], -12)

    DM.register_level("KICK", -6)
    DM.register_level("BASS", -8)
    DM.register_level("SUB_BASS", -8)

    sleep_beats(2)

    ctl.stop_track(T["DROP_CRASH"])

    print("  Ramping reverb back...")
    for beat in range(4):
        prog = beat / 4
        reverb_level = prog * 0.25
        ctl.set_send(T["STAB"], 0, reverb_level)
        ctl.set_send(T["RIDE"], 0, reverb_level * 0.8)
        ctl.set_send(T["DING"], 0, reverb_level + 0.1)
        sleep_beats(1)

    # After 4 bars, switch from "both" to alternating
    print("  >>> After initial impact, beginning stab alternation <<<")

    for bar in range(2, 48):
        # BREATHING - STAB/PEAK-LEAD alternation (start at bar 8)
        if bar == 8:
            # Transition from "both" to single stab
            ctl.stop_track(T["STAB"])
            ctl.set_volume(T["STAB"], 0)
            BA._active_stab = "peak_lead"
            print(f"    [Breathe] Bar {bar}: Transitioning to alternation mode")

        if bar % POLY["STAB_SWAP"] == 0 and bar > 8:
            if bar == 32:
                BA.climax_both_stabs(ctl, S["PEAK"], bar)
            else:
                BA.swap_stab(ctl, S["PEAK"], bar)

        BA.update_arpeggio_volume(ctl, bar)

        if bar % POLY["DARK_TEXTURE"] == 0 and bar > 4:
            BA.dark_texture_swell(ctl, S["PEAK"], bar)
            if BA._active_stab == "peak_lead" or BA._active_stab == "both":
                print(f"    [v13] COLLISION: PEAK_LEAD + DARK_TEXTURE active!")
        elif bar % POLY["DARK_TEXTURE"] == 4:
            BA.dark_texture_fade(ctl)

        SC.process_spectral_carving(ctl, bar)

        if bar % POLY["RIDE"] == 0:
            ctl.set_volume_db(T["RIDE"], H.vary(-11, 12))

        if bar % POLY["NOISE_RISER"] == 0 and bar > 4:
            ctl.fire_clip(T["NOISE_RISER"], S["PEAK"])
            ctl.set_volume_db(T["NOISE_RISER"], -10)
            print(f"    [Ear Candy] Noise riser swell @ bar {bar}")
        elif bar % POLY["NOISE_RISER"] == 2:
            ctl.set_volume_db(T["NOISE_RISER"], -4)
        elif bar % POLY["NOISE_RISER"] == 4:
            ctl.stop_track(T["NOISE_RISER"])

        if bar % POLY["FX_HITS"] == 0 and bar > 6:
            ctl.fire_clip(T["FX_HITS"], S["PEAK"])
            ctl.set_volume_db(T["FX_HITS"], -3)
            print(f"    [Ear Candy] FX_HITS @ bar {bar} @ -3dB")
        elif bar % POLY["FX_HITS"] == 1:
            ctl.stop_track(T["FX_HITS"])

        if bar % POLY["ATMOSPHERE"] == 0 and bar > 8:
            ctl.fire_clip(T["ATMOSPHERE"], S["PEAK"])
            ctl.set_volume_db(T["ATMOSPHERE"], -6)
            print(f"    [Ear Candy] ATMOSPHERE swell @ bar {bar} @ -6dB")
        elif bar % POLY["ATMOSPHERE"] == 3:
            ctl.stop_track(T["ATMOSPHERE"])

        CE.increment_hat_degradation(0.008)
        VM.increment_degradation(0.005)
        if bar % 4 == 0:
            CE.degrade_hats(ctl, HAT_TRACKS, device_idx=1)

        VM.process_bar(ctl, bar)

        if VM.should_fire(bar):
            texture_level = BA.get_texture_level()
            if VM.safe_fire(ctl, S["PEAK"], texture_level):
                pass

        kick_vol = -6 + H.lfo(bar, 0.15, 0.4, 0.2)
        ctl.set_volume_db(T["KICK"], max(-7, min(-5, kick_vol)))
        DM.register_level("KICK", kick_vol)

        SC.process_sidechain_breathing(ctl, kick_vol)

        if bar == 24:
            ctl.fire_clip(T["DROP_CRASH"], S["PEAK"])
            ctl.set_volume_db(T["DROP_CRASH"], -6)
            print("    [Impact] DROP_CRASH @ bar 24")
        elif bar == 26:
            ctl.stop_track(T["DROP_CRASH"])

        sleep_bars(1)
        if bar % 8 == 0:
            active = BA.get_active_stab()
            density = DM.get_density()
            print_bar(bar + 1, 48, f"PEAK [{active.upper()}] density:{density:.2f}")


# =============================================================================
# PHASE 7: EVOLVE
# =============================================================================
def phase_evolve(ctl):
    print_section("PHASE 7: EVOLVE - Sustained Energy", 32)

    VM.set_phase("evolve", ctl)
    BA.reset()

    MT.rigid_fire(ctl, T["KICK"], S["EVOLVE"])
    MT.rigid_fire(ctl, T["BASS"], S["EVOLVE"])
    ctl.set_volume_db(T["KICK"], -7)
    ctl.set_volume_db(T["BASS"], -9)
    DM.register_level("KICK", -7)
    DM.register_level("BASS", -9)
    sleep_bars(2)

    MT.humanize_fire(ctl, T["DRIVING_HATS"], S["EVOLVE"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["OPEN_HATS"], S["EVOLVE"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["PERCUSSION"], S["EVOLVE"], slop_intensity=0.6)
    sleep_bars(2)

    MT.humanize_fire(ctl, T["RIDE"], S["EVOLVE"], slop_intensity=0.5)
    MT.humanize_fire(ctl, T["STAB"], S["EVOLVE"], slop_intensity=0.3)
    ctl.set_volume_db(T["STAB"], -8)
    BA._active_stab = "stab"
    SC.set_peak_lead_active(False)
    print("  >>> Starting EVOLVE with STAB <<<")

    MT.rigid_fire(ctl, T["SUB_BASS"], S["EVOLVE"])
    sleep_bars(2)

    BA.start_arpeggio(ctl, S["EVOLVE"], 6)

    ctl.fire_clip(T["INDUSTRIAL"], S["EVOLVE"])
    ctl.fire_clip(T["DING"], S["EVOLVE"])
    SC.set_industrial_active(True, -12)

    for bar in range(6, 32):
        if bar % POLY["STAB_SWAP"] == 0 and bar > 6:
            BA.swap_stab(ctl, S["EVOLVE"], bar)

        BA.update_arpeggio_volume(ctl, bar)

        if bar % POLY["DARK_TEXTURE"] == 0 and bar > 8:
            BA.dark_texture_swell(ctl, S["EVOLVE"], bar)
        elif bar % POLY["DARK_TEXTURE"] == 4:
            BA.dark_texture_fade(ctl)

        SC.process_spectral_carving(ctl, bar)

        if bar % POLY["RIDE"] == 0:
            ctl.set_volume_db(T["RIDE"], H.vary(-11, 12))

        if bar % POLY["DING"] == 0:
            ctl.set_send(T["DING"], 1, H.vary(0.35, 25))

        if bar % POLY["NOISE_RISER"] == 0 and bar > 8:
            ctl.fire_clip(T["NOISE_RISER"], S["EVOLVE"])
            ctl.set_volume_db(T["NOISE_RISER"], -10)
        elif bar % POLY["NOISE_RISER"] == 2:
            ctl.set_volume_db(T["NOISE_RISER"], -4)
        elif bar % POLY["NOISE_RISER"] == 4:
            ctl.stop_track(T["NOISE_RISER"])

        if bar % POLY["FX_HITS"] == 0 and bar > 10:
            ctl.fire_clip(T["FX_HITS"], S["EVOLVE"])
            ctl.set_volume_db(T["FX_HITS"], -3)
        elif bar % POLY["FX_HITS"] == 1:
            ctl.stop_track(T["FX_HITS"])

        if bar % POLY["ATMOSPHERE"] == 0 and bar > 12:
            ctl.fire_clip(T["ATMOSPHERE"], S["EVOLVE"])
            ctl.set_volume_db(T["ATMOSPHERE"], -6)
        elif bar % POLY["ATMOSPHERE"] == 3:
            ctl.stop_track(T["ATMOSPHERE"])

        CE.increment_hat_degradation(0.012)
        VM.increment_degradation(0.008)
        if bar % 4 == 0:
            CE.degrade_hats(ctl, HAT_TRACKS, device_idx=1)

        VM.process_bar(ctl, bar)

        if VM.should_fire(bar):
            texture_level = BA.get_texture_level()
            VM.safe_fire(ctl, S["EVOLVE"], texture_level)

        kick_vol = DM.get_level("KICK")
        SC.process_sidechain_breathing(ctl, kick_vol)

        if bar == 20:
            ctl.fire_clip(T["DROP_CRASH"], S["EVOLVE"])
            ctl.set_volume_db(T["DROP_CRASH"], -8)
            print("    [Impact] DROP_CRASH @ bar 20")
        elif bar == 22:
            ctl.stop_track(T["DROP_CRASH"])

        sleep_bars(1)
        if bar % 8 == 0:
            active = BA.get_active_stab()
            print_bar(bar + 1, 32, f"EVOLVING [{active.upper()}]")


# =============================================================================
# PHASE 8: OUTRO
# =============================================================================
def phase_outro(ctl):
    print_section("PHASE 8: OUTRO - Fading Memory", 24)

    VM.set_phase("outro", ctl)
    SC.reset()

    MT.rigid_fire(ctl, T["KICK"], S["OUTRO"])
    MT.rigid_fire(ctl, T["BASS"], S["OUTRO"])
    MT.humanize_fire(ctl, T["CLOSED_HATS"], S["OUTRO"], slop_intensity=0.4)
    ctl.fire_clip(T["INDUSTRIAL"], S["OUTRO"])
    ctl.fire_clip(T["DING"], S["OUTRO"])

    ctl.set_volume_db(T["KICK"], -8)
    ctl.set_volume_db(T["BASS"], -10)

    phase_out_schedule = {
        3: [T["ARPEGGIO"], T["PEAK_LEAD"], T["FX_HITS"], T["FX_DOWNLIFT"]],
        6: [T["RIDE"], T["PERCUSSION"], T["ATMOSPHERE"], T["DARK_TEXTURE"]],
        9: [T["STAB"], T["SUB_BASS"]],
        12: [T["OPEN_HATS"], T["DRIVING_HATS"]],
        18: [T["INDUSTRIAL"], T["DING"]],
    }

    for bar in range(24):
        if bar in phase_out_schedule:
            tracks_to_stop = phase_out_schedule[bar]
            for track in tracks_to_stop:
                ctl.stop_track(track)
                ctl.set_volume(track, 0)
            print(f"  Bar {bar}: Phasing out {len(tracks_to_stop)} tracks")

        VM.process_bar(ctl, bar)

        if VM.should_fire(bar) and bar < 16:
            VM.fire(ctl, S["OUTRO"])

        if bar >= 12:
            close_prog = (bar - 12) / 12
            SB.set_kick_intensity(1.0 - close_prog)

        if bar >= 18:
            fade_prog = (bar - 18) / 6
            fade_db = (fade_prog ** 1.2) * 20 + H.jitter(0, 0.5)
            ctl.set_volume_db(T["KICK"], -8 - fade_db)
            ctl.set_volume_db(T["BASS"], -10 - fade_db)
            ctl.set_volume_db(T["CLOSED_HATS"], -10 - fade_db)

        sleep_bars(1)
        if bar % 6 == 0:
            print_bar(bar + 1, 24)

    print("  >>> END - Voice returns to the underground <<<")


# =============================================================================
# MAIN
# =============================================================================
def run_performance():
    print("\n" + "=" * 60)
    print("  SUBTERRANEAN v13 - 'Accelerator'")
    print("  Surgeon / Regis / Ancient Methods Style")
    print("  BPM: 133 | Key: G minor")
    print("=" * 60)
    print("\nv13 - ACCELERATED BUILDUP + HARDER DROP:")
    print("  1. FASTER BUILDUP:")
    print("     - INTRO: 24 -> 16 bars (compressed)")
    print("     - LAYER 1: 24 -> 16 bars (faster layering)")
    print("     - BUILD: Steeper energy ramp")
    print("     - BREAK: 12 -> 8 bars (tighter)")
    print("     - GAP: 1-beat silence before impact")
    print("  2. HARDER DROP:")
    print("     - Total silence before impact (contrast)")
    print("     - DROP_CRASH @ -4dB (was -6dB)")
    print("     - FX_HITS @ -2dB (was -4dB)")
    print("     - STAB + PEAK_LEAD BOTH fire together")
    print("     - KICK @ -6dB (was -7dB)")
    print("     - SUB_BASS @ -8dB (was -10dB)")
    print("-" * 60)
    print("\nPerformance Structure:")
    print("  1. INTRO      - Compressed build (16 bars)")
    print("  2. LAYER 1    - Fast layering (16 bars)")
    print("  3. BUILD      - Aggressive tension (12 bars)")
    print("  4. BREAK      - Tight alien exposure (8 bars)")
    print("  5. GAP        - SILENCE -> MASSIVE DROP (2 bars)")
    print("  6. PEAK       - Full power (48 bars)")
    print("  7. EVOLVE     - Sustained energy (32 bars)")
    print("  8. OUTRO      - Fading memory (24 bars)")
    print("-" * 60)
    print("  Total: ~158 bars (~4:30 at 133 BPM)")
    print("=" * 60)

    input("\nPress ENTER to start performance...")

    ctl = AbletonController("127.0.0.1", 11000)

    try:
        ctl.start()

        phase_intro(ctl)
        phase_layer1(ctl)
        phase_build(ctl)
        phase_break(ctl)
        phase_gap(ctl)
        phase_peak(ctl)
        phase_evolve(ctl)
        phase_outro(ctl)

        ctl.stop()

    except KeyboardInterrupt:
        print("\n\n>>> Performance interrupted <<<")
        print("  Restoring safe volume levels...")
        reset_volumes(ctl, quiet=True)
        ctl.stop()
        print("  Volumes restored. Safe to restart.")

    print("\n" + "=" * 60)
    print("  Performance Complete!")
    print("=" * 60)


def run_reset_only():
    print("\n" + "=" * 60)
    print("  VOLUME RESET MODE")
    print("=" * 60)
    ctl = AbletonController("127.0.0.1", 11000)
    reset_volumes(ctl)
    print("\n" + "=" * 60)
    print("  All volumes restored!")
    print("=" * 60)


def print_usage():
    print("""
Usage: python perform_subterranean_v13.py [options]

Options:
  (no args)    Run the full performance
  --reset      Reset all track volumes to safe defaults
  --help       Show this help message

v13 - ACCELERATOR:
  1. Faster Buildup:
     - INTRO compressed from 24 to 16 bars
     - LAYER 1 compressed from 24 to 16 bars
     - BUILD with steeper energy ramp
     - BREAK tightened from 12 to 8 bars
     - Total silence before drop for maximum contrast

  2. Harder Drop:
     - 1-beat silence before impact
     - DROP_CRASH @ -4dB (louder)
     - FX_HITS @ -2dB (massive)
     - STAB + PEAK_LEAD both fire together
     - KICK @ -6dB, SUB_BASS @ -8dB (heavier)

Total runtime: ~4:30 (was ~5:45)
""")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--reset", "-r", "reset"):
            run_reset_only()
        elif arg in ("--help", "-h", "help"):
            print_usage()
        else:
            print(f"Unknown option: {arg}")
            print_usage()
    else:
        run_performance()
