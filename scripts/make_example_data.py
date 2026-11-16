"""Generate the synthetic example dataset (data/example/m01..m05).

Deterministic, stdlib only. Every match validates against the kit schema:
goals in events.csv match match.csv, exactly 11 starters, one substitution.
Coverage by construction: every event type, all three game states (the
opponent scores first at least once), 3 home and 2 away matches.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "example"

MATCHES = [
    # (folder, match_id, date, opponent, venue, rival_goals, opponent_goals)
    ("m01", "m01", "2026-03-01", "Club Muestra", "home", 2, 1),
    ("m02", "m02", "2026-03-08", "Deportivo Prueba", "away", 0, 1),
    ("m03", "m03", "2026-03-15", "Sportivo Modelo", "home", 3, 0),
    ("m04", "m04", "2026-03-22", "Union Ficticia", "away", 1, 1),
    ("m05", "m05", "2026-03-29", "Juventud Demo", "home", 2, 0),
]
PLAYERS = [f"Jugador {i:02d}" for i in range(1, 19)]


def match_events(rng, rival_goals: int, opponent_goals: int, opponent_first: bool):
    """Build an event list (minute, type, team, zone, detail) for one match."""
    events = []

    def goal_scorers(goals, team, minute_from=1):
        minutes = sorted(rng.sample(range(minute_from, 91), goals))
        for minute in minutes:
            detail = "penalty" if rng.random() < 0.15 else ("set_piece" if rng.random() < 0.3 else "open_play")
            events.append((minute, "goal", team, rng.choice([14, 16, 17]), detail))

    if opponent_first and opponent_goals:
        goal_scorers(1, "opponent", minute_from=5)
    goal_scorers(rival_goals, "rival", minute_from=10)
    if not opponent_first or not opponent_goals:
        goal_scorers(opponent_goals, "opponent", minute_from=20)

    for _ in range(rng.randint(8, 14)):
        events.append((rng.randint(1, 93), "shot", rng.choice(["rival", "opponent"]),
                       rng.randint(7, 18), rng.choice(["on_target", "off_target", "blocked"])))
    for _ in range(rng.randint(4, 8)):
        events.append((rng.randint(1, 92), "corner", rng.choice(["rival", "opponent"]),
                       rng.choice([16, 17]), rng.choice(["crossed", "crossed", "short", "direct"])))
    for _ in range(rng.randint(3, 6)):
        events.append((rng.randint(1, 92), "free_kick", rng.choice(["rival", "opponent"]),
                       rng.randint(10, 17), rng.choice(["direct", "crossed", "short"])))
    for _ in range(rng.randint(10, 18)):
        events.append((rng.randint(1, 94), "recovery", rng.choice(["rival", "opponent"]),
                       rng.randint(1, 18), ""))
    events.sort(key=lambda e: e[0])
    return events


def write_events(path: Path, events) -> None:
    rival = opponent = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["minute", "event_type", "team", "zone", "game_state", "player", "detail"])
        for minute, etype, team, zone, detail in events:
            state = "winning" if rival > opponent else "losing" if rival < opponent else "drawing"
            player = ""
            writer.writerow([minute, etype, team, zone, state, player, detail])
            if etype == "goal":
                if team == "rival":
                    rival += 1
                else:
                    opponent += 1


def write_lineup(path: Path, rng, sub_minute: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["player", "shirt_number", "position", "starter", "minute_in", "minute_out"])
        for i, name in enumerate(PLAYERS[:11], 1):
            writer.writerow([name, i, "MF", "true", "", ""])
        writer.writerow([PLAYERS[11], 12, "DF", "false", sub_minute, ""])


def write_match(path: Path, match_id: str, date: str, opponent: str, venue: str,
                rg: int, og: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["match_id", "date", "rival_team", "opponent", "venue",
                         "rival_goals", "opponent_goals", "competition"])
        writer.writerow([match_id, date, "Atletico Ejemplo", opponent, venue, rg, og, "Liga Ejemplo"])


def main() -> None:
    rng = random.Random(2026)
    OUT.mkdir(parents=True, exist_ok=True)
    for idx, (folder, match_id, date, opponent, venue, rg, og) in enumerate(MATCHES):
        target = OUT / folder
        target.mkdir(exist_ok=True)
        write_match(target / "match.csv", match_id, date, opponent, venue, rg, og)
        events = match_events(rng, rg, og, opponent_first=(idx == 1))  # m02: opponent scores first
        write_events(target / "events.csv", events)
        sub_minute = 55 + idx * 5
        write_lineup(target / "lineup.csv", rng, sub_minute)
        print(f"wrote {target} ({len(events)} events)")


if __name__ == "__main__":
    main()
