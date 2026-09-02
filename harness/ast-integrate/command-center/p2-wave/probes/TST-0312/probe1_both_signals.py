#!/usr/bin/env python3
"""Named probe 1: revert a real change; both signals agree baseline is restored.

Field: post-revert benchmark delta vs the measured null-delta floor, AND
git-diff/tree identity vs the pre-change SHA. Also the conjunction gate's
four-cell table (OR is not restore). Distinct from probe 2 (residue paths
and revert-of-revert byte identity).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revert_restore import (  # noqa: E402
    RESTORED,
    SINGLE_SIGNAL_REJECTED,
    scenario_restore_real_change,
    scenario_single_signal_gate,
)

ART = REPO / "command-center/receipts/TST-0312.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0312-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0312":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0312" not in text:
        return fail("sentinel absent")

    with tempfile.TemporaryDirectory(prefix="tst0312-p1-") as tmp:
        restore = scenario_restore_real_change(Path(tmp))
        gate = scenario_single_signal_gate()

    if not restore["pass"] or not restore["both_signals_agree_restored"]:
        print(json.dumps(restore, indent=2, default=str)[:4000])
        return fail("live restore did not get both signals RESTORED")
    after = restore["after_revert"]
    if not after["benchmark"]["ok"] or not after["path"]["ok"]:
        return fail("one signal missing on live restore")
    if after["verdict"] != RESTORED:
        return fail(f"verdict {after['verdict']}")
    if restore["during_change"]["verdict"] == RESTORED:
        return fail("pre-revert change was invisible")
    if abs(float(after["benchmark"]["delta"])) > float(after["benchmark"]["floor"]):
        return fail("post-revert delta outside variance floor")
    if after["path"]["git_diff_paths"] or after["path"]["residue"]:
        return fail("path signal not clean after restore")
    if not gate["pass"]:
        return fail("conjunction gate truth table failed")
    or_row = next(
        r for r in gate["rows"] if r["bench_ok"] is True and r["path_ok"] is False
    )
    if or_row["got"] != SINGLE_SIGNAL_REJECTED:
        return fail("OR of signals was accepted as restore")

    rec = doc.get("restore_real_change") or {}
    if rec.get("both_signals_agree_restored") is not True:
        return fail("receipt restore flag drift")
    rec_after = rec.get("after_revert") or {}
    if rec_after.get("verdict") != RESTORED:
        return fail("receipt after_revert verdict drift")
    rec_gate = doc.get("single_signal_gate") or {}
    if rec_gate.get("pass") is not True:
        return fail("receipt gate flag drift")

    out = {
        "probe": "probe1-both-signals",
        "unit_id": "TST-0312",
        "baseline_sha": restore["baseline_sha"],
        "changed_sha": restore["changed_sha"],
        "during_verdict": restore["during_change"]["verdict"],
        "after_verdict": after["verdict"],
        "benchmark_delta": after["benchmark"]["delta"],
        "variance_floor": after["benchmark"]["floor"],
        "path_git_diff": after["path"]["git_diff_paths"],
        "path_residue": after["path"]["residue"],
        "gate_pass": gate["pass"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"during={out['during_verdict']} after={out['after_verdict']} "
        f"delta={out['benchmark_delta']} floor={out['variance_floor']} "
        f"git_diff={out['path_git_diff']} residue={out['path_residue']}"
    )
    print("SUCCESS:TST-0312-probe1 both signals agree baseline restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
