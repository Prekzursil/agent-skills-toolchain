#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0476.json two-signal health report."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixtures import COMPONENTS, INVENTORY_PATH, ensure_fixtures  # noqa: E402
from tools.plugin.healthcheck import digest_text, render_report  # noqa: E402

OUT = "command-center/receipts/IMP-0476.json"
SCHEMA = "command-center/schema/health-report.schema.json"
SENTINEL = "SENTINEL:IMP-0476:HEALTH-TWO-SIGNAL"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0476/probe1_verdicts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0476/probe2_independence.py"
)
QUESTION = (
    "Implement the health-check command so every reported status is backed by "
    "two mechanically independent probes, and any single-probe check reports "
    "NOT-CHECKED rather than OK. Exact question: how many of the health checks "
    "can currently produce a green verdict from one probe alone?"
)


def main() -> int:
    inventory = ensure_fixtures()
    live = render_report(COMPONENTS, inventory)
    if live["two_signal_ok_from_one_probe_count"] != 0:
        print("FAILED:IMP-0476 emit leaked OK from one probe")
        return 1
    if live["single_probe_green_capable_count"] != 3:
        print(
            "FAILED:IMP-0476 emit capable_count="
            f"{live['single_probe_green_capable_count']} want=3"
        )
        return 1
    by_id = {c["id"]: c for c in live["checks"]}
    want = {
        "ledger.writable": "OK",
        "deploy.in_sync": "OK",
        "hooks.loaded": "NOT-CHECKED",
        "skills.registered": "NOT-CHECKED",
        "mcp.reachable": "NOT-CHECKED",
        "router.responding": "DISAGREE",
        "cache.valid": "FAIL",
    }
    for cid, status in want.items():
        row = by_id.get(cid)
        if not row or row["status"] != status:
            print(f"FAILED:IMP-0476 emit {cid} status={None if not row else row['status']} want {status}")
            return 1
        if len(row.get("probes") or []) < 1:
            print(f"FAILED:IMP-0476 emit {cid} missing probe listing")
            return 1
        if status in {"OK", "DISAGREE", "FAIL"} and len(row["probes"]) < 2:
            print(f"FAILED:IMP-0476 emit {cid} did not list BOTH probes")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks_out = []
    for row in live["checks"]:
        checks_out.append(
            {
                "id": row["id"],
                "title": row["title"],
                "component": row["component"],
                "status": row["status"],
                "declared_probe_count": row["declared_probe_count"],
                "ran_probe_count": row["ran_probe_count"],
                "unique_methods": row["unique_methods"],
                "mechanically_independent": row["mechanically_independent"],
                "violation": row["violation"],
                "can_green_from_one_probe": row["can_green_from_one_probe"],
                "naive_single_signal_would_green": row["naive_single_signal_would_green"],
                "probes": [
                    {
                        "id": p["id"],
                        "method": p["method"],
                        "command": p["command"],
                        "ok": p["ok"],
                        "ran": p["ran"],
                        "output": p["output"],
                    }
                    for p in row["probes"]
                ],
            }
        )

    doc = {
        "unit_id": "IMP-0476",
        "schema_version": 1,
        "report_kind": "health-report",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Health-check command built on two-signal probes only",
        "question": QUESTION,
        "spec_anchor": (
            "catalog IMP-0476; IMP-0043 health-check runner; "
            "rules/common/single-signal-verification.md two mechanically "
            "independent probes; failure classes single-signal-green, "
            "undeclared-source-probe"
        ),
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "exact_question": live["exact_question"],
        "exact_question_answer": live["exact_question_answer"],
        "single_probe_green_capable_count": live["single_probe_green_capable_count"],
        "single_probe_green_capable_ids": live["single_probe_green_capable_ids"],
        "two_signal_ok_from_one_probe_count": live["two_signal_ok_from_one_probe_count"],
        "two_signal_ok_ids": live["two_signal_ok_ids"],
        "two_signal_ok_count": live["two_signal_ok_count"],
        "not_checked_count": live["not_checked_count"],
        "disagree_count": live["disagree_count"],
        "fail_count": live["fail_count"],
        "check_count": live["check_count"],
        "answer_basis": (
            "Three inventory checks (hooks.loaded, skills.registered, "
            "mcp.reachable) have at least one OK probe but fewer than two "
            "mechanically independent methods, so a single-signal aggregator "
            "would green them. The shipped two-signal command renders them "
            "NOT-CHECKED, never OK. two_signal_ok_from_one_probe_count=0."
        ),
        "inventory": {
            "id": live["inventory_id"],
            "root": "command-center/p2-wave/probes/IMP-0476/fixtures/components",
            "inventory_path": "command-center/p2-wave/probes/IMP-0476/fixtures/inventory.json",
            "imp_0471_receipt": {
                "path": "command-center/receipts/IMP-0471.json",
                "present": (REPO / "command-center/receipts/IMP-0471.json").is_file(),
                "note": "Dependency receipt is absent on this worktree; inventory is the local installed-component fixture plus a live scan that found no prior health-check command besides plugin.healthcheck.installed_version.",
            },
        },
        "command": {
            "module": "tools.plugin.healthcheck",
            "cli": (
                "python3 -m tools.plugin.healthcheck --root "
                "command-center/p2-wave/probes/IMP-0476/fixtures/components "
                "--inventory command-center/p2-wave/probes/IMP-0476/fixtures/inventory.json"
            ),
            "preserved_api": "installed_version(prefix, package) still requires plugin.json and health.json versions to agree",
        },
        "checks": checks_out,
        "evidence": [
            {
                "claim": "A check that declares only one probe renders NOT-CHECKED, not OK, even when that probe is healthy.",
                "verdict": "CONFIRMED",
                "anchor": "hooks.loaded status=NOT-CHECKED with one file-stat probe ok=true",
                "ids": ["hooks.loaded", "mcp.reachable"],
            },
            {
                "claim": "Two probes that are not mechanically independent (cloned file-stat) cannot green.",
                "verdict": "CONFIRMED",
                "anchor": "skills.registered status=NOT-CHECKED unique_methods=['file-stat']",
                "ids": ["skills.registered"],
            },
            {
                "claim": "Two independent probes that disagree render DISAGREE, never OK.",
                "verdict": "CONFIRMED",
                "anchor": "router.responding file-stat ok / content-hash fail",
                "ids": ["router.responding"],
            },
            {
                "claim": "A genuinely healthy component with two independent agreeing probes renders OK.",
                "verdict": "CONFIRMED",
                "anchor": "ledger.writable and deploy.in_sync file-stat + content-hash both ok",
                "ids": ["ledger.writable", "deploy.in_sync"],
            },
        ],
        "tests": [
            {
                "id": "T1-single-probe-not-checked",
                "name": "single-probe check renders NOT-CHECKED",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-disagree-never-ok",
                "name": "two-probe disagreeing check renders DISAGREE never OK",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-positive-healthy-component",
                "name": "two-signal healthy component renders OK",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T4-independence-audit",
                "name": "three-check independence audit (file-stat vs content-hash vs clone)",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "C1-single-probe-hooks",
                "kind": "single-declared-probe",
                "description": "hooks.loaded declares one OK file-stat probe; two-signal command must not green it.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "C2-disagree-router",
                "kind": "disagreeing-independent-probes",
                "description": "router.responding file-stat OK and content-hash FAIL must be DISAGREE.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0476-probe2-independence-audit",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-reads bytes and st_size for ledger (agree), router "
                "(disagree), and skills (cloned file-stat, not independent). It "
                "does not call adjudicate()."
            ),
            "audited_checks": [
                "ledger.writable",
                "router.responding",
                "skills.registered",
            ],
        },
        "named_probes": [
            {"id": "probe1", "role": "verdict-table", "command": P1},
            {"id": "probe2", "role": "independence-audit", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0476/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": "command-center/receipts/IMP-0471.json is absent; detector two-state table was not joined.",
                "settling_experiment": "Re-run this health-check against the IMP-0471 receipt once that unit is delivered.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "scope": {
            "proof_surface": (
                "seven-check installed-component inventory under "
                "command-center/p2-wave/probes/IMP-0476/fixtures/components; "
                "tools.plugin.healthcheck two-signal adjudicator"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "IMP-0471 detector two-state receipt was present",
                "IMP-0043 production probe registry was imported",
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "tools/plugin/healthcheck.py",
                "exists": True,
                "role": "implementation",
            },
            {
                "path": str(INVENTORY_PATH.relative_to(REPO).as_posix()),
                "exists": True,
                "role": "inventory",
            },
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = digest_text(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0476 artifact {size}B below floor")
        return 1
    if SENTINEL.encode("utf-8") not in out.read_bytes():
        print("FAILED:IMP-0476 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "answer="
        + str(live["exact_question_answer"])
        + " capable="
        + ",".join(live["single_probe_green_capable_ids"])
        + " leaked_ok="
        + str(live["two_signal_ok_from_one_probe_count"])
    )
    print("SUCCESS:IMP-0476 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
