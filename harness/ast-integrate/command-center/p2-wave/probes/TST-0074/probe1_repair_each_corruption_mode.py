#!/usr/bin/env python3
"""Named probe 1: each install-tree corruption is repaired, then golden journeys pass."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.journeys import run_journeys  # noqa: E402
from plugin.repair import (  # noqa: E402
    COMPONENT_FOR_MODE,
    CORRUPTION_MODES,
    RED_JOURNEY,
    apply_corruption,
    repair_install,
    seed_install,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0074-probe1 {msg}")
    return 1


def main() -> int:
    rows = []
    for mode in CORRUPTION_MODES:
        with tempfile.TemporaryDirectory(prefix=f"tst0074-p1-{mode}-") as raw:
            tmp = Path(raw)
            seeded = seed_install(tmp / "home", tmp / "blob")
            live = Path(seeded["live_root"])
            healthy = run_journeys(live)
            if not healthy["ok"]:
                return fail(f"{mode} healthy journeys failed {healthy['failed']}")
            planted = apply_corruption(live, mode)
            broken = run_journeys(live)
            red = RED_JOURNEY[mode]
            if red not in broken["failed"]:
                return fail(f"{mode} did not red {red}: {broken}")
            repaired = repair_install(tmp / "home")
            if not repaired["ok"]:
                return fail(f"{mode} repair not ok {repaired}")
            restored_paths = [r["path"] for r in repaired["restored"]]
            if COMPONENT_FOR_MODE[mode] not in restored_paths:
                return fail(f"{mode} did not restore {COMPONENT_FOR_MODE[mode]}: {restored_paths}")
            after = run_journeys(live)
            if not after["ok"]:
                return fail(f"{mode} post-repair journeys failed {after['failed']}")
            rows.append(
                {
                    "mode": mode,
                    "component": planted["component"],
                    "corruption": planted,
                    "healthy_ok": healthy["ok"],
                    "broken_failed": broken["failed"],
                    "red_journey": red,
                    "repair_ok": repaired["ok"],
                    "repair_exit_is_not_evidence": True,
                    "restored": restored_paths,
                    "post_repair_journeys_ok": after["ok"],
                    "post_repair_failed": after["failed"],
                    "post_repair_journey_details": {
                        k: {"ok": v["ok"], "detail": v.get("detail")}
                        for k, v in after["journeys"].items()
                    },
                }
            )
    payload = {
        "probe": "probe1-repair-each-corruption-mode",
        "unit_id": "TST-0074",
        "ok": True,
        "modes": [r["mode"] for r in rows],
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:TST-0074-probe1 each corruption mode repaired; golden journeys pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
