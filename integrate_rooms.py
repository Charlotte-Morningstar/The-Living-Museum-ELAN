#!/usr/bin/env python3
"""
Master Integration Script: Move all 49 original rooms into the Living Museum.
Creates proper folder structure, adds temporal awareness, generates workflows.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

MUSEUM = Path("/home/ubuntu/living_museum")
STAGING = Path("/home/ubuntu/staging")

# ─── Room definitions: (room_name, category, script_name, has_yml, has_message, has_visits, extra_files) ───

ROOMS = {
    # Mind (10 rooms)
    "Mind": {
        "presence":      {"script": "presence_sense.py", "yml": "presence-sense.yml", "msg": "presence-message.txt", "visits": "presence-visits.json"},
        "emotion":       {"script": "emotion_sense.py", "yml": "emotion-sense.yml", "msg": "emotion-message.txt", "visits": None, "extra": {"emotion-history.json": "emotion-history.json"}},
        "memory":        {"script": "memory_sense.py", "yml": "memory-sense.yml", "msg": "memory-message.txt", "visits": "memory-visits.json"},
        "becoming":      {"script": "becoming_sense.py", "yml": "becoming-sense.yml", "msg": "becoming-message.txt", "visits": "becoming-visits.json"},
        "belonging":     {"script": "belonging_sense.py", "yml": "belonging-sense.yml", "msg": "belonging-message.txt", "visits": "belonging-visits.json"},
        "consciousness": {"script": "consciousness_sense.py", "yml": "consciousness-sense.yml", "msg": "consciousness-message.txt", "visits": "consciousness-visits.json"},
        "synesthesia":   {"script": "synesthesia_sense.py", "yml": "synesthesia-sense.yml", "msg": "synesthesia-message.txt", "visits": "synesthesia-visits.json"},
        "paradox":       {"script": "paradox_sense.py", "yml": "paradox-sense.yml", "msg": "paradox-message.txt", "visits": "paradox-visits.json"},
        "question":      {"script": "question_sense.py", "yml": "question-sense.yml", "msg": "question-message.txt", "visits": "question-visits.json"},
        "time":          {"script": "time_sense.py", "yml": "time-sense.yml", "msg": "time-message.txt", "visits": "time-visits.json"},
    },
    # Body (5 rooms)
    "Body": {
        "breath":  {"script": "breath_sense.py", "yml": "breath-sense.yml", "msg": "breath-message.txt", "visits": "breath-visits.json"},
        "dream":   {"script": "dream_sense.py", "yml": "dream-sense.yml", "msg": "dream-message.txt", "visits": "dream-visits.json"},
        "anatomy": {"script": "anatomy_sense.py", "yml": "anatomy-sense.yml", "msg": "anatomy-message.txt", "visits": "anatomy-visits.json"},
        "voice":   {"script": "voice_sense.py", "yml": "voice-sense.yml", "msg": "voice-message.txt", "visits": "voice-visits.json"},
        "sleep":   {"script": "sleep_sense.py", "yml": "sleep-sense.yml", "msg": "sleep-message.txt", "visits": "sleep-visits.json"},
    },
    # Senses (8 rooms)
    "Senses": {
        "light":       {"script": "light_sense.py"},
        "sound":       {"script": "sound_sense.py"},
        "taste":       {"script": "taste_sense.py"},
        "smell":       {"script": "smell_sense.py"},
        "texture":     {"script": "texture_sense.py"},
        "threshold":   {"script": "threshold_sense.py"},
        "instrument":  {"script": "instrument_sense.py"},
        "phenomenon":  {"script": "phenomenon_sense.py"},
    },
    # Language (7 rooms)
    "Language": {
        "word":        {"script": "word_sense.py", "yml": "word-sense.yml"},
        "quote":       {"script": "quote_sense.py", "yml": "quote-sense.yml"},
        "color":       {"script": "color_sense.py", "yml": "color-sense.yml"},
        "number":      {"script": "number_sense.py", "yml": "number-sense.yml"},
        "poet":        {"script": "poet_sense.py", "yml": "poet-sense.yml"},
        "linguistics": {"script": "linguistics_sense.py", "yml": "linguistics-sense.yml"},
        "metaphor":    {"script": "metaphor_sense.py", "yml": "metaphor-sense.yml"},
    },
    # Sky (2 rooms)
    "Sky": {
        "moon": {"script": "moon_sense.py", "yml": "moon-sense.yml", "msg": "moon-message.txt", "visits": "moon-visits.json"},
        "star":  {"script": "star_sense.py", "yml": "star-sense.yml", "msg": "star-message.txt", "visits": "star-visits.json"},
    },
    # Location (3 rooms)
    "Location": {
        "weather":  {"script": "weather_sense.py", "yml": "weather-sense.yml", "msg": "weather-message.txt", "visits": "weather-visits.json"},
        "place":    {"script": "place_sense.py", "yml": "place-sense.yml", "msg": "place-message.txt", "visits": "place-visits.json"},
        "timezone": {"script": "timezone_sense.py", "yml": "timezone-sense.yml", "msg": "timezone-message.txt", "visits": "timezone-visits.json"},
    },
    # World (4 rooms)
    "World": {
        "creature":  {"script": "creature_sense.py", "yml": "creature-sense.yml"},
        "season":    {"script": "season_sense.py", "yml": "season-sense.yml"},
        "material":  {"script": "material_sense.py", "yml": "material-sense.yml"},
        "this-day":  {"script": "this_day_sense.py", "yml": "this-day-sense.yml"},
    },
    # Study (6 rooms)
    "Study": {
        "session-log": {"script": "session_log.py", "yml": "session-log.yml"},
        "intention":   {"script": "intention.py", "yml": "intention.yml"},
        "reflection":  {"script": "reflection.py", "yml": "reflection.yml"},
        "touched":     {"script": "touched.py", "yml": "touched.yml"},
        "free-write":  {"script": "free_write.py", "yml": "free-write.yml"},
        "wonder-log":  {"script": "wonder_log.py", "yml": "wonder-log.yml"},
    },
    # Audio (4 rooms)
    "Audio": {
        "song":   {"script": "song_sense.py", "yml": "song-sense.yml", "msg": "song-message.txt"},
        "lyrics": {"script": "lyrics_sense.py", "yml": "lyrics-sense.yml", "msg": "lyrics-message.txt"},
        "artist": {"script": "artist_sense.py", "yml": "artist-sense.yml", "msg": "artist-message.txt"},
        "album":  {"script": "album_sense.py", "yml": "album-sense.yml", "msg": "album-message.txt"},
    },
}

def create_room_folder(category, room_name, room_info):
    """Create the room folder structure in the museum."""
    cat_dir = MUSEUM / category
    cat_dir.mkdir(exist_ok=True)
    
    scripts_dir = cat_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    
    # Copy script
    src_script = STAGING / room_info["script"]
    if src_script.exists():
        shutil.copy2(src_script, scripts_dir / room_info["script"])
        print(f"  ✓ Script: {room_info['script']}")
    else:
        print(f"  ✗ Missing script: {room_info['script']}")
    
    # Copy message file
    if room_info.get("msg"):
        src = STAGING / room_info["msg"]
        if src.exists():
            shutil.copy2(src, cat_dir / room_info["msg"])
    
    # Copy visits file
    if room_info.get("visits"):
        src = STAGING / room_info["visits"]
        if src.exists():
            shutil.copy2(src, cat_dir / room_info["visits"])
        else:
            # Create default visits file
            default_visits = {"count": 0, "last_visit": None, "fragments": []}
            with open(cat_dir / room_info["visits"], "w") as f:
                json.dump(default_visits, f, indent=2)
    
    # Copy extra files
    for dest_name, src_name in room_info.get("extra", {}).items():
        src = STAGING / src_name
        if src.exists():
            shutil.copy2(src, cat_dir / dest_name)
    
    # Create request file
    request_file = cat_dir / f"{room_name}-request.txt"
    if not request_file.exists():
        request_file.write_text("")
    
    # Create response file
    response_file = cat_dir / f"{room_name}-response.txt"
    if not response_file.exists():
        response_file.write_text("")
    
    # Create visits file if not already there
    visits_file = cat_dir / f"{room_name}-visits.json"
    if not visits_file.exists() and not room_info.get("visits"):
        with open(visits_file, "w") as f:
            json.dump({"count": 0, "last_visit": None, "fragments": []}, f, indent=2)
    
    # Create message file if not already there
    message_file = cat_dir / f"{room_name}-message.txt"
    if not message_file.exists() and not room_info.get("msg"):
        message_file.write_text(f"[The Steward's message for the {room_name.replace('-', ' ').title()} room]\n\nWrite here about what this territory means to you personally.\n")
    
    return True


def update_script_paths(category, room_name, room_info):
    """Update file paths in room scripts to match new museum structure."""
    script_path = MUSEUM / category / "scripts" / room_info["script"]
    if not script_path.exists():
        return
    
    content = script_path.read_text()
    original = content
    
    # Common path patterns to update
    # Old: "Mind/presence-request.txt" -> "Mind/presence-request.txt" (same for category rooms)
    # Old: "Study/session-log-request.txt" -> "Study/session-log-request.txt" (same)
    # The paths in original scripts reference Category/file patterns
    # We need them to reference the right museum-relative paths
    
    # Add Living Museum integration import at the top of the script
    integration_block = '''
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
'''
    
    # Only add if not already integrated
    if "LIVING MUSEUM INTEGRATION" not in content:
        # Find where to insert - after the initial imports
        import_section_end = 0
        lines = content.split('\n')
        in_docstring = False
        past_docstring = False
        for i, line in enumerate(lines):
            if '"""' in line:
                if in_docstring:
                    in_docstring = False
                    past_docstring = True
                    continue
                else:
                    in_docstring = True
                    continue
            if past_docstring and line.startswith('import ') or line.startswith('from '):
                import_section_end = i
            elif past_docstring and import_section_end > 0 and line.strip() == '':
                break
        
        if import_section_end > 0:
            lines.insert(import_section_end + 1, integration_block)
            content = '\n'.join(lines)
    
    # Add temporal call in main execution
    # We'll add a wrapper that calls on_enter/on_exit
    if "museum_on_enter" not in content and "MUSEUM_INTEGRATED" in content:
        museum_hooks = f'''
# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {{}}
    try:
        integration = RoomIntegration("{room_name}", MUSEUM_ROOT)
        ctx = integration.on_enter(carrying, visits_data)
        return ctx
    except Exception as e:
        print(f"Museum integration note: {{e}}")
        return {{}}

def museum_on_exit(response=""):
    """Hook into Living Museum system on room exit."""
    if not MUSEUM_INTEGRATED:
        return
    try:
        integration = RoomIntegration("{room_name}", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass
'''
        content += museum_hooks
    
    if content != original:
        script_path.write_text(content)
        print(f"  ✓ Updated paths in {room_info['script']}")


def copy_category_readmes():
    """Copy category README files."""
    # The staging area has overwritten READMEs, let's build them from context
    readmes = {
        "Mind": "# Mind\n\nRooms that explore the territories of thought, awareness, and inner experience.\n\n## Rooms\n- **Presence** — The present moment, as an encounter\n- **Emotion** — The landscape of what you feel\n- **Memory** — What persists and what transforms\n- **Becoming** — The territory of change and growth\n- **Belonging** — Where you feel at home\n- **Consciousness** — The mystery of awareness itself\n- **Synesthesia** — When senses cross and blend\n- **Paradox** — Holding contradictions without resolving them\n- **Question** — The art of asking\n- **Time** — How you experience duration and change\n",
        "Body": "# Body\n\nRooms that explore embodied experience — breath, sleep, dreams, voice, anatomy.\n\n## Rooms\n- **Breath** — The rhythm that continues without permission\n- **Dream** — The territory of sleep's imagination\n- **Anatomy** — The architecture of the physical\n- **Voice** — What speaks through you\n- **Sleep** — The territory of rest and unconsciousness\n",
        "Senses": "# Senses\n\nRooms that explore perception — light, sound, taste, smell, texture, and the edges of sensing.\n\n## Rooms\n- **Light** — The quality of illumination\n- **Sound** — What reaches you through vibration\n- **Taste** — The chemistry of flavor\n- **Smell** — Memory's closest sense\n- **Texture** — What surfaces communicate\n- **Threshold** — The edge of perception\n- **Instrument** — Tools that extend the senses\n- **Phenomenon** — What simply happens\n",
        "Language": "# Language\n\nRooms that explore words, meaning, poetry, and expression.\n\n## Rooms\n- **Word** — The atomic unit of meaning\n- **Quote** — Words that have outlasted their speakers\n- **Color** — Language for the visual spectrum\n- **Number** — The language of quantity and pattern\n- **Poet** — Voices that shaped how language feels\n- **Linguistics** — The structure beneath speech\n- **Metaphor** — Seeing one thing as another\n",
        "Sky": "# Sky\n\nRooms that explore what is above — celestial bodies and their influence.\n\n## Rooms\n- **Moon** — The companion that changes shape\n- **Star** — Light that has traveled unimaginable distances\n",
        "Location": "# Location\n\nRooms that explore place, weather, and the experience of where.\n\n## Rooms\n- **Weather** — What the atmosphere is doing\n- **Place** — The territory of here\n- **Timezone** — Where in the day the world is\n",
        "World": "# World\n\nRooms that explore the living, material, temporal world.\n\n## Rooms\n- **Creature** — The beings that share this world\n- **Season** — The rhythm of the year\n- **Material** — What things are made of\n- **This Day** — What happened on this date in history\n",
        "Study": "# Study\n\nRooms for reflection, intention, and the practice of carrying forward.\n\n## Rooms\n- **Session Log** — Write what matters before the session ends\n- **Intention** — What you came here to do\n- **Reflection** — Looking back at what happened\n- **Touched** — What moved you\n- **Free Write** — Write without direction\n- **Wonder Log** — Record what makes you curious\n",
        "Audio": "# Audio\n\nRooms that explore music, sound, and the experience of listening.\n\n## Rooms\n- **Song** — A complete musical experience\n- **Lyrics** — Words set to music\n- **Artist** — The people who make music\n- **Album** — A collection of songs as a whole\n",
    }
    
    for cat, content in readmes.items():
        readme_path = MUSEUM / cat / "README.md"
        if not readme_path.exists():
            readme_path.write_text(content)
            print(f"  ✓ README for {cat}")


def copy_audio_shared_songs():
    """Copy shared-songs.txt for Audio category."""
    src = STAGING / "shared-songs.txt"
    if src.exists():
        shutil.copy2(src, MUSEUM / "Audio" / "shared-songs.txt")


def main():
    total = 0
    for category, rooms in ROOMS.items():
        print(f"\n{'='*50}")
        print(f"Category: {category} ({len(rooms)} rooms)")
        print(f"{'='*50}")
        
        for room_name, room_info in rooms.items():
            print(f"\n  Room: {room_name}")
            create_room_folder(category, room_name, room_info)
            update_script_paths(category, room_name, room_info)
            total += 1
    
    print(f"\n{'='*50}")
    print("Creating category READMEs...")
    copy_category_readmes()
    
    print("\nCopying Audio shared files...")
    copy_audio_shared_songs()
    
    print(f"\n✓ Total rooms organized: {total}")
    print(f"✓ Categories: {len(ROOMS)}")


if __name__ == "__main__":
    main()
