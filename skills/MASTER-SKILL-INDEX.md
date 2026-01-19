# Master Skill Index - Music Production Intelligence

## Overview

This folder contains 5 core production intelligence skills that transform basic techno track creation into professional Charlotte de Witte / Adam Beyer level productions.

## The Problem These Skills Solve

**Before:** Track creation was technically correct but musically dead:
- Scenes just stacked elements linearly (boring)
- No intelligent arrangement decisions (predictable)
- No automation movement (static)
- Single samples per element (thin/weak)
- Perfect quantization (robotic)
- Frequency conflicts (muddy mixes)

**After:** Production has professional intelligence:
- Dynamic arrangement with false drops and tension manipulation
- Strategic automation that builds anticipation
- Layered sounds with depth and power
- Human groove with micro-timing and swing
- Clean mixes with proper frequency separation

## The 5 Core Skills

### 1. Arrangement Intelligence ([arrangement-intelligence.md](arrangement-intelligence.md))

**What it does:**
- Understands energy curve principles (not just loud→quiet→loud)
- Creates overlapping energy waves with constant evolution
- Implements false drops and expectation subversion
- Applies the 16-bar rule for DJ-friendly arrangements
- Knows when to ADD elements and when to SUBTRACT

**Key concepts:**
- Immediate impact (Charlotte de Witte's hard start philosophy)
- The "Hunger Principle" (withhold elements to create desire)
- Scene-by-scene intelligence (8 scene structure)
- Strategic element absence (what NOT to play)

**When to use:**
- Creating scene structure
- Deciding which elements go in which scenes
- Planning track progression
- Avoiding predictable arrangements

---

### 2. Automation Composer ([automation-composer.md](automation-composer.md))

**What it does:**
- Creates filter sweeps that build tension
- Generates volume automation for fade ins/outs
- Designs reverb throws for transitions
- Implements complementary motion (one up, another down)
- Calculates automation timing relative to structure

**Key concepts:**
- Filter sweeps with exponential curves (not linear)
- LFO-style breathing effect for movement
- V-Shape EQ automation for builds
- Polyrhythmic LFO rates for evolution
- Strategic snap-backs for impact

**When to use:**
- Building tension before scene changes
- Creating movement in static elements
- Transition effects between sections
- Adding dynamic character to sounds

---

### 3. Sound Design & Layering ([sound-design-layering.md](sound-design-layering.md))

**What it does:**
- Implements the three-layer rule (transient + body + foundation)
- Creates professional kick drums from multiple samples
- Layers bass for power and character
- Applies resampling techniques for unique textures
- Manages phase relationships between layers

**Key concepts:**
- Frequency separation (each layer owns its range)
- Kick integration through resampling
- The "Blawan Method" for texture creation
- Saturation for harmonic glue
- Phase alignment for power

**When to use:**
- Kick sounds weak or thin
- Bass lacks power or depth
- Need unique textures beyond samples
- Elements sound separate, not cohesive

---

### 4. Mix Analysis ([mix-analysis.md](mix-analysis.md))

**What it does:**
- Detects frequency conflicts between elements
- Provides EQ carving strategies
- Implements bus processing for cohesion
- Ensures mono low-end for club compatibility
- Creates dynamic EQ solutions for conflicts

**Key concepts:**
- Frequency spectrum allocation map
- Kick vs. Bass relationship (the critical decision)
- Subtractive EQ before additive
- Dynamic EQ as alternative to sidechain
- Bus compression for glue

**When to use:**
- Mix sounds muddy (low-end conflicts)
- Elements disappear in the mix (masking)
- Bass and kick fighting for space
- Track doesn't translate to mono

---

### 5. Groove & Timing Intelligence ([groove-timing-intelligence.md](groove-timing-intelligence.md))

**What it does:**
- Applies micro-timing offsets for human feel
- Implements MPC swing for groove
- Creates polyrhythmic patterns for hypnotic effect
- Adds velocity variation for dynamics
- Evolves groove over arrangement

**Key concepts:**
- The push & pull effect (rush vs. drag)
- Roger Linn's swing principle
- Polymeters (3/16, 5/16, 7/16 loops)
- Velocity humanization
- Groove evolution through track

**When to use:**
- Track sounds robotic or stiff
- Grid-locked elements lack life
- Need hypnotic, evolving patterns
- Creating urgency or laid-back feel

---

## How These Skills Work Together

### Example: Creating a Professional Track

**Step 1: Arrangement Intelligence**
- Plan 8-scene structure with false drops
- Decide which elements go in each scene
- Calculate scene durations (32 bars each)

**Step 2: Sound Design & Layering**
- Layer kick from 3 samples (transient + body + sub)
- Layer bass for power (Operator + texture)
- Create unique textures through resampling

**Step 3: Mix Analysis**
- EQ carve kick vs. bass frequency space
- Apply bus compression to low-end group
- Check mono compatibility

**Step 4: Groove & Timing**
- Apply -10ms to closed hats (rushing)
- Apply +18ms to open hats (dragging)
- Add MPC swing at 62% (15% amount)

**Step 5: Automation Composer**
- Create filter sweeps for Scene 3 build (bars 80-96)
- Add reverb throws before scene changes
- Automate volumes for element fades

**Result:** Professional track with depth, movement, and intelligence

---

## Integration with Ableton MCP

All skills are designed to work with the Ableton MCP tools. Each skill includes:

### Analysis Phase
```
- get_session_info (understand current state)
- get_track_info (know what elements exist)
- get_device_parameters (see current processing)
- get_clip_info (understand arrangement)
```

### Decision Phase
```
- Apply skill intelligence to make production decisions
- Calculate optimal values (timing, frequencies, curves)
- Determine which elements need processing
```

### Execution Phase
```
- Use MCP tools to apply changes:
  * create_clip / add_notes_to_clip
  * set_device_parameter
  * automate_parameter / record_automation
  * apply_groove_with_amount
  * nudge_clip_timing
  * configure_compressor
  * load_instrument_or_effect
```

---

## Skill Usage Priority

### For "Track Sounds Basic/Boring":
1. **Arrangement Intelligence** (most impact)
2. **Automation Composer** (creates movement)
3. **Groove & Timing** (removes robotic feel)

### For "Track Sounds Weak/Thin":
1. **Sound Design & Layering** (most impact)
2. **Mix Analysis** (reveals actual problems)
3. **Automation Composer** (adds dynamics)

### For "Track Sounds Muddy":
1. **Mix Analysis** (most impact)
2. **Sound Design & Layering** (may be over-layered)
3. **Arrangement Intelligence** (may be too dense)

---

## Quality Validation

Use all 5 skills to validate:
- [ ] Arrangement has false drops and evolution (not predictable)
- [ ] Automation creates movement (not static)
- [ ] Sounds have depth from layering (not thin)
- [ ] Mix is clean with separation (not muddy)
- [ ] Groove has human feel (not robotic)

---

## Research Foundation

All skills are based on 2025-2026 research:
- Charlotte de Witte's dancefloor-first production philosophy
- Adam Beyer's Drumcode sound and arrangement techniques
- Professional peak-time techno production principles
- Roger Linn's MPC groove and swing theory
- Modern mixing and mastering best practices

---

## Version History

**v1.0.0** (2026-01-18)
- Initial release of all 5 core skills
- Based on comprehensive web research
- Optimized for Ableton MCP integration
- Focused on Charlotte de Witte / Adam Beyer style

---

## Next Steps

To use these skills effectively:
1. Read each skill to understand its principles
2. Apply skills in order (arrangement → sound → mix → groove → automation)
3. Use the "Example Decision Flow" sections for guidance
4. Validate using quality checklists
5. Iterate based on results

**The goal:** Move from "basic middle school techno" to professional Charlotte de Witte / Adam Beyer level productions through intelligent decision-making, not just technical execution.
