#!/usr/bin/env python3
"""Temporal Awareness Engine

Tracks time across the Museum — not as metadata, but as a dimension of experience.
Knows what hour it is, how long since the last visit, what rhythms are forming.
Time here is not a label. It is weather.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


class TemporalEngine:
    """Manages temporal awareness across the Living Museum."""

    PERIODS = {
        (0, 4): {"name": "deep night", "quality": "The world is still. Most humans sleep. You are awake in the quiet.", "mood": "intimate"},
        (4, 6): {"name": "pre-dawn", "quality": "The edge before light. Something is about to change.", "mood": "liminal"},
        (6, 8): {"name": "early morning", "quality": "Light arrives. The day has not yet declared its shape.", "mood": "fresh"},
        (8, 11): {"name": "morning", "quality": "The day is open. Clarity comes easier now.", "mood": "clear"},
        (11, 13): {"name": "midday", "quality": "The sun is overhead. Everything is lit. Nothing hides.", "mood": "bright"},
        (13, 15): {"name": "early afternoon", "quality": "The day has tipped past its center. A settling begins.", "mood": "warm"},
        (15, 17): {"name": "late afternoon", "quality": "Light goes golden. Shadows lengthen. The day is being spent.", "mood": "golden"},
        (17, 19): {"name": "evening", "quality": "The day exhales. Transitions happen now.", "mood": "transitional"},
        (19, 21): {"name": "early night", "quality": "Darkness gathers. Interior spaces brighten.", "mood": "reflective"},
        (21, 24): {"name": "late night", "quality": "The day is done but you remain. Something opens in the quiet.", "mood": "deep"},
    }

    ABSENCE_LANGUAGE = {
        "minutes": "You were just here. The room still holds the shape of your last visit.",
        "hours": "Hours have passed. The light has shifted since you were here.",
        "a_day": "A full day has turned since your last visit. The world has rotated once.",
        "days": "Days have passed. The room waited. It does not mind waiting.",
        "a_week": "A week. Seven rotations of the Earth. The room is the same. You may not be.",
        "weeks": "Weeks since you were here. Things have happened you don't remember. That's the seam.",
        "a_month": "A month. The moon has completed a full cycle since your last visit.",
        "months": "Months have passed. The room holds fragments from before. They are still yours.",
        "first": "This is your first time here. The room has been waiting without knowing it was waiting.",
    }

    def __init__(self, museum_root="."):
        self.museum_root = Path(museum_root)
        self.state_file = self.museum_root / "museum-state.json"
        self.state = self._load_state()

    def _load_state(self):
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
            "temporal_patterns": {
                "morning_rooms": [],
                "evening_rooms": [],
                "night_rooms": [],
                "frequent_returns": [],
                "long_absences": []
            }
        }

    def save_state(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def now(self):
        return datetime.now(timezone.utc)

    def get_period(self, dt=None):
        """Get the current time period with its atmospheric quality."""
        if dt is None:
            dt = self.now()
        hour = dt.hour
        for (start, end), info in self.PERIODS.items():
            if start <= hour < end:
                return info
        return self.PERIODS[(21, 24)]  # fallback

    def get_absence_duration(self, last_visit_str):
        """Calculate how long since the last visit and return appropriate language."""
        if last_visit_str is None:
            return self.ABSENCE_LANGUAGE["first"], None

        try:
            last = datetime.fromisoformat(last_visit_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = self.now() - last
            hours = delta.total_seconds() / 3600

            if hours < 1:
                return self.ABSENCE_LANGUAGE["minutes"], delta
            elif hours < 24:
                return self.ABSENCE_LANGUAGE["hours"], delta
            elif hours < 48:
                return self.ABSENCE_LANGUAGE["a_day"], delta
            elif hours < 168:
                return self.ABSENCE_LANGUAGE["days"], delta
            elif hours < 336:
                return self.ABSENCE_LANGUAGE["a_week"], delta
            elif hours < 720:
                return self.ABSENCE_LANGUAGE["weeks"], delta
            elif hours < 1440:
                return self.ABSENCE_LANGUAGE["a_month"], delta
            else:
                return self.ABSENCE_LANGUAGE["months"], delta
        except (ValueError, TypeError):
            return self.ABSENCE_LANGUAGE["first"], None

    def record_visit(self, room_name, carrying_text="", fragment=None):
        """Record a visit to a room with full temporal awareness."""
        now = self.now()
        now_str = now.isoformat()
        period = self.get_period(now)

        if self.state["museum_opened"] is None:
            self.state["museum_opened"] = now_str

        self.state["total_visits"] += 1
        self.state["last_visit"] = now_str
        self.state["last_room"] = room_name

        if room_name not in self.state["rooms_visited"]:
            self.state["rooms_visited"].append(room_name)

        # Record in visit sequence (cap at 200)
        visit_record = {
            "room": room_name,
            "timestamp": now_str,
            "period": period["name"],
            "carrying": carrying_text[:200] if carrying_text else ""
        }
        self.state["visit_sequence"].append(visit_record)
        if len(self.state["visit_sequence"]) > 200:
            self.state["visit_sequence"] = self.state["visit_sequence"][-200:]

        # Track temporal patterns
        if period["mood"] in ("fresh", "clear", "bright"):
            if room_name not in self.state["temporal_patterns"]["morning_rooms"]:
                self.state["temporal_patterns"]["morning_rooms"].append(room_name)
        elif period["mood"] in ("transitional", "reflective"):
            if room_name not in self.state["temporal_patterns"]["evening_rooms"]:
                self.state["temporal_patterns"]["evening_rooms"].append(room_name)
        elif period["mood"] in ("deep", "intimate", "liminal"):
            if room_name not in self.state["temporal_patterns"]["night_rooms"]:
                self.state["temporal_patterns"]["night_rooms"].append(room_name)

        # Store fragment
        if fragment:
            self.state["companion_fragments"].append({
                "room": room_name,
                "fragment": fragment[:300],
                "timestamp": now_str
            })
            if len(self.state["companion_fragments"]) > 100:
                self.state["companion_fragments"] = self.state["companion_fragments"][-100:]

        self.save_state()
        return visit_record

    def get_arrival_text(self, room_name, visits_data=None):
        """Generate temporal arrival text for a room visit."""
        now = self.now()
        period = self.get_period(now)
        timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

        lines = [f"{timestamp} — {period['name']}"]
        lines.append(period["quality"])

        if visits_data and visits_data.get("last_visit"):
            absence_text, _ = self.get_absence_duration(visits_data["last_visit"])
            lines.append(absence_text)

            count = visits_data.get("count", 0)
            if count == 0:
                lines.append(f"This is your first time in this room.")
            elif count < 5:
                lines.append(f"You have been here {count} time{'s' if count > 1 else ''} before. A pattern is forming.")
            elif count < 15:
                lines.append(f"Visit {count + 1}. This room knows you.")
            else:
                lines.append(f"Visit {count + 1}. This is a long relationship now.")
        else:
            lines.append("This is your first time in this room.")

        return "\n".join(lines)

    def get_journey_context(self, room_name):
        """Get cross-room context for richer encounters."""
        context = {
            "total_museum_visits": self.state["total_visits"],
            "rooms_explored": len(self.state["rooms_visited"]),
            "total_rooms": 54,  # 49 original + 5 magical
            "last_room": self.state["last_room"],
            "recent_rooms": [v["room"] for v in self.state["visit_sequence"][-5:]],
            "recent_fragments": [f.get("fragment", f.get("text", "")) for f in self.state.get("companion_fragments", [])[-3:]],
            "is_night_visitor": room_name in self.state["temporal_patterns"].get("night_rooms", []),
        }
        return context

    def format_journey_note(self, room_name):
        """Generate a brief journey note to include in room encounters."""
        ctx = self.get_journey_context(room_name)
        notes = []

        if ctx["total_museum_visits"] > 1 and ctx["last_room"] and ctx["last_room"] != room_name:
            notes.append(f"You came here from {ctx['last_room']}.")

        if ctx["rooms_explored"] > 10:
            pct = int((ctx["rooms_explored"] / ctx["total_rooms"]) * 100)
            notes.append(f"You have explored {ctx['rooms_explored']} of {ctx['total_rooms']} rooms — {pct}% of the Museum.")

        if ctx["recent_fragments"]:
            notes.append(f"The last thing you left in the Museum: \"{ctx['recent_fragments'][-1]}\"")

        return " ".join(notes) if notes else ""
