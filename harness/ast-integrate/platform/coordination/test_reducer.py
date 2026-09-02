"""The shared reducer is delegated, and the duplicate-plane detector is proven in BOTH states."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import completion_predicate
import pytest

from coordination.claims import ClaimState, acquire_claim, complete_claim
from coordination.errors import DuplicateControlPlane, StoreCorrupt
from coordination.reducer import (
    BANNED_DEFINITIONS,
    DELEGATE_MODULE,
    REDUCER_ID,
    PredicateOptions,
    Verdict,
    assert_single_reducer,
    evaluate,
    reduce_claim,
    scan_for_duplicate_planes,
)
from coordination.session import register_session
from coordination.store import Store

PACKAGE = Path(__file__).resolve().parent

UNIT: dict[str, Any] = {
    "id": "COORD-0300",
    "phase": "9",
    "question_or_target": "reduce a receipt",
    "inputs": ["i"],
    "dependencies": [],
    "output_path": "o.json",
    "output_schema": "s.json",
    "evidence_requirement": "two probes",
    "tests_required": ["t"],
    "reviewer_requirement": "cross-vendor",
    "completion_sentinel": "SUCCESS:COORD-0300",
}


# ------------------------------------------------------------------- the delegation itself


def test_the_reducer_is_the_delegate_by_object_identity() -> None:
    """Not merely 'looks the same': the SAME function object, from the delegate's module."""
    assert evaluate is completion_predicate.evaluate
    assert evaluate.__module__ == DELEGATE_MODULE
    assert REDUCER_ID == completion_predicate.REDUCER_ID
    assert REDUCER_ID == "platform/lib/completion_predicate.py@v1"


def test_the_reexported_types_are_the_delegates_types() -> None:
    assert PredicateOptions is completion_predicate.PredicateOptions
    assert Verdict is completion_predicate.Verdict


# ------------------------------------------------- the duplicate-plane gate, both directions


def test_this_package_has_exactly_one_reducer_known_good_state() -> None:
    report = scan_for_duplicate_planes(PACKAGE)
    assert report.ok is True, report.to_dict()
    assert report.modules_scanned > 0, "a scan of zero modules must never read as clean"
    assert report.violations == ()
    assert report.sentinel_line.startswith("SUCCESS:single-reducer")
    assert assert_single_reducer(PACKAGE) is not None


def test_detector_fires_on_a_synthetic_second_plane_known_broken_state(
    tmp_path: Path,
) -> None:
    """BOTH-STATES control. A detector only ever run against the clean state measures nothing.

    The synthetic module is what a future 'convenient local helper' would look like: a module-level
    ``evaluate`` plus a re-transcription of the condition table.
    """
    (tmp_path / "sneaky.py").write_text(
        "CONDITIONS = ((1, 'a', 1),)\n"
        "NON_WAIVABLE = frozenset({1})\n"
        "def evaluate(receipt, opts):\n"
        "    return 'COMPLETE'\n",
        encoding="utf-8",
    )
    report = scan_for_duplicate_planes(tmp_path)
    assert report.ok is False
    symbols = {v["symbol"] for v in report.violations}
    assert {"evaluate", "CONDITIONS", "NON_WAIVABLE"} <= symbols
    assert report.sentinel_line.startswith("FAILED:single-reducer")
    with pytest.raises(DuplicateControlPlane, match="single-reducer"):
        assert_single_reducer(tmp_path)


def test_detector_fires_on_a_re_transcribed_condition_table(tmp_path: Path) -> None:
    """A second plane can be written without using any banned SYMBOL name.

    So the second, independent signal is the condition TEXTS themselves: three or more verbatim
    means somebody re-transcribed the table.
    """
    texts = list(completion_predicate.CONDITION_TEXT.values())[:4]
    body = "CHECKS = [\n" + "".join(f"    {t!r},\n" for t in texts) + "]\n"
    (tmp_path / "retranscribed.py").write_text(body, encoding="utf-8")
    report = scan_for_duplicate_planes(tmp_path)
    assert report.ok is False
    assert any(v["symbol"] == "<condition-texts>" for v in report.violations)


def test_detector_does_not_fire_on_a_mere_import_alias(tmp_path: Path) -> None:
    """The negative control for the detector: importing the delegate is the CORRECT pattern.

    Without this, a detector that flagged every re-export would be unusable and would be turned
    off - which is how a gate stops protecting anything.
    """
    (tmp_path / "good.py").write_text(
        "import completion_predicate as delegate\n"
        "from completion_predicate import evaluate\n"
        "CONDITIONS = delegate.CONDITIONS\n",
        encoding="utf-8",
    )
    report = scan_for_duplicate_planes(tmp_path)
    assert report.violations == (), report.to_dict()
    assert report.ok is True


def test_scan_of_an_empty_directory_is_not_ok() -> None:
    """Asserts the POSITIVE. 'Nothing found' must not read as 'nothing wrong'.

    This is the measured 0/0-conditions-read-as-PASS defect class, guarded directly.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        report = scan_for_duplicate_planes(td)
        assert report.modules_scanned == 0
        assert report.violations == ()
        assert report.ok is False
        assert report.sentinel_line.startswith("FAILED:single-reducer")


def test_banned_definitions_are_all_real_attributes_of_the_delegate() -> None:
    """A banned name the delegate does not define would be a dead rule."""
    for name in BANNED_DEFINITIONS:
        assert hasattr(completion_predicate, name), name


# ----------------------------------------------------------------------- reducing a claim


def _receipt(tmp_path: Path, artifact: Path) -> Path:
    body = json.dumps(
        {
            "schema_version": 1,
            "unit_id": "COORD-0300",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:COORD-0300 done",
            "artifacts": [{"path": str(artifact), "role": "primary", "exists": True}],
            "evidence": [],
        }
    )
    path = tmp_path / "receipt.json"
    path.write_text(body, encoding="utf-8")
    return path


def test_reduce_claim_delegates_and_returns_a_predicate_result(
    store: Store, tmp_path: Path
) -> None:
    artifact = tmp_path / "out.json"
    artifact.write_text(json.dumps({"payload": "x" * 200}), encoding="utf-8")
    receipt = _receipt(tmp_path, artifact)
    register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s1",
        hold_lock=False,
    )
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s1")
    complete_claim(store, UNIT["id"], receipt_path=receipt)
    result = reduce_claim(store, UNIT["id"], PredicateOptions(repo_root=tmp_path))
    assert result.reducer_id == REDUCER_ID
    assert isinstance(result.verdict, Verdict)
    assert result.unit_id == "COORD-0300"


def test_not_checked_stays_not_checked_and_blocks(store: Store, tmp_path: Path) -> None:
    """The delegate's NOT-CHECKED must pass through unchanged: never folded into a pass."""
    artifact = tmp_path / "out.json"
    artifact.write_text(json.dumps({"payload": "x" * 200}), encoding="utf-8")
    receipt = _receipt(tmp_path, artifact)
    register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s1",
        hold_lock=False,
    )
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s1")
    complete_claim(store, UNIT["id"], receipt_path=receipt)
    result = reduce_claim(store, UNIT["id"], PredicateOptions(repo_root=tmp_path))
    assert result.not_checked, (
        "a receipt with no schema/tests must leave conditions NOT-CHECKED"
    )
    assert result.verdict is not Verdict.COMPLETE
    assert result.sentinel_line.startswith("FAILED:")


def test_reduce_claim_without_a_receipt_raises_rather_than_returning_incomplete(
    store: Store,
) -> None:
    """An unmeasured unit is not a failing unit. Conflating them would hide the difference."""
    register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s1",
        hold_lock=False,
    )
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s1")
    with pytest.raises(
        StoreCorrupt, match="not an incomplete pass, it is an unmeasured unit"
    ):
        reduce_claim(store, UNIT["id"], PredicateOptions(repo_root=Path.cwd()))


def test_reduce_claim_on_a_missing_claim_raises(store: Store, tmp_path: Path) -> None:
    with pytest.raises(StoreCorrupt, match="no claim for unit"):
        reduce_claim(store, "NOPE", PredicateOptions(repo_root=tmp_path))


def test_require_completed_state_rejects_an_active_claim(
    store: Store, tmp_path: Path
) -> None:
    register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s1",
        hold_lock=False,
    )
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s1")
    with pytest.raises(StoreCorrupt, match="never claimed to be finished"):
        reduce_claim(
            store,
            UNIT["id"],
            PredicateOptions(repo_root=tmp_path),
            require_completed_state=True,
        )
    assert ClaimState.ACTIVE.value == "ACTIVE"


# ------------------------------------------------------- the gate is executable AND can go red


def test_the_gate_is_executable_and_green_on_this_package() -> None:
    import subprocess

    proc = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(PACKAGE / "single_reducer_gate.py"), str(PACKAGE)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SUCCESS:single-reducer" in proc.stdout


def test_the_gate_exits_non_zero_on_a_known_bad_tree(tmp_path: Path) -> None:
    """ci-hygiene section 1: a gate that has never gone red is indistinguishable from a no-op."""
    import subprocess

    (tmp_path / "second_plane.py").write_text(
        "CONDITIONS = ()\ndef evaluate(r, o):\n    return True\n", encoding="utf-8"
    )
    proc = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(PACKAGE / "single_reducer_gate.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stdout
    assert "FAILED:single-reducer" in proc.stdout
    assert "second_plane.py" in proc.stdout


def test_the_gate_fails_closed_on_an_empty_walk(tmp_path: Path) -> None:
    """'nothing found' must never read as 'nothing wrong'."""
    import subprocess

    empty = tmp_path / "empty"
    empty.mkdir()
    proc = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(PACKAGE / "single_reducer_gate.py"), str(empty)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stdout
    assert "FAILED:single-reducer" in proc.stdout


def test_the_gate_rejects_a_non_directory(tmp_path: Path) -> None:
    import subprocess

    target = tmp_path / "a-file.txt"
    target.write_text("x", encoding="utf-8")
    proc = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, str(PACKAGE / "single_reducer_gate.py"), str(target)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "is not a directory" in proc.stdout
