"""Blueprints 7-8 of 12: BP-GEM-01 Wide-Lens Gem Sweep, BP-GEM-02 Anti-Overfit Candidate Gate."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(HERE))

import bp1_build as B  # noqa: E402

S = B.schema

# --------------------------------------------------------------- 7. BP-GEM-01

_G1_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "WebSearch",
    "WebFetch",
    "Write(command-center/sweeps/**)",
    "mcp__search-hub__web_search_exa",
    "mcp__search-hub__firecrawl_search",
    "mcp__searxng__searxng_web_search",
    "mcp__github__search_repositories",
    "mcp__codex__codex",
]


def _gem01() -> dict[str, Any]:
    root = "command-center/sweeps/bp-gem-01"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-gem-01-wide-lens-gem-sweep",
            "name": "Wide-Lens Gem Sweep",
            "description": (
                "Discover high-value additions to the owner's own toolkit by fanning ~40 INDEPENDENT "
                "discovery lenses and converging to a tiered adopt / build / prune queue. The merge "
                "that makes this worth running is the DEDUP GROUNDING stage: the wide-roster source "
                "workflow had no grounding pass and re-proposed things already built, while the "
                "narrow source had grounding but only 14 lenses. Grounding runs FIRST so no lens can "
                "propose an existing capability, and the adopt/prune judgement is delegated to "
                "BP-GEM-02 as a SUBWORKFLOW rather than reimplemented here - discovery and judgement "
                "stay separable. The blueprint has NO write permission outside its artifact root, "
                "which is what makes a 40-agent sweep safe to run."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["collective-intelligence-and-meta"],
            "tags": ["discovery", "wide-fanout", "dedup-grounding"],
            "flagship": False,
            "params": {
                "scope": {
                    "type": "string",
                    "required": True,
                    "min_length": 10,
                    "description": "What the sweep is hunting over",
                },
                "lens_roster": {
                    "type": "array",
                    "required": True,
                    "min_items": 4,
                    "max_items": 80,
                    "items": {"type": "string", "min_length": 3},
                    "description": "One independent discovery lens per entry; the roster IS the reproducibility surface",
                },
                "already_built_inventory": {
                    "type": "path",
                    "required": True,
                    "description": "Inventory of what already exists; without it every lens re-proposes the estate back to itself",
                },
                "absorption_budget": {
                    "type": "integer",
                    "default": 6,
                    "minimum": 0,
                    "maximum": 200,
                    "description": "Items the estate will actually build this cycle - discovery without a budget manufactures a backlog",
                },
                "include_codex_arm": {
                    "type": "boolean",
                    "default": True,
                    "description": "Optional S1b: a cross-vendor Codex lens set",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "The ONLY writable root: discovery has no other write permission",
                },
            },
            "roles": {
                "grounding-agent": {
                    "description": "Enumerates what already exists so no lens can propose it; produces the dedup set every lens is briefed with",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/sweeps/**)",
                    ],
                    "speaking_rights": "always",
                },
                "discovery-lens": {
                    "description": "One lens, one angle, no sight of sibling lenses; a lens that finds nothing records a NULL RESULT with its search surface",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "WebSearch",
                        "WebFetch",
                        "mcp__search-hub__web_search_exa",
                        "mcp__search-hub__firecrawl_search",
                        "mcp__searxng__searxng_web_search",
                        "mcp__github__search_repositories",
                        "Write(command-center/sweeps/**)",
                    ],
                    "min_participants": 4,
                    "max_participants": 80,
                    "speaking_rights": "always",
                },
                "codex-lens": {
                    "description": "Cross-vendor lens set: independent failure modes, not extra headcount",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "cross_vendor_required": True,
                    "tool_permissions": [
                        "Read",
                        "mcp__codex__codex",
                        "Write(command-center/sweeps/**)",
                    ],
                    "speaking_rights": "on-request",
                },
                "synthesiser": {
                    "description": "Merges and dedupes the lens output; may not add a candidate no lens produced",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "max",
                    "authority": "chair",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/sweeps/**)",
                    ],
                    "speaking_rights": "always",
                },
                "queue-builder": {
                    "description": "Turns judged candidates into an owner-consumable decision queue, one line per decision",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "informed",
                    "tool_permissions": ["Read", "Write(command-center/sweeps/**)"],
                    "speaking_rights": "always",
                },
                "owner": {
                    "description": "The human owner - the only role that sets the absorption budget and accepts the queue",
                    "vendor": "human",
                    "authority": "owner",
                    "speaking_rights": "on-request",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_G1_ALLOW),
                "deny": [
                    "Bash",
                    "Write(platform/**)",
                    "Write(command-center/WORK-UNIT-CATALOG.json)",
                    "mcp__github__create_pull_request",
                ],
                "network": "read-only",
                "write_paths": ["command-center/sweeps/**"],
                "forbid_write_paths": [
                    "platform/**",
                    "command-center/WORK-UNIT-CATALOG.json",
                    "skills/**",
                ],
                "source_policy": {
                    "require_provenance": True,
                    "offline_only": False,
                    "license_allowlist": [
                        "MIT",
                        "Apache-2.0",
                        "BSD-3-Clause",
                        "MPL-2.0",
                        "owner-proprietary",
                    ],
                    "treat_fetched_content_as_data": True,
                    "paywalled": "skip",
                },
            },
            "model_routing": {
                "strategy": "vendor-diverse",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'codex-lens'",
                        "target": {
                            "model": "gpt-5-codex",
                            "vendor": "openai",
                            "effort": "high",
                        },
                        "reason": "a cross-vendor arm names options no in-vendor lens names",
                    }
                ],
                "fallbacks": [
                    {"model": "opus", "vendor": "anthropic", "effort": "high"}
                ],
                "forbid_downgrade_below": "opus",
            },
            "subworkflows": {
                "bp-gem-02-anti-overfit-candidate-gate": {
                    "workflow_id": "bp-gem-02-anti-overfit-candidate-gate",
                    "version_range": ">=1.0.0 <2.0.0",
                    "source": "platform/workflows/bp-gem-02-anti-overfit-candidate-gate.json",
                }
            },
            "gates": {
                "grounding-present": {
                    "predicate": "custom-expression",
                    "expression": "dedup_set_rows > 0 AND lenses_briefed_with_dedup_set == true",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "null-results-recorded": {
                    "predicate": "custom-expression",
                    "expression": "lenses_returning_nothing_without_search_surface == 0",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "repair",
                },
            },
            "stages": [
                {
                    "id": "ground",
                    "title": "Enumerate what already exists so no lens can re-propose it",
                    "kind": "task",
                    "role": "grounding-agent",
                    "checkpoint": True,
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPG-0101",
                        title="Build the dedup set from the already-built inventory and the estate itself",
                        phase="2B",
                        target=(
                            "Produce the dedup set: every capability that already exists in scope, with "
                            "the path or identifier that proves it. This set is injected into every "
                            "lens brief, so a lens proposing an existing capability is a defect, not a "
                            "duplicate to filter later."
                        ),
                        inputs=["params.scope", "params.already_built_inventory"],
                        deps=[],
                        role="grounding-agent",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/sweeps/**)",
                        ],
                        substrate="local-single",
                        timeout=2400,
                        out_path=f"{root}/dedup-set.json",
                        out_schema=S("capability-index"),
                        evidence="every row carries the path or identifier that proves the capability exists; a row with no locator is dropped and the drop is recorded",
                        tests=[
                            "MANDATORY dedup control: a KNOWN-BUILT item must appear in the dedup set; if it does not, the merge that justifies this blueprint has failed",
                            "a missing already_built_inventory must FAIL this stage, never yield an empty dedup set that silently permits every proposal",
                        ],
                        reviewer="the synthesiser rejects any candidate that string- or semantically matches a dedup-set row and records the match",
                        postcondition="the dedup set exists, is non-empty, and every row carries a locator",
                        retry="two strikes then pivot: after two attempts, ask the owner for the inventory rather than proceeding without one",
                        failure_classes=["inventory-missing", "detector-truncation"],
                        mechanism="dedup-grounding-before-discovery",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/dedup-set.json",
                            S("capability-index"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPG-0101",
                            consumers=["grounding-gate", "lens-fanout", "synthesise"],
                        )
                    ],
                },
                {
                    "id": "grounding-gate",
                    "title": "No lens launches until the dedup set exists and is in every brief",
                    "kind": "gate",
                    "depends_on": ["ground"],
                    "gate_ref": "grounding-present",
                },
                {
                    "id": "lens-fanout",
                    "title": "Fan out the lens roster, staggered, each blind to its siblings",
                    "kind": "fanout",
                    "depends_on": ["grounding-gate"],
                    "over": {
                        "source": "param",
                        "ref": "lens_roster",
                        "item_var": "lens",
                        "key_field": "lens",
                    },
                    "max_concurrency": 12,
                    "arrival_stagger_ms": 500,
                    "max_items": 80,
                    "on_item_failure": "quarantine",
                    "body": [
                        {
                            "id": "run-lens",
                            "title": "Run one discovery lens against the dedup set",
                            "kind": "task",
                            "role": "discovery-lens",
                            "timeout_seconds": 3000,
                            "cache": B.cache_block(
                                f"{root}/cache/lenses",
                                ["stage_id", "item_key", "params_hash", "model_id"],
                                ttl=604800,
                            ),
                            "work_unit": B.wu(
                                uid="BPG-0102",
                                title="Emit candidates for one lens, or a null result naming the surface searched",
                                phase="2B",
                                target=(
                                    "For the assigned lens, emit candidates that are NOT in the dedup "
                                    "set, each with an external anchor or a file:line. A lens that finds "
                                    "nothing emits a NULL RESULT naming the surface it searched - "
                                    "absence of evidence must be attributable to a search."
                                ),
                                inputs=[f"{root}/dedup-set.json", "params.scope"],
                                deps=["BPG-0101"],
                                role="discovery-lens",
                                tools=[
                                    "Read",
                                    "Grep",
                                    "Glob",
                                    "WebSearch",
                                    "WebFetch",
                                    "mcp__search-hub__web_search_exa",
                                    "mcp__search-hub__firecrawl_search",
                                    "mcp__searxng__searxng_web_search",
                                    "mcp__github__search_repositories",
                                    "Write(command-center/sweeps/**)",
                                ],
                                substrate="local-parallel",
                                timeout=3000,
                                out_path=f"{root}/lenses/lens-candidates.json",
                                out_schema=S("gem-candidate"),
                                evidence="every candidate carries an external URL or a file:line plus its licence where third-party; a null result carries the queries run",
                                tests=[
                                    "a lens pointed at a KNOWN-BUILT item must return it as deduped, never as a new candidate",
                                    "a lens with nothing to report must emit a null result with its search surface, not an empty file",
                                ],
                                reviewer="the anti-overfit gate subworkflow judges every survivor; this lens does not judge its own candidates",
                                postcondition="the lens file exists, parses, and each candidate has an anchor or the file is an explicit null result",
                                retry="two strikes then pivot: after two failures, record the lens as a null result with the failure attached",
                                failure_classes=[
                                    "engine-unreachable",
                                    "quota-exhausted",
                                    "partial-artifact",
                                ],
                                mechanism="independent-discovery-lens",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/lenses/lens-candidates.json",
                                    S("gem-candidate"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPG-0102",
                                    consumers=["synthesise"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "quorum",
                        "quorum": 0.7,
                        "on_partial": "proceed-degraded",
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "codex-arm",
                    "title": "Optional S1b: a cross-vendor Codex lens set",
                    "kind": "task",
                    "depends_on": ["lens-fanout"],
                    "when": "include_codex_arm == true",
                    "role": "codex-lens",
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPG-0103",
                        title="Run a cross-vendor lens set with the prompt passed BY FILE",
                        phase="2B",
                        target=(
                            "Dispatch a Codex lens set for the same scope, prompt passed BY FILE and "
                            "blocking, and mark every candidate no in-vendor lens produced. Exit 0 "
                            "alone is SEVERED, not success: the result must also be a non-empty "
                            "schema-valid file."
                        ),
                        inputs=[f"{root}/dedup-set.json", "params.scope"],
                        deps=["BPG-0101"],
                        role="codex-lens",
                        tools=[
                            "Read",
                            "mcp__codex__codex",
                            "Write(command-center/sweeps/**)",
                        ],
                        substrate="cross-vendor-codex",
                        timeout=2400,
                        out_path=f"{root}/codex-candidates.json",
                        out_schema=S("gem-candidate"),
                        evidence="the dispatch records exit code, the output file path, its byte count and its schema verdict - all three, because exit 0 alone is not a result",
                        tests=[
                            "a prompt above the Windows command-line limit must go by FILE and succeed, not fail with an argument-length error",
                            "a killed peer must produce a terminal FAILED marker with the diagnostic tail, never silence",
                        ],
                        reviewer="the synthesiser marks cross-vendor-only candidates explicitly so their independence is visible in the queue",
                        postcondition="exit 0 AND a non-empty output file AND a schema-valid parse - or a terminal FAILED marker",
                        model="gpt-5-codex",
                        vendor="openai",
                        basis="cross-vendor discovery: independent failure modes, not extra headcount",
                        retry="two strikes then pivot: retry ONCE ignoring user config on an argument-limit failure, then stop",
                        failure_classes=[
                            "win-arg-limit",
                            "severed-stream",
                            "codex-exit-nonzero",
                        ],
                        mechanism="cross-vendor-lens-arm",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/codex-candidates.json",
                            S("gem-candidate"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPG-0103",
                            consumers=["synthesise"],
                        )
                    ],
                },
                {
                    "id": "null-result-gate",
                    "title": "A silent lens is a defect: every empty lens must name its search surface",
                    "kind": "gate",
                    "depends_on": ["codex-arm"],
                    "gate_ref": "null-results-recorded",
                },
                {
                    "id": "synthesise",
                    "title": "Merge and dedupe the lens output against the grounding set",
                    "kind": "task",
                    "depends_on": ["null-result-gate"],
                    "role": "synthesiser",
                    "timeout_seconds": 3000,
                    "work_unit": B.wu(
                        uid="BPG-0104",
                        title="Produce one deduped candidate list with per-candidate provenance and lens attribution",
                        phase="2B",
                        target=(
                            "Merge every lens output into one list: dedupe against the grounding set "
                            "AND against sibling lenses, attribute each survivor to the lenses that "
                            "found it, and add nothing no lens produced."
                        ),
                        inputs=[
                            f"{root}/lenses/lens-candidates.json",
                            f"{root}/codex-candidates.json",
                            f"{root}/dedup-set.json",
                        ],
                        deps=["BPG-0102", "BPG-0103"],
                        role="synthesiser",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/sweeps/**)",
                        ],
                        substrate="local-single",
                        timeout=3000,
                        out_path=f"{root}/candidates.json",
                        out_schema=S("synthesis-candidate"),
                        evidence="each survivor names every lens that produced it and its anchor; each dedup drop names the grounding row or sibling it matched",
                        tests=[
                            "MANDATORY: a candidate identical to a dedup-set row must be dropped with the matched row named - this is the measurement that the merge works",
                            "a candidate the synthesiser invented (no lens attribution) must be rejected",
                        ],
                        reviewer="an adversarial reviewer receives the siblings' FULL lens text, not the digest, and checks for a survivor that duplicates a dropped one",
                        postcondition="the candidate list exists, parses, every survivor has at least one lens attribution, and every drop names its match",
                        retry="two strikes then pivot: after two failures emit the partial list plus the unmerged lens files",
                        failure_classes=[
                            "overclaim",
                            "partial-artifact",
                            "duplicate-proposal",
                        ],
                        mechanism="dedup-against-grounding-and-siblings",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/candidates.json",
                            S("synthesis-candidate"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPG-0104",
                            consumers=["judge-candidates", "tier-queue"],
                        )
                    ],
                },
                {
                    "id": "judge-candidates",
                    "title": "Delegate adopt / build / prune to the anti-overfit gate (a subworkflow, not a copy)",
                    "kind": "subworkflow",
                    "depends_on": ["synthesise"],
                    "workflow": {
                        "workflow_id": "bp-gem-02-anti-overfit-candidate-gate",
                        "version_range": ">=1.0.0 <2.0.0",
                    },
                    "params": {"delegated_from": "bp-gem-01-wide-lens-gem-sweep"},
                    "isolation": "none",
                    "propagate_failure": True,
                    "timeout_seconds": 3600,
                },
                {
                    "id": "tier-queue",
                    "title": "Build the owner-consumable tiered decision queue",
                    "kind": "task",
                    "depends_on": ["judge-candidates"],
                    "role": "queue-builder",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0105",
                        title="Emit the T0-T3 decision queue with one actionable line per candidate",
                        phase="2B",
                        target=(
                            "Turn the judged candidates into a decision queue: T0-T3 tier, the "
                            "adopt/build/prune verdict with its reason code, the effort estimate, and "
                            "whether it fits the absorption budget. Prose is not a deliverable here; "
                            "the queue is."
                        ),
                        inputs=[f"{root}/candidates.json", "params.absorption_budget"],
                        deps=["BPG-0104"],
                        role="queue-builder",
                        tools=["Read", "Write(command-center/sweeps/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/decision-queue.json",
                        out_schema=S("disposition-table"),
                        evidence="every row carries tier, verdict, reason code and budget-fit; the count of rows above the budget is stated numerically",
                        tests=[
                            "a queue with more T0 items than the absorption budget must state the overflow explicitly rather than silently truncating",
                        ],
                        reviewer="the owner reads the queue; a queue longer than the budget with no overflow statement is rejected",
                        postcondition="the queue exists, parses, and reconciles its T0 count against the absorption budget",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["overclaim", "partial-artifact"],
                        mechanism="tiered-decision-queue",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/decision-queue.json",
                            S("disposition-table"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPG-0105",
                            consumers=["owner-review"],
                        )
                    ],
                },
                {
                    "id": "owner-review",
                    "title": "Owner accepts the queue and confirms the absorption budget",
                    "kind": "human_checkpoint",
                    "depends_on": ["tier-queue"],
                    "prompt": (
                        "The sweep produced a tiered decision queue. Accept it as the cycle's build "
                        "list, trim it to the absorption budget, or reject the sweep. Discovery beyond "
                        "what the estate will absorb becomes a backlog, so an over-budget queue needs "
                        "an explicit decision."
                    ),
                    "approvers": ["owner"],
                    "approval_mode": "owner-only",
                    "timeout_seconds": 86400,
                    "on_timeout": "proceed",
                    "owner_approval_required": True,
                    "options": ["accept-queue", "trim-to-budget", "reject-sweep"],
                    "decision_artifact": B.artifact(
                        f"{root}/owner-decision.json",
                        S("decision-record"),
                        min_bytes=128,
                        consumers=["command-center/DECISION-LOG.json"],
                    ),
                },
            ],
            "stopping_rules": [
                {
                    "id": "marginal-lens-zero-survivors",
                    "expression": "surviving_candidates_from_last_three_lenses == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "lenses_returned >= 6",
                    "on_stop": "complete",
                },
                {
                    "id": "roster-exhausted",
                    "expression": "lenses_remaining == 0",
                    "applies_to": "workflow",
                    "on_stop": "complete",
                },
                {
                    "id": "absorption-budget-saturated",
                    "expression": "t0_candidates >= 3 AND surviving_candidates_from_last_three_lenses == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "lenses_returned >= 6",
                    "on_stop": "complete",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                3,
                escalate_to="synthesise",
                retry_on=["engine-unreachable", "quota-exhausted", "severed-stream"],
            ),
            "failure_policy": B.failure(
                "degrade-loudly",
                [
                    "engine-unreachable",
                    "quota-exhausted",
                    "duplicate-proposal",
                    "partial-artifact",
                ],
                escalate_to="owner-review",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="fanout-item",
                keys=[
                    "workflow_id",
                    "workflow_version",
                    "stage_id",
                    "item_key",
                    "params_hash",
                ],
            ),
            "replay": B.replay_not_deterministic(),
            "cache": B.cache_block(
                f"{root}/cache",
                ["workflow_version", "stage_id", "item_key", "params_hash", "model_id"],
                ttl=604800,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "WebSearch",
                    "WebFetch",
                    "mcp__codex__codex",
                    "mcp__search-hub__firecrawl_search",
                    "Write(command-center/sweeps/**)",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(2400, 9000, 28800),
                tokens=(1500000, 6000000, 20000000),
                tool_calls=(400, 3000),
                cost=(12.0, 45.0, 160.0),
                risk="low",
                reversibility="reversible",
                blast_radius="DISCOVERY ONLY: no write permission outside command-center/sweeps/**; that separation is what makes a 40-agent sweep safe",
                confidence="roughly-even",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-gem-01.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "wf-saved-workspace-gem-hunt",
                        "relation": "MERGE",
                        "license": "owner-proprietary",
                        "credit": "owner (~40-lens roster, opus pinning, codex arm, resume)",
                    },
                    {
                        "source": "wf-saved-harness-self-improve-sweep",
                        "relation": "MERGE",
                        "license": "owner-proprietary",
                        "credit": "owner (the dedup GROUNDING stage and T0-T3 tiering)",
                    },
                    {
                        "source": "skills/gem-hunt",
                        "relation": "ADOPT-WITH-WRAPPER",
                        "license": "owner-proprietary",
                        "credit": "owner (invocation surface, adopt/prune vocabulary)",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-GEM-01",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=[
                    "wf-saved-workspace-gem-hunt",
                    "wf-saved-harness-self-improve-sweep",
                ],
            ),
            "outputs": {
                "decision-queue": B.artifact(
                    f"{root}/decision-queue.json",
                    S("disposition-table"),
                    min_bytes=512,
                    consumers=["owner-review", "command-center/DECISION-LOG.json"],
                ),
                "candidates": B.artifact(
                    f"{root}/candidates.json",
                    S("synthesis-candidate"),
                    min_bytes=512,
                    consumers=["bp-gem-02-anti-overfit-candidate-gate"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-GEM-01", 468),
                "acquisition_route_from_card": "MERGE",
                "mechanism_signature": [
                    "dedup-grounding-before-discovery",
                    "wide-independent-lens-fanout",
                    "null-result-with-search-surface",
                    "cross-vendor-lens-arm",
                    "judgement-delegated-to-a-subworkflow",
                    "absorption-budget-bounded-queue",
                ],
                "contraindications": [
                    "NOT for interrogating one existing plan - that is a requirements grill",
                    "NOT for ordinary topic research - that is BP-RES-01",
                    "NOT when the estate cannot absorb more surface: discovery without an absorption budget manufactures a backlog",
                ],
                "why_not_a_duplicate_of_bp_gem_02": (
                    "This blueprint DISCOVERS and produces a candidate list; BP-GEM-02 only JUDGES a "
                    "list it did not produce. The relationship is composition, not overlap: the "
                    "judge-candidates stage CALLS BP-GEM-02 as a subworkflow rather than "
                    "reimplementing its anchor and budget checks."
                ),
                "unverified": [
                    "UNVERIFIED post-merge; settling experiment = re-run both source workflows and the "
                    "merged form on the same scope and count DUPLICATE-of-already-built proposals - the "
                    "merged form should approach zero, and the dedup control test is the floor.",
                ],
                "owner_decision": "Merge the two source sweeps into this one canonical form, or keep the narrow 14-lens variant as a cheap mode?",
                "worked_example": {
                    "name": "sweep for missing harness capabilities with 8 lenses",
                    "params": {
                        "scope": "capabilities the agent harness is missing relative to comparable frontier tooling",
                        "lens_roster": [
                            "external-sota-scan",
                            "adjacent-tool-parity",
                            "internal-gap-from-failures",
                            "rule-derived-gaps",
                            "marketplace-scan",
                            "executed-corpus-mine",
                            "vendor-changelog-delta",
                            "practitioner-forum",
                        ],
                        "already_built_inventory": "command-center/CAPABILITY-INVENTORY.json",
                        "absorption_budget": 6,
                        "include_codex_arm": True,
                    },
                    "expected_stage_order": [
                        "ground",
                        "grounding-gate",
                        "lens-fanout",
                        "codex-arm",
                        "null-result-gate",
                        "synthesise",
                        "judge-candidates",
                        "tier-queue",
                        "owner-review",
                    ],
                    "expected_skipped": [],
                    "expected_max_parallel": 12,
                    "expected_gate_ids": ["grounding-gate", "null-result-gate"],
                    "acceptance": [
                        "a known-built item is deduped by the grounding stage, not re-proposed",
                        "every lens that found nothing carries its search surface",
                        "the queue states its T0 overflow against the budget of 6",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "marginal-lens-zero-survivors",
                            "why": "the floor stops an early barren lens from ending a sweep before six lenses have returned",
                            "fires_on": {
                                "surviving_candidates_from_last_three_lenses": 0,
                                "lenses_returned": 8,
                                "lenses_remaining": 2,
                                "t0_candidates": 4,
                            },
                            "does_not_fire_on": {
                                "surviving_candidates_from_last_three_lenses": 0,
                                "lenses_returned": 3,
                                "lenses_remaining": 5,
                                "t0_candidates": 4,
                            },
                        },
                        {
                            "rule": "roster-exhausted",
                            "why": "the sweep ends when the roster is spent even if candidates were still arriving",
                            "fires_on": {
                                "surviving_candidates_from_last_three_lenses": 2,
                                "lenses_returned": 8,
                                "lenses_remaining": 0,
                                "t0_candidates": 4,
                            },
                            "does_not_fire_on": {
                                "surviving_candidates_from_last_three_lenses": 2,
                                "lenses_returned": 8,
                                "lenses_remaining": 3,
                                "t0_candidates": 4,
                            },
                        },
                    ],
                },
            },
        }
    )


# --------------------------------------------------------------- 8. BP-GEM-02

_G2_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "Bash:python",
    "Write(command-center/decisions/**)",
]


def _gem02() -> dict[str, Any]:
    root = "command-center/decisions/bp-gem-02"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-gem-02-anti-overfit-candidate-gate",
            "name": "Anti-Overfit Candidate Gate",
            "description": (
                "Given ANY candidate list - from a sweep, a council, a marketplace, a reviewer - "
                "decide ADOPT / BUILD / PRUNE / DEFER against a fixed rejected-architecture list, a "
                "dedup set and an absorption budget, WITHOUT re-running discovery. Stages S0-S3 are "
                "deterministic set arithmetic; only the ambiguous residue reaches a model. The "
                "signature property is fail-closed on a blank required input: a missing or empty "
                "already-built inventory makes the gate REFUSE to run rather than pass everything, "
                "because a required-but-blank field defaults to worst case, not to 'probably fine'. "
                "Its tool policy denies every discovery tool: this blueprint may judge, never search."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": [
                "collective-intelligence-and-meta",
                "security-governance-and-risk",
            ],
            "tags": ["deterministic-gate", "fail-closed", "absorption-budget"],
            "flagship": True,
            "params": {
                "candidates": {
                    "type": "path",
                    "required": True,
                    "description": "The candidate list under judgement; this gate never produces one",
                },
                "already_built_inventory": {
                    "type": "path",
                    "required": True,
                    "description": (
                        "Required. An absent or EMPTY inventory makes the gate refuse: passing every "
                        "candidate because the dedup set is missing is the fail-open this exists to prevent."
                    ),
                },
                "rejected_components": {
                    "type": "array",
                    "required": True,
                    "min_items": 1,
                    "max_items": 100,
                    "items": {"type": "string", "min_length": 3},
                    "description": "Rejected ARCHITECTURES (a second orchestration runtime, a vector-DB memory, a durable-execution engine, a trained critic, observability SaaS, a guardrail framework) - not unfamiliar ideas",
                },
                "absorption_budget": {
                    "type": "integer",
                    "required": True,
                    "minimum": 0,
                    "maximum": 200,
                    "description": "A HARD cap on ADOPT+BUILD verdicts, not a suggestion",
                },
                "owner_override_register": {
                    "type": "path",
                    "default": "command-center/decisions/anchor-overrides.json",
                    "description": "Optional S1b: where a knowingly-accepted anchor violation is recorded",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "gate-runner": {
                    "description": "Runs the deterministic set arithmetic; has judge authority precisely because it exercises no judgement",
                    "vendor": "any",
                    "effort": "low",
                    "authority": "judge",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/decisions/**)",
                    ],
                    "speaking_rights": "always",
                },
                "adjudicator": {
                    "description": "Sees ONLY the ambiguous residue the deterministic stages could not decide, and must give a reason code per ruling",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "voting",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/decisions/**)",
                    ],
                    "speaking_rights": "on-request",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_G2_ALLOW),
                "deny": [
                    "Bash",
                    "WebSearch",
                    "WebFetch",
                    "mcp__search-hub__web_search_exa",
                    "mcp__searxng__searxng_web_search",
                    "mcp__github__search_repositories",
                    "mcp__codex__codex",
                ],
                "network": "none",
                "write_paths": ["command-center/decisions/**"],
                "forbid_write_paths": [
                    "platform/**",
                    "command-center/WORK-UNIT-CATALOG.json",
                ],
                "source_policy": {
                    "offline_only": True,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "cost-aware",
                "default": {
                    "model": "none-deterministic-script",
                    "vendor": "mixed",
                    "effort": "low",
                },
                "routes": [
                    {
                        "when": "stage_role == 'adjudicator'",
                        "target": {
                            "model": "opus",
                            "vendor": "anthropic",
                            "effort": "high",
                        },
                        "reason": "only the ambiguous residue is worth a model; the rest is set arithmetic",
                    }
                ],
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "inputs-complete": {
                    "predicate": "custom-expression",
                    "expression": (
                        "already_built_inventory_rows > 0 AND rejected_components_declared > 0 "
                        "AND absorption_budget_declared == true AND candidate_rows > 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "budget-respected": {
                    "predicate": "custom-expression",
                    "expression": "adopt_plus_build_verdicts <= absorption_budget AND verdicts_without_reason_code == 0",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
            },
            "stages": [
                {
                    "id": "input-completeness-gate",
                    "title": "FAIL CLOSED: refuse to run on a blank required input",
                    "kind": "gate",
                    "gate_ref": "inputs-complete",
                },
                {
                    "id": "dedup",
                    "title": "S0 deterministic dedup against the already-built set",
                    "kind": "task",
                    "depends_on": ["input-completeness-gate"],
                    "role": "gate-runner",
                    "timeout_seconds": 600,
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/decisions/**)",
                    ],
                    "work_unit": B.wu(
                        uid="BPG-0201",
                        title="Mark every candidate that already exists, by exact and normalised name match",
                        phase="2B",
                        target=(
                            "Compare each candidate against the already-built inventory by exact match "
                            "and by a normalised form (case, separators, common suffixes). A match is "
                            "PRUNE with reason code DUPLICATE-OF-BUILT naming the matched row."
                        ),
                        inputs=["params.candidates", "params.already_built_inventory"],
                        deps=[],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/dedup-verdicts.json",
                        out_schema=S("dedup-report"),
                        evidence="every PRUNE names the inventory row it matched and the match kind (exact / normalised); the comparison is a script, not a judgement",
                        tests=[
                            "MANDATORY: a candidate identical to a built item must be PRUNED with the matched row named",
                            "both-states: a genuinely new candidate in the same list must survive - a deduper that prunes everything is as broken as one that prunes nothing",
                        ],
                        reviewer="the anchor stage re-reads the survivors only; a pruned candidate is not re-litigated by a model",
                        postcondition="every candidate has a dedup outcome and every PRUNE names its matched row and match kind",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="set membership is exactly computable; an LLM comparison here measured 86 percent accurate with 100 percent of errors in the unsafe direction",
                        retry="none: a deterministic comparison over unchanged inputs cannot produce a different result",
                        failure_classes=["inventory-missing", "schema-invalid"],
                        mechanism="deterministic-set-dedup",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/dedup-verdicts.json",
                            S("dedup-report"),
                            sentinel="SUCCESS:BPG-0201",
                            consumers=["anchor-check"],
                        )
                    ],
                },
                {
                    "id": "anchor-check",
                    "title": "S1 anti-overfit anchor: reject a rejected ARCHITECTURE, not an unfamiliar idea",
                    "kind": "task",
                    "depends_on": ["dedup"],
                    "role": "gate-runner",
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPG-0202",
                        title="Prune any survivor that reintroduces a declared rejected architecture",
                        phase="2B",
                        target=(
                            "Check each surviving candidate against the rejected_components list. A "
                            "match is PRUNE with reason code ANCHOR-VIOLATION naming the component. "
                            "Unfamiliarity is NOT a reason: the list is of rejected architectures, not "
                            "of ideas the estate has not seen before."
                        ),
                        inputs=[
                            f"{root}/dedup-verdicts.json",
                            "params.rejected_components",
                        ],
                        deps=["BPG-0201"],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/anchor-verdicts.json",
                        out_schema=S("option-closure"),
                        evidence="every ANCHOR-VIOLATION names the rejected component matched and quotes the candidate text that matched it",
                        tests=[
                            "MANDATORY: a candidate proposing a vector-DB memory must be PRUNED with the anchor named",
                            "a merely UNFAMILIAR candidate must NOT be pruned by this stage - that would make the anchor a novelty filter",
                        ],
                        reviewer="the owner override register is the only route to accept a known anchor violation, and it records who accepted it",
                        postcondition="every survivor has an anchor outcome and every violation names its component plus the matching text",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="a declared list plus text matching; judgement enters only at the residue stage",
                        retry="none: deterministic matching over unchanged inputs",
                        failure_classes=["anchor-list-missing", "schema-invalid"],
                        mechanism="rejected-architecture-anchor-match",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/anchor-verdicts.json",
                            S("option-closure"),
                            sentinel="SUCCESS:BPG-0202",
                            consumers=["bus-check"],
                        )
                    ],
                },
                {
                    "id": "bus-check",
                    "title": "S2 bus check: does it ride the existing hook / skill / MCP bus, or demand a new runtime?",
                    "kind": "task",
                    "depends_on": ["anchor-check"],
                    "role": "gate-runner",
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPG-0203",
                        title="Classify each survivor by the bus it needs and downgrade a bus-less ADOPT to DEFER",
                        phase="2B",
                        target=(
                            "For each survivor decide which existing bus carries it - hook, skill, MCP, "
                            "CLI, or NONE. A candidate that needs a bus the estate does not have is "
                            "downgraded to DEFER with the missing bus NAMED, never adopted on the "
                            "assumption the bus will appear."
                        ),
                        inputs=[f"{root}/anchor-verdicts.json"],
                        deps=["BPG-0202"],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Bash:python",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/bus-verdicts.json",
                        out_schema=S("compatibility-matrix"),
                        evidence="each row names the carrying bus and the file or config that proves the bus exists; a DEFER names the missing bus",
                        tests=[
                            "a candidate needing a bus the estate lacks must be DEFER with that bus named, not ADOPT",
                            "both-states: a candidate riding an existing MCP must be allowed through with the proving locator recorded",
                        ],
                        reviewer="the budget stage cannot promote a DEFER back to ADOPT; only the owner override register can",
                        postcondition="every survivor names its bus, with a locator when the bus exists and a name when it does not",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="bus presence is a filesystem and config fact, not an opinion",
                        retry="none: deterministic inspection over unchanged inputs",
                        failure_classes=["bus-undetermined", "schema-invalid"],
                        mechanism="existing-bus-or-defer",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/bus-verdicts.json",
                            S("compatibility-matrix"),
                            sentinel="SUCCESS:BPG-0203",
                            consumers=["budget-fit"],
                        )
                    ],
                },
                {
                    "id": "budget-fit",
                    "title": "S3 absorption budget: a hard cap, not a suggestion",
                    "kind": "task",
                    "depends_on": ["bus-check"],
                    "role": "gate-runner",
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPG-0204",
                        title="Fit the survivors into the absorption budget and DEFER the overflow explicitly",
                        phase="2B",
                        target=(
                            "Rank the survivors and admit at most absorption_budget of them as ADOPT or "
                            "BUILD. Everything above the line becomes DEFER with reason code "
                            "BUDGET-OVERFLOW and its rank recorded, so nothing is silently dropped."
                        ),
                        inputs=[
                            f"{root}/bus-verdicts.json",
                            "params.absorption_budget",
                        ],
                        deps=["BPG-0203"],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/budget-fit.json",
                        out_schema=S("intervention-ranking"),
                        evidence="the artifact states the budget, the admitted count and the overflow count numerically, and every overflow row carries its rank",
                        tests=[
                            "with budget 0 every survivor must be DEFER with BUDGET-OVERFLOW - a budget of zero must be honoured, not treated as unset",
                            "the admitted count must never exceed the budget",
                        ],
                        reviewer="the budget gate recomputes the admitted count independently of this stage's own claim",
                        postcondition="admitted count is at most the budget, and every overflow row carries a rank and the BUDGET-OVERFLOW reason code",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="counting and ranking are exactly computable",
                        retry="none: deterministic arithmetic over unchanged inputs",
                        failure_classes=["budget-undeclared", "schema-invalid"],
                        mechanism="hard-absorption-budget-cap",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/budget-fit.json",
                            S("intervention-ranking"),
                            sentinel="SUCCESS:BPG-0204",
                            consumers=[
                                "residue-adjudication",
                                "budget-gate",
                                "emit-verdicts",
                            ],
                        )
                    ],
                },
                {
                    "id": "residue-adjudication",
                    "title": "The ONLY model-judged stage: the ambiguous residue",
                    "kind": "task",
                    "depends_on": ["budget-fit"],
                    "when": "ambiguous_residue > 0",
                    "role": "adjudicator",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0205",
                        title="Rule on the candidates the deterministic stages could not decide",
                        phase="2B",
                        target=(
                            "For each candidate the deterministic stages left ambiguous - a near-match "
                            "that may be a genuinely new variant, a bus that half exists - rule "
                            "ADOPT / BUILD / PRUNE / DEFER with a reason code, and say which "
                            "deterministic stage was ambiguous and why."
                        ),
                        inputs=[
                            f"{root}/budget-fit.json",
                            f"{root}/dedup-verdicts.json",
                        ],
                        deps=["BPG-0204"],
                        role="adjudicator",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/residue-rulings.json",
                        out_schema=S("adjudication-record"),
                        evidence="each ruling names the ambiguous stage, the competing readings, and the reason code chosen",
                        tests=[
                            "a semantic near-match that is a genuinely new variant must be allowed through with the difference stated - a deduper that prunes every variant ossifies the estate",
                            "the adjudicator must not touch a candidate the deterministic stages already decided",
                        ],
                        reviewer="one independent reviewer checks no deterministic verdict was overturned here",
                        postcondition="every ambiguous candidate has a ruling with a reason code, and no unambiguous candidate was re-decided",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["ambiguity-unresolvable", "overclaim"],
                        mechanism="residue-only-model-judgement",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/residue-rulings.json",
                            S("adjudication-record"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPG-0205",
                            consumers=["emit-verdicts"],
                        )
                    ],
                },
                {
                    "id": "budget-gate",
                    "title": "Every verdict has a reason code and the budget was not exceeded",
                    "kind": "gate",
                    "depends_on": ["residue-adjudication"],
                    "gate_ref": "budget-respected",
                },
                {
                    "id": "emit-verdicts",
                    "title": "Emit the reason-coded verdict table",
                    "kind": "task",
                    "depends_on": ["budget-gate"],
                    "role": "gate-runner",
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPG-0206",
                        title="Reduce every stage outcome to one verdict per candidate with its reason code",
                        phase="2B",
                        target=(
                            "Produce one row per input candidate: verdict, reason code, the stage that "
                            "decided it, and the anchor or inventory row it matched where relevant. The "
                            "row count must equal the input candidate count exactly."
                        ),
                        inputs=[
                            f"{root}/budget-fit.json",
                            f"{root}/residue-rulings.json",
                            "params.candidates",
                        ],
                        deps=["BPG-0204", "BPG-0205"],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/decisions/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/verdicts.json",
                        out_schema=S("disposition-table"),
                        evidence="the artifact reconciles its row count against the input candidate count and states the per-verdict tallies numerically",
                        tests=[
                            "the verdict row count must equal the input candidate count - a dropped candidate is a defect, not a filter",
                            "every row must carry a reason code; a verdict without one is invalid",
                        ],
                        reviewer="the calling workflow reads this table; a row count mismatch is a hard reject",
                        postcondition="one verdict per input candidate, each with a reason code, reconciled against the input count",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="a deterministic reduction over the stage outcomes",
                        retry="none: deterministic reduction over unchanged inputs",
                        failure_classes=["schema-invalid", "count-mismatch"],
                        mechanism="reason-coded-verdict-reduction",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/verdicts.json",
                            S("disposition-table"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPG-0206",
                            consumers=[
                                "bp-gem-01-wide-lens-gem-sweep",
                                "command-center/DECISION-LOG.json",
                            ],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "candidate-list-exhausted",
                    "expression": "candidates_without_verdict == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "candidate_rows > 0",
                    "on_stop": "complete",
                },
                {
                    "id": "refuse-on-blank-input",
                    "expression": "already_built_inventory_rows == 0 OR rejected_components_declared == 0",
                    "applies_to": "workflow",
                    "on_stop": "escalate",
                },
            ],
            "retry_policy": B.retry_none(),
            "failure_policy": B.failure(
                "fail-fast",
                [
                    "inventory-missing",
                    "budget-undeclared",
                    "count-mismatch",
                    "ambiguity-unresolvable",
                ],
                escalate_to="the calling workflow",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="stage",
                keys=["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
            ),
            "replay": B.replay_deterministic(
                20260810, f"{root}/replay/journal.jsonl", verify="hash-equal"
            ),
            "cache": B.cache_block(
                f"{root}/cache",
                ["workflow_version", "stage_id", "inputs_hash"],
                ttl=604800,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                ["Bash:python", "Write(command-center/decisions/**)"],
                emits=["plan", "estimate", "permission-report", "artifact-diff"],
            ),
            "estimate": B.estimate_block(
                wallclock=(60, 300, 1800),
                tokens=(10000, 60000, 250000),
                tool_calls=(15, 120),
                cost=(0.05, 0.3, 1.5),
                risk="low",
                reversibility="reversible",
                blast_radius="judgement only: no discovery tool is reachable and no write leaves command-center/decisions/bp-gem-02/**",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-gem-02.bundle.json",
                includes=[
                    "definition",
                    "tests",
                    "examples",
                    "lineage",
                    "replay-journal",
                ],
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "exec-gem-hunt-2026-06-30",
                        "relation": "DISTILL",
                        "license": "owner-proprietary",
                        "credit": "owner (the anchor stage existed only inside that run)",
                    },
                    {
                        "source": "wf-saved-harness-self-improve-sweep",
                        "relation": "DISTILL",
                        "license": "owner-proprietary",
                        "credit": "owner (T0-T3 tiering vocabulary)",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-GEM-02",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ]
            ),
            "outputs": {
                "verdicts": B.artifact(
                    f"{root}/verdicts.json",
                    S("disposition-table"),
                    min_bytes=256,
                    consumers=[
                        "bp-gem-01-wide-lens-gem-sweep",
                        "command-center/DECISION-LOG.json",
                    ],
                )
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-GEM-02", 512),
                "acquisition_route_from_card": "DISTILL",
                "mechanism_signature": [
                    "fail-closed-on-blank-required-input",
                    "deterministic-set-dedup",
                    "rejected-architecture-anchor-match",
                    "existing-bus-or-defer",
                    "hard-absorption-budget-cap",
                    "residue-only-model-judgement",
                    "reason-coded-verdict-reduction",
                ],
                "contraindications": [
                    "NOT a discovery stage - it never searches, and its tool policy denies every search tool",
                    "NOT for candidates whose value is unknown - send those to a probe first",
                    "do NOT use it to reject a candidate merely because it is unfamiliar: the list is of rejected ARCHITECTURES",
                ],
                "why_not_a_duplicate_of_bp_gem_01": (
                    "BP-GEM-01 discovers; this only judges - and can judge lists it did not produce "
                    "(a council's options, a marketplace listing, a reviewer's suggestions). It is "
                    "called BY BP-GEM-01 as a subworkflow, which is why neither reimplements the other."
                ),
                "unverified": [
                    "UNVERIFIED whether standalone use changes any verdict; settling experiment = apply "
                    "it to the last three candidate lists produced in this estate and count changed verdicts.",
                ],
                "owner_decision": "What is the absorption budget per cycle, and who curates rejected_components so the anchor does not ossify?",
                "worked_example": {
                    "name": "judge a 40-candidate sweep output against a budget of 6",
                    "params": {
                        "candidates": "command-center/sweeps/bp-gem-01/candidates.json",
                        "already_built_inventory": "command-center/CAPABILITY-INVENTORY.json",
                        "rejected_components": [
                            "second orchestration runtime",
                            "vector-DB or knowledge-graph memory",
                            "durable-execution engine",
                            "trained critic model",
                            "observability SaaS",
                            "guardrail framework",
                        ],
                        "absorption_budget": 6,
                    },
                    "facts": {"ambiguous_residue": 4},
                    "expected_stage_order": [
                        "input-completeness-gate",
                        "dedup",
                        "anchor-check",
                        "bus-check",
                        "budget-fit",
                        "residue-adjudication",
                        "budget-gate",
                        "emit-verdicts",
                    ],
                    "expected_skipped": [],
                    "expected_max_parallel": 1,
                    "expected_gate_ids": ["input-completeness-gate", "budget-gate"],
                    "fact_variants": [
                        {"facts": {"ambiguous_residue": 4}, "expected_skipped": []},
                        {
                            "facts": {"ambiguous_residue": 0},
                            "expected_skipped": ["residue-adjudication"],
                        },
                    ],
                    "acceptance": [
                        "a candidate identical to a built item is PRUNED by S0 with the matched row named",
                        "a candidate proposing a vector store is PRUNED by S1 with the anchor named",
                        "an EMPTY already_built_inventory makes the gate REFUSE, not pass everything",
                        "the ADOPT+BUILD count never exceeds 6",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "candidate-list-exhausted",
                            "why": "the floor stops an empty candidate list from reading as a completed judgement",
                            "fires_on": {
                                "candidates_without_verdict": 0,
                                "candidate_rows": 40,
                                "already_built_inventory_rows": 120,
                                "rejected_components_declared": 6,
                            },
                            "does_not_fire_on": {
                                "candidates_without_verdict": 0,
                                "candidate_rows": 0,
                                "already_built_inventory_rows": 120,
                                "rejected_components_declared": 6,
                            },
                        },
                        {
                            "rule": "refuse-on-blank-input",
                            "why": "THE signature property: a blank required input must escalate, never pass everything",
                            "fires_on": {
                                "candidates_without_verdict": 40,
                                "candidate_rows": 40,
                                "already_built_inventory_rows": 0,
                                "rejected_components_declared": 6,
                            },
                            "does_not_fire_on": {
                                "candidates_without_verdict": 40,
                                "candidate_rows": 40,
                                "already_built_inventory_rows": 120,
                                "rejected_components_declared": 6,
                            },
                        },
                    ],
                },
            },
        }
    )


def blueprints() -> list[dict[str, Any]]:
    return [_gem01(), _gem02()]
