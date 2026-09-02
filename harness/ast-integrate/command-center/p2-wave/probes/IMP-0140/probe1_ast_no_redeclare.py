#!/usr/bin/env python3
"""Named probe 1: AST walk finds zero redeclarations of dispatch retry constants.

Signal (1) of IMP-0140. Production tree must be clean. The rival fixture must
be detected (both-states): detector fires on bad, silent on good.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentrail" / "tests"))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

import test_no_rival_core as rival  # noqa: E402

from agentspec.retry import (  # noqa: E402
    DISPATCH_RETRY_REASONS,
    DispatchLedger,
    REASON_RATE_LIMITED,
    REASON_WIN_ARG_LIMIT,
    plan_retry,
)


def main() -> int:
    prod = rival.scan_production()
    if not prod["ok"]:
        print("FAILED:IMP-0140-probe1 production redeclarations")
        print(json.dumps(prod, indent=2)[:3000])
        return 1
    if prod["files_walked"] < 2:
        print(f"FAILED:IMP-0140-probe1 files_walked={prod['files_walked']}")
        return 1
    required = {
        "WIN_ARG_LIMIT_RETRY_COUNT",
        "RATE_LIMITED_MAX_RETRIES",
        "RATE_LIMITED_BACKOFF_BASE_MS",
        "RATE_LIMITED_BACKOFF_CAP_MS",
        "DISPATCH_RETRY_REASONS",
        "REASON_WIN_ARG_LIMIT",
        "REASON_RATE_LIMITED",
        "plan_retry",
    }
    missing = sorted(required - set(prod["owned"]))
    if missing:
        print(f"FAILED:IMP-0140-probe1 owned missing {missing}")
        return 1

    wf = rival.module_calls_plan_retry(REPO / rival.WORKFLOW_REL)
    if wf["calls"] < 1:
        print(f"FAILED:IMP-0140-probe1 workflow_retry does not call plan_retry {wf}")
        return 1

    rival_path = HERE / "fixtures" / "rival_redeclare.py"
    owned = rival.owned_dispatch_symbols(REPO / rival.RETRY_REL)
    bad_hits = rival.find_redeclarations(rival_path, owned, owner_retry=REPO / rival.RETRY_REL)
    if len(bad_hits) < 3:
        print(f"FAILED:IMP-0140-probe1 rival not detected hits={bad_hits}")
        return 1

    rails = rival.rails_toml_files()
    if len(rails) > 1:
        print(f"FAILED:IMP-0140-probe1 second rail registry {rails}")
        return 1

    # Dispatch rail is not widened: unknown reasons do not retry.
    ledger = DispatchLedger()
    other = plan_retry("node-failed", 0, ledger)
    if other.retry:
        print("FAILED:IMP-0140-probe1 dispatch rail widened to node-failed")
        return 1
    win0 = plan_retry(REASON_WIN_ARG_LIMIT, 0, ledger)
    win1 = plan_retry(REASON_WIN_ARG_LIMIT, 1, ledger)
    rate0 = plan_retry(REASON_RATE_LIMITED, 0, ledger)
    if not win0.retry or win1.retry or not rate0.retry:
        print("FAILED:IMP-0140-probe1 dispatch plan_retry contract broken")
        return 1
    if REASON_WIN_ARG_LIMIT not in DISPATCH_RETRY_REASONS:
        print("FAILED:IMP-0140-probe1 DISPATCH_RETRY_REASONS missing win-arg-limit")
        return 1

    rival.test_no_retry_constant_redeclarations()
    rival.test_workflow_layer_calls_plan_retry()
    rival.test_no_second_rail_registry()

    out = {
        "adjudicated": 0,
        "pass": True,
        "probe": "probe1-ast-no-redeclare",
        "unit_id": "IMP-0140",
        "files_walked": prod["files_walked"],
        "owned_count": len(prod["owned"]),
        "redeclarations": 0,
        "workflow_plan_retry_calls": wf["calls"],
        "rival_hits": len(bad_hits),
        "rival_names": sorted({h["name"] for h in bad_hits}),
        "both_states": {
            "silent_on_good": len(prod["redeclarations"]) == 0,
            "fired_on_bad": len(bad_hits) >= 3,
        },
        "rails_toml": rails,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "walk files={files} redeclarations=0 rival_hits={hits} "
        "plan_retry_calls={calls} both_states_ok=True".format(
            files=prod["files_walked"],
            hits=len(bad_hits),
            calls=wf["calls"],
        )
    )
    print("SUCCESS:IMP-0140-probe1 AST zero redeclarations and rival both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
