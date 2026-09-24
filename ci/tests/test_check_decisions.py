"""Tests for ci/check_decisions.py, the decision-record expiry gate (runbook Phase 4a).

Hermetic: each case builds its own docs/decisions/ under tmp_path and passes --root and
--today, so no verdict depends on the committed records or on the calendar. Run by
.github/workflows/decisions.yml by name and by skill-dual-write.yml's ci/tests sweep.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / "check_decisions.py"
sys.path.insert(0, str(GATE.parent))
import check_decisions as gate  # noqa: E402

NAME = "2026-09-24-example.md"
VALID = """\
title: Example decision
date: 2026-09-24
status: accepted
review_by: 2026-10-24
evidence:
  - docs/AUDIT-2026-09-24-sota-transcript-and-lanes.md#8-root-cause
"""
Run = Callable[..., tuple[int, list[str]]]


def rec(frontmatter: str) -> str:
    return f"---\n{frontmatter}---\n\n# Example\n\n## Decision\n\nText.\n"


def write(
    root: Path, text: str, name: str = NAME, eol: str = "\n", enc: str = "utf-8"
) -> None:
    """Write one file; enc="utf-8-sig" prepends a BOM, as some Windows editors do."""
    folder = root / "docs" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(text.replace("\n", eol).encode(enc))


@pytest.fixture
def run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    def _run(today: str = "2026-10-01") -> tuple[int, list[str]]:
        code = gate.main(["--root", str(tmp_path), "--today", today])
        return code, capsys.readouterr().out.splitlines()

    return _run


@pytest.mark.parametrize(("eol", "enc"), [("\n", "utf-8"), ("\r\n", "utf-8-sig")])
def test_valid_record_passes_with_one_summary_line(
    tmp_path: Path, run: Run, eol: str, enc: str
) -> None:
    write(tmp_path, rec(VALID), eol=eol, enc=enc)
    write(tmp_path, "# Decision records\n", "README.md")  # skipped: no frontmatter
    write(tmp_path, rec("title: <one line>\ndate: YYYY-MM-DD\n"), "TEMPLATE.md")
    assert run() == (
        0,
        [
            "decisions OK: 1 record(s) as of 2026-10-01 "
            "(0 proposed, 1 accepted, 0 superseded, 0 retired)"
        ],
    )


@pytest.mark.parametrize("today", ["2026-10-25", "2027-06-01"])
@pytest.mark.parametrize("retest", ["", "retested: 2026-10-23 re-ran a day early\n"])
def test_expired_accepted_record_without_a_retest_fails(
    tmp_path: Path, run: Run, today: str, retest: str
) -> None:
    write(tmp_path, rec(VALID + retest))
    code, out = run(today)
    assert code == 1
    assert len(out) == 1
    assert out[0].startswith(
        f"docs/decisions/{NAME}: accepted and past review_by 2026-10-24"
    )


def test_review_by_day_itself_and_unaccepted_statuses_do_not_expire(
    tmp_path: Path, run: Run
) -> None:
    write(tmp_path, rec(VALID))
    assert run("2026-10-24")[0] == 0
    for status in ("proposed", "superseded", "retired"):
        write(tmp_path, rec(VALID.replace("accepted", status)))
        assert run("2027-06-01")[0] == 0, status


@pytest.mark.parametrize(
    "retested",
    [
        "2026-10-24 still in force",
        "2026-10-30 re-measured",
        '"2026-10-30 holds: 0 new lanes"',
    ],
)
def test_expired_record_with_a_retest_on_or_after_review_by_passes(
    tmp_path: Path, run: Run, retested: str
) -> None:
    write(tmp_path, rec(VALID + f"retested: {retested}\n"))
    code, out = run("2026-11-01")
    assert code == 0, out
    assert out[0].startswith("decisions OK: 1 record(s) as of 2026-11-01")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# Example\n", "frontmatter missing"),
        ("---\n" + VALID + "# no closing line\n", "no closing '---' line"),
        (rec(VALID.replace("status: accepted\n", "")), "missing required key 'status'"),
        (
            rec(VALID.replace("2026-10-24", "24/10/2026")),
            "review_by must be 'YYYY-MM-DD'",
        ),
        (rec(VALID.replace("accepted", "done")), "status 'done' is not one of"),
        (
            rec(VALID + "supercedes: docs/decisions/old.md\n"),
            "unknown key 'supercedes'",
        ),
        (rec(VALID + "status: proposed\n"), "duplicate key 'status'"),
        (rec(VALID.replace("Example decision", "Freeze: 30 days")), "quote values"),
        (rec("  - stray item\n" + VALID), "a '- item' under a list key"),
        (rec(VALID.replace("evidence:\n  - ", "evidence: ")), "evidence must be a"),
        (
            rec(VALID + "retested: 2026-09-30\n"),
            "retested must be 'YYYY-MM-DD <result>'",
        ),
        (rec(VALID + "retested: 2026-12-01 from the future\n"), "dated after today"),
    ],
)
def test_malformed_frontmatter_fails(
    tmp_path: Path, run: Run, text: str, expected: str
) -> None:
    write(tmp_path, text)
    code, out = run()
    assert code == 1
    assert out and all(line.startswith(f"docs/decisions/{NAME}: ") for line in out)
    assert any(expected in line for line in out), out


def test_supersedes_must_name_an_existing_file(tmp_path: Path, run: Run) -> None:
    old = "docs/decisions/2026-09-01-old.md"
    write(tmp_path, rec(VALID + f"supersedes: {old}\n"))
    assert run() == (
        1,
        [f"docs/decisions/{NAME}: supersedes '{old}': no such repo-relative file"],
    )
    write(tmp_path, rec(VALID.replace("accepted", "superseded")), Path(old).name)
    assert run()[0] == 0


def test_supersedes_rejects_paths_outside_repo(tmp_path: Path, run: Run) -> None:
    # A supersedes value that escapes the repo root must be rejected even if the target
    # exists on disk, so a replacement decision cannot satisfy the gate by naming a file
    # outside the repository (path traversal).
    escape = "../../../../../../etc/passwd"
    write(tmp_path, rec(VALID + f"supersedes: {escape}\n"))
    assert run() == (
        1,
        [
            f"docs/decisions/{NAME}: supersedes '{escape}': "
            "must be a repo-relative path inside the repository"
        ],
    )


def test_supersedes_must_name_a_decision_record(tmp_path: Path, run: Run) -> None:
    # A real in-repo file that is not a decision record (e.g. the root README) must be
    # rejected, so a replacement cannot claim a transition without naming a predecessor
    # record under docs/decisions/.
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    write(tmp_path, rec(VALID + "supersedes: README.md\n"))
    assert run() == (
        1,
        [
            f"docs/decisions/{NAME}: supersedes 'README.md': "
            "must name a decision record under docs/decisions/ (a non-template .md file)"
        ],
    )


def test_cli_exit_codes(tmp_path: Path) -> None:
    def cli(today: str) -> subprocess.CompletedProcess[str]:
        argv = [sys.executable, str(GATE), "--root", str(tmp_path), "--today", today]
        return subprocess.run(argv, capture_output=True, text=True, check=False)

    # No docs/decisions/ at all: there is nothing it could check, so it must not pass.
    assert cli("2026-10-01").returncode == 2
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    empty = cli("2026-10-01")
    assert (empty.returncode, empty.stdout) == (
        1,
        "docs/decisions: no decision records\n",
    )
    write(tmp_path, rec(VALID))
    assert cli("2026-10-24").returncode == 0
    assert cli("2026-10-25").returncode == 1
    assert cli("24/10/2026").returncode == 2  # argparse rejects a non-ISO date
