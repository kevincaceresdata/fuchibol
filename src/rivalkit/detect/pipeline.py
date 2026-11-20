"""Unified autotag candidate fusion and enrichment pipeline.

CLI usage:
  python -m rivalkit.detect.pipeline --workdir WORKDIR
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

from .analyze_goals import W, H, zone_of
from .merge_shotmap import merge_shots
from .transcribe import match_keywords

GOAL_SHOUT_WINDOW_S = 30.0      # gol/golazo within this of a flip is the goal itself
STANDALONE_PEAK_PROMINENCE = 8.5


def minute_from_ts(ts: float, t_1t: float = 874.0, t_2t: float = 1962.0,
                   halftime_ts: float = 3700.0) -> int:
    """Convert a video timestamp (seconds) into a 1-based match minute (1..120)."""
    if ts < halftime_ts:
        return max(1, int((ts - t_1t) // 60) + 1)
    return max(46, min(120, int((ts - t_2t) // 60) + 1))


def classify_commentary_type(text: str) -> tuple[str, str]:
    """Map a commentary segment to (event_type, detail)."""
    low = text.lower()
    if "penal" in low:
        return "penalty", ""
    if any(w in low for w in ("córner", "corner", "córcer", "corcer", "esquina")):
        return "corner", "crossed"
    if "tiro libre" in low or "falta" in low:
        return "free_kick", "direct"
    if "ataj" in low or "arco" in low:
        return "shot", "on_target"
    if "afuera" in low:
        return "shot", "off_target"
    return "shot", ""


def fuse_candidates(flips: Sequence[dict], peaks: Sequence[dict],
                    segments: Sequence[dict], rival_is_away: bool = True,
                    merge_window_s: float = 12.0, t_1t: float = 874.0,
                    t_2t: float = 1962.0,
                    halftime_ts: float = 3700.0) -> list[dict]:
    """Fuse scoreboard flips, commentary hits, and audio peaks into candidates.

    Flips are authoritative goals; commentary hits keep their non-goal keywords
    (gol/golazo is dropped within GOAL_SHOUT_WINDOW_S of a flip so goals are
    not double-counted); a strong peak near a flip or a keyword segment is
    absorbed by it instead of becoming its own shot.
    """

    def minute(ts: float) -> int:
        return minute_from_ts(ts, t_1t=t_1t, t_2t=t_2t, halftime_ts=halftime_ts)

    events: list[dict] = []
    flip_times = [float(f["t"]) for f in flips]
    for f in flips:
        l0, _, r0 = str(f["from"]).partition("-")
        l1, _, r1 = str(f["to"]).partition("-")
        rival = int(r1) > int(r0) if rival_is_away else int(l1) > int(l0)
        events.append({
            "minute": minute(float(f["t"])),
            "ts": float(f["t"]),
            "type": "goal",
            "team": "rival" if rival else "opponent",
            "zone": 17 if rival else 2,
            "detail": "open_play",
            "player": "",
        })

    keyword_times: list[float] = []
    for seg in segments:
        hits = match_keywords(seg["text"])
        if not hits:
            continue
        ts = (float(seg["start"]) + float(seg["end"])) / 2.0
        keyword_times.append(ts)
        if any(abs(ts - ft) <= GOAL_SHOUT_WINDOW_S for ft in flip_times):
            hits = [k for k in hits if k not in ("gol", "golazo")]
            if not hits:
                continue
        etype, detail = classify_commentary_type(seg["text"])
        events.append({
            "minute": minute(ts), "ts": ts, "type": etype, "team": "rival",
            "zone": 17, "detail": detail, "player": "",
        })

    anchors = flip_times + keyword_times
    for p in peaks:
        t = float(p["t"])
        if float(p["prominence"]) < STANDALONE_PEAK_PROMINENCE:
            continue
        if any(abs(t - a) <= merge_window_s for a in anchors):
            continue
        events.append({
            "minute": minute(t), "ts": t, "type": "shot", "team": "rival",
            "zone": 17, "detail": "", "player": "",
        })

    events.sort(key=lambda e: (int(e["minute"]), float(e["ts"])))
    return events


def enrich_with_tracking(events: Sequence[dict], pitch_rows: Sequence[dict],
                         fps: float = 30.0, window_s: float = 3.0) -> list[dict]:
    """Re-zone each event from the modal tracked player zone near its ts."""
    out = [dict(e) for e in events]
    for ev in out:
        zones: list[int] = []
        for r in pitch_rows:
            if r.get("class") != "player":
                continue
            x_m, y_m = float(r["x_m"]), float(r["y_m"])
            if not (0.0 <= x_m <= W and 0.0 <= y_m <= H):
                continue
            if abs(int(r["frame"]) / fps - float(ev["ts"])) <= window_s:
                zones.append(zone_of(x_m, y_m))
        if zones:
            ev["zone"] = Counter(zones).most_common(1)[0][0]
    return out


def run_pipeline(workdir: Path, out_events_raw: Path | None = None,
                 rival_is_away: bool = True) -> list[dict]:
    """Fuse every detection artifact found in `workdir` into `events_raw.json`.

    Inputs (all optional): flips.json (find_flips), peaks.json (audio_peaks),
    transcript.jsonl (transcribe_wav), pitch_positions.csv (tracking, columns
    frame/class/x_m/y_m), and shotmap.json (Sofascore shots).
    """
    workdir = Path(workdir)

    def load_json(name: str):
        path = workdir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    flips = (load_json("flips.json") or {}).get("flips", [])
    peaks = (load_json("peaks.json") or {}).get("top", [])
    segments: list[dict] = []
    transcript = workdir / "transcript.jsonl"
    if transcript.is_file():
        segments = [json.loads(line) for line in
                    transcript.read_text(encoding="utf-8").splitlines() if line.strip()]

    events = fuse_candidates(flips, peaks, segments, rival_is_away=rival_is_away)

    pitch_csv = workdir / "pitch_positions.csv"
    if pitch_csv.is_file():
        with pitch_csv.open(encoding="utf-8", newline="") as fh:
            events = enrich_with_tracking(events, list(csv.DictReader(fh)))

    shots = load_json("shotmap.json")
    if shots:
        home, away = ("opponent", "rival") if rival_is_away else ("rival", "opponent")
        # shortcut: merge_shots orients added-shot zones for rival=away; with
        # rival at home the labels are swapped here but added zones keep the
        # isHome orientation. Upgrade when tagging a rival-home shotmap.
        events, _, _ = merge_shots(events, shots, home_team=home, away_team=away)

    out = Path(out_events_raw) if out_events_raw is not None else workdir / "events_raw.json"
    out.write_text(json.dumps({"events": events}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.pipeline")
    parser.add_argument("--workdir", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--rival-is-home", action="store_true")
    args = parser.parse_args(argv)
    events = run_pipeline(args.workdir, out_events_raw=args.out,
                          rival_is_away=not args.rival_is_home)
    out = args.out if args.out is not None else args.workdir / "events_raw.json"
    print(f"{len(events)} events -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
