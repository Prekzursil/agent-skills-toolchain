#!/usr/bin/env python3
"""IMP-0090 probe1 (signal 1): the rendered install-time surface lists
EXACTLY the declared permissions (set equality with the metadata), for
every fixture shape. Negative control: a package declaring nothing
renders the named empty line, never a blank screen. Reviewer property:
high-risk permissions are visually distinguishable (banner + markers),
not buried in a flat list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.permission_catalog import (  # noqa: E402
    EMPTY_SURFACE_LINE,
    extract_declared,
)
from marketplace.permission_surface import (  # noqa: E402
    high_risk_visually_distinct,
    render_permission_surface,
)

FIXTURES = REPO / "tools" / "marketplace" / "tests" / "fixtures"


def rendered_ids(surface: str) -> set[str]:
    ids = set()
    for line in surface.splitlines():
        if line.startswith("PERM "):
            ids.add(line.split()[1])
    return ids


def main() -> int:
    checks = {}
    per_fixture = {}

    for path in sorted(FIXTURES.glob("declared-*.json")):
        pkg = json.loads(path.read_text(encoding="utf-8"))
        surface = render_permission_surface(pkg)
        declared = set(extract_declared(pkg))
        rendered = rendered_ids(surface)
        eq = rendered == declared
        per_fixture[path.name] = {
            "declared": sorted(declared),
            "rendered": sorted(rendered),
            "set_equality": eq,
        }
        checks[f"set_equality:{path.name}"] = eq

    # named empty line for a package declaring nothing (negative control)
    none_pkg = json.loads((FIXTURES / "declared-none.json").read_text(encoding="utf-8"))
    surface = render_permission_surface(none_pkg)
    checks["negative_control_empty_named"] = (
        EMPTY_SURFACE_LINE in surface.splitlines() and surface.strip() != ""
    )

    # high-risk visually distinct, not a flat list (reviewer property)
    mixed_pkg = json.loads((FIXTURES / "declared-mixed.json").read_text(encoding="utf-8"))
    mixed_surface = render_permission_surface(mixed_pkg)
    checks["critical_banner_and_marker"] = (
        "=== CRITICAL ===" in mixed_surface
        and "RISK=critical !!!" in mixed_surface
    )
    checks["high_marker_present"] = "[HIGH]" in mixed_surface
    checks["high_risk_distinct_flag_true"] = high_risk_visually_distinct(
        mixed_surface, extract_declared(mixed_pkg)
    )
    checks["surface_is_grouped_not_flat"] = (
        mixed_surface.index("=== CRITICAL ===")
        < mixed_surface.index("network.connect")
    )

    out = {
        "probe": "probe1-rendered-equals-declared",
        "unit_id": "IMP-0090",
        "fixtures": per_fixture,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0090-probe1 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0090-probe1 rendered set equals declared set on every fixture; empty package renders its named line; high-risk visually distinct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
