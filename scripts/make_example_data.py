"""Generate the seeded synthetic example dataset (data/example/m01..m05).

Stdlib only. One random.Random(2026) stream makes every run byte-identical, so
the example CSVs are regenerated rather than edited by hand.
"""

import csv
import random
from pathlib import Path

RIVAL = "AtlActico Ejemplo"
COMPETITION = "Primera Nacional Ejemplo"
ROOT = Path(__file__).resolve().parent.parent / "data" / "example"

PLAYERS = [f"Jugador {i:02d}" for i in range(1, 19)]
OPP_PLAYERS = [f"Adversario {i:02d}" for i in range(1, 12)]
ATTACKERS = ["Jugador 07", "Jugador 08", "Jugador 09", "Jugador 10", "Jugador 11"]
OPP_ATTACKERS = [f"Adversario {i:02d}" for i in (7, 8, 9, 10, 11)]

# match_id, date, opponent, venue, goals for/against.
FIXED = [
    ("m01", "2026-08-08", "Club Muestra", "home", 2, 1),
    ("m02", "2026-08-15", "Deportivo Prueba", "away", 1, 1),
    ("m03", "2026-08-22", "Atlético Simulado", "home", 1, 0),
    ("m04", "2026-08-29", "Unión Ficticia", "away", 1, 2),
    ("m05", "2026-09-05", "Sport Equipo", "home", 3, 1),
]

# Fixed goal sequence per match: (minute, team, scorer shirt, detail).
# m01 has the opponent scoring first so all three game states appear.
GOALS = {
    "m01": [(23, "opponent", 9, "open_play"), (41, "rival", 9, "open_play"),
            (78, "rival", 5, "open_play")],
    "m02": [(30, "rival", 10, "open_play"), (66, "opponent", 11, "set_piece")],
    "m03": [(55, "rival", 9, "open_play")],
    "m04": [(12, "opponent", 9, "open_play"), (38, "opponent", 7, "penalty"),
            (80, "rival", 11, "open_play")],
    "m05": [(20, "rival", 9, "penalty"), (44, "opponent", 5, "open_play"),
            (63, "rival", 10, "open_play"), (85, "rival", 5, "open_play")],
}

# Executed penalties that were NOT converted (event only, no goal row).
PENALTIES = {"m01": [(55, "rival")]}

# One substitution per match: (shirt in, minute, shirt out).
SUBS = {"m01": (12, 70, 9), "m02": (13, 60, 6), "m03": (14, 78, 10),
        "m04": (15, 46, 8), "m05": (16, 82, 11)}

POSITIONS = {"Jugador 01": "GK"}
for i in range(2, 6):
    POSITIONS[f"Jugador {i:02d}"] = "DF"
for i in range(6, 9):
    POSITIONS[f"Jugador {i:02d}"] = "MF"
for i in range(9, 12):
    POSITIONS[f"Jugador {i:02d}"] = "FW"
for i in range(12, 15):
    POSITIONS[f"Jugador {i:02d}"] = "DF"
for i in range(15, 17):
    POSITIONS[f"Jugador {i:02d}"] = "MF"
for i in range(17, 19):
    POSITIONS[f"Jugador {i:02d}"] = "FW"


def shot_zone(rng, team):
    return rng.choice([12, 13, 14, 15, 16, 16, 17, 17, 18, 11] if team == "rival"
                      else [1, 2, 3, 4, 5, 5, 6, 6, 7, 8])


def corner_zone(rng, team):
    return rng.choice([13, 16, 12, 15, 18, 14] if team == "rival"
                      else [4, 1, 6, 3, 7, 2])


def fk_zone(rng, team):
    return rng.choice([14, 15, 17, 13, 16, 18] if team == "rival"
                      else [3, 4, 5, 2, 6, 1])


def attack_player(rng, team):
    return rng.choice(ATTACKERS if team == "rival" else OPP_ATTACKERS)


def recovery_player(rng, team):
    return rng.choice(PLAYERS[:11] if team == "rival" else OPP_PLAYERS)


def build_events(rng, match_id):
    rows = []
    for minute, team, shirt, detail in GOALS[match_id]:
        name = PLAYERS[shirt - 1] if team == "rival" else f"Adversario {shirt:02d}"
        rows.append([minute, "goal", team, shot_zone(rng, team), name, detail])
    for minute, team in PENALTIES.get(match_id, []):
        rows.append([minute, "penalty", team, 17, attack_player(rng, team), ""])

    def scatter(kind, counts, zone_fn, player_fn, detail_fn):
        for team, count in counts:
            for _ in range(count):
                rows.append([rng.randint(1, 94), kind, team, zone_fn(rng, team),
                             player_fn(rng, team), detail_fn(rng)])

    scatter("shot", (("rival", 17), ("opponent", 12)), shot_zone, attack_player,
            lambda r: r.choice(["on_target", "on_target", "off_target", "blocked"]))
    scatter("corner", (("rival", 6), ("opponent", 4)), corner_zone, attack_player,
            lambda r: r.choice(["crossed", "crossed", "crossed", "short", "short", "direct"]))
    scatter("free_kick", (("rival", 5), ("opponent", 4)), fk_zone, attack_player,
            lambda r: r.choice(["crossed", "crossed", "direct", "direct", "short"]))
    scatter("recovery", (("rival", 17), ("opponent", 15)),
            lambda r, t: r.randint(1, 18), recovery_player, lambda r: "")

    rows.sort(key=lambda r: r[0])  # stable: fixed rows keep priority on ties
    out, goals_for, goals_against = [], 0, 0
    for minute, kind, team, zone, player, detail in rows:
        state = ("winning" if goals_for > goals_against
                 else "losing" if goals_for < goals_against else "drawing")
        out.append([minute, kind, team, zone, state, player, detail])
        if kind == "goal":
            if team == "rival":
                goals_for += 1
            else:
                goals_against += 1
    return out


def build_lineup(match_id):
    shirt_in, minute, shirt_out = SUBS[match_id]
    rows = []
    for i, name in enumerate(PLAYERS, 1):
        starter = i <= 11
        minute_in = minute if i == shirt_in else ""
        minute_out = minute if i == shirt_out else ""
        rows.append([name, i, POSITIONS[name], str(starter).lower(),
                     minute_in, minute_out])
    return rows


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    rng = random.Random(2026)
    for match_id, date, opponent, venue, goals_for, goals_against in FIXED:
        folder = ROOT / match_id
        folder.mkdir(parents=True, exist_ok=True)
        write_csv(folder / "match.csv",
                  ["match_id", "date", "rival_team", "opponent", "venue",
                   "rival_goals", "opponent_goals", "competition"],
                  [[match_id, date, RIVAL, opponent, venue, goals_for,
                    goals_against, COMPETITION]])
        write_csv(folder / "events.csv",
                  ["minute", "event_type", "team", "zone", "game_state",
                   "player", "detail"], build_events(rng, match_id))
        write_csv(folder / "lineup.csv",
                  ["player", "shirt_number", "position", "starter",
                   "minute_in", "minute_out"], build_lineup(match_id))
        print(f"wrote {folder.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
