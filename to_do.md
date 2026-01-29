# Adam Beyer Style Flagship Techno Track - Production Plan

## Track Concept: "Subterranean"
**BPM:** 130 | **Key:** G minor | **Style:** Peak-time techno with false drops and constant evolution

---

## Production Philosophy (From Skills)
- **Arrangement Intelligence:** False drops, overlapping energy waves, never static
- **Sound Design:** Three-layer kicks, frequency-separated elements
- **Groove:** MPC swing (62%), micro-timing offsets (-10ms hats, +18ms open hats)
- **Automation:** Exponential filter sweeps, complementary motion
- **Mix:** Kick dominates sub, bass high-passed at 60Hz, dynamic EQ

---

## Phase 1: Track Setup
- [x] Read all skill documentation
- [x] Analyze sample library for selection
- [ ] Create track structure (10 tracks)
- [ ] Set up return tracks (Reverb, Delay)
- [ ] Load Simpler on sample tracks

## Phase 2: Sound Selection & Layering

### Kick Layers (Three-Layer Rule)
| Layer | Sample | Purpose | Processing |
|-------|--------|---------|------------|
| Transient | BOS_BRT_Kick_Rumble_One_Shot_Bern.wav | Click/attack (2kHz+) | HP @ 2kHz, short decay |
| Body | BOS_DHT_Kick_One_Shot_Rumble_Hard.wav | Character (100-500Hz) | BP 100-500Hz |
| Sub | BOS_DHT_Kick_One_Shot_Rumble_Massive.wav | Weight (40-100Hz) | LP @ 100Hz, mono |

### Other Elements
| Element | Sample | Notes |
|---------|--------|-------|
| Bass | Operator synth (G1 sine) | Rolling 16th pattern, sidechained |
| Closed Hat | From browser | 16th notes, -10ms nudge |
| Open Hat | BOS_HGT_Drum_Hat_Open_One_Shot_Parka.wav | Upbeats, +18ms nudge |
| Stab | TA_USC_SYNTH_STAB_BEAM_Gm.wav | Filtered entry |
| Atmosphere | ff_dwt_130_atmosphere_loop_ripper.wav | 130 BPM match |
| Ride | From browser | Peak sections only |

---

## Phase 3: Scene-by-Scene Arrangement (Charlotte de Witte / Adam Beyer Style)

### Scene 1: Immediate Impact (Bars 1-32) - 32 bars
**Philosophy:** "Start strong, not quiet"
- [x] Elements: Kick (layered) + Bass (filtered) + Closed Hats
- [ ] Bass filter at 300Hz (dark, mysterious)
- [ ] Groove: No swing yet (establish foundation)
- **Bar 17:** Add subtle percussion variation

### Scene 2: First Layer (Bars 33-64) - 32 bars
**Philosophy:** "Add ONE element, not everything"
- [ ] Add: Filtered Stab (keep dark/mysterious)
- [ ] Open hats enter with swing
- [ ] Bass filter opens slightly to 500Hz
- **Bar 49:** First micro-variation in stab pattern

### Scene 3: False Build (Bars 65-96) - 32 bars
**Philosophy:** "Create expectation but don't deliver"
- [ ] Add: Atmosphere texture
- [ ] Add: Riser FX (bar 80-96)
- [ ] Filter automation: HP on drums begins
- [ ] At bar 96: DON'T drop - subvert expectations
- **Key moment:** Tension without release

### Scene 4: Breakdown Fake-Out (Bars 97-128) - 32 bars
**Philosophy:** "Remove kick/bass BUT keep energy"
- [ ] REMOVE: Kick and Bass (obvious breakdown)
- [ ] KEEP: Hats with groove, atmosphere
- [ ] ADD: White noise texture, tension elements
- [ ] Reverb sends increase significantly
- **Goal:** Create "vacuum" feeling before real impact

### Scene 5: False Drop (Bars 129-160) - 32 bars
**Philosophy:** "Kick returns but filtered/altered"
- [ ] Kick returns with HIGH-PASS filter (not full)
- [ ] Bass in half-time or heavily filtered
- [ ] Add unexpected element (industrial texture)
- [ ] Audience thinks: "That wasn't the real drop"
- **Twist:** Subvert the subversion

### Scene 6: REAL Peak (Bars 161-208) - 48 bars (extended)
**Philosophy:** "Maximum energy - but evolved"
- [ ] ALL elements active with variations
- [ ] Ride cymbal at full velocity (FINALLY)
- [ ] Bass filter FULLY open
- [ ] Stab pattern CHANGED (not same as Scene 2)
- [ ] Add polymetric percussion (5/16 loop)
- **Payoff:** Everything listeners waited for, but evolved

### Scene 7: Maintain & Evolve (Bars 209-256) - 48 bars
**Philosophy:** "Don't cool down, EVOLVE"
- [ ] Swap polymetric patterns (5/16 becomes 7/16)
- [ ] Change bass pattern (different rhythm, same notes)
- [ ] Filter automation creates movement
- [ ] Keep ride cymbal (maintain energy)
- **No reduction:** Variation only

### Scene 8: DJ Tool Outro (Bars 257-288) - 32 bars
**Philosophy:** "Professional exit"
- [ ] Strip to: Kick + Bass + Minimal Hats
- [ ] Remove: All FX, atmosphere, stabs
- [ ] Keep groove locked for next DJ
- **Clean mix-out point**

---

## Phase 4: Groove & Timing

### Micro-Timing Offsets
| Element | Offset | Effect |
|---------|--------|--------|
| Kick | 0ms | Anchor (grid-locked) |
| Closed Hats | -10ms | Rushing/urgency |
| Open Hats | +18ms | Dragging/swing |
| Claps/Snares | +25ms | Heavy/weighted |
| Bass | +2ms | Slight glue with kick |

### MPC Swing
- **Amount:** 62% (looser than triplets, funkier)
- **Timing:** 15%
- **Velocity:** 12%
- **Apply to:** Hi-hats, percussion

### Polyrhythmic Elements
- Scene 6: 5/16 percussion loop (resolves every 5 bars)
- Scene 7: 7/16 percussion loop (resolves every 7 bars)

---

## Phase 5: Automation

### Filter Automation
| Scene | Element | Start | End | Curve |
|-------|---------|-------|-----|-------|
| 1-2 | Bass | 300Hz | 500Hz | Linear |
| 3 | Drums HP | 20Hz | 150Hz | Exponential |
| 3 | Bass | 500Hz | 1.2kHz | Exponential |
| 5 | Kick HP | 200Hz | 60Hz | Snap |
| 6 | Bass | 60Hz | Full | Instant |

### Volume Automation
- Atmosphere: 8-bar fade in (logarithmic)
- Riser FX: 16-bar exponential build
- Scene 4: Hats +2dB (compensate for missing kick)

### Send Automation
- Scene 4: Reverb send 20% → 60%
- Scene transitions: 1-bar reverb throws

---

## Phase 6: Mix & Processing

### EQ Carving (Kick Dominates Sub)
| Element | High-Pass | Low-Pass | Cuts |
|---------|-----------|----------|------|
| Kick | 30Hz | - | 200-300Hz (-3dB boxiness) |
| Bass | 60Hz | 500Hz | - |
| Stabs | 300Hz | - | - |
| Hats | 4-8kHz | - | - |
| Atmosphere | 200Hz | 10kHz | - |

### Bus Processing
- **Low-End Bus (Kick+Bass):** Glue comp (2:1, 30ms attack), tape saturation, mono <100Hz
- **Drum Bus:** Glue comp (3:1), console saturation

### Sidechain
- Bass → Kick: Threshold -18dB, Ratio 4:1, Attack 0.01ms

---

## Phase 7: Validation Checklist

### Arrangement Intelligence
- [ ] Every scene is 16/32/48 bars (DJ-friendly)
- [ ] No two consecutive scenes feel identical
- [ ] At least one false drop exists (Scene 3/5)
- [ ] Elements don't all enter/exit simultaneously
- [ ] 16-bar section without kick exists (Scene 4)
- [ ] Total track length: 6-8 minutes

### Sound Design
- [ ] Kick has three layers (transient/body/sub)
- [ ] Each layer occupies distinct frequency range
- [ ] Bass stays below 500Hz
- [ ] All low-end elements are mono

### Groove
- [ ] Kick remains grid-locked (0ms)
- [ ] Hats have rushing feel (-8 to -12ms)
- [ ] Open hats have dragging feel (+15 to +20ms)
- [ ] MPC swing applied (54-66%)
- [ ] Velocity variation on hats

### Automation
- [ ] No parameter stays static for >16 bars
- [ ] Filter sweeps use exponential curves
- [ ] Automation peaks at 16-bar boundaries
- [ ] Snap-backs are intentional and impactful

### Mix
- [ ] Kick and bass have clear separation
- [ ] Low-end (<100Hz) is 100% mono
- [ ] Mix translates to mono (no phase cancellation)
- [ ] Percussion is bright and crisp

---

## Phase 8: Performance Script
- [ ] Create perform_set.py for AbletonOSC
- [ ] Map all scenes to SCENE_INDEX
- [ ] Create automation macros for live tweaks
- [ ] Test full performance run

---

## Manual Requirements (Stop and request if needed)
- [ ] Sample loading to Simpler (if MCP fails)
- [ ] Complex routing configurations
- [ ] Any audio recording/resampling

---

## Current Progress
**Status:** Starting Phase 1 - Track Setup
**Last Updated:** Session start
