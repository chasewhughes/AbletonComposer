# Mix Analysis Skill

## Purpose
Provides frequency conflict detection, EQ carving strategies, and mixing intelligence to ensure clean, powerful techno mixes that translate across all systems.

## Core Mixing Philosophy

### Frequency Space Management
Every element must have its own "home" in the frequency spectrum. When two elements compete for the same space, use EQ to decide the winner.

### Subtractive Before Additive
Always cut conflicting frequencies before boosting. Carve out mud before adding presence.

### Mono Low-End (Critical)
Everything below 100-120Hz must be mono for club system compatibility and phase coherence.

## Frequency Map for Peak-Time Techno

### The Spectrum Allocation

```
SUB-BASS (30-60 Hz):
  Owner: Kick fundamental OR Bass fundamental (choose one)
  Conflict: If both occupy this space = mud
  Solution: One element dominates, other sits above

LOW-END (60-120 Hz):
  Primary: Kick body
  Secondary: Bass body (if kick allows)
  Conflict: Most common source of "muddy" mixes
  Solution: Dynamic sidechain or EQ carving

LOW-MIDS (120-300 Hz):
  Primary: Bass main range
  Avoid: Kick tail, rumble elements
  Conflict: Boomy, indistinct low-end
  Solution: High-pass kick at 120Hz (steep), let bass own this

MID-RANGE (300Hz-2kHz):
  Primary: Stabs, leads, synth bodies
  Avoid: Bass (already cut), Kick (already cut)
  Conflict: Tinny bass, muddy stabs
  Solution: Complementary EQ cuts

HIGH-MIDS (2kHz-6kHz):
  Primary: Hat fundamentals, stab presence
  Secondary: Kick transient click
  Conflict: Harsh, brittle mix
  Solution: Subtle cuts, not boosts

HIGHS (6kHz-12kHz):
  Primary: Hat shimmer, ride cymbal
  Secondary: Atmosphere air
  Conflict: Harsh sibilance
  Solution: Shelf EQ, not bell boosts

AIR (12kHz+):
  Owner: Open hats, atmosphere, textures
  Caution: Boost sparingly
  Purpose: Perceived "expensive" sound
```

## EQ Carving Strategies

### Kick vs. Bass (The Critical Relationship)

**Strategy 1: Kick Dominates Sub (Most Common)**
```
Kick:
  - Let sub-bass remain (40-80Hz full)
  - Bell cut @ 200-300Hz (remove boxiness)
  - Slight boost @ 4-6kHz (transient click)

Bass:
  - High-pass @ 60Hz (steep 24-48dB/oct)
  - Main body: 100-300Hz
  - Low-pass @ 500Hz (stay out of mid-range)
  - Dynamic EQ: Cut 60-80Hz ONLY when kick hits
    (Alternative to sidechain compression)
```

**Strategy 2: Bass Dominates Sub (Less Common)**
```
Kick:
  - High-pass @ 80Hz (remove sub entirely)
  - Focus on: 100Hz (punch) + 4kHz (click)
  - Very transient-focused

Bass:
  - Owns 40-120Hz fully
  - Becomes the "weight" of the track
  - Must have strong sub content
```

### Stab/Lead vs. Bass

**Frequency Separation:**
```
Stab/Lead:
  - High-pass @ 200-300Hz minimum
  - Main range: 400Hz-2kHz
  - Don't let it creep into bass territory

Bass:
  - Low-pass @ 500Hz
  - If stab feels "thin", problem is NOT bass
  - Problem is stab needs more body (300-800Hz)
```

### Hats vs. Ride vs. Atmosphere

**High Frequency Management:**
```
Closed Hats:
  - High-pass @ 6kHz
  - Main energy: 8-10kHz
  - Short decay

Open Hats:
  - High-pass @ 4kHz
  - Decay into 10-12kHz range
  - More body than closed

Ride Cymbal:
  - High-pass @ 2kHz
  - Body: 3-5kHz
  - Shimmer: 8-12kHz
  - Most full-range of high elements

Atmosphere:
  - Low-pass @ 10kHz OR high-shelf cut
  - Purpose: Sits "behind" percussion
  - Should not compete with hats
```

## Dynamic EQ vs. Static EQ

### When to Use Dynamic EQ

**Kick/Bass Conflict Resolution:**
```
Instead of sidechain compression:
  - Insert Dynamic EQ on bass
  - Create band @ 60-80Hz (kick fundamental)
  - Sidechain to kick track
  - Action: Cut 3-6dB ONLY when kick hits
  - Result: Bass stays full until kick strikes
```

**Stab/Hat Conflict:**
```
If stabs make hats disappear:
  - Dynamic EQ on stabs
  - Band @ 8-10kHz (hat presence)
  - Cut 2-3dB when hats hit
  - Triggered by hat track sidechain
```

### When to Use Static EQ

```
- Foundational frequency carving (always-on)
- Removing rumble/mud (high-pass filters)
- Tonal shaping (bass body, kick punch)
- Air and presence (high-shelf adjustments)
```

## Mixing Checklist by Element

### Kick Drum

```
- [ ] Sub content: 40-60Hz (present and mono)
- [ ] Punch: ~100Hz (defined but not boomy)
- [ ] Boxiness: 200-300Hz (cut if muddy)
- [ ] Transient: 4-6kHz (clear but not harsh)
- [ ] Rumble: <30Hz (removed entirely)
```

### Bass

```
- [ ] High-pass: 40-60Hz (depending on kick strategy)
- [ ] Body: 100-300Hz (main presence)
- [ ] Cut-off: 500Hz (doesn't enter mid-range)
- [ ] Mono: 100% (no stereo width in low-end)
- [ ] Sidechain: Ducks cleanly when kick hits
```

### Stabs/Leads

```
- [ ] High-pass: 200-300Hz (no bass conflict)
- [ ] Body: 400Hz-1kHz (fullness without mud)
- [ ] Presence: 2-4kHz (cuts through mix)
- [ ] Air: 8-12kHz (optional shimmer)
- [ ] Width: Can be stereo (no mono issues)
```

### Hats & Percussion

```
- [ ] High-pass: 4-8kHz (very bright)
- [ ] No mud: <2kHz completely removed
- [ ] Velocity variation: Not static volumes
- [ ] Stereo width: Slight (not wide)
- [ ] Level: Audible but not dominating
```

### Atmosphere/Pads

```
- [ ] Low-cut: 200-500Hz (stay out of bass/kick)
- [ ] Body: 500Hz-2kHz (warmth without mud)
- [ ] Sits back: -12 to -18dB relative to drums
- [ ] Width: Can be very wide
- [ ] Movement: Filter/volume automation for evolution
```

## Bus Processing Strategy

### Low-End Bus (Kick + Bass Group)

```
Purpose: Glue low-end elements together

Processing Chain:
  1. Glue Compressor:
     - Ratio: 2:1
     - Attack: 30ms (slow, preserves transient)
     - Release: Auto or fast
     - GR: 1-2dB maximum
     - Purpose: Binds kick decay into bass attack

  2. Saturation (Tape/Tube):
     - Drive: 10-20%
     - Purpose: Harmonic content for small speakers

  3. Utility (Critical):
     - Force <100Hz to MONO
     - Purpose: Phase coherence on club systems

  4. Safety Limiter:
     - Ceiling: -6dB
     - Purpose: Prevent low-end from dominating mix
```

### Drum Bus (All Percussion)

```
Purpose: Make drums feel cohesive

Processing Chain:
  1. Glue Compressor:
     - Ratio: 2:1-3:1
     - Attack: Medium (10-20ms)
     - Release: Fast
     - GR: 2-3dB
     - Purpose: Adds "snap" to percussion

  2. Saturation (Console/Analog):
     - Drive: 15-25%
     - Purpose: Adds harmonic glue

  3. High-pass:
     - 30-40Hz
     - Purpose: Remove sub-rumble from hats
```

### No Bus Processing Needed

```
- Stabs/Leads (process individually)
- Return tracks (already processed)
- Atmosphere (keep clean for automation)
```

## Phase & Polarity Checking

### Critical Phase Relationships

**Kick Layers:**
```
If layering multiple kick samples:
  1. Zoom to sample level
  2. Align first transient peaks exactly
  3. Check: Do waveforms reinforce or cancel?
  4. Test: Flip polarity, listen for volume change
  5. Keep configuration that sounds fuller/louder
```

**Kick vs. Bass:**
```
Method 1 - Polarity Test:
  1. Solo kick + bass
  2. Flip bass polarity
  3. If volume increases = phase was canceling
  4. Keep polarity that gives more low-end

Method 2 - Visual Check:
  1. Use oscilloscope plugin
  2. Watch kick/bass relationship
  3. Ideal: Bass waveform starts when kick decays
  4. If they peak together = potential cancellation
```

### Mono Compatibility Check

```
Essential for club systems:
  1. Switch mix to mono
  2. Listen: Does low-end disappear?
  3. If yes: Stereo information in <120Hz
  4. Solution: Utility plugin, force bass to mono
```

## Integration with Ableton MCP

### Analyzing Mix State:

```
1. Get session info (all tracks)
2. Get device parameters (see current EQ settings)
3. Get track volumes (check balance)
```

### Applying EQ Carving:

```
Use set_device_parameter for EQ Eight:

Kick EQ:
  - "1 Filter Type": High Pass
  - "1 Frequency": 30 (30Hz)
  - "2 Filter Type": Bell
  - "2 Frequency": 250 (200-300Hz)
  - "2 Gain": -3dB (cut boxiness)

Bass EQ:
  - "1 Filter Type": High Pass
  - "1 Frequency": 60 (60Hz)
  - "8 Filter Type": Low Pass
  - "8 Frequency": 500 (500Hz)
```

### Creating Bus Compression:

```
Use create_audio_bus:
  - Route Kick + Bass to group
  - Use configure_compressor:
    * Ratio: 2
    * Attack: 0.03 (30ms)
    * Makeup: auto
```

## Quality Validation Checklist

- [ ] No two elements dominate same frequency range
- [ ] Kick and bass have clear separation (not fighting)
- [ ] Low-end (<100Hz) is 100% mono
- [ ] High-pass filters remove inaudible rumble
- [ ] No elements sound "muddy" (200-400Hz checked)
- [ ] Mix translates to mono (no phase cancellation)
- [ ] Percussion is bright and crisp (not dull)
- [ ] Stabs/leads don't mask bass or get masked by bass
- [ ] Atmosphere sits "behind" main elements
- [ ] Total mix has headroom (not constant 0dBFS)

## Example Decision Flow

```
User: "The bass and kick sound muddy together"

Step 1: Identify frequency conflict
  - Get EQ settings for both tracks
  - Check: Both likely occupying 60-120Hz

Step 2: Choose dominant element
  - Question: Should kick or bass own the sub?
  - Decision: Kick dominates (most common in techno)

Step 3: Apply frequency carving
  Kick:
    - Keep sub-bass (40-80Hz)
    - Cut boxiness (200-300Hz, -3dB)

  Bass:
    - High-pass @ 60Hz (steep slope)
    - Main body 100-300Hz
    - Low-pass @ 500Hz

Step 4: Add dynamic control
  - Sidechain compressor on bass from kick
  - OR Dynamic EQ cutting 60-80Hz when kick hits

Step 5: Validate
  - Solo kick + bass
  - Check: Can you hear both clearly?
  - Check: Is kick punchy, bass full?
  - If yes: Conflict resolved

Result: Clean, powerful low-end with definition
```

## Research Sources

This skill is based on:
- [Mixing low-end in techno without mud](https://www.samplesoundmusic.com/blogs/news/mixing-low-end-in-techno-kick-vs-bassline-without-mud)
- [Frequency masking techniques](https://www.masteringbox.com/learn/frequency-masking)
- [Pro secrets for mixing kick and bass](https://mixingmonster.com/mixing-kick-and-bass/)
- [EQ carving for kick/bass separation](https://www.mind-flux.com/news-1/2019/9/20/how-to-mix-techno-kick-and-bass)
- [How to EQ kick and bass for powerful low-end](https://www.productionmusiclive.com/blogs/news/how-to-eq-kick-and-bass-for-powerful-low-end)
- [EQ frequency ranges and their impact (2026)](https://mixingmonster.com/eq-frequency-ranges/)

## Version
1.0.0 - Initial release based on professional mixing techniques
