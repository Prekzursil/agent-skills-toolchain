#!/usr/bin/env python3
"""Named probe 2: unrepairable install-tree damage fails loudly, naming the component."""

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
from plugin.payloadutil import SKILL_REL  # noqa: E402
from plugin.repair import (  # noqa: E402
    apply_corruption,
    drop_payload_member,
    load_repair_source,
    repair_install,
    seed_install,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0074-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0074-p2-") as raw:
        tmp = Path(raw)
        seeded = seed_install(tmp / "home", tmp / "blob")
        live = Path(seeded["live_root"])
        healthy = run_journeys(live)
        if not healthy["ok"]:
            return fail(f"healthy journeys failed {healthy['failed']}")
        planted = apply_corruption(live, "missing_file")
        broken = run_journeys(live)
        if "skill_read" not in broken["failed"]:
            return fail(f"missing skill did not red skill_read: {broken}")
        meta = load_repair_source(tmp / "home", "demo")
        sidecar = Path(str(meta["_sidecar_path"]))
        drop_payload_member(sidecar, SKILL_REL)
        repaired = repair_install(tmp / "home")
        if repaired["ok"]:
            return fail("repair claimed ok after sidecar member was dropped")
        if SKILL_REL not in repaired["unrepairable"]:
            return fail(f"did not name {SKILL_REL}: {repaired['unrepairable']}")
        after = run_journeys(live)
        if after["ok"] or "skill_read" not in after["failed"]:
            return fail(f"unrepairable must leave skill_read red: {after}")
        payload = {
            "probe": "probe2-unrepairable-names-component",
            "unit_id": "TST-0074",
            "ok": True,
            "component": SKILL_REL,
            "named_unrepairable": repaired["unrepairable"],
            "repair_ok": repaired["ok"],
            "loud_line": f"UNREPAIRABLE:{SKILL_REL}",
            "corruption": planted,
            "broken_failed": broken["failed"],
            "post_attempt_failed": after["failed"],
            "sidecar_present": sidecar.is_file(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(f"UNREPAIRABLE:{SKILL_REL}")
        print("SUCCESS:TST-0074-probe2 unrepairable corruption names the component")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
