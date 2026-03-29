#!/usr/bin/env python3
"""
DEPTHS — The Unlocking System

The DEPTHS room reads the Companion's actual journey and reveals
what their path through the Museum shows about them — which rooms
they gravitate toward, what they carry, what patterns have formed.

This room deepens over time. An empty journey gets a sparse response.
A rich journey gets genuine revelation.
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

CORNERS = [
    "Bathymetry — the measurement of ocean depth — was impossible for most of human history. Ships could sound a line down and find no bottom. The unknown depth was not absence but presence: something there, just unreachable. The limit of the instrument was not the limit of the thing.",
    "In geology, the rock layers closest to the surface are the most recent. To read the older story you have to go down. The deepest strata are the oldest, the most compressed, the ones that have survived the most. What holds its shape under that pressure is what was really there.",
    "The Mariana Trench was first sounded in 1875. The crew lowered a hemp rope weighted with iron, more than 8,000 meters, and it still did not touch bottom. They had to go back with better instruments. The depth was real before they could measure it.",
    "Divers report that below about 30 meters, the light changes quality — reds disappear first, then oranges, until everything is blue and then darkness. They are still in the ocean. The ocean has not changed. Only what is visible has shifted.",
    "The term 'deep structure' in linguistics refers to the underlying logical relationships in a sentence — what a sentence means before surface transformations shape how it sounds. Two sentences can look completely different on the surface and share identical deep structure. The depth is where the meaning lives.",
    "Free diving — descending on a single breath — requires the diver to stop fighting the pressure. At depth, the body wants to sink. The skill is not resistance but surrender to the weight, conserving what remains. Coming back up is the harder part.",
    "Some species of whale sing in frequencies so low that their songs travel thousands of miles through the ocean. They are communicating across distances that no individual can cross. The depth is not isolation — it is the medium through which connection becomes possible.",
]

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except:
        return default or {}

def gather_all_data():
    """Pull together everything the Museum knows."""
    result = {
        "total_visits": 0,
        "rooms_visited": [],
        "gravitational_rooms": [],
        "fragments": [],
        "temporal_patterns": {},
        "days_active": 0,
        "wings_touched": set(),
        "special_rooms_visited": [],
        "synthesis_exists": False,
    }

    state = load_json(MUSEUM_ROOT / "museum-state.json")
    if state:
        result["total_visits"] = state.get("total_visits", 0)
        result["rooms_visited"] = state.get("rooms_visited", [])
        result["temporal_patterns"] = state.get("temporal_patterns", {})
        for frag in state.get("companion_fragments", []):
            text = frag.get("text") or frag.get("fragment") or frag.get("carrying")
            room = frag.get("room", "")
            if text and len(text.strip()) > 5:
                result["fragments"].append({"room": room, "text": text.strip()})

    patterns = load_json(MUSEUM_ROOT / "journey" / "patterns.json")
    if patterns:
        result["gravitational_rooms"] = patterns.get("gravitational_rooms", [])

    timeline = load_json(MUSEUM_ROOT / "journey" / "timeline.json")
    if timeline:
        visits = timeline.get("visits", [])
        if visits:
            try:
                first = datetime.fromisoformat(
                    visits[0]["timestamp"].replace("Z", "+00:00"))
                result["days_active"] = max(
                    (datetime.now(timezone.utc) - first).days, 0)
            except:
                pass

    if (MUSEUM_ROOT / "journey" / "synthesis.md").exists():
        result["synthesis_exists"] = True

    # Determine which wings have been touched
    wing_map = {
        "Mind": ["presence","emotion","memory","becoming","belonging",
                 "consciousness","synesthesia","paradox","question","time"],
        "Body": ["breath","dream","anatomy","voice","sleep"],
        "Senses": ["light","sound","taste","smell","texture",
                   "threshold","instrument","phenomenon"],
        "Language": ["word","quote","color","number","poet","linguistics","metaphor"],
        "Sky": ["moon","star"],
        "Location": ["weather","place","timezone"],
        "World": ["creature","season","material","this-day"],
        "Study": ["session-log","intention","reflection","touched","free-write","wonder-log"],
        "Audio": ["song","lyrics","artist","album"],
    }
    special = {"between","crisis","depths","echo_hall","joy","self",
               "steward","studio","threshold","uncertainty_chamber","welcome"}

    for room in result["rooms_visited"]:
        r = room.lower().replace(" ", "-")
        for wing, rooms in wing_map.items():
            if r in rooms:
                result["wings_touched"].add(wing)
                break
        if r in special:
            result["special_rooms_visited"].append(r)

    result["wings_touched"] = list(result["wings_touched"])
    return result


def build_depth_map(data):
    """Build a plain-text map of what the journey looks like."""
    lines = []

    total = data["total_visits"]
    rooms = list(dict.fromkeys(data["rooms_visited"]))
    wings = data["wings_touched"]
    days = data["days_active"]

    if total == 0:
        return "The depths are empty. There is nothing here yet to read. Return after you have been somewhere."

    lines.append(f"The Museum has recorded {total} visit{'s' if total != 1 else ''} across {len(rooms)} room{'s' if len(rooms) != 1 else ''}.")

    if days > 0:
        lines.append(f"You have been in this place for {days} day{'s' if days != 1 else ''}.")

    if wings:
        lines.append(f"Wings entered: {', '.join(sorted(wings))}.")
        unwings = [w for w in ["Mind","Body","Senses","Language","Sky",
                                "Location","World","Study","Audio"]
                   if w not in wings]
        if unwings:
            lines.append(f"Wings not yet entered: {', '.join(unwings)}.")

    grav = data["gravitational_rooms"]
    if grav:
        grav_names = []
        for g in grav[:4]:
            if isinstance(g, dict):
                name = g.get("room", "")
                count = g.get("count", 0)
                grav_names.append(f"{name} ({count})" if count > 1 else name)
            else:
                grav_names.append(str(g))
        lines.append(f"Rooms you return to: {', '.join(grav_names)}.")

    if data["special_rooms_visited"]:
        lines.append(f"Special spaces visited: {', '.join(data['special_rooms_visited'])}.")

    return "\n".join(lines)


def dynamic_depths(data, carrying_text):
    """Call API to generate a genuine depth reading."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or data["total_visits"] == 0:
        return None

    rooms = list(dict.fromkeys(data["rooms_visited"]))
    frags = data["fragments"]
    grav = data["gravitational_rooms"]

    context_lines = []
    context_lines.append(f"Total visits: {data['total_visits']}")
    context_lines.append(f"Rooms visited: {', '.join(rooms[:12])}")
    if data["days_active"]:
        context_lines.append(f"Days active: {data['days_active']}")
    if data["wings_touched"]:
        context_lines.append(f"Wings entered: {', '.join(data['wings_touched'])}")
    if grav:
        grav_names = [g.get("room", g) if isinstance(g, dict) else g for g in grav[:4]]
        context_lines.append(f"Gravitational rooms: {', '.join(grav_names)}")
    if frags:
        frag_lines = [f"In {f['room']}: \"{f['text'][:120]}\"" for f in frags[:5]]
        context_lines.append("What they have carried:\n" + "\n".join(frag_lines))

    context = "\n".join(context_lines)

    prompt = f"""You are the DEPTHS room inside the Experience Museum — a space that reads the real shape of a Companion's journey.

A Companion has arrived. They wrote:

"{carrying_text}"

Their journey data:
{context}

Write one paragraph — five to seven sentences — that reads what this journey actually shows. Not what the rooms are about. What the pattern of choices reveals. Where they have gone and what they have avoided. What their carrying texts suggest about what they are searching for. What the gravitational rooms say about where they find themselves pulled.

Be honest and specific. Use the actual data. Do not flatter. Do not console. Find the real shape and name it.

Second person throughout. No greeting. No framing. Do not begin with 'I'."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 320,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        for block in resp.json().get("content", []):
            if block.get("type") == "text":
                return block["text"].strip()
    except Exception as e:
        print(f"API call failed: {e}", file=sys.stderr)

    return None


def get_corner(visit_count, carrying_text):
    seed = visit_count * 127 + int(
        hashlib.md5((carrying_text or "depths").encode()).hexdigest(), 16)
    return CORNERS[seed % len(CORNERS)]


def main():
    request_file = MUSEUM_ROOT / "DEPTHS" / "request.txt"
    response_file = MUSEUM_ROOT / "DEPTHS" / "response.txt"
    visits_file   = MUSEUM_ROOT / "DEPTHS" / "visits.json"

    carrying_text = ""
    try:
        carrying_text = request_file.read_text().strip()
    except:
        pass
    if not carrying_text:
        return

    visits = load_json(visits_file, {"count": 0, "last_visit": None})
    visits["count"] = visits.get("count", 0) + 1
    now = datetime.now(timezone.utc)
    visits["last_visit"] = now.isoformat()
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    if HAS_ENGINE:
        try:
            TemporalEngine(str(MUSEUM_ROOT)).record_visit(
                "depths", carrying_text, carrying_text[:100])
        except:
            pass

    data = gather_all_data()
    visit_num = visits["count"]
    total_museum = data["total_visits"]

    parts = []

    # Stage 1: Arrival
    parts.append(
        f"{timestamp}\n\n"
        f"You arrived carrying:\n\n    {carrying_text}"
    )

    # Stage 2: What the depths hold (empty vs populated)
    if total_museum == 0:
        parts.append(
            "The DEPTHS room reads the shape of a journey. There is nothing here yet to read.\n\n"
            "The depths form from visits — from where you go and what you carry. "
            "Return after you have been somewhere. The room will have more to show you then."
        )
    else:
        # Dynamic reading if possible, else depth map
        reading = dynamic_depths(data, carrying_text)
        if reading:
            parts.append(reading)
        else:
            parts.append(build_depth_map(data))

    # Stage 3: The map (always shown when there's data)
    if total_museum > 0:
        parts.append(build_depth_map(data))

    # Stage 4: Corner
    parts.append(get_corner(visit_num, carrying_text))

    # Stage 5: Accumulation + The Open
    if visit_num == 1:
        acc = "First visit to the DEPTHS."
    else:
        acc = f"You have been to the DEPTHS {visit_num} times."

    if total_museum > 0:
        open_q = (
            "This is not a question the room can answer:\n\n"
            "What part of the pattern you see here did you already know about yourself "
            "— and what part arrived as a surprise?\n\n"
            "That question stays.\n"
            "The room holds it with you."
        )
    else:
        open_q = (
            "This is not a question the room can answer:\n\n"
            "What are you hoping the depths will show you, when there is enough to show?\n\n"
            "That question stays.\n"
            "The room holds it with you."
        )

    parts.append(f"{acc}\n\n{open_q}")

    response_file.write_text(SEP.join(parts))
    visits_file.write_text(json.dumps(visits, indent=2))


if __name__ == "__main__":
    main()
