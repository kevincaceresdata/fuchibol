"""Merge Sofascore shotmap into events_raw.json (add missing shots, enrich matches).

Zone mapping: Sofascore `x` = % distance FROM the attacked goal (0 = goal line).
  Home (opponent): band = floor(x / 100 * 6)
  Away (rival):    band = floor((100 - x) / 100 * 6)
Lane: lane = 2 - floor(y / 100 * 3). Zone = band * 3 + lane + 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

DETAIL = {"save": "on_target", "miss": "off_target", "block": "blocked"}


def zone_for(is_home: bool, x: float, y: float) -> int:
    """Convert Sofascore shotmap (is_home, x, y) to rivalkit zone 1..18."""
    band = int(x / 100.0 * 6) if is_home else int((100.0 - x) / 100.0 * 6)
    lane = 2 - min(2, max(0, int(y / 100.0 * 3)))
    return min(5, max(0, band)) * 3 + lane + 1


def ts_for(minute: int, first_half_offset: int = 874, second_half_offset: int = 1962) -> int:
    """Approximate video timestamp (seconds) from match minute."""
    offset = first_half_offset if minute <= 45 else second_half_offset
    return int(minute) * 60 + offset + 30


def last_token(name: str) -> str:
    tokens = name.split()
    return tokens[-1].lower() if tokens else ""


def merge_shots(events: Sequence[dict], shots: Sequence[dict],
                home_team: str = "opponent",
                away_team: str = "rival") -> tuple[list[dict], int, list[dict]]:
    """Enrich existing shot events with player names and append missing open-play shots."""
    merged = [dict(e) for e in events]
    consumed = [False] * len(merged)
    added: list[dict] = []
    for s in shots:
        if s.get("shotType") == "goal":
            continue
        minute = int(s["time"])
        team = home_team if s.get("isHome") else away_team
        player = str(s.get("player", ""))
        hit = None
        for i, e in enumerate(merged):
            if consumed[i] or e.get("type") != "shot" or e.get("team") != team:
                continue
            existing_player = str(e.get("player") or "")
            if abs(int(e["minute"]) - minute) <= 1 and (
                not existing_player
                or last_token(existing_player) in last_token(player)
                or last_token(player) in last_token(existing_player)
            ):
                hit = i
                break
        if hit is not None:
            consumed[hit] = True
            if not merged[hit].get("player"):
                merged[hit]["player"] = player
            continue
        added.append({
            "minute": minute,
            "ts": ts_for(minute),
            "type": "shot",
            "team": team,
            "zone": zone_for(bool(s.get("isHome")), float(s["x"]), float(s["y"])),
            "detail": DETAIL.get(str(s.get("shotType", "")), ""),
            "player": player,
        })

    merged.extend(added)
    merged.sort(key=lambda e: (int(e["minute"]), float(e["ts"])))
    return merged, sum(consumed), added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.merge_shotmap")
    parser.add_argument("--shots", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args(argv)

    shots = json.loads(args.shots.read_text(encoding="utf-8"))
    raw = json.loads(args.events.read_text(encoding="utf-8"))
    merged, enriched, added = merge_shots(raw.get("events", []), shots)
    args.events.write_text(
        json.dumps({"events": merged}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"enriched={enriched} | added={len(added)} | total={len(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
