"""Blueprints 3-4 of 12: BP-RES-03 Academic Corpus Consolidation, BP-RES-04 Claim-Decomposition."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(HERE))

import bp1_build as B  # noqa: E402

S = B.schema

# --------------------------------------------------------------- 3. BP-RES-03

_R3_ALLOW = [
    "Read",
    "Grep",
    "Write(command-center/research/**)",
    "mcp__scholarly-access__paper_resolve",
    "mcp__scholarly-access__paper_batch_resolve",
    "mcp__scholarly-access__paper_access_status",
    "mcp__scholarly-access__paper_find_oa_pdf",
    "mcp__scholarly-access__paper_download_oa_pdf",
    "mcp__scholarly-access__paper_citation_graph",
    "mcp__scholarly-access__paper_fetch_metadata",
    "mcp__paper-search__search_openalex",
    "mcp__paper-search__search_pubmed",
    "mcp__paper-search__search_europepmc",
    "mcp__pdf-reader__read_pdf",
]


def _res03() -> dict[str, Any]:
    root = "command-center/research/bp-res-03"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-03-academic-corpus-consolidation",
            "name": "Academic Corpus Consolidation",
            "description": (
                "Turn identifiers (DOI / PMID / arXiv id) or a topic query into canonical metadata, "
                "a LEGAL access-status table, span-cited extractions and a T1-T4 evidence-graded "
                "shortlist. The distinguishing machine is the access gate: a paper whose PDF is not "
                "open-access is reported metadata-only and may never be paraphrased from its "
                "abstract as though it had been read, and the paywall-circumvention route is DENIED "
                "in tool_policy rather than merely discouraged. Because identifiers are stable this "
                "is the one research blueprint in the set that is genuinely replayable - with "
                "verify=schema-equal, because access_status is time-varying."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": [
                "research-and-evidence",
                "data-science-knowledge-and-creative",
            ],
            "tags": ["literature", "open-access-gate", "evidence-tiering"],
            "flagship": False,
            "params": {
                "input_mode": {
                    "type": "enum",
                    "enum": ["identifiers", "topic"],
                    "required": True,
                    "description": "Which resolve path runs; the other is skipped by its `when`",
                },
                "identifiers": {
                    "type": "array",
                    "default": [],
                    "max_items": 500,
                    "items": {"type": "string", "min_length": 4},
                    "description": "DOIs / PMIDs / arXiv ids when input_mode is identifiers",
                },
                "topic_query": {
                    "type": "string",
                    "default": "",
                    "max_length": 500,
                    "description": "Free-text query when input_mode is topic",
                },
                "evidence_scheme": {
                    "type": "enum",
                    "enum": ["t1t4", "none"],
                    "default": "t1t4",
                    "description": "t1t4 = human / animal / in-vitro / mechanistic tiering",
                },
                "max_papers": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Hard cap on papers read",
                },
                "expand_citation_graph": {
                    "type": "boolean",
                    "default": False,
                    "description": "Optional S1b: one hop, to catch the paper everyone cites and nobody listed",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "resolver": {
                    "description": "Resolves each identifier to canonical metadata; a miss is returned in `unresolved` with the failing probe, never a plausible-looking title",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__scholarly-access__paper_resolve",
                        "mcp__scholarly-access__paper_batch_resolve",
                        "mcp__scholarly-access__paper_fetch_metadata",
                        "mcp__paper-search__search_openalex",
                        "mcp__paper-search__search_pubmed",
                        "mcp__paper-search__search_europepmc",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "access-classifier": {
                    "description": "Decides open-access vs paywalled per paper and owns the legal gate; has VETO over any downstream read",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "veto",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__scholarly-access__paper_access_status",
                        "mcp__scholarly-access__paper_find_oa_pdf",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "span-reader": {
                    "description": "Extracts findings only as quoted spans with a page location; never summarises a paper it could not open",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__scholarly-access__paper_download_oa_pdf",
                        "mcp__pdf-reader__read_pdf",
                        "Read",
                        "Write(command-center/research/**)",
                    ],
                    "min_participants": 1,
                    "max_participants": 8,
                    "speaking_rights": "always",
                },
                "evidence-grader": {
                    "description": "Assigns T1-T4 and records that the tier is a model judgement over the stated study design, not a measurement",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "voting",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
                "shortlist-synthesiser": {
                    "description": "Ranks and summarises; may cite only span-backed findings and must carry the metadata-only rows through visibly",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "chair",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/research/**)",
                    ],
                    "speaking_rights": "always",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R3_ALLOW),
                "deny": [
                    "Bash",
                    "WebFetch",
                    "WebSearch",
                    "mcp__paper-search__download_scihub",
                    "mcp__sci-hub__*",
                ],
                "network": "read-only",
                "write_paths": ["command-center/research/**"],
                "forbid_write_paths": ["command-center/WORK-UNIT-CATALOG.json"],
                "source_policy": {
                    "offline_only": False,
                    "license_allowlist": [
                        "CC-BY-4.0",
                        "CC-BY-SA-4.0",
                        "CC0-1.0",
                        "publisher-open-access",
                    ],
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "static",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "open-access-only": {
                    "predicate": "custom-expression",
                    "expression": (
                        "paywalled_papers_paraphrased == 0 AND claims_without_cited_span == 0 "
                        "AND circumvention_tool_calls == 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "no-hallucinated-identifier": {
                    "predicate": "custom-expression",
                    "expression": "identifiers_resolved_without_registry_hit == 0",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
            },
            "stages": [
                {
                    "id": "resolve-identifiers",
                    "title": "Resolve supplied identifiers to canonical metadata",
                    "kind": "task",
                    "when": "input_mode == 'identifiers'",
                    "role": "resolver",
                    "checkpoint": True,
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0301",
                        title="Resolve every supplied identifier, or return it as unresolved with the failing probe",
                        phase="2B",
                        target=(
                            "For each supplied identifier, fetch canonical metadata from a registry. "
                            "An identifier with no registry hit is returned under `unresolved` with "
                            "the probe that missed - never as a fabricated title."
                        ),
                        inputs=["params.identifiers", "params.max_papers"],
                        deps=[],
                        role="resolver",
                        tools=[
                            "mcp__scholarly-access__paper_batch_resolve",
                            "mcp__scholarly-access__paper_fetch_metadata",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/resolved-metadata.json",
                        out_schema=S("reference-resolution"),
                        evidence="each row carries the registry queried and its raw response id; each unresolved row carries the probe and the miss",
                        tests=[
                            "a syntactically valid but non-existent DOI must land in `unresolved`; a real DOI in the same batch must resolve (both-states in one run)",
                        ],
                        reviewer="the access classifier refuses to classify any row lacking a registry response id",
                        postcondition="every supplied identifier appears exactly once, either resolved with a registry id or unresolved with a probe",
                        retry="fixed backoff, at most 3 attempts per identifier; a third miss is recorded unresolved rather than retried further",
                        failure_classes=[
                            "identifier-unresolvable",
                            "registry-unreachable",
                        ],
                        mechanism="identifier-anchored-resolution",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/resolved-metadata.json",
                            S("reference-resolution"),
                            sentinel="SUCCESS:BPR-0301",
                            consumers=["classify-access"],
                        )
                    ],
                },
                {
                    "id": "resolve-topic",
                    "title": "Resolve a topic query to a candidate paper set",
                    "kind": "task",
                    "when": "input_mode == 'topic'",
                    "role": "resolver",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0302",
                        title="Search the scholarly indexes for the topic and cap the candidate set",
                        phase="2B",
                        target=(
                            "Search the scholarly indexes for the topic query and emit at most "
                            "max_papers candidates, each already carrying a canonical identifier so "
                            "the rest of the pipeline is identifier-anchored."
                        ),
                        inputs=["params.topic_query", "params.max_papers"],
                        deps=[],
                        role="resolver",
                        tools=[
                            "mcp__paper-search__search_openalex",
                            "mcp__paper-search__search_pubmed",
                            "mcp__paper-search__search_europepmc",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/topic-candidates.json",
                        out_schema=S("sampling-frame"),
                        evidence="the sampling frame records every index queried, the query string, the returned count and the cap that was applied",
                        tests=[
                            "a topic with more hits than max_papers must record the truncation as a declared cap, never present the floor as the total",
                        ],
                        reviewer="one independent reviewer checks the frame is not silently biased to one index",
                        postcondition="the frame exists, parses, names every index queried, and every candidate carries a canonical identifier",
                        retry="fixed backoff, at most 2 attempts per index",
                        failure_classes=["registry-unreachable", "detector-truncation"],
                        mechanism="topic-to-identifier-frame",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/topic-candidates.json",
                            S("sampling-frame"),
                            sentinel="SUCCESS:BPR-0302",
                            consumers=["classify-access"],
                        )
                    ],
                },
                {
                    "id": "identifier-gate",
                    "title": "No resolved paper without a registry hit",
                    "kind": "gate",
                    "depends_on": ["resolve-identifiers", "resolve-topic"],
                    "gate_ref": "no-hallucinated-identifier",
                },
                {
                    "id": "classify-access",
                    "title": "Legal access classification per paper (the veto stage)",
                    "kind": "task",
                    "depends_on": ["identifier-gate"],
                    "role": "access-classifier",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0303",
                        title="Classify each paper open-access or paywalled and record the licence evidence",
                        phase="2B",
                        target=(
                            "For every resolved paper decide OPEN-ACCESS (with the OA PDF URL and its "
                            "licence) or PAYWALLED. A PAYWALLED paper is marked metadata-only and its "
                            "row forbids any downstream read."
                        ),
                        inputs=[
                            f"{root}/resolved-metadata.json",
                            f"{root}/topic-candidates.json",
                        ],
                        deps=["BPR-0301", "BPR-0302"],
                        role="access-classifier",
                        tools=[
                            "mcp__scholarly-access__paper_access_status",
                            "mcp__scholarly-access__paper_find_oa_pdf",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/access-table.json",
                        out_schema=S("license-and-rights-record"),
                        evidence="each row carries the licence string, the OA URL when open, and the measurement date - access status is time-varying and must be dated",
                        tests=[
                            "a set with a known-paywalled paper must yield exactly that many metadata-only rows",
                            "both-states: a known-OA paper in the same set must be classified open with its licence named",
                        ],
                        reviewer="the span reader treats this table as authoritative and cannot open a paper it marks metadata-only",
                        postcondition="every paper has an access row carrying a licence or an explicit paywalled marker plus a measurement date",
                        retry="fixed backoff, at most 2 attempts; an indeterminate status resolves to PAYWALLED (adverse inference on a blank required field)",
                        failure_classes=[
                            "licence-indeterminate",
                            "registry-unreachable",
                        ],
                        mechanism="legal-access-classification-veto",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/access-table.json",
                            S("license-and-rights-record"),
                            sentinel="SUCCESS:BPR-0303",
                            consumers=["span-read-fanout", "access-gate", "shortlist"],
                        )
                    ],
                },
                {
                    "id": "span-read-fanout",
                    "title": "Read only the open-access PDFs, as quoted spans",
                    "kind": "fanout",
                    "depends_on": ["classify-access"],
                    "over": {
                        "source": "artifact",
                        "ref": f"{root}/access-table.json",
                        "item_var": "paper",
                        "key_field": "doi",
                    },
                    "max_concurrency": 4,
                    "arrival_stagger_ms": 300,
                    "max_items": 500,
                    "on_item_failure": "quarantine",
                    "body": [
                        {
                            "id": "span-read",
                            "title": "Extract span-cited findings from one open-access paper",
                            "kind": "task",
                            "role": "span-reader",
                            "timeout_seconds": 1800,
                            "work_unit": B.wu(
                                uid="BPR-0304",
                                title="Extract each finding as a quoted span with a page location",
                                phase="2B",
                                target=(
                                    "Open the OA PDF and extract findings ONLY as quoted spans with a "
                                    "page location. If the access table marks this paper metadata-only, "
                                    "emit nothing and record the refusal."
                                ),
                                inputs=[f"{root}/access-table.json"],
                                deps=["BPR-0303"],
                                role="span-reader",
                                tools=[
                                    "mcp__scholarly-access__paper_download_oa_pdf",
                                    "mcp__pdf-reader__read_pdf",
                                    "Write(command-center/research/**)",
                                ],
                                substrate="local-parallel",
                                timeout=1800,
                                out_path=f"{root}/spans/paper-spans.json",
                                out_schema=S("citation-audit"),
                                evidence="every finding carries cited_text plus a page location; a finding without a span is dropped with that reason recorded",
                                tests=[
                                    "a metadata-only paper must produce a recorded refusal and zero findings - never an abstract-derived summary",
                                ],
                                reviewer="the evidence grader may grade only span-backed findings and must reject a finding with no page location",
                                postcondition="the span file exists, parses, and every finding carries cited_text and a page location",
                                retry="two strikes then pivot: after two failed PDF opens, mark the paper unreadable rather than paraphrasing the abstract",
                                failure_classes=[
                                    "pdf-unreadable",
                                    "licence-indeterminate",
                                    "partial-artifact",
                                ],
                                mechanism="span-cited-extraction",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/spans/paper-spans.json",
                                    S("citation-audit"),
                                    sentinel="SUCCESS:BPR-0304",
                                    consumers=["grade-evidence"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "quorum",
                        "quorum": 0.9,
                        "on_partial": "proceed-with-quarantine",
                        "reject_result_matching": ["started in the background"],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "grade-evidence",
                    "title": "Assign T1-T4 evidence tiers over the stated study design",
                    "kind": "task",
                    "depends_on": ["span-read-fanout"],
                    "when": "evidence_scheme == 't1t4'",
                    "role": "evidence-grader",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0305",
                        title="Grade each paper T1-T4 from its stated design and record the judgement disclaimer",
                        phase="2B",
                        target=(
                            "Assign an evidence tier per paper from the design stated in its own "
                            "quoted spans (T1 human trial, T2 human observational, T3 animal, T4 "
                            "in-vitro or mechanistic), citing the span that establishes the design."
                        ),
                        inputs=[f"{root}/spans/paper-spans.json"],
                        deps=["BPR-0304"],
                        role="evidence-grader",
                        tools=["Read", "Grep", "Write(command-center/research/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/evidence-tiers.json",
                        out_schema=S("reliability-weighting"),
                        evidence="each tier cites the span that states the design; the artifact records in-band that tiering is judgement over a stated design, not a measurement",
                        tests=[
                            "a paper whose spans never state a design must be tiered UNKNOWN, not guessed into T4",
                        ],
                        reviewer="one independent reviewer re-grades three papers blind to the first grade and any disagreement is recorded, not averaged away",
                        postcondition="every span-backed paper has a tier or an explicit UNKNOWN plus the citing span",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["overclaim", "design-unstated"],
                        mechanism="t1t4-design-tiering",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/evidence-tiers.json",
                            S("reliability-weighting"),
                            sentinel="SUCCESS:BPR-0305",
                            consumers=["shortlist"],
                        )
                    ],
                },
                {
                    "id": "citation-expand",
                    "title": "Optional S1b: one-hop citation expansion",
                    "kind": "task",
                    "depends_on": ["grade-evidence"],
                    "when": "expand_citation_graph == true",
                    "role": "resolver",
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0306",
                        title="Expand one citation hop and keep only papers above the tier floor",
                        phase="2B",
                        target=(
                            "Walk one hop of the citation graph from the highest-tier papers and keep "
                            "only new papers that would sit at or above the current tier floor; the "
                            "expansion re-enters the access gate like any other paper."
                        ),
                        inputs=[
                            f"{root}/evidence-tiers.json",
                            f"{root}/access-table.json",
                        ],
                        deps=["BPR-0305"],
                        role="resolver",
                        tools=[
                            "mcp__scholarly-access__paper_citation_graph",
                            "Write(command-center/research/**)",
                        ],
                        substrate="local-single",
                        timeout=1200,
                        out_path=f"{root}/citation-expansion.json",
                        out_schema=S("lineage-report"),
                        evidence="each expanded paper names the paper it was reached from and the hop direction (cites / cited-by)",
                        tests=[
                            "an expansion that adds no paper above the tier floor must record an empty result with that reason, not an empty file",
                        ],
                        reviewer="the access classifier re-runs over every expanded paper; expansion does not bypass the legal gate",
                        postcondition="the expansion exists, parses, and every row names its parent paper and hop direction",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=[
                            "registry-unreachable",
                            "identifier-unresolvable",
                        ],
                        mechanism="one-hop-citation-graph",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/citation-expansion.json",
                            S("lineage-report"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0306",
                            consumers=["shortlist"],
                        )
                    ],
                },
                {
                    "id": "access-gate",
                    "title": "No paraphrase of a paywalled paper; no claim without a span; no circumvention call",
                    "kind": "gate",
                    "depends_on": ["grade-evidence", "citation-expand"],
                    "gate_ref": "open-access-only",
                },
                {
                    "id": "shortlist",
                    "title": "Rank and summarise, carrying the metadata-only rows through visibly",
                    "kind": "task",
                    "depends_on": ["access-gate"],
                    "role": "shortlist-synthesiser",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0307",
                        title="Emit the ranked shortlist plus the access summary and the unresolved set",
                        phase="2B",
                        target=(
                            "Produce the ranked shortlist: one line per paper with its tier, its "
                            "one-line span-backed finding, and its access status. Metadata-only and "
                            "unresolved rows stay visible in the output."
                        ),
                        inputs=[
                            f"{root}/evidence-tiers.json",
                            f"{root}/access-table.json",
                            f"{root}/citation-expansion.json",
                        ],
                        deps=["BPR-0303", "BPR-0305"],
                        role="shortlist-synthesiser",
                        tools=["Read", "Grep", "Write(command-center/research/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/shortlist.json",
                        out_schema=S("research-registry"),
                        evidence="every ranked line cites the span behind its finding; the access summary states the open / paywalled / unresolved counts numerically",
                        tests=[
                            "the sum of open + paywalled + unresolved rows must equal the input identifier count exactly - a dropped paper is a defect, not a rounding",
                        ],
                        reviewer="one adversarial reviewer in a fresh context checks no metadata-only paper has acquired a finding",
                        postcondition="the shortlist exists, parses, reconciles its counts against the input set, and shows every metadata-only row",
                        retry="two strikes then pivot: after two failures emit the partial shortlist plus the blocking reason",
                        failure_classes=["overclaim", "partial-artifact"],
                        mechanism="access-aware-ranked-shortlist",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/shortlist.json",
                            S("research-registry"),
                            min_bytes=1024,
                            sentinel="SUCCESS:BPR-0307",
                            consumers=["command-center/CLAIM-REGISTRY.json"],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "identifier-list-exhausted",
                    "expression": "identifiers_remaining == 0 AND papers_without_verdict == 0",
                    "applies_to": "workflow",
                    "on_stop": "complete",
                },
                {
                    "id": "expansion-below-tier-floor",
                    "expression": "expansion_papers_above_floor == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "papers_graded >= 5",
                    "on_stop": "complete",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                3,
                escalate_to="shortlist",
                retry_on=["registry-unreachable", "pdf-unreadable"],
            ),
            "failure_policy": B.failure(
                "quarantine",
                [
                    "identifier-unresolvable",
                    "licence-indeterminate",
                    "pdf-unreadable",
                    "registry-unreachable",
                ],
                escalate_to="shortlist",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="fanout-item",
                keys=["workflow_id", "stage_id", "item_key", "inputs_hash"],
            ),
            "replay": B.replay_deterministic(
                20260810, f"{root}/replay/journal.jsonl", verify="schema-equal"
            ),
            "cache": B.cache_block(
                f"{root}/cache",
                ["workflow_version", "stage_id", "item_key", "inputs_hash"],
                ttl=2592000,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "mcp__scholarly-access__paper_download_oa_pdf",
                    "mcp__pdf-reader__read_pdf",
                    "Write(command-center/research/**)",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(600, 2700, 9000),
                tokens=(120000, 700000, 2200000),
                tool_calls=(150, 900),
                cost=(1.0, 3.5, 11.0),
                risk="low",
                reversibility="reversible",
                blast_radius="writes only under command-center/research/bp-res-03/**; no paywall circumvention route is reachable",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-03.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "skills/scholarly-literature-review",
                        "relation": "MERGE",
                        "license": "owner-proprietary",
                        "credit": "owner",
                    },
                    {
                        "source": "skills/biomedical-paper-triage",
                        "relation": "MERGE",
                        "license": "owner-proprietary",
                        "credit": "owner",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-03",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=[
                    "skills/scholarly-literature-review@1.0.0",
                    "skills/biomedical-paper-triage@1.0.0",
                ],
            ),
            "outputs": {
                "shortlist": B.artifact(
                    f"{root}/shortlist.json",
                    S("research-registry"),
                    min_bytes=1024,
                    consumers=["command-center/CLAIM-REGISTRY.json"],
                ),
                "access-table": B.artifact(
                    f"{root}/access-table.json",
                    S("license-and-rights-record"),
                    min_bytes=256,
                    consumers=["shortlist"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-03", 290),
                "acquisition_route_from_card": "ADAPT",
                "mechanism_signature": [
                    "identifier-anchored-resolution",
                    "legal-access-classification-veto",
                    "open-access-only-hard-deny",
                    "span-cited-extraction",
                    "t1t4-design-tiering",
                    "count-reconciliation-against-input-set",
                ],
                "contraindications": [
                    "NOT for a general web question - it is identifier-anchored by construction",
                    "NOT for grey literature or vendor whitepapers: no DOI means the tiering collapses",
                    "NEVER route through a paywall-circumvention proxy - that route is in tool_policy.deny, not merely discouraged",
                ],
                "replay_note": (
                    "the only genuinely replayable research blueprint of the twelve, because DOIs are "
                    "stable. verify is schema-equal rather than hash-equal on purpose: access_status "
                    "is time-varying, so a byte-equal replay would fail for a legitimate reason."
                ),
                "unverified": [
                    "UNVERIFIED at scale; settling experiment = a 30-DOI run auditing every "
                    "access_status against the publisher page and reporting the disagreement count.",
                ],
                "worked_example": {
                    "name": "ten-DOI set with three known paywalled papers",
                    "params": {
                        "input_mode": "identifiers",
                        "identifiers": [
                            "10.1038/s41586-020-2649-2",
                            "10.1093/nar/gkaa942",
                            "10.1016/j.cell.2019.05.031",
                        ],
                        "evidence_scheme": "t1t4",
                        "max_papers": 10,
                        "expand_citation_graph": False,
                    },
                    "expected_stage_order": [
                        "resolve-identifiers",
                        "resolve-topic",
                        "identifier-gate",
                        "classify-access",
                        "span-read-fanout",
                        "grade-evidence",
                        "citation-expand",
                        "access-gate",
                        "shortlist",
                    ],
                    "expected_skipped": ["resolve-topic", "citation-expand"],
                    "expected_max_parallel": 4,
                    "expected_gate_ids": ["identifier-gate", "access-gate"],
                    "acceptance": [
                        "exactly as many metadata-only rows as there are paywalled papers",
                        "a fabricated DOI appears under unresolved with the failing probe",
                        "open + paywalled + unresolved == the supplied identifier count",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "identifier-list-exhausted",
                            "why": "the run may not stop while any paper still lacks a verdict",
                            "fires_on": {
                                "identifiers_remaining": 0,
                                "papers_without_verdict": 0,
                                "expansion_papers_above_floor": 2,
                                "papers_graded": 9,
                            },
                            "does_not_fire_on": {
                                "identifiers_remaining": 0,
                                "papers_without_verdict": 3,
                                "expansion_papers_above_floor": 2,
                                "papers_graded": 9,
                            },
                        },
                        {
                            "rule": "expansion-below-tier-floor",
                            "why": "a barren expansion stops the walk only after enough papers have been graded to say so",
                            "fires_on": {
                                "identifiers_remaining": 4,
                                "papers_without_verdict": 1,
                                "expansion_papers_above_floor": 0,
                                "papers_graded": 7,
                            },
                            "does_not_fire_on": {
                                "identifiers_remaining": 4,
                                "papers_without_verdict": 1,
                                "expansion_papers_above_floor": 0,
                                "papers_graded": 2,
                            },
                        },
                    ],
                },
            },
        }
    )


# --------------------------------------------------------------- 4. BP-RES-04

_R4_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "Bash:python",
    "Write(command-center/verification/**)",
    "mcp__codex__codex",
]


def _res04() -> dict[str, Any]:
    root = "command-center/verification/bp-res-04"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-04-claim-decomposition-verification",
            "name": "Claim-Decomposition Verification Pass",
            "description": (
                "Take a FINISHED document - a report, an audit finding set, any agent's completion "
                "claim - decompose it into atomic claims, re-probe each with a MECHANICALLY "
                "DIFFERENT instrument, and emit a per-claim CONFIRMED / REFUTED / UNRESOLVED ledger. "
                "The verdict is computed by a deterministic SCRIPT, not by a model, and the script's "
                "signature rule closes the measured hole in the source implementation: a CONFIRMED "
                "or REFUTED claim whose `source_probe` is empty is a VIOLATION, never 'independent'. "
                "SHADOW and BLOCKING are both wired: `mode` selects which gate stage runs, so "
                "promoting the gate is a parameter change, not a rewrite."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["research-and-evidence", "collective-intelligence-and-meta"],
            "tags": ["claim-gate", "deterministic-verdict", "shadow-then-promote"],
            "flagship": True,
            "params": {
                "document": {
                    "type": "path",
                    "required": True,
                    "description": "The finished document under verification",
                },
                "instrument_registry": {
                    "type": "path",
                    "required": True,
                    "description": (
                        "Allowlist of verifier instruments. A required-but-missing registry makes "
                        "every claim UNRESOLVED - it never degrades to CONFIRMED."
                    ),
                },
                "mode": {
                    "type": "enum",
                    "enum": ["shadow", "blocking"],
                    "default": "shadow",
                    "description": "shadow = log and continue; blocking = a violation stops the caller",
                },
                "cross_vendor_top_n": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 0,
                    "maximum": 20,
                    "description": "How many load-bearing claims also get a cross-vendor verifier; 0 disables the pass",
                },
                "max_claims": {
                    "type": "integer",
                    "default": 120,
                    "minimum": 1,
                    "maximum": 2000,
                    "description": "Cap on atomic claims decomposed from one document",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "decomposer": {
                    "description": "Splits the document into atomic, independently checkable claims; adds no claim the document does not make",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/verification/**)",
                    ],
                    "speaking_rights": "always",
                },
                "instrument-assigner": {
                    "description": "Assigns each claim a verifier whose MECHANISM differs from the claim's own source probe; may not assign the source probe back",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/verification/**)",
                    ],
                    "speaking_rights": "always",
                },
                "claim-verifier": {
                    "description": "Re-probes ONE claim with its assigned instrument and never sees another verifier's verdict",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "voting",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Bash:python",
                        "Write(command-center/verification/**)",
                    ],
                    "min_participants": 1,
                    "max_participants": 32,
                    "speaking_rights": "always",
                },
                "cross-vendor-verifier": {
                    "description": "Second verifier from a different vendor for the load-bearing claims, because a same-vendor verifier shares the author's blind spots",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "effort": "high",
                    "authority": "voting",
                    "vote_weight": 2,
                    "independence": "cross-examining",
                    "cross_vendor_required": True,
                    "tool_permissions": ["Read", "Grep", "mcp__codex__codex"],
                    "speaking_rights": "rebuttal-only",
                },
                "gate-runner": {
                    "description": "Runs the deterministic gate script; has judge authority precisely because it exercises no judgement",
                    "vendor": "any",
                    "effort": "low",
                    "authority": "judge",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/verification/**)",
                    ],
                    "speaking_rights": "always",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R4_ALLOW),
                "deny": [
                    "Bash",
                    "WebFetch",
                    "WebSearch",
                    "Write(command-center/research/**)",
                    "Write(platform/schema/**)",
                ],
                "network": "none",
                "write_paths": ["command-center/verification/**"],
                "forbid_write_paths": [
                    "command-center/WORK-UNIT-CATALOG.json",
                    "platform/schema/**",
                ],
                "source_policy": {
                    "offline_only": True,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "escalating",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'gate-runner'",
                        "target": {
                            "model": "none-deterministic-script",
                            "vendor": "mixed",
                            "effort": "low",
                        },
                        "reason": "the verdict must be computed, not judged - routing the gate to a model would reintroduce the failure it exists to catch",
                    }
                ],
                "escalation": {
                    "on": ["low-confidence", "reviewer-refuted"],
                    "target": {
                        "model": "gpt-5-codex",
                        "vendor": "openai",
                        "effort": "high",
                    },
                    "max_escalations": 1,
                },
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "source-probe-required": {
                    "predicate": "custom-expression",
                    "expression": (
                        "confirmed_claims_without_source_probe == 0 "
                        "AND refuted_claims_without_source_probe == 0 "
                        "AND same_probe_rerun_claims == 0 "
                        "AND unresolved_claims_promoted_to_confirmed == 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "source-probe-required-shadow": {
                    "predicate": "custom-expression",
                    "expression": (
                        "confirmed_claims_without_source_probe == 0 "
                        "AND refuted_claims_without_source_probe == 0 "
                        "AND same_probe_rerun_claims == 0 "
                        "AND unresolved_claims_promoted_to_confirmed == 0"
                    ),
                    "blocking": False,
                    "evidence_required": True,
                    "on_fail": "record-and-continue",
                },
            },
            "stages": [
                {
                    "id": "decompose-claims",
                    "title": "Decompose the finished document into atomic claims",
                    "kind": "task",
                    "role": "decomposer",
                    "checkpoint": True,
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0401",
                        title="Split the document into atomic claims, each with the source probe the document itself cites",
                        phase="2B",
                        target=(
                            "Decompose the document into atomic claims. For each claim record the "
                            "SOURCE PROBE the document offers for it - the measurement that produced "
                            "it - or record that the document offers none. Add no claim the document "
                            "does not make."
                        ),
                        inputs=["params.document", "params.max_claims"],
                        deps=[],
                        role="decomposer",
                        tools=["Read", "Grep", "Write(command-center/verification/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/claims.json",
                        out_schema=S("claim-record"),
                        evidence="each claim carries the document offset or heading it came from, plus the source_probe text or an explicit null",
                        tests=[
                            "a document sentence carrying two independent assertions must yield two claims, not one compound claim",
                            "both-states: a claim whose document offers NO probe must record source_probe null, and an adjacent claim with a probe must record it",
                        ],
                        reviewer="the instrument assigner rejects any claim that is not independently checkable and returns it for re-splitting",
                        postcondition="the claim file exists, parses, and every claim has an anchor into the document plus a source_probe field that is present or explicitly null",
                        retry="two strikes then pivot: after two rejected decompositions, enumerate at least two alternative splitting strategies",
                        failure_classes=[
                            "decomposition-ambiguous",
                            "document-unreadable",
                        ],
                        mechanism="safe-atomic-claim-decomposition",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/claims.json",
                            S("claim-record"),
                            sentinel="SUCCESS:BPR-0401",
                            consumers=["assign-instruments"],
                        )
                    ],
                },
                {
                    "id": "assign-instruments",
                    "title": "Assign a mechanically different instrument per claim",
                    "kind": "task",
                    "depends_on": ["decompose-claims"],
                    "role": "instrument-assigner",
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0402",
                        title="Map each claim to a verifier instrument whose mechanism differs from its source probe",
                        phase="2B",
                        target=(
                            "For each claim pick a verifier from the instrument registry whose "
                            "mechanism differs from the claim's source probe - a different shell, a "
                            "different data field, a different measurement. Record WHY it differs. If "
                            "no different instrument exists, mark the claim NO-INDEPENDENT-INSTRUMENT."
                        ),
                        inputs=[f"{root}/claims.json", "params.instrument_registry"],
                        deps=["BPR-0401"],
                        role="instrument-assigner",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/verification/**)",
                        ],
                        substrate="local-single",
                        timeout=1200,
                        out_path=f"{root}/assignment-matrix.json",
                        out_schema=S("assignment-matrix"),
                        evidence="each row carries source_probe fingerprint, verifier fingerprint, and the one-line reason the two mechanisms differ",
                        tests=[
                            "a claim whose only available instrument equals its source probe must be marked NO-INDEPENDENT-INSTRUMENT, never assigned that instrument",
                            "a missing instrument registry must make the stage FAIL rather than assign a default instrument",
                        ],
                        reviewer="the gate script independently recomputes both fingerprints and flags same-probe-rerun regardless of what this stage claimed",
                        postcondition="every claim has an assignment row with two distinct mechanism fingerprints, or an explicit NO-INDEPENDENT-INSTRUMENT marker",
                        retry="fixed backoff, at most 2 attempts; a second failure marks the affected claims NO-INDEPENDENT-INSTRUMENT",
                        failure_classes=["instrument-unavailable", "same-probe-rerun"],
                        mechanism="mechanism-difference-assignment",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/assignment-matrix.json",
                            S("assignment-matrix"),
                            sentinel="SUCCESS:BPR-0402",
                            consumers=[
                                "reprobe-fanout",
                                "deterministic-gate",
                                "shadow-gate",
                            ],
                        )
                    ],
                },
                {
                    "id": "reprobe-fanout",
                    "title": "Re-probe every claim in parallel, each with its own instrument",
                    "kind": "fanout",
                    "depends_on": ["assign-instruments"],
                    "over": {
                        "source": "artifact",
                        "ref": f"{root}/assignment-matrix.json",
                        "item_var": "claim",
                        "key_field": "claim_id",
                    },
                    "max_concurrency": 8,
                    "arrival_stagger_ms": 200,
                    "max_items": 2000,
                    "on_item_failure": "continue",
                    "body": [
                        {
                            "id": "reprobe-claim",
                            "title": "Re-probe one claim with its assigned instrument",
                            "kind": "task",
                            "role": "claim-verifier",
                            "timeout_seconds": 900,
                            "work_unit": B.wu(
                                uid="BPR-0403",
                                title="Run the assigned instrument and emit one verdict with its verifier probe recorded",
                                phase="2B",
                                target=(
                                    "Run the assigned instrument against the claim and emit exactly one "
                                    "verdict: CONFIRMED, REFUTED or UNRESOLVED. Record the verifier "
                                    "probe verbatim. An unavailable instrument yields UNRESOLVED naming "
                                    "the missing instrument - never CONFIRMED."
                                ),
                                inputs=[
                                    f"{root}/assignment-matrix.json",
                                    "params.instrument_registry",
                                ],
                                deps=["BPR-0402"],
                                role="claim-verifier",
                                tools=[
                                    "Read",
                                    "Grep",
                                    "Glob",
                                    "Bash:python",
                                    "Write(command-center/verification/**)",
                                ],
                                substrate="local-parallel",
                                timeout=900,
                                out_path=f"{root}/reprobes/claim-verdict.json",
                                out_schema=S("reprobe-record"),
                                evidence="the verdict row carries the verifier probe verbatim, its raw output, and an anchor (file:line, command output, or URL)",
                                tests=[
                                    "an unavailable instrument must yield UNRESOLVED naming the instrument (both-states: the same claim with the instrument present must yield a real verdict)",
                                ],
                                reviewer="no verifier sees another verifier's verdict; the reconciliation is the gate script's job",
                                postcondition="exactly one verdict row exists for the claim, carrying a verifier probe and an anchor",
                                retry="two strikes then pivot: after two instrument failures return UNRESOLVED with the failure recorded",
                                failure_classes=[
                                    "instrument-unavailable",
                                    "detector-failure",
                                    "timeout",
                                ],
                                mechanism="independent-per-claim-reprobe",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/reprobes/claim-verdict.json",
                                    S("reprobe-record"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPR-0403",
                                    consumers=[
                                        "deterministic-gate",
                                        "shadow-gate",
                                        "emit-ledger",
                                    ],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "all",
                        "on_partial": "fail",
                        "require_stages": ["reprobe-claim"],
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "cross-vendor-reprobe",
                    "title": "Cross-vendor second verifier on the load-bearing claims",
                    "kind": "task",
                    "depends_on": ["reprobe-fanout"],
                    "when": "cross_vendor_top_n > 0",
                    "role": "cross-vendor-verifier",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0404",
                        title="Independently re-probe the top-N load-bearing claims from a different vendor",
                        phase="2B",
                        target=(
                            "For the N most load-bearing claims, re-probe from a different vendor with "
                            "no sight of the in-vendor verdict, and record agreement or disagreement "
                            "as an independence measurement."
                        ),
                        inputs=[
                            f"{root}/reprobes/claim-verdict.json",
                            "params.cross_vendor_top_n",
                        ],
                        deps=["BPR-0403"],
                        role="cross-vendor-verifier",
                        tools=["Read", "Grep", "mcp__codex__codex"],
                        substrate="cross-vendor-codex",
                        timeout=1800,
                        out_path=f"{root}/cross-vendor-audit.json",
                        out_schema=S("independence-audit"),
                        evidence="per claim: the second-vendor probe, its output, and whether it agrees; a severed dispatch is recorded as NOT-CHECKED, never as agreement",
                        tests=[
                            "a killed dispatch must produce NOT-CHECKED, never silence and never an inferred agreement",
                            "a result string containing a background receipt must be rejected outright rather than parsed as a verdict",
                        ],
                        reviewer="the gate script treats a NOT-CHECKED cross-vendor row as absent evidence, not as corroboration",
                        postcondition="each selected claim has a second-vendor row carrying a probe, an output and an agreement flag or NOT-CHECKED",
                        model="gpt-5-codex",
                        vendor="openai",
                        basis="cross-vendor independence: a same-vendor verifier shares the author's blind spots",
                        retry="two strikes then pivot: after two severed dispatches record NOT-CHECKED and stop retrying",
                        failure_classes=[
                            "severed-stream",
                            "codex-exit-nonzero",
                            "win-arg-limit",
                        ],
                        mechanism="cross-vendor-independence-audit",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/cross-vendor-audit.json",
                            S("independence-audit"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0404",
                            consumers=["deterministic-gate", "shadow-gate"],
                        )
                    ],
                },
                {
                    "id": "shadow-gate",
                    "title": "SHADOW mode: run the deterministic gate, log the violations, do not block",
                    "kind": "gate",
                    "depends_on": ["cross-vendor-reprobe"],
                    "when": "mode == 'shadow'",
                    "gate_ref": "source-probe-required-shadow",
                },
                {
                    "id": "blocking-gate",
                    "title": "BLOCKING mode: a violation stops the caller",
                    "kind": "gate",
                    "depends_on": ["cross-vendor-reprobe"],
                    "when": "mode == 'blocking'",
                    "gate_ref": "source-probe-required",
                },
                {
                    "id": "emit-ledger",
                    "title": "Emit the per-claim ledger and the violation list",
                    "kind": "task",
                    "depends_on": ["shadow-gate", "blocking-gate"],
                    "role": "gate-runner",
                    "timeout_seconds": 900,
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/verification/**)",
                    ],
                    "work_unit": B.wu(
                        uid="BPR-0405",
                        title="Compute the ledger deterministically: verdicts, violations, ok flag",
                        phase="2B",
                        target=(
                            "Reduce the verdicts to one ledger: per claim the verdict, source_probe, "
                            "verifier_probe, independence flag and anchor; plus the violation list and "
                            "an ok flag. A CONFIRMED or REFUTED verdict with an empty source_probe is "
                            "a violation - the exact case the source implementation's own 30-test "
                            "regression did not cover."
                        ),
                        inputs=[
                            f"{root}/reprobes/claim-verdict.json",
                            f"{root}/cross-vendor-audit.json",
                            f"{root}/assignment-matrix.json",
                        ],
                        deps=["BPR-0403", "BPR-0404"],
                        role="gate-runner",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/verification/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/claim-ledger.json",
                        out_schema=S("attestation-ledger"),
                        evidence="the ledger is produced by a script whose exit code and stdout are recorded; ok is computed from the violation list, never asserted",
                        tests=[
                            "MANDATORY both-states: a ledger input with a CONFIRMED claim carrying an EMPTY source_probe must produce a violation and ok=false; filling that one field must flip ok to true with everything else unchanged",
                            "identical source and verifier fingerprints must produce a same-probe-rerun violation",
                            "a clean input must produce violations == [] - the gate must be able to pass, or it is a permanent red light",
                        ],
                        reviewer="the gate is deterministic, so review targets the SCRIPT and its both-states battery rather than the verdict",
                        postcondition="the ledger exists, parses, every claim has exactly one verdict, and ok equals (violations == [])",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="a deterministic reducer: model judgement here is what produced the defect being fixed",
                        retry="none: a deterministic reducer over unchanged inputs cannot produce a different result",
                        failure_classes=["schema-invalid", "gate-input-incomplete"],
                        mechanism="deterministic-verdict-reduction",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/claim-ledger.json",
                            S("attestation-ledger"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPR-0405",
                            consumers=["command-center/CLAIM-REGISTRY.json"],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "every-claim-has-a-verdict",
                    "expression": "claims_without_verdict == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "claims_decomposed >= 1",
                    "on_stop": "complete",
                },
                {
                    "id": "no-independent-instrument-left",
                    "expression": "unassigned_claims == 0 AND instruments_available >= 1",
                    "applies_to": "workflow",
                    "on_stop": "escalate",
                },
            ],
            "retry_policy": B.retry_none(),
            "failure_policy": B.failure(
                "escalate-to-human",
                [
                    "instrument-unavailable",
                    "same-probe-rerun",
                    "gate-input-incomplete",
                    "severed-stream",
                ],
                escalate_to="emit-ledger",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="work-unit",
                keys=[
                    "workflow_id",
                    "workflow_version",
                    "stage_id",
                    "item_key",
                    "inputs_hash",
                ],
            ),
            "replay": B.replay_deterministic(
                20260810, f"{root}/replay/journal.jsonl", verify="hash-equal"
            ),
            "cache": B.cache_block(
                f"{root}/cache",
                [
                    "workflow_version",
                    "stage_id",
                    "item_key",
                    "inputs_hash",
                    "tool_versions",
                ],
                ttl=604800,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "Bash:python",
                    "Write(command-center/verification/**)",
                    "mcp__codex__codex",
                ],
                emits=[
                    "plan",
                    "estimate",
                    "permission-report",
                    "graph",
                    "artifact-diff",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(300, 1500, 5400),
                tokens=(80000, 400000, 1400000),
                tool_calls=(90, 600),
                cost=(0.5, 2.0, 7.0),
                risk="low",
                reversibility="reversible",
                blast_radius="read-only over the document; writes only under command-center/verification/bp-res-04/**",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-04.bundle.json",
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
                        "source": "07f465f3:.agents/skills/claim-verify-gate",
                        "relation": "REPAIR",
                        "license": "owner-proprietary",
                        "credit": "owner (undeployed skill)",
                    },
                    {
                        "source": "rules/common/single-signal-verification.md",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "measured defect: _validate() at :132-156 does not require source_probe",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-04",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=["07f465f3:.agents/skills/claim-verify-gate"],
            ),
            "outputs": {
                "ledger": B.artifact(
                    f"{root}/claim-ledger.json",
                    S("attestation-ledger"),
                    min_bytes=512,
                    consumers=["command-center/CLAIM-REGISTRY.json"],
                ),
                "assignment": B.artifact(
                    f"{root}/assignment-matrix.json",
                    S("assignment-matrix"),
                    min_bytes=256,
                    consumers=["emit-ledger"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-04", 334),
                "acquisition_route_from_card": "REPAIR",
                "mechanism_signature": [
                    "safe-atomic-claim-decomposition",
                    "mechanism-difference-instrument-assignment",
                    "independent-per-claim-reprobe",
                    "deterministic-script-verdict-reduction",
                    "empty-source-probe-is-a-violation",
                    "shadow-or-blocking-gate-by-parameter",
                ],
                "contraindications": [
                    "NOT a substitute for running the code - that is a test blueprint",
                    "NOT for creative or subjective output where `claim` is undefined",
                    "do NOT run it on its own output: a gate verifying itself is a single signal",
                ],
                "the_repaired_defect": (
                    "The source implementation's _validate() requires an id, text and a recognised "
                    "verdict but NOT source_probe, so an absent source normalises to empty strings "
                    "that any non-empty verifier trivially differs from - and the same-probe-rerun "
                    "check cannot fire. Its shipped 30-test regression passes because its "
                    "missing-probe case omits the VERIFIER, not the SOURCE. The mandatory both-states "
                    "test on BPR-0405 is that missing case."
                ),
                "owner_decision": "Ship the claim gate SHADOW-only, or let it block once its both-states battery is green? Both paths are wired; `mode` selects.",
                "unverified": [
                    "UNVERIFIED that closing the hole changes a real verdict within a month; "
                    "settling experiment = run the gate in shadow over the next 20 completion claims "
                    "and count how many carry a CONFIRMED verdict with no source probe.",
                ],
                "worked_example": {
                    "name": "gate a finished audit report in shadow mode",
                    "params": {
                        "document": "command-center/research/bp-res-01/report.json",
                        "instrument_registry": "command-center/verification/instrument-registry.json",
                        "mode": "shadow",
                        "cross_vendor_top_n": 3,
                        "max_claims": 60,
                    },
                    "expected_stage_order": [
                        "decompose-claims",
                        "assign-instruments",
                        "reprobe-fanout",
                        "cross-vendor-reprobe",
                        "shadow-gate",
                        "blocking-gate",
                        "emit-ledger",
                    ],
                    "expected_skipped": ["blocking-gate"],
                    "expected_max_parallel": 8,
                    "expected_gate_ids": ["shadow-gate", "blocking-gate"],
                    "mode_variants": [
                        {"mode": "shadow", "expected_skipped": ["blocking-gate"]},
                        {"mode": "blocking", "expected_skipped": ["shadow-gate"]},
                    ],
                    "acceptance": [
                        "a CONFIRMED claim with an empty source_probe appears in violations[] and ok is false",
                        "a claim whose verifier fingerprint equals its source fingerprint is flagged same-probe-rerun",
                        "a clean document yields violations == []",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "every-claim-has-a-verdict",
                            "why": "the floor stops the rule firing vacuously on a document that decomposed into nothing",
                            "fires_on": {
                                "claims_without_verdict": 0,
                                "claims_decomposed": 42,
                                "unassigned_claims": 0,
                                "instruments_available": 6,
                            },
                            "does_not_fire_on": {
                                "claims_without_verdict": 0,
                                "claims_decomposed": 0,
                                "unassigned_claims": 0,
                                "instruments_available": 6,
                            },
                        },
                        {
                            "rule": "no-independent-instrument-left",
                            "why": "an empty instrument registry must escalate rather than pass",
                            "fires_on": {
                                "claims_without_verdict": 2,
                                "claims_decomposed": 42,
                                "unassigned_claims": 0,
                                "instruments_available": 6,
                            },
                            "does_not_fire_on": {
                                "claims_without_verdict": 2,
                                "claims_decomposed": 42,
                                "unassigned_claims": 0,
                                "instruments_available": 0,
                            },
                        },
                    ],
                },
            },
        }
    )


def blueprints() -> list[dict[str, Any]]:
    return [_res03(), _res04()]
