"""Scoreboard crop diffing, audio RMS peak detection, and crop contact sheets.

CLI usage:
  python -m rivalkit.detect.analyze diff --workdir WORKDIR
  python -m rivalkit.detect.analyze peaks --workdir WORKDIR
  python -m rivalkit.detect.analyze sheet --workdir WORKDIR st 3 15
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

SCORE_INTERVAL = 2.0   # seconds between score crops
STRIP_INTERVAL = 60.0  # seconds between full scoreboard strips


def diff_events(score_dir: Path, out: Path | None = None,
                interval: float = SCORE_INTERVAL) -> dict:
    """Detect score-digit changes across consecutive `sc_*.jpg` crops."""
    score_dir = Path(score_dir)
    files = sorted(score_dir.glob("sc_*.jpg"))
    if len(files) < 2:
        raise ValueError(f"need at least 2 score crops in {score_dir}")
    prev = None
    deltas: list[float] = []
    for f in files:
        with Image.open(f) as raw:
            img = raw.convert("L").resize((64, 36))
            a = np.asarray(img, dtype=np.int16)
        if prev is not None:
            deltas.append(float(np.abs(a - prev).mean()))
        prev = a
    arr = np.array(deltas, dtype=np.float64)
    med = float(np.median(arr))
    thr = max(med * 2.5, 25.0)  # single-digit change ~40-60; bar in/out >100
    hot = arr > thr
    events: list[dict] = []
    i = 0
    while i < len(hot):
        if hot[i]:
            j = i
            while j + 1 < len(hot) and (hot[j + 1] or (j + 2 < len(hot) and hot[j + 2])):
                j += 1
            events.append({
                "first_idx": i + 1,
                "last_idx": j + 1,
                "t_first": round((i + 1) * interval, 1),
                "t_last": round((j + 1) * interval, 1),
                "max_delta": round(float(arr[i:j + 1].max()), 1),
            })
            i = j + 1
        else:
            i += 1
    payload = {
        "threshold": round(float(thr), 2),
        "median_delta": round(float(med), 2),
        "events": events,
    }
    if out is not None:
        Path(out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def contact_sheet(workdir: Path, kind: str, nums: Sequence[int | str],
                  out: Path | None = None) -> Path:
    """Build a 2-column labeled contact sheet from `st_NNNN.jpg` or `sc_NNNN.jpg`."""
    workdir = Path(workdir)
    src = workdir / ("strip" if kind == "st" else "score")
    interval = STRIP_INTERVAL if kind == "st" else SCORE_INTERVAL
    files: list[tuple[int, Path]] = []
    for n in nums:
        idx = int(n)
        pat = f"st_{idx:04d}.jpg" if kind == "st" else f"sc_{idx:04d}.jpg"
        p = src / pat
        if p.exists():
            files.append((idx, p))
    if not files:
        raise FileNotFoundError(f"no {kind} crops found in {src}")
    cols = 2
    with Image.open(files[0][1]) as first_im:
        w, h = first_im.size
    label_h = 22
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * w, rows * (h + label_h)), "black")
    draw = ImageDraw.Draw(canvas)
    for k, (n, p) in enumerate(files):
        with Image.open(p) as im:
            x = (k % cols) * w
            y = (k // cols) * (h + label_h)
            canvas.paste(im.copy(), (x, y + label_h))
        draw.text((x + 4, y + 4), f"#{n} t={(n - 1) * interval:.0f}s", fill="yellow")
    if out is None:
        out = workdir / f"sheet_{kind}_{'_'.join(str(int(n)) for n in nums[:6])}.png"
    out = Path(out)
    canvas.save(out)
    return out


def _sliding_filter_1d(arr: np.ndarray, size: int, fn) -> np.ndarray:
    half = size // 2
    padded = np.pad(arr, (half, half), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, size)
    return fn(windows, axis=-1)


def audio_peaks(wav_path: Path, out: Path | None = None,
                min_prominence_db: float = 6.0, min_spacing_s: int = 6,
                max_peaks: int = 60) -> dict:
    """Compute 1-second RMS dB prominence peaks over a 60s rolling median baseline."""
    wav_path = Path(wav_path)
    if not wav_path.is_file():
        raise FileNotFoundError(f"audio file not found: {wav_path}")
    with wave.open(str(wav_path), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    win = rate  # 1 second window
    nwin = len(raw) // win
    rms = np.sqrt((raw[: nwin * win].reshape(nwin, win) ** 2).mean(axis=1))
    db = 20.0 * np.log10(rms + 1e-9)
    base = _sliding_filter_1d(db, 61, np.median)
    prom = db - base
    local_max = _sliding_filter_1d(prom, 13, np.max)
    cand = np.where((prom == local_max) & (prom > min_prominence_db))[0]
    cand = cand[np.argsort(prom[cand])[::-1]]
    kept: list[int] = []
    for c in cand:
        if all(abs(int(c) - k) > min_spacing_s for k in kept):
            kept.append(int(c))
        if len(kept) >= max_peaks:
            break
    top = sorted((round(float(db[k]), 1), round(float(prom[k]), 1), k) for k in kept)
    payload = {"top": [{"t": k, "db": d, "prominence": p} for d, p, k in top]}
    if out is not None:
        Path(out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.analyze")
    parser.add_argument("cmd", choices=("diff", "peaks", "sheet"))
    parser.add_argument("extra", nargs="*")
    parser.add_argument("--workdir", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    workdir = args.workdir
    if args.cmd == "diff":
        out = workdir / "events.json"
        res = diff_events(workdir / "score", out=out)
        print(f"thr={res['threshold']:.2f}, {len(res['events'])} events -> {out}")
    elif args.cmd == "peaks":
        out = workdir / "peaks.json"
        res = audio_peaks(workdir / "audio.wav", out=out)
        print(f"{len(res['top'])} peaks -> {out}")
    elif args.cmd == "sheet":
        if len(args.extra) < 2:
            parser.error("sheet requires KIND (st|sc) and at least one crop number")
        out = contact_sheet(workdir, args.extra[0], args.extra[1:])
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
