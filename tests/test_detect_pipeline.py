"""Tests for the unified autotag fusion pipeline (rivalkit.detect.pipeline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rivalkit.detect.pipeline import (
    classify_commentary_type,
    enrich_with_tracking,
    fuse_candidates,
    main,
    minute_from_ts,
    run_pipeline,
)
from rivalkit.detect.transcribe import KEYWORDS, match_keywords


def test_minute_from_ts_maps_video_time_to_match_minutes():
    # First half: kickoff (t_1t) is minute 1; anything before clamps to 1.
    assert minute_from_ts(874.0) == 1
    assert minute_from_ts(0.0) == 1
    assert minute_from_ts(874.0 + 60 * 9) == 10
    # Second half: the halftime boundary clamps to 46, then runs up to 120.
    assert minute_from_ts(3700.0) == 46
    assert minute_from_ts(1962.0 + 60 * 50) == 51
    assert minute_from_ts(1962.0 + 60 * 130) == 120


def test_classify_commentary_type_ranks_penal_corner_free_kick_then_shot():
    assert classify_commentary_type("¡PENAL para el rival!") == ("penalty", "")
    assert classify_commentary_type("Penal tras la revisión del VAR") == ("penalty", "")
    assert classify_commentary_type("El córner fue despejado") == ("corner", "crossed")
    assert classify_commentary_type("Tiro libre desde la puerta del área") == ("free_kick", "direct")
    assert classify_commentary_type("Falta en el mediocampo") == ("free_kick", "direct")
    assert classify_commentary_type("Gran atajada del arquero") == ("shot", "on_target")
    assert classify_commentary_type("El remate se fue afuera") == ("shot", "off_target")
    assert classify_commentary_type("Remate de cabeza en el segundo palo") == ("shot", "")


def test_fuse_candidates_converts_flips_into_authoritative_goals():
    flips = [
        {"t": 1188.0, "from": "0-0", "to": "0-1"},
        {"t": 2153.0, "from": "0-1", "to": "1-1"},
    ]
    events = fuse_candidates(flips, [], [], rival_is_away=True)
    # Rival is away: the right/away digit flip is the rival goal, home is opponent.
    assert events[0] == {"minute": 6, "ts": 1188.0, "type": "goal", "team": "rival",
                         "zone": 17, "detail": "open_play", "player": ""}
    assert events[1] == {"minute": 22, "ts": 2153.0, "type": "goal", "team": "opponent",
                         "zone": 2, "detail": "open_play", "player": ""}
    # Rival at home: the same flips swap team attribution.
    events = fuse_candidates(flips, [], [], rival_is_away=False)
    assert [e["team"] for e in events] == ["opponent", "rival"]
    assert [e["zone"] for e in events] == [2, 17]


def test_fuse_candidates_ignores_pure_goal_shouts_near_a_flip():
    flips = [{"t": 1000.0, "from": "0-0", "to": "0-1"}]
    segments = [{"start": 1010.0, "end": 1014.0, "text": "¡GOLAZO de Joel Orlando!"}]
    peaks = [{"t": 1013, "db": -9.0, "prominence": 10.0}]
    events = fuse_candidates(flips, peaks, segments)
    # The goal is counted once by the flip; the shout and its crowd roar add nothing.
    assert len(events) == 1
    assert events[0]["type"] == "goal"


def test_fuse_candidates_keeps_non_goal_keywords_near_a_flip():
    flips = [{"t": 1000.0, "from": "0-0", "to": "0-1"}]
    segments = [{"start": 1010.0, "end": 1014.0, "text": "¡GOL! ¡Qué remate imperioso!"}]
    events = fuse_candidates(flips, [], segments)
    # Only the gol/golazo keywords are ignored near the flip; remate survives.
    assert [e["type"] for e in events] == ["goal", "shot"]


def test_fuse_candidates_goal_shout_far_from_any_flip_stays_a_candidate():
    segments = [{"start": 3000.0, "end": 3006.0, "text": "¡GOLAZO para el rival!"}]
    events = fuse_candidates([], [], segments)
    assert events == [{"minute": 36, "ts": 3003.0, "type": "shot", "team": "rival",
                       "zone": 17, "detail": "", "player": ""}]


def test_fuse_candidates_pairs_peak_with_commentary_into_one_event():
    segments = [{"start": 2400.0, "end": 2406.0, "text": "Tremendo remate al arco"}]
    peaks = [{"t": 2402, "db": -12.0, "prominence": 10.0}]
    events = fuse_candidates([], peaks, segments)
    assert len(events) == 1
    assert events[0] == {"minute": 26, "ts": 2403.0, "type": "shot", "team": "rival",
                         "zone": 17, "detail": "on_target", "player": ""}


def test_fuse_candidates_standalone_strong_peaks_become_shots():
    peaks = [{"t": 3000, "db": -10.0, "prominence": 9.0}]
    assert fuse_candidates([], peaks, []) == [
        {"minute": 36, "ts": 3000.0, "type": "shot", "team": "rival",
         "zone": 17, "detail": "", "player": ""}]
    # Weak peaks never become candidates.
    assert fuse_candidates([], [{"t": 3000, "db": -10.0, "prominence": 8.4}], []) == []


def test_fuse_candidates_suppresses_celebration_peak_near_flip():
    flips = [{"t": 1188.0, "from": "0-0", "to": "0-1"}]
    peaks = [{"t": 1194, "db": -8.0, "prominence": 11.0}]
    events = fuse_candidates(flips, peaks, [])
    assert [e["type"] for e in events] == ["goal"]


def test_fuse_candidates_sorts_events_by_minute_and_ts():
    flips = [{"t": 3000.0, "from": "0-0", "to": "0-1"}]
    segments = [{"start": 2400.0, "end": 2406.0, "text": "Remate al arco"}]
    events = fuse_candidates(flips, [], segments)
    assert [(e["minute"], e["ts"]) for e in events] == [(26, 2403.0), (36, 3000.0)]


def test_fuse_candidates_events_carry_exact_contract_keys():
    events = fuse_candidates(
        [{"t": 1188.0, "from": "0-0", "to": "0-1"}],
        [{"t": 3000, "db": -10.0, "prominence": 9.0}],
        [{"start": 2400.0, "end": 2406.0, "text": "Remate al arco"}],
    )
    assert len(events) == 3
    for ev in events:
        assert set(ev) == {"minute", "ts", "type", "team", "zone", "detail", "player"}


def test_enrich_with_tracking_rezones_events_from_modal_player_zone():
    events = [{"minute": 6, "ts": 1188.0, "type": "goal", "team": "rival", "zone": 17,
               "detail": "open_play", "player": ""}]
    rows = [
        {"frame": "35640", "class": "player", "x_m": "95.0", "y_m": "50.0"},  # zone 16
        {"frame": "35640", "class": "player", "x_m": "96.0", "y_m": "52.0"},  # zone 16
        {"frame": "35640", "class": "player", "x_m": "95.0", "y_m": "30.0"},  # zone 17
        {"frame": "35640", "class": "goalkeeper", "x_m": "95.0", "y_m": "50.0"},
        {"frame": "35640", "class": "player", "x_m": "110.0", "y_m": "50.0"},  # off-pitch
        {"frame": "30000", "class": "player", "x_m": "95.0", "y_m": "50.0"},   # out of window
    ]
    out = enrich_with_tracking(events, rows, fps=30.0, window_s=3.0)
    assert out[0]["zone"] == 16
    # Events with no tracked players nearby keep their original zone.
    far = enrich_with_tracking([dict(events[0], ts=5000.0)], rows, fps=30.0, window_s=3.0)
    assert far[0]["zone"] == 17


def test_run_pipeline_fuses_all_artifacts_into_events_raw(tmp_path: Path):
    (tmp_path / "flips.json").write_text(json.dumps(
        {"flips": [{"t": 1188.0, "from": "0-0", "to": "0-1"}]}), encoding="utf-8")
    (tmp_path / "peaks.json").write_text(json.dumps(
        {"top": [{"t": 2402, "db": -12.0, "prominence": 10.0},
                 {"t": 3000, "db": -10.0, "prominence": 9.0}]}), encoding="utf-8")
    (tmp_path / "transcript.jsonl").write_text("\n".join(
        json.dumps(s, ensure_ascii=False) for s in [
            {"start": 2400.0, "end": 2406.0, "text": "Tremendo remate al arco"},
            {"start": 2500.0, "end": 2504.0, "text": "El córcer fue despejado"},
            {"start": 700.0, "end": 706.0, "text": "Los equipos ya saltan al campo"},
        ]) + "\n", encoding="utf-8")
    (tmp_path / "pitch_positions.csv").write_text(
        "frame,class,x_m,y_m\n"
        "35640,player,95.0,50.0\n"
        "35640,player,96.0,52.0\n"
        "35640,player,95.0,30.0\n"
        "35640,goalkeeper,95.0,50.0\n"
        "35640,player,110.0,50.0\n"
        "30000,player,95.0,50.0\n"
        "99120,player,95.0,50.0\n",
        encoding="utf-8")
    (tmp_path / "shotmap.json").write_text(json.dumps([
        {"shotType": "goal", "time": 6, "isHome": True,
         "player": "Alejandro Gagliardi", "x": 8, "y": 50},
        {"shotType": "save", "time": 26, "isHome": False,
         "player": "Joel Orlando", "x": 10, "y": 50},
        {"shotType": "miss", "time": 40, "isHome": False,
         "player": "Facundo De La Vega", "x": 18, "y": 20},
    ]), encoding="utf-8")

    events = run_pipeline(tmp_path)

    # The goal zone is re-derived from tracking (modal zone 16); the shotmap
    # enriches the minute-26 shot with its scorer and adds the minute-40
    # Sofascore miss without letting the nearby tracked row override its
    # measured zone.
    assert events == [
        {"minute": 6, "ts": 1188.0, "type": "goal", "team": "rival", "zone": 16,
         "detail": "open_play", "player": ""},
        {"minute": 26, "ts": 2403.0, "type": "shot", "team": "rival", "zone": 17,
         "detail": "on_target", "player": "Joel Orlando"},
        {"minute": 28, "ts": 2502.0, "type": "corner", "team": "rival", "zone": 17,
         "detail": "crossed", "player": ""},
        {"minute": 36, "ts": 3000.0, "type": "shot", "team": "rival", "zone": 17,
         "detail": "", "player": ""},
        {"minute": 40, "ts": 3304, "type": "shot", "team": "rival", "zone": 15,
         "detail": "off_target", "player": "Facundo De La Vega"},
    ]
    raw = json.loads((tmp_path / "events_raw.json").read_text(encoding="utf-8"))
    assert raw == {"events": events}


def test_run_pipeline_with_no_artifacts_writes_empty_events(tmp_path: Path):
    events = run_pipeline(tmp_path)
    assert events == []
    raw = json.loads((tmp_path / "events_raw.json").read_text(encoding="utf-8"))
    assert raw == {"events": []}


def test_cli_writes_events_raw_and_supports_rival_at_home(tmp_path: Path, capsys):
    (tmp_path / "flips.json").write_text(json.dumps(
        {"flips": [{"t": 1188.0, "from": "0-0", "to": "0-1"}]}), encoding="utf-8")
    assert main(["--workdir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "events_raw.json").read_text(encoding="utf-8"))
    assert data["events"][0]["team"] == "rival"
    out = tmp_path / "custom.json"
    assert main(["--workdir", str(tmp_path), "--rival-is-home", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["events"][0]["team"] == "opponent"
    assert data["events"][0]["zone"] == 2
    assert "custom.json" in capsys.readouterr().out


# --- recovery detection (S8) ---------------------------------------------------

@pytest.mark.parametrize("word", ["recupera", "recupero", "roba", "robo",
                                  "quita", "corta", "intercep"])
def test_recovery_words_are_in_the_transcriber_vocabulary(word):
    assert word in KEYWORDS
    assert match_keywords(f"El cinco {word} la pelota") == [word]


def test_classify_commentary_type_detects_recovery():
    assert classify_commentary_type("La recupera en el mediocampo") == ("recovery", "")
    assert classify_commentary_type("Gran recuperación en la salida") == ("recovery", "")
    assert classify_commentary_type("Le roba la pelota al enganche") == ("recovery", "")
    assert classify_commentary_type("El robo fue limpio") == ("recovery", "")
    assert classify_commentary_type("La quita en campo contrario") == ("recovery", "")
    assert classify_commentary_type("Corta el avance rival") == ("recovery", "")
    assert classify_commentary_type("Intercepta el pase largo") == ("recovery", "")


def test_classify_commentary_type_ranks_set_pieces_and_shot_words_above_recovery():
    # Set pieces still win over recovery vocabulary.
    assert classify_commentary_type("Recupera en el área y hay penal") == ("penalty", "")
    assert classify_commentary_type("La roba y gana el córner") == ("corner", "crossed")
    assert classify_commentary_type("La quita y comete falta") == ("free_kick", "direct")
    # Explicit shot words win over recovery vocabulary.
    assert classify_commentary_type("La recupera y mete un remate cruzado") == ("shot", "")
    assert classify_commentary_type("Cabeza tras recuperar el balón") == ("shot", "")
    assert classify_commentary_type("Recupera y saca un zapatazo al arco") == ("shot", "on_target")
    assert classify_commentary_type("La corta pero el remate se fue afuera") == ("shot", "off_target")
    assert classify_commentary_type("Gran atajada tras la recuperación") == ("shot", "on_target")
    # No set piece, no shot word, no recovery word: fallback stays a shot.
    assert classify_commentary_type("Pelotazo al área") == ("shot", "")


def test_fuse_candidates_turns_recovery_hits_into_recovery_events():
    segments = [{"start": 2500.0, "end": 2504.0,
                 "text": "¡La recupera Almagro en campo contrario y sale jugando!"}]
    events = fuse_candidates([], [], segments)
    assert events == [{"minute": 28, "ts": 2502.0, "type": "recovery", "team": "rival",
                       "zone": 17, "detail": "", "player": ""}]
