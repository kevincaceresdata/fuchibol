"""Classify score digits in every score crop to find exact scoreboard flip times.

Templates are the mean grayscale patch of each digit, built from ranges
whose score state was verified. Unknown state (bar hidden / transition) is
assigned when MSE to the best template exceeds 8x the calibrated noise floor.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

NW, NH = 135, 75
LEFT = (18, 18, 50, 66)
RIGHT = (62, 18, 96, 66)
INTERVAL = 2.0

DEFAULT_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("0", "0", 470, 590),
    ("1", "0", 620, 1690),
    ("1", "1", 1720, 2820),
    ("2", "1", 2870, 3630),
)


def patch(score_dir: Path, n: int, box: tuple[int, int, int, int]) -> np.ndarray:
    with Image.open(Path(score_dir) / f"sc_{n:04d}.jpg") as raw:
        im = raw.convert("L").crop(box)
        return np.asarray(im, dtype=np.float32) / 255.0


def build_templates(score_dir: Path,
                    ranges: Sequence[tuple[str, str, int, int]] = DEFAULT_RANGES,
                    step: int = 7) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    left_tpl: dict[str, np.ndarray] = {}
    right_tpl: dict[str, np.ndarray] = {}
    for l_label, r_label, a, b in ranges:
        ls = [patch(score_dir, n, LEFT) for n in range(a, b, step)]
        rs = [patch(score_dir, n, RIGHT) for n in range(a, b, step)]
        left_tpl[l_label] = np.mean(ls, axis=0)
        right_tpl[r_label] = np.mean(rs, axis=0)
    return left_tpl, right_tpl


def mse(a: np.ndarray, b: np.ndarray) -> float:
    return float(((a - b) ** 2).mean())


def classify_crop(score_dir: Path, n: int,
                  left_tpl: dict[str, np.ndarray],
                  right_tpl: dict[str, np.ndarray]) -> tuple[dict[str, float], dict[str, float]]:
    pl, pr = patch(score_dir, n, LEFT), patch(score_dir, n, RIGHT)
    dl = {k: mse(pl, t) for k, t in left_tpl.items()}
    dr = {k: mse(pr, t) for k, t in right_tpl.items()}
    return dl, dr


def find_flips(score_dir: Path,
               ranges: Sequence[tuple[str, str, int, int]] = DEFAULT_RANGES,
               step_template: int = 7,
               step_noise: int = 13,
               interval: float = INTERVAL,
               out: Path | None = None) -> dict:
    """Classify all score crops, mode-smooth (window 5), and extract score flips."""
    score_dir = Path(score_dir)
    left_tpl, right_tpl = build_templates(score_dir, ranges=ranges, step=step_template)
    files = sorted(score_dir.glob("sc_*.jpg"))
    if not files:
        raise FileNotFoundError(f"no sc_*.jpg crops in {score_dir}")
    n_max = max(int(f.stem.split("_")[1]) for f in files)

    noise: list[float] = []
    for _, _, a, b in ranges:
        for n in range(a, b, step_noise):
            dl, dr = classify_crop(score_dir, n, left_tpl, right_tpl)
            noise.append(min(dl.values()) + min(dr.values()))
    floor = float(np.median(noise))
    thr = max(floor * 8.0, 1e-4)

    states: dict[int, str | None] = {}
    for n in range(1, n_max + 1):
        dl, dr = classify_crop(score_dir, n, left_tpl, right_tpl)
        l_best = min(dl, key=dl.get)
        r_best = min(dr, key=dr.get)
        if dl[l_best] + dr[r_best] > thr:
            states[n] = None
        else:
            states[n] = f"{l_best}-{r_best}"

    seq = [states.get(n) for n in range(1, n_max + 1)]

    def smooth(i: int) -> str | None:
        win = [s for s in seq[max(0, i - 2):i + 3] if s]
        return max(set(win), key=win.count) if win else None

    flips: list[dict] = []
    prev: str | None = None
    for i in range(len(seq)):
        s = smooth(i)
        n = i + 1
        if s != prev:
            if s is not None and prev is not None:
                flips.append({
                    "n": n,
                    "t": round((n - 1) * interval, 1),
                    "from": prev,
                    "to": s,
                })
            prev = s

    payload = {"thr": thr, "floor": floor, "flips": flips}
    if out is not None:
        Path(out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.classify_digits")
    parser.add_argument("--workdir", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    out = args.workdir / "flips.json"
    res = find_flips(args.workdir / "score", out=out)
    print(f"noise floor {res['floor']:.5f} thr {res['thr']:.4f} -> {len(res['flips'])} flips ({out})")
    for f in res["flips"]:
        print(f"  t={f['t']:8.1f}  {f['from']} -> {f['to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
