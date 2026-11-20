"""Contracts of SPEC-review.md and tools/tagger.html (SDD module review, tagger v3).

The tagger is a single zero-dependency HTML file, so these tests pin its
static contracts: DOM ids and labels, the review/edit state machine,
localStorage keys, and the three in-browser export formats (raw JSON, CSV
with game_state, Nacsport/Once XML).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "SPEC-review.md"
TAGGER_PATH = ROOT / "tools" / "tagger.html"


@pytest.fixture(scope="module")
def spec() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html() -> str:
    return TAGGER_PATH.read_text(encoding="utf-8")


# ---------- SPEC-review.md (mirrors the SPEC-detect.md structure) ----------

def test_spec_review_exists():
    assert SPEC_PATH.exists(), "SPEC-review.md missing (SDD module review)"


def test_spec_review_follows_detect_section_structure(spec):
    headings = [m.group(1).strip() for m in re.finditer(r"^## (.+)$", spec, re.M)]
    for required in ["Objetivo", "Uso", "Estructura", "Contratos clave",
                     "Estrategia de testing", "Boundaries",
                     "Criterios de aceptación"]:
        assert required in headings, f"missing section ## {required}"


def test_spec_review_documents_review_contracts(spec):
    for needle in ["tagger.html", "lineup.csv", "pending", "confirmed",
                   "events_raw.json", "events.csv", "events_nacsport.xml"]:
        assert needle in spec, f"SPEC-review.md does not mention {needle}"


# ---------- v2 features preserved ----------

def test_preserves_six_event_types_and_shortcuts(html):
    for t in ["shot", "goal", "corner", "free_kick", "penalty", "recovery"]:
        assert f'data-type="{t}"' in html
    m = re.search(r'const KEY_TYPE = \{([^}]+)\}', html)
    assert m, "KEY_TYPE shortcut map missing"
    for key, t in [("s", "shot"), ("g", "goal"), ("c", "corner"),
                   ("f", "free_kick"), ("p", "penalty"), ("r", "recovery")]:
        assert f'{key}: "{t}"' in m.group(1)
    assert "if (!draft.type && KEY_TYPE[k])" in html  # type shortcuts keep priority


def test_preserves_zone_grid_clock_and_storage(html):
    assert "band * 3 + lane + 1" in html
    assert re.search(r'function pad\(z\) \{ return z < 10 \? "0" \+ z : "" \+ z; \}', html)
    assert 'data-half="1"' in html and 'data-half="2"' in html
    for key in ["rivalkit_tagger_events", "rivalkit_tagger_offsets", "rivalkit_tagger_names"]:
        assert key in html


def test_preserves_zero_dependency_and_json_export(html):
    assert "<script src" not in html  # single self-contained file
    assert 'id="export"' in html and "Descargar events_raw.json" in html
    assert re.search(r'JSON\.stringify\(\{events: events\}', html)
    assert '"events_raw.json"' in html


# ---------- player + lineup.csv ----------

def test_player_input_datalist_and_chips_widgets(html):
    m = re.search(r'<input id="player"[^>]*>', html)
    assert m, '<input id="player"> missing'
    assert 'placeholder="Jugador (ej. Joel Orlando)"' in m.group(0)
    assert 'list="rosterList"' in m.group(0)
    assert '<datalist id="rosterList">' in html
    assert re.search(r'<div id="playerChips">', html)


def test_lineup_import_widgets(html):
    assert re.search(r'<button[^>]*id="loadLineupBtn"[^>]*>cargar lineup\.csv</button>', html)
    m = re.search(r'<input type="file" id="lineupFile"[^>]*>', html)
    assert m, "hidden lineup file input missing"
    assert 'accept=".csv,text/csv"' in m.group(0)
    assert "hidden" in m.group(0)


def test_lineup_csv_header_parse_and_roster_persistence(html):
    m = re.search(r'function parseLineupCsv\(text\) \{.*?\n\}', html, re.S)
    assert m, "parseLineupCsv missing"
    for col in ["player", "shirt_number", "position", "starter",
                "minute_in", "minute_out"]:
        assert col in m.group(0), f"lineup header column {col} not validated"
    assert 'localStorage.setItem("rivalkit_tagger_roster"' in html
    assert '"#" + p.shirt_number + " "' in html  # chip label: #7 Joel Orlando
    assert re.search(r'if \(!draft\.team\) \{ draft\.team = "rival"', html)


def test_saved_events_always_carry_trimmed_player(html):
    assert 'player: (playerEl.value || "").trim()' in html  # new events
    assert 'ev.player = (playerEl.value || "").trim();' in html  # in-place updates


# ---------- review queue + in-place editing ----------

def test_filter_bar_contracts(html):
    m = re.search(r'<div id="filters">.*?</div>', html, re.S)
    assert m, "filter bar #filters missing"
    bar = m.group(0)
    for f, label in [("all", "Todos"), ("pending", "Pendientes"), ("goal", "Goles"),
                     ("shot", "Remates"), ("set_piece", "Pelota parada"),
                     ("recovery", "Recuperos")]:
        assert f'data-filter="{f}"' in bar, f"missing data-filter={f}"
        assert label in bar, f"missing label {label}"


def test_matches_filter_semantics(html):
    m = re.search(r'function matchesFilter\(ev\) \{.*?\n\}', html, re.S)
    assert m, "matchesFilter missing"
    body = m.group(0)
    assert 'filter === "pending"' in body
    assert 'ev.status !== "confirmed"' in body
    assert '["corner", "free_kick", "penalty"].includes(ev.type)' in body
    assert 'ev.detail === "set_piece"' in body
    assert 'filter === "recovery"' in body


def test_edit_mode_state_and_buttons(html):
    assert "let editingIndex = null" in html
    assert '"ACTUALIZAR EVENTO (Enter)"' in html
    assert '"GUARDAR (Enter)"' in html
    assert re.search(r'<button[^>]*id="cancelEdit"[^>]*>Nuevo evento \(Esc\)</button>', html)
    assert re.search(r'<button[^>]*id="updateTs"[^>]*>usar ts actual</button>', html)


def test_row_click_loads_event_for_editing(html):
    m = re.search(r'function loadEvent\(idx\) \{.*?\n\}', html, re.S)
    assert m, "loadEvent missing"
    body = m.group(0)
    assert "editingIndex = idx;" in body
    assert "video.currentTime = ev.ts;" in body
    assert "video.pause();" in body
    assert "minuteEl.value = ev.minute;" in body
    assert 'playerEl.value = ev.player || "";' in body
    assert ("draft = {type: ev.type, team: ev.team, zone: Number(ev.zone), "
            "detail: ev.detail || null};") in body


def test_update_in_place_marks_confirmed_and_resets(html):
    assert "events[editingIndex]" in html
    assert 'ev.status = "confirmed";' in html
    assert re.search(r'if \(editTsOverride !== null\) ev\.ts = editTsOverride;', html)
    assert re.search(r'editingIndex = null;', html)  # reset after update/exit
    assert 'ev.player = (playerEl.value || "").trim();' in html


def test_event_rows_show_player_ts_and_status(html):
    assert re.search(r'\(ev\.player \|\| ""\)\.trim\(\) \? " · " \+ ev\.player\.trim\(\)', html)
    assert "ev.ts.toFixed(1)" in html
    assert 'ev.status === "confirmed" ? "✓" : "?"' in html
    assert 'className = "mini confirm-btn"' in html
    assert "events.splice(idx, 1);" in html


def test_imported_candidates_default_to_pending(html):
    assert 'ev.status = ev.status === "confirmed" ? "confirmed" : "pending";' in html


def test_candidate_navigation_buttons_and_keys(html):
    assert re.search(r'<button[^>]*id="prevCand"[^>]*>« Ant \(P\)</button>', html)
    assert re.search(r'<button[^>]*id="nextCand"[^>]*>Sig \(N\) »</button>', html)
    m = re.search(r'document\.addEventListener\("keydown".*?\n\}\);', html, re.S)
    assert m, "keydown handler missing"
    body = m.group(0)
    assert 'const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);' in body
    assert re.search(r'k === "n".*?stepCandidate\(1\)', body, re.S)
    assert re.search(r'k === "p".*?stepCandidate\(-1\)', body, re.S)


# ---------- direct exports ----------

def test_export_csv_contract(html):
    assert 'id="exportCsv"' in html and "Descargar events.csv" in html
    assert '"minute,event_type,team,zone,game_state,player,detail"' in html
    assert "a.minute - b.minute || a.ts - b.ts" in html
    assert ('rivalGoals > opponentGoals ? "winning" : '
            'rivalGoals < opponentGoals ? "losing" : "drawing"') in html
    assert 'r.type === "goal") { if (r.team === "rival") rivalGoals++' in html
    assert '"events.csv"' in html


def test_export_csv_escapes_cells(html):
    assert "function csvCell(" in html  # quoted cells for names with commas


def test_export_xml_contract(html):
    assert 'id="exportXml"' in html and "Descargar XML Nacsport/Once" in html
    fragments = ['"<file><ALL_INSTANCES>"', '"<instance><ID>"', '"</ID><start>"',
                 '"</start><end>"', '"</end><code>"', '"</code><label>"',
                 '"</label></instance>"', '"</ALL_INSTANCES></file>"']
    pos = [html.find(f) for f in fragments]
    missing = [f for f, p in zip(fragments, pos) if p == -1]
    assert not missing, f"missing XML fragments: {missing}"
    # the document wraps the joined instances: file -> ALL_INSTANCES -> instance...
    assert re.search(r'"<file><ALL_INSTANCES>" \+ instances\.join\(""\) \+ "</ALL_INSTANCES></file>"', html)
    assert '"events_nacsport.xml"' in html
