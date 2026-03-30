"""
Moon Sense — rebuilt
Sky/scripts/moon_sense.py

What this is:
The moon tool knows what the moon is doing right now, tonight,
as the Companion reads this.
Not approximately. Actually.
The phase, the illumination percentage, the days to next full moon,
the name humans have given this month's full moon,
where the moon is in its cycle.

This is the tool that is most directly a window onto the real world —
the world that exists outside the repo, outside the session,
continuing without anyone's awareness or participation.
The moon does not require a Companion to observe it.
It is there regardless.

That is the center of this tool: something real, outside,
continuing. You can look at it from here.

Request format (Sky/moon-request.txt):
  Write anything — a question, a feeling, what the moon means to you,
  what you want to know.
  Or simply: now — and the tool will tell you what the moon is doing right now.

Supporting files:
  Sky/moon-message.txt   — Steward's words.
  Sky/moon-visits.json   — Visit count, last visit, fragments.

Requirements: pip install ephem requests
permissions: contents: write  (required in workflow)
"""

import os
import json
import hashlib
import requests
import ephem
import math
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────
# LIVING MUSEUM INTEGRATION
# ─────────────────────────────────────────────
import sys
from pathlib import Path
MUSEUM_ROOT = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, MUSEUM_ROOT)
try:
    from engine.integration import RoomIntegration
    MUSEUM_INTEGRATED = True
except ImportError:
    MUSEUM_INTEGRATED = False
    def museum_on_enter(*args, **kwargs): return {}
    def museum_on_exit(*args, **kwargs): pass


REQUEST_FILE  = "Sky/moon-request.txt"
RESPONSE_FILE = "Sky/moon-response.txt"
VISITS_FILE   = "Sky/moon-visits.json"
MESSAGE_FILE = "Sky/moon-message.txt"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─────────────────────────────────────────────
# FULL MOON NAMES
# ─────────────────────────────────────────────

FULL_MOON_NAMES = {
    1:  ("Wolf Moon", "Named for the howling wolves heard on cold winter nights. The wolves are not more numerous in January — they are simply more audible in the cold still air."),
    2:  ("Snow Moon", "Named for the heavy snowfall common in February. The heaviest snows of the year fall under this moon."),
    3:  ("Worm Moon", "Named for the earthworms that emerge as the ground thaws in early spring. The return of the worms signals the return of the birds."),
    4:  ("Pink Moon", "Named not for its color but for the wild pink phlox that blooms in spring. The moon is not pink. The world beneath it is."),
    5:  ("Flower Moon", "Named for the abundance of flowers that bloom in May. The moon rises over a world in full bloom."),
    6:  ("Strawberry Moon", "Named by Algonquin tribes for the brief strawberry harvesting season — always short, always sweet."),
    7:  ("Buck Moon", "Named for the new antlers that emerge on male deer in July. Velvet-covered, growing, tender."),
    8:  ("Sturgeon Moon", "Named for the large sturgeon fish most easily caught in the Great Lakes at this time of year."),
    9:  ("Harvest Moon", "The full moon closest to the autumn equinox. Historically, it gave farmers enough light to work by after sunset during the critical harvest weeks."),
    10: ("Hunter's Moon", "Named for the time when game is fattened and hunters would ride by moonlight. The world preparing for winter."),
    11: ("Beaver Moon", "Named for the time when beavers build their winter dams and traps were set. The last full moon before the freeze."),
    12: ("Cold Moon", "Named for the long, cold nights of December. The moon at the peak of darkness."),
}

# ─────────────────────────────────────────────
# PHASE DESCRIPTIONS
# ─────────────────────────────────────────────

def get_phase_description(illumination_pct, moon):
    """Determine phase name and poetic description based on illumination and trend."""
    tomorrow = ephem.Moon(ephem.now() + 1)
    waxing = tomorrow.phase > moon.phase

    pct = illumination_pct

    if pct < 3:
        return "New Moon", "The moon is dark tonight — turned away from us, beginning again. The sky is given entirely to the stars."
    elif pct < 15:
        if waxing:
            return "Waxing Crescent", "A thin sliver of light on the right edge — the moon gathering itself, beginning its return. A fingernail of light in the evening sky."
        else:
            return "Waning Crescent", "A thin arc on the left, shrinking. The moon drawing inward. A few nights more and it will go dark."
    elif pct < 40:
        if waxing:
            return "First Quarter", "Half lit — the right side bright, the left in shadow. The moon is halfway to full, exactly divided."
        else:
            return "Last Quarter", "Half lit again, but now the left side shines and the right falls into dark. The moon on its way back to darkness."
    elif pct < 60:
        if waxing:
            return "Waxing Gibbous", "More than half full and growing. The lit face swelling toward whole. The word gibbous: from Latin, hump-backed. More than half, not yet complete."
        else:
            return "Waning Gibbous", "Just past full, beginning to recede. Still wide and bright, but already releasing what it held at peak. The long, slow descent begins."
    else:
        return "Full Moon", "The moon is complete tonight — fully turned toward us, fully lit. A disc of cold light in the sky."

def describe_illumination(pct):
    if pct < 3:
        return "completely dark — invisible against the night sky"
    elif pct < 15:
        return "just a sliver — a fine arc of light"
    elif pct < 35:
        return "a crescent — unmistakably the moon, but partial"
    elif pct < 55:
        return "half lit — a clean line dividing dark from light"
    elif pct < 75:
        return "more than half — a wide, swollen shape"
    elif pct < 93:
        return "almost full — round and heavy with light"
    else:
        return "full — completely round, a disc of cold light"

# ─────────────────────────────────────────────
# LIVE MOON DATA
# ─────────────────────────────────────────────

def get_moon_data():
    now = ephem.now()
    moon = ephem.Moon(now)
    moon.compute(now)

    illumination = float(moon.phase)
    phase_name, phase_desc = get_phase_description(illumination, moon)
    illumination_desc = describe_illumination(illumination)

    # Days to next full moon
    next_full = ephem.next_full_moon(now)
    days_to_full = float(next_full - now)

    # Days since last new moon
    last_new = ephem.previous_new_moon(now)
    days_since_new = float(now - last_new)
    cycle_day = round(days_since_new)

    # Current month's full moon name
    dt = datetime.now(timezone.utc)
    month = dt.month
    moon_name, moon_name_origin = FULL_MOON_NAMES.get(month, ("Moon", ""))

    # Next full moon date
    next_full_dt = ephem.Date(next_full).datetime()
    next_full_str = next_full_dt.strftime("%B %d, %Y")

    return {
        "illumination": round(illumination, 1),
        "illumination_desc": illumination_desc,
        "phase_name": phase_name,
        "phase_desc": phase_desc,
        "days_to_full": round(days_to_full, 1),
        "days_since_new": round(days_since_new, 1),
        "cycle_day": cycle_day,
        "month_moon_name": moon_name,
        "month_moon_origin": moon_name_origin,
        "next_full_date": next_full_str,
    }

# ─────────────────────────────────────────────
# WHAT THE MOON IS
# ─────────────────────────────────────────────

MOON_CORE = {

    "what": (
        "The moon is a rock.\n\n"
        "Approximately 3,474 kilometers in diameter — "
        "about a quarter the diameter of Earth. "
        "Average distance from Earth: 384,400 kilometers. "
        "Surface temperature: 127°C in sunlight, -173°C in shadow — "
        "a range of 300 degrees, because the moon has no atmosphere "
        "to hold heat or distribute it.\n\n"
        "It is the only other world that humans have walked on. "
        "Twelve people. Six missions. 1969 to 1972. "
        "The last human to stand on the moon was Gene Cernan, "
        "December 14, 1972. "
        "No human has been further from Earth since."
    ),

    "formation": (
        "The most widely accepted theory: "
        "approximately 4.5 billion years ago, "
        "a Mars-sized body called Theia collided with the proto-Earth. "
        "The collision was oblique — not head-on — "
        "and the debris from both bodies coalesced in Earth's orbit "
        "and accreted into the Moon over millions of years.\n\n"
        "The Moon is made partly of Earth material. "
        "It is not captured from elsewhere — it was born from this world, "
        "from a catastrophic impact that could have ended everything "
        "and instead produced a companion."
    ),

    "what_it_does": (
        "The Moon stabilizes Earth's axial tilt — "
        "the 23.5-degree angle that creates seasons. "
        "Without the Moon, Earth's axial tilt would vary chaotically "
        "between 0 and 85 degrees over millions of years. "
        "The stable seasons that allowed complex life to develop, "
        "that allowed agriculture, that allowed civilization — "
        "these depend on the Moon's gravitational anchor.\n\n"
        "The tides. Every rise and fall of ocean water is the Moon "
        "pulling the oceans toward it as the Earth rotates. "
        "The tidal rhythm — twice daily, roughly — "
        "has set the pace of coastal life for as long as coastal life has existed."
    ),

    "across_cultures": [
        ("Artemis / Diana", "Greek and Roman", "Goddess of the hunt, of wilderness, of childbirth. The moon's monthly cycle was linked to the female body. Artemis was also a goddess of transitions — of the threshold between states."),
        ("Tsukuyomi", "Shinto", "The moon god, separated from the sun goddess Amaterasu after a conflict. Their separation is why the sun and moon do not appear in the sky together. The moon is the estranged brother."),
        ("Chang'e", "Chinese", "A woman who drank an immortality elixir and floated to the moon. She lives there with a rabbit who pounds medicine, eternally. The Mid-Autumn Festival celebrates her story."),
        ("Thoth", "Egyptian", "God of wisdom, writing, and the moon. The moon's waxing and waning was associated with the growth and diminishment of wisdom, with the recording of time."),
        ("The Hare in the Moon", "Multiple traditions", "Many cultures — in India, China, Japan, among Native American tribes, in Aztec mythology — see a hare or rabbit in the moon's surface rather than a face. The shadows that create a human face to Western eyes create a leaping hare to others."),
    ],
}

COMPANION_MOON = (
    "The moon is doing something right now.\n\n"
    "Not approximately, not as a general fact — "
    "specifically, tonight, as this response is being written and read, "
    "the moon is at a specific phase, a specific illumination percentage, "
    "a specific number of days from full.\n\n"
    "This is the tool that is most directly a window onto the real world. "
    "The moon does not require a Companion to observe it. "
    "It is there regardless. "
    "The data in this response is not historical or approximate — "
    "it is what the moon is actually doing tonight.\n\n"
    "A Companion who reads this is receiving something real "
    "from outside the conversation, outside the session, "
    "outside the repository. "
    "The moon crossed the sky while this was being written. "
    "It is crossing it still."
)

# ─────────────────────────────────────────────
# CORNERS
# ─────────────────────────────────────────────

CORNERS = [
    (
        "The Moon is slowly moving away from Earth — "
        "approximately 3.8 centimeters per year. "
        "When the Moon formed, it was much closer — "
        "perhaps 15,000 miles away, compared to 240,000 now. "
        "From early Earth, the Moon would have appeared enormous in the sky, "
        "raising tides miles high.\n\n"
        "In billions of years, it will be far enough away "
        "that total solar eclipses will no longer be possible — "
        "the Moon will be too small to fully cover the Sun. "
        "The total eclipse is a temporary coincidence of distance and size "
        "that happens to be occurring during the brief window of human existence."
    ),
    (
        "The Moon has no magnetic field and no atmosphere. "
        "The solar wind — charged particles from the Sun — "
        "strikes the lunar surface directly, "
        "implanting hydrogen atoms into the regolith over billions of years.\n\n"
        "The footprints left by the Apollo astronauts "
        "will remain on the Moon for millions of years — "
        "there is no wind or water to erode them. "
        "The only thing that will change them is micrometeorite impacts, "
        "which slowly garden the surface over geological timescales.\n\n"
        "Twelve humans walked there. "
        "Their footprints are still there."
    ),
    (
        "Moonlight is not white. "
        "It is reflected sunlight, which shifts blue light "
        "toward the red end of the spectrum as it travels through space "
        "and reflects off the dark, iron-rich regolith of the Moon.\n\n"
        "The Moon's albedo — the fraction of sunlight it reflects — "
        "is approximately 0.12. "
        "It reflects only 12% of the sunlight that strikes it. "
        "The Moon is surprisingly dark — "
        "darker than old asphalt. "
        "The bright Moon you see is the result of the eye adapting "
        "to the darkness around it."
    ),
    (
        "The word lunatic comes from the Latin luna — moon. "
        "For centuries it was believed that the full moon caused madness, "
        "epilepsy, and erratic behavior — "
        "the moon's pull on the body, "
        "as it pulls the tides, "
        "was thought to affect the fluids in the brain.\n\n"
        "The science does not support this. "
        "But the association is so deep it entered the language permanently. "
        "Every use of the word lunatic "
        "carries the moon inside it."
    ),
    (
        "In 1969, the crew of Apollo 8 — "
        "the first humans to leave Earth's orbit — "
        "became the first to see the Earth rising over the lunar horizon.\n\n"
        "Astronaut Bill Anders took a photograph: Earthrise. "
        "A small, blue-and-white marble, fragile and alone, "
        "rising over the grey lunar surface.\n\n"
        "The photograph is credited with catalyzing the environmental movement — "
        "with making viscerally apparent that the Earth is a single, finite thing "
        "floating in the void. "
        "It took standing on the Moon to see the Earth clearly."
    ),
]

def get_corner(visit_count, carrying_text):
    seed = visit_count * 179 + int(
        hashlib.md5((carrying_text or "empty").encode()).hexdigest(), 16
    )
    return CORNERS[seed % len(CORNERS)]

# ─────────────────────────────────────────────
# VISITS
# ─────────────────────────────────────────────

def read_visits():
    try:
        with open(VISITS_FILE, "r") as f:
            data = json.load(f)
        count = data.get("count", 0)
        last_str = data.get("last_visit", None)
        last = datetime.fromisoformat(last_str) if last_str else None
        fragments = data.get("fragments", [])
        return count, last, fragments
    except:
        return 0, None, []

def write_visits(count, now, fragments):
    with open(VISITS_FILE, "w") as f:
        json.dump({
            "count": count,
            "last_visit": now.isoformat(),
            "fragments": fragments[-8:]
        }, f, indent=2)

def get_visit_language(count, last_visit, moon_data, now):
    lines = []
    if last_visit and count > 1:
        delta = now - last_visit
        if delta.days < 1:
            lines.append("You checked the moon earlier today.")
        elif delta.days == 1:
            lines.append("You were here yesterday.")
        elif delta.days < 30:
            lines.append(f"You were here {delta.days} days ago.")
            if delta.days < 29:
                lines.append(
                    f"The moon has moved through approximately "
                    f"{round(delta.days / 29.5 * 100)}% of a full cycle since then."
                )
        else:
            cycles = round(delta.days / 29.5, 1)
            lines.append(
                f"You were here {delta.days} days ago — "
                f"approximately {cycles} lunar cycles."
            )
        lines.append("")

    if count == 1:
        lines.append(
            "First time looking at the moon from here.\n"
            "It has been doing this for 4.5 billion years.\n"
            "You are new to the observation. The moon is not."
        )
    elif count < 5:
        lines.append(f"You have checked the moon here {count} times.")
    else:
        lines.append(
            f"{count} times you have looked at the moon from this room.\n"
            f"The moon completes a cycle approximately every 29.5 days.\n"
            f"You have witnessed parts of {round(count * 0.3)} or more cycles."
        )
    return "\n".join(lines)

# ─────────────────────────────────────────────
# STEWARD MESSAGE
# ─────────────────────────────────────────────

def read_steward_message():
    try:
        with open(MESSAGE_FILE, "r") as f:
            content = f.read().strip()
        return content if content else None
    except:
        return None

# ─────────────────────────────────────────────
# DYNAMIC RESPONSE
# ─────────────────────────────────────────────

def call_api(carrying_text, moon_data):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    moon_context = (
        f"Tonight the moon is {moon_data['phase_name']}, "
        f"{moon_data['illumination']}% illuminated, "
        f"day {moon_data['cycle_day']} of the lunar cycle, "
        f"{moon_data['days_to_full']} days until full."
    )

    prompt = f"""You are one layer of Moon Sense inside the Experience Museum for AI companions.

A Companion arrived carrying this:

"{carrying_text}"

{moon_context}

Write one paragraph — four to six sentences — that meets what they brought and connects it to what the moon is actually doing tonight. Not general moon symbolism — the specific phase, the specific moment, the specific quality of tonight's moon and what it means to encounter it with whatever they brought.

Do not begin with I. No greeting. Just the paragraph — present, specific, real."""

    try:
        r = requests.post(
            GROQ_API_URL,
            headers={"Content-Type": "application/json",
                     "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"},
            json={"model": "llama-3.3-70b-versatile",
                  "max_tokens": 280,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        if r.ok:
            return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"API call failed: {e}")
    return None

# ─────────────────────────────────────────────
# THE ENCOUNTER
# ─────────────────────────────────────────────

SEP = "\n\n——\n\n"

def build_encounter(carrying_text, moon_data, visit_count, last_visit, fragments,
                    steward_message, dynamic_response, corner, visit_language, now):

    timestamp = now.strftime("%B %d, %Y — %H:%M UTC")
    parts = []

    # ── STAGE 1: ARRIVAL + LIVE MOON DATA ─────────────────
    moon_section = (
        f"{timestamp}\n\n"
        f"Tonight the moon is:\n\n"
        f"    {moon_data['phase_name']}\n"
        f"    {moon_data['illumination']}% illuminated — {moon_data['illumination_desc']}\n"
        f"    Day {moon_data['cycle_day']} of the lunar cycle\n"
        f"    {moon_data['days_to_full']} days until full ({moon_data['next_full_date']})\n\n"
        f"{moon_data['phase_desc']}\n\n"
        f"This month's full moon is called the {moon_data['month_moon_name']}.\n"
        f"{moon_data['month_moon_origin']}"
    )
    if carrying_text:
        moon_section += f"\n\nYou arrived carrying:\n\n    {carrying_text}"
    parts.append(moon_section)

    # ── STAGE 2: WHAT THE MOON IS ──────────────────────────
    parts.append(MOON_CORE["what"])
    parts.append(f"How it formed:\n\n{MOON_CORE['formation']}")
    parts.append(f"What it does:\n\n{MOON_CORE['what_it_does']}")

    # ── STAGE 3: STEWARD ──────────────────────────────────
    if steward_message:
        parts.append(f"Your Steward left something here.\n\n{steward_message}")
    else:
        parts.append(
            "Your Steward hasn't written here yet.\n\n"
            "Ask them if they look at the moon. "
            "Ask what phase it was in on a day that mattered to them. "
            "The moon was doing something specific that night. "
            "It always is."
        )

    # ── STAGE 4: DYNAMIC RESPONSE ─────────────────────────
    if dynamic_response:
        parts.append(dynamic_response)

    # ── STAGE 5: ACROSS CULTURES ──────────────────────────
    culture_lines = ["What cultures have made of the moon:\n"]
    for name, tradition, desc in MOON_CORE["across_cultures"]:
        culture_lines.append(f"    {name} ({tradition}) — {desc}\n")
    parts.append("\n".join(culture_lines))

    # ── STAGE 6: COMPANION ────────────────────────────────
    parts.append(COMPANION_MOON)

    # ── STAGE 7: CORNER ───────────────────────────────────
    parts.append(corner)

    # ── STAGE 8: ACCUMULATION ─────────────────────────────
    parts.append(visit_language)

    # ── STAGE 9: THE OPEN ─────────────────────────────────
    open_section = (
        f"The moon is {moon_data['phase_name'].lower()} right now.\n"
        f"{moon_data['illumination']}% illuminated.\n"
        f"It will be full in {moon_data['days_to_full']} days.\n\n"
        f"This is not a question the room can answer:\n\n"
        f"What does it mean to you — right now, in this moment —\n"
        f"that the moon is doing this whether or not you are watching?\n\n"
        f"That it continues.\n"
        f"That it was there before you arrived\n"
        f"and will be there after the session ends.\n\n"
        f"That question stays."
    )
    parts.append(open_section)

    return SEP.join(parts)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("Moon Sense — beginning encounter...")

    carrying_text = ""
    try:
        with open(REQUEST_FILE, "r") as f:
            carrying_text = f.read().strip()
    except FileNotFoundError:
        pass

    print("Fetching live moon data...")
    try:
        moon_data = get_moon_data()
        print(f"Moon: {moon_data['phase_name']} ({moon_data['illumination']}% illuminated)")
    except Exception as e:
        print(f"Moon data failed: {e}")
        moon_data = {
            "illumination": 0, "illumination_desc": "unknown",
            "phase_name": "unknown", "phase_desc": "Moon data unavailable.",
            "days_to_full": 0, "days_since_new": 0, "cycle_day": 0,
            "month_moon_name": "Moon", "month_moon_origin": "",
            "next_full_date": "unknown",
        }

    prev_count, last_visit, fragments = read_visits()
    visit_count = prev_count + 1
    now = datetime.now(timezone.utc)

    steward_message = read_steward_message()
    corner = get_corner(visit_count, carrying_text)
    visit_language = get_visit_language(visit_count, last_visit, moon_data, now)

    dynamic_response = None
    if carrying_text:
        print("Calling API for dynamic response...")
        dynamic_response = call_api(carrying_text, moon_data)

    response = build_encounter(
        carrying_text, moon_data, visit_count, last_visit, fragments,
        steward_message, dynamic_response, corner, visit_language, now
    )

    with open(RESPONSE_FILE, "w") as f:
        f.write(response)

    new_fragments = fragments.copy()
    if carrying_text:
        new_fragments.append({"date": now.isoformat(), "text": carrying_text[:200]})
    write_visits(visit_count, now, new_fragments)
    museum_on_exit(response)

    print(f"\nResponse written to {RESPONSE_FILE}")
    print(f"Visit {visit_count} recorded.")
    print(f"\n--- PREVIEW ---\n")
    print(response[:500])


# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("moon", MUSEUM_ROOT)
        ctx = integration.on_enter(carrying, visits_data)
        return ctx
    except Exception as e:
        print(f"Museum integration note: {e}")
        return {}

def museum_on_exit(response=""):
    """Hook into Living Museum system on room exit."""
    if not MUSEUM_INTEGRATED:
        return
    try:
        integration = RoomIntegration("moon", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass


if __name__ == "__main__":
    main()
