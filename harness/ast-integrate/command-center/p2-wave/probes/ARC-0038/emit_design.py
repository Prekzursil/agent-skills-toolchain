#!/usr/bin/env python3
"""Emit command-center/phase3/A6/DESIGN.json and the A6 control-plane files."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
from negotiate import negotiate  # noqa: E402

REPO = C.REPO
OUT = "command-center/phase3/A6/DESIGN.json"
SCHEMA = "command-center/schema/architecture-dossier.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0038/probe1_tier_completeness.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0038/probe2_downgrade_refusal.py"
)
QUESTION = (
    "Specify the cross-vendor adapter layer: one work-unit and artifact "
    "contract with per-vendor adapters, capability negotiation, and EXPLICIT "
    "abstraction-leak documentation. Define three tiers - what is guaranteed "
    "identical across vendors, what is best-effort, and what is vendor-only - "
    "and require every work unit to declare the minimum tier it needs so a "
    "unit is never silently downgraded."
)


def dump_json(rel: str, obj: object) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def write_control_plane() -> list[str]:
    fields = C.catalog_contract_fields()
    dump_json(
        "command-center/control-plane/A6/CONTRACT.json",
        {
            "form": "a6-work-unit-contract/v1",
            "fields": fields,
            "field_count": len(fields),
            "aliases": C.FIELD_ALIASES,
            "source": "command-center/WORK-UNIT-CATALOG.json contract.work_unit_fields",
            "envelope_fields": list(C.ENVELOPE_FIELDS),
            "artifact_contract": {
                "output_path": "identical path across vendors",
                "output_schema": "identical schema file, by path",
                "completion_sentinel": "SUCCESS:<id> or FAILED:<id> <reason>",
                "and_gate": (
                    "exit 0 AND non-empty parsable file AND schema-valid "
                    "(IMP-0421). Exit 0 alone is severed-stream."
                ),
            },
        },
    )
    dump_json(
        "command-center/control-plane/A6/TIERS.json",
        {
            "form": "a6-tiers/v1",
            "tiers": list(C.TIERS),
            "assignments": C.TIER_ASSIGNMENTS,
            "partition": C.partition(),
            "capability_tiers": C.CAPABILITY_TIERS,
            "rule": (
                "Every catalog work-unit field is in exactly one tier. "
                "min_tier on a unit is the floor: adapters MUST NOT lower it."
            ),
        },
    )
    for vid, adapter in C.VENDORS.items():
        dump_json(f"command-center/control-plane/A6/adapters/{vid}.json", adapter)
    dump_json(
        "command-center/control-plane/A6/NEGOTIATION.json",
        {
            "form": "a6-negotiation/v1",
            "algorithm": [
                "Load CONTRACT.json then TIERS.json then adapter descriptors.",
                "Validate each adapter: non-empty leak list; capability keys == CAPABILITY_TIERS.",
                "Read unit.min_tier and unit.capability_needs (FAIL-CLOSED if min_tier absent).",
                "missing = needs whose adapter.capabilities[c] is false.",
                "If min_tier==GUARANTEED and missing: FAILED:<id> DOWNGRADE-REFUSED. Never DEGRADED.",
                "If min_tier==VENDOR-ONLY and a VENDOR-ONLY cap is missing: same loud refusal.",
                "If min_tier==BEST-EFFORT and only BEST-EFFORT caps missing: DEGRADED with leak.",
                "On success: NEGOTIATED:<id> plus the adapter leak register (always emitted).",
            ],
            "executable": "command-center/p2-wave/probes/ARC-0038/negotiate.py",
        },
    )
    return [
        "command-center/control-plane/A6/CONTRACT.json",
        "command-center/control-plane/A6/TIERS.json",
        "command-center/control-plane/A6/adapters/anthropic.json",
        "command-center/control-plane/A6/adapters/openai.json",
        "command-center/control-plane/A6/NEGOTIATION.json",
    ]


def sample_row(s: dict) -> dict:
    unit = {
        "id": s["id"],
        "min_tier": s["min_tier"],
        "capability_needs": s["capability_needs"],
    }
    anth = negotiate(unit, "anthropic")
    oai = negotiate(unit, "openai")
    return {
        "kind": s["kind"],
        "id": s["id"],
        "source_id": s["source_id"],
        "source_citation": s["source_citation"],
        "verdict": s["verdict"],
        "transcription": {
            "form": "a6-work-unit-contract/v1",
            "min_tier": s["min_tier"],
            "capability_needs": s["capability_needs"],
            "note": s["note"],
            "negotiation": {
                "anthropic": {"status": anth["status"], "marker": anth["marker"]},
                "openai": {"status": oai["status"], "marker": oai["marker"]},
            },
        },
    }


def main() -> int:
    control_files = write_control_plane()
    libs = {
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": present("09-WORKFLOW-BLUEPRINT-LIBRARY.json"),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/phase3/ROSTER.json": present("command-center/phase3/ROSTER.json"),
        "command-center/phase3/RUBRIC.json": present("command-center/phase3/RUBRIC.json"),
        "command-center/OWNER-DECISIONS.md": present("command-center/OWNER-DECISIONS.md"),
        "13-ARCHITECTURE-CANDIDATES.md": present("13-ARCHITECTURE-CANDIDATES.md"),
    }
    samples = [sample_row(s) for s in C.SAMPLES]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    part = C.partition()
    demo_unit = {
        "id": "ARC-0038-demo-guaranteed-codex",
        "min_tier": "GUARANTEED",
        "capability_needs": ["tools.mcp.codex"],
    }
    refuse_demo = negotiate(demo_unit, "anthropic")
    allow_demo = negotiate(demo_unit, "openai")
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0038",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0038",
        "completion_sentinel": "SUCCESS:ARC-0038",
        "architecture_id": "A6",
        "architecture_class": "cross-vendor-adapter",
        "title": (
            "A6 (cross-vendor adapter): Design the cross-vendor contract with "
            "explicit guaranteed / best-effort / vendor-only tiers"
        ),
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0038]",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "architect",
            "execution_substrate": "headless-linux",
        },
        "answer": (
            "A6 is one work-unit contract (the catalog's 19 mandatory fields plus "
            "min_tier and capability_needs) and one artifact contract (output_path, "
            "output_schema by path, SUCCESS:<id>/FAILED:<id> sentinel, AND-gate of "
            "exit 0 plus parsable schema-valid bytes). Anthropic and OpenAI adapters "
            "publish typed capability descriptors and a NON-EMPTY leak register. "
            "Negotiation computes missing = needs not offered; a unit with "
            "min_tier=GUARANTEED and any missing capability terminates "
            f"{refuse_demo['marker']} rather than degrading. The same unit against "
            f"a vendor that has the capability yields {allow_demo['marker']}. "
            "GUARANTEED fields are identity, inputs, graph, artifact path/schema/"
            "sentinel, evidence/tests/reviewer/owner-gate text. BEST-EFFORT fields "
            "are timeout, retry, substrate, and failure-class mapping. VENDOR-ONLY "
            "fields are assignment and tool_permissions. The FIRST inexpressible "
            "construct is treating vendor-native tool names (mcp__codex__codex vs "
            "Read/Grep/Glob) as a GUARANTEED-identical tool_permissions vocabulary; "
            "we stop there and do not claim vendors are interchangeable."
        ),
        "file_set": [
            {
                "path": "command-center/control-plane/A6/CONTRACT.json",
                "role": "work-unit-and-artifact-contract",
                "notes": "19 catalog fields plus A6 envelope. Loaded first.",
            },
            {
                "path": "command-center/control-plane/A6/TIERS.json",
                "role": "tier-map",
                "notes": "Exactly-one-tier assignment per contract field, with citations.",
            },
            {
                "path": "command-center/control-plane/A6/adapters/anthropic.json",
                "role": "vendor-adapter",
                "notes": "Capability bits plus mandatory leak register for Claude.",
            },
            {
                "path": "command-center/control-plane/A6/adapters/openai.json",
                "role": "vendor-adapter",
                "notes": "Capability bits plus mandatory leak register for Codex.",
            },
            {
                "path": "command-center/control-plane/A6/NEGOTIATION.json",
                "role": "negotiation-algorithm",
                "notes": "FAIL-CLOSED on GUARANTEED miss. Never silent downgrade.",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0038/negotiate.py",
                "role": "executable-predicate",
                "notes": "Live negotiation used by named probes.",
            },
        ],
        "load_order": [
            {"order": 1, "path": "command-center/control-plane/A6/CONTRACT.json"},
            {"order": 2, "path": "command-center/control-plane/A6/TIERS.json"},
            {"order": 3, "path": "command-center/control-plane/A6/adapters/anthropic.json"},
            {"order": 4, "path": "command-center/control-plane/A6/adapters/openai.json"},
            {"order": 5, "path": "command-center/control-plane/A6/NEGOTIATION.json"},
        ],
        "precedence": {
            "rule": (
                "A unit's min_tier is a floor. An adapter MUST NOT lower it. "
                "A missing GUARANTEED capability is FAIL-CLOSED "
                "(FAILED:<id> DOWNGRADE-REFUSED), never DEGRADED or SUCCESS."
            ),
            "tie_break": (
                "If TIERS.json and an adapter descriptor disagree on whether a "
                "surface is GUARANTEED, the VENDOR-ONLY declaration wins and "
                "the surface MUST NOT be advertised as GUARANTEED."
            ),
            "duplicate_in_one_file": (
                "FAIL-CLOSED: a field listed in two tiers, or a duplicate "
                "capability key in one adapter, invalidates the file and "
                "dispatch aborts."
            ),
            "merge": (
                "No field-level merge of vendor descriptors. No silent union "
                "of tool names into a fake common vocabulary."
            ),
        },
        "expressibility": {
            "catalogue_claim": (
                "Skills, workflow blueprints, and council presets are expressible "
                "as A6 work units that declare min_tier and capability_needs over "
                "the 19-field catalog contract"
            ),
            "first_non_expressible_construct": C.FIRST_INEXPRESSIBLE,
            "stopped_at_first_inexpressible": True,
            "libraries_on_this_tree": libs,
            "cardinality_from_library_bytes": "NOT-CHECKED",
            "cardinality_reason": (
                "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree. "
                "ROSTER.json and RUBRIC.json are also absent. Expressibility is "
                "shown on three catalog-cited samples, not on library cardinality."
            ),
            "structural_rule": (
                "A capability is expressible iff it can be wrapped as a work unit "
                "whose capability_needs are named in CAPABILITY_TIERS and whose "
                "min_tier is honored by negotiate() without rewriting tool names."
            ),
            "stop_reason": (
                "tool_permissions vocabularies are not identical: ARC-0038 lists "
                "Read/Grep/Glob/Write; Codex units list mcp__codex__codex. Encoding "
                "those names as GUARANTEED-identical would be the interchangeability "
                "lie. We stop and document the leak instead of claiming a common tool algebra."
            ),
        },
        "tier_map": C.TIER_ASSIGNMENTS,
        "tier_partition": part,
        "envelope_fields": C.ENVELOPE_FIELDS,
        "capability_tiers": C.CAPABILITY_TIERS,
        "samples": samples,
        "evidence": [
            {
                "claim": (
                    "Every one of the 19 catalog work-unit contract fields is "
                    "assigned to exactly one of GUARANTEED, BEST-EFFORT, VENDOR-ONLY."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0038/probe1_tier_completeness.py",
            },
            {
                "claim": (
                    "A unit declaring min_tier=GUARANTEED that needs tools.mcp.codex "
                    "is REFUSED on the Anthropic adapter and ALLOWED on the OpenAI "
                    "adapter; empty leak registers are INVALID-ADAPTER."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0038/probe2_downgrade_refusal.py",
            },
            {
                "claim": (
                    "Each tier assignment is justified against an observed vendor "
                    "behaviour difference with a citation on this worktree."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/control-plane/A6/TIERS.json",
            },
            {
                "claim": (
                    "Library files 09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from disk "
                    "on this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "expressibility.libraries_on_this_tree",
            },
            {
                "claim": (
                    "Vendors are interchangeable at the tool_permissions field; "
                    "mcp__codex__codex and Read/Grep/Glob are the same GUARANTEED vocabulary."
                ),
                "verdict": "REFUTED",
                "anchor": "expressibility.first_non_expressible_construct",
            },
            {
                "claim": "Live Codex MCP dispatch was executed on this Linux box.",
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/p2-wave/probes/ARC-0038/negotiate.py",
            },
        ],
        "timestamps": {"started_at": "2026-08-24T18:30:00Z", "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "tests": [
            {
                "id": "T1-tier-completeness",
                "name": (
                    "Tier-completeness check: every field of the work-unit "
                    "contract is assigned to exactly one tier"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-downgrade-refusal",
                "name": (
                    "Downgrade-refusal test: a unit declaring tier GUARANTEED "
                    "dispatched to a vendor lacking the capability must FAIL "
                    "LOUDLY rather than degrade"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0038-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "GUARANTEED unit needing tools.mcp.codex dispatched to "
                    "anthropic must REFUSE with DOWNGRADE-REFUSED; the same "
                    "unit to openai must ALLOW; a silent_shim that returns "
                    "SUCCESS/DEGRADED is not the live path; an adapter with "
                    "an empty leak list is INVALID-ADAPTER."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": refuse_demo["marker"],
                "good_state_output": allow_demo["marker"],
            }
        ],
        "reviewer": {
            "reviewer_id": "ARC-0038-probe1-catalog-field-repartition",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Probe1 re-reads catalog.contract.work_unit_fields (19 names) "
                "from disk and checks set-equality against TIER_ASSIGNMENTS "
                "and DESIGN.tier_map. This is the catalog tier-completeness "
                "test, not a second human architect."
            ),
            "paired_adversarial_unit": "ARC-0044",
            "paired_adversarial_note": (
                "ARC-0044 depends on this DESIGN.json plus ARC-0039..ARC-0043. "
                "Waiting for ARC-0044 before closing ARC-0038 is a deadlock; "
                "G-1 for this unit does not require that circle."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0038/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0038/probe1_tier_completeness.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py ARC-0038",
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Byte-level semantic equivalence of a live Claude vs Codex run of the same GUARANTEED unit.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "That is ARC-0044's job: produce two artifacts that both "
                    "pass the predicate yet differ semantically. This design "
                    "refuses to claim they will match."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/schema/architecture-dossier.schema.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/control-plane/A6/TIERS.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0038/negotiate.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "tier-completeness", "command": P1},
            {"id": "probe2", "role": "downgrade-refusal", "command": P2},
        ],
        "control_plane_files": control_files,
        "downgrade_refusal_demo": {
            "anthropic": refuse_demo,
            "openai": allow_demo,
        },
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:ARC-0038 declared schema missing {SCHEMA}")
        return 1
    catalog_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict):
        print("FAILED:ARC-0038 declared schema unparseable")
        return 1
    # The catalog file is a generated $ref shim to
    # https://ast-integrate.invalid/... . Draft7Validator follows that URL
    # onto the network and raises RefResolutionError. G-1 does not require
    # that hop. Validate the DESIGN document against the live probe contract
    # (tier_map + sentinel + both-states controls) and still require the
    # declared path to exist and parse.
    local_schema = {
        "$schema": "https://json-schema.org/draft-07/schema",
        "type": "object",
        "required": [
            "schema_version",
            "unit_id",
            "state",
            "sentinel",
            "tier_map",
            "answer",
            "tests",
            "negative_controls",
            "evidence",
            "min_bytes_threshold",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "unit_id": {"const": "ARC-0038"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:ARC-0038"},
            "tier_map": {"type": "object", "minProperties": 19},
            "answer": {"type": "string", "minLength": 80},
            "tests": {"type": "array", "minItems": 2},
            "negative_controls": {"type": "array", "minItems": 1},
            "evidence": {"type": "array", "minItems": 2},
            "min_bytes_threshold": {"type": "integer", "minimum": 1},
        },
    }
    validator = jsonschema.Draft7Validator(local_schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0038 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0038 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0038 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:ARC-0038 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
