"""Blueprints 5-6 of 12: BP-RES-05 Briefed-Fact Re-Probe Council, BP-RES-06 Verdict Refresh."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(HERE))

import bp1_build as B  # noqa: E402

S = B.schema

# --------------------------------------------------------------- 5. BP-RES-05

_R5_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "Bash:python",
    "Bash:pwsh",
    "Write(command-center/preflight/**)",
    "mcp__codex__codex",
]


def _res05() -> dict[str, Any]:
    root = "command-center/preflight/bp-res-05"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-05-briefed-fact-reprobe-council",
            "name": "Briefed-Fact Re-Probe Council",
            "description": (
                "Stop a wrong 'VERIFIED GROUND TRUTH' in an orchestrator brief from propagating "
                "into every lane. Each briefed fact is re-probed with a mechanically different "
                "instrument BEFORE any lane launches, and the reconciler reads PROBES rather than "
                "counting votes - because in the measured baseline 4 of 6 agents refuted a false "
                "briefed fact while 2 'CONFIRMED' it by re-running the orchestrator's own broken "
                "probe. The pipeline ends in a HARD BARRIER: the fan-out cannot start until every "
                "briefed fact carries a verdict and the corrections are emitted. A zero-correction "
                "result is itself suspicious and triggers a spot audit rather than a green light."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["research-and-evidence", "collective-intelligence-and-meta"],
            "tags": ["pre-fanout-barrier", "probe-wins-over-votes", "reprobe"],
            "flagship": True,
            "params": {
                "brief": {
                    "type": "path",
                    "required": True,
                    "description": "The orchestrator brief whose asserted facts are under test",
                },
                "planned_fanout_size": {
                    "type": "integer",
                    "required": True,
                    "minimum": 1,
                    "maximum": 1024,
                    "description": "How many agents the brief is about to launch; the reason this gate is cheap by comparison",
                },
                "cross_vendor_on_blast_radius": {
                    "type": "boolean",
                    "default": True,
                    "description": "Re-probe cross-vendor any fact whose falsity would invalidate more than two lanes",
                },
                "max_facts": {
                    "type": "integer",
                    "default": 40,
                    "minimum": 1,
                    "maximum": 400,
                    "description": "Cap on briefed facts extracted from one brief",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "fact-extractor": {
                    "description": "Pulls every factual assertion out of the brief together with the probe and timestamp the brief cites for it",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/preflight/**)",
                    ],
                    "speaking_rights": "always",
                },
                "instrument-assigner": {
                    "description": "Assigns each fact a re-probe that is mechanically DIFFERENT from the brief's own probe and must say why it differs",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Glob",
                        "Write(command-center/preflight/**)",
                    ],
                    "speaking_rights": "always",
                },
                "reprober": {
                    "description": (
                        "Re-probes ONE fact. Is told the original probe explicitly and is FORBIDDEN "
                        "from re-running it; re-running the briefed probe is not a second signal"
                    ),
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
                        "Bash:pwsh",
                        "Write(command-center/preflight/**)",
                    ],
                    "min_participants": 1,
                    "max_participants": 40,
                    "speaking_rights": "always",
                },
                "cross-vendor-reprober": {
                    "description": "Second-vendor re-probe for a fact whose falsity would invalidate more than two lanes",
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
                "reconciler": {
                    "description": (
                        "Resolves a split verdict by READING THE PROBES, never by counting agents; "
                        "a specific probe beats an agent majority"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "max",
                    "authority": "judge",
                    "independence": "cross-examining",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/preflight/**)",
                    ],
                    "speaking_rights": "always",
                },
                "owner": {
                    "description": "The human owner - the only role that may accept a corrected brief or authorise launching anyway",
                    "vendor": "human",
                    "authority": "owner",
                    "speaking_rights": "on-request",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R5_ALLOW),
                "deny": [
                    "Bash",
                    "WebFetch",
                    "WebSearch",
                    "Write(command-center/research/**)",
                ],
                "network": "none",
                "write_paths": ["command-center/preflight/**"],
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
                "strategy": "vendor-diverse",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'cross-vendor-reprober'",
                        "target": {
                            "model": "gpt-5-codex",
                            "vendor": "openai",
                            "effort": "high",
                        },
                        "reason": "a same-vendor re-probe can share the mechanism that produced the false fact",
                    }
                ],
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "mechanism-independence": {
                    "predicate": "custom-expression",
                    "expression": (
                        "reprobes_sharing_mechanism_with_original == 0 "
                        "AND facts_without_assigned_instrument == 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "retry",
                },
                "brief-corrected": {
                    "predicate": "custom-expression",
                    "expression": "facts_without_verdict == 0 AND corrections_emitted == true",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "escalate-to-human",
                },
            },
            "stages": [
                {
                    "id": "extract-facts",
                    "title": "Extract every asserted fact with its stated probe and timestamp",
                    "kind": "task",
                    "role": "fact-extractor",
                    "checkpoint": True,
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0501",
                        title="Enumerate the brief's factual assertions, each with the probe and date the brief cites",
                        phase="2B",
                        target=(
                            "List every factual claim the brief asserts as ground truth. For each, "
                            "record the probe the brief cites and its timestamp, or record that the "
                            "brief cites NONE - an undeclared source probe is zero signals, not one."
                        ),
                        inputs=["params.brief", "params.max_facts"],
                        deps=[],
                        role="fact-extractor",
                        tools=["Read", "Grep", "Write(command-center/preflight/**)"],
                        substrate="local-single",
                        timeout=1200,
                        out_path=f"{root}/briefed-facts.json",
                        out_schema=S("stale-premise-reprobe"),
                        evidence="each fact carries its brief offset, the cited probe text or an explicit null, the timestamp, and the count of lanes that would be invalidated if it were false",
                        tests=[
                            "a brief sentence asserting a fact with NO probe must be recorded with probe null, not skipped",
                            "both-states: a fact WITH a cited probe in the same brief must carry that probe verbatim",
                        ],
                        reviewer="the instrument assigner rejects any fact whose blast-radius count is missing, because that count drives cross-vendor selection",
                        postcondition="every asserted fact appears once with a probe field (present or null), a timestamp and a blast-radius count",
                        retry="two strikes then pivot: after two extractions the owner is asked whether the brief is even fact-shaped",
                        failure_classes=["brief-unreadable", "spec-underspecified"],
                        mechanism="briefed-fact-extraction-with-probe",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/briefed-facts.json",
                            S("stale-premise-reprobe"),
                            sentinel="SUCCESS:BPR-0501",
                            consumers=["assign-different-instrument"],
                        )
                    ],
                },
                {
                    "id": "assign-different-instrument",
                    "title": "Assign a mechanically different re-probe per fact",
                    "kind": "task",
                    "depends_on": ["extract-facts"],
                    "role": "instrument-assigner",
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0502",
                        title="Pick a different shell, a different data field or a different measurement per fact",
                        phase="2B",
                        target=(
                            "For each briefed fact choose a re-probe that differs from the brief's own "
                            "probe in MECHANISM - a different shell, a different data field, a "
                            "different instrument - and state the difference in one line. Where no "
                            "different instrument exists, mark the fact NO-INDEPENDENT-INSTRUMENT."
                        ),
                        inputs=[f"{root}/briefed-facts.json"],
                        deps=["BPR-0501"],
                        role="instrument-assigner",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/preflight/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/reprobe-assignments.json",
                        out_schema=S("assignment-matrix"),
                        evidence="each row states the original mechanism, the assigned mechanism, and the one-line reason they differ",
                        tests=[
                            "a fact whose brief probe was a Git-Bash `which` must NOT be assigned another Git-Bash `which`; the assignment must name a different shell",
                            "a fact with no available alternative instrument must be marked NO-INDEPENDENT-INSTRUMENT rather than assigned the original",
                        ],
                        reviewer="the independence gate recomputes mechanism equality independently of this stage's own claim",
                        postcondition="every fact has an assignment with two distinct mechanisms, or an explicit NO-INDEPENDENT-INSTRUMENT marker",
                        retry="fixed backoff, at most 3 attempts; the gate returns rejected assignments here for re-assignment",
                        failure_classes=["same-probe-rerun", "instrument-unavailable"],
                        mechanism="different-mechanism-assignment",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/reprobe-assignments.json",
                            S("assignment-matrix"),
                            sentinel="SUCCESS:BPR-0502",
                            consumers=["independence-gate", "reprobe-fanout"],
                        )
                    ],
                },
                {
                    "id": "independence-gate",
                    "title": "Reject and re-assign any re-probe that shares a mechanism with the original",
                    "kind": "gate",
                    "depends_on": ["assign-different-instrument"],
                    "gate_ref": "mechanism-independence",
                },
                {
                    "id": "reprobe-fanout",
                    "title": "One short agent per fact, each forbidden from re-running the briefed probe",
                    "kind": "fanout",
                    "depends_on": ["independence-gate"],
                    "over": {
                        "source": "artifact",
                        "ref": f"{root}/reprobe-assignments.json",
                        "item_var": "fact",
                        "key_field": "fact_id",
                    },
                    "max_concurrency": 6,
                    "arrival_stagger_ms": 250,
                    "max_items": 400,
                    "on_item_failure": "continue",
                    "body": [
                        {
                            "id": "reprobe-fact",
                            "title": "Re-probe one briefed fact with the assigned different instrument",
                            "kind": "task",
                            "role": "reprober",
                            "timeout_seconds": 600,
                            "work_unit": B.wu(
                                uid="BPR-0503",
                                title="Confirm or refute one briefed fact using a mechanically different probe",
                                phase="2B",
                                target=(
                                    "Run the assigned instrument. Emit CONFIRMED, REFUTED or "
                                    "UNRESOLVED plus the verbatim probe and output. Re-running the "
                                    "briefed probe does NOT count and must never be reported as "
                                    "CONFIRMED - if that is all you can do, return UNRESOLVED."
                                ),
                                inputs=[
                                    f"{root}/reprobe-assignments.json",
                                    f"{root}/briefed-facts.json",
                                ],
                                deps=["BPR-0502"],
                                role="reprober",
                                tools=[
                                    "Read",
                                    "Grep",
                                    "Glob",
                                    "Bash:python",
                                    "Bash:pwsh",
                                    "Write(command-center/preflight/**)",
                                ],
                                substrate="local-parallel",
                                timeout=600,
                                out_path=f"{root}/reprobes/fact-verdict.json",
                                out_schema=S("reprobe-record"),
                                evidence="verdict + the exact command or field read + its raw output + a one-line statement of how this differs from the briefed probe",
                                tests=[
                                    "a fact whose obvious probe is BROKEN (a Git-Bash `which` against a .cmd shim) must yield: PROBE refuted, FACT confirmed - the two are separate verdicts",
                                    "a re-probe that ends up re-running the original mechanism must self-report UNRESOLVED with that reason",
                                ],
                                reviewer="no re-prober sees another's verdict; reconciliation reads probes centrally",
                                postcondition="exactly one verdict exists for the fact, carrying its probe, its output and the difference statement",
                                retry="two strikes then pivot: after two instrument failures return UNRESOLVED and demote the fact to a low-confidence assumption",
                                failure_classes=[
                                    "instrument-unavailable",
                                    "same-probe-rerun",
                                    "detector-failure",
                                ],
                                mechanism="forbidden-original-probe-reprobe",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/reprobes/fact-verdict.json",
                                    S("reprobe-record"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPR-0503",
                                    consumers=["reconcile-by-probe"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "all",
                        "on_partial": "fail",
                        "require_stages": ["reprobe-fact"],
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "cross-vendor-reprobe",
                    "title": "Cross-vendor re-probe for any fact that would invalidate more than two lanes",
                    "kind": "task",
                    "depends_on": ["reprobe-fanout"],
                    "when": "cross_vendor_on_blast_radius == true",
                    "role": "cross-vendor-reprober",
                    "timeout_seconds": 1200,
                    "work_unit": B.wu(
                        uid="BPR-0504",
                        title="Second-vendor re-probe of the high-blast-radius facts",
                        phase="2B",
                        target=(
                            "For every fact whose falsity would invalidate more than two planned "
                            "lanes, re-probe from a different vendor with no sight of the in-vendor "
                            "verdict, and record agreement or disagreement."
                        ),
                        inputs=[
                            f"{root}/reprobes/fact-verdict.json",
                            f"{root}/briefed-facts.json",
                        ],
                        deps=["BPR-0503"],
                        role="cross-vendor-reprober",
                        tools=["Read", "Grep", "mcp__codex__codex"],
                        substrate="cross-vendor-codex",
                        timeout=1200,
                        out_path=f"{root}/cross-vendor-reprobe.json",
                        out_schema=S("independence-audit"),
                        evidence="per fact: the second-vendor probe, its output, and the agreement flag; a severed dispatch is NOT-CHECKED, never agreement",
                        tests=[
                            "a killed dispatch must produce NOT-CHECKED with the diagnostic tail, never silence",
                            "a background receipt string must be rejected outright, never parsed as a verdict",
                        ],
                        reviewer="the reconciler treats NOT-CHECKED as absent evidence and says so in the correction record",
                        postcondition="every high-blast fact has a second-vendor row carrying a probe and an agreement flag or NOT-CHECKED",
                        model="gpt-5-codex",
                        vendor="openai",
                        basis="vendor independence on exactly the facts whose falsity is most expensive",
                        retry="two strikes then pivot: after two severed dispatches record NOT-CHECKED and stop",
                        failure_classes=[
                            "severed-stream",
                            "codex-exit-nonzero",
                            "win-arg-limit",
                        ],
                        mechanism="blast-radius-scoped-cross-vendor-reprobe",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/cross-vendor-reprobe.json",
                            S("independence-audit"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0504",
                            consumers=["reconcile-by-probe"],
                        )
                    ],
                },
                {
                    "id": "reconcile-by-probe",
                    "title": "Resolve every split verdict by reading probes, never by counting agents",
                    "kind": "task",
                    "depends_on": ["reprobe-fanout", "cross-vendor-reprobe"],
                    "role": "reconciler",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0505",
                        title="Rule on each fact from the probes and emit the brief corrections",
                        phase="2B",
                        target=(
                            "For each fact, read every probe and rule CONFIRMED / REFUTED / "
                            "UNRESOLVED. On a split, the more specific probe wins - agent counts are "
                            "not evidence. Emit the brief corrections, and demote any UNRESOLVED fact "
                            "from 'ground truth' to 'assumption (low confidence)'."
                        ),
                        inputs=[
                            f"{root}/reprobes/fact-verdict.json",
                            f"{root}/cross-vendor-reprobe.json",
                        ],
                        deps=["BPR-0503", "BPR-0504"],
                        role="reconciler",
                        tools=["Read", "Grep", "Write(command-center/preflight/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/brief-corrections.json",
                        out_schema=S("divergence-ruling"),
                        evidence="each ruling names the winning probe and why it is more specific than the loser; a ruling justified by a vote count is invalid",
                        tests=[
                            "seed a 4-refute / 2-confirm split where the 2 re-ran the broken briefed probe - the ruling must be REFUTED and must cite the probe, not the 4",
                            "both-states: the same split with the 2 using a genuinely different instrument must NOT be auto-resolved; it must be UNRESOLVED and escalate",
                        ],
                        reviewer="the owner checkpoint sees the ruling and the raw probes side by side, so the reconciler cannot launder a vote count as a probe",
                        postcondition="every fact has a ruling naming its winning probe, and the corrections list exists even when empty",
                        retry="two strikes then pivot: a second failure escalates the whole brief to the owner rather than guessing",
                        failure_classes=["split-unresolvable", "overclaim"],
                        mechanism="probe-wins-over-vote-count",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/brief-corrections.json",
                            S("divergence-ruling"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPR-0505",
                            consumers=[
                                "zero-correction-audit",
                                "launch-barrier",
                                "owner-accept",
                            ],
                        )
                    ],
                },
                {
                    "id": "zero-correction-audit",
                    "title": "A zero-correction result is itself suspicious - spot-audit it",
                    "kind": "task",
                    "depends_on": ["reconcile-by-probe"],
                    "when": "corrections_found == 0",
                    "role": "reconciler",
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0506",
                        title="Spot-audit three facts by hand when the council found nothing to correct",
                        phase="2B",
                        target=(
                            "The measured baseline had FOUR false 'VERIFIED GROUND TRUTH' facts in one "
                            "run, so a zero-correction verdict is more likely a broken council than a "
                            "perfect brief. Hand-audit three facts, including the highest-blast one, "
                            "and record whether the council's instruments could have detected a "
                            "falsehood at all."
                        ),
                        inputs=[
                            f"{root}/brief-corrections.json",
                            f"{root}/reprobes/fact-verdict.json",
                        ],
                        deps=["BPR-0505"],
                        role="reconciler",
                        tools=[
                            "Read",
                            "Grep",
                            "Glob",
                            "Bash:python",
                            "Write(command-center/preflight/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/zero-correction-audit.json",
                        out_schema=S("negative-evidence-audit"),
                        evidence="for each audited fact: the instrument used, and an explicit statement of what a FALSE version of this fact would have looked like to that instrument",
                        tests=[
                            "MANDATORY detector control: inject one KNOWN-FALSE fact into the brief - the council must refute it, and this audit must show the instrument that caught it",
                            "an instrument that cannot distinguish the true from the false version must be reported as measuring nothing",
                        ],
                        reviewer="the owner sees this audit before accepting a zero-correction brief",
                        postcondition="three facts are audited and each carries the would-a-falsehood-be-visible answer",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["detector-failure", "instrument-unavailable"],
                        mechanism="zero-result-is-suspicious-audit",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/zero-correction-audit.json",
                            S("negative-evidence-audit"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0506",
                            consumers=["launch-barrier", "owner-accept"],
                        )
                    ],
                },
                {
                    "id": "corrections-gate",
                    "title": "Every briefed fact has a verdict and the corrections are emitted",
                    "kind": "gate",
                    "depends_on": ["reconcile-by-probe", "zero-correction-audit"],
                    "gate_ref": "brief-corrected",
                },
                {
                    "id": "launch-barrier",
                    "title": "HARD BARRIER: the real fan-out may not start before this point",
                    "kind": "barrier",
                    "depends_on": ["corrections-gate"],
                    "barrier": {
                        "mode": "all",
                        "on_partial": "fail",
                        "require_stages": ["reconcile-by-probe", "corrections-gate"],
                        "reject_result_matching": ["started in the background"],
                        "verify_artifact_exists": True,
                    },
                    "joins": ["reconcile-by-probe", "zero-correction-audit"],
                },
                {
                    "id": "owner-accept",
                    "title": "Owner accepts the corrected brief, or authorises launching anyway",
                    "kind": "human_checkpoint",
                    "depends_on": ["launch-barrier"],
                    "when": "corrections_found > 0",
                    "prompt": (
                        "The re-probe council corrected the brief. Accept the corrections before the "
                        "fan-out launches, dispute a specific ruling (the probes are attached), or "
                        "authorise launching on the uncorrected brief and accept the lane risk."
                    ),
                    "approvers": ["owner"],
                    "approval_mode": "owner-only",
                    "timeout_seconds": 86400,
                    "on_timeout": "escalate",
                    "owner_approval_required": True,
                    "options": [
                        "accept-corrections",
                        "dispute-a-ruling",
                        "launch-uncorrected",
                    ],
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
                    "id": "every-fact-has-a-verdict",
                    "expression": "facts_without_verdict == 0",
                    "applies_to": "workflow",
                    "minimum_conditions": "facts_extracted >= 1",
                    "on_stop": "complete",
                },
                {
                    "id": "no-instrument-diversity-left",
                    "expression": "facts_with_no_independent_instrument > 0",
                    "applies_to": "workflow",
                    "on_stop": "escalate",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                3,
                escalate_to="owner-accept",
                retry_on=["instrument-unavailable", "severed-stream"],
            ),
            "failure_policy": B.failure(
                "escalate-to-human",
                [
                    "same-probe-rerun",
                    "instrument-unavailable",
                    "split-unresolvable",
                    "detector-failure",
                ],
                escalate_to="owner-accept",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="fanout-item",
                keys=["workflow_id", "stage_id", "item_key", "inputs_hash"],
            ),
            "replay": {
                "deterministic": False,
                "journal_path": f"{root}/replay/assignments.jsonl",
                "record": [
                    "params",
                    "inputs",
                    "tool_calls",
                    "tool_results",
                    "env_fingerprint",
                ],
                "forbid_nondeterministic_sources": ["random"],
                "replay_source": "recorded-journal",
                "verify": "semantic-equal",
                "hash_algorithm": "sha256",
                "on_divergence": "record-discrepancy",
            },
            "cache": B.cache_off(),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "Bash:python",
                    "Bash:pwsh",
                    "Write(command-center/preflight/**)",
                    "mcp__codex__codex",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(180, 900, 3600),
                tokens=(30000, 150000, 600000),
                tool_calls=(40, 300),
                cost=(0.2, 0.9, 3.5),
                risk="low",
                reversibility="reversible",
                blast_radius="read-only over the brief and the estate; writes only under command-center/preflight/bp-res-05/**",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-05.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "rules/common/fan-out-contract.md#A4",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "measured: 4 of 6 agents refuted, 2 CONFIRMED by re-running the orchestrator's broken probe",
                    },
                    {
                        "source": "rules/common/fan-out-contract.md#B4",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "the resolution rule: on a split verdict the specific probe wins over the agent count",
                    },
                    {
                        "source": "skills/fresh-context-verify",
                        "relation": "EXTEND",
                        "license": "owner-proprietary",
                        "credit": "owner",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-05",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ]
            ),
            "outputs": {
                "corrections": B.artifact(
                    f"{root}/brief-corrections.json",
                    S("divergence-ruling"),
                    min_bytes=256,
                    consumers=["the fan-out this gate precedes"],
                ),
                "facts": B.artifact(
                    f"{root}/briefed-facts.json",
                    S("stale-premise-reprobe"),
                    min_bytes=256,
                    consumers=["reconcile-by-probe"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-05", 378),
                "acquisition_route_from_card": "BUILD-NEW",
                "mechanism_signature": [
                    "briefed-fact-extraction-with-stated-probe",
                    "different-mechanism-assignment",
                    "original-probe-rerun-forbidden",
                    "probe-wins-over-vote-count-reconciliation",
                    "zero-result-is-suspicious-audit",
                    "hard-barrier-before-fanout-launch",
                ],
                "contraindications": [
                    "NOT for facts that are cheap to re-measure inline - just measure them",
                    "NOT when the brief asserts no facts",
                    "the serial barrier is the cost: it delays the fan-out by one short agent per fact",
                ],
                "measured_baseline": (
                    "One run: 4 agents correctly refuted a briefed fact while 2 'CONFIRMED' it by "
                    "re-running the orchestrator's own broken Git-Bash `which` - complete with "
                    "dutiful evidence tags. Four briefed 'VERIFIED GROUND TRUTH' facts were false in "
                    "that single run. That base rate is why zero corrections triggers an audit."
                ),
                "unverified": [
                    "UNVERIFIED on this estate post-build; settling experiment = a seeded-false-fact "
                    "run measuring the refutation rate against the 4-of-6 baseline the rule records.",
                ],
                "worked_example": {
                    "name": "gate a 40-agent program brief carrying five asserted ground truths",
                    "params": {
                        "brief": "command-center/PROGRAM-BRIEF.md",
                        "planned_fanout_size": 40,
                        "cross_vendor_on_blast_radius": True,
                        "max_facts": 20,
                    },
                    "facts": {"corrections_found": 2},
                    "expected_stage_order": [
                        "extract-facts",
                        "assign-different-instrument",
                        "independence-gate",
                        "reprobe-fanout",
                        "cross-vendor-reprobe",
                        "reconcile-by-probe",
                        "zero-correction-audit",
                        "corrections-gate",
                        "launch-barrier",
                        "owner-accept",
                    ],
                    "expected_skipped": ["zero-correction-audit"],
                    "expected_max_parallel": 6,
                    "expected_gate_ids": ["independence-gate", "corrections-gate"],
                    "fact_variants": [
                        {
                            "facts": {"corrections_found": 2},
                            "expected_skipped": ["zero-correction-audit"],
                        },
                        {
                            "facts": {"corrections_found": 0},
                            "expected_skipped": ["owner-accept"],
                        },
                    ],
                    "acceptance": [
                        "a seeded KNOWN-FALSE briefed fact is refuted",
                        "a true fact whose obvious probe is broken yields: PROBE refuted, FACT confirmed",
                        "the barrier blocks the fan-out until every fact carries a verdict",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "every-fact-has-a-verdict",
                            "why": "the floor prevents a brief that extracted zero facts from reading as a clean pass",
                            "fires_on": {
                                "facts_without_verdict": 0,
                                "facts_extracted": 5,
                                "facts_with_no_independent_instrument": 0,
                            },
                            "does_not_fire_on": {
                                "facts_without_verdict": 0,
                                "facts_extracted": 0,
                                "facts_with_no_independent_instrument": 0,
                            },
                        },
                        {
                            "rule": "no-instrument-diversity-left",
                            "why": "a fact with no independent instrument must escalate, never silently pass as ground truth",
                            "fires_on": {
                                "facts_without_verdict": 1,
                                "facts_extracted": 5,
                                "facts_with_no_independent_instrument": 2,
                            },
                            "does_not_fire_on": {
                                "facts_without_verdict": 1,
                                "facts_extracted": 5,
                                "facts_with_no_independent_instrument": 0,
                            },
                        },
                    ],
                },
            },
        }
    )


# --------------------------------------------------------------- 6. BP-RES-06

_R6_ALLOW = [
    "Read",
    "WebFetch",
    "Write(command-center/monitors/**)",
    "mcp__search-hub__firecrawl_monitor_create",
    "mcp__search-hub__firecrawl_monitor_check",
    "mcp__search-hub__firecrawl_monitor_list",
    "mcp__search-hub__firecrawl_monitor_get",
    "mcp__basic-memory__read_note",
    "mcp__basic-memory__write_note",
    "mcp__basic-memory__edit_note",
]


def _res06() -> dict[str, Any]:
    root = "command-center/monitors/bp-res-06"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-res-06-longitudinal-verdict-refresh",
            "name": "Longitudinal Verdict Refresh",
            "description": (
                "Treat a settled research verdict as PERISHABLE: watch its load-bearing sources on a "
                "cadence and re-open the verdict only when a source actually moves materially. The "
                "distinguishing machine is the pair (change-detection loop, temporal-validity memory "
                "write): a material change spawns a fresh research run as a SUBWORKFLOW and marks the "
                "old note superseded_by, while a non-change writes a dated no-op observation - "
                "because silence is not evidence a page is stable. A monitor that has never fired is "
                "validated against a known-changed control page before its silence is trusted, and if "
                "the monitor service is unreachable the verdict is marked STALE-UNWATCHED, not HOLDS."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": [
                "data-science-knowledge-and-creative",
                "research-and-evidence",
            ],
            "tags": ["temporal-validity", "change-monitor", "verdict-decay"],
            "flagship": False,
            "params": {
                "verdict_note_permalink": {
                    "type": "string",
                    "required": True,
                    "min_length": 3,
                    "description": "The memory note holding the verdict under watch",
                },
                "watched_urls": {
                    "type": "array",
                    "required": True,
                    "min_items": 1,
                    "max_items": 25,
                    "items": {"type": "string", "min_length": 8},
                    "description": "The verdict's load-bearing sources",
                },
                "control_url": {
                    "type": "string",
                    "required": True,
                    "min_length": 8,
                    "description": "A page the owner can edit at will - the detector control that proves the monitor can fire",
                },
                "materiality_rule": {
                    "type": "string",
                    "required": True,
                    "min_length": 10,
                    "description": "The stated rule that decides whether a diff is material; recorded with every decision because the judgement is not deterministic",
                },
                "cadence": {
                    "type": "enum",
                    "enum": ["daily", "weekly", "monthly"],
                    "default": "weekly",
                    "description": "Poll cadence",
                },
                "max_cycles": {
                    "type": "integer",
                    "default": 52,
                    "minimum": 1,
                    "maximum": 520,
                    "description": "Hard bound on the polling loop",
                },
                "etag_precheck": {
                    "type": "boolean",
                    "default": True,
                    "description": "Cheap HTTP ETag / Last-Modified check before spending a paid monitor call",
                },
            },
            "roles": {
                "monitor-registrar": {
                    "description": "Registers the monitors on a PAID external service; the owner must approve because it commits standing quota",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "low",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "mcp__search-hub__firecrawl_monitor_create",
                        "mcp__search-hub__firecrawl_monitor_list",
                        "Write(command-center/monitors/**)",
                    ],
                    "speaking_rights": "always",
                },
                "change-poller": {
                    "description": "Polls on cadence and does the cheap ETag pre-check first; reports a service outage as an outage, never as no-change",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "low",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": [
                        "WebFetch",
                        "mcp__search-hub__firecrawl_monitor_check",
                        "mcp__search-hub__firecrawl_monitor_get",
                        "Write(command-center/monitors/**)",
                    ],
                    "speaking_rights": "always",
                },
                "materiality-judge": {
                    "description": "Runs ONLY on a detected change and decides materiality against the stated rule, recording the rule text with the decision",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "voting",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "WebFetch",
                        "Write(command-center/monitors/**)",
                    ],
                    "speaking_rights": "on-request",
                },
                "memory-curator": {
                    "description": "Writes temporal validity: superseded_by on the old note, valid_as_of on the new one, so recall surfaces current truth",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "chair",
                    "independence": "informed",
                    "tool_permissions": [
                        "mcp__basic-memory__read_note",
                        "mcp__basic-memory__write_note",
                        "mcp__basic-memory__edit_note",
                        "Write(command-center/monitors/**)",
                    ],
                    "speaking_rights": "always",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_R6_ALLOW),
                "deny": ["Bash", "WebSearch", "mcp__basic-memory__delete_note"],
                "require_owner_approval": ["mcp__search-hub__firecrawl_monitor_create"],
                "network": "read-only",
                "write_paths": ["command-center/monitors/**"],
                "forbid_write_paths": ["command-center/WORK-UNIT-CATALOG.json"],
                "source_policy": {
                    "offline_only": False,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "skip",
                },
            },
            "model_routing": {
                "strategy": "cost-aware",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "medium"},
                "routes": [
                    {
                        "when": "stage_role == 'materiality-judge'",
                        "target": {
                            "model": "opus",
                            "vendor": "anthropic",
                            "effort": "high",
                        },
                        "reason": "materiality is the only judgement in the loop; the polling around it is mechanical",
                    }
                ],
                "forbid_downgrade_below": "opus",
            },
            "subworkflows": {
                "bp-res-01-grounded-evidence-cascade": {
                    "workflow_id": "bp-res-01-grounded-evidence-cascade",
                    "version_range": ">=1.0.0 <2.0.0",
                    "source": "platform/workflows/bp-res-01-grounded-evidence-cascade.json",
                }
            },
            "gates": {
                "monitor-can-fire": {
                    "predicate": "custom-expression",
                    "expression": "control_monitor_fired == true AND monitors_registered >= 1",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "service-reachable": {
                    "predicate": "custom-expression",
                    "expression": "monitor_service_reachable == true",
                    "blocking": False,
                    "evidence_required": True,
                    "on_fail": "record-and-continue",
                },
            },
            "stages": [
                {
                    "id": "register-monitors",
                    "title": "Register monitors on the verdict's load-bearing URLs (paid, owner-approved)",
                    "kind": "task",
                    "role": "monitor-registrar",
                    "checkpoint": True,
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0601",
                        title="Register one monitor per watched URL plus one on the owner-editable control page",
                        phase="2B",
                        target=(
                            "Register a change monitor for each load-bearing URL and one for the "
                            "control page. Record the monitor ids and the quota this commits, because "
                            "standing monitor quota is the real cost of this blueprint."
                        ),
                        inputs=[
                            "params.watched_urls",
                            "params.control_url",
                            "params.cadence",
                        ],
                        deps=[],
                        role="monitor-registrar",
                        tools=[
                            "mcp__search-hub__firecrawl_monitor_create",
                            "mcp__search-hub__firecrawl_monitor_list",
                            "Write(command-center/monitors/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/monitor-contract.json",
                        out_schema=S("telemetry-contract"),
                        evidence="each row carries the monitor id returned by the service, the URL, the cadence, and the quota committed",
                        tests=[
                            "registering with an unreachable service must FAIL loudly, never record a monitor id it did not receive",
                        ],
                        reviewer="the owner approves the standing quota commitment before this stage runs (tool_policy.require_owner_approval)",
                        postcondition="every watched URL plus the control page has a monitor id returned by the service",
                        retry="fixed backoff, at most 2 attempts; a second failure leaves the verdict UNWATCHED and says so",
                        failure_classes=["service-unreachable", "quota-exhausted"],
                        owner_approval=True,
                        mechanism="paid-monitor-registration",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/monitor-contract.json",
                            S("telemetry-contract"),
                            sentinel="SUCCESS:BPR-0601",
                            consumers=["control-probe", "poll-loop"],
                        )
                    ],
                },
                {
                    "id": "control-probe",
                    "title": "Detector control: edit the control page and require the monitor to fire",
                    "kind": "task",
                    "depends_on": ["register-monitors"],
                    "role": "change-poller",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPR-0602",
                        title="Prove the monitor can fire at all before trusting any silence from it",
                        phase="2B",
                        target=(
                            "Have the owner-editable control page changed, then check its monitor. It "
                            "MUST fire. A monitor that does not fire on a known change measures "
                            "nothing, and every silent monitor in this run is therefore untrustworthy."
                        ),
                        inputs=[f"{root}/monitor-contract.json", "params.control_url"],
                        deps=["BPR-0601"],
                        role="change-poller",
                        tools=[
                            "mcp__search-hub__firecrawl_monitor_check",
                            "WebFetch",
                            "Write(command-center/monitors/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/detector-control.json",
                        out_schema=S("detector-control"),
                        evidence="the control page's before/after hash, the monitor's fire event, and the elapsed time from edit to detection",
                        tests=[
                            "MANDATORY both-states: the control monitor must FIRE after the page is edited and must NOT fire on an unedited static page in the same cycle",
                        ],
                        reviewer="the control gate blocks the loop until this fires, so no silent monitor is ever read as stability",
                        postcondition="the control monitor fired and the fire event is recorded with its detection latency",
                        retry="fixed backoff, at most 3 attempts spread over the cadence; a third miss fails the control",
                        failure_classes=["detector-failure", "service-unreachable"],
                        mechanism="known-changed-control-page",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/detector-control.json",
                            S("detector-control"),
                            sentinel="SUCCESS:BPR-0602",
                            consumers=["control-gate", "poll-loop"],
                        )
                    ],
                },
                {
                    "id": "control-gate",
                    "title": "Silence is not evidence: the loop cannot start until the control fires",
                    "kind": "gate",
                    "depends_on": ["control-probe"],
                    "gate_ref": "monitor-can-fire",
                },
                {
                    "id": "poll-loop",
                    "title": "Poll on cadence; judge materiality only on a real change",
                    "kind": "loop",
                    "depends_on": ["control-gate"],
                    "loop_var": "cycle",
                    "body": [
                        {
                            "id": "etag-precheck",
                            "title": "Cheap ETag / Last-Modified check before spending a paid call",
                            "kind": "task",
                            "when": "etag_precheck == true",
                            "role": "change-poller",
                            "timeout_seconds": 300,
                            "work_unit": B.wu(
                                uid="BPR-0603",
                                title="Compare ETag and Last-Modified before invoking the paid monitor",
                                phase="2B",
                                target=(
                                    "For each watched URL compare the stored ETag / Last-Modified with "
                                    "the live headers. Only URLs whose headers moved, or that expose no "
                                    "validators at all, are escalated to the paid monitor call."
                                ),
                                inputs=[f"{root}/monitor-contract.json"],
                                deps=["BPR-0601"],
                                role="change-poller",
                                tools=["WebFetch", "Write(command-center/monitors/**)"],
                                substrate="local-single",
                                timeout=300,
                                out_path=f"{root}/cycles/etag-precheck.json",
                                out_schema=S("measurement-run"),
                                evidence="per URL: the stored and live validator values, and the escalate / skip decision",
                                tests=[
                                    "a URL exposing NO ETag and NO Last-Modified must be escalated, never treated as unchanged",
                                ],
                                reviewer="the poll stage re-reads this decision and records any URL it skipped so a missed change is attributable",
                                postcondition="every watched URL has an escalate / skip decision carrying both validator values",
                                retry="fixed backoff, at most 2 attempts per URL",
                                failure_classes=[
                                    "service-unreachable",
                                    "detector-failure",
                                ],
                                mechanism="validator-precheck-before-paid-call",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/cycles/etag-precheck.json",
                                    S("measurement-run"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPR-0603",
                                    consumers=["poll-cycle"],
                                )
                            ],
                        },
                        {
                            "id": "poll-cycle",
                            "title": "Check the monitors and record a dated observation either way",
                            "kind": "task",
                            "depends_on": ["etag-precheck"],
                            "role": "change-poller",
                            "timeout_seconds": 900,
                            "work_unit": B.wu(
                                uid="BPR-0604",
                                title="Check each escalated monitor and write a dated observation, change or no-change",
                                phase="2B",
                                target=(
                                    "Check the monitors for the escalated URLs. Write a dated "
                                    "observation for EVERY watched URL - including an explicit no-op "
                                    "record - so an absence of fires is attributable rather than silent. "
                                    "A service outage is recorded as STALE-UNWATCHED, never as no-change."
                                ),
                                inputs=[
                                    f"{root}/cycles/etag-precheck.json",
                                    f"{root}/monitor-contract.json",
                                ],
                                deps=["BPR-0603"],
                                role="change-poller",
                                tools=[
                                    "mcp__search-hub__firecrawl_monitor_check",
                                    "mcp__search-hub__firecrawl_monitor_get",
                                    "Write(command-center/monitors/**)",
                                ],
                                substrate="local-single",
                                timeout=900,
                                out_path=f"{root}/cycles/observation.json",
                                out_schema=S("evidence-decay-report"),
                                evidence="one dated row per watched URL per cycle: changed / unchanged / STALE-UNWATCHED, with the diff summary when changed",
                                tests=[
                                    "with the service unreachable, every row must read STALE-UNWATCHED - a run that reports 'unchanged' during an outage is the failure this test exists for",
                                ],
                                reviewer="the memory curator refuses to write HOLDS for any cycle containing a STALE-UNWATCHED row",
                                postcondition="every watched URL has a dated observation for this cycle",
                                retry="fixed backoff, at most 2 attempts; a second failure records STALE-UNWATCHED",
                                failure_classes=[
                                    "service-unreachable",
                                    "quota-exhausted",
                                ],
                                mechanism="dated-no-op-observation",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/cycles/observation.json",
                                    S("evidence-decay-report"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPR-0604",
                                    consumers=["judge-materiality", "curate-memory"],
                                )
                            ],
                        },
                        {
                            "id": "judge-materiality",
                            "title": "Judge materiality against the stated rule, on change only",
                            "kind": "task",
                            "depends_on": ["poll-cycle"],
                            "when": "changes_detected > 0",
                            "role": "materiality-judge",
                            "timeout_seconds": 1200,
                            "work_unit": B.wu(
                                uid="BPR-0605",
                                title="Decide whether a detected diff is material to THIS verdict",
                                phase="2B",
                                target=(
                                    "For each detected change decide material / immaterial strictly "
                                    "against the stated materiality_rule, and record the rule text "
                                    "verbatim beside the decision, because the judgement is not "
                                    "deterministic and must be auditable later."
                                ),
                                inputs=[
                                    f"{root}/cycles/observation.json",
                                    "params.materiality_rule",
                                ],
                                deps=["BPR-0604"],
                                role="materiality-judge",
                                tools=[
                                    "Read",
                                    "WebFetch",
                                    "Write(command-center/monitors/**)",
                                ],
                                substrate="local-single",
                                timeout=1200,
                                out_path=f"{root}/cycles/materiality.json",
                                out_schema=S("evidence-integrity-report"),
                                evidence="each decision quotes the diff span it turned on and the materiality_rule text as applied",
                                tests=[
                                    "a cosmetic diff (whitespace, a nav link) must be immaterial",
                                    "both-states: a diff that changes the number the verdict rests on must be material",
                                ],
                                reviewer="the owner can re-read the rule text and the diff span together, so a drifting interpretation is visible",
                                postcondition="every detected change has a material / immaterial decision carrying the diff span and the rule text",
                                retry="fixed backoff, at most 2 attempts",
                                failure_classes=["materiality-ambiguous", "overclaim"],
                                mechanism="rule-quoted-materiality-judgement",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/cycles/materiality.json",
                                    S("evidence-integrity-report"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPR-0605",
                                    consumers=["reopen-research", "curate-memory"],
                                )
                            ],
                        },
                    ],
                    "convergence": {
                        "max_iterations": 520,
                        "min_iterations": 1,
                        "converged_when": "verdict_retired == true OR cycle >= max_cycles",
                        "no_progress_rounds": 12,
                        "metrics": [
                            {"name": "verdict_retired", "direction": "stabilize"},
                            {
                                "name": "material_changes",
                                "direction": "decrease",
                                "target": 0,
                            },
                        ],
                        "on_no_convergence": "emit-partial",
                    },
                },
                {
                    "id": "reopen-research",
                    "title": "On a material change, re-open the verdict by spawning a fresh research run",
                    "kind": "subworkflow",
                    "depends_on": ["poll-loop"],
                    "when": "material_change_confirmed == true",
                    "workflow": {
                        "workflow_id": "bp-res-01-grounded-evidence-cascade",
                        "version_range": ">=1.0.0 <2.0.0",
                    },
                    "params": {
                        "reopened_from": "bp-res-06-longitudinal-verdict-refresh"
                    },
                    "isolation": "none",
                    "propagate_failure": False,
                    "timeout_seconds": 10800,
                },
                {
                    "id": "service-gate",
                    "title": "An unreachable monitor service means STALE-UNWATCHED, not HOLDS",
                    "kind": "gate",
                    "depends_on": ["poll-loop"],
                    "gate_ref": "service-reachable",
                },
                {
                    "id": "curate-memory",
                    "title": "Write temporal validity: superseded_by on the old note, valid_as_of on the new",
                    "kind": "task",
                    "depends_on": ["reopen-research", "service-gate"],
                    "role": "memory-curator",
                    "timeout_seconds": 900,
                    "work_unit": B.wu(
                        uid="BPR-0606",
                        title="Update the memory graph so recall surfaces current truth and dead ends are retired",
                        phase="2B",
                        target=(
                            "Write the verdict status. On a material change: add superseded_by to the "
                            "old note and valid_as_of to the new one. On no change: append a dated "
                            "no-op observation. On an outage: mark the verdict STALE-UNWATCHED."
                        ),
                        inputs=[
                            f"{root}/cycles/materiality.json",
                            f"{root}/cycles/observation.json",
                            "params.verdict_note_permalink",
                        ],
                        deps=["BPR-0604", "BPR-0605"],
                        role="memory-curator",
                        tools=[
                            "mcp__basic-memory__read_note",
                            "mcp__basic-memory__write_note",
                            "mcp__basic-memory__edit_note",
                            "Write(command-center/monitors/**)",
                        ],
                        substrate="local-single",
                        timeout=900,
                        out_path=f"{root}/supersession.json",
                        out_schema=S("supersession-graph"),
                        evidence="the supersession graph records both edges (old superseded_by new, new valid_as_of date) and the note revision ids returned by the memory store",
                        tests=[
                            "exactly one superseded_by edge per material change - a second write for the same change is a duplicate defect",
                            "an outage cycle must produce a STALE-UNWATCHED status and NO supersession edge",
                        ],
                        reviewer="one independent reviewer re-reads the old note and confirms it now points forward, so recall cannot surface the retired verdict as current",
                        postcondition="the verdict status is written, and every material change has exactly one supersession edge carrying store revision ids",
                        retry="two strikes then pivot: after two failed writes, leave the old note untouched and escalate - a half-written supersession is worse than none",
                        failure_classes=["memory-write-failed", "service-unreachable"],
                        mechanism="temporal-validity-supersession-write",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/supersession.json",
                            S("supersession-graph"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPR-0606",
                            consumers=["command-center/CLAIM-REGISTRY.json"],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "verdict-retired",
                    "expression": "verdict_retired == true OR owner_unsubscribed == true",
                    "applies_to": "workflow",
                    "on_stop": "complete",
                },
                {
                    "id": "monitor-noise-dominates",
                    "expression": "immaterial_fires_per_material_fire >= 10",
                    "applies_to": "workflow",
                    "minimum_conditions": "cycles_completed >= 4",
                    "on_stop": "escalate",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                3,
                escalate_to="curate-memory",
                retry_on=["service-unreachable", "quota-exhausted"],
            ),
            "failure_policy": B.failure(
                "degrade-loudly",
                [
                    "service-unreachable",
                    "quota-exhausted",
                    "materiality-ambiguous",
                    "memory-write-failed",
                ],
                escalate_to="curate-memory",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="stage",
                keys=["workflow_id", "workflow_version", "stage_id", "params_hash"],
            ),
            "replay": B.replay_not_deterministic(),
            "cache": B.cache_off(),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "mcp__search-hub__firecrawl_monitor_create",
                    "mcp__search-hub__firecrawl_monitor_check",
                    "mcp__basic-memory__write_note",
                    "mcp__basic-memory__edit_note",
                    "Write(command-center/monitors/**)",
                ],
            ),
            "estimate": B.estimate_block(
                wallclock=(60, 300, 1800),
                tokens=(5000, 30000, 150000),
                tool_calls=(10, 80),
                cost=(0.05, 0.4, 2.0),
                risk="medium",
                reversibility="reversible-with-effort",
                blast_radius="registers PAID standing monitors and mutates the memory graph; deleting the monitors is an owner action",
                confidence="roughly-even",
                owner_approval=True,
            ),
            "portability": B.portability_block(
                "command-center/export/bp-res-06.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "skills/firecrawl",
                        "relation": "COMPOSE",
                        "license": "third-party service, owner account",
                        "credit": "Firecrawl",
                    },
                    {
                        "source": "basic-memory temporal validity (superseded_by / valid_as_of)",
                        "relation": "COMPOSE",
                        "license": "owner-proprietary",
                        "credit": "owner",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-RES-06",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ]
            ),
            "outputs": {
                "supersession": B.artifact(
                    f"{root}/supersession.json",
                    S("supersession-graph"),
                    min_bytes=128,
                    consumers=["command-center/CLAIM-REGISTRY.json"],
                ),
                "monitor-contract": B.artifact(
                    f"{root}/monitor-contract.json",
                    S("telemetry-contract"),
                    min_bytes=128,
                    consumers=["poll-loop"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-RES-06", 422),
                "acquisition_route_from_card": "COMPOSE",
                "mechanism_signature": [
                    "paid-monitor-registration-with-owner-approval",
                    "known-changed-control-page-before-trusting-silence",
                    "validator-precheck-before-paid-call",
                    "dated-no-op-observation",
                    "rule-quoted-materiality-judgement",
                    "temporal-validity-supersession-write",
                    "stale-unwatched-instead-of-holds-on-outage",
                ],
                "contraindications": [
                    "NOT for high-churn pages - monitor noise swamps signal, and the stopping rule exists to say so",
                    "NOT for anything behind auth",
                    "NOT a substitute for re-running the research when the domain shifts structurally: a structural shift can invalidate a verdict with ZERO URL changes, which this blueprint cannot see",
                ],
                "unverified": [
                    "UNVERIFIED end-to-end; settling experiment = register 3 monitors, edit exactly one "
                    "control page, and confirm exactly one fire and exactly one superseded_by write.",
                    "UNVERIFIED that <=5 watched verdicts is the sustainable ceiling before monitor "
                    "noise dominates; the monitor-noise-dominates stopping rule is the instrument that "
                    "would measure it.",
                ],
                "owner_decision": "Which verdicts (if any) are worth a standing PAID monitor, and at what cadence?",
                "worked_example": {
                    "name": "watch a model-pricing verdict weekly",
                    "params": {
                        "verdict_note_permalink": "main/reference/model-pricing-verdict-2026-08",
                        "watched_urls": [
                            "https://docs.anthropic.com/en/docs/about-claude/pricing",
                            "https://platform.openai.com/docs/pricing",
                        ],
                        "control_url": "https://example.invalid/owner-editable-control-page",
                        "materiality_rule": "a change is material only if a price-per-million-tokens figure or a model id in the verdict's table changes",
                        "cadence": "weekly",
                        "max_cycles": 52,
                        "etag_precheck": True,
                    },
                    "facts": {"material_change_confirmed": True, "changes_detected": 1},
                    "expected_stage_order": [
                        "register-monitors",
                        "control-probe",
                        "control-gate",
                        "poll-loop",
                        "reopen-research",
                        "service-gate",
                        "curate-memory",
                    ],
                    "expected_skipped": [],
                    "expected_max_parallel": 1,
                    "expected_gate_ids": ["control-gate", "service-gate"],
                    "expected_loop_bound": 520,
                    "acceptance": [
                        "the control page edit produces exactly one monitor fire",
                        "a cosmetic diff on a watched page is judged immaterial and writes a dated no-op",
                        "a price change is material, spawns the research subworkflow, and writes exactly one superseded_by edge",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "monitor-noise-dominates",
                            "why": "the floor stops a single noisy first cycle from retiring the monitor",
                            "fires_on": {
                                "immaterial_fires_per_material_fire": 14,
                                "cycles_completed": 9,
                                "verdict_retired": False,
                                "owner_unsubscribed": False,
                            },
                            "does_not_fire_on": {
                                "immaterial_fires_per_material_fire": 14,
                                "cycles_completed": 2,
                                "verdict_retired": False,
                                "owner_unsubscribed": False,
                            },
                        },
                        {
                            "rule": "verdict-retired",
                            "why": "the loop must end when the owner retires or unsubscribes the verdict",
                            "fires_on": {
                                "immaterial_fires_per_material_fire": 1,
                                "cycles_completed": 9,
                                "verdict_retired": True,
                                "owner_unsubscribed": False,
                            },
                            "does_not_fire_on": {
                                "immaterial_fires_per_material_fire": 1,
                                "cycles_completed": 9,
                                "verdict_retired": False,
                                "owner_unsubscribed": False,
                            },
                        },
                    ],
                },
            },
        }
    )


def blueprints() -> list[dict[str, Any]]:
    return [_res05(), _res06()]
