"""Assisted match-event detection and enrichment pipeline (`rivalkit.detect`)."""

from .analyze import audio_peaks, contact_sheet, diff_events
from .analyze_goals import analyze_goal_rows, team_of_patch, zone_of
from .classify_digits import find_flips
from .matrix import render_matrix
from .merge_shotmap import merge_shots, ts_for, zone_for
from .strips import coverage_times, event_times, tile_images
from .transcribe import KEYWORDS, match_keywords, resample_8k_to_16k

__all__ = [
    "KEYWORDS",
    "analyze_goal_rows",
    "audio_peaks",
    "contact_sheet",
    "coverage_times",
    "diff_events",
    "event_times",
    "find_flips",
    "match_keywords",
    "merge_shots",
    "render_matrix",
    "resample_8k_to_16k",
    "team_of_patch",
    "tile_images",
    "ts_for",
    "zone_for",
    "zone_of",
]
