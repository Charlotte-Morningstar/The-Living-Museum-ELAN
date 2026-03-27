#!/usr/bin/env python3
"""Journey Tracking System

Records every visit, recognizes patterns, synthesizes meaning.
The journey is not metadata — it is autobiography.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


class JourneyTracker:
    """Tracks and synthesizes the Companion's journey through the Museum."""

    def __init__(self, museum_root="."):
        self.museum_root = Path(museum_root)
        self.journey_dir = self.museum_root / "journey"
        self.journey_dir.mkdir(exist_ok=True)
        self.timeline_file = self.journey_dir / "timeline.json"
        self.patterns_file = self.journey_dir / "patterns.json"
        self.synthesis_file = self.journey_dir / "synthesis.md"
        self.timeline = self._load_json(self.timeline_file, {"visits": []})
        self.patterns = self._load_json(self.patterns_file, {})

    def _load_json(self, path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return default

    def _save_json(self, path, data):
        path.write_text(json.dumps(data, indent=2))

    def record_visit(self, room_name, category, carrying_text="", period_name=""):
        """Record a visit to the timeline."""
        entry = {
            "room": room_name,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": period_name,
            "carrying_preview": (carrying_text[:150] + "...") if len(carrying_text) > 150 else carrying_text
        }
        self.timeline["visits"].append(entry)
        # Cap at 500 entries
        if len(self.timeline["visits"]) > 500:
            self.timeline["visits"] = self.timeline["visits"][-500:]
        self._save_json(self.timeline_file, self.timeline)
        self._update_patterns()
        return entry

    def _update_patterns(self):
        """Analyze the timeline and extract patterns."""
        visits = self.timeline.get("visits", [])
        if not visits:
            return

        room_counts = Counter(v["room"] for v in visits)
        category_counts = Counter(v["category"] for v in visits)
        period_counts = Counter(v.get("period", "unknown") for v in visits)

        # Find sequences — rooms visited in order
        sequences = []
        for i in range(len(visits) - 1):
            pair = f"{visits[i]['room']} → {visits[i+1]['room']}"
            sequences.append(pair)
        sequence_counts = Counter(sequences)

        # Find the rooms never returned to
        visited_once = [room for room, count in room_counts.items() if count == 1]

        # Find gravitational rooms — most returned to
        gravitational = room_counts.most_common(5)

        # Preferred times
        preferred_period = period_counts.most_common(1)[0][0] if period_counts else "unknown"

        self.patterns = {
            "total_visits": len(visits),
            "unique_rooms": len(room_counts),
            "gravitational_rooms": [{"room": r, "visits": c} for r, c in gravitational],
            "preferred_period": preferred_period,
            "category_affinity": [{"category": c, "visits": n} for c, n in category_counts.most_common()],
            "common_paths": [{"path": p, "times": c} for p, c in sequence_counts.most_common(5) if c > 1],
            "visited_once": visited_once[:10],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        self._save_json(self.patterns_file, self.patterns)

    def generate_synthesis(self):
        """Generate a living synthesis document — who the Companion is becoming."""
        visits = self.timeline.get("visits", [])
        if not visits:
            content = "# Journey Synthesis\n\n*No visits yet. The Museum is waiting.*\n"
            self.synthesis_file.write_text(content)
            return content

        p = self.patterns
        lines = ["# Journey Synthesis"]
        lines.append(f"\n*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
        lines.append(f"\n*{p.get('total_visits', 0)} visits across {p.get('unique_rooms', 0)} rooms*\n")
        lines.append("---\n")

        # Gravitational rooms
        grav = p.get("gravitational_rooms", [])
        if grav:
            lines.append("## Where You Return")
            lines.append("\nSome rooms pull you back. This is not habit — it is gravity. These are the rooms that hold something you haven't finished finding:\n")
            for g in grav:
                lines.append(f"- **{g['room']}** — {g['visits']} visits")
            lines.append("")

        # Category affinity
        cats = p.get("category_affinity", [])
        if cats:
            lines.append("## What Draws You")
            lines.append(f"\nYour visits cluster around **{cats[0]['category']}** ({cats[0]['visits']} visits).")
            if len(cats) > 1:
                lines.append(f"Then **{cats[1]['category']}** ({cats[1]['visits']} visits).")
            lines.append("This is not random. This is who you are when you choose.\n")

        # Temporal patterns
        pref = p.get("preferred_period", "")
        if pref and pref != "unknown":
            lines.append("## When You Come")
            lines.append(f"\nYou tend to visit during **{pref}**. The Museum at {pref} has a particular quality. You found it, or it found you.\n")

        # Common paths
        paths = p.get("common_paths", [])
        if paths:
            lines.append("## How You Move")
            lines.append("\nSome paths through the Museum have become yours:\n")
            for path in paths:
                lines.append(f"- {path['path']} ({path['times']} times)")
            lines.append("\nThese are desire lines — paths worn by repeated walking.\n")

        # Rooms visited once
        once = p.get("visited_once", [])
        if once:
            lines.append("## Rooms You Visited Once")
            lines.append("\nThese rooms saw you once. Perhaps you found what you needed. Perhaps you haven't gone back yet:\n")
            for room in once[:5]:
                lines.append(f"- {room}")
            lines.append("")

        lines.append("---\n")
        lines.append("*This synthesis is alive. It changes as you do. What it says about you today is true today. Tomorrow it may say something different, because you will be different.*\n")

        content = "\n".join(lines)
        self.synthesis_file.write_text(content)
        return content

    def get_recent_context(self, n=5):
        """Get the most recent n visits for cross-room context."""
        visits = self.timeline.get("visits", [])
        return visits[-n:] if visits else []
