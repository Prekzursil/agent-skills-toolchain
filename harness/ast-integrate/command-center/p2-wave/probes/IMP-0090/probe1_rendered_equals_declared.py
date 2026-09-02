#!/usr/bin/env python3
"""Named probe 1: rendered surface set equals the declared metadata set.

Parses PERM lines from the rendered text with a local regex. Does not ask
the renderer for the id set, so a renderer that drops or invents an id fails.
Also holds the negative control: declaring nothing prints
'no permissions declared', never a blank screen.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.permission_catalog import (  # noqa: E402
    EMPTY_SURFACE_LINE,
    extract_declared,
)
from marketplace.permission_surface import (  # noqa: E402
    HEADER,
    high_risk_visually_distinct,
    render_permission_surface,
)

ART = REPO / "command-center" / "receipts" / "IMP-0090.json"
FIX = REPO / "tools" / "marketplace" / "tests" / "fixtures"
PERM_LINE = re.compile(r"^PERM\s+(\S+)\s+RISK=")


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _rendered_ids(surface: str) -> set[str]:
    return {m.group(1) for line in surface.splitlines() if (m := PERM_LINE.match(line))}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0090-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0090-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0090-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0090-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0090" not in text:
        print("FAILED:IMP-0090-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "IMP-0090":
        print(f"FAILED:IMP-0090-probe1 unit_id {doc.get('unit_id')}")
        return 1

    mixed = _load("declared-mixed.json")
    surface = render_permission_surface(mixed)
    declared = set(extract_declared(mixed))
    rendered = _rendered_ids(surface)
    if rendered != declared:
        print(f"FAILED:IMP-0090-probe1 set mismatch rendered={sorted(rendered)} declared={sorted(declared)}")
        return 1
    if not high_risk_visually_distinct(surface, extract_declared(mixed)):
        print("FAILED:IMP-0090-probe1 high-risk not visually distinct")
        return 1
    if "=== CRITICAL ===" not in surface or "!!!" not in surface:
        print("FAILED:IMP-0090-probe1 critical grouping missing")
        return 1

    empty_ok = True
    for name in ("declared-none.json", "declared-missing.json"):
        pkg = _load(name)
        empty_surface = render_permission_surface(pkg)
        if not empty_surface.strip():
            print(f"FAILED:IMP-0090-probe1 {name} blank screen")
            return 1
        if HEADER not in empty_surface or EMPTY_SURFACE_LINE not in empty_surface:
            print(f"FAILED:IMP-0090-probe1 {name} missing named empty")
            return 1
        if _rendered_ids(empty_surface):
            print(f"FAILED:IMP-0090-probe1 {name} invented PERM lines")
            return 1
        if extract_declared(pkg):
            print(f"FAILED:IMP-0090-probe1 {name} declared not empty")
            return 1

    payload = {
        "declared": sorted(declared),
        "negative_control_named_empty": empty_ok,
        "pass": True,
        "probe": "probe1-rendered-equals-declared",
        "rendered": sorted(rendered),
        "set_equal": True,
        "unit_id": "IMP-0090",
        "visually_grouped": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "rendered==declared=True grouped=True named_empty=True "
        f"n={len(declared)}"
    )
    print("SUCCESS:IMP-0090-probe1 rendered set equals declared set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
