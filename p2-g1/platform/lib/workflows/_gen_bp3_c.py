"""bp-3 blueprints 9-12 (BP-PLN-01..04) plus the two SHARED subworkflows they factor out.

Design source: 09-WORKFLOW-BLUEPRINT-LIBRARY.md lines 1626-1802 (doc-order 33-36 of 96).

Why the two shared subworkflows exist
-------------------------------------
The distinctness self-check found that BP-PLN-02 and BP-PLN-03 both compute a pairwise
file-overlap matrix. They are NOT near-duplicates - PLN-02 decides CONCURRENCY ADMISSION over
PREDICTED file sets, PLN-03 decides MERGE ORDER over MEASURED git refs, and merging them would
conflate two different decisions - but shipping the same primitive twice would be exactly the
copy-and-rename the spec forbids. So the primitive is factored into ONE subworkflow that both
reference. The same reasoning applies to write-as-you-go, which BP-PLN-04 needs and which is a
prerequisite of any long-running unit. These two are SUBWORKFLOWS, not blueprints, and are
deliberately NOT counted toward the twelve.
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

OVERLAP_SUB = "shared.pairwise-overlap-matrix"
WAYG_SUB = "shared.write-as-you-go-artifact"


# ================================================================== SHARED SUBWORKFLOW 1


def sub_pairwise_overlap() -> dict[str, Any]:
    """The shared exact primitive: pairwise set intersection + connected components.

    Referenced by BP-PLN-02 (concurrency admission) and BP-PLN-03 (merge ordering). It answers
    only the arithmetic question; both callers keep their own, different decision rule.
    """
    return {
        "dsl_version": "1.0.0",
        "id": OVERLAP_SUB,
        "name": "Pairwise Overlap Matrix (shared primitive)",
        "description": (
            "Compute the pairwise intersection of N named path sets and the connected components "
            "of the resulting graph. Exact arithmetic, no judgement: fan-out-contract C4 measured "
            "that handing this class of question to LLM judgement scores 86% with 100% of the "
            "errors pointing at data loss. An UNKNOWN path set is treated as overlapping "
            "everything (adverse inference), so a caller can never optimistically parallelise a "
            "unit whose footprint it could not determine."
        ),
        "version": "1.0.0",
        "kind": "subworkflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["deterministic", "shared-primitive", "adverse-inference"],
        "flagship": False,
        "params": {
            "path_sets": {
                "type": "object",
                "required": True,
                "description": "name -> array of repo-relative paths, or null for UNKNOWN",
                "schema": {
                    "type": "object",
                    "minProperties": 1,
                    "additionalProperties": {
                        "oneOf": [
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "null"},
                        ]
                    },
                },
            }
        },
        "roles": {
            "computer": {
                "description": "Runs the exact algorithm; this role holds no discretion at all",
                "model": "none-deterministic-script",
                "vendor": "any",
                "effort": "low",
                "authority": "judge",
                "independence": "independent",
                "tool_permissions": ["Read", "Bash:python"],
            }
        },
        "tool_policy": deny_policy(
            ["Read", "Bash:python", "Write(command-center/overlap/**)"],
            network="none",
            write_paths=["command-center/overlap/**"],
        ),
        # NO model_routing block on purpose: this subworkflow contains no model stage at all.
        # The DSL's model_target vendor enum has no non-model member (role_spec.vendor accepts
        # "any", model_target.vendor does not), so a deterministic stage is expressed as a ROLE
        # with vendor="any" and NO route - inventing a vendor for a script would be a lie in the
        # one field a router reads.
        "gates": {
            "unknown-is-conflict": expr_gate(
                "unknown_sets_treated_as_conflicting == true", "fail"
            )
        },
        "stages": [
            {
                "id": "compute-matrix",
                "title": "Compute the intersection matrix and its connected components",
                "kind": "task",
                "role": "computer",
                "timeout_seconds": 300,
                "work_unit": wu(
                    uid="BP3-SHARED-OVERLAP",
                    title="Compute the pairwise overlap matrix and the serial groups",
                    phase="2B",
                    target="For every unordered pair emit the intersection; then emit the connected components of the overlap graph.",
                    inputs=["params.path_sets"],
                    dependencies=[],
                    model="none-deterministic-script",
                    vendor="any",
                    role="computer",
                    basis="an exact algorithm is cheaper and strictly more accurate than a model here",
                    tools=["Read", "Bash:python"],
                    substrate="local-single",
                    timeout=300,
                    output_path="command-center/overlap/matrix.json",
                    output_schema=schema("collision-census"),
                    evidence="the artifact carries every pair with a non-empty intersection, plus the component partition; both are recomputable from the inputs",
                    tests=[
                        "two sets sharing one path must appear in the matrix and land in ONE component",
                        "a null (UNKNOWN) set must overlap every other set, never zero of them",
                        "two disjoint sets must produce no pair entry and two separate components",
                    ],
                    reviewer="none - this is arithmetic and is asserted by tests, not reviewed by opinion",
                    retry="none; a deterministic computation that fails is a defect, not a flake",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="the component partition covers every input name exactly once",
                ),
                "produces": [
                    artifact(
                        "command-center/overlap/matrix.json",
                        schema("collision-census"),
                        min_bytes=64,
                        sentinel="SUCCESS:BP3-SHARED-OVERLAP",
                        consumers=[
                            "bp-pln-02.file-disjoint-work-unit-decomposition",
                            "bp-pln-03.multi-pr-stacking-order-planner",
                        ],
                    )
                ],
            }
        ],
        "stopping_rules": [
            {
                "id": "matrix-complete",
                "expression": "pairs_computed == expected_pairs",
                "applies_to": "workflow",
                "on_stop": "complete",
            }
        ],
        "retry_policy": {"strategy": "none", "max_attempts": 1},
        "failure_policy": failure_policy(
            "fail-fast", ["detector-failure"], "caller", "command-center/quarantine/overlap"
        ),
        "resume": {"enabled": False},
        "replay": replay(
            20260810,
            "command-center/replay/overlap.jsonl",
            ["params", "inputs"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/overlap", ["workflow_version", "inputs_hash"], 604800
        ),
        "dry_run": dry_run(
            "command-center/dry-run/overlap-plan.json",
            ["Bash:python", "Write(command-center/overlap/**)"],
            ["plan"],
        ),
        "estimate": estimate_static(
            wallclock=(1, 5, 60),
            tokens=(0, 0, 0),
            tool_calls=(2, 6),
            risk="low",
            reversibility="reversible",
            blast_radius="pure computation; writes one artifact under command-center/overlap/**",
        ),
        "portability": portability("command-center/export/shared-overlap.bundle.json"),
        "lineage": lineage(
            [("rules/common/fan-out-contract.md#C4", "REBUILD-FROM-SPEC")],
        ),
        "outputs": {
            "matrix": artifact(
                "command-center/overlap/matrix.json",
                schema("collision-census"),
                min_bytes=64,
                consumers=[
                    "bp-pln-02.file-disjoint-work-unit-decomposition",
                    "bp-pln-03.multi-pr-stacking-order-planner",
                ],
            )
        },
        "x_extensions": {
            "role": "SHARED PRIMITIVE - not one of the twelve blueprints",
            "mechanism": "mechanisms.pairwise_overlap + mechanisms.serial_groups",
            "why_factored_out": (
                "BP-PLN-02 and BP-PLN-03 both need it. Shipping it twice would be the "
                "renamed-copy the spec forbids; merging its two callers would conflate "
                "concurrency admission with merge ordering."
            ),
        },
    }


# ================================================================== SHARED SUBWORKFLOW 2


def sub_write_as_you_go() -> dict[str, Any]:
    """The shared durability primitive: a truthful partial beats a perfect artifact never written."""
    return {
        "dsl_version": "1.0.0",
        "id": WAYG_SUB,
        "name": "Write-As-You-Go Truthful Artifact (shared primitive)",
        "description": (
            "Write the artifact IMMEDIATELY as a skeleton in which every claim is marked 'UNKNOWN "
            "- not yet measured', then rewrite it at each milestone. Whatever is on disk must "
            "ALWAYS be truthful. Measured: one unit ran 70 minutes, produced 691 KB of transcript, "
            "then froze and wrote NOTHING - an unrecoverable total loss; a relaunched unit under "
            "this mandate produced a truthful artifact in 3 minutes. The postcondition is the "
            "inverse of the mandate: an artifact still carrying the UNKNOWN marker is NOT complete."
        ),
        "version": "1.0.0",
        "kind": "subworkflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["durability", "truthful-partial", "postcondition", "shared-primitive"],
        "flagship": False,
        "params": {
            "artifact_path": {"type": "path", "required": True, "description": "Where the unit's artifact lives"},
            "claims": {
                "type": "array",
                "required": True,
                "items": {"type": "string"},
                "min_items": 1,
                "description": "Every claim the finished artifact will make; each is enumerated up front as UNKNOWN",
            },
            "min_artifact_bytes": {
                "type": "integer",
                "default": 256,
                "minimum": 1,
                "description": "Below this the artifact is a stub, not a partial result",
            },
        },
        "roles": {
            "writer": {
                "description": "Owns the artifact and rewrites it at every milestone rather than at the end",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "advisory",
                "tool_permissions": ["Read", "Write(command-center/**)"],
                "write_paths": ["command-center/**"],
            }
        },
        "tool_policy": deny_policy(
            ["Read", "Write(command-center/**)"], network="none", write_paths=["command-center/**"]
        ),
        "model_routing": opus_routing(floor=None),
        "gates": {
            "skeleton-exists-first": expr_gate(
                "skeleton_written_before_work_started == true", "fail"
            ),
            "unknown-marker-blocks-completion": expr_gate(
                "unknown_markers_remaining == 0 AND artifact_bytes >= 256", "fail"
            ),
        },
        "stages": [
            {
                "id": "write-skeleton",
                "title": "Write the skeleton with every claim marked UNKNOWN, BEFORE any work",
                "kind": "task",
                "role": "writer",
                "timeout_seconds": 300,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-SHARED-WAYG-SKELETON",
                    title="Write the truthful skeleton first",
                    phase="2B",
                    target="Enumerate every claim the artifact will make and write each as UNKNOWN, plus a COVERAGE line naming the unmeasured sections.",
                    inputs=["params.claims", "params.artifact_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="writer",
                    basis="cheap and mandatory; the artifact must exist before it can be truthful",
                    tools=["Read", "Write(command-center/**)"],
                    substrate="local-single",
                    timeout=300,
                    output_path="command-center/durability/skeleton.json",
                    output_schema=schema("work-result"),
                    evidence="the skeleton exists on disk and carries one UNKNOWN row per declared claim plus a COVERAGE line",
                    tests=[
                        "a skeleton missing a declared claim must FAIL, since an unenumerated claim can be silently forgotten",
                        "the skeleton must state that if it still reads this way the unit died before measuring anything",
                    ],
                    reviewer="none - existence and row count are mechanical",
                    retry="none; if the skeleton cannot be written the unit cannot start",
                    failure_classes=["partial-artifact"],
                    owner_approval=False,
                    sentinel_extra="the file exists and carries one UNKNOWN row per declared claim",
                ),
                "produces": [
                    artifact(
                        "command-center/durability/skeleton.json",
                        schema("work-result"),
                        min_bytes=64,
                        sentinel="SUCCESS:BP3-SHARED-WAYG-SKELETON",
                        consumers=["rewrite-at-milestone"],
                    )
                ],
            },
            {
                "id": "rewrite-at-milestone",
                "title": "Rewrite the artifact at each milestone; the disk copy stays truthful",
                "kind": "loop",
                "depends_on": ["write-skeleton"],
                "loop_var": "milestone",
                "body": [
                    {
                        "id": "rewrite-once",
                        "kind": "task",
                        "role": "writer",
                        "timeout_seconds": 600,
                        "work_unit": wu(
                            uid="BP3-SHARED-WAYG-REWRITE",
                            title="Replace UNKNOWN rows with measured values as each milestone lands",
                            phase="2B",
                            target="Rewrite the artifact so every measured claim carries its measurement and every unmeasured claim still says UNKNOWN.",
                            inputs=["command-center/durability/skeleton.json"],
                            dependencies=["BP3-SHARED-WAYG-SKELETON"],
                            model="opus",
                            vendor="anthropic",
                            role="writer",
                            basis="the rewrite cadence is what converts a total-loss risk into partial progress",
                            tools=["Read", "Write(command-center/**)"],
                            substrate="local-single",
                            timeout=600,
                            output_path="command-center/durability/artifact.json",
                            output_schema=schema("work-result"),
                            evidence="each replaced row names the measurement that replaced it; an unmeasured row is left as UNKNOWN rather than filled in optimistically",
                            tests=[
                                "an UNKNOWN row replaced without a cited measurement must FAIL as an overclaim",
                                "the artifact must remain parseable after every rewrite, so a crash mid-rewrite cannot corrupt it",
                            ],
                            reviewer="the caller's completion predicate",
                            retry="bounded by the loop; a failed rewrite leaves the previous truthful copy in place",
                            failure_classes=["partial-artifact", "overclaim"],
                            owner_approval=False,
                            sentinel_extra="the artifact parses and every non-UNKNOWN row cites a measurement",
                        ),
                    }
                ],
                "convergence": {
                    "max_iterations": 50,
                    "min_iterations": 1,
                    "converged_when": "unknown_markers_remaining == 0",
                    "no_progress_rounds": 3,
                    "metrics": [
                        {"name": "unknown_markers_remaining", "direction": "decrease", "target": 0}
                    ],
                    "on_no_convergence": "emit-partial",
                },
            },
            {
                "id": "postcondition",
                "title": "An artifact still carrying UNKNOWN is NOT complete, however green the run",
                "kind": "gate",
                "depends_on": ["rewrite-at-milestone"],
                "gate_ref": "unknown-marker-blocks-completion",
            },
        ],
        "stopping_rules": [
            {
                "id": "artifact-truthful-and-complete",
                "expression": "unknown_markers_remaining == 0",
                "applies_to": "workflow",
                "minimum_conditions": "skeleton_written_before_work_started == true",
                "on_stop": "complete",
            },
            {
                "id": "died-mid-flight",
                "expression": "unit_died == true AND artifact_parses == true",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": {"strategy": "none", "max_attempts": 1},
        "failure_policy": failure_policy(
            "degrade-loudly",
            ["partial-artifact"],
            "caller",
            "command-center/quarantine/durability",
        ),
        "resume": resume(
            "command-center/checkpoints/durability",
            "stage",
            ["workflow_id", "stage_id", "inputs_hash"],
        ),
        "replay": {"deterministic": False},
        "cache": {"enabled": False},
        "dry_run": dry_run(
            "command-center/dry-run/durability-plan.json",
            ["Write(command-center/**)"],
            ["plan"],
        ),
        "estimate": estimate_static(
            wallclock=(5, 60, 600),
            tokens=(1000, 8000, 40000),
            tool_calls=(3, 60),
            risk="low",
            reversibility="reversible",
            blast_radius="writes one artifact under command-center/**; overwrites only its own prior copy",
        ),
        "portability": portability("command-center/export/shared-wayg.bundle.json"),
        "lineage": lineage(
            [("rules/common/fan-out-contract.md#C1", "REBUILD-FROM-SPEC")],
        ),
        "outputs": {
            "artifact": artifact(
                "command-center/durability/artifact.json",
                schema("work-result"),
                min_bytes=256,
                consumers=["bp-pln-04.resume-safe-program-checkpointing", "the caller"],
            )
        },
        "x_extensions": {
            "role": "SHARED PRIMITIVE - not one of the twelve blueprints",
            "mechanism": "mechanisms.unit_complete + mechanisms.is_truthful_partial",
            "why_factored_out": (
                "BP-PLN-04 needs it as a stage, and every long-running unit in the programme "
                "needs it as a discipline. Promoting it to a thirteenth blueprint would inflate "
                "the range count against a sibling's allocation; leaving it inline in PLN-04 "
                "would hide a reusable primitive."
            ),
        },
    }


# --------------------------------------------------------------------------------- PLN-01


def bp_pln_01() -> dict[str, Any]:
    """Mechanical plan-lint FIRST, then three adversarial lenses only on what a script cannot judge."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-pln-01.mechanical-plan-lint-then-adversarial-trio",
        "name": "Mechanical Plan-Lint then Adversarial Trio",
        "description": (
            "Lint a plan mechanically FIRST - structure, missing sections, unnumbered steps, "
            "untestable acceptance, missing rollback - and only then spend three fresh adversarial "
            "reviewers on what a script cannot judge. The ordering IS the mechanism: if stage 0 "
            "fails hard the reviewers never run, because spending adversarial budget on a "
            "malformed plan is waste. All three lenses must PASS; a FAIL returns the plan to its "
            "author with the blocking items attached."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability", "collective-intelligence-and-meta"],
        "tags": ["plan-gate", "lint-before-llm", "adversarial-trio", "typed-verdicts"],
        "flagship": True,
        "params": {
            "plan_path": {"type": "path", "required": True, "description": "The plan under review"},
            "requirements_path": {
                "type": "path",
                "description": "Requirements the plan must satisfy; when absent the completeness lens says NOT-CHECKED",
            },
            "constraints": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Hard constraints the plan may not violate",
            },
            "cross_vendor_fourth_lens": {
                "type": "boolean",
                "default": False,
                "description": "Add a fourth cross-vendor reviewer on a high-stakes plan; three same-vendor lenses share blind spots",
            },
            "revisions_allowed": {
                "type": "integer",
                "default": 2,
                "minimum": 0,
                "maximum": 5,
                "description": "How many author revisions before the gate escalates instead of looping",
            },
        },
        "roles": {
            "linter": {
                "description": "A deterministic script. It holds no discretion and its verdict is not an opinion.",
                "model": "none-deterministic-script",
                "vendor": "any",
                "effort": "low",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Bash:python"],
                "speaking_rights": "always",
            },
            "feasibility_lens": {
                "description": "Can this plan actually be executed with what exists today",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "completeness_lens": {
                "description": "What the requirements demand and the plan omits",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "scope_lens": {
                "description": "Steps that exceed the stated goal, and steps the goal needs that are absent",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob"],
                "speaking_rights": "always",
            },
            "cross_vendor_lens": {
                "description": "Optional fourth lens from another vendor for high-stakes plans",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "on-request",
            },
            "aggregator": {
                "description": "Counts typed verdicts; it does not average opinions or break ties by vibe",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "judge",
                "independence": "informed",
                "tool_permissions": ["Read", "Bash:python", "Write(command-center/plan-gate/**)"],
                "write_paths": ["command-center/plan-gate/**"],
            },
        },
        "tool_policy": deny_policy(
            ["Read", "Grep", "Glob", "Bash:python", "Write(command-center/plan-gate/**)"],
            network="none",
            write_paths=["command-center/plan-gate/**"],
            forbid_write_paths=["command-center/WORK-UNIT-CATALOG.json"],
        ),
        "model_routing": opus_routing(
            strategy="capability",
            routes=[
                # The linter deliberately has NO route: it is a script, and model_target has no
                # vendor value that honestly denotes "not a model". It is expressed as a role with
                # vendor="any" instead, which is the field that does allow it.
                {
                    "when": "cross_vendor_fourth_lens == true",
                    "target": {"model": "gpt-5-codex", "vendor": "openai", "effort": "high"},
                    "reason": "three same-vendor lenses share blind spots on a high-stakes plan",
                },
            ],
        ),
        "gates": {
            "lint-hard-pass": expr_gate("lint_hard_violations == 0", "fail"),
            "trio-unanimous": expr_gate("lenses_passed == lenses_run AND lenses_run >= 3", "repair"),
            "nothing-mechanical-sent-to-an-llm": expr_gate(
                "reviewer_findings_a_script_could_have_made == 0", "record-and-continue", blocking=False
            ),
        },
        "stages": [
            {
                "id": "s0-lint",
                "title": "S0 LINT mechanically - structure, numbering, acceptance, rollback",
                "kind": "task",
                "role": "linter",
                "timeout_seconds": 600,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-PLN01-S0",
                    title="Run the deterministic plan lint before any reviewer is spent",
                    phase="2B",
                    target="Check the plan for missing sections, unnumbered steps, untestable acceptance criteria and a missing rollback section.",
                    inputs=["params.plan_path"],
                    dependencies=[],
                    model="none-deterministic-script",
                    vendor="any",
                    role="linter",
                    basis="anything a script can decide is never sent to a model",
                    tools=["Read", "Bash:python"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/plan-gate/pln01-lint.json",
                    output_schema=schema("conformance-report"),
                    evidence="every violation names the section and the rule id; the lint records the exact command and exit code",
                    tests=[
                        "a plan with no rollback section MUST be caught by the LINT, not by a reviewer",
                        "the lint must be shown to fire on a known-bad plan before its silence counts as clean",
                        "a lint that found zero inputs must FAIL closed, since a lint over nothing is not a pass",
                    ],
                    reviewer="none - a deterministic lint is asserted by tests, not reviewed",
                    retry="none; a lint failure is a plan defect, not a flake",
                    failure_classes=["detector-failure", "plan-malformed"],
                    owner_approval=False,
                    sentinel_extra="the lint enumerated a non-empty input set and recorded its exit code",
                ),
                "produces": [
                    artifact(
                        "command-center/plan-gate/pln01-lint.json",
                        schema("conformance-report"),
                        min_bytes=128,
                        sentinel="SUCCESS:BP3-PLN01-S0",
                        consumers=["s0-gate", "s2-aggregate"],
                    )
                ],
            },
            {
                "id": "s0-gate",
                "title": "S0 gate: a hard lint failure STOPS here - reviewers are not spent on a malformed plan",
                "kind": "gate",
                "depends_on": ["s0-lint"],
                "gate_ref": "lint-hard-pass",
            },
            {
                "id": "s1-review",
                "title": "S1 FAN OUT three fresh adversarial lenses in parallel",
                "kind": "fanout",
                "depends_on": ["s0-gate"],
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
                        "id": "run-lens",
                        "kind": "task",
                        "role": "feasibility_lens",
                        "timeout_seconds": 1800,
                        "work_unit": wu(
                            uid="BP3-PLN01-S1",
                            title="Review the plan through exactly one adversarial lens",
                            phase="2B",
                            target="Return a typed PASS or FAIL for one lens, with each blocking item anchored to a numbered plan step.",
                            inputs=["params.plan_path", "command-center/plan-gate/pln01-lint.json"],
                            dependencies=["BP3-PLN01-S0"],
                            model="opus",
                            vendor="anthropic",
                            role="feasibility_lens",
                            basis="one lens per agent; a reviewer holding two lenses averages them",
                            tools=["Read", "Grep", "Glob"],
                            substrate="local-parallel",
                            timeout=1800,
                            output_path="command-center/plan-gate/pln01-review.json",
                            output_schema=schema("meta-review-finding"),
                            evidence="each blocking item cites the plan step number and states what would have to be true for it to pass",
                            tests=[
                                "a structurally perfect but infeasible plan MUST be caught by a reviewer, not by the lint - the two benchmark cases must be caught by different stages",
                                "a reviewer returning untyped prose is retried ONCE with the verdict vocabulary enumerated inline, then counted as a null lens",
                            ],
                            reviewer="the aggregator, which counts lenses instead of averaging them",
                            retry="one retry with the vocabulary enumerated inline, then null lens",
                            failure_classes=["schema-invalid", "null-lens"],
                            owner_approval=False,
                            sentinel_extra="the verdict token is recognised and every blocking item cites a plan step number",
                        ),
                    }
                ],
                "barrier": {
                    "mode": "all",
                    "on_partial": "proceed-with-quarantine",
                    "require_stages": ["run-lens"],
                    "reject_result_matching": [
                        "started in the background",
                        "Check /codex:status",
                    ],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s2-aggregate",
                "title": "S2 AGGREGATE typed verdicts and attribute each finding to its right stage",
                "kind": "task",
                "role": "aggregator",
                "depends_on": ["s1-review"],
                "timeout_seconds": 900,
                "work_unit": wu(
                    uid="BP3-PLN01-S2",
                    title="Aggregate the typed verdicts and measure what the lint should have caught",
                    phase="2B",
                    target="Count PASS and FAIL per lens, and flag every reviewer finding that a deterministic lint could have produced.",
                    inputs=["command-center/plan-gate/pln01-review.json", "command-center/plan-gate/pln01-lint.json"],
                    dependencies=["BP3-PLN01-S1"],
                    model="opus",
                    vendor="anthropic",
                    role="aggregator",
                    basis="counting typed verdicts is arithmetic; only the lint-attribution call is judgement",
                    tools=["Read", "Bash:python", "Write(command-center/plan-gate/**)"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/plan-gate/pln01-verdict.json",
                    output_schema=schema("adjudication-report"),
                    evidence="the verdict records lenses_run and lenses_passed separately, so a null lens cannot be silently counted as a pass",
                    tests=[
                        "two PASS plus one null lens must NOT aggregate to a gate PASS",
                        "a reviewer finding that the lint rules already cover must be reported, so the lint can absorb it next time",
                    ],
                    reviewer="the owner reads the verdict; the gate does not need an opinion",
                    retry="one retry then escalate",
                    failure_classes=["null-lens", "overclaim"],
                    owner_approval=False,
                    sentinel_extra="lenses_run and lenses_passed are both recorded and a null lens is counted as neither",
                ),
            },
            {
                "id": "s2-gate",
                "title": "S2 gate: all lenses that ran must have PASSED, and at least three must have run",
                "kind": "gate",
                "depends_on": ["s2-aggregate"],
                "gate_ref": "trio-unanimous",
            },
            {
                "id": "s2b-lint-feedback",
                "title": "S2b ADVISORY: findings a script could have made are lint debt, not review value",
                "kind": "gate",
                "depends_on": ["s2-gate"],
                "gate_ref": "nothing-mechanical-sent-to-an-llm",
            },
        ],
        "stopping_rules": [
            {
                "id": "gate-pass",
                "expression": "lint_hard_violations == 0 AND lenses_passed == lenses_run AND lenses_run >= 3",
                "applies_to": "workflow",
                "minimum_conditions": "lint_inputs_enumerated >= 1",
                "on_stop": "complete",
            },
            {
                "id": "author-out-of-revisions",
                "expression": "revisions_used >= 2",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": two_strikes(3, "aggregator", ["schema-invalid", "null-lens"]),
        "failure_policy": failure_policy(
            "degrade-loudly",
            ["plan-malformed", "null-lens", "detector-failure"],
            "aggregator",
            "command-center/quarantine/pln01",
        ),
        "resume": resume(
            "command-center/checkpoints/pln01",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        # The LINT is deterministic and the REVIEWS are not, so replay records both but verifies
        # only the schema: claiming hash equality over reviewer prose would be an overclaim.
        "replay": replay(
            20260810,
            "command-center/replay/pln01.jsonl",
            ["params", "inputs", "tool_calls", "model_outputs"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/pln01",
            ["workflow_version", "stage_id", "inputs_hash", "model_id"],
            86400,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/pln01-plan.json",
            ["Bash:python", "Write(command-center/plan-gate/**)"],
            ["plan", "estimate", "permission-report"],
        ),
        "estimate": estimate_static(
            wallclock=(300, 1500, 5400),
            tokens=(40000, 220000, 700000),
            tool_calls=(20, 180),
            risk="low",
            reversibility="reversible",
            blast_radius="read-only over the plan; writes only under command-center/plan-gate/**",
        ),
        "portability": portability("command-center/export/bp-pln-01.bundle.json"),
        "lineage": lineage(
            [
                ("workflows/plan-gate.mjs", "ADOPT-AS-IS"),
                ("metaswarm/plan-review-gate", "MERGE"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-01", "REBUILD-FROM-SPEC"),
            ],
            rollback=["workflows/plan-gate.mjs@current"],
        ),
        "outputs": {
            "lint": artifact(
                "command-center/plan-gate/pln01-lint.json",
                schema("conformance-report"),
                min_bytes=128,
                consumers=["the gate", "the plan author"],
            ),
            "verdict": artifact(
                "command-center/plan-gate/pln01-verdict.json",
                schema("adjudication-report"),
                min_bytes=256,
                consumers=["the plan author", "the owner"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-01 (doc-order 33 of 96)",
            "distinguishing_mechanism": (
                "the ORDERING is the mechanism: a hard lint failure prevents the reviewers from "
                "running at all. BP-REQ-05 applies the same ordering to REQUIREMENTS; BP-CNC-01 "
                "reviews a DESIGN with personas and has no mechanical stage."
            ),
            "posture": (
                "SHADOW in its source form: advisory. Project governance may promote it to "
                "blocking, which is a stricter layer and therefore allowed."
            ),
            "worked_example": {
                "name": "each benchmark case must be caught by the RIGHT stage",
                "narrative": (
                    "Two plans. The first has no rollback section: the deterministic lint must "
                    "catch it, and the reviewers must never be spent. The second is structurally "
                    "perfect - numbered steps, rollback present, testable acceptance - but "
                    "proposes a step that cannot be executed with what exists; the lint passes it "
                    "and a reviewer must catch it. A blueprint where BOTH are caught by the same "
                    "stage has lost the property."
                ),
                "mechanism": "mechanisms.is_testable (the lint's acceptance rule) + stage ordering",
                "input": {
                    "plan_a": {
                        "sections": ["goal", "steps"],
                        "acceptance": "the export should feel fast",
                        "has_rollback": False,
                    },
                    "plan_b": {
                        "sections": ["goal", "steps", "rollback"],
                        "acceptance": "p95 latency <= 2000 ms over 100 runs",
                        "has_rollback": True,
                    },
                },
                "expected": {
                    "plan_a_caught_by": "lint",
                    "plan_a_reviewers_spent": 0,
                    "plan_b_caught_by": "reviewer",
                    "plan_b_lint_violations": 0,
                },
                "controls": [
                    {
                        "mutate": "give plan_a a rollback section and a testable criterion",
                        "expected_lint_violations": 0,
                        "why": "the lint must be able to pass, or it is a permanently-red gate that tells you nothing",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- PLN-02


def bp_pln_02() -> dict[str, Any]:
    """File-disjoint decomposition: PROVE disjointness before admitting units to concurrency."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-pln-02.file-disjoint-work-unit-decomposition",
        "name": "File-Disjoint Work-Unit Decomposition",
        "description": (
            "Decompose a plan into work units that PROVABLY do not touch the same files, because "
            "file-disjoint agents still share one git index and a broad 'git add -A' sweeps a "
            "sibling's uncommitted work. The sources of this shape all USE worktree isolation; "
            "none computes the disjointness proof - they assert it. Making the overlap matrix "
            "mechanical is the contribution. A unit whose file set cannot be determined is "
            "SERIALISED, never optimistically parallelised."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["worktree-isolation", "deterministic", "adverse-inference", "concurrency-admission"],
        "flagship": True,
        "params": {
            "plan_path": {"type": "path", "required": True, "description": "The plan to decompose"},
            "repo_file_index_path": {
                "type": "path",
                "required": True,
                "description": "The repo file index the per-unit footprints are resolved against",
            },
            "widen_by_import_closure": {
                "type": "boolean",
                "default": True,
                "description": "Widen each unit's footprint by its import closure: an edit can force a change in a caller",
            },
            "max_parallel": {
                "type": "integer",
                "default": 8,
                "minimum": 1,
                "maximum": 64,
                "description": "Concurrency ceiling for the emitted graph",
            },
        },
        "roles": {
            "decomposer": {
                "description": "Enumerates each unit's file footprint conservatively from the plan",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": ["Read", "Grep", "Glob", "Bash:git"],
            },
            "residue_judge": {
                "description": "Judges ONLY the ambiguous residue the algorithm could not classify",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "judge",
                "independence": "informed",
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "on-request",
            },
            "emitter": {
                "description": "Writes the execution graph and the isolation assignment",
                "model": "none-deterministic-script",
                "vendor": "any",
                "effort": "low",
                "authority": "judge",
                "tool_permissions": ["Read", "Bash:python", "Write(command-center/decomposition/**)"],
                "write_paths": ["command-center/decomposition/**"],
            },
        },
        "tool_policy": deny_policy(
            [
                "Read",
                "Grep",
                "Glob",
                "Bash:git",
                "Bash:python",
                "Write(command-center/decomposition/**)",
            ],
            network="none",
            write_paths=["command-center/decomposition/**"],
        ),
        # The emitter is a deterministic script and therefore carries NO model route: it is
        # declared as a role with vendor="any". model_target.vendor has no honest value for
        # "not a model", so none is invented.
        "model_routing": opus_routing(strategy="capability"),
        "subworkflows": {
            OVERLAP_SUB: {
                "workflow_id": OVERLAP_SUB,
                "version_range": ">=1.0.0 <2.0.0",
                "source": "platform/workflows/_shared/shared.pairwise-overlap-matrix.subworkflow.json",
            }
        },
        "gates": {
            "worktree-is-the-default": expr_gate(
                "mutating_units_without_worktree == 0", "fail"
            ),
            "no-broad-add": expr_gate(
                "scoped_add_units_using_add_all == 0 AND staged_diff_verified == true", "fail"
            ),
            "unknown-footprint-serialised": expr_gate(
                "unknown_footprint_units_parallelised == 0", "fail"
            ),
        },
        "stages": [
            {
                "id": "s0-enumerate",
                "title": "S0/S0b ENUMERATE each unit's file footprint, widened by import closure",
                "kind": "task",
                "role": "decomposer",
                "timeout_seconds": 1800,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-PLN02-S0",
                    title="Enumerate per-unit file footprints conservatively",
                    phase="2B",
                    target="For each work unit list the files it will touch, widened by import closure, or mark the footprint UNKNOWN.",
                    inputs=["params.plan_path", "params.repo_file_index_path"],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="decomposer",
                    basis="conservative estimation costs parallelism; an optimistic estimate costs data",
                    tools=["Read", "Grep", "Glob", "Bash:git"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/decomposition/pln02-footprints.json",
                    output_schema=schema("assignment-matrix"),
                    evidence="each listed path resolves in the repo file index, and each UNKNOWN footprint says WHY it could not be determined",
                    tests=[
                        "a unit whose footprint cannot be determined must be emitted as UNKNOWN, never as an empty set",
                        "an empty footprint and an UNKNOWN footprint must be distinguishable in the artifact",
                    ],
                    reviewer="the residue judge, only for units marked UNKNOWN",
                    retry="two strikes then pivot to marking the footprint UNKNOWN and serialising the unit",
                    failure_classes=["spec-underspecified", "detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every unit has either a resolved footprint or an explicit UNKNOWN with a reason",
                ),
                "produces": [
                    artifact(
                        "command-center/decomposition/pln02-footprints.json",
                        schema("assignment-matrix"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-PLN02-S0",
                        consumers=["s1-matrix"],
                    )
                ],
            },
            {
                "id": "s1-matrix",
                "title": "S1 COMPUTE the pairwise overlap matrix (shared exact primitive)",
                "kind": "subworkflow",
                "depends_on": ["s0-enumerate"],
                "workflow": {
                    "workflow_id": OVERLAP_SUB,
                    "version_range": ">=1.0.0 <2.0.0",
                },
                "params": {"path_sets_from": "command-center/decomposition/pln02-footprints.json"},
                "isolation": "none",
                "propagate_failure": True,
            },
            {
                "id": "s2-group",
                "title": "S2/S3/S4 GROUP overlapping units, ASSIGN isolation, EMIT the graph",
                "kind": "task",
                "role": "emitter",
                "depends_on": ["s1-matrix"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-PLN02-S2",
                    title="Group overlaps into serial groups, assign isolation, emit the execution graph",
                    phase="2B",
                    target="Compute connected components of the overlap graph, assign worktree to mutating units and scoped-add otherwise, and emit the graph.",
                    inputs=["command-center/overlap/matrix.json", "command-center/decomposition/pln02-footprints.json"],
                    dependencies=["BP3-PLN02-S0", "BP3-SHARED-OVERLAP"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="emitter",
                    basis="components and isolation assignment are arithmetic over the matrix",
                    tools=["Read", "Bash:python", "Write(command-center/decomposition/**)"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/decomposition/pln02-graph.json",
                    output_schema=schema("dispatch-plan"),
                    evidence="every unit appears in exactly one serial group and carries exactly one isolation mode",
                    tests=[
                        "two units editing the same file must land in ONE serial group",
                        "every mutating unit must be assigned worktree isolation - the default is not scoped-add",
                        "a unit with an UNKNOWN footprint must be assigned serial, never parallel",
                    ],
                    reviewer="none - this is arithmetic asserted by tests",
                    retry="none; a deterministic grouping that fails is a defect",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every unit is in exactly one group with exactly one isolation mode",
                ),
                "produces": [
                    artifact(
                        "command-center/decomposition/pln02-graph.json",
                        schema("dispatch-plan"),
                        min_bytes=256,
                        sentinel="SUCCESS:BP3-PLN02-S2",
                        consumers=["bp-arc-02.architect-to-editor-split-build", "the executor"],
                    ),
                    artifact(
                        "command-center/decomposition/pln02-isolation.json",
                        schema("isolation-report"),
                        min_bytes=128,
                        consumers=["the executor"],
                    ),
                ],
            },
            {
                "id": "s4-worktree-gate",
                "title": "S4 gate: worktree isolation is the DEFAULT for every mutating unit",
                "kind": "gate",
                "depends_on": ["s2-group"],
                "gate_ref": "worktree-is-the-default",
            },
            {
                "id": "s4-add-gate",
                "title": "S4 gate: a scoped-add unit uses explicit paths and verifies the staged diff",
                "kind": "gate",
                "depends_on": ["s4-worktree-gate"],
                "gate_ref": "no-broad-add",
            },
            {
                "id": "s4-unknown-gate",
                "title": "S4 gate: an undeterminable footprint is serialised (adverse inference)",
                "kind": "gate",
                "depends_on": ["s4-add-gate"],
                "gate_ref": "unknown-footprint-serialised",
            },
        ],
        "stopping_rules": [
            {
                "id": "graph-emitted",
                "expression": "graph_emitted == true AND unknown_footprint_units_parallelised == 0",
                "applies_to": "workflow",
                "minimum_conditions": "units_enumerated >= 1",
                "on_stop": "complete",
            },
            {
                "id": "everything-overlaps",
                "expression": "serial_groups == 1 AND units_enumerated >= 2",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": {"strategy": "none", "max_attempts": 1},
        "failure_policy": failure_policy(
            "fail-fast",
            ["detector-failure", "spec-underspecified"],
            "residue-judge",
            "command-center/quarantine/pln02",
        ),
        "resume": resume(
            "command-center/checkpoints/pln02",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        # FULLY deterministic: the overlap matrix is arithmetic, so hash equality is the honest
        # verification mode here (contrast the reviewer-bearing blueprints, which use schema-equal).
        "replay": replay(
            20260810,
            "command-center/replay/pln02.jsonl",
            ["params", "inputs", "tool_calls", "tool_results"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/pln02", ["workflow_version", "stage_id", "inputs_hash"], 604800
        ),
        "dry_run": dry_run(
            "command-center/dry-run/pln02-plan.json",
            ["Bash:git", "Bash:python", "Write(command-center/decomposition/**)"],
            ["plan", "graph", "permission-report"],
        ),
        "estimate": estimate_static(
            wallclock=(120, 900, 3600),
            tokens=(20000, 100000, 300000),
            tool_calls=(15, 120),
            risk="low",
            reversibility="reversible",
            blast_radius="read-only over the plan and repo index; writes only under command-center/decomposition/**",
        ),
        "portability": portability("command-center/export/bp-pln-02.bundle.json"),
        "lineage": lineage(
            [
                ("skills/workflow-authoring", "COMPOSE"),
                ("skills/claude-devfleet", "COMPOSE"),
                ("rules/common/fan-out-contract.md#C4", "REBUILD-FROM-SPEC"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-02", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "graph": artifact(
                "command-center/decomposition/pln02-graph.json",
                schema("dispatch-plan"),
                min_bytes=256,
                consumers=["the executor", "bp-pln-03.multi-pr-stacking-order-planner"],
            ),
            "isolation": artifact(
                "command-center/decomposition/pln02-isolation.json",
                schema("isolation-report"),
                min_bytes=128,
                consumers=["the executor"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-02 (doc-order 34 of 96)",
            "distinguishing_mechanism": (
                "CONCURRENCY ADMISSION over PREDICTED footprints, with adverse inference on an "
                "unknown footprint and worktree isolation as the default. It shares the overlap "
                "primitive with BP-PLN-03 by REFERENCE, and their decisions differ: this one "
                "answers 'may these run at the same time', PLN-03 answers 'in what order do these "
                "land'. BP-IMP-02 EXECUTES in worktrees; this decides which units may run at all."
            ),
            "measured_gap_closed": (
                "worktree isolation appears in 9 of 329 executed workflows (2.7%). Making it the "
                "default for mutating units is the specific gap this closes."
            ),
            "worked_example": {
                "name": "one shared file collapses two units into a serial group",
                "narrative": (
                    "Four units. u1 and u2 both touch src/app.py, so they must land in one serial "
                    "group. u3 is disjoint and may run in parallel. u4's footprint could not be "
                    "determined, so under adverse inference it overlaps everything and is "
                    "serialised - which, because the overlap graph is connected through u4, pulls "
                    "the whole set into one group. That is the correct, conservative answer."
                ),
                "mechanism": "mechanisms.pairwise_overlap + mechanisms.serial_groups + mechanisms.assign_isolation",
                "input": {
                    "path_sets": {
                        "u1": ["src/app.py", "src/a.py"],
                        "u2": ["src/app.py", "src/b.py"],
                        "u3": ["docs/readme.md"],
                        "u4": None,
                    },
                    "mutating": ["u1", "u2", "u3"],
                },
                "expected": {
                    "overlap_pairs": [["u1", "u2"], ["u1", "u4"], ["u2", "u4"], ["u3", "u4"]],
                    "serial_groups": [["u1", "u2", "u3", "u4"]],
                    "isolation": {"u1": "worktree", "u2": "worktree", "u3": "worktree", "u4": "serial"},
                },
                "controls": [
                    {
                        "mutate": "give u4 the concrete footprint ['tests/test_c.py']",
                        "expected_serial_groups": [["u1", "u2"], ["u3"], ["u4"]],
                        "why": "with u4's footprint known the graph splits into three components - which proves the UNKNOWN handling, not the arithmetic, produced the single group",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- PLN-03


def bp_pln_03() -> dict[str, Any]:
    """Multi-PR stacking order: byte-identity and a measured conflict surface, not mergeStateStatus."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-pln-03.multi-pr-stacking-order-planner",
        "name": "Multi-PR Stacking-Order Planner",
        "description": (
            "Determine the real merge order of N open PRs by measuring what actually conflicts. "
            "mergeStateStatus CLEAN is evaluated in ISOLATION and says nothing about PR-to-PR "
            "overlap: seven CLEAN PRs looked mutually conflicting and were fully stackable because "
            "the overlapping content was BYTE-IDENTICAL, so whichever merged second was a no-op. "
            "Conflict COST is measured with a throwaway merge and counted in unmerged paths, never "
            "estimated from diff size - a +72k-line PR measured a five-file conflict surface."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["merge-order", "byte-identity", "conflict-surface", "throwaway-probe"],
        "flagship": True,
        "params": {
            "prs": {
                "type": "array",
                "required": True,
                "items": {"type": "string"},
                "min_items": 2,
                "description": "PR refs to order. One PR has no ordering problem.",
            },
            "base_ref": {
                "type": "string",
                "required": True,
                "min_length": 3,
                "description": "The base to measure against, e.g. origin/main",
            },
            "probe_branch_prefix": {
                "type": "string",
                "default": "throwaway/merge-probe",
                "description": "Every merge probe runs on a THROWAWAY branch; a probe that dirties a real branch is a process failure",
            },
            "forge_token": {
                "type": "secret_ref",
                "secret": True,
                "description": (
                    "Reference NAME of the forge credential the gh calls authenticate with. This "
                    "blueprint is the only one in its range that talks to a forge, so it is the "
                    "only one that must declare a credential. Declaring it as a secret_ref (rather "
                    "than leaving it implicit in the ambient environment) is what makes the "
                    "export-redaction rule checkable: the VALUE may never enter an artifact, a log, "
                    "an export bundle or a replay journal - only this reference name travels. The "
                    "workflow never reads, prints or rotates the credential."
                ),
            },
        },
        "roles": {
            "measurer": {
                "description": "Runs git plumbing only: changed-file lists, byte digests, throwaway merges, revision walks",
                "model": "none-deterministic-script",
                "vendor": "any",
                "effort": "low",
                "authority": "judge",
                "independence": "independent",
                "tool_permissions": ["Read", "Bash:git", "Bash:gh", "Bash:python"],
            },
            "semantic_judge": {
                "description": "Judges only the residue byte-identity cannot settle: two different edits that mean the same thing, or the reverse",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": ["Read", "Grep"],
                "speaking_rights": "on-request",
            },
        },
        "tool_policy": deny_policy(
            [
                "Read",
                "Grep",
                "Bash:git",
                "Bash:gh",
                "Bash:python",
                "Write(command-center/stacking/**)",
            ],
            network="read-only",
            write_paths=["command-center/stacking/**"],
            forbid_write_paths=["command-center/WORK-UNIT-CATALOG.json"],
            source_policy={
                "require_provenance": True,
                "treat_fetched_content_as_data": True,
                "paywalled": "record-as-not-checked",
            },
        ),
        # The measurer runs git plumbing only, so it carries NO model route and is declared as a
        # role with vendor="any": byte digests and unmerged-path counts are exact and a model
        # would only add error.
        "model_routing": opus_routing(strategy="capability"),
        "subworkflows": {
            OVERLAP_SUB: {
                "workflow_id": OVERLAP_SUB,
                "version_range": ">=1.0.0 <2.0.0",
                "source": "platform/workflows/_shared/shared.pairwise-overlap-matrix.subworkflow.json",
            }
        },
        "gates": {
            "probe-tree-clean": expr_gate(
                "probe_branches_abandoned == probe_branches_created AND working_tree_dirty == false",
                "fail",
            ),
            "no-mergestate-shortcut": expr_gate(
                "order_derived_from_mergestatestatus_alone == false", "fail"
            ),
            "surface-measured-not-estimated": expr_gate(
                "conflict_surface_from_line_count == false AND unmerged_paths_counted == true",
                "fail",
            ),
        },
        "stages": [
            {
                "id": "s0-changed-files",
                "title": "S0 LIST changed files per PR, three-dot against the base",
                "kind": "task",
                "role": "measurer",
                "timeout_seconds": 900,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-PLN03-S0",
                    title="List each PR's changed files with a three-dot diff",
                    phase="2B",
                    target="For each PR compute the changed-file set using base...head, so working-tree noise is excluded.",
                    inputs=["params.prs", "params.base_ref"],
                    dependencies=[],
                    model="none-deterministic-script",
                    vendor="any",
                    role="measurer",
                    basis="git plumbing, no judgement",
                    tools=["Read", "Bash:git", "Bash:gh"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/stacking/pln03-changed-files.json",
                    output_schema=schema("collision-census"),
                    evidence="records the exact three-dot diff command per PR alongside its file list",
                    tests=[
                        "a two-dot diff must be rejected: it folds in working-tree noise, which is how an untracked file appears to be 'in the PR'",
                        "a stale branch far behind the base must be measured with three dots, or it appears to propose mass deletion",
                    ],
                    reviewer="none - the recorded command is the evidence",
                    retry="two strikes then pivot to fetching the base first",
                    failure_classes=["detector-failure", "stale-pinned-ref"],
                    owner_approval=False,
                    sentinel_extra="every PR carries a three-dot command string and a file list",
                ),
                "produces": [
                    artifact(
                        "command-center/stacking/pln03-changed-files.json",
                        schema("collision-census"),
                        min_bytes=192,
                        sentinel="SUCCESS:BP3-PLN03-S0",
                        consumers=["s1-matrix", "s2-byte-identity"],
                    )
                ],
            },
            {
                "id": "s1-matrix",
                "title": "S1 PAIRWISE overlap matrix (shared exact primitive)",
                "kind": "subworkflow",
                "depends_on": ["s0-changed-files"],
                "workflow": {"workflow_id": OVERLAP_SUB, "version_range": ">=1.0.0 <2.0.0"},
                "params": {"path_sets_from": "command-center/stacking/pln03-changed-files.json"},
                "isolation": "none",
                "propagate_failure": True,
            },
            {
                "id": "s2-byte-identity",
                "title": "S2 TEST byte-identity of the overlapping content",
                "kind": "task",
                "role": "measurer",
                "depends_on": ["s1-matrix"],
                "timeout_seconds": 900,
                "work_unit": wu(
                    uid="BP3-PLN03-S2",
                    title="Digest the overlapping content on both sides of every overlapping pair",
                    phase="2B",
                    target="For each overlapping path in each pair, compare content digests; byte-identical overlap is stackable, not conflicting.",
                    inputs=["command-center/overlap/matrix.json", "command-center/stacking/pln03-changed-files.json"],
                    dependencies=["BP3-PLN03-S0", "BP3-SHARED-OVERLAP"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="measurer",
                    basis="a digest comparison is exact; an LLM opinion on sameness is not",
                    tools=["Read", "Bash:git", "Bash:python"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/stacking/pln03-byte-parity.json",
                    output_schema=schema("byte-parity-report"),
                    evidence="each overlapping path records both digests, so the identical/conflicting split is recomputable",
                    tests=[
                        "two PRs whose overlapping content is byte-identical must be reported STACKABLE, not conflicting",
                        "content read for digesting must come from the committed blob, never from the working tree, because line endings differ between them on this platform",
                    ],
                    reviewer="the semantic judge only for pairs that differ but may mean the same thing",
                    retry="two strikes then pivot to a per-hunk comparison",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every overlapping path carries two digests and an identical/conflicting verdict",
                ),
                "produces": [
                    artifact(
                        "command-center/stacking/pln03-byte-parity.json",
                        schema("byte-parity-report"),
                        min_bytes=128,
                        sentinel="SUCCESS:BP3-PLN03-S2",
                        consumers=["s3-surface", "s5-order"],
                    )
                ],
            },
            {
                "id": "s3-surface",
                "title": "S3 MEASURE the real conflict surface with a throwaway merge",
                "kind": "task",
                "role": "measurer",
                "depends_on": ["s2-byte-identity"],
                "timeout_seconds": 1800,
                "work_unit": wu(
                    uid="BP3-PLN03-S3",
                    title="Count unmerged paths from a throwaway merge, then abort it",
                    phase="2B",
                    target="On a throwaway branch, merge without committing and count the unmerged paths; that count, not the diff size, is the cost.",
                    inputs=["params.prs", "params.base_ref", "params.probe_branch_prefix"],
                    dependencies=["BP3-PLN03-S2"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="measurer",
                    basis="the conflict surface must be measured, because line count is not a cost proxy",
                    tools=["Bash:git", "Bash:python", "Read"],
                    substrate="local-single",
                    timeout=1800,
                    output_path="command-center/stacking/pln03-surface.json",
                    output_schema=schema("collision-census"),
                    evidence="records the probe branch name, the unmerged-path count, and the abort that followed",
                    tests=[
                        "every probe must run on a throwaway branch and must be aborted; a probe that leaves the tree dirty is a process failure",
                        "a large-diff PR with a small conflict surface must report the SMALL number - the whole point is that line count misleads",
                    ],
                    reviewer="none - the recorded branch and counts are the evidence",
                    retry="two strikes then pivot to a fresh throwaway branch",
                    failure_classes=["detector-failure", "dirty-probe-tree"],
                    owner_approval=False,
                    sentinel_extra="every probe branch was created, counted, and aborted, and the working tree is clean",
                ),
            },
            {
                "id": "s3-gate",
                "title": "S3 gate: every probe branch aborted, working tree clean",
                "kind": "gate",
                "depends_on": ["s3-surface"],
                "gate_ref": "probe-tree-clean",
            },
            {
                "id": "s4-superset",
                "title": "S4 DETECT superset relations - if B contains A, reconcile from B",
                "kind": "task",
                "role": "measurer",
                "depends_on": ["s3-gate"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-PLN03-S4",
                    title="Find pairs where one PR already contains the other's work",
                    phase="2B",
                    target="For each ordered pair, decide whether B contains A by walking revisions; if so, close A in B's favour.",
                    inputs=["params.prs", "params.base_ref"],
                    dependencies=["BP3-PLN03-S3"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="measurer",
                    basis="a revision-set containment test is exact",
                    tools=["Bash:git", "Bash:python", "Read"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/stacking/pln03-supersets.json",
                    output_schema=schema("supersession-graph"),
                    evidence="each superset claim records the two revision sets that establish containment",
                    tests=["a PR whose commits are all present in another must be reported as superseded, not as a separate merge"],
                    reviewer="the semantic judge when containment holds by revision but the diffs differ",
                    retry="two strikes then pivot to a diff-level containment check",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every superset claim records both revision sets",
                ),
            },
            {
                "id": "s5-order",
                "title": "S5 EMIT the merge order, ranked by measured surface",
                "kind": "task",
                "role": "measurer",
                "depends_on": ["s4-superset"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-PLN03-S5",
                    title="Emit the recommended merge order",
                    phase="2B",
                    target="Order the PRs by measured conflict surface ascending, with deterministic tie-breaks, and list the byte-identical stackable pairs.",
                    inputs=[
                        "command-center/stacking/pln03-surface.json",
                        "command-center/stacking/pln03-byte-parity.json",
                        "command-center/stacking/pln03-supersets.json",
                    ],
                    dependencies=["BP3-PLN03-S4"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="measurer",
                    basis="the ordering rule is declared and arithmetic, so two runs agree",
                    tools=["Read", "Bash:python", "Write(command-center/stacking/**)"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/stacking/pln03-order.json",
                    output_schema=schema("release-gate-report"),
                    evidence="the order records, per PR, the surface count that placed it and any superset relation that removed it",
                    tests=[
                        "the order must be stable across two runs on the same inputs",
                        "a superseded PR must not appear in the order at all",
                    ],
                    reviewer="the owner, who merges",
                    retry="none; a deterministic ordering that fails is a defect",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every ordered PR carries the surface count that placed it",
                ),
                "produces": [
                    artifact(
                        "command-center/stacking/pln03-order.json",
                        schema("release-gate-report"),
                        min_bytes=192,
                        sentinel="SUCCESS:BP3-PLN03-S5",
                        consumers=["the owner", "bp-rel-01 (PR shepherd, another range)"],
                    )
                ],
            },
            {
                "id": "s5-gate",
                "title": "S5 gate: the order came from measurement, not from mergeStateStatus or line count",
                "kind": "gate",
                "depends_on": ["s5-order"],
                "gate_ref": "no-mergestate-shortcut",
            },
            {
                "id": "s5-surface-gate",
                "title": "S5 gate: cost was counted in unmerged paths, not estimated from diff size",
                "kind": "gate",
                "depends_on": ["s5-gate"],
                "gate_ref": "surface-measured-not-estimated",
            },
        ],
        "stopping_rules": [
            {
                "id": "order-emitted",
                "expression": "merge_order_emitted == true AND probe_branches_abandoned == probe_branches_created",
                "applies_to": "workflow",
                "minimum_conditions": "prs_measured >= 2",
                "on_stop": "complete",
            },
            {
                "id": "all-superseded",
                "expression": "unsuperseded_prs <= 1",
                "applies_to": "workflow",
                "on_stop": "complete",
            },
        ],
        "retry_policy": two_strikes(3, "semantic-judge", ["detector-failure", "dirty-probe-tree"]),
        "failure_policy": failure_policy(
            "fail-fast",
            ["detector-failure", "dirty-probe-tree", "stale-pinned-ref"],
            "semantic-judge",
            "command-center/quarantine/pln03",
        ),
        "resume": resume(
            "command-center/checkpoints/pln03",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
        ),
        "replay": replay(
            20260810,
            "command-center/replay/pln03.jsonl",
            ["params", "inputs", "tool_calls", "tool_results", "env_fingerprint"],
            "hash-equal",
        ),
        "cache": cache(
            "command-center/cache/pln03",
            ["workflow_version", "stage_id", "inputs_hash", "tool_versions"],
            43200,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/pln03-plan.json",
            ["Bash:git", "Bash:gh", "Bash:python", "Write(command-center/stacking/**)"],
            ["plan", "estimate", "permission-report", "graph"],
        ),
        "estimate": estimate_static(
            wallclock=(180, 1200, 5400),
            tokens=(10000, 60000, 200000),
            tool_calls=(30, 250),
            risk="low",
            reversibility="reversible",
            blast_radius="all probing happens on throwaway branches which are aborted; the real branches are read-only and only command-center/stacking/** is written",
        ),
        "portability": portability("command-center/export/bp-pln-03.bundle.json"),
        "lineage": lineage(
            [
                ("rules/common/fan-out-contract.md#C3", "REBUILD-FROM-SPEC"),
                ("workflows/reconcile-all-branches-prs", "GENERALIZE"),
                ("rules/common/stale-megapr-reconcile.md", "MERGE"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-03", "REBUILD-FROM-SPEC"),
            ]
        ),
        "outputs": {
            "order": artifact(
                "command-center/stacking/pln03-order.json",
                schema("release-gate-report"),
                min_bytes=192,
                consumers=["the owner"],
            ),
            "byte_parity": artifact(
                "command-center/stacking/pln03-byte-parity.json",
                schema("byte-parity-report"),
                min_bytes=128,
                consumers=["the owner", "the semantic judge"],
            ),
            "supersets": artifact(
                "command-center/stacking/pln03-supersets.json",
                schema("supersession-graph"),
                min_bytes=96,
                consumers=["the owner"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-03 (doc-order 35 of 96)",
            "distinguishing_mechanism": (
                "MERGE ORDERING over MEASURED git refs, decided by byte-identity of the "
                "overlapping content plus a throwaway-merge unmerged-path count plus revision-set "
                "containment. It shares the overlap primitive with BP-PLN-02 by REFERENCE; the "
                "decision, the inputs and the deciding tests are all different. BP-REL-01 "
                "shepherds ONE PR; this orders many before any is shepherded."
            ),
            "honest_bound": (
                "byte-identity is a strong but incomplete conflict predictor: two textually "
                "different edits can still conflict semantically, which is why a semantic judge "
                "exists for exactly that residue and nothing else."
            ),
            "worked_example": {
                "name": "byte-identical overlap is stackable, and surface beats line count",
                "narrative": (
                    "PR-1 and PR-2 both change ci.yml. The bytes they land there are IDENTICAL "
                    "(PR-2 already contains PR-1's edit), so the pair is STACKABLE and whichever "
                    "merges second is a no-op on that path. PR-3 also touches ci.yml but with "
                    "different bytes, so PR-1/PR-3 is a true conflict. Ordering then runs on the "
                    "measured surface: PR-3 has the largest diff but only one conflicting path, "
                    "so it is not automatically last."
                ),
                "mechanism": "mechanisms.classify_overlap + mechanisms.is_superset + mechanisms.merge_order",
                "input": {
                    "pr1_content": {"ci.yml": "on: push\n", "a.py": "x = 1\n"},
                    "pr2_content": {"ci.yml": "on: push\n", "b.py": "y = 2\n"},
                    "pr3_content": {"ci.yml": "on: pull_request\n"},
                    "commits": {"pr1": ["c1"], "pr2": ["c1", "c2"], "pr3": ["c9"]},
                    "surface": {"pr1": 0, "pr2": 0, "pr3": 1},
                },
                "expected": {
                    "pr1_pr2_identical": ["ci.yml"],
                    "pr1_pr2_conflicts": [],
                    "pr1_pr3_conflicts": ["ci.yml"],
                    "pr2_supersets_pr1": True,
                    "order": ["pr1", "pr2", "pr3"],
                },
                "controls": [
                    {
                        "mutate": "change pr2's ci.yml bytes to 'on: schedule'",
                        "expected_pr1_pr2_conflicts": ["ci.yml"],
                        "why": "the digest comparison is doing the work - identical bytes are what make the pair stackable, not the shared path",
                    }
                ],
            },
        },
    }


# --------------------------------------------------------------------------------- PLN-04


def bp_pln_04() -> dict[str, Any]:
    """Resume-safe checkpointing: a POSTCONDITION per unit, and a carve-out around pipeline()."""
    return {
        "dsl_version": "1.0.0",
        "id": "bp-pln-04.resume-safe-program-checkpointing",
        "name": "Resume-Safe Program Checkpointing",
        "description": (
            "Structure a long program so a kill, a compaction or a session loss resumes from the "
            "last completed unit. Completion is a POSTCONDITION ON THE ARTIFACT, never 'the agent "
            "said done': a unit whose artifact still reads 'UNKNOWN - not yet measured' is not "
            "complete however green the run looked. Two repairs over the source design: the "
            "write-as-you-go mandate, which converts a total-loss risk into partial progress, and "
            "an explicit carve-out that no resumable boundary may be wrapped in a pipeline, "
            "because a stopped pipeline re-runs its first stage."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": ["engineering-and-reliability"],
        "tags": ["resume", "postcondition", "write-as-you-go", "pipeline-carve-out"],
        "flagship": True,
        "params": {
            "program_units": {
                "type": "array",
                "required": True,
                "items": {"type": "string"},
                "min_items": 1,
                "description": "The unit ids the program is decomposed into",
            },
            "artifact_root": {
                "type": "path",
                "required": True,
                "description": "Where per-unit artifacts live. Partial artifacts live here, never in temp - they can carry sensitive intermediate data.",
            },
            "min_artifact_bytes": {
                "type": "integer",
                "default": 256,
                "minimum": 1,
                "description": "A completion predicate floor: below this the artifact is a stub, not a result",
            },
            "heartbeat_seconds": {
                "type": "integer",
                "default": 900,
                "minimum": 30,
                "description": "Per-unit heartbeat so a FROZEN unit is distinguishable from a merely slow one",
            },
        },
        "roles": {
            "unit_runner": {
                "description": "Runs one program unit and rewrites its artifact at every milestone",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "independent",
                "min_participants": 1,
                "max_participants": 64,
                "tool_permissions": ["Read", "Grep", "Write(command-center/**)"],
                "write_paths": ["command-center/**"],
            },
            "checkpoint_keeper": {
                "description": "Evaluates each unit's postcondition and owns the resume plan; it never asks a unit whether it finished",
                "model": "none-deterministic-script",
                "vendor": "any",
                "effort": "low",
                "authority": "judge",
                "independence": "independent",
                "tool_permissions": ["Read", "Bash:python", "Write(command-center/checkpoints/**)"],
                "write_paths": ["command-center/checkpoints/**"],
            },
        },
        "tool_policy": deny_policy(
            [
                "Read",
                "Grep",
                "Bash:python",
                "Write(command-center/**)",
                "Write(command-center/checkpoints/**)",
            ],
            network="none",
            write_paths=["command-center/**"],
        ),
        # The checkpoint keeper is a file-predicate evaluator: NO model route, role vendor="any".
        # Routing a postcondition to a model would reintroduce the self-report this blueprint
        # exists to eliminate.
        "model_routing": opus_routing(strategy="capability"),
        "subworkflows": {
            WAYG_SUB: {
                "workflow_id": WAYG_SUB,
                "version_range": ">=1.0.0 <2.0.0",
                "source": "platform/workflows/_shared/shared.write-as-you-go-artifact.subworkflow.json",
            }
        },
        "gates": {
            "postcondition-not-self-report": expr_gate(
                "units_marked_complete_without_artifact_check == 0", "fail"
            ),
            "unknown-marker-is-not-complete": expr_gate(
                "units_complete_with_unknown_markers == 0", "fail"
            ),
            "no-pipeline-around-a-resumable-boundary": expr_gate(
                "resumable_boundaries_wrapped_in_pipeline == 0", "fail"
            ),
            "unit-complete": unit_gate([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "repair"),
        },
        "stages": [
            {
                "id": "s0-define-predicates",
                "title": "S0 DEFINE a machine-checkable completion predicate per unit",
                "kind": "task",
                "role": "checkpoint_keeper",
                "timeout_seconds": 900,
                "checkpoint": True,
                "work_unit": wu(
                    uid="BP3-PLN04-S0",
                    title="Write one machine-checkable postcondition per program unit",
                    phase="2B",
                    target="For each unit define the artifact path, the minimum size, the schema it must satisfy, and the marker that disqualifies it.",
                    inputs=["params.program_units", "params.artifact_root", "params.min_artifact_bytes"],
                    dependencies=[],
                    model="none-deterministic-script",
                    vendor="any",
                    role="checkpoint_keeper",
                    basis="a predicate that needs judgement is not a predicate",
                    tools=["Read", "Bash:python", "Write(command-center/checkpoints/**)"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/checkpoints/pln04-predicates.json",
                    output_schema=schema("stopping-condition"),
                    evidence="each predicate is expressed as a file test - exists, size, parses, schema-valid, no UNKNOWN marker - with no prose condition",
                    tests=[
                        "a predicate phrased as 'the agent reports success' must be REJECTED; that is self-report, not a postcondition",
                        "a predicate with no size floor must be rejected, since an empty file would satisfy exists-and-parses",
                    ],
                    reviewer="none - a predicate is either machine-checkable or it is not",
                    retry="none; an unwritable predicate means the unit is not decomposable yet",
                    failure_classes=["spec-underspecified"],
                    owner_approval=False,
                    sentinel_extra="every unit has a predicate composed only of file tests",
                ),
                "produces": [
                    artifact(
                        "command-center/checkpoints/pln04-predicates.json",
                        schema("stopping-condition"),
                        min_bytes=128,
                        sentinel="SUCCESS:BP3-PLN04-S0",
                        consumers=["s1-run", "s2-mark", "s3-resume"],
                    )
                ],
            },
            {
                "id": "s1-run",
                "title": "S1 RUN units, each writing a truthful partial from the first second",
                "kind": "fanout",
                "depends_on": ["s0-define-predicates"],
                "over": {
                    "source": "param",
                    "ref": "program_units",
                    "item_var": "unit",
                    "key_field": "unit",
                },
                "max_concurrency": 8,
                "arrival_stagger_ms": 500,
                "max_items": 256,
                "on_item_failure": "quarantine",
                "body": [
                    {
                        "id": "write-as-you-go",
                        "kind": "subworkflow",
                        "workflow": {"workflow_id": WAYG_SUB, "version_range": ">=1.0.0 <2.0.0"},
                        "params": {"artifact_root_from": "params.artifact_root"},
                        "isolation": "worktree",
                        "propagate_failure": False,
                    },
                    {
                        "id": "run-unit",
                        "kind": "task",
                        "role": "unit_runner",
                        "depends_on": ["write-as-you-go"],
                        "timeout_seconds": 7200,
                        "work_unit": wu(
                            uid="BP3-PLN04-S1",
                            title="Run one unit, rewriting its artifact at each milestone",
                            phase="2B",
                            target="Execute one program unit, keeping the on-disk artifact truthful at every point so a death mid-flight still leaves usable partial progress.",
                            inputs=["command-center/checkpoints/pln04-predicates.json"],
                            dependencies=["BP3-PLN04-S0"],
                            model="opus",
                            vendor="anthropic",
                            role="unit_runner",
                            basis="substantive work; the artifact discipline is what makes it survivable",
                            tools=["Read", "Grep", "Write(command-center/**)"],
                            substrate="local-parallel",
                            timeout=7200,
                            output_path="command-center/checkpoints/pln04-unit.json",
                            output_schema=schema("work-result"),
                            evidence="the artifact existed before the work started and was rewritten at each milestone; a heartbeat distinguishes frozen from slow",
                            tests=[
                                "a unit killed mid-flight must leave a PARSEABLE artifact whose unmeasured rows still say UNKNOWN",
                                "a unit that wrote nothing must be classified NOT_STARTED, never inferred complete from its transcript length",
                            ],
                            reviewer="the checkpoint keeper's postcondition, which never reads the transcript",
                            retry="two strikes then pivot; a resumed unit must not re-run a completed sibling",
                            failure_classes=["partial-artifact", "agent-death-at-orchestrator-boundary"],
                            owner_approval=False,
                            sentinel_extra="the artifact parses and its unmeasured rows still carry the UNKNOWN marker",
                        ),
                    },
                ],
                "barrier": {
                    "mode": "deadline",
                    "deadline_seconds": 28800,
                    "on_partial": "proceed-with-quarantine",
                    "reject_result_matching": [
                        "started in the background",
                        "Check /codex:status",
                    ],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "s2-mark",
                "title": "S2 MARK completion only when the postcondition passes",
                "kind": "task",
                "role": "checkpoint_keeper",
                "depends_on": ["s1-run"],
                "timeout_seconds": 900,
                "work_unit": wu(
                    uid="BP3-PLN04-S2",
                    title="Evaluate every unit's postcondition against its artifact on disk",
                    phase="2B",
                    target="For each unit evaluate exists, size, parses, schema-valid and no-UNKNOWN-marker, and record COMPLETE, PARTIAL or NOT_STARTED.",
                    inputs=["command-center/checkpoints/pln04-predicates.json", "command-center/checkpoints/pln04-unit.json"],
                    dependencies=["BP3-PLN04-S1"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="checkpoint_keeper",
                    basis="the postcondition must never consult the agent that produced the artifact",
                    tools=["Read", "Bash:python", "Write(command-center/checkpoints/**)"],
                    substrate="local-single",
                    timeout=900,
                    output_path="command-center/checkpoints/pln04-state.json",
                    output_schema=schema("completion-census"),
                    evidence="each state records which sub-condition failed, so PARTIAL is actionable rather than a bare label",
                    tests=[
                        "an artifact still carrying the UNKNOWN marker must be PARTIAL, never COMPLETE",
                        "an artifact below the size floor must be PARTIAL even when it parses",
                        "the checker must be run against a known-incomplete artifact and shown to say PARTIAL before its COMPLETE verdicts are trusted",
                    ],
                    reviewer="none - the predicate is the reviewer",
                    retry="none; a deterministic check that fails is a defect",
                    failure_classes=["detector-failure"],
                    owner_approval=False,
                    sentinel_extra="every unit carries a state and, when not COMPLETE, the sub-condition that failed",
                ),
                "produces": [
                    artifact(
                        "command-center/checkpoints/pln04-state.json",
                        schema("completion-census"),
                        min_bytes=128,
                        sentinel="SUCCESS:BP3-PLN04-S2",
                        consumers=["s3-resume", "the owner"],
                    )
                ],
            },
            {
                "id": "s2-gate",
                "title": "S2 gate: no unit is marked complete without an artifact check",
                "kind": "gate",
                "depends_on": ["s2-mark"],
                "gate_ref": "postcondition-not-self-report",
            },
            {
                "id": "s2b-gate",
                "title": "S2b gate: an UNKNOWN marker disqualifies completion",
                "kind": "gate",
                "depends_on": ["s2-gate"],
                "gate_ref": "unknown-marker-is-not-complete",
            },
            {
                "id": "s3-resume",
                "title": "S3 On resume, SKIP units whose predicate already passes",
                "kind": "task",
                "role": "checkpoint_keeper",
                "depends_on": ["s2b-gate"],
                "timeout_seconds": 600,
                "work_unit": wu(
                    uid="BP3-PLN04-S3",
                    title="Emit the resume plan: which units to skip and which to run",
                    phase="2B",
                    target="Partition the units into skip and run purely from the recorded postcondition states, with no reference to any transcript.",
                    inputs=["command-center/checkpoints/pln04-state.json"],
                    dependencies=["BP3-PLN04-S2"],
                    model="none-deterministic-script",
                    vendor="any",
                    role="checkpoint_keeper",
                    basis="the resume decision is a partition over recorded states",
                    tools=["Read", "Bash:python", "Write(command-center/checkpoints/**)"],
                    substrate="local-single",
                    timeout=600,
                    output_path="command-center/checkpoints/pln04-resume.json",
                    output_schema=schema("idempotency-report"),
                    evidence="skip and run partition the unit set exactly once, and the idempotency key for each unit is recorded",
                    tests=[
                        "kill the program mid-unit and resume: COMPLETE units must NOT re-run",
                        "the killed unit's partial must be truthful and it must appear in the run set",
                        "skip and run together must cover every unit exactly once",
                    ],
                    reviewer="none - the partition is arithmetic",
                    retry="none; a deterministic partition that fails is a defect, not a flake",
                    failure_classes=["detector-failure", "pipeline-first-stage-rerun"],
                    owner_approval=False,
                    sentinel_extra="skip and run partition the unit set exactly once",
                ),
            },
            {
                "id": "s4-pipeline-carveout",
                "title": "S4 ASSERT no resumable boundary is wrapped in a pipeline",
                "kind": "gate",
                "depends_on": ["s3-resume"],
                "gate_ref": "no-pipeline-around-a-resumable-boundary",
            },
            {
                "id": "s5-predicate",
                "title": "S5 gate the program artifact on the shared 12-condition predicate",
                "kind": "gate",
                "depends_on": ["s4-pipeline-carveout"],
                "gate_ref": "unit-complete",
            },
        ],
        "stopping_rules": [
            {
                "id": "all-units-complete",
                "expression": "units_complete == units_total",
                "applies_to": "workflow",
                "minimum_conditions": "predicates_defined == units_total",
                "on_stop": "complete",
            },
            {
                "id": "died-but-truthful",
                "expression": "units_partial >= 1 AND partial_artifacts_parse == true",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
        ],
        "retry_policy": two_strikes(
            3, "checkpoint-keeper", ["agent-death-at-orchestrator-boundary", "quota-429-storm"]
        ),
        "failure_policy": failure_policy(
            "degrade-loudly",
            ["partial-artifact", "agent-death-at-orchestrator-boundary", "detector-failure"],
            "checkpoint-keeper",
            "command-center/quarantine/pln04",
        ),
        "resume": resume(
            "command-center/checkpoints/pln04",
            "work-unit",
            ["workflow_id", "workflow_version", "stage_id", "item_key", "params_hash", "inputs_hash"],
        ),
        "replay": replay(
            20260810,
            "command-center/replay/pln04.jsonl",
            ["params", "inputs", "tool_calls", "timings", "env_fingerprint"],
            "schema-equal",
        ),
        "cache": cache(
            "command-center/cache/pln04",
            ["workflow_version", "stage_id", "item_key", "params_hash", "inputs_hash"],
            604800,
        ),
        "dry_run": dry_run(
            "command-center/dry-run/pln04-plan.json",
            ["Bash:python", "Write(command-center/**)", "Write(command-center/checkpoints/**)"],
            ["plan", "estimate", "graph", "artifact-diff"],
        ),
        "estimate": estimate_static(
            wallclock=(600, 14400, 86000),
            tokens=(50000, 1000000, 6000000),
            tool_calls=(40, 900),
            risk="low",
            reversibility="reversible",
            blast_radius="writes per-unit artifacts and checkpoint state under command-center/**; partial artifacts stay under the artifact root rather than in temp because they can carry sensitive intermediate data",
        ),
        "portability": portability("command-center/export/bp-pln-04.bundle.json"),
        "lineage": lineage(
            [
                ("workflows/codex-auth-research-fanout.mjs", "REPAIR"),
                ("skills/workflow-authoring", "COMPOSE"),
                ("skills/strategic-compact", "COMPOSE"),
                ("rules/common/fan-out-contract.md#C1", "REBUILD-FROM-SPEC"),
                ("09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-04", "REBUILD-FROM-SPEC"),
            ],
            rollback=["workflows/codex-auth-research-fanout.mjs@current"],
        ),
        "outputs": {
            "state": artifact(
                "command-center/checkpoints/pln04-state.json",
                schema("completion-census"),
                min_bytes=128,
                consumers=["the resume planner", "the owner"],
            ),
            "resume_plan": artifact(
                "command-center/checkpoints/pln04-resume.json",
                schema("idempotency-report"),
                min_bytes=128,
                consumers=["the orchestrator on restart"],
            ),
        },
        "x_extensions": {
            "design_card": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-PLN-04 (doc-order 36 of 96)",
            "distinguishing_mechanism": (
                "completion is a POSTCONDITION on the artifact evaluated by a party that never "
                "reads the transcript, plus the pipeline carve-out. BP-INC-03 RECOVERS a run that "
                "already died without checkpoints; this prevents the loss in the first place."
            ),
            "repairs_over_source": [
                "the write-as-you-go mandate, referenced as a shared subworkflow rather than restated",
                "the explicit carve-out that a resumable boundary is never wrapped in a pipeline, because a stopped pipeline re-runs its first stage",
            ],
            "unverified_inline": (
                "UNVERIFIED that the pipeline first-stage-rerun defect still behaves as recorded on "
                "the current runtime; this blueprint carves around it unconditionally, which is "
                "safe either way. Settling experiment: wrap one unit in a pipeline, stop it, resume, "
                "and observe whether stage one re-runs - a both-states probe, not a single reading."
            ),
            "worked_example": {
                "name": "an UNKNOWN marker keeps a unit out of the skip set",
                "narrative": (
                    "Three units have artifacts on disk. u1 is fully measured and large enough: "
                    "COMPLETE, and a resume must skip it. u2 parses and is large enough but still "
                    "carries 'UNKNOWN - not yet measured': it is PARTIAL and must be re-run, which "
                    "is the exact case where a transcript-based check would wrongly skip it. u3 is "
                    "a two-byte stub: below the floor, so PARTIAL."
                ),
                "mechanism": "mechanisms.unit_complete + mechanisms.resume_plan",
                "input": {
                    "min_bytes": 32,
                    "artifacts": {
                        "u1": "measured: pairs=12 groups=3 isolation=worktree; all rows measured and cited.",
                        "u2": "pairs=12; groups: UNKNOWN - not yet measured; isolation: UNKNOWN - not yet measured.",
                        "u3": "ok",
                    },
                },
                "expected": {"skip": ["u1"], "run": ["u2", "u3"]},
                "controls": [
                    {
                        "mutate": "replace u2's UNKNOWN rows with measured values",
                        "expected_skip": ["u1", "u2"],
                        "why": "the marker, not the file size, is what held u2 back - removing it must move u2 into skip",
                    },
                    {
                        "mutate": "lower min_bytes to 1",
                        "expected_run_contains": "u2",
                        "why": "u2 must still be re-run on the marker alone, proving the two conditions are independent",
                    },
                ],
            },
        },
    }


BLUEPRINTS = [bp_pln_01, bp_pln_02, bp_pln_03, bp_pln_04]
SHARED = [sub_pairwise_overlap, sub_write_as_you_go]
