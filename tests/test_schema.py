from pathlib import Path

import pytest

from rivalkit.schema import ValidationError, load_matches, load_notes, zone_rect

MATCH = ("match_id,date,rival_team,opponent,venue,rival_goals,opponent_goals,competition\n"
         "m01,2026-03-01,Atletico Ejemplo,Club Muestra,home,1,0,Liga\n")
EVENTS = ("minute,event_type,team,zone,game_state,player,detail\n"
          "10,shot,rival,14,drawing,Jugador 09,on_target\n"
          "34,goal,rival,17,drawing,Jugador 09,open_play\n"
          "50,corner,opponent,16,winning,,crossed\n")
LINEUP = ("player,shirt_number,position,starter,minute_in,minute_out\n"
          + "".join(f"Jugador {i:02d},{i},MF,true,,\n" for i in range(1, 12))
          + "Jugador 12,12,DF,false,60,\n")
FILES = {"match.csv": MATCH, "events.csv": EVENTS, "lineup.csv": LINEUP}


def write_match(root: Path, name="m01", edits=(), skip=()) -> Path:
    """Write a valid match folder, applying (file, old, new) text edits and skipping files."""
    folder = root / name
    folder.mkdir()
    files = dict(FILES)
    for file, old, new in edits:
        assert old in files[file], old
        files[file] = files[file].replace(old, new)
    for file, text in files.items():
        if file not in skip:
            (folder / file).write_bytes(text.encode("utf-8"))
    return folder


def errors_of(*folders) -> str:
    with pytest.raises(ValidationError) as exc:
        load_matches(list(folders))
    return "\n".join(exc.value.errors)


def test_complete_folder_is_accepted(tmp_path):
    data = load_matches([write_match(tmp_path)])
    assert data.rival == "Atletico Ejemplo"
    assert len(data.matches) == 1 and len(data.events) == 3 and len(data.lineup) == 12
    assert list(data.lineup["minute_in"].dropna()) == [60]


@pytest.mark.parametrize("edit, expected", [
    (("events.csv", "10,shot", "121,shot"), "events.csv:2: minute: '121' is not an integer from 0 to 120"),
    (("events.csv", "10,shot", "-1,shot"), "events.csv:2: minute: '-1'"),
    (("events.csv", "10,shot", "12.5,shot"), "events.csv:2: minute: '12.5'"),
    (("events.csv", "shot,rival,14", "tackle,rival,14"), "events.csv:2: event_type: 'tackle' is not one of"),
    (("events.csv", "crossed", "on_target"), "events.csv:4: detail: 'on_target' is not allowed for corner"),
    (("events.csv", "shot,rival,14", "shot,rival,0"), "events.csv:2: zone: '0' is not an integer from 1 to 18"),
    (("events.csv", "shot,rival,14", "shot,rival,19"), "events.csv:2: zone: '19'"),
    (("events.csv", "shot,rival,14", "shot,rival,box"), "events.csv:2: zone: 'box'"),
    (("events.csv", "10,shot,rival", "10,,rival"), "events.csv:2: event_type: ''"),
    (("match.csv", ",home,", ",neutral,"), "match.csv:2: venue: 'neutral' is not one of home, away"),
    (("match.csv", "Liga\n", "Liga\nm02,2026-03-08,A,B,away,0,0,Liga\n"), "match.csv: exactly one data row"),
    (("match.csv", "2026-03-01", "01/03/2026"), "match.csv:2: date: '01/03/2026'"),
    (("lineup.csv", "Jugador 11,11,MF,true", "Jugador 11,11,MF,false"), "lineup.csv: expected exactly 11 starters, found 10"),
    (("lineup.csv", "false,60,", "false,70,60"), "lineup.csv:13: minute_in, minute_out: minute_out 60 is lower than minute_in 70"),
    (("match.csv", "1,0,Liga", "2,0,Liga"), "m01: rival goals: match.csv says 2, events.csv has 1 rival goal events"),
])
def test_invalid_folder(tmp_path, edit, expected):
    assert expected in errors_of(write_match(tmp_path, edits=[edit]))


def test_missing_folder_and_file(tmp_path):
    out = errors_of(tmp_path / "nope", write_match(tmp_path, skip=("lineup.csv",)))
    assert "nope: not an existing folder" in out
    assert "m01/lineup.csv: file not found" in out


def test_missing_column_still_checks_the_others(tmp_path):
    folder = write_match(tmp_path, edits=[("events.csv", "zone,game_state,player", "zone,player"),
                                          ("events.csv", "10,shot", "125,shot")])
    out = errors_of(folder)
    assert out.count("missing columns: game_state") == 1
    assert "events.csv:2: minute: '125'" in out


def test_all_errors_reported_together_with_row_numbers(tmp_path):
    out = errors_of(write_match(tmp_path, edits=[("events.csv", "34,goal", "125,goal"),
                                                 ("events.csv", "50,corner,opponent,16", "50,corner,opponent,19")]))
    assert "events.csv:3: minute" in out and "events.csv:4: zone" in out


def test_mixed_rival_names_both_in_error(tmp_path):
    a = write_match(tmp_path, "a")
    b = write_match(tmp_path, "b", edits=[("match.csv", "Atletico Ejemplo", "Club B")])
    out = errors_of(a, b)
    assert "'Club B'" in out and "'Atletico Ejemplo'" in out


def test_same_folder_twice_is_loaded_once(tmp_path):
    folder = write_match(tmp_path)
    assert len(load_matches([folder, folder]).matches) == 1


def test_semicolon_bom_and_unknown_column(tmp_path):
    folder = write_match(tmp_path)
    (folder / "events.csv").write_bytes(
        ("﻿" + EVENTS.replace(",", ";").replace("detail", "detail;x").replace("on_target", "on_target;1")
         ).encode("utf-8"))
    assert len(load_matches([folder]).events) == 3


def test_cp1252_file(tmp_path):
    folder = write_match(tmp_path)
    (folder / "events.csv").write_bytes(EVENTS.replace("Jugador 09", "Ñandú").encode("cp1252"))
    assert "Ñandú" in set(load_matches([folder]).events["player"])


def test_enum_case_and_spaces_are_tolerated(tmp_path):
    folder = write_match(tmp_path, edits=[("lineup.csv", "Jugador 01,1,MF,true", "Jugador 01,1,MF, TRUE"),
                                          ("match.csv", ",home,", ", Home ,")])
    assert load_matches([folder]).matches["venue"].iloc[0] == "home"


# --- notes ---------------------------------------------------------------------------

MIN = '[summary]\nidentity = "x"\n[plan]\ninstructions = ["a"]\n'


def notes_errors(tmp_path, toml: str) -> str:
    path = tmp_path / "notes.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_notes(path)
    return "\n".join(exc.value.errors)


@pytest.mark.parametrize("toml, expected", [
    ('[plan]\ninstructions = ["a"]\n', "the summary is required"),
    ('[summary]\nidentity = "x"\n', "the match plan is required"),
    ('[summary]\nidentity = "x"\n[plan]\ninstructions = ["  "]\n', "the match plan is required"),
    (MIN + 'weaknesses = "x"\n', "plan.weaknesses"),
    ('[summary]\nidentity = "x"\nweaknesses = "x"\n[plan]\ninstructions = ["a"]\n',
     "summary.weaknesses must be a list of texts"),
    (MIN + '[observations]\ncon_pelota = "x"\n', "unknown key 'observations.con_pelota' (allowed: identity_and_lineup"),
    (MIN + '[[key_players]]\nname = "J"\n', "key_players[1].note"),
    ("[summary\n", "invalid TOML"),
])
def test_invalid_notes(tmp_path, toml, expected):
    assert expected in notes_errors(tmp_path, toml)


def test_missing_notes_file(tmp_path):
    with pytest.raises(ValidationError, match="file not found"):
        load_notes(tmp_path / "notes.toml")


def test_minimal_notes_load_with_empty_optional_parts(tmp_path):
    path = tmp_path / "notes.toml"
    path.write_text(MIN, encoding="utf-8")
    notes = load_notes(path)
    assert notes.observations == {} and notes.key_players == () and notes.clips == ()


def test_text_beyond_caps_is_unchanged(tmp_path):
    ident = "uno\ndos\ntres\ncuatro"
    items = [f"punto {i}" for i in range(5)]
    path = tmp_path / "notes.toml"
    path.write_text(f'[summary]\nidentity = """{ident}"""\nweaknesses = {items!r}\n'.replace("'", '"')
                    + '[plan]\ninstructions = ["a"]\n', encoding="utf-8")
    notes = load_notes(path)
    assert notes.identity == ident and notes.weaknesses == tuple(items)


def test_zone_geometry():
    x0, y0, w, h = zone_rect(1)
    assert (x0, round(y0, 2), round(w, 2), round(h, 2)) == (0, 66.67, 16.67, 33.33)
    x0, y0, _, _ = zone_rect(17)
    assert round(x0, 2) == 83.33 and round(y0, 2) == 33.33
