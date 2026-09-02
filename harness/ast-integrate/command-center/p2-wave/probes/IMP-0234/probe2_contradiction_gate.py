#!/usr/bin/env python3
"""Named probe 2: all-favorable evidence set fires the contradiction-search gate.

Both-states: all-favorable corpus -> fired; mixed corpus with search -> silent.
Planted drop of negative evidence is a second broken state (ledger + gate).
Also runs flagship gem-hunt e2e (real artifact, min size, parse).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / S.RECEIPT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return S.fail("probe2 receipt absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0234":
        return S.fail(f"probe2 unit_id {doc.get('unit_id')}")
    if "SUCCESS:IMP-0234" not in ART.read_text(encoding="utf-8"):
        return S.fail("probe2 sentinel absent")

    b = S.live_bundle()
    bad = b["gate_all_favorable"]
    good = b["gate_mixed"]
    skip = b["gate_skip_mixed"]
    drop = b["drop_negative"]
    if not bad.get("fired"):
        return S.fail(f"probe2 all-favorable did not fire gate {bad}")
    if bad.get("code") != "missing_contradiction_search":
        return S.fail(f"probe2 all-favorable code {bad.get('code')}")
    if good.get("fired"):
        return S.fail(f"probe2 mixed corpus fired gate (good state not silent) {good}")
    if not skip.get("fired"):
        return S.fail(f"probe2 skip-search on mixed did not fire {skip}")
    if not drop["gate"].get("fired"):
        return S.fail(f"probe2 drop-negative did not fire gate {drop['gate']}")
    if not drop["ledger"].get("dropped_negative_ids"):
        return S.fail("probe2 drop-negative ledger empty (detector silent on planted drop)")
    if drop["ledger"].get("empty_ledger_proven"):
        return S.fail("probe2 drop-negative proved empty ledger (false green)")
    e2e = b["flagship_e2e"]["gem-hunt"]
    if not e2e["pass"]:
        return S.fail(f"probe2 gem-hunt flagship e2e {e2e}")
    # All four blueprints must retain negatives on the mixed corpus.
    for bp_id, row in b["flagship_e2e"].items():
        if not row["negative_retained"]:
            return S.fail(f"probe2 {bp_id} dropped negatives")

    payload = {
        "probe": "probe2-contradiction-gate",
        "unit_id": "IMP-0234",
        "pass": True,
        "all_favorable_fired": True,
        "all_favorable_code": bad["code"],
        "mixed_silent": True,
        "skip_search_fired": True,
        "drop_negative_fired": True,
        "dropped_negative_ids": drop["ledger"]["dropped_negative_ids"],
        "gem_hunt_e2e_bytes": e2e["bytes"],
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"bad={bad['code']} good={good['code']} skip={skip['code']} "
        f"dropped={drop['ledger']['dropped_negative_ids']} e2e_bytes={e2e['bytes']}"
    )
    print("SUCCESS:IMP-0234-probe2 contradiction-search gate both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
