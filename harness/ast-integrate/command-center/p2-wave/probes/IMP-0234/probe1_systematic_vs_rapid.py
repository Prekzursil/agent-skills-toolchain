#!/usr/bin/env python3
"""Named probe 1: systematic vs rapid declared-parameter diff and fingerprints.

Signal 1 of IMP-0234: computed parameter diff is non-empty AND fingerprints
differ. A prose-only twin keeps the fingerprint (rename/prose invariance).
Also runs flagship deep-research e2e (real artifact, min size, parse).
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
        return S.fail("probe1 receipt absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0234":
        return S.fail(f"probe1 unit_id {doc.get('unit_id')}")
    if "SUCCESS:IMP-0234" not in ART.read_text(encoding="utf-8"):
        return S.fail("probe1 sentinel absent")

    b = S.live_bundle()
    if not b["registration"]["ok"]:
        return S.fail(f"probe1 register {b['registration']['failed']}")
    if set(b["library_ids"]) != {
        "deep-research",
        "gem-hunt",
        "systematic-literature-review",
        "rapid-literature-review",
    }:
        return S.fail(f"probe1 library ids {b['library_ids']}")
    if not b["parameter_diff_nonempty"]:
        return S.fail("probe1 systematic vs rapid parameter_diff empty (one blueprint, two names)")
    if not b["fingerprints_differ"]:
        return S.fail("probe1 systematic and rapid fingerprints collide")
    if not b["rename_invariant"]:
        return S.fail("probe1 fingerprint changed under identifier rename")
    if not b["prose_twin_same_fp"]:
        return S.fail("probe1 prose-only twin changed fingerprint (structure leaked identifiers)")
    if not b["param_fork_differs"]:
        return S.fail("probe1 source_quota fork did not change fingerprint (parameter not load-bearing)")
    if not b["omission_codes_distinct"]:
        return S.fail(f"probe1 omission codes not 6 distinct {b['omissions']}")
    e2e = b["flagship_e2e"]["deep-research"]
    if not e2e["pass"]:
        return S.fail(f"probe1 deep-research flagship e2e {e2e}")

    live_sys = b["systematic_fp"]
    live_rap = b["rapid_fp"]
    claimed = ((doc.get("evidence_measurements") or {}).get("fingerprints") or {})
    if claimed.get("systematic-literature-review") and claimed["systematic-literature-review"] != live_sys:
        return S.fail("probe1 receipt systematic fingerprint disagrees with live recompute")
    if claimed.get("rapid-literature-review") and claimed["rapid-literature-review"] != live_rap:
        return S.fail("probe1 receipt rapid fingerprint disagrees with live recompute")

    payload = {
        "probe": "probe1-systematic-vs-rapid",
        "unit_id": "IMP-0234",
        "pass": True,
        "parameter_diff": b["parameter_diff"],
        "systematic_fp": live_sys,
        "rapid_fp": live_rap,
        "fingerprints_differ": True,
        "rename_invariant": True,
        "prose_twin_same_fp": True,
        "param_fork_differs": True,
        "omission_codes_distinct": True,
        "deep_research_e2e_bytes": e2e["bytes"],
        "sys_params": b["sys_params"],
        "rap_params": b["rap_params"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "diff_keys="
        + ",".join(sorted(b["parameter_diff"]))
        + f" sys_fp={live_sys[:12]} rap_fp={live_rap[:12]} e2e_bytes={e2e['bytes']}"
    )
    print("SUCCESS:IMP-0234-probe1 systematic vs rapid parameter diff and fingerprints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
