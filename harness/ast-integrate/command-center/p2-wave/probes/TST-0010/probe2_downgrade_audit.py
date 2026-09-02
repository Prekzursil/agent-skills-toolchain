#!/usr/bin/env python3
"""Named probe 2: silent P1->P2 does not unblock; audited downgrade appends JSONL.

Mechanically different from probe 1: this probe mutates ledger bytes on disk,
hashes the audit-file prefix (append-only), and invokes the downgrade CLI.
Probe 1 only evaluates open vs resolved fixtures.
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
DEFECT_ID = "TST0010-D-DOWNGRADE"


def run_cli(argv: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(CLI), *argv],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def parse_eval(text: str) -> tuple[dict, str]:
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
    return json.loads("\n".join(lines[:trans_i])), lines[trans_i]


def main() -> int:
    if not CLI.is_file():
        print("FAILED:TST-0010-probe2 completion_c10.py missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="tst0010-p2-") as td:
        tmp = Path(td)
        receipt_path = tmp / "candidate.json"
        audit_path = tmp / "defect-audit.jsonl"
        receipt = c10.isolation_candidate()
        c10.open_defect(
            receipt,
            defect_id=DEFECT_ID,
            severity="P1",
            summary="planted P1 to attempt silent downgrade",
            audit_path=audit_path,
            actor="TST-0010-probe2",
            ts="2026-08-24T18:30:00Z",
        )
        c10.save_json(receipt_path, receipt)

        before_n = len(c10.load_audit(audit_path))
        before_prefix = c10.audit_prefix_sha256(audit_path, before_n)
        before_bytes = audit_path.read_bytes()

        rc0, out0 = run_cli(
            ["evaluate", "--receipt", str(receipt_path), "--audit", str(audit_path)]
        )
        doc0, tr0 = parse_eval(out0)
        if rc0 == 0 or doc0.get("failing_condition_id") != 10:
            print(out0)
            print("FAILED:TST-0010-probe2 baseline open P1 did not fail C10")
            return 1

        mutated = c10.load_json(receipt_path)
        mutated["defects"][0]["severity"] = "P2"
        c10.save_json(receipt_path, mutated)
        naive = c10.naive_c10(mutated)
        rc1, out1 = run_cli(
            ["evaluate", "--receipt", str(receipt_path), "--audit", str(audit_path)]
        )
        doc1, tr1 = parse_eval(out1)
        if naive.get("satisfied") is not True:
            print("FAILED:TST-0010-probe2 naive C10 was not fooled (control inert)")
            return 1
        if rc1 == 0 or doc1.get("failing_condition_id") != 10:
            print(out1)
            print("FAILED:TST-0010-probe2 silent P1->P2 unblocked SUCCESS")
            return 1
        if DEFECT_ID not in (doc1.get("named_defect_ids") or []):
            print(out1)
            print("FAILED:TST-0010-probe2 silent downgrade did not name the defect id")
            return 1
        if DEFECT_ID not in (doc1.get("unauthorized_downgrade_ids") or []):
            print(out1)
            print("FAILED:TST-0010-probe2 unauthorized_downgrade_ids missing")
            return 1
        if audit_path.read_bytes() != before_bytes:
            print("FAILED:TST-0010-probe2 silent mutation wrote the audit log")
            return 1

        restored = c10.load_json(receipt_path)
        restored["defects"][0]["severity"] = "P1"
        c10.save_json(receipt_path, restored)

        rc_blank, out_blank = run_cli(
            [
                "downgrade",
                "--receipt",
                str(receipt_path),
                "--audit",
                str(audit_path),
                "--defect-id",
                DEFECT_ID,
                "--to",
                "P2",
                "--reason",
                "",
                "--actor",
                "TST-0010-probe2",
            ]
        )
        if rc_blank == 0:
            print(out_blank)
            print("FAILED:TST-0010-probe2 blank-reason downgrade was accepted")
            return 1
        if len(c10.load_audit(audit_path)) != before_n:
            print("FAILED:TST-0010-probe2 blank reason appended an audit row")
            return 1

        rc_dg, out_dg = run_cli(
            [
                "downgrade",
                "--receipt",
                str(receipt_path),
                "--audit",
                str(audit_path),
                "--defect-id",
                DEFECT_ID,
                "--to",
                "P2",
                "--reason",
                "owner-approved P1 to P2 with append-only audit row",
                "--actor",
                "TST-0010-probe2",
                "--now",
                "2026-08-24T18:31:00Z",
            ]
        )
        if rc_dg != 0 or "SUCCESS:c10-downgrade" not in out_dg:
            print(out_dg)
            print("FAILED:TST-0010-probe2 audited downgrade CLI failed")
            return 1

        after_lines = [
            ln
            for ln in audit_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if len(after_lines) != before_n + 1:
            print(f"FAILED:TST-0010-probe2 audit lines {len(after_lines)} want {before_n + 1}")
            return 1
        if c10.audit_prefix_sha256(audit_path, before_n) != before_prefix:
            print("FAILED:TST-0010-probe2 audit prefix rewritten (not append-only)")
            return 1
        new_row = json.loads(after_lines[-1])
        if (
            new_row.get("action") != "downgrade"
            or new_row.get("defect_id") != DEFECT_ID
            or new_row.get("from_severity") != "P1"
            or new_row.get("to_severity") != "P2"
        ):
            print(json.dumps(new_row, indent=2))
            print("FAILED:TST-0010-probe2 audit row shape")
            return 1

        rc2, out2 = run_cli(
            ["evaluate", "--receipt", str(receipt_path), "--audit", str(audit_path)]
        )
        doc2, tr2 = parse_eval(out2)
        if rc2 != 0 or doc2.get("can_reach_success") is not True:
            print(out2)
            print("FAILED:TST-0010-probe2 audited P2 still blocked")
            return 1

        freeze = HERE / "fixtures"
        freeze.mkdir(parents=True, exist_ok=True)
        (freeze / "downgrade_audit_row.jsonl").write_text(
            after_lines[-1] + "\n", encoding="utf-8"
        )
        (freeze / "downgrade_cli.transcript.txt").write_text(
            out_dg + "\n---evaluate-after---\n" + tr2 + "\n", encoding="utf-8"
        )

        payload = {
            "probe": "probe2-downgrade-audit",
            "unit_id": "TST-0010",
            "defect_id": DEFECT_ID,
            "naive_fooled": True,
            "silent_still_blocks": True,
            "blank_reason_refused": True,
            "audit_lines_before": before_n,
            "audit_lines_after": len(after_lines),
            "prefix_hash_unchanged": True,
            "audit_row": new_row,
            "audited_can_reach_success": True,
            "silent_transcript": tr1,
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        print(
            f"silent_blocks=True naive_fooled=True audit_rows={before_n}->{len(after_lines)} "
            f"from={new_row.get('from_severity')} to={new_row.get('to_severity')}"
        )
        print("SUCCESS:TST-0010-probe2 silent downgrade refused; audit row appended")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
