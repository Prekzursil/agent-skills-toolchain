#!/usr/bin/env python3
"""IMP-0207 probe 1: privilege-widening preset rejected; narrowing accepted.

Rebuilt 2026-10-26 by builder shard11 wave3 after the prior probe directory
was lost mid-flight (host session death). Both states against the LIVE
loader (tools/agentspec/agentspec/packs.py:load_pack):
  * a preset requesting Write beyond the workflow ceiling is rejected with
    closed id pack-preset-tool-permission-widening (extra=['Write']);
  * a preset requesting public-tor beyond the source ceiling is rejected
    with closed id pack-preset-source-policy-widening (extra=['public-tor']);
  * a narrowing preset loads and its effective binding is the subset;
  * an EDITED narrowing preset that adds Write is rejected on reload (a
    silent intersection-clip is never a success path);
  * non-semver version "1.2" is rejected with pack-semver-invalid.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.packs import PackViolation, load_pack  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def doc_of(result):
    if isinstance(result, PackViolation):
        return None
    return result


def violation_of(result):
    return result if isinstance(result, PackViolation) else None


def main() -> int:
    fails = []
    narrow = load_pack(FIX / "pack_narrow.json")
    pack = doc_of(narrow)
    if pack is None:
        fails.append(f"narrow pack rejected: {narrow}")
        eff_tools = eff_sources = None
    else:
        binding = pack.effective_for("wf.research", "preset.narrow")
        eff_tools = sorted(binding.tool_permissions)
        eff_sources = sorted(binding.source_policy)
        if eff_tools != ["Grep", "Read"] or eff_sources != ["code", "official-docs"]:
            fails.append(f"narrow binding not the narrowing subset: {eff_tools} / {eff_sources}")

    wt = violation_of(load_pack(FIX / "pack_widen_tools.json"))
    if wt is None or wt.code != "pack-preset-tool-permission-widening" or wt.extra != ["Write"]:
        fails.append(f"widen-tools not rejected as expected: {wt}")

    src = violation_of(load_pack(FIX / "pack_widen_source.json"))
    if src is None or src.code != "pack-preset-source-policy-widening" or src.extra != ["public-tor"]:
        fails.append(f"widen-source not rejected as expected: {src}")

    # reload mutant: narrowing preset edited to add Write must reject on reload
    raw = json.loads((FIX / "pack_narrow.json").read_text(encoding="utf-8"))
    mutated = copy.deepcopy(raw)
    mutated["presets"][0]["tool_permissions"].append("Write")
    reloaded = violation_of(load_pack(mutated))
    if reloaded is None or reloaded.code != "pack-preset-tool-permission-widening":
        fails.append(f"edited narrowing preset accepted on reload: {reloaded}")

    bad_ver = copy.deepcopy(raw)
    bad_ver["version"] = "1.2"
    semv = violation_of(load_pack(bad_ver))
    if semv is None or semv.code != "pack-semver-invalid":
        fails.append(f"invalid semver not rejected: {semv}")

    print(f"narrow_ok={pack is not None} tools={eff_tools} sources={eff_sources} "
          f"widen_tools={wt.code if wt else None}:{wt.extra if wt else None} "
          f"widen_source={src.code if src else None}:{src.extra if src else None} "
          f"reload_reject={reloaded.code if reloaded else None} "
          f"semver={semv.code if semv else None}")
    if fails:
        print("FAILED:IMP-0207-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:IMP-0207-probe1 privilege-widening rejected; narrowing accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
