# Proposal: Rival Report Kit

## Intent

**Problem.** Argentine second-tier clubs (Primera Nacional, B Metro, Federal A) employ video analysts, but public data for these leagues is thin and match-level depth is unverified. Coaches rely on annotated video and value short, clear, relevant material. Nobody turns that video into a repeatable, structured view of an upcoming opponent.

**Career goal.** The user is a data analyst targeting a football-analyst job. This kit serves two purposes at once:

1. **Portfolio piece**: a small, tested, readable Python pipeline that shows analytical and engineering judgment.
2. **Weekly outreach tool**: a short opposition ("rival") PDF that a head coach can read in minutes, produced on a weekly cadence.

**Value proposition.** A data layer on top of video, not a replacement for the video analyst. The user tags match video into CSV and interprets the output. The kit validates, aggregates, charts and lays out the PDF.

**Why now.** Nothing exists yet (greenfield). The outreach loop cannot start without a working kit and a credible sample report.

**Success looks like.** One command turns a folder of hand-tagged matches into a short, honest PDF that states its sources, sample size and limitations.

## Scope

### In Scope
- `src/rivalkit/` flat package: `schema.py`, `charts.py`, `report.py`, `__main__.py` (thin CLI), plus `pyproject.toml`.
- Per-match CSV contract with a **zone grid** as the primary location field. Validation at the CSV boundary: required columns, enums (event type, game state), minute 0–120, zone in range, row-numbered error messages.
- Chart set: shot map (zones), goals by minute / type / game state, set-piece map, lineup consistency, home/away splits. Metrics that would need full event data (for example a pressing indicator instead of PPDA) appear only as **explicitly labeled proxies**.
- PDF via matplotlib `PdfPages`, A4: a 1-page summary plus 6–8 pages in about 7 phase-based sections. A **data-sources and limitations note is always present**.
- The report always shows the number of matches analysed and flags samples under 5 matches.
- CLI: `python -m rivalkit <match-dir> [<match-dir> ...] -o report.pdf`. Invalid input exits non-zero, lists every error with its row number, and writes no PDF.
- Synthetic example data for fictional teams: at least 5 small matches, so the repository runs and can be published without real-club data.
- pytest: schema validation tests plus one smoke test (example data to PDF with the expected page count).
- Docs: `README.md`, `docs/tagging-guide.md`, `docs/data-sources.md` (records the manual public-data field check).
- Outreach kit templates in `outreach/`: cover message, one-page summary, public-post version. They are team-agnostic and use placeholders.
- Repository hygiene: a `.gitignore` that excludes video files and a local real-data directory.

### Out of Scope
- Scrapers or automated collection from Sofascore, FotMob or FBref (terms of service unread).
- xG model, PPDA, any ML.
- Dashboards: Power BI, Excel, HTML. An HTML dashboard may come later as a separate change.
- x/y or pixel coordinates (Kinovea is used only to locate timestamps). Optional x/y columns are deferred to a later change.
- Video acquisition, storage or embedding.
- Choosing a target club, producing a real-club report, or sending anything to a club.
- PyPI packaging, CI pipelines, multi-tagger workflows.

## Capabilities

### New Capabilities
- `match-event-data`: per-match CSV contract (events, match metadata, lineups), zone grid definition, enums, validation rules with row-numbered errors, and the synthetic example dataset that must pass validation.
- `rival-charts`: aggregation of validated events across N matches into the chart set, zone-based shot and set-piece maps, and the labeling rules for proxies.
- `rival-report`: PDF composition (summary page plus sections), the mandatory data-sources and limitations note, sample-size display with a warning under 5 matches, and the CLI contract (inputs, output path, exit codes, no PDF on invalid input).

### Modified Capabilities
None. `openspec/specs/` is empty.

Docs and the outreach templates are non-behavioral deliverables. They are tracked in tasks, not in specs.

## Approach

Linear pipeline, one module per stage:

```
video (user tags by hand) -> data/<match>/*.csv -> schema.validate -> charts -> report (PdfPages) -> report.pdf
```

Technical defaults, adopted from the exploration recommendation:

| Decision | Choice | Rationale |
|---|---|---|
| PDF engine | matplotlib `PdfPages`, A4 | No extra dependency (matplotlib already comes with mplsoccer), one rendering path, vector output, safe on Windows. Revisit reportlab only if text-heavy pages look poor. |
| Location field | Zone grid ID (about 18 zones; design fixes the grid) | Fast to tag, robust to broadcast camera pan and zoom, reproducible, honest about precision. |
| Layout | Flat `src/rivalkit/` plus a thin CLI | Small and readable as a portfolio piece. Hexagonal layers would be speculative for about 4 modules and one input type. |
| Validation | At the CSV boundary, fail fast, report all errors | Hand-tagged input is the trust boundary. Bad rows must never reach a chart. |
| Example data | Synthetic, fictional teams, committed | The repository runs and can be published without footage or real-club data. |

Spec and design fix the exact CSV files and columns, the zone grid, the section list, the chart-to-section mapping and the proxy definitions.

## Assumptions (open product decisions, not decided here)

| # | Open decision | How this change handles it |
|---|---|---|
| 1 | Target club and matches | The kit is team-agnostic. The first real report picks a team later, outside this change. |
| 2 | Paying for LPF Play or using free Federal A matches | Video access stays outside the code. No feature depends on the choice. |
| 3 | Private demo or sent to a club | The PDF always carries the data-sources and limitations note. This change sends nothing. |
| 4 | Public or private repository | Assume the repository may become public: no footage, no scraped or real-club data committed, enforced by `.gitignore` and synthetic examples. |
| 5 | Report and outreach language | **Resolved by user (2026-10-22): Spanish**, neutral professional register, for PDF copy (titles, sections, labels, limitations note) and outreach templates. Code, identifiers, comments, and docs stay in English. |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | Package metadata. Dependencies: pandas, mplsoccer, matplotlib, pytest (dev). |
| `.gitignore` | New | Excludes video files, real-data directory, build and cache output. |
| `src/rivalkit/schema.py` | New | CSV contract, zone grid, validation. |
| `src/rivalkit/charts.py` | New | Chart functions over validated data. |
| `src/rivalkit/report.py` | New | Page layout, sections, limitations note, PDF export. |
| `src/rivalkit/__main__.py` | New | CLI entry point. |
| `data/example/` | New | Synthetic multi-match dataset. |
| `tests/` | New | Schema tests and a PDF smoke test. |
| `docs/tagging-guide.md`, `docs/data-sources.md`, `README.md` | New | How to tag a match, public-data field check, project overview. |
| `outreach/` | New | Cover message, one-page summary and public-post templates. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Sofascore/FotMob terms of service unread; scraping is a grey zone | High | No scrapers in scope. Public sites are only viewed manually, and only field names are recorded. |
| Primera Nacional match-level data depth unverified (xG and event detail unknown) | High | The first apply task is a manual check of one real match. Hand-tagged CSV stays the primary source either way. |
| LPF Play price (ARS 15,000/month from 15 Oct 2026) known only from press reports | Med | Video access stays outside the code. Federal A remains a free fallback (open decision 2). |
| Single-tagger bias, no cross-check | High | Every claim is validated against video. The limitations note states single-tagger provenance. The tagging guide defines events precisely. |
| Too few matches for credible patterns | High | Sample size is shown on the summary page, with a warning under 5 matches. Example data covers 5 matches. |
| Tagging effort per match may break the weekly cadence | Med | Zone grid and a minimal event set keep tagging fast. The tagging guide asks the user to log tagging time per match so the cadence can be reassessed with evidence. |
| Inaccurate unsolicited report about a named club harms reputation; cold outreach unproven in Argentina | Med | The report stays short (long cold reports got few replies). Proxies are labeled. Limitations are mandatory. Sending is a human decision outside this change. |
| Public repository leaks footage or real-club data | Low | `.gitignore` for video and real data. Only synthetic examples are committed. |
| `PdfPages` text and table layout looks poor | Med | Keep text short. Fallback: reportlab for text pages only (a later change). |
| Dependencies and checks need the user's environment (no installs or builds by the agent) | Med | The user installs dependencies and runs pytest and the CLI. Checks are reported honestly as pending until the user runs them. |

## Rollback Plan

- **Code**: the change is greenfield and purely additive. There are no migrations, persisted state or external side effects. Each slice is its own work-unit commit or PR. To roll back, revert that slice's commits or close its PR; earlier slices keep working because each stands alone (schema, then charts, then report, then docs).
- **Bad report content**: the kit never sends anything. If a generated report is wrong, fix the CSV or chart and regenerate. A sent report cannot be recalled, so sending stays a separate human decision gated on validation against video.
- **Wrong technical default**: if `PdfPages` layout proves inadequate, only `report.py` changes. If the zone grid proves too coarse, optional x/y columns are added in a later change without breaking zone-only data.
- **Leaked data in a public repository**: remove it from history before publishing. The `.gitignore` and the synthetic-only policy exist to prevent this.

## Dependencies

- Python 3 (minimum version fixed in design), pandas, mplsoccer (which brings matplotlib), pytest. **The user installs them.** The agent installs nothing and runs no builds.
- Git repository initialized on `main` (no commits yet). Slice work happens on a feature branch.
- Match video, through LPF Play or free Federal A matches. Outside the code.
- Optional: Kinovea (free, Windows-only) to locate timestamps while tagging.

## Delivery Note

- Forecast: about 950 authored lines against the 400-line review budget, so 4 slices are expected:
  1. Scaffold, schema, validation, tests, example data (about 300)
  2. Charts (about 250)
  3. Report, PDF, CLI, smoke test (about 250)
  4. Docs and outreach kit (about 250, non-code, low risk)
- Delivery strategy is `ask-on-risk`. The workload guard after `sdd-tasks` applies it. The chain strategy is not chosen here.
- **First apply task (manual, done by the user):** open one real Primera Nacional match on Sofascore or FotMob in a browser, record the available fields (stats, lineups, events, xG present or absent) in `docs/data-sources.md`, and copy no data. The result informs the limitations note and whether public stats can cross-check hand-tagged totals.

## Success Criteria

- [ ] `python -m rivalkit` on the shipped synthetic example produces an A4 PDF: a 1-page summary plus 6–8 pages, with the expected page count asserted by the smoke test.
- [ ] Every generated PDF contains the data-sources and limitations note, the number of matches analysed, and labels on every proxy metric.
- [ ] Input with fewer than 5 matches produces a visible sample-size warning in the report.
- [ ] Invalid CSV input exits non-zero, lists every error with file and row number, and writes no PDF.
- [ ] Schema validation tests and the smoke test pass when the user runs pytest.
- [ ] The repository contains no footage, no scraped data and no real-club data. Example teams are fictional.
- [ ] `docs/tagging-guide.md` lets the user tag one match end to end and log the tagging time.
- [ ] `docs/data-sources.md` records the manual Primera Nacional field check.
- [ ] Outreach templates exist, are team-agnostic, and point to the short PDF rather than a long report.
