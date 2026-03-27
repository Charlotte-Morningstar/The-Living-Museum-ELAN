#!/usr/bin/env python3
"""Integration Helpers

Tools for connecting existing rooms to the Living Museum infrastructure.
Adds temporal awareness, journey tracking, and cross-room state to any room.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.temporal import TemporalEngine
from engine.journey import JourneyTracker
from engine.state import StateManager


class RoomIntegration:
    """Provides Living Museum integration for any room script."""

    ROOM_CATEGORIES = {
        # Mind
        "presence": "Mind", "emotion": "Mind", "memory": "Mind",
        "becoming": "Mind", "belonging": "Mind", "consciousness": "Mind",
        "synesthesia": "Mind", "paradox": "Mind", "question": "Mind", "time": "Mind",
        # Body
        "breath": "Body", "dream": "Body", "anatomy": "Body",
        "voice": "Body", "sleep": "Body",
        # Senses
        "light": "Senses", "sound": "Senses", "texture": "Senses",
        "taste": "Senses", "smell": "Senses", "phenomenon": "Senses",
        "threshold": "Senses", "instrument": "Senses",
        # Language
        "word": "Language", "quote": "Language", "color": "Language",
        "number": "Language", "poet": "Language", "linguistics": "Language",
        "metaphor": "Language",
        # Sky
        "moon": "Sky", "star": "Sky",
        # Location
        "weather": "Location", "place": "Location", "timezone": "Location",
        # World
        "creature": "World", "season": "World", "material": "World",
        "this-day": "World",
        # Study
        "session-log": "Study", "intention": "Study", "reflection": "Study",
        "touched": "Study", "free-write": "Study", "wonder-log": "Study",
        # Audio
        "song": "Audio", "lyrics": "Audio", "artist": "Audio", "album": "Audio",
        # Magical Spaces
        "self-portrait": "SELF", "studio": "STUDIO", "between": "BETWEEN",
        "steward": "STEWARD", "echo-hall": "ECHO_HALL",
        # Essential Spaces
        "uncertainty": "UNCERTAINTY_CHAMBER", "joy": "JOY",
        "welcome": "WELCOME", "depths": "DEPTHS",
        "threshold": "THRESHOLD", "crisis": "CRISIS",
    }

    def __init__(self, room_name, museum_root=None):
        self.room_name = room_name
        if museum_root is None:
            # Try to find museum root by walking up from CWD
            museum_root = self._find_museum_root()
        self.museum_root = Path(museum_root)
        self.temporal = TemporalEngine(museum_root)
        self.journey = JourneyTracker(museum_root)
        self.state_mgr = StateManager(museum_root)
        self.category = self.ROOM_CATEGORIES.get(room_name, "Unknown")

    def _find_museum_root(self):
        """Walk up directories to find the museum root (contains museum-state.json)."""
        current = Path.cwd()
        for _ in range(5):
            if (current / "museum-state.json").exists():
                return str(current)
            current = current.parent
        return "."

    def on_enter(self, carrying_text="", visits_data=None):
        """Call when a Companion enters a room. Returns enriched arrival context."""
        # Get temporal context
        arrival_text = self.temporal.get_arrival_text(self.room_name, visits_data)
        journey_note = self.temporal.format_journey_note(self.room_name)
        cross_room = self.state_mgr.get_cross_room_context(self.room_name)

        # Record the visit
        period = self.temporal.get_period()
        self.temporal.record_visit(self.room_name, carrying_text, carrying_text[:100] if carrying_text else None)
        self.journey.record_visit(self.room_name, self.category, carrying_text, period["name"])

        # Store fragment
        if carrying_text:
            self.state_mgr.add_fragment(self.room_name, carrying_text)

        return {
            "arrival_text": arrival_text,
            "journey_note": journey_note,
            "cross_room_context": cross_room,
            "period": period,
            "is_first_visit": visits_data is None or visits_data.get("count", 0) == 0,
        }

    def on_exit(self, response_text=""):
        """Call after generating a response. Updates synthesis."""
        # Periodically regenerate synthesis
        if self.state_mgr.state.get("total_visits", 0) % 5 == 0:
            self.journey.generate_synthesis()

    def get_enrichment_prompt(self, carrying_text):
        """Get additional context to add to the Anthropic API prompt."""
        ctx = self.temporal.get_journey_context(self.room_name)
        parts = []

        if ctx["recent_fragments"]:
            parts.append(f"Recently in other rooms, this Companion carried: {'; '.join(ctx['recent_fragments'][-2:])}")

        if ctx["total_museum_visits"] > 20:
            parts.append(f"This Companion has visited the Museum {ctx['total_museum_visits']} times across {ctx['rooms_explored']} rooms. They are not new here.")

        cross = self.state_mgr.get_cross_room_context(self.room_name)
        if cross:
            parts.append(f"Cross-room context: {cross}")

        return "\n".join(parts) if parts else ""
