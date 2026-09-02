#!/usr/bin/env python3
"""Probe 2: effective permissions are the computed intersection, asserted directly.

The expected set is computed here with set algebra on the fixture lists, not
by reading a label the loader printed. Union of the same sets must differ
from intersection so the check is non-vacuous.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.packs import LoadedPack, PackViolation, load_pack  # noqa: E402
from agentspec.semver import compare_semver, parse_semver  # noqa: E402
from scenario import (  # noqa: E402
    NARROW_SOURCES,
    NARROW_TOOLS,
    PRESET_NARROW,
    WF_ID,
    WORKFLOW_SOURCES,
    WORKFLOW_TOOLS,
    pack_narrow,
)

OUT = HERE / "probe2-intersection.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0207-probe2 {msg}")
    return 1


def main() -> int:
    loaded = load_pack(pack_narrow())
    if isinstance(loaded, PackViolation) or not isinstance(loaded, LoadedPack):
        return fail(f"narrow pack failed to load: {loaded}")

    workflow = loaded.workflow(WF_ID)
    preset = loaded.preset(PRESET_NARROW)
    requested_tools = preset.requested_tool_permissions
    requested_sources = preset.requested_source_policy
    if requested_tools is None or requested_sources is None:
        return fail("narrowing preset did not declare both axes")

    expected_tools = WORKFLOW_TOOLS & NARROW_TOOLS
    expected_sources = WORKFLOW_SOURCES & NARROW_SOURCES
    union_tools = WORKFLOW_TOOLS | NARROW_TOOLS
    union_sources = WORKFLOW_SOURCES | NARROW_SOURCES

    if expected_tools != NARROW_TOOLS:
        return fail("fixture NARROW_TOOLS is not a subset of WORKFLOW_TOOLS")
    if expected_tools == WORKFLOW_TOOLS:
        return fail("fixture does not actually narrow tools (vacuous intersection)")
    if expected_tools == union_tools:
        return fail("tool union equals intersection; cannot distinguish clip from keep")
    if expected_sources == WORKFLOW_SOURCES:
        return fail("fixture does not actually narrow sources")
    if expected_sources == union_sources:
        return fail("source union equals intersection")

    independent_tools = frozenset(workflow.tool_permissions) & frozenset(requested_tools)
    independent_sources = frozenset(workflow.source_policy) & frozenset(requested_sources)
    if independent_tools != expected_tools:
        return fail(f"independent tool intersection {sorted(independent_tools)}")
    if independent_sources != expected_sources:
        return fail(f"independent source intersection {sorted(independent_sources)}")

    binding = loaded.effective_for(WF_ID, PRESET_NARROW)
    if binding.tool_permissions != independent_tools:
        return fail(
            f"loader tools {sorted(binding.tool_permissions)} != "
            f"intersection {sorted(independent_tools)}"
        )
    if binding.source_policy != independent_sources:
        return fail(
            f"loader sources {sorted(binding.source_policy)} != "
            f"intersection {sorted(independent_sources)}"
        )
    if binding.tool_permissions != frozenset({"Read", "Grep"}):
        return fail(f"member assertion failed: {sorted(binding.tool_permissions)}")
    if binding.source_policy != frozenset({"official-docs", "code"}):
        return fail(f"source member assertion failed: {sorted(binding.source_policy)}")

    v120 = parse_semver("1.2.0")
    v130 = parse_semver("1.3.0")
    if v120 is None or v130 is None or compare_semver(v120, v130) >= 0:
        return fail("semver 1.2.0 must compare older than 1.3.0")
    if compare_semver(loaded.version, v120) != 0:
        return fail("loaded pack version is not 1.2.0")

    topic_keys = {k for k, _ in workflow.params} if workflow.params and isinstance(workflow.params[0], tuple) else set()
    if "topic" not in topic_keys and ("topic",) not in [(p if isinstance(p, str) else None) for p in workflow.params]:
        param_ok = any(
            (isinstance(p, tuple) and p and p[0] == "topic") or p == "topic"
            for p in workflow.params
        )
        if not param_ok:
            return fail(f"IMP-0133 params not carried: {workflow.params!r}")

    doc = {
        "pass": True,
        "probe": "probe2-intersection",
        "unit_id": "IMP-0207",
        "declared_tools": sorted(workflow.tool_permissions),
        "requested_tools": sorted(requested_tools),
        "independent_intersection_tools": sorted(independent_tools),
        "loader_effective_tools": sorted(binding.tool_permissions),
        "union_tools": sorted(union_tools),
        "declared_sources": sorted(workflow.source_policy),
        "requested_sources": sorted(requested_sources),
        "independent_intersection_sources": sorted(independent_sources),
        "loader_effective_sources": sorted(binding.source_policy),
        "union_sources": sorted(union_sources),
        "vacuous": False,
        "semver_order_1_2_0_lt_1_3_0": True,
        "params_carried": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"tools_declared={sorted(workflow.tool_permissions)} "
        f"tools_requested={sorted(requested_tools)} "
        f"tools_intersection={sorted(independent_tools)} "
        f"tools_effective={sorted(binding.tool_permissions)} "
        f"sources_intersection={sorted(independent_sources)} "
        f"sources_effective={sorted(binding.source_policy)}"
    )
    print("SUCCESS:IMP-0207-probe2 effective permissions are the computed intersection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
