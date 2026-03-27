#!/usr/bin/env python3
"""Add Temporal Awareness to Existing Rooms

This script modifies an existing room script to integrate with the
Living Museum's temporal awareness engine. It adds:
- Time period awareness (what hour, what quality of light)
- Absence tracking (how long since last visit)
- Journey context (what rooms were visited before this one)
- Cross-room fragment sharing

Usage:
    python integration/add_temporal.py <room_script_path>

The script creates a modified copy with '_integrated' suffix.
"""

import sys
import os
import re
from pathlib import Path

INTEGRATION_HEADER = '''
# ---- Living Museum Integration ----
import sys as _sys
from pathlib import Path as _Path
_MUSEUM_ROOT = _Path(__file__).parent.parent
if str(_MUSEUM_ROOT.parent) not in _sys.path:
    _sys.path.insert(0, str(_MUSEUM_ROOT.parent))

try:
    from engine.integration import RoomIntegration
    _HAS_MUSEUM = True
except ImportError:
    _HAS_MUSEUM = False
# ---- End Integration Header ----
'''

INTEGRATION_ON_ENTER = '''
    # ---- Living Museum: On Enter ----
    _museum_context = ""
    if _HAS_MUSEUM:
        try:
            _integration = RoomIntegration("{room_name}", str(_Path(__file__).parent.parent.parent))
            _ctx = _integration.on_enter(carrying_text, visits)
            _museum_context = _ctx.get("arrival_text", "")
            _journey_note = _ctx.get("journey_note", "")
            if _museum_context:
                response_parts.insert(1, _museum_context)
            if _journey_note:
                response_parts.insert(2, _journey_note)
        except Exception:
            pass
    # ---- End On Enter ----
'''

INTEGRATION_ON_EXIT = '''
    # ---- Living Museum: On Exit ----
    if _HAS_MUSEUM:
        try:
            _integration.on_exit()
        except Exception:
            pass
    # ---- End On Exit ----
'''


def add_temporal_to_script(script_path):
    """Add temporal awareness integration to an existing room script."""
    script_path = Path(script_path)
    if not script_path.exists():
        print(f"Error: {script_path} not found")
        return False

    content = script_path.read_text()

    # Check if already integrated
    if "Living Museum Integration" in content:
        print(f"{script_path.name} is already integrated.")
        return True

    # Extract room name from filename
    room_name = script_path.stem.replace("_sense", "").replace("_", "-")

    # Add integration header after imports
    import_section_end = 0
    for match in re.finditer(r'^(?:import |from )', content, re.MULTILINE):
        line_end = content.index('\n', match.start())
        import_section_end = max(import_section_end, line_end + 1)

    if import_section_end > 0:
        content = content[:import_section_end] + INTEGRATION_HEADER + content[import_section_end:]
    else:
        content = INTEGRATION_HEADER + content

    # Write the integrated version
    output_path = script_path.parent / f"{script_path.stem}_integrated.py"
    output_path.write_text(content)
    print(f"Created integrated version: {output_path}")
    print(f"Room name detected: {room_name}")
    print(f"\nTo complete integration, add the on_enter block after loading visits data")
    print(f"and the on_exit block before writing the response file.")
    print(f"\nSee integration/example-room/ for a complete example.")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python integration/add_temporal.py <room_script_path>")
        print("\nThis adds Living Museum temporal awareness to an existing room script.")
        print("Creates a new file with '_integrated' suffix.")
        sys.exit(1)

    add_temporal_to_script(sys.argv[1])


if __name__ == "__main__":
    main()
