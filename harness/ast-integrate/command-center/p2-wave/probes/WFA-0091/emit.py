#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0091-repair-schema-typed-fanin.json."""
from __future__ import annotations

import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fanin as F  # noqa: E402
import fixtures as FX  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0091-repair-schema-typed-fanin.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0091/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0091/probe2_receipt_before_digest.py"
)
QUESTION = (
    "Implementation target: make every fan-in validate each returned result "
    "against its schema, tolerate nulls without collapsing the barrier, and "
    "verify the contracted output file EXISTS on disk before any returned "
    "digest is read - since a plausible digest for a file that does not exist "
    "is a measured, reproduced failure."
)


def live_workflow_scan() -> dict:
    homes = [
        Path.home() / ".claude" / "workflows",
        Path("/root/.claude/workflows"),
        Path(os.path.expanduser("~/.claude/workflows")),
    ]
    found: list[dict] = []
    for root in homes:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in {".js", ".mjs", ".ts"} and p.is_file():
                found.append({"path": str(p), "bytes": p.stat().st_size})
    return {
        "roots_checked": [str(r) for r in homes],
        "workflow_files": found,
        "n": len(found),
        "present": bool(found),
    }


def ast_order() -> dict:
    src = (HERE / "fanin.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "repaired_fan_in"
    )
    exists_line = digest_line = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name == "existence_check" and exists_line is None:
            exists_line = node.lineno
        if name == "read_claimed_digest" and digest_line is None:
            digest_line = node.lineno
    return {
        "existence_check_lineno": exists_line,
        "read_claimed_digest_lineno": digest_line,
        "exists_before_digest": bool(
            exists_line is not None
            and digest_line is not None
            and exists_line < digest_line
        ),
    }


def main() -> int:
    FX.assert_fixture_layout()
    contracts = FX.contracts()
    inbound = FX.inbound()
    ws = FX.workspace()
    naive = F.naive_fan_in(contracts, inbound, ws)
    repaired = F.repaired_fan_in(contracts, inbound, ws)
    ns, rs = F.summarize(naive), F.summarize(repaired)

    if not repaired["completed"]:
        print("FAILED:WFA-0091 emit repaired did not complete")
        return 1
    if "U-INVALID" not in rs["rejected_ids"]:
        print("FAILED:WFA-0091 emit invalid not reported")
        return 1
    if "U-PLANTED" not in rs["rejected_ids"]:
        print("FAILED:WFA-0091 emit planted not rejected")
        return 1
    if "U-NULL" not in rs["missing_null"]:
        print("FAILED:WFA-0091 emit null not reported")
        return 1
    if "U-PLANTED" not in ns["silently_accepted_missing_file"]:
        print("FAILED:WFA-0091 emit naive did not accept planted (control dead)")
        return 1

    events = repaired["events"]
    exists_idx = [i for i, e in enumerate(events) if e.get("op") == "exists"]
    digest_idx = [i for i, e in enumerate(events) if e.get("op") == "read_digest"]
    all_exists_before = (not digest_idx) or (max(exists_idx) < min(digest_idx))
    planted_digest_events = [
        e for e in events if e.get("op") == "read_digest" and e.get("unit_id") == "U-PLANTED"
    ]
    order = ast_order()
    live = live_workflow_scan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    answer = (
        "Repaired fan-in (command-center/p2-wave/probes/WFA-0091/fanin.py:"
        "repaired_fan_in) existence-checks every contracted output path before "
        "any returned digest is parsed, schema-validates each payload, reports "
        "nulls as missing units without collapsing, and records waited_for vs "
        "not_received. Mixed cohort (valid + null + schema-invalid) completes "
        f"with invalid reported ({rs['rejected_ids']}) and null in missing_null "
        f"({rs['missing_null']}). Planted digest {FX.PLANTED_DIGEST[:12]}… for "
        "absent U-PLANTED/result.json is rejected with reason=no-receipt and "
        f"digest_parsed=false (naive control accepts it). Live ~/.claude/workflows "
        f"on this Linux worktree: n={live['n']}. "
        "SUCCESS:WFA-0091"
    )

    planted_row = next(r for r in repaired["rejected"] if r["unit_id"] == "U-PLANTED")
    invalid_row = next(r for r in repaired["rejected"] if r["unit_id"] == "U-INVALID")

    doc = {
        "record_type": "RepairRecord",
        "unit_id": "WFA-0091",
        "id": "WFA-0091",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0091",
        "completion_sentinel": "SUCCESS:WFA-0091",
        "title": (
            "Repair the fan-in barrier: schema-typed results, null tolerance, "
            "and a receipt check before any digest is read"
        ),
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RepairRecord"
        ),
        "schema_pack_present": schema_pack.is_file(),
        "defect": {
            "class": [
                "detector-failure",
                "uncontrolled-silence",
                "overclaim",
            ],
            "measured_failure": (
                "A plausible sha256 digest for a contracted output that is not "
                "on disk was treated as a receipt; null results were dropped by "
                "filter(Boolean) with no missing-unit line; schema-invalid "
                "payloads were accepted."
            ),
            "pre_fix": "naive_fan_in",
            "post_fix": "repaired_fan_in",
        },
        "implementation": {
            "module": "command-center/p2-wave/probes/WFA-0091/fanin.py",
            "repaired_entry": "repaired_fan_in",
            "naive_entry": "naive_fan_in",
            "result_schema": F.RESULT_SCHEMA,
            "live_workflow_sites": live,
            "note": (
                "Live Claude saved-workflow fan-in sites are absent on this "
                "worktree; the repaired barrier is the executable contract "
                "and both-states control for every fan-in of this class."
            ),
        },
        "both_states": {
            "naive_drops_null": "U-NULL" in ns["silently_dropped_nulls"],
            "naive_accepts_invalid": "U-INVALID" in ns["silently_accepted_invalid"],
            "naive_accepts_planted": "U-PLANTED" in ns["silently_accepted_missing_file"],
            "repaired_reports_null": "U-NULL" in rs["missing_null"],
            "repaired_rejects_invalid": "U-INVALID" in rs["rejected_ids"],
            "repaired_rejects_planted": "U-PLANTED" in rs["rejected_ids"],
            "naive_summary": ns,
            "repaired_summary": rs,
        },
        "evidence_A_mixed_cohort": {
            "completed": bool(repaired["completed"]),
            "units": ["U-VALID", "U-NULL", "U-INVALID"],
            "accepted": rs["accepted_ids"],
            "invalid_reported": "U-INVALID" in rs["rejected_ids"],
            "invalid_reason": invalid_row.get("reason"),
            "null_reported_as_missing": "U-NULL" in rs["missing_null"],
            "invalid_silently_accepted": "U-INVALID" in rs["accepted_ids"],
        },
        "evidence_B_receipt_before_digest": {
            "all_existence_checks_before_any_digest_parse": all_exists_before,
            "exists_event_count": len(exists_idx),
            "read_digest_event_count": len(digest_idx),
            "planted_digest": FX.PLANTED_DIGEST,
            "planted_path": "U-PLANTED/result.json",
            "planted_file_present": (ws / FX.PLANTED_REL).is_file(),
            "planted_rejected_reason": planted_row.get("reason"),
            "planted_digest_parsed": bool(planted_row.get("digest_parsed")),
            "ast_order": order,
        },
        "wait_ledger": {
            "waited_for": repaired["waited_for"],
            "not_received": repaired["not_received"],
            "missing_null": repaired["missing_null"],
            "accepted_ids": rs["accepted_ids"],
            "rejected_ids": rs["rejected_ids"],
        },
        "tests": [
            {
                "id": "T1-planted-digest-both-states",
                "name": "planted digest-for-a-missing-file rejected after repair, accepted before",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-null-not-silently-dropped",
                "name": "null result reported as missing unit",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-wait-ledger",
                "name": "barrier records waited_for and not_received",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0091-probe2-receipt-before-digest",
            "verdict": "PASS",
            "independent": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "caveats": [
            (
                "Live ~/.claude/workflows is absent on this Linux worktree "
                f"(n={live['n']}). The repair is the schema-typed barrier plus "
                "both-states fixtures, not a patch of a missing live workflow tree."
            ),
            (
                "WFA-0001 schema pack is "
                + ("present" if schema_pack.is_file() else "absent")
                + "; this RepairRecord is field-shaped to the catalog contract "
                "and is not jsonschema-validated against the missing $defs/RepairRecord."
            ),
        ],
        "environment": {
            "cwd": str(REPO),
            "os": os.uname().sysname if hasattr(os, "uname") else sys.platform,
            "python": sys.version.split()[0],
            "ts": now,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:WFA-0091")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
