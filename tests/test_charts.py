"""Aggregation edge cases and drawing for the chart set."""

from pathlib import Path

import pandas as pd
import pytest
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from rivalkit.charts import (INTERVALS, LABELS, PRESSING_PROXY_DEFINITION,
                             bar_chart, goal_breakdown, lineup_summary, plain,
                             pressing_proxy, record, select, set_piece_counts,
                             shot_map, table, venue_splits, zone_counts,
                             zone_legend, zone_map)
from rivalkit.schema import Dataset, load_matches

MATCH_COLS = ["match", "match_id", "date", "rival_team", "opponent", "venue",
              "rival_goals", "opponent_goals", "competition"]
EVENT_COLS = ["match", "minute", "event_type", "team", "zone", "game_state", "player", "detail"]
LINEUP_COLS = ["match", "player", "shirt_number", "position", "starter", "minute_in", "minute_out"]


def ev(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=EVENT_COLS)


def make_dataset(events, lineup, venues=("home", "away"),
                 goals=((1, 0), (0, 1))) -> Dataset:
    n = len(venues)
    matches = pd.DataFrame({
        "match": [f"m{i}" for i in range(1, n + 1)],
        "match_id": [f"m{i:02d}" for i in range(1, n + 1)],
        "date": pd.to_datetime([f"2026-03-{i:02d}" for i in range(1, n + 1)]),
        "rival_team": ["Rival FC"] * n,
        "opponent": [f"Oponente {i}" for i in range(1, n + 1)],
        "venue": list(venues),
        "rival_goals": [g[0] for g in goals],
        "opponent_goals": [g[1] for g in goals],
        "competition": ["Liga"] * n,
    })
    return Dataset("Rival FC", matches, events, lineup)


def empty_dataset() -> Dataset:
    return Dataset("", pd.DataFrame(columns=MATCH_COLS),
                   pd.DataFrame(columns=EVENT_COLS),
                   pd.DataFrame(columns=LINEUP_COLS))


# --- aggregation ---------------------------------------------------------------------

def test_zone_counts_exclude_opponent_and_own_goal():
    events = ev([
        ("m1", 10, "shot", "rival", 14, "drawing", "", "on_target"),
        ("m1", 20, "shot", "rival", 14, "drawing", "", "off_target"),
        ("m1", 30, "shot", "rival", 14, "drawing", "", "blocked"),
        ("m1", 40, "goal", "rival", 14, "drawing", "", "open_play"),
        ("m1", 12, "shot", "opponent", 14, "losing", "", "on_target"),
        ("m1", 50, "goal", "rival", 5, "winning", "", "own_goal"),
        ("m2", 10, "shot", "rival", 17, "drawing", "", "on_target"),
    ])
    counts = zone_counts(select(events, "rival", ("shot", "goal")))
    assert len(counts) == 18 and list(counts.index) == list(range(1, 19))
    assert counts[14] == 4 and counts[5] == 0 and counts[17] == 1
    assert counts.sum() == 5  # the opponent shot is not mixed in


def test_goal_breakdown_intervals_are_right_closed():
    events = ev([
        ("m1", 47, "goal", "rival", 17, "drawing", "", ""),
        ("m1", 90, "goal", "rival", 16, "winning", "", "set_piece"),
        ("m1", 93, "goal", "rival", 16, "winning", "", "penalty"),
    ])
    s = goal_breakdown(events, "rival", "interval")
    assert list(s.index) == list(INTERVALS)
    assert s["46-60"] == 1 and s["76-90"] == 1 and s["91+"] == 1
    assert s["0-15"] == 0 and s.sum() == 3


def test_goal_breakdown_by_detail_and_game_state():
    events = ev([
        ("m1", 47, "goal", "rival", 17, "drawing", "", ""),
        ("m1", 60, "goal", "rival", 16, "winning", "", "set_piece"),
        ("m1", 88, "goal", "rival", 17, "winning", "", "penalty"),
    ])
    by_detail = goal_breakdown(events, "rival", "detail")
    assert by_detail[""] == 1 and by_detail["set_piece"] == 1 and by_detail["penalty"] == 1
    by_state = goal_breakdown(events, "rival", "game_state")
    assert by_state["drawing"] == 1 and by_state["winning"] == 2 and by_state["losing"] == 0


def test_set_piece_counts_penalty_detail_ignored():
    events = ev([
        ("m1", 5, "corner", "rival", 16, "drawing", "", "crossed"),
        ("m1", 6, "corner", "rival", 16, "drawing", "", "short"),
        ("m1", 7, "free_kick", "rival", 17, "drawing", "", "direct"),
        ("m1", 8, "penalty", "rival", 17, "drawing", "", "direct"),
        ("m1", 9, "corner", "opponent", 16, "winning", "", "crossed"),
    ])
    rival = set_piece_counts(events, "rival")
    assert rival["corner/crossed"] == 1 and rival["corner/short"] == 1
    assert rival["free_kick/direct"] == 1 and rival["penalty"] == 1
    assert "penalty/direct" not in rival.index
    assert set_piece_counts(events, "opponent")["corner/crossed"] == 1


def test_pressing_proxy_counts_opposing_half_recoveries_per_match():
    events = ev([
        ("m1", 10, "recovery", "rival", 10, "drawing", "", ""),
        ("m1", 20, "recovery", "rival", 14, "drawing", "", ""),
        ("m1", 30, "recovery", "rival", 5, "drawing", "", ""),
        ("m1", 40, "recovery", "opponent", 17, "drawing", "", ""),
        ("m2", 10, "recovery", "rival", 8, "drawing", "", ""),
    ])
    s = pressing_proxy(make_dataset(events, pd.DataFrame(columns=LINEUP_COLS)))
    assert list(s) == [2, 0]  # zone 5 and opponent recovery excluded; m2 counts 0
    assert list(s.index) == ["01/03 vs Oponente 1", "02/03 vs Oponente 2"]


def _eleven(match, names):
    rows = [[match, n, str(i + 1), "MF", True, None, None] for i, n in enumerate(names)]
    return rows


def test_lineup_summary_minutes_starts_and_distinct_xi():
    names = [f"P {i:02d}" for i in range(1, 12)]
    rows = []
    for m in range(1, 6):
        rows += _eleven(f"m{m}", names)
    rows += [
        ["m1", "S 12", "12", "DF", False, 60, None],      # 30 minutes in a 90-minute match
        ["m1", "U 13", "13", "FW", False, None, None],    # unused substitute: 0 minutes
        ["m5", "P 01", "1", "MF", True, None, None],      # duplicate row: counted once
    ]
    lineup = pd.DataFrame(rows, columns=LINEUP_COLS)
    lineup["minute_in"] = pd.array(lineup["minute_in"], dtype="Int64")
    lineup["minute_out"] = pd.array(lineup["minute_out"], dtype="Int64")
    events = ev([("m5", 93, "goal", "rival", 17, "drawing", "", "open_play")])
    frame, distinct = lineup_summary(make_dataset(events, lineup))
    assert distinct == 1  # the same eleven across all 5 matches
    by_name = frame.set_index("player")
    assert by_name.loc["P 01", "starts"] == 5
    assert by_name.loc["P 01", "minutes"] == 90 * 4 + 93  # m5 ended at minute 93
    assert by_name.loc["S 12", "minutes"] == 30
    assert by_name.loc["U 13", "minutes"] == 0


def test_venue_splits_averages_and_missing_venue_is_nan():
    events = ev([
        ("m1", 10, "shot", "rival", 14, "drawing", "", "on_target"),
        ("m1", 20, "shot", "rival", 14, "drawing", "", "on_target"),
        ("m1", 30, "shot", "opponent", 14, "losing", "", "on_target"),
        ("m2", 10, "shot", "rival", 17, "drawing", "", "on_target"),
        ("m3", 10, "shot", "rival", 17, "drawing", "", "on_target"),
    ])
    data = make_dataset(events, pd.DataFrame(columns=LINEUP_COLS),
                        venues=("home", "home", "away"), goals=((2, 0), (0, 1), (4, 2)))
    s = venue_splits(data)
    assert s.loc["home", "matches"] == 2 and s.loc["away", "matches"] == 1
    assert s.loc["home", "goals_for"] == 1.0 and s.loc["home", "shots"] == 1.5
    assert s.loc["away", "shots"] == 1.0

    home_only = venue_splits(make_dataset(events, pd.DataFrame(columns=LINEUP_COLS),
                                          venues=("home",), goals=((1, 0),)))
    away = home_only.loc["away"]
    assert away["matches"] == 0
    assert away[["goals_for", "goals_against", "shots", "shots_against"]].isna().all()


def test_record():
    matches = pd.DataFrame({"rival_goals": [2, 0, 1], "opponent_goals": [1, 0, 3]})
    assert record(matches) == {"wins": 1, "draws": 1, "losses": 1,
                               "goals_for": 3, "goals_against": 4}


def test_labels_and_plain():
    assert LABELS["no_data"] == "Sin datos" and LABELS[""] == "Sin especificar"
    assert plain("US$ 100") == "US\\$ 100"


# --- drawing -------------------------------------------------------------------------

def example_data() -> Dataset:
    folders = sorted(p for p in Path("data/example").iterdir() if p.is_dir())
    return load_matches(folders)


def texts(ax) -> list[str]:
    return [t.get_text() for t in ax.texts]


def test_every_chart_renders_on_example_data():
    data = example_data()
    remates = select(data.events, "rival", ("shot", "goal"))
    cases = [
        shot_map(Figure().add_subplot(), data.events, "rival", "Mapa de remates"),
        shot_map(Figure().add_subplot(), data.events, "opponent", "Remates recibidos"),
        zone_map(Figure().add_subplot(), zone_counts(remates), "Pelota parada"),
        bar_chart(Figure().add_subplot(), goal_breakdown(data.events, "rival", "interval"),
                  "Goles a favor"),
        bar_chart(Figure().add_subplot(), pressing_proxy(data),
                  "Presión tras pérdida (proxy)", subtitle=PRESSING_PROXY_DEFINITION),
        table(Figure().add_subplot(), lineup_summary(data)[0], "Jugadores"),
        table(Figure().add_subplot(), venue_splits(data), "Local y visitante"),
        zone_legend(Figure().add_subplot()),
    ]
    assert all(isinstance(ax, Axes) for ax in cases)


def test_empty_inputs_render_sin_datos():
    data = empty_dataset()
    ax_shots = shot_map(Figure().add_subplot(), data.events, "rival", "Mapa de remates")
    ax_zones = zone_map(Figure().add_subplot(), pd.Series(dtype=float), "Pelota parada")
    ax_bars = bar_chart(Figure().add_subplot(), pd.Series(dtype=float), "Goles")
    ax_table = table(Figure().add_subplot(), pd.DataFrame(), "Jugadores")
    for ax in (ax_shots, ax_zones, ax_bars, ax_table):
        assert LABELS["no_data"] in texts(ax)


def test_no_chart_mentions_model_metrics():
    data = example_data()
    ax = shot_map(Figure().add_subplot(), data.events, "rival", "Mapa de remates")
    assert "xG" not in ax.get_title() and "PPDA" not in ax.get_title()


def test_proxy_chart_is_labelled_as_proxy():
    ax = bar_chart(Figure().add_subplot(), pd.Series([2, 0], index=["a", "b"]),
                   "Presión (proxy)", subtitle=PRESSING_PROXY_DEFINITION)
    drawn = " ".join(texts(ax)) + ax.get_title()
    assert "proxy" in drawn and "recuperaciones" in drawn
