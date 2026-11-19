"""Cross-match tracking with event data: scorer zone, keeper colors, box occupation.

Reads tracking CSVs (`pitch_gN.csv`), samples torso HSV colors from goal clips,
and reports per goal: deepest attacker at the goal frame with pitch position +
rivalkit zone, keeper colors by end, and box occupation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

import numpy as np

W, H = 105.0, 68.0
DEFAULT_CLIPS = {
    1: ("goal1.mp4", 1188.0, 1201.0),
    2: ("goal2.mp4", 3388.0, 3399.5),
    3: ("goal3.mp4", 5650.0, 5665.0),
}
DEFAULT_SCORER_TEAM = {1: "AGR", 2: "ALM", 3: "AGR"}


def team_of_patch(hsv: Sequence[float]) -> str:
    """Classify mean HSV torso patch into keeper/team color label."""
    h, s, v = float(hsv[0]), float(hsv[1]), float(hsv[2])
    if s > 70 and (h >= 145 or h <= 8):
        return "KEEP_PINK"
    if s > 80 and 18 <= h <= 38:
        return "KEEP_YELLOW"
    if s > 60 and 95 <= h <= 140:
        return "ALM"
    if s < 80 and v > 110:
        return "AGR"
    if s > 40 and 40 <= h <= 90:
        return "AGR"
    return "?"


def zone_of(xm: float, ym: float) -> int:
    """Map metric pitch coordinates (105x68 m) to rivalkit zone 1..18."""
    band = min(5, max(0, int(xm / (W / 6.0))))
    lane = 2 - min(2, max(0, int(ym / (H / 3.0))))
    return band * 3 + lane + 1


def sample_colors(clip_path: Path, rows: list[dict], target_frame: int) -> None:
    import cv2

    want: dict[int, list[dict]] = {
        int(r["frame"]): [] for r in rows if int(r["frame"]) <= target_frame + 40
    }
    for r in rows:
        f = int(r["frame"])
        if f in want:
            want[f].append(r)
    cap = cv2.VideoCapture(str(clip_path))
    n_frame = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            n_frame += 1
            if n_frame not in want:
                continue
            for r in want[n_frame]:
                x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
                cx, cy = int((x1 + x2) / 2), int(y1 + 0.28 * (y2 - y1))
                patch = frame[max(0, cy - 6):cy + 6, max(0, cx - 6):cx + 6]
                if patch.size == 0:
                    r["team"] = "?"
                    continue
                hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3).mean(axis=0)
                r["team"] = team_of_patch(hsv)
    finally:
        cap.release()


def analyze_goal_rows(rows: Sequence[dict], target_frame: int, expected_team: str) -> dict:
    """Summarize deepest players, scorer proxy, goal end, and box occupation at `target_frame`."""
    at = [
        r for r in rows
        if int(r["frame"]) == target_frame
        and r.get("class") == "player"
        and 0.0 <= float(r["x_m"]) <= W
    ]
    deep = sorted(at, key=lambda r: min(float(r["x_m"]), W - float(r["x_m"])))[:4]
    scorer = deep[0] if deep else None
    gx = 0.0 if scorer and float(scorer["x_m"]) < W / 2.0 else W
    box = [r for r in at if abs(float(r["x_m"]) - gx) <= 16.5]
    return {
        "scorer_team_expected": expected_team,
        "scorer": ({
            "x_m": round(float(scorer["x_m"]), 1),
            "y_m": round(float(scorer["y_m"]), 1),
            "zone": zone_of(float(scorer["x_m"]), float(scorer["y_m"])),
            "color": scorer.get("team"),
        } if scorer else None),
        "deep_players": [{
            "x_m": round(float(r["x_m"]), 1),
            "y_m": round(float(r["y_m"]), 1),
            "zone": zone_of(float(r["x_m"]), float(r["y_m"])),
            "color": r.get("team"),
        } for r in deep],
        "box_players": len(box),
        "box_colors": dict(Counter(r.get("team") for r in box)),
        "goal_end": "L" if gx == 0.0 else "R",
    }


def analyze_lab_goals(lab_dir: Path,
                      clips: dict[int, tuple[str, float, float]] = DEFAULT_CLIPS,
                      scorer_teams: dict[int, str] = DEFAULT_SCORER_TEAM) -> dict:
    lab_dir = Path(lab_dir)
    report: dict[str, dict] = {}
    for n, (clip_name, t0, tg) in clips.items():
        csv_path = lab_dir / "output" / f"pitch_g{n}.csv"
        with csv_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        target = int((tg - t0) * 30)
        sample_colors(lab_dir / "data" / clip_name, rows, target)
        report[f"goal{n}"] = analyze_goal_rows(rows, target, scorer_teams.get(n, "?"))
    out = lab_dir / "output" / "goal_analysis.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.analyze_goals")
    parser.add_argument("--lab-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = analyze_lab_goals(args.lab_dir)
    print(f"analyzed {len(report)} goals -> {args.lab_dir / 'output' / 'goal_analysis.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
