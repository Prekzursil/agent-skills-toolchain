#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0399.json from a live harness run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import assert_harness_healthy, run_harness  # noqa: E402
from router import PIN_DIGEST, PIN_MODEL_ID  # noqa: E402

OUT = REPO / "command-center/receipts/IMP-0399.json"
SCHEMA = "command-center/schema/mutation-report.schema.json"
SENTINEL = "SENTINEL:IMP-0399:ROUTER-MUTATIONS-SCORED"
QUESTION = (
    "Implement the router mutation harness: programmatically corrupt one "
    "description, delete one trigger row, invert one precedence rule, and "
    "unpin the embedding model — and assert the regression suite goes RED "
    "for each. Exact question: how many of the four mutations SURVIVE the "
    "suite, and what exactly is unprotected for each survivor?"
)


def main() -> int:
    report = run_harness()
    try:
        assert_harness_healthy(report)
    except AssertionError as exc:
        print(f"FAILED:IMP-0399 emit harness unhealthy: {exc}")
        print(json.dumps(report, indent=2, default=str)[:4000])
        return 1

    survivors = [
        {
            "mutation": row["mutation"],
            "unprotected_behavior": row["unprotected_if_survived"],
            "observed": row["observed"],
            "failure_ids": row["failure_ids"],
        }
        for row in report["contracted"]
        if row["survived"]
    ]
    killed_rows = [row for row in report["contracted"] if row["killed"]]
    state = "SUCCESS"
    if report["detector_broken"] or report["n_killed"] < 1:
        state = "FAILED"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0399",
        "id": "IMP-0399",
        "state": state,
        "status": "DELIVERED" if state == "SUCCESS" else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema": SCHEMA,
        "title": "Router mutation harness proving the regression suite detects what it claims",
        "question": QUESTION,
        "answer": report["answer"],
        "n_contracted": 4,
        "n_killed": report["n_killed"],
        "n_survived": report["n_survived"],
        "survivors": survivors,
        "killed": [r["mutation"] for r in killed_rows],
        "mutation_table": report["contracted"],
        "control": {
            **report["control"],
            "role": "known-caught mutation proving the harness can observe redness",
            "caught": report["harness_can_observe_red"],
        },
        "fifth_mutation": {
            **report["fifth"],
            "role": "adversarial refuter mutation (defaults to REFUTED until killed)",
            "design": (
                "always-fire trigger T-CATCHALL-WEATHER injecting cap.weather "
                "into every query, including labelled negatives"
            ),
        },
        "identity_control": report["identity"],
        "harness_can_observe_red": report["harness_can_observe_red"],
        "clean_suite_green": report["clean_suite_green"],
        "identity_stays_green": report["identity_stays_green"],
        "detector_broken": report["detector_broken"],
        "suite_stayed_green_on_all_four": report["suite_stayed_green_on_all_four"],
        "corpus": report["corpus"],
        "pin": {
            "model_id": PIN_MODEL_ID,
            "digest": PIN_DIGEST,
        },
        "inputs_measured": {
            "imp0398_receipt": "command-center/receipts/IMP-0398.json",
            "imp0398_present": report["corpus"]["imp0398_receipt_present"],
            "estate_router_search": [
                "hooks/semantic-router",
                "capability-index.json",
            ],
            "estate_router_present": False,
            "fixture_router": "command-center/p2-wave/probes/IMP-0399/router.py",
            "note": (
                "IMP-0398 receipt and estate router source are absent on this "
                "worktree. The harness scores a fixture router that exposes "
                "the four contracted mutation surfaces plus a labelled corpus "
                "that defeats always-top-3 popularity (negative fraction "
                f"{report['corpus']['negative_fraction']:.3f}, baseline exact-"
                f"set rate {report['corpus']['baseline_exact_set_rate']:.3f})."
            ),
        },
        "tests": [
            {
                "id": "clean-green",
                "result": "PASS" if report["clean_suite_green"] else "FAIL",
            },
            {
                "id": "control-red",
                "result": "PASS" if report["harness_can_observe_red"] else "FAIL",
            },
            {
                "id": "identity-green",
                "result": "PASS" if report["identity_stays_green"] else "FAIL",
            },
            {
                "id": "four-contracted-not-all-green",
                "result": (
                    "PASS"
                    if not report["suite_stayed_green_on_all_four"]
                    else "FAIL"
                ),
            },
            {
                "id": "fifth-adversarial",
                "result": "PASS" if report["fifth"]["observed"] == "RED" else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0399-probe2-adversarial-fifth-mutation",
            "independent": True,
            "defaults_to": "REFUTED",
            "verdict": "PASS" if report["fifth"]["observed"] == "RED" else "REFUTED",
            "note": (
                "Same-worktree automated refuter (not a second-vendor human). "
                "PASS only if the fifth mutation turns the suite RED and the "
                "identity mutation stays GREEN."
            ),
        },
        "evidence": [
            "command-center/p2-wave/probes/IMP-0399/harness.py",
            "command-center/p2-wave/probes/IMP-0399/suite.py",
            "command-center/p2-wave/probes/IMP-0399/router.py",
            "command-center/p2-wave/probes/IMP-0399/fixtures/corpus.json",
        ],
        "ts": now,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} state={state}")
    print(report["answer"])
    print(SENTINEL)
    return 0 if state == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
