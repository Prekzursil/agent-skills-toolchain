#!/usr/bin/env python3
"""Probe 1: privilege-widening preset rejected; narrowing preset accepted.

Both-states on tools and on source_policy. A widening preset is not silently
clipped to the intersection — load returns the named widening violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.packs import (  # noqa: E402
    LoadedPack,
    PackViolation,
    load_pack,
    privilege_intersection,
)
from scenario import (  # noqa: E402
    NARROW_SOURCES,
    NARROW_TOOLS,
    PRESET_NARROW,
    WF_ID,
    WIDEN_SOURCE,
    WIDEN_TOOL,
    WORKFLOW_SOURCES,
    WORKFLOW_TOOLS,
    pack_edited_widen,
    pack_invalid_semver,
    pack_narrow,
    pack_widen_source,
    pack_widen_tools,
)

OUT = HERE / "probe1-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0207-probe1 {msg}")
    return 1


def main() -> int:
    narrow = load_pack(pack_narrow())
    if isinstance(narrow, PackViolation):
        return fail(f"narrowing pack rejected: {narrow.code} {narrow.message}")
    if not isinstance(narrow, LoadedPack):
        return fail(f"narrowing pack unexpected type {type(narrow)}")
    if str(narrow.version) != "1.2.0":
        return fail(f"semver not preserved: {narrow.version}")
    binding = narrow.effective_for(WF_ID, PRESET_NARROW)
    if binding.tool_permissions != NARROW_TOOLS:
        return fail(f"narrow tools={sorted(binding.tool_permissions)}")
    if binding.source_policy != NARROW_SOURCES:
        return fail(f"narrow sources={sorted(binding.source_policy)}")
    if binding.tool_permissions == WORKFLOW_TOOLS:
        return fail("narrowing preset left workflow tools unchanged")

    widen_t = load_pack(pack_widen_tools())
    if not isinstance(widen_t, PackViolation):
        return fail("tool-widening pack was accepted")
    if widen_t.code != "pack-preset-tool-permission-widening":
        return fail(f"tool-widening code={widen_t.code}")
    if WIDEN_TOOL not in widen_t.extra:
        return fail(f"tool-widening extra={widen_t.extra} missing {WIDEN_TOOL}")
    if widen_t.axis != "tool_permissions":
        return fail(f"tool-widening axis={widen_t.axis}")
    clipped_tools = privilege_intersection(
        frozenset(pack_widen_tools()["presets"][0]["tool_permissions"]),
        WORKFLOW_TOOLS,
    )
    if clipped_tools == WORKFLOW_TOOLS and isinstance(widen_t, LoadedPack):
        return fail("tool widening was clipped instead of rejected")
    if not isinstance(widen_t, PackViolation):
        return fail("tool widening produced a loaded pack (silent clip)")

    widen_s = load_pack(pack_widen_source())
    if not isinstance(widen_s, PackViolation):
        return fail("source-widening pack was accepted")
    if widen_s.code != "pack-preset-source-policy-widening":
        return fail(f"source-widening code={widen_s.code}")
    if WIDEN_SOURCE not in widen_s.extra:
        return fail(f"source-widening extra={widen_s.extra} missing {WIDEN_SOURCE}")
    if widen_s.axis != "source_policy":
        return fail(f"source-widening axis={widen_s.axis}")

    edited = load_pack(pack_edited_widen())
    if not isinstance(edited, PackViolation):
        return fail("edited narrowing preset silently widened")
    if edited.code != "pack-preset-tool-permission-widening":
        return fail(f"edited-widen code={edited.code}")
    if WIDEN_TOOL not in edited.extra:
        return fail("edited-widen did not name Write")

    bad_ver = load_pack(pack_invalid_semver())
    if not isinstance(bad_ver, PackViolation) or bad_ver.code != "pack-semver-invalid":
        return fail(f"invalid semver not rejected: {bad_ver}")

    doc = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "IMP-0207",
        "narrow_accepted": True,
        "narrow_effective_tools": sorted(binding.tool_permissions),
        "narrow_effective_sources": sorted(binding.source_policy),
        "tool_widening_rejected": True,
        "tool_widening_code": widen_t.code,
        "tool_widening_extra": list(widen_t.extra),
        "source_widening_rejected": True,
        "source_widening_code": widen_s.code,
        "source_widening_extra": list(widen_s.extra),
        "editable_reload_rejected_widen": True,
        "invalid_semver_rejected": True,
        "silent_clip_refused": True,
        "both_states": {
            "widening_rejected": True,
            "narrowing_accepted": True,
        },
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"narrow_ok=True tools={sorted(binding.tool_permissions)} "
        f"sources={sorted(binding.source_policy)} "
        f"widen_tools={widen_t.code}:{list(widen_t.extra)} "
        f"widen_source={widen_s.code}:{list(widen_s.extra)}"
    )
    print("SUCCESS:IMP-0207-probe1 privilege-widening rejected; narrowing accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
