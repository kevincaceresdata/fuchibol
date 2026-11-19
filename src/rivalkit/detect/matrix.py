"""Zone matrix (6x3, rival's goal left) of all events, one panel per team."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle

LABEL = {
    "goal": "GOL",
    "shot": "REM",
    "corner": "COR",
    "free_kick": "TL",
    "penalty": "PEN",
    "recovery": "REC",
}
DEFAULT_COLORS = {"rival": "#1f6feb", "opponent": "#2f9e5f"}


def load_events_by_team(events_csv: Path,
                        rival_name: str = "Almagro",
                        opponent_name: str = "Agropecuario") -> dict[str, dict[int, list[tuple[str, int, str]]]]:
    by_team: dict[str, dict[int, list[tuple[str, int, str]]]] = defaultdict(lambda: defaultdict(list))
    with Path(events_csv).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            team = rival_name if r["team"].strip().lower() == "rival" else opponent_name
            by_team[team][int(r["zone"])].append(
                (r["event_type"].strip().lower(), int(r["minute"]), r.get("detail", ""))
            )
    return by_team


def draw_panel(ax, team: str, zones: dict[int, list[tuple[str, int, str]]],
               color: str, rival_name: str = "Almagro") -> None:
    ax.add_patch(Rectangle((0, 0), 100, 100, fill=False, ec="#333", lw=2))
    ax.plot([50, 50], [0, 100], color="#333", lw=1.5)
    ax.add_patch(Circle((50, 50), 9.15, fill=False, ec="#333", lw=1.2))
    ax.add_patch(Rectangle((0, 21), 16.5, 58, fill=False, ec="#333", lw=1.2))
    ax.add_patch(Rectangle((83.5, 21), 16.5, 58, fill=False, ec="#333", lw=1.2))
    for z in range(1, 19):
        band, lane = divmod(z - 1, 3)
        x0 = band * 100 / 6
        y0 = (2 - lane) * 100 / 3
        items = zones.get(z, [])
        n = len(items)
        if n:
            ax.add_patch(Rectangle(
                (x0, y0), 100 / 6, 100 / 3,
                fc=color, alpha=min(0.15 + 0.22 * n, 0.85), ec="white", lw=1.5,
            ))
        else:
            ax.add_patch(Rectangle((x0, y0), 100 / 6, 100 / 3, fc="none", ec="#ddd", lw=0.8))
        ax.text(x0 + 1.2, y0 + 100 / 3 - 6.5, f"{z:02d}", fontsize=7, color="#999")
        lines = [f"{LABEL.get(t, t.upper())} {m}'" for t, m, _ in sorted(items, key=lambda i: i[1])]
        if lines:
            ax.text(
                x0 + 50 / 6, y0 + 100 / 6, "\n".join(lines[:5]),
                ha="center", va="center", fontsize=8.5, fontweight="bold", color="#111",
            )
        if len(lines) > 5:
            ax.text(x0 + 50 / 6, y0 + 6, f"+{len(lines) - 5}", ha="center", fontsize=7, color="#555")
    ax.set_xlim(-4, 104)
    ax.set_ylim(-8, 104)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"{team} ({sum(len(v) for v in zones.values())} eventos)",
        fontsize=12, fontweight="bold", color=color,
    )
    ax.text(0, -5, f"← arco de {rival_name}", fontsize=9, color="#555", ha="left")
    ax.text(100, -5, f"ataque {team} →", fontsize=9, color="#555", ha="right")


def render_matrix(events_csv: Path, out_png: Path,
                  rival_name: str = "Almagro",
                  opponent_name: str = "Agropecuario",
                  title: str | None = None) -> Path:
    data = load_events_by_team(events_csv, rival_name=rival_name, opponent_name=opponent_name)
    fig = Figure(figsize=(15, 6.5))
    ax_left = fig.add_subplot(1, 2, 1)
    ax_right = fig.add_subplot(1, 2, 2)
    draw_panel(ax_left, rival_name, data[rival_name], DEFAULT_COLORS["rival"], rival_name=rival_name)
    draw_panel(ax_right, opponent_name, data[opponent_name], DEFAULT_COLORS["opponent"], rival_name=rival_name)
    fig.suptitle(title or f"{opponent_name} vs {rival_name} · matriz de eventos", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    return out_png


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.matrix")
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--rival", default="Almagro")
    parser.add_argument("--opponent", default="Agropecuario")
    args = parser.parse_args(argv)
    out = render_matrix(args.events, args.output, rival_name=args.rival, opponent_name=args.opponent)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
