#!/usr/bin/env python3
"""Named probe 2: runtime enforcement query vs declared set.

Does not import marketplace.permission_surface. Queries
plugin.permission_enforcement independently. A declared id with no gated
hook is decorative and must be flagged. The gated-only fixture must match
exactly; the decorative fixture must not be reported as fully enforced.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.permission_enforcement import (  # noqa: E402
    query_decorative,
    query_effective,
    query_enforced_set,
)

ART = REPO / "command-center" / "receipts" / "IMP-0090.json"
FIX = REPO / "tools" / "marketplace" / "tests" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0090-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0090-probe2 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0090-probe2 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0090-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0090" not in text:
        print("FAILED:IMP-0090-probe2 sentinel absent")
        return 1

    gated = _load("declared-object-form.json")
    gated_eff = query_effective(gated)
    if not gated_eff["declared_equals_enforced"]:
        print(f"FAILED:IMP-0090-probe2 gated fixture mismatch {gated_eff}")
        return 1
    if gated_eff["decorative"]:
        print(f"FAILED:IMP-0090-probe2 gated fixture decorative {gated_eff['decorative']}")
        return 1
    if set(gated_eff["enforced"]) != {"filesystem.write", "network.connect"}:
        print(f"FAILED:IMP-0090-probe2 gated enforced {gated_eff['enforced']}")
        return 1

    mixed = _load("declared-mixed.json")
    mixed_eff = query_effective(mixed)
    if not mixed_eff["declared_equals_enforced"]:
        print(f"FAILED:IMP-0090-probe2 mixed mismatch {mixed_eff}")
        return 1

    deco = _load("declared-decorative.json")
    deco_enforced = set(query_enforced_set(deco))
    deco_flags = set(query_decorative(deco))
    if deco_enforced != {"filesystem.write"}:
        print(f"FAILED:IMP-0090-probe2 decorative enforced {deco_enforced}")
        return 1
    if deco_flags != {"ui.notify", "telemetry.collect"}:
        print(f"FAILED:IMP-0090-probe2 decorative flags {deco_flags}")
        return 1
    if not deco_flags:
        print("FAILED:IMP-0090-probe2 decorative declarations were not flagged")
        return 1

    empty = _load("declared-none.json")
    if query_enforced_set(empty) or query_decorative(empty):
        print("FAILED:IMP-0090-probe2 empty package not empty")
        return 1

    payload = {
        "decorative_flagged": sorted(deco_flags),
        "gated_equal": True,
        "mixed_equal": True,
        "pass": True,
        "probe": "probe2-declared-equals-enforced",
        "renderer_imported": "marketplace.permission_surface" in sys.modules,
        "unit_id": "IMP-0090",
    }
    if payload["renderer_imported"]:
        print("FAILED:IMP-0090-probe2 imported the renderer; signals are not independent")
        return 1
    print(json.dumps(payload, sort_keys=True))
    print(
        "gated_equal=True mixed_equal=True decorative_flagged="
        f"{sorted(deco_flags)} renderer_imported=False"
    )
    print("SUCCESS:IMP-0090-probe2 declared set equals enforced set; decorative flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
