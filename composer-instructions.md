I have enclosed:

techno-manual.md file, which is a set of detailed instructions we must follow using the primarily Ableton MCP to create this track according to this documentation.

## CRITICAL: Production Intelligence Skills

Before starting any production work, you MUST reference the professional production intelligence skills located in the `skills/` folder. These skills transform basic track creation into Charlotte de Witte / Adam Beyer level productions:

- **[skills/MASTER-SKILL-INDEX.md](skills/MASTER-SKILL-INDEX.md)** - Start here for overview and skill integration guidance
- **[skills/arrangement-intelligence.md](skills/arrangement-intelligence.md)** - Scene structure, energy curves, false drops
- **[skills/sound-design-layering.md](skills/sound-design-layering.md)** - Multi-sample layering, kick construction, resampling
- **[skills/mix-analysis.md](skills/mix-analysis.md)** - Frequency conflict resolution, EQ carving, bus processing
- **[skills/groove-timing-intelligence.md](skills/groove-timing-intelligence.md)** - Micro-timing, MPC swing, polyrhythms
- **[skills/automation-composer.md](skills/automation-composer.md)** - Filter sweeps, volume automation, effect throws

**Each phase below references which skills to apply. You must consult these skills to make intelligent production decisions, not just execute technical steps.**

---

1. Create a 'to_do.md' file for this project which outlines step-by-step what you need to do according to this file to create the song in Ableton. As you finish checkpoints, update the 'to-do.md' file to mark your progress.

Be very careful because the last time we tried this, the clips were not placed in the correct track and and scene and lacked notes, could not play. Also, if you have any questions for the creator, let me know and I will ask him. 

2. **Sample Library System (`library.json`):**

   **YOU HAVE ACCESS TO `library.json` - A comprehensive sample database with spectral analysis data.**

   **What library.json contains:**
   - 193 pre-analyzed samples with full metadata
   - Spectral characteristics: `spectral_centroid_mean`, `brightness`, `warmth`
   - Transient data: `attack_time_ms`, `onset_density`
   - Categorization: `category`, `subcategory`, `energy_level` (1-10), `texture_tags`
   - File paths: `file_path` (absolute path to sample)
   - BPM and key information where applicable

   **How to use library.json for sample selection:**

   a) **Search by category** (grep for `"category": "kick"` or `"category": "bass"`)
   b) **Search by energy level** (grep for `"energy_level": 8` for high-energy samples)
   c) **Search by texture** (grep for `"dark"`, `"bright"`, `"rumbling"`, etc. in texture_tags)
   d) **Check attack time** (avoid samples with `attack_time_ms > 100` for rhythmic elements like kicks/hats)
   e) **Filter by brightness** (0.0-1.0 scale; >0.5 = bright samples for transients, <0.3 = dark samples for subs)
   f) **Check warmth** (0.0-1.0 scale; >0.7 = warm/full-bodied samples)

   **Sample selection workflow:**
   1. Grep `library.json` for desired characteristics (e.g., `"category": "kick"` AND `"energy_level": 8`)
   2. Check spectral data to understand frequency content (brightness/warmth/centroid)
   3. Note the `file_path` from library.json entry
   4. Copy samples from source library to local `samples/` folder
   5. Load into Ableton using MCP tools

   **Example library.json entry:**
   ```json
   {
     "file_name": "kick_hard_001.wav",
     "file_path": "/Users/.../samples/kick_hard_001.wav",
     "category": "kick",
     "subcategory": "hard",
     "spectral_centroid_mean": 297.2,
     "brightness": 0.04,
     "warmth": 1.0,
     "attack_time_ms": 11.4,
     "onset_density": 4.15,
     "energy_level": 8,
     "texture_tags": ["punchy", "hard", "transient"]
   }
   ```

   **CRITICAL:** Before requesting manual sample loading, you MUST first load a Simpler device onto the target track using `mcp__ableton__load_instrument_or_effect` with URI `query:Synths#Simpler`. Users cannot drag samples onto tracks without Simpler already loaded.

   **Alternate search method (if needed):** Grep `.claude/metadata/LIBRARY_INDEX.md` by category, BPM, energy, or texture to find sample IDs [###], then grep `library.json` with the filename to get full details. 

3. When finished with the song, create a 'perform_set.py' for AbletonOSC live performance. Reference the existing `perform_set.py` as a template - it includes the local pythonosc import path, correct OSC addresses (e.g., `/live/scene/fire`, `/live/track/set/mute`), and performance macros. The `AbletonOSC/` folder contains the required pythonosc library.

Notes:

1. You will be unlikely to transfer recordings from sample library into the tracks, or some other actions that need to be manually performed, into a ‘manual-requirements.md’ file, if they are required to proceed, stop your process and request me to complete them for you. Important: Splice samples in Ableton's browser are being treated as MIDI files (likely they contain MIDI data or Ableton is interpreting them that way).

2. If you encounter something that you need to do manually during this process, but is able to perform using the Ableton-MCP, create a ‘ableton-mcp-additions.mcp’ addition file which will request what to add to the ableton-mcp. 

3. If using 11Labs Only: Some areas of the documentation may refer to 11Labs content, if this is the case, use the 11Labs MCP to retrieve the files and collect them.

4. If downloads are necessary, add them to out project folder to keep everything organized and add it to Ableton via the mcp if you can, if not , then document it for manual to do.

5. When setting up tracks and clips, be sure that they include notes when you set them up in accordance with teh protocol document, otherwise you will insert the clips but they will not sound.