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

## Slice 3 (tasks 3.1-3.11): code done, 3.9-3.10 pending (user checks)

- [x] 3.1-3.4 `src/rivalkit/report.py`: constants, `_wrap`, `_block` flow cursor, `_data_box` (grey, rule separator), `summary_lines` (warning first when N < 5, singular "1 partido"), `data_facts`, 8 page builders in spec order, overflow stderr warning, `write_report` atomic (`PdfPages` on `.tmp`, `rc_context({"pdf.fonttype": 42})`, `os.replace`)
- [x] 3.5 `src/rivalkit/__main__.py`: argparse, in-process glob, combined errors `N error(s); no PDF written` exit 1, `wrote OUTPUT (8 pages, N matches)`, small-sample stderr warning, write-failure message exit 1, usage exit 2
- [x] 3.6 `tests/test_report.py` (7 tests: 8 A4 pages full/minimal notes, invalid CSV leaves output untouched, missing plan, usage exit 2, argument-order determinism, summary warning/singular, overflow warning exit 0)
- [x] 3.7-3.8 `.venv\Scripts\python -m pytest tests`: `57 passed`; sample `rival-report.pdf` generated (gitignored)
- [ ] 3.9 user visual check of the sample PDF
- [ ] 3.10 user manual Spanish verify of the sample PDF
- [x] 3.11 committed on `feat/rival-kit-3-report` as `feat(report): add 8-page PDF report and CLI`

## Slice 4 (tasks 4.1-4.7): done, 4.6 user skim pending

- [x] 4.1 `README.md`: overview, quick start, commands, flat-pipeline architecture, notes usage, data policy
- [x] 4.2 `docs/tagging-guide.md`: 18-zone grid, per-column rules, conventions (goals once, penalties, own goals, minute rules, recoveries both teams), Excel tips, tagging-time column, notes format and caps
- [x] 4.3 `docs/data-sources.md`: 2026-11-13 verification — YouTube streams unusable for tagging (frame-inspected), LPF Play as official source, Sofascore/FotMob/ESPN/ScoreBat coverage table, FotMob xG implication; Sofascore/FotMob/ESPN ToS reading still pending (task 1.1, user-owned)
- [x] 4.4 `outreach/cover-message.md`, `outreach/one-page-summary.md`, `outreach/public-post.md`: neutral Spanish, `{{...}}` placeholders, pointing to the short PDF
- [x] 4.5 `readme = "README.md"` added to `pyproject.toml`
- [ ] 4.6 user: full suite green on branch (57 passed); docs skim pending
- [x] 4.7 committed on `feat/rival-kit-4-docs` as `docs: add readme, tagging guide, data sources and outreach templates`

### Deviations (slice 4)

- Docs written without diacritics where practical to avoid encoding pitfalls in editors, matching the existing ASCII-style copy convention of the data example notes.
- `data-sources.md` records the 2026-11-13 verification (which superseded the 2026-10-31 link list) and flags the ToS reading as the remaining task-1.1 item.

### Deviations (slice 3)

- `set_piece_counts` (charts.py) now sorts categories deterministically (frequency, then key). Found by the argument-order determinism test: raw `value_counts` ties follow row order, and `events` row order follows CLI argument order because `load_matches` sorts matches but not events/lineup.
- Page 4 ("Sin pelota y transiciones") layout was compacted after the example data triggered a real overflow warning during apply.
- Match-plan instructions are wrapped at `WRAP_FULL` and numbered on their first line; the design only required "numbered instructions, as written".
- `write_report` cleans up the `.tmp` file on any exception (not only on rendering failure) so a crash mid-render never leaves a partial PDF.

## Deviations (slice 2a)

- Bench players 12-18 were given positions (DF/MF/FW) so every lineup row has one; the spec only requires the column to exist.

- Notes: each `[[key_players]]` entry requires `note` (error if missing), following the design text "needs a non-empty name and a text note".
- Notes: `summary` counts as present when identity, weaknesses or threats has any non-blank text (design: "all empty or blank" is missing).
- CSV: free-text columns (`match_id`, `rival_team`, `opponent`, `competition`, `player`, `shirt_number`, `position`) are only required to exist, as the design says; empty values are accepted.
- cp1252 fallback decodes with `errors="replace"` so undefined bytes never raise.
- The goal-count error reads `<folder>: rival goals: match.csv says N, events.csv has M rival goal events` (and `opponent`), per the design example.
