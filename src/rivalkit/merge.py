"""Merge reviewed tagger events into validated CSV, correction audits and XML.

`convert_events` is the single validation path shared by
`scripts/tagger_export.py`; `diff_corrections` audits what the human changed
against the autotag candidates; `export_sportscode_xml` writes the
Sportscode / Nacsport / Once Sport interchange file. Flat module: pure
functions, the only I/O is the explicit out paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

EVENT_TYPES = {"shot", "goal", "corner", "free_kick", "penalty", "recovery"}
TEAMS = {"rival", "opponent"}
DETAILS = {
    "goal": {"open_play", "set_piece", "penalty", "own_goal"},
    "shot": {"on_target", "off_target", "blocked"},
    "corner": {"direct", "crossed", "short"},
    "free_kick": {"direct", "crossed", "short"},
}
CSV_FIELDS = ["minute", "event_type", "team", "zone", "game_state", "player", "detail"]

DIFF_FIELDS = ("type", "team", "zone", "detail", "player")
INSTANCE_WINDOW_S = 15.0


def _is_rejected(row: object) -> bool:
    """A candidate the human rejected (tagger v3 `status` or legacy `verdict`)."""
    return (isinstance(row, dict)
            and (row.get("status") == "rejected" or row.get("verdict") == "rejected"))


def convert_events(rows: list[dict]) -> list[dict]:
    """Validate raw tagger rows and attach game_state, sorted by match time.

    Rejected candidates (status/verdict == "rejected") are dropped before
    validation, so a rejected row can never fail the export. Validation
    error messages are byte-identical to the original tagger_export script.
    """
    errors: list[str] = []
    clean: list[dict] = []
    for i, ev in enumerate(rows, 1):
        if _is_rejected(ev):
            continue
        label = f"evento {i}"
        try:
            minute = int(ev["minute"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}: minute invalido {ev.get('minute')!r}")
            continue
        if not 0 <= minute <= 120:
            errors.append(f"{label}: minute {minute} fuera de 0-120")
        event_type = str(ev.get("type", ""))
        if event_type not in EVENT_TYPES:
            errors.append(f"{label}: type {event_type!r} no es uno de {sorted(EVENT_TYPES)}")
        team = str(ev.get("team", ""))
        if team not in TEAMS:
            errors.append(f"{label}: team {team!r} no es rival/opponent")
        try:
            zone = int(ev["zone"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}: zone invalida {ev.get('zone')!r}")
            continue
        if not 1 <= zone <= 18:
            errors.append(f"{label}: zone {zone} fuera de 1-18")
        detail = str(ev.get("detail") or "")
        allowed = DETAILS.get(event_type, set())
        if detail and detail not in allowed:
            errors.append(f"{label}: detail {detail!r} no permitido para {event_type}")
        try:
            ts = float(ev.get("ts", 0))
        except (TypeError, ValueError):
            ts = 0.0
        if errors and errors[-1].startswith(label):
            continue
        clean.append({"minute": minute, "ts": ts, "type": event_type,
                      "team": team, "zone": zone, "detail": detail,
                      "player": str(ev.get("player") or "")})
    if errors:
        raise SystemExit("\n".join(errors))

    clean.sort(key=lambda e: (e["minute"], e["ts"]))
    rival_goals = opponent_goals = 0
    out = []
    for e in clean:
        state = ("winning" if rival_goals > opponent_goals
                 else "losing" if rival_goals < opponent_goals else "drawing")
        out.append({"minute": e["minute"], "event_type": e["type"], "team": e["team"],
                    "zone": e["zone"], "game_state": state, "player": e["player"],
                    "detail": e["detail"]})
        if e["type"] == "goal":
            # team is the credited side (own goals included), per the tagging guide
            if e["team"] == "rival":
                rival_goals += 1
            else:
                opponent_goals += 1
    return out


def _as_int(value: object) -> object:
    """Coerce to int for comparison; keep the raw value when not numeric."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return value


def _ts_of(row: dict) -> float | None:
    try:
        return float(row["ts"])
    except (KeyError, TypeError, ValueError):
        return None


def _view(row: dict | None) -> dict:
    """Comparable projection of one event for the corrections diff."""
    if row is None:
        return {f: None for f in DIFF_FIELDS}
    return {
        "type": str(row.get("type") or row.get("event_type") or ""),
        "team": str(row.get("team") or ""),
        "zone": _as_int(row.get("zone")),
        "detail": str(row.get("detail") or ""),
        "player": str(row.get("player") or ""),
    }


def _changes(before_row: dict | None, after_row: dict | None) -> dict:
    """Per-field {before, after} pairs; empty when nothing differs."""
    b, a = _view(before_row), _view(after_row)
    return {f: {"before": b[f], "after": a[f]} for f in DIFF_FIELDS if b[f] != a[f]}


def _nearest_index(before: list[dict], after: dict, used: set[int],
                   window: float) -> int | None:
    """Closest unused candidate within `window` on ts; same minute if ts is missing."""
    a_ts = _ts_of(after)
    best: int | None = None
    best_d: float | None = None
    for i, b in enumerate(before):
        if i in used:
            continue
        b_ts = _ts_of(b)
        if a_ts is None or b_ts is None:
            if _as_int(b.get("minute")) == _as_int(after.get("minute")):
                return i
            continue
        d = abs(b_ts - a_ts)
        if d <= window and (best_d is None or d < best_d):
            best, best_d = i, d
    return best


def diff_corrections(before: list[dict], after: list[dict],
                     match_window_s: float = 8.0) -> list[dict]:
    """Structured diff of human-reviewed `after` events vs autotag `before`.

    Each `after` event pairs with the nearest unused `before` candidate within
    `match_window_s` on ts (same `minute` when either side lacks ts). Rejected
    rows in `after` are ignored, so a rejected candidate surfaces as "removed".
    Entries are {"action", "ts", "minute", "changes"} with action in
    confirmed|modified|added|removed; removed candidates are appended after
    the reviewed timeline.
    """
    used: set[int] = set()
    out: list[dict] = []
    for a in after:
        if _is_rejected(a):
            continue
        idx = _nearest_index(before, a, used, match_window_s)
        if idx is None:
            out.append({"action": "added", "ts": a.get("ts"), "minute": a.get("minute"),
                        "changes": _changes(None, a)})
            continue
        used.add(idx)
        changes = _changes(before[idx], a)
        out.append({"action": "modified" if changes else "confirmed",
                    "ts": a.get("ts"), "minute": a.get("minute"), "changes": changes})
    for i, b in enumerate(before):
        if i not in used:
            out.append({"action": "removed", "ts": b.get("ts"), "minute": b.get("minute"),
                        "changes": _changes(b, None)})
    return out


def write_corrections_log(before: list[dict], after: list[dict], out_path: Path) -> int:
    """Write the corrections diff as JSONL; return the number of entries."""
    entries = diff_corrections(before, after)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(entries)


def export_sportscode_xml(rows: list[dict], out_path: Path) -> int:
    """Write Sportscode/Nacsport/Once Sport XML; return instances written.

    Accepts raw tagger rows (`type` + `ts`) or converted rows (`event_type`,
    no ts: instances land at `minute * 60` seconds). Each instance spans a
    fixed 15 s window from its timestamp; rejected rows are filtered out.
    """
    kept = [r for r in rows if not _is_rejected(r)]
    lines = ["<?xml version='1.0' encoding='utf-8'?>", "<file>", "  <ALL_INSTANCES>"]
    for i, r in enumerate(kept, 1):
        minute = _as_int(r.get("minute"))
        try:
            start = float(r["ts"])
        except (KeyError, TypeError, ValueError):
            start = float(minute) * 60.0
        end = start + INSTANCE_WINDOW_S
        event_type = str(r.get("type") or r.get("event_type") or "")
        team = str(r.get("team") or "")
        detail = str(r.get("detail") or "")
        zone = _as_int(r.get("zone"))
        player = escape(str(r.get("player") or ""))
        code = escape(f"{minute:02d} {event_type.upper()} {team.upper()}")
        tipo = escape(f"{event_type}/{detail}" if detail else event_type)
        lines += [
            "    <instance>",
            f"      <ID>{i}</ID>",
            f"      <start>{start:.2f}</start>",
            f"      <end>{end:.2f}</end>",
            f"      <code>{code}</code>",
            "      <label>",
            "        <group>Minuto</group>",
            f"        <text>{minute}'</text>",
            "      </label>",
            "      <label>",
            "        <group>Zona</group>",
            f"        <text>Zona {zone:02d}</text>",
            "      </label>",
            "      <label>",
            "        <group>Jugador</group>",
            f"        <text>{player}</text>",
            "      </label>",
            "      <label>",
            "        <group>Tipo</group>",
            f"        <text>{tipo}</text>",
            "      </label>",
            "    </instance>",
        ]
    lines += ["  </ALL_INSTANCES>", "</file>"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(kept)
