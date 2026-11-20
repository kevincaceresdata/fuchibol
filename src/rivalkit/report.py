"""Composition of the fixed 8-page A4 report and the atomic PDF write.

The page list, the Spanish copy, the analyst-text flow layout and the
mandatory data-sources and limitations note live here. Charts come from
`charts.py` and draw into axes placed on each page.
"""

from __future__ import annotations

import os
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

import pandas as pd
from matplotlib import image as mpl_image
from matplotlib import rc_context
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import charts
from .charts import PALETTE
from .schema import Dataset, Notes

SECTIONS = ("Identidad y alineación", "Con pelota", "Sin pelota y transiciones",
            "Pelota parada", "Jugadores clave", "Plan de partido",
            "Fuentes de datos y limitaciones")
MIN_MATCHES = 5
PAGE_COUNT = 9  # portada + 8 paginas de contenido
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
    "Los sitios de datos públicos (FotMob, Sofascore) se consultaron por API para contrastar alineaciones, goleadores, tarjetas y mapa de remates.",
    "Las observaciones, los jugadores clave y el plan de partido son interpretación del analista.",
]


def _fecha_label(m) -> str:
    mid = str(m["match_id"]) if "match_id" in m else str(m["match"]).replace("\\", "/").split("/")[-1]
    return (f"FECHA {mid[1:]}" if mid.lower().startswith("f") and mid[1:].isdigit()
            else mid.upper())


# --- portada -------------------------------------------------------------------------

def _page_cover(data: Dataset, notes: Notes, crest=None, opp_crest=None) -> Figure:
    """Portada a pagina completa: fondo azul profundo, franja tricolor, escudo, rival y marcador."""
    fig = Figure(figsize=A4_INCHES)
    fig.patch.set_facecolor(PALETTE["brand_dark"])
    # Franja tricolor superior e inferior (Azul Almagro / Blanco / Negro)
    strip_top = fig.add_axes([_MARGIN, 0.885, 1 - 2 * _MARGIN, 0.012])
    strip_top.axis("off")
    strip_top.add_patch(Rectangle((0.0, 0), 0.34, 1, facecolor=PALETTE["brand"], transform=strip_top.transAxes))
    strip_top.add_patch(Rectangle((0.34, 0), 0.32, 1, facecolor="white", transform=strip_top.transAxes))
    strip_top.add_patch(Rectangle((0.66, 0), 0.34, 1, facecolor="#0B0F19", transform=strip_top.transAxes))
    fig.lines.append(plt_line(_MARGIN, 0.105, 1 - _MARGIN, 0.105, fig,
                              color=PALETTE["brand_light"], linewidth=1.2))
    if crest is not None:
        size_in = 1.55
        w, h = size_in / A4_INCHES[0], size_in / A4_INCHES[1]
        back = fig.add_axes([0.5 - w / 2 - 0.014, 0.675 - h / 2 - 0.012, w + 0.028, h + 0.024])
        back.axis("off")
        back.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.02,rounding_size=0.12",
                                      facecolor="white", edgecolor=PALETTE["brand_light"],
                                      linewidth=1.5, transform=back.transAxes))
        ax = fig.add_axes([0.5 - w / 2, 0.675 - h / 2, w, h])
        ax.axis("off")
        ax.imshow(crest, aspect="equal")
    fig.text(0.5, 0.555, "INFORME TÉCNICO", fontsize=13, color=PALETTE["brand_light"],
             ha="center", fontweight="bold")
    fig.text(0.5, 0.490, charts.plain(data.rival).upper(), fontsize=38, color="white",
             ha="center", va="center", fontweight="bold")
    n = len(data.matches)
    if n == 1:
        m = data.matches.iloc[0]
        card = fig.add_axes([_MARGIN + 0.06, 0.285, 1 - 2 * (_MARGIN + 0.06), 0.135])
        card.axis("off")
        card.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.02,rounding_size=0.08",
                                      facecolor="#132966", edgecolor=PALETTE["brand_light"],
                                      linewidth=1.0, transform=card.transAxes))
        if opp_crest is not None:
            _crest_in_axes(card, opp_crest, 0.12, 0.58, 0.42)
        if crest is not None:
            _crest_in_axes(card, crest, 0.88, 0.58, 0.42)
        card.text(0.5, 0.62, charts.plain(
            f"{m['opponent']}  {int(m['opponent_goals'])} - {int(m['rival_goals'])}  {data.rival}"),
            fontsize=14.5, fontweight="bold", color="white", ha="center", va="center",
            transform=card.transAxes)
        card.text(0.5, 0.22, charts.plain(
            f"{m['competition']} · {_fecha_label(m)} · {m['date']:%d/%m/%Y}"),
            fontsize=9.5, color=PALETTE["brand_light"], ha="center", va="center",
            transform=card.transAxes)
    else:
        fig.text(0.5, 0.40, f"{n} partidos analizados", fontsize=14, color="white",
                 ha="center", va="center")
    fig.text(0.5, 0.088, "Preparado con rivalkit · Datos etiquetados con asistencia "
                         "automática y revisión humana", fontsize=8,
             color=PALETTE["brand_light"], ha="center", va="center")
    fig.text(0.5, 0.062, "Escudos: Wikimedia Commons (uso educativo) · Limitaciones: página 9",
             fontsize=7, color="#8FA3D0", ha="center", va="center")
    return fig


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


@lru_cache(maxsize=4)
def _crest(assets_dir: str | None, name: str):
    """Escudo como array de imagen, o None si no existe."""
    if not assets_dir:
        return None
    path = Path(assets_dir) / name
    if not path.exists():
        return None
    try:
        return mpl_image.imread(path)
    except Exception:
        return None


def _crest_chip(fig: Figure, img, x_right: float, y_center: float, size_in: float) -> None:
    """Chip blanco con el escudo, alineado al borde derecho x_right (fig coords)."""
    w = size_in / A4_INCHES[0]
    h = size_in / A4_INCHES[1]
    x0 = x_right - w
    y0 = y_center - h / 2
    back = fig.add_axes([x0 - 0.004, y0 - 0.0035, w + 0.008, h + 0.007])
    back.axis("off")
    back.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.02,rounding_size=0.18",
                                  facecolor="white", edgecolor="none",
                                  transform=back.transAxes))
    ax = fig.add_axes([x0, y0, w, h])
    ax.axis("off")
    ax.imshow(img, aspect="equal")


def _page(title: str, rival: str, n: int, k: int, crest=None) -> Figure:
    fig = Figure(figsize=A4_INCHES)
    fig.patch.set_facecolor("white")
    # banda de encabezado con la identidad del club
    band = fig.add_axes([0, 0.935, 1, 0.065])
    band.axis("off")
    band.add_patch(Rectangle((0, 0), 1, 1, facecolor=PALETTE["brand_dark"],
                             edgecolor="none", transform=band.transAxes))
    band.add_patch(Rectangle((0, 0), 1, 0.055, facecolor=PALETTE["brand_light"],
                             edgecolor="none", transform=band.transAxes))
    band.text(_MARGIN, 0.62, charts.plain(title), fontsize=14, fontweight="bold",
              color="white", va="center", transform=band.transAxes)
    band.text(_MARGIN, 0.22, charts.plain(rival), fontsize=9.5,
              color=PALETTE["brand_light"], va="center", transform=band.transAxes)
    if crest is not None:
        _crest_chip(fig, crest, 1 - _MARGIN, 0.9675, 0.34)
    footer = (f"{rival} · {n} partido{_plural(n)} analizado{_plural(n)} · "
              f"Datos etiquetados con asistencia automática y revisión humana · "
              f"Página {k} de {PAGE_COUNT}")
    fig.text(_MARGIN, 0.045, charts.plain(footer), fontsize=8,
             color=PALETTE["muted"], va="bottom")
    fig.lines.append(plt_line(_MARGIN, 0.062, 1 - _MARGIN, 0.062, fig,
                              color=PALETTE["grid"], linewidth=0.8))
    return fig


def _hero_card(fig: Figure, data: Dataset, y: float, crest, opp_crest) -> float:
    """Tarjeta del partido: escudos, marcador, competencia y fecha (solo 1 partido)."""
    if len(data.matches) != 1:
        return y
    m = data.matches.iloc[0]
    height = 0.115
    ax = fig.add_axes([_MARGIN, y - height, 1 - 2 * _MARGIN, height])
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.008,rounding_size=0.045",
                                facecolor=PALETTE["panel"], edgecolor="none",
                                transform=ax.transAxes))
    ax.plot([0.015, 0.985], [0.97, 0.97], color=PALETTE["brand"], linewidth=2.2,
            transform=ax.transAxes, clip_on=False, solid_capstyle="round")
    ax.text(0.5, 0.80, charts.plain(str(m["competition"])).upper(), fontsize=8.5,
            color=PALETTE["muted"], ha="center", va="center", transform=ax.transAxes)
    mid = str(m["match_id"]) if "match_id" in m else str(m["match"]).replace("\\", "/").split("/")[-1]
    fecha = (f"FECHA {mid[1:]}" if mid.lower().startswith("f") and mid[1:].isdigit()
             else mid.upper())
    ax.text(0.5, 0.63, charts.plain(f"{fecha} · {m['date']:%d/%m/%Y} · Condición: "
                                    f"{'Local' if m['venue'] == 'home' else 'Visitante'}"),
            fontsize=8.5, color=PALETTE["muted"], ha="center", va="center",
            transform=ax.transAxes)
    # escudos
    if opp_crest is not None:
        _crest_in_axes(ax, opp_crest, 0.125, 0.30, 0.17)
    if crest is not None:
        _crest_in_axes(ax, crest, 0.875, 0.30, 0.17)
    ax.text(0.395, 0.30, charts.plain(str(m["opponent"])).upper(), fontsize=11.5,
            fontweight="bold", color=PALETTE["ink"], ha="right", va="center",
            transform=ax.transAxes)
    ax.text(0.50, 0.30, f"{int(m['opponent_goals'])}  -  {int(m['rival_goals'])}",
            fontsize=20, fontweight="bold", color=PALETTE["brand_dark"],
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.605, 0.30, charts.plain(str(data.rival)).upper(), fontsize=11.5,
            fontweight="bold", color=PALETTE["ink"], ha="left", va="center",
            transform=ax.transAxes)
    ax.text(0.985, 0.06, "Escudos: Wikimedia Commons (uso educativo)", fontsize=6,
            color=PALETTE["muted"], ha="right", va="center", transform=ax.transAxes)
    return y - height - 0.012


def _crest_in_axes(ax, img, x_center: float, y_center: float, h_frac: float) -> None:
    h = h_frac
    w = h * (A4_INCHES[1] / A4_INCHES[0]) * (img.shape[1] / img.shape[0])
    inset = ax.inset_axes([x_center - w / 2, y_center - h / 2, w, h])
    inset.axis("off")
    inset.imshow(img, aspect="equal")


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width) or [""])
    return lines


def plt_line(x0: float, y0: float, x1: float, y1: float, fig: Figure,
             color: str, linewidth: float):
    """Line2D helper for figure-coordinate rules (importable without pyplot)."""
    from matplotlib.lines import Line2D
    return Line2D([x0, x1], [y0, y1], figure=fig, color=color, linewidth=linewidth,
                  transform=fig.transFigure)


def _block(fig: Figure, y: float, heading: str | None, lines: list[str],
           size: float = 10, color: str | None = None) -> float:
    color = color or PALETTE["ink"]
    if heading:
        fig.text(_MARGIN, y, charts.plain(heading), fontsize=size,
                 fontweight="bold", va="top", color=PALETTE["brand"])
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
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=PALETTE["panel"], edgecolor="none",
                           transform=ax.transAxes))
    ax.plot([0, 1], [1.02, 1.02], color=PALETTE["brand"], linewidth=1.6,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.02, 0.86, _DATA_TITLE, fontsize=8.5, fontweight="bold",
            color=PALETTE["brand"], va="top", transform=ax.transAxes)
    for i, line in enumerate(lines):
        ax.text(0.02, 0.86 - (i + 1) * 0.13, charts.plain(line), fontsize=8.5,
                color=PALETTE["muted"], va="top", transform=ax.transAxes)
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


def _kpi_strip(fig: Figure, data: Dataset, y: float) -> float:
    """Tira de 4 tarjetas KPI (Goles, Remates, Pelota parada, Zona frecuente)."""
    events = data.events
    rec = charts.record(data.matches)
    shots_f = len(charts.select(events, "rival", ("shot", "goal")))
    shots_a = len(charts.select(events, "opponent", ("shot", "goal")))
    sp_f = len(charts.select(events, "rival", ("corner", "free_kick", "penalty")))
    sp_a = len(charts.select(events, "opponent", ("corner", "free_kick", "penalty")))
    zc = charts.zone_counts(charts.select(events, "rival", ("shot", "goal")))
    top_zone = f"Zona {int(zc.idxmax())}" if zc.sum() > 0 else "—"
    cards = [
        ("GOLES (FAVOR / CONTRA)", f"{rec['goals_for']}  /  {rec['goals_against']}"),
        ("REMATES TOTALES (F / C)", f"{shots_f}  /  {shots_a}"),
        ("PELOTA PARADA (F / C)", f"{sp_f}  /  {sp_a}"),
        ("ZONA PRINCIPAL ATAQUE", top_zone),
    ]
    h = 0.056
    total_w = 1 - 2 * _MARGIN
    gap = 0.014
    w = (total_w - 3 * gap) / 4
    for i, (label, val) in enumerate(cards):
        ax = fig.add_axes([_MARGIN + i * (w + gap), y - h, w, h])
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.08",
                                    facecolor=PALETTE["panel"], edgecolor=PALETTE["grid"],
                                    linewidth=0.8, transform=ax.transAxes))
        ax.add_patch(Rectangle((0, 0.88), 1, 0.12, facecolor=PALETTE["brand"],
                               edgecolor="none", transform=ax.transAxes))
        ax.text(0.5, 0.62, val, fontsize=11.5, fontweight="bold",
                color=PALETTE["brand_dark"], ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.22, label, fontsize=6.5, fontweight="bold",
                color=PALETTE["muted"], ha="center", va="center", transform=ax.transAxes)
    return y - h - 0.012


def _page_summary(fig: Figure, data: Dataset, notes: Notes,
                  crest=None, opp_crest=None) -> float:
    y = 0.925
    y = _hero_card(fig, data, y, crest, opp_crest)
    y = _kpi_strip(fig, data, y)
    skip = ("Rival:", "Competición:", "Fechas:") if len(data.matches) == 1 else ()
    for line in summary_lines(data):
        if line.startswith(skip) or (skip and line.endswith("partido analizado")
                                     and len(data.matches) == 1):
            continue
        if line.startswith("Muestra reducida"):
            ax = fig.add_axes([_MARGIN, y - 0.036, 1 - 2 * _MARGIN, 0.032])
            ax.axis("off")
            ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=PALETTE["alert_bg"],
                                   edgecolor="none", transform=ax.transAxes))
            ax.add_patch(Rectangle((0, 0), 0.008, 1, facecolor=PALETTE["alert"],
                                   edgecolor="none", transform=ax.transAxes))
            ax.text(0.02, 0.5, charts.plain(line), fontsize=8.4,
                    color=PALETTE["alert"], va="center", transform=ax.transAxes)
            y -= 0.046
        else:
            fig.text(_MARGIN, y, charts.plain(line), fontsize=9.5, va="top")
            y -= _LINE * 0.95
    y -= 0.004
    analyst = [notes.identity] if notes.identity.strip() else []
    if notes.weaknesses:
        analyst.append("Debilidades a explotar:")
        analyst += [f"- {w}" for w in notes.weaknesses]
    if notes.threats:
        analyst.append("Amenazas a neutralizar:")
        analyst += [f"- {t}" for t in notes.threats]
    y = _block(fig, y, "Lectura del analista",
               [l for seg in analyst for l in _wrap(seg, WRAP_FULL)], size=9.4)
    y = _data_box(fig, y, data_facts(data))
    fig.text(_MARGIN, y, "Ver limitaciones del análisis en la página 9", fontsize=8.5,
             color=PALETTE["muted"], va="top")
    return y


# --- section pages -------------------------------------------------------------------

def _page_identity(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    frame, distinct = charts.lineup_summary(data)
    ax = fig.add_axes([_MARGIN, 0.455, 1 - 2 * _MARGIN, 0.435])
    charts.table(ax, frame, _chart_title("Jugadores de la plantilla", n))
    y = 0.430
    fig.text(_MARGIN, y, f"Onces iniciales distintos: {distinct} en {n} partido{_plural(n)}",
             fontsize=10, fontweight="bold", va="top", color=PALETTE["brand"])
    ax = fig.add_axes([_MARGIN, 0.265, 1 - 2 * _MARGIN, 0.115])
    splits = charts.venue_splits(data).copy()
    splits.index = ["Local", "Visitante"]
    splits = splits.reset_index().rename(columns={"index": "Condición"})
    charts.table(ax, splits, _chart_title("Local y visitante", n))
    return _observation(fig, 0.225, notes, "identity_and_lineup")


def _three_bars(fig: Figure, data: Dataset, team: str, base: str, y_axes: float) -> None:
    for i, by in enumerate(("interval", "detail", "game_state")):
        ax = fig.add_axes([_MARGIN + i * 0.30, y_axes, 0.24, 0.142])
        charts.bar_chart(ax, charts.goal_breakdown(data.events, team, by), _axis_label(by))


def _axis_label(by: str) -> str:
    return {"interval": "Por tramo (min)", "detail": "Por vía de gol", "game_state": "Por estado"}[by]


def _page_in_possession(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    fig.text(_MARGIN, 0.905, "Ataque organizado", fontsize=10.5, fontweight="bold",
             va="top", color=PALETTE["brand"])
    ax = fig.add_axes([_MARGIN, 0.535, 1 - 2 * _MARGIN, 0.32])
    charts.shot_map(ax, data.events, "rival", _chart_title("Mapa de remates", n))
    fig.text(_MARGIN, 0.485, "Goles a favor", fontsize=10.5, fontweight="bold", va="top",
             color=PALETTE["brand"])
    _three_bars(fig, data, "rival", "Goles", 0.285)
    return _observation(fig, 0.215, notes, "in_possession")


def _page_out_of_possession(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    proxy = charts.pressing_proxy(data)
    fig.text(_MARGIN, 0.905, "Transición defensiva: presión (proxy)", fontsize=10.5,
             fontweight="bold", va="top", color=PALETTE["brand"])
    ax = fig.add_axes([_MARGIN, 0.705, 1 - 2 * _MARGIN, 0.125])
    charts.bar_chart(ax, proxy, _chart_title("Recuperaciones en campo contrario", n),
                     subtitle=charts.PRESSING_PROXY_DEFINITION)
    fig.text(_MARGIN, 0.672, f"Promedio: {proxy.mean():.1f} recuperaciones por partido",
             fontsize=8.5, color=PALETTE["muted"], va="top")
    fig.text(_MARGIN, 0.642, "Defensa organizada", fontsize=10.5, fontweight="bold",
             va="top", color=PALETTE["brand"])
    ax = fig.add_axes([_MARGIN, 0.445, 1 - 2 * _MARGIN, 0.165])
    charts.shot_map(ax, data.events, "opponent", _chart_title("Remates recibidos", n))
    fig.text(_MARGIN, 0.412, "Goles en contra", fontsize=10.5, fontweight="bold",
             va="top", color=PALETTE["brand"])
    _three_bars(fig, data, "opponent", "Goles", 0.222)
    return _observation(fig, 0.155, notes, "out_of_possession")


def _set_piece_zone_counts(events: pd.DataFrame, team: str) -> pd.Series:
    pieces = charts.select(events, team, ("corner", "free_kick", "penalty"))
    counts = pieces["zone"].value_counts()
    return counts.reindex(range(1, 19), fill_value=0).astype(float)


def _page_set_pieces(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    events = data.events
    for col, team, base in ((0.0, "rival", "Ofensiva (rival)"), (0.5, "opponent", "Defensiva (oponentes)")):
        fig.text(_MARGIN + col, 0.905, base, fontsize=10.5, fontweight="bold", va="top",
                 color=PALETTE["brand"])
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
    y = 0.915
    if not notes.key_players:
        y = _block(fig, y, None, ["El analista no incluyó jugadores clave en las notas de este informe."])
    else:
        frame, _ = charts.lineup_summary(data)
        by_name = frame.set_index("player") if len(frame) else frame
        rival_ev = data.events[data.events["team"] == "rival"]
        goals = rival_ev[rival_ev["event_type"] == "goal"]
        shots = rival_ev[rival_ev["event_type"].isin(("shot", "goal"))]
        for name, note in notes.key_players:
            wrapped = _wrap(note, WRAP_FULL - 6)
            card_h = max(0.085, 0.048 + len(wrapped) * _LINE * 0.95)
            ax = fig.add_axes([_MARGIN, y - card_h, 1 - 2 * _MARGIN, card_h])
            ax.axis("off")
            ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.008,rounding_size=0.05",
                                        facecolor=PALETTE["panel"], edgecolor=PALETTE["grid"],
                                        linewidth=0.8, transform=ax.transAxes))
            ax.add_patch(Rectangle((0, 0), 0.010, 1, facecolor=PALETTE["brand"],
                                   edgecolor="none", transform=ax.transAxes))
            ax.text(0.025, 0.78, charts.plain(name), fontsize=11.5, fontweight="bold",
                    va="center", color=PALETTE["brand_dark"], transform=ax.transAxes)
            if len(by_name) and name in by_name.index:
                row = by_name.loc[name]
                scored = int((goals["player"] == name).sum())
                att = int((shots["player"] == name).sum())
                pos = str(row["position"]) if pd.notna(row["position"]) and str(row["position"]) else "—"
                badge = (f"Pos: {pos} · {int(row['starts'])} tit. · {int(row['minutes'])} min"
                         f" · {att} rem. · {scored} gol{'es' if scored != 1 else ''}")
                ax.text(0.98, 0.78, charts.plain(badge), fontsize=8.5, fontweight="bold",
                        va="center", ha="right", color=PALETTE["brand"], transform=ax.transAxes)
            for idx, ln in enumerate(wrapped):
                ax.text(0.025, 0.45 - idx * 0.24, charts.plain(ln), fontsize=9.5,
                        va="center", color=PALETTE["ink"], transform=ax.transAxes)
            y -= card_h + 0.016
    return _observation(fig, y - 0.005, notes, "key_players")


def _draw_timeline_matrix(fig: Figure, data: Dataset, y_top: float) -> float:
    """Cronología táctica de eventos (minuto 0..95 x zona 1..18) para Plan de partido."""
    events = data.events
    if events.empty or y_top < 0.34:
        return y_top
    h = min(0.23, y_top - 0.095)
    ax = fig.add_axes([_MARGIN + 0.055, y_top - h - 0.02, 1 - 2 * _MARGIN - 0.055, h])
    ax.set_title("Cronología de eventos por minuto y zona (azul: rival · ámbar: oponente · ★: gol)",
                 fontsize=9.5, fontweight="bold", loc="left", color=PALETTE["brand"], pad=6)
    ax.set_xlim(0, 96)
    ax.set_ylim(0.5, 18.5)
    ax.set_xticks(range(0, 95, 15))
    ax.set_xticklabels([f"{m}'" for m in range(0, 95, 15)], fontsize=7.5)
    ax.set_yticks([2, 5, 8, 11, 14, 17])
    ax.set_yticklabels(["Z01-03 (Prop.)", "Z04-06", "Z07-09",
                        "Z10-12", "Z13-15", "Z16-18 (Rival)"], fontsize=7)
    ax.axvline(45, color=PALETTE["muted"], linestyle="--", linewidth=0.8, alpha=0.6)
    ax.grid(True, color=PALETTE["grid"], linewidth=0.5, alpha=0.7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ordered = events.sort_values(["minute", "zone", "team", "event_type"], kind="mergesort")
    for row in ordered.itertuples(index=False):
        color = PALETTE["brand"] if row.team == "rival" else PALETTE["opp"]
        is_goal = row.event_type == "goal"
        marker = "*" if is_goal else ("o" if row.event_type == "shot" else "s")
        size = 110 if is_goal else 36
        ax.scatter(row.minute, row.zone, c=color, marker=marker, s=size,
                   edgecolors="white", linewidths=0.6, alpha=0.92, zorder=4 if is_goal else 3)
    return y_top - h - 0.035


def _page_match_plan(fig: Figure, data: Dataset, notes: Notes) -> float:
    y = 0.92
    lines = []
    for i, instruction in enumerate(notes.instructions, 1):
        wrapped = _wrap(instruction, WRAP_FULL)
        lines.append(f"{i}. {wrapped[0]}")
        lines += ["   " + line for line in wrapped[1:]]
    y = _block(fig, y, "Instrucciones", lines)
    if notes.clips:
        clip_lines = []
        for c in notes.clips:
            w = _wrap(c, WRAP_FULL - 2)
            clip_lines.append(f"- {w[0]}")
            clip_lines += ["  " + ln for ln in w[1:]]
        y = _block(fig, y, "Clips de referencia", clip_lines)
    y = _observation(fig, y, notes, "match_plan")
    if y > 0.36:
        _draw_timeline_matrix(fig, data, y - 0.01)
    return y


def _page_sources(fig: Figure, data: Dataset, notes: Notes) -> float:
    n = len(data.matches)
    limits = [ln for i, t in enumerate(_LIMITATIONS)
              for ln in _wrap(f"({chr(97 + i)}) {t}", WRAP_FULL)]
    y = _block(fig, 0.92, "Fuentes de datos y limitaciones", limits)
    sample = (f"Muestra analizada: {n} partido{_plural(n)} analizado{_plural(n)}.")
    if n < MIN_MATCHES:
        sample += " Muestra reducida: con menos de 5 partidos los patrones pueden no ser representativos."
    y = _block(fig, y, None, _wrap(sample, WRAP_FULL), size=9.5)
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


_PAGES = (("Portada", _page_cover), ("Resumen", _page_summary), (SECTIONS[0], _page_identity),
          (SECTIONS[1], _page_in_possession), (SECTIONS[2], _page_out_of_possession),
          (SECTIONS[3], _page_set_pieces), (SECTIONS[4], _page_key_players),
          (SECTIONS[5], _page_match_plan), (SECTIONS[6], _page_sources))


def write_report(data: Dataset, notes: Notes, out: Path,
                 assets_dir: Path | None = None) -> int:
    """Render the 8 pages to `out` atomically; returns pages written.

    A page whose text flows past the footer is still rendered; a stderr
    warning names it and the exit code stays 0 elsewhere. `assets_dir` may
    contain logo.png (rival crest) and opponent_logo.png for the branding.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    n = len(data.matches)
    assets = str(assets_dir) if assets_dir else None
    crest = _crest(assets, "logo.png")
    opp_crest = _crest(assets, "opponent_logo.png")
    figures, overflow = [], []
    for k, (title, build) in enumerate(_PAGES, 1):
        if build is _page_cover:
            figures.append(build(data, notes, crest=crest, opp_crest=opp_crest))
            continue
        fig = _page(title, data.rival, n, k, crest=crest)
        if build is _page_summary:
            bottom = build(fig, data, notes, crest=crest, opp_crest=opp_crest)
        else:
            bottom = build(fig, data, notes)
        if bottom < _FOOTER_Y:
            overflow.append(title)
        figures.append(fig)
    try:
        with rc_context({**charts.rc_style(), "pdf.fonttype": 42}):
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
