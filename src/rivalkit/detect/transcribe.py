"""Transcribe match audio with faster-whisper (Spanish, base model).

Passes audio as a 16 kHz numpy float32 array directly into `model.transcribe`
to bypass PyAV 19's `decode_audio` incompatibility, writes `transcript.jsonl`
(one segment per line: start/end/text) and `transcript_hits.txt` for commentary
event keywords.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path
from typing import Sequence

import numpy as np

# Recovery vocabulary lives beside KEYWORDS so the transcriber's hit filter
# and the pipeline's recovery classification share one source of truth.
RECOVERY_WORDS: tuple[str, ...] = (
    "recupera", "recupero", "roba", "robo", "quita", "corta", "intercep",
)

KEYWORDS: tuple[str, ...] = (
    "gol", "remate", "cabeza", "córner", "córcer", "corcer", "corner", "esquina",
    "tiro libre", "falta", "penal", "tarjeta", "amarilla", "roja",
    "ataj", "golazo", "palito", "palos", "afuera", "cruc",
    *RECOVERY_WORDS,
)


def resample_8k_to_16k(raw: np.ndarray) -> np.ndarray:
    """Linearly upsample an 8 kHz mono float32 signal to 16 kHz."""
    if len(raw) == 0:
        return np.empty(0, dtype=np.float32)
    return np.interp(
        np.linspace(0, len(raw), len(raw) * 2, endpoint=False),
        np.arange(len(raw)),
        raw,
    ).astype(np.float32)


def match_keywords(text: str, keywords: Sequence[str] = KEYWORDS) -> list[str]:
    """Return commentary event keywords found in `text` (case-insensitive)."""
    low = text.lower()
    return [k for k in keywords if k in low]


def load_wav_16k(audio_path: Path) -> np.ndarray:
    with wave.open(str(audio_path), "rb") as w:
        rate = w.getframerate()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if rate == 8000:
        return resample_8k_to_16k(raw)
    if rate == 16000:
        return raw
    factor = 16000.0 / float(rate)
    out_len = int(round(len(raw) * factor))
    return np.interp(
        np.linspace(0, len(raw), out_len, endpoint=False),
        np.arange(len(raw)),
        raw,
    ).astype(np.float32)


def transcribe_wav(audio_path: Path, out_jsonl: Path, out_hits: Path,
                   model_size: str = "base", device: str = "cpu",
                   compute_type: str = "int8") -> tuple[int, int]:
    from faster_whisper import WhisperModel

    arr = load_wav_16k(Path(audio_path))
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        arr,
        language="es",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True,
    )
    out_jsonl = Path(out_jsonl)
    out_hits = Path(out_hits)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    hits: list[str] = []
    seg_count = 0
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for seg in segments:
            seg_count += 1
            text = seg.text.strip()
            fh.write(json.dumps({
                "start": round(seg.start, 1),
                "end": round(seg.end, 1),
                "text": text,
            }, ensure_ascii=False) + "\n")
            found = match_keywords(text)
            if found:
                hits.append(f"{seg.start:8.1f}s  [{','.join(found)}]  {text}")
    out_hits.write_text("\n".join(hits), encoding="utf-8")
    return seg_count, len(hits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivalkit.detect.transcribe")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--model", default="base")
    args = parser.parse_args(argv)
    out_jsonl = args.out_dir / "transcript.jsonl"
    out_hits = args.out_dir / "transcript_hits.txt"
    n_seg, n_hits = transcribe_wav(args.audio, out_jsonl, out_hits, model_size=args.model)
    print(f"segments={n_seg}, hits={n_hits} -> {out_jsonl}, {out_hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
