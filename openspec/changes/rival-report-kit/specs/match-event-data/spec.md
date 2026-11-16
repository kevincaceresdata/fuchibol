# match-event-data Specification

## Purpose

Defines the per-match CSV contract (events, match metadata, lineups), the zone grid, the allowed enums, the validation rules with row-numbered errors, and the synthetic example dataset. Hand-tagged CSV is the trust boundary: nothing invalid may reach charts or the report.

## ADDED Requirements

### Requirement: Match folder layout

A match MUST be one folder containing exactly three CSV files: `match.csv` (one data row), `events.csv` (zero or more rows) and `lineup.csv` (one row per player). A folder missing any of these files MUST be reported as invalid.

#### Scenario: Complete folder is accepted
- GIVEN a folder with `match.csv`, `events.csv` and `lineup.csv`, all valid
- WHEN the folder is loaded
- THEN the match is accepted

#### Scenario: Missing file
- GIVEN a folder without `lineup.csv`
- WHEN the folder is loaded
- THEN an error naming the folder and the missing file is reported

### Requirement: Match metadata contract

`match.csv` MUST contain exactly one data row with the columns `match_id`, `date` (ISO `YYYY-MM-DD`), `rival_team`, `opponent`, `venue` (`home` or `away`, from the rival team's perspective), `rival_goals` and `opponent_goals` (non-negative integers), and `competition`. Column names and enum values MUST be English; free-text values (team names) are unrestricted.

#### Scenario: Invalid venue
- GIVEN `match.csv` with `venue` equal to `neutral`
- WHEN validated
- THEN an error is reported for that file and row naming column `venue` and the allowed values

#### Scenario: More than one data row
- GIVEN `match.csv` with two data rows
- WHEN validated
- THEN an error is reported stating exactly one row is required

### Requirement: Event contract

`events.csv` MUST contain the columns `minute`, `event_type`, `team`, `zone`, `game_state`, `player` and `detail`. Required values: `minute`, `event_type`, `team`, `zone`, `game_state`. `player` and `detail` MAY be empty.

- `minute` MUST be an integer from 0 to 120 inclusive.
- `event_type` MUST be one of: `shot`, `goal`, `corner`, `free_kick`, `penalty`, `recovery`.
- `team` MUST be `rival` or `opponent`.
- `game_state` MUST be one of `winning`, `drawing`, `losing`, always from the rival team's perspective.
- `detail` MUST be, when present, one of the values allowed for its event type: for `goal` — `open_play`, `set_piece`, `penalty`, `own_goal`; for `shot` — `on_target`, `off_target`, `blocked`; for `corner` and `free_kick` — `direct`, `crossed`, `short`. An empty `detail` is always allowed.

#### Scenario: Valid event row
- GIVEN an event row `minute=34, event_type=shot, team=rival, zone=14, game_state=drawing`
- WHEN validated
- THEN no error is reported for that row

#### Scenario: Minute out of range
- GIVEN an event row with `minute=125`
- WHEN validated
- THEN an error names the file, the row number, column `minute` and the allowed range 0-120

#### Scenario: Unknown event type
- GIVEN an event row with `event_type=tackle`
- WHEN validated
- THEN an error names the file, the row number, column `event_type` and the allowed values

#### Scenario: Detail incompatible with event type
- GIVEN an event row with `event_type=corner` and `detail=on_target`
- WHEN validated
- THEN an error names the row and column `detail`

### Requirement: Zone grid

The pitch MUST be divided into 18 zones numbered 1 to 18: 3 lanes (left, centre, right, as seen from the tagged team's attacking direction) by 6 depth bands from the tagged team's own goal line to the opposing goal line. Zones MUST be expressed in the tagged team's attacking direction: for `team=opponent` events, the zone MUST still be recorded in the attacking direction of the team that performed the event. A `zone` outside 1-18 or non-integer MUST be invalid. The exact zone numbering MUST be documented in the tagging guide.

#### Scenario: Zone out of range
- GIVEN an event row with `zone=19`
- WHEN validated
- THEN an error names the file, row number, column `zone` and the range 1-18

#### Scenario: Non-numeric zone
- GIVEN an event row with `zone=box`
- WHEN validated
- THEN an error names column `zone` and states an integer 1-18 is required

### Requirement: Optional coordinates are not part of the contract

Columns `x` and `y` are out of scope. Extra, unknown columns MUST be ignored without error.

#### Scenario: Unknown column present
- GIVEN `events.csv` with an extra column `x`
- WHEN validated
- THEN no error is reported and the column has no effect

### Requirement: Lineup contract

`lineup.csv` MUST contain the columns `player`, `shirt_number`, `position`, `starter` (`true` or `false`), `minute_in` and `minute_out` (integers 0-120; an empty `minute_in` means on the pitch from kickoff for a starter and did not play for a non-starter; an empty `minute_out` means to the final whistle). A match MUST have exactly 11 starters. `minute_out` MUST NOT be lower than `minute_in`.

#### Scenario: Wrong number of starters
- GIVEN a `lineup.csv` with 10 rows where `starter=true`
- WHEN validated
- THEN an error states that exactly 11 starters are required and reports the count found

#### Scenario: Inverted substitution minutes
- GIVEN a lineup row with `minute_in=70` and `minute_out=60`
- WHEN validated
- THEN an error names the row and the two columns

### Requirement: Cross-file consistency

The number of `goal` events with `team=rival` SHOULD equal `rival_goals` in `match.csv`, and likewise for the opponent. A mismatch MUST be reported as a validation error. A `goal` event with `detail=penalty` SHOULD NOT be required to have a matching `penalty` event.

#### Scenario: Goal count mismatch
- GIVEN `match.csv` with `rival_goals=2` and `events.csv` containing one rival goal
- WHEN validated
- THEN an error names the match folder and both counts

### Requirement: Row-numbered, exhaustive, actionable errors

Validation MUST collect all errors across all files and all matches before reporting; it MUST NOT stop at the first error. Each error MUST identify the file (including the match folder), the data row number as the user sees it in a spreadsheet (header is row 1), the column, the offending value and what is allowed. Missing required columns MUST be reported once per file, naming the missing columns. Validation MUST NOT produce partial output for invalid input.

#### Scenario: Multiple errors reported together
- GIVEN `events.csv` with a bad `minute` on row 3 and a bad `zone` on row 7
- WHEN validated
- THEN both errors are reported in a single result, each with its own row number

#### Scenario: Missing required column
- GIVEN `events.csv` without the `game_state` column
- WHEN validated
- THEN one error names the file and the missing column, and row-level checks for that column are skipped

#### Scenario: Empty required value
- GIVEN an event row with an empty `event_type`
- WHEN validated
- THEN an error names the row and column `event_type`

### Requirement: Synthetic example dataset

The repository MUST ship at least 5 match folders under `data/example/` for fictional teams only. Every example match MUST pass validation. The example data MUST contain no real club, player or footage-derived information, and MUST cover every event type, every game state, both venues and substitutions, so that every chart and section can render.

#### Scenario: Example data validates
- GIVEN the shipped `data/example/` match folders
- WHEN validated
- THEN no errors are reported

#### Scenario: Example data is sufficient
- GIVEN the shipped example data
- WHEN counted
- THEN at least 5 distinct matches exist, with both `home` and `away` venues
