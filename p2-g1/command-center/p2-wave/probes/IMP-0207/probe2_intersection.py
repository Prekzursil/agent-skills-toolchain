#!/usr/bin/env python3
"""IMP-0207 probe 2: effective permissions are the computed intersection.

Rebuilt 2026-10-26 by builder shard11 wave3 after the prior probe directory
was lost mid-flight (host session death). The probe computes the expected
intersection ITSELF from the fixture JSON with plain set algebra (independent
derivation - it never calls packs.privilege_intersection) and requires the
loader's effective binding to equal it. Also proves the check non-vacuous
(the union of the same sets is strictly larger) and exercises semver
ordering plus the workflow params surface.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.packs import load_pack  # noqa: E402
from agentspec.semver import compare_semver, parse_semver  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def main() -> int:
    fails = []
    raw = json.loads((FIX / "pack_narrow.json").read_text(encoding="utf-8"))
    wf_raw = raw["workflows"][0]
    preset_raw = raw["presets"][0]

    # independent derivation: plain set algebra over the fixture JSON
    exp_tools = sorted(set(wf_raw["tool_permissions"]) & set(preset_raw["tool_permissions"]))
    exp_sources = sorted(set(wf_raw["source_policy"]) & set(preset_raw["source_policy"]))
    union_tools = sorted(set(wf_raw["tool_permissions"]) | set(preset_raw["tool_permissions"]))
    union_sources = sorted(set(wf_raw["source_policy"]) | set(preset_raw["source_policy"]))

    pack = load_pack(FIX / "pack_narrow.json")
    if isinstance(pack, object) and hasattr(pack, "effective_for"):
        binding = pack.effective_for("wf.research", "preset.narrow")
        got_tools = sorted(binding.tool_permissions)
        got_sources = sorted(binding.source_policy)
    else:
        fails.append(f"pack did not load: {pack}")
        got_tools = got_sources = []

    tools_declared = sorted(wf_raw["tool_permissions"])
    tools_requested = sorted(preset_raw["tool_permissions"])
    print(f"tools_declared={tools_declared} tools_requested={tools_requested} "
          f"tools_intersection={exp_tools} tools_effective={got_tools} "
          f"sources_intersection={exp_sources} sources_effective={got_sources}")

    if got_tools != exp_tools:
        fails.append(f"tool binding != independent intersection: {got_tools} != {exp_tools}")
    if got_sources != exp_sources:
        fails.append(f"source binding != independent intersection: {got_sources} != {exp_sources}")
    # non-vacuity on the tools axis: declared/requested differ there, so the
    # union is strictly larger; the sources axis has equal declared/requested
    # sets, where intersection == union is the correct effective answer.
    if not len(union_tools) > len(exp_tools):
        fails.append("non-vacuity check failed: tool union not strictly larger than intersection")

    if compare_semver("1.2.0", "1.3.0") != -1 or compare_semver("1.3.0", "1.2.0") != 1 \
            or compare_semver("1.2.0", "1.2.0") != 0:
        fails.append("semver ordering wrong")
    if str(parse_semver("1.2.0")) != "1.2.0" or parse_semver("1.2") is not None:
        fails.append("semver parse wrong: strict triple required")

    wf = pack.workflow("wf.research")
    if not any(k == "topic" for k, _v in wf.params):
        fails.append(f"workflow params missing topic field: {wf.params}")

    if fails:
        print("FAILED:IMP-0207-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:IMP-0207-probe2 effective permissions are the computed intersection")
    return 0


if __name__ == "__main__":
    sys.exit(main())
