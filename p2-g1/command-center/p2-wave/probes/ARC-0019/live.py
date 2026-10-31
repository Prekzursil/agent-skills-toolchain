"""Live-tree registry-versus-deployed measurement for ARC-0019.

Pairing: ARC-0010 typed registry (the only package index on this tree)
versus command-center/control-plane/A3/installed/ (the A3 install root).
A3 DESIGN.json is absent; that absence is disclosed, not filled by
rebuilding ARC-0017.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reconcile import load_registry, reconcile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY_REL = "command-center/p2-wave/probes/ARC-0010/registry.json"
INSTALL_REL = "command-center/control-plane/A3/installed"
DESIGN_REL = "command-center/phase3/A3/DESIGN.json"
OWNER_REL = "command-center/OWNER-DECISIONS.md"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def live_report(repo: Path = REPO) -> dict[str, Any]:
    reg_path = repo / REGISTRY_REL
    registry = load_registry(reg_path)
    result = reconcile(
        registry, repo / INSTALL_REL, registry_path=REGISTRY_REL
    )
    result["pairing"] = "a3-registry-vs-installed"
    result["design_path"] = DESIGN_REL
    result["design_present"] = (repo / DESIGN_REL).is_file()
    result["owner_decisions_path"] = OWNER_REL
    result["owner_decisions_present"] = (repo / OWNER_REL).is_file()
    result["pr_only_binding_record"] = CATALOG_REL
    result["pr_only_binding_present"] = (repo / CATALOG_REL).is_file()
    fails: list[str] = []
    if result["direction_a_fail"]:
        fails.append("registry_not_deployed")
    if result["direction_b_fail"]:
        fails.append("deployed_not_in_registry")
    if result["hash_fail"]:
        fails.append("hash_mismatch")
    result["fails_today"] = fails
    return result


if __name__ == "__main__":
    print(json.dumps(live_report(), indent=2, sort_keys=True))
