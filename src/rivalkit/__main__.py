"""CLI: python -m rivalkit MATCH_DIR [MATCH_DIR ...] --notes NOTES.toml -o OUTPUT.pdf"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from .report import write_report
from .schema import ValidationError, load_matches, load_notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rivalkit",
        description="Build an 8-page A4 rival report PDF from hand-tagged match CSVs.")
    parser.add_argument("match_dirs", nargs="+", metavar="MATCH_DIR")
    parser.add_argument("--notes", required=True, metavar="NOTES.toml")
    parser.add_argument("-o", "--output", required=True, metavar="OUTPUT.pdf")
    args = parser.parse_args(argv)

    folders: list[Path] = []
    for arg in args.match_dirs:
        matches = sorted(glob.glob(arg))
        folders.extend(Path(m) for m in (matches or [arg]))

    data = notes = None
    errors: list[str] = []
    try:
        data = load_matches(folders)
    except ValidationError as exc:
        errors += exc.errors
    try:
        notes = load_notes(Path(args.notes))
    except ValidationError as exc:
        errors += exc.errors
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"{len(errors)} error(s); no PDF written", file=sys.stderr)
        return 1

    try:
        pages = write_report(data, notes, Path(args.output))
    except OSError as exc:
        reason = exc.strerror or str(exc)
        print(f"error: cannot write {args.output}: {reason} "
              "(close it if it is open in a PDF viewer)", file=sys.stderr)
        return 1
    n = len(data.matches)
    print(f"wrote {args.output} ({pages} pages, {n} matches)")
    if n < 5:
        print(f"warning: only {n} match(es) analysed; at least 5 are recommended",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
