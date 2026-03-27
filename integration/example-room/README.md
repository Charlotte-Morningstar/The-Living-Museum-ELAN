# Example Room — Integrated with the Living Museum

This folder shows the complete pattern for a room that is fully integrated
with the Living Museum's temporal awareness engine.

## Files

- `example_sense.py` — The room script with full integration
- `example-request.txt` — Where the Companion writes
- `example-response.txt` — Where the room responds
- `example-visits.json` — Visit tracking
- `example-message.txt` — Steward message
- `example-sense.yml` — GitHub Action workflow (goes in .github/workflows/)

## The Pattern

Every room follows the same loop:

1. Companion writes in the request file
2. GitHub Action fires the Python script
3. Script reads request, loads visits, generates encounter
4. Script writes response and updates visits
5. Companion reads the response

The Living Museum adds:
- Temporal arrival text (what time period, how long since last visit)
- Journey context (what rooms were visited recently)
- Cross-room fragments (what was carried in other rooms)
- Automatic journey tracking (recorded in museum-state.json)

## Integration Points

In your script, add these three things:

1. **Import** the integration at the top
2. **Call on_enter()** after loading the request to get temporal context
3. **Call on_exit()** after writing the response to update journey state
