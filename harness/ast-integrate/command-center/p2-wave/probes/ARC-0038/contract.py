"""A6 work-unit contract, three-tier map, vendor adapters, abstraction leaks.

SSOT for ARC-0038. Every catalog work-unit field is assigned to exactly one
tier. Citations are paths on this worktree, not assumed vendor docs.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

# Live catalog key names that alias the 19-field Prompt-Two contract.
FIELD_ALIASES = {
    "target": "question_or_target",
    "assignment": "assigned_model_vendor_role",
}

TIERS = ("GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY")

# Each assignment cites an observed vendor behaviour difference on this tree.
TIER_ASSIGNMENTS = {
    "id": {
        "tier": "GUARANTEED",
        "justification": (
            "Unit identity is the dispatch key and the sentinel suffix. Both "
            "vendors must round-trip the same id; renaming at the adapter is a "
            "contract break, not a flavour difference."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:7",
    },
    "title": {
        "tier": "GUARANTEED",
        "justification": (
            "Human-readable identity travels with the unit. Adapters may not "
            "rewrite the title to match a vendor-native job name."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:8",
    },
    "phase": {
        "tier": "GUARANTEED",
        "justification": (
            "Phase is program metadata (Phase 3 tournament for ARC-0038). It is "
            "not a vendor runtime property."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:9",
    },
    "target": {
        "tier": "GUARANTEED",
        "justification": (
            "The work statement (live key question_or_target) is the same text "
            "whichever adapter runs. Vendor paraphrase of the question is an "
            "abstraction leak and is forbidden at GUARANTEED."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12582",
    },
    "inputs": {
        "tier": "GUARANTEED",
        "justification": (
            "Declared input paths are the unit's closed file set. An adapter "
            "that silently drops an absent Windows restore path and continues "
            "would hide NOT-CHECKED as SUCCESS."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12567",
    },
    "dependencies": {
        "tier": "GUARANTEED",
        "justification": (
            "The catalog graph is vendor-neutral. Adapter-side 'close enough' "
            "substitution of a dependency is a silent downgrade."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12551",
    },
    "output_path": {
        "tier": "GUARANTEED",
        "justification": (
            "G-1 delivery is existence+parse of this path. Codex AND-gate "
            "(IMP-0421) already measured that exit 0 without the file is "
            "severed-stream, not SUCCESS. The path is therefore identical "
            "across vendors."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12578",
    },
    "output_schema": {
        "tier": "GUARANTEED",
        "justification": (
            "ARC-0043's schema-parity test requires both vendors' artifacts to "
            "validate against the identical schema file, by path. Schema "
            "substitution is a lie."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12579",
    },
    "completion_sentinel": {
        "tier": "GUARANTEED",
        "justification": (
            "ARC-0040 requires every dispatch to end in SUCCESS:<id> or "
            "FAILED:<id> <reason> and never in silence. Progress streams are "
            "not sentinels (measured failure class on this estate)."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12684",
    },
    "evidence_requirement": {
        "tier": "GUARANTEED",
        "justification": (
            "The evidence bar is the unit's, not the vendor's. A vendor that "
            "cannot produce a cited measurement must FAIL, not lower the bar."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12558",
    },
    "tests_required": {
        "tier": "GUARANTEED",
        "justification": (
            "The two catalog tests (tier-completeness; downgrade-refusal) are "
            "the same predicates on every adapter. Skipping a test because a "
            "vendor lacks a tool is a silent downgrade."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12585",
    },
    "owner_approval_required": {
        "tier": "GUARANTEED",
        "justification": (
            "Owner gate is program policy. An adapter must not infer approval "
            "from a vendor-native 'auto-run' flag."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12580",
    },
    "reviewer_requirement": {
        "tier": "GUARANTEED",
        "justification": (
            "The declared reviewer constraint (independent architect; paired "
            "ARC-0044 refutation) is catalog text. Fulfillment is scheduling; "
            "the field's meaning does not change by vendor. Waiting on ARC-0044 "
            "before G-1 of ARC-0038 is a deadlock and is recorded as such, not "
            "rewritten."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12584",
    },
    "timeout_seconds": {
        "tier": "BEST-EFFORT",
        "justification": (
            "IMP-0420 requires the declared timeout to be the one applied, not "
            "a default. Kill/cancel mechanisms differ (process kill vs API "
            "cancel vs MCP tool abort). The adapter must try to honor the "
            "integer; residual mechanism difference is a documented leak."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:60124",
    },
    "retry_policy": {
        "tier": "BEST-EFFORT",
        "justification": (
            "Catalog retry for Codex is 'once on win-arg-limit with "
            "--ignore-user-config and --prompt-file; never --background'. "
            "Claude native dispatch does not share CreateProcess 32767. The "
            "portable intent (no silent retry into a verdict; prompt-by-file) "
            "is best-effort; the Codex flags themselves are vendor-only."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:11051",
    },
    "execution_substrate": {
        "tier": "BEST-EFFORT",
        "justification": (
            "ARC-0038 declares local-parallel; IMP-0421 Codex adapter declares "
            "local-serialized; IMP-0419 declares worktree-isolated. Substrate "
            "labels are not interchangeable. The adapter should preserve the "
            "unit's declared substrate when the host can, and leak when it cannot."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12559",
    },
    "failure_classification": {
        "tier": "BEST-EFFORT",
        "justification": (
            "The catalog taxonomy is shared, but vendor error vocabularies "
            "differ: Windows OS error 206 / win-arg-limit vs Claude tool-error "
            "vs MCP schema-invalid-while-tools-active (ARC-0040). Mapping into "
            "the unit's declared classes is best-effort; unmapped errors must "
            "surface as FAILED:<id> unmapped-vendor-error, never as SUCCESS."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:32477",
    },
    "assignment": {
        "tier": "VENDOR-ONLY",
        "justification": (
            "assigned_model_vendor_role binds vendor+model+role. ARC-0038 is "
            "anthropic/opus/architect; ARC-0044 is openai/codex-cli-default/"
            "adversarial-refuter. Pretending these are the same assignment is "
            "the interchangeability lie ARC-0044 exists to refute."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12543",
    },
    "tool_permissions": {
        "tier": "VENDOR-ONLY",
        "justification": (
            "ARC-0038 lists Read/Grep/Glob/Write. Cross-vendor units list "
            "mcp__codex__codex. Those names are not a common vocabulary. "
            "Treating them as GUARANTEED-identical is the first inexpressible "
            "construct: vendor-native tool names as a portable permission set."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12906",
    },
}

# A6 envelope fields (not in the Prompt-Two 19; required by this architecture).
ENVELOPE_FIELDS = {
    "min_tier": {
        "tier": "GUARANTEED",
        "justification": (
            "Every unit must declare the minimum tier it needs. Missing min_tier "
            "FAIL-CLOSED. Adapters may not infer a lower tier."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:12582",
    },
    "capability_needs": {
        "tier": "GUARANTEED",
        "justification": (
            "Declared capability ids are the negotiation input. Computed "
            "intersection, not asserted (IMP-0419 evidence_requirement)."
        ),
        "citation": "command-center/WORK-UNIT-CATALOG.json:60073",
    },
}

CAPABILITY_TIERS = {
    "artifact.json_schema": "GUARANTEED",
    "artifact.completion_sentinel": "GUARANTEED",
    "dispatch.blocking_foreground": "GUARANTEED",
    "transport.prompt_by_file": "GUARANTEED",
    "tools.fs.read": "GUARANTEED",
    "tools.fs.write": "GUARANTEED",
    "streaming.progress_not_result": "BEST-EFFORT",
    "tools.mcp.codex": "VENDOR-ONLY",
    "tools.native.claude_grep": "VENDOR-ONLY",
    "runtime.ignore_user_config": "VENDOR-ONLY",
    "runtime.win32_createprocess_32767": "VENDOR-ONLY",
}

VENDORS = {
    "anthropic": {
        "adapter_id": "a6.anthropic.v1",
        "vendor": "anthropic",
        "capabilities": {
            "artifact.json_schema": True,
            "artifact.completion_sentinel": True,
            "dispatch.blocking_foreground": True,
            "transport.prompt_by_file": True,
            "tools.fs.read": True,
            "tools.fs.write": True,
            "streaming.progress_not_result": True,
            "tools.mcp.codex": False,
            "tools.native.claude_grep": True,
            "runtime.ignore_user_config": False,
            "runtime.win32_createprocess_32767": False,
        },
        "leaks": [
            {
                "id": "A6-LEAK-ANTH-001",
                "surface": "tool_permissions",
                "text": (
                    "Claude first-class tools are Read/Grep/Glob/Write/Bash. "
                    "mcp__codex__codex is not a Claude tool. Mapping Codex MCP "
                    "names onto Claude tools is a lie."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:12591",
            },
            {
                "id": "A6-LEAK-ANTH-002",
                "surface": "streaming",
                "text": (
                    "A progress stream is not a result. ARC-0040 records "
                    "progress-mistaken-for-result as a measured estate failure."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:12684",
            },
            {
                "id": "A6-LEAK-ANTH-003",
                "surface": "runtime.ignore_user_config",
                "text": (
                    "There is no Claude equivalent of Codex --ignore-user-config. "
                    "Retry-on-win-arg-limit with that flag is not portable."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:11051",
            },
        ],
    },
    "openai": {
        "adapter_id": "a6.openai.v1",
        "vendor": "openai",
        "capabilities": {
            "artifact.json_schema": True,
            "artifact.completion_sentinel": True,
            "dispatch.blocking_foreground": True,
            "transport.prompt_by_file": True,
            "tools.fs.read": True,
            "tools.fs.write": True,
            "streaming.progress_not_result": True,
            "tools.mcp.codex": True,
            "tools.native.claude_grep": False,
            "runtime.ignore_user_config": True,
            "runtime.win32_createprocess_32767": True,
        },
        "leaks": [
            {
                "id": "A6-LEAK-OAI-001",
                "surface": "transport.prompt_by_file",
                "text": (
                    "Windows CreateProcess caps the command line at 32,767 "
                    "characters. A measured inline prompt of 34,472 died with "
                    "OS error 206. Prompts MUST go by file, never inline."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:32477",
            },
            {
                "id": "A6-LEAK-OAI-002",
                "surface": "dispatch.blocking_foreground",
                "text": (
                    "Fire-and-forget --background loses the result. IMP-0421: "
                    "a work-unit dispatch must be structurally unable to run "
                    "detached. Exit 0 with an empty/missing last-message file "
                    "is severed-stream, not SUCCESS."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:60145",
            },
            {
                "id": "A6-LEAK-OAI-003",
                "surface": "tool_permissions",
                "text": (
                    "mcp__codex__codex is vendor-only. Claude Read/Grep/Glob "
                    "are not Codex tools. Schema-invalid output while MCP tools "
                    "are active is a measured failure class (ARC-0040)."
                ),
                "citation": "command-center/WORK-UNIT-CATALOG.json:12684",
            },
        ],
    },
}

SAMPLES = [
    {
        "kind": "skill",
        "id": "skill.council",
        "source_id": "skills/council/SKILL.md",
        "source_citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09]",
        "min_tier": "GUARANTEED",
        "capability_needs": [
            "artifact.json_schema",
            "artifact.completion_sentinel",
            "dispatch.blocking_foreground",
            "transport.prompt_by_file",
            "tools.fs.read",
        ],
        "verdict": "EXPRESSIBLE",
        "note": (
            "Four named roles as static prompt sections. Portable as a work "
            "unit that needs only GUARANTEED capabilities. Does not require "
            "mcp.codex or Claude-only Grep."
        ),
    },
    {
        "kind": "workflow_blueprint",
        "id": "wf.catalog-class.discovery-only",
        "source_id": "09-WORKFLOW-BLUEPRINT-LIBRARY.json#discovery_only",
        "source_citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A08]",
        "min_tier": "GUARANTEED",
        "capability_needs": [
            "artifact.json_schema",
            "artifact.completion_sentinel",
            "dispatch.blocking_foreground",
            "transport.prompt_by_file",
            "tools.fs.read",
            "tools.fs.write",
        ],
        "verdict": "EXPRESSIBLE",
        "note": (
            "Finite declarative stages. Expressible as a GUARANTEED unit so "
            "long as tool_permissions stay in the portable fs.read/fs.write "
            "set, not vendor-native tool names."
        ),
    },
    {
        "kind": "council_preset",
        "id": "council.preset.catalog-class.editable",
        "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
        "source_citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09]",
        "min_tier": "GUARANTEED",
        "capability_needs": [
            "artifact.json_schema",
            "artifact.completion_sentinel",
            "dispatch.blocking_foreground",
            "transport.prompt_by_file",
            "tools.fs.read",
            "streaming.progress_not_result",
        ],
        "verdict": "EXPRESSIBLE",
        "note": (
            "Declarative roles/voting/stopping. Progress-not-result is "
            "BEST-EFFORT: a vendor that emits a progress stream must not treat "
            "it as the terminal artifact."
        ),
    },
]

FIRST_INEXPRESSIBLE = (
    "vendor-native tool names (mcp__codex__codex vs Read/Grep/Glob) treated as "
    "a GUARANTEED-identical tool_permissions vocabulary"
)


def catalog_contract_fields() -> list[str]:
    import json

    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    fields = list(doc["contract"]["work_unit_fields"])
    return fields


def partition() -> dict[str, list[str]]:
    out = {t: [] for t in TIERS}
    for field, meta in TIER_ASSIGNMENTS.items():
        out[meta["tier"]].append(field)
    for t in TIERS:
        out[t].sort()
    return out
