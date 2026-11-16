# Apply Progress: rival-report-kit

## Slice 1 (tasks 1.2-1.12): done

- [x] 1.2 `pyproject.toml`
- [x] 1.3 `.gitignore`
- [x] 1.4 `src/rivalkit/__init__.py`
- [x] 1.5-1.7 `src/rivalkit/schema.py` (constants, zone geometry, text reader, CSV validation, `Dataset`, notes)
- [x] 1.8-1.9 `tests/test_schema.py`
- [x] 1.10 `.venv` created, `pip install -e .[dev]` done inside it
- [x] 1.11 `.venv/Scripts/python -m pytest tests/test_schema.py`: `36 passed in 1.03s`
- [x] 1.12 committed on `feat/rival-kit-1-schema`

Task 1.1 (manual research) is user-owned and still open. Slice 2a done; 2b-4 not started.

## Slice 2a (tasks 2.1-2.3b): done

- [x] 2.1 `scripts/make_example_data.py` (stdlib, `random.Random(2026)`, fixed goals/lineups, seeded rest; ~82 events per match)
- [x] 2.2 `data/example/m01..m05/{match,events,lineup}.csv` generated
- [x] 2.3 `data/example/notes.toml` (neutral Spanish, 7 observation keys, 3 key players from generated lineups) + `test_example_data_loads_and_covers` in `tests/test_schema.py`
- [x] 2.3b `.venv/Scripts/python -m pytest tests/test_schema.py`: `37 passed`; committed on `feat/rival-kit-2-charts` as `feat(example): add seeded synthetic dataset and example notes`

## Deviations (slice 2a)

- Bench players 12-18 were given positions (DF/MF/FW) so every lineup row has one; the spec only requires the column to exist.

- Notes: each `[[key_players]]` entry requires `note` (error if missing), following the design text "needs a non-empty name and a text note".
- Notes: `summary` counts as present when identity, weaknesses or threats has any non-blank text (design: "all empty or blank" is missing).
- CSV: free-text columns (`match_id`, `rival_team`, `opponent`, `competition`, `player`, `shirt_number`, `position`) are only required to exist, as the design says; empty values are accepted.
- cp1252 fallback decodes with `errors="replace"` so undefined bytes never raise.
- The goal-count error reads `<folder>: rival goals: match.csv says N, events.csv has M rival goal events` (and `opponent`), per the design example.
