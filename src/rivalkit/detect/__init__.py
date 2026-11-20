"""Assisted match-event detection and enrichment pipeline (`rivalkit.detect`)."""

from __future__ import annotations

import importlib

_EXPORTS = {
    "audio_peaks": ".analyze",
    "contact_sheet": ".analyze",
    "diff_events": ".analyze",
    "analyze_goal_rows": ".analyze_goals",
    "team_of_patch": ".analyze_goals",
    "zone_of": ".analyze_goals",
    "find_flips": ".classify_digits",
    "render_matrix": ".matrix",
    "merge_shots": ".merge_shotmap",
    "ts_for": ".merge_shotmap",
    "zone_for": ".merge_shotmap",
    "classify_commentary_type": ".pipeline",
    "enrich_with_tracking": ".pipeline",
    "fuse_candidates": ".pipeline",
    "minute_from_ts": ".pipeline",
    "run_pipeline": ".pipeline",
    "coverage_times": ".strips",
    "event_times": ".strips",
    "tile_images": ".strips",
    "KEYWORDS": ".transcribe",
    "match_keywords": ".transcribe",
    "resample_8k_to_16k": ".transcribe",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    mod_name = _EXPORTS.get(name)
    if mod_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = importlib.import_module(mod_name, __name__)
    return getattr(mod, name)
