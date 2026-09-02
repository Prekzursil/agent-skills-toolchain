#!/usr/bin/env python3
"""Probe 2: corpus blast-radius of settled records already missing source_probe.

Mechanically different from probe 1. Does not rebuild ADV claim records.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import census  # noqa: E402

COMPLETE = HERE / "fixtures" / "complete_claim.json"


def main() -> int:
    live = census(REPO)
    complete = json.loads(COMPLETE.read_text(encoding="utf-8"))
    sys.path.insert(0, str(REPO / "tools" / "command-center"))
    import claim_gate as cg  # noqa: E402

    # Directionality control: a complete fixture is NOT counted as missing-source.
    complete_row_ok = (
        cg.check_claim(complete)["ok"] is True
        and bool(complete.get("source_probe"))
        and bool(complete.get("verifier_probe"))
    )
    # Walker must actually look at claim-shaped records (not a constant zero).
    walker_live = live["settled_claim_shaped"] >= 1
    payload = {
        "pass": bool(complete_row_ok and walker_live),
        "probe": "probe2-corpus-audit-missing-source",
        "unit_id": "ADV-0113",
        "census": live,
        "complete_fixture_has_both_probes": complete_row_ok,
        "universal_lineage_holds": live["every_settled_has_source"],
        "did_not_rewrite_corpus": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0113-probe2 corpus audit")
        return 1
    print(
        "SUCCESS:ADV-0113-probe2 corpus census "
        f"settled={live['settled_claim_shaped']} "
        f"missing_source={live['settled_missing_source']} "
        f"canonical_present={live['canonical_present']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
