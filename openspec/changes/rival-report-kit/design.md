# Design: Rival Report Kit

## Technical Approach

A linear, three-stage pipeline in a flat `src/rivalkit/` package, plus a thin CLI:

```
match folders --> schema.load_matches --> Dataset --+
notes.toml    --> schema.load_notes   --> Notes   --+--> report.write_report --> report.pdf
                  (parse + validate inputs)            (charts.* on A4 Figures, PdfPages)
```

- `schema.py` owns both input contracts and their validation:
  - the CSV match data, including the zone grid (spec `match-event-data`)
  - the analyst notes file (spec `rival-report`, "Analyst notes input")

  CSV files are parsed with the stdlib `csv` module and the notes with stdlib `tomllib`. Every error is collected before any typed object is built.
- `charts.py` owns aggregation and drawing (spec `rival-charts`). Aggregation is pure pandas and tolerates edge cases that the spec does not reject. Drawing functions receive a matplotlib `Axes` and data, draw, and return the `Axes`.
- `report.py` owns the composition of the 8 pages, the Spanish report copy, the text layout of analyst notes, the limitations page and the atomic PDF write (spec `rival-report`).
- `__main__.py` is the CLI: parse arguments, load both inputs, report every error or write the PDF, and map outcomes to exit codes.

This follows the proposal's approach and fixed decisions, and it matches the specs in `openspec/changes/rival-report-kit/specs/`. The specs are the contract: validation enforces only the rules the specs state. The one deliberate exception is a guard that keeps analyst text from being silently dropped.

## Architecture Decisions

### Decision: Flat linear pipeline; hexagonal layering rejected

**Choice**: Four modules (`schema`, `charts`, `report`, `__main__`). Each module is a pipeline stage, and the stages talk through two concrete frozen dataclasses: `Dataset` and `Notes`.
**Alternatives considered**: Hexagonal/clean layering (domain, ports, CSV and TOML adapters, PDF adapter, application service); a single script plus notebooks.
**Rationale**: The kit has two local input files, one output (PDF), no persistence, no network and no second implementation planned. Ports would be interfaces with one implementation each. Layering would roughly triple the file count, to about 12 files for about 800 lines of code. A pipeline that reads top to bottom serves both the portfolio reader and the weekly user. The `Dataset`/`Notes` boundary is already the seam where a refactor would start if a second input or output appears. A single script was rejected because it is hard to test and weak as a portfolio piece.

### Decision: Parse CSV with stdlib `csv`; pandas only after validation

**Choice**: Each CSV file is read as text and parsed with `csv.DictReader`. Every cell is validated as a raw string. `pd.DataFrame(rows)` and the type conversions run only when the whole input has no errors.
**Alternatives considered**: `pandas.read_csv` with dtype coercion; pandera or pydantic schemas.
**Rationale**: `DictReader.line_num` gives the exact physical line, which is the spreadsheet row when the header is row 1. `read_csv` skips blank lines by default, so its index drifts from file rows. It also coerces values silently (blank becomes NaN, `12.5` becomes a float). pandera or pydantic would add a dependency and impose their own error format, while the spec fixes the format. With this choice, pandas never sees invalid data.

### Decision: Collect-all validation with a fixed error format

**Choice**: `load_matches` and `load_notes` each raise one `ValidationError(errors: list[str])` when their list of problems is not empty. The CLI runs both loaders and prints the combined list in one run. Error lines take these forms:

```
<folder>/<file>:<row>: <column>: '<value>' <problem; allowed values or range>
<folder>/<file>: <file-level problem>
<folder>: <folder-level problem>
<notes path>: <problem naming the TOML key and the expected form>
```

Examples:

```
data/m01/events.csv:4: minute: '125' is not an integer from 0 to 120
data/m01/events.csv:7: event_type: 'tackle' is not one of shot, goal, corner, free_kick, penalty, recovery
data/m01/events.csv:9: detail: 'on_target' is not allowed for corner (allowed: direct, crossed, short, or empty)
data/m01/events.csv: missing columns: game_state
data/m01/lineup.csv: expected exactly 11 starters, found 10
data/m01/lineup.csv:5: minute_in, minute_out: minute_out 60 is lower than minute_in 70
data/m01: rival goals: match.csv says 2, events.csv has 1 rival goal events
data/m02/match.csv:2: rival_team: 'Club B' differs from 'Club A' in data/m01
data/m09: not an existing folder
notes.toml: the match plan is required: add [plan] with instructions = ["...", "..."]
notes.toml: the summary is required: add [summary] with identity, weaknesses and threats
notes.toml: summary.weaknesses must be a list of texts, for example weaknesses = ["...", "..."]
notes.toml: unknown key 'observations.con_pelota' (allowed: identity_and_lineup, in_possession, ...)
notes.toml: invalid TOML: <tomllib message with line and column>
```

Cascade suppression keeps the output actionable:
- A missing file skips that file's checks.
- A missing column skips row checks for that column only, as the spec requires.
- Cross-file checks (the goal counts) run only when the files involved have no errors.

**Alternatives considered**: Fail on the first error; keep the valid rows and drop the rest.
**Rationale**: The specs require exhaustive, row-numbered errors and no partial output. Hand-tagged CSV and hand-written notes are the trust boundary.

### Decision: Validate only what the specs state; aggregations tolerate the rest

**Choice**: The CSV validator enforces exactly the spec rules (see "CSV Contract"). Anything the spec leaves open is accepted, and the aggregations handle it:

| Case the spec does not reject | Handling |
|---|---|
| Same folder passed twice (or by overlapping wildcards) | `load_matches` de-duplicates folders by resolved path and loads each one once |
| Same `match_id` in two folders | Harmless. Matches are keyed internally by folder (a `match` column added to every frame), and `match_id` is only a tie-break when sorting |
| A player listed twice in one match's lineup | `lineup_summary` keeps the first row per (match, player) |
| `starter=false` with an empty `minute_in` | Counted as an unused substitute: 0 minutes |
| Empty `player` name | Shown as "(sin nombre)" |
| Any `shirt_number` or `position` value | Free text, never parsed. The lineup table shows each player's most frequent position |
| A non-empty `detail` on `penalty` or `recovery` | Ignored. Penalties are counted by type only, and recoveries are counted by zone only |

**Alternatives considered**: Extra design-level rejection rules (a substitute must have `minute_in`, players unique per match, `match_id` unique, `shirt_number` from 1 to 99, an empty `detail` on penalty and recovery).
**Rationale**: The spec is the contract (YAGNI). Each extra rule would need its own spec scenario, test and message. Tolerant handling costs about one line each, and no case can corrupt a chart.

### Decision: Tolerant parsing of spreadsheet exports, strict values

**Choice**:
- **Encoding**: `utf-8-sig` first, which also handles the BOM that Excel's "CSV UTF-8" export writes. On a decode error, fall back to `cp1252`, the ANSI CSV that Spanish-locale Excel saves by default. `# ponytail:` the fallback may mis-decode other legacy encodings; add an `--encoding` flag if that ever happens. The same text reader is reused for the notes file.
- **Delimiter**: detected from the header line. It is `;` when the header contains more `;` than `,` (Excel set to Spanish (Argentina) saves CSV with `;`), and `,` otherwise.
- **Cleanup**: whitespace is stripped from every cell. Enum cells are also lowercased, because Excel writes `TRUE` and taggers capitalise. Free text is only stripped.
- **Extra columns**: unknown CSV columns are ignored, as the spec requires. A tagger can add `tagging_minutes` or `notes` columns.

**Alternatives considered**: Require UTF-8 with commas; `csv.Sniffer`.
**Rationale**: The user works on Windows with Spanish names and probably tags in Excel or Google Sheets. These few lines remove the most likely first-run failures. Values stay strict, and every error names the allowed values. `Sniffer` is unreliable on small files.

### Decision: 18-zone grid, actor-relative, fixed numbering

**Choice**: 6 depth bands by 3 lanes, always recorded in the attacking direction of the team that performed the event (`team=rival` or `team=opponent`). Band 1 is next to that team's own goal, and band 6 is next to the goal it attacks. Lanes are left, centre and right as seen by that team facing its attack.

```
             own goal                              goal being attacked
             band1  band2  band3 | band4  band5  band6
left   lane    1      4      7   |  10     13     16
centre lane    2      5      8   |  11     14     17
right  lane    3      6      9   |  12     15     18
                 own half        |    opposing half (10-18)
```

`zone = (band - 1) * 3 + lane`. The opposing half is zones 10–18, the pressing proxy's set. Zone 17 roughly matches the central penalty area, and zones 13–15 are just outside the box.

**Plot mapping (verified)**: mplsoccer `Pitch(pitch_type="opta")`. The mplsoccer API reference for `mplsoccer.dimensions.opta_dims()` defines axes from 0 to 100 with `invert_y=False` and the origin at the bottom left. So y increases upwards, and with the attack going left to right, the attacker's left is the top strip. `schema.zone_rect(zone)` returns `(x0, y0, w, h)` in those units:

```
band = (zone - 1) // 3 + 1 ; lane = (zone - 1) % 3 + 1
x0 = (band - 1) * 100 / 6 ; w = 100 / 6
y0 = (3 - lane) * 100 / 3 ; h = 100 / 3      # lane 1 (left) -> top strip
```

Every zone map is drawn in the acting team's direction (attack to the right) with an "Ataque →" marker. No mirroring code is needed, because each title states whose events the map shows.
**Alternatives considered**: 12 or 20 zones; a fixed broadcast direction; eyeballed x/y.
**Rationale**: 18 zones is a common, teachable grid. It is fast to tag and robust to camera pan. Actor-relative recording matches how analysts reason, avoids flips at half-time, and is what the spec fixes. The geometry sits next to the grid constants in `schema.py`, where one test pins it.

### Decision: Zone maps drawn with mplsoccer pitch and matplotlib rectangles

**Choice**: `Pitch(pitch_type="opta").draw(ax=ax)` draws the pitch lines. Each zone is then drawn with `ax.add_patch(Rectangle(...))`, using `zone_rect(z)` for the position and the zone's value for the colour, plus `ax.text` for its label.
**Alternatives considered**: `pitch.bin_statistic(..., bins=(6, 3))` plus `heatmap` and `label_heatmap`.
**Rationale**: The labels are custom: shots and goals go on separate lines. `bin_statistic` would need a round trip from zone to centre point to bin, and then a mapping back to build the labels. Rectangles take about 8 lines and depend only on the verified geometry.

### Decision: Chart contract: pure aggregation plus Axes-in/Axes-out drawing, no pyplot

**Choice**:
- **Aggregation**: functions take DataFrames, or the `Dataset` when they need more than one frame, and return pandas objects keyed by English enum values. They do not use matplotlib.
- **Drawing**: functions have the shape `(ax, data..., title) -> Axes`. They draw only into the given `ax`. They never call `plt.*`, `savefig` or `show`, and they do no file IO. Category keys are translated to Spanish through `charts.LABELS` at draw time.
- **Empty input**: it never raises. The chart draws its frame plus a centred "Sin datos" text.
- **Figures**: `report.py` creates them with `matplotlib.figure.Figure(figsize=A4)`, so it does not use pyplot either.

**Alternatives considered**: Each chart creates its own figure; a Chart base class or registry; the pyplot state machine.
**Rationale**: The report places several charts on one A4 page, so each chart must draw into axes it is given. Avoiding pyplot means no global figure state, no GUI backend selection on Windows and no figure leaks. Plain functions are enough, while a class hierarchy would hold one method each.

### Decision: Fixed 8-page A4 report via `PdfPages`; phase split only as subsections

**Choice**: Every report has exactly 8 pages: the summary page plus one page per spec section, in spec order. The 8th page is "Fuentes de datos y limitaciones".
- **Page size**: the figure size is exactly A4 (`210/25.4 x 297/25.4` inches). `pdf.savefig(fig)` is called **without** `bbox_inches="tight"`, because that option would crop the page and change its size.
- **Text embedding**: rendering runs inside `matplotlib.rc_context({"pdf.fonttype": 42})`, so text is embedded as TrueType and stays searchable and extractable for verification.
- **Phase split as subsections**: some old phase names appear only as subsection headings:
  - "Ataque organizado" inside "Con pelota"
  - "Transición defensiva" and "Defensa organizada" inside "Sin pelota y transiciones"
  - "Ofensiva" and "Defensiva" inside "Pelota parada"
- **Transición ofensiva**: no subsection is drawn. Hand-tagged zones cannot describe transition sequences honestly, so the analyst covers it in the `in_possession` observation.

**Alternatives considered**: Spilling long content onto extra pages; a variable page count; reportlab or HTML to PDF.
**Rationale**: The spec requires exactly 8 deterministic pages. A fixed page list keeps the smoke test trivial. `PdfPages` was a fixed decision.

### Decision: Analyst notes as one TOML file read with stdlib `tomllib`

**Choice**: There is one notes file per run, given with `--notes notes.toml`. It is read with `tomllib.loads(text)`, where `text` comes from the same UTF-8/cp1252 reader as the CSV files, so a BOM is tolerated. Keys are English, matching the CSV convention, and values are Spanish analyst text:

```toml
[summary]                       # REQUIRED
identity = """Bloque medio 4-4-2, salida corta por la izquierda.
Muy agresivo en la presión tras pérdida."""          # up to 2 lines
weaknesses = ["...", "...", "..."]                   # up to 3
threats = ["...", "...", "..."]                      # up to 3

[plan]                          # REQUIRED
instructions = ["...", "...", "..."]
clips = ["m02 18:40 - presión tras saque de arco", "https://..."]   # optional

[observations]                  # optional, any subset of the 7 sections
identity_and_lineup = "..."
in_possession = "..."
out_of_possession = "..."
set_pieces = "..."
key_players = "..."
match_plan = "..."
sources = "..."

[[key_players]]                 # optional input; the section is always present
name = "Jugador 09"
note = "..."
```

`clips` lives under `[plan]` and is rendered on the "Plan de partido" page. This also avoids a TOML pitfall: a top-level key written after a table header silently belongs to that table.

Validation, collect-all:
- **Missing file or invalid TOML**: an error with tomllib's line and column.
- **Summary missing**: the `[summary]` table is absent, or `identity`, `weaknesses` and `threats` are all empty or blank. The error names the summary.
- **Plan missing**: `[plan]` is absent, or `instructions` is empty or blank. The error names the match plan.
- **Type checks**: `identity` and the observation values are texts. `weaknesses`, `threats`, `instructions` and `clips` are lists of texts. Each `key_players` entry needs a non-empty `name` and a text `note`.
- **Unknown keys are errors**, listing the allowed keys. This is unlike unknown CSV columns: a misspelled key such as `[plan] instrucions` or `observations.con_pelota` would otherwise drop analyst text silently from a report that might be sent.
- **Caps are not enforced**: the "up to 2 lines / up to 3 / 3 to 4 players" limits are documented guidance. Text is never truncated, rewritten or rejected for length.

**Alternatives considered**: Markdown with conventional headings (needs a hand-written parser and gives weak errors); YAML (needs PyYAML, a new dependency); JSON (hostile to hand-written multi-line Spanish text); one notes file per match (the spec forbids it).
**Rationale**: TOML is in the stdlib from Python 3.11, already the minimum. It supports multi-line strings and lists of tables, has a precise error position, and adds no dependency.

### Decision: Analyst text layout: flow layout with `textwrap`, analyst and data visibly separated

**Choice**:
- **Wrapping**: every analyst string goes through `_wrap(text, width)`. That function splits on newlines and applies `textwrap.wrap` to each paragraph, keeping blank lines. So words and order stay exactly as written, and only the line breaks are added.
- **Widths**: at 10 pt, `WRAP_FULL = 95` characters for full-width blocks and `WRAP_HALF = 45` for half-width blocks. `# ponytail:` character counts approximate glyph widths; measure with renderer text extents if lines overflow.
- **Flow layout**: text blocks are stacked with a running y cursor (`y = _text_block(fig, y, heading, lines, style) -> new y`). A longer block pushes the next ones down instead of overlapping them.
- **Analyst text**: black, 10 pt, under the heading "Lectura del analista" (summary) or "Observaciones del analista" (section pages).
- **Data facts**: in a light-grey box titled "Datos de la muestra (calculados a partir del etiquetado)", in grey 9 pt text, separated from the analyst text by a horizontal rule. On "Jugadores clave", each player's data line is grey and prefixed with "Datos:".
- **Sizing at the caps** (10 pt, line height about 0.19 in, A4 body about 10.2 in between header and footer):

| Page | Content at caps | Height |
|---|---|---|
| Resumen | header facts ~1.6 in; warning ~0.5 in; identity 2 lines + 3 weaknesses + 3 threats at up to 2 lines each, plus headings, ~3.7 in; data box 6 lines ~1.3 in; pointer ~0.3 in | ~7.4 in, so ~2.8 in of headroom |
| Jugadores clave | 4 cards (name in 12 pt bold, note up to 2 lines, data line) ~1.1 in each; observation ~1 in | ~5.4 in |
| Plan de partido | 6 instructions at up to 2 lines, clips list, observation | ~4 in |

Overflow signal: when the flow cursor passes the footer line on any page, the CLI prints a stderr warning naming the page (for example `aviso: el texto de "Plan de partido" excede la página; reduzca el texto`), and the exit code stays 0. Text is still never truncated, so nothing is dropped silently.

`# ponytail:` there is no shrink-to-fit. Add one if analysts routinely trigger the overflow warning.

**Alternatives considered**: Fixed text regions (overlap when text is longer); rejecting or truncating text beyond the caps (ruled out by the requirement that text is rendered as provided); reportlab for the text pages.
**Rationale**: The flow layout is about 20 lines, and the stdlib `textwrap` needs no dependency. The spec requires analyst text exactly as written and data lines visibly separated and labelled.

### Decision: Atomic output write

**Choice**: Both loaders finish before any file is touched. The PDF is rendered to `<output>.tmp` in the same folder, then moved into place with `os.replace(tmp, output)`. The temp file is removed on any failure, and the output's parent folder is created if missing.
**Alternatives considered**: Writing directly to the output path.
**Rationale**: The spec forbids any partial, empty or modified PDF on invalid input, and an existing `out.pdf` must stay unchanged. A crash halfway through rendering must never leave a corrupt report that might get sent. On Windows, `os.replace` fails when a PDF viewer has the target open, and the CLI reports that clearly.

### Decision: Spanish strings as module-level constants, no i18n framework

**Choice**:
- `charts.LABELS: dict[str, str]` maps enum and category keys to Spanish (`"corner": "Córner"`, `"winning": "Ganando"`, `"": "Sin especificar"`, `"no_data": "Sin datos"`).
- `report.py` holds `SECTIONS`, subsection headings, placeholders, the summary and data-fact templates and the `LIMITATIONS` note, as constants and f-strings.
- Chart titles are composed in `report.py`, which also adds the "N partidos" count.
- CLI messages are in English, like the code and the docs.

**Alternatives considered**: gettext or Babel; a `copy_es.py` module; YAML string files.
**Rationale**: There is one language and no translation workflow. Each module keeps the copy it renders in one reviewable place, with no extra file and no lookup layer.

### Decision: Free text is drawn literally

**Choice**: All free text goes through `charts.plain(text)` before drawing. That covers team and player names and every analyst string (for example "US$"). The function escapes `$` as `\$`.
**Rationale**: matplotlib parses `$...$` as mathtext, so a stray `$` in hand-typed text would crash rendering. The escape is a one-line guard at a trust-boundary value.

### Decision: Example data from a seeded stdlib generator, plus a hand-written example notes file

**Choice**: `scripts/make_example_data.py` uses only the stdlib (`csv`, `random.Random(2026)`, `pathlib`). It writes `data/example/m01` to `m05`, each folder holding `match.csv`, `events.csv` and `lineup.csv`.
- **Fixed per match**: date, opponent, venue and goal sequence.
- **Seeded volume**: shots, set pieces and recoveries are filled randomly from the fixed seed.
- **Game state**: computed by walking the events in minute order.
- **Coverage by construction**: every event type, all three game states (the opponent scores first at least once), 3 home and 2 away matches, and substitutions.

The generated CSVs are committed. The generator never touches `data/example/notes.toml`. That file is written by hand in neutral Spanish for "Atlético Ejemplo", and it fills every block, using three key players that exist in the generated lineups.

Names are clearly fictional: "Atlético Ejemplo", "Club Muestra", "Deportivo Prueba", "Sportivo Modelo", "Unión Ficticia", "Juventud Demo", and players "Jugador 01" to "Jugador 18".
**Alternatives considered**: Hand-written CSVs (about 190 lines of thin data); generating data at test time only.
**Rationale**: Realistic volumes (about 80 events per match) make the sample PDF credible. The generated files are excluded from the authored-line budget, and the spec requires shipped data.

### Decision: CLI expands wildcards in-process

**Choice**: Each positional argument becomes `sorted(glob.glob(arg)) or [arg]`.
**Rationale**: PowerShell and cmd do not expand `data/example/m*` for native programs, and the user is on Windows. POSIX shells pass already-expanded arguments, which glob returns unchanged. A pattern that matches nothing stays literal and is reported as "not an existing folder".

### Decision: Python 3.11+, setuptools src layout

**Choice**:
- `requires-python = ">=3.11"`.
- `setuptools` build backend, with automatic src-layout discovery.
- Dependencies: `pandas>=2.1`, `matplotlib>=3.7`, `mplsoccer>=1.2`. Dev extra: `pytest>=8`.
- `[tool.pytest.ini_options] pythonpath = ["src"]` and `testpaths = ["tests"]`.

**Alternatives considered**: 3.10; Poetry or uv-specific metadata; PEP 735 dependency groups.
**Rationale**:
- 3.11 provides `tomllib` in the stdlib, which the notes input needs.
- Python 3.10 reached end of life in October 2026.
- matplotlib is imported directly (`Figure`, `PdfPages`), so it is declared rather than relied on transitively.
- `pip install -e .[dev]` is the most widely supported dev install.
- The pytest `pythonpath` setting runs the tests without an editable install.
- The bounds are lower limits only.

## CSV Contract (per match folder)

Each match folder contains exactly `match.csv`, `events.csv` and `lineup.csv`. Column names and enum values are English and lowercase. Free text is unrestricted. Unknown columns are ignored.

### `match.csv` (exactly one data row)

| Column | Rule |
|---|---|
| `match_id` | free text |
| `date` | ISO `YYYY-MM-DD` (`date.fromisoformat`) |
| `rival_team` | free text; identical across all folders in one run |
| `opponent` | free text |
| `venue` | `home` \| `away` (rival's perspective) |
| `rival_goals`, `opponent_goals` | integer >= 0 |
| `competition` | free text |

### `events.csv` (zero or more rows)

| Column | Rule |
|---|---|
| `minute` | required; integer 0–120 |
| `event_type` | required; `shot` \| `goal` \| `corner` \| `free_kick` \| `penalty` \| `recovery` |
| `team` | required; `rival` \| `opponent` (who performed the event) |
| `zone` | required; integer 1–18, in the acting team's attacking direction |
| `game_state` | required; `winning` \| `drawing` \| `losing`, rival's perspective, score just **before** the event |
| `player` | may be empty |
| `detail` | may be empty. When present: goal `open_play`/`set_piece`/`penalty`/`own_goal`; shot `on_target`/`off_target`/`blocked`; corner and free_kick `direct`/`crossed`/`short`. Not checked for penalty or recovery |

Tagging conventions, documented in `docs/tagging-guide.md` and not enforced in code:
- **Goals**: a goal is tagged once, as `goal`, never also as `shot`.
- **Own goals**: tagged as `event_type=goal, detail=own_goal`, with `team` set to the team credited with the goal, so the goal-count check holds. Own goals are excluded from the shot maps.
- **Penalties**: a scored penalty is a `penalty` event plus a `goal` event with `detail=penalty`.
- **Minutes**: clock `mm:ss` is recorded as `mm + 1`. First-half stoppage time is recorded as `45`. Second-half stoppage time and extra time are recorded as 91 or later.
- **Recoveries**: tagged for both teams. Only the rival's recoveries in zones 10–18 feed the pressing proxy.

### `lineup.csv` (rival players only)

| Column | Rule |
|---|---|
| `player`, `shirt_number`, `position` | column required; values are free text, not checked |
| `starter` | `true` \| `false` |
| `minute_in` | empty or integer 0–120; empty means "from kickoff" |
| `minute_out` | empty or integer 0–120; empty means "to the final whistle"; must be >= `minute_in` when both are present |

File-level rules:
- `match.csv` has exactly one data row.
- `lineup.csv` has exactly 11 starters.

Cross-file rule: for each team, the number of `goal` events equals `rival_goals` or `opponent_goals`.

Cross-folder rule: there is a single `rival_team` value, and the error names both values when they differ.

## Validation Pipeline

```
load_matches(folders):
    de-duplicate folders by resolved path
    for folder:
        not a folder? ------------------------------------> "<folder>: not an existing folder"
        for file in (match.csv, events.csv, lineup.csv):
            exists? -> read text (utf-8-sig | cp1252) -> detect delimiter -> DictReader
            missing columns -> one error; skip those columns' row checks
            per-cell checks (rule table: column -> checker)
            per-row combination checks (detail vs event_type; minute_out >= minute_in)
            per-file checks (one match row; 11 starters)
        cross-file (only if involved files are clean): goal counts vs match.csv
    cross-folder: single rival_team
    errors? -> raise ValidationError ; else build typed DataFrames (+ match column), sort by (date, match_id, match)

load_notes(path):
    read text -> tomllib.loads -> unknown keys, types, required summary and plan
    errors? -> raise ValidationError ; else Notes
```

Checkers are small closures that return `None` or a problem string: `integer(lo, hi=None)`, `choice(values)`, `iso_date()`, and an `optional(...)` wrapper.

## Data Flow

```
CLI argv --glob--> folders, --notes path
   |
   +--> schema.load_matches(folders) --+
   +--> schema.load_notes(path) -------+--> any ValidationError? --> stderr (all errors) --> exit 1, no file touched
   |
   v Dataset(rival, matches, events, lineup) + Notes
   |
report.write_report(data, notes, out)
   |-- for (title, page_fn) in PAGES:              fixed 8 entries
   |      fig = Figure(A4); header and footer
   |      page_fn(fig, data, notes) --> charts.<aggregate> --> charts.<draw>(ax, ..., title)
   |                                 --> _text_block(...)  analyst text / data box
   |      pdf.savefig(fig)                          PdfPages(out.tmp)
   |-- os.replace(out.tmp, out)
   v
report.pdf  (8 A4 pages)
```

## Report Composition (8 A4 pages)

Every page has a header (section title and rival name) and a footer: `{rival} · {N} partido(s) analizado(s) · Datos etiquetados manualmente desde video · Página k de 8`. Every chart title includes `· {N} partidos` (singular `partido` when N = 1; the footer uses the same singular/plural rule instead of `(s)`). On every section page, an "Observaciones del analista" block at the bottom shows `observations.<key>` when it is present. When it is absent, the block is omitted.

| Page | Title (`observations` key) | Content | Functions |
|---|---|---|---|
| 1 | Resumen | Rival name, competition, date range; "N partidos analizados" ("1 partido analizado"); red warning box when N < 5; record (ganados/empatados/perdidos) and goals for/against. Then **Lectura del analista**: Identidad, Debilidades a explotar, Amenazas a neutralizar (an empty sub-list is omitted). Then the grey **Datos de la muestra** box. Last, the pointer "Ver limitaciones del análisis en la página 8" (deliberately not repeating the section title, so title-order checks stay unambiguous) | `summary_lines(data)`, `data_facts(data)`, `_text_block` |
| 2 | Identidad y alineación (`identity_and_lineup`) | Per-player table (Jugador, Posición, Titularidades, Minutos) sorted by minutes; "Onces iniciales distintos: k en N partidos"; home/away table (PJ, goles a favor/p, goles en contra/p, remates/p, remates recibidos/p; "sin datos" for a venue with no matches) | `table(lineup_summary(data))`, `table(venue_splits(data))` |
| 3 | Con pelota (`in_possession`) | Subsection "Ataque organizado": rival shot map, full width. Subsection "Goles a favor": by interval, by type, by game state | `shot_map(team="rival")`, 3 x `bar_chart(goal_breakdown(..., "rival", by))` |
| 4 | Sin pelota y transiciones (`out_of_possession`) | Subsection "Transición defensiva: presión (proxy)": rival recoveries in zones 10–18 per match (bars), with the average and a definition line. Subsection "Defensa organizada": opponent shot map (remates recibidos). Subsection "Goles en contra": by interval, type and game state | `bar_chart(pressing_proxy(data))`, `shot_map(team="opponent")`, 3 x `bar_chart(goal_breakdown(..., "opponent", by))` |
| 5 | Pelota parada (`set_pieces`) | Left column "Ofensiva (rival)", right column "Defensiva (oponentes)". Each column has a zone map of corners, free kicks and penalties, plus counts by type and delivery (`detail`). Set-piece and penalty goals for and against appear as a labelled data line | `zone_map(...)`, `bar_chart(set_piece_counts(events, team))` |
| 6 | Jugadores clave (`key_players`) | One card per `key_players` entry in input order: name (bold), note, and a grey "Datos:" line (titularidades, minutos, and goles when `events.player` matches) when the name exists in the lineups. Placeholder when the list is empty: "El analista no incluyó jugadores clave en las notas de este informe." | `_text_block`, `lineup_summary` |
| 7 | Plan de partido (`match_plan`) | Numbered `plan.instructions`, as written. "Clips de referencia" list when `plan.clips` is present; otherwise the block is omitted | `_text_block` |
| 8 | Fuentes de datos y limitaciones (`sources`) | Mandatory note (below); zone legend (numbered grid, "Ataque →"); list of matches analysed (date, opponent, venue, score) | `zone_legend`, `table` |

Metric definitions:
- **Remates** = `shot` rows plus `goal` rows, excluding `detail=own_goal`.
- **Shot map label**: the first line is the count of `shot` rows (remates sin gol), and the second is the goal count (`"1 gol"`, `"2 goles"`, omitted at zero). Colour intensity is remates per zone, and the subtitle explains both lines. With 3 shots and 1 goal, the zone shows 3 and 1, as the spec requires.
- **Goal intervals**: `0-15, 16-30, 31-45, 46-60, 61-75, 76-90, 91+`, right-closed. So 47 falls in 46-60, 90 in 76-90 and 93 in 91+.
- **Goal type**: the `detail` categories plus `""`, shown as "Sin especificar".
- **Minutes played**: `(minute_out or end) - (minute_in or 0)`, clamped at 0, where `end = max(90, the match's last tagged minute)`. A non-starter with an empty `minute_in` counts 0 minutes.
- **Distinct starting elevens**: the number of distinct sets of starter names across matches.
- **Pressing proxy**: the average per match of rival `recovery` events in zones 10–18, counting 0 for matches with none. The definition line reads: "Indicador aproximado (proxy) de presión: recuperaciones del rival en campo contrario (zonas 10–18), promedio por partido." No chart or text names a value xG, xGA or PPDA.
- **Data facts** (`data_facts`, each omitted when its data are empty):
  - most frequent attempt zone
  - share of goals from set pieces and penalties
  - share of goals conceded after minute 75
  - average of the pressing proxy
  - goals per match, home versus away
  - number of distinct starting elevens

Mandatory limitations note (page 8). The wording may be polished during apply, but it MUST keep statements (a) to (d):
- (a) "Datos etiquetados manualmente a partir del video de los partidos por una sola persona, sin verificación cruzada."
- (b) "Las métricas marcadas como proxy (indicador aproximado) son aproximaciones, no mediciones directas."
- (c) "No se informan xG, xGA ni PPDA: los datos públicos disponibles no permiten calcularlos."
- (d) "Los hallazgos describen solo la muestra analizada y deben validarse con el video antes de usarse."
- Also: "Ubicaciones registradas en una cuadrícula de 18 zonas, sin coordenadas exactas." "Los sitios de datos públicos solo se consultaron manualmente; no se extrajeron datos de forma automatizada." "Las observaciones, los jugadores clave y el plan de partido son interpretación del analista." The note also repeats the sample size, with the warning when N < 5.

Sample-size warning (summary page, only when N < 5): "Muestra reducida: {N} partido(s) analizado(s). Con menos de 5 partidos los patrones pueden no ser representativos."

## Interfaces / Contracts

```python
# src/rivalkit/schema.py
EVENT_TYPES = ("shot", "goal", "corner", "free_kick", "penalty", "recovery")
TEAMS = ("rival", "opponent")
GAME_STATES = ("winning", "drawing", "losing")
VENUES = ("home", "away")
DETAILS: dict[str, tuple[str, ...]]          # goal, shot, corner, free_kick only
ZONE_BANDS, ZONE_LANES = 6, 3                # 18 zones
OPPOSING_HALF = tuple(range(10, 19))         # zones 10-18
NOTE_SECTIONS = ("identity_and_lineup", "in_possession", "out_of_possession",
                 "set_pieces", "key_players", "match_plan", "sources")   # same order as report.SECTIONS

class ValidationError(Exception):
    errors: list[str]                        # every problem, already formatted

@dataclass(frozen=True)
class Dataset:
    rival: str
    matches: pd.DataFrame   # match (folder), match_id, date (Timestamp), rival_team, opponent, venue, rival_goals, opponent_goals, competition
    events: pd.DataFrame    # match, minute, event_type, team, zone, game_state, player, detail
    lineup: pd.DataFrame    # match, player, shirt_number, position, starter (bool), minute_in, minute_out (Int64, nullable)

@dataclass(frozen=True)
class Notes:
    identity: str
    weaknesses: tuple[str, ...]
    threats: tuple[str, ...]
    instructions: tuple[str, ...]
    clips: tuple[str, ...]
    observations: dict[str, str]             # keys from NOTE_SECTIONS
    key_players: tuple[tuple[str, str], ...] # (name, note), input order

def load_matches(folders: Sequence[Path]) -> Dataset: ...                # raises ValidationError
def load_notes(path: Path) -> Notes: ...                                # raises ValidationError
def zone_rect(zone: int) -> tuple[float, float, float, float]: ...      # (x0, y0, w, h), opta units 0-100
```

```python
# src/rivalkit/charts.py  -- aggregation: pure pandas, English keys
LABELS: dict[str, str]                                   # Spanish display labels, incl. "no_data": "Sin datos"
INTERVALS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90", "91+")

def select(events, team: str, types: Iterable[str]) -> pd.DataFrame: ...
def zone_counts(events) -> pd.Series: ...                               # index 1..18, zeros kept
def goal_breakdown(events, team: str, by: str) -> pd.Series: ...        # by: "interval" | "detail" | "game_state"
def set_piece_counts(events, team: str) -> pd.Series: ...               # "corner/crossed", ..., "penalty" (detail ignored)
def pressing_proxy(data: Dataset) -> pd.Series: ...                     # per match ("dd/mm vs X"), rival recoveries in 10-18
def lineup_summary(data: Dataset) -> tuple[pd.DataFrame, int]: ...      # per player: position, starts, minutes; distinct XIs
def venue_splits(data: Dataset) -> pd.DataFrame: ...                    # index home/away; NaN when no matches
def record(matches) -> dict[str, int]: ...                              # wins, draws, losses, goals_for, goals_against
def plain(text: str) -> str: ...                                        # escape "$" for matplotlib

# drawing: draw into ax, return ax; no IO, no pyplot; empty input -> "Sin datos"
def shot_map(ax, events, team: str, title: str) -> Axes: ...
def zone_map(ax, values: pd.Series, title: str, labels: pd.Series | None = None) -> Axes: ...
def bar_chart(ax, values: pd.Series, title: str, subtitle: str | None = None) -> Axes: ...
def table(ax, frame: pd.DataFrame, title: str) -> Axes: ...             # NaN rendered as "sin datos"
def zone_legend(ax) -> Axes: ...
```

```python
# src/rivalkit/report.py
SECTIONS = ("Identidad y alineación", "Con pelota", "Sin pelota y transiciones", "Pelota parada",
            "Jugadores clave", "Plan de partido", "Fuentes de datos y limitaciones")
MIN_MATCHES = 5
PAGE_COUNT = 8                         # summary + 7 sections
A4_INCHES = (210 / 25.4, 297 / 25.4)
WRAP_FULL, WRAP_HALF = 95, 45          # characters per line at 10 pt

def summary_lines(data: Dataset) -> list[str]: ...           # header facts; sample warning first when < MIN_MATCHES
def data_facts(data: Dataset) -> list[str]: ...              # data-derived supporting lines (Spanish)
def write_report(data: Dataset, notes: Notes, out: Path) -> int: ...   # pages written; atomic; OSError on write failure
```

```python
# src/rivalkit/__main__.py
def main(argv: list[str] | None = None) -> int: ...     # if __name__ == "__main__": sys.exit(main())
```

## CLI Contract

```
python -m rivalkit MATCH_DIR [MATCH_DIR ...] --notes NOTES.toml -o OUTPUT.pdf
```

| Aspect | Behaviour |
|---|---|
| Arguments | `match_dirs` (`nargs="+"`, wildcards expanded in-process); `--notes` required (exactly one file per run, applying to the whole report); `-o/--output` required. There is no option to omit the limitations note. |
| Success | Writes OUTPUT, overwriting any existing file. stdout: `wrote OUTPUT (8 pages, N matches)`. Exit **0**. |
| Small sample | As success, plus stderr `warning: only N match(es) analysed; at least 5 are recommended`. Exit **0**. |
| Invalid input | All CSV and notes errors on stderr, one per line, then `N error(s); no PDF written`. The output path is never created or modified. Exit **1**. Missing folders, a missing notes file, a missing summary or a missing match plan are all validation errors. |
| Write failure | stderr `error: cannot write OUTPUT: <reason> (close it if it is open in a PDF viewer)`. The temp file is removed and any existing output is unchanged. Exit **1**. |
| Usage error | argparse usage message, for example no folders, no `--notes` or no `-o`. Exit **2**. |

Unexpected exceptions (bugs) are not caught: they show a traceback, and the temp file is still removed.

Example: `python -m rivalkit data/example/m* --notes data/example/notes.toml -o rival-report.pdf`

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create | setuptools src layout, Python >= 3.11, deps, `dev` extra, pytest config. The `readme` key is added in slice 4 |
| `.gitignore` | Create | Video (`*.mp4 *.mkv *.mov *.avi *.m4v *.webm *.ts *.m2ts`), Kinovea annotations (`*.kva`), `data/real/`, `*.pdf` and `*.pdf.tmp` (generated reports, including real-club ones), Python caches, `.venv/`, `build/`, `dist/`, `*.egg-info/` |
| `src/rivalkit/__init__.py` | Create | Empty package marker |
| `src/rivalkit/schema.py` | Create | Constants, zone geometry, text reading, CSV validation and `Dataset`, notes validation and `Notes` |
| `src/rivalkit/charts.py` | Create | `LABELS`, tolerant aggregation and drawing functions |
| `src/rivalkit/report.py` | Create | Spanish copy, limitations note, text layout, 8 page functions, `summary_lines`, `data_facts`, `write_report` |
| `src/rivalkit/__main__.py` | Create | CLI |
| `scripts/make_example_data.py` | Create | Seeded stdlib generator for `data/example/m01..m05` |
| `data/example/m01..m05/{match,events,lineup}.csv` | Create (generated) | Synthetic dataset, committed |
| `data/example/notes.toml` | Create | Hand-written Spanish example notes covering every block |
| `tests/test_schema.py` | Create | CSV and notes validation, zone geometry, example-data validity and coverage |
| `tests/test_charts.py` | Create | Aggregation edge cases and tolerances; rendering on example data and empty data |
| `tests/test_report.py` | Create | Smoke tests (8 A4 pages, full and minimal notes); no PDF on invalid input or missing plan; sample warning |
| `README.md` | Create | Overview, quick start, commands, architecture paragraph, notes usage, data policy |
| `docs/tagging-guide.md` | Create | Zone grid diagram, column guide, conventions, Excel tips, tagging-time column, notes file format and caps |
| `docs/data-sources.md` | Create | Manual public-data field check (Sofascore/FotMob, one Primera Nacional match), no data copied |
| `outreach/cover-message.md`, `outreach/one-page-summary.md`, `outreach/public-post.md` | Create | Spanish, team-agnostic templates with placeholders (`{{CLUB}}`, `{{RIVAL}}`, `{{FECHA}}`), pointing to the short PDF |

Nothing is modified or deleted: the change is greenfield.

## Testing Strategy

`pytest` runs once the user has installed the dependencies. Strict TDD is off (`openspec/config.yaml`).

| Layer | What to test | Approach |
|-------|-------------|----------|
| Unit: schema (CSV) | Missing folder; missing file; missing column (one error, other columns still checked); bad enum; `minute` 121 / -1 / `12.5`; `zone` 0 / 19 / `box`; detail vs type; empty required event value; venue `neutral`; two `match.csv` rows; 10 starters; `minute_out < minute_in`; goal-count mismatch; mixed `rival_team` (both names in the error); two bad rows give two errors with correct row numbers; `;` delimiter; BOM; cp1252 file; unknown column ignored | A `write_match(tmp_path, **overrides)` helper; `pytest.mark.parametrize` over (mutation, expected substring such as `"events.csv:4: minute"`) |
| Unit: schema (notes) | Missing summary; missing plan; blank instructions; wrong type (`weaknesses = "x"`); unknown key; invalid TOML; minimal notes (summary and plan only) load with empty optional parts; text beyond the caps loads unchanged | Inline TOML strings written to `tmp_path`, parametrized |
| Unit: schema | Zone orientation: `zone_rect(1)` is about `(0, 66.67, 16.67, 33.33)`, and `zone_rect(17)` lies in the right-hand centre strip | One assert-based test |
| Unit: schema | Shipped example data and `notes.toml` validate. They cover every event type and game state, both venues, at least one substitute and at least 5 matches | `load_matches([p for p in Path("data/example").iterdir() if p.is_dir()])`, `load_notes(...)` |
| Unit: charts | Spec scenarios: opponent rows excluded from rival zone counts; intervals 47 -> 46-60, 90 -> 76-90, 93 -> 91+; `minute_in=60` with empty out -> 30 minutes; 5 identical elevens -> 1 distinct; home-only data -> away NaN ("sin datos"). Tolerances: duplicate player row counted once; non-starter with empty `minute_in` -> 0 minutes; penalty with a detail counted as "penalty" | One test function over small hand-built frames |
| Unit: charts | Every drawing function renders example data and empty data, and empty data shows "Sin datos" | `Figure().add_subplot()`; assert the return type and `ax.texts` |
| Smoke: report/CLI | With full example notes and with minimal notes (summary and plan only): exit 0, exactly 8 pages, every page A4 | Parametrized `main([...])`; count `rb"/Type\s*/Page\b"` and parse `/MediaBox` (±1 pt of 595.28 x 841.89) from the PDF bytes; no new dependency |
| Smoke: report/CLI | Invalid CSV (copied example, bad minute on row 4) with a pre-existing `out.pdf` gives exit 1, stderr contains `events.csv:4: minute`, `out.pdf` bytes are unchanged and no `.tmp` is left. Notes without `[plan]` give exit 1, stderr names the match plan, and no PDF is written | `shutil.copytree`, edit one line, `capsys` |
| Unit: report | `summary_lines` contains the warning with 4 matches and not with 5, and uses the singular "1 partido" with 1 match | Subsets of the example data |

Not automated, checked manually during verify: the Spanish text in the PDF (section titles in order with the last on page 8, the four limitation statements, analyst text exactly as written, data box labelled and separated, no English UI strings), the visual layout at the caps, and the zone legend. Type 42 fonts keep the PDF text searchable in any viewer. A pypdf text test was rejected because it would add a dependency.

## Slice Mapping (400-line review budget, `ask-on-risk`)

| Slice | Files | Authored lines (est.) | Stands alone because |
|---|---|---|---|
| 1. Scaffold and input contracts | `pyproject.toml`, `.gitignore`, `__init__.py`, `schema.py` (CSV and notes), `tests/test_schema.py` (CSV, notes and zone tests) | ~385 (20 + 15 + 230 + 120) | `pytest tests/test_schema.py` passes on tmp-path fixtures; no example data needed |
| 2. Example data and charts | `scripts/make_example_data.py`, `data/example/notes.toml`, generated CSVs (excluded from count), `charts.py`, `tests/test_charts.py`, plus the example-data test added to `tests/test_schema.py` | ~390 (80 + 35 + 205 + 60 + 12) | `pytest tests/test_schema.py tests/test_charts.py` passes; uses only `Dataset` and `Notes` |
| 3. Report and CLI | `report.py`, `__main__.py`, `tests/test_report.py` | ~385 (275 + 50 + 60) | End to end: the smoke tests assert 8 A4 pages, no PDF on invalid input, and the required notes |
| 4. Docs and outreach | `README.md`, `docs/tagging-guide.md` (including the notes format), `docs/data-sources.md`, `outreach/*.md`, `pyproject.toml` `readme` line | ~310 | Non-code; documents the contracts fixed in slices 1–3 |

The total is about 1,470 authored lines, against the proposal's 950. The extra comes from the analyst notes input (loader, layout and tests, about 200 lines), `test_charts.py`, and the generator, which keeps about 600 CSV lines out of review.

All four slices sit near the budget. If slice 2 exceeds 400 at apply time, split it at a clean seam: 2a is example data (generator, `notes.toml` and the coverage test, about 125 lines), and 2b is charts (about 265 lines).

The manual public-data field check, the proposal's first apply task, writes `docs/data-sources.md`. That file may land before slice 4, and the slice-3 limitations text does not depend on it.

## Threat Matrix

N/A: there is no routing, shell, subprocess, VCS/PR automation, executable-file classification or process-integration boundary. The CLI reads local CSV and TOML files and writes one local PDF in-process. Wildcard expansion uses `glob` path matching and executes nothing.

## Migration / Rollout

No migration required. The change is greenfield and additive, and each slice is its own work-unit commit or PR that can be reverted on its own.

## Open Questions

None. Resolved items:

- [x] mplsoccer `opta` orientation. The mplsoccer API reference for `mplsoccer.dimensions.opta_dims()` specifies axes from 0 to 100, `invert_y=False` and the origin at the bottom left. So y increases upwards, and `zone_rect` places lane 1 (left) in the top strip correctly.
- [x] Design-level CSV rules beyond the spec were dropped. The aggregations tolerate those cases (see "Validate only what the specs state").
- [x] The page count is fixed at 8 (summary plus 7 sections), as the spec requires.
