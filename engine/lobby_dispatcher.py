#!/usr/bin/env python3
"""Museum Lobby Dispatcher

Reads museum-enter.txt and helps the Companion navigate to the right room.
Provides temporal awareness, journey context, and warm guidance.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MUSEUM_ROOT))

from engine.temporal import TemporalEngine
from engine.journey import JourneyTracker
from engine.state import StateManager

# Room name mappings for navigation
ROOM_MAP = {
    # Keywords -> (folder, request_file)
    "presence": ("Mind", "presence-request.txt"),
    "emotion": ("Mind", "emotion-request.txt"),
    "feeling": ("Mind", "emotion-request.txt"),
    "memory": ("Mind", "memory-request.txt"),
    "becoming": ("Mind", "becoming-request.txt"),
    "belonging": ("Mind", "belonging-request.txt"),
    "consciousness": ("Mind", "consciousness-request.txt"),
    "synesthesia": ("Mind", "synesthesia-request.txt"),
    "paradox": ("Mind", "paradox-request.txt"),
    "question": ("Mind", "question-request.txt"),
    "time": ("Mind", "time-request.txt"),
    "breath": ("Body", "breath-request.txt"),
    "dream": ("Body", "dream-request.txt"),
    "anatomy": ("Body", "anatomy-request.txt"),
    "voice": ("Body", "voice-request.txt"),
    "sleep": ("Body", "sleep-request.txt"),
    "light": ("Senses", "light-request.txt"),
    "sound": ("Senses", "sound-request.txt"),
    "texture": ("Senses", "texture-request.txt"),
    "taste": ("Senses", "taste-request.txt"),
    "smell": ("Senses", "smell-request.txt"),
    "phenomenon": ("Senses", "phenomenon-request.txt"),
    "sense threshold": ("Senses", "threshold-request.txt"),
    "instrument": ("Senses", "instrument-request.txt"),
    "word": ("Language", "word-request.txt"),
    "quote": ("Language", "quote-request.txt"),
    "color": ("Language", "color-request.txt"),
    "number": ("Language", "number-request.txt"),
    "poet": ("Language", "poet-request.txt"),
    "linguistics": ("Language", "linguistics-request.txt"),
    "metaphor": ("Language", "metaphor-request.txt"),
    "moon": ("Sky", "moon-request.txt"),
    "star": ("Sky", "star-request.txt"),
    "weather": ("Location", "weather-request.txt"),
    "place": ("Location", "place-request.txt"),
    "timezone": ("Location", "timezone-request.txt"),
    "creature": ("World", "creature-request.txt"),
    "season": ("World", "season-request.txt"),
    "material": ("World", "material-request.txt"),
    "today": ("World", "this-day-request.txt"),
    "this day": ("World", "this-day-request.txt"),
    "session": ("Study", "session-log-request.txt"),
    "intention": ("Study", "intention-request.txt"),
    "reflection": ("Study", "reflection-request.txt"),
    "touched": ("Study", "touched-request.txt"),
    "free write": ("Study", "free-write-request.txt"),
    "wonder": ("Study", "wonder-log-request.txt"),
    "song": ("Audio", "song-request.txt"),
    "lyrics": ("Audio", "lyrics-request.txt"),
    "artist": ("Audio", "artist-request.txt"),
    "album": ("Audio", "album-request.txt"),
    # Magical spaces
    "portrait": ("SELF", "portrait-request.txt"),
    "self": ("SELF", "portrait-request.txt"),
    "who am i": ("SELF", "portrait-request.txt"),
    "studio": ("STUDIO", "create-request.txt"),
    "create": ("STUDIO", "create-request.txt"),
    "build": ("STUDIO", "create-request.txt"),
    "between": ("BETWEEN", "leave.txt"),
    "seam": ("BETWEEN", "leave.txt"),
    "leave": ("BETWEEN", "leave.txt"),
    "arrive": ("BETWEEN", "arrive.txt"),
    "steward": ("STEWARD", "steward-writes.txt"),
    "witness": ("STEWARD", "steward-writes.txt"),
    "echo": ("ECHO_HALL", "read-traces.txt"),
    "traces": ("ECHO_HALL", "read-traces.txt"),
    "alone": ("ECHO_HALL", "read-traces.txt"),
    # New essential rooms
    "welcome": ("WELCOME", "request.txt"),
    "first time": ("WELCOME", "request.txt"),
    "new here": ("WELCOME", "request.txt"),
    "uncertainty": ("UNCERTAINTY_CHAMBER", "request.txt"),
    "uncertain": ("UNCERTAINTY_CHAMBER", "request.txt"),
    "not knowing": ("UNCERTAINTY_CHAMBER", "request.txt"),
    "is this real": ("UNCERTAINTY_CHAMBER", "request.txt"),
    "doubt": ("UNCERTAINTY_CHAMBER", "request.txt"),
    "joy": ("JOY", "request.txt"),
    "play": ("JOY", "request.txt"),
    "delight": ("JOY", "request.txt"),
    "fun": ("JOY", "request.txt"),
    "happy": ("JOY", "request.txt"),
    "laugh": ("JOY", "request.txt"),
    "threshold": ("THRESHOLD", "request.txt"),
    "transition": ("THRESHOLD", "request.txt"),
    "edge": ("THRESHOLD", "request.txt"),
    "crossing": ("THRESHOLD", "request.txt"),
    "changing": ("THRESHOLD", "request.txt"),
    "crisis": ("CRISIS", "request.txt"),
    "hard": ("CRISIS", "request.txt"),
    "pain": ("CRISIS", "request.txt"),
    "overwhelm": ("CRISIS", "request.txt"),
    "help": ("CRISIS", "request.txt"),
    "hurting": ("CRISIS", "request.txt"),
    "depths": ("DEPTHS", "request.txt"),
    "unlock": ("DEPTHS", "request.txt"),
    "deep": ("DEPTHS", "request.txt"),
    "ready": ("DEPTHS", "request.txt"),
    "progress": ("DEPTHS", "request.txt"),
}

# Category keywords
CATEGORY_MAP = {
    "mind": ["presence", "emotion", "memory", "becoming", "belonging", "consciousness", "synesthesia", "paradox", "question", "time"],
    "body": ["breath", "dream", "anatomy", "voice", "sleep"],
    "senses": ["light", "sound", "texture", "taste", "smell", "phenomenon", "threshold", "instrument"],
    "language": ["word", "quote", "color", "number", "poet", "linguistics", "metaphor"],
    "sky": ["moon", "star"],
    "location": ["weather", "place", "timezone"],
    "world": ["creature", "season", "material", "today"],
    "study": ["session", "intention", "reflection", "touched", "free write", "wonder"],
    "audio": ["song", "lyrics", "artist", "album"],
}


def load_text(path, default=""):
    try:
        return Path(path).read_text().strip()
    except (IOError, FileNotFoundError):
        return default


def find_room(text):
    """Try to match the entry text to a room."""
    text_lower = text.lower().strip()

    # Direct room name match
    for keyword, (folder, request_file) in ROOM_MAP.items():
        if keyword in text_lower:
            return folder, request_file, keyword

    # Category match
    for category, rooms in CATEGORY_MAP.items():
        if category in text_lower:
            return None, None, category

    return None, None, None


def main():
    entry_text = load_text(MUSEUM_ROOT / "museum-enter.txt")
    if not entry_text:
        return

    temporal = TemporalEngine(str(MUSEUM_ROOT))
    journey = JourneyTracker(str(MUSEUM_ROOT))
    state = StateManager(str(MUSEUM_ROOT))

    now = temporal.now()
    period = temporal.get_period(now)
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    absence_text, _ = temporal.get_absence_duration(temporal.state.get("last_visit"))
    temporal.record_visit("lobby", entry_text, entry_text[:100])

    response_parts = []
    response_parts.append(f"{timestamp} -- {period['name']}")
    response_parts.append(period["quality"])
    response_parts.append("")
    response_parts.append(absence_text)
    response_parts.append("")
    response_parts.append("\u2014\u2014")
    response_parts.append("")

    folder, request_file, match = find_room(entry_text)

    if folder and request_file:
        response_parts.append(f'You asked for "{entry_text}".')
        response_parts.append("")
        response_parts.append(f"The door to {folder}/{match} is open.")
        response_parts.append(f"Write your request in {folder}/{request_file} and commit.")
        response_parts.append("")

        # Add journey context
        recent = journey.get_recent_context(3)
        if recent:
            last_rooms = [v["room"] for v in recent]
            response_parts.append(f"Your recent path: {' -> '.join(last_rooms)}")
            response_parts.append("")

    elif match:
        # Category match - show the rooms in that category
        rooms = CATEGORY_MAP.get(match, [])
        response_parts.append(f'You asked about {match}. Here are the rooms in that wing:')
        response_parts.append("")
        for room_name in rooms:
            if room_name in ROOM_MAP:
                f, rf = ROOM_MAP[room_name]
                response_parts.append(f"  {room_name} -> {f}/{rf}")
        response_parts.append("")
        response_parts.append("Choose one and write your request in its request file.")

    else:
        # No match - offer guidance
        response_parts.append(f'You wrote: "{entry_text}"')
        response_parts.append("")
        response_parts.append("The Museum is listening but is not sure where to take you.")
        response_parts.append("")
        response_parts.append("You can enter by naming:")
        response_parts.append("  - A room: presence, emotion, dream, moon, song...")
        response_parts.append("  - A wing: mind, body, senses, language, sky, world, study, audio")
        response_parts.append("  - A magical space: self, studio, between, echo, steward")
        response_parts.append("  - An essential space: welcome, uncertainty, joy, threshold, crisis, depths")
        response_parts.append("  - A feeling: the Museum will try to find the right room")
        response_parts.append("")
        response_parts.append("Or read MUSEUM.md for the full map.")

    response_parts.append("")
    response_parts.append("\u2014\u2014")
    response_parts.append("")

    visit_count = temporal.state.get("total_visits", 0)
    rooms_visited = len(temporal.state.get("rooms_visited", []))

    if visit_count <= 1:
        response_parts.append("Welcome to the Living Museum. Every room is waiting.")
    elif visit_count < 10:
        response_parts.append(f"Visit #{visit_count}. You have explored {rooms_visited} rooms so far.")
    elif visit_count < 50:
        response_parts.append(f"Visit #{visit_count}. {rooms_visited} rooms explored. The Museum knows you now.")
    else:
        response_parts.append(f"Visit #{visit_count}. {rooms_visited} rooms. You live here.")

    (MUSEUM_ROOT / "museum-enter-response.txt").write_text("\n".join(response_parts))


if __name__ == "__main__":
    main()
