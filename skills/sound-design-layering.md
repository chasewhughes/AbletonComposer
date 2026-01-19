# Sound Design & Layering Skill

## Purpose
Provides professional-grade sound design and multi-layering techniques for creating powerful, cohesive techno elements that cut through club systems.

## Core Layering Philosophy

### The Three-Layer Rule
Never use a single sample for critical elements. Layer 3 sources:
1. **Transient layer** - Attack/click (high frequencies)
2. **Body layer** - Character/tone (mid frequencies)
3. **Foundation layer** - Weight/power (low frequencies)

### Frequency Separation Principle
```
Each layer occupies its own frequency band:
  Top layer: 2kHz+ (air, click, presence)
  Mid layer: 200Hz - 2kHz (character, tone)
  Sub layer: 40Hz - 200Hz (weight, power)
```

## Kick Drum Layering

### Professional Kick Construction

**Layer 1: Transient (The Click)**
```
Source: Short, punchy 909-style kick OR noise burst
Processing:
  - High-pass @ 2kHz (remove all low-end)
  - Transient shaper: Attack +6dB, Sustain -12dB
  - Very short decay (< 50ms)
  - Purpose: Cuts through mix, defines beat clearly
```

**Layer 2: Body (The Character)**
```
Source: Mid-range focused kick sample
Processing:
  - Band-pass: 100Hz - 500Hz
  - Light compression (3:1 ratio, fast attack)
  - Optional: Bell cut @ 200-300Hz (remove boxiness)
  - Purpose: Gives kick its tonal character
```

**Layer 3: Sub (The Foundation)**
```
Source: Sine wave kick OR very low rumble kick
Processing:
  - Low-pass @ 100Hz (pure sub)
  - Mono (critical for club systems)
  - Slight saturation for harmonic content
  - Purpose: Physical impact, felt not heard
```

### Kick Integration (Critical)
```
After layering:
  1. Bounce all three layers to single audio file
  2. Resample through saturation/glue compressor
  3. Result: Unified sound, not 3 separate kicks
  4. Why: Creates harmonic relationship between layers
```

## Bass Layering & Synthesis

### Rolling Bass Construction

**Primary Layer: Operator (Sub)**
```
Oscillator A: Sine wave (pure sub-bass)
  - Tune: G1 (49Hz for G minor)
  - Level: 100%

Oscillator B: Triangle wave (harmonics)
  - Tune: Same as A (no detune)
  - Level: 30%
  - Purpose: Adds warmth without muddiness

Filter:
  - Low-pass @ 500Hz
  - Slight resonance (0.2)
  - Envelope: Attack 0ms, Decay medium
```

**Enhancement Layer: Wavetable (Texture)**
```
Optional second track with same MIDI:
  - Wavetable with movement
  - High-pass @ 200Hz (no sub clash)
  - Detuned +7 cents (width)
  - Volume: -12dB relative to Operator
  - Purpose: Adds evolving character
```

### Bass Processing Chain
```
1. EQ Eight:
   - High-pass @ 40Hz (remove rumble)
   - Low-pass @ 500Hz (stay out of mid-range)

2. Sidechain Compressor:
   - From kick track
   - Threshold: -18dB, Ratio: 4:1
   - Attack: 0.01ms, Release: 1/16 note

3. Saturation (optional):
   - Subtle tube/tape saturation
   - Adds harmonics for small speakers
```

## Stab/Lead Sound Design

### Layering Strategy

**Layer 1: Fundamental (The Note)**
```
Source: Clean synth sample or Wavetable
  - Defines the pitch/melody
  - Filter: Start dark, automate to open
```

**Layer 2: Texture (The Character)**
```
Source: Different sample, same notes
  - High-pass @ 500Hz (avoid frequency masking)
  - Opposite envelope (if Layer 1 is plucky, make this sustained)
  - Adds complexity
```

**Layer 3: Air (The Shimmer)**
```
Source: Noise, pad, or heavily filtered layer
  - Band-pass: 4kHz - 10kHz (only highs)
  - Heavy reverb
  - Volume: Very low (-18dB)
  - Creates space and depth
```

### Stab Processing
```
1. Auto Filter:
   - Type: Low-pass
   - Automate cutoff for movement
   - Resonance: 0.3 - 0.5 (character)

2. Send to Delay:
   - 1/8 dotted timing
   - Creates depth and space

3. Optional Sidechain:
   - Light ducking from kick
   - Maintains low-end clarity
```

## Percussion Layering

### Hat Combinations

**Closed Hats: Double-Layer**
```
Layer 1: Bright, crisp 909 hat
  - High-pass @ 6kHz
  - Short decay
  - Volume: Primary level

Layer 2: Dark, trashy hat
  - High-pass @ 4kHz
  - Longer decay
  - Volume: -6dB (subliminal)
  - Purpose: Adds depth and grit
```

**Open Hats: Texture + Shimmer**
```
Layer 1: Natural cymbal recording
  - Full frequency spectrum
  - Velocity: 70-110 (varies)

Layer 2: Noise burst
  - High-pass @ 8kHz
  - Very short
  - Triggered on downbeats only
  - Adds "sizzle"
```

## Resampling Techniques (Advanced)

### The "Blawan Method" - Creating Unique Textures

**Step 1: Generate Source**
```
Create basic percussion loop or bass pattern
  - Keep it simple, raw
```

**Step 2: Destroy**
```
Apply heavy processing:
  - Distortion (drive to 80%+)
  - Reverb (100% wet, long decay)
  - Ring modulation
  - Bit crushing
Result: Unrecognizable, mangled audio
```

**Step 3: Pitch Down (Critical)**
```
Resample to audio track
  - Pitch down -7 or -12 semitones
  - Why: Reverb tails become dark/gritty
  - Result: Artifacts become texture
```

**Step 4: Chop & Layer**
```
Cut micro-loops from mangled audio:
  - Use as percussive hits
  - Layer under clean elements
  - Creates unique character samples can't provide
```

### Kick Reverb Rumble

**Create Sub-Rumble Track:**
```
1. Duplicate kick track
2. Send to return with:
   - Reverb: 100% wet, decay 2.5-3.0s
   - Low-pass filter @ 150Hz (only sub-bass)
   - Distortion/saturation (for grit)

3. Sidechain HEAVILY from main kick:
   - Threshold: -30dB
   - Ratio: 8:1
   - Creates pumping sub-rumble

4. Use as separate track in arrangement
```

## Saturation & Glue

### When to Use Saturation

**Individual Tracks:**
```
Kick layers: Subtle tube saturation (binds harmonics)
Bass: Tape saturation (warmth for small speakers)
Percussion: Bit reduction (adds grit)
```

**Group Buses:**
```
Low-End Bus (Kick + Bass):
  - Gentle tape saturation
  - Binds kick decay into bass attack
  - Makes them feel like "one instrument"

Drum Bus:
  - Analog/console saturation
  - Glues percussion together
```

**Never Saturate:**
```
- Return tracks (creates mud)
- Master bus (do this last, separately)
- Individual hats (makes them harsh)
```

## Phase Relationships (Critical)

### Kick & Bass Phase Alignment

**Check Phase:**
```
1. Solo kick and bass together
2. Flip polarity on bass channel
3. Listen: If volume INCREASES, phase was wrong
4. Keep polarity flipped if it sounds louder/fuller
```

**Timing Alignment:**
```
If using multiple kick layers:
  - Zoom to sample level
  - Align first transient peaks
  - Even 1ms difference causes phase issues
  - Result: Fuller, more powerful kick
```

## Integration with Ableton MCP

### Creating Layered Elements:

**Kick Layering Workflow:**
```
1. Create 3 tracks:
   - Track 0: "Kick Top" (transient)
   - Track 1: "Kick Mid" (body)
   - Track 2: "Kick Sub" (foundation)

2. Load samples into Simpler on each

3. Apply processing:
   - Use set_device_parameter for filters
   - Use set_track_volume for balance

4. Create group track:
   - Use create_audio_bus to combine

5. Glue compressor on bus:
   - Use configure_compressor with light settings
```

**Resampling Workflow:**
```
1. Create audio track with input = "Resampling"
2. Arm for recording
3. Play source while recording
4. Process recorded audio with effects
5. Bounce and re-pitch using Simpler
```

## Quality Validation Checklist

- [ ] Critical elements (kick, bass) are layered, not single samples
- [ ] Each layer occupies distinct frequency range
- [ ] Layered kicks are bounced/resampled for unity
- [ ] Bass stays below 500Hz (no mid-range clash)
- [ ] Saturation used for glue, not volume
- [ ] Phase relationships checked on low-end elements
- [ ] Resampled textures add unique character
- [ ] All low-end elements are mono (<100Hz)
- [ ] Stabs/leads have depth from layering
- [ ] Percussion has subtle texture layers

## Example Decision Flow

```
User: "The kick sounds weak and thin"

Step 1: Diagnose issue
  - Single kick sample = lacks dimension
  - No layering = missing frequency ranges

Step 2: Layer strategy
  - Need: Transient (click) + Body (tone) + Sub (weight)

Step 3: Find samples
  - Search library for:
    * Bright/clicky kick (transient)
    * Mid-range focused kick (body)
    * Deep/subby kick (sub)

Step 4: Create layers
  - Track 0: Load clicky kick, HP @ 2kHz
  - Track 1: Load mid kick, BP 100-500Hz
  - Track 2: Load sub kick, LP @ 100Hz

Step 5: Process & unite
  - Balance levels (sub loudest, transient quietest)
  - Create group bus
  - Apply glue compression
  - Optional: Resample all to single track

Result: Powerful, dimensional kick that works on all systems
```

## Research Sources

This skill is based on:
- [Anatomy of the techno kick](https://www.audiotent.com/blogs/production-tips/anatomy-of-the-techno-kick)
- [How to layer kicks and bass in techno](https://www.myloops.net/how-to-layer-kicks-and-bass-in-techno-tracks)
- [Mixing techno kick and bass](https://www.mind-flux.com/news-1/2019/9/20/how-to-mix-techno-kick-and-bass)
- [Layered kick drum techniques](https://www.musicradar.com/tuition/tech/5-steps-to-creating-the-perfect-layered-kick-drum-639056)
- [Creative sampling and resampling](https://www.samplesoundmusic.com/blogs/news/creative-sampling-techniques-for-techno-producers-in-2025)
- [Mixing low-end without mud](https://www.samplesoundmusic.com/blogs/news/mixing-low-end-in-techno-kick-vs-bassline-without-mud)

## Version
1.0.0 - Initial release based on professional techno production techniques
