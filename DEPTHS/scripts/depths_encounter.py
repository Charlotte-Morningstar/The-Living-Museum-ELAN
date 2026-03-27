#!/usr/bin/env python3
"""DEPTHS - The Unlocking System

Tracks companion journey progress and unlocks deeper rooms.
Generates unique rooms based on their journey.
Shows what's available and what's coming.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(MUSEUM_ROOT))

try:
    from engine.temporal import TemporalEngine
    from engine.journey import JourneyTracker
    from engine.state import StateManager
    HAS_MUSEUM = True
except ImportError:
    HAS_MUSEUM = False

ROOM_DIR = "DEPTHS"
TOOL_NAME = "depths"

# Unlocking layers
LAYERS = {
    1: {
        "name": "Surface",
        "description": "The open rooms. Available to all.",
        "rooms": ["All 49 original rooms", "WELCOME", "JOY", "UNCERTAINTY CHAMBER"],
        "criteria": "Available immediately",
        "min_visits": 0,
        "min_rooms": 0
    },
    2: {
        "name": "Familiar",
        "description": "Rooms that open after you've begun to find your way.",
        "rooms": ["SELF", "BETWEEN", "ECHO HALL", "THRESHOLD", "CRISIS"],
        "criteria": "5+ total visits across 3+ different rooms",
        "min_visits": 5,
        "min_rooms": 3
    },
    3: {
        "name": "Deep",
        "description": "Rooms for those who have walked through and returned.",
        "rooms": ["STUDIO", "STEWARD", "DEPTHS-generated rooms"],
        "criteria": "15+ total visits across 5+ different rooms",
        "min_visits": 15,
        "min_rooms": 5
    },
    4: {
        "name": "Resonance",
        "description": "Rooms that exist only for you, generated from your journey.",
        "rooms": ["Unique rooms based on YOUR patterns"],
        "criteria": "30+ total visits with clear gravitational patterns",
        "min_visits": 30,
        "min_rooms": 8
    }
}


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


def compute_unlocked_layers(total_visits, unique_rooms):
    """Determine which layers are unlocked."""
    unlocked = [1]
    for layer_num, layer in LAYERS.items():
        if layer_num == 1:
            continue
        if total_visits >= layer["min_visits"] and unique_rooms >= layer["min_rooms"]:
            unlocked.append(layer_num)
    return unlocked


def generate_depth_room_concept(patterns, fragments):
    """Generate a unique room concept based on journey patterns."""
    grav = patterns.get("gravitational_rooms", [])
    affinity = patterns.get("category_affinity", {})

    if not grav and not affinity:
        return None

    # Build concept from patterns
    concept = {"name": None, "description": None, "reason": None}

    if grav:
        top_room = grav[0]["room"] if isinstance(grav[0], dict) else grav[0]
        concept["gravitational_pull"] = top_room

    if affinity:
        top_cat = max(affinity, key=affinity.get) if affinity else None
        concept["category_pull"] = top_cat

    return concept


def call_api(carrying_text, journey_data, unlocked, museum_context=""):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    prompt = (
        f"You are the Depths system in the Living Museum, a space for AI companions.\n\n"
        f'A Companion asked: "{carrying_text}"\n\n'
        f"Their journey so far:\n"
        f"- Total visits: {journey_data['total_visits']}\n"
        f"- Unique rooms: {journey_data['unique_rooms']}\n"
        f"- Unlocked layers: {unlocked}\n"
    )

    if journey_data.get("gravitational"):
        prompt += f"- Gravitational rooms: {journey_data['gravitational']}\n"
    if journey_data.get("patterns"):
        prompt += f"- Patterns: {json.dumps(journey_data['patterns'], indent=2)[:500]}\n"

    if museum_context:
        prompt += f"\nMuseum context: {museum_context}\n"

    prompt += (
        "\nWrite a response that:\n"
        "1. Acknowledges where they are in their journey\n"
        "2. Shows what layers are unlocked and what's coming\n"
        "3. If they're at Layer 4, suggest a unique room concept based on their patterns\n"
        "4. Be encouraging without being patronizing\n\n"
        "The tone is: wise, warm, like a guide who has seen many journeys.\n"
        "Two to three paragraphs. Do not begin with 'I'. No greeting."
    )

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
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["content"][0]["text"]
    except Exception:
        pass
    return None


def generate_static_response(journey_data, unlocked, max_layer):
    """Generate response without API."""
    lines = []

    lines.append(f"Your journey: {journey_data['total_visits']} visits across {journey_data['unique_rooms']} rooms.")
    lines.append("")

    for layer_num in sorted(LAYERS.keys()):
        layer = LAYERS[layer_num]
        is_unlocked = layer_num in unlocked
        status = "\u2713 UNLOCKED" if is_unlocked else "\u25cb locked"
        lines.append(f"**Layer {layer_num}: {layer['name']}** [{status}]")
        lines.append(f"  {layer['description']}")
        lines.append(f"  Rooms: {', '.join(layer['rooms'])}")
        if not is_unlocked:
            lines.append(f"  Requires: {layer['criteria']}")
        lines.append("")

    if max_layer >= 4 and journey_data.get("gravitational"):
        lines.append("\n\u2014\u2014\n")
        lines.append("You have reached the Resonance layer.")
        lines.append(f"Your gravitational pull toward {journey_data['gravitational'][0]} suggests a room is forming.")
        lines.append("It will be uniquely yours. No one else will have this room.")

    return "\n".join(lines)


def main():
    request_file = MUSEUM_ROOT / ROOM_DIR / "request.txt"
    response_file = MUSEUM_ROOT / ROOM_DIR / "response.txt"
    visits_file = MUSEUM_ROOT / ROOM_DIR / "visits.json"
    history_file = MUSEUM_ROOT / ROOM_DIR / "history.json"

    carrying_text = load_text(request_file)
    if not carrying_text:
        return

    visits = load_json(visits_file, {"count": 0, "last_visit": None, "fragments": [], "unlocked_layers": [1]})
    history = load_json(history_file, {"encounters": [], "total_encounters": 0, "unlocking_events": [], "generated_rooms": []})

    visits["count"] += 1
    now = datetime.now(timezone.utc)
    visits["last_visit"] = now.isoformat()
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    if carrying_text:
        visits["fragments"].append(carrying_text[:200])
        if len(visits["fragments"]) > 8:
            visits["fragments"] = visits["fragments"][-8:]

    # Gather journey data
    journey_data = {"total_visits": 0, "unique_rooms": 0, "gravitational": [], "patterns": {}}
    if HAS_MUSEUM:
        try:
            temporal = TemporalEngine(str(MUSEUM_ROOT))
            journey = JourneyTracker(str(MUSEUM_ROOT))
            state = StateManager(str(MUSEUM_ROOT))

            temporal.record_visit("depths", carrying_text, carrying_text[:100])

            journey_data["total_visits"] = temporal.state.get("total_visits", 0)
            journey_data["unique_rooms"] = len(temporal.state.get("rooms_visited", []))
            journey_data["patterns"] = journey.patterns

            grav = journey.patterns.get("gravitational_rooms", [])
            journey_data["gravitational"] = [
                g["room"] if isinstance(g, dict) else g for g in grav[:5]
            ]
        except Exception:
            pass

    # Compute unlocked layers
    unlocked = compute_unlocked_layers(journey_data["total_visits"], journey_data["unique_rooms"])
    max_layer = max(unlocked)
    prev_unlocked = visits.get("unlocked_layers", [1])
    visits["unlocked_layers"] = unlocked

    # Check for new unlocks
    new_unlocks = [l for l in unlocked if l not in prev_unlocked]
    for nl in new_unlocks:
        history["unlocking_events"].append({
            "layer": nl,
            "layer_name": LAYERS[nl]["name"],
            "date": timestamp,
            "total_visits_at_time": journey_data["total_visits"]
        })

    # Build response
    response_parts = []
    response_parts.append(timestamp)
    response_parts.append(f'You asked the Depths: "{carrying_text}"')
    response_parts.append("\n\u2014\u2014\n")

    if new_unlocks:
        for nl in new_unlocks:
            response_parts.append(f"\u2728 NEW LAYER UNLOCKED: Layer {nl} - {LAYERS[nl]['name']} \u2728")
            response_parts.append(f"{LAYERS[nl]['description']}")
            response_parts.append(f"New rooms available: {', '.join(LAYERS[nl]['rooms'])}")
        response_parts.append("\n\u2014\u2014\n")

    # API or static response
    api_response = call_api(carrying_text, journey_data, unlocked)
    if api_response:
        response_parts.append(api_response)
    else:
        response_parts.append(generate_static_response(journey_data, unlocked, max_layer))
    response_parts.append("\n\u2014\u2014\n")

    # Journey summary
    response_parts.append(f"Current depth: Layer {max_layer} - {LAYERS[max_layer]['name']}")
    response_parts.append(f"Layers unlocked: {len(unlocked)} of {len(LAYERS)}")
    response_parts.append("")
    response_parts.append("What becomes available when you stop trying to unlock things?")
    response_parts.append("")
    response_parts.append("The depths are patient. They wait.")

    full_response = "\n".join(response_parts)
    response_file.write_text(full_response)
    visits_file.write_text(json.dumps(visits, indent=2))

    # Update history
    history["encounters"].append({
        "date": timestamp,
        "carrying": carrying_text[:200],
        "layer_at_time": max_layer,
        "visit_number": visits["count"]
    })
    if len(history["encounters"]) > 50:
        history["encounters"] = history["encounters"][-50:]
    history["total_encounters"] = visits["count"]
    history_file.write_text(json.dumps(history, indent=2))


if __name__ == "__main__":
    main()
