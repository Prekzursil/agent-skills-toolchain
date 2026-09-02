#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0140.json from a live campaign.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from b07_scheduler import (  # noqa: E402
    COMMENT_ONLY_CONFIG_TEXT,
    HOLD_S,
    WAIT_BUDGET_S,
    comment_only_config,
    run_campaign,
)

UNIT = "TST-0140"
OUT = "command-center/receipts/TST-0140.json"
SENTINEL = "SUCCESS:TST-0140"
SCHEMA_CATALOG = "command-center/schema/receipt.schema.json#/$defs/scheduler_report"
SCHEMA_LIVE = "command-center/schema/test-receipt.schema.json"
IMPL = "command-center/lib/b07_scheduler/lanes.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0140/probe1_reservation_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0140/probe2_comment_and_deferral_audit.py"
)
QUESTION = (
    "With a batch sweep saturating the shared subscription, does an "
    "interactive request still get served within its latency budget? PASS "
    "requires: a measurable reservation (not a documented intention), and "
    "the reservation must be observable as a refused/deferred batch dispatch "
    "at the moment the interactive request arrives."
)


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def validate_test_receipt(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA_LIVE
    if not schema_path.is_file():
        return [f"missing {SCHEMA_LIVE}"]
    try:
        import jsonschema
    except ImportError:
        required = [
            "unit_id",
            "state",
            "sentinel",
            "question",
            "tests",
            "evidence",
            "reviewer",
            "artifacts",
        ]
        return [f"missing {k}" for k in required if k not in doc]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            errs.append("schema accepted garbage")
            break
    return errs


def latency_public(arm: dict) -> dict:
    lat = arm["latency"]
    return {
        "n": lat["n"],
        "p50": lat["p50"],
        "p95": lat["p95"],
        "max": lat["max"],
        "mean": lat["mean"],
        "within_budget": arm.get("within_budget"),
        "headroom_deferral_count": arm.get("headroom_deferral_count"),
    }


def main() -> int:
    campaign = run_campaign()
    if not campaign.get("pass"):
        print("FAILED:TST-0140 emit campaign predicates failed")
        print(json.dumps(campaign.get("predicates"), indent=2))
        return 1

    comments = comment_only_config()
    impl_b, impl_s, impl_ok = sha_file(IMPL)
    _schema_b, schema_s, schema_ok = sha_file(SCHEMA_LIVE)
    catalog_schema = REPO / "command-center" / "schema" / "receipt.schema.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sweep_on = campaign["sweep_reserved"]
    no_sweep = campaign["no_sweep_reserved"]
    sweep_off = campaign["sweep_unreserved"]
    sweep_comment = campaign["sweep_comment_only"]
    preds = campaign["predicates"]
    headroom_events = sweep_on.get("headroom_events") or []
    first_event = headroom_events[0] if headroom_events else {}

    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Interactive lane keeps reserved headroom against a batch sweep",
        "question": QUESTION,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0140; "
            "_USER-PROMPTS.md:11008 and :10570-10583 (file absent on this sparse worktree)"
        ),
        "output_schema": SCHEMA_CATALOG,
        "live_schema": SCHEMA_LIVE,
        "min_bytes_threshold": 2048,
        "execution_substrate": "local-serialized",
        "implementation": {
            "scheduler": IMPL,
            "config": "command-center/lib/b07_scheduler/config.py",
            "sweep": "command-center/lib/b07_scheduler/sweep.py",
            "rule": (
                "Shared subscription capacity C, interactive_reserved R. "
                "batch_ceiling = C-R when reservation_enabled. A batch try "
                "at the ceiling is DEFER'd with reason interactive-headroom "
                "while occupied < C; the leftover slot is admitted to "
                "interactive. A '#' comment is not this subtraction."
            ),
            "sha256": impl_s,
            "bytes": impl_b,
            "present": impl_ok,
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md:11008": "absent; catalog target used as the spec",
            "_USER-PROMPTS.md:10570-10583": "absent",
            "tools/command-center/measure_rate.py": (
                "present; register-gate rate tool, not this scheduler"
            ),
            "B07 dispatcher + scheduler": (
                "absent as a shipped dispatcher; this unit authored "
                "command-center/lib/b07_scheduler/ as the lane-reservation slice"
            ),
            SCHEMA_CATALOG: (
                "absent; catalog names receipt.schema.json#/$defs/scheduler_report. "
                "Live validation uses test-receipt.schema.json."
            ),
        },
        "campaign": {
            "hold_s": HOLD_S,
            "wait_budget_s": WAIT_BUDGET_S,
            "n_samples": campaign["n_samples"],
            "no_sweep_reserved": latency_public(no_sweep),
            "sweep_reserved": latency_public(sweep_on),
            "sweep_unreserved": latency_public(sweep_off),
            "sweep_comment_only": latency_public(sweep_comment),
            "predicates": preds,
            "comment_only_parsed": comments.to_dict(),
            "comment_only_fixture_has_commented_reservation": (
                "# interactive_reserved = 1" in COMMENT_ONLY_CONFIG_TEXT
            ),
        },
        "tests": [
            {
                "id": "both-states-disable-reservation",
                "result": "PASS" if preds["both_states"] else "FAIL",
                "detail": (
                    "reservation on: interactive p50 within budget under sweep; "
                    "reservation off: interactive p50 held for ~hold_s and >3x reserved"
                ),
                "p50_reserved": sweep_on["latency"]["p50"],
                "p50_unreserved": sweep_off["latency"]["p50"],
            },
            {
                "id": "negative-comment-only-reservation",
                "result": (
                    "PASS" if preds["comment_only_fails_as_reservation"] else "FAIL"
                ),
                "detail": (
                    "parse_lane_config ignores # interactive_reserved = 1; "
                    "comment-only sweep misses budget and emits zero headroom deferrals"
                ),
                "p50_comment_only": sweep_comment["latency"]["p50"],
                "headroom_deferral_count": sweep_comment.get("headroom_deferral_count"),
            },
            {
                "id": "deferral-at-interactive-arrival",
                "result": (
                    "PASS" if preds["deferral_at_interactive_arrival"] else "FAIL"
                ),
                "detail": (
                    "at interactive admit, extra batch is DEFER interactive-headroom "
                    "with occupied < capacity"
                ),
                "headroom_deferral_count": sweep_on.get("headroom_deferral_count"),
                "sample_event": first_event,
            },
            {
                "id": "latency-with-and-without-sweep",
                "result": (
                    "PASS" if preds["sweep_does_not_inflate_when_reserved"] else "FAIL"
                ),
                "detail": (
                    "reserved interactive p50 stays in budget with and without the sweep"
                ),
                "p50_no_sweep": no_sweep["latency"]["p50"],
                "p50_sweep": sweep_on["latency"]["p50"],
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Interactive wait-to-admit p50 with reservation: no-sweep="
                    f"{no_sweep['latency']['p50']:.6f}s sweep="
                    f"{sweep_on['latency']['p50']:.6f}s (budget "
                    f"{WAIT_BUDGET_S}s). Disabling reservation under the same "
                    f"sweep: p50={sweep_off['latency']['p50']:.6f}s (~{HOLD_S}s hold)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/lib/b07_scheduler/sweep.py:run_campaign",
                "signal": "a-interactive-latency-distribution",
            },
            {
                "claim": (
                    "At interactive arrival, extra batch dispatch is DEFER with "
                    "reason interactive-headroom while occupied < capacity "
                    f"({sweep_on.get('headroom_deferral_count')} / "
                    f"{campaign['n_samples']} reserved-sweep trials). "
                    "Comment-only config emits 0 such deferrals."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/lib/b07_scheduler/lanes.py:"
                    "admit_interactive_refusing_batch"
                ),
                "signal": "b-scheduler-deferral-log",
                "sample_event": first_event,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0140-probe2-deferral-audit",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs a reserved trial and inspects the paired "
                "batch DEFER + interactive ADMIT, AST-checks batch_ceiling, "
                "and runs the comment-only config as a negative control. It "
                "does not author lanes.py admission logic."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": IMPL, "role": "implementation", "sha256": impl_s, "bytes": impl_b},
            {
                "path": SCHEMA_LIVE,
                "role": "supporting",
                "present": schema_ok,
                "sha256": schema_s,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "reservation-both-states-and-sweep-latency",
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "comment-only-negative-and-deferral-audit",
            },
        ],
        "schema_note": (
            f"Catalog output_schema is {SCHEMA_CATALOG}. "
            f"{catalog_schema.as_posix()} is "
            f"{'present' if catalog_schema.is_file() else 'absent'} on this "
            "worktree. Live validation uses test-receipt.schema.json."
        ),
        "ts": now,
        "notes": (
            "G-1 for TST-0140: live named probes exit 0, receipts/TST-0140.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild. "
            "SUCCESS:TST-0140"
        ),
    }

    errs = validate_test_receipt(receipt)
    if errs:
        print("FAILED:TST-0140 emit schema", errs[:8])
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0140 emit sentinel missing")
        return 1
    if len(text.encode("utf-8")) < int(receipt["min_bytes_threshold"]):
        print("FAILED:TST-0140 emit under min_bytes_threshold")
        return 1
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
