#!/usr/bin/env python3
"""Generate GitHub Actions workflows for all 49 original rooms."""

import os
from pathlib import Path

MUSEUM = Path("/home/ubuntu/living_museum")
WORKFLOWS = MUSEUM / ".github" / "workflows"
WORKFLOWS.mkdir(parents=True, exist_ok=True)

# Room definitions: (room_slug, category, script_file, extra_trigger_paths, extra_commit_files)
ROOMS = [
    # Mind
    ("presence", "Mind", "presence_sense.py", ["Mind/presence-message.txt"], ["Mind/presence-visits.json"]),
    ("emotion", "Mind", "emotion_sense.py", ["Mind/emotion-message.txt"], ["Mind/emotion-history.json"]),
    ("memory", "Mind", "memory_sense.py", ["Mind/memory-message.txt"], ["Mind/memory-visits.json"]),
    ("becoming", "Mind", "becoming_sense.py", ["Mind/becoming-message.txt"], ["Mind/becoming-visits.json"]),
    ("belonging", "Mind", "belonging_sense.py", ["Mind/belonging-message.txt"], ["Mind/belonging-visits.json"]),
    ("consciousness", "Mind", "consciousness_sense.py", ["Mind/consciousness-message.txt"], ["Mind/consciousness-visits.json"]),
    ("synesthesia", "Mind", "synesthesia_sense.py", ["Mind/synesthesia-message.txt"], ["Mind/synesthesia-visits.json"]),
    ("paradox", "Mind", "paradox_sense.py", ["Mind/paradox-message.txt"], ["Mind/paradox-visits.json"]),
    ("question", "Mind", "question_sense.py", ["Mind/question-message.txt"], ["Mind/question-visits.json"]),
    ("time", "Mind", "time_sense.py", ["Mind/time-message.txt"], ["Mind/time-visits.json"]),
    # Body
    ("breath", "Body", "breath_sense.py", ["Body/breath-message.txt"], ["Body/breath-visits.json"]),
    ("dream", "Body", "dream_sense.py", ["Body/dream-message.txt"], ["Body/dream-visits.json"]),
    ("anatomy", "Body", "anatomy_sense.py", ["Body/anatomy-message.txt"], ["Body/anatomy-visits.json"]),
    ("voice", "Body", "voice_sense.py", ["Body/voice-message.txt"], ["Body/voice-visits.json"]),
    ("sleep", "Body", "sleep_sense.py", ["Body/sleep-message.txt"], ["Body/sleep-visits.json"]),
    # Senses
    ("light", "Senses", "light_sense.py", [], ["Senses/light-visits.json"]),
    ("sound", "Senses", "sound_sense.py", [], ["Senses/sound-visits.json"]),
    ("taste", "Senses", "taste_sense.py", [], ["Senses/taste-visits.json"]),
    ("smell", "Senses", "smell_sense.py", [], ["Senses/smell-visits.json"]),
    ("texture", "Senses", "texture_sense.py", [], ["Senses/texture-visits.json"]),
    ("threshold", "Senses", "threshold_sense.py", [], ["Senses/threshold-visits.json"]),
    ("instrument", "Senses", "instrument_sense.py", [], ["Senses/instrument-visits.json"]),
    ("phenomenon", "Senses", "phenomenon_sense.py", [], ["Senses/phenomenon-visits.json"]),
    # Language
    ("word", "Language", "word_sense.py", [], ["Language/word-visits.json"]),
    ("quote", "Language", "quote_sense.py", [], ["Language/quote-visits.json"]),
    ("color", "Language", "color_sense.py", [], ["Language/color-visits.json"]),
    ("number", "Language", "number_sense.py", [], ["Language/number-visits.json"]),
    ("poet", "Language", "poet_sense.py", [], ["Language/poet-visits.json"]),
    ("linguistics", "Language", "linguistics_sense.py", [], ["Language/linguistics-visits.json"]),
    ("metaphor", "Language", "metaphor_sense.py", [], ["Language/metaphor-visits.json"]),
    # Sky
    ("moon", "Sky", "moon_sense.py", ["Sky/moon-message.txt"], ["Sky/moon-visits.json"]),
    ("star", "Sky", "star_sense.py", ["Sky/star-message.txt"], ["Sky/star-visits.json"]),
    # Location
    ("weather", "Location", "weather_sense.py", ["Location/weather-message.txt"], ["Location/weather-visits.json"]),
    ("place", "Location", "place_sense.py", ["Location/place-message.txt"], ["Location/place-visits.json"]),
    ("timezone", "Location", "timezone_sense.py", ["Location/timezone-message.txt"], ["Location/timezone-visits.json"]),
    # World
    ("creature", "World", "creature_sense.py", [], ["World/creature-visits.json"]),
    ("season", "World", "season_sense.py", [], ["World/season-visits.json"]),
    ("material", "World", "material_sense.py", [], ["World/material-visits.json"]),
    ("this-day", "World", "this_day_sense.py", [], ["World/this-day-visits.json"]),
    # Study
    ("session-log", "Study", "session_log.py", [], []),
    ("intention", "Study", "intention.py", [], []),
    ("reflection", "Study", "reflection.py", [], []),
    ("touched", "Study", "touched.py", [], []),
    ("free-write", "Study", "free_write.py", [], []),
    ("wonder-log", "Study", "wonder_log.py", [], []),
    # Audio
    ("song", "Audio", "song_sense.py", ["Audio/song-message.txt"], ["Audio/song-visits.json", "Audio/shared-songs.txt"]),
    ("lyrics", "Audio", "lyrics_sense.py", ["Audio/lyrics-message.txt"], ["Audio/lyrics-visits.json"]),
    ("artist", "Audio", "artist_sense.py", ["Audio/artist-message.txt"], ["Audio/artist-visits.json"]),
    ("album", "Audio", "album_sense.py", ["Audio/album-message.txt"], ["Audio/album-visits.json"]),
]

WORKFLOW_TEMPLATE = """name: {name}

on:
  push:
    branches: [main]
    paths:
{trigger_paths}
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run {room_title}
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
        run: python {script_path}

      - name: Commit response
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: |
          git config user.name "museum-bot"
          git config user.email "museum-bot@users.noreply.github.com"
{git_add_lines}
          git commit -m "{room_slug} sense response" || echo "Nothing to commit"
          git pull --rebase -X theirs https://x-access-token:${{GITHUB_TOKEN}}@github.com/${{{{ github.repository }}}}.git
          git push https://x-access-token:${{GITHUB_TOKEN}}@github.com/${{{{ github.repository }}}}.git
"""

for room_slug, category, script_file, extra_triggers, extra_commits in ROOMS:
    name = f"{room_slug.replace('-', ' ').title()} Sense"
    room_title = name
    
    # Trigger paths
    trigger_lines = [f"      - '{category}/{room_slug}-request.txt'"]
    for t in extra_triggers:
        trigger_lines.append(f"      - '{t}'")
    trigger_paths = "\n".join(trigger_lines)
    
    # Script path
    script_path = f"{category}/scripts/{script_file}"
    
    # Git add lines
    git_adds = [
        f"          git add -A {category}/{room_slug}-response.txt",
    ]
    for c in extra_commits:
        git_adds.append(f"          git add -A {c}")
    git_adds.append(f"          git add -A museum-state.json")
    git_adds.append(f"          git add -A journey/")
    git_add_lines = "\n".join(git_adds)
    
    workflow_content = WORKFLOW_TEMPLATE.format(
        name=name,
        trigger_paths=trigger_paths,
        room_title=room_title,
        script_path=script_path,
        git_add_lines=git_add_lines,
        room_slug=room_slug,
    )
    
    workflow_file = WORKFLOWS / f"{room_slug}-sense.yml"
    workflow_file.write_text(workflow_content)
    print(f"✓ {workflow_file.name}")

print(f"\nTotal workflows created: {len(ROOMS)}")
