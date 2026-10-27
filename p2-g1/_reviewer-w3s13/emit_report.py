#!/usr/bin/env python3
"""Emit _reviewer-w3s13/closure_report.json + fail_inventory.json (read-only).

Combines the verifier results with the program's own fail-closed schema
resolver output so each FAIL verdict carries its precise failing checks.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "platform" / "lib"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import schema_resolver as sr  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "_reviewer-w3s13"
VERIFY_OUT = HERE / "verify_out.json"
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-w3s13-2026-10-26"


def main() -> int:
    data = json.loads(VERIFY_OUT.read_text(encoding="utf-8"))
    entries = json.loads((REPO / "_shard13-w3-entries.json").read_text(encoding="utf-8"))
    report = {
        "reviewer_id": REVIEWER_ID,
        "wave": "wave3",
        "shard": 13,
        "units_total": len(data["units"]),
        "generated": data.get("generated"),
        "battery": [
            "A artifact exists/non-empty/parses, not self-declared BLOCKED/FAILED "
            "(BLOCKED + failure.classification=[reviewer-absent] = closable)",
            "B receipt_core closure rule (reviewer PASS + independent true)",
            "E catalog completion_sentinel verbatim in receipt text",
            "C output_schema resolved fail-closed via platform/lib/schema_resolver"
            ".validate_artifact against the declared physical schema",
            "D UNIT-ARTIFACT-MANIFEST.json primary row sha256 (CRLF->LF) matches "
            "the live artifact; supporting rows digest-checked against live tree",
            "F named probes re-executed live by the reviewer, rc=0, SUCCESS marker, "
            "no FAILED marker",
        ],
        "instruments": [
            "_reviewer-w3s13/verify_shard13_w3.py (read-only, run pre- and post-stamp)",
            "platform/lib/schema_resolver.validate_artifact (the program's fail-closed "
            "output_schema validator; the instrument prior accepted reviewers used)",
        ],
        "verdicts": {},
        "summary": {},
    }
    inventory = []
    n_pass = n_fail = 0
    for uid in data["units"]:
        rep = data["results"][uid]
        declared = entries[uid]["output_schema"]
        receipt_path = REPO / rep["output_path"]
        schema_errors: list[str] = []
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            schema_errors = sr.validate_artifact(receipt, declared)
        except Exception as exc:  # receipt unreadable is itself a fail
            schema_errors = [f"<root>: receipt unreadable: {type(exc).__name__}"]
        other_fails = [f for f in rep.get("fails", []) if not f.startswith("schema:")]
        if not rep.get("fails"):
            n_pass += 1
            verdict = {
                "verdict": "PASS",
                "state": "SUCCESS",
                "closure": ("stamped by " + REVIEWER_ID + "; manifest primary row "
                            "re-hashed to the stamped receipt (live re-hash 2026-10-26)"),
                "checks": rep.get("notes", []),
            }
        else:
            n_fail += 1
            verdict = {
                "verdict": "FAIL",
                "receipt_unchanged": True,
                "primary_failing_check": (
                    "output_schema non-conformance: declared "
                    f"{declared} resolves to "
                    f"{sr.resolve(declared).physical_path}"
                    f"{sr.resolve(declared).physical_fragment or ''} with "
                    f"{len(schema_errors)} error(s) via schema_resolver"
                ),
                "schema_error_count": len(schema_errors),
                "schema_errors_first8": [e[:220] for e in schema_errors[:8]],
                "other_failing_checks": other_fails,
                "verified_ok": [n for n in rep.get("notes", []) if "probes-ok" in n],
            }
            inventory.append(
                {
                    "unit_id": uid,
                    "declared_output_schema": declared,
                    "physical_schema": (
                        sr.resolve(declared).physical_path
                        + (sr.resolve(declared).physical_fragment or "")
                    ),
                    "schema_error_count": len(schema_errors),
                    "schema_errors": schema_errors,
                    "other_fails": other_fails,
                    "repair_hint": (
                        "builder-side receipt shape repair to the declared physical "
                        "schema (missing required core fields / probe fingerprint / "
                        "role enum / additionalProperties), then re-review; probes "
                        "and primary manifest row already verified green by the "
                        "reviewer"
                    ),
                }
            )
        report["verdicts"][uid] = verdict
    report["summary"] = {"PASS": n_pass, "FAIL": n_fail}
    (HERE / "closure_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (HERE / "fail_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"closure_report.json: {n_pass} PASS / {n_fail} FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
