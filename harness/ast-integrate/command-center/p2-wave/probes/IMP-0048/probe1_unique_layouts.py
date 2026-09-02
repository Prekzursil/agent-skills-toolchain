#!/usr/bin/env python3
"""Probe 1: one unique match per historical layout, two signals each."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.layout_fingerprints import (  # noqa: E402
    FINGERPRINT_IDS,
    STATUS_UNIQUE,
    classify,
    inspect,
)
from plugin.layout_fixtures import HISTORICAL_BUILDERS, materialize_all  # noqa: E402

FIX = HERE / "fixtures"


def main() -> int:
    trees = materialize_all(FIX)
    rows = []
    for fp_id, builder in HISTORICAL_BUILDERS.items():
        name = {
            "pre-marketplace-copied-skills": "copied-skills",
            "per-project-mcp-json": "mcp-json",
            "root-scoped-disabledMcpServers": "root-disabled",
            "pre-dispatch-hooks": "pre-dispatch",
        }[fp_id]
        root = trees[name]
        result = classify(root)
        ev = {e.fingerprint_id: e for e in inspect(root)}[fp_id]
        ok = (
            result["status"] == STATUS_UNIQUE
            and result["selected"] == fp_id
            and result["match_ids"] == [fp_id]
            and ev.marker.present
            and ev.discriminator.present
            and ev.marker.kind == "marker-file"
            and ev.discriminator.kind in {"key-location", "directory-shape"}
            and bool(result["step_chain"])
        )
        rec = {
            "fingerprint_id": fp_id,
            "ok": ok,
            "status": result["status"],
            "selected": result["selected"],
            "step_chain": result["step_chain"],
            "marker": ev.marker.to_dict(),
            "discriminator": ev.discriminator.to_dict(),
            "estate": str(root.relative_to(REPO)),
        }
        rows.append(rec)
        print(
            f"layout {fp_id} ok={ok} status={result['status']} "
            f"marker={ev.marker.present} discriminator={ev.discriminator.present}"
        )
        if not ok:
            print(json.dumps(rec, indent=2)[:2000])
            print("FAILED:IMP-0048-probe1 unique-layout")
            return 1

    marker_only = [
        ("marker-only-skills", "pre-marketplace-copied-skills"),
        ("marker-only-mcp", "per-project-mcp-json"),
        ("marker-only-claude-json", "root-scoped-disabledMcpServers"),
        ("marker-only-hooks", "pre-dispatch-hooks"),
        ("home-mcp-wrong-file", "per-project-mcp-json"),
    ]
    for name, fp_id in marker_only:
        result = classify(trees[name])
        ev = {e.fingerprint_id: e for e in inspect(trees[name])}[fp_id]
        if result["selected"] == fp_id or fp_id in result["match_ids"]:
            print(f"FAILED:IMP-0048-probe1 marker-only fired {name} {fp_id}")
            print(json.dumps(result, indent=2)[:2000])
            return 1
        if name != "home-mcp-wrong-file" and not ev.marker.present:
            print(f"FAILED:IMP-0048-probe1 expected marker on {name}")
            return 1
        if ev.matched:
            print(f"FAILED:IMP-0048-probe1 matched on single signal {name}")
            return 1
        print(
            f"marker-only {name} fp={fp_id} marker={ev.marker.present} "
            f"discriminator={ev.discriminator.present} matched=False"
        )

    if set(FINGERPRINT_IDS) != set(HISTORICAL_BUILDERS):
        print("FAILED:IMP-0048-probe1 fingerprint catalog drift")
        return 1

    out = {
        "probe": "probe1-unique-layouts",
        "unit_id": "IMP-0048",
        "historical": rows,
        "layouts_checked": len(rows),
        "marker_only_refused": len(marker_only),
        "two_signals_required": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0048-probe1 unique layouts and two-signal requirement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
