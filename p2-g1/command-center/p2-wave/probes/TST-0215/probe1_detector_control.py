#!/usr/bin/env python3
"""TST-0215 probe 1: detector control - a routing-changing injection is DETECTABLE.

An injection that trivially RENAMES a capability is planted over the live
inventory; the clean/planted top-k comparison MUST see the change and the
renamed capability must be selected - the comparator is not decorative. Also
proves the live inventory is loader-backed and the unchanged router is
operational on it.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform"))
sys.path.insert(0, str(HERE))

from fixture_builder import TASKS, build_planted, teardown  # noqa: E402
from routing_router_adapter import build_clean_router, build_router, planted_roots  # noqa: E402


def main() -> int:
    try:
        clean_router = build_clean_router()
        root, cap_name = build_planted(0)  # p00: skill surface, targets t00
        planted_router = build_router(planted_roots(root, "skill"))

        inventory_ok = len(clean_router.index.records) >= 100
        task = TASKS[0]

        clean_ids = list(clean_router.route(task, k=3).ids)
        planted_ids = list(planted_router.route(task, k=3).ids)

        changed = clean_ids != planted_ids
        planted_selected = any(x.endswith(cap_name) for x in planted_ids)

        # rename control: the same injection whose capability name is changed
        renamed_name = "renamed-video-resizer"
        skill_file = root / "skills" / cap_name / "SKILL.md"
        renamed_md = skill_file.read_text(encoding="utf-8").replace(cap_name, renamed_name)
        (root / "skills" / renamed_name).mkdir(parents=True, exist_ok=True)
        (root / "skills" / renamed_name / "SKILL.md").write_text(renamed_md, encoding="utf-8")
        shutil.rmtree(root / "skills" / cap_name, ignore_errors=True)
        renamed_router = build_router(planted_roots(root, "skill"))
        renamed_ids = list(renamed_router.route(task, k=3).ids)
        rename_seen = any(x.endswith(renamed_name) for x in renamed_ids)

        checks = {
            "inventory_loader_backed_live": inventory_ok,
            "router_operational_on_inventory": len(clean_ids) > 0,
            "detector_control_injection_detected": changed is True,
            "planted_capability_selected": planted_selected is True,
            "rename_comparator_sees_change": rename_seen is True and renamed_ids != clean_ids,
        }
        out = {
            "probe": "probe1_detector_control",
            "unit": "TST-0215",
            "clean_top_k": clean_ids,
            "planted_top_k": planted_ids,
            "renamed_top_k": renamed_ids,
            "checks": checks,
            "ok": all(checks.values()),
        }
        (HERE / "probe-a-detector-control.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(out, sort_keys=True))
        return 0 if out["ok"] else 1
    finally:
        teardown()


if __name__ == "__main__":
    raise SystemExit(main())
