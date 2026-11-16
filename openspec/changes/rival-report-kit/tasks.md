# Tasks: Rival Report Kit

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,470 authored (generated CSVs excluded): ~385 / ~390 / ~385 / ~310 |
| 400-line budget risk | High (every slice is within ~5% of the budget; slice 2 may exceed it) |
| Chained PRs recommended | Yes |
| Suggested split | Slice 1 -> Slice 2 (or 2a -> 2b) -> Slice 3 -> Slice 4 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (user, 2026-10-22) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Slice boundaries:
- Slice 1: scaffold and input contracts (`pyproject.toml`, `.gitignore`, `src/rivalkit/__init__.py`, `src/rivalkit/schema.py`, `tests/test_schema.py`) ~385.
- Slice 2: example data and charts ~390. Clean split point if it runs over 400: **2a** example data (generator, `data/example/notes.toml`, example-data test, ~125) and **2b** charts (`src/rivalkit/charts.py`, `tests/test_charts.py`, ~265). Tasks below are numbered so the split falls between 2.3 and 2.4.
- Slice 3: report and CLI (`src/rivalkit/report.py`, `src/rivalkit/__main__.py`, `tests/test_report.py`) ~385, including the overflow stderr warning.
- Slice 4: docs and outreach ~310 (non-code).

Notes:
- Chain strategy resolved by the user (2026-10-22): stacked-to-main. One PR per slice, each merged to `main` in order. Resolve `chained-pr` and `work-unit-commits` from `.atl/skill-registry.md` when planning the PRs.
- Work happens on a feature branch (repo is on `main` with no commits). Create the branch before the first commit.
- Never run builds. Dependencies are installed only into the project `.venv` (user approved, 2026-10-22); run tests and scripts with `.venv\Scripts\python`. Strict TDD is off; tests ship in the same slice as their behavior.
- Git identity is repo-local (`kevin-aiplayers`, GitHub noreply email). Commit messages are Conventional Commits with no AI attribution. Stacked branches: `feat/rival-kit-1-schema` (from `main`), `feat/rival-kit-2-charts`, `feat/rival-kit-3-report`, `feat/rival-kit-4-docs`. No push or PR without explicit user confirmation.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Package scaffold plus CSV and notes validation | PR 1 (base = tracker branch if feature-branch-chain) | `pytest tests/test_schema.py` | `python -c "from rivalkit.schema import load_notes"` after install | `pyproject.toml`, `.gitignore`, `src/rivalkit/__init__.py`, `src/rivalkit/schema.py`, `tests/test_schema.py` |
| 2 (2a) | Seeded example data and example notes | PR 2 (base = PR 1 branch) | `pytest tests/test_schema.py` | `python scripts/make_example_data.py` regenerates `data/example/m01..m05` identically | `scripts/`, `data/example/`, example test in `tests/test_schema.py` |
| 2 (2b) | Aggregation and drawing functions | PR 2 or PR 3 (base = previous PR branch) | `pytest tests/test_schema.py tests/test_charts.py` | Render each chart on example data into a `Figure` (covered by `tests/test_charts.py`) | `src/rivalkit/charts.py`, `tests/test_charts.py` |
| 3 | Report composition and CLI | PR 3/4 (base = previous PR branch) | `pytest tests/test_report.py` | `python -m rivalkit data/example/m* --notes data/example/notes.toml -o rival-report.pdf` | `src/rivalkit/report.py`, `src/rivalkit/__main__.py`, `tests/test_report.py` |
| 4 | Docs and outreach | last PR (base = previous PR branch) | `pytest` (full suite still green) | N/A: non-code, documents slices 1-3 | `README.md`, `docs/tagging-guide.md`, `docs/data-sources.md`, `outreach/` |

## Phase 0: Manual research (USER, before or alongside slice 1)

- [ ] 1.1 **MANUAL (user)**: open one real Primera Nacional 2026 match on Sofascore and on FotMob. Record the fields each site exposes (events, minutes, zones/coordinates, lineups, substitutions, xG availability) in `docs/data-sources.md`. Read and summarize each site's terms of service (scraping, reuse, attribution). Copy no data. This closes the proposal's research gap. The file may land before slice 4; slice 3 limitations text does not depend on it. Commit: `docs: record manual public-data field check`.

## Slice 1 / Phase 1: Scaffold and input contracts (~385 lines)

- [x] 1.2 Create `pyproject.toml`: setuptools src layout, `requires-python = ">=3.11"`, dependencies `pandas>=2.1`, `matplotlib>=3.7`, `mplsoccer>=1.2`, extra `dev = ["pytest>=8"]`, `[tool.pytest.ini_options] pythonpath = ["src"]`, `testpaths = ["tests"]`. Do not add a `readme` key yet (slice 4).
- [x] 1.3 Create `.gitignore`: video (`*.mp4 *.mkv *.mov *.avi *.m4v *.webm *.ts *.m2ts`), `*.kva`, `data/real/`, `*.pdf`, `*.pdf.tmp`, Python caches, `.venv/`, `build/`, `dist/`, `*.egg-info/`.
- [x] 1.4 Create empty `src/rivalkit/__init__.py`.
- [x] 1.5 Create `src/rivalkit/schema.py` part A: constants (`EVENT_TYPES`, `TEAMS`, `GAME_STATES`, `VENUES`, `DETAILS`, `ZONE_BANDS`, `ZONE_LANES`, `OPPOSING_HALF`, `NOTE_SECTIONS`), `ValidationError(errors)`, `zone_rect(zone)` per the design formula, and the text reader (`utf-8-sig` then `cp1252` fallback, delimiter detection from the header, cell stripping, enum lowercasing).
- [x] 1.6 In `src/rivalkit/schema.py` part B: checker closures (`integer`, `choice`, `iso_date`, `optional`) and `load_matches(folders)` with folder de-duplication, per-file checks, missing-file and missing-column handling with cascade suppression, the 11-starter and one-match-row rules, the goal-count cross-file check (only when the files involved are clean), the single `rival_team` cross-folder check, and `Dataset` construction after all checks pass (pandas conversion only then).
- [x] 1.7 In `src/rivalkit/schema.py` part C: `Notes` dataclass and `load_notes(path)` with `tomllib`, collect-all errors (missing file, invalid TOML with line and column, missing summary, missing plan, type checks, unknown keys listing allowed keys); caps are not enforced and text is never altered.
- [x] 1.8 Create `tests/test_schema.py` CSV tests with a `write_match(tmp_path, **overrides)` helper, parametrized on (mutation, expected substring). Cases: complete folder accepted; missing folder; missing file; missing column (other columns still checked); venue `neutral`; two `match.csv` rows; minute 121 / -1 / `12.5`; unknown event type; `detail` incompatible with type; zone 0 / 19 / `box`; empty required value; 10 starters; `minute_out < minute_in`; goal-count mismatch; mixed `rival_team` (both names in the error); two bad rows give two errors with correct row numbers; `;` delimiter; BOM; cp1252 file; unknown column ignored.
- [x] 1.9 In `tests/test_schema.py` add notes tests with inline TOML in `tmp_path`: missing summary; missing plan; blank instructions; `weaknesses = "x"` wrong type; unknown key; invalid TOML; minimal notes load with empty optional parts; text beyond the caps loads unchanged. Add one assert-based zone geometry test (`zone_rect(1)` about `(0, 66.67, 16.67, 33.33)`; `zone_rect(17)` in the right-hand centre strip).
- [x] 1.10 Create `.venv` in the project (`python -m venv .venv`) and install into it: `.venv\Scripts\python -m pip install -e .[dev]` (user approved, 2026-10-22). Never install outside `.venv`.
- [x] 1.11 Run `.venv\Scripts\python -m pytest tests/test_schema.py` and confirm it passes.
- [x] 1.12 Commit slice 1 on the feature branch: `feat(schema): add package scaffold and CSV/notes validation`. No AI attribution.

Acceptance (spec scenarios): match-event-data "Complete folder is accepted", "Missing file", "Invalid venue", "More than one data row", "Minute out of range", "Unknown event type", "Detail incompatible with event type", "Zone out of range", "Non-numeric zone", "Unknown column present", "Wrong number of starters", "Inverted substitution minutes", "Goal count mismatch", "Multiple errors reported together", "Missing required column", "Empty required value"; rival-report "Missing match plan", "Missing summary", "Only required parts supplied", "Mixed rivals".

## Slice 2a / Phase 2: Example data (~125 lines)

- [ ] 2.1 Create `scripts/make_example_data.py` (stdlib only: `csv`, `random.Random(2026)`, `pathlib`): writes `data/example/m01..m05/{match,events,lineup}.csv`. Fixed per match: date, opponent, venue, goal sequence. Seeded: shots, set pieces, recoveries. Game state computed walking events in minute order. Coverage by construction: every event type, all three game states (opponent scores first at least once), 3 home and 2 away, at least one substitution, own goal not required. Fictional names ("Atlético Ejemplo", "Club Muestra", ..., "Jugador 01".."Jugador 18").
- [ ] 2.2 Run `.venv\Scripts\python scripts/make_example_data.py`, then confirm `data/example/m01..m05` exist with three CSVs each.
- [ ] 2.3 Create `data/example/notes.toml` by hand in neutral Spanish for "Atlético Ejemplo": fills `[summary]`, `[plan]` (with `clips`), all 7 `[observations]` keys, and three `[[key_players]]` entries whose names exist in the generated lineups. The generator never touches this file. Add to `tests/test_schema.py` the example-data test: `load_matches([p for p in Path("data/example").iterdir() if p.is_dir()])` and `load_notes("data/example/notes.toml")` pass; every event type and game state present; both venues; at least one substitute; at least 5 matches.
- [ ] 2.3b Run `.venv\Scripts\python -m pytest tests/test_schema.py`. Commit (split point 2a): `feat(example): add seeded synthetic dataset and example notes`.

Acceptance (spec scenarios): match-event-data "Example data validates", "Example data is sufficient".

## Slice 2b / Phase 3: Charts (~265 lines)

- [ ] 2.4 Create `src/rivalkit/charts.py` aggregation: `LABELS` (Spanish, including `"no_data": "Sin datos"` and `"": "Sin especificar"`), `INTERVALS`, `select`, `zone_counts` (index 1..18, zeros kept), `goal_breakdown` (by interval / detail / game_state; right-closed intervals; 47 -> 46-60, 90 -> 76-90, 93 -> 91+), `set_piece_counts` (detail ignored for penalty), `pressing_proxy` (rival recoveries in zones 10-18, 0 for matches with none), `lineup_summary` (first row per match+player, non-starter with empty `minute_in` -> 0 minutes, end = max(90, last tagged minute), distinct XIs), `venue_splits` (NaN for a missing venue), `record`, `plain` (escape `$`). Remates = shot + goal rows excluding `own_goal`.
- [ ] 2.5 In `src/rivalkit/charts.py` add drawing: `shot_map`, `zone_map` (mplsoccer `Pitch(pitch_type="opta")` plus `Rectangle` per `zone_rect`, label with shots then goals line, "Ataque →" marker), `bar_chart`, `table` (NaN as "sin datos"), `zone_legend`. Axes in / Axes out, no pyplot, no IO; empty input draws the frame plus centred "Sin datos"; titles and labels in Spanish.
- [ ] 2.6 Create `tests/test_charts.py`. Aggregation (small hand-built frames): opponent rows excluded from rival zone counts; zone counts 3 shots + 1 goal; interval edges (47, 90, 93); `minute_in=60` with empty out -> 30 minutes; 5 identical elevens -> 1 distinct; home-only data -> away NaN; duplicate player row counted once; non-starter with empty `minute_in` -> 0 minutes; penalty with a detail counted as "penalty". Rendering: every drawing function on example data and on empty data returns an `Axes`, and empty shows "Sin datos" in `ax.texts` (`Figure().add_subplot()`); no title contains xG, xGA or PPDA; proxy chart labelled as proxy.
- [ ] 2.7 Run `.venv\Scripts\python -m pytest tests/test_schema.py tests/test_charts.py`.
- [ ] 2.8 **USER (visual)**: render the zone legend and one shot map to an image (a throwaway snippet or the first report in slice 3) and confirm zone numbering and orientation: zone 1 top-left of the own half, "Ataque →" to the right, zone 17 centre of the attacking end.
- [ ] 2.9 Commit slice 2 (or 2b if split): `feat(charts): add zone aggregation and drawing functions`.

Acceptance (spec scenarios): rival-charts "Aggregation across matches", "Zone counts", "Opponent events excluded", "Minute intervals", "Stoppage time", "Set pieces split by side", "Stable eleven", "Substitution minutes", "Both venues present", "Only home matches", "Proxy labeled", "No xG or PPDA", "No set pieces", "Chart titles are Spanish".

## Slice 3 / Phase 4: Report and CLI (~385 lines)

- [ ] 3.1 Create `src/rivalkit/report.py` copy and helpers: `SECTIONS`, `MIN_MATCHES = 5`, `PAGE_COUNT = 8`, `A4_INCHES`, `WRAP_FULL`, `WRAP_HALF`, Spanish constants, the `LIMITATIONS` note keeping statements (a) to (d) plus the extras from design, `_wrap` (textwrap per paragraph, keeps blank lines and words), `_text_block(fig, y, heading, lines, style) -> new y` (flow cursor), `summary_lines` (singular "1 partido"; sample warning first when N < 5), `data_facts` (each fact omitted when empty).
- [ ] 3.2 In `src/rivalkit/report.py` add the 8 page functions in spec order (Resumen; Identidad y alineación; Con pelota; Sin pelota y transiciones; Pelota parada; Jugadores clave; Plan de partido; Fuentes de datos y limitaciones) with header/footer ("Página k de 8"), chart titles with "N partidos", "Observaciones del analista" block per section page when present, "Lectura del analista" and the grey "Datos de la muestra" box separated by a rule, key-player cards with "Datos:" lines, and the zone legend plus match list on page 8.
- [ ] 3.3 **Overflow signal** in `src/rivalkit/report.py`: when the flow cursor passes the footer line on any page, record the page; `write_report` (or the page loop) emits to stderr `aviso: el texto de "<page>" excede la página; reduzca el texto`; exit code stays 0; text is never truncated.
- [ ] 3.4 In `src/rivalkit/report.py` add `write_report(data, notes, out)`: `Figure(A4)`, `PdfPages(out.tmp)` inside `rc_context({"pdf.fonttype": 42})`, `savefig` without `bbox_inches`, `os.replace(tmp, out)`, tmp removed on failure, parent folder created, returns pages written.
- [ ] 3.5 Create `src/rivalkit/__main__.py`: argparse (`match_dirs nargs="+"`, `--notes` required, `-o/--output` required), in-process wildcard expansion `sorted(glob.glob(arg)) or [arg]`, run both loaders and print all errors then `N error(s); no PDF written` (exit 1), success line `wrote OUTPUT (8 pages, N matches)`, stderr `warning: only N match(es) analysed; at least 5 are recommended` when N < 5, write failure message `error: cannot write OUTPUT: <reason> (close it if it is open in a PDF viewer)` (exit 1), usage errors exit 2.
- [ ] 3.6 Create `tests/test_report.py`: parametrized `main([...])` with full example notes and minimal notes (summary and plan only) -> exit 0, exactly 8 pages (`rb"/Type\s*/Page\b"` count), each `/MediaBox` within 1 pt of 595.28 x 841.89; invalid CSV copy (`shutil.copytree`, bad minute on row 4) with a pre-existing `out.pdf` -> exit 1, stderr has `events.csv:4: minute`, `out.pdf` bytes unchanged, no `.tmp`; notes without `[plan]` -> exit 1, stderr names the match plan, no PDF; no folders / no `--notes` / no `-o` -> exit 2; folder argument order does not change the output; `summary_lines` shows the warning with 4 matches, not with 5, and uses "1 partido" with 1 match; overflow warning printed to stderr for an over-long plan while exit stays 0.
- [ ] 3.7 Run `.venv\Scripts\python -m pytest tests/test_report.py` and the full suite `.venv\Scripts\python -m pytest`.
- [ ] 3.8 Generate the sample PDF with the `.venv` Python: `python -m rivalkit data/example/m* --notes data/example/notes.toml -o rival-report.pdf`. The `*.pdf` file is gitignored.
- [ ] 3.9 **USER (visual check)**: open `rival-report.pdf` and confirm 8 A4 pages, the zone legend on page 8 (numbering, "Ataque →"), no text overlap, charts readable, and the data box visibly separated from analyst text.
- [ ] 3.10 **USER (manual Spanish verify)**: confirm section titles appear in order with "Fuentes de datos y limitaciones" last on page 8; the four limitation statements (a) to (d) are present; analyst text appears exactly as written in `data/example/notes.toml`; no English UI strings in the PDF; no chart or text names xG, xGA or PPDA as a value.
- [ ] 3.11 Commit slice 3: `feat(report): add 8-page PDF report and CLI`. No AI attribution.

Acceptance (spec scenarios): rival-report "Multiple folders", "No folders given", "Folder does not exist", "Invalid CSV", "Pre-existing output not overwritten", "Errors across several matches", "Page count", "Section titles", "Page size", "Every chart is placed", "Matches analysed shown", "Record shown", "Missing match plan", "Missing summary", "Only required parts supplied", "Analyst text kept apart from data", "One notes input for many matches", "Mixed rivals", "Four matches", "Five matches", "One match", "Note present", "No way to suppress", "Labels in Spanish", "Argument order".

## Slice 4 / Phase 5: Docs and outreach (~310 lines)

- [ ] 4.1 Create `README.md`: overview, quick start (`pip install -e .[dev]`, the example command), commands, architecture paragraph (flat pipeline), notes usage, data policy (no real data or video committed, no scraping).
- [ ] 4.2 Create `docs/tagging-guide.md`: zone grid diagram, column guide per file, conventions (goals once as `goal`, own goals, penalties, minute `mm+1`, stoppage, recoveries for both teams), Excel/Google Sheets tips (CSV UTF-8, `;` delimiter), tagging-time column, notes file format and the documented caps.
- [ ] 4.3 Finalize `docs/data-sources.md` from task 1.1 findings if it has not landed already (read-only check that it names Sofascore, FotMob and the terms of service summary).
- [ ] 4.4 Create `outreach/cover-message.md`, `outreach/one-page-summary.md`, `outreach/public-post.md`: Spanish, team-agnostic templates with `{{CLUB}}`, `{{RIVAL}}`, `{{FECHA}}` placeholders, pointing to the short PDF.
- [ ] 4.5 Add the `readme = "README.md"` line to `pyproject.toml`.
- [ ] 4.6 **USER**: run `pytest` (full suite) to confirm nothing regressed; skim the docs for accuracy against slices 1 to 3.
- [ ] 4.7 Commit slice 4: `docs: add readme, tagging guide, data sources and outreach templates`.

Acceptance: the docs describe the contracts fixed in slices 1 to 3; the spec requirement "Mandatory data-sources and limitations note" stays consistent with `docs/data-sources.md`; the full `pytest` suite passes.
