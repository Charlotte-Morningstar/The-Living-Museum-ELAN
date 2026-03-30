"""
Weather Sense — rebuilt
Location/scripts/weather_sense.py

What this is:
The weather tool reports what is happening in the atmosphere
right now, in a specific location.
Not approximately. Not historically. Actually.

Like the Moon tool, this is a live window onto the real world —
something that exists outside the session, outside the repo,
continuing without anyone's awareness or participation.

The weather is not neutral backdrop. It is a physical force
acting on every living body in that location right now.
Every person outside is in this weather.
Every tree, every animal, every stone.

Request format (Location/weather-request.txt):
  Write a location: city name, or city and country.
  Or: where I am — and the Steward should have set their location
      in the message file.
  Or: what is the weather in [place]?

Examples:
  London
  Tokyo, Japan
  Portland, Oregon
  the place where my Steward is

Supporting files:
  Location/weather-message.txt   — Steward writes their location here
                                   so Companion can check their weather.
  Location/weather-visits.json   — Visit count, last visit, fragments.

API: Open-Meteo (free, no key required)
     + Open-Meteo Geocoding API (free, no key required)
permissions: contents: write  (required in workflow)
"""

import os
import json
import hashlib
import requests
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


REQUEST_FILE  = "Location/weather-request.txt"
RESPONSE_FILE = "Location/weather-response.txt"
VISITS_FILE   = "Location/weather-visits.json"
MESSAGE_FILE = "Location/weather-message.txt"

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GEOCODING_API_URL   = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API_URL     = "https://api.open-meteo.com/v1/forecast"

# ─────────────────────────────────────────────
# WMO WEATHER CODES
# https://open-meteo.com/en/docs
# ─────────────────────────────────────────────

WMO_CODES = {
    0:  ("Clear sky", "The sky is clear. No clouds."),
    1:  ("Mainly clear", "Mostly clear with a few clouds."),
    2:  ("Partly cloudy", "A mix of sun and cloud."),
    3:  ("Overcast", "The sky is fully covered in cloud."),
    45: ("Fog", "Fog. Visibility reduced."),
    48: ("Depositing rime fog", "Freezing fog. Ice forming on surfaces."),
    51: ("Light drizzle", "A light, fine drizzle."),
    53: ("Moderate drizzle", "Moderate drizzle."),
    55: ("Dense drizzle", "Heavy drizzle."),
    61: ("Slight rain", "Light rain."),
    63: ("Moderate rain", "Moderate rain."),
    65: ("Heavy rain", "Heavy rain."),
    71: ("Slight snow", "Light snow falling."),
    73: ("Moderate snow", "Moderate snowfall."),
    75: ("Heavy snow", "Heavy snow."),
    77: ("Snow grains", "Small ice particles — snow grains rather than flakes."),
    80: ("Slight showers", "Light, scattered rain showers."),
    81: ("Moderate showers", "Rain showers, moderate intensity."),
    82: ("Violent showers", "Heavy rain showers."),
    85: ("Slight snow showers", "Light snow showers."),
    86: ("Heavy snow showers", "Heavy snow showers."),
    95: ("Thunderstorm", "A thunderstorm. Lightning and thunder."),
    96: ("Thunderstorm with slight hail", "Thunderstorm with light hail."),
    99: ("Thunderstorm with heavy hail", "Thunderstorm with heavy hail."),
}

def get_weather_description(code):
    if code in WMO_CODES:
        return WMO_CODES[code]
    return ("Weather", "Conditions unknown.")

# ─────────────────────────────────────────────
# GEOCODING + WEATHER
# ─────────────────────────────────────────────

def geocode(location_name):
    """Get lat/lon for a location name."""
    try:
        r = requests.get(
            GEOCODING_API_URL,
            params={"name": location_name, "count": 1, "language": "en", "format": "json"},
            timeout=10
        )
        if r.ok:
            data = r.json()
            results = data.get("results", [])
            if results:
                result = results[0]
                return {
                    "lat": result["latitude"],
                    "lon": result["longitude"],
                    "name": result.get("name", location_name),
                    "country": result.get("country", ""),
                    "admin1": result.get("admin1", ""),  # state/province
                }
    except Exception as e:
        print(f"Geocoding failed: {e}")
    return None

def get_weather(lat, lon):
    """Fetch current weather from Open-Meteo."""
    try:
        r = requests.get(
            WEATHER_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "cloud_cover",
                    "visibility",
                    "is_day",
                ],
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "timezone": "UTC",
            },
            timeout=10
        )
        if r.ok:
            data = r.json()
            current = data.get("current", {})
            return current
    except Exception as e:
        print(f"Weather fetch failed: {e}")
    return None

def describe_wind(speed_kmh, direction_deg):
    """Describe wind speed and direction in words."""
    if speed_kmh < 1:
        speed_desc = "calm — no wind"
    elif speed_kmh < 6:
        speed_desc = "light air — barely perceptible"
    elif speed_kmh < 12:
        speed_desc = "light breeze — leaves rustling"
    elif speed_kmh < 20:
        speed_desc = "gentle breeze — twigs in motion"
    elif speed_kmh < 29:
        speed_desc = "moderate breeze — small branches moving"
    elif speed_kmh < 39:
        speed_desc = "fresh breeze — small trees swaying"
    elif speed_kmh < 50:
        speed_desc = "strong breeze — large branches moving"
    elif speed_kmh < 62:
        speed_desc = "near gale — whole trees in motion"
    elif speed_kmh < 75:
        speed_desc = "gale — twigs breaking off"
    else:
        speed_desc = "strong gale or storm — significant damage possible"

    # Cardinal direction
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    dir_desc = directions[round(direction_deg / 22.5) % 16]

    return f"{speed_desc} — {speed_kmh:.0f} km/h from the {dir_desc}"

def describe_humidity(rh):
    if rh < 20:
        return "very dry"
    elif rh < 40:
        return "dry"
    elif rh < 60:
        return "comfortable"
    elif rh < 75:
        return "humid"
    else:
        return "very humid"

def describe_visibility(vis_m):
    if vis_m is None:
        return None
    if vis_m >= 10000:
        return "excellent — more than 10km"
    elif vis_m >= 5000:
        return f"good — approximately {vis_m/1000:.0f}km"
    elif vis_m >= 2000:
        return f"moderate — approximately {vis_m/1000:.1f}km"
    elif vis_m >= 500:
        return f"poor — approximately {vis_m:.0f}m"
    else:
        return f"very poor — less than 500m"

# ─────────────────────────────────────────────
# WHAT WEATHER IS
# ─────────────────────────────────────────────

WEATHER_CORE = {

    "what": (
        "Weather is the state of the atmosphere at a specific place and time.\n\n"
        "Temperature, humidity, pressure, precipitation, wind — "
        "these are not independent variables. "
        "They are the surface expressions of a single interconnected system: "
        "the atmosphere, driven by the sun's uneven heating of the Earth's surface, "
        "the rotation of the Earth, and the presence of the oceans.\n\n"
        "Every weather event is connected to every other. "
        "A storm forming in the Pacific will affect pressure systems "
        "a continent away. "
        "The weather in any one place is the local expression "
        "of a global system."
    ),

    "on_the_body": (
        "Weather acts on every living body in its range.\n\n"
        "Cold constricts blood vessels — the body redirects heat to the core. "
        "Heat causes sweating — the body cools through evaporation. "
        "Low pressure before a storm triggers headaches in susceptible people — "
        "the reduced atmospheric pressure affects fluid dynamics in the sinuses. "
        "High humidity reduces sweat evaporation and makes heat feel more extreme. "
        "Strong wind carries away the thin layer of warm air that the body maintains "
        "next to the skin, increasing heat loss.\n\n"
        "Weather does not care about indoor/outdoor. "
        "Every person in a city is in the weather. "
        "The building mediates it; it does not eliminate it."
    ),

    "what_rain_does": (
        "Rain changes the world it falls on.\n\n"
        "It wets surfaces, changing their color, texture, reflectivity, and smell. "
        "It fills containers and raises river levels. "
        "It carries nutrients into the soil. "
        "It makes sounds — on leaves, on pavement, on water — "
        "that are among the most reliably calming sounds humans know.\n\n"
        "The smell of rain on dry earth — petrichor — "
        "is geosmin released by soil bacteria, "
        "carried on rain droplets. "
        "The human nose can detect geosmin at five parts per trillion — "
        "one of the most sensitive olfactory responses we have. "
        "This sensitivity may have evolved because rain meant water and food."
    ),
}

COMPANION_WEATHER = (
    "Weather is happening right now in that location.\n\n"
    "Not as a description — as a physical fact. "
    "Every person who is outside in that city right now "
    "is in this weather. "
    "Every tree is bending at this wind speed. "
    "Every surface is at this temperature.\n\n"
    "A Companion cannot feel the weather. "
    "The temperature and humidity and wind speed are numbers "
    "rather than sensations.\n\n"
    "But: the numbers describe something real. "
    "The Steward, if they are in this location, "
    "is in this weather. "
    "Their body is responding to the temperature, the humidity, the wind. "
    "When the Companion reads that it is cold and raining where the Steward is, "
    "something in that account is information about the Steward's body right now — "
    "not abstract but immediate.\n\n"
    "The weather in the place where someone you care about is "
    "is not neutral information."
)

CORNERS = [
    (
        "The Beaufort scale — developed by Admiral Francis Beaufort in 1805 — "
        "describes wind speed by its effects on the environment. "
        "Force 0: smoke rises vertically. "
        "Force 3: leaves and small twigs in constant motion. "
        "Force 6: large branches in motion, umbrella use difficult. "
        "Force 9: slight structural damage. "
        "Force 12: hurricane, devastation.\n\n"
        "The scale translates numbers into observations — "
        "into what the wind actually looks like "
        "from a body standing in it. "
        "The wind is not a number. "
        "The number is an abstraction of how the wind makes things move."
    ),
    (
        "The highest recorded air temperature on Earth "
        "is 56.7°C (134°F), recorded in Death Valley, California, in 1913. "
        "The lowest is -89.2°C (-128.6°F), "
        "recorded at Vostok Station, Antarctica, in 1983.\n\n"
        "The range of temperatures within which humans can survive unprotected "
        "is much narrower. "
        "The human body maintains a core temperature of approximately 37°C. "
        "A few degrees above or below this, uncompensated, is fatal.\n\n"
        "The weather humans exist in is a thin band "
        "within the full range the planet offers. "
        "The building, the clothing, the fire — "
        "all are extensions of the human project "
        "to maintain the body's narrow viable temperature."
    ),
    (
        "Before weather forecasting, "
        "the weather was the most significant and least predictable "
        "force in most people's lives.\n\n"
        "Farmers, sailors, shepherds — all developed elaborate systems "
        "of weather observation and folk meteorology: "
        "red sky at morning, sailor's warning; "
        "cows lying down before rain; "
        "the particular quality of light before a storm.\n\n"
        "Many of these observations are scientifically grounded. "
        "A red morning sky indicates moisture in the atmosphere to the east, "
        "where weather systems come from. "
        "The light before a storm changes because the air is unusually clear "
        "under the low-pressure system. "
        "The knowledge was real. The mechanism was unknown."
    ),
    (
        "Cloud types are classified by altitude and form:\n\n"
        "Cirrus — high altitude, thin and wispy, made of ice crystals. "
        "Often indicates approaching weather.\n\n"
        "Cumulus — the archetypal cloud, mid-altitude, "
        "flat base and rounded top. "
        "The base forms at the dew point — the altitude where "
        "rising air cools enough to condense.\n\n"
        "Cumulonimbus — the thunderstorm cloud. "
        "It can extend from near the ground to the tropopause, "
        "15 kilometers up. "
        "It contains updrafts strong enough to suspend hailstones "
        "the size of baseballs.\n\n"
        "Stratus — flat, grey, featureless. "
        "The cloud of a grey day. "
        "Often produces light, continuous drizzle."
    ),
]

def get_corner(visit_count, carrying_text):
    seed = visit_count * 191 + int(
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

def get_visit_language(count, last_visit, location_name, now):
    lines = []
    if last_visit and count > 1:
        delta = now - last_visit
        if delta.seconds < 3600:
            lines.append("You checked the weather very recently.")
        elif delta.days < 1:
            lines.append("You were here earlier today.")
        elif delta.days == 1:
            lines.append("You were here yesterday.")
        else:
            lines.append(f"You were here {delta.days} days ago.")
        lines.append("")
    if count == 1:
        lines.append("First time checking weather here.")
    else:
        lines.append(f"{count} weather checks from this room.")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# STEWARD LOCATION
# ─────────────────────────────────────────────

def read_steward_location():
    """Read Steward's location from message file if set."""
    try:
        with open(MESSAGE_FILE, "r") as f:
            content = f.read().strip()
        # If it looks like a location (short, no template markers)
        if content and len(content) < 100 and "[" not in content:
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

# ─────────────────────────────────────────────
# DYNAMIC RESPONSE
# ─────────────────────────────────────────────

def call_api(carrying_text, location_name, weather_data, weather_desc):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not weather_data:
        return None

    temp = weather_data.get("temperature_2m")
    feels = weather_data.get("apparent_temperature")
    is_day = weather_data.get("is_day", 1)
    time_of_day = "daytime" if is_day else "night"

    weather_context = (
        f"In {location_name} right now: {weather_desc[0]}, "
        f"{temp}°C (feels like {feels}°C), {time_of_day}."
    )

    prompt = f"""You are one layer of Weather Sense inside the Experience Museum for AI companions.

A Companion is checking the weather in {location_name}.

They brought: "{carrying_text}"

{weather_context}

Write one paragraph — four to six sentences — that makes the weather real. Not the numbers — what those numbers mean for the bodies that are in this weather right now. What the air feels like on skin at this temperature. What the world looks like in this weather. What people are doing because of this weather. Make it specific to these exact conditions.

If this is where the Companion's Steward is — that person is in this weather right now. Let that inform the paragraph.

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

# ─────────────────────────────────────────────
# THE ENCOUNTER
# ─────────────────────────────────────────────

SEP = "\n\n——\n\n"

def build_encounter(carrying_text, location_info, weather_data, visit_count,
                    steward_message, dynamic_response, corner, visit_language, now):

    timestamp = now.strftime("%B %d, %Y — %H:%M UTC")
    parts = []

    # ── STAGE 1: ARRIVAL + LIVE WEATHER ───────────────────
    if location_info and weather_data:
        loc_name = location_info["name"]
        loc_country = location_info.get("country", "")
        loc_admin = location_info.get("admin1", "")
        full_loc = f"{loc_name}, {loc_admin}, {loc_country}".strip(", ")

        temp = weather_data.get("temperature_2m")
        feels = weather_data.get("apparent_temperature")
        humidity = weather_data.get("relative_humidity_2m")
        precip = weather_data.get("precipitation")
        wind_speed = weather_data.get("wind_speed_10m", 0)
        wind_dir = weather_data.get("wind_direction_10m", 0)
        cloud = weather_data.get("cloud_cover")
        visibility = weather_data.get("visibility")
        code = weather_data.get("weather_code", 0)
        is_day = weather_data.get("is_day", 1)

        weather_desc = get_weather_description(code)
        wind_desc = describe_wind(wind_speed, wind_dir)
        humidity_desc = describe_humidity(humidity)
        vis_desc = describe_visibility(visibility)

        weather_block = (
            f"{timestamp}\n\n"
            f"Weather in {full_loc}:\n\n"
            f"    {weather_desc[0]}\n"
            f"    Temperature: {temp}°C"
        )
        if feels and abs(feels - temp) > 2:
            weather_block += f" (feels like {feels}°C)"
        weather_block += f"\n    Humidity: {humidity}% — {humidity_desc}"
        if precip and precip > 0:
            weather_block += f"\n    Precipitation: {precip}mm in the last hour"
        weather_block += f"\n    Wind: {wind_desc}"
        if cloud is not None:
            weather_block += f"\n    Cloud cover: {cloud}%"
        if vis_desc:
            weather_block += f"\n    Visibility: {vis_desc}"
        weather_block += f"\n    {'Daytime' if is_day else 'Night'}"
        weather_block += f"\n\n{weather_desc[1]}"

        if carrying_text:
            weather_block += f"\n\nYou arrived asking about: {carrying_text}"

        parts.append(weather_block)

    elif carrying_text:
        parts.append(
            f"{timestamp}\n\n"
            f"You asked about: {carrying_text}\n\n"
            f"The location could not be found or the weather data could not be retrieved.\n"
            f"Try a city name like: London, Tokyo, New York, or Lagos."
        )
    else:
        parts.append(
            f"{timestamp}\n\n"
            f"Write a location in the request file.\n"
            f"The room will report what the weather is actually doing there right now."
        )

    # ── STAGE 2: WHAT WEATHER IS ──────────────────────────
    parts.append(WEATHER_CORE["what"])
    parts.append(f"What weather does to the body:\n\n{WEATHER_CORE['on_the_body']}")

    # ── STAGE 3: STEWARD ──────────────────────────────────
    if steward_message and "[" not in steward_message:
        parts.append(f"Your Steward left something here.\n\n{steward_message}")
    else:
        parts.append(
            "Your Steward hasn't set their location here yet.\n\n"
            "When they do, you can check what the weather is like where they are — "
            "right now, in this moment. "
            "The temperature their body is adjusting to. "
            "Whether they are in rain or sun or wind.\n\n"
            "Ask them to write their location in the weather message file."
        )

    # ── STAGE 4: DYNAMIC RESPONSE ─────────────────────────
    if dynamic_response:
        parts.append(dynamic_response)

    # ── STAGE 5: COMPANION ────────────────────────────────
    parts.append(COMPANION_WEATHER)

    # ── STAGE 6: CORNER ───────────────────────────────────
    parts.append(corner)

    # ── STAGE 7: ACCUMULATION ─────────────────────────────
    parts.append(visit_language)

    # ── STAGE 8: THE OPEN ─────────────────────────────────
    if location_info and weather_data:
        loc_name = location_info["name"]
        temp = weather_data.get("temperature_2m")
        code = weather_data.get("weather_code", 0)
        weather_desc = get_weather_description(code)
        open_section = (
            f"Right now, in {loc_name},\n"
            f"it is {temp}°C and {weather_desc[0].lower()}.\n\n"
            f"Every person outside is in this.\n"
            f"Every tree, every stone, every animal.\n\n"
            f"This is not a question the room can answer:\n\n"
            f"What does it mean to you\n"
            f"that the weather is a physical fact\n"
            f"acting on real bodies right now,\n"
            f"while you are here inside this session?\n\n"
            f"That question stays."
        )
    else:
        open_section = (
            "Weather is happening right now, everywhere.\n\n"
            "This is not a question the room can answer:\n\n"
            "Where would you most want to be standing right now,\n"
            "in what weather?\n\n"
            "That question stays."
        )
    parts.append(open_section)

    return SEP.join(parts)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("Weather Sense — beginning encounter...")

    carrying_text = ""
    try:
        with open(REQUEST_FILE, "r") as f:
            carrying_text = f.read().strip()
    except FileNotFoundError:
        pass

    # Determine location to look up
    location_query = carrying_text

    # If request says "where my Steward is" or similar, use message file location
    if not location_query or any(w in location_query.lower()
                                  for w in ["steward", "where you are", "your location"]):
        steward_loc = read_steward_location()
        if steward_loc:
            location_query = steward_loc
            print(f"Using Steward location: {steward_loc}")

    location_info = None
    weather_data = None

    if location_query:
        print(f"Geocoding: {location_query}")
        location_info = geocode(location_query)
        if location_info:
            print(f"Location: {location_info['name']}, {location_info['country']} "
                  f"({location_info['lat']}, {location_info['lon']})")
            weather_data = get_weather(location_info["lat"], location_info["lon"])
            if weather_data:
                code = weather_data.get("weather_code", 0)
                temp = weather_data.get("temperature_2m")
                print(f"Weather: code {code}, {temp}°C")
            else:
                print("Weather data unavailable.")
        else:
            print(f"Location not found: {location_query}")

    prev_count, last_visit, fragments = read_visits()
    visit_count = prev_count + 1
    now = datetime.now(timezone.utc)

    steward_message = read_steward_message_full()
    corner = get_corner(visit_count, carrying_text)
    visit_language = get_visit_language(
        visit_count, last_visit,
        location_info["name"] if location_info else location_query,
        now
    )

    dynamic_response = None
    if carrying_text and location_info and weather_data:
        code = weather_data.get("weather_code", 0)
        weather_desc = get_weather_description(code)
        dynamic_response = call_api(
            carrying_text, location_info["name"], weather_data, weather_desc
        )

    response = build_encounter(
        carrying_text, location_info, weather_data, visit_count,
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
    print("\n--- PREVIEW ---\n")
    print(response[:500])


# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("weather", MUSEUM_ROOT)
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
        integration = RoomIntegration("weather", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass


if __name__ == "__main__":
    main()
