"""Conversion of raw tagger JSON into events.csv with computed game_state."""

import json

import pytest

from scripts.tagger_export import convert


def test_game_state_is_computed_before_each_event():
    rows = [
        {"minute": 10, "ts": 100, "type": "goal", "team": "rival", "zone": 17, "detail": "open_play"},
        {"minute": 20, "ts": 200, "type": "shot", "team": "opponent", "zone": 14, "detail": "on_target"},
        {"minute": 30, "ts": 300, "type": "goal", "team": "opponent", "zone": 16, "detail": "open_play"},
        {"minute": 40, "ts": 400, "type": "shot", "team": "rival", "zone": 15, "detail": ""},
    ]
    out = convert(rows)
    assert [r["game_state"] for r in out] == ["drawing", "winning", "winning", "drawing"]
    assert [r["minute"] for r in out] == [10, 20, 30, 40]


def test_rows_are_sorted_by_minute_then_timestamp():
    rows = [
        {"minute": 30, "ts": 9, "type": "shot", "team": "rival", "zone": 14, "detail": ""},
        {"minute": 30, "ts": 2, "type": "corner", "team": "rival", "zone": 16, "detail": "crossed"},
        {"minute": 5, "ts": 1, "type": "recovery", "team": "opponent", "zone": 8, "detail": ""},
    ]
    out = convert(rows)
    assert [(r["minute"], r["event_type"]) for r in out] == [
        (5, "recovery"), (30, "corner"), (30, "shot")]


def test_scored_penalty_counts_once_and_keeps_detail():
    rows = [
        {"minute": 60, "ts": 10, "type": "penalty", "team": "rival", "zone": 17, "detail": ""},
        {"minute": 60, "ts": 11, "type": "goal", "team": "rival", "zone": 17, "detail": "penalty"},
        {"minute": 70, "ts": 12, "type": "shot", "team": "opponent", "zone": 5, "detail": ""},
    ]
    out = convert(rows)
    assert [r["game_state"] for r in out] == ["drawing", "drawing", "winning"]


def test_own_goal_credited_to_team_field():
    # own_goal rows credit the team in `team`, so the count follows it
    rows = [
        {"minute": 80, "ts": 1, "type": "goal", "team": "rival", "zone": 1, "detail": "own_goal"},
    ]
    out = convert(rows)
    assert out[0]["game_state"] == "drawing"  # 0-0 before; rival credited after


@pytest.mark.parametrize("row, needle", [
    ({"minute": 5, "type": "shot", "team": "rival", "zone": 19, "detail": ""}, "zone 19"),
    ({"minute": 5, "type": "tackle", "team": "rival", "zone": 5, "detail": ""}, "type 'tackle'"),
    ({"minute": 5, "type": "shot", "team": "own", "zone": 5, "detail": ""}, "team 'own'"),
    ({"minute": 5, "type": "shot", "team": "rival", "zone": 5, "detail": "crossed"}, "detail 'crossed'"),
    ({"minute": 200, "type": "shot", "team": "rival", "zone": 5, "detail": ""}, "minute 200"),
])
def test_invalid_rows_raise_together(row, needle):
    with pytest.raises(SystemExit) as exc:
        convert([row])
    assert needle in str(exc.value)


def test_export_roundtrip_matches_schema_columns(tmp_path):
    rows = [{"minute": 1, "ts": 1, "type": "shot", "team": "rival", "zone": 14, "detail": "on_target"}]
    from scripts.tagger_export import main
    raw = tmp_path / "events_raw.json"
    raw.write_text(json.dumps({"events": rows}), encoding="utf-8")
    out = tmp_path / "events.csv"
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["tagger_export.py", str(raw)]) == 0
    text = buf.getvalue()
    assert text.splitlines()[0] == "minute,event_type,team,zone,game_state,player,detail"
    assert "1,shot,rival,14,drawing,,on_target" in text
