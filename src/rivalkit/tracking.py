"""Player tracking: YOLO + ByteTrack pixels, homography to meters, shirt classification.

Flat module (schema.py-style): pure helpers first, the video runner last with lazy
imports so the test suite runs without cv2/ultralytics/supervision. The pitch
helpers already proven in `rivalkit.detect.analyze_goals` are re-exported here
instead of duplicated.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from statistics import median_low
from typing import Sequence

import numpy as np

from rivalkit.detect.analyze_goals import (
    W,
    H,
    analyze_goal_rows,
    team_of_patch,
    zone_of,
)

# Grass gate in OpenCV HSV units (hue 0..180).
GRASS_HUE_MIN, GRASS_HUE_MAX, GRASS_SAT_MIN = 32, 100, 20
# Referee shirts: orange hue window in OpenCV HSV units.
REFEREE_HUE_MIN, REFEREE_HUE_MAX = 5, 22
TRACKS_HEADER = ("frame", "track_id", "class", "x1", "y1", "x2", "y2", "x", "y")


def is_grass(hsv_patch: np.ndarray, min_green_fraction: float = 0.15) -> bool:
    """True when the fraction of green pixels (hue 32..100, sat > 20) exceeds the threshold."""
    hsv = np.asarray(hsv_patch)
    if hsv.size == 0:
        return False
    hue, sat = hsv[..., 0], hsv[..., 1]
    green = (hue >= GRASS_HUE_MIN) & (hue <= GRASS_HUE_MAX) & (sat > GRASS_SAT_MIN)
    return bool(green.mean() > min_green_fraction)


def project_points(
    pixel_points: Sequence[tuple[float, float]],
    correspondences: Sequence[tuple[float, float, float, float]],
) -> list[tuple[float, float]]:
    """Project pixel (x, y) points to pitch meters via a DLT/SVD planar homography.

    `correspondences` are (x_px, y_px, x_m, y_m); at least 4, in general position.
    shortcut: callers pass one fixed calibration per camera angle instead of
    recalibrating per frame; recalibrate when the broadcast angle changes.
    """
    if len(correspondences) < 4:
        raise ValueError(f"homography needs >= 4 correspondences, got {len(correspondences)}")
    a = np.zeros((2 * len(correspondences), 9), dtype=np.float64)
    for i, (x, y, u, v) in enumerate(correspondences):
        a[2 * i] = (x, y, 1, 0, 0, 0, -u * x, -u * y, -u)
        a[2 * i + 1] = (0, 0, 0, x, y, 1, -v * x, -v * y, -v)
    _, _, vt = np.linalg.svd(a)
    h = vt[-1].reshape(3, 3)
    h = h / h[2, 2]
    out: list[tuple[float, float]] = []
    for x, y in pixel_points:
        p = h @ np.array([x, y, 1.0])
        out.append((round(float(p[0] / p[2]), 2), round(float(p[1] / p[2]), 2)))
    return out


def classify_tracks(
    track_rgb_samples: dict[int, Sequence[tuple[float, float, float]]],
    track_hues: dict[int, Sequence[float]] | None = None,
) -> dict[int, str]:
    """Label tracks "referee" (median hue 5..22); split the rest into
    "dark_team"/"light_team" by deterministic 2-means (seed 7) on mean RGB,
    where the centroid with the lower channel sum is the dark team."""
    labels: dict[int, str] = {}
    hues = track_hues or {}
    remaining: list[int] = []
    for tid, samples in track_rgb_samples.items():
        if tid in hues and REFEREE_HUE_MIN <= float(np.median(hues[tid])) <= REFEREE_HUE_MAX:
            labels[tid] = "referee"
        else:
            remaining.append(tid)
    if len(remaining) < 2:
        return labels  # a single track cannot be split into two teams
    pts = np.array(
        [np.mean(track_rgb_samples[tid], axis=0) for tid in remaining], dtype=np.float64
    )
    rng = np.random.default_rng(7)
    centroids = pts[rng.choice(len(pts), size=2, replace=False)]
    assigned = np.zeros(len(pts), dtype=np.int64)
    for _ in range(50):
        dists = ((pts[:, None, :] - centroids[None, :, :]) ** 2).sum(-1)
        assigned = dists.argmin(axis=1)
        new_centroids = np.array([
            pts[assigned == k].mean(axis=0) if (assigned == k).any() else centroids[k]
            for k in (0, 1)
        ])
        if np.allclose(new_centroids, centroids):
            break
        centroids = new_centroids
    dark = int(np.argmin(centroids.sum(axis=1)))
    for tid, k in zip(remaining, assigned):
        labels[tid] = "dark_team" if k == dark else "light_team"
    return labels


def window_zone(
    rows: Sequence[dict],
    frame_start: int,
    frame_end: int,
    team: str | None = None,
) -> dict:
    """Summarize player rows in [frame_start, frame_end]: modal zone (median on
    tie), row count, players within 16.5 m of a goal line, and the goal end of
    the deepest player."""
    matched = [
        r for r in rows
        if frame_start <= int(r["frame"]) <= frame_end
        and r.get("class") == "player"
        and 0.0 <= float(r["x_m"]) <= W
        and 0.0 <= float(r["y_m"]) <= H
        and (team is None or r.get("team") == team)
    ]
    if not matched:
        return {"zone": None, "count": 0, "box_players": 0, "goal_end": None}
    zones = [zone_of(float(r["x_m"]), float(r["y_m"])) for r in matched]
    counts = Counter(zones)
    top = max(counts.values())
    winners = [z for z, c in counts.items() if c == top]
    zone = winners[0] if len(winners) == 1 else int(median_low(zones))
    box_players = sum(
        1 for r in matched if min(float(r["x_m"]), W - float(r["x_m"])) <= 16.5
    )
    deepest = min(matched, key=lambda r: min(float(r["x_m"]), W - float(r["x_m"])))
    goal_end = "L" if float(deepest["x_m"]) < W / 2.0 else "R"
    return {
        "zone": zone,
        "count": len(matched),
        "box_players": box_players,
        "goal_end": goal_end,
    }


def track_clip(
    video_path: Path,
    out_csv: Path,
    model_path: str = "yolov8s.pt",
    imgsz: int = 960,
) -> int:
    """Run YOLOv8 persons + ByteTrack over a clip; write one CSV row per tracked
    player per frame, where (x, y) is the foot (bottom-center of the bbox).
    Returns the number of frames processed."""
    import cv2
    import supervision as sv
    from ultralytics import YOLO

    model = YOLO(model_path)
    tracker = sv.ByteTrack()
    cap = cv2.VideoCapture(str(video_path))
    n = 0
    try:
        with Path(out_csv).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(TRACKS_HEADER)
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                n += 1
                result = model(frame, imgsz=imgsz, classes=[0], verbose=False)[0]
                tracks = tracker.update_with_detections(
                    sv.Detections.from_ultralytics(result)
                )
                if tracks.tracker_id is None:
                    continue
                for box, tid in zip(tracks.xyxy, tracks.tracker_id):
                    x1, y1, x2, y2 = (float(v) for v in box)
                    writer.writerow([
                        n, int(tid), "player",
                        round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1),
                        round((x1 + x2) / 2.0, 1), round(y2, 1),
                    ])
    finally:
        cap.release()
    return n
