"""bp-3 blueprints 1-4: BP-REQ-03, BP-REQ-04, BP-REQ-05, BP-ARC-01.

Design source: 09-WORKFLOW-BLUEPRINT-LIBRARY.md lines 1268-1445 (doc-order 25-28 of 96).
Each ``stages`` list reproduces that card's declared S0..Sn - the stage graph is consumed
from the design, not reinvented.
"""

from __future__ import annotations

from typing import Any

from _bp3_common import (
    artifact,
    cache,
    deny_policy,
    dry_run,
    estimate_static,
    expr_gate,
    failure_policy,
    lineage,
    opus_routing,
    portability,
    replay,
    resume,
    schema,
    two_strikes,
    unit_gate,
    wu,
)

# --------------------------------------------------------------------------------- REQ-03


def bp_req_03() -> dict[str, Any]:
    """EVPI-gated clarification: <=3 questions, pre-execution only, `*` bypass honoured.

    Distinguishing mechanism: a question is DROPPED when every one of its options leads to
    the same plan (zero expected value of information). The actuator is a human checkpoint -
    contrast BP-REQ-04, whose actuator is a verification probe against the world.
    """
    return {
        "dsl_version": "1.0.0",
        "id": "bp-req-03.evpi-gated-clarification",
        "name": "EVPI-Gated Clarification",
        "description": (
            "Ask the owner 1-3 questions ONLY when the answer would change the approach, and "
            "never after the first two actions. The mid-task prohibition is a security "
            "property, not etiquette: a 'clarification' raised mid-task is the surface through "
            "which fetched content steers the plan. A prompt prefixed '*' is already scoped and "
            "must produce ZERO questions."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["product-design-and-strategy"],
        "tags": ["clarification", "evpi", "pre-execution", "injection-surface"],
        "flagship": True,
        "params": {
            "prompt": {"type": "string", "required": True, "min_length": 1, "description": "The raw owner prompt"},
            "repo_context_root": {"type": "path", "default": ".", "description": "Root the scan grounds options in"},
            "star_prefixed": {
                "type": "boolean",
                "default": False,
                "description": "True when the prompt begins with '*' - the scoped bypass; forces zero questions",
            },
            "actions_elapsed": {
                "type": "integer",
                "default": 0,
                "minimum": 0,
                "description": "Tool actions already taken this turn; >2 closes the clarification window for good",
            },
            "max_questions": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 3,
                "description": "Hard cap. 4 questions is a violation, not a thorough gate.",
            },
        },
        "roles": {
            "scanner": {
                "description": "Grounds every candidate option in a real repo fact before it is offered",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "owner": {
                "description": "The human being asked; the only role that can answer",
                "vendor": "human",
                "authority": "owner",
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "AskUserQuestion", "Write(command-center/clarify/**)"],
            network="none",
            write_paths=["command-center/clarify/**"],
            forbid_write_paths=["command-center/WORK-UNIT-CATALOG.json"],
        ),
        "model_routing": opus_routing(),
        "gates": {
            "window-open": expr_gate(
                "bypass_star == false AND actions_elapsed <= 2",
                "fail",
            ),
            "evpi-positive": expr_gate(
                "questions_with_single_plan == 0 AND questions_asked <= 3", "fail"
            ),
        },
        "stages": [
            {
                "id": "s0-scan",
                "title": "S0 SCAN repo context",
                "kind": "task",
                "role": "scanner",
                "timeout_seconds": 600,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-REQ03-S0",
                    title="Scan repo context so every option offered is grounded in a real fact",
                    phase="2B",
                    target="Collect the repo facts that could disambiguate the prompt, so no offered option is invented.",
                    inputs=["params.prompt", "params.repo_context_root"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="scanner",
                    basis="substantive subagents default to Opus",
                    tools=["Read", "Grep", "Glob"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/clarify/req03-scan.json",
                    output_schema=schema("capability-index"),
                    evidence="every candidate option cites a file:line or an exact command output that grounds it",
                    tests=["a scan that grounds zero options must FAIL, not emit an ungrounded option list"],
                    reviewer="none - gated mechanically by the grounding assertion, not by opinion",
                    retry="none; a failed scan escalates to an open question rather than inventing options",
                    failure_classes=["ungroundable-option", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every option in the artifact carries a repo anchor",
                ),
                "produces": [
                    artifact(
                        "command-center/clarify/req03-scan.json",
                        schema("capability-index"),
                        min_bytes=128,
                        sentinel="SUCCESS:BP3-REQ03-S0",
                        consumers=["s1-identify"],
                    )
                ],
            },
            {
                "id": "s1-identify",
                "title": "S1 IDENTIFY material ambiguity",
                "kind": "task",
                "role": "scanner",
                "depends_on": ["s0-scan"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-REQ03-S1",
                    title="Separate material ambiguity from cosmetic under-specification",
                    phase="2B",
                    target="Name each ambiguity and the two or more materially different plans it would produce.",
                    inputs=["command-center/clarify/req03-scan.json"],
                    dependencies=["BP3-REQ03-S0"],
                    model="opus",
                    vendor="anthropic",
                    role="scanner",
                    basis="judgement over grounded facts",
                    tools=["Read", "Grep"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/clarify/req03-ambiguities.json",
                    output_schema=schema("unknowns-closure"),
                    evidence="each ambiguity names the >=2 distinct plans it produces; a single-plan ambiguity is not material",
                    tests=["an ambiguity listing one plan must be classified immaterial"],
                    reviewer="none - the >=2-distinct-plans test is mechanical",
                    retry="none; an unresolvable ambiguity is recorded, not guessed",
                    failure_classes=["spec-underspecified"],
                    owner_approval=False,
                    sentinel_extra="every recorded ambiguity lists at least two distinct plans",
                ),
            },
            {
                "id": "s2-evpi",
                "title": "S2 COMPUTE EVPI and drop zero-value questions",
                "kind": "gate",
                "depends_on": ["s1-identify"],
                "gate_ref": "evpi-positive",
            },
            {
                "id": "s2b-window",
                "title": "S2b ENFORCE the pre-execution window and the * bypass",
                "kind": "gate",
                "depends_on": ["s2-evpi"],
                "gate_ref": "window-open",
            },
            {
                "id": "s3-ask",
                "title": "S3 ASK at most three grounded questions",
                "kind": "human_checkpoint",
                "depends_on": ["s2b-window"],
                "prompt": "Answer the surviving clarification questions, or reply 'proceed' to accept the stated default for each.",
                "approvers": ["owner"],
                "approval_mode": "owner-only",
                "timeout_seconds": 3600,
                "on_timeout": "proceed",
                "owner_approval_required": False,
                "options": ["answer", "proceed-with-defaults", "cancel"],
                "decision_artifact": artifact(
                    "command-center/clarify/req03-questions.json",
                    schema("owner-decision-packet"),
                    min_bytes=192,
                    consumers=["command-center/clarify/req03-closure.json"],
                ),
            },
        ],
        "stopping_rules": [
            {
                "id": "no-material-ambiguity-or-cap-reached",
                "expression": "material_ambiguity == false OR questions_asked >= 3",
                "applies_to": "workflow",
                "minimum_conditions": "repo_context_scanned == true",
                "on_stop": "complete",
            },
            {
                "id": "scoped-bypass",
                "expression": "bypass_star == true",
                "applies_to": "workflow",
                "on_stop": "complete",
            },
        ],
        "retry_policy": {"strategy": "none", "max_attempts": 1},
        "failure_policy": failure_policy(
            "degrade-loudly",
            ["ungroundable-option", "spec-underspecified"],
            "s3-ask",
            "command-center/quarantine/req03",
        ),
        # A <=3-question pre-execution gate is NOT resumable: a half-asked question set must be
        # re-derived against the CURRENT prompt, never replayed from a stale checkpoint.
        "resume": {"enabled": False},
        "replay": {"deterministic": False},
        # Never serve a clarification from cache - the prompt is the cache key that matters and
        # it changes every turn.
        "cache": {"enabled": False},
        "dry_run": dry_run(
            "command-center/dry-run/req03-plan.json",
            ["AskUserQuestion", "Write(command-center/clarify/**)"],
            ["plan", "permission-report"],
        ),
        "estimate": estimate_static(
            wallclock=(20, 120, 600),
            tokens=(4000, 20000, 80000),
            tool_calls=(8, 40),
            risk="low",
            reversibility="reversible",
            blast_radius="writes only under command-center/clarify/**; asks the owner at most three questions",
        ),
        "portability": portability("command-center/export/bp-req-03.bundle.json"),
        "lineage": lineage(
            [
                ("skills/clarify-requirements", "ADOPT-AS-IS"),
                ("AGENTS.md#1-front-load-clarification", "REBUILD-FROM-SPEC"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-03", "REBUILD-FROM-SPEC"),
            ],
            rollback=["skills/clarify-requirements@current"],
        ),
        "outputs": {
            "questions": artifact(
                "command-center/clarify/req03-questions.json",
                schema("owner-decision-packet"),
                min_bytes=192,
                consumers=["the calling workflow", "command-center/clarify/req03-closure.json"],
            ),
            "closure": artifact(
                "command-center/clarify/req03-closure.json",
                schema("owner-question-closure"),
                min_bytes=128,
                consumers=["the calling workflow"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-03 (doc-order 25 of 96)",
            "distinguishing_mechanism": (
                "drop a question whose options all produce the SAME plan; actuator is a human "
                "checkpoint. BP-REQ-04 shares the pre-execution slot but actuates a probe."
            ),
            "contraindications": [
                "never mid-task (actions_elapsed > 2)",
                "never when the prompt is '*'-prefixed",
                "never to rubber-stamp an obvious task - that is permission theatre",
            ],
            "worked_example": {
                "name": "star-bypass and single-plan drop",
                "narrative": (
                    "Two candidate questions are raised. The first offers two options that "
                    "produce genuinely different plans and survives. The second offers three "
                    "options that all produce 'rebuild-from-scratch', so its EVPI is zero and it "
                    "is dropped. A second run with star_prefixed=true must ask nothing at all."
                ),
                "mechanism": "mechanisms.evpi_questions",
                "input": {
                    "candidates": [
                        {
                            "text": "Should the migration be in-place or via a shadow table?",
                            "options": {"in-place": "plan-A", "shadow-table": "plan-B"},
                        },
                        {
                            "text": "Which font should the report use?",
                            "options": {
                                "inter": "rebuild-from-scratch",
                                "roboto": "rebuild-from-scratch",
                                "system": "rebuild-from-scratch",
                            },
                        },
                    ],
                    "star_prefixed": False,
                    "actions_elapsed": 0,
                },
                "expected": {
                    "kept_texts": ["Should the migration be in-place or via a shadow table?"],
                    "dropped_count": 1,
                },
                "controls": [
                    {"star_prefixed": True, "expected_kept": 0, "why": "the '*' bypass must be absolute"},
                    {"actions_elapsed": 3, "expected_kept": 0, "why": "the window closes after two actions"},
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- REQ-04


def bp_req_04() -> dict[str, Any]:
    """Assumption-ledger elicitation: rate, adverse-infer blanks, route LOW rows to a PROBE."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-req-04.assumption-ledger-elicitation",
        "name": "Assumption-Ledger Elicitation",
        "description": (
            "Before a long-horizon plan runs, enumerate what it silently assumes, rate each row "
            "high/medium/low, and treat a LOW-confidence LOAD-BEARING row as a verify-or-clarify "
            "trigger rather than a silent bet. A required-but-blank field defaults to the WORST "
            "case and that default is written down. On any step failure the ledger is re-read "
            "first, because a wrong assumption is the usual root cause."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["product-design-and-strategy", "security-governance-and-risk"],
        "tags": ["assumptions", "adverse-inference", "verify-not-ask", "pre-execution"],
        "flagship": True,
        "params": {
            "plan_path": {"type": "path", "required": True, "description": "The plan whose assumptions are extracted"},
            "required_fields": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Fields the plan MUST fill; a blank one is adverse-inferred to worst case",
            },
            "worst_case_defaults": {
                "type": "object",
                "default": {},
                "description": "field -> the worst-case value a blank must resolve to",
            },
            "probe_budget": {
                "type": "integer",
                "default": 4,
                "minimum": 1,
                "maximum": 32,
                "description": "Max verification probes fanned out for LOW+load-bearing rows",
            },
        },
        "roles": {
            "extractor": {
                "description": "Reads the plan and lists what it takes for granted, including omissions",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep"],
            },
            "rater": {
                "description": "Assigns load_bearing and a high/medium/low band, and must justify a high band",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "voting",
                "independence": "independent",
                "tool_permissions": ["Read"],
            },
            "prober": {
                "description": "Re-derives a low-confidence assumption in a fresh context that cannot inherit the plan's reasoning",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "judge",
                "independence": "independent",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep", "Bash:git", "Bash:python"],
            },
        },
        "tool_policy": deny_policy(
            [
                "Read",
                "Grep",
                "Bash:git",
                "Bash:python",
                "Write(command-center/assumptions/**)",
            ],
            network="none",
            write_paths=["command-center/assumptions/**"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == prober",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "a same-vendor prober inherits the same blind spot that produced the assumption",
                }
            ],
        ),
        "gates": {
            "no-silent-bet": expr_gate(
                "low_confidence_load_bearing_unhandled == 0", "escalate-to-human"
            ),
            "blanks-adverse-inferred": expr_gate(
                "blank_required_fields == 0 OR worst_case_defaults_written == true", "fail"
            ),
        },
        "stages": [
            {
                "id": "s0-extract",
                "title": "S0 EXTRACT the assumptions the plan rests on",
                "kind": "task",
                "role": "extractor",
                "timeout_seconds": 900,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-REQ04-S0",
                    title="Extract the load-bearing premises a plan never states",
                    phase="2B",
                    target="List every premise the plan would break without, including premises implied by an omission.",
                    inputs=["params.plan_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="extractor",
                    basis="substantive subagents default to Opus",
                    tools=["Read", "Grep"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/assumptions/req04-ledger.json",
                    output_schema=schema("residual-risk-ledger"),
                    evidence="each row quotes the plan line that implies it, or names the omission that implies it",
                    tests=["a plan with a blank required field must yield a row carrying the worst-case default"],
                    reviewer="the rater, who may not also author rows",
                    retry="two strikes then pivot to a differently-seeded extraction",
                    failure_classes=["spec-underspecified", "overclaim"],
                    owner_approval=False,
                    sentinel_extra="every row quotes a plan line or names the omission it comes from",
                ),
                "produces": [
                    artifact(
                        "command-center/assumptions/req04-ledger.json",
                        schema("residual-risk-ledger"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-REQ04-S0",
                        consumers=["s1-mark", "s2-rate"],
                    )
                ],
            },
            {
                "id": "s0b-blanks",
                "title": "S0b APPLY the adverse-inference default to every blank required field",
                "kind": "gate",
                "depends_on": ["s0-extract"],
                "gate_ref": "blanks-adverse-inferred",
            },
            {
                "id": "s1-mark",
                "title": "S1 MARK which rows are load-bearing",
                "kind": "task",
                "role": "rater",
                "depends_on": ["s0b-blanks"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-REQ04-S1",
                    title="Mark load_bearing, and drop rows that are not",
                    phase="2B",
                    target="Decide, per row, whether the plan fails if the row is false. A non-load-bearing row is deleted, not carried.",
                    inputs=["command-center/assumptions/req04-ledger.json"],
                    dependencies=["BP3-REQ04-S0"],
                    model="opus",
                    vendor="anthropic",
                    role="rater",
                    basis="judgement, reviewed by the prober downstream",
                    tools=["Read"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/assumptions/req04-marked.json",
                    output_schema=schema("residual-risk-ledger"),
                    evidence="each load_bearing=true row names the plan step that fails if the row is false",
                    tests=["a ritual row with no failing step must be dropped, keeping the ledger from becoming a checklist"],
                    reviewer="the prober re-reads the marks before probing",
                    retry="two strikes then pivot; a third identical marking pass is banned",
                    failure_classes=["overclaim", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="no row is load_bearing without a named failing step",
                ),
            },
            {
                "id": "s2-rate",
                "title": "S2 RATE confidence high/medium/low",
                "kind": "task",
                "role": "rater",
                "depends_on": ["s1-mark"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-REQ04-S2",
                    title="Attach a calibrated band to every load-bearing row",
                    phase="2B",
                    target="Assign high, medium or low to each load-bearing row and pair the band with its evidence tag.",
                    inputs=["command-center/assumptions/req04-marked.json"],
                    dependencies=["BP3-REQ04-S1"],
                    model="opus",
                    vendor="anthropic",
                    role="rater",
                    basis="calibrated banding, not a bare hedge",
                    tools=["Read"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/assumptions/req04-rated.json",
                    output_schema=schema("residual-risk-ledger"),
                    evidence="a high band cites the measurement that justifies it; a bare 'should be fine' is rejected as a hedge",
                    tests=["a high band with no cited measurement must be demoted to low"],
                    reviewer="the prober, cross-vendor",
                    retry="two strikes then pivot",
                    failure_classes=["overclaim"],
                    owner_approval=False,
                    sentinel_extra="every band is paired with an evidence tag",
                ),
            },
            {
                "id": "s3-probe",
                "title": "S3 VERIFY every LOW-confidence load-bearing row (never silently bet)",
                "kind": "fanout",
                "depends_on": ["s2-rate"],
                "over": {
                    "source": "artifact",
                    "ref": "command-center/assumptions/req04-rated.json",
                    "item_var": "assumption",
                    "key_field": "row_id",
                },
                "max_concurrency": 4,
                "arrival_stagger_ms": 500,
                "max_items": 32,
                "on_item_failure": "quarantine",
                "body": [
                    {
                        "id": "probe-one",
                        "kind": "task",
                        "role": "prober",
                        "timeout_seconds": 1200,
                        "work_unit": wu(
                            uid="BP3-REQ04-S3",
                            title="Re-derive one low-confidence assumption in a fresh context",
                            phase="2B",
                            target="Independently establish or refute one assumption using a mechanically different measurement from the one that produced it.",
                            inputs=["command-center/assumptions/req04-rated.json"],
                            dependencies=["BP3-REQ04-S2"],
                            model="gpt-5-codex",
                            vendor="openai",
                            role="prober",
                            basis="cross-vendor so the probe cannot inherit the author's reasoning",
                            tools=["Read", "Grep", "Bash:git", "Bash:python"],
                            substrate="codex-mcp",
                            timeout=1200,
                            output_path="command-center/assumptions/req04-probe.json",
                            output_schema=schema("stale-premise-reprobe"),
                            evidence="names BOTH the source measurement that produced the assumption and the mechanically different one that checked it",
                            tests=[
                                "re-running the ORIGINAL probe must be rejected as a non-independent signal",
                                "a probe with no declared source measurement is a violation, not an independent confirmation",
                            ],
                            reviewer="the rater reads the probe before the band is revised",
                            retry="two strikes then pivot to a third measurement class",
                            failure_classes=["detector-failure", "same-probe-rerun"],
                            owner_approval=False,
                            sentinel_extra="the artifact names a source probe AND a mechanically different verifier",
                        ),
                    }
                ],
                "barrier": {
                    "mode": "all",
                    "on_partial": "fail",
                    "reject_result_matching": [
                        "started in the background",
                        "Check /codex:status",
                    ],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s3-gate",
                "title": "S3 gate: no LOW+load-bearing row may be carried silently",
                "kind": "gate",
                "depends_on": ["s3-probe"],
                "gate_ref": "no-silent-bet",
            },
            {
                "id": "s4-recheck",
                "title": "S4 RE-CHECK the ledger on any step failure (failure-triggered, not scheduled)",
                "kind": "repair_loop",
                "depends_on": ["s3-gate"],
                "target": ["s2-rate", "s3-probe"],
                "max_attempts": 2,
                "classification_filter": ["detector-failure", "overclaim", "stale-premise"],
                "escalate_to": "owner",
                "require_root_cause": True,
                "when": "step_failed == true",
                "diagnose": {
                    "id": "recheck-diagnose",
                    "kind": "task",
                    "role": "prober",
                    "work_unit": wu(
                        uid="BP3-REQ04-S4D",
                        title="Find which ledger row the failure falsifies",
                        phase="2B",
                        target="Map the observed failure back to the assumption it falsifies, or state that no ledger row explains it.",
                        inputs=["command-center/assumptions/req04-rated.json"],
                        dependencies=["BP3-REQ04-S3"],
                        model="gpt-5-codex",
                        vendor="openai",
                        role="prober",
                        basis="cross-vendor diagnosis",
                        tools=["Read", "Grep", "Bash:python"],
                        substrate="codex-mcp",
                        timeout=900,
                        output_path="command-center/assumptions/req04-recheck.json",
                        output_schema=schema("root-cause-graph"),
                        evidence="links the failure signal to the row it falsifies, or records NO-LEDGER-ROW-EXPLAINS-THIS",
                        tests=["a failure explained by no row must widen the ledger, not be forced onto an existing row"],
                        reviewer="the rater, who must accept or contest the demotion before it lands",
                        retry="one retry then escalate",
                        failure_classes=["detector-failure"],
                        owner_approval=False,
                        sentinel_extra="the failure is either linked to a row or explicitly recorded as unexplained",
                    ),
                },
                "verify": {
                    "id": "recheck-verify",
                    "kind": "gate",
                    "gate": expr_gate(
                        "falsified_rows_demoted == true AND low_confidence_load_bearing_unhandled == 0",
                        "escalate-to-human",
                    ),
                },
            },
        ],
        "stopping_rules": [
            {
                "id": "ledger-clean",
                "expression": "low_confidence_load_bearing_unhandled == 0",
                "applies_to": "workflow",
                "minimum_conditions": "rows_rated >= 1",
                "on_stop": "complete",
            },
            {
                "id": "probe-impossible",
                "expression": "probe_impossible == true AND risk_recorded_with_blast_radius == true",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": two_strikes(3, "owner", ["detector-failure", "severed-stream"]),
        "failure_policy": failure_policy(
            "escalate-to-human",
            ["stale-premise", "detector-failure", "overclaim"],
            "owner",
            "command-center/quarantine/req04",
        ),
        "resume": resume(
            "command-center/checkpoints/req04",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key", "params_hash"],
        ),
        "replay": replay(
            20260810,
            "command-center/replay/req04.jsonl",
            ["params", "inputs", "tool_calls", "model_outputs"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/req04",
            ["workflow_version", "stage_id", "inputs_hash", "model_id"],
            86400,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/req04-plan.json",
            ["Bash:git", "Bash:python", "Write(command-center/assumptions/**)"],
            ["plan", "estimate", "graph"],
        ),
        "estimate": estimate_static(
            wallclock=(120, 900, 3600),
            tokens=(20000, 120000, 400000),
            tool_calls=(20, 160),
            risk="low",
            reversibility="reversible",
            blast_radius="read-only over the plan and repo; writes only under command-center/assumptions/**",
        ),
        "portability": portability("command-center/export/bp-req-04.bundle.json"),
        "lineage": lineage(
            [
                ("AGENTS.md#1b-surface-load-bearing-assumptions", "REBUILD-FROM-SPEC"),
                ("skills/fresh-context-verify", "COMPOSE"),
                ("workflows/plan-gate.mjs", "DISTILL"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-04", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "ledger": artifact(
                "command-center/assumptions/req04-rated.json",
                schema("residual-risk-ledger"),
                min_bytes=256,
                consumers=["the calling plan", "bp-pln-01.mechanical-plan-lint-then-adversarial-trio"],
            ),
            "probes": artifact(
                "command-center/assumptions/req04-probe.json",
                schema("stale-premise-reprobe"),
                min_bytes=192,
                consumers=["the calling plan"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-04 (doc-order 26 of 96)",
            "distinguishing_mechanism": (
                "route a LOW-confidence load-bearing row to a cross-vendor VERIFICATION PROBE, "
                "not to an owner question; and resolve a blank required field to the worst case. "
                "BP-REQ-03 asks the owner; this one interrogates the world."
            ),
            "worked_example": {
                "name": "stale pinned ref plus a blank required field",
                "narrative": (
                    "A plan assumes 'origin/main is at the ref we pinned three weeks ago' and "
                    "leaves the rollback field blank. The pinned-ref row is load-bearing with low "
                    "confidence and no probe, so it must be reported unhandled. The blank rollback "
                    "field must resolve to the declared worst case, not to an empty string."
                ),
                "mechanism": "mechanisms.unhandled_assumptions + mechanisms.blank_field_default",
                "input": {
                    "rows": [
                        {
                            "text": "origin/main is still at the ref pinned three weeks ago",
                            "load_bearing": True,
                            "confidence": "low",
                            "verification_probe": None,
                        },
                        {
                            "text": "the test suite runs in under ten minutes",
                            "load_bearing": False,
                            "confidence": "low",
                            "verification_probe": None,
                        },
                        {
                            "text": "the coverage gate command exists in this project",
                            "load_bearing": True,
                            "confidence": "low",
                            "verification_probe": "read .coverage-thresholds.json and run enforcement.command",
                        },
                    ],
                    "blank_field": {"declared": "", "worst_case": "no rollback path exists"},
                },
                "expected": {
                    "unhandled_texts": ["origin/main is still at the ref pinned three weeks ago"],
                    "blank_resolves_to": "no rollback path exists",
                },
                "controls": [
                    {
                        "mutate": "give the pinned-ref row a verification_probe",
                        "expected_unhandled": 0,
                        "why": "a probed row is handled; the gate must then pass",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- REQ-05


def bp_req_05() -> dict[str, Any]:
    """Intent-to-PRD: mechanical testability lint + decision-log ancestry BEFORE any reviewer."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-req-05.intent-to-prd-with-reviewer",
        "name": "Intent-to-PRD with Testability Lint",
        "description": (
            "Convert a CLOSED decision log into requirements whose acceptance criteria a test can "
            "later assert. The adaptation over the source skill is two mechanical checks that run "
            "BEFORE any reviewer is spent: every requirement must carry a machine-checkable "
            "acceptance criterion, and every requirement must trace to a decision-log ancestor - "
            "an orphan requirement is scope creep. A PRD over an unsettled decision log is fiction."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["product-design-and-strategy"],
        "tags": ["prd", "acceptance-criteria", "traceability", "lint-before-llm"],
        "flagship": True,
        "params": {
            "decision_log_path": {"type": "path", "required": True, "description": "The CLOSED decision log"},
            "definition_of_done": {"type": "string", "required": True, "min_length": 10, "description": "The owner's DoD"},
            "non_goals": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Explicit non-goals; a requirement contradicting one is a violation",
            },
            "allow_unverifiable": {
                "type": "boolean",
                "default": False,
                "description": "When false, a requirement with testable=false blocks; the owner may accept one explicitly",
            },
        },
        "roles": {
            "author": {
                "description": "Writes requirements strictly from settled decisions, inventing nothing",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "tool_permissions": ["Read", "Grep", "Write(command-center/prd/**)"],
                "write_paths": ["command-center/prd/**"],
            },
            "feasibility_reviewer": {
                "description": "Adversarial lens: can this be built at all, with what is actually available",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "always",
            },
            "completeness_reviewer": {
                "description": "Adversarial lens: what the DoD requires and the PRD omits",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "always",
            },
            "scope_reviewer": {
                "description": "Adversarial lens: requirements that exceed the decision log or contradict a non-goal",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "always",
            },
            "owner": {
                "description": "Accepts, explicitly and in writing, any requirement that cannot be verified",
                "vendor": "human",
                "authority": "owner",
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Write(command-center/prd/**)"],
            network="none",
            write_paths=["command-center/prd/**"],
            require_owner_approval=["Write(command-center/prd/accepted-unverifiable.json)"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == scope_reviewer",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "the scope lens is the one most likely to share the author's frame, so it is cross-vendor",
                }
            ],
        ),
        "gates": {
            "testability-lint": expr_gate(
                "untestable_requirements == 0 OR allow_unverifiable == true", "fail"
            ),
            "traceability-lint": expr_gate("orphan_requirements == 0", "fail"),
            "trio-pass": expr_gate("reviewers_passed == 3", "repair"),
        },
        "stages": [
            {
                "id": "s0-author",
                "title": "S0 AUTHOR requirements from the decision log",
                "kind": "task",
                "role": "author",
                "timeout_seconds": 1800,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-REQ05-S0",
                    title="Author requirements that each cite the decision that produced them",
                    phase="2B",
                    target="Turn each settled decision into one or more requirements, each with an acceptance criterion and a decision id.",
                    inputs=["params.decision_log_path", "params.definition_of_done", "params.non_goals"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="author",
                    basis="substantive subagents default to Opus",
                    tools=["Read", "Grep", "Write(command-center/prd/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/prd/req05-requirements.json",
                    output_schema=schema("requirement-record"),
                    evidence="every requirement carries the decision-log id it descends from and a criterion with a comparator and a quantity",
                    tests=[
                        "a requirement phrased 'should feel fast' must be emitted with testable=false so the lint can reject it",
                        "a requirement with no decision id must be emitted so the traceability lint can flag it",
                    ],
                    reviewer="the adversarial trio, after the mechanical lints pass",
                    retry="two strikes then pivot; a third authoring pass on the same frame is banned",
                    failure_classes=["spec-underspecified", "scope-creep"],
                    owner_approval=False,
                    sentinel_extra="every requirement carries an acceptance criterion field, even when testable=false",
                ),
                "produces": [
                    artifact(
                        "command-center/prd/req05-requirements.json",
                        schema("requirement-record"),
                        min_bytes=512,
                        sentinel="SUCCESS:BP3-REQ05-S0",
                        consumers=["s1-lint", "s1b-trace", "s2-review"],
                    )
                ],
            },
            {
                "id": "s1-lint",
                "title": "S1 LINT: every acceptance criterion must be machine-checkable",
                "kind": "gate",
                "depends_on": ["s0-author"],
                "gate_ref": "testability-lint",
            },
            {
                "id": "s1b-trace",
                "title": "S1b TRACE every requirement to a decision-log ancestor",
                "kind": "gate",
                "depends_on": ["s1-lint"],
                "gate_ref": "traceability-lint",
            },
            {
                "id": "s2-review",
                "title": "S2 REVIEW adversarially - three independent lenses in parallel",
                "kind": "fanout",
                "depends_on": ["s1b-trace"],
                "over": {
                    "source": "literal",
                    "items": ["feasibility", "completeness", "scope"],
                    "item_var": "lens",
                    "key_field": "lens",
                },
                "max_concurrency": 3,
                "arrival_stagger_ms": 250,
                "on_item_failure": "continue",
                "body": [
                    {
                        "id": "review-lens",
                        "kind": "task",
                        "role": "feasibility_reviewer",
                        "timeout_seconds": 1800,
                        "work_unit": wu(
                            uid="BP3-REQ05-S2",
                            title="Review the PRD through exactly one named lens",
                            phase="2B",
                            target="Return a typed PASS or FAIL for one lens, with every blocking item anchored to a requirement id.",
                            inputs=["command-center/prd/req05-requirements.json"],
                            dependencies=["BP3-REQ05-S0"],
                            model="opus",
                            vendor="anthropic",
                            role="feasibility_reviewer",
                            basis="one lens per agent so a single reviewer cannot average two verdicts together",
                            tools=["Read", "Grep"],
                            substrate="local-parallel",
                            timeout=1800,
                            output_path="command-center/prd/req05-review.json",
                            output_schema=schema("meta-review-finding"),
                            evidence="each blocking item names the requirement id and the reason it cannot pass",
                            tests=["a reviewer returning prose instead of a typed verdict is retried once with the vocabulary enumerated inline, then treated as a null lens"],
                            reviewer="the aggregator, which counts lenses rather than averaging opinions",
                            retry="one retry with the verdict vocabulary enumerated inline, then null lens",
                            failure_classes=["schema-invalid", "null-lens"],
                            owner_approval=False,
                            sentinel_extra="the artifact carries a recognised verdict token and every blocking item names a requirement id",
                        ),
                    }
                ],
                "barrier": {
                    "mode": "all",
                    "on_partial": "proceed-with-quarantine",
                    "reject_result_matching": ["started in the background", "Check /codex:status"],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s2-gate",
                "title": "S2 gate: all three lenses must PASS",
                "kind": "gate",
                "depends_on": ["s2-review"],
                "gate_ref": "trio-pass",
            },
            {
                "id": "s3-revise",
                "title": "S3 REVISE against the blocking items, then re-lint",
                "kind": "loop",
                "depends_on": ["s2-gate"],
                "loop_var": "revision",
                "body": [
                    {
                        "id": "apply-revision",
                        "kind": "task",
                        "role": "author",
                        "timeout_seconds": 1800,
                        "work_unit": wu(
                            uid="BP3-REQ05-S3",
                            title="Rewrite only the blocked requirements",
                            phase="2B",
                            target="Rewrite each blocked requirement so its criterion is machine-checkable, or escalate it for explicit owner acceptance.",
                            inputs=["command-center/prd/req05-review.json"],
                            dependencies=["BP3-REQ05-S2"],
                            model="opus",
                            vendor="anthropic",
                            role="author",
                            basis="the author owns the revision; reviewers do not rewrite",
                            tools=["Read", "Write(command-center/prd/**)"],
                            substrate="local-single",
                            timeout=1800,
                            output_path="command-center/prd/req05-requirements.json",
                            output_schema=schema("requirement-record"),
                            evidence="each revised requirement links the blocking item it answers",
                            tests=["a revision that silently drops a blocked requirement rather than fixing it must be caught by the closure count"],
                            reviewer="the same three lenses, re-run on the revised document",
                            retry="bounded by the loop convergence, never by an inner retry",
                            failure_classes=["overclaim", "scope-creep"],
                            owner_approval=False,
                            sentinel_extra="the revised requirement count is not lower than the original minus explicitly withdrawn items",
                        ),
                    }
                ],
                "convergence": {
                    "max_iterations": 3,
                    "min_iterations": 1,
                    "converged_when": "blocking_items == 0 AND untestable_requirements == 0",
                    "no_progress_rounds": 2,
                    "metrics": [
                        {"name": "blocking_items", "direction": "decrease", "target": 0},
                        {"name": "untestable_requirements", "direction": "decrease", "target": 0},
                    ],
                    "on_no_convergence": "escalate",
                },
            },
            {
                "id": "s3b-owner-accept",
                "title": "S3b OWNER accepts any requirement that stays unverifiable",
                "kind": "human_checkpoint",
                "depends_on": ["s3-revise"],
                "when": "untestable_requirements > 0",
                "prompt": "One or more requirements cannot be expressed as a machine-checkable criterion. Accept them as explicitly unverifiable, or send them back for rewriting.",
                "approvers": ["owner"],
                "approval_mode": "owner-only",
                "timeout_seconds": 86400,
                "on_timeout": "fail",
                "owner_approval_required": True,
                "options": ["accept-as-unverifiable", "return-for-rewrite"],
                "decision_artifact": artifact(
                    "command-center/prd/accepted-unverifiable.json",
                    schema("owner-decision-packet"),
                    min_bytes=128,
                ),
            },
        ],
        "stopping_rules": [
            {
                "id": "prd-closed",
                "expression": "untestable_requirements == 0 AND orphan_requirements == 0 AND reviewers_passed == 3",
                "applies_to": "workflow",
                "minimum_conditions": "requirements_count >= 1",
                "on_stop": "complete",
            },
            {
                "id": "decision-log-open",
                "expression": "decision_log_closed == false",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": two_strikes(3, "s3b-owner-accept", ["schema-invalid", "null-lens"]),
        "failure_policy": failure_policy(
            "escalate-to-human",
            ["spec-underspecified", "scope-creep", "null-lens"],
            "s3b-owner-accept",
            "command-center/quarantine/req05",
        ),
        "resume": resume(
            "command-center/checkpoints/req05",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        "replay": replay(
            20260810,
            "command-center/replay/req05.jsonl",
            ["params", "inputs", "model_outputs"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/req05",
            ["workflow_version", "stage_id", "inputs_hash"],
            604800,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/req05-plan.json",
            ["Write(command-center/prd/**)"],
            ["plan", "estimate", "artifact-diff"],
        ),
        "estimate": estimate_static(
            wallclock=(600, 2400, 7200),
            tokens=(60000, 250000, 700000),
            tool_calls=(30, 220),
            risk="low",
            reversibility="reversible",
            blast_radius="writes only under command-center/prd/**; produces a document, changes no code",
        ),
        "portability": portability("command-center/export/bp-req-05.bundle.json"),
        "lineage": lineage(
            [
                ("skills/to-prd", "EXTEND"),
                ("workflows/plan-gate.mjs", "DISTILL"),
                ("metaswarm/plan-review-gate", "COMPOSE"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-05", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "prd": artifact(
                "command-center/prd/req05-requirements.json",
                schema("requirement-record"),
                min_bytes=512,
                consumers=["bp-pln-01.mechanical-plan-lint-then-adversarial-trio", "the test phase"],
            ),
            "closure": artifact(
                "command-center/prd/req05-closure.json",
                schema("requirement-closure"),
                min_bytes=192,
                consumers=["the implementation phase"],
            ),
            "traceability": artifact(
                "command-center/prd/req05-traceability.json",
                schema("traceability-matrix"),
                min_bytes=192,
                consumers=["the owner", "bp-pln-01.mechanical-plan-lint-then-adversarial-trio"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-REQ-05 (doc-order 27 of 96)",
            "distinguishing_mechanism": (
                "two MECHANICAL lints (criterion testability, decision-log ancestry) gate the "
                "reviewers, so no adversarial budget is spent on a document a script can reject. "
                "BP-PLN-01 applies the same ordering to a PLAN (the HOW); this applies it to "
                "REQUIREMENTS (the WHAT)."
            ),
            "worked_example": {
                "name": "should-feel-fast and an orphan requirement",
                "narrative": (
                    "Four requirements are authored. 'The export should feel fast' has no "
                    "comparator and no quantity, so the testability lint rejects it. 'Add a dark "
                    "theme' traces to no decision id, so the traceability lint flags it as scope "
                    "creep. The two well-formed requirements pass both lints."
                ),
                "mechanism": "mechanisms.is_testable + mechanisms.orphan_requirements",
                "input": {
                    "criteria": {
                        "R1": "p95 export latency <= 2000 ms measured over 100 runs",
                        "R2": "The export should feel fast",
                        "R3": "exactly 0 rows are dropped when the source file is truncated",
                        "R4": "the UI is clean and modern",
                    },
                    "ancestors": {"R1": "D-004", "R2": "D-004", "R3": "D-007", "R4": None},
                    "decision_ids": ["D-004", "D-007"],
                },
                "expected": {
                    "testable": {"R1": True, "R2": False, "R3": True, "R4": False},
                    "orphans": ["R4"],
                },
                "controls": [
                    {
                        "mutate": "rewrite R2 as 'p95 export latency <= 2000 ms'",
                        "expected_testable": True,
                        "why": "a comparator plus a quantity is exactly what makes it assertable",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- ARC-01


def bp_arc_01() -> dict[str, Any]:
    """Architecture tournament: frozen rubric, pairwise bracket, MANDATORY minority-report fold-in."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-arc-01.architecture-tournament",
        "name": "Architecture Tournament with Minority-Report Fold-In",
        "description": (
            "Generate N genuinely independent architectures, then run them head-to-head in a "
            "pairwise bracket scored on a rubric FROZEN before generation, so the winner beats a "
            "rival rather than a blank page. Three properties make this more than a beauty "
            "contest: a critical error eliminates in round one instead of being averaged away, a "
            "champion must beat its rival on a NAMED dimension, and the minority report of what "
            "the losers did better is mandatory and is folded back into the champion."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability", "collective-intelligence-and-meta"],
        "tags": ["tournament", "frozen-rubric", "minority-report", "independence"],
        "flagship": True,
        "params": {
            "problem": {"type": "string", "required": True, "min_length": 20, "description": "The architecture question"},
            "n_architectures": {
                "type": "integer",
                "default": 4,
                "minimum": 2,
                "maximum": 16,
                "description": "How many independent architectures to generate",
            },
            "rubric_weights": {
                "type": "object",
                "required": True,
                "description": "dimension -> weight, FROZEN before S1; mutating it after generation is the failure this blueprint exists to prevent",
                "schema": {
                    "type": "object",
                    "minProperties": 2,
                    "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
            "critical_error_dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Dimensions on which a zero is fatal rather than merely low-scoring",
            },
            "constraints": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Hard constraints every architecture must satisfy",
            },
        },
        "roles": {
            "architect": {
                "description": "Produces ONE architecture in isolation, blind to every sibling's output",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "max",
                "authority": "advisory",
                "independence": "independent",
                "min_participants": 2,
                "max_participants": 16,
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "bracket_judge": {
                "description": "Scores one pair on the frozen rubric and must name the deciding dimension",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "judge",
                "vote_weight": 1,
                "independence": "cross-examining",
                "tool_permissions": ["Read", "Bash:python"],
                "speaking_rights": "always",
            },
            "cross_vendor_judge": {
                "description": "Second judge from another vendor, so a shared blind spot cannot decide the bracket",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "judge",
                "independence": "independent",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Bash:python"],
            },
            "minority_writer": {
                "description": "Writes what each eliminated architecture did better, and what must be folded in",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": ["Read", "Write(command-center/tournament/**)"],
                "write_paths": ["command-center/tournament/**"],
            },
            "owner": {
                "description": "Decides whether the tournament cost is warranted for this decision size",
                "vendor": "human",
                "authority": "owner",
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/tournament/**)"],
            network="none",
            write_paths=["command-center/tournament/**"],
            forbid_write_paths=["command-center/WORK-UNIT-CATALOG.json"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == cross_vendor_judge",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "cross-vendor diversity on the judging seat, not only on the generating seat",
                }
            ],
            escalation={
                "on": ["low-confidence", "reviewer-refuted"],
                "target": {"model": "opus", "vendor": "anthropic", "effort": "max"},
                "max_escalations": 2,
            },
        ),
        "gates": {
            "rubric-frozen": expr_gate(
                "rubric_hash_recorded == true AND rubric_changed_after_generation == false", "fail"
            ),
            "independence": expr_gate("near_duplicate_pairs == 0", "retry"),
            "named-dimension": expr_gate(
                "champion_selected == true AND deciding_dimension_named == true", "fail"
            ),
            "minority-mandatory": expr_gate(
                "minority_report_written == true AND fold_in_decisions_recorded == true",
                "fail",
            ),
            # The terminal deliverable is gated by the program's ONE shared 12-condition
            # completion predicate, referenced rather than reimplemented here.
            "champion-artifact-complete": unit_gate(
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "repair"
            ),
        },
        "stages": [
            {
                "id": "s0-freeze-rubric",
                "title": "S0 FIX the rubric and weights, and hash them",
                "kind": "gate",
                "gate_ref": "rubric-frozen",
                "produces": [
                    artifact(
                        "command-center/tournament/arc01-rubric.json",
                        schema("architecture-review"),
                        min_bytes=128,
                        consumers=["s2-bracket"],
                    )
                ],
            },
            {
                "id": "s1-generate",
                "title": "S1 GENERATE N architectures in isolation",
                "kind": "fanout",
                "depends_on": ["s0-freeze-rubric"],
                "over": {
                    "source": "param",
                    "ref": "n_architectures",
                    "item_var": "architect_slot",
                    "key_field": "architect_slot",
                },
                "max_concurrency": 8,
                "arrival_stagger_ms": 400,
                "max_items": 16,
                "on_item_failure": "quarantine",
                "body": [
                    {
                        "id": "generate-one",
                        "kind": "task",
                        "role": "architect",
                        "timeout_seconds": 3600,
                        "work_unit": wu(
                            uid="BP3-ARC01-S1",
                            title="Produce one architecture without seeing any sibling",
                            phase="2B",
                            target="Design one complete architecture for the stated problem, scoring itself against no rubric dimension it invented.",
                            inputs=["params.problem", "params.constraints", "command-center/tournament/arc01-rubric.json"],
                            dependencies=[],
                            model="opus",
                            vendor="anthropic",
                            role="architect",
                            basis="independent generation demands maximum effort per lens",
                            tools=["Read", "Grep", "Glob"],
                            substrate="local-parallel",
                            timeout=3600,
                            output_path="command-center/tournament/arc01-architecture.json",
                            output_schema=schema("architecture-dossier"),
                            evidence="every design claim anchors to a repo fact or an external source; a claim with neither is marked UNVERIFIED inline",
                            tests=[
                                "an architecture whose fingerprint equals a sibling's must be re-run with a different seed constraint",
                                "an architecture violating a declared constraint must be rejected before scoring",
                            ],
                            reviewer="two bracket judges, one of them cross-vendor; never the sibling architects",
                            retry="two strikes then pivot to a different seed constraint rather than a third identical run",
                            failure_classes=["independence-violation", "constraint-violation"],
                            owner_approval=False,
                            sentinel_extra="the dossier declares a fingerprint and satisfies every declared constraint",
                        ),
                    }
                ],
                "barrier": {
                    "mode": "quorum",
                    "quorum": 0.75,
                    "on_partial": "proceed-degraded",
                    "reject_result_matching": ["started in the background", "Check /codex:status"],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s1b-independence",
                "title": "S1b CHECK independence - a near-duplicate is a failed lens, not a consensus",
                "kind": "gate",
                "depends_on": ["s1-generate"],
                "gate_ref": "independence",
            },
            {
                "id": "s2-bracket",
                "title": "S2 BRACKET: pairwise comparisons on the frozen rubric",
                "kind": "loop",
                "depends_on": ["s1b-independence"],
                "loop_var": "bracket_round",
                "body": [
                    {
                        "id": "judge-round",
                        "kind": "task",
                        "role": "bracket_judge",
                        "timeout_seconds": 2400,
                        "work_unit": wu(
                            uid="BP3-ARC01-S2",
                            title="Judge one bracket round on the frozen rubric",
                            phase="2B",
                            target="For each pair, compute the weighted score, apply the critical-error override, and name the deciding dimension.",
                            inputs=["command-center/tournament/arc01-architecture.json", "command-center/tournament/arc01-rubric.json"],
                            dependencies=["BP3-ARC01-S1"],
                            model="opus",
                            vendor="anthropic",
                            role="bracket_judge",
                            basis="scoring is arithmetic over declared scores; the judgement is only in assigning the scores",
                            tools=["Read", "Bash:python"],
                            substrate="local-parallel",
                            timeout=2400,
                            output_path="command-center/tournament/arc01-bracket.json",
                            output_schema=schema("tournament-score"),
                            evidence="every round records both weighted totals, the deciding dimension, and what the loser scored higher on",
                            tests=[
                                "a deliberately fatal architecture must be eliminated in round one by the critical-error override, not out-scored on average",
                                "a round whose winner names no deciding dimension must FAIL",
                            ],
                            reviewer="the cross-vendor judge re-scores any round decided by less than one rubric point",
                            retry="two strikes then pivot to explicit re-scoring by the cross-vendor judge",
                            failure_classes=["overclaim", "detector-failure"],
                            owner_approval=False,
                            sentinel_extra="each round names a deciding dimension and records the loser's better dimensions",
                        ),
                    }
                ],
                "convergence": {
                    "max_iterations": 5,
                    "min_iterations": 1,
                    "converged_when": "remaining_architectures == 1",
                    "no_progress_rounds": 1,
                    "metrics": [{"name": "remaining_architectures", "direction": "decrease", "target": 1}],
                    "on_no_convergence": "escalate",
                },
            },
            {
                "id": "s2-gate",
                "title": "S2 gate: a champion must beat a rival on a NAMED dimension",
                "kind": "gate",
                "depends_on": ["s2-bracket"],
                "gate_ref": "named-dimension",
            },
            {
                "id": "s3-minority",
                "title": "S3 WRITE the minority report of what the losers did better",
                "kind": "task",
                "role": "minority_writer",
                "depends_on": ["s2-gate"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC01-S3",
                    title="Record every dimension on which an eliminated architecture beat the champion",
                    phase="2B",
                    target="Enumerate the losers' wins and propose, per win, whether it can be folded into the champion.",
                    inputs=["command-center/tournament/arc01-bracket.json"],
                    dependencies=["BP3-ARC01-S2"],
                    model="opus",
                    vendor="anthropic",
                    role="minority_writer",
                    basis="informed rather than independent - this role must read every dossier",
                    tools=["Read", "Write(command-center/tournament/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/tournament/arc01-minority.json",
                    output_schema=schema("dissent-audit"),
                    evidence="each entry names the losing architecture, the dimension, and the score gap that justifies the claim",
                    tests=["a bracket in which some loser scored higher on some dimension must produce a non-empty minority report"],
                    reviewer="the cross-vendor judge checks that no loser win was omitted",
                    retry="one retry then escalate; discarding the losers is not an acceptable outcome",
                    failure_classes=["digest-loss", "overclaim"],
                    owner_approval=False,
                    sentinel_extra="every dimension on which a loser out-scored the champion appears in the report",
                ),
                "produces": [
                    artifact(
                        "command-center/tournament/arc01-minority.json",
                        schema("dissent-audit"),
                        min_bytes=192,
                        sentinel="SUCCESS:BP3-ARC01-S3",
                        consumers=["s4-fold-in"],
                    )
                ],
            },
            {
                "id": "s4-fold-in",
                "title": "S4 FOLD the minority report's wins into the champion",
                "kind": "task",
                "role": "minority_writer",
                "depends_on": ["s3-minority"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC01-S4",
                    title="Fold each accepted minority win into the champion architecture",
                    phase="2B",
                    target="Produce the champion-plus-fold-in dossier, recording for each minority win whether it was folded in and why.",
                    inputs=["command-center/tournament/arc01-minority.json", "command-center/tournament/arc01-bracket.json"],
                    dependencies=["BP3-ARC01-S3"],
                    model="opus",
                    vendor="anthropic",
                    role="minority_writer",
                    basis="the fold-in is what makes a tournament worth more than a single design council",
                    tools=["Read", "Write(command-center/tournament/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/tournament/arc01-champion.json",
                    output_schema=schema("architecture-dossier"),
                    evidence="every minority win carries an explicit folded_in true/false with a reason",
                    tests=["a champion dossier that records no fold-in decision for a listed minority win must FAIL"],
                    reviewer="the owner, who is the only role that can accept the champion",
                    retry="one retry then escalate to the owner",
                    failure_classes=["digest-loss"],
                    owner_approval=False,
                    sentinel_extra="every minority win has an explicit folded_in decision with a reason",
                ),
            },
            {
                "id": "s4-gate",
                "title": "S4 gate: the minority report and its fold-in decisions both exist",
                "kind": "gate",
                "depends_on": ["s4-fold-in"],
                "gate_ref": "minority-mandatory",
            },
            {
                "id": "s4b-predicate",
                "title": "S4b gate the champion dossier on the shared 12-condition predicate",
                "kind": "gate",
                "depends_on": ["s4-gate"],
                "gate_ref": "champion-artifact-complete",
            },
        ],
        "stopping_rules": [
            {
                "id": "champion-with-fold-in",
                "expression": "champion_selected == true AND minority_report_written == true AND fold_in_decisions_recorded == true",
                "applies_to": "workflow",
                "minimum_conditions": "architectures_scored >= 2",
                "on_stop": "complete",
            },
            {
                "id": "criteria-not-fixable",
                "expression": "rubric_fixable == false",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": two_strikes(3, "owner", ["independence-violation", "schema-invalid"]),
        "failure_policy": failure_policy(
            "degrade-loudly",
            ["independence-violation", "constraint-violation", "digest-loss"],
            "owner",
            "command-center/quarantine/arc01",
        ),
        "resume": resume(
            "command-center/checkpoints/arc01",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key", "params_hash"],
        ),
        # The bracket record, not the deliberation, is the artifact: judge scoring is not
        # reproducible, so replay verifies the SCHEMA of the record rather than a hash.
        "replay": replay(
            20260810,
            "command-center/replay/arc01.jsonl",
            ["params", "inputs", "model_outputs", "timings"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/arc01",
            ["workflow_version", "stage_id", "item_key", "params_hash", "model_id"],
            259200,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/arc01-plan.json",
            ["Bash:python", "Write(command-center/tournament/**)"],
            ["plan", "estimate", "graph"],
        ),
        "estimate": estimate_static(
            wallclock=(1800, 9000, 28800),
            tokens=(300000, 1400000, 4000000),
            tool_calls=(80, 600),
            risk="medium",
            reversibility="reversible",
            blast_radius="writes only under command-center/tournament/**; produces a design decision, no code",
        ),
        "portability": portability("command-center/export/bp-arc-01.bundle.json"),
        "lineage": lineage(
            [
                ("skills/execution-grounded-bon", "GENERALIZE"),
                ("skills/critique-panel", "COMPOSE"),
                ("workflows/design-gate.mjs", "COMPOSE"),
                ("workflows/trainer-gui-mega-plan", "DISTILL"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-01", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "champion": artifact(
                "command-center/tournament/arc01-champion.json",
                schema("architecture-dossier"),
                min_bytes=1024,
                consumers=["the owner", "bp-arc-04.failure-domain-mapping-workshop"],
            ),
            "bracket": artifact(
                "command-center/tournament/arc01-bracket.json",
                schema("tournament-score"),
                min_bytes=512,
                consumers=["the owner"],
            ),
            "minority": artifact(
                "command-center/tournament/arc01-minority.json",
                schema("dissent-audit"),
                min_bytes=192,
                consumers=["the owner", "the champion fold-in stage"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-01 (doc-order 28 of 96)",
            "owner_decision": (
                "OPEN: is a tournament worth 3-5x a single design council at this estate's typical "
                "decision size? Recorded here rather than silently answered."
            ),
            "distinguishing_mechanism": (
                "pairwise bracket over GENERATED candidates with a critical-error override and a "
                "mandatory minority-report fold-in. BP-PLN-01 gates ONE artifact; this one "
                "selects among several and then re-imports what the losers did better."
            ),
            "worked_example": {
                "name": "a fatal candidate eliminated in round one",
                "narrative": (
                    "Four architectures are scored on a two-dimension frozen rubric. 'alpha' "
                    "carries a critical error (it stores a credential in the repo) and is "
                    "eliminated before any averaging. 'delta' is a near-duplicate of 'beta', which "
                    "is an independence failure. Of the survivors the champion must name the "
                    "dimension that decided its win, and 'gamma' beat it on recoverability, which "
                    "must appear in the minority report."
                ),
                "mechanism": "mechanisms.eliminate_critical + mechanisms.near_duplicates + mechanisms.bracket",
                "input": {
                    "weights": {"correctness": 0.6, "recoverability": 0.4},
                    "architectures": [
                        {"name": "alpha", "scores": {"correctness": 4, "recoverability": 4}, "critical_errors": ["stores a credential in the repo"], "fingerprint": "a"},
                        {"name": "beta", "scores": {"correctness": 4, "recoverability": 1}, "critical_errors": [], "fingerprint": "b"},
                        {"name": "gamma", "scores": {"correctness": 2, "recoverability": 4}, "critical_errors": [], "fingerprint": "c"},
                        {"name": "delta", "scores": {"correctness": 4, "recoverability": 1}, "critical_errors": [], "fingerprint": "b"},
                    ],
                },
                "expected": {
                    "eliminated": ["alpha"],
                    "near_duplicate_pairs": [["beta", "delta"]],
                    "champion": "beta",
                    "minority_report_contains": ["recoverability"],
                },
                "controls": [
                    {
                        "mutate": "clear alpha's critical_errors",
                        "expected_champion": "alpha",
                        "why": "the override is doing the work - without it the fatal design wins on score",
                    }
                ],
            },
        },
    }


BLUEPRINTS = [bp_req_03, bp_req_04, bp_req_05, bp_arc_01]
