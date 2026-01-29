# Manual Requirements - Subterranean (Adam Beyer Style Track)

## CURRENT STATUS

### Samples Loaded via MCP (DONE):
| Track | Name | Sample | Status |
|-------|------|--------|--------|
| 0 | KICK | Kick 909 1 | LOADED |
| 2 | CLOSED-HATS | Hihat Closed DMX | LOADED |
| 3 | OPEN-HATS | Hihat Open Brim | LOADED |
| 4 | PERCUSSION | Clap 909 | LOADED |
| 6 | RIDE | Cymbal 808 Full | LOADED |

### Auto Filters (DONE):
| Track | Name | Device | Settings |
|-------|------|--------|----------|
| 1 | BASS | Auto Filter | Freq=0.15, Res=0.3, Slope=12dB |
| 5 | STAB | Auto Filter | Freq=0.2, Res=0.4, Slope=24dB |

---

## REMAINING MANUAL TASKS

### 1. Load Atmosphere Sample into Simpler (Track 7: ATMOSPHERE)
**Sample Path:** `/Users/chasehughes/Documents/Github-hughes7370/SoundAnalyst/samples/ff_dwt_130_atmosphere_loop_ripper.wav`

**Instructions:**
1. Click on Track 7 (ATMOSPHERE) - it now has a Simpler device
2. Open Finder and navigate to the sample path above
3. Drag the .wav file into Simpler's waveform display area
4. In Simpler, enable Loop mode for continuous playback
5. The sample is 130 BPM and will sync perfectly

**After loading the sample:**
- I will create a MIDI clip to trigger it

---

### 2. Load FX Riser Sample into Simpler (Track 8: FX-RISER)
**Sample Path:** `/Users/chasehughes/Documents/Github-hughes7370/SoundAnalyst/samples/125BPM_LONG_RISER_01.wav`

**Instructions:**
1. Click on Track 8 (FX-RISER) - it now has a Simpler device
2. Open Finder and navigate to the sample path above
3. Drag the .wav file into Simpler's waveform display area
4. In Simpler, set to One-Shot mode (no loop)

**After loading the sample:**
- I will create a MIDI clip to trigger it before Scene 4

---

## Track Layout (Updated)

| Index | Name | Type | Device | Sample Status |
|-------|------|------|--------|---------------|
| 0 | KICK | MIDI | Simpler (Kick 909 1) | LOADED |
| 1 | BASS | MIDI | Operator + Auto Filter | READY |
| 2 | CLOSED-HATS | MIDI | Simpler (Hihat Closed DMX) | LOADED |
| 3 | OPEN-HATS | MIDI | Simpler (Hihat Open Brim) | LOADED |
| 4 | PERCUSSION | MIDI | Simpler (Clap 909) | LOADED |
| 5 | STAB | MIDI | Wavetable + Auto Filter | READY |
| 6 | RIDE | MIDI | Simpler (Cymbal 808 Full) | LOADED |
| 7 | ATMOSPHERE | MIDI | Simpler (empty) | NEEDS SAMPLE |
| 8 | FX-RISER | MIDI | Simpler (empty) | NEEDS SAMPLE |

---

## After Loading These 2 Samples

Let me know when done and I will:
1. Create MIDI clips for ATMOSPHERE and FX-RISER
2. Add filter automation for tension
3. Run final validation
4. Create perform_set.py
