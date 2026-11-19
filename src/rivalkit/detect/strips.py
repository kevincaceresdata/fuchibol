"""Build film-strip sheets: 12-frame sequences tiled 3x4 with timestamp labels.

- Event sheets (`evNN_mMM.png`): centered on each tagged event (`t-9 .. t+2`, 1s steps)
- Coverage sheets (`covNN.png`): every 10 min of match time, 12 frames at 25s steps (5 min span)
- Generic tiling (`tile_images`): 2-column contact sheet labeled by filename stem
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

CELL_W, CELL_H, LABEL = 640, 360, 20
COLS, ROWS = 3, 4


def event_times(ts: float) -> list[float]:
    """12 timestamps from t-9 to t+2 at 1-second steps."""
    return [float(ts) - 9.0 + k for k in range(12)]


def coverage_times(t0: float, step: float = 25.0) -> list[float]:
    """12 timestamps starting at t0 with 25-second steps (5-minute span)."""
    return [float(t0) + step * k for k in range(12)]


def grab_frame(cap, t: float):
    import cv2

    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, frame = cap.read()
    if not ok:
        return None
    frame = cv2.resize(frame, (CELL_W, CELL_H))
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def render_strip_sheet(cap, times: Sequence[float], out_path: Path) -> Path:
    canvas = Image.new("RGB", (COLS * CELL_W, ROWS * (CELL_H + LABEL)), "black")
    draw = ImageDraw.Draw(canvas)
    for k, t in enumerate(times):
        img = grab_frame(cap, t)
        if img is None:
            continue
        x = (k % COLS) * CELL_W
        y = (k // COLS) * (CELL_H + LABEL)
        canvas.paste(Image.fromarray(img), (x, y + LABEL))
        draw.text((x + 6, y + 3), f"t={t:.0f}s  ({t / 60:.1f} min)", fill="yellow")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path


def tile_images(files: Sequence[Path], out_path: Path, cols: int = 2, label_h: int = 24) -> Path:
    """Tile arbitrary image files into a multi-column contact sheet labeled by stem."""
    paths = [Path(f) for f in files]
    if not paths:
        raise ValueError("tile_images requires at least one image path")
    with Image.open(paths[0]) as first:
        w, h = first.size
    rows = (len(paths) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * w, rows * (h + label_h)), "black")
    draw = ImageDraw.Draw(canvas)
    for k, f in enumerate(paths):
        x = (k % cols) * w
        y = (k // cols) * (h + label_h)
        with Image.open(f) as im:
            canvas.paste(im.copy(), (x, y + label_h))
        draw.text((x + 6, y + 5), f.stem, fill="yellow")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path


def build_match_strips(video_path: Path, events_json_path: Path, out_dir: Path,
                       t_start: int = 900, t_end: int = 8400, t_step: int = 600) -> list[Path]:
    import cv2

    events = json.loads(Path(events_json_path).read_text(encoding="utf-8"))["events"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    written: list[Path] = []
    try:
        for i, ev in enumerate(events, 1):
            ts = float(ev["ts"])
            p = render_strip_sheet(cap, event_times(ts), out_dir / f"ev{i:02d}_m{ev['minute']}.png")
            written.append(p)
        for j, t0 in enumerate(range(t_start, t_end, t_step), 1):
            p = render_strip_sheet(cap, coverage_times(t0), out_dir / f"cov{j:02d}.png")
            written.append(p)
    finally:
        cap.release()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.strips")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    written = build_match_strips(args.video, args.events, args.out)
    print(f"wrote {len(written)} strip sheets -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
