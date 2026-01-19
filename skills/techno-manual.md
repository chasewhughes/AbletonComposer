Techno Production Field Manual

Target Style: Drumcode / Peak-Time Techno
Platform: Ableton Live (Adaptable to other DAWs)

1. Project Initialization

Configure the DAW environment before composing.

Sample Rate/Bit Depth: 24-bit / 44.1kHz.

Tempo: 128 BPM – 132 BPM (Standard: 130 BPM).

Key Signature:

F Minor (Root ~43.6Hz)

G Minor (Root ~49Hz)

Reasoning: Sub-bass resonant frequency optimization.

Scene Execution Matrix (Session View Setup)

Pre-load these 8 scenes to map energy progression while jamming.

INTRO: Minimal (Kick, Bass, Atmosphere).

BUILD 1: High-energy percussion enters (Closed Hats, Main Stab).

BUILD 2: Full percussion (Open Hats, Textures). Energy ramps.

TENSION: The Breakdown. Kick/Bass drop out. Vocals/Atmosphere forward.

DROP: Maximum energy. Rumble and Ride Cymbal active.

PEAK: Sustained energy. Variations and response elements.

COOL DOWN: Strip back elements. Remove Ride/Highs.

OUTRO: Minimal elements for DJ mix-out.

2. Asset Selection ("The Crate")

Pre-load assets based on source logic.

A. Splice/Sample-Based Assets (The Organic Layer)

Kick: Processed 909-style sample. (Must have transient "click").

Hi-Hats/Rides: Real cymbal recordings (shimmer/phase variance).

Atmosphere: Field recordings, industrial ambience, vinyl crackle.

Vocal: Spoken word phrases (short, loopable mantras).

B. Internal Synthesis (The Precision Layer)

Sub Bass/Roll: Ableton Operator (Sine/Triangle wave).

Synth Stabs: Wavetable or Analog (for envelope/filter automation).

3. Core Track Configuration

Apply these specific processing chains to the primary elements.

Track 1: The Kick (Anchor)

Source: Mono Sample (50Hz–100Hz focus).

Pattern: 4/4 (1, 1.2, 1.3, 1.4).

Volume: -6.0 dB.

Processing Chain:

EQ Eight: Low Cut @ 30Hz (48dB/oct); Bell Cut @ 200-300Hz (remove boxiness).

Compressor: Slow Attack (10-30ms), Fast Release, Ratio 4:1.

Utility: "Bass Mono" enabled < 120Hz.

Clipper (Optional): Hard clip 1-2dB off the transient peak.

Track 2: Rolling Bass (Groove)

Source: Operator (Sine/Triangle).

Pattern: 16th notes on off-beats (Empty downbeat).

Processing Chain:

EQ Eight: Low Cut @ 40Hz, High Cut @ 500Hz.

Sidechain Compressor: Triggered by Kick. Threshold -18dB, Ratio 4:1, Attack 0.01ms, Release timed to 1/16th note.

Track 3: The Rumble (Atmosphere)

Source: Reverb Return of the Kick OR specialized rumble loop.

Chain (Reverb Method):

Reverb: 100% Wet, Decay 1.5s–3.0s.

Distortion: Amp or Drum Buss (Crunch).

Filter: Low-Pass @ 150Hz.

Sidechain: Heavy ducking from Kick (pumping effect).

M/S EQ: High-Pass the SIDE signal @ 100-150Hz (Keep low-end mono).

Track 4: Ride Cymbal (Energy)

Source: Natural Ride sample.

Pattern: 8th notes.

Processing Chain:

EQ: High Pass @ 2kHz.

Sidechain: Heavy ducking by Kick.

Velocity: Downbeat ~70, Upbeat ~110.

4. Advanced Engineering

Phase Alignment (Kick & Bass)

Visual Check: Use Oscilloscope (e.g., Psyscope).

Zero-Crossing: Align the first positive excursion of the Bass to match the Kick’s fundamental phase.

Tuning: Ensure Kick tail resolves to the Key (e.g., F1) to prevent beating.

Polarity: Flip polarity on Bass channel to check for volume increase (constructive interference).

Filter Topology (Linear vs. Minimum Phase)

Removing Sub-Rumble (<30Hz): Use Minimum Phase (Gentle Slope 12-18dB/oct).

Reason: Steep Linear Phase causes pre-ringing (ghost suck effect); Steep Minimum Phase causes group delay (smearing).

Parallel Processing: Use Linear Phase only.

Reason: Essential to prevent phase cancellation when mixing wet/dry signals.

Dynamic Spectral Management

Avoid Static Low Cuts: Do not high-pass Bass at 30Hz with steep slopes (causes group delay).

Dynamic EQ (Sidechain):

Insert Dynamic EQ on Bass.

Create Bell Filter @ Kick Fundamental (e.g., 60Hz).

Route Kick to Sidechain.

Action: Cut 3-6dB @ 60Hz only when Kick hits.

The Low-End Bus (Kick + Bass Group)

Routing: Route Kick and Bass tracks to a single Group Bus before the Master.

Glue Compressor: Slow Attack (30ms), Fast Release, Ratio 2:1, 1-2dB Gain Reduction.

Purpose: Glues the kick decay into the bass attack.

Saturation: Subtle Tube/Tape Drive.

Purpose: Binds harmonics and helps translation on small speakers.

Safety Utility: Force everything < 100Hz to MONO at the Bus level.

Mono Compatibility (Rumble)

Sub-Bass (<100Hz): 100% Mono.

Low-Mids (100-300Hz): Controlled width (attenuate sides).

High-Mids (>300Hz): Boost sides for width/air.

5. Groove & Humanization

Micro-Timing (The "Push & Pull")

Kick: 0ms (Dead Grid).

Closed Hat: Nudge -5ms to -12ms (Rushing/Urgent).

Open Hat: Nudge +5ms to +20ms (Dragging/Swing).

Snare/Clap: Nudge +15ms to +30ms (Lazy/Heavy).

Polymeters (Hypnotic Loops)

Technique: Unlink Clip Envelopes or use odd loop lengths.

3/16 Loop: Rushing, high energy (Hats).

5/16 Loop: Funky, off-kilter (Bass/Leads).

7/16 Loop: Deep trance, long evolution (Textures).

Resolution: A 5-step loop against a 4/4 kick resolves every 5 bars.

Velocity Variation

Manual: Set Downbeats ~100, Off-beats ~115.

Randomization: Apply Velocity MIDI effect (Random range: 10-15).

Groove Pool: Apply MPC 16 Swing-55 or 57. Timing: 10-20%.

6. Texture & Sound Design

The "Wash Out" Rack (Transition Tool)

Create an Audio Effect Rack with two chains (Dry/Wet). Map one Macro to:

Dry Vol: 0dB to -inf.

Wet Vol: -inf to 0dB.

High Pass Filter: 20Hz to 5kHz (on Wet chain).

Simple Delay: Feedback 70-80% (on Wet chain).

Reverb: Long Hall (on Wet chain).

Shepard Tone Riser

Oscillators: 3 Sine waves.

Tuning: Root, +1 Octave, +2 Octaves.

Pitch: Automate all to rise +12st over 8 bars.

Volume: Fade IN bottom octave, Fade OUT top octave.

FM Cymbals (Metallic Dissonance)

Source: FM Synth (Operator).

Oscillators: 4-6 Ops with non-integer ratios (e.g., 1:1.45, 1:3.89).

Effect: Apply Ring Modulation.

Result: Inharmonic, cold, industrial textures that sample packs cannot replicate.

Resampling Recursion (The "Blawan" Method)

Generate: Create a basic bleep/percussion loop.

Destroy: Apply heavy Distortion, Reverb, Modulation.

Resample: Bounce to audio.

Pitch Down: Crucial Step. Pitch the audio down -7 or -12 semitones.

Result: Reverb tails become dark/gritty; artifacts become texture.

Chop: Cut micro-loops from the mangled audio.

Rumble/Feedback Loops

Return Track: Enable "Send to Self".

Limit: Place Limiter at end of chain (Safety).

Chain: Delay (Short) -> Pitch Shift -> Distortion -> Filter.

Result: Self-oscillating industrial drones.

7. Arrangement Structure

The 16-Bar Rule

Changes occur every 16 bars.

Micro-variations (fills/glitches) occur every 4 bars.

The 7-Minute Template

Time

Section

Elements

0:00

Intro

Kick, Rumble, stripped percussion. (DJ Tool).

1:30

Build A

Introduce Motif. Energy ramp (Hats/Rides).

3:00

Breakdown 1

Kick removed. Narrative/Vocal focus.

4:00

Fake Peak

Drop with restrained energy (No Ride/Filtered Rumble).

4:30

Main Break

"Deep Vacuum." V-Shape EQ. Long silence.

5:30

Main Drop

Maximum energy. All elements. Full Rumble & Ride.

6:30

Outro

Subtractive. Remove hook, leave drums.

The "Fake Drop"

Build tension for 32 bars.

At Bar 33 (Expected Drop): Insert 8 bars of silence/minimalism/vocal.

Real Drop hits at Bar 41.

8. Mixing & Loudness (Clip-to-Zero)

Crest Factor Management

Goal: Shave "invisible peaks" (transients) to gain headroom.

Individual Channels (Kick/Snare): Hard Clip 1-3dB off the top.

Drum Bus: Hard Clip or Soft Clip Pro. Threshold -1.0dB.

Master Bus Chain

V-Shape EQ (Automation Only):

High Pass: Automate 20Hz -> 200Hz during builds. Snap to 20Hz at drop.

High Shelf: Automate gain 0dB -> +4dB during builds. Snap to 0dB at drop.

Bus Compressor: SSL Style. Slow Attack (30ms), Ratio 2:1, Gain Reduction ~1dB.

Hard Clipper: StandardCLIP. Shave 1-2dB of summed peaks.

Limiter: FabFilter Pro-L2. Ceiling -0.3dB (or -1.0dBTP). Lookahead 0.5ms.

Spectral Reference (Pink Noise)

Mix balance should approximate a Pink Noise curve (-3dB/octave slope).

Sub-bass (40-60Hz) is the loudest point.

Highs (6kHz+) are boosted/saturated to cut through large systems.