# Subterranean Techno Track - Session Summary

**Date:** 2026-01-19
**Tempo:** 133 BPM
**Key:** G Minor (root G0/G1 = MIDI 31/43)
**Style:** Dark industrial techno with vocal elements
**Time Signature:** 4/4

---

## Track Overview (19 Tracks)

| # | Track Name | Type | Device | Purpose |
|---|------------|------|--------|---------|
| 0 | KICK | MIDI | Kick 909 1 (Simpler) + Saturator + EQ Eight | 4/4 foundation |
| 1 | BASS | MIDI | Operator + Auto Filter + Saturator + Phaser-Flanger + Compressor + EQ Eight | Rolling 16th note bass |
| 2 | CLOSED-HATS | MIDI | Hihat Closed DMX (Simpler) + Auto Filter + Saturator | Tight rhythmic drive |
| 3 | DRIVING-HATS | MIDI | DS HH + Auto Filter | Additional hat layer |
| 4 | OPEN-HATS | MIDI | Hihat Open Brim (Simpler) + Auto Filter + Saturator | Syncopated swing |
| 5 | PERCUSSION | MIDI | Clap 909 (Simpler) + Auto Filter + Saturator | Polymetric clap loops |
| 6 | STAB | MIDI | Wavetable + Auto Filter + Saturator + Erosion + Reverb | Filtered stab hits |
| 7 | RIDE | MIDI | Cymbal 808 Full (Simpler) + Auto Filter + Saturator + Compressor + Overdrive | Peak energy cymbal |
| 8 | ATMOSPHERE | MIDI | ff_dwt_130_atmosphere_loop_ripper (Simpler) | Dark ambient texture |
| 9 | FX-RISER | MIDI | 125BPM_LONG_RISER_01 (Simpler) | Build tension |
| 10 | FX-HITS | MIDI | Impact Layered (Simpler) | Impact hits for transitions |
| 11 | FX-DOWNLIFT | MIDI | Impact Layered Reversed (Simpler) | Reverse impact FX |
| 12 | VOCAL | MIDI | tts_Subte_20260119_102731 (Simpler) + Reverb + EQ Eight | Main vocal sample |
| 13 | VOCAL-2 | MIDI | tts_Deepe_20260119_104627 (Simpler) + Reverb | Secondary vocal |
| 14 | NOISE-SWEEP | MIDI | Hyper Riser (Rack) | Noise sweep riser |
| 15 | INDUSTRIAL | MIDI | Dark Swarm (Rack) + Auto Filter | Industrial texture |
| 16 | DING | MIDI | Bells Damped (Operator) + Auto Filter + Saturator | Bell motif |
| 17 | NOISE-RISER | MIDI | Operator + Auto Filter | Noise riser synth |
| 18 | DARK-TEXTURE | MIDI | MPE Objectivism Drone (Rack) | Dark drone texture |

### Return Tracks (3 FX Sends)
- **A-REVERB:** 2x Reverb (stacked for depth)
- **B-DELAY:** 2x Delay (layered)
- **C-Delay Throw:** Delay (for throws/transitions)

---

## Scene Arrangement (8 Scenes)

| Scene | Clip Slot | Active Tracks | Purpose |
|-------|-----------|---------------|---------|
| **S1** | 0 | Kick, Bass, Closed-Hats, Vocal, Industrial, Ding | Immediate impact intro |
| **S2** | 1 | Kick, Bass, Closed-Hats, Driving-Hats, Open-Hats, Stab, FX-Hits, Ding | Building groove |
| **S3** | 2 | Kick, Bass, Closed-Hats, Driving-Hats, Open-Hats, Stab, Vocal, Noise-Riser, Ding | Rising tension |
| **S4** | 3 | Bass, Closed-Hats, Open-Hats, Stab, Atmosphere, Vocal, Noise-Sweep, Industrial, Ding | Breakdown (no kick) |
| **S5** | 4 | FX-Riser, FX-Hits, Vocal, Noise-Riser, Ding | False drop tension |
| **S6** | 5 | Kick, Bass, Closed-Hats, Driving-Hats, Open-Hats, Percussion, Stab, Ride, Atmosphere, FX-Hits, FX-Downlift, Vocal, Industrial, Dark-Texture, Ding | PEAK ENERGY |
| **S7** | 6 | Kick, Bass, Driving-Hats, Open-Hats, Percussion, Ride, Atmosphere, FX-Hits, FX-Downlift, Vocal, Industrial, Ding | Evolving energy |
| **S8** | 7 | Kick, Bass, Closed-Hats, Industrial, Ding | Outro (DJ tool) |

---

## Musical Content

### Key Signature: G Minor
**Scale degrees used:** G, A, Bb, C, D, Eb, F (natural minor)

### Bass Line (Track 1)
- **Root note:** G (MIDI 31 = G0, MIDI 43 = G1)
- **Pattern:** Rolling 16th notes with velocity variation (105-118)
- **Pitches used:** G0(31), A0(33), Bb0(34), C1(36), D1(38), Eb1(39), F1(41), G1(43)
- **Duration:** 0.25 beats (16th notes)
- **Clip lengths:** 32-192 beats depending on section

### Kick Pattern (Track 0)
- **Pattern:** Four-on-the-floor with velocity accents
- **Pitch:** C3 (MIDI 60) - sample trigger
- **Velocity pattern:** 127 (downbeat) → 115 → 105 → 110 (creates groove)
- **Fills:** Extra 8th note hits at end of 8-bar phrases (velocity 100)
- **Duration:** 0.5 beats per hit

### Stab Pattern (Track 6)
- **Pitches:** G3 (MIDI 55) + Bb3 (MIDI 58)
- **Pattern:** Syncopated offbeat hits (start_time on .5 positions)
- **Duration:** 0.25 beats (short stabs)
- **Velocity variation:** 85-100

### Percussion (Track 5)
- **Polymetric patterns:** 5/16 and 7/16 loops for hypnotic phase shifting
- **S6-Perc-5-16:** 5-beat loop
- **S7-Perc-7-16:** 7-beat loop

---

## Processing Chains

### Common signal chain pattern:
Most tracks use: **Simpler/Synth → Auto Filter → Saturator**

### Bass chain (Track 1):
Operator → Auto Filter → Saturator → Phaser-Flanger → Compressor → EQ Eight

### Kick chain (Track 0):
Simpler (909 sample) → Saturator → EQ Eight

### Ride chain (Track 7):
Simpler → Auto Filter → Saturator → Compressor → Overdrive

### Vocal chain (Track 12):
Simpler (TTS vocal) → Reverb → EQ Eight

---

## Clip Lengths by Section

| Section | Standard Length | Extended Length |
|---------|-----------------|-----------------|
| Intro/Build | 128 beats (32 bars) | - |
| Breakdown | 64 beats (16 bars) | 128 beats |
| Peak | 192 beats (48 bars) | - |
| Polymetric | 5, 7, 16, 32 beats | Custom loops |
| Outro | 128 beats (32 bars) | - |

---

## Technical Notes

### Velocity Dynamics
- **Kick:** 105-127 range (4-step pattern per bar)
- **Bass:** 105-118 range (humanized)
- **Stabs:** 85-100 range (accent on main hits)
- **Hats:** Varied per clip for different energy levels

### Timing/Groove
- Kick: Grid-locked for punch
- Hats: Various swing patterns per scene
- Polymetric percussion for hypnotic phase relationships

### Sample Sources
- **Vocals:** ElevenLabs TTS (tts_Subte, tts_Deepe)
- **Drum samples:** 909, 808, DMX sources
- **Atmosphere:** ff_dwt_130 loop
- **FX:** Impact layers, risers

---

## Currently Playing (Scene 7)

As of session capture, the following clips are active:
- S7-Kick-Evolve (192 beats)
- S7-Bass-Fifth (32 beats)
- S7-Hats-Offbeat (32 beats)
- S7-OpenHat-Syncopated (32 beats)
- S7-Perc-7-16 (7 beats - polymetric)
- S6-Ride-Full (192 beats)
- S7-Atmos-Evolve (192 beats)
- S7-Impact-Evolve (192 beats)
- S7-Downlift (192 beats)
- S7-Vocal-Evolve (192 beats)
- S7-Industrial-Doubled (32 beats)
- DING slot 6 (16 beats)

---

## Project Philosophy

### Dark Industrial Techno Aesthetic
- Heavy use of distortion/saturation throughout
- Filtered elements for movement
- Industrial textures (Dark Swarm rack)
- TTS vocals for otherworldly feel
- Polymetric percussion for hypnotic loops

### Dynamic Arrangement
- Immediate hard impact (no soft intro)
- Constant element addition/subtraction
- Fake breakdown at Scene 4
- Extended peak section (Scene 6)
- DJ-friendly outro tool

---

**Last Updated:** 2026-01-19
**Master Volume:** 58.5%
**Tempo:** 133 BPM
