# rival-report Specification

## Purpose

Defines the PDF composition (summary page plus phase-based sections), the mandatory data-sources and limitations note, the sample-size display and warning, and the CLI contract (inputs, output, exit codes, no PDF on invalid input). All user-visible PDF copy is Spanish, neutral professional register.

## ADDED Requirements

### Requirement: CLI invocation

The kit MUST be runnable as `python -m rivalkit <match-dir> [<match-dir> ...] -o <report.pdf>` plus one analyst notes input (see "Analyst notes input"; its option name is a design decision). At least one match folder MUST be required. `-o` MUST set the output path.

#### Scenario: Multiple folders
- GIVEN 5 valid match folders and a valid analyst notes input
- WHEN `python -m rivalkit m1 m2 m3 m4 m5 -o out.pdf` is run with that notes input
- THEN `out.pdf` is written and the process exits with code 0

#### Scenario: No folders given
- GIVEN no match folder arguments
- WHEN the command is run
- THEN a usage message is shown, the exit code is non-zero and no PDF is written

#### Scenario: Folder does not exist
- GIVEN a path that is not an existing folder
- WHEN the command is run
- THEN an error naming the path is shown, the exit code is non-zero and no PDF is written

### Requirement: Invalid input blocks the PDF

If any input fails `match-event-data` validation, the CLI MUST print every error (each with match folder, file, row number, column, offending value, allowed values), exit non-zero, and MUST NOT create or modify any PDF at the output path, including no partial or empty file.

#### Scenario: Invalid CSV
- GIVEN one folder with an invalid `minute` on row 4 of `events.csv`
- WHEN the command is run
- THEN the error with the folder, `events.csv` and row 4 is printed, the exit code is non-zero and no PDF exists at the output path

#### Scenario: Pre-existing output not overwritten
- GIVEN an existing `out.pdf` and an invalid input
- WHEN the command is run
- THEN `out.pdf` is left unchanged

#### Scenario: Errors across several matches
- GIVEN two folders, each with a different error
- WHEN the command is run
- THEN both errors are printed in one run

### Requirement: Page structure

A generated PDF MUST be A4 and MUST consist of a 1-page summary followed by exactly these 7 top-level sections, in this order, with these Spanish titles, one page each (8 pages in total):

1. Identidad y alineación
2. Con pelota
3. Sin pelota y transiciones
4. Pelota parada
5. Jugadores clave
6. Plan de partido
7. Fuentes de datos y limitaciones

"Jugadores clave" and "Plan de partido" are MANDATORY. The phase split (ataque organizado, transición ofensiva, transición defensiva, defensa organizada, pelota parada ofensiva, pelota parada defensiva) MAY appear as subsections inside "Con pelota", "Sin pelota y transiciones" and "Pelota parada", but MUST NOT appear as top-level sections. The page count MUST be deterministic for a given input, so a test can assert it.

#### Scenario: Page count
- GIVEN any valid input
- WHEN the PDF is generated
- THEN it has exactly 8 pages (1 summary + 7 sections)

#### Scenario: Section titles
- GIVEN a generated PDF
- WHEN its text is inspected
- THEN all 7 section titles appear in the listed order, the last one on the final page

#### Scenario: Page size
- GIVEN a generated PDF
- WHEN each page size is inspected
- THEN each page is A4

### Requirement: Chart-to-section mapping

Each chart from `rival-charts` MUST appear in at least one section. The lineup consistency and home/away splits MUST appear in "Identidad y alineación"; the shot map and goals scored breakdown MUST appear in "Con pelota"; the pressing proxy and goals conceded breakdown MUST appear in "Sin pelota y transiciones"; the set-piece view MUST appear in "Pelota parada", with rival and opponent set pieces shown separately.

#### Scenario: Every chart is placed
- GIVEN a generated PDF from example data
- WHEN its sections are inspected
- THEN shot map, goals breakdown, set-piece view, pressing proxy, lineup consistency and home/away splits each appear

### Requirement: Summary page content

The summary page MUST show: the rival team name, the date range of the matches analysed, the number of matches analysed, the record (wins, draws, losses) and goals for/against, and the analyst summary (identity, weaknesses to exploit, threats to neutralize) from the analyst notes. It MUST NOT contain more than one page of content.

#### Scenario: Matches analysed shown
- GIVEN 6 valid matches
- WHEN the PDF is generated
- THEN the summary page states that 6 matches were analysed

#### Scenario: Record shown
- GIVEN 3 wins, 1 draw and 1 loss
- WHEN the PDF is generated
- THEN the summary shows 3 wins, 1 draw and 1 loss

### Requirement: Analyst notes input

The CLI MUST accept exactly one analyst notes input per run (not one per match folder), which carries the analyst's own interpretation of the video. The file format is a design decision. The notes MUST carry:

- **Summary (REQUIRED):** the rival's identity in up to 2 lines, up to 3 weaknesses to exploit, and up to 3 threats to neutralize.
- **Observations per section (optional):** free text for any of the 7 sections.
- **Key players (optional input, mandatory section):** 3 to 4 players, each with a name and one line.
- **Match plan (REQUIRED):** concrete instructions.
- **Clip references (optional):** timestamps or links.

If the summary or the match plan is missing or empty, validation MUST fail with an actionable message naming the missing part, the exit code MUST be non-zero and no PDF MUST be written. Absent optional fields MUST render a neutral Spanish placeholder or omit the block, without error. When no key players are supplied, "Jugadores clave" MUST still be present with a neutral Spanish placeholder. Analyst text MUST be rendered as provided, not rewritten or generated. Data-derived facts (for example, the share of goals conceded after minute 75) MAY appear as supporting lines, clearly visually separated and labeled as data, from the analyst text.

#### Scenario: Missing match plan
- GIVEN valid match folders and notes with a summary but no match plan
- WHEN the command is run
- THEN an error says the match plan is required, the exit code is non-zero and no PDF is written

#### Scenario: Missing summary
- GIVEN notes with a match plan but no summary
- WHEN the command is run
- THEN an error says the summary is required, the exit code is non-zero and no PDF is written

#### Scenario: Only required parts supplied
- GIVEN notes with only a summary and a match plan
- WHEN the PDF is generated
- THEN it is written with 8 pages, optional blocks omitted or shown as neutral Spanish placeholders

#### Scenario: Analyst text kept apart from data
- GIVEN notes and data-derived supporting lines
- WHEN the PDF is generated
- THEN the analyst text appears as written and the data lines are visibly separated and labeled as data

#### Scenario: One notes input for many matches
- GIVEN 5 match folders and one notes input
- WHEN the command is run
- THEN the single notes input applies to the whole report

### Requirement: Single rival per report

All provided match folders MUST share the same `rival_team` value. A mix of different rival teams MUST be rejected as an input error before any PDF is written.

#### Scenario: Mixed rivals
- GIVEN two folders whose `rival_team` differ
- WHEN the command is run
- THEN an error names both values, the exit code is non-zero and no PDF is written

### Requirement: Sample-size warning

When fewer than 5 matches are analysed, the report MUST still be generated (exit code 0) and the summary page MUST show a visible warning, in Spanish, that the sample is small and patterns may not be representative. With 5 or more matches, the warning MUST NOT appear.

#### Scenario: Four matches
- GIVEN 4 valid matches
- WHEN the PDF is generated
- THEN the PDF is written, the exit code is 0 and the summary contains the sample-size warning

#### Scenario: Five matches
- GIVEN 5 valid matches
- WHEN the PDF is generated
- THEN the summary contains no sample-size warning

#### Scenario: One match
- GIVEN 1 valid match
- WHEN the PDF is generated
- THEN the PDF is written with the warning and the count "1 partido"

### Requirement: Mandatory data-sources and limitations note

Every generated PDF MUST include a data-sources and limitations note, in Spanish, with no option to omit it. The note MUST state at least: (a) data were hand-tagged from match video by a single tagger, with no cross-check; (b) metrics labeled as proxies are approximations; (c) no xG, xGA or PPDA figures are claimed because public data do not allow them; (d) findings are descriptive of the sample analysed and should be validated against video before use. The note MUST be the content of the final section, "Fuentes de datos y limitaciones", on the last page.

#### Scenario: Note present
- GIVEN any successful run
- WHEN the PDF text is inspected
- THEN the limitations note with all four statements is present

#### Scenario: No way to suppress
- GIVEN the CLI options
- WHEN inspected
- THEN no option exists to omit the note

### Requirement: Spanish copy

All user-visible PDF text (titles, section names, labels, observations, warnings, the limitations note) MUST be in Spanish, in a neutral professional register without regional slang. Source code, identifiers and CSV schema stay in English.

#### Scenario: Labels in Spanish
- GIVEN a generated PDF
- WHEN its text is inspected
- THEN labels such as "partidos analizados" appear and English UI strings do not

### Requirement: Deterministic output

Given identical input and the same output path, the report content MUST be the same, except for an optional generation date. The same set of folders in a different argument order MUST yield the same content ordering by match date.

#### Scenario: Argument order
- GIVEN the same folders passed in two different orders
- WHEN each run produces a PDF
- THEN match ordering inside the report follows match date in both
