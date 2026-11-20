"""Tests for the merge module: conversion, corrections audit and XML export."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from rivalkit.merge import (
    CSV_FIELDS,
    DETAILS,
    EVENT_TYPES,
    TEAMS,
    convert_events,
    diff_corrections,
    export_sportscode_xml,
    write_corrections_log,
)


# --- convert_events ---------------------------------------------------------

def test_convert_events_computes_game_state_before_each_event():
    rows = [
        {"minute": 10, "ts": 100, "type": "goal", "team": "rival", "zone": 17, "detail": "open_play"},
        {"minute": 20, "ts": 200, "type": "shot", "team": "opponent", "zone": 14, "detail": "on_target"},
        {"minute": 30, "ts": 300, "type": "goal", "team": "opponent", "zone": 16, "detail": "open_play"},
        {"minute": 40, "ts": 400, "type": "recovery", "team": "rival", "zone": 12, "detail": ""},
    ]
    out = convert_events(rows)
    assert [r["game_state"] for r in out] == ["drawing", "winning", "winning", "drawing"]
    assert [r["minute"] for r in out] == [10, 20, 30, 40]


def test_convert_events_sorts_by_minute_then_ts():
    rows = [
        {"minute": 30, "ts": 9, "type": "shot", "team": "rival", "zone": 14, "detail": ""},
        {"minute": 30, "ts": 2, "type": "corner", "team": "rival", "zone": 16, "detail": "crossed"},
        {"minute": 5, "ts": 1, "type": "recovery", "team": "opponent", "zone": 8, "detail": ""},
    ]
    out = convert_events(rows)
    assert [(r["minute"], r["event_type"]) for r in out] == [
        (5, "recovery"), (30, "corner"), (30, "shot")]


def test_convert_events_rows_carry_csv_fields_keys_in_order():
    rows = [{"minute": 1, "ts": 1, "type": "shot", "team": "rival", "zone": 14,
             "detail": "on_target", "player": "Joel"}]
    out = convert_events(rows)
    assert list(out[0]) == CSV_FIELDS


def test_convert_events_drops_rejected_candidates_before_validation():
    rows = [
        {"minute": 10, "ts": 100, "type": "goal", "team": "rival", "zone": 17, "detail": "open_play"},
        # Invalid but rejected: never validated, never fails the export.
        {"minute": 999, "type": "shot", "team": "rival", "zone": 5, "detail": "", "status": "rejected"},
        {"minute": 20, "ts": 200, "type": "shot", "team": "opponent", "zone": 14, "detail": "on_target",
         "verdict": "rejected"},
        {"minute": 30, "ts": 300, "type": "corner", "team": "rival", "zone": 16, "detail": "crossed",
         "status": "confirmed"},
    ]
    out = convert_events(rows)
    assert [(r["minute"], r["event_type"]) for r in out] == [(10, "goal"), (30, "corner")]


def test_convert_events_all_rejected_yields_empty_list():
    rows = [{"minute": 5, "type": "shot", "team": "rival", "zone": 5, "detail": "",
             "status": "rejected"}]
    assert convert_events(rows) == []


@pytest.mark.parametrize("row, message", [
    ({"minute": 5, "type": "shot", "team": "rival", "zone": 19, "detail": ""},
     "evento 1: zone 19 fuera de 1-18"),
    ({"minute": 5, "type": "tackle", "team": "rival", "zone": 5, "detail": ""},
     "evento 1: type 'tackle' no es uno de "
     "['corner', 'free_kick', 'goal', 'penalty', 'recovery', 'shot']"),
    ({"minute": 5, "type": "shot", "team": "own", "zone": 5, "detail": ""},
     "evento 1: team 'own' no es rival/opponent"),
    ({"minute": 5, "type": "shot", "team": "rival", "zone": 5, "detail": "crossed"},
     "evento 1: detail 'crossed' no permitido para shot"),
    ({"minute": 200, "type": "shot", "team": "rival", "zone": 5, "detail": ""},
     "evento 1: minute 200 fuera de 0-120"),
    ({"minute": "x", "type": "shot", "team": "rival", "zone": 5, "detail": ""},
     "evento 1: minute invalido 'x'"),
    ({"minute": 5, "type": "shot", "team": "rival", "zone": "z", "detail": ""},
     "evento 1: zone invalida 'z'"),
])
def test_convert_events_keeps_exact_tagger_error_messages(row, message):
    with pytest.raises(SystemExit) as exc:
        convert_events([row])
    assert str(exc.value) == message


def test_convert_events_reports_all_invalid_rows_together():
    rows = [
        {"minute": 5, "type": "shot", "team": "rival", "zone": 5, "detail": ""},
        {"minute": 200, "type": "shot", "team": "rival", "zone": 5, "detail": ""},
        {"minute": 5, "type": "shot", "team": "own", "zone": 5, "detail": ""},
    ]
    with pytest.raises(SystemExit) as exc:
        convert_events(rows)
    assert str(exc.value).splitlines() == [
        "evento 2: minute 200 fuera de 0-120",
        "evento 3: team 'own' no es rival/opponent",
    ]


def test_recovery_events_flow_through_the_merge_module(tmp_path):
    assert "recovery" in EVENT_TYPES
    rows = [{"minute": 28, "ts": 2502.0, "type": "recovery", "team": "rival", "zone": 12,
             "detail": "", "player": ""}]
    assert convert_events(rows)[0]["event_type"] == "recovery"
    out = tmp_path / "recovery.xml"
    assert export_sportscode_xml(rows, out) == 1
    assert "<code>28 RECOVERY RIVAL</code>" in out.read_text(encoding="utf-8")


# --- diff_corrections / write_corrections_log --------------------------------

def _shot(minute, ts, **extra):
    row = {"minute": minute, "ts": ts, "type": "shot", "team": "rival", "zone": 17,
           "detail": "", "player": ""}
    row.update(extra)
    return row


def test_diff_corrections_reports_confirmed_modified_added_removed():
    before = [
        _shot(10, 100.0),
        _shot(26, 500.0, zone=14, detail="on_target"),
        _shot(40, 900.0, zone=15),
    ]
    after = [
        _shot(10, 100.0),
        _shot(26, 504.0, zone=15, detail="on_target", player="Joel Orlando"),
        {"minute": 30, "ts": 2000.0, "type": "recovery", "team": "rival", "zone": 12,
         "detail": "", "player": ""},
    ]
    entries = diff_corrections(before, after)
    assert [e["action"] for e in entries] == ["confirmed", "modified", "added", "removed"]

    confirmed, modified, added, removed = entries
    assert confirmed["ts"] == 100.0 and confirmed["minute"] == 10
    assert confirmed["changes"] == {}

    assert modified["ts"] == 504.0 and modified["minute"] == 26
    assert modified["changes"] == {
        "zone": {"before": 14, "after": 15},
        "player": {"before": "", "after": "Joel Orlando"},
    }

    assert added["changes"]["type"] == {"before": None, "after": "recovery"}
    assert added["changes"]["zone"] == {"before": None, "after": 12}

    assert removed["ts"] == 900.0 and removed["minute"] == 40
    assert removed["changes"]["type"] == {"before": "shot", "after": None}


def test_diff_corrections_matches_on_minute_when_ts_is_missing():
    before = [{"minute": 10, "type": "shot", "team": "rival", "zone": 17, "detail": "", "player": ""}]
    after = [{"minute": 10, "type": "corner", "team": "rival", "zone": 16, "detail": "crossed",
              "player": ""}]
    entries = diff_corrections(before, after)
    assert entries[0]["action"] == "modified"
    assert entries[0]["ts"] is None
    assert entries[0]["changes"]["type"] == {"before": "shot", "after": "corner"}

    # Different minute with no ts on either side: no match at all.
    other = diff_corrections(before, [dict(after[0], minute=11)])
    assert [e["action"] for e in other] == ["added", "removed"]


def test_diff_corrections_window_is_inclusive_and_configurable():
    before = [_shot(10, 100.0)]
    at_edge = [_shot(10, 108.0)]
    assert diff_corrections(before, at_edge)[0]["action"] == "confirmed"

    beyond = [_shot(10, 108.5)]
    assert [e["action"] for e in diff_corrections(before, beyond)] == ["added", "removed"]
    assert diff_corrections(before, beyond, match_window_s=10.0)[0]["action"] == "confirmed"


def test_diff_corrections_ignores_rejected_rows_in_after():
    before = [_shot(10, 100.0)]
    after = [
        dict(_shot(10, 100.0), status="confirmed"),
        dict(_shot(26, 500.0, type="corner", zone=16, detail="crossed"), status="rejected"),
    ]
    entries = diff_corrections(before, after)
    # The confirmed candidate matches; the rejected corner never becomes "added".
    assert [e["action"] for e in entries] == ["confirmed"]


def test_write_corrections_log_writes_jsonl_and_returns_count(tmp_path):
    before = [_shot(10, 100.0)]
    after = [
        _shot(10, 100.0, zone=15),
        {"minute": 30, "ts": 1800.0, "type": "recovery", "team": "rival", "zone": 12,
         "detail": "", "player": ""},
    ]
    log = tmp_path / "corrections.jsonl"
    assert write_corrections_log(before, after, log) == 2
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert entries[0]["action"] == "modified"
    assert entries[0]["changes"]["zone"] == {"before": 17, "after": 15}
    assert entries[1]["action"] == "added"
    assert entries[1]["changes"]["type"] == {"before": None, "after": "recovery"}


# --- export_sportscode_xml ----------------------------------------------------

def test_export_sportscode_xml_from_raw_rows(tmp_path):
    rows = [
        {"minute": 5, "ts": 1193.0, "type": "goal", "team": "rival", "zone": 17,
         "detail": "open_play", "player": "Joel Orlando"},
        {"minute": 26, "ts": 500.0, "type": "shot", "team": "rival", "zone": 14,
         "detail": "on_target", "player": "", "status": "rejected"},
        {"minute": 36, "ts": 3000.0, "type": "recovery", "team": "opponent", "zone": 8,
         "detail": "", "player": ""},
    ]
    out = tmp_path / "events.xml"
    assert export_sportscode_xml(rows, out) == 2
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<?xml version='1.0' encoding='utf-8'?>")
    assert "<file>" in text and "</ALL_INSTANCES>" in text
    assert "<ID>1</ID>" in text and "<ID>2</ID>" in text
    # Instances span a 15 s window from the video timestamp.
    assert "<start>1193.00</start>" in text
    assert "<end>1208.00</end>" in text
    assert "<code>05 GOAL RIVAL</code>" in text
    assert "<group>Minuto</group>" in text and "<text>5'</text>" in text
    assert "<text>Zona 17</text>" in text
    assert "<text>Joel Orlando</text>" in text
    assert "<text>goal/open_play</text>" in text
    # The rejected shot never reaches the XML; recovery rows export with a bare Tipo.
    assert "shot" not in text
    assert "<code>36 RECOVERY OPPONENT</code>" in text
    assert "<text>Zona 08</text>" in text
    assert "<text>recovery</text>" in text
    assert text.rstrip().endswith("</file>")


def test_export_sportscode_xml_accepts_converted_rows(tmp_path):
    converted = convert_events([
        {"minute": 5, "ts": 1, "type": "corner", "team": "rival", "zone": 16,
         "detail": "crossed", "player": ""},
    ])
    out = tmp_path / "converted.xml"
    assert export_sportscode_xml(converted, out) == 1
    text = out.read_text(encoding="utf-8")
    # Converted rows have no ts: instances land at minute * 60 seconds.
    assert "<start>300.00</start>" in text
    assert "<text>corner/crossed</text>" in text
    assert "<text>Zona 16</text>" in text


def test_export_sportscode_xml_with_no_rows_writes_empty_skeleton(tmp_path):
    out = tmp_path / "empty.xml"
    assert export_sportscode_xml([], out) == 0
    text = out.read_text(encoding="utf-8")
    assert "<ALL_INSTANCES>\n  </ALL_INSTANCES>" in text
    assert text.rstrip().endswith("</file>")


# --- scripts/tagger_export.py CLI facade ---------------------------------------

def test_tagger_export_reexports_the_merge_contract():
    from scripts.tagger_export import DETAILS as X_DETAILS
    from scripts.tagger_export import EVENT_TYPES as X_EVENT_TYPES
    from scripts.tagger_export import TEAMS as X_TEAMS
    from scripts.tagger_export import convert

    assert convert is convert_events
    assert X_EVENT_TYPES == EVENT_TYPES
    assert X_TEAMS == TEAMS
    assert X_DETAILS == DETAILS


def _write_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "events_raw.json"
    raw.write_text(json.dumps({"events": [
        {"minute": 1, "ts": 1, "type": "shot", "team": "rival", "zone": 14,
         "detail": "on_target"},
    ]}), encoding="utf-8")
    return raw


def test_tagger_export_default_writes_csv_to_stdout(tmp_path):
    from scripts.tagger_export import main
    raw = _write_raw(tmp_path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["tagger_export.py", str(raw)]) == 0
    text = buf.getvalue()
    assert text.splitlines()[0] == "minute,event_type,team,zone,game_state,player,detail"
    assert "1,shot,rival,14,drawing,,on_target" in text


def test_tagger_export_out_flag_writes_csv_file_and_keeps_stdout_clean(tmp_path):
    from scripts.tagger_export import main
    raw = _write_raw(tmp_path)
    csv_path = tmp_path / "events.csv"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["tagger_export.py", str(raw), "-o", str(csv_path)]) == 0
    assert buf.getvalue() == ""
    text = csv_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "minute,event_type,team,zone,game_state,player,detail"
    assert "1,shot,rival,14,drawing,,on_target" in text


def test_tagger_export_xml_flag_writes_nacsport_file(tmp_path, capsys):
    from scripts.tagger_export import main
    raw = _write_raw(tmp_path)
    xml_path = tmp_path / "events.xml"
    assert main(["tagger_export.py", str(raw), "--xml", str(xml_path)]) == 0
    text = xml_path.read_text(encoding="utf-8")
    assert "<code>01 SHOT RIVAL</code>" in text
    assert "<text>shot/on_target</text>" in text
    captured = capsys.readouterr()
    assert f"1 instances -> {xml_path}" in captured.err
    # --xml without -o skips the CSV stdout dump.
    assert captured.out == ""


def test_tagger_export_corrections_flag_writes_audit_log(tmp_path, capsys):
    from scripts.tagger_export import main
    autotag = tmp_path / "autotag.json"
    autotag.write_text(json.dumps({"events": [
        _shot(10, 100.0),
        _shot(40, 900.0, zone=15),
    ]}), encoding="utf-8")
    reviewed = tmp_path / "events_raw.json"
    reviewed.write_text(json.dumps({"events": [
        _shot(10, 100.0),
        {"minute": 26, "ts": 500.0, "type": "corner", "team": "rival", "zone": 16,
         "detail": "crossed", "player": ""},
    ]}), encoding="utf-8")
    log = tmp_path / "corrections.jsonl"
    assert main(["tagger_export.py", str(reviewed), "--corrections", str(autotag), str(log)]) == 0
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [e["action"] for e in entries] == ["confirmed", "added", "removed"]
    captured = capsys.readouterr()
    assert f"3 corrections -> {log}" in captured.err


def test_tagger_export_flags_combine_into_three_outputs(tmp_path):
    from scripts.tagger_export import main
    autotag = tmp_path / "autotag.json"
    autotag.write_text(json.dumps({"events": [
        {"minute": 1, "ts": 1, "type": "shot", "team": "rival", "zone": 14,
         "detail": "on_target"},
    ]}), encoding="utf-8")
    raw = _write_raw(tmp_path)
    csv_path = tmp_path / "events.csv"
    xml_path = tmp_path / "events.xml"
    log = tmp_path / "corrections.jsonl"
    argv = ["tagger_export.py", str(raw), "-o", str(csv_path), "--xml", str(xml_path),
            "--corrections", str(autotag), str(log)]
    assert main(argv) == 0
    assert "minute,event_type" in csv_path.read_text(encoding="utf-8")
    assert "<code>01 SHOT RIVAL</code>" in xml_path.read_text(encoding="utf-8")
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [e["action"] for e in entries] == ["confirmed"]
