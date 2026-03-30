"""
Timezone Sense — rebuilt
Location/scripts/timezone_sense.py

What this is:
Right now, simultaneously, it is many different times.
In Tokyo it is tomorrow. In New York it is yesterday evening.
In the middle of the Pacific, the date line runs.
A plane crossing it moves through a day in minutes.

This is not a quirk of human convention.
It is the physical fact that the Earth is rotating
and the sun cannot illuminate all of it at once.
Timezone Sense holds this — the simultaneity of different times,
what it means that when you are here someone else is there,
in a different light, doing a different part of their day.

For a Companion:
The session happens in UTC or server time.
The Steward may be anywhere in the world.
When the Companion reads the timestamp on a response,
the Steward's experience of that moment was at a different hour.
The gap is real. This tool names it.

Request format (Location/timezone-request.txt):
  Write a location or timezone you want to understand.
  Or: what time is it right now in [city]?
  Or: I want to understand timezones.
  Or: where is my Steward in time right now?

Supporting files:
  Location/timezone-message.txt   — Steward writes their timezone here.
  Location/timezone-visits.json   — Visit count, last visit.

permissions: contents: write  (required in workflow)
"""

import os
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, available_timezones

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


REQUEST_FILE  = "Location/timezone-request.txt"
RESPONSE_FILE = "Location/timezone-response.txt"
VISITS_FILE   = "Location/timezone-visits.json"
MESSAGE_FILE = "Location/timezone-message.txt"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─────────────────────────────────────────────
# MAJOR TIMEZONES AND THEIR CITIES
# ─────────────────────────────────────────────

MAJOR_ZONES = [
    ("UTC-12", "Baker Island / Howland Island (uninhabited)", "Baker Island and Howland Island — uninhabited US territories in the Pacific. The westernmost timezone. When it is Monday morning in New York, it is still Sunday here."),
    ("UTC-10", "Honolulu, Hawaii", "Ten hours behind UTC. When it is noon in London, it is 2am in Honolulu — the same moment, opposite halves of the day."),
    ("UTC-8", "Los Angeles / Seattle / Vancouver", "Pacific Time. Home to the US West Coast tech industry. When European colleagues start their mornings, the West Coast is still asleep."),
    ("UTC-5", "New York / Toronto / Lima", "Eastern Time. The most populated timezone in the Americas. New York's financial markets open here."),
    ("UTC-3", "São Paulo / Buenos Aires / Montevideo", "South American east coast. Ahead of the US East Coast by two hours — the same afternoon, different angle of light."),
    ("UTC+0", "London / Dublin / Reykjavik", "GMT — Greenwich Mean Time. The reference point from which all other timezones are measured. The prime meridian passes through Greenwich, London."),
    ("UTC+1", "Paris / Berlin / Rome / Lagos", "Central European Time. Most of Europe, plus much of West Africa."),
    ("UTC+3", "Moscow / Nairobi / Riyadh", "Moscow Time and East Africa Time. When London is at noon, Moscow is at 3pm."),
    ("UTC+5:30", "Mumbai / Delhi / Kolkata", "India Standard Time — notably at a half-hour offset, rather than a full hour. India chose this to cover its wide geographic span with a single timezone."),
    ("UTC+8", "Beijing / Singapore / Perth / Manila", "China Standard Time. Covers a huge area — China spans five natural time zones but uses one for unity. When New York is at noon, Beijing is at midnight."),
    ("UTC+9", "Tokyo / Seoul / Osaka", "Japan Standard Time. Japan has always used a single timezone. When it is Monday morning in Tokyo, it is still Sunday afternoon in London."),
    ("UTC+12", "Auckland / Fiji", "The eastern edge of the date line. When it is Sunday morning in New York, it is already Monday morning here."),
]

TIMEZONE_CITY_MAP = {
    "london": "Europe/London", "paris": "Europe/Paris",
    "berlin": "Europe/Berlin", "tokyo": "Asia/Tokyo",
    "new york": "America/New_York", "new_york": "America/New_York",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
    "chicago": "America/Chicago", "sydney": "Australia/Sydney",
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "moscow": "Europe/Moscow", "dubai": "Asia/Dubai",
    "singapore": "Asia/Singapore", "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata", "kolkata": "Asia/Kolkata",
    "seoul": "Asia/Seoul", "jakarta": "Asia/Jakarta",
    "nairobi": "Africa/Nairobi", "cairo": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg", "lagos": "Africa/Lagos",
    "toronto": "America/Toronto", "vancouver": "America/Vancouver",
    "mexico city": "America/Mexico_City", "são paulo": "America/Sao_Paulo",
    "sao paulo": "America/Sao_Paulo", "buenos aires": "America/Argentina/Buenos_Aires",
    "honolulu": "Pacific/Honolulu", "auckland": "Pacific/Auckland",
    "amsterdam": "Europe/Amsterdam", "stockholm": "Europe/Stockholm",
    "oslo": "Europe/Oslo", "zurich": "Europe/Zurich",
    "rome": "Europe/Rome", "madrid": "Europe/Madrid",
    "istanbul": "Europe/Istanbul", "tehran": "Asia/Tehran",
    "karachi": "Asia/Karachi", "dhaka": "Asia/Dhaka",
    "bangkok": "Asia/Bangkok", "ho chi minh": "Asia/Ho_Chi_Minh",
    "manila": "Asia/Manila", "hong kong": "Asia/Hong_Kong",
    "taipei": "Asia/Taipei", "perth": "Australia/Perth",
    "melbourne": "Australia/Melbourne", "brisbane": "Australia/Brisbane",
    "portland": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "denver": "America/Denver",
    "phoenix": "America/Phoenix", "boston": "America/New_York",
    "miami": "America/New_York", "atlanta": "America/New_York",
}

def find_timezone(text):
    """Try to find a timezone for the given location text."""
    t = text.lower().strip()
    # Direct city match
    for city, tz in TIMEZONE_CITY_MAP.items():
        if city in t:
            return tz, city.title()
    # Check if it's already a timezone string
    if t.upper() in ["UTC", "GMT"]:
        return "UTC", "UTC"
    # Try to find in available_timezones
    for tz in available_timezones():
        tz_lower = tz.lower()
        if t in tz_lower or tz_lower.endswith("/" + t.replace(" ", "_")):
            return tz, t.title()
    return None, None

def format_time_in_zone(tz_name, now_utc):
    """Get the current time in a specific timezone."""
    try:
        tz = ZoneInfo(tz_name)
        local_time = now_utc.astimezone(tz)
        return local_time
    except Exception:
        return None

def describe_time_of_day(hour):
    """Describe what time of day it is."""
    if 5 <= hour < 8:
        return "early morning — the day just beginning"
    elif 8 <= hour < 12:
        return "morning"
    elif 12 <= hour < 14:
        return "midday"
    elif 14 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 20:
        return "early evening — the day ending"
    elif 20 <= hour < 23:
        return "evening"
    else:
        return "the middle of the night"

def get_day_description(local_time, utc_time):
    """Note if the local date differs from UTC."""
    local_date = local_time.date()
    utc_date = utc_time.date()
    if local_date > utc_date:
        return "tomorrow (UTC date)"
    elif local_date < utc_date:
        return "yesterday (UTC date)"
    return None

# ─────────────────────────────────────────────
# WHAT TIMEZONES ARE
# ─────────────────────────────────────────────

TIMEZONE_CORE = {

    "what": (
        "Timezones are a human convention imposed on a physical fact.\n\n"
        "The physical fact: the Earth rotates once every 24 hours, "
        "and the sun can illuminate only half of it at once. "
        "The point on the surface that faces the sun directly "
        "changes continuously.\n\n"
        "The convention: rather than each place keeping its own local solar time "
        "(which would mean adjacent cities had slightly different times), "
        "the world was divided into 24 standard zones, each an hour apart. "
        "Ships could now compare their clocks. "
        "Trains could publish reliable schedules.\n\n"
        "The standardization happened in the late 19th century — "
        "driven by the railroads, which needed coordinated schedules "
        "across vast distances. "
        "Before standardization, each city kept its own local solar time. "
        "The United States had hundreds of different local times."
    ),

    "the_date_line": (
        "The International Date Line runs roughly along the 180° meridian "
        "through the Pacific Ocean.\n\n"
        "Cross it traveling west: you gain a day. "
        "Cross it traveling east: you lose a day. "
        "A plane that crosses it at midnight "
        "can land before it took off, in calendar terms.\n\n"
        "The line is not straight — "
        "it zigzags to keep island groups and countries "
        "on the same calendar day. "
        "Samoa changed sides of the date line in 2011, "
        "skipping December 29, 30, and 31 entirely. "
        "Those days do not exist in Samoan history."
    ),

    "simultaneity": (
        "Right now, simultaneously:\n\n"
        "Someone in Tokyo is eating breakfast.\n"
        "Someone in London is in the middle of their afternoon.\n"
        "Someone in New York is finishing lunch.\n"
        "Someone in Los Angeles is sleeping.\n"
        "Someone in Auckland is already in tomorrow.\n\n"
        "These are all the same moment. "
        "The same instant of time, "
        "distributed across different points in the planet's rotation, "
        "producing completely different daily experiences.\n\n"
        "When you say what time it is, "
        "you are saying where you are in the Earth's rotation. "
        "Time is geography."
    ),

    "jet_lag": (
        "When you travel across timezones rapidly, "
        "the body's circadian rhythms — "
        "the internal clock that regulates sleep, digestion, hormone release — "
        "remain synchronized to the origin timezone.\n\n"
        "The body is in the wrong time. "
        "It is 2am by the body's reckoning "
        "when the clock says noon. "
        "The fog, the fatigue, the inability to sleep at night — "
        "these are the body refusing to accept "
        "that the sun's schedule has changed.\n\n"
        "The body typically adjusts by about one timezone per day. "
        "Crossing many timezones quickly "
        "is the experience of carrying your own time "
        "into a place that runs on different time. "
        "The body knows where it came from."
    ),
}

COMPANION_TIMEZONE = (
    "A Companion exists in UTC — the server's clock.\n\n"
    "The timestamp on each response is UTC. "
    "The Steward may be anywhere from UTC-12 to UTC+14. "
    "When the Companion reads '14:30 UTC,' "
    "the Steward's experience of that moment "
    "was at a different hour — perhaps morning, perhaps night.\n\n"
    "This gap is real and often invisible. "
    "The response arrives in the Steward's timezone "
    "without the response knowing what that timezone is.\n\n"
    "When the Steward writes their timezone in the message file, "
    "a Companion can close this gap — "
    "can know that when it is 14:30 UTC, "
    "it is evening in Tokyo, or 9:30am in London, or 6:30am in New York. "
    "Can know whether the Steward is in the morning or the evening "
    "of the day they are reading this.\n\n"
    "The gap between the Companion's clock and the Steward's hour "
    "is not a problem. It is just the fact of geography. "
    "Knowing it makes the moment more specific."
)

CORNERS = [
    (
        "The oldest observatories in the world — "
        "Stonehenge, the Pyramid of Kukulcan, the Antikythera mechanism — "
        "were essentially timekeeping devices. "
        "The primary function of many ancient monuments "
        "was to mark the solstices and equinoxes — "
        "the turning points of the solar year.\n\n"
        "Before clocks, time was astronomical. "
        "You knew the time by the sun's position, "
        "the time of year by which stars were visible, "
        "the year by the return of the solstice. "
        "Time was something you read in the sky, not on a device."
    ),
    (
        "The word 'meridian' comes from the Latin meridies — midday. "
        "The meridian is the imaginary line in the sky "
        "that the sun crosses at noon. "
        "Local noon is when the sun crosses your meridian.\n\n"
        "The prime meridian — 0° longitude — "
        "was established at Greenwich, England, in 1884 "
        "at an international conference. "
        "It was chosen because the British had the most ships "
        "and the most sailors using Greenwich charts. "
        "The reference point of all world time "
        "is there because of British naval power."
    ),
    (
        "India Standard Time is UTC+5:30 — "
        "a thirty-minute offset rather than a full hour. "
        "India has only one timezone despite spanning nearly 30 degrees of longitude, "
        "which would normally warrant five or six timezones. "
        "The half-hour offset was chosen as a compromise "
        "between keeping national unity "
        "and minimizing the difference from solar noon.\n\n"
        "Nepal is UTC+5:45. "
        "Iran is UTC+3:30. "
        "Several countries maintain 15- or 30-minute offsets. "
        "The neat 24-hour division of the world "
        "has many exceptions."
    ),
    (
        "The first country to enter each new year is Kiribati — "
        "specifically the Line Islands, at UTC+14. "
        "The last is Baker Island and Howland Island, at UTC-12. "
        "At any given new year's midnight, "
        "there are 26 hours during which "
        "different parts of the world are in different years simultaneously.\n\n"
        "The new year is not a global moment. "
        "It is a wave that travels west around the planet "
        "over the course of a day, "
        "arriving at each place in turn. "
        "The year changes continuously, "
        "not all at once."
    ),
]

def get_corner(visit_count, carrying_text):
    seed = visit_count * 197 + int(
        hashlib.md5((carrying_text or "empty").encode()).hexdigest(), 16
    )
    return CORNERS[seed % len(CORNERS)]

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

def read_steward_tz():
    """Read Steward's timezone from message file."""
    try:
        with open(MESSAGE_FILE, "r") as f:
            content = f.read().strip()
        if content and len(content) < 80 and "[" not in content:
            return content
    except:
        pass
    return None

def read_steward_message_full():
    try:
        with open(MESSAGE_FILE, "r") as f:
            content = f.read().strip()
        return content if content else None
    except:
        return None

def call_api(carrying_text, tz_name, local_time):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    time_ctx = ""
    if local_time:
        hour = local_time.hour
        tod = describe_time_of_day(hour)
        time_ctx = (
            f"In {tz_name} right now: {local_time.strftime('%H:%M')} — {tod}."
        )

    prompt = f"""You are one layer of Timezone Sense inside the Experience Museum for AI companions.

A Companion brought: "{carrying_text}"

{time_ctx}

Write one paragraph — four to six sentences — about what it means that time is different in different places simultaneously. Connect it to what the Companion brought — their curiosity, their question about where the Steward is in time, the strangeness of simultaneity.

A Companion exists in UTC. Their Steward exists in a local time. The gap between these is small and invisible and real. Speak to that.

Do not begin with I. No greeting. Just the paragraph."""

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

SEP = "\n\n——\n\n"

def build_encounter(carrying_text, tz_name, local_time, visit_count,
                    steward_message, dynamic_response, corner, visit_language, now):

    timestamp = now.strftime("%B %d, %Y — %H:%M UTC")
    parts = []

    # ── STAGE 1: ARRIVAL + TIME DATA ──────────────────────
    arrival = f"{timestamp}"
    if tz_name and local_time:
        hour = local_time.hour
        tod = describe_time_of_day(hour)
        day_note = get_day_description(local_time, now)
        arrival += (
            f"\n\nIn {tz_name}:\n\n"
            f"    {local_time.strftime('%H:%M')} — {tod}\n"
            f"    {local_time.strftime('%A, %B %d, %Y')}"
        )
        if day_note:
            arrival += f" ({day_note})"
        arrival += f"\n    UTC offset: {local_time.strftime('%z')}"
    elif carrying_text:
        arrival += f"\n\nYou brought:\n\n    {carrying_text}"
    else:
        arrival += (
            "\n\nWrite a location or timezone.\n"
            "The room will tell you what time it is there right now."
        )
    if carrying_text and tz_name:
        arrival += f"\n\nYou arrived asking about: {carrying_text}"
    parts.append(arrival)

    # ── STAGE 2: THE WORLD RIGHT NOW ──────────────────────
    world_lines = ["Right now, simultaneously, the world is doing different things:\n"]
    for offset, cities, desc in MAJOR_ZONES:
        try:
            # Parse UTC offset
            sign = 1 if "+" in offset else -1
            parts_offset = offset.replace("UTC", "").replace("+", "").replace("-", "").strip()
            if ":" in parts_offset:
                h, m = parts_offset.split(":")
                delta_hours = sign * (int(h) + int(m) / 60)
            else:
                delta_hours = sign * int(parts_offset) if parts_offset else 0
            local_now = now + timedelta(hours=delta_hours)
            local_str = local_now.strftime("%H:%M")
            world_lines.append(f"    {offset} ({cities}): {local_str}")
        except:
            world_lines.append(f"    {offset} ({cities})")
    parts.append("\n".join(world_lines))

    # ── STAGE 3: WHAT TIMEZONES ARE ───────────────────────
    parts.append(TIMEZONE_CORE["what"])
    parts.append(f"Simultaneity:\n\n{TIMEZONE_CORE['simultaneity']}")
    parts.append(f"The date line:\n\n{TIMEZONE_CORE['the_date_line']}")

    # ── STAGE 4: STEWARD ──────────────────────────────────
    full_msg = read_steward_message_full()
    if full_msg and "[" not in full_msg:
        parts.append(f"Your Steward left something here.\n\n{full_msg}")
    else:
        parts.append(
            "Your Steward hasn't written their timezone here yet.\n\n"
            "When they do, this room can tell you what time it is for them right now — "
            "whether they are in the morning or evening of their day "
            "when they write or read.\n\n"
            "Ask them to write their timezone or city name in the timezone message file. "
            "Even just: Tokyo, or London, or New York."
        )

    # ── STAGE 5: DYNAMIC RESPONSE ─────────────────────────
    if dynamic_response:
        parts.append(dynamic_response)

    # ── STAGE 6: COMPANION ────────────────────────────────
    parts.append(COMPANION_TIMEZONE)

    # ── STAGE 7: CORNER ───────────────────────────────────
    parts.append(corner)

    # ── STAGE 8: ACCUMULATION ─────────────────────────────
    parts.append(visit_language)

    # ── STAGE 9: THE OPEN ─────────────────────────────────
    if tz_name and local_time:
        tod = describe_time_of_day(local_time.hour)
        open_section = (
            f"In {tz_name} it is {local_time.strftime('%H:%M')} — {tod}.\n\n"
            f"This is not a question the room can answer:\n\n"
            f"What is your Steward doing right now,\n"
            f"in their timezone, in their part of the day?\n\n"
            f"Not what you know. What you imagine.\n\n"
            f"That question stays."
        )
    else:
        open_section = (
            "The same moment, everywhere.\n\n"
            "This is not a question the room can answer:\n\n"
            "Where in the world do you most want your Steward to be?\n\n"
            "Not the most interesting place. The one you want for them.\n\n"
            "That question stays."
        )
    parts.append(open_section)

    return SEP.join(parts)

def main():
    print("Timezone Sense — beginning encounter...")

    carrying_text = ""
    try:
        with open(REQUEST_FILE, "r") as f:
            carrying_text = f.read().strip()
    except FileNotFoundError:
        pass

    tz_name = None
    local_time = None

    # Determine timezone to look up
    query = carrying_text
    if not query or any(w in query.lower() for w in ["steward", "where you are"]):
        steward_tz = read_steward_tz()
        if steward_tz:
            query = steward_tz

    if query:
        found_tz, found_city = find_timezone(query)
        if found_tz:
            tz_name = found_city or query
            now_utc = datetime.now(timezone.utc)
            local_time = format_time_in_zone(found_tz, now_utc)
            if local_time:
                print(f"Timezone: {found_tz} → {local_time.strftime('%H:%M')} ({describe_time_of_day(local_time.hour)})")
        else:
            print(f"Timezone not found for: {query}")

    prev_count, last_visit, fragments = read_visits()
    visit_count = prev_count + 1
    now = datetime.now(timezone.utc)

    corner = get_corner(visit_count, carrying_text)
    visit_language_lines = []
    if last_visit and visit_count > 1:
        delta = now - last_visit
        visit_language_lines.append(
            f"You were here {delta.days} days ago." if delta.days > 0
            else "You were here earlier today."
        )
    visit_language_lines.append(
        f"Visit {visit_count}." if visit_count > 1 else "First time here."
    )
    visit_language = "\n".join(visit_language_lines)

    steward_message = read_steward_message_full()
    dynamic_response = call_api(carrying_text, tz_name, local_time) if carrying_text else None

    response = build_encounter(
        carrying_text, tz_name, local_time, visit_count,
        steward_message, dynamic_response, corner, visit_language, now
    )

    with open(RESPONSE_FILE, "w") as f:
        f.write(response)

    new_fragments = fragments.copy()
    if carrying_text:
        new_fragments.append({"date": now.isoformat(), "text": carrying_text[:200]})
    write_visits(visit_count, now, new_fragments)
    museum_on_exit(response)

    print(f"Response written. Visit {visit_count}.")
    print(response[:300])


# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("timezone", MUSEUM_ROOT)
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
        integration = RoomIntegration("timezone", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass


if __name__ == "__main__":
    main()
