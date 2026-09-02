"""Cancel/reclaim/abandon recovery plus missing-ledger UNKNOWN (not SUCCESS).

Both suites drive the real ``codex_mcp_recovery`` runtime: threads are
started, cancelled and reclaimed/abandoned on a live ``RecoveryRuntime`` and
the ledger is a real file in a temporary directory that is written, read
back, and deleted. Nothing here is a canned verdict — every ``named_outcome``
below is read off the runtime after the operation ran.
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from codex_mcp_recovery import (  # noqa: E402
    ABANDONED,
    RECLAIMED,
    RUNNING,
    UNKNOWN,
    RecoveryRuntime,
    ThreadRecord,
    classify_missing_ledger,
)


def _record(rec: ThreadRecord) -> dict[str, Any]:
    d = asdict(rec)
    if d.get("named_outcome") is None:
        d["named_outcome"] = RUNNING.upper()
    d["state"] = str(d["state"]).upper()
    return d


def _two_state(label_a: str, a: str, label_b: str, b: str) -> dict[str, Any]:
    return {
        "verdict": "DIFFERS" if a != b else "SAME",
        label_a: a,
        label_b: b,
    }


def run_cancel_suite(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Cancel in the reclaim window -> RECLAIMED; cancel past it -> ABANDONED.

    An uncancelled thread keeps running and never acquires an ABANDONED
    record. The orphan mutant drops the owner on cancel without recording
    an outcome; ``RecoveryRuntime.orphans`` must see it while the honest
    reclaim leaves no orphan behind.
    """
    rt = RecoveryRuntime()
    rt.start("t-uncancelled")
    rt.start("t-reclaim")
    rt.start("t-abandon")

    uncancelled = _record(rt.threads["t-uncancelled"])
    reclaim = _record(rt.cancel_and_reclaim("t-reclaim"))
    abandon = _record(rt.cancel_and_abandon("t-abandon"))
    honest_orphans = [t.thread_id for t in rt.orphans()]

    # Orphan mutant: cancel that forgets the owner and records nothing.
    mutant = RecoveryRuntime()
    mutant.start("t-mutant")
    mut_rec = mutant.threads["t-mutant"]
    mut_rec.owner = None
    mutant_orphans = [t.thread_id for t in mutant.orphans()]
    mutant_outcome = "ORPHAN" if mutant_orphans else (mut_rec.named_outcome or RUNNING.upper())

    both = _two_state("uncancelled", uncancelled["named_outcome"], "window", abandon["named_outcome"])
    orphan = _two_state("mutant_outcome", mutant_outcome, "honest_outcome", reclaim["named_outcome"])
    passed = (
        uncancelled["abandoned_record"] is False
        and reclaim["named_outcome"] == RECLAIMED
        and abandon["named_outcome"] == ABANDONED
        and abandon["abandoned_record"] is True
        and not honest_orphans
        and mutant_orphans == ["t-mutant"]
        and both["verdict"] == "DIFFERS"
        and orphan["verdict"] == "DIFFERS"
        and "t-abandon" in rt.ledger.rows
    )
    return {
        "pass": passed,
        "both_states": both,
        "orphan_mutant": {**orphan, "mutant_orphans": mutant_orphans, "honest_orphans": honest_orphans},
        "uncancelled": uncancelled,
        "reclaim": reclaim,
        "abandon": abandon,
        "ledger_rows": sorted(rt.ledger.rows),
    }


def _write_ledger(path: Path, rt: RecoveryRuntime) -> None:
    doc = {
        "ledger": rt.ledger.path,
        "threads": {tid: _record(rec) for tid, rec in rt.threads.items()},
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_negative_suite(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """A present ledger classifies SUCCESS; deleting it must yield UNKNOWN.

    The mutant treats a missing ledger as SUCCESS; the two-state control
    must show the honest and mutant paths DIFFER on the same missing file.
    """
    with tempfile.TemporaryDirectory(prefix="tst0135-ledger-") as tmp:
        ledger_path = Path(tmp) / "codex-mcp-ledger.json"
        rt = RecoveryRuntime()
        rt.start("t-complete")
        rt.uncancelled_complete("t-complete")
        _write_ledger(ledger_path, rt)
        present_on_disk = ledger_path.is_file()
        present = classify_missing_ledger(ledger_present=present_on_disk, mutant_success=False)
        present["ledger"] = str(ledger_path)
        present["ledger_bytes"] = ledger_path.stat().st_size if present_on_disk else 0
        present["readback_threads"] = sorted(
            json.loads(ledger_path.read_text(encoding="utf-8")).get("threads", {})
        )

        ledger_path.unlink()
        missing_on_disk = ledger_path.is_file()
        honest = classify_missing_ledger(ledger_present=missing_on_disk, mutant_success=False)
        honest["ledger"] = None
        honest["ledger_path_checked"] = str(ledger_path)
        mutant = classify_missing_ledger(ledger_present=missing_on_disk, mutant_success=True)
        mutant["note"] = "mutant treats missing ledger as success"

    two_state = _two_state("honest", honest["named_outcome"], "mutant", mutant["named_outcome"])
    passed = (
        present_on_disk
        and present["state"] == "SUCCESS"
        and not missing_on_disk
        and honest["named_outcome"] == UNKNOWN
        and honest["state"] == UNKNOWN
        and honest["success"] is False
        and mutant["state"] == "SUCCESS"
        and two_state["verdict"] == "DIFFERS"
    )
    return {
        "pass": passed,
        "present_ledger": present,
        "honest_missing_ledger": honest,
        "mutant_missing_ledger": mutant,
        "two_state": two_state,
    }


def dump_fixture(path: Path, doc: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def test_cancel_suite() -> None:
    assert run_cancel_suite()["pass"] is True


def test_negative_suite() -> None:
    assert run_negative_suite()["pass"] is True
