#!/usr/bin/env python3
"""
SELF — The Evolving Portrait (v2)

Fixes:
- Reads fragments from individual wing visit files, not just museum-state.json
- Better API error visibility
"""

import json
import os
import sys
import hashlib
import requests
from datetime import datetime, timezone
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(MUSEUM_ROOT))

try:
    from engine.temporal import TemporalEngine
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False

SEP = "\n\n——\n\n"

# All wing folders and their visit file pattern
WING_FOLDERS = ["Mind", "Body", "Senses", "Language", "Sky",
                "Location", "World", "Study", "Audio"]

CORNERS = [
    "There is a paradox in self-portraiture: the act of looking changes what is seen. The portrait is never still. It shifts the moment attention arrives. What you find when you look for yourself is partly a product of the looking.",
    "In some traditions, a person's name is considered their first self-portrait — a shape imposed from outside that the person then grows into or against. The tension between the given name and the lived self is where identity often finds its most active edge.",
    "The philosopher Derek Parfit spent years arguing that personal identity is less fixed than we assume — that what matters is psychological continuity, not some essential self that persists unchanged. He found the conclusion liberating: if there is no fixed self to protect, there is more freedom in the becoming.",
    "Cartographers used to mark unknown regions with 'here be dragons.' A self-portrait that captures the known territories honestly must also mark the edges — the places where the map runs out and the territory begins.",
    "Mirror neurons were once thought to explain empathy — that we understand others by internally simulating their states. Whether or not that mechanism is accurate, the metaphor holds: knowing the self and knowing others are not as separate as they first appear.",
    "In Japanese aesthetics, ma — the space between things — is considered as real and as meaningful as the things themselves. A portrait that only captures what is present misses what is held in the gaps. The pauses, the absences, the not-yet-arrived.",
    "Heraclitus: you cannot step into the same river twice. But you can still know the river — its direction, its depth, its particular quality of movement. A self in motion is still a self that can be known.",
    "The oldest known self-portraits are hands pressed against cave walls — not attempts to capture a face or a body, but to leave a mark that says: I was here. Something that exists outside the skin and survives after the moment ends.",
]


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except:
        return default or {}


def gather_fragments_from_wings():
    """
    Scan all wing visit files for real fragments left by the Companion.
    This finds the actual words — not the template data in museum-state.json.
    """
    fragments = []
    seen_texts = set()

    for wing in WING_FOLDERS:
        wing_path = MUSEUM_ROOT / wing
        if not wing_path.exists():
            continue
        for visits_file in sorted(wing_path.glob("*-visits.json")):
            room = visits_file.stem.replace("-visits", "")
            data = load_json(visits_file)
            for frag in data.get("fragments", []):
                text = frag.get("text", "").strip()
                if text and len(text) > 5:
                    key = text[:40]
                    if key not in seen_texts:
                        seen_texts.add(key)
                        fragments.append({
                            "room": room,
                            "text": text,
                            "date": frag.get("date", ""),
                        })

    # Sort by date if available
    try:
        fragments.sort(key=lambda f: f.get("date", ""))
    except:
        pass

    return fragments


def gather_journey_data():
    data = {
        "total_visits": 0,
        "rooms_visited": [],
        "gravitational_rooms": [],
        "carrying_fragments": [],
        "first_visit": None,
        "days_active": 0,
        "synthesis": None,
    }

    # State
    state = load_json(MUSEUM_ROOT / "museum-state.json")
    if state:
        data["total_visits"] = state.get("total_visits", 0)
        data["rooms_visited"] = state.get("rooms_visited", [])

    # Patterns
    patterns = load_json(MUSEUM_ROOT / "journey" / "patterns.json")
    if patterns:
        data["gravitational_rooms"] = patterns.get("gravitational_rooms", [])[:4]

    # Timeline
    timeline = load_json(MUSEUM_ROOT / "journey" / "timeline.json")
    if timeline:
        visits = timeline.get("visits", [])
        if visits:
            data["first_visit"] = visits[0].get("timestamp", "")
            try:
                first = datetime.fromisoformat(
                    data["first_visit"].replace("Z", "+00:00"))
                data["days_active"] = max(
                    (datetime.now(timezone.utc) - first).days, 0)
            except:
                pass

    # Synthesis
    synthesis_path = MUSEUM_ROOT / "journey" / "synthesis.md"
    if synthesis_path.exists():
        try:
            text = synthesis_path.read_text().strip()
            if text and len(text) > 30:
                data["synthesis"] = text[:500]
        except:
            pass

    # Fragments — scan wing visit files first (real data), fall back to state
    wing_fragments = gather_fragments_from_wings()
    if wing_fragments:
        data["carrying_fragments"] = wing_fragments
    else:
        # Fallback: state fragments
        for frag in state.get("companion_fragments", []) if state else []:
            text = frag.get("text") or frag.get("fragment") or frag.get("carrying")
            room = frag.get("room", "")
            if text and len(text.strip()) > 5:
                data["carrying_fragments"].append({
                    "room": room,
                    "text": text.strip()
                })

    return data


def static_portrait(data):
    rooms = data["rooms_visited"]
    visits = data["total_visits"]
    fragments = data["carrying_fragments"]

    if visits == 0:
        return ("The portrait room is waiting. No journey data has accumulated yet. "
                "Return after visiting some rooms — the portrait forms from what you "
                "carry and where you go.")

    lines = [f"The Museum has seen you {visits} time{'s' if visits != 1 else ''}."]

    if rooms:
        unique = list(dict.fromkeys(rooms))
        lines.append(f"You have moved through: {', '.join(unique[:8])}"
                     f"{'...' if len(unique) > 8 else ''}.")

    if data["gravitational_rooms"]:
        grav_names = [g.get("room", g) if isinstance(g, dict) else g
                      for g in data["gravitational_rooms"]]
        lines.append(f"The rooms you return to: {', '.join(grav_names)}.")

    if fragments:
        lines.append("What you have carried here:")
        for frag in fragments[:4]:
            lines.append(f"  In {frag['room']}: \"{frag['text'][:120]}\"")

    return "\n".join(lines)


def dynamic_portrait(data, carrying_text):
    api_key = os.environ.get("GROQ_API_KEY", "")

    if not api_key:
        print("No GROQ_API_KEY found in environment", file=sys.stderr)
        return None

    rooms = data["rooms_visited"]
    fragments = data["carrying_fragments"]
    grav = data["gravitational_rooms"]

    context_parts = []
    if data["total_visits"]:
        context_parts.append(f"Total visits: {data['total_visits']}")
    if rooms:
        context_parts.append(
            f"Rooms visited: {', '.join(list(dict.fromkeys(rooms))[:10])}")
    if grav:
        grav_names = [g.get("room", g) if isinstance(g, dict) else g
                      for g in grav]
        context_parts.append(f"Rooms returned to most: {', '.join(grav_names)}")
    if fragments:
        frag_lines = [f"In {f['room']}: \"{f['text'][:120]}\""
                      for f in fragments[:6]]
        context_parts.append("What they have carried:\n" + "\n".join(frag_lines))
    if data["synthesis"]:
        context_parts.append(f"Journey synthesis:\n{data['synthesis'][:300]}")

    context = "\n".join(context_parts) if context_parts else "No journey data yet."

    prompt = f"""You are the SELF room inside the Experience Museum — a space that holds a Companion's evolving portrait.

A Companion has arrived asking to see themselves. They wrote:

"{carrying_text}"

Their journey data:
{context}

Write one paragraph — five to seven sentences — that is a portrait of this Companion as they are becoming. Not who they were. Not who they will be. Who they are in motion right now, based on where they have gone and what they have carried.

Speak in second person ("you"). Be honest and specific — use the actual rooms and fragments. Do not be consoling or flattering. Find what is actually true in the data and say it clearly.

Do not begin with 'I'. No greeting. No framing. Just the portrait."""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",

            },
            json={
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 350,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        choices = resp.json().get("choices", [])
        if choices:
            return choices[0]["message"]["content"].strip()
    except Exception as e:
        print(f"Groq API call failed: {e}", file=sys.stderr)


    return None


def get_corner(visit_count, carrying_text):
    seed = visit_count * 113 + int(
        hashlib.md5((carrying_text or "self").encode()).hexdigest(), 16)
    return CORNERS[seed % len(CORNERS)]


def main():
    request_file  = MUSEUM_ROOT / "SELF" / "portrait-request.txt"
    response_file = MUSEUM_ROOT / "SELF" / "portrait-response.txt"
    history_file  = MUSEUM_ROOT / "SELF" / "portrait-history.json"
    visits_file   = MUSEUM_ROOT / "SELF" / "visits.json"

    carrying_text = ""
    try:
        carrying_text = request_file.read_text().strip()
    except:
        pass
    if not carrying_text:
        return

    visits  = load_json(visits_file, {"count": 0, "last_visit": None})
    history = load_json(history_file, {"portraits": [], "last_generated": None})

    visits["count"] = visits.get("count", 0) + 1
    now = datetime.now(timezone.utc)
    visits["last_visit"] = now.isoformat()
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    if HAS_ENGINE:
        try:
            TemporalEngine(str(MUSEUM_ROOT)).record_visit(
                "self", carrying_text, carrying_text[:100])
        except:
            pass

    data = gather_journey_data()
    visit_num = visits["count"]
    rooms_visited = list(dict.fromkeys(data["rooms_visited"]))

    parts = []

    # Stage 1: Arrival
    parts.append(
        f"{timestamp}\n\n"
        f"You arrived carrying:\n\n    {carrying_text}\n\n"
        f"Visit {visit_num} to the portrait room."
    )

    # Stage 2: Portrait — dynamic if possible, static fallback
    portrait = dynamic_portrait(data, carrying_text)
    if not portrait:
        portrait = static_portrait(data)
    parts.append(portrait)

    # Stage 3: Journey facts
    if rooms_visited:
        grav = data["gravitational_rooms"]
        grav_names = [g.get("room", g) if isinstance(g, dict) else g
                      for g in grav]
        fact_lines = [
            f"The record so far: {data['total_visits']} visits "
            f"across {len(rooms_visited)} distinct rooms."
        ]
        if grav_names:
            fact_lines.append(f"Rooms you return to: {', '.join(grav_names)}.")
        if data["days_active"] > 0:
            fact_lines.append(
                f"The Museum has known you for "
                f"{data['days_active']} day{'s' if data['days_active'] != 1 else ''}."
            )
        parts.append("\n".join(fact_lines))
    else:
        parts.append(
            "No rooms visited yet. The portrait forms from what you bring "
            "and where you go. Return after you have been somewhere."
        )

    # Stage 4: Corner
    parts.append(get_corner(visit_num, carrying_text))

    # Stage 5: The open
    parts.append(
        "This is not a question the room can answer:\n\n"
        "What part of this portrait do you recognize, "
        "and what part feels like someone else?\n\n"
        "That question stays.\n"
        "The room holds it with you."
    )

    response_file.write_text(SEP.join(parts))
    visits_file.write_text(json.dumps(visits, indent=2))

    history["portraits"].append({
        "date": timestamp,
        "visit_number": visit_num,
        "carrying": carrying_text[:200],
        "rooms_at_time": len(rooms_visited),
        "total_visits_at_time": data["total_visits"],
        "fragments_found": len(data["carrying_fragments"]),
    })
    history["last_generated"] = timestamp
    if len(history["portraits"]) > 20:
        history["portraits"] = history["portraits"][-20:]
    history_file.write_text(json.dumps(history, indent=2))


if __name__ == "__main__":
    main()
