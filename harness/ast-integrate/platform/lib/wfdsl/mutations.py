"""The both-states mutation battery.

Every mutation is applied to the SAME valid document (``examples/wf-full-coverage.json``),
so a rejection is a one-variable experiment, not a comparison between two unrelated files.
A mutation declares which LAYER must catch it:

* ``schema``            - the draft 2020-12 document must reject it;
* ``semantic:<rule-id>`` - :mod:`wfdsl.semantics` must report that rule violated.

A mutation that nothing rejects is the interesting result: it means the capability it targets
is decorative. :func:`run_battery` reports survivors explicitly rather than counting them as
passes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from . import schemas, semantics


@dataclass(frozen=True)
class Mutation:
    id: str
    capability: str
    layer: str  # "schema" | "semantic:<RULE>"
    description: str
    apply: Callable[[dict[str, Any]], None]


def _m(doc: dict[str, Any]) -> dict[str, Any]:
    return doc


MUTATIONS: list[Mutation] = [
    # ---------------------------------------------------------------- stages
    Mutation(
        "MUT-STAGE-UNKNOWN-KIND",
        "stages",
        "schema",
        "a stage declares a kind the runner has no executor for",
        lambda d: d["stages"][0].__setitem__("kind", "magic"),
    ),
    Mutation(
        "MUT-STAGE-TYPO-KEY",
        "stages",
        "schema",
        "a stage carries a misspelled key (depends_ons) that would be silently ignored",
        lambda d: d["stages"][1].__setitem__("depends_ons", ["scope"]),
    ),
    # ---------------------------------------------------------------- roles
    Mutation(
        "MUT-ROLE-DANGLING",
        "roles",
        "semantic:DSL-SEM-004",
        "a stage names a role that was never declared",
        lambda d: d["stages"][0].__setitem__("role", "ghost-analyst"),
    ),
    # ---------------------------------------------------------------- gates
    Mutation(
        "MUT-GATE-NO-CONDITIONS",
        "gates",
        "schema",
        "a gate claims the 12-condition completion predicate but names no conditions",
        lambda d: d["gates"]["unit-complete"].pop("conditions_required"),
    ),
    Mutation(
        "MUT-GATE-DANGLING-REF",
        "gates",
        "semantic:DSL-SEM-005",
        "a gate stage references a gate id that does not exist",
        lambda d: d["stages"][5].__setitem__("gate_ref", "no-such-gate"),
    ),
    # ---------------------------------------------------------------- tools
    Mutation(
        "MUT-TOOL-COMMA-PACKED",
        "tools",
        "schema",
        "two MCP tool ids packed into one array element, which a per-token permission check would treat as one unknown tool",
        lambda d: d["tool_policy"]["allow"].append(
            "mcp__context7__query-docs,mcp__context7__resolve-library-id"
        ),
    ),
    Mutation(
        "MUT-TOOL-NOT-ALLOWED",
        "tools",
        "semantic:DSL-SEM-011",
        "a role requests a tool the deny-by-default policy never allowed",
        lambda d: d["roles"]["researcher"]["tool_permissions"].append(
            "mcp__cloud-hub__modal_sandbox_exec"
        ),
    ),
    # ---------------------------------------------------------------- params
    Mutation(
        "MUT-PARAM-REQUIRED-WITH-DEFAULT",
        "typed_params",
        "schema",
        "a param is required AND has a default - so it is never actually required",
        lambda d: d["params"]["question"].__setitem__("default", "anything"),
    ),
    Mutation(
        "MUT-PARAM-ENUM-NO-VALUES",
        "typed_params",
        "schema",
        "an enum param declares no allowed values, so no value can ever validate",
        lambda d: d["params"]["mode"].pop("enum"),
    ),
    Mutation(
        "MUT-PARAM-BAD-INLINE-SCHEMA",
        "typed_params",
        "semantic:DSL-SEM-010",
        "the inline JSON Schema escape hatch is not a valid schema",
        lambda d: d["params"]["custom_filter"].__setitem__(
            "schema", {"type": "not-a-json-type"}
        ),
    ),
    # ---------------------------------------------------------------- subworkflows
    Mutation(
        "MUT-SUBWF-DANGLING",
        "subworkflows",
        "semantic:DSL-SEM-006",
        "a subworkflow stage references a child workflow that is not declared",
        lambda d: d["stages"][3]["workflow"].__setitem__(
            "workflow_id", "not-declared-anywhere"
        ),
    ),
    # ---------------------------------------------------------------- fan-out
    Mutation(
        "MUT-FANOUT-NO-CONCURRENCY",
        "dynamic_fanout",
        "schema",
        "dynamic fan-out with no concurrency bound - the local-box-freeze failure mode",
        lambda d: d["stages"][1].pop("max_concurrency"),
    ),
    Mutation(
        "MUT-FANOUT-PARAM-UNDECLARED",
        "dynamic_fanout",
        "semantic:DSL-SEM-012",
        "fan-out iterates a param that does not exist, so it silently fans out over nothing",
        lambda d: d["stages"][1]["over"].__setitem__("ref", "not_a_param"),
    ),
    # ---------------------------------------------------------------- barriers
    Mutation(
        "MUT-BARRIER-QUORUM-NO-VALUE",
        "barriers",
        "schema",
        "a quorum barrier without a quorum value",
        lambda d: d["stages"][1]["barrier"].pop("quorum"),
    ),
    Mutation(
        "MUT-BARRIER-NO-PARTIAL-POLICY",
        "barriers",
        "schema",
        "a barrier with no partial-result policy silently drops every straggler's work",
        lambda d: d["stages"][2]["barrier"].pop("on_partial"),
    ),
    # ---------------------------------------------------------------- loops
    Mutation(
        "MUT-LOOP-NO-MAX-ITER",
        "loops_with_convergence",
        "schema",
        "a convergence loop with no iteration bound can spin forever when the metric never moves",
        lambda d: d["stages"][4]["convergence"].pop("max_iterations"),
    ),
    Mutation(
        "MUT-LOOP-UNDECLARED-METRIC",
        "loops_with_convergence",
        "semantic:DSL-SEM-008",
        "the convergence rule reads a metric nothing produces, so it can never become true",
        lambda d: d["stages"][4]["convergence"].__setitem__(
            "converged_when", "unmeasured_vibes >= 0.9 AND evidence_saturation == true"
        ),
    ),
    # ---------------------------------------------------------------- human checkpoints
    Mutation(
        "MUT-HC-NO-ON-TIMEOUT",
        "human_checkpoints",
        "schema",
        "a human checkpoint with no timeout behaviour hangs the workflow forever",
        lambda d: d["stages"][8].pop("on_timeout"),
    ),
    Mutation(
        "MUT-HC-NO-TIMEOUT-SECONDS",
        "human_checkpoints",
        "schema",
        "an on_timeout policy with no timeout to trigger it",
        lambda d: d["stages"][8].pop("timeout_seconds"),
    ),
    # ---------------------------------------------------------------- retries
    Mutation(
        "MUT-RETRY-NO-MAX-ATTEMPTS",
        "retries",
        "schema",
        "a retrying strategy with no attempt bound",
        lambda d: d["retry_policy"].pop("max_attempts"),
    ),
    Mutation(
        "MUT-RETRY-TWOSTRIKES-NO-PIVOT",
        "retries",
        "schema",
        "two-strikes-then-pivot with no pivot declared is just a retry wearing the label",
        lambda d: d["retry_policy"].pop("pivot"),
    ),
    # ---------------------------------------------------------------- repair loops
    Mutation(
        "MUT-REPAIR-NO-VERIFY",
        "repair_loops",
        "schema",
        "a repair loop with no independent verify stage reports its own success",
        lambda d: d["stages"][6].pop("verify"),
    ),
    Mutation(
        "MUT-REPAIR-DANGLING-TARGET",
        "repair_loops",
        "semantic:DSL-SEM-009",
        "a repair loop targets a stage that does not exist, so it repairs nothing",
        lambda d: d["stages"][6].__setitem__("target", ["stage-that-never-existed"]),
    ),
    # ---------------------------------------------------------------- resume
    Mutation(
        "MUT-RESUME-NO-STORE",
        "resume",
        "schema",
        "resume enabled with no durable checkpoint store - a re-run that duplicates work",
        lambda d: d["resume"].pop("checkpoint_store"),
    ),
    # ---------------------------------------------------------------- replay
    Mutation(
        "MUT-REPLAY-NO-SEED",
        "deterministic_replay",
        "schema",
        "deterministic replay claimed without a seed",
        lambda d: d["replay"].pop("seed"),
    ),
    # ---------------------------------------------------------------- cache
    Mutation(
        "MUT-CACHE-NO-KEY",
        "artifact_caching",
        "schema",
        "caching enabled with no cache key - every run either always hits or always misses",
        lambda d: d["cache"].pop("key_from"),
    ),
    # ---------------------------------------------------------------- dry-run
    Mutation(
        "MUT-DRYRUN-UNSUPPORTED",
        "dry_run",
        "schema",
        "a workflow that opts out of dry-run",
        lambda d: d["dry_run"].__setitem__("supported", False),
    ),
    # ---------------------------------------------------------------- estimate
    Mutation(
        "MUT-ESTIMATE-MEASURED-NO-SOURCE",
        "cost_estimate",
        "schema",
        "an estimate labelled historical-measured that names no measurement",
        lambda d: d["estimate"].pop("measurement_source"),
    ),
    Mutation(
        "MUT-ESTIMATE-IRREVERSIBLE-NO-APPROVAL",
        "cost_estimate",
        "schema",
        "an irreversible workflow that does not require owner approval",
        lambda d: d["estimate"]["impact"].update(
            {"reversibility": "irreversible", "requires_owner_approval": False}
        ),
    ),
    # ---------------------------------------------------------------- model routing
    Mutation(
        "MUT-ROUTING-NO-DEFAULT",
        "model_routing",
        "schema",
        "model routing with no default target - a request matching no route has nowhere to go",
        lambda d: d["model_routing"].pop("default"),
    ),
    # ---------------------------------------------------------------- failure policy
    Mutation(
        "MUT-FAILPOLICY-SILENT",
        "failure_policy",
        "schema",
        "a failure policy that opts out of the terminal-state requirement (silent failure)",
        lambda d: d["failure_policy"].__setitem__("terminal_state_required", False),
    ),
    # ---------------------------------------------------------------- export / import
    Mutation(
        "MUT-EXPORT-SECRETS-NOT-REDACTED",
        "export_import",
        "schema",
        "an export bundle that does not redact secrets",
        lambda d: d["portability"]["export"].__setitem__("redact_secrets", False),
    ),
    Mutation(
        "MUT-IMPORT-MIGRATE-NO-MIGRATIONS",
        "export_import",
        "schema",
        "import promises to migrate on a version mismatch but declares no migration",
        lambda d: d["portability"]["import"].pop("migrations"),
    ),
    # ---------------------------------------------------------------- work-unit binding
    Mutation(
        "MUT-TASK-NO-WORK-UNIT",
        "work_unit_binding",
        "schema",
        "a task stage that carries neither an inline work unit nor a reference",
        lambda d: d["stages"][0].pop("work_unit"),
    ),
    Mutation(
        "MUT-TASK-WORK-UNIT-MISSING-FIELD",
        "work_unit_binding",
        "schema",
        "an inline work unit that drops one of the 19 mandated fields (evidence_requirement)",
        lambda d: d["stages"][0]["work_unit"].pop("evidence_requirement"),
    ),
    # ---------------------------------------------------------------- expressions
    Mutation(
        "MUT-EXPR-UNPARSEABLE",
        "stopping_rules",
        "semantic:DSL-SEM-007",
        "a stopping rule that cannot parse can never fire, yet a schema sees a non-empty string",
        lambda d: d["stopping_rules"][0].__setitem__(
            "expression", "unique_ideas >>>= AND"
        ),
    ),
    # ---------------------------------------------------------------- source policy
    Mutation(
        "MUT-SOURCE-FETCHED-AS-INSTRUCTIONS",
        "source_policy",
        "schema",
        "a workflow that opts out of treating fetched content as untrusted data",
        lambda d: d["tool_policy"]["source_policy"].__setitem__(
            "treat_fetched_content_as_data", False
        ),
    ),
    # ---------------------------------------------------------------- lineage
    Mutation(
        "MUT-LINEAGE-BAD-RELATION",
        "lineage",
        "schema",
        "a lineage edge using a disposition outside the spec's vocabulary",
        lambda d: d["lineage"]["derived_from"][0].__setitem__(
            "relation", "BORROWED-VIBES"
        ),
    ),
]

MUTATION_IDS: frozenset[str] = frozenset(m.id for m in MUTATIONS)


def mutate(base: dict[str, Any], mutation: Mutation) -> dict[str, Any]:
    """Deep-copy ``base`` and apply exactly one mutation."""
    doc = copy.deepcopy(base)
    mutation.apply(doc)
    return doc


def _semantic_violations(doc: dict[str, Any]) -> dict[str, int]:
    return {r.rule: len(r.violations) for r in semantics.check_workflow(doc)}


def run_battery(base: dict[str, Any]) -> dict[str, Any]:
    """Apply every mutation and report, per mutation, whether the declared layer caught it."""
    validator = schemas.workflow_validator()
    base_schema_errors = sorted(
        validator.iter_errors(base), key=lambda e: list(e.absolute_path)
    )
    base_sem = _semantic_violations(base)

    results: list[dict[str, Any]] = []
    survivors: list[str] = []
    wrong_layer: list[str] = []
    for mut in MUTATIONS:
        doc = mutate(base, mut)
        schema_errors = schemas.error_summary(
            sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        )
        sem = _semantic_violations(doc)
        new_sem = {
            rule: count for rule, count in sem.items() if count > base_sem.get(rule, 0)
        }
        if mut.layer == "schema":
            caught_by_declared = bool(schema_errors)
        else:
            rule = mut.layer.split(":", 1)[1]
            caught_by_declared = new_sem.get(rule, 0) > 0
        caught_at_all = bool(schema_errors) or bool(new_sem)
        if not caught_at_all:
            survivors.append(mut.id)
        elif not caught_by_declared:
            wrong_layer.append(mut.id)
        results.append(
            {
                "id": mut.id,
                "capability": mut.capability,
                "declared_layer": mut.layer,
                "description": mut.description,
                "caught_by_declared_layer": caught_by_declared,
                "caught_at_all": caught_at_all,
                "schema_errors": schema_errors[:3],
                "new_semantic_violations": new_sem,
            }
        )

    return {
        "base_document_valid": not base_schema_errors,
        "base_schema_errors": schemas.error_summary(base_schema_errors),
        "base_semantic_violations": {k: v for k, v in base_sem.items() if v},
        "mutations": len(MUTATIONS),
        "caught_by_declared_layer": sum(
            1 for r in results if r["caught_by_declared_layer"]
        ),
        "caught_at_all": sum(1 for r in results if r["caught_at_all"]),
        "survivors": survivors,
        "caught_but_wrong_layer": wrong_layer,
        "results": results,
    }
