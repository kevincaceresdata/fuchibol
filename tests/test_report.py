"""Smoke tests: 8 A4 pages, no PDF on invalid input, sample warning, CLI contract."""

import re
import shutil
from pathlib import Path

import pytest

from rivalkit.__main__ import main
from rivalkit.report import summary_lines
from rivalkit.schema import load_matches

EXAMPLE = Path("data/example")
NOTES = EXAMPLE / "notes.toml"
MINIMAL = '[summary]\nidentity = "x"\n[plan]\ninstructions = ["a"]\n'


def folders() -> list[str]:
    return [str(p) for p in sorted(EXAMPLE.iterdir()) if p.is_dir()]


def args(out, notes=str(NOTES), dirs=None) -> list[str]:
    return (dirs if dirs is not None else folders()) + ["--notes", str(notes), "-o", str(out)]


def page_count(path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))


def every_page_is_a4(path: Path) -> bool:
    boxes = re.findall(rb"/MediaBox\s*\[([^\]]+)\]", path.read_bytes())
    assert boxes, "no /MediaBox found"
    for box in boxes:
        nums = [float(n) for n in box.split()]
        assert abs(nums[2] - 595.28) < 1 and abs(nums[3] - 841.89) < 1, nums
    return True


def test_full_and_minimal_notes_produce_8_a4_pages(tmp_path, capsys):
    minimal = tmp_path / "notes.toml"
    minimal.write_text(MINIMAL, encoding="utf-8")
    for notes in (str(NOTES), minimal):
        out = tmp_path / f"report-{Path(notes).stem}.pdf"
        assert main(args(out, notes=notes)) == 0
        assert out.is_file()
        assert page_count(out) == 8
        assert every_page_is_a4(out)
    assert "wrote" in capsys.readouterr().out


def test_invalid_csv_keeps_existing_output_and_leaves_no_tmp(tmp_path, capsys):
    bad = tmp_path / "bad"
    shutil.copytree(EXAMPLE, bad)
    events = (bad / "m01" / "events.csv").read_text(encoding="utf-8").splitlines()
    first = events[3].split(",")  # physical row 4: header is row 1
    first[0] = "130"
    events[3] = ",".join(first)
    (bad / "m01" / "events.csv").write_text("\n".join(events) + "\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    out.write_bytes(b"OLD")
    assert main(args(out, dirs=[str(bad / m) for m in ("m01", "m02", "m03", "m04", "m05")])) == 1
    err = capsys.readouterr().err
    assert "events.csv:4: minute" in err
    assert "no PDF written" in err
    assert out.read_bytes() == b"OLD"
    assert not list(tmp_path.glob("*.pdf.tmp"))


def test_notes_without_plan_fails_without_pdf(tmp_path, capsys):
    notes = tmp_path / "notes.toml"
    notes.write_text('[summary]\nidentity = "x"\n', encoding="utf-8")
    out = tmp_path / "out.pdf"
    assert main(args(out, notes=notes)) == 1
    assert "the match plan is required" in capsys.readouterr().err
    assert not out.exists()


def test_usage_errors_exit_2(tmp_path):
    for argv in ([], folders(), folders() + ["--notes", str(NOTES)]):
        with pytest.raises(SystemExit) as exc:
            main(argv)
        assert exc.value.code == 2
    assert not list(tmp_path.glob("*.pdf"))


def _normalized(path: Path) -> bytes:
    b = path.read_bytes()
    b = re.sub(rb"/CreationDate \([^)]*\)", b"", b)
    b = re.sub(rb"/ID \[<[^>]+>\s*<[^>]+>\]", b"", b)
    return b


def test_argument_order_does_not_change_output(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    assert main(args(a)) == 0
    assert main(args(b, dirs=list(reversed(folders())))) == 0
    assert _normalized(a) == _normalized(b)


def test_summary_lines_sample_warning_and_singular():
    all_folders = sorted(p for p in EXAMPLE.iterdir() if p.is_dir())
    four = summary_lines(load_matches(all_folders[:4]))
    five = summary_lines(load_matches(all_folders))
    one = summary_lines(load_matches(all_folders[:1]))
    assert any("Muestra reducida" in ln for ln in four)
    assert not any("Muestra reducida" in ln for ln in five)
    assert any("1 partido analizado" in ln for ln in one)
    assert any("5 partidos analizados" in ln for ln in five)


def test_overflow_warning_goes_to_stderr_but_exit_stays_0(tmp_path, capsys):
    instructions = [f"Instrucción {i}: " + "texto " * 40 for i in range(40)]
    items = ", ".join(f'"{t}"' for t in instructions)
    notes = tmp_path / "notes.toml"
    notes.write_text(f'[summary]\nidentity = "x"\n[plan]\ninstructions = [{items}]\n',
                     encoding="utf-8")
    out = tmp_path / "out.pdf"
    assert main(args(out, notes=notes)) == 0
    assert 'aviso: el texto de "Plan de partido" excede la página; reduzca el texto' \
        in capsys.readouterr().err
