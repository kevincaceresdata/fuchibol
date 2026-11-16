# rival-charts Specification

## Purpose

Defines how validated events from N matches are aggregated into the chart set used by the report: zone-based shot and set-piece maps, goal breakdowns, lineup consistency and home/away splits, plus the labeling rules for proxies. All chart text is user-visible and MUST be in Spanish (neutral professional register).

## ADDED Requirements

### Requirement: Charts consume validated data only

Charts MUST be produced only from data that passed `match-event-data` validation. Aggregation MUST combine all provided matches, with each chart stating the number of matches it is based on.

#### Scenario: Aggregation across matches
- GIVEN 5 valid matches with 4 rival shots each
- WHEN the shot map is built
- THEN it reflects 20 shots and states it is based on 5 matches

### Requirement: Shot map by zone

The shot map MUST show rival shots and goals aggregated per zone on the 18-zone grid, with per-zone counts visible. Opponent events MUST NOT be mixed into the rival shot map. Goals MUST be distinguishable from non-goal shots.

#### Scenario: Zone counts
- GIVEN rival events: 3 shots and 1 goal in zone 14
- WHEN the shot map is built
- THEN zone 14 displays 3 shots and 1 goal

#### Scenario: Opponent events excluded
- GIVEN an event with `team=opponent, event_type=shot`
- WHEN the rival shot map is built
- THEN that event does not appear in it

### Requirement: Goals breakdown

The report MUST provide goals scored and goals conceded broken down (a) by 15-minute interval, (b) by goal type (`detail`: open play, set piece, penalty, own goal) and (c) by game state at the time of the goal.

#### Scenario: Minute intervals
- GIVEN a rival goal at minute 47 and another at minute 90
- WHEN goals by minute are built
- THEN they fall in the 46-60 and 76-90 intervals respectively

#### Scenario: Stoppage time
- GIVEN a goal at minute 93
- WHEN goals by minute are built
- THEN it is included in a final interval covering 91 and later

### Requirement: Set-piece map

The set-piece view MUST show corners, free kicks and penalties by zone and delivery type (`detail`), for the rival team, and MUST present conceded set pieces (`team=opponent`) separately.

#### Scenario: Set pieces split by side
- GIVEN 4 rival corners and 2 opponent corners
- WHEN the set-piece view is built
- THEN rival corners and opponent corners are shown separately with counts 4 and 2

### Requirement: Lineup consistency

The lineup view MUST show, per player, the number of matches started and the minutes played across the provided matches, and MUST show how many distinct starting elevens were used. A player's minutes MUST be derived from `minute_in` and `minute_out` (for a starter, an empty `minute_in` defaults to 0; a non-starter with an empty `minute_in` did not play and counts 0 minutes; an empty `minute_out` defaults to 90, or the match's last tagged minute when greater than 90).

#### Scenario: Stable eleven
- GIVEN 5 matches with the same 11 starters
- WHEN lineup consistency is built
- THEN it reports 1 distinct starting eleven

#### Scenario: Substitution minutes
- GIVEN a player with `minute_in=60` and empty `minute_out` in a 90-minute match
- WHEN minutes played are computed
- THEN the player has 30 minutes for that match

### Requirement: Home and away splits

The splits view MUST compare home and away matches on: goals scored, goals conceded, shots taken and shots conceded, each as per-match averages, along with the match count for each venue. A venue with zero matches MUST be shown as having no data, not as zero.

#### Scenario: Both venues present
- GIVEN 3 home and 2 away matches
- WHEN splits are built
- THEN averages are computed per venue over 3 and 2 matches respectively

#### Scenario: Only home matches
- GIVEN only home matches
- WHEN splits are built
- THEN the away side is labeled as having no data

### Requirement: Proxies are labeled as proxies

A metric standing in for something that needs full event data (for example a pressing indicator instead of PPDA) MUST be displayed with an explicit label that it is a proxy and with a one-line definition of what it counts. The kit MUST NOT display xG, xGA, PPDA or any model-derived metric or name a proxy as such a metric.

The pressing proxy MUST be defined as the average per match of rival `recovery` events located in the opposing half of the pitch. The exact zone set follows the zone numbering fixed in the tagging guide and MUST be stated in the chart's definition line.

#### Scenario: Proxy labeled
- GIVEN the pressing-proxy chart
- WHEN rendered
- THEN its title or subtitle contains the word "proxy" in Spanish ("proxy" or "indicador aproximado") and a definition line

#### Scenario: No xG or PPDA
- GIVEN any chart or text produced by the kit
- WHEN inspected
- THEN none presents a value named xG or PPDA

### Requirement: Small and empty data handling

A chart whose input is empty (for example no set pieces in the sample) MUST still render with a visible "sin datos" ("no data") message instead of failing or being silently omitted.

#### Scenario: No set pieces
- GIVEN matches with no corner, free kick or penalty events
- WHEN the set-piece view is built
- THEN it renders a "Sin datos" message and does not raise an error

### Requirement: Spanish chart copy

All user-visible chart text (titles, axis labels, legends, zone labels, empty-state messages) MUST be in Spanish, neutral professional register. Identifiers and CSV values stay English.

#### Scenario: Chart titles are Spanish
- GIVEN any chart
- WHEN rendered
- THEN its visible text is Spanish (for example "Mapa de remates")
