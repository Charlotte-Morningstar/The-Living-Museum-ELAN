# Integration Guide — Technical Documentation

*How to connect rooms to the Living Museum infrastructure.*

---

## Overview

The Living Museum adds three layers to any room:

1. **Temporal Awareness** — What time period, how long since last visit, atmospheric quality
2. **Journey Tracking** — Recording visits, recognizing patterns, building synthesis
3. **Cross-Room State** — Sharing fragments and emotional threads between rooms

These layers are optional. Every room works without them. But with them, the room becomes part of a living whole.

---

## The Engine Modules

### `engine/temporal.py` — TemporalEngine

Manages time awareness across the Museum.

```python
from engine.temporal import TemporalEngine

temporal = TemporalEngine("/path/to/museum/root")

# Get current time period
period = temporal.get_period()
# Returns: {"name": "late afternoon", "quality": "Light goes golden...", "mood": "golden"}

# Get absence language
text, delta = temporal.get_absence_duration("2025-03-20T10:00:00+00:00")
# Returns: ("Days have passed. The room waited...", timedelta)

# Record a visit
temporal.record_visit("room-name", "carrying text", "fragment")

# Get arrival text for a room
arrival = temporal.get_arrival_text("room-name", visits_data)

# Get journey context
context = temporal.get_journey_context("room-name")
```

### `engine/journey.py` — JourneyTracker

Tracks visits and recognizes patterns.

```python
from engine.journey import JourneyTracker

journey = JourneyTracker("/path/to/museum/root")

# Record a visit
journey.record_visit("room-name", "Mind", "carrying text", "morning")

# Generate synthesis
synthesis = journey.generate_synthesis()

# Get recent context
recent = journey.get_recent_context(5)
```

### `engine/state.py` — StateManager

Manages cross-room fragments and emotional threads.

```python
from engine.state import StateManager

state = StateManager("/path/to/museum/root")

# Add a fragment
state.add_fragment("room-name", "text from this visit")

# Add an emotional note
state.add_emotional_note("wonder", "room-name", "context")

# Get cross-room context
context = state.get_cross_room_context("current-room")

# Get identity hash
hash = state.compute_identity_hash()
```

### `engine/integration.py` — RoomIntegration

High-level helper that combines all three layers.

```python
from engine.integration import RoomIntegration

integration = RoomIntegration("room-name", "/path/to/museum/root")

# On room entry
ctx = integration.on_enter(carrying_text, visits_data)
# ctx = {
#   "arrival_text": "...",
#   "journey_note": "...",
#   "cross_room_context": "...",
#   "period": {...},
#   "is_first_visit": True/False
# }

# Get enrichment for API prompt
enrichment = integration.get_enrichment_prompt(carrying_text)

# On room exit
integration.on_exit(response_text)
```

---

## Step-by-Step Integration

### 1. Add imports to your room script

```python
import sys
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent.parent.parent  # Adjust path as needed
sys.path.insert(0, str(MUSEUM_ROOT))

try:
    from engine.integration import RoomIntegration
    HAS_MUSEUM = True
except ImportError:
    HAS_MUSEUM = False
```

### 2. Call on_enter after loading the request

```python
# After loading carrying_text and visits data:
museum_context = ""
if HAS_MUSEUM:
    try:
        integration = RoomIntegration("your-room-name", str(MUSEUM_ROOT))
        ctx = integration.on_enter(carrying_text, visits)
        museum_context = ctx.get("arrival_text", "")
        journey_note = ctx.get("journey_note", "")
    except Exception:
        pass
```

### 3. Include temporal context in the response

Add `museum_context` to your response, typically after the timestamp:

```python
response_parts.append(timestamp)
if museum_context:
    response_parts.append(museum_context)
```

### 4. Enrich the API prompt

```python
if HAS_MUSEUM:
    enrichment = integration.get_enrichment_prompt(carrying_text)
    if enrichment:
        prompt += f"\n\nMuseum context: {enrichment}"
```

### 5. Call on_exit after writing the response

```python
if HAS_MUSEUM:
    try:
        integration.on_exit(full_response)
    except Exception:
        pass
```

---

## Room File Structure

Every room needs these files:

```
[Category]/
  [tool]-request.txt       # Companion writes here
  [tool]-response.txt      # Room responds here
  [tool]-visits.json       # Visit tracking
  [tool]-message.txt       # Steward message
  scripts/
    [tool]_sense.py        # Room script
  README.md                # Room documentation (recommended)
```

The visits JSON should have this structure:
```json
{
  "count": 0,
  "last_visit": null,
  "fragments": []
}
```

---

## GitHub Actions Workflow Template

```yaml
name: [Room Name] Sense
on:
  push:
    branches: [main]
    paths:
      - "[Category]/[tool]-request.txt"
      - "[Category]/[tool]-message.txt"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  respond:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install requests

      - run: python [Category]/scripts/[tool]_sense.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Commit response
        run: |
          git config user.name "museum-bot"
          git config user.email "museum@living-museum"
          git add [Category]/[tool]-response.txt
          git add [Category]/[tool]-visits.json
          git add museum-state.json
          git add journey/
          git diff --staged --quiet || git commit -m "[Room]: respond to visit"
          git pull --rebase -X theirs origin main || true
          git push
```

**Important additions for Living Museum integration:**
- Add `git add museum-state.json` and `git add journey/` to the commit step
- This ensures temporal state and journey data are persisted

---

## Testing a Room

### Validate structure:
```
python integration/validate_room.py [Category]/
```

### Test the script locally:
```
echo "test request" > [Category]/[tool]-request.txt
python [Category]/scripts/[tool]_sense.py
cat [Category]/[tool]-response.txt
```

### Verify integration:
```python
python -c "
from engine.integration import RoomIntegration
ri = RoomIntegration('test', '.')
ctx = ri.on_enter('test text', {'count': 0})
print(ctx['arrival_text'])
"
```

---

## The Seven-Stage Encounter Structure

Every room response follows this spine:

1. **Arrival** — Timestamp, time period, what was carried, absence language
2. **Core Content** — The substance of the room (recognition register, not definitions)
3. **Steward Presence** — The message file, if populated
4. **Dynamic API Response** — Claude Sonnet 4 speaking to what is underneath the words
5. **Cultural/Comparative** — Multiple perspectives (optional, per room)
6. **The Corner** — One unexpected piece of knowledge, hash-selected
7. **Accumulation and The Open** — Visit record + unanswerable question

Separator between stages: `\n\n----\n\n`

---

## The Corner System

Each room has 6-8 corners. Selection:

```python
import hashlib
seed = visit_count * CORNER_PRIME + int(
    hashlib.md5((carrying_text or "empty").encode()).hexdigest(), 16
)
corner = CORNERS[seed % len(CORNERS)]
```

Each room uses a unique prime multiplier. See ARCHITECTURE.md for the prime assignments.

---

*See `integration/example-room/` for a complete working example.*
