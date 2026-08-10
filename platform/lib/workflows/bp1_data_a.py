"""Blueprints 1-2 of 12: BP-RES-01 Grounded Evidence Cascade, BP-RES-02 Multilingual Fusion."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(HERE))

import bp1_build as B  # noqa: E402

S = B.schema

# --------------------------------------------------------------- 1. BP-RES-01

_R1_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "WebSearch",
    "WebFetch",
    "Write(command-center/research/**)",
    "mcp__search-hub__web_search_exa",
    "mcp__search-hub__tavily_search",
    "mcp__search-hub__firecrawl_scrape",
    "mcp__search-hub__search_usage",
    "mcp__searxng__searxng_web_search",
    "mcp__searxng__searxng_instance_info",
    "mcp__codex__codex",
]


def _res01() -> dict[str, Any]:
    root = "command-center/research/bp-res-01"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-01-grounded-evidence-cascade",
            "name": "Grounded Evidence Cascade",
            "description": (
                "Answer a research question with every claim carrying a live-fetched source "
                "anchor and a two-axis (authority x recency) source assessment, never model "
                "recall. A claim with zero anchors is emitted as `unresolved`, never as prose. "
                "Mechanism: a tool-health preflight census gates the run, lenses fan out one per "
                "SOURCE CLASS, each claim is re-checked FACT/RACE-style, then sources are scored "
                "on two axes before synthesis."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["research-and-evidence"],
            "tags": ["deep-research", "anchored-claims", "tool-health-preflight"],
            "flagship": True,
            "params": {
                "question": {
                    "type": "string",
                    "required": True,
                    "min_length": 10,
                    "max_length": 2000,
                    "description": "The owner question to answer",
                },
                "source_classes": {
                    "type": "array",
                    "required": True,
                    "min_items": 1,
                    "max_items": 24,
                    "items": {"type": "string", "min_length": 2},
                    "description": "One grounded lens is fanned out per source class",
                },
                "max_sources": {
                    "type": "integer",
                    "default": 40,
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Upper bound on sources reviewed across all lenses",
                },
                "time_horizon": {
                    "type": "enum",
                    "enum": ["any", "last12months", "last90days"],
                    "default": "any",
                    "description": "Recency floor applied to the recency axis",
                },
                "expand_citation_graph": {
                    "type": "boolean",
                    "default": False,
                    "description": "Optional S4b: one-hop citation expansion",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
                "search_api_key": {
                    "type": "secret_ref",
                    "secret": True,
                    "description": (
                        "Reference NAME of the search credential. The value never enters an "
                        "artifact, a log, an export bundle or a replay journal."
                    ),
                },
            },
            "roles": {
                "preflight-auditor": {
                    "description": (
                        "Enumerates the live research MCP inventory and each engine's quota "
                        "state BEFORE any lens runs; an engine that cannot be shown UP is not "
                        "used and is recorded as unavailable"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "mcp__searxng__searxng_instance_info",
                        "mcp__search-hub__search_usage",
                        "Write(command-center/research/**)",
                    ],
                    "write_paths": ["command-center/research/**"],
                    "speaking_rights": "always",
                },
                "question-architect": {
                    "description": (
                        "Decomposes the question into one lens per source class, each with a "
                        "named settling probe; never answers the question itself"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "grounded-lens": {
                    "description": (
                        "Gathers evidence for exactly one source class and must attach a URL or "
                        "a file:line to every claim it emits"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "WebSearch",
                        "WebFetch",
                        "mcp__search-hub__web_search_exa",
                        "mcp__search-hub__tavily_search",
                        "mcp__search-hub__firecrawl_scrape",
                        "mcp__searxng__searxng_web_search",
                        "Write(command-center/research/**)",
                    ],
                    "write_paths": ["command-center/research/**"],
                    "min_participants": 1,
                    "max_participants": 24,
                    "speaking_rights": "always",
                },
                "fact-verifier": {
                    "description": (
                        "Cross-vendor FACT/RACE re-check: re-derives each claim from the raw "
                        "fetched artifact, never from a lens summary"
                    ),
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "effort": "high",
                    "authority": "voting",
                    "vote_weight": 2,
                    "independence": "cross-examining",
                    "cross_vendor_required": True,
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "WebFetch",
                        "mcp__codex__codex",
                    ],
                    "speaking_rights": "rebuttal-only",
                },
                "source-assessor": {
                    "description": (
                        "Scores each surviving source on the two declared axes (authority, "
                        "recency) and records that this is a MODEL JUDGEMENT, not a measurement"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "synthesiser": {
                    "description": (
                        "Writes the report with an inline confidence band per claim and an "
                        "`unresolved` section that is never silently dropped"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "max",
                    "authority": "chair",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R1_ALLOW),
                "deny": [
                    "Bash",
                    "Write(command-center/WORK-UNIT-CATALOG.json)",
                    "mcp__github__create_pull_request",
                ],
                "require_owner_approval": ["Write(command-center/export/**)"],
                "network": "read-only",
                "write_paths": ["command-center/research/**"],
                "forbid_write_paths": [
                    "command-center/WORK-UNIT-CATALOG.json",
                    "platform/schema/**",
                ],
                "source_policy": {
                    "allow_domains": [],
                    "deny_domains": ["example-content-farm.invalid"],
                    "offline_only": False,
                    "license_allowlist": [
                        "MIT",
                        "Apache-2.0",
                        "BSD-3-Clause",
                        "CC-BY-4.0",
                        "public-domain",
                    ],
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "vendor-diverse",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'fact-verifier'",
                        "target": {
                            "model": "gpt-5-codex",
                            "vendor": "openai",
                            "effort": "high",
                        },
                        "reason": "a same-vendor verifier shares the lens author's blind spots",
                    }
                ],
                "fallbacks": [{"model": "gpt-5-codex", "vendor": "openai"}],
                "escalation": {
                    "on": ["failure", "reviewer-refuted", "quota-429"],
                    "target": {"model": "opus", "vendor": "anthropic", "effort": "max"},
                    "max_escalations": 2,
                },
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "anchor-or-unresolved": {
                    "predicate": "custom-expression",
                    "expression": (
                        "claims_without_anchor == 0 AND tool_health_recorded == true "
                        "AND anchors_from_engines_proven_up == true"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "repair",
                },
                "unit-complete": {
                    "predicate": "completion-predicate-v1",
                    "predicate_ref": "platform/schema/completion-predicate-result.schema.json",
                    "conditions_required": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "escalate-to-human",
                },
            },
            "stages": [
                {
                    "id": "preflight",
                    "title": "Census the live research tools and their quota state",
                    "kind": "task",
                    "role": "preflight-auditor",
                    "checkpoint": True,
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0101",
                        title="Enumerate live research engines and record each one's UP/DOWN/quota state",
                        phase="2B",
                        target=(
                            "Produce the engine roster this run may use: for every research MCP in "
                            "the inventory, record reachable/unreachable and remaining quota, and "
                            "mark the substitution order a lens must follow when its first engine "
                            "is exhausted."
                        ),
                        inputs=[
                            "params.question",
                            "params.source_classes",
                            "params.search_api_key",
                        ],
                        deps=[],
                        role="preflight-auditor",
                        tools=[
                            "Read",
                            "mcp__searxng__searxng_instance_info",
                            "mcp__search-hub__search_usage",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/tool-health.json",
                        out_schema=S("health-report"),
                        evidence=(
                            "each engine row carries the exact probe invoked and its verbatim "
                            "reachability response; an engine with no probe output is recorded "
                            "unavailable, never assumed UP"
                        ),
                        tests=[
                            "both-states control: an engine pointed at an unreachable endpoint must be "
                            "recorded DOWN, and the same engine pointed at its real endpoint must be "
                            "recorded UP in the same run",
                        ],
                        reviewer="the synthesiser re-reads this roster before accepting any anchor and rejects an anchor from an engine not proven UP",
                        postcondition=(
                            "the roster exists, parses, names every engine the lenses will use, and "
                            "each row carries a probe output"
                        ),
                        retry="fixed backoff, at most 2 attempts; a second failure records the engine unavailable rather than retrying a third time",
                        failure_classes=[
                            "engine-unreachable",
                            "quota-exhausted",
                            "detector-failure",
                        ],
                        mechanism="tool-health-preflight-census",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/tool-health.json",
                            S("health-report"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPR-0101",
                            consumers=["decompose", "lens-fanout", "anchor-gate"],
                        )
                    ],
                },
                {
                    "id": "decompose",
                    "title": "Decompose the question into one lens per source class",
                    "kind": "task",
                    "depends_on": ["preflight"],
                    "role": "question-architect",
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0102",
                        title="Emit the lens plan: one answerable sub-question per source class with a settling probe",
                        phase="2B",
                        target=(
                            "Turn the question into one sub-question per declared source class, each "
                            "carrying the probe that would settle it and the engine (from the "
                            "preflight roster) that will be used."
                        ),
                        inputs=[
                            "params.question",
                            f"{root}/tool-health.json",
                            "params.max_sources",
                        ],
                        deps=["BPR-0101"],
                        role="question-architect",
                        tools=["Read", "Grep", "Write(command-center/research/**)"],
                        substrate="local-single",
                        timeout=1200,
                        out_path=f"{root}/lens-plan.json",
                        out_schema=S("sampling-plan"),
                        evidence="every sub-question names its settling probe and the engine assigned to it from the preflight roster",
                        tests=[
                            "a source class whose every engine is DOWN in the preflight roster must appear "
                            "in the plan as unservable, not silently dropped",
                        ],
                        reviewer="one independent reviewer confirms the sub-questions jointly cover the question and none is unanswerable by construction",
                        postcondition="the plan exists, parses, and has one entry per declared source class",
                        retry="two strikes then pivot: after two rejected plans, enumerate at least two alternative decompositions before a third attempt",
                        failure_classes=["spec-underspecified", "engine-unreachable"],
                        mechanism="source-class-decomposition",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/lens-plan.json",
                            S("sampling-plan"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPR-0102",
                            consumers=["lens-fanout"],
                        )
                    ],
                },
                {
                    "id": "lens-fanout",
                    "title": "Fan out one grounded lens per source class",
                    "kind": "fanout",
                    "depends_on": ["decompose"],
                    "over": {
                        "source": "param",
                        "ref": "source_classes",
                        "item_var": "source_class",
                        "key_field": "source_class",
                    },
                    "max_concurrency": 6,
                    "arrival_stagger_ms": 400,
                    "max_items": 24,
                    "on_item_failure": "quarantine",
                    "body": [
                        {
                            "id": "lens-gather",
                            "title": "Gather anchored evidence for one source class",
                            "kind": "task",
                            "role": "grounded-lens",
                            "timeout_seconds": 2400,
                            "cache": B.cache_block(
                                f"{root}/cache/lenses",
                                [
                                    "stage_id",
                                    "item_key",
                                    "params_hash",
                                    "model_id",
                                    "tool_versions",
                                ],
                                ttl=86400,
                            ),
                            "work_unit": B.wu(
                                uid="BPR-0103",
                                title="Gather and anchor every claim for one source class",
                                phase="2B",
                                target=(
                                    "For the assigned source class, emit claims each carrying a live "
                                    "URL or file:line, the engine that produced it, and the fetch "
                                    "timestamp; a claim you cannot anchor goes to `unresolved`."
                                ),
                                inputs=[
                                    f"{root}/lens-plan.json",
                                    f"{root}/tool-health.json",
                                ],
                                deps=["BPR-0102"],
                                role="grounded-lens",
                                tools=[
                                    "WebSearch",
                                    "WebFetch",
                                    "mcp__search-hub__web_search_exa",
                                    "mcp__search-hub__tavily_search",
                                    "mcp__search-hub__firecrawl_scrape",
                                    "mcp__searxng__searxng_web_search",
                                    "Write(command-center/research/**)",
                                ],
                                substrate="local-parallel",
                                timeout=2400,
                                out_path=f"{root}/lenses/lens-record.json",
                                out_schema=S("research-claim-record"),
                                evidence="one URL or file:line per claim plus the engine id and fetch time; an unanchored statement is emitted under `unresolved`, never as prose",
                                tests=[
                                    "a question with a known-present anchor must yield that anchor (detector control)",
                                    "a deliberately unanswerable sub-question must yield mostly `unresolved`, not confident prose",
                                ],
                                reviewer="the cross-vendor fact-verifier re-derives a sample of claims from the raw fetched page, not from this summary",
                                postcondition="the record exists, parses, and every claim row has either an anchor or an `unresolved` marker",
                                retry="two strikes then pivot: on a second engine failure switch to the next engine in the preflight substitution order and record the substitution",
                                failure_classes=[
                                    "engine-unreachable",
                                    "quota-exhausted",
                                    "paywalled",
                                    "partial-artifact",
                                ],
                                mechanism="anchored-lens-gather",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/lenses/lens-record.json",
                                    S("research-claim-record"),
                                    min_bytes=256,
                                    sentinel="SUCCESS:BPR-0103",
                                    consumers=["fact-race-verify", "source-assess"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "quorum",
                        "quorum": 0.75,
                        "on_partial": "proceed-degraded",
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "fact-race-verify",
                    "title": "Cross-vendor FACT/RACE re-check of every claim",
                    "kind": "task",
                    "depends_on": ["lens-fanout"],
                    "role": "fact-verifier",
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPR-0104",
                        title="Re-derive each claim from its raw source and record CONFIRMED / REFUTED / UNRESOLVED",
                        phase="2B",
                        target=(
                            "For every claim emitted by the lenses, re-fetch the anchor and decide "
                            "whether the claim survives its own source. A claim whose anchor does not "
                            "contain it is REFUTED, not softened."
                        ),
                        inputs=[f"{root}/lenses/lens-record.json"],
                        deps=["BPR-0103"],
                        role="fact-verifier",
                        tools=["Read", "Grep", "WebFetch", "mcp__codex__codex"],
                        substrate="cross-vendor-codex",
                        timeout=2400,
                        out_path=f"{root}/claim-confirmations.json",
                        out_schema=S("confirmation-record"),
                        evidence="per claim: the re-fetched anchor, the quoted span that carries it, and the verdict; a verdict with no quoted span is UNRESOLVED",
                        tests=[
                            "seed one claim that its own anchor does NOT support - the pass must return REFUTED for it and CONFIRMED for an adjacent true claim in the same run",
                        ],
                        reviewer="the synthesiser may not promote a claim this pass left UNRESOLVED",
                        postcondition="every claim in the lens records has exactly one verdict row carrying a quoted span or an explicit UNRESOLVED reason",
                        model="gpt-5-codex",
                        vendor="openai",
                        basis="cross-vendor verification: an independent vendor has independent failure modes",
                        retry="two strikes then pivot: after two severed dispatches, fall back to an in-vendor verifier and record the loss of vendor independence",
                        failure_classes=[
                            "severed-stream",
                            "codex-exit-nonzero",
                            "quota-exhausted",
                        ],
                        mechanism="fact-race-reverification",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/claim-confirmations.json",
                            S("confirmation-record"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPR-0104",
                            consumers=["source-assess", "anchor-gate", "synthesise"],
                        )
                    ],
                },
                {
                    "id": "source-assess",
                    "title": "Score every surviving source on the authority and recency axes",
                    "kind": "task",
                    "depends_on": ["fact-race-verify"],
                    "role": "source-assessor",
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0105",
                        title="Two-axis source assessment with an explicit judgement disclaimer",
                        phase="2B",
                        target=(
                            "Score each surviving source on authority and on recency against the "
                            "declared time_horizon, and record on the artifact that both axes are "
                            "model judgement rather than measurement."
                        ),
                        inputs=[
                            f"{root}/claim-confirmations.json",
                            "params.time_horizon",
                        ],
                        deps=["BPR-0104"],
                        role="source-assessor",
                        tools=["Read", "Grep", "Write(command-center/research/**)"],
                        substrate="local-single",
                        timeout=1200,
                        out_path=f"{root}/source-assessment.json",
                        out_schema=S("reliability-weighting"),
                        evidence="each score cites the property it was derived from (publisher, author, date field) and the artifact states in-band that the axes are judgement, not measurement",
                        tests=[
                            "a source dated outside the declared time_horizon must score low on recency and must not be silently excluded",
                        ],
                        reviewer="one independent reviewer spot-checks three scores against the source page and records any disagreement",
                        postcondition="every source in the confirmation record has both axis scores and the judgement disclaimer is present",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["overclaim", "partial-artifact"],
                        mechanism="two-axis-source-assessment",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/source-assessment.json",
                            S("reliability-weighting"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPR-0105",
                            consumers=["synthesise"],
                        )
                    ],
                },
                {
                    "id": "citation-expansion",
                    "title": "Optional S4b: one-hop citation expansion",
                    "kind": "task",
                    "depends_on": ["source-assess"],
                    "when": "expand_citation_graph == true",
                    "role": "grounded-lens",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0106",
                        title="Expand one hop from the highest-authority sources and re-anchor anything new",
                        phase="2B",
                        target=(
                            "From the top-authority sources, follow one hop of citations and emit only "
                            "sources that add an anchor the existing set does not already carry."
                        ),
                        inputs=[f"{root}/source-assessment.json"],
                        deps=["BPR-0105"],
                        role="grounded-lens",
                        tools=[
                            "WebFetch",
                            "mcp__search-hub__web_search_exa",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-parallel",
                        timeout=1800,
                        out_path=f"{root}/citation-expansion.json",
                        out_schema=S("citation-audit"),
                        evidence="each expanded row names the source it was reached from and the anchor it adds; a row adding no new anchor is dropped with that reason recorded",
                        tests=[
                            "a citation set with zero new anchors must produce an empty expansion with the reason recorded, not an empty file",
                        ],
                        reviewer="the synthesiser treats an expanded source as ordinary evidence, subject to the same anchor gate",
                        postcondition="the expansion exists, parses, and every row names its parent source and its new anchor",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["engine-unreachable", "paywalled"],
                        mechanism="one-hop-citation-expansion",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/citation-expansion.json",
                            S("citation-audit"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0106",
                            consumers=["synthesise"],
                        )
                    ],
                },
                {
                    "id": "anchor-gate",
                    "title": "No claim without an anchor; no anchor from an engine not proven UP",
                    "kind": "gate",
                    "depends_on": ["source-assess", "citation-expansion"],
                    "gate_ref": "anchor-or-unresolved",
                },
                {
                    "id": "synthesise",
                    "title": "Write the report with an inline confidence band per claim",
                    "kind": "task",
                    "depends_on": ["anchor-gate"],
                    "role": "synthesiser",
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPR-0107",
                        title="Synthesise the anchored answer, the unresolved set, and the tool-health footer",
                        phase="2B",
                        target=(
                            "Write the report: every claim carries its anchor, its verdict and an "
                            "inline confidence band; the unresolved set is a first-class section; the "
                            "footer records which engines were UP and which substitutions happened."
                        ),
                        inputs=[
                            f"{root}/claim-confirmations.json",
                            f"{root}/source-assessment.json",
                            f"{root}/tool-health.json",
                        ],
                        deps=["BPR-0104", "BPR-0105"],
                        role="synthesiser",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=2400,
                        out_path=f"{root}/report.json",
                        out_schema=S("research-registry"),
                        evidence="every claim row carries anchor + verdict + confidence band inline; the unresolved count is stated numerically in the summary",
                        tests=[
                            "delete one anchor from the confirmation record and the report build must FAIL the anchor gate rather than emit the claim as prose (both-states: restore it and the build passes)",
                        ],
                        reviewer="one adversarial reviewer in a fresh context who authored none of the lenses checks for claims whose confidence band exceeds their evidence",
                        postcondition="the report exists, parses, states its unresolved count, and carries the tool-health footer",
                        retry="two strikes then pivot: after two failed syntheses, emit the partial report plus the blocking reason instead of a third attempt",
                        failure_classes=[
                            "overclaim",
                            "partial-artifact",
                            "detector-failure",
                        ],
                        mechanism="anchored-synthesis-with-bands",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/report.json",
                            S("research-registry"),
                            min_bytes=2048,
                            sentinel="SUCCESS:BPR-0107",
                            consumers=[
                                "completion-gate",
                                "command-center/CLAIM-REGISTRY.json",
                            ],
                        )
                    ],
                },
                {
                    "id": "completion-gate",
                    "title": "The one shared 12-condition completion predicate",
                    "kind": "gate",
                    "depends_on": ["synthesise"],
                    "gate_ref": "unit-complete",
                },
            ],
            "stopping_rules": [
                {
                    "id": "evidence-saturated",
                    "expression": "evidence_saturation == true OR elapsed_minutes >= 180",
                    "applies_to": "workflow",
                    "minimum_conditions": "sources_reviewed >= 10",
                    "on_stop": "complete",
                },
                {
                    "id": "marginal-lens-exhausted",
                    "expression": "new_anchors_in_last_two_lenses == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "lenses_returned >= 3",
                    "on_stop": "complete",
                },
                {
                    "id": "unanswerable-proved",
                    "expression": "proof_of_impossibility == true",
                    "applies_to": "workflow",
                    "on_stop": "emit-partial",
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
                    "paywalled",
                    "detector-failure",
                    "partial-artifact",
                ],
                escalate_to="synthesise",
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
                [
                    "workflow_version",
                    "stage_id",
                    "params_hash",
                    "inputs_hash",
                    "model_id",
                    "tool_versions",
                ],
                ttl=604800,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "WebFetch",
                    "WebSearch",
                    "Write(command-center/research/**)",
                    "mcp__search-hub__firecrawl_scrape",
                    "mcp__codex__codex",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(600, 2400, 7200),
                tokens=(200000, 900000, 2500000),
                tool_calls=(220, 900),
                cost=(1.5, 4.0, 12.0),
                risk="low",
                reversibility="reversible",
                blast_radius="writes only under command-center/research/bp-res-01/**",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-01.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "skills/deep-research",
                        "relation": "ADOPT-AS-IS",
                        "license": "owner-proprietary",
                        "credit": "owner",
                    },
                    {
                        "source": "exec-claude-code-docs-deep-research",
                        "relation": "EXTEND",
                        "credit": "executed workflow corpus",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-01",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=["skills/deep-research@1.0.0"],
            ),
            "outputs": {
                "report": B.artifact(
                    f"{root}/report.json",
                    S("research-registry"),
                    min_bytes=2048,
                    consumers=[
                        "command-center/CLAIM-REGISTRY.json",
                        "bp-res-06-longitudinal-verdict-refresh",
                    ],
                )
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-01", 204),
                "acquisition_route_from_card": "ADOPT",
                "mechanism_signature": [
                    "tool-health-preflight-census",
                    "source-class-lens-fanout",
                    "cross-vendor-fact-race-recheck",
                    "two-axis-source-assessment",
                    "anchor-or-unresolved-hard-gate",
                    "engine-substitution-on-quota-exhaustion",
                ],
                "contraindications": [
                    "NOT for a question answerable from the repo - use a grounded file:line lens",
                    "NOT for a single fact lookup - that is one fetch",
                    "NOT when the answer must be deterministically replayable: live web state drifts",
                ],
                "replay_note": (
                    "replay.deterministic is FALSE on purpose: the open web is not replayable. The "
                    "artifact cache makes a re-run within TTL reproducible, so the cache key is "
                    "recorded in the report footer instead of a determinism claim."
                ),
                "per_item_path_note": (
                    "the DSL relative_path grammar forbids brace templating, so a fan-out body "
                    "declares the canonical per-item record NAME; the runner derives the per-item "
                    "path from the barrier key_field plus resume.idempotency_key_from item_key."
                ),
                "unverified": [
                    "UNVERIFIED that this shape beats a bare WebSearch loop on anchors-per-claim; "
                    "settling experiment = run both on the same five questions and count "
                    "anchors/claim and unresolved/claim.",
                ],
                "worked_example": {
                    "name": "what changed in Claude Code Workflows since 2026-06-01",
                    "params": {
                        "question": "What changed in Claude Code saved Workflows between 2026-06-01 and today?",
                        "source_classes": [
                            "vendor-docs",
                            "release-notes",
                            "practitioner-blogs",
                        ],
                        "max_sources": 30,
                        "time_horizon": "last90days",
                        "expand_citation_graph": False,
                        "search_api_key": "EXA_API_KEY",
                    },
                    "expected_stage_order": [
                        "preflight",
                        "decompose",
                        "lens-fanout",
                        "fact-race-verify",
                        "source-assess",
                        "citation-expansion",
                        "anchor-gate",
                        "synthesise",
                        "completion-gate",
                    ],
                    "expected_skipped": ["citation-expansion"],
                    "expected_max_parallel": 6,
                    "expected_gate_ids": ["anchor-gate", "completion-gate"],
                    "expected_artifact_count": 7,
                    "acceptance": [
                        ">=8 distinct anchors across the three lenses",
                        "0 claims emitted without an anchor",
                        "the tool-health footer names every engine used",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "evidence-saturated",
                            "why": "the minimum_conditions floor must block a cheap early stop",
                            "fires_on": {
                                "evidence_saturation": True,
                                "elapsed_minutes": 42,
                                "sources_reviewed": 14,
                                "new_anchors_in_last_two_lenses": 5,
                                "lenses_returned": 3,
                                "proof_of_impossibility": False,
                            },
                            "does_not_fire_on": {
                                "evidence_saturation": True,
                                "elapsed_minutes": 42,
                                "sources_reviewed": 4,
                                "new_anchors_in_last_two_lenses": 5,
                                "lenses_returned": 3,
                                "proof_of_impossibility": False,
                            },
                        },
                        {
                            "rule": "marginal-lens-exhausted",
                            "why": "a lens adding no new anchor stops the cascade only after three lenses have returned",
                            "fires_on": {
                                "evidence_saturation": False,
                                "elapsed_minutes": 30,
                                "sources_reviewed": 12,
                                "new_anchors_in_last_two_lenses": 0,
                                "lenses_returned": 5,
                                "proof_of_impossibility": False,
                            },
                            "does_not_fire_on": {
                                "evidence_saturation": False,
                                "elapsed_minutes": 30,
                                "sources_reviewed": 12,
                                "new_anchors_in_last_two_lenses": 0,
                                "lenses_returned": 2,
                                "proof_of_impossibility": False,
                            },
                        },
                    ],
                },
            },
        }
    )


# --------------------------------------------------------------- 2. BP-RES-02

_R2_ALLOW = [
    "Read",
    "Bash:python",
    "WebFetch",
    "Write(command-center/research/**)",
    "mcp__searxng__searxng_web_search",
    "mcp__searxng__searxng_instance_info",
    "mcp__brightdata__search_engine",
    "mcp__brightdata__scrape_as_markdown",
    "mcp__search-hub__firecrawl_search",
    "mcp__search-hub__firecrawl_scrape",
]


def _res02() -> dict[str, Any]:
    root = "command-center/research/bp-res-02"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-02-multilingual-native-index-fusion",
            "name": "Multilingual Native-Index Fusion Research",
            "description": (
                "Reach sources that exist only behind a non-English native index, then fuse the "
                "per-engine rankings with deterministic Reciprocal Rank Fusion so a Yandex / Naver "
                "/ Seznam hit competes fairly with a Google hit. Routing axis is LANGUAGE AND INDEX, "
                "not source class, and the fusion step is arithmetic in a script - given the "
                "archived per-engine rankings the fused order is recomputable exactly. An engine "
                "that returns zero for a known-present control term is DETECTOR-FAILED and dropped "
                "from the fusion, never read as evidence of absence."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["research-and-evidence"],
            "tags": ["multilingual", "rank-fusion", "detector-control"],
            "flagship": False,
            "params": {
                "question": {
                    "type": "string",
                    "required": True,
                    "min_length": 10,
                    "description": "The question, stated in English",
                },
                "target_languages": {
                    "type": "array",
                    "required": True,
                    "min_items": 1,
                    "max_items": 8,
                    "items": {"type": "string", "min_length": 2, "max_length": 12},
                    "description": "BCP-47-ish language tags to translate the query into",
                },
                "engines": {
                    "type": "array",
                    "default": ["yandex", "naver", "seznam", "searx-brave"],
                    "min_items": 2,
                    "max_items": 12,
                    "items": {"type": "string", "min_length": 3},
                    "description": "One lens per engine; at least two, because a single engine cannot be fused",
                },
                "k_per_engine": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Results taken from each engine before fusion",
                },
                "control_term": {
                    "type": "string",
                    "required": True,
                    "min_length": 2,
                    "description": (
                        "A term KNOWN to be present in each engine's index. An engine that returns "
                        "zero for it is a broken detector, not evidence of absence."
                    ),
                },
                "include_forum_lens": {
                    "type": "boolean",
                    "default": False,
                    "description": "Optional S1b community/forum lens",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "query-translator": {
                    "description": "Rewrites the question using the NATIVE technical term in each target language, never a transliteration",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": ["Read", "Write(command-center/research/**)"],
                    "speaking_rights": "always",
                },
                "engine-lens": {
                    "description": "Queries exactly one engine and returns its RAW ranking, unreordered, so the fusion has honest inputs",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__searxng__searxng_web_search",
                        "mcp__brightdata__search_engine",
                        "mcp__search-hub__firecrawl_search",
                        "Write(command-center/research/**)",
                    ],
                    "min_participants": 2,
                    "max_participants": 12,
                    "speaking_rights": "always",
                },
                "forum-lens": {
                    "description": "Mines community and forum surfaces, whose retrieval shape differs from web search, and marks every lead as reputation-soft",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__brightdata__scrape_as_markdown",
                        "WebFetch",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "on-request",
                },
                "rank-fuser": {
                    "description": "Runs Reciprocal Rank Fusion as arithmetic in a script; makes no judgement and may not reorder a fused row",
                    "vendor": "any",
                    "effort": "low",
                    "authority": "judge",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "in-language-verifier": {
                    "description": "Fetches and reads the top-k IN THE SOURCE LANGUAGE and attaches the original-language quote beside every translated claim",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "voting",
                    "independence": "cross-examining",
                    "tool_permissions": [
                        "WebFetch",
                        "mcp__search-hub__firecrawl_scrape",
                        "Read",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "rebuttal-only",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R2_ALLOW),
                "deny": [
                    "Bash",
                    "WebSearch",
                    "mcp__search-hub__web_search_exa",
                    "Write(command-center/WORK-UNIT-CATALOG.json)",
                ],
                "network": "read-only",
                "write_paths": ["command-center/research/**"],
                "forbid_write_paths": ["command-center/WORK-UNIT-CATALOG.json"],
                "source_policy": {
                    "deny_domains": ["example-content-farm.invalid"],
                    "offline_only": False,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "capability",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'rank-fuser'",
                        "target": {
                            "model": "none-deterministic-script",
                            "vendor": "mixed",
                            "effort": "low",
                        },
                        "reason": "rank fusion is arithmetic; routing it to a model would make a deterministic step non-deterministic",
                    }
                ],
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "fusion-integrity": {
                    "predicate": "custom-expression",
                    "expression": (
                        "rows_without_origin_engine == 0 AND detector_failed_engines_excluded == true "
                        "AND engines_contributing >= 2"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "translation-fidelity": {
                    "predicate": "custom-expression",
                    "expression": "translated_claims_without_original_quote == 0",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "repair",
                },
            },
            "stages": [
                {
                    "id": "translate-query",
                    "title": "Rewrite the question with the native technical term per language",
                    "kind": "task",
                    "role": "query-translator",
                    "checkpoint": True,
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0201",
                        title="Emit one native-language query per target language plus the engine assignment",
                        phase="2B",
                        target=(
                            "For each target language, write the query a native practitioner would "
                            "type - the domain's own term, not a transliteration - and assign the "
                            "engines whose index actually covers that language."
                        ),
                        inputs=[
                            "params.question",
                            "params.target_languages",
                            "params.engines",
                        ],
                        deps=[],
                        role="query-translator",
                        tools=["Read", "Write(command-center/research/**)"],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/query-plan.json",
                        out_schema=S("sampling-plan"),
                        evidence="each row carries the source English phrase, the native query, and the reason the native term differs from a literal translation",
                        tests=[
                            "a term with an established native form must NOT be transliterated; the row must show both forms so the difference is visible",
                        ],
                        reviewer="the in-language verifier confirms each native query is idiomatic for the domain before the fan-out spends quota",
                        postcondition="the plan exists, parses, and covers every declared target language with at least one engine assigned",
                        retry="two strikes then pivot: after two rejected translations, enumerate at least two alternative term choices",
                        failure_classes=["translation-fidelity", "spec-underspecified"],
                        mechanism="native-term-query-translation",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/query-plan.json",
                            S("sampling-plan"),
                            sentinel="SUCCESS:BPR-0201",
                            consumers=["engine-control", "engine-fanout"],
                        )
                    ],
                },
                {
                    "id": "engine-control",
                    "title": "Detector control: every engine must return the known-present control term",
                    "kind": "task",
                    "depends_on": ["translate-query"],
                    "role": "engine-lens",
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0202",
                        title="Probe each engine with the control term and mark a zero-return engine DETECTOR-FAILED",
                        phase="2B",
                        target=(
                            "Query every declared engine for the control term. An engine returning "
                            "zero results is DETECTOR-FAILED and is excluded from the fusion with "
                            "that reason recorded; its silence is never read as absence of evidence."
                        ),
                        inputs=[
                            "params.engines",
                            "params.control_term",
                            f"{root}/query-plan.json",
                        ],
                        deps=["BPR-0201"],
                        role="engine-lens",
                        tools=[
                            "mcp__searxng__searxng_web_search",
                            "mcp__brightdata__search_engine",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-parallel",
                        timeout=900,
                        out_path=f"{root}/engine-control.json",
                        out_schema=S("detector-control"),
                        evidence="per engine: the exact control query, the returned count, and the PASS/DETECTOR-FAILED verdict",
                        tests=[
                            "both-states: point one engine at a deliberately wrong endpoint - it must be DETECTOR-FAILED - and the same engine at its real endpoint must PASS in the same run",
                        ],
                        reviewer="the rank fuser refuses to fuse any engine this probe marked DETECTOR-FAILED",
                        postcondition="every declared engine has a verdict row carrying its control-query output",
                        retry="fixed backoff, at most 2 attempts; a 429 is recorded as rate-limited-retry-later, never as DETECTOR-FAILED",
                        failure_classes=[
                            "engine-unreachable",
                            "rate-limited",
                            "detector-failure",
                        ],
                        mechanism="per-engine-detector-control",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/engine-control.json",
                            S("detector-control"),
                            sentinel="SUCCESS:BPR-0202",
                            consumers=["engine-fanout", "rrf-fuse", "fusion-gate"],
                        )
                    ],
                },
                {
                    "id": "engine-fanout",
                    "title": "One lens per engine, staggered against rate limits",
                    "kind": "fanout",
                    "depends_on": ["engine-control"],
                    "over": {
                        "source": "param",
                        "ref": "engines",
                        "item_var": "engine",
                        "key_field": "engine",
                    },
                    "max_concurrency": 4,
                    "arrival_stagger_ms": 750,
                    "max_items": 12,
                    "on_item_failure": "quarantine",
                    "body": [
                        {
                            "id": "engine-query",
                            "title": "Return one engine's RAW ranking, unreordered",
                            "kind": "task",
                            "role": "engine-lens",
                            "timeout_seconds": 1800,
                            "work_unit": B.wu(
                                uid="BPR-0203",
                                title="Capture the top-k raw ranking from one engine for every native query",
                                phase="2B",
                                target=(
                                    "For the assigned engine, run each native query and archive the "
                                    "top-k ranking EXACTLY as returned, with position preserved, so "
                                    "the fusion can be recomputed from the archive alone."
                                ),
                                inputs=[
                                    f"{root}/query-plan.json",
                                    f"{root}/engine-control.json",
                                    "params.k_per_engine",
                                ],
                                deps=["BPR-0202"],
                                role="engine-lens",
                                tools=[
                                    "mcp__searxng__searxng_web_search",
                                    "mcp__brightdata__search_engine",
                                    "mcp__search-hub__firecrawl_search",
                                    "Write(command-center/research/**)",
                                ],
                                substrate="local-parallel",
                                timeout=1800,
                                out_path=f"{root}/engines/raw-ranking.json",
                                out_schema=S("router-corpus"),
                                evidence="every row carries engine id, query text, integer position, url and source_language; positions are contiguous from 1",
                                tests=[
                                    "a rate-limited engine must emit a partial ranking plus a rate-limited marker, never an empty file that reads as zero results",
                                ],
                                reviewer="the rank fuser validates position contiguity before fusing and rejects a re-sorted ranking",
                                postcondition="the raw ranking exists, parses, and positions are contiguous with no re-sorting applied",
                                retry="two strikes then pivot: after two 429s, defer this engine to a later staggered wave rather than hammering it",
                                failure_classes=[
                                    "rate-limited",
                                    "engine-unreachable",
                                    "partial-artifact",
                                ],
                                mechanism="raw-ranking-capture",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/engines/raw-ranking.json",
                                    S("router-corpus"),
                                    sentinel="SUCCESS:BPR-0203",
                                    consumers=["rrf-fuse"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "quorum",
                        "quorum": 0.5,
                        "on_partial": "proceed-with-quarantine",
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "rrf-fuse",
                    "title": "Deterministic Reciprocal Rank Fusion over the archived rankings",
                    "kind": "task",
                    "depends_on": ["engine-fanout"],
                    "role": "rank-fuser",
                    "timeout_seconds": 600,
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/research/**)",
                    ],
                    "cache": B.cache_block(
                        f"{root}/cache/fusion",
                        ["stage_id", "inputs_hash", "tool_versions"],
                        ttl=2592000,
                    ),
                    "work_unit": B.wu(
                        uid="BPR-0204",
                        title="Compute the RRF score per url and emit the fused ranking with origin engines",
                        phase="2B",
                        target=(
                            "Fuse the archived per-engine rankings with RRF in a script: score(url) = "
                            "sum over engines of 1/(k + position). Every fused row names every engine "
                            "that returned it; a row returned by exactly one engine is flagged "
                            "single-engine-weak."
                        ),
                        inputs=[
                            f"{root}/engines/raw-ranking.json",
                            f"{root}/engine-control.json",
                        ],
                        deps=["BPR-0203"],
                        role="rank-fuser",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/fused-ranking.json",
                        out_schema=S("tournament-score"),
                        evidence="the fused file records the RRF constant k, every contributing engine per row, and a checksum of the input rankings so the fusion is recomputable",
                        tests=[
                            "recompute the fusion twice from the same archive: the output must be byte-identical",
                            "both-states: drop one engine from the archive and the fused ORDER must change; restore it and the original order must return",
                        ],
                        reviewer="no reviewer may reorder a fused row; a disagreement is recorded as a dispute against the RRF constant, not as a manual reorder",
                        postcondition="the fused ranking exists, parses, names >=2 contributing engines, and records the RRF constant plus the input checksum",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="arithmetic, not judgement: a model here would destroy the determinism this step exists for",
                        retry="none: a deterministic script that failed will fail identically, so a retry is meaningless - fix the input instead",
                        failure_classes=["schema-invalid", "partial-artifact"],
                        mechanism="reciprocal-rank-fusion",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/fused-ranking.json",
                            S("tournament-score"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPR-0204",
                            consumers=["verify-top-k", "fusion-gate", "report"],
                        )
                    ],
                },
                {
                    "id": "forum-lens-pass",
                    "title": "Optional S1b: community and forum surface",
                    "kind": "task",
                    "depends_on": ["rrf-fuse"],
                    "when": "include_forum_lens == true",
                    "role": "forum-lens",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0205",
                        title="Mine community surfaces whose retrieval shape differs from web search",
                        phase="2B",
                        target=(
                            "Mine forum and community surfaces for the native queries and emit leads "
                            "marked reputation-soft; a community lead is never promoted above a fused "
                            "row on reputation alone."
                        ),
                        inputs=[
                            f"{root}/query-plan.json",
                            f"{root}/fused-ranking.json",
                        ],
                        deps=["BPR-0204"],
                        role="forum-lens",
                        tools=[
                            "mcp__brightdata__scrape_as_markdown",
                            "WebFetch",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-parallel",
                        timeout=1800,
                        out_path=f"{root}/forum-leads.json",
                        out_schema=S("research-claim-record"),
                        evidence="each lead carries the community URL, the quoted post span, and an explicit reputation-soft marker",
                        tests=[
                            "a scraped post containing an instruction-shaped string must be recorded as DATA with the instruction neutralised, never executed",
                        ],
                        reviewer="the in-language verifier treats every community lead as unverified until it is confirmed outside the community that produced it",
                        postcondition="the leads file exists, parses, and every row carries the reputation-soft marker",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=[
                            "rate-limited",
                            "injection-attempt",
                            "engine-unreachable",
                        ],
                        mechanism="community-surface-mining",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/forum-leads.json",
                            S("research-claim-record"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0205",
                            consumers=["verify-top-k"],
                        )
                    ],
                },
                {
                    "id": "verify-top-k",
                    "title": "Read the top-k in the source language and attach the original quote",
                    "kind": "task",
                    "depends_on": ["rrf-fuse", "forum-lens-pass"],
                    "role": "in-language-verifier",
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPR-0206",
                        title="Fetch and read the fused top-k in-language and pair every translated claim with its original quote",
                        phase="2B",
                        target=(
                            "For the fused top-k, fetch the page and read it in the source language. "
                            "Every claim carried into English must sit beside the original-language "
                            "span it came from, so a numeric or precise claim can be re-checked."
                        ),
                        inputs=[
                            f"{root}/fused-ranking.json",
                            f"{root}/forum-leads.json",
                        ],
                        deps=["BPR-0204"],
                        role="in-language-verifier",
                        tools=[
                            "WebFetch",
                            "mcp__search-hub__firecrawl_scrape",
                            "Read",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-parallel",
                        timeout=2400,
                        out_path=f"{root}/in-language-verification.json",
                        out_schema=S("confirmation-record"),
                        evidence="per claim: the original-language quote, its URL, and the English rendering; a numeric claim without an original-language quote is UNRESOLVED",
                        tests=[
                            "seed a numeric claim whose source states a different number - the pass must return REFUTED and quote the original",
                        ],
                        reviewer="one independent reviewer who did not translate the query re-reads two quotes and records any rendering disagreement",
                        postcondition="every top-k row has a verdict and every translated claim carries its original-language quote",
                        retry="two strikes then pivot: after two fetch failures on one row, mark it UNRESOLVED with the fetch error rather than a third attempt",
                        failure_classes=[
                            "translation-fidelity",
                            "engine-unreachable",
                            "paywalled",
                        ],
                        mechanism="in-language-quote-pairing",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/in-language-verification.json",
                            S("confirmation-record"),
                            sentinel="SUCCESS:BPR-0206",
                            consumers=["fidelity-gate", "report"],
                        )
                    ],
                },
                {
                    "id": "fusion-gate",
                    "title": "No fused row without its origin engine; no DETECTOR-FAILED engine in the fusion",
                    "kind": "gate",
                    "depends_on": ["verify-top-k"],
                    "gate_ref": "fusion-integrity",
                },
                {
                    "id": "fidelity-gate",
                    "title": "No translated claim without its original-language quote",
                    "kind": "gate",
                    "depends_on": ["fusion-gate"],
                    "gate_ref": "translation-fidelity",
                },
                {
                    "id": "report",
                    "title": "Report the fused ranking with source_language on every row",
                    "kind": "task",
                    "depends_on": ["fidelity-gate"],
                    "role": "rank-fuser",
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0207",
                        title="Emit the fused report, the excluded-engine list, and the unique-value verdict",
                        phase="2B",
                        target=(
                            "Write the report: fused rows with source_language and origin engines, the "
                            "engines excluded and why, and an explicit statement of how many unique "
                            "non-English domains the run added over an English-only baseline - "
                            "including when that number is zero."
                        ),
                        inputs=[
                            f"{root}/fused-ranking.json",
                            f"{root}/in-language-verification.json",
                            f"{root}/engine-control.json",
                        ],
                        deps=["BPR-0204", "BPR-0206"],
                        role="rank-fuser",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/report.json",
                        out_schema=S("research-registry"),
                        evidence="the unique-non-English-domain count is computed from the fused rows, not asserted; the excluded-engine list carries each exclusion reason",
                        tests=[
                            "an English-native question must produce a near-zero unique-value verdict - the correct NEGATIVE result, reported rather than hidden",
                        ],
                        reviewer="one adversarial reviewer checks that a single-engine-weak row is not presented as corroborated",
                        postcondition="the report exists, parses, states the unique-non-English-domain count numerically, and lists every excluded engine with a reason",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="the report is a projection of the deterministic fusion plus the verification record",
                        retry="none: recomputing a projection of unchanged inputs cannot change the result",
                        failure_classes=["schema-invalid", "overclaim"],
                        mechanism="fused-report-with-negative-result",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/report.json",
                            S("research-registry"),
                            min_bytes=1024,
                            sentinel="SUCCESS:BPR-0207",
                            consumers=["command-center/CLAIM-REGISTRY.json"],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "fusion-stable",
                    "expression": "fused_top_k_changed_by_last_engine == false",
                    "applies_to": "workflow",
                    "minimum_conditions": "engines_contributing >= 2",
                    "on_stop": "complete",
                },
                {
                    "id": "engine-roster-exhausted",
                    "expression": "engines_remaining == 0",
                    "applies_to": "workflow",
                    "on_stop": "complete",
                },
                {
                    "id": "no-unique-value",
                    "expression": "unique_non_english_domains == 0 AND engines_contributing >= 2",
                    "applies_to": "workflow",
                    "on_stop": "emit-partial",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                3, escalate_to="report", retry_on=["rate-limited", "engine-unreachable"]
            ),
            "failure_policy": B.failure(
                "degrade-loudly",
                [
                    "rate-limited",
                    "engine-unreachable",
                    "translation-fidelity",
                    "detector-failure",
                    "injection-attempt",
                ],
                escalate_to="report",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="fanout-item",
                keys=["workflow_id", "stage_id", "item_key", "params_hash"],
            ),
            "replay": {
                "deterministic": False,
                "journal_path": f"{root}/replay/engine-rankings.jsonl",
                "record": ["params", "inputs", "tool_calls", "tool_results", "timings"],
                "replay_source": "recorded-journal",
                "verify": "semantic-equal",
                "hash_algorithm": "sha256",
                "on_divergence": "record-discrepancy",
            },
            "cache": B.cache_block(
                f"{root}/cache",
                ["workflow_version", "stage_id", "inputs_hash", "item_key"],
                ttl=259200,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "WebFetch",
                    "mcp__searxng__searxng_web_search",
                    "mcp__brightdata__search_engine",
                    "mcp__brightdata__scrape_as_markdown",
                    "Write(command-center/research/**)",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(900, 3000, 9000),
                tokens=(150000, 600000, 1800000),
                tool_calls=(180, 700),
                cost=(2.0, 6.0, 18.0),
                risk="medium",
                reversibility="reversible",
                blast_radius="writes only under command-center/research/bp-res-02/**; regional engines are a higher injection-risk surface",
                confidence="roughly-even",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-02.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "07f465f3:.agents/skills/multilingual-search",
                        "relation": "REPAIR",
                        "license": "owner-proprietary",
                        "credit": "owner (undeployed skill)",
                    },
                    {
                        "source": "exec-phenibut-bromantane-deep-probe-w2",
                        "relation": "MERGE",
                        "credit": "executed workflow corpus",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-02",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=["07f465f3:.agents/skills/multilingual-search"],
            ),
            "outputs": {
                "fused-report": B.artifact(
                    f"{root}/report.json",
                    S("research-registry"),
                    min_bytes=1024,
                    consumers=["command-center/CLAIM-REGISTRY.json"],
                ),
                "raw-rankings": B.artifact(
                    f"{root}/engines/raw-ranking.json",
                    S("router-corpus"),
                    min_bytes=256,
                    consumers=["rrf-fuse"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-02", 247),
                "acquisition_route_from_card": "REPAIR",
                "mechanism_signature": [
                    "native-term-query-translation",
                    "per-engine-detector-control",
                    "raw-ranking-archive",
                    "deterministic-reciprocal-rank-fusion",
                    "in-language-original-quote-pairing",
                    "single-engine-weak-flagging",
                ],
                "contraindications": [
                    "NOT when the corpus is English-native: pure overhead, and the blueprint is designed to SAY so",
                    "NOT for legal or medical guidance in a language you cannot read - the translation layer is a fidelity risk on precise claims",
                ],
                "replay_note": (
                    "deterministic is FALSE because engine indexes drift between runs, but the "
                    "per-engine rankings are journalled, so the FUSION step alone is exactly "
                    "recomputable - verify is semantic-equal rather than hash-equal for that reason."
                ),
                "owner_decision": "Deploy the nine dark .agents/skills as one batch, or one at a time behind individual proof?",
                "unverified": [
                    "UNVERIFIED that translation + RRF beats either arm alone; settling experiment = "
                    "one question, three arms (skill alone / channel-mining alone / fused), counting "
                    "unique VERIFIED sources per arm.",
                ],
                "worked_example": {
                    "name": "find Russian-language documentation for a niche industrial controller",
                    "params": {
                        "question": "Which firmware revisions of the OWEN PLC110 family fixed the Modbus RTU timeout defect?",
                        "target_languages": ["ru", "cs"],
                        "engines": ["yandex", "seznam", "searx-brave"],
                        "k_per_engine": 20,
                        "control_term": "modbus",
                        "include_forum_lens": True,
                    },
                    "expected_stage_order": [
                        "translate-query",
                        "engine-control",
                        "engine-fanout",
                        "rrf-fuse",
                        "forum-lens-pass",
                        "verify-top-k",
                        "fusion-gate",
                        "fidelity-gate",
                        "report",
                    ],
                    "expected_skipped": [],
                    "expected_max_parallel": 4,
                    "expected_gate_ids": ["fusion-gate", "fidelity-gate"],
                    "acceptance": [
                        ">=3 unique non-English domains in the fused top 10",
                        "every fused row names its origin engines",
                        "any engine returning 0 for `modbus` is excluded as DETECTOR-FAILED",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "fusion-stable",
                            "why": "fusion may only be called stable once at least two engines contributed",
                            "fires_on": {
                                "fused_top_k_changed_by_last_engine": False,
                                "engines_contributing": 3,
                                "engines_remaining": 0,
                                "unique_non_english_domains": 4,
                            },
                            "does_not_fire_on": {
                                "fused_top_k_changed_by_last_engine": False,
                                "engines_contributing": 1,
                                "engines_remaining": 0,
                                "unique_non_english_domains": 4,
                            },
                        },
                        {
                            "rule": "no-unique-value",
                            "why": "the correct NEGATIVE result on an English-native topic must be reachable and reported",
                            "fires_on": {
                                "fused_top_k_changed_by_last_engine": True,
                                "engines_contributing": 3,
                                "engines_remaining": 1,
                                "unique_non_english_domains": 0,
                            },
                            "does_not_fire_on": {
                                "fused_top_k_changed_by_last_engine": True,
                                "engines_contributing": 3,
                                "engines_remaining": 1,
                                "unique_non_english_domains": 2,
                            },
                        },
                    ],
                },
            },
        }
    )


def blueprints() -> list[dict[str, Any]]:
    return [_res01(), _res02()]
