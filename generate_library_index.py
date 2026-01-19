#!/usr/bin/env python3
"""
Library Index Generator for Audio Sample Library
Converts large library.json into a searchable LIBRARY_INDEX.md for efficient Claude Code lookup
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def format_texture_tags(tags: List[str], max_tags: int = 3) -> str:
    """Format texture tags for display, limiting to most relevant"""
    if not tags:
        return "N/A"
    return ", ".join(tags[:max_tags])


def format_key(sample: Dict[str, Any]) -> str:
    """Format key information in a consistent way"""
    key = sample.get("key", "Unknown")
    root_note = sample.get("root_note", "")
    scale_type = sample.get("scale_type", "")

    if key and key != "Unknown" and key != "atonal":
        return key
    elif root_note and scale_type:
        return f"{root_note} {scale_type}"
    elif sample.get("is_tonal") in [False, "False", "false"]:
        return "Atonal"
    else:
        return "Unknown"


def get_vibe_descriptor(sample: Dict[str, Any]) -> str:
    """Create a concise vibe descriptor from texture tags and energy"""
    texture_tags = sample.get("texture_tags", [])
    energy = sample.get("energy_level", 5)

    vibe_parts = []
    if texture_tags:
        vibe_parts.extend(texture_tags[:2])

    if energy >= 8:
        vibe_parts.append("High Energy")
    elif energy <= 3:
        vibe_parts.append("Low Energy")

    return "/".join(vibe_parts) if vibe_parts else "Neutral"


def get_category_display(sample: Dict[str, Any]) -> str:
    """Get category with subcategory if available"""
    category = sample.get("category", "Unknown")
    subcategory = sample.get("subcategory")

    if subcategory and subcategory != category:
        return f"{category}/{subcategory}"
    return category


def calculate_spectral_descriptor(sample: Dict[str, Any]) -> str:
    """Create a human-readable spectral descriptor"""
    centroid = sample.get("spectral_centroid_mean", 0)

    if centroid < 300:
        return f"{centroid:.0f}Hz (Very Low)"
    elif centroid < 800:
        return f"{centroid:.0f}Hz (Low)"
    elif centroid < 2000:
        return f"{centroid:.0f}Hz (Mid)"
    elif centroid < 5000:
        return f"{centroid:.0f}Hz (High-Mid)"
    else:
        return f"{centroid:.0f}Hz (High)"


def check_timing_warning(sample: Dict[str, Any]) -> str:
    """Check for potential timing issues based on attack time"""
    attack_time = sample.get("attack_time_ms", 0)

    if attack_time > 100:
        return f" ⚠️ SLOW ATTACK ({attack_time:.0f}ms - Use as Atmosphere/Drone)"
    return ""


def generate_index_entry(idx: int, sample: Dict[str, Any]) -> str:
    """Generate a single index entry line"""
    file_name = sample.get("file_name", "Unknown")
    file_path = sample.get("file_path", "")
    category = get_category_display(sample)
    key = format_key(sample)
    bpm = sample.get("bpm", 0)
    bpm_display = f"{bpm:.0f}" if bpm and bpm > 0 else "N/A"
    vibe = get_vibe_descriptor(sample)
    spectral = calculate_spectral_descriptor(sample)
    duration = sample.get("duration_seconds", 0)
    warning = check_timing_warning(sample)

    entry = (
        f"[{idx:03d}] `{file_name}` | "
        f"Type: {category} | "
        f"Key: {key} | "
        f"BPM: {bpm_display} | "
        f"Duration: {duration:.2f}s | "
        f"Vibe: {vibe} | "
        f"Spectral: {spectral}"
        f"{warning}"
    )

    return entry


def generate_category_summary(samples: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """Group sample indices by category for quick lookup"""
    category_map = {}

    for idx, sample in enumerate(samples, start=1):
        category = sample.get("category", "Unknown")
        if category not in category_map:
            category_map[category] = []
        category_map[category].append(idx)

    return category_map


def generate_key_summary(samples: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """Group sample indices by key for quick lookup"""
    key_map = {}

    for idx, sample in enumerate(samples, start=1):
        key = format_key(sample)
        if key not in key_map:
            key_map[key] = []
        key_map[key].append(idx)

    return key_map


def generate_bpm_summary(samples: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """Group sample indices by BPM range for quick lookup"""
    bpm_ranges = {
        "Very Slow (<100)": [],
        "Slow (100-115)": [],
        "Medium (115-130)": [],
        "Fast (130-145)": [],
        "Very Fast (>145)": [],
        "No BPM": []
    }

    for idx, sample in enumerate(samples, start=1):
        bpm = sample.get("bpm", 0)

        if not bpm or bpm <= 0:
            bpm_ranges["No BPM"].append(idx)
        elif bpm < 100:
            bpm_ranges["Very Slow (<100)"].append(idx)
        elif bpm < 115:
            bpm_ranges["Slow (100-115)"].append(idx)
        elif bpm < 130:
            bpm_ranges["Medium (115-130)"].append(idx)
        elif bpm < 145:
            bpm_ranges["Fast (130-145)"].append(idx)
        else:
            bpm_ranges["Very Fast (>145)"].append(idx)

    return bpm_ranges


def main():
    # Get library.json path
    script_dir = Path(__file__).parent
    library_path = script_dir / "library.json"

    if not library_path.exists():
        print(f"ERROR: Could not find library.json at {library_path}")
        sys.exit(1)

    print(f"Loading library from {library_path}...")

    # Load the library
    with open(library_path, 'r', encoding='utf-8') as f:
        library_data = json.load(f)

    samples = library_data.get("samples", [])
    metadata = library_data.get("metadata", {})

    print(f"Loaded {len(samples)} samples")
    print("Generating index...")

    # Generate summaries
    category_summary = generate_category_summary(samples)
    key_summary = generate_key_summary(samples)
    bpm_summary = generate_bpm_summary(samples)

    # Build the markdown content
    md_lines = [
        "# AUDIO SAMPLE LIBRARY - QUICK INDEX",
        "",
        f"**Total Samples:** {len(samples)}",
        f"**Analysis Date:** {metadata.get('analyzed_at', 'Unknown')}",
        f"**Source Directory:** `{metadata.get('source_directory', 'Unknown')}`",
        "",
        "---",
        "",
        "## HOW TO USE THIS INDEX",
        "",
        "This is a **compressed search index** for efficient Claude Code lookup.",
        "",
        "### Search Workflow:",
        "1. **Search:** Use Grep on this file to find candidates by category, key, BPM, or vibe",
        "2. **Fetch:** Once you find a candidate ID [###], use Grep on library.json to get full details",
        "3. **Execute:** Use the file_path from library.json in your Ableton commands",
        "",
        "### Example Searches:",
        "- Find all bass samples in G minor: `grep -i \"Type: Bass\" LIBRARY_INDEX.md | grep -i \"Key: G\"`",
        "- Find high-energy kicks: `grep -i \"kick\" LIBRARY_INDEX.md | grep -i \"High Energy\"`",
        "- Find samples around 131 BPM: `grep \"BPM: 13[0-5]\" LIBRARY_INDEX.md`",
        "",
        "### Important Notes:",
        "- ⚠️ Samples with SLOW ATTACK (>100ms) should NOT be used as rhythmic elements",
        "- Use them for Atmosphere, Drone, or Pad tracks instead",
        "",
        "---",
        "",
        "## QUICK CATEGORY LOOKUP",
        ""
    ]

    # Add category summary
    for category, indices in sorted(category_summary.items()):
        md_lines.append(f"**{category}:** {len(indices)} samples - IDs: {', '.join(f'[{i:03d}]' for i in indices[:10])}" +
                       (f" ... (+{len(indices)-10} more)" if len(indices) > 10 else ""))

    md_lines.extend([
        "",
        "---",
        "",
        "## QUICK KEY LOOKUP",
        ""
    ])

    # Add key summary
    for key, indices in sorted(key_summary.items()):
        md_lines.append(f"**{key}:** {len(indices)} samples - IDs: {', '.join(f'[{i:03d}]' for i in indices[:10])}" +
                       (f" ... (+{len(indices)-10} more)" if len(indices) > 10 else ""))

    md_lines.extend([
        "",
        "---",
        "",
        "## QUICK BPM RANGE LOOKUP",
        ""
    ])

    # Add BPM summary
    for bpm_range, indices in bpm_summary.items():
        if indices:
            md_lines.append(f"**{bpm_range}:** {len(indices)} samples - IDs: {', '.join(f'[{i:03d}]' for i in indices[:10])}" +
                           (f" ... (+{len(indices)-10} more)" if len(indices) > 10 else ""))

    md_lines.extend([
        "",
        "---",
        "",
        "## FULL SAMPLE INDEX",
        "",
        "**Format:** [ID] `filename` | Type | Key | BPM | Duration | Vibe | Spectral",
        ""
    ])

    # Add all sample entries
    for idx, sample in enumerate(samples, start=1):
        md_lines.append(generate_index_entry(idx, sample))

    md_lines.extend([
        "",
        "---",
        "",
        "## LOOKUP INSTRUCTIONS FOR CLAUDE",
        "",
        "When you need a sample:",
        "1. Grep this file for your criteria (e.g., 'Bass', 'G Minor', '131 BPM')",
        "2. Note the [ID] of promising candidates",
        "3. Use Grep on library.json: `grep -A 50 '\"file_name\": \"<filename>\"' library.json`",
        "4. Extract the full file_path for use in Ableton MCP commands",
        "",
        "**Pro Tip:** For precise spectral/envelope data, always fetch the full JSON entry.",
        ""
    ])

    # Write the output
    output_path = script_dir / ".claude" / "metadata" / "LIBRARY_INDEX.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    print(f"✓ Generated {output_path}")
    print(f"✓ Index contains {len(samples)} samples")
    print(f"✓ {len(category_summary)} categories indexed")
    print(f"✓ {len(key_summary)} keys indexed")
    print("\nYou can now use Grep to search LIBRARY_INDEX.md efficiently!")


if __name__ == "__main__":
    main()
