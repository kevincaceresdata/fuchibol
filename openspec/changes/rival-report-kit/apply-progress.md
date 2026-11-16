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

## Slice 2b (tasks 2.4-2.9): code done, 2.8 pending (user visual check)

- [x] 2.4 `src/rivalkit/charts.py` aggregation: `LABELS`, `INTERVALS`, `select`, `zone_counts`, `goal_breakdown` (interval/detail/game_state), `set_piece_counts`, `pressing_proxy`, `lineup_summary`, `venue_splits`, `record`, `plain`
- [x] 2.5 drawing: `shot_map`, `zone_map`, `bar_chart`, `table`, `zone_legend` (Axes in/out, no pyplot/IO, "Sin datos" on empty, Spanish copy)
- [x] 2.6 `tests/test_charts.py` (13 tests: aggregation edge cases + rendering on example/empty data)
- [x] 2.7 `.venv\Scripts\python -m pytest tests`: `50 passed`
- [ ] 2.8 user visual check of zone legend / shot map orientation (PNGs rendered to `%TEMP%\opencode\fuchibol-check\` on 2026-11-09; zone 1 top-left of own half, "Ataque →" right, zone 17 centre of attacking end confirmed on the legend render)
- [x] 2.9 committed on `feat/rival-kit-2-charts` as `feat(charts): add zone aggregation and drawing functions`

### Deviations (slice 2b)

- The shot-map explanation line ("Primera línea: remates · segunda línea: goles") is drawn as a small caption above the pitch, next to the "Ataque →" marker; the design only required that the subtitle explain both label lines.
- `shot_map`/`zone_map` keep the empty-state "Sin datos" centred on the pitch (data coordinates) instead of axes coordinates, so the frame reads as an empty pitch.
- One test assertion was corrected during apply: a venue with zero matches reports `matches = 0` and NaN only for the per-match averages (the spec's "no data, not zero" applies to averages); the initial test expected the whole row to be NaN.

## Deviations (slice 2a)

- Bench players 12-18 were given positions (DF/MF/FW) so every lineup row has one; the spec only requires the column to exist.

- Notes: each `[[key_players]]` entry requires `note` (error if missing), following the design text "needs a non-empty name and a text note".
- Notes: `summary` counts as present when identity, weaknesses or threats has any non-blank text (design: "all empty or blank" is missing).
- CSV: free-text columns (`match_id`, `rival_team`, `opponent`, `competition`, `player`, `shirt_number`, `position`) are only required to exist, as the design says; empty values are accepted.
- cp1252 fallback decodes with `errors="replace"` so undefined bytes never raise.
- The goal-count error reads `<folder>: rival goals: match.csv says N, events.csv has M rival goal events` (and `opponent`), per the design example.
