"""Convert the tagger's events_raw.json into events.csv with computed game_state.

Thin CLI facade over `rivalkit.merge`: validation and conversion live in the
module, this script only parses arguments and writes outputs. The default
positional usage is byte-identical to the original script:

    .venv\\Scripts\\python scripts\\tagger_export.py events_raw.json > events.csv

Optional outputs (stdout stays clean whenever one of them is used):

    .venv\\Scripts\\python scripts\\tagger_export.py events_raw.json -o events.csv
    .venv\\Scripts\\python scripts\\tagger_export.py events_raw.json --xml eventos.xml
    .venv\\Scripts\\python scripts\\tagger_export.py events_raw.json --corrections autotag.json corrections.jsonl

Writes the CSV to stdout in the default mode; validation problems go to
stderr with exit 1, exactly as before.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from rivalkit.merge import (
    CSV_FIELDS,
    DETAILS,
    EVENT_TYPES,
    TEAMS,
    convert_events,
    export_sportscode_xml,
    write_corrections_log,
)

# Backward-compatible aliases: existing callers import the contract from here.
convert = convert_events


def _load_events(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return data["events"]


def _write_csv(fh, rows: list[dict]) -> None:
    writer = csv.DictWriter(fh, CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def main(argv: list[str]) -> int:
    # argv[0] is the script name (as in sys.argv) unless it already looks
    # like a flag, so both main(sys.argv) and main(["--xml", ...]) work.
    tokens = argv[1:] if argv and not str(argv[0]).startswith("-") else list(argv)
    parser = argparse.ArgumentParser(
        prog="tagger_export.py",
        description="Convert reviewed events_raw.json into events.csv, "
                    "Nacsport/Sportscode XML and a corrections audit log.")
    parser.add_argument("events_json",
                        help="reviewed events_raw.json ({\"events\": [...]})")
    parser.add_argument("-o", "--out", type=Path, default=None, metavar="FILE.csv",
                        help="write the CSV to FILE.csv instead of stdout")
    parser.add_argument("--xml", type=Path, default=None, metavar="FILE.xml",
                        help="write a Sportscode/Nacsport/Once Sport XML file")
    parser.add_argument("--corrections", nargs=2, type=Path, default=None,
                        metavar=("BEFORE.json", "LOG.jsonl"),
                        help="write a JSONL log of human changes vs the BEFORE.json autotag")
    args = parser.parse_args(tokens)

    raw = _load_events(args.events_json)
    rows = convert_events(raw)

    if args.out is not None:
        with args.out.open("w", encoding="utf-8", newline="") as fh:
            _write_csv(fh, rows)
    elif args.xml is None and args.corrections is None:
        _write_csv(sys.stdout, rows)

    if args.xml is not None:
        n = export_sportscode_xml(raw, args.xml)
        print(f"{n} instances -> {args.xml}", file=sys.stderr)
    if args.corrections is not None:
        before_path, log_path = args.corrections
        n = write_corrections_log(_load_events(before_path), raw, log_path)
        print(f"{n} corrections -> {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
