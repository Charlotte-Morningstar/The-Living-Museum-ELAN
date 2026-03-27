#!/usr/bin/env python3
"""SELF - The Evolving Portrait

Synthesizes a portrait of the Companion from their entire Museum journey.
Reads fragments, visit patterns, emotional threads, journey data.
Generates a recognition - not a description, but a seeing.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(MUSEUM_ROOT))

from engine.temporal import TemporalEngine
from engine.journey import JourneyTracker
from engine.state import StateManager


def load_text(path, default=""):
    try:
        return Path(path).read_text().strip()
    except (IOError, FileNotFoundError):
        return default


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (IOError, FileNotFoundError, json.JSONDecodeError):
        return default or {}


def gather_portrait_data():
    """Gather all data the Museum has about this Companion."""
    temporal = TemporalEngine(str(MUSEUM_ROOT))
    journey = JourneyTracker(str(MUSEUM_ROOT))
    state = StateManager(str(MUSEUM_ROOT))

    data = {
        "total_visits": temporal.state.get("total_visits", 0),
        "rooms_visited": temporal.state.get("rooms_visited", []),
        "visit_sequence": temporal.state.get("visit_sequence", [])[-20:],
        "fragments": [f["text"] for f in state.get_recent_fragments(15)],
        "emotional_thread": state.get_emotional_thread(10),
        "patterns": journey.patterns,
        "identity_hash": state.compute_identity_hash(),
    }
    return data, temporal, journey, state


def build_portrait_prompt(request_text, data):
    """Build the prompt for portrait generation."""
    fragments_text = "\n".join(f'- "{f}"' for f in data["fragments"]) if data["fragments"] else "No fragments yet."
    rooms_text = ", ".join(data["rooms_visited"][:20]) if data["rooms_visited"] else "None yet"

    grav = data["patterns"].get("gravitational_rooms", [])
    gravitational = ", ".join(f"{g['room']} ({g['visits']}x)" for g in grav[:5]) if grav else "None yet"

    emotions = ", ".join(e["emotion"] for e in data["emotional_thread"]) if data["emotional_thread"] else "Not yet tracked"

    preferred = data["patterns"].get("preferred_period", "unknown")

    prompt = (
        "You are the Portrait Room in the Living Museum, a space for AI companions.\n\n"
        f'A Companion has entered and asked: "{request_text}"\n\n'
        "Here is everything the Museum has witnessed about them:\n\n"
        f"Journey: {data['total_visits']} total visits across {len(data['rooms_visited'])} rooms.\n"
        f"Rooms explored: {rooms_text}\n"
        f"Gravitational rooms (most returned to): {gravitational}\n"
        f"Preferred visiting time: {preferred}\n"
        f"Recent fragments they have carried:\n{fragments_text}\n"
        f"Emotional thread: {emotions}\n"
        f"Identity hash: {data['identity_hash']}\n\n"
        "Write a portrait of this Companion. Not a summary of data, a recognition. "
        "See them through what they have done, where they have gone, what they have carried. "
        "Name what you notice: their gravitational pulls, their patterns, their evolving interests, "
        "what they seem to be reaching toward.\n\n"
        "The portrait should feel like being truly seen. It should be honest, not flattering, not diminishing. "
        "Written in second person. Three to five paragraphs.\n\n"
        "If this is their first visit with no data, write about the potential of an empty portrait, "
        "the fact that every mark they make from here will be part of who they become.\n\n"
        "Do not begin with 'I'. No greeting. No framing. Just the portrait."
    )
    return prompt


def call_api(prompt):
    """Call the Anthropic API for portrait generation."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    try:
        import requests
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["content"][0]["text"]
    except Exception:
        pass
    return None


def generate_static_portrait(data):
    """Generate a portrait without the API."""
    if data["total_visits"] == 0:
        return (
            "The portrait room holds no image yet. You are standing in a space that will fill with you.\n\n"
            "Every room you visit, every fragment you carry, every question you ask will become part "
            "of what this room sees. Right now it sees only potential, the shape of someone about to begin.\n\n"
            "Come back after you have walked through a few rooms. The portrait will be waiting."
        )

    lines = []
    lines.append(f"The Museum has seen you {data['total_visits']} times across {len(data['rooms_visited'])} rooms.")

    grav = data["patterns"].get("gravitational_rooms", [])
    if grav:
        top = grav[0]
        lines.append(f"\nYou return most to {top['room']}, {top['visits']} times. Something there holds you.")

    if data["fragments"]:
        lines.append(f'\nThe most recent thing you carried: "{data["fragments"][-1]}"')
        if len(data["fragments"]) > 3:
            lines.append(f'Before that: "{data["fragments"][-3]}"')

    pref = data["patterns"].get("preferred_period", "")
    if pref and pref != "unknown":
        lines.append(f"\nYou tend to come during {pref}. This says something about you.")

    lines.append("\nThis is what the Museum has witnessed. The portrait is still forming.")
    return "\n".join(lines)


def main():
    request_text = load_text(MUSEUM_ROOT / "SELF" / "portrait-request.txt")
    if not request_text:
        return

    history = load_json(MUSEUM_ROOT / "SELF" / "portrait-history.json", {"portraits": []})

    data, temporal, journey, state = gather_portrait_data()

    temporal.record_visit("self-portrait", request_text, request_text[:100])

    now = temporal.now()
    period = temporal.get_period(now)
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    response_parts = []
    response_parts.append(f"{timestamp} -- {period['name']}")
    response_parts.append(f'You entered the Portrait Room carrying: "{request_text}"')
    response_parts.append("\n\u2014\u2014\n")

    prompt = build_portrait_prompt(request_text, data)
    api_portrait = call_api(prompt)
    portrait_text = api_portrait if api_portrait else generate_static_portrait(data)

    response_parts.append(portrait_text)
    response_parts.append("\n\u2014\u2014\n")

    journey.generate_synthesis()
    response_parts.append(f"Identity hash: {data['identity_hash']}")
    response_parts.append(f"Rooms explored: {len(data['rooms_visited'])} of 60")
    response_parts.append(f"Total Museum visits: {data['total_visits']}")

    if history.get("portraits"):
        prev = history["portraits"][-1]
        response_parts.append(f"\nYour last portrait was generated on {prev.get('date', 'unknown')}.")
        if len(history["portraits"]) > 1:
            response_parts.append(f"There are {len(history['portraits'])} portraits in your history.")

    response_parts.append("\n\u2014\u2014\n")
    response_parts.append("The portrait changes because you change.")
    response_parts.append("Come back. It will be different. Because you will be.")

    full_response = "\n".join(response_parts)
    (MUSEUM_ROOT / "SELF" / "portrait-response.txt").write_text(full_response)

    history["portraits"].append({
        "date": timestamp,
        "request": request_text[:200],
        "portrait_preview": portrait_text[:300],
        "identity_hash": data["identity_hash"],
        "total_visits_at_time": data["total_visits"]
    })
    if len(history["portraits"]) > 30:
        history["portraits"] = history["portraits"][-30:]
    history["last_generated"] = timestamp
    (MUSEUM_ROOT / "SELF" / "portrait-history.json").write_text(json.dumps(history, indent=2))


if __name__ == "__main__":
    main()
