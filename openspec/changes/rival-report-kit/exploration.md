# Exploration: rival-report-kit

## Current State

Greenfield repository: no code, no tests, no dependencies. Only `openspec/` (config, empty specs/archive) and `.atl/` exist. Public data for Argentine second-tier football (Primera Nacional, B Metro, Federal A) is thin, so the kit's real value is a repeatable pipeline: tag video → validate CSV → chart → short PDF. Hand-tagged CSV is the primary data source.

## Research Inputs (sdd-research, status partial)

- Every Primera Nacional club had at least one video analyst in 2019; pay ranged from ad honorem to ~ARS 200k/month (stale) — https://www.tiempoar.com.ar/ta_article/futbol-camara-accion-los-secretos-del-boom-del-videoanalisis/ . Racing de Córdoba runs a data department on Wyscout — https://www.hudl.com/blog/racing-de-córdoba-análisis-wyscout . Value proposition: a data layer on top of video, not a replacement for the video analyst.
- No documented Argentine hire via cold reports. Public portfolio, ad-honorem first credit, and contacts have precedent. A 30-page cold report sent widely got few replies — https://oppositionscouting.substack.com/p/analysing-a-league-2-opposition-report
- Coaches rely mostly on annotated video and value clarity/relevance. Phase-based structure (FIFA EFI). Sample ≥5 matches; validate every claim against video.
- Sofascore/FotMob cover Primera Nacional with basic stats; match-level xG unverified. FBref lost Opta advanced stats in Jan 2026. Scraping ToS unread (grey zone). Video: LPF Play Plan Plus ARS 15,000/month from 15 Oct 2026 (press reports only). Kinovea is free, Windows-only.
- PPDA requires full event data; not computable from public data. Use labeled proxies.

## Affected Areas (all new)

- `pyproject.toml` — dependencies: pandas, mplsoccer, matplotlib, pytest.
- `src/rivalkit/schema.py` — CSV column contract and validation.
- `src/rivalkit/charts.py` — shot map, goals by minute/type/game state, set-piece map, lineup consistency, home/away splits.
- `src/rivalkit/report.py` — 1-page summary + 6–8 pages in 7 sections, PDF export.
- `src/rivalkit/__main__.py` — CLI: `python -m rivalkit data/<match>/ -o out.pdf`.
- `data/example/*.csv` — synthetic data so the repo runs and is publishable without real club data.
- `tests/` — pytest.
- `docs/tagging-guide.md` — how to tag a match.
- `outreach/` — cover message, one-page summary, public-post version.

## Approaches

### Fork 1: PDF generation

| Option | Pros | Cons | Effort |
|---|---|---|---|
| matplotlib `PdfPages` | No extra dependency (ships with matplotlib, required by mplsoccer); one rendering path; vector output; safe on Windows | Manual text/table layout | Low–Med |
| HTML → PDF (WeasyPrint/headless Chrome) | Best typography | WeasyPrint needs GTK/Pango on Windows; Chrome needs a browser; close to the rejected HTML route | Med–High |
| Quarto/Jupyter | Narrative + code together | Needs Quarto + LaTeX/Typst; heaviest toolchain | High |
| reportlab | Flowing text and tables; pure pip | Second layout API next to matplotlib; charts embedded as images | Med |

### Fork 2: Coordinates for hand tagging

| Option | Pros | Cons | Effort |
|---|---|---|---|
| Kinovea pixel export | Precise | Broadcast cameras pan/zoom; pixels do not map to the pitch without per-frame calibration; Windows-only | High |
| Pitch-zone grid (e.g. 18 zones) | Fast, robust to camera angle, reproducible, honest about precision | Coarse shot maps | Low |
| Eyeballed x/y on mplsoccer pitch | Best-looking maps | False precision, tagger noise, slower | Med |

### Fork 3: Layout

| Option | Pros | Cons | Effort |
|---|---|---|---|
| Flat `src/rivalkit/` + `data/`, `tests/`, `outreach/` | Conventional, small, readable as a portfolio | None material | Low |
| Single script + notebooks | Fastest start | Untestable, weak portfolio, hard to repeat weekly | Low |
| Hexagonal layers | Matches the user's usual style | Speculative for ~4 modules and one input type | Med |

## Recommendation

- **PDF:** matplotlib `PdfPages`, A4 pages. Revisit reportlab only if text-heavy pages look poor.
- **Coordinates:** zone grid as primary field (`zone` ID); optional `x,y` columns later, taking precedence when present. Kinovea used only to locate timestamps, not as a coordinate source.
- **Layout:** flat package — `schema.py`, `charts.py`, `report.py`, thin CLI.
- **Validation at the CSV boundary:** required columns, enums for event type and game state, minute 0–120, zone in range, row-numbered error messages.
- **Tests:** pytest for schema validation + one smoke test (example data → PDF with expected page count).
- **Example data:** synthetic, shipped in the repo.

## Size Forecast (400-line review budget)

| Area | Estimated authored lines |
|---|---|
| Schema + validation | ~120 |
| Charts | ~200 |
| Report + PDF | ~150 |
| CLI | ~30 |
| Tests | ~120 |
| Example data | ~60 |
| Packaging | ~20 |
| Docs + outreach | ~250 |
| **Total** | **~950** |

Exceeds the budget; slicing required. Suggested slices:
1. Scaffold + schema + validation + tests + example data (~300)
2. Charts (~250)
3. Report + PDF + CLI + smoke test (~250)
4. Docs + outreach kit (~250, non-code, low risk)

## Risks

- Single tagger, no cross-check: every claim must be validated against video.
- Reports need ≥5 matches; a one-match demo may look thin.
- Cold outreach is unproven in Argentina.
- PPDA and xG not computable from public data; proxies must be labeled.
- A public repo must not embed footage. An inaccurate unsolicited report about a named club is a reputation risk.
- LPF Play pricing rests on press reports only.
- Tagging effort per match may make a weekly cadence unrealistic.
- Dependencies must be installed by the user (no installs/builds in the agent environment).

## Open Product Decisions (not decided here)

1. Target club and match(es).
2. Pay for LPF Play or use free Federal A matches.
3. Private demo vs. sent to a club.
4. Public portfolio repository or private.
5. Zone grid vs. x/y precision (recommended: zone-first).

## Ready for Proposal

Yes. Open decisions can be carried as assumptions or asked one at a time.
