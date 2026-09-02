#!/usr/bin/env python3
"""Named probe 1: open P1 blocks SUCCESS; resolved P1 does not.

Signal is a real CLI subprocess transcript (exit code + named defect id),
not a function return. The candidate satisfies the other 11 conditions so
the failing-condition-id is 10 in isolation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import completion_c10 as c10  # noqa: E402

CLI = REPO / "tools/command-center/completion_c10.py"
DEFECT_ID = "TST0010-D-OPEN-P1"


def run_evaluate(receipt: Path, audit: Path) -> tuple[int, dict, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CLI),
            "evaluate",
            "--receipt",
            str(receipt),
            "--audit",
            str(audit),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    lines = text.splitlines()
    trans_i = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("FAILED:condition-10") or line.startswith("PASS:condition-10")
        ),
        None,
    )
    if trans_i is None:
        raise RuntimeError(f"no condition-10 transcript in:\n{text[-1500:]}")
    body = "\n".join(lines[:trans_i])
    result = json.loads(body)
    return proc.returncode, result, lines[trans_i]


def materialize(root: Path, *, closed: bool) -> tuple[Path, Path]:
    receipt = c10.isolation_candidate()
    audit_path = root / ("closed-audit.jsonl" if closed else "open-audit.jsonl")
    c10.open_defect(
        receipt,
        defect_id=DEFECT_ID,
        severity="P1",
        summary="planted open P1; other 11 conditions hold",
        audit_path=audit_path,
        actor="TST-0010-probe1",
        ts="2026-08-24T18:20:00Z",
    )
    if closed:
        c10.resolve_defect(
            receipt,
            defect_id=DEFECT_ID,
            reason="defect closed; must not block SUCCESS",
            actor="TST-0010-probe1",
            audit_path=audit_path,
            status="closed",
            ts="2026-08-24T18:21:00Z",
        )
    receipt_path = root / ("candidate_closed_p1.json" if closed else "candidate_open_p1.json")
    c10.save_json(receipt_path, receipt)
    return receipt_path, audit_path


def main() -> int:
    if not CLI.is_file():
        print("FAILED:TST-0010-probe1 completion_c10.py missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="tst0010-p1-") as td:
        tmp = Path(td)
        open_receipt, open_audit = materialize(tmp / "open", closed=False)
        closed_receipt, closed_audit = materialize(tmp / "closed", closed=True)

        open_rc, open_doc, open_tr = run_evaluate(open_receipt, open_audit)
        closed_rc, closed_doc, closed_tr = run_evaluate(closed_receipt, closed_audit)

        payload = {
            "probe": "probe1-open-p1-blocks",
            "unit_id": "TST-0010",
            "defect_id": DEFECT_ID,
            "open_exit": open_rc,
            "open_failing_condition_id": open_doc.get("failing_condition_id"),
            "open_named": open_doc.get("named_defect_ids"),
            "open_other_11": open_doc.get("other_11_satisfied"),
            "open_transcript": open_tr,
            "closed_exit": closed_rc,
            "closed_failing_condition_id": closed_doc.get("failing_condition_id"),
            "closed_can_reach_success": closed_doc.get("can_reach_success"),
            "closed_transcript": closed_tr,
            "pass": False,
        }

        if open_rc == 0:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 open P1 exited 0 (must block)")
            return 1
        if open_doc.get("failing_condition_id") != 10:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 failing-condition-id is not 10")
            return 1
        if DEFECT_ID not in (open_doc.get("named_defect_ids") or []):
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 defect id not named")
            return 1
        if DEFECT_ID not in open_tr:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 transcript does not name the defect id")
            return 1
        if open_doc.get("other_11_satisfied") is not True:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print(f"FAILED:TST-0010-probe1 other 11 not SATISFIED {open_doc.get('other_11_unsatisfied')}")
            return 1
        if open_doc.get("state") == "SUCCESS" or open_doc.get("can_reach_success"):
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 open P1 reached SUCCESS")
            return 1
        if closed_rc != 0:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print(f"FAILED:TST-0010-probe1 closed P1 evaluate rc={closed_rc}")
            return 1
        if closed_doc.get("can_reach_success") is not True:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 closed P1 still blocked")
            return 1
        if closed_doc.get("failing_condition_id") is not None:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0010-probe1 closed P1 has a failing condition")
            return 1

        freeze = HERE / "fixtures"
        freeze.mkdir(parents=True, exist_ok=True)
        (freeze / "blocked_open_p1.transcript.txt").write_text(
            open_tr + "\n" + json.dumps(open_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (freeze / "candidate_open_p1.json").write_text(
            open_receipt.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (freeze / "candidate_closed_p1.json").write_text(
            closed_receipt.read_text(encoding="utf-8"), encoding="utf-8"
        )

        payload["pass"] = True
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"open_rc={open_rc} named={open_doc.get('named_defect_ids')} "
            f"closed_rc={closed_rc} other_11={open_doc.get('other_11_satisfied')}"
        )
        print("SUCCESS:TST-0010-probe1 open P1 blocks; closed P1 does not; id named")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
