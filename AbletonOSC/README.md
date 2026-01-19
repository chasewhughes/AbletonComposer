# AbletonOSC Setup

This folder contains the pythonosc library needed for the perform_set.py script.

## Installation Steps

### 1. Install the AbletonOSC Remote Script in Ableton Live

Copy the `abletonosc` folder from the full AbletonOSC repository to your Ableton MIDI Remote Scripts folder:

**macOS:**
```
/Users/YOUR_USERNAME/Music/Ableton/User Library/Remote Scripts/
```

Or for the application bundle:
```
/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/MIDI Remote Scripts/
```

### 2. Enable in Ableton Live

1. Open Ableton Live
2. Go to **Preferences** → **Link/Tempo/MIDI**
3. Under **Control Surface**, select **AbletonOSC** from the dropdown
4. Leave Input and Output as "None"

### 3. Verify Connection

The AbletonOSC script listens on:
- **Port 11000** (receive commands)
- **Port 11001** (send responses)

## Running perform_set.py

From the AbletonComposer directory:

```bash
python perform_set.py
```

Or with auto-play through all scenes:

```bash
python perform_set.py --auto
```

## Full AbletonOSC Repository

For the complete AbletonOSC project with documentation:
https://github.com/ideoforms/AbletonOSC

The `abletonosc` Remote Script folder from that repo is what needs to be installed in Ableton.
