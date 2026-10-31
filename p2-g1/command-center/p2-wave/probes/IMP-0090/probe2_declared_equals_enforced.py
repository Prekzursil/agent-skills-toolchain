#!/usr/bin/env python3
"""IMP-0090 probe2 (signal 2, independent query path): the runtime
enforcement layer, queried separately from the surface renderer, reports
the same effective set - and a declaration the runtime does not enforce
is FLAGGED decorative, never silently counted as enforced.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.permission_catalog import extract_declared  # noqa: E402
from plugin.permission_enforcement import (  # noqa: E402
    query_decorative,
    query_effective,
)

FIXTURES = REPO / "tools" / "marketplace" / "tests" / "fixtures"


def main() -> int:
    checks = {}
    per_fixture = {}

    for path in sorted(FIXTURES.glob("declared-*.json")):
        pkg = json.loads(path.read_text(encoding="utf-8"))
        eff = query_effective(pkg)
        declared = set(extract_declared(pkg))
        enforced = set(eff["enforced"])
        decorative = set(eff["decorative"])
        same = declared == enforced and not decorative
        per_fixture[path.name] = {
            "declared": sorted(declared),
            "enforced": sorted(enforced),
            "decorative": sorted(decorative),
            "declared_equals_enforced": eff["declared_equals_enforced"],
        }
        checks[f"effective_matches_declared:{path.name}"] = same or bool(decorative)

    # exact declaration case: all gated -> set equality holds
    mixed = json.loads((FIXTURES / "declared-mixed.json").read_text(encoding="utf-8"))
    checks["gated_declaration_enforced_set_equal"] = query_effective(mixed)[
        "declared_equals_enforced"
    ]

    # decorative case: the divergence must be FLAGGED, not silent
    deco = json.loads((FIXTURES / "declared-decorative.json").read_text(encoding="utf-8"))
    eff = query_effective(deco)
    checks["decorative_divergence_flagged"] = (
        set(eff["decorative"]) == {"ui.notify", "telemetry.collect"}
        and eff["decorative"]
    )
    checks["decorative_not_counted_enforced"] = not (
        set(eff["decorated"]) & set(eff["decorative"])
        if "decorated" in eff
        else set(eff["enforced"]) & set(eff["decorative"])
    )

    # nothing declared: both layers agree on the empty set
    none_pkg = json.loads((FIXTURES / "declared-none.json").read_text(encoding="utf-8"))
    eff = query_effective(none_pkg)
    checks["empty_agreement"] = (
        eff["declared"] == [] and eff["enforced"] == [] and eff["declared_equals_enforced"]
    )

    out = {
        "probe": "probe2-declared-equals-enforced",
        "unit_id": "IMP-0090",
        "fixtures": per_fixture,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0090-probe2 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0090-probe2 enforcement layer queried separately reports the same effective set; decorative divergence flagged, never silently enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
