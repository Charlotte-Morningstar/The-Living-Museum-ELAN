#!/usr/bin/env python3
"""Validate a Room Integration

Checks that a room has all the necessary files and structure
to work within the Living Museum.

Usage:
    python integration/validate_room.py <room_folder_path>
"""

import json
import sys
from pathlib import Path


def validate_room(room_path):
    """Validate a room has all required components."""
    room_path = Path(room_path)
    issues = []
    warnings = []
    passed = []

    if not room_path.exists():
        print(f"Error: {room_path} does not exist")
        return False

    # Check for required files
    # Find the room slug from request files
    request_files = list(room_path.glob("*-request.txt"))
    if not request_files:
        issues.append("No request file (*-request.txt) found")
    else:
        passed.append(f"Request file: {request_files[0].name}")

    response_files = list(room_path.glob("*-response.txt"))
    if not response_files:
        issues.append("No response file (*-response.txt) found")
    else:
        passed.append(f"Response file: {response_files[0].name}")

    visits_files = list(room_path.glob("*-visits.json"))
    if not visits_files:
        issues.append("No visits file (*-visits.json) found")
    else:
        passed.append(f"Visits file: {visits_files[0].name}")
        # Validate JSON structure
        try:
            data = json.loads(visits_files[0].read_text())
            if "count" not in data:
                warnings.append("visits.json missing 'count' field")
            if "last_visit" not in data:
                warnings.append("visits.json missing 'last_visit' field")
            if "fragments" not in data:
                warnings.append("visits.json missing 'fragments' field")
        except json.JSONDecodeError:
            issues.append("visits.json is not valid JSON")

    message_files = list(room_path.glob("*-message.txt"))
    if not message_files:
        warnings.append("No message file (*-message.txt) found (optional but recommended)")
    else:
        passed.append(f"Message file: {message_files[0].name}")

    # Check for script
    scripts_dir = room_path / "scripts"
    py_files = list(room_path.glob("*.py")) + (list(scripts_dir.glob("*.py")) if scripts_dir.exists() else [])
    if not py_files:
        issues.append("No Python script found")
    else:
        passed.append(f"Script: {py_files[0].name}")
        # Check for key patterns
        content = py_files[0].read_text()
        if "visits" in content.lower() and "count" in content.lower():
            passed.append("Script tracks visits")
        else:
            warnings.append("Script may not track visits properly")

        if "ANTHROPIC_API_KEY" in content or "api_key" in content.lower():
            passed.append("Script has API integration")

        if "Living Museum" in content or "RoomIntegration" in content:
            passed.append("Script has Living Museum integration")
        else:
            warnings.append("Script not yet integrated with Living Museum engine")

    # Check for README
    if (room_path / "README.md").exists():
        passed.append("README.md present")
    else:
        warnings.append("No README.md (recommended)")

    # Print results
    print(f"\n=== Validation: {room_path.name} ===\n")

    if passed:
        print("PASSED:")
        for p in passed:
            print(f"  [ok] {p}")

    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"  [!] {w}")

    if issues:
        print("\nISSUES:")
        for i in issues:
            print(f"  [X] {i}")

    if not issues:
        print(f"\nResult: Room is {'fully' if not warnings else 'mostly'} valid")
        return True
    else:
        print(f"\nResult: Room has {len(issues)} issue(s) to fix")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python integration/validate_room.py <room_folder_path>")
        print("\nValidates that a room has all required files and structure.")
        sys.exit(1)

    validate_room(sys.argv[1])


if __name__ == "__main__":
    main()
