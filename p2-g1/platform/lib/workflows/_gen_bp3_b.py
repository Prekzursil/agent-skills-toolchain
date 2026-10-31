"""bp-3 blueprints 5-8: BP-ARC-02, BP-ARC-03, BP-ARC-04, BP-ARC-05.

Design source: 09-WORKFLOW-BLUEPRINT-LIBRARY.md lines 1446-1623 (doc-order 29-32 of 96).
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

# --------------------------------------------------------------------------------- ARC-02


def bp_arc_02() -> dict[str, Any]:
    """Architect-to-Editor split: a typed change-spec crosses the vendor boundary, not a chat."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-arc-02.architect-to-editor-split-build",
        "name": "Architect-to-Editor Split Build",
        "description": (
            "Separate deciding WHAT to change from mechanically applying it: an Opus architect "
            "emits a typed change-spec, a Codex editor applies it. The change-spec - not the "
            "conversation - is the durable, reviewable, re-appliable artifact, so a different "
            "editor can reproduce the change. The lint ladder is capped at max_reflections and "
            "the attempt after the cap ESCALATES to the lead for re-decomposition; it never "
            "becomes a further retry."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["cross-vendor", "change-spec", "lint-ladder", "escalate-not-grind"],
        "flagship": True,
        "params": {
            "goal": {"type": "string", "required": True, "min_length": 15, "description": "What must change, in one sentence"},
            "repo_map_path": {
                "type": "path",
                "required": True,
                "description": "PageRank-ranked symbol map over LSP reference edges - the grounding, not a vector store",
            },
            "max_reflections": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 3,
                "description": "Lint-ladder cap. The attempt after this one escalates; it is never a retry.",
            },
            "sandbox": {
                "type": "enum",
                "enum": ["none", "wsl2", "docker", "modal"],
                "default": "none",
                "description": "Windows has no native OS process sandbox, so any change that EXECUTES anything routes off-native",
            },
            "editor_vendor": {
                "type": "enum",
                "enum": ["openai", "anthropic"],
                "default": "openai",
                "description": "Editor vendor. Defaulting to the non-architect vendor is the point of the split.",
            },
        },
        "roles": {
            "architect": {
                "description": "Decides the change and emits a typed change-spec complete enough that the editor needs no judgement",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "max",
                "authority": "chair",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/changespec/**)"],
                "write_paths": ["command-center/changespec/**"],
                "speaking_rights": "always",
            },
            "editor": {
                "description": "Applies the change-spec verbatim and fails LOUDLY on an under-specified spec instead of improvising",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "advisory",
                "independence": "informed",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep", "Bash:git", "mcp__codex__codex"],
                "speaking_rights": "on-request",
            },
            "lead": {
                "description": "Re-decomposes the work unit when the editor breaches the failure threshold",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "max",
                "authority": "veto",
                "independence": "informed",
                "tool_permissions": ["Read", "Grep", "Write(command-center/changespec/**)"],
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            [
                "Read",
                "Grep",
                "Glob",
                "Bash:git",
                "Bash:python",
                "mcp__codex__codex",
                "Write(command-center/changespec/**)",
            ],
            network="none",
            write_paths=["command-center/changespec/**"],
            forbid_write_paths=["command-center/WORK-UNIT-CATALOG.json"],
            require_owner_approval=["Bash:git"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == editor",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "the editor is deliberately a different vendor from the architect",
                }
            ],
            escalation={
                "on": ["failure", "timeout"],
                "target": {"model": "opus", "vendor": "anthropic", "effort": "max"},
                "max_escalations": 1,
            },
        ),
        "gates": {
            "spec-complete": expr_gate(
                "change_spec_validates == true AND unresolved_editor_questions == 0", "fail"
            ),
            "lint-clean-or-escalate": expr_gate(
                "lint_clean == true OR lint_attempts >= 3", "escalate-to-human"
            ),
            "dispatch-was-blocking": expr_gate(
                "editor_result_is_artifact == true AND background_receipt_returned == false",
                "fail",
            ),
            "unit-complete": unit_gate([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "repair"),
        },
        "stages": [
            {
                "id": "s0-ground",
                "title": "S0 GROUND with a PageRank repo map",
                "kind": "task",
                "role": "architect",
                "timeout_seconds": 1200,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-ARC02-S0",
                    title="Rank the symbols the change will touch, using LSP reference edges",
                    phase="2B",
                    target="Produce the ranked symbol neighbourhood of the goal so the change-spec is grounded in the real call graph.",
                    inputs=["params.goal", "params.repo_map_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="architect",
                    basis="grounding quality determines change-spec quality",
                    tools=["Read", "Grep", "Glob", "Bash:python"],
                    substrate="local-single",
                    timeout=1200,
                    output_path="command-center/changespec/arc02-repo-map.json",
                    output_schema=schema("capability-index"),
                    evidence="every ranked symbol is reachable from a real reference edge, not from a name-similarity guess",
                    tests=["a symbol with no inbound reference edge must not appear in the ranked neighbourhood"],
                    reviewer="the lead reads the map before the change-spec is accepted",
                    retry="two strikes then pivot to a narrower symbol seed",
                    failure_classes=["detector-failure", "spec-underspecified"],
                    owner_approval=False,
                    sentinel_extra="every ranked symbol cites the reference edge that ranked it",
                ),
                "produces": [
                    artifact(
                        "command-center/changespec/arc02-repo-map.json",
                        schema("capability-index"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-ARC02-S0",
                        consumers=["s1-architect"],
                    )
                ],
            },
            {
                "id": "s1-architect",
                "title": "S1 ARCHITECT emits a typed change-spec",
                "kind": "task",
                "role": "architect",
                "depends_on": ["s0-ground"],
                "timeout_seconds": 2400,
                "work_unit": wu(
                    uid="BP3-ARC02-S1",
                    title="Emit a typed change-spec the editor can apply without judgement",
                    phase="2B",
                    target="Write the complete change-spec: per file, the exact edit intent, the acceptance check, and the rollback.",
                    inputs=["command-center/changespec/arc02-repo-map.json", "params.goal"],
                    dependencies=["BP3-ARC02-S0"],
                    model="opus",
                    vendor="anthropic",
                    role="architect",
                    basis="the deciding is the hard part and belongs on the strongest model",
                    tools=["Read", "Grep", "Write(command-center/changespec/**)"],
                    substrate="local-single",
                    timeout=2400,
                    output_path="command-center/changespec/arc02-change-spec.json",
                    output_schema=schema("contract-spec"),
                    evidence="each edit names the file, the anchor it applies at, the acceptance check, and the rollback step",
                    tests=[
                        "a spec entry with no acceptance check must FAIL validation, since the editor could not tell success from failure",
                        "a spec that leaves an edit anchor ambiguous must FAIL rather than let the editor choose",
                    ],
                    reviewer="the editor is the reviewer of record: if it needs to ask, the spec is incomplete",
                    retry="two strikes then pivot to a decomposed spec of smaller units",
                    failure_classes=["spec-underspecified", "overclaim"],
                    owner_approval=False,
                    sentinel_extra="every edit carries an anchor, an acceptance check and a rollback",
                ),
                "produces": [
                    artifact(
                        "command-center/changespec/arc02-change-spec.json",
                        schema("contract-spec"),
                        min_bytes=512,
                        sentinel="SUCCESS:BP3-ARC02-S1",
                        consumers=["s2-editor", "the replay surface"],
                    )
                ],
            },
            {
                "id": "s1-gate",
                "title": "S1 gate: an under-specified spec must not reach the editor",
                "kind": "gate",
                "depends_on": ["s1-architect"],
                "gate_ref": "spec-complete",
            },
            {
                "id": "s2-apply",
                "title": "S2 EDITOR applies the spec, S3 LINTs only the changed files",
                "kind": "loop",
                "depends_on": ["s1-gate"],
                "loop_var": "reflection",
                "body": [
                    {
                        "id": "editor-apply",
                        "kind": "task",
                        "role": "editor",
                        "timeout_seconds": 1800,
                        "work_unit": wu(
                            uid="BP3-ARC02-S2",
                            title="Apply the change-spec through a BLOCKING cross-vendor dispatch",
                            phase="2B",
                            target="Apply every edit in the change-spec verbatim, and fail loudly on any entry that requires a judgement call.",
                            inputs=["command-center/changespec/arc02-change-spec.json"],
                            dependencies=["BP3-ARC02-S1"],
                            model="gpt-5-codex",
                            vendor="openai",
                            role="editor",
                            basis="cross-vendor diversity per work unit; the editor is not the architect",
                            tools=["Read", "Grep", "mcp__codex__codex"],
                            substrate="codex-mcp",
                            timeout=1800,
                            output_path="command-center/changespec/arc02-applied-diff.json",
                            output_schema=schema("work-result"),
                            evidence="exit code 0 AND a non-empty parseable output artifact AND that artifact validates against the declared schema - all three, never exit code alone",
                            tests=[
                                "a result string containing 'started in the background' or 'Check /codex:status' must be REJECTED as a receipt, not accepted as a result",
                                "an under-specified spec entry must produce FAILED with the entry id, never an improvised edit",
                            ],
                            reviewer="the lint ladder, then the lead on threshold breach",
                            retry="bounded by the loop convergence at max_reflections; the attempt after the cap escalates instead",
                            failure_classes=["severed-stream", "win-arg-limit", "schema-invalid", "spec-underspecified"],
                            owner_approval=False,
                            sentinel_extra="the dispatch was foreground, the output artifact exists and parses, and it validates against its schema",
                        ),
                    },
                    {
                        "id": "lint-changed-only",
                        "kind": "task",
                        "role": "architect",
                        "depends_on": ["editor-apply"],
                        "timeout_seconds": 900,
                        "work_unit": wu(
                            uid="BP3-ARC02-S3",
                            title="Lint only the files the editor changed",
                            phase="2B",
                            target="Run the project lint over exactly the changed file set, so cost scales with the diff and not with the repo.",
                            inputs=["command-center/changespec/arc02-applied-diff.json"],
                            dependencies=["BP3-ARC02-S2"],
                            model="opus",
                            vendor="anthropic",
                            role="architect",
                            basis="a changed-file-only lint is the smallest check that could still catch this change",
                            tools=["Read", "Bash:python", "Bash:git"],
                            substrate="local-single",
                            timeout=900,
                            output_path="command-center/changespec/arc02-lint.json",
                            output_schema=schema("conformance-report"),
                            evidence="records the exact command, its exit code, and the changed-file list it was given",
                            tests=[
                                "a lint over an EMPTY changed-file set must FAIL closed, because a lint that examined nothing is not a pass",
                                "the lint must be verified against a known-bad file before its silence counts as clean",
                            ],
                            reviewer="none - exit code plus the both-states control is the evidence",
                            retry="bounded by the loop; a lint failure feeds the next reflection",
                            failure_classes=["detector-failure", "lint-failure"],
                            owner_approval=False,
                            sentinel_extra="the changed-file set is non-empty and the recorded command exited 0",
                        ),
                    },
                ],
                "convergence": {
                    "max_iterations": 3,
                    "min_iterations": 1,
                    "converged_when": "lint_violations == 0",
                    "no_progress_rounds": 2,
                    "metrics": [
                        {"name": "lint_violations", "direction": "decrease", "target": 0},
                    ],
                    "on_no_convergence": "escalate",
                },
            },
            {
                "id": "s2-dispatch-gate",
                "title": "S2 gate: a background receipt is not a result",
                "kind": "gate",
                "depends_on": ["s2-apply"],
                "gate_ref": "dispatch-was-blocking",
            },
            {
                "id": "s3-lint-gate",
                "title": "S3 gate: lint clean, or the ladder is spent",
                "kind": "gate",
                "depends_on": ["s2-dispatch-gate"],
                "gate_ref": "lint-clean-or-escalate",
            },
            {
                "id": "s4-escalate",
                "title": "S4 ESCALATE to the lead for re-decomposition - never a fourth attempt",
                "kind": "repair_loop",
                "depends_on": ["s3-lint-gate"],
                "when": "lint_clean == false",
                "target": ["s1-architect", "s2-apply"],
                "max_attempts": 1,
                "classification_filter": ["lint-failure", "spec-underspecified", "severed-stream"],
                "escalate_to": "lead",
                "require_root_cause": True,
                "diagnose": {
                    "id": "lead-diagnose",
                    "kind": "task",
                    "role": "lead",
                    "timeout_seconds": 1200,
                    "work_unit": wu(
                        uid="BP3-ARC02-S4D",
                        title="Decide whether the spec, the decomposition, or the editor failed",
                        phase="2B",
                        target="Attribute the repeated failure to the change-spec, the unit decomposition, or the editor rail, and enumerate at least two alternatives.",
                        inputs=["command-center/changespec/arc02-lint.json", "command-center/changespec/arc02-change-spec.json"],
                        dependencies=["BP3-ARC02-S3"],
                        model="opus",
                        vendor="anthropic",
                        role="lead",
                        basis="re-decomposition is a judgement the lead owns",
                        tools=["Read", "Grep", "Write(command-center/changespec/**)"],
                        substrate="local-single",
                        timeout=1200,
                        output_path="command-center/changespec/arc02-escalation.json",
                        output_schema=schema("root-cause-graph"),
                        evidence="names the failing fingerprint and at least two mechanically different alternatives",
                        tests=["an escalation offering fewer than two alternatives must FAIL - that is a retry wearing an escalation label"],
                        reviewer="the owner when the alternatives all require a scope change",
                        retry="none; this stage IS the pivot",
                        failure_classes=["spec-underspecified", "decomposition-too-coarse"],
                        owner_approval=False,
                        sentinel_extra="at least two mechanically different alternatives are enumerated",
                    ),
                },
                "verify": {
                    "id": "escalation-verified",
                    "kind": "gate",
                    "gate": expr_gate(
                        "alternatives_enumerated >= 2 AND root_cause_named == true", "fail"
                    ),
                },
            },
            {
                "id": "s5-predicate",
                "title": "S5 gate the applied change on the shared 12-condition predicate",
                "kind": "gate",
                "depends_on": ["s4-escalate"],
                "gate_ref": "unit-complete",
            },
        ],
        "stopping_rules": [
            {
                "id": "lint-clean-or-ladder-spent",
                "expression": "lint_clean == true OR lint_attempts >= 3",
                "applies_to": "workflow",
                "minimum_conditions": "change_spec_validates == true",
                "on_stop": "complete",
            },
            {
                "id": "editor-rail-severed",
                "expression": "editor_result_is_artifact == false AND dispatch_attempts >= 2",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": two_strikes(3, "lead", ["severed-stream", "win-arg-limit", "quota-429-storm"]),
        "failure_policy": failure_policy(
            "escalate-to-human",
            ["severed-stream", "spec-underspecified", "lint-failure"],
            "lead",
            "command-center/quarantine/arc02",
        ),
        "resume": resume(
            "command-center/checkpoints/arc02",
            "work-unit",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        # The change-spec IS the replay surface: a different editor re-applying the same spec is
        # the reproduction, so replay verifies the spec hash rather than the editor's prose.
        "replay": replay(
            20260810,
            "command-center/replay/arc02.jsonl",
            ["params", "inputs", "tool_calls", "tool_results", "env_fingerprint"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/arc02",
            ["workflow_version", "stage_id", "inputs_hash", "prompt_hash", "model_id", "tool_versions"],
            86400,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/arc02-plan.json",
            ["mcp__codex__codex", "Bash:git", "Bash:python", "Write(command-center/changespec/**)"],
            ["plan", "estimate", "permission-report", "artifact-diff"],
        ),
        "estimate": estimate_static(
            wallclock=(600, 3000, 10800),
            tokens=(80000, 400000, 1200000),
            tool_calls=(40, 300),
            risk="medium",
            reversibility="reversible-with-effort",
            blast_radius="the editor mutates repo files; every edit carries a declared rollback and the change-spec can be re-applied or reverted",
        ),
        "portability": portability("command-center/export/bp-arc-02.bundle.json"),
        "lineage": lineage(
            [
                ("skills/orchestration-patterns", "ADOPT-AS-IS"),
                ("rules/common/cross-vendor-dispatch.md", "REBUILD-FROM-SPEC"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-02", "REBUILD-FROM-SPEC"),
            ],
            rollback=["skills/orchestration-patterns@current"],
        ),
        "outputs": {
            "change_spec": artifact(
                "command-center/changespec/arc02-change-spec.json",
                schema("contract-spec"),
                min_bytes=512,
                consumers=["the editor", "any future editor re-applying the change", "code review"],
            ),
            "applied_diff": artifact(
                "command-center/changespec/arc02-applied-diff.json",
                schema("work-result"),
                min_bytes=256,
                consumers=["the lint stage", "code review"],
            ),
            "lint": artifact(
                "command-center/changespec/arc02-lint.json",
                schema("conformance-report"),
                min_bytes=128,
                consumers=["the lint gate", "the lead"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-02 (doc-order 29 of 96)",
            "distinguishing_mechanism": (
                "a typed change-spec crosses the vendor boundary and the lint ladder is CAPPED, so "
                "the attempt after the cap is a re-decomposition rather than a fourth try. "
                "BP-IMP-01 is the per-work-unit quality pipeline; this is the role split INSIDE "
                "its implement step and nests within it."
            ),
            "cross_vendor_dispatch_constraints": [
                "the dispatch MUST block: a job id or a 'started in the background' string is not a result",
                "pass the prompt BY FILE: Windows CreateProcess caps a command line at 32,767 chars",
                "pass --ignore-user-config on every non-interactive invocation, so the active MCP inventory cannot blow the arg limit",
                "set an explicit 30-minute timeout; the silent 10-minute default is what makes agents reach for --background",
            ],
            "worked_example": {
                "name": "the lint ladder escalates on the fourth attempt",
                "narrative": (
                    "The editor applies the spec and the changed-file lint fails three times in a "
                    "row. With max_reflections=3 the ladder stops at three and the outcome is "
                    "'escalate' with three attempts used - a fourth attempt must never be made. "
                    "The control shows the same input reaching 'clean' when the second attempt "
                    "succeeds, which proves the ladder is not simply always escalating."
                ),
                "mechanism": "mechanisms.lint_ladder",
                "input": {"attempt_results": [False, False, False, True], "cap": 3},
                "expected": {"outcome": "escalate", "attempts_used": 3},
                "controls": [
                    {
                        "attempt_results": [False, True, False],
                        "expected_outcome": "clean",
                        "expected_attempts": 2,
                        "why": "the ladder must be capable of both outcomes, or it measures nothing",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- ARC-03


def bp_arc_03() -> dict[str, Any]:
    """Anti-overfit architecture audit: DISARMED is not UNUSED, and no removal without a trace."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-arc-03.anti-overfit-architecture-audit",
        "name": "Anti-Overfit Architecture Audit",
        "description": (
            "Audit an existing agent architecture for accreted complexity: what has been added "
            "that no longer earns its place, and what a minimal rebuild would look like. The "
            "mandatory distinction is DISARMED versus UNUSED - a guard can be registered, "
            "permanently silent, and still load-bearing, so 'not exercised recently' is never "
            "sufficient evidence of deadness. Absent telemetry the component is UNKNOWN, never "
            "presumed dead, and no removal is proposed without a traced blast radius."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["security-governance-and-risk", "engineering-and-reliability"],
        "tags": ["subtraction", "disarmed-vs-unused", "blast-radius", "both-states"],
        "flagship": True,
        "params": {
            "inventory_path": {"type": "path", "required": True, "description": "The component inventory to audit"},
            "telemetry_path": {
                "type": "path",
                "description": "Event-ledger telemetry. When absent every component is UNKNOWN, not dead.",
            },
            "allow_security_removal": {
                "type": "boolean",
                "default": False,
                "description": "OWNER DECISION, unresolved: may this audit even propose removing a security-bearing component?",
            },
            "rejected_components": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Previously rejected candidates, so the audit does not re-propose a settled no",
            },
        },
        "roles": {
            "component_auditor": {
                "description": "Audits one component: is it registered, when was it last exercised, does it fire at all",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "min_participants": 1,
                "max_participants": 64,
                "tool_permissions": ["Read", "Grep", "Glob", "Bash:python"],
            },
            "synthesiser": {
                "description": "Merges the per-component verdicts and sketches the minimal rebuild",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": ["Read", "Write(command-center/audit/**)"],
                "write_paths": ["command-center/audit/**"],
            },
            "removal_critic": {
                "description": "Argues, per proposal, that the component is load-bearing and must survive",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "cross-examining",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep", "Bash:python"],
                "speaking_rights": "rebuttal-only",
            },
            "owner": {
                "description": "The only role that may approve removing anything security-bearing",
                "vendor": "human",
                "authority": "owner",
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/audit/**)"],
            network="none",
            write_paths=["command-center/audit/**"],
            forbid_write_paths=[".claude/hooks/**", ".claude/rules/**", "command-center/WORK-UNIT-CATALOG.json"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == removal_critic",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "the critic must not share the auditor's vantage point, which is what makes a dormant guard look dead",
                }
            ],
        ),
        "gates": {
            "disarmed-distinguished": expr_gate(
                "components_classified_without_both_states_probe == 0", "fail"
            ),
            "no-untraced-removal": expr_gate(
                "removal_proposals_without_blast_radius == 0", "fail"
            ),
            "security-removal-owner-only": expr_gate(
                "security_bearing_removals == 0 OR owner_approved_security_removal == true",
                "escalate-to-human",
            ),
        },
        "stages": [
            {
                "id": "s0-inventory",
                "title": "S0 INVENTORY the components",
                "kind": "task",
                "role": "synthesiser",
                "timeout_seconds": 1200,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-ARC03-S0",
                    title="Enumerate every component, with the scope the enumeration covered",
                    phase="2B",
                    target="List every component in the architecture and state the search scope, because a floor presented as a total is its own failure class.",
                    inputs=["params.inventory_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="synthesiser",
                    basis="the inventory is deterministic; only the later judgement is not",
                    tools=["Read", "Grep", "Glob"],
                    substrate="local-single",
                    timeout=1200,
                    output_path="command-center/audit/arc03-inventory.json",
                    output_schema=schema("audit-inventory"),
                    evidence="records the exact search scope and depth, so the count cannot be read as a total when it is a floor",
                    tests=["an inventory that walked one directory level must declare depth=1, not present its count as complete"],
                    reviewer="the removal critic checks the scope before any verdict is trusted",
                    retry="two strikes then pivot to a wider scope",
                    failure_classes=["detector-truncation"],
                    owner_approval=False,
                    sentinel_extra="the artifact declares its search scope and depth alongside the count",
                ),
                "produces": [
                    artifact(
                        "command-center/audit/arc03-inventory.json",
                        schema("audit-inventory"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-ARC03-S0",
                        consumers=["s1-measure"],
                    )
                ],
            },
            {
                "id": "s1-measure",
                "title": "S1/S1b MEASURE last-exercised from telemetry, and probe DISARMED vs UNUSED",
                "kind": "fanout",
                "depends_on": ["s0-inventory"],
                "over": {
                    "source": "artifact",
                    "ref": "command-center/audit/arc03-inventory.json",
                    "item_var": "component",
                    "key_field": "component_id",
                },
                "max_concurrency": 12,
                "arrival_stagger_ms": 200,
                "max_items": 256,
                "on_item_failure": "quarantine",
                "body": [
                    {
                        "id": "audit-component",
                        "kind": "task",
                        "role": "component_auditor",
                        "timeout_seconds": 900,
                        "work_unit": wu(
                            uid="BP3-ARC03-S1",
                            title="Classify one component as live, dormant, disarmed, unregistered or unknown",
                            phase="2B",
                            target="Measure last-exercised from telemetry and run a both-states probe: does this component fire on a KNOWN-BROKEN input at all?",
                            inputs=["command-center/audit/arc03-inventory.json", "params.telemetry_path"],
                            dependencies=["BP3-ARC03-S0"],
                            model="opus",
                            vendor="anthropic",
                            role="component_auditor",
                            basis="one auditor per component so a single agent cannot average two verdicts",
                            tools=["Read", "Grep", "Bash:python"],
                            substrate="local-parallel",
                            timeout=900,
                            output_path="command-center/audit/arc03-component.json",
                            output_schema=schema("detector-control"),
                            evidence="last-exercised comes from the event ledger, NEVER from a file mtime; the both-states result is recorded as a separate field",
                            tests=[
                                "a registered component that does not fire on a known-broken input must classify as DISARMED, never as unused",
                                "a component with no telemetry and no both-states probe must classify as UNKNOWN, never as dead",
                            ],
                            reviewer="the removal critic, cross-vendor",
                            retry="two strikes then pivot to a different probe class",
                            failure_classes=["detector-failure", "fail-open-on-missing-dependency"],
                            owner_approval=False,
                            sentinel_extra="the artifact carries both a telemetry field and an explicit both-states result",
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
                "id": "s1-gate",
                "title": "S1 gate: nothing is classified without a both-states probe",
                "kind": "gate",
                "depends_on": ["s1-measure"],
                "gate_ref": "disarmed-distinguished",
            },
            {
                "id": "s2-judge",
                "title": "S2/S3 JUDGE earns_place and COMPUTE the removal blast radius",
                "kind": "task",
                "role": "synthesiser",
                "depends_on": ["s1-gate"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC03-S2",
                    title="Decide earns_place per component and trace what breaks if it is removed",
                    phase="2B",
                    target="For each component decide whether it earns its place, and trace every consumer that would break on removal.",
                    inputs=["command-center/audit/arc03-component.json"],
                    dependencies=["BP3-ARC03-S1"],
                    model="opus",
                    vendor="anthropic",
                    role="synthesiser",
                    basis="synthesis over measured classifications, not over impressions",
                    tools=["Read", "Grep", "Write(command-center/audit/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/audit/arc03-blast-radius.json",
                    output_schema=schema("blast-radius"),
                    evidence="every removal proposal enumerates the files, callers and configs that reference the component",
                    tests=[
                        "a removal proposal with an empty consumer trace must FAIL, since an untraced removal is not a proposal",
                        "a component previously in rejected_components must not be re-proposed",
                    ],
                    reviewer="the removal critic argues the opposite case for every proposal",
                    retry="two strikes then pivot; a third identical judgement pass is banned",
                    failure_classes=["overclaim", "detector-truncation"],
                    owner_approval=False,
                    sentinel_extra="every removal proposal carries a non-empty consumer trace",
                ),
            },
            {
                "id": "s3-gate",
                "title": "S3 gate: no removal proposal without a blast-radius trace",
                "kind": "gate",
                "depends_on": ["s2-judge"],
                "gate_ref": "no-untraced-removal",
            },
            {
                "id": "s4-critic",
                "title": "S4 ADVERSARIAL critic: 'you are about to delete something load-bearing'",
                "kind": "task",
                "role": "removal_critic",
                "depends_on": ["s3-gate"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC03-S4",
                    title="Argue that each proposed removal is load-bearing",
                    phase="2B",
                    target="For every removal proposal, construct the strongest case that the component is still load-bearing, and say which case survives.",
                    inputs=["command-center/audit/arc03-blast-radius.json"],
                    dependencies=["BP3-ARC03-S2"],
                    model="gpt-5-codex",
                    vendor="openai",
                    role="removal_critic",
                    basis="a same-vendor critic inherits the vantage point that made the component look dead",
                    tools=["Read", "Grep", "Bash:python"],
                    substrate="codex-mcp",
                    timeout=1800,
                    output_path="command-center/audit/arc03-critique.json",
                    output_schema=schema("refutation-record"),
                    evidence="each counter-argument cites the code path or config that still depends on the component",
                    tests=["a dormant security guard must survive this stage; a critique that clears one is itself the defect"],
                    reviewer="the owner for any security-bearing case",
                    retry="two strikes then pivot to a differently-framed critique",
                    failure_classes=["overclaim", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every proposal has an explicit survives/does-not-survive verdict with a cited dependency",
                ),
            },
            {
                "id": "s4-owner",
                "title": "S4b OWNER decides on any security-bearing removal",
                "kind": "human_checkpoint",
                "depends_on": ["s4-critic"],
                "when": "security_bearing_removals > 0",
                "prompt": "This audit proposes removing a security-bearing component. Approve it, refuse it, or rule that this category is permanently out of scope for architecture audits.",
                "approvers": ["owner"],
                "approval_mode": "owner-only",
                "timeout_seconds": 86400,
                "on_timeout": "fail",
                "owner_approval_required": True,
                "options": ["approve-this-removal", "refuse", "rule-category-out-of-scope"],
                "decision_artifact": artifact(
                    "command-center/audit/arc03-owner-decision.json",
                    schema("owner-decision-packet"),
                    min_bytes=128,
                ),
            },
            {
                "id": "s4-security-gate",
                "title": "S4c gate: a security-bearing removal needs recorded owner approval",
                "kind": "gate",
                "depends_on": ["s4-owner"],
                "gate_ref": "security-removal-owner-only",
            },
            {
                "id": "s5-sketch",
                "title": "S5 SKETCH the minimal rebuild",
                "kind": "task",
                "role": "synthesiser",
                "depends_on": ["s4-security-gate"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC03-S5",
                    title="Sketch what a minimal rebuild of this architecture would contain",
                    phase="2B",
                    target="Describe the smallest architecture that would still satisfy every surviving component's purpose.",
                    inputs=["command-center/audit/arc03-critique.json", "command-center/audit/arc03-blast-radius.json"],
                    dependencies=["BP3-ARC03-S4"],
                    model="opus",
                    vendor="anthropic",
                    role="synthesiser",
                    basis="the sketch is the audit's positive deliverable, not only a delete list",
                    tools=["Read", "Write(command-center/audit/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/audit/arc03-minimal-rebuild.json",
                    output_schema=schema("architecture-dossier"),
                    evidence="every element of the sketch maps to a surviving component purpose, so the sketch cannot smuggle in new scope",
                    tests=["a sketch element with no surviving-purpose mapping must be flagged as new scope, not as simplification"],
                    reviewer="the removal critic reads the sketch for silently dropped purposes",
                    retry="one retry then emit partial",
                    failure_classes=["scope-creep", "digest-loss"],
                    owner_approval=False,
                    sentinel_extra="every sketch element maps to a surviving component purpose",
                ),
            },
        ],
        "stopping_rules": [
            {
                "id": "all-components-judged",
                "expression": "components_unjudged == 0",
                "applies_to": "workflow",
                "minimum_conditions": "both_states_probes_run >= 1",
                "on_stop": "complete",
            },
            {
                "id": "telemetry-absent",
                "expression": "telemetry_available == false",
                "applies_to": "workflow",
                "minimum_conditions": "components_inventoried >= 1",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": two_strikes(3, "owner", ["detector-failure", "severed-stream"]),
        "failure_policy": failure_policy(
            "quarantine",
            ["detector-failure", "detector-truncation", "overclaim"],
            "owner",
            "command-center/quarantine/arc03",
        ),
        "resume": resume(
            "command-center/checkpoints/arc03",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key"],
        ),
        "replay": replay(
            20260810,
            "command-center/replay/arc03.jsonl",
            ["params", "inputs", "tool_calls", "tool_results"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/arc03",
            ["workflow_version", "stage_id", "item_key", "inputs_hash"],
            43200,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/arc03-plan.json",
            ["Bash:python", "Write(command-center/audit/**)"],
            ["plan", "estimate", "permission-report", "graph"],
        ),
        "estimate": estimate_static(
            wallclock=(900, 5400, 21600),
            tokens=(150000, 800000, 2500000),
            tool_calls=(60, 500),
            risk="medium",
            reversibility="reversible",
            blast_radius="the AUDIT is read-only and writes only under command-center/audit/**; its RECOMMENDATIONS are what carry risk, which is why each one needs a traced blast radius before it is actionable",
        ),
        "portability": portability("command-center/export/bp-arc-03.bundle.json"),
        "lineage": lineage(
            [
                ("skills/agent-architecture-audit", "DISTILL"),
                ("skills/agent-harness-construction", "DISTILL"),
                ("skills/agent-introspection-debugging", "DISTILL"),
                ("rules/common/single-signal-verification.md", "REBUILD-FROM-SPEC"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-03", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "components": artifact(
                "command-center/audit/arc03-component.json",
                schema("detector-control"),
                min_bytes=256,
                consumers=["the synthesiser", "the removal critic"],
            ),
            "blast_radius": artifact(
                "command-center/audit/arc03-blast-radius.json",
                schema("blast-radius"),
                min_bytes=256,
                consumers=["the removal critic", "the owner"],
            ),
            "minimal_rebuild": artifact(
                "command-center/audit/arc03-minimal-rebuild.json",
                schema("architecture-dossier"),
                min_bytes=512,
                consumers=["the owner", "bp-arc-01.architecture-tournament"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-03 (doc-order 30 of 96)",
            "owner_decision": (
                "OPEN: does an architecture audit get authority to PROPOSE removing a "
                "security-bearing component, or is that category permanently out of scope? The "
                "param allow_security_removal defaults to false, so the safe answer is the "
                "default until the owner rules."
            ),
            "distinguishing_mechanism": (
                "the DISARMED-versus-UNUSED both-states discrimination plus a mandatory "
                "blast-radius trace per removal. BP-ARC-04 maps FUTURE options against a failure "
                "catalogue; this audits EXISTING components for accretion."
            ),
            "not_a_duplicate_of_bp_dbg_05": (
                "BP-DBG-05 (Silent-Disarm Hunt, doc-order 47, another unit's range) HUNTS for "
                "disarmed guards as its whole purpose. This blueprint CONSUMES that distinction "
                "as one input to a subtraction decision. The both-states probe is deliberately "
                "referenced as a per-component sub-step here rather than reimplemented as a "
                "second hunt, so the two do not manufacture overlapping coverage."
            ),
            "worked_example": {
                "name": "a disarmed guard must not be classified as unused",
                "narrative": (
                    "Four components. 'stale-guard' is registered, has not fired recently, and "
                    "does NOT fire on a known-broken input: DISARMED, which is a defect to fix, "
                    "not a component to delete. 'quiet-guard' is registered, has not fired "
                    "recently, but DOES fire on a known-broken input: live-dormant, and it must "
                    "survive. 'no-telemetry' never had a both-states probe run, so it is UNKNOWN. "
                    "Only the unregistered handler is even eligible for removal, and only with a "
                    "traced blast radius and no security bearing."
                ),
                "mechanism": "mechanisms.classify_component + mechanisms.removable",
                "input": {
                    "components": {
                        "stale-guard": {"registered": True, "fired_recently": False, "fires_on_known_bad_state": False},
                        "quiet-guard": {"registered": True, "fired_recently": False, "fires_on_known_bad_state": True},
                        "no-telemetry": {"registered": True, "fired_recently": False, "fires_on_known_bad_state": None},
                        "orphan-handler": {"registered": False, "fired_recently": False, "fires_on_known_bad_state": None},
                    },
                    "removal_context": {"blast_radius_traced": True, "security_bearing": False},
                },
                "expected": {
                    "classes": {
                        "stale-guard": "disarmed",
                        "quiet-guard": "live-dormant",
                        "no-telemetry": "unknown-no-both-states-probe",
                        "orphan-handler": "unregistered",
                    },
                    "removable": ["orphan-handler"],
                },
                "controls": [
                    {
                        "mutate": "mark orphan-handler security_bearing=true",
                        "expected_removable": 0,
                        "why": "a security-bearing removal is owner-only and can never be auto-approved",
                    },
                    {
                        "mutate": "drop the blast-radius trace",
                        "expected_removable": 0,
                        "why": "an untraced removal is not a proposal",
                    },
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- ARC-04


def bp_arc_04() -> dict[str, Any]:
    """Failure-domain mapping: walk TEN measured classes per option; a probe-less domain is unmonitored."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-arc-04.failure-domain-mapping-workshop",
        "name": "Failure-Domain Mapping Workshop",
        "description": (
            "Force every architectural option to declare its failure domains before it is chosen, "
            "by walking a catalogue of ten failure classes this estate has actually exhibited. Per "
            "applicable class the option must state the symptom, WHO NOTICES, the blast radius and "
            "a detection probe. If the answer to 'who notices' is nobody, or the domain has no "
            "probe, the option carries an unmonitored failure domain and must say so. Options are "
            "then compared on domains, not on features. An option with zero domains is a red flag, "
            "not a green light."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["security-governance-and-risk"],
        "tags": ["failure-domains", "fail-open", "who-notices", "design-time"],
        "flagship": True,
        "params": {
            "options": {
                "type": "array",
                "required": True,
                "items": {"type": "string"},
                "min_items": 1,
                "description": "The architectural options to map; one mapper runs per option",
            },
            "failure_class_catalogue_path": {
                "type": "path",
                "required": True,
                "description": "The maintained catalogue of measured failure classes; catalogue completeness bounds this blueprint",
            },
            "require_probe_per_domain": {
                "type": "boolean",
                "default": True,
                "description": "When true, an applicable domain with no detection probe cannot be called handled",
            },
        },
        "roles": {
            "mapper": {
                "description": "Walks the whole catalogue against exactly one option and declares each domain",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "min_participants": 1,
                "max_participants": 16,
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "comparator": {
                "description": "Builds the cross-option table on DOMAINS, refusing to rank on features",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "judge",
                "independence": "informed",
                "tool_permissions": ["Read", "Bash:python", "Write(command-center/failure-domains/**)"],
                "write_paths": ["command-center/failure-domains/**"],
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/failure-domains/**)"],
            network="none",
            write_paths=["command-center/failure-domains/**"],
        ),
        "model_routing": opus_routing(),
        "gates": {
            "catalogue-fully-walked": expr_gate(
                "classes_walked == classes_in_catalogue", "fail"
            ),
            "unmonitored-declared": expr_gate(
                "unmonitored_domains_undisclosed == 0", "fail"
            ),
            "zero-domains-is-a-red-flag": expr_gate(
                "domains_applicable >= 1 OR option_declared_under_specified == true", "fail"
            ),
        },
        "stages": [
            {
                "id": "s0-walk",
                "title": "S0-S3 WALK the catalogue per option and name a probe per domain",
                "kind": "fanout",
                "over": {
                    "source": "param",
                    "ref": "options",
                    "item_var": "option",
                    "key_field": "option",
                },
                "max_concurrency": 6,
                "arrival_stagger_ms": 250,
                "max_items": 16,
                "on_item_failure": "abort",
                "body": [
                    {
                        "id": "map-one-option",
                        "kind": "task",
                        "role": "mapper",
                        "timeout_seconds": 1800,
                        "work_unit": wu(
                            uid="BP3-ARC04-S0",
                            title="Map one option against every class in the failure catalogue",
                            phase="2B",
                            target="For each of the ten measured failure classes, decide whether it applies to this option, and if so state symptom, who notices, blast radius and a detection probe.",
                            inputs=["params.options", "params.failure_class_catalogue_path"],
                            dependencies=[],
                            model="opus",
                            vendor="anthropic",
                            role="mapper",
                            basis="one mapper per option so the comparison table is built from independent walks",
                            tools=["Read", "Grep", "Glob"],
                            substrate="local-parallel",
                            timeout=1800,
                            output_path="command-center/failure-domains/arc04-domains.json",
                            output_schema=schema("failure-taxonomy"),
                            evidence="every applicable domain names a concrete detection probe, or is explicitly marked unmonitored with who_notices=nobody",
                            tests=[
                                "an option carrying a try/except ImportError guard MUST flag fail-open-on-missing-dependency",
                                "an option whose who_notices is 'the agent' for a fail-open class must be rejected, since the agent is exactly what does not notice",
                                "an option mapping to zero domains must be flagged under-specified, never accepted as safe",
                            ],
                            reviewer="the comparator, which cross-checks that all ten classes were walked",
                            retry="two strikes then pivot to a re-framed option description",
                            failure_classes=["fail-open-on-missing-dependency", "detector-truncation", "spec-underspecified"],
                            owner_approval=False,
                            sentinel_extra="all ten catalogue classes appear in the artifact with an explicit applies true or false",
                        ),
                    }
                ],
                "barrier": {
                    "mode": "all",
                    "on_partial": "fail",
                    "reject_result_matching": ["started in the background"],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s0-gate",
                "title": "S0 gate: the whole catalogue was walked, not a subset",
                "kind": "gate",
                "depends_on": ["s0-walk"],
                "gate_ref": "catalogue-fully-walked",
            },
            {
                "id": "s3b-probe-inventory",
                "title": "S3b MARK which probes exist today and which must be built",
                "kind": "task",
                "role": "comparator",
                "depends_on": ["s0-gate"],
                "timeout_seconds": 1200,
                "work_unit": wu(
                    uid="BP3-ARC04-S3B",
                    title="Split declared probes into exists-today and must-be-built",
                    phase="2B",
                    target="For every named detection probe, establish whether it exists and runs today, or is a probe that would have to be built.",
                    inputs=["command-center/failure-domains/arc04-domains.json"],
                    dependencies=["BP3-ARC04-S0"],
                    model="opus",
                    vendor="anthropic",
                    role="comparator",
                    basis="a domain whose probe does not exist yet is an unmonitored domain today",
                    tools=["Read", "Grep", "Bash:python"],
                    substrate="local-single",
                    timeout=1200,
                    output_path="command-center/failure-domains/arc04-probe-inventory.json",
                    output_schema=schema("threat-coverage-matrix"),
                    evidence="each exists-today claim cites the file and the command that runs the probe",
                    tests=[
                        "a probe claimed to exist must be shown to FIRE on a known-broken state before the claim is accepted",
                        "a probe that cannot be located must be classified must-be-built, never assumed present",
                    ],
                    reviewer="the mapper of the affected option confirms the classification",
                    retry="two strikes then pivot to declaring the probe must-be-built",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every exists-today probe cites a file and a command, and was shown to fire on a known-broken state",
                ),
                "produces": [
                    artifact(
                        "command-center/failure-domains/arc04-probe-inventory.json",
                        schema("threat-coverage-matrix"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-ARC04-S3B",
                        consumers=["s4-compare"],
                    )
                ],
            },
            {
                "id": "s3-unmonitored-gate",
                "title": "S3 gate: every unmonitored domain is disclosed, not quietly omitted",
                "kind": "gate",
                "depends_on": ["s3b-probe-inventory"],
                "gate_ref": "unmonitored-declared",
            },
            {
                "id": "s4-compare",
                "title": "S4 COMPARE options on DOMAINS, not on features",
                "kind": "task",
                "role": "comparator",
                "depends_on": ["s3-unmonitored-gate"],
                "timeout_seconds": 1200,
                "work_unit": wu(
                    uid="BP3-ARC04-S4",
                    title="Build the cross-option comparison table keyed on failure domains",
                    phase="2B",
                    target="Rank the options by unmonitored-domain count and blast radius, explicitly refusing to rank on feature count.",
                    inputs=[
                        "command-center/failure-domains/arc04-domains.json",
                        "command-center/failure-domains/arc04-probe-inventory.json",
                    ],
                    dependencies=["BP3-ARC04-S3B"],
                    model="opus",
                    vendor="anthropic",
                    role="comparator",
                    basis="the comparison is arithmetic over declared domains; only the tie-break is judgement",
                    tools=["Read", "Bash:python", "Write(command-center/failure-domains/**)"],
                    substrate="local-single",
                    timeout=1200,
                    output_path="command-center/failure-domains/arc04-comparison.json",
                    output_schema=schema("compatibility-matrix"),
                    evidence="the table shows, per option, each applicable class and whether it is monitored today",
                    tests=["an option with the most features but the most unmonitored domains must not rank first"],
                    reviewer="the owner, who chooses among mapped options",
                    retry="one retry then emit partial",
                    failure_classes=["overclaim"],
                    owner_approval=False,
                    sentinel_extra="every option column lists all ten classes with a monitored-today flag",
                ),
            },
            {
                "id": "s4-gate",
                "title": "S4 gate: an option with zero domains is under-specified, not safe",
                "kind": "gate",
                "depends_on": ["s4-compare"],
                "gate_ref": "zero-domains-is-a-red-flag",
            },
        ],
        "stopping_rules": [
            {
                "id": "catalogue-walked",
                "expression": "classes_walked == classes_in_catalogue AND unmonitored_domains_undisclosed == 0",
                "applies_to": "workflow",
                "minimum_conditions": "options_mapped >= 1",
                "on_stop": "complete",
            },
            {
                "id": "option-not-enumerable",
                "expression": "failure_modes_enumerable == false",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": two_strikes(3, "comparator", ["detector-failure", "spec-underspecified"]),
        "failure_policy": failure_policy(
            "fail-fast",
            ["spec-underspecified", "detector-failure", "fail-open-on-missing-dependency"],
            "comparator",
            "command-center/quarantine/arc04",
        ),
        "resume": resume(
            "command-center/checkpoints/arc04",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key"],
        ),
        # The catalogue walk is deterministic in structure: the same option traits and the same
        # catalogue produce the same applies/does-not-apply set, so a hash comparison is meaningful.
        "replay": replay(
            20260810,
            "command-center/replay/arc04.jsonl",
            ["params", "inputs", "model_outputs"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/arc04",
            ["workflow_version", "stage_id", "item_key", "inputs_hash"],
            604800,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/arc04-plan.json",
            ["Bash:python", "Write(command-center/failure-domains/**)"],
            ["plan", "graph"],
        ),
        "estimate": estimate_static(
            wallclock=(300, 1800, 7200),
            tokens=(40000, 200000, 600000),
            tool_calls=(20, 150),
            risk="low",
            reversibility="reversible",
            blast_radius="read-only over the options; writes only under command-center/failure-domains/**",
        ),
        "portability": portability("command-center/export/bp-arc-04.bundle.json"),
        "lineage": lineage(
            [
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#the-ten-failure-classes", "REBUILD-FROM-SPEC"),
                ("tools/detector-self-test", "COMPOSE"),
                ("skills/agent-architecture-audit", "COMPOSE"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-04", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "domains": artifact(
                "command-center/failure-domains/arc04-domains.json",
                schema("failure-taxonomy"),
                min_bytes=512,
                consumers=["the comparator", "bp-arc-01.architecture-tournament"],
            ),
            "comparison": artifact(
                "command-center/failure-domains/arc04-comparison.json",
                schema("compatibility-matrix"),
                min_bytes=256,
                consumers=["the owner"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-04 (doc-order 31 of 96)",
            "distinguishing_mechanism": (
                "a fixed, MEASURED ten-class catalogue is walked against each option, and the "
                "load-bearing output is 'who notices' plus a named probe per domain. "
                "BP-ARC-03 audits what already exists; this maps options before one is chosen."
            ),
            "honest_bound": (
                "catalogue completeness bounds this blueprint: it can only surface classes the "
                "catalogue contains. It maps; it does not prove. Proving a domain is handled is "
                "the testing family's job, not this one's."
            ),
            "worked_example": {
                "name": "a try/except ImportError guard must flag fail-open",
                "narrative": (
                    "An option is described by two traits: it guards an optional dependency with "
                    "try/except ImportError, and it pins a ref. Both corresponding classes must "
                    "come back applicable. A detection probe is supplied for the pinned ref but "
                    "NOT for the fail-open guard, so fail-open-on-missing-dependency comes back "
                    "unmonitored - and that is precisely the class that produced nine of nine "
                    "disarmed checks at one measurement."
                ),
                "mechanism": "mechanisms.failure_domain_walk + mechanisms.unmonitored_domains",
                "input": {
                    "option_traits": ["try-except-importerror", "pins-a-ref"],
                    "probes": {"stale-pinned-ref": "re-resolve the ref and compare to the pin on every run"},
                },
                "expected": {
                    "applicable": ["fail-open-on-missing-dependency", "stale-pinned-ref"],
                    "unmonitored": ["fail-open-on-missing-dependency"],
                    "classes_walked": 10,
                },
                "controls": [
                    {
                        "mutate": "add a probe for fail-open-on-missing-dependency",
                        "expected_unmonitored": 0,
                        "why": "the probe is what converts a declared domain into a monitored one",
                    },
                    {
                        "mutate": "empty the option traits",
                        "expected_applicable": 0,
                        "why": "zero applicable domains must be reachable, or the walk is rubber-stamping",
                    },
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- ARC-05


def bp_arc_05() -> dict[str, Any]:
    """Vendor-neutral spec emission: round-trip topology equality, and the two live conflicts surfaced."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-arc-05.vendor-neutral-workflow-spec-emission",
        "name": "Vendor-Neutral Workflow Spec Emission",
        "description": (
            "Emit a workflow as a declarative, provider-mapped spec rather than as script bound to "
            "one runtime, so a blueprint can run on more than one vendor. The gate that makes this "
            "more than a translation exercise is a ROUND-TRIP: the emitted spec must reproduce the "
            "source's stage topology exactly, and a mismatch REJECTS the spec rather than patching "
            "it to look right. A stage with no mapping for a vendor is declared UNSUPPORTED for "
            "that vendor, never silently dropped."
        ),
        "version": "1.0.0",
        "kind": "meta-workflow",
        "categories": ["collective-intelligence-and-meta", "engineering-and-reliability"],
        "tags": ["vendor-neutral", "round-trip", "portability", "spec-emission"],
        "flagship": True,
        "params": {
            "source_workflow_path": {
                "type": "path",
                "required": True,
                "description": "The workflow to promote into a portable spec",
            },
            "provider_matrix": {
                "type": "object",
                "required": True,
                "description": "stage id -> vendor -> invocation. A missing cell means UNSUPPORTED, not 'the default'.",
                "schema": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "additionalProperties": {"type": "string", "minLength": 1},
                    },
                },
            },
            "max_depth": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 1,
                "description": "The machine-readable form of the one-level-nesting rule. Fixed at 1 by design.",
            },
            "max_threads": {
                "type": "integer",
                "required": True,
                "minimum": 1,
                "maximum": 128,
                "description": (
                    "REQUIRED WITH NO DEFAULT ON PURPOSE. The spec layer carries a live conflict: "
                    "lifecycle.yaml says max_threads=4 while the owner's standing preference is to "
                    "fan out large. Rather than silently inherit either value this blueprint "
                    "refuses to run until the owner states one."
                ),
            },
            "worker_model_floor": {
                "type": "enum",
                "required": True,
                "enum": ["sonnet", "opus"],
                "description": (
                    "The second live conflict, also deliberately undefaulted: agent-roles/core.yaml "
                    "routes worker=sonnet while the standing preference is Opus for all "
                    "substantive subagents. The owner picks; the spec records the pick."
                ),
            },
        },
        "roles": {
            "translator": {
                "description": "Extracts the stage sequence, invariants and limits, and maps each stage per vendor",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Bash:python", "Write(command-center/spec/**)"],
                "write_paths": ["command-center/spec/**"],
            },
            "portability_critic": {
                "description": "Lists what is genuinely vendor-locked instead of pretending it is portable",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "cross-examining",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "always",
            },
            "roundtrip_validator": {
                "description": "Mechanically compares the emitted topology to the source topology",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "judge",
                "independence": "independent",
                "tool_permissions": ["Read", "Bash:python"],
            },
            "owner": {
                "description": "Resolves the two recorded spec-layer conflicts; the spec cannot invent an answer",
                "vendor": "human",
                "authority": "owner",
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/spec/**)"],
            network="none",
            write_paths=["command-center/spec/**"],
            forbid_write_paths=["platform/workflows/**"],
        ),
        "model_routing": opus_routing(
            strategy="vendor-diverse",
            routes=[
                {
                    "when": "stage_role == portability_critic",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "a portability critic from the locked-in vendor cannot see the lock-in",
                }
            ],
        ),
        "gates": {
            "handoff-fields-exact": expr_gate(
                "handoff_required_fields_match == true AND max_depth == 1", "fail"
            ),
            "unsupported-declared": expr_gate(
                "silently_dropped_stages == 0", "fail"
            ),
            "roundtrip-equal": expr_gate("roundtrip_topology_equal == true", "fail"),
            "conflicts-resolved": expr_gate(
                "max_threads_declared == true AND worker_model_floor_declared == true", "fail"
            ),
        },
        "stages": [
            {
                "id": "s0-extract",
                "title": "S0 EXTRACT the stage sequence and invariants from the source workflow",
                "kind": "task",
                "role": "translator",
                "timeout_seconds": 1800,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-ARC05-S0",
                    title="Extract topology and invariants from the source workflow",
                    phase="2B",
                    target="Produce the stage sequence, the dependency edges and the declared invariants of the source workflow, in document order.",
                    inputs=["params.source_workflow_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="translator",
                    basis="extraction fidelity is what the round-trip later measures",
                    tools=["Read", "Grep", "Bash:python"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/spec/arc05-topology.json",
                    output_schema=schema("contract-spec"),
                    evidence="the extracted topology is emitted as an ordered list of stage id, kind and dependency edges, so equality is decidable",
                    tests=["a workflow with a nested stage body must appear in the extracted topology, not be flattened away"],
                    reviewer="the round-trip validator, mechanically",
                    retry="two strikes then pivot to an AST-level extraction",
                    failure_classes=["digest-loss", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="the topology list is ordered and includes every nested stage",
                ),
                "produces": [
                    artifact(
                        "command-center/spec/arc05-topology.json",
                        schema("contract-spec"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-ARC05-S0",
                        consumers=["s1-map", "s4-roundtrip"],
                    )
                ],
            },
            {
                "id": "s1-map",
                "title": "S1 MAP each stage to a provider invocation per vendor",
                "kind": "task",
                "role": "translator",
                "depends_on": ["s0-extract"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC05-S1",
                    title="Map every stage to a per-vendor invocation, declaring UNSUPPORTED where there is none",
                    phase="2B",
                    target="For each stage and each vendor, record the invocation, or record UNSUPPORTED explicitly rather than omitting the cell.",
                    inputs=["command-center/spec/arc05-topology.json", "params.provider_matrix"],
                    dependencies=["BP3-ARC05-S0"],
                    model="opus",
                    vendor="anthropic",
                    role="translator",
                    basis="an omitted cell reads as a default and is how portability is faked",
                    tools=["Read", "Bash:python", "Write(command-center/spec/**)"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/spec/arc05-provider-map.json",
                    output_schema=schema("parity-matrix"),
                    evidence="every (stage, vendor) cell is present and is either an invocation or the literal UNSUPPORTED",
                    tests=["a stage with no mapping for a vendor must yield UNSUPPORTED, never an absent cell"],
                    reviewer="the portability critic",
                    retry="two strikes then pivot to declaring the vendor unsupported wholesale",
                    failure_classes=["digest-loss", "overclaim"],
                    owner_approval=False,
                    sentinel_extra="the matrix is dense: every stage x vendor cell exists",
                ),
            },
            {
                "id": "s1-gate",
                "title": "S1 gate: no stage is silently dropped for a vendor",
                "kind": "gate",
                "depends_on": ["s1-map"],
                "gate_ref": "unsupported-declared",
            },
            {
                "id": "s2-limits",
                "title": "S2 DECLARE limits and the typed handoff",
                "kind": "task",
                "role": "translator",
                "depends_on": ["s1-gate"],
                "timeout_seconds": 1200,
                "work_unit": wu(
                    uid="BP3-ARC05-S2",
                    title="Declare limits and the typed handoff contract exactly",
                    phase="2B",
                    target="Write the limits block and the handoff contract, carrying the required handoff fields exactly and pinning max_depth at 1.",
                    inputs=["params.max_threads", "params.worker_model_floor", "params.max_depth"],
                    dependencies=["BP3-ARC05-S1"],
                    model="opus",
                    vendor="anthropic",
                    role="translator",
                    basis="the limits block is the machine-readable form of the nesting and handoff rules",
                    tools=["Read", "Write(command-center/spec/**)"],
                    substrate="local-single",
                    timeout=1200,
                    output_path="command-center/spec/arc05-limits.json",
                    output_schema=schema("handoff"),
                    evidence="the handoff field set is compared element-by-element against the contract, not summarised as compatible",
                    tests=[
                        "a handoff missing one required field must FAIL rather than be reported compatible",
                        "max_depth other than 1 must FAIL - one-level nesting is not negotiable",
                    ],
                    reviewer="the portability critic",
                    retry="one retry then escalate to the owner",
                    failure_classes=["spec-underspecified"],
                    owner_approval=False,
                    sentinel_extra="the handoff field set matches exactly and max_depth equals 1",
                ),
            },
            {
                "id": "s2-gate",
                "title": "S2 gate: handoff fields exact, nesting depth pinned",
                "kind": "gate",
                "depends_on": ["s2-limits"],
                "gate_ref": "handoff-fields-exact",
            },
            {
                "id": "s3-critique",
                "title": "S3 CRITIQUE portability - list what is vendor-locked",
                "kind": "task",
                "role": "portability_critic",
                "depends_on": ["s2-gate"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-ARC05-S3",
                    title="Name every feature that is genuinely vendor-locked",
                    phase="2B",
                    target="Identify each runtime feature with no cross-vendor equivalent and list it as vendor-locked rather than mapping it optimistically.",
                    inputs=["command-center/spec/arc05-provider-map.json"],
                    dependencies=["BP3-ARC05-S2"],
                    model="gpt-5-codex",
                    vendor="openai",
                    role="portability_critic",
                    basis="cross-vendor, because the locked-in vendor cannot see its own lock-in",
                    tools=["Read", "Grep"],
                    substrate="codex-mcp",
                    timeout=1800,
                    output_path="command-center/spec/arc05-portability.json",
                    output_schema=schema("vendor-capability"),
                    evidence="each vendor-locked entry names the feature and the vendor that lacks an equivalent",
                    tests=["a Claude-only runtime feature must appear in vendor_locked_features, never be silently mapped"],
                    reviewer="the translator may contest an entry but may not delete it",
                    retry="two strikes then pivot",
                    failure_classes=["overclaim", "digest-loss"],
                    owner_approval=False,
                    sentinel_extra="every vendor-locked feature names both the feature and the lacking vendor",
                ),
            },
            {
                "id": "s4-roundtrip",
                "title": "S4 ROUND-TRIP validate: the spec must reproduce the source topology",
                "kind": "task",
                "role": "roundtrip_validator",
                "depends_on": ["s3-critique"],
                "timeout_seconds": 900,
                "work_unit": wu(
                    uid="BP3-ARC05-S4",
                    title="Compare emitted topology to source topology, element by element",
                    phase="2B",
                    target="Assert that the emitted spec's ordered stage topology equals the source's, and emit the first differing element when it does not.",
                    inputs=["command-center/spec/arc05-topology.json", "command-center/spec/arc05-provider-map.json"],
                    dependencies=["BP3-ARC05-S3"],
                    model="opus",
                    vendor="anthropic",
                    role="roundtrip_validator",
                    basis="topology equality is an exact comparison and must be computed, not judged",
                    tools=["Read", "Bash:python"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/spec/arc05-roundtrip.json",
                    output_schema=schema("determinism-report"),
                    evidence="records both topologies and the first differing element, so a pass is falsifiable",
                    tests=[
                        "dropping one stage from the emitted spec must make the round-trip FAIL",
                        "reordering two dependency edges must make the round-trip FAIL",
                    ],
                    reviewer="none - this is an exact comparison, not an opinion",
                    retry="none; a mismatch rejects the spec rather than retrying the comparison",
                    failure_classes=["digest-loss", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="both topologies are recorded and either equal, or the first difference is named",
                ),
                "produces": [
                    artifact(
                        "command-center/spec/arc05-roundtrip.json",
                        schema("determinism-report"),
                        min_bytes=192,
                        sentinel="SUCCESS:BP3-ARC05-S4",
                        consumers=["s4-gate", "the owner"],
                    )
                ],
            },
            {
                "id": "s4-gate",
                "title": "S4 gate: a round-trip mismatch REJECTS the spec",
                "kind": "gate",
                "depends_on": ["s4-roundtrip"],
                "gate_ref": "roundtrip-equal",
            },
            {
                "id": "s5-owner-conflicts",
                "title": "S5 OWNER resolves the two recorded spec-layer conflicts",
                "kind": "human_checkpoint",
                "depends_on": ["s4-gate"],
                "prompt": "Two spec-layer conflicts must be resolved before this spec is authoritative: lifecycle max_threads=4 versus the standing fan-out-large preference, and roles.worker=sonnet versus the Opus-for-substantive-subagents preference. State which wins for each.",
                "approvers": ["owner"],
                "approval_mode": "owner-only",
                "timeout_seconds": 86400,
                "on_timeout": "fail",
                "owner_approval_required": True,
                "options": ["keep-lifecycle-values", "keep-standing-preferences", "set-explicit-values"],
                "decision_artifact": artifact(
                    "command-center/spec/arc05-owner-decision.json",
                    schema("owner-decision-packet"),
                    min_bytes=128,
                    consumers=["the emitted spec"],
                ),
            },
            {
                "id": "s5-gate",
                "title": "S5 gate: both conflicting values are explicitly declared",
                "kind": "gate",
                "depends_on": ["s5-owner-conflicts"],
                "gate_ref": "conflicts-resolved",
            },
        ],
        "stopping_rules": [
            {
                "id": "roundtrip-validates",
                "expression": "roundtrip_topology_equal == true AND silently_dropped_stages == 0",
                "applies_to": "workflow",
                "minimum_conditions": "stages_extracted >= 1",
                "on_stop": "complete",
            },
            {
                "id": "no-cross-vendor-equivalent",
                "expression": "vendor_locked_features >= 1 AND declared_vendor_locked == true",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": two_strikes(3, "owner", ["digest-loss", "severed-stream"]),
        "failure_policy": failure_policy(
            "fail-fast",
            ["digest-loss", "spec-underspecified", "detector-failure"],
            "owner",
            "command-center/quarantine/arc05",
        ),
        "resume": resume(
            "command-center/checkpoints/arc05",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        # The spec IS the determinism surface, so replay compares hashes: an emitted spec that
        # differs byte-for-byte from a previous emission of the same source is a divergence.
        "replay": replay(
            20260810,
            "command-center/replay/arc05.jsonl",
            ["params", "inputs", "tool_calls", "tool_results", "env_fingerprint"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/arc05",
            ["workflow_version", "stage_id", "inputs_hash", "tool_versions"],
            604800,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/arc05-plan.json",
            ["Bash:python", "Write(command-center/spec/**)"],
            ["plan", "estimate", "graph", "artifact-diff"],
        ),
        "estimate": estimate_static(
            wallclock=(600, 3600, 14400),
            tokens=(60000, 350000, 1000000),
            tool_calls=(30, 250),
            risk="low",
            reversibility="reversible",
            blast_radius="writes only under command-center/spec/**; explicitly forbidden from writing platform/workflows/**, so it cannot overwrite the source it is translating",
        ),
        "portability": portability(
            "command-center/export/bp-arc-05.bundle.json",
            includes=["definition", "presets", "examples", "tests", "lineage"],
        ),
        "lineage": lineage(
            [
                ("~/.agents/workflows/grill.yaml", "EXTEND"),
                ("~/.agents/workflows/lifecycle.yaml", "MERGE"),
                ("agent-roles/core.yaml", "MERGE"),
                ("tools/agentspec", "COMPOSE"),
                ("tools/agentrail", "COMPOSE"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-05", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "spec": artifact(
                "command-center/spec/arc05-provider-map.json",
                schema("parity-matrix"),
                min_bytes=512,
                consumers=["the dispatch rail", "the owner"],
            ),
            "portability_report": artifact(
                "command-center/spec/arc05-portability.json",
                schema("vendor-capability"),
                min_bytes=192,
                consumers=["the owner"],
            ),
            "roundtrip": artifact(
                "command-center/spec/arc05-roundtrip.json",
                schema("determinism-report"),
                min_bytes=192,
                consumers=["the round-trip gate"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-ARC-05 (doc-order 32 of 96)",
            "owner_decision": (
                "OPEN, and mechanised rather than assumed: max_threads and worker_model_floor are "
                "REQUIRED params with NO default, so this blueprint cannot run until the owner "
                "states which side of each live conflict wins. A default here would silently pick "
                "a winner."
            ),
            "distinguishing_mechanism": (
                "topology round-trip equality as a REJECT gate, plus explicit UNSUPPORTED cells. "
                "BP-XVD-04 is the runtime multi-rail dispatch; this is the spec format and the "
                "translation discipline that feeds it."
            ),
            "anti_overfit_anchor": (
                "this is declarative config over existing tools and explicitly NOT a second "
                "orchestration runtime - the dispatch shell invokes existing vendor CLIs."
            ),
            "worked_example": {
                "name": "a dropped stage must fail the round-trip",
                "narrative": (
                    "A three-stage source workflow with one nested body stage is extracted, "
                    "emitted, and compared. Identical topology passes. Dropping the nested stage "
                    "from the emitted spec must FAIL - that is the whole point of the gate, since "
                    "a flattening translator otherwise looks successful. A stage with no provider "
                    "cell must appear in vendor_locked_features rather than vanish."
                ),
                "mechanism": "mechanisms.roundtrip_equal + mechanisms.vendor_locked",
                "input": {
                    "source_stages": [
                        {"id": "a", "kind": "task", "depends_on": []},
                        {
                            "id": "b",
                            "kind": "fanout",
                            "depends_on": ["a"],
                            "body": [{"id": "b-inner", "kind": "task", "depends_on": []}],
                        },
                        {"id": "c", "kind": "gate", "depends_on": ["b"]},
                    ],
                    "provider_map": {"a": {"anthropic": "task"}, "b": {"anthropic": "fanout"}, "c": {}},
                },
                "expected": {
                    "identical_roundtrip": True,
                    "topology_length": 4,
                    "vendor_locked": ["c"],
                },
                "controls": [
                    {
                        "mutate": "drop stage b-inner from the emitted copy",
                        "expected_roundtrip": False,
                        "why": "a flattened nested stage is exactly the silent loss this gate exists to catch",
                    }
                ],
            },
        },
    }


BLUEPRINTS = [bp_arc_02, bp_arc_03, bp_arc_04, bp_arc_05]
