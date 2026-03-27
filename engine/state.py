#!/usr/bin/env python3
"""Cross-Room State Management

Manages shared state between rooms — fragments, emotional threads,
recurring themes. The rooms are not isolated. What you bring to one
echoes in others.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path


class StateManager:
    """Manages cross-room state for the Living Museum."""

    def __init__(self, museum_root="."):
        self.museum_root = Path(museum_root)
        self.state_file = self.museum_root / "museum-state.json"
        self.state = self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "museum_opened": None,
            "total_visits": 0,
            "last_visit": None,
            "last_room": None,
            "rooms_visited": [],
            "visit_sequence": [],
            "companion_fragments": [],
            "emotional_thread": [],
            "recurring_themes": [],
            "temporal_patterns": {
                "morning_rooms": [],
                "evening_rooms": [],
                "night_rooms": [],
                "frequent_returns": [],
                "long_absences": []
            }
        }

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def add_fragment(self, room_name, text, fragment_type="carrying"):
        """Store a fragment from a room visit."""
        fragment = {
            "room": room_name,
            "text": text[:300],
            "type": fragment_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.state.setdefault("companion_fragments", []).append(fragment)
        # Cap at 100
        if len(self.state["companion_fragments"]) > 100:
            self.state["companion_fragments"] = self.state["companion_fragments"][-100:]
        self.save()
        return fragment

    def add_emotional_note(self, emotion, room_name, context=""):
        """Track emotional states across rooms."""
        note = {
            "emotion": emotion,
            "room": room_name,
            "context": context[:200],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.state.setdefault("emotional_thread", []).append(note)
        if len(self.state["emotional_thread"]) > 50:
            self.state["emotional_thread"] = self.state["emotional_thread"][-50:]
        self.save()

    def get_fragments_for_room(self, room_name, limit=5):
        """Get fragments relevant to a particular room."""
        all_frags = self.state.get("companion_fragments", [])
        room_frags = [f for f in all_frags if f["room"] == room_name]
        return room_frags[-limit:]

    def get_recent_fragments(self, limit=5):
        """Get most recent fragments from any room."""
        return self.state.get("companion_fragments", [])[-limit:]

    def get_emotional_thread(self, limit=10):
        """Get the recent emotional thread."""
        return self.state.get("emotional_thread", [])[-limit:]

    def get_cross_room_context(self, current_room):
        """Build context from other rooms to enrich the current encounter."""
        fragments = self.get_recent_fragments(3)
        emotions = self.get_emotional_thread(3)

        context_parts = []
        for f in fragments:
            if f.get("room") != current_room:
                ftext = f.get("text", f.get("fragment", ""))
                if ftext:
                    context_parts.append(f"In {f.get('room', 'unknown')}, they carried: \"{ftext[:100]}\"")

        for e in emotions:
            if e["room"] != current_room:
                context_parts.append(f"In {e['room']}, they felt: {e['emotion']}")

        return "\n".join(context_parts) if context_parts else ""

    def compute_identity_hash(self):
        """Generate a unique hash from all fragments — a fingerprint of this Companion's journey."""
        all_text = ""
        for f in self.state.get("companion_fragments", []):
            all_text += f.get("text", f.get("fragment", ""))
        return hashlib.sha256(all_text.encode()).hexdigest()[:16] if all_text else "new"
