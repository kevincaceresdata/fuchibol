"""Render the F36 highlight clips with YOLO tracking, team colours and a zone radar.

Reads the mp4 clips under outreach/almagro-entrega/clips and writes H.264 overlays
to outreach/almagro-entrega/clips_yolo. CPU-only: about 0.5 s/frame at imgsz=640.

The pitch mapping follows the grass mask of every frame, so the radar keeps up with
the broadcast camera pan and zoom instead of a fixed trapezoid.

Usage:
    .venv\\Scripts\\python scripts\\render_yolo_clips.py [--clips 03,04] [--limit 30]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
from ultralytics import YOLO

cv2.setNumThreads(1)

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "outreach" / "almagro-entrega" / "clips"
OUT_DIR = ROOT / "outreach" / "almagro-entrega" / "clips_yolo"
MODEL = Path(r"C:\Users\k3vca\Desktop\Proyectos\football-tracking-lab\models\hf_football.pt")
TITLES = {
    "01": ("5' GOL EN CONTRA (Gagliardi) - Z01", "1T"),
    "02": ("33' ATAQUE ALMAGRO (Orlando) - Z17", "1T"),
    "03": ("42' GOL ALMAGRO (Orlando) - Z17", "1T"),
    "04": ("56' PENAL RECLAMADO (De La Vega) - Z17", "2T"),
    "05": ("61' GOL EN CONTRA (J.C. Vega) - Z02", "2T"),
}
OUT_W, OUT_H = 1280, 720
IMGSZ = 640

# Role ids used as class_id so supervision annotators pick the right colour.
ALM, AGR, REF, BAL = 0, 1, 2, 3
ROLE_COLOR = {ALM: (235, 99, 37), AGR: (245, 245, 245), REF: (40, 170, 255)}
PALETTE = sv.ColorPalette(
    [
        sv.Color(r=37, g=99, b=235),  # Almagro: royal blue
        sv.Color(r=245, g=245, b=245),  # Agropecuario: white
        sv.Color(r=255, g=170, b=40),  # referee / goalkeeper: amber
        sv.Color(r=0, g=235, b=255),  # ball: yellow
    ]
)
ELLIPSE = sv.EllipseAnnotator(color=PALETTE, thickness=2, start_angle=-45, end_angle=235)
TRACE = sv.TraceAnnotator(color=PALETTE, position=sv.Position.BOTTOM_CENTER, trace_length=18, thickness=2)
TRIANGLE = sv.TriangleAnnotator(color=sv.Color(r=0, g=235, b=255), base=13, height=11)


def grass_bbox(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box of the largest grass region: the camera-view anchor for the radar."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (30, 35, 30), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
    if w * h < 0.15 * frame.shape[0] * frame.shape[1]:
        return None
    return x, y, x + w, y + h


def draw_chips(frame: np.ndarray, persons: sv.Detections, roles: list[int], labels: list[str]) -> None:
    """Draw chips widest-first and drop any that would overlap an already placed one."""
    order = sorted(range(len(labels)), key=lambda k: float(persons.xyxy[k][2] - persons.xyxy[k][0]), reverse=True)
    placed: list[tuple[int, int, int, int]] = []
    scale, thick = 0.34, 1
    for k in order:
        text = labels[k]
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        x1, y1, x2, _ = persons.xyxy[k]
        x0 = int((float(x1) + float(x2)) / 2.0 - tw / 2) - 3
        y0 = int(float(y1)) - th - 9
        rect = (x0, y0, x0 + tw + 6, y0 + th + 5)
        if any(rect[0] < p[2] and p[0] < rect[2] and rect[1] < p[3] and p[1] < rect[3] for p in placed):
            continue
        placed.append(rect)
        cv2.rectangle(frame, rect[:2], rect[2:], ROLE_COLOR[roles[k]], -1)
        cv2.putText(frame, text, (rect[0] + 3, rect[1] + th + 1), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (15, 18, 24), thick, cv2.LINE_AA)


def on_pitch(frame: np.ndarray, foot: tuple[float, float]) -> bool:
    """Reject detections whose foot is on the stands, the scoreboard or outside the grass."""
    fh, fw = frame.shape[:2]
    x, y = foot
    if not (0.01 * fw < x < 0.99 * fw and 0.12 * fh < y < 0.995 * fh):
        return False
    ix, iy = int(x), min(int(y) + 3, fh - 1)
    patch = frame[max(0, iy - 8) : iy + 9, max(0, ix - 12) : ix + 13]
    if patch.size == 0:
        return False
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    grass = ((h >= 30) & (h <= 95) & (s >= 30) & (v >= 30)).mean()
    white = ((s < 45) & (v > 120)).mean()
    return bool(grass >= 0.15 or white >= 0.35)


def classify_role(frame: np.ndarray, xyxy: np.ndarray, cls_id: int) -> int:
    """Team of one detection from the blue excess of its torso patch.

    Almagro wears royal blue, Agropecuario white; the ratio of pixels where blue
    clearly beats red separates them far better than median HSV on a 20 px box.
    """
    x1, y1, x2, y2 = (int(v) for v in xyxy)
    h, w = max(2, y2 - y1), max(2, x2 - x1)
    crop = frame[max(0, y1 + int(0.16 * h)) : min(frame.shape[0], y1 + int(0.44 * h)),
                 max(0, x1 + int(0.28 * w)) : min(frame.shape[1], x2 - int(0.28 * w))]
    if crop.size == 0:
        return AGR
    b = crop[..., 0].astype(int)
    g = crop[..., 1].astype(int)
    r = crop[..., 2].astype(int)
    blue = float(((b > r + 30) & (b > 45) & (g < b - 5)).mean())
    if cls_id in (1, 3) and blue < 0.20:
        return REF
    return ALM if blue >= 0.20 else AGR


def draw_radar(frame: np.ndarray, points: list[tuple[float, float, int]], cell: int) -> None:
    """Bottom-right 6x3 camera-view grid, translucent over the video."""
    fh, fw = frame.shape[:2]
    mw, mh = 252, 162
    mx, my = fw - mw - 18, fh - mh - 18
    overlay = frame.copy()
    cv2.rectangle(overlay, (mx - 5, my - 24), (mx + mw + 5, my + mh + 5), (18, 26, 40), -1)
    cv2.rectangle(overlay, (mx, my), (mx + mw, my + mh), (46, 118, 52), -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

    if 1 <= cell <= 18:
        col, row = (cell - 1) // 3, (cell - 1) % 3
        zw, zh = mw / 6.0, mh / 3.0
        zx, zy = mx + int(col * zw), my + int(row * zh)
        tint = frame.copy()
        cv2.rectangle(tint, (zx, zy), (zx + int(zw), zy + int(zh)), (30, 205, 245), -1)
        cv2.addWeighted(tint, 0.35, frame, 0.65, 0, frame)

    for b in range(1, 6):
        gx = mx + int(b * mw / 6.0)
        cv2.line(frame, (gx, my), (gx, my + mh), (110, 175, 115), 1)
    for lane in range(1, 3):
        gy = my + int(lane * mh / 3.0)
        cv2.line(frame, (mx, gy), (mx + mw, gy), (110, 175, 115), 1)
    cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), (235, 240, 235), 1)

    for nx, ny, role in points:
        rx = mx + int(np.clip(nx, 0.02, 0.98) * mw)
        ry = my + int(np.clip(ny, 0.02, 0.98) * mh)
        cv2.circle(frame, (rx, ry), 4, ROLE_COLOR.get(role, (245, 245, 245)), -1)
        cv2.circle(frame, (rx, ry), 5, (15, 15, 15), 1)

    cv2.putText(frame, "RADAR VISTA CAMARA  |  18 CELDAS", (mx + 2, my - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.34, (240, 244, 250), 1, cv2.LINE_AA)


def render_clip(src: Path, dst: Path, title: str, half: str, limit: int | None) -> int:
    model = YOLO(str(MODEL))
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if limit:
        total = min(total, limit)
    raw = dst.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (OUT_W, OUT_H))
    votes: dict[int, list[int]] = {}
    frame_n = 0

    while frame_n < total:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (OUT_W, OUT_H))
        result = model.track(frame, imgsz=IMGSZ, conf=0.30, iou=0.5, classes=[0, 1, 2, 3],
                             persist=True, tracker="bytetrack.yaml", verbose=False)[0]
        dets = sv.Detections.from_ultralytics(result)
        if dets.tracker_id is None:
            dets.tracker_id = np.arange(len(dets))

        keep = []
        for i, (xyxy, cid) in enumerate(zip(dets.xyxy, dets.class_id)):
            foot = (float((xyxy[0] + xyxy[2]) / 2.0), float(xyxy[3]))
            if int(cid) == 0 or on_pitch(frame, foot):
                keep.append(i)
        dets = dets[np.array(keep, dtype=int)] if keep else dets[:0]
        balls = dets[dets.class_id == 0]
        persons = dets[dets.class_id != 0]

        roles, labels, feet = [], [], []
        for xyxy, cid, tid in zip(persons.xyxy, persons.class_id, persons.tracker_id):
            role = classify_role(frame, xyxy, int(cid))
            hist = votes.setdefault(int(tid), [])
            hist.append(role)
            role = max(set(hist[-20:]), key=hist[-20:].count)
            roles.append(role)
            labels.append(("ALM" if role == ALM else "AGR" if role == AGR else "REF") + f" #{int(tid)}")
            feet.append(((float(xyxy[0]) + float(xyxy[2])) / 2.0, float(xyxy[3])))

        if len(persons):
            persons.class_id = np.array(roles, dtype=int)
            frame = TRACE.annotate(scene=frame, detections=persons)
            frame = ELLIPSE.annotate(scene=frame, detections=persons)
            draw_chips(frame, persons, roles, labels)
        if len(balls):
            balls.class_id = np.full(len(balls), BAL, dtype=int)
            frame = TRIANGLE.annotate(scene=frame, detections=balls)

        bbox = grass_bbox(frame)
        projected, cells = [], []
        if bbox and feet:
            x0, y0, x1, y1 = bbox
            for (fx, fy), role in zip(feet, roles):
                nx = (fx - x0) / max(1.0, x1 - x0)
                ny = (fy - y0) / max(1.0, y1 - y0)
                projected.append((nx, ny, role))
                if role in (ALM, AGR) and 0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0:
                    cells.append(min(5, int(nx * 6)) * 3 + min(2, int(ny * 3)) + 1)
        cell = max(set(cells), key=cells.count) if cells else 0
        if cell:
            draw_radar(frame, projected, cell)

        fh = frame.shape[0]
        overlay = frame.copy()
        cv2.rectangle(overlay, (16, fh - 68), (560, fh - 14), (18, 28, 48), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        cv2.putText(frame, "RIVALKIT  |  " + title, (26, fh - 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)
        n_alm = sum(1 for r in roles if r == ALM)
        n_agr = sum(1 for r in roles if r == AGR)
        cv2.putText(frame, f"Almagro {n_alm}  |  Agropecuario {n_agr}  |  {half}  |  celda C{cell:02d}",
                    (26, fh - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (150, 195, 245), 1, cv2.LINE_AA)

        writer.write(frame)
        frame_n += 1
        if frame_n % 150 == 0:
            print(f"  {dst.name}: {frame_n}/{total} frames", flush=True)

    cap.release()
    writer.release()
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw), "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    raw.unlink(missing_ok=True)
    return frame_n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render YOLO overlay clips for the F36 package.")
    ap.add_argument("--clips", default="", help="comma separated clip prefixes, e.g. 03,04")
    ap.add_argument("--limit", type=int, default=0, help="render only the first N frames per clip")
    args = ap.parse_args(argv)

    wanted = [f"{int(t):02d}" if t.strip().isdigit() else t.strip()
              for t in args.clips.split(",") if t.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {p.stem.split("_")[0]: p for p in sorted(SRC_DIR.glob("*.mp4"))}
    if not sources:
        print(f"no clips under {SRC_DIR}", file=sys.stderr)
        return 1
    order = wanted or sorted(sources)
    for prefix in order:
        src = sources.get(prefix)
        if src is None:
            print(f"skip {prefix}: no source clip", file=sys.stderr)
            continue
        title, half = TITLES.get(prefix, (src.stem, "1T"))
        dst = OUT_DIR / f"yolo_{src.stem}.mp4"
        print(f"rendering {src.name} -> {dst.name}", flush=True)
        n = render_clip(src, dst, title, half, args.limit or None)
        print(f"  done: {n} frames, {dst.stat().st_size // 1024} KB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
