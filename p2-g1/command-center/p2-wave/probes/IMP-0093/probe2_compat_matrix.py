#!/usr/bin/env python3
"""IMP-0093 probe2 (signal 2, independent of probe1): license
compatibility over the resolved dependency closure, cross-checked
against the published matrix file loaded directly (not through the
compatibility module's loader).

- a COMPATIBLE closure stays ok;
- an incompatible closure is reported with the EXACT offending pair
  (CDDL-1.0 x GPL-3.0-only), never averaged into a pass rate;
- a pair not covered by the published matrix is UNKNOWN-NEEDS-REVIEW,
  never assumed compatible, routed to the owner;
- the tool never asserts legal advice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace import compatibility as compat  # noqa: E402
from marketplace.license import (  # noqa: E402
    check_closure,
    resolve_with_license_gate,
)

MATRIX = REPO / "tools" / "marketplace" / "data" / "compatibility-matrix.json"


def main() -> int:
    checks = {}

    # load the published matrix DIRECTLY, independently of the module loader
    raw = json.loads(MATRIX.read_text(encoding="utf-8"))
    checks["matrix_loadable"] = len(raw.get("pairs") or {}) >= 100
    checks["uncovered_policy_declared"] = (
        raw.get("policy", {}).get("uncovered_pair_verdict") == "UNKNOWN-NEEDS-REVIEW"
    )

    # cross-check: module verdicts equal raw-file verdicts over a sweep
    sweep = [
        ("MIT", "Apache-2.0"),
        ("MIT", "GPL-2.0-only"),
        ("Apache-2.0", "GPL-2.0-only"),
        ("Apache-2.0", "GPL-3.0-only"),
        ("GPL-2.0-only", "GPL-3.0-only"),
        ("LGPL-3.0-only", "GPL-3.0-only"),
        ("LGPL-3.0-only", "GPL-2.0-only"),
        ("MPL-2.0", "GPL-3.0-only"),
        ("MPL-2.0", "GPL-2.0-only"),
        ("EPL-2.0", "GPL-3.0-only"),
        ("EPL-1.0", "GPL-2.0-only"),
        ("CDDL-1.0", "GPL-2.0-only"),
        ("AGPL-3.0-only", "GPL-2.0-only"),
    ]
    divergences = []
    for a, b in sweep:
        key = compat.pair_key(a, b)
        mod_verdict = compat.pair_compatibility(a, b)["verdict"]
        row = (raw.get("pairs") or {}).get(key)
        file_verdict = str(row.get("verdict") or "").upper() if row else "UNKNOWN-NEEDS-REVIEW"
        if mod_verdict != file_verdict:
            divergences.append({"pair": key, "module": mod_verdict, "file": file_verdict})
    checks["module_matches_published_file_per_pair"] = not divergences

    # COMPATIBLE closure stays ok
    good = check_closure(["MIT", "BSD-3-Clause", "Apache-2.0"])
    checks["compatible_closure_ok"] = good["ok"] and not good["needs_review"]

    # the exact offending pair is named, never averaged
    bad = check_closure(["MIT", "CDDL-1.0", "GPL-3.0-only"])
    offending_pairs = [v["pair"] for v in bad["offending"]]
    checks["offending_pair_exact"] = offending_pairs == ["CDDL-1.0|GPL-3.0-only"]

    # unknown pair: UNKNOWN-NEEDS-REVIEW, never compatible, routed to owner
    unk = check_closure(["MIT", "SSPL-1.0"])
    pair0 = unk["pairs"][0]
    checks["unknown_pair_never_compatible"] = (
        pair0["verdict"] == "UNKNOWN-NEEDS-REVIEW"
        and pair0["verdict"] != "COMPATIBLE"
    )
    checks["unknown_routes_to_owner"] = bool(
        unk["needs_review"]
        and unk["owner_action"]
        and "owner" in unk["owner_action"]
    )

    # resolve-time gate refuses the incompatible closure naming the pair
    resolved = resolve_with_license_gate(
        [
            {"name": "zfs", "license": "CDDL-1.0"},
            {"name": "linux", "license": "GPL-3.0-only"},
        ]
    )
    checks["resolve_gate_refuses_with_exact_pair"] = (
        not resolved["ok"]
        and [v["pair"] for v in resolved["offending"]] == ["CDDL-1.0|GPL-3.0-only"]
    )
    checks["not_legal_advice"] = "not legal advice" in resolved["legal_disclaimer"]

    out = {
        "probe": "probe2-compat-matrix",
        "unit_id": "IMP-0093",
        "matrix_rows": len(raw.get("pairs") or {}),
        "sweep_pairs": len(sweep),
        "divergences": divergences,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0093-probe2 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0093-probe2 closure verdicts match published matrix per pair; exact offending pair named; unknown routed to owner, never assumed compatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
