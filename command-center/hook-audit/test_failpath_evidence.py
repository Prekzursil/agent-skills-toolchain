"""Regressions for the fail-path evidence-destruction defect (verifier item V3 + 2 siblings).

Written RED-FIRST: the three `test_no_probe_*` cases below fail against the pre-fix probes,
which is the only reason a later green means anything.

Deliberately pytest functions, not a standalone `main()` script. The verifier recorded that
three regression files in this directory collect ZERO pytest tests, so a new file written in
that shape would have added a fourth uncollectable suite to a lane whose own CI wiring was
already corrected once for exactly this (`python`, not `pytest`, for test_citation_gate.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _b13_failpath_writes as scanner  # noqa: E402
import _evidence_io  # noqa: E402

OFFENDING_PROBES = (
    "_r4_githygiene_range.py",
    "_r4_budget_ceiling.py",
    "_r4_wire_exit.py",
)

# The exact V3 construction: write a tracked evidence file, then bail out non-zero.
BROKEN_SHAPE = """
from pathlib import Path
def main() -> int:
    out = {}
    if not discriminates:
        out["verdict"] = "INCONCLUSIVE"
        Path("R4-GITHYGIENE-RANGE.json").write_text("{}")
        print("FAILED:x")
        return 1
    Path("R4-GITHYGIENE-RANGE.json").write_text("{}")
    return 0
"""

FIXED_SHAPE = """
from pathlib import Path
def main() -> int:
    out = {}
    if not discriminates:
        out["verdict"] = "INCONCLUSIVE"
        write_evidence(Path("R4-GITHYGIENE-RANGE.json"), out, ok=False)
        print("FAILED:x")
        return 1
    write_evidence(Path("R4-GITHYGIENE-RANGE.json"), out, ok=True)
    return 0
"""


# --- the helper's contract ------------------------------------------------------


def test_ok_run_replaces_the_committed_file(tmp_path: Path) -> None:
    target = tmp_path / "E.json"
    target.write_text('{"old": 1}', encoding="utf-8")
    written = _evidence_io.write_evidence(target, {"new": 2}, ok=True)
    assert written == target
    assert json.loads(target.read_text(encoding="utf-8")) == {"new": 2}


def test_failed_run_does_not_touch_the_committed_file(tmp_path: Path) -> None:
    target = tmp_path / "E.json"
    target.write_text('{"old": 1}', encoding="utf-8")
    before = target.read_bytes()
    written = _evidence_io.write_evidence(target, {"verdict": "INCONCLUSIVE"}, ok=False)
    assert written != target
    assert target.read_bytes() == before, (
        "a failed run must not replace committed evidence"
    )
    assert json.loads(written.read_text(encoding="utf-8"))["verdict"] == "INCONCLUSIVE"


def test_failed_run_writes_a_named_sibling(tmp_path: Path) -> None:
    target = tmp_path / "R4-GITHYGIENE-RANGE.json"
    written = _evidence_io.write_evidence(target, {}, ok=False)
    assert written.name == "R4-GITHYGIENE-RANGE.INCONCLUSIVE.json"
    assert not target.exists(), (
        "the failed run must not create the committed name either"
    )


def test_failed_run_creates_nothing_at_the_committed_path_when_absent(
    tmp_path: Path,
) -> None:
    # A probe run in a fresh clone must not manufacture an evidence file out of a failure.
    target = tmp_path / "E.json"
    _evidence_io.write_evidence(target, {"verdict": "INCONCLUSIVE"}, ok=False)
    assert not target.exists()


# --- the scanner discriminates (both states) ------------------------------------


def test_scanner_flags_the_broken_shape() -> None:
    tracked = {"R4-GITHYGIENE-RANGE.json"}
    assert scanner.scan_source(BROKEN_SHAPE, tracked), (
        "scanner must fire on the known-broken shape"
    )


def test_scanner_is_silent_on_the_fixed_shape() -> None:
    tracked = {"R4-GITHYGIENE-RANGE.json"}
    assert not scanner.scan_source(FIXED_SHAPE, tracked), (
        "scanner must not fire on the fix"
    )


def test_scanner_ignores_untracked_targets() -> None:
    # Destroying scratch is not destroying evidence; the claim is about committed files.
    assert not scanner.scan_source(BROKEN_SHAPE, {"SOMETHING-ELSE.json"})


# --- the real probes ------------------------------------------------------------


def _offenders(name: str) -> list[dict]:
    tracked = scanner.tracked_json_names()
    assert len(tracked) >= scanner.MIN_TRACKED_JSON, (
        "tracked-file resolution went blind"
    )
    return scanner.scan_source((HERE / name).read_text(encoding="utf-8"), tracked)


def test_no_probe_githygiene_range_writes_evidence_on_a_fail_path() -> None:
    assert _offenders("_r4_githygiene_range.py") == []


def test_no_probe_budget_ceiling_writes_evidence_on_a_fail_path() -> None:
    assert _offenders("_r4_budget_ceiling.py") == []


def test_no_probe_wire_exit_writes_evidence_on_a_fail_path() -> None:
    assert _offenders("_r4_wire_exit.py") == []


def test_the_whole_directory_is_clean() -> None:
    tracked = scanner.tracked_json_names()
    offenders = {
        p.name: f
        for p in sorted(HERE.glob("*.py"))
        for f in [scanner.scan_source(p.read_text(encoding="utf-8"), tracked)]
        if f
    }
    assert offenders == {}, (
        f"probes still destroying committed evidence: {sorted(offenders)}"
    )
