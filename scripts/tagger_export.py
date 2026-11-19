"""Convert the tagger's events_raw.json into events.csv with computed game_state.

The tagger records the match-clock minute, the video timestamp, the event
type, the acting team and the zone. It does not ask for the game state:
this script derives it by walking the events in minute order and keeping
the running score, from the rival's perspective, before each event.

Usage:
    .venv\\Scripts\\python scripts\\tagger_export.py events_raw.json > events.csv

Writes the CSV to stdout; validation problems go to stderr with exit 1.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EVENT_TYPES = {"shot", "goal", "corner", "free_kick", "penalty", "recovery"}
TEAMS = {"rival", "opponent"}
DETAILS = {
    "goal": {"open_play", "set_piece", "penalty", "own_goal"},
    "shot": {"on_target", "off_target", "blocked"},
    "corner": {"direct", "crossed", "short"},
    "free_kick": {"direct", "crossed", "short"},
}


def convert(rows: list[dict]) -> list[dict]:
    """Validate raw tagger rows and attach game_state, sorted by match time."""
    errors: list[str] = []
    clean: list[dict] = []
    for i, ev in enumerate(rows, 1):
        label = f"evento {i}"
        try:
            minute = int(ev["minute"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}: minute invalido {ev.get('minute')!r}")
            continue
        if not 0 <= minute <= 120:
            errors.append(f"{label}: minute {minute} fuera de 0-120")
        event_type = str(ev.get("type", ""))
        if event_type not in EVENT_TYPES:
            errors.append(f"{label}: type {event_type!r} no es uno de {sorted(EVENT_TYPES)}")
        team = str(ev.get("team", ""))
        if team not in TEAMS:
            errors.append(f"{label}: team {team!r} no es rival/opponent")
        try:
            zone = int(ev["zone"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}: zone invalida {ev.get('zone')!r}")
            continue
        if not 1 <= zone <= 18:
            errors.append(f"{label}: zone {zone} fuera de 1-18")
        detail = str(ev.get("detail") or "")
        allowed = DETAILS.get(event_type, set())
        if detail and detail not in allowed:
            errors.append(f"{label}: detail {detail!r} no permitido para {event_type}")
        try:
            ts = float(ev.get("ts", 0))
        except (TypeError, ValueError):
            ts = 0.0
        if errors and errors[-1].startswith(label):
            continue
        clean.append({"minute": minute, "ts": ts, "type": event_type,
                      "team": team, "zone": zone, "detail": detail,
                      "player": str(ev.get("player") or "")})
    if errors:
        raise SystemExit("\n".join(errors))

    clean.sort(key=lambda e: (e["minute"], e["ts"]))
    rival_goals = opponent_goals = 0
    out = []
    for e in clean:
        state = ("winning" if rival_goals > opponent_goals
                 else "losing" if rival_goals < opponent_goals else "drawing")
        out.append({"minute": e["minute"], "event_type": e["type"], "team": e["team"],
                    "zone": e["zone"], "game_state": state, "player": e["player"],
                    "detail": e["detail"]})
        if e["type"] == "goal":
            # team is the credited side (own goals included), per the tagging guide
            if e["team"] == "rival":
                rival_goals += 1
            else:
                opponent_goals += 1
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python scripts/tagger_export.py events_raw.json > events.csv",
              file=sys.stderr)
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8-sig"))
    rows = convert(data["events"])
    writer = csv.DictWriter(sys.stdout, ["minute", "event_type", "team", "zone",
                                          "game_state", "player", "detail"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
