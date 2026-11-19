"""Unit and fast integration tests for src/rivalkit/detect/ submodules."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from rivalkit.detect.analyze import audio_peaks, contact_sheet, diff_events
from rivalkit.detect.analyze_goals import analyze_goal_rows, team_of_patch, zone_of
from rivalkit.detect.classify_digits import LEFT, NW, NH, RIGHT, find_flips
from rivalkit.detect.matrix import render_matrix
from rivalkit.detect.merge_shotmap import merge_shots, ts_for, zone_for
from rivalkit.detect.strips import coverage_times, event_times, tile_images
from rivalkit.detect.transcribe import match_keywords, resample_8k_to_16k


def test_analyze_diff_events_clusters_hot_score_changes(tmp_path: Path):
    score_dir = tmp_path / "score"
    score_dir.mkdir()
    for i in range(1, 11):
        val = 20 if i < 5 else 200
        img = Image.new("L", (135, 75), color=val)
        img.save(score_dir / f"sc_{i:04d}.jpg")
    out = tmp_path / "events.json"
    result = diff_events(score_dir, out=out)
    assert out.is_file()
    assert len(result["events"]) == 1
    ev = result["events"][0]
    assert ev["first_idx"] == 4
    assert ev["t_first"] == 8.0
    assert ev["max_delta"] > 100.0


def test_analyze_audio_peaks_finds_loud_bursts(tmp_path: Path):
    rate = 1000
    duration_s = 80
    rng = np.random.default_rng(42)
    samples = (rng.normal(0, 0.005, rate * duration_s)).astype(np.float32)
    t_sec = np.arange(rate, dtype=np.float32) / rate
    tone = 0.6 * np.sin(2 * np.pi * 200 * t_sec)
    samples[20 * rate:21 * rate] = tone
    samples[55 * rate:56 * rate] = tone
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    wav_path = tmp_path / "audio.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())

    out = tmp_path / "peaks.json"
    res = audio_peaks(wav_path, out=out)
    assert out.is_file()
    times = {p["t"] for p in res["top"]}
    assert 20 in times
    assert 55 in times


def test_analyze_contact_sheet_renders_png(tmp_path: Path):
    strip_dir = tmp_path / "strip"
    strip_dir.mkdir()
    for n in (1, 2):
        Image.new("RGB", (120, 40), color=(40 * n, 80, 120)).save(strip_dir / f"st_{n:04d}.jpg")
    out = contact_sheet(tmp_path, "st", [1, 2])
    assert out.is_file()
    with Image.open(out) as im:
        assert im.size == (240, 40 + 22)


def test_classify_digits_detects_persistent_score_flip(tmp_path: Path):
    score_dir = tmp_path / "score"
    score_dir.mkdir()
    rng = np.random.default_rng(7)
    for n in range(1, 25):
        arr = rng.integers(15, 25, size=(NH, NW), dtype=np.uint8)
        # Left box is bright after crop 12 ("1"), dark before ("0")
        x0, y0, x1, y1 = LEFT
        arr[y0:y1, x0:x1] = 210 if n >= 13 else 30
        rx0, ry0, rx1, ry1 = RIGHT
        arr[ry0:ry1, rx0:rx1] = 30
        Image.fromarray(arr, mode="L").save(score_dir / f"sc_{n:04d}.jpg", quality=95)

    ranges = [("0", "0", 1, 10), ("1", "0", 14, 24)]
    out = tmp_path / "flips.json"
    res = find_flips(score_dir, ranges=ranges, step_template=2, step_noise=2, out=out)
    assert out.is_file()
    assert len(res["flips"]) == 1
    flip = res["flips"][0]
    assert flip["from"] == "0-0"
    assert flip["to"] == "1-0"
    assert 11 <= flip["n"] <= 15


def test_strips_times_and_tile_images(tmp_path: Path):
    ev_t = event_times(100.0)
    assert len(ev_t) == 12
    assert ev_t[0] == 91.0 and ev_t[-1] == 102.0

    cov_t = coverage_times(900.0)
    assert len(cov_t) == 12
    assert cov_t[0] == 900.0 and cov_t[1] == 925.0

    img1 = tmp_path / "a.jpg"
    img2 = tmp_path / "b.jpg"
    Image.new("RGB", (80, 50), "red").save(img1)
    Image.new("RGB", (80, 50), "blue").save(img2)
    out = tile_images([img1, img2], tmp_path / "sheet.png")
    assert out.is_file()
    with Image.open(out) as im:
        assert im.size == (160, 50 + 24)


def test_transcribe_keywords_and_resample():
    raw = np.linspace(-1.0, 1.0, 800, dtype=np.float32)
    resampled = resample_8k_to_16k(raw)
    assert len(resampled) == 1600
    assert resampled.dtype == np.float32

    hits = match_keywords("¡Tremendo remate al arco y es penal para Almagro!")
    assert "remate" in hits
    assert "penal" in hits


def test_merge_shotmap_enriches_existing_and_adds_missing_shots():
    # Home attack near opponent's goal (x=5 -> band 0 -> zones 1..3)
    assert zone_for(True, 5.0, 50.0) == 2
    # Away attack near home goal (x=5 -> 100-5=95 -> band 5 -> zones 16..18)
    assert zone_for(False, 5.0, 50.0) == 17
    assert ts_for(10) == 10 * 60 + 874 + 30
    assert ts_for(60) == 60 * 60 + 1962 + 30

    events = [
        {"minute": 15, "ts": 1800, "type": "shot", "team": "rival", "zone": 17, "detail": "on_target", "player": ""},
    ]
    shots = [
        {"shotType": "goal", "time": 6, "isHome": True, "player": "Alejandro Gagliardi", "x": 8, "y": 50},
        {"shotType": "save", "time": 15, "isHome": False, "player": "Joel Orlando", "x": 10, "y": 50},
        {"shotType": "miss", "time": 30, "isHome": False, "player": "Facundo De La Vega", "x": 18, "y": 20},
    ]
    merged, enriched_count, added = merge_shots(events, shots)
    assert enriched_count == 1
    assert len(added) == 1
    assert len(merged) == 2
    assert merged[0]["player"] == "Joel Orlando"
    assert merged[1]["player"] == "Facundo De La Vega"
    assert merged[1]["detail"] == "off_target"


def test_matrix_renders_two_panel_zone_png(tmp_path: Path):
    out = tmp_path / "matriz_eventos.png"
    render_matrix(Path("data/example/m01/events.csv"), out, rival_name="Almagro", opponent_name="Agropecuario")
    assert out.is_file()
    assert out.stat().st_size > 5000


def test_analyze_goals_hsv_and_metric_zones():
    assert team_of_patch((160, 120, 200)) == "KEEP_PINK"
    assert team_of_patch((25, 140, 220)) == "KEEP_YELLOW"
    assert team_of_patch((115, 120, 180)) == "ALM"
    assert team_of_patch((60, 60, 180)) == "AGR"
    assert zone_of(5.0, 34.0) == 2
    assert zone_of(100.0, 34.0) == 17

    rows = [
        {"frame": "10", "class": "goalkeeper", "x_m": "3.0", "y_m": "34.0", "team": "KEEP_PINK"},
        {"frame": "10", "class": "player", "x_m": "8.5", "y_m": "32.0", "team": "AGR"},
        {"frame": "10", "class": "player", "x_m": "12.0", "y_m": "36.0", "team": "ALM"},
    ]
    info = analyze_goal_rows(rows, target_frame=10, expected_team="AGR")
    assert info["scorer_team_expected"] == "AGR"
    assert info["scorer"]["zone"] == 2
    assert info["goal_end"] == "L"
    assert info["box_players"] == 2
