"""Input contracts: per-match CSV folders and the analyst notes file.

Everything is validated as raw strings and every error is collected before any
typed object is built, so pandas never sees invalid data.
"""

from __future__ import annotations

import csv
import io
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

EVENT_TYPES = ("shot", "goal", "corner", "free_kick", "penalty", "recovery")
TEAMS = ("rival", "opponent")
GAME_STATES = ("winning", "drawing", "losing")
VENUES = ("home", "away")
DETAILS = {
    "goal": ("open_play", "set_piece", "penalty", "own_goal"),
    "shot": ("on_target", "off_target", "blocked"),
    "corner": ("direct", "crossed", "short"),
    "free_kick": ("direct", "crossed", "short"),
}
ZONE_BANDS, ZONE_LANES = 6, 3
OPPOSING_HALF = tuple(range(10, 19))
NOTE_SECTIONS = ("identity_and_lineup", "in_possession", "out_of_possession",
                 "set_pieces", "key_players", "match_plan", "sources")

# Enum-like columns are lowercased (Excel writes TRUE, taggers capitalise).
_LOWER = {"event_type", "team", "game_state", "venue", "starter", "detail"}


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


def zone_rect(zone: int) -> tuple[float, float, float, float]:
    """(x0, y0, w, h) of a zone in mplsoccer opta units; lane 1 (left) is the top strip."""
    band, lane = divmod(zone - 1, ZONE_LANES)
    return (band * 100 / ZONE_BANDS, (ZONE_LANES - 1 - lane) * 100 / ZONE_LANES,
            100 / ZONE_BANDS, 100 / ZONE_LANES)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # ponytail: cp1252 may mis-decode other legacy encodings; add an --encoding flag if so
        return raw.decode("cp1252", errors="replace")


# --- checkers: value -> None or a problem string ---------------------------------

Check = Callable[[str], "str | None"]


def integer(lo: int, hi: int | None = None) -> Check:
    def check(v: str) -> str | None:
        if re.fullmatch(r"-?\d+", v) and int(v) >= lo and (hi is None or int(v) <= hi):
            return None
        return f"is not an integer from {lo} to {hi}" if hi is not None else f"is not an integer >= {lo}"
    return check


def choice(values: Sequence[str]) -> Check:
    return lambda v: None if v in values else f"is not one of {', '.join(values)}"


def iso_date() -> Check:
    def check(v: str) -> str | None:
        try:
            date.fromisoformat(v)
        except ValueError:
            return "is not a date in YYYY-MM-DD format"
        return None
    return check


def optional(check: Check) -> Check:
    return lambda v: None if v == "" else check(v)


# Column -> checker (None = free text, only the column must exist).
MATCH = {"match_id": None, "date": iso_date(), "rival_team": None, "opponent": None,
         "venue": choice(VENUES), "rival_goals": integer(0), "opponent_goals": integer(0),
         "competition": None}
EVENTS = {"minute": integer(0, 120), "event_type": choice(EVENT_TYPES), "team": choice(TEAMS),
          "zone": integer(1, ZONE_BANDS * ZONE_LANES), "game_state": choice(GAME_STATES),
          "player": None, "detail": None}
LINEUP = {"player": None, "shirt_number": None, "position": None,
          "starter": choice(("true", "false")),
          "minute_in": optional(integer(0, 120)), "minute_out": optional(integer(0, 120))}


def _event_combo(row: dict) -> str | None:
    allowed = DETAILS.get(row["event_type"])
    if allowed and row["detail"] and row["detail"] not in allowed:
        return (f"detail: '{row['detail']}' is not allowed for {row['event_type']} "
                f"(allowed: {', '.join(allowed)}, or empty)")
    return None


def _lineup_combo(row: dict) -> str | None:
    a, b = row["minute_in"], row["minute_out"]
    if a.isdigit() and b.isdigit() and int(b) < int(a):
        return f"minute_in, minute_out: minute_out {b} is lower than minute_in {a}"
    return None


def _one_row(rows: list, label: str) -> str | None:
    return None if len(rows) == 1 else f"{label}: exactly one data row is required, found {len(rows)}"


def _eleven(rows: list, label: str) -> str | None:
    n = sum(r["starter"] == "true" for r in rows)
    return None if n == 11 else f"{label}: expected exactly 11 starters, found {n}"


def _read_table(folder: Path, name: str, spec: dict, errors: list[str],
                combo=None, filecheck=None) -> tuple[list[dict], bool]:
    """Parse and check one CSV. Returns (rows keeping only spec columns, no errors found)."""
    label = f"{folder.as_posix()}/{name}"
    path = folder / name
    if not path.is_file():
        errors.append(f"{label}: file not found")
        return [], False
    before = len(errors)
    text = _read_text(path)
    header = next((ln for ln in text.splitlines() if ln.strip()), "")
    reader = csv.DictReader(io.StringIO(text), delimiter=";" if header.count(";") > header.count(",") else ",")
    reader.fieldnames = [f.strip() for f in reader.fieldnames or []]
    missing = [c for c in spec if c not in reader.fieldnames]
    if missing:
        errors.append(f"{label}: missing columns: {', '.join(missing)}")
    rows = []
    for raw in reader:
        row = {c: (raw.get(c) or "").strip() for c in spec if c in reader.fieldnames}
        for c in _LOWER & row.keys():
            row[c] = row[c].lower()
        n = reader.line_num
        for c, check in spec.items():
            problem = check(row[c]) if check and c in row else None
            if problem:
                errors.append(f"{label}:{n}: {c}: '{row[c]}' {problem}")
        if combo and not missing:
            problem = combo(row)
            if problem:
                errors.append(f"{label}:{n}: {problem}")
        rows.append(row)
    if filecheck and not missing:
        problem = filecheck(rows, label)
        if problem:
            errors.append(problem)
    return rows, len(errors) == before


def _frame(rows: list[dict], columns, folder: str) -> pd.DataFrame:
    return pd.DataFrame([{"match": folder, **r} for r in rows], columns=["match", *columns])


def _nullable_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace("", None)).astype("Int64")


@dataclass(frozen=True)
class Dataset:
    rival: str
    matches: pd.DataFrame
    events: pd.DataFrame
    lineup: pd.DataFrame


def load_matches(folders: Sequence[Path]) -> Dataset:
    errors: list[str] = []
    seen, loaded = set(), []
    for folder in map(Path, folders):
        key = folder.resolve()
        if key in seen:
            continue
        seen.add(key)
        if not folder.is_dir():
            errors.append(f"{folder.as_posix()}: not an existing folder")
            continue
        m, m_ok = _read_table(folder, "match.csv", MATCH, errors, filecheck=_one_row)
        e, e_ok = _read_table(folder, "events.csv", EVENTS, errors, combo=_event_combo)
        l, l_ok = _read_table(folder, "lineup.csv", LINEUP, errors, combo=_lineup_combo, filecheck=_eleven)
        if m_ok and e_ok:
            for team in TEAMS:
                goals = sum(r["event_type"] == "goal" and r["team"] == team for r in e)
                if goals != int(m[0][f"{team}_goals"]):
                    errors.append(f"{folder.as_posix()}: {team} goals: match.csv says "
                                  f"{m[0][team + '_goals']}, events.csv has {goals} {team} goal events")
        if m_ok:
            loaded.append((folder, m, e, l))
    first = None
    for folder, m, *_ in loaded:
        if first is None:
            first = (m[0]["rival_team"], folder)
        elif m[0]["rival_team"] != first[0]:
            errors.append(f"{folder.as_posix()}/match.csv:2: rival_team: '{m[0]['rival_team']}' "
                          f"differs from '{first[0]}' in {first[1].as_posix()}")
    if errors:
        raise ValidationError(errors)

    cat = lambda frames, cols: (pd.concat(frames, ignore_index=True) if frames
                                else pd.DataFrame(columns=["match", *cols]))
    matches = cat([_frame(m, MATCH, f.as_posix()) for f, m, *_ in loaded], MATCH)
    events = cat([_frame(e, EVENTS, f.as_posix()) for f, _, e, *_ in loaded], EVENTS)
    lineup = cat([_frame(l, LINEUP, f.as_posix()) for f, _, _, l in loaded], LINEUP)
    matches["date"] = pd.to_datetime(matches["date"])
    for c in ("rival_goals", "opponent_goals"):
        matches[c] = matches[c].astype(int)
    matches = matches.sort_values(["date", "match_id", "match"], ignore_index=True)
    events["minute"] = events["minute"].astype(int)
    events["zone"] = events["zone"].astype(int)
    lineup["starter"] = lineup["starter"] == "true"
    for c in ("minute_in", "minute_out"):
        lineup[c] = _nullable_int(lineup[c])
    return Dataset(matches["rival_team"].iloc[0] if len(matches) else "", matches, events, lineup)


# --- analyst notes -----------------------------------------------------------------

_TOP = ("summary", "plan", "observations", "key_players")
_KEYS = {"summary": ("identity", "weaknesses", "threats"), "plan": ("instructions", "clips"),
         "observations": NOTE_SECTIONS}


@dataclass(frozen=True)
class Notes:
    identity: str
    weaknesses: tuple[str, ...]
    threats: tuple[str, ...]
    instructions: tuple[str, ...]
    clips: tuple[str, ...]
    observations: dict[str, str]
    key_players: tuple[tuple[str, str], ...]


def load_notes(path: Path) -> Notes:
    path = Path(path)
    label = path.as_posix()
    if not path.is_file():
        raise ValidationError([f"{label}: file not found"])
    try:
        data = tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError([f"{label}: invalid TOML: {exc}"])

    errors: list[str] = []

    def table(key: str) -> dict:
        value = data.get(key, {})
        if not isinstance(value, dict):
            errors.append(f"{label}: {key} must be a table, for example [{key}]")
            return {}
        for k in value:
            if k not in _KEYS[key]:
                errors.append(f"{label}: unknown key '{key}.{k}' (allowed: {', '.join(_KEYS[key])})")
        return value

    def text(value, key: str) -> str:
        if isinstance(value, str):
            return value
        errors.append(f"{label}: {key} must be a text, for example {key.split('.')[-1]} = \"...\"")
        return ""

    def texts(value, key: str) -> tuple[str, ...]:
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return tuple(value)
        errors.append(f"{label}: {key} must be a list of texts, "
                      f"for example {key.split('.')[-1]} = [\"...\", \"...\"]")
        return ()

    for k in data:
        if k not in _TOP:
            errors.append(f"{label}: unknown key '{k}' (allowed: {', '.join(_TOP)})")
    summary, plan, obs = table("summary"), table("plan"), table("observations")
    identity = text(summary.get("identity", ""), "summary.identity")
    weaknesses = texts(summary.get("weaknesses", []), "summary.weaknesses")
    threats = texts(summary.get("threats", []), "summary.threats")
    instructions = texts(plan.get("instructions", []), "plan.instructions")
    clips = texts(plan.get("clips", []), "plan.clips")
    observations = {k: text(v, f"observations.{k}") for k, v in obs.items() if k in NOTE_SECTIONS}
    players = []
    raw_players = data.get("key_players", [])
    if not isinstance(raw_players, list) or not all(isinstance(p, dict) for p in raw_players):
        errors.append(f"{label}: key_players must be a list of tables, "
                      "for example [[key_players]] with name and note")
        raw_players = []
    for i, p in enumerate(raw_players, 1):
        for k in p:
            if k not in ("name", "note"):
                errors.append(f"{label}: unknown key 'key_players[{i}].{k}' (allowed: name, note)")
        name = text(p.get("name", ""), f"key_players[{i}].name")
        if not name.strip():
            errors.append(f"{label}: key_players[{i}].name is required")
        if "note" not in p:
            errors.append(f"{label}: key_players[{i}].note is required, for example note = \"...\"")
        players.append((name, text(p.get("note", ""), f"key_players[{i}].note")))

    if not (identity.strip() or any(s.strip() for s in weaknesses + threats)):
        errors.append(f"{label}: the summary is required: add [summary] with identity, weaknesses and threats")
    if not any(s.strip() for s in instructions):
        errors.append(f'{label}: the match plan is required: add [plan] with instructions = ["...", "..."]')
    if errors:
        raise ValidationError(errors)
    return Notes(identity, weaknesses, threats, instructions, clips, observations, tuple(players))
