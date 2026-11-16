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

Task 1.1 (manual research) is user-owned and still open. Slices 2-4 not started.

## Deviations

- Notes: each `[[key_players]]` entry requires `note` (error if missing), following the design text "needs a non-empty name and a text note".
- Notes: `summary` counts as present when identity, weaknesses or threats has any non-blank text (design: "all empty or blank" is missing).
- CSV: free-text columns (`match_id`, `rival_team`, `opponent`, `competition`, `player`, `shirt_number`, `position`) are only required to exist, as the design says; empty values are accepted.
- cp1252 fallback decodes with `errors="replace"` so undefined bytes never raise.
- The goal-count error reads `<folder>: rival goals: match.csv says N, events.csv has M rival goal events` (and `opponent`), per the design example.
