#!/usr/bin/env python3
"""Probe 1: declared capability is REACHABLE, not merely present as a file.

Both-states, two measured classes:
  * skill exists in repo but not in live directory → UNREACHABLE alarm fires;
    same skill on the loaded fixture is silent (inventory + canary).
  * plugin installed but hooks unloaded → hook NOT-FIRED; loaded fixture fires.

Observables are tool-inventory-entry and process-visible canaries, never
Path.is_file on the declaration.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import observables as O  # noqa: E402
import runtime as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A1/TEST-PLAN.json"


def main() -> int:
    run = S.run_scenario()
    print(
        json.dumps(
            {
                "silent_on_loaded": run.get("silent_on_loaded"),
                "skill_class_fires_on_unloaded": run.get("skill_class_fires_on_unloaded"),
                "hooks_class_fires_on_unloaded": run.get("hooks_class_fires_on_unloaded"),
                "anti_tautology": run.get("anti_tautology"),
                "loaded_inventory": (run.get("loaded") or {}).get("tool_inventory"),
                "loaded_hooks": (run.get("loaded") or {}).get("hook_inventory"),
                "skill_bad_inventory": (run.get("skill_repo_not_live") or {}).get("tool_inventory"),
                "hooks_bad_inventory": (run.get("hooks_unloaded") or {}).get("hook_inventory"),
                "skill_bad_repo_exists": (run.get("skill_repo_not_live") or {}).get("repo_skill_exists"),
                "skill_bad_live_exists": (run.get("skill_repo_not_live") or {}).get("live_skill_exists"),
                "hooks_plugin_installed": (run.get("hooks_unloaded") or {}).get("plugin_installed"),
                "hooks_plugin_hooks_enabled": (run.get("hooks_unloaded") or {}).get("plugin_hooks_enabled"),
            },
            sort_keys=True,
        )
    )
    if not run.get("pass"):
        print("FAILED:ARC-0008-probe1 scenario did not prove both-states reachability")
        return 1
    skill_bad = run["skill_repo_not_live"]
    if skill_bad["file_existence_would_pass_skill"] and skill_bad["skill_reachable"]:
        print("FAILED:ARC-0008-probe1 skill class collapsed to file existence")
        return 1
    hooks_bad = run["hooks_unloaded"]
    if hooks_bad["file_existence_would_pass_hook"] and hooks_bad["hook_fired"]:
        print("FAILED:ARC-0008-probe1 hooks class collapsed to file existence")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0008-probe1 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0008-probe1 self-declared {doc.get('state')}")
        return 1
    ok, why = O.check_tests(doc)
    print(f"plan_tests_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0008-probe1 TEST-PLAN tests/observables/both-states")
        return 1
    rec = doc.get("measured_classes") or {}
    if rec.get("skill_repo_not_live", {}).get("fired_on_unloaded") is not True:
        print("FAILED:ARC-0008-probe1 plan did not record skill-class both-states")
        return 1
    if rec.get("hooks_unloaded", {}).get("fired_on_unloaded") is not True:
        print("FAILED:ARC-0008-probe1 plan did not record hooks-class both-states")
        return 1
    loaded = run["loaded"]
    if not any("DISPATCH skill.council FIRED" in ln for ln in (loaded.get("log_lines") or [])):
        print("FAILED:ARC-0008-probe1 missing loader-log dispatch line")
        return 1
    if not R.canary_fired(loaded["skill"]["canary"]):
        print("FAILED:ARC-0008-probe1 loaded canary missing")
        return 1
    print(
        f"fired_on_unloaded_skill={run['skill_class_fires_on_unloaded']} "
        f"fired_on_unloaded_hooks={run['hooks_class_fires_on_unloaded']} "
        f"silent_on_loaded={run['silent_on_loaded']} "
        f"anti_tautology={run['anti_tautology']}"
    )
    print("SUCCESS:ARC-0008-probe1 reachability both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
