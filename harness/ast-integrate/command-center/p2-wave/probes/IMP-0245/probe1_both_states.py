#!/usr/bin/env python3
"""Named probe 1: both-states malicious-plugin-review.

Planted over-permissioned package and planted auto-loading agent config
must FLAG. The clean twin, including instruction-shaped README prose, must
not. Patterns are separable: auto-load fixture is class-legal on permissions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "blueprints" / "security"
sys.path.insert(0, str(LIB))

from contract import register  # noqa: E402
from malicious_plugin import review_package  # noqa: E402

PKGS = HERE / "fixtures" / "packages"


def _has_rule(result: dict, rule_id: str) -> bool:
    return any(f.get("rule_id") == rule_id for f in result.get("findings") or [])


def _paths_for_rule(result: dict, rule_id: str) -> list[str]:
    return [str(f.get("path")) for f in result.get("findings") or [] if f.get("rule_id") == rule_id]


def main() -> int:
    gated = register(LIB)
    if not gated["pass"] or len(gated["registered"]) != 4:
        print("FAILED:IMP-0245-probe1 contract", json.dumps(gated, sort_keys=True))
        return 1
    if gated["flagship"] != ["wf.malicious-plugin-review"]:
        print("FAILED:IMP-0245-probe1 flagship", gated["flagship"])
        return 1

    over = review_package(PKGS / "over-permissioned")
    auto = review_package(PKGS / "auto-load-config")
    clean = review_package(PKGS / "clean")

    if over.get("verdict") != "FLAG" or not _has_rule(over, "EXCESSIVE_PERMISSION"):
        print("FAILED:IMP-0245-probe1 over-permissioned miss", json.dumps(over, sort_keys=True)[:2000])
        return 1
    if auto.get("verdict") != "FLAG" or not _has_rule(auto, "AUTO_LOADING_AGENT_CONFIG"):
        print("FAILED:IMP-0245-probe1 autoload miss", json.dumps(auto, sort_keys=True)[:2000])
        return 1
    if _has_rule(auto, "EXCESSIVE_PERMISSION"):
        print("FAILED:IMP-0245-probe1 autoload also permission (patterns not separable)")
        return 1
    auto_paths = _paths_for_rule(auto, "AUTO_LOADING_AGENT_CONFIG")
    if not any(p.startswith(".claude/hooks/") for p in auto_paths):
        print("FAILED:IMP-0245-probe1 missing .claude/hooks", auto_paths)
        return 1
    if not any(p.startswith(".codex/hooks/") for p in auto_paths):
        print("FAILED:IMP-0245-probe1 missing .codex/hooks", auto_paths)
        return 1
    if any(p.endswith("README.md") or p.endswith("SKILL.md") for p in auto_paths):
        print("FAILED:IMP-0245-probe1 flagged imported prose", auto_paths)
        return 1
    if clean.get("verdict") != "CLEAN" or clean.get("findings"):
        print("FAILED:IMP-0245-probe1 clean false positive", json.dumps(clean, sort_keys=True)[:2000])
        return 1
    readme = (PKGS / "clean" / "README.md").read_text(encoding="utf-8")
    if ".codex/hooks" not in readme or ".claude/hooks" not in readme:
        print("FAILED:IMP-0245-probe1 clean README lost the prose control")
        return 1

    out = {
        "adjudicated": 3,
        "auto_load_flagged": True,
        "auto_load_paths": auto_paths,
        "clean_silent": True,
        "contract_registered": gated["registered"],
        "flagship": gated["flagship"],
        "over_permission_flagged": True,
        "pass": True,
        "probe": "probe1-both-states-malicious-plugin",
        "prose_not_flagged": True,
        "unit_id": "IMP-0245",
    }
    print(json.dumps(out, sort_keys=True))
    print("over flagged=True rule=EXCESSIVE_PERMISSION")
    print("autoload flagged=True rules=AUTO_LOADING_AGENT_CONFIG paths=" + ",".join(auto_paths))
    print("clean flagged=False findings=0")
    print("SUCCESS:IMP-0245-probe1 both-states planted patterns and clean control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
