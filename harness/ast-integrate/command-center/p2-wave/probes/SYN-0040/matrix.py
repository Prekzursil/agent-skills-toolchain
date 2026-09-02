"""Both-states runner, verdict classifier, mutation sweep for SYN-0040."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from constants import (
    BUCKET_UNITS,
    CALIBRATION_ID,
    HERE,
    PRODUCTION_RECEIPT_HINTS,
    REPO,
)
from fixtures import SPECS, materialize

Json = dict[str, Any]


def classify(broken_rc: int | None, good_rc: int | None) -> str:
    if broken_rc is None or good_rc is None:
        return "NOT-CHECKED"
    if broken_rc != 0 and good_rc == 0:
        return "VALID"
    if broken_rc == 0 and good_rc == 0:
        return "SILENT-IN-BOTH"
    if broken_rc != 0 and good_rc != 0:
        return "NOISY-IN-BOTH"
    return "INVERTED"


def valid_requires_both_codes(row: Json) -> bool:
    if row.get("verdict") != "VALID":
        return True
    return isinstance(row.get("broken_exit_code"), int) and isinstance(
        row.get("good_exit_code"), int
    )


def matrix_fail_reasons(rows: list[Json]) -> list[dict[str, str]]:
    """A matrix fails when any row is silent/noisy/inverted, NOT-CHECKED, or
    VALID without both exit codes. SILENT-IN-BOTH is a failing cell.
    """
    out: list[dict[str, str]] = []
    for row in rows:
        gid = str(row.get("id") or "")
        verdict = str(row.get("verdict") or "")
        if verdict == "VALID":
            if not valid_requires_both_codes(row):
                out.append({"id": gid, "reason": "valid-without-exit-codes"})
            continue
        if verdict == "SILENT-IN-BOTH":
            out.append({"id": gid, "reason": "silent-in-both"})
        elif verdict == "NOISY-IN-BOTH":
            out.append({"id": gid, "reason": "noisy-in-both"})
        elif verdict == "INVERTED":
            out.append({"id": gid, "reason": "inverted"})
        elif verdict == "NOT-CHECKED":
            out.append({"id": gid, "reason": "not-checked"})
        else:
            out.append({"id": gid, "reason": f"unknown-verdict:{verdict}"})
    return out


def run_gate(gate_id: str, fixture_path: Path) -> tuple[int, str, list[str]]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "gates.py"), gate_id, str(fixture_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    issues: list[str] = []
    try:
        payload = json.loads(proc.stdout or "{}")
        issues = list(payload.get("issues") or [])
    except json.JSONDecodeError:
        issues = ["unparseable-gate-stdout"]
    return proc.returncode, text, issues


def production_receipt_present(unit_id: str) -> dict[str, Any]:
    hints = PRODUCTION_RECEIPT_HINTS.get(unit_id) or []
    present = [h for h in hints if (REPO / h).is_file() and (REPO / h).stat().st_size > 0]
    return {
        "hints": hints,
        "present": present,
        "any": bool(present),
    }


def run_both_states(gate_id: str, paths: dict[str, str]) -> Json:
    broken_path = REPO / paths["broken"]
    good_path = REPO / paths["good"]
    broken_rc, broken_out, broken_issues = run_gate(gate_id, broken_path)
    good_rc, good_out, good_issues = run_gate(gate_id, good_path)
    verdict = classify(broken_rc, good_rc)
    prod = production_receipt_present(gate_id)
    return {
        "id": gate_id,
        "producing_unit": gate_id,
        "title": SPECS[gate_id]["title"],
        "broken_exit_code": broken_rc,
        "good_exit_code": good_rc,
        "verdict": verdict,
        "not_checked_reason": None,
        "broken_issues": broken_issues,
        "good_issues": good_issues,
        "broken_fixture": paths["broken"],
        "good_fixture": paths["good"],
        "broken_stdout": broken_out[-500:],
        "good_stdout": good_out[-500:],
        "implementation_locus": "command-center/p2-wave/probes/SYN-0040/gates.py",
        "producing_unit_receipt": prod,
        "source": (
            "producing-unit-receipt"
            if prod["any"]
            else "fixture-local-predicate (producing unit receipt absent)"
        ),
    }


def run_mutation(gate_id: str, paths: dict[str, str]) -> Json:
    mutated_path = REPO / paths["mutated"]
    rc, out, issues = run_gate(gate_id, mutated_path)
    return {
        "id": gate_id,
        "mutation": SPECS[gate_id]["mutation_name"],
        "mutated_fixture": paths["mutated"],
        "exit_code": rc,
        "fired": rc != 0,
        "issues": issues,
        "stdout": out[-400:],
    }


def run_bucket() -> Json:
    written = materialize()
    rows = [run_both_states(gid, written[gid]) for gid in BUCKET_UNITS]
    calibration = run_both_states(CALIBRATION_ID, written[CALIBRATION_ID])
    mutations = [run_mutation(gid, written[gid]) for gid in BUCKET_UNITS]
    counts = {
        "gates": len(rows),
        "VALID": sum(1 for r in rows if r["verdict"] == "VALID"),
        "SILENT-IN-BOTH": sum(1 for r in rows if r["verdict"] == "SILENT-IN-BOTH"),
        "NOISY-IN-BOTH": sum(1 for r in rows if r["verdict"] == "NOISY-IN-BOTH"),
        "INVERTED": sum(1 for r in rows if r["verdict"] == "INVERTED"),
        "NOT-CHECKED": sum(1 for r in rows if r["verdict"] == "NOT-CHECKED"),
    }
    bucket_fails = matrix_fail_reasons(rows)
    with_silent = matrix_fail_reasons(rows + [calibration])
    return {
        "paths": written,
        "gates": rows,
        "calibration": calibration,
        "mutations": mutations,
        "counts": counts,
        "bucket_fail_reasons": bucket_fails,
        "bucket_matrix_pass": not bucket_fails,
        "silent_calibration_fails_matrix": any(
            item["reason"] == "silent-in-both" for item in with_silent
        ),
        "mutation_all_fired": all(item["fired"] for item in mutations),
    }


def every_bucket_unit_has_row(rows: list[Json]) -> bool:
    have = {str(r.get("producing_unit") or r.get("id")) for r in rows}
    return set(BUCKET_UNITS) <= have
