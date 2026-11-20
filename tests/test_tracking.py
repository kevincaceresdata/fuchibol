"""Unit and fast integration tests for src/rivalkit/tracking.py."""

from __future__ import annotations

import csv
import sys
import types
from pathlib import Path

import numpy as np
import pytest

import rivalkit.tracking as tracking
from rivalkit.tracking import classify_tracks, is_grass, project_points, window_zone


def _grass_patch(n_green: int) -> np.ndarray:
    """(10, 10, 3) uint8 HSV patch with `n_green` of 100 green pixels."""
    green = np.array([60, 120, 100], dtype=np.uint8)
    other = np.array([10, 120, 100], dtype=np.uint8)
    rows = [green] * n_green + [other] * (100 - n_green)
    return np.array(rows, dtype=np.uint8).reshape(10, 10, 3)


def test_is_grass_green_fraction_exceeds_threshold():
    assert is_grass(_grass_patch(100))
    assert is_grass(_grass_patch(20))  # 0.20 > 0.15
    assert not is_grass(_grass_patch(15))  # 0.15 does not exceed 0.15
    assert is_grass(_grass_patch(15), min_green_fraction=0.1)
    assert not is_grass(_grass_patch(0))


def test_is_grass_hue_and_saturation_boundaries():
    def patch(hue: int, sat: int) -> np.ndarray:
        p = np.zeros((4, 4, 3), dtype=np.uint8)
        p[..., 0], p[..., 1], p[..., 2] = hue, sat, 100
        return p

    assert is_grass(patch(32, 21))
    assert is_grass(patch(100, 21))
    assert not is_grass(patch(31, 21))
    assert not is_grass(patch(101, 21))
    assert not is_grass(patch(60, 20))  # saturation must exceed 20


def test_project_points_maps_frame_corners_to_pitch_meters():
    corners = [
        (0.0, 0.0, 0.0, 0.0),
        (1920.0, 0.0, 105.0, 0.0),
        (0.0, 1080.0, 0.0, 68.0),
        (1920.0, 1080.0, 105.0, 68.0),
    ]
    out = project_points([(960.0, 540.0), (480.0, 270.0)], corners)
    assert out == [(52.5, 34.0), (26.25, 17.0)]


def test_project_points_recovers_a_true_projective_homography():
    h_true = np.array([[0.05, 0.0, 1.5], [0.0, 0.06, -2.0], [1e-5, 2e-5, 1.0]])
    pixels = np.array(
        [[100.0, 120.0], [1500.0, 300.0], [300.0, 900.0], [1800.0, 1000.0], [960.0, 540.0]]
    )
    meters = (h_true @ np.c_[pixels, np.ones(len(pixels))].T).T

    def to_m(row: np.ndarray) -> tuple[float, float]:
        return (row[0] / row[2], row[1] / row[2])

    corr = [(pixels[i, 0], pixels[i, 1], *to_m(meters[i])) for i in range(4)]
    out = project_points([(pixels[4, 0], pixels[4, 1])], corr)
    assert out == [tuple(round(v, 2) for v in to_m(meters[4]))]


def test_project_points_requires_four_correspondences():
    with pytest.raises(ValueError):
        project_points([(1.0, 1.0)], [(0.0, 0.0, 0.0, 0.0)] * 3)


def test_classify_tracks_referee_and_deterministic_team_split():
    rgb = {
        1: [(25, 30, 60), (27, 32, 58)],  # dark shirts
        3: [(28, 29, 55), (26, 31, 57)],
        2: [(235, 235, 240), (230, 232, 238)],  # white shirts
        4: [(240, 238, 245), (236, 240, 242)],
        9: [(200, 120, 40), (198, 118, 38)],  # orange referee shirt
    }
    hues = {1: [124.0, 126.0], 3: [123.0], 2: [90.0, 80.0], 4: [100.0], 9: [10.0, 12.0]}
    out = classify_tracks(rgb, hues)
    assert out[9] == "referee"
    assert out[1] == "dark_team" and out[3] == "dark_team"
    assert out[2] == "light_team" and out[4] == "light_team"
    assert classify_tracks(rgb, hues) == out  # rng seed 7 -> deterministic


def test_classify_tracks_referee_hue_window_edges():
    rgb = {5: [(255, 0, 0)], 6: [(255, 0, 0)], 7: [(255, 0, 0)], 8: [(255, 0, 0)]}
    hues = {5: [5.0], 6: [22.0], 7: [4.0], 8: [23.0]}
    out = classify_tracks(rgb, hues)
    assert out[5] == "referee" and out[6] == "referee"
    assert out[7] != "referee" and out[8] != "referee"


def test_classify_tracks_without_hues_and_single_track():
    two = {1: [(25, 30, 60)], 2: [(235, 235, 240)]}
    out = classify_tracks(two)  # no hues -> nobody can be the referee
    assert set(out.values()) == {"dark_team", "light_team"}
    assert out[1] == "dark_team" and out[2] == "light_team"
    assert classify_tracks({1: [(60, 60, 60)]}) == {}  # one track cannot be split in two


WINDOW_ROWS = [
    {"frame": "90", "class": "player", "x_m": "5.0", "y_m": "34.0"},  # before the window
    {"frame": "100", "class": "player", "x_m": "5.0", "y_m": "34.0"},  # zone 2, left box
    {"frame": "102", "class": "player", "x_m": "6.0", "y_m": "34.0"},  # zone 2, left box
    {"frame": "104", "class": "goalkeeper", "x_m": "2.0", "y_m": "34.0"},  # not a player
    {"frame": "104", "class": "player", "x_m": "90.0", "y_m": "10.0"},  # zone 18, right box
    {"frame": "106", "class": "player", "x_m": "52.5", "y_m": "34.0"},  # zone 11, midfield
    {"frame": "108", "class": "player", "x_m": "50.0", "y_m": "-5.0"},  # off the pitch (y)
    {"frame": "109", "class": "player", "x_m": "5.0", "y_m": "34.0"},  # after the window
]


def test_window_zone_modes_box_and_goal_end():
    out = window_zone(WINDOW_ROWS, 100, 108)
    assert out["count"] == 4
    assert out["zone"] == 2  # mode of zones [2, 2, 18, 11]
    assert out["box_players"] == 3  # 5.0 and 6.0 near L; 105-90=15 near R; midfield out
    assert out["goal_end"] == "L"  # deepest player stands at x=5


def test_window_zone_team_filter_empty_and_tie():
    rows = [
        {"frame": "10", "class": "player", "x_m": "5.0", "y_m": "34.0", "team": "dark_team"},
        {"frame": "10", "class": "player", "x_m": "5.0", "y_m": "34.0", "team": "light_team"},
        {"frame": "11", "class": "player", "x_m": "30.0", "y_m": "10.0", "team": "light_team"},
    ]
    assert window_zone(rows, 10, 11, team="dark_team") == {
        "zone": 2, "count": 1, "box_players": 1, "goal_end": "L",
    }
    light = window_zone(rows, 10, 11, team="light_team")
    assert light["count"] == 2
    assert light["zone"] == 2  # zones [2, 6] tie -> lower median
    assert window_zone(rows, 50, 60) == {
        "zone": None, "count": 0, "box_players": 0, "goal_end": None,
    }


def test_reexports_detect_goal_helpers():
    from rivalkit.detect import analyze_goals

    assert tracking.W is analyze_goals.W
    assert tracking.H is analyze_goals.H
    assert tracking.zone_of is analyze_goals.zone_of
    assert tracking.team_of_patch is analyze_goals.team_of_patch
    assert tracking.analyze_goal_rows is analyze_goals.analyze_goal_rows


def test_heavy_video_stack_stays_lazily_imported():
    assert "cv2" not in sys.modules
    assert "ultralytics" not in sys.modules
    assert "supervision" not in sys.modules


def test_track_clip_writes_foot_rows_per_frame(tmp_path: Path, monkeypatch):
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]

    class FakeCapture:
        def __init__(self, path: str):
            self._frames = list(frames)

        def read(self):
            return (True, self._frames.pop(0)) if self._frames else (False, None)

        def release(self):
            pass

    class FakeResult:
        def __init__(self, xyxy, class_id):
            self.boxes = types.SimpleNamespace(xyxy=xyxy, class_id=class_id)

    class FakeYOLO:
        def __init__(self, model_path: str):
            pass

        def __call__(self, frame, imgsz=640, classes=None, verbose=False):
            xyxy = np.array(
                [[10.0, 20.0, 30.0, 40.0], [50.0, 60.0, 70.0, 80.0]], dtype=np.float32
            )
            return [FakeResult(xyxy, np.array([0, 0]))]

    class FakeDetections:
        def __init__(self, xyxy, class_id):
            self.xyxy = xyxy
            self.class_id = class_id
            self.tracker_id = None

        @classmethod
        def from_ultralytics(cls, result):
            return cls(result.boxes.xyxy, result.boxes.class_id)

    class FakeByteTrack:
        def update_with_detections(self, dets):
            dets.tracker_id = np.array([7, 8])
            return dets

    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace(VideoCapture=FakeCapture))
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    monkeypatch.setitem(
        sys.modules,
        "supervision",
        types.SimpleNamespace(Detections=FakeDetections, ByteTrack=FakeByteTrack),
    )

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"stub")  # the stubbed capture never decodes it
    out = tmp_path / "tracks.csv"

    assert tracking.track_clip(video, out, model_path="stub.pt", imgsz=960) == 3

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["frame", "track_id", "class", "x1", "y1", "x2", "y2", "x", "y"]
    assert len(rows) == 7  # header + 2 players x 3 frames
    assert rows[1] == ["1", "7", "player", "10.0", "20.0", "30.0", "40.0", "20.0", "40.0"]
    assert rows[2] == ["1", "8", "player", "50.0", "60.0", "70.0", "80.0", "60.0", "80.0"]
    assert rows[6][0] == "3"  # last frame row
