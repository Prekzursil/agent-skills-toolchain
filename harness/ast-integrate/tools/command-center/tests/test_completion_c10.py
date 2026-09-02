#!/usr/bin/env python3
"""Catalog tests for condition 10 (open P0/P1 attachment + audited downgrade).

Runnable as a script (emit_receipt invokes this file directly) and as pytest.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parent.parent
sys.path.insert(0, str(PKG))

import completion_c10 as c10  # noqa: E402

CLI = PKG / "completion_c10.py"


def _run(argv: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(CLI), *argv],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def _parse(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    idx = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("FAILED:condition-10") or line.startswith("PASS:condition-10")
    )
    return json.loads("\n".join(lines[:idx])), lines[idx]


def test_open_p1_blocks_success() -> None:
    with tempfile.TemporaryDirectory(prefix="c10-open-") as td:
        root = Path(td)
        receipt = c10.isolation_candidate()
        audit = root / "audit.jsonl"
        c10.open_defect(
            receipt,
            defect_id="T-OPEN-P1",
            severity="P1",
            summary="catalog test: open P1 must block",
            audit_path=audit,
            actor="test_completion_c10",
            ts="2026-08-24T18:20:00Z",
        )
        path = root / "candidate.json"
        c10.save_json(path, receipt)
        rc, out = _run(["evaluate", "--receipt", str(path), "--audit", str(audit)])
        doc, trans = _parse(out)
        assert rc != 0, out
        assert doc["failing_condition_id"] == 10
        assert "T-OPEN-P1" in (doc.get("named_defect_ids") or [])
        assert "T-OPEN-P1" in trans
        assert doc.get("other_11_satisfied") is True
        assert doc.get("can_reach_success") is not True
        assert "FAILED:condition-10" in trans


def test_closed_p1_does_not_block() -> None:
    with tempfile.TemporaryDirectory(prefix="c10-closed-") as td:
        root = Path(td)
        receipt = c10.isolation_candidate()
        audit = root / "audit.jsonl"
        c10.open_defect(
            receipt,
            defect_id="T-CLOSED-P1",
            severity="P1",
            summary="catalog test: closed P1 must not block",
            audit_path=audit,
            actor="test_completion_c10",
            ts="2026-08-24T18:20:00Z",
        )
        c10.resolve_defect(
            receipt,
            defect_id="T-CLOSED-P1",
            reason="closed for the both-states control",
            actor="test_completion_c10",
            audit_path=audit,
            status="closed",
            ts="2026-08-24T18:21:00Z",
        )
        path = root / "candidate.json"
        c10.save_json(path, receipt)
        rc, out = _run(["evaluate", "--receipt", str(path), "--audit", str(audit)])
        doc, trans = _parse(out)
        assert rc == 0, out
        assert doc.get("can_reach_success") is True
        assert doc.get("failing_condition_id") is None
        assert trans.startswith("PASS:condition-10")


def test_severity_downgrade_writes_an_audit_row() -> None:
    with tempfile.TemporaryDirectory(prefix="c10-dg-") as td:
        root = Path(td)
        receipt = c10.isolation_candidate()
        audit = root / "audit.jsonl"
        c10.open_defect(
            receipt,
            defect_id="T-DOWNGRADE",
            severity="P1",
            summary="catalog test: audited P1->P2",
            audit_path=audit,
            actor="test_completion_c10",
            ts="2026-08-24T18:30:00Z",
        )
        path = root / "candidate.json"
        c10.save_json(path, receipt)
        before_n = len(c10.load_audit(audit))
        before_prefix = c10.audit_prefix_sha256(audit, before_n)

        mutated = c10.load_json(path)
        mutated["defects"][0]["severity"] = "P2"
        naive = c10.naive_c10(mutated)
        assert naive.get("satisfied") is True
        c10.save_json(path, mutated)
        rc_silent, out_silent = _run(
            ["evaluate", "--receipt", str(path), "--audit", str(audit)]
        )
        doc_silent, _ = _parse(out_silent)
        assert rc_silent != 0
        assert doc_silent["failing_condition_id"] == 10
        assert "T-DOWNGRADE" in (doc_silent.get("unauthorized_downgrade_ids") or [])

        restored = c10.load_json(path)
        restored["defects"][0]["severity"] = "P1"
        c10.save_json(path, restored)

        rc_blank, _ = _run(
            [
                "downgrade",
                "--receipt",
                str(path),
                "--audit",
                str(audit),
                "--defect-id",
                "T-DOWNGRADE",
                "--to",
                "P2",
                "--reason",
                "",
                "--actor",
                "test_completion_c10",
            ]
        )
        assert rc_blank != 0
        assert len(c10.load_audit(audit)) == before_n

        rc_dg, out_dg = _run(
            [
                "downgrade",
                "--receipt",
                str(path),
                "--audit",
                str(audit),
                "--defect-id",
                "T-DOWNGRADE",
                "--to",
                "P2",
                "--reason",
                "owner-approved P1 to P2 with append-only audit row",
                "--actor",
                "test_completion_c10",
                "--now",
                "2026-08-24T18:31:00Z",
            ]
        )
        assert rc_dg == 0, out_dg
        assert "SUCCESS:c10-downgrade" in out_dg
        after = [ln for ln in audit.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(after) == before_n + 1
        assert c10.audit_prefix_sha256(audit, before_n) == before_prefix
        row = json.loads(after[-1])
        assert row["action"] == "downgrade"
        assert row["defect_id"] == "T-DOWNGRADE"
        assert row["from_severity"] == "P1"
        assert row["to_severity"] == "P2"
        rc_ok, out_ok = _run(["evaluate", "--receipt", str(path), "--audit", str(audit)])
        doc_ok, _ = _parse(out_ok)
        assert rc_ok == 0, out_ok
        assert doc_ok.get("can_reach_success") is True


def main() -> int:
    tests = [
        test_open_p1_blocks_success,
        test_closed_p1_does_not_block,
        test_severity_downgrade_writes_an_audit_row,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print("SUCCESS:test_completion_c10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
