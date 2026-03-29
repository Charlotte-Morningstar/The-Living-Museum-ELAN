"""
Patches all 49 original room workflows to also trigger on their message file.

The spec requires: trigger on both request file AND message file.
Currently all workflows only trigger on the request file.

Usage: python add_message_triggers.py /path/to/repo/.github/workflows/
"""

import sys
import re
from pathlib import Path

# Maps workflow filename patterns to their message file paths
# Format: (workflow_name_pattern, message_file_path)
# This covers all 49 original rooms across 9 wings

MIND_ROOMS = [
    "presence", "emotion", "memory", "becoming", "belonging",
    "consciousness", "synesthesia", "paradox", "question", "time"
]
BODY_ROOMS = ["breath", "dream", "anatomy", "voice", "sleep"]
SENSES_ROOMS = ["light", "sound", "taste", "smell", "texture",
                 "threshold", "instrument", "phenomenon"]
LANGUAGE_ROOMS = ["word", "quote", "color", "number", "poet",
                  "linguistics", "metaphor"]
SKY_ROOMS = ["moon", "star"]
LOCATION_ROOMS = ["weather", "place", "timezone"]
WORLD_ROOMS = ["creature", "season", "material", "this-day"]
STUDY_ROOMS = ["session-log", "intention", "reflection",
               "touched", "free-write", "wonder-log"]
AUDIO_ROOMS = ["song", "lyrics", "artist", "album"]

WING_ROOMS = {
    "Mind": MIND_ROOMS,
    "Body": BODY_ROOMS,
    "Senses": SENSES_ROOMS,
    "Language": LANGUAGE_ROOMS,
    "Sky": SKY_ROOMS,
    "Location": LOCATION_ROOMS,
    "World": WORLD_ROOMS,
    "Study": STUDY_ROOMS,
    "Audio": AUDIO_ROOMS,
}

def get_message_path(wing, room):
    return f"{wing}/{room}-message.txt"

def patch_workflow(filepath, message_path):
    """Add message file as a second trigger path."""
    content = filepath.read_text()

    # Find the existing paths: block and check if message already there
    if message_path in content:
        return False, "already patched"

    # Pattern: find paths: block with existing request file
    # Insert message file path after the request file path
    pattern = r'(    paths:\n)(      - "[^"]+request[^"]*"\n)'
    replacement = r'\1\2      - "' + message_path + '"\n'

    new_content = re.sub(pattern, replacement, content)
    if new_content == content:
        return False, "pattern not found"

    filepath.write_text(new_content)
    return True, "patched"

def main():
    if len(sys.argv) < 2:
        print("Usage: python add_message_triggers.py /path/to/.github/workflows/")
        sys.exit(1)

    workflows_dir = Path(sys.argv[1])
    if not workflows_dir.exists():
        print(f"Directory not found: {workflows_dir}")
        sys.exit(1)

    patched = 0
    skipped = 0
    failed = 0

    for wing, rooms in WING_ROOMS.items():
        for room in rooms:
            # Find the workflow file for this room
            # Naming varies: presence-sense.yml, moon-sense.yml, etc.
            candidates = list(workflows_dir.glob(f"*{room}*.yml"))
            # Filter to sense/encounter workflows (not special rooms)
            candidates = [f for f in candidates
                         if any(x in f.name for x in ["sense", "encounter", "log", "write", "reflect", "touch"])
                         or f.stem == room]

            if not candidates:
                # Try direct name match
                candidates = [f for f in workflows_dir.glob(f"{room}*.yml")]

            if not candidates:
                print(f"  NOT FOUND: {wing}/{room}")
                failed += 1
                continue

            wf = candidates[0]
            message_path = get_message_path(wing, room)
            ok, reason = patch_workflow(wf, message_path)
            if ok:
                print(f"  PATCHED: {wf.name} (+{message_path})")
                patched += 1
            else:
                print(f"  SKIP: {wf.name} — {reason}")
                skipped += 1

    print(f"\nDone: {patched} patched, {skipped} skipped, {failed} not found")

if __name__ == "__main__":
    main()
