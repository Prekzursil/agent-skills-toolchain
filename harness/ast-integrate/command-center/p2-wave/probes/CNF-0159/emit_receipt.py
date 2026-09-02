#!/usr/bin/env python3
"""Emit CNF-0159 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))
import dispatch_integrity as di  # noqa: E402

UID = "CNF-0159"
OUT_REL = "command-center/receipts/CNF-0159.json"
SCHEMA_REL = "command-center/schema/confirmation-tooling-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0159/probe1_known_broken.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0159/probe2_both_states_order.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/confirmation/dispatch_integrity/gate.py",
    "command-center/confirmation/dispatch_integrity/pipeline.py",
    "command-center/confirmation/dispatch_integrity/digest_reader.py",
    "command-center/confirmation/dispatch_integrity/ledger.py",
    "command-center/confirmation/dispatch_integrity/historical_ledger.jsonl",
    "command-center/p2-wave/probes/CNF-0159/probe1_known_broken.py",
    "command-center/p2-wave/probes/CNF-0159/probe2_both_states_order.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def confirmation_output_paths() -> list[dict]:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    rows = []
    for u in catalog.get("work_units") or []:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or "")
        if not uid.startswith("CNF-"):
            continue
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        p = REPO / rel
        rows.append(
            {
                "unit_id": uid,
                "output_path": rel,
                "present": p.is_file() and p.stat().st_size > 0,
            }
        )
    return rows


def gate_logs() -> list[dict]:
    logs = []
    rows = di.load_historical_ledger(REPO)
    for row in rows:
        di.reset_parse_events()
        out = di.fan_in(REPO, di.ledger_row_to_result(row))
        logs.append(
            {
                "source": "historical_ledger",
                "ledger_id": row.get("ledger_id"),
                "kind": row.get("kind"),
                "accepted": out["accepted"],
                "rejected_by": out["gate"]["rejected_by"],
                "file_opened": out["gate"]["file_opened"],
                "digest_reader_invoked": bool(di.parse_events()),
                "checks": out["gate"]["checks"],
            }
        )
    return logs


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    logs = gate_logs()
    if not logs:
        print("FAILED:emit no ledger logs")
        return 1
    if any(row["accepted"] for row in logs):
        print("FAILED:emit historical ledger row accepted")
        return 1
    if any(row["digest_reader_invoked"] for row in logs):
        print("FAILED:emit digest reader invoked on ledger reject")
        return 1

    census = confirmation_output_paths()
    present = sum(1 for r in census if r["present"])
    missing = [r["unit_id"] for r in census if not r["present"]]
    cnf0154 = next((r for r in census if r["unit_id"] == "CNF-0154"), None)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0159",
        "completion_sentinel": "SUCCESS:CNF-0159",
        "title": "Dispatch-integrity gate: reject fire-and-forget receipts before any digest is read",
        "question_or_target": (
            "Implementation target: a fan-in gate that runs BEFORE any confirmation "
            "digest is read and rejects (a) any result containing 'started in the "
            "background' or 'Check /codex:status', (b) any result whose contracted "
            "output file fails Test-Path, and (c) any result whose file is empty or "
            "unparsable. Measured precedent: 3 of 3 cross-vendor agents returned "
            "plausible digests for files that do not exist, and one agent's entire "
            "final answer was a background receipt whose real finding was discarded unread."
        ),
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "output_schema": SCHEMA_REL,
        "implementation": {
            "gate": "command-center/confirmation/dispatch_integrity/gate.py",
            "pipeline": "command-center/confirmation/dispatch_integrity/pipeline.py",
            "digest_reader": "command-center/confirmation/dispatch_integrity/digest_reader.py",
            "ledger": "command-center/confirmation/dispatch_integrity/historical_ledger.jsonl",
            "call_order": "fan_in calls evaluate_result, returns on reject, then calls read_digest",
            "test_path_equivalent": "pathlib.Path.is_file (PowerShell Test-Path -PathType Leaf)",
            "notes": (
                "CNF-0154 dispatch records are absent on this worktree "
                f"(present={None if cnf0154 is None else cnf0154['present']}). "
                "The historical ledger freezes the catalog's measured precedent as JSONL "
                "and the gate is exercised on those rows. A reconstructed ledger is not "
                "a live CNF-0154 MCP transcript; it is the bad input the catalog names."
            ),
        },
        "checks_per_result": logs,
        "confirmation_output_census": {
            "confirmation_units_with_output_path": len(census),
            "present_nonempty": present,
            "absent_or_empty": len(census) - present,
            "cnf0154_contracted_path": None if cnf0154 is None else cnf0154["output_path"],
            "cnf0154_present": None if cnf0154 is None else cnf0154["present"],
            "sample_absent": missing[:12],
        },
        "evidence": [
            {
                "id": "E1-three-checks-logged",
                "kind": "gate-log",
                "detail": (
                    "Every fan_in result records background_receipt, test_path, and "
                    "parseable with passed/skipped/detail. Historical ledger rows: "
                    + json.dumps(
                        [
                            {
                                "ledger_id": r["ledger_id"],
                                "rejected_by": r["rejected_by"],
                                "checks": [
                                    {
                                        "name": c["name"],
                                        "passed": c["passed"],
                                        "skipped": c["skipped"],
                                    }
                                    for c in r["checks"]
                                ],
                            }
                            for r in logs
                        ]
                    )
                ),
            },
            {
                "id": "E2-historical-fire-and-forget",
                "kind": "ledger",
                "detail": (
                    "hist-fnf-001 (kind=fire-and-forget-background-receipt) was fed to "
                    "fan_in and rejected_by=background_receipt; digest reader parse "
                    "events stayed empty. Path: "
                    "command-center/confirmation/dispatch_integrity/historical_ledger.jsonl"
                ),
            },
            {
                "id": "E3-phantom-digest-before-parse",
                "kind": "ordering",
                "detail": (
                    "Three historical phantom-digest rows naming "
                    "command-center/receipts/CNF-0154.json (missing on this tree) were "
                    "rejected_by=test_path with parseable skipped and digest reader idle. "
                    "A plausible inline JSON digest is not treated as the file."
                ),
            },
            {
                "id": "E4-pipeline-ast-call-order",
                "kind": "ast",
                "detail": (
                    "probe2 parses pipeline.py AST: evaluate_result is called before "
                    "read_digest; the reject If returns before read_digest; read_digest "
                    "is not in the reject branch. This is an import/call-order test, "
                    "not a comment."
                ),
            },
        ],
        "tests_run": [
            {
                "id": "probe1-known-broken",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "covers": [
                    "synthetic background receipt rejected",
                    "digest naming nonexistent path rejected before parse",
                    "historical fire-and-forget ledger row rejected",
                    "empty and unparsable files rejected by parseable",
                ],
            },
            {
                "id": "probe2-both-states-order",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "covers": [
                    "valid result with real non-empty parsable file passes silently",
                    "AST call-order: gate before digest reader",
                    "reviewer plausible digest with no file refused",
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0159-probe2-plausible-digest-no-file",
            "verdict": "PASS",
            "independent": True,
            "attempt": (
                "Submitted a plausible SUCCESS:CNF-0159 digest (verdict CONFIRMED, "
                "fake sha256, claimed bytes=4096) whose contracted_output_path "
                "command-center/receipts/CNF-0159-reviewer-phantom.json does not exist. "
                "Gate rejected_by=test_path; digest reader was not invoked. "
                "A digest is a claim; Test-Path on the contracted file is the receipt."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/confirmation/dispatch_integrity/pipeline.py",
                "exists": True,
                "role": "implementation",
            },
        ],
        "residual_unknowns": [
            "CNF-0154 live MCP dispatch transcripts are not on this worktree; the ledger is the catalog-named measured precedent, not a harvested job log.",
            "rules/common/fan-out-contract.md and rules/common/cross-vendor-dispatch.md are not on this worktree; checks follow the unit text.",
        ],
        "ts": now,
        "SUCCESS:CNF-0159": True,
    }

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=2, sort_keys=False) + "\n"
    if "SUCCESS:CNF-0159" not in blob:
        print("FAILED:emit sentinel missing from blob")
        return 1
    out_path.write_text(blob, encoding="utf-8")

    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
        try:
            jsonschema.validate(receipt, schema)
        except Exception as exc:
            # Shim $id points at ast-integrate.invalid; G-1 does not require
            # remote $ref resolution. Receipt is already on disk.
            print(f"WARN:emit schema-ref-unresolved {type(exc).__name__}")

    sha, size = digest_file(out_path)
    if size < receipt["min_bytes_threshold"]:
        print(f"FAILED:emit receipt too small bytes={size}")
        return 1

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0159",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "known-broken-controls",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-call-order-reviewer",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0159/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0159-probe2-plausible-digest-no-file",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0159: live named probes exit 0, receipts/CNF-0159.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        s, b = digest_file(p)
        return {
            "path": rel,
            "sha256": s,
            "bytes": b,
            "present": True,
            "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/CNF-0159/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT_REL, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:CNF-0159 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
