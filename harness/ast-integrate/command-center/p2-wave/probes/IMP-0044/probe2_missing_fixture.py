#!/usr/bin/env python3
"""Probe 2: missing broken-fixture is UNTRUSTWORTHY, not skipped.

Also runs a reviewer-designed always-OK probe (returns PASS, ignores fixtures)
and requires the harness to catch it.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from both_states_harness import (  # noqa: E402
    UNTRUSTWORTHY,
    ProbeSpec,
    bundled_fixtures,
    evaluate,
    missing_broken_control,
    reviewer_always_pass_probe,
)

ART = REPO / "command-center" / "receipts" / "IMP-0044.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0044-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0044" not in text:
        print("FAILED:IMP-0044-probe2 sentinel absent")
        return 1

    missing = missing_broken_control()
    broken, good = bundled_fixtures()
    reviewer = evaluate(
        ProbeSpec(
            probe_id="reviewer-always-pass",
            run=reviewer_always_pass_probe,
            known_broken=broken,
            known_good=good,
            description="reviewer-added always-OK probe of independent design",
        )
    )
    with tempfile.TemporaryDirectory(prefix="imp0044-p2-") as raw:
        tmp = Path(raw)
        ghost = tmp / "ghost-broken.fixture"
        local_good = tmp / "good.txt"
        local_good.write_text("healthy\n", encoding="utf-8")
        local_missing = evaluate(
            ProbeSpec(
                probe_id="local-missing-broken",
                run=lambda _p: "OK",
                known_broken=ghost,
                known_good=local_good,
            )
        )

    ok = (
        missing.trust == UNTRUSTWORTHY
        and missing.skipped is False
        and missing.reason == "missing-broken-fixture"
        and missing.broken_fixture_present is False
        and local_missing.trust == UNTRUSTWORTHY
        and local_missing.skipped is False
        and reviewer.trust == UNTRUSTWORTHY
        and reviewer.skipped is False
        and reviewer.reason == "same-verdict-both-states"
    )
    payload = {
        "probe": "probe2-missing-fixture",
        "unit_id": "IMP-0044",
        "missing_trust": missing.trust,
        "missing_skipped": missing.skipped,
        "missing_reason": missing.reason,
        "local_missing_trust": local_missing.trust,
        "local_missing_skipped": local_missing.skipped,
        "reviewer_trust": reviewer.trust,
        "reviewer_reason": reviewer.reason,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"missing_skipped={missing.skipped} missing_trust={missing.trust} "
        f"reviewer={reviewer.trust}"
    )
    if not ok:
        print("FAILED:IMP-0044-probe2 missing-fixture / reviewer always-ok")
        return 1
    print("SUCCESS:IMP-0044-probe2 missing broken-fixture UNTRUSTWORTHY not skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
