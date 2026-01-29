# Ableton AI Composer

**An experiment in AI-driven music composition using Claude, Ableton Live 12, and the Model Context Protocol (MCP)**

Listen to the result: [SoundCloud - Subterranean](https://soundcloud.com/bwv-363160597)

## The Question

Can large language models compose sophisticated music from end-to-end without relying on sequence prediction models (like Suno or Udio)?

Current AI music generators are trained on existing music and predict sequences, but they don't inherently understand music theory. They also can't output separated stems for professional editing. This project explores whether an LLM, given the right tools and knowledge, can compose original music based on music theory principles rather than pattern matching.

## The Approach

Techno was chosen as the target genre because:
- Instruments can be electronically generated
- Mathematical patterns underpin the genre's structure
- Clear compositional rules exist (16-bar phrases, energy curves, etc.)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE                                     │
│                         (Orchestration Layer)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     CLAUDE SKILLS (Music Theory)                     │    │
│  ├──────────────┬──────────────┬──────────────┬──────────────┬─────────┤    │
│  │ Arrangement  │  Automation  │ Sound Design │     Mix      │ Groove  │    │
│  │ Intelligence │   Composer   │  & Layering  │   Analysis   │ Timing  │    │
│  ├──────────────┼──────────────┼──────────────┼──────────────┼─────────┤    │
│  │ • Energy     │ • Filter     │ • 3-layer    │ • Frequency  │ • Micro │    │
│  │   curves     │   sweeps     │   kicks      │   conflicts  │   timing│    │
│  │ • False      │ • Volume     │ • Bass       │ • EQ carving │ • MPC   │    │
│  │   drops      │   automation │   layering   │ • Bus        │   swing │    │
│  │ • 16-bar     │ • Reverb     │ • Resampling │   processing │ • Poly- │    │
│  │   rule       │   throws     │   techniques │ • Mono       │   meters│    │
│  │ • Tension    │ • LFO rates  │ • Phase      │   compat.    │ • Human │    │
│  │   release    │              │   alignment  │              │   feel  │    │
│  └──────────────┴──────────────┴──────────────┴──────────────┴─────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        SAMPLE LIBRARY (library.json)                 │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │  193 samples with spectral analysis:                        │    │    │
│  │  │  • spectral_centroid, brightness, warmth                    │    │    │
│  │  │  • attack_time_ms, onset_density                            │    │    │
│  │  │  • energy_level (1-10), texture_tags                        │    │    │
│  │  │  • BPM, key, category/subcategory                           │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │  AI selects samples by spectral profile without hearing them        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   ABLETON MCP   │       │   ABLETON OSC   │       │  ELEVENLABS MCP │
│  (Composition)  │       │  (Performance)  │       │    (Vocals)     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ • Create tracks │       │ • Fire scenes   │       │ • Voice cloning │
│ • Add clips     │       │ • Fade volumes  │       │ • Text-to-speech│
│ • Insert notes  │       │ • Mute/unmute   │       │ • Audio effects │
│ • Load devices  │       │ • Real-time     │       └─────────────────┘
│ • Set params    │       │   automation    │
│ • Configure FX  │       │ • Spectral      │
└────────┬────────┘       │   carving       │
         │                └────────┬────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ABLETON LIVE 12                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Session View: 8 Scenes × 23 Tracks                                   │  │
│  │  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                    │  │
│  │  │INTRO│LAYER│BUILD│BREAK│ GAP │PEAK │EVOLVE│OUTRO│                   │  │
│  │  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤                    │  │
│  │  │ 16  │ 16  │ 24  │  8  │  1  │ 32  │ 24  │ 16  │  bars              │  │
│  │  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘                    │  │
│  │                                                                        │  │
│  │  Tracks: Kick, Bass, Sub, Hats, Perc, Stabs, Ride, Atmosphere,        │  │
│  │          FX Risers, Vocals, Industrial, Textures, Peak Lead...         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AUDIO ANALYSIS FEEDBACK                            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Stem separation for per-instrument analysis                        │  │
│  │  • Spectral profile comparison against reference tracks               │  │
│  │  • Frequency conflict detection                                       │  │
│  │  • Mix balance evaluation                                             │  │
│  │  • Iterative refinement based on analysis results                     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Claude Skills (`/skills`)
Music production intelligence distilled from professional techno producers (Charlotte de Witte, Adam Beyer, Ben Klock). These aren't prompts - they're structured decision-making frameworks:

| Skill | Purpose |
|-------|---------|
| `arrangement-intelligence.md` | Scene structure, energy curves, false drops, tension/release |
| `automation-composer.md` | Filter sweeps, volume fades, reverb throws, LFO rates |
| `sound-design-layering.md` | 3-layer kicks, bass construction, resampling techniques |
| `mix-analysis.md` | Frequency carving, bus processing, mono compatibility |
| `groove-timing-intelligence.md` | Micro-timing offsets, MPC swing, polyrhythms |

### 2. Sample Library (`library.json`)
Since AI cannot "hear" audio, samples are pre-analyzed with spectral data:

```json
{
  "file_name": "kick_hard_001.wav",
  "spectral_centroid_mean": 297.2,
  "brightness": 0.04,
  "warmth": 1.0,
  "attack_time_ms": 11.4,
  "energy_level": 8,
  "texture_tags": ["punchy", "hard", "transient"]
}
```

The AI selects samples based on spectral characteristics, energy level, and texture tags - matching sonic profiles without hearing.

### 3. Note Generation Scripts (`generate_*.py`)
Python scripts that generate MIDI note data following music theory rules:

- `generate_bass.py` - Half-time techno bass in G minor with velocity evolution
- `generate_hats.py` - Polyrhythmic hat patterns with swing
- `generate_peak_bass.py` - Aggressive peak-section bass patterns

These output JSON note arrays that are inserted via the Ableton MCP.

### 4. Performance Engine (`perform_subterranean_v13.py`)
A 60KB Python script that performs the composed track via OSC:

**Key Features:**
- **Scene transitions** - Fires scenes at musically appropriate times
- **Volume automation** - Fades instruments in/out for natural progression
- **Spectral carving** - Real-time EQ adjustments to prevent frequency collision
- **Polymetric triggers** - Elements fire on prime-number intervals (7, 11, 13 bars)
- **Vocal mangling** - Dynamic filter/reverb modulation on vocal tracks

```python
# Example: Track mapping with spectral priority
RIGID_TRACKS = {T["KICK"], T["BASS"], T["SUB_BASS"]}  # Never swing
TIGHT_TRACKS = {T["STAB"], T["PEAK_LEAD"], T["DING"]}  # Minimal timing variance
```

### 5. Ableton MCP Integration
Forked from the Ableton MCP Extended project, with additions for:
- Clip note manipulation
- Device parameter automation
- Sample loading workflows
- Scene management

### 6. ElevenLabs MCP
Generates vocal elements:
- Text-to-speech for spoken word sections
- Sound effects for risers and impacts

## Workflow

```
1. RESEARCH          Gemini Deep Research → Music theory reports
        ↓
2. SKILLS            Reports → Claude Skills (structured knowledge)
        ↓
3. SAMPLE SELECTION  library.json → Match spectral profiles to needs
        ↓
4. COMPOSITION       Ableton MCP → Create tracks, clips, notes
        ↓
5. SOUND DESIGN      Ableton MCP → Load/configure instruments & FX
        ↓
6. PERFORMANCE       Ableton OSC → perform_subterranean_v13.py
        ↓
7. ANALYSIS          Stem separation → Frequency analysis → Feedback
        ↓
8. ITERATION         Adjustments based on analysis → Repeat 4-7
```

## Results & Findings

**The Output:** A 4:30 peak-time techno track at 133 BPM in G minor

**What Worked:**
- Structured music theory knowledge enabled coherent composition
- Spectral analysis allowed sample selection without hearing
- OSC-based performance created natural transitions
- Iterative feedback loop improved mix quality

**Limitations Discovered:**
- Models adhere closely to standard music theory
- Difficulty generating truly novel/unexpected patterns
- Creative "outside the box" decisions remain challenging
- Real-time audio feedback would improve iteration speed

## Project Structure

```
AbletonComposer/
├── skills/                      # Claude music production skills
│   ├── MASTER-SKILL-INDEX.md   # Skill overview and integration
│   ├── arrangement-intelligence.md
│   ├── automation-composer.md
│   ├── sound-design-layering.md
│   ├── mix-analysis.md
│   └── groove-timing-intelligence.md
├── AbletonOSC/                  # OSC library for live performance
├── library.json                 # Pre-analyzed sample database
├── generate_bass.py             # Bass note generation
├── generate_hats.py             # Hat pattern generation
├── generate_peak_bass.py        # Peak section bass
├── perform_subterranean_v13.py  # Performance script
├── composer-instructions.md     # Project orchestration guide
└── mcp-setup/                   # MCP configuration guides
```

## Requirements

- Ableton Live 12
- [Ableton MCP Extended](https://github.com/ahujasid/ableton-mcp) (forked)
- [AbletonOSC](https://github.com/ideoforms/AbletonOSC) Remote Script
- Claude Code with MCP support
- ElevenLabs MCP (optional, for vocals)
- Python 3.x with `python-osc`

## Future Directions

This experiment suggests that future models may be capable of:
- Generating genuinely novel musical patterns
- Real-time audio analysis and adjustment
- Cross-genre composition with intentional rule-breaking
- Collaborative human-AI composition workflows

The goal is to measure AI creativity not just by technical execution, but by the ability to produce unexpected, emotionally resonant music that transcends training data patterns.

---

*Built with Claude Code, Ableton Live 12 MCP, and AbletonOSC*

*An experiment in AI creativity by [@hughes7370](https://github.com/hughes7370)*
