#!/usr/bin/env python3
"""Probe 2: hand-edit a generated artifact; detector reports TAMPERED, not drift."""
from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generator as G  # noqa: E402

SKILL_REL = "skills/skill.council/SKILL.md"
PLUGIN_REL = "plugin.json"


def main() -> int:
    registry = G.load_default_registry()
    files = G.generate(registry)
    with tempfile.TemporaryDirectory(prefix="arc0010-") as tmp:
        root = Path(tmp)
        G.write_tree(files, root)
        rows = G.classify_tree(root, registry)
        if any(r["status"] != "CLEAN" for r in rows):
            print(f"FAILED:ARC-0010-probe2 baseline not CLEAN {rows}")
            return 1
        skill = root / SKILL_REL
        sibling = root / PLUGIN_REL
        if not skill.is_file() or not sibling.is_file():
            print("FAILED:ARC-0010-probe2 expected generated files missing")
            return 1
        skill.write_bytes(skill.read_bytes() + b"\nHAND-EDIT TAMPER\n")
        rows = {r["path"]: r for r in G.classify_tree(root, registry)}
        tampered = rows[SKILL_REL]
        plugin = rows[PLUGIN_REL]
        print(
            f"hand_edit status={tampered['status']} reason={tampered.get('reason')} "
            f"sibling={plugin['status']}"
        )
        if tampered["status"] != "TAMPERED":
            print("FAILED:ARC-0010-probe2 expected TAMPERED, not legitimate drift")
            return 1
        if plugin["status"] != "CLEAN":
            print("FAILED:ARC-0010-probe2 good sibling was not silent")
            return 1
        mutated = copy.deepcopy(registry)
        for entry in mutated["entries"]:
            if entry["id"] == "skill.council":
                entry["instructions"] = entry["instructions"] + " registry-changed"
        stale_rows = {r["path"]: r for r in G.classify_tree(root, mutated)}
        stale = stale_rows[SKILL_REL]
        print(f"registry_change status={stale['status']} reason={stale.get('reason')}")
        if stale["status"] != "STALE":
            print("FAILED:ARC-0010-probe2 registry change must be STALE, not TAMPERED")
            return 1
        G.write_tree(G.generate(registry), root)
        restored = {r["path"]: r["status"] for r in G.classify_tree(root, registry)}
        print(f"restored statuses={sorted(set(restored.values()))}")
        if set(restored.values()) != {"CLEAN"}:
            print("FAILED:ARC-0010-probe2 regenerate did not reverse the hand-edit")
            return 1
    print(
        "fired_on_bad=True silent_on_good=True "
        "tampered_not_drift=True restore_reverses=True"
    )
    print("SUCCESS:ARC-0010-probe2 negative control reports tampered not drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
