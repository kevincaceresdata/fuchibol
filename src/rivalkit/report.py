"""Composition of the fixed 8-page A4 report and the atomic PDF write.

The page list, the Spanish copy, the analyst-text flow layout and the
mandatory data-sources and limitations note live here. Charts come from
`charts.py` and draw into axes placed on each page.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pandas as pd
from matplotlib import rc_context
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from . import charts
from .schema import Dataset, Notes

SECTIONS = ("Identidad y alineación", "Con pelota", "Sin pelota y transiciones",
            "Pelota parada", "Jugadores clave", "Plan de partido",
            "Fuentes de datos y limitaciones")
MIN_MATCHES = 5
PAGE_COUNT = 8
A4_INCHES = (210 / 25.4, 297 / 25.4)
WRAP_FULL, WRAP_HALF = 95, 45

_MARGIN = 0.08
_LINE = 0.019          # figure fraction per 10 pt line (about 0.19 in)
_FOOTER_Y = 0.065      # content must stay above the footer
_DATA_TITLE = "Datos de la muestra (calculados a partir del etiquetado)"
_LIMITATIONS = [
    "Datos etiquetados manualmente a partir del video de los partidos por una sola persona, sin verificación cruzada.",
    "Las métricas marcadas como proxy (indicador aproximado) son aproximaciones, no mediciones directas.",
    "No se informan xG, xGA ni PPDA: los datos públicos disponibles no permiten calcularlos.",
    "Los hallazgos describen solo la muestra analizada y deben validarse con el video antes de usarse.",
    "Ubicaciones registradas en una cuadrícula de 18 zonas, sin coordenadas exactas.",
    "Los sitios de datos públicos solo se consultaron manualmente; no se extrajeron datos de forma automatizada.",
    "Las observaciones, los jugadores clave y el plan de partido son interpretación del analista.",
]


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width) or [""])
    return lines


def _page(title: str, rival: str, n: int, k: int) -> Figure:
    fig = Figure(figsize=A4_INCHES)
    fig.text(_MARGIN, 0.965, charts.plain(title), fontsize=13, fontweight="bold", va="top")
    fig.text(_MARGIN, 0.946, charts.plain(rival), fontsize=10, color="0.3", va="top")
    footer = (f"{rival} · {n} partido{_plural(n)} analizado{_plural(n)} · "
              f"Datos etiquetados manualmente desde video · Página {k} de {PAGE_COUNT}")
    fig.text(_MARGIN, 0.03, charts.plain(footer), fontsize=8, color="0.35", va="bottom")
    return fig


def _block(fig: Figure, y: float, heading: str | None, lines: list[str],
           size: float = 10, color: str = "black") -> float:
    if heading:
        fig.text(_MARGIN, y, charts.plain(heading), fontsize=size,
                 fontweight="bold", va="top")
        y -= _LINE * size / 10
    for line in lines:
        fig.text(_MARGIN + 0.01, y, charts.plain(line), fontsize=size,
                 color=color, va="top")
        y -= _LINE * size / 10
    return y - 0.006


def _data_box(fig: Figure, y: float, lines: list[str]) -> float:
    height = (len(lines) + 1.4) * _LINE * 0.9 + 0.012
    ax = fig.add_axes([_MARGIN, y - height, 1 - 2 * _MARGIN, height])
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="0.94", edgecolor="none",
                           transform=ax.transAxes))
    ax.plot([0, 1], [1.02, 1.02], color="0.55", linewidth=0.8, transform=ax.transAxes,
            clip_on=False)
    ax.text(0.02, 0.86, _DATA_TITLE, fontsize=8.5, fontweight="bold",
            color="0.25", va="top", transform=ax.transAxes)
    for i, line in enumerate(lines):
        ax.text(0.02, 0.86 - (i + 1) * 0.13, charts.plain(line), fontsize=8.5,
                color="0.25", va="top", transform=ax.transAxes)
    return y - height - 0.008


def _observation(fig: Figure, y: float, notes: Notes, key: str) -> float:
    text = notes.observations.get(key, "")
    if not text.strip():
        return y
    return _block(fig, y, "Observaciones del analista", _wrap(text, WRAP_FULL))


def _chart_title(base: str, n: int) -> str:
    return f"{base} · {n} partido{_plural(n)}"


# --- summary page --------------------------------------------------------------------

def summary_lines(data: Dataset) -> list[str]:
    m = data.matches
    n = len(m)
    lines = []
    if n < MIN_MATCHES:
        lines.append(f"Muestra reducida: {n} partido{_plural(n)} analizado{_plural(n)}. "
                     "Con menos de 5 partidos los patrones pueden no ser representativos.")
    rec = charts.record(m)
    lines += [
        f"Rival: {data.rival}",
        f"Competición: {m['competition'].iloc[0] if n else '-'}",
        f"Fechas: {m['date'].min():%d/%m/%Y} - {m['date'].max():%d/%m/%Y}" if n else "Fechas: -",
        f"{n} partido{_plural(n)} analizado{_plural(n)}",
        (f"Récord: {rec['wins']} ganados, {rec['draws']} empatados, "
         f"{rec['losses']} perdidos · Goles: {rec['goals_for']} a favor, "
         f"{rec['goals_against']} en contra"),
    ]
    return lines


def data_facts(data: Dataset) -> list[str]:
    events, matches = data.events, data.matches
    n = len(matches)
    if n == 0:
        return []
    facts = []
    attempts = charts.zone_counts(charts.select(events, "rival", ("shot", "goal")))
    if attempts.sum() > 0:
        facts.append(f"Zona más frecuente de remate: zona {int(attempts.idxmax())}")
    goals = charts.select(events, "rival", ("goal",))
    if len(goals):
        set_pieces = int(goals["detail"].isin(("set_piece", "penalty")).sum())
        facts.append(f"Goles de pelota parada o penal: {set_pieces} de {len(goals)} "
                     f"({round(100 * set_pieces / len(goals))} %)")
    conceded = charts.select(events, "opponent", ("goal",))
    if len(conceded):
        late = int((conceded["minute"] > 75).sum())
        facts.append(f"Goles en contra después del minuto 75: {late} de {len(conceded)} "
                     f"({round(100 * late / len(conceded))} %)")
    proxy = charts.pressing_proxy(data)
    facts.append(f"Recuperaciones en campo contrario (proxy): {proxy.mean():.1f} por partido")
    splits = charts.venue_splits(data)
    home, away = splits.loc["home"], splits.loc["away"]
    if home.notna()["goals_for"] and away.notna()["goals_for"]:
        facts.append(f"Goles por partido: {home['goals_for']:.2f} local / "
                     f"{away['goals_for']:.2f} visitante")
    facts.append(f"Onces iniciales distintos: {charts.lineup_summary(data)[1]}")
    return facts


def _page_summary(fig: Figure, data: Dataset, notes: Notes) -> float:
    y = 0.92
    for line in summary_lines(data):
        if line.startswith("Muestra reducida"):
            ax = fig.add_axes([_MARGIN, y - 0.045, 1 - 2 * _MARGIN, 0.04])
            ax.axis("off")
            ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f6d5d5", edgecolor="none",
                                   transform=ax.transAxes))
            ax.text(0.02, 0.5, charts.plain(line), fontsize=9.5, color="#8a1f1f",
                    va="center", transform=ax.transAxes)
            y -= 0.058
        else:
            fig.text(_MARGIN, y, charts.plain(line), fontsize=10, va="top")
            y -= _LINE
    y -= 0.006
    analyst = [notes.identity] if notes.identity.strip() else []
    if notes.weaknesses:
        analyst.append("Debilidades a explotar:")
        analyst += [f"- {w}" for w in notes.weaknesses]
    if notes.threats:
        analyst.append("Amenazas a neutralizar:")
        analyst += [f"- {t}" for t in notes.threats]
    y = _block(fig, y, "Lectura del analista", [l for seg in analyst for l in _wrap(seg, WRAP_FULL)])
    y = _data_box(fig, y, data_facts(data))
    fig.text(_MARGIN, y, "Ver limitaciones del análisis en la página 8", fontsize=9,
             color="0.35", va="top")
    return y


# --- section pages -------------------------------------------------------------------

def _page_identity(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    frame, distinct = charts.lineup_summary(data)
    ax = fig.add_axes([_MARGIN, 0.56, 1 - 2 * _MARGIN, 0.34])
    charts.table(ax, frame, _chart_title("Jugadores de la plantilla", n))
    y = 0.52
    fig.text(_MARGIN, y, f"Onces iniciales distintos: {distinct} en {n} partido{_plural(n)}",
             fontsize=10, fontweight="bold", va="top")
    ax = fig.add_axes([_MARGIN, 0.28, 1 - 2 * _MARGIN, 0.16])
    charts.table(ax, charts.venue_splits(data), _chart_title("Local y visitante", n))
    return _observation(fig, 0.24, notes, "identity_and_lineup")


def _three_bars(fig: Figure, data: Dataset, team: str, base: str, y_axes: float) -> None:
    n = len(data.matches)
    for i, by in enumerate(("interval", "detail", "game_state")):
        ax = fig.add_axes([_MARGIN + i * 0.30, y_axes, 0.26, 0.17])
        charts.bar_chart(ax, charts.goal_breakdown(data.events, team, by),
                         _chart_title(f"{base} por {_axis_label(by)}", n))


def _axis_label(by: str) -> str:
    return {"interval": "minuto", "detail": "tipo", "game_state": "estado"}[by]


def _page_in_possession(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    fig.text(_MARGIN, 0.92, "Ataque organizado", fontsize=10.5, fontweight="bold", va="top")
    ax = fig.add_axes([_MARGIN, 0.55, 1 - 2 * _MARGIN, 0.35])
    charts.shot_map(ax, data.events, "rival", _chart_title("Mapa de remates", n))
    fig.text(_MARGIN, 0.50, "Goles a favor", fontsize=10.5, fontweight="bold", va="top")
    _three_bars(fig, data, "rival", "Goles", 0.30)
    return _observation(fig, 0.26, notes, "in_possession")


def _page_out_of_possession(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    proxy = charts.pressing_proxy(data)
    fig.text(_MARGIN, 0.92, "Transición defensiva: presión (proxy)", fontsize=10.5,
             fontweight="bold", va="top")
    ax = fig.add_axes([_MARGIN, 0.74, 1 - 2 * _MARGIN, 0.15])
    charts.bar_chart(ax, proxy, _chart_title("Recuperaciones en campo contrario", n),
                     subtitle=charts.PRESSING_PROXY_DEFINITION)
    fig.text(_MARGIN, 0.705, f"Promedio: {proxy.mean():.1f} recuperaciones por partido",
             fontsize=9, color="0.35", va="top")
    fig.text(_MARGIN, 0.67, "Defensa organizada", fontsize=10.5, fontweight="bold", va="top")
    ax = fig.add_axes([_MARGIN, 0.46, 1 - 2 * _MARGIN, 0.19])
    charts.shot_map(ax, data.events, "opponent", _chart_title("Remates recibidos", n))
    fig.text(_MARGIN, 0.425, "Goles en contra", fontsize=10.5, fontweight="bold", va="top")
    _three_bars(fig, data, "opponent", "Goles", 0.245)
    return _observation(fig, 0.215, notes, "out_of_possession")


def _set_piece_zone_counts(events: pd.DataFrame, team: str) -> pd.Series:
    pieces = charts.select(events, team, ("corner", "free_kick", "penalty"))
    counts = pieces["zone"].value_counts()
    return counts.reindex(range(1, 19), fill_value=0).astype(float)


def _page_set_pieces(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    events = data.events
    for col, team, base in ((0.0, "rival", "Ofensiva (rival)"), (0.5, "opponent", "Defensiva (oponentes)")):
        fig.text(_MARGIN + col, 0.92, base, fontsize=10.5, fontweight="bold", va="top")
        ax = fig.add_axes([_MARGIN + col, 0.60, 0.42, 0.28])
        charts.zone_map(ax, _set_piece_zone_counts(events, team),
                        _chart_title("Pelotas paradas por zona", n))
        ax = fig.add_axes([_MARGIN + col, 0.40, 0.42, 0.16])
        charts.bar_chart(ax, charts.set_piece_counts(events, team),
                         _chart_title("Pelotas paradas por tipo", n))
    for_team = lambda t: int(charts.select(events, t, ("goal",))["detail"].isin(("set_piece", "penalty")).sum())
    fig.text(_MARGIN, 0.35, f"Goles de pelota parada o penal: {for_team('rival')} a favor · "
                            f"{for_team('opponent')} en contra", fontsize=9.5, va="top")
    return _observation(fig, 0.31, notes, "set_pieces")


def _page_key_players(fig: Figure, data: Dataset, notes: Notes) -> float:
    y = 0.92
    if not notes.key_players:
        y = _block(fig, y, None, ["El analista no incluyó jugadores clave en las notas de este informe."])
    else:
        frame, _ = charts.lineup_summary(data)
        by_name = frame.set_index("player") if len(frame) else frame
        goals = data.events[(data.events["event_type"] == "goal") & (data.events["team"] == "rival")]
        for name, note in notes.key_players:
            fig.text(_MARGIN, y, charts.plain(name), fontsize=12, fontweight="bold", va="top")
            y -= _LINE * 1.2
            y = _block(fig, y, None, _wrap(note, WRAP_FULL))
            facts = []
            if len(by_name) and name in by_name.index:
                row = by_name.loc[name]
                scored = int((goals["player"] == name).sum())
                goals_txt = f", {scored} gol{'es' if scored != 1 else ''}" if scored else ""
                facts.append(f"Datos: {int(row['starts'])} titularidades, "
                             f"{int(row['minutes'])} minutos{goals_txt}")
            if facts:
                y = _block(fig, y - 0.002, None, facts, size=8.5, color="0.4")
            y -= 0.004
    return _observation(fig, y, notes, "key_players")


def _page_match_plan(fig: Figure, data: Dataset, notes: Notes) -> float:
    y = 0.92
    lines = []
    for i, instruction in enumerate(notes.instructions, 1):
        wrapped = _wrap(instruction, WRAP_FULL)
        lines.append(f"{i}. {wrapped[0]}")
        lines += ["   " + line for line in wrapped[1:]]
    y = _block(fig, y, "Instrucciones", lines)
    if notes.clips:
        y = _block(fig, y, "Clips de referencia", [f"- {c}" for c in notes.clips])
    return _observation(fig, y, notes, "match_plan")


def _page_sources(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    y = _block(fig, 0.92, "Fuentes de datos y limitaciones", [f"({c}) {t}" for c, t in
             zip(("a", "b", "c", "d", "e", "f", "g"), _LIMITATIONS)])
    sample = f"Muestra analizada: {n} partido{_plural(n)} analizado{_plural(n)}."
    if n < MIN_MATCHES:
        sample += " Muestra reducida: con menos de 5 partidos los patrones pueden no ser representativos."
    y = _block(fig, y, None, [sample], size=9.5)
    ax = fig.add_axes([_MARGIN, y - 0.30, 0.5, 0.28])
    charts.zone_legend(ax)
    matches = data.matches.copy()
    listing = pd.DataFrame({
        "Fecha": [f"{d:%d/%m/%Y}" for d in matches["date"]],
        "Rival": matches["opponent"],
        "Condición": ["Local" if v == "home" else "Visitante" for v in matches["venue"]],
        "Resultado": [f"{r}-{o}" for r, o in zip(matches["rival_goals"], matches["opponent_goals"])],
    })
    ax = fig.add_axes([_MARGIN + 0.52, y - 0.24, 0.4, 0.22])
    charts.table(ax, listing, "Partidos analizados")
    return _observation(fig, y - 0.32, notes, "sources")


_PAGES = (("Resumen", _page_summary), (SECTIONS[0], _page_identity),
          (SECTIONS[1], _page_in_possession), (SECTIONS[2], _page_out_of_possession),
          (SECTIONS[3], _page_set_pieces), (SECTIONS[4], _page_key_players),
          (SECTIONS[5], _page_match_plan), (SECTIONS[6], _page_sources))


def write_report(data: Dataset, notes: Notes, out: Path) -> int:
    """Render the 8 pages to `out` atomically; returns pages written.

    A page whose text flows past the footer is still rendered; a stderr
    warning names it and the exit code stays 0 elsewhere.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    n = len(data.matches)
    figures, overflow = [], []
    for k, (title, build) in enumerate(_PAGES, 1):
        fig = _page(title, data.rival, n, k)
        bottom = build(fig, data, notes)
        if bottom < _FOOTER_Y:
            overflow.append(title)
        figures.append(fig)
    try:
        with rc_context({"pdf.fonttype": 42}):
            with PdfPages(tmp) as pdf:
                for fig in figures:
                    pdf.savefig(fig)
        os.replace(tmp, out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    for title in overflow:
        print(f'aviso: el texto de "{title}" excede la página; reduzca el texto',
              file=sys.stderr)
    return len(figures)
