# Automation Composer Skill

## Purpose
Creates intelligent, musical automation for filters, volumes, sends, and effects that build tension and create movement in peak-time techno productions.

## Core Principles

### Automation Philosophy
- **Never static**: Every element should have some movement over time
- **Complementary motion**: When one parameter opens, another closes
- **Timed to structure**: Automation peaks/valleys align with 16-bar sections
- **Musical curves**: Use exponential/logarithmic curves, not just linear

## Filter Automation Strategies

### Bass Filter Sweeps (Tension Building)

**Build Section (16 bars before change):**
```
Bars 80-96 (leading to scene change):
  - Start: 200Hz (filtered/dark)
  - Bar 88 (halfway): 800Hz (opening)
  - Bar 96 (climax): SNAP to 20Hz OR fully open to 2kHz
  - Curve: Exponential (slow start, rapid finish)
```

**Peak Section (Breathing Effect):**
```
Use LFO-style automation:
  - Frequency: 1/2 bar (quarter note rate at 130 BPM)
  - Range: 300Hz - 1.2kHz
  - Shape: Sine wave (smooth)
  - Purpose: Creates "pumping" character without sidechain
```

**Breakdown Section (Tension Hold):**
```
Bars 97-112 (no kick):
  - Keep filter at 500Hz (mid-range focus)
  - Add resonance automation: 0.1 → 0.4
  - Creates "hollow" techno sound
  - Snap resonance back to 0.1 when kick returns
```

### Stab/Lead Filter Animation

**Scene Entry (First 8 bars):**
```
Keep filter closed, introduce slowly:
  - Bar 1-4: 300Hz (very dark)
  - Bar 5-8: Open to 1kHz
  - Bar 9+: Modulate with LFO
```

**Before Drops (Create Expectation):**
```
  - Start 4 bars before drop
  - High-pass: 20Hz → 5kHz (extreme sweep)
  - Resonance: 0.2 → 0.8 (adds screaming quality)
  - At drop: SNAP both back to neutral
```

## Volume Automation Strategies

### Atmosphere/Pad Elements

**Fade In (8-16 bars):**
```
Use logarithmic curve:
  - Bar 1: -inf dB (silence)
  - Bar 4: -24 dB (barely present)
  - Bar 8: -12 dB (subliminal)
  - Bar 16: -6 dB (present but not dominant)
```

**Fade Out (4-8 bars):**
```
Use linear or exponential:
  - Faster exit creates urgency
  - Exit 4 bars before next element enters
  - Creates space for new sounds
```

### Riser FX

**Build Automation (16 bars):**
```
  - Volume: -inf → -3dB (exponential curve)
  - High-pass filter: 500Hz → 8kHz (paired with volume)
  - Reverb send: 20% → 80% (adds space)
  - At climax: Cut immediately (don't fade out)
```

### Percussion Dynamics

**Hat Volume Rides:**
```
Create pocket for other elements:
  - When stab plays: Reduce hats -3dB
  - When ride enters: Reduce closed hats -4dB
  - When kick drops out: Boost hats +2dB (maintain energy)
```

## Send Effect Automation

### Reverb Throws (Transition Effect)

**Pre-Scene Change (1-2 bars before):**
```
Bar 95-96 (before scene 4):
  - Reverb Send A: 0% → 80% over 1 bar
  - Decay time: 2.0s → 4.0s
  - Creates "wash out" effect
  - Reset to 0% immediately at bar 97
```

### Delay Feedback Bursts

**Energy Peak Moments:**
```
Every 32 bars during peak:
  - Bar 192: Delay feedback 40% → 90% over 1 beat
  - Hold for 2 beats
  - Return to 40% over 1 beat
  - Creates controlled chaos
```

## Advanced Automation Techniques

### V-Shape EQ (Master Bus)

**Build Section Only (automate then remove):**
```
Bars 80-96:
  - High-pass: 20Hz → 150Hz (removes low-end)
  - High-shelf: 0dB → +3dB @ 8kHz (emphasizes highs)
  - At bar 96: SNAP BACK to neutral
  - Result: Drop feels huge and full
```

### Macro Parameter Animation

**"Wash Out" Rack Macro:**
```
Create crossfade between dry/wet chains:
  - Macro at 0: Clean signal
  - Macro at 100: Reverb + delay + high-pass
  - Automate: 0 → 100 over 8 bars (transitions)
  - Use before breakdowns
```

### Polyrhythmic Automation

**LFO Rates That Don't Sync:**
```
Bass filter: 1/3 bar rate (creates polyrhythm)
Stab resonance: 1/5 bar rate (different cycle)
Result: Sounds "evolve" naturally, never repeat exactly
```

## Automation Timing Guidelines

### When to Start Automation

```
8 bars before change: Subtle movement begins
4 bars before change: Obvious automation
2 bars before change: Riser/FX automation
1 bar before change: Reverb throws, extreme sweeps
At change: SNAP or SMOOTH depending on impact desired
```

### Curve Types by Use Case

```
Tension building: Exponential (slow start, fast end)
Fade ins: Logarithmic (fast start, slow end)
LFO/breathing: Sine/triangle (smooth oscillation)
Drops/impacts: Instant (no curve, immediate snap)
```

## Integration with Ableton MCP

### Before Creating Automation:
1. Get clip info to know clip length
2. Get device parameters to know what's automatable
3. Calculate bar positions based on 130 BPM, 4/4 time

### Creating Automation:
```
Use mcp__ableton__record_automation for clip automation:
  - Breakpoints: Array of [time_in_beats, value]
  - Interpolation: "linear", "exponential", "logarithmic"
  - clear_existing: true (replace old automation)

Use mcp__ableton__automate_parameter for smart curves:
  - Automatically generates breakpoints
  - Supports curve types: linear, exponential, s_curve
```

### Example Automation Creation:
```
Filter sweep on bass (Scene 3 build):
  Track: 1 (Rolling Bass)
  Clip: Scene 3 (clip_index 2)
  Device: Auto Filter (device_index 2)
  Parameter: "Frequency"

  Breakpoints:
    [0, 0.2]    // Bar 65: 200Hz (dark)
    [16, 0.25]  // Bar 73: Still mostly closed
    [28, 0.6]   // Bar 85: Opening up
    [31, 0.9]   // Bar 95: Almost open
    [32, 0.1]   // Bar 96: SNAP back closed (surprise)
```

## Quality Validation Checklist

- [ ] No parameter stays static for > 16 bars
- [ ] Filter sweeps use exponential curves (not linear)
- [ ] Volume fades align with structural changes
- [ ] Automation peaks occur at 16-bar boundaries
- [ ] Complementary motion (one up, another down)
- [ ] Reverb/delay automation used for transitions
- [ ] No automation "fights" the mix (e.g., opening two basses simultaneously)
- [ ] LFO rates create polyrhythmic interest
- [ ] Snap-backs are intentional and impactful
- [ ] All automation enhances musicality (not just "because we can")

## Example Decision Flow

```
User: "Add filter automation to create tension"

Step 1: Identify automation candidates
  - Bass (most impactful for tension)
  - Stab lead (melodic interest)
  - Group high-pass (dramatic)

Step 2: Calculate timing
  - Scene 3: Bars 65-96 (32 bars)
  - Start automation: Bar 80 (16 before change)
  - Peak automation: Bar 96 (scene change)

Step 3: Choose parameters
  - Bass: Filter frequency sweep
  - Stab: Resonance increase
  - Drum group: High-pass automation

Step 4: Select curves
  - Bass filter: Exponential (builds tension)
  - Stab resonance: Linear (steady increase)
  - Drum HP: Extreme exponential (last 4 bars only)

Step 5: Create automation via MCP
  Use automate_parameter for bass filter:
    - start_value: 0.2 (200Hz)
    - end_value: 0.9 (open)
    - duration_bars: 16
    - curve: "exponential"

Step 6: Validate
  - Check that automation doesn't conflict with other elements
  - Ensure snap-back at bar 96 is intentional
  - Verify creates desired tension
```

## Research Sources

This skill is based on:
- [Filter sweep fundamentals and techniques](https://www.perfectcircuit.com/signal/filter-sweeps)
- [LFO modulation approaches in electronic music](https://blog.landr.com/how-to-use-lfos/)
- [Creative LFO techniques for synths](https://www.izotope.com/en/learn/creative-ways-to-use-lfos-on-synths-and-beats.html)
- [Advanced filter automation in techno](https://musictech.com/tutorials/logic-tutorial-filtering/)
- [Automation techniques for building tension](https://www.edmprod.com/tension/)

## Version
1.0.0 - Initial release based on 2026 techno production research
