#!/usr/bin/env python3
"""Named probe 2: both-states oracle control on resume.

Good state: a unit whose receipt still PASSES the oracle is NOT re-dispatched.
Bad state:  a unit whose receipt FAILS the oracle IS re-dispatched.
Same resume code path; only the live receipt differs.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.oracle import Oracle  # noqa: E402
from agentspec.resume import KillAtFraction, ResumableRunner, persist_json  # noqa: E402
from scenario import kill_after_units, workflow  # noqa: E402

FAIL_UNIT = "U02"


def kill_partial(root: Path) -> int:
    wf = workflow()
    stop = kill_after_units(len(wf.units))
    runner = ResumableRunner(root)
    try:
        runner.run(wf, run_id="partial", stop_after_units=stop)
    except KillAtFraction as exc:
        return exc.dispatched
    raise AssertionError("kill point was not reached")


def fail_receipt(root: Path, unit_id: str) -> str:
    """Flip a passing receipt to FAILED so the oracle must reject it."""
    path = root / "receipts" / f"{unit_id}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["state"] = "FAILED"
    doc["sentinel"] = f"FAILED:{unit_id}"
    persist_json(path, doc)
    verdict = Oracle().passes(path, root=root)
    if verdict.ok:
        raise AssertionError("oracle still passed after FAILED mutation")
    return verdict.reason


def resume(root: Path) -> dict:
    runner = ResumableRunner(root)
    return runner.run(workflow(), run_id="resume")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0145-probe2-"))
    try:
        good_dir = tmp / "good"
        bad_dir = tmp / "bad"
        kill_partial(good_dir)
        kill_partial(bad_dir)
        fail_reason = fail_receipt(bad_dir, FAIL_UNIT)
        good = resume(good_dir)
        bad = resume(bad_dir)
        good_reran = FAIL_UNIT in good["dispatch_log"]
        bad_reran = FAIL_UNIT in bad["dispatch_log"]
        payload = {
            "probe": "probe2-oracle-fail-both-states",
            "unit_id": "IMP-0145",
            "fail_unit": FAIL_UNIT,
            "oracle_fail_reason": fail_reason,
            "good_resume_dispatch_count": good["dispatch_count"],
            "bad_resume_dispatch_count": bad["dispatch_count"],
            "good_reran_fail_unit": good_reran,
            "bad_reran_fail_unit": bad_reran,
            "good_dispatch_log": good["dispatch_log"],
            "bad_dispatch_log": bad["dispatch_log"],
            "both_states_diverge": (not good_reran) and bad_reran,
            "pass": False,
        }
        errors: list[str] = []
        if good_reran:
            errors.append("good-state-reran-passing-receipt")
        if not bad_reran:
            errors.append("bad-state-did-not-rerun-failed-receipt")
        if bad["dispatch_count"] <= good["dispatch_count"]:
            errors.append("bad-state-dispatch-not-greater")
        # After resume, the previously-failed unit must now pass (re-run repaired it).
        repaired = Oracle().passes(bad_dir / "receipts" / f"{FAIL_UNIT}.json", root=bad_dir)
        if not repaired.ok:
            errors.append("failed-unit-not-repaired-on-rerun")
        still_good = Oracle().passes(
            good_dir / "receipts" / f"{FAIL_UNIT}.json", root=good_dir
        )
        if not still_good.ok:
            errors.append("good-state-receipt-lost")
        payload["errors"] = errors
        payload["pass"] = not errors
        print(json.dumps(payload, sort_keys=True))
        if errors:
            print("FAILED:IMP-0145-probe2", ",".join(errors))
            return 1
        print(
            f"both_states ok=True good_reran={good_reran} bad_reran={bad_reran} "
            f"good_n={good['dispatch_count']} bad_n={bad['dispatch_count']}"
        )
        print("SUCCESS:IMP-0145-probe2 oracle-fail both-states control")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
