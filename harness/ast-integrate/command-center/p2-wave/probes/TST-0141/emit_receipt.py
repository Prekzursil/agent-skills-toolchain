#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0141.json from live property + mutation runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import N_INTERLEAVINGS, N_TAKERS, run_all  # noqa: E402
from token_bucket import audit_permits  # noqa: E402

OUT = "command-center/receipts/TST-0141.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0141/probe1_property.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0141/probe2_audit.py"
)
QUESTION = (
    "Under 64 concurrent takers, can the token bucket ever go negative or "
    "issue more permits than its capacity in any window? PASS requires zero "
    "violations across a randomized property run and a deterministic replay "
    "of any counterexample."
)
ANSWER = (
    "NO: 10_000 randomized 64-taker interleavings of the CAS bucket produced "
    "zero negative balances and zero over-capacity windows. An independent "
    "recompute of the issued-permit log agrees. Removing the CAS compare "
    "makes a 2-taker colliding schedule over-issue; the shrinker reduces a "
    "padded counterexample and the replay still fails."
)


def main() -> int:
    bundle = run_all()
    if not bundle["ok"]:
        print("FAILED:TST-0141 emit property/mutation/live did not pass")
        print(json.dumps({k: bundle.get(k) for k in ("property", "mutation", "live_threads")}, indent=2)[:4000])
        return 1

    prop = bundle["property"]
    mut = bundle["mutation"]
    live = bundle["live_threads"]
    live_log = bundle["live_permit_log"]
    live_audit = audit_permits(live_log, live["capacity"])
    if not live_audit["ok"]:
        print("FAILED:TST-0141 emit independent live audit")
        print(json.dumps(live_audit, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0141",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "scheduler_report",
        "title": "Token-bucket accounting is race-free under N concurrent takers",
        "question": QUESTION,
        "answer": ANSWER,
        "sentinel": "SUCCESS:TST-0141",
        "completion_sentinel": "SUCCESS:TST-0141",
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "registered": True,
        "output_schema": SCHEMA,
        "catalog_output_schema": (
            "command-center/schema/receipt.schema.json#/$defs/scheduler_report"
        ),
        "property": {
            "n": prop["n"],
            "n_takers": prop["n_takers"],
            "runs_completed": prop["runs_completed"],
            "failures": prop["failures"],
            "granted_histogram": prop["granted_histogram"],
            "seed": prop["seed"],
            "ok": prop["ok"],
        },
        "mutation": {
            "ok": mut["ok"],
            "crafted_violations": mut["crafted_violations"],
            "crafted_tokens": mut["crafted_tokens"],
            "crafted_granted": mut["crafted_granted"],
            "crafted_audit": mut["crafted_audit"],
            "padded_len": mut["padded_len"],
            "shrunk_len": mut["shrunk_len"],
            "shrunk_schedule": mut["shrunk_schedule"],
            "shrunk_violations": mut["shrunk_violations"],
            "cas_control_ok": mut["cas_control_ok"],
            "cas_granted": mut["cas_granted"],
            "cas_tokens": mut["cas_tokens"],
            "lock_cas_removed": True,
        },
        "live_threads": {
            "n_takers": live["n_takers"],
            "capacity": live["capacity"],
            "granted": live["granted"],
            "tokens": live["tokens"],
            "ok": live["ok"],
            "independent_audit": live_audit,
        },
        "tests": [
            {
                "id": "property-10000-randomized-interleavings",
                "requirement": (
                    "property test with 10,000 randomized interleavings; any "
                    "counterexample must shrink to a minimal reproducing schedule"
                ),
                "verdict": "PASS",
                "evidence": (
                    f"n={prop['n']} n_takers={prop['n_takers']} "
                    f"runs_completed={prop['runs_completed']} "
                    f"failures={prop['failures']} seed={prop['seed']}"
                ),
            },
            {
                "id": "mutation-remove-lock-cas",
                "requirement": (
                    "mutation control: remove the lock/CAS and confirm the "
                    "property fails"
                ),
                "verdict": "PASS",
                "evidence": (
                    f"mutant granted={mut['crafted_granted']} "
                    f"tokens={mut['crafted_tokens']} "
                    f"violations={mut['crafted_violations']} "
                    f"padded_len={mut['padded_len']} shrunk_len={mut['shrunk_len']} "
                    f"cas_control_ok={mut['cas_control_ok']} cas_granted={mut['cas_granted']}"
                ),
            },
        ],
        "controls": {
            "internal_invariant": {
                "pass": True,
                "note": (
                    "SimBucket.cas and TokenBucket.take assert "
                    "0 <= tokens <= capacity after every successful mutation "
                    "and record trips on the mutant."
                ),
            },
            "external_permit_log_audit": {
                "pass": True,
                "note": (
                    "audit_permits() never reads the bucket's token field; it "
                    "sums amount per window_id from the issued-permit log."
                ),
                "live_audit": live_audit,
                "mutant_audit": mut["crafted_audit"],
            },
            "cas_vs_mutant_same_schedule": {
                "pass": True,
                "schedule": [("step", 0), ("step", 1), ("step", 0), ("step", 1)],
                "mutant_ok": False,
                "cas_ok": mut["cas_control_ok"],
            },
        },
        "evidence": [
            {
                "kind": "internal-invariant",
                "path": "command-center/p2-wave/probes/TST-0141/token_bucket.py",
                "note": (
                    "Invariant trips live on SimBucket.invariant_trips / "
                    "TokenBucket.invariant_trips. CAS 10_000-run min_tokens stayed "
                    f">= 0 (granted histogram {prop['granted_histogram']})."
                ),
            },
            {
                "kind": "external-permit-log-audit",
                "path": "command-center/p2-wave/probes/TST-0141/token_bucket.py",
                "note": (
                    f"Independent audit of the 64-thread permit log: "
                    f"ok={live_audit['ok']} per_window={live_audit['per_window']} "
                    f"total_granted={live_audit['total_granted']} "
                    f"over_capacity_windows={live_audit['over_capacity_windows']}."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0141-probe2-permit-log-audit",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes window totals from the permit log without "
                "reading the bucket token field, and requires the CAS-removed "
                "mutant to over-issue on a colliding 2-taker schedule while the "
                "same schedule is clean with CAS. Shrinker must shorten a padded "
                "counterexample and replay still fails."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "property-10000-interleavings", "command": P1},
            {"id": "probe2", "role": "permit-log-audit-mutation", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0141/token_bucket.py",
                "exists": True,
                "role": "implementation",
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "receipt.schema.json#/$defs/scheduler_report exists on this tree",
            ],
            "proof_surface": (
                "deterministic 10_000-seed interleavings of 64 takers; "
                "independent permit-log audit; CAS-removed colliding schedule "
                "plus shrink/replay"
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "scheduler-tester",
            "execution_substrate": "linux-local",
        },
        "measured_at": now,
        "n_interleavings": N_INTERLEAVINGS,
        "n_takers": N_TAKERS,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0141 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:TST-0141" not in text:
        print("FAILED:TST-0141 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:TST-0141 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
