#!/usr/bin/env python3
"""Planted-unattested vs genuine-run controls for CNF-0008."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from attestation import classify_one, opposite_controls

GENUINE_BODY = (
    "from pathlib import Path\n"
    "import sys\n"
    "Path(sys.argv[1]).write_text('CNF-0008 genuine probe ran\\n', encoding='utf-8')\n"
)


def planted_receipt(tmp: Path) -> dict:
    missing = tmp / "never-ran.out"
    phantom = tmp / "never_ran_probe.py"
    cmd = f"{sys.executable} {phantom} {missing}"
    return {
        "id": "receipt-planted-unattested",
        "claim_id": "CNF-0008-planted-never-run",
        "confirmer": {"id": "cnf-0008-planted-confirmer", "vendor": "fixture"},
        "source_probe": {
            "id": "never-ran-probe",
            "tool": "Bash",
            "shell": "bash",
            "command": cmd,
            "data_field": "produced_file",
            "measurement_kind": "exit-and-mtime",
        },
        "verifier_probe": {
            "id": "attestation-auditor",
            "tool": "Python",
            "shell": "python3",
            "command": "attestation.classify_one",
            "data_field": "ledger_and_mtime",
            "measurement_kind": "cross-check",
        },
        "verbatim_output": "asserted without a run",
        "verdict": "CONFIRMED",
        "residual": "none claimed",
        "ledger_row_id": "ledger-does-not-exist",
        "produced_path": str(missing),
        "exit_code": 0,
    }


def run_genuine(tmp: Path) -> tuple[dict, list[dict]]:
    script = tmp / "genuine_probe.py"
    out = tmp / "genuine-probe.out"
    script.write_text(GENUINE_BODY, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        raise RuntimeError(
            f"genuine probe failed rc={proc.returncode} out={out} "
            f"stderr={(proc.stderr or '')[-400:]}"
        )
    cmd = f"{sys.executable} {script} {out}"
    ledger_id = "ledger-genuine-001"
    mtime = out.stat().st_mtime
    ledger_row = {
        "id": ledger_id,
        "tool": "Bash",
        "shell": "bash",
        "command": cmd,
        "exit_code": proc.returncode,
        "produced": [{"path": str(out), "mtime": mtime}],
        "data_field": "produced_file",
        "measurement_kind": "exit-and-mtime",
    }
    receipt = {
        "id": "receipt-genuine-control",
        "claim_id": "CNF-0008-control-ran",
        "confirmer": {"id": "cnf-0008-genuine-confirmer", "vendor": "fixture"},
        "source_probe": {
            "id": "genuine-probe",
            "tool": "Bash",
            "shell": "bash",
            "command": cmd,
            "data_field": "produced_file",
            "measurement_kind": "exit-and-mtime",
        },
        "verifier_probe": {
            "id": "attestation-auditor",
            "tool": "Python",
            "shell": "python3",
            "command": "attestation.classify_one",
            "data_field": "ledger_and_mtime",
            "measurement_kind": "cross-check",
        },
        "verbatim_output": (proc.stdout or "") + out.read_text(encoding="utf-8"),
        "verdict": "CONFIRMED",
        "residual": "none",
        "ledger_row_id": ledger_id,
        "produced_path": str(out),
        "produced_mtime": mtime,
        "exit_code": proc.returncode,
    }
    return receipt, [ledger_row]


def run_both(tmp: Path) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    planted = planted_receipt(tmp)
    genuine, ledger = run_genuine(tmp)
    planted_row = classify_one(planted, [], [tmp])
    genuine_row = classify_one(genuine, ledger, [tmp])
    ok = opposite_controls(planted_row, genuine_row)
    (tmp / "planted-receipt.json").write_text(
        json.dumps(planted, indent=2) + "\n", encoding="utf-8"
    )
    (tmp / "genuine-receipt.json").write_text(
        json.dumps(genuine, indent=2) + "\n", encoding="utf-8"
    )
    (tmp / "ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in ledger), encoding="utf-8"
    )
    return {
        "ok": ok,
        "planted": planted_row,
        "genuine": genuine_row,
        "planted_receipt": planted,
        "genuine_receipt": genuine,
        "ledger": ledger,
        "tmp": str(tmp),
    }
