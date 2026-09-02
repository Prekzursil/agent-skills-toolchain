#!/usr/bin/env python3
"""Probe 1: named intersection of projected path sets (IMP-0126 signal 1).

Independent of the sequential-install census. Computes the casefold-key
intersection of two packages' IMP-0010 projections, requires it non-empty,
and requires both claimants named. Confirms the detector imports the
IMP-0022 `casefold_key` function object rather than a second rule.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.fixtures import PKG_ALPHA, PKG_BETA_CASEFOLD, PKG_GAMMA_DISJOINT  # noqa: E402
from marketplace.index_lint import lint_index  # noqa: E402
from marketplace.path_conflict import casefold_key, named_intersection  # noqa: E402
from plugin import casefold_paths as imp0022  # noqa: E402
from plugin.projection_map import project_payload  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0126.json"
PC_SRC = REPO / "tools/marketplace/path_conflict.py"
CF_SRC = REPO / "tools/plugin/casefold_paths.py"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0126-probe1 {msg}")
    return 1


def _imports_imp0022(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "plugin.casefold_paths":
            names = {alias.name for alias in node.names}
            if "casefold_key" in names:
                return True
    return False


def _casefold_key_uses_nfc_and_casefold(src: str) -> bool:
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "casefold_key":
            fn = node
            break
    if fn is None:
        return False
    uses_nfc = False
    uses_casefold = False
    uses_lower = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "nfc":
                uses_nfc = True
        if isinstance(node, ast.Attribute):
            if node.attr == "casefold":
                uses_casefold = True
            if node.attr == "lower":
                uses_lower = True
    return uses_nfc and uses_casefold and not uses_lower


def main() -> int:
    if casefold_key is not imp0022.casefold_key:
        return _fail("marketplace.casefold_key is not IMP-0022 function object")
    pc_text = PC_SRC.read_text(encoding="utf-8")
    cf_text = CF_SRC.read_text(encoding="utf-8")
    if not _imports_imp0022(pc_text):
        return _fail("path_conflict.py does not import plugin.casefold_paths.casefold_key")
    if not _casefold_key_uses_nfc_and_casefold(cf_text):
        return _fail("IMP-0022 casefold_key is not NFC-then-casefold")
    pc_tree = ast.parse(pc_text)
    for node in ast.walk(pc_tree):
        if isinstance(node, ast.Attribute) and node.attr == "lower":
            return _fail("path_conflict.py calls .lower — second comparison rule")

    map_a = project_payload(PKG_ALPHA["id"], PKG_ALPHA["payload"])
    map_b = project_payload(PKG_BETA_CASEFOLD["id"], PKG_BETA_CASEFOLD["payload"])
    map_c = project_payload(PKG_GAMMA_DISJOINT["id"], PKG_GAMMA_DISJOINT["payload"])
    keys, conflicts = named_intersection(map_a, map_b)
    if not keys:
        return _fail("projected casefold intersection is empty")
    if not conflicts:
        return _fail("intersection non-empty but claimants not named")
    named = {n for c in conflicts for n in c.named_packages()}
    if named != {PKG_ALPHA["id"], PKG_BETA_CASEFOLD["id"]}:
        return _fail(f"claimants named={named}")
    for conflict in conflicts:
        msg = conflict.refuse_message()
        if PKG_ALPHA["id"] not in msg or PKG_BETA_CASEFOLD["id"] not in msg:
            return _fail(f"refuse message missing a claimant: {msg}")
        print(f"conflict key={conflict.casefold_key!r} named={conflict.named_packages()}")
        print(f"  {msg}")

    disjoint_keys, disjoint_conflicts = named_intersection(map_a, map_c)
    if disjoint_keys or disjoint_conflicts:
        return _fail("negative control: disjoint pair produced an intersection")

    dirty = {
        "packages": [
            {"id": PKG_ALPHA["id"], "payload_paths": list(PKG_ALPHA["payload"])},
            {
                "id": PKG_BETA_CASEFOLD["id"],
                "payload_paths": list(PKG_BETA_CASEFOLD["payload"]),
            },
        ]
    }
    lint_hits = lint_index(dirty)
    lint_named = {n for c in lint_hits for n in c.named_packages()}
    if lint_named != {PKG_ALPHA["id"], PKG_BETA_CASEFOLD["id"]}:
        return _fail(f"index-lint claimants={lint_named}")

    eszett_a = ".claude/skills/straße.md"
    eszett_b = ".claude/skills/STRASSE.md"
    if eszett_a.lower() == eszett_b.lower():
        return _fail("control broken: lower() already collides ß/SS")
    if imp0022.casefold_key(eszett_a) != imp0022.casefold_key(eszett_b):
        return _fail("casefold missed ß/SS collision (would be a lower() rule)")
    composed = ".claude/skills/café.md"
    decomposed = ".claude/skills/cafe\u0301.md"
    if imp0022.casefold_key(composed) != imp0022.casefold_key(decomposed):
        return _fail("NFC not applied before casefold")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0126" not in blob:
        return _fail("sentinel absent from receipt")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if PKG_ALPHA["id"] not in blob or PKG_BETA_CASEFOLD["id"] not in blob:
        return _fail("receipt does not name both claimants")

    print(
        json.dumps(
            {
                "probe": "probe1-intersection-named",
                "unit_id": "IMP-0126",
                "intersection_keys": sorted(keys),
                "named_packages": sorted(named),
                "conflicts": len(conflicts),
                "index_lint_hits": len(lint_hits),
                "disjoint_negative_control": True,
                "imp0022_identity": True,
                "nfc_then_casefold": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0126-probe1 named projection intersection and IMP-0022 identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
