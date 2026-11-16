"""Aggregation of validated events into chart-ready series, plus drawing.

Aggregation is pure pandas and keyed by English enum values. Drawing
functions receive a matplotlib Axes, draw only into it and return it: no
pyplot, no IO. Empty input renders a visible "Sin datos" message instead of
raising or being omitted.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from mplsoccer import Pitch

from .schema import (GAME_STATES, OPPOSING_HALF, VENUES,
                     ZONE_BANDS, ZONE_LANES, Dataset, zone_rect)

LABELS = {
    "shot": "Remate", "goal": "Gol", "corner": "Córner", "free_kick": "Tiro libre",
    "penalty": "Penal", "recovery": "Recuperación",
    "rival": "Rival", "opponent": "Oponente",
    "winning": "Ganando", "drawing": "Empatando", "losing": "Perdiendo",
    "home": "Local", "away": "Visitante",
    "open_play": "Jugada abierta", "set_piece": "Pelota parada", "own_goal": "Autogol",
    "on_target": "Al arco", "off_target": "Desviado", "blocked": "Bloqueado",
    "direct": "Directo", "crossed": "Centro", "short": "Corto",
    "player": "Jugador", "position": "Posición", "starts": "Titularidades",
    "minutes": "Minutos", "matches": "PJ", "goals_for": "Goles a favor/p",
    "goals_against": "Goles en contra/p", "shots": "Remates/p",
    "shots_against": "Remates recibidos/p",
    "no_data": "Sin datos", "": "Sin especificar",
}
INTERVALS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90", "91+")
_INTERVAL_BINS = (0, 15, 30, 45, 60, 75, 90, np.inf)
PRESSING_PROXY_DEFINITION = ("Indicador aproximado (proxy) de presión: recuperaciones "
                             "del rival en campo contrario (zonas 10-18), promedio por partido.")
_ZONE_COUNT = ZONE_BANDS * ZONE_LANES
_BAR_COLOR = "#4472a8"


def plain(text: str) -> str:
    """Escape '$' so hand-typed text never triggers matplotlib mathtext."""
    return text.replace("$", "\\$")


def _label(key) -> str:
    return LABELS.get(key, key) if key != "" else LABELS[""]


def select(events: pd.DataFrame, team: str, types: Iterable[str]) -> pd.DataFrame:
    return events[(events["team"] == team) & events["event_type"].isin(tuple(types))]


def zone_counts(events: pd.DataFrame) -> pd.Series:
    """Remates (shot + goal, own goals excluded) per zone, index 1..18, zeros kept."""
    attempts = events[events["event_type"].isin(("shot", "goal"))
                      & (events["detail"] != "own_goal")]
    counts = attempts["zone"].value_counts()
    return counts.reindex(range(1, _ZONE_COUNT + 1), fill_value=0).astype(int)


def goal_breakdown(events: pd.DataFrame, team: str, by: str) -> pd.Series:
    goals = select(events, team, ("goal",))
    if by == "interval":
        cats = pd.cut(goals["minute"], bins=_INTERVAL_BINS, labels=INTERVALS,
                      right=True, include_lowest=True)
        return cats.value_counts().reindex(INTERVALS, fill_value=0).astype(int)
    if by == "detail":
        order = ("open_play", "set_piece", "penalty", "own_goal", "")
        return goals["detail"].value_counts().reindex(order, fill_value=0).astype(int)
    if by == "game_state":
        return (goals["game_state"].value_counts()
                .reindex(GAME_STATES, fill_value=0).astype(int))
    raise ValueError(f"unknown goal breakdown: {by!r}")


def set_piece_counts(events: pd.DataFrame, team: str) -> pd.Series:
    pieces = select(events, team, ("corner", "free_kick", "penalty"))
    keys = ["penalty" if t == "penalty" else f"{t}/{d}"
            for t, d in zip(pieces["event_type"], pieces["detail"])]
    return pd.Series(keys, dtype=object).value_counts()


def pressing_proxy(data: Dataset) -> pd.Series:
    """Rival recoveries in the opposing half (zones 10-18) per match, 0 when none."""
    zone_ok = data.events["zone"].isin(OPPOSING_HALF)
    recoveries = data.events[(data.events["team"] == "rival")
                             & (data.events["event_type"] == "recovery") & zone_ok]
    counts = recoveries.groupby("match").size()
    index = [f"{d:%d/%m} vs {o}" for d, o in zip(data.matches["date"], data.matches["opponent"])]
    return pd.Series([int(counts.get(m, 0)) for m in data.matches["match"]], index=index)


def lineup_summary(data: Dataset) -> tuple[pd.DataFrame, int]:
    """Per player: most frequent position, starts and minutes; plus distinct XIs."""
    first = data.lineup.drop_duplicates(["match", "player"], keep="first").copy()
    last_tagged = data.events.groupby("match")["minute"].max()
    first["end"] = [max(90, int(last_tagged.get(m, 0))) for m in first["match"]]
    played = first["starter"] | first["minute_in"].notna()
    minutes = (first["minute_out"].fillna(first["end"])
               - first["minute_in"].fillna(0)).where(played, 0).clip(lower=0)
    first["starts"], first["minutes"] = first["starter"].astype(int), minutes.astype(int)
    grouped = first.groupby("player")
    frame = pd.DataFrame({
        "position": grouped["position"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else ""),
        "starts": grouped["starts"].sum(),
        "minutes": grouped["minutes"].sum(),
    }).reset_index()
    frame = frame.sort_values(["minutes", "starts", "player"],
                              ascending=[False, False, True], ignore_index=True)
    elevens = first[first["starter"]].groupby("match")["player"].agg(frozenset).nunique()
    return frame, int(elevens)


def venue_splits(data: Dataset) -> pd.DataFrame:
    """Per-venue per-match averages; a venue with no matches is NaN, not zero."""
    attempts = data.events[data.events["event_type"].isin(("shot", "goal"))
                           & (data.events["detail"] != "own_goal")]
    rows = {}
    for venue in VENUES:
        played = data.matches[data.matches["venue"] == venue]
        if len(played) == 0:
            rows[venue] = {"matches": 0, "goals_for": np.nan, "goals_against": np.nan,
                           "shots": np.nan, "shots_against": np.nan}
            continue
        folder = set(played["match"])
        ours = attempts[attempts["team"] == "rival"]
        theirs = attempts[attempts["team"] == "opponent"]
        rows[venue] = {
            "matches": len(played),
            "goals_for": played["rival_goals"].mean(),
            "goals_against": played["opponent_goals"].mean(),
            "shots": len(ours[ours["match"].isin(folder)]) / len(played),
            "shots_against": len(theirs[theirs["match"].isin(folder)]) / len(played),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def record(matches: pd.DataFrame) -> dict[str, int]:
    return {"wins": int((matches["rival_goals"] > matches["opponent_goals"]).sum()),
            "draws": int((matches["rival_goals"] == matches["opponent_goals"]).sum()),
            "losses": int((matches["rival_goals"] < matches["opponent_goals"]).sum()),
            "goals_for": int(matches["rival_goals"].sum()),
            "goals_against": int(matches["opponent_goals"].sum())}


# --- drawing -------------------------------------------------------------------------

def _draw_pitch(ax: Axes) -> Axes:
    Pitch(pitch_type="opta").draw(ax=ax)
    ax.text(0.98, 1.0, "Ataque →", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8)
    return ax


def _zone_patches(ax: Axes, values: pd.Series, cmap_name: str,
                  labels: pd.Series | None = None) -> None:
    vmax = max(1.0, float(np.nanmax(values.values))) if len(values) else 1.0
    cmap = colormaps[cmap_name]
    for zone in range(1, _ZONE_COUNT + 1):
        value = float(values.get(zone, 0) or 0)
        color = cmap(0.10 + 0.85 * value / vmax) if value > 0 else "white"
        x0, y0, w, h = zone_rect(zone)
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=color,
                               edgecolor="0.75", linewidth=0.6))
        if labels is not None:
            label = labels.get(zone, "")
            if label:
                ax.text(x0 + w / 2, y0 + h / 2, label, ha="center", va="center", fontsize=8)


def _goals_word(n: int) -> str:
    return "1 gol" if n == 1 else f"{n} goles"


def shot_map(ax: Axes, events: pd.DataFrame, team: str, title: str) -> Axes:
    """Zone map of shots (first line) and goals (second line); colour is total attempts."""
    attempts = select(events, team, ("shot", "goal"))
    _draw_pitch(ax)
    ax.set_title(plain(title), fontsize=11, loc="left")
    ax.text(0.0, 1.0, "Primera línea: remates · segunda línea: goles",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=7.5, color="0.35")
    if len(attempts) == 0:
        ax.text(50, 50, LABELS["no_data"], ha="center", va="center",
                fontsize=12, color="0.4")
        return ax
    shots = attempts[attempts["event_type"] == "shot"]["zone"].value_counts()
    goals = attempts[(attempts["event_type"] == "goal")
                     & (attempts["detail"] != "own_goal")]["zone"].value_counts()
    labels = pd.Series({z: f"{int(shots.get(z, 0))}\n{_goals_word(int(goals.get(z, 0)))}"
                        for z in range(1, _ZONE_COUNT + 1) if int(goals.get(z, 0)) > 0
                        or int(shots.get(z, 0)) > 0})
    _zone_patches(ax, zone_counts(attempts).astype(float), "Blues", labels)
    return ax


def zone_map(ax: Axes, values: pd.Series, title: str,
             labels: pd.Series | None = None) -> Axes:
    _draw_pitch(ax)
    ax.set_title(plain(title), fontsize=11, loc="left")
    if len(values) == 0:
        ax.text(50, 50, LABELS["no_data"], ha="center", va="center",
                fontsize=12, color="0.4")
        return ax
    _zone_patches(ax, values, "Blues", labels)
    return ax


def bar_chart(ax: Axes, values: pd.Series, title: str,
              subtitle: str | None = None) -> Axes:
    ax.set_title(plain(title), fontsize=11, loc="left")
    if subtitle:
        ax.text(0.0, 1.005, plain(subtitle), transform=ax.transAxes,
                ha="left", va="bottom", fontsize=8, color="0.35")
    values = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).fillna(0)
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if len(values) == 0 or values.sum() == 0:
        ax.text(0.5, 0.5, LABELS["no_data"], transform=ax.transAxes,
                ha="center", va="center", fontsize=11, color="0.4")
        return ax
    names = [str(_label(k)) for k in values.index]
    ax.bar(range(len(values)), values.values, color=_BAR_COLOR, width=0.65)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(names, fontsize=8.5)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", color="0.9", linewidth=0.6)
    ax.set_axisbelow(True)
    return ax


def _cell(value) -> str:
    if pd.isna(value):
        return "sin datos"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.1f}"
    return str(value)


def table(ax: Axes, frame: pd.DataFrame, title: str) -> Axes:
    ax.axis("off")
    ax.set_title(plain(title), fontsize=11, loc="left")
    if frame.empty:
        ax.text(0.5, 0.5, LABELS["no_data"], transform=ax.transAxes,
                ha="center", va="center", fontsize=11, color="0.4")
        return ax
    headers = [str(_label(c)) for c in frame.columns]
    rows = [[_cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))]

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths))

    y = 0.98
    ax.text(0.02, y, line(headers), transform=ax.transAxes, fontsize=9,
            fontfamily="monospace", va="top")
    for row in rows:
        y -= 0.05
        ax.text(0.02, y, line(row), transform=ax.transAxes, fontsize=9,
                fontfamily="monospace", va="top")
    return ax


def zone_legend(ax: Axes) -> Axes:
    _draw_pitch(ax)
    for zone in range(1, _ZONE_COUNT + 1):
        x0, y0, w, h = zone_rect(zone)
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor="0.93",
                               edgecolor="0.6", linewidth=0.6))
        ax.text(x0 + w / 2, y0 + h / 2, str(zone), ha="center", va="center", fontsize=9)
    return ax
