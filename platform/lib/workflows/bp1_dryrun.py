"""Deterministic dry-run planner for Workflow-DSL v1 documents.

WHY THIS EXISTS
    ``platform/schema/workflow-dsl.schema.json`` declares a ``dry_run`` capability whose
    ``emits`` may promise ``plan`` / ``estimate`` / ``permission-report`` / ``graph``. Until
    something actually PRODUCES those four things the promise is decorative, and a blueprint
    that only ever gets fed to a JSON-Schema validator is a document, not an executable
    artifact. This module is the reference producer: given a blueprint plus a parameter
    binding it type-checks the params, walks the stage DAG, and emits the promised plan.

    It is also what makes a per-blueprint MUTATION control meaningful. A schema rejection
    proves the schema works; a planner whose computed stage order stops matching the
    blueprint's own declared ``x_extensions.worked_example.expected_stage_order`` proves
    THAT BLUEPRINT's topology is load-bearing.

DESIGN RULES
    * DETERMINISTIC. Topological order breaks ties by DECLARATION order, never by set or
      dict iteration order, and nothing here reads the clock, a RNG, the environment, or
      the filesystem. Two runs on the same document are byte-identical.
    * FAIL CLOSED. An unknown identifier in a ``when`` expression, a param that violates its
      declared type, an unbounded fan-out, a dependency cycle: each raises. Nothing degrades
      to "probably fine".
    * SECRETS NEVER TRAVEL. A param declared ``secret`` (or typed ``secret_ref``) is replaced
      by an opaque ``<secret_ref:NAME>`` token before it can reach a plan, a graph, or a
      permission report, so serialising the report cannot leak the value.
    * NOT AN ORCHESTRATION RUNTIME. It executes nothing, spawns nothing and calls no tool -
      it plans. (Anti-overfit anchor: no second runtime is introduced.)

AUTHORSHIP NOTE
    First authored by the ``blueprints/bp-1`` unit and deliberately named with a ``bp1_``
    prefix so a sibling blueprint unit writing into this same directory cannot clobber it.
    It is generic over any Workflow-DSL v1 document; if a sibling ships an equivalent
    planner these should be consolidated into one shared module.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

LIB_ROOT = Path(__file__).resolve().parents[1]
if str(LIB_ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(LIB_ROOT))

from wfdsl import expr as _expr  # noqa: E402

__all__ = [
    "PlanError",
    "ParamError",
    "TopologyError",
    "PlanStep",
    "Plan",
    "bind_params",
    "plan_workflow",
    "dry_run_report",
    "check_stopping_rules",
    "unbounded_constructs",
    "requested_tools",
    "denied_tool_requests",
    "declared_artifacts",
    "declared_schema_refs",
]


class PlanError(Exception):
    """Base: the document could not be planned. Never downgraded to a warning."""


class ParamError(PlanError):
    """A parameter binding violates the blueprint's declared param contract."""


class TopologyError(PlanError):
    """The stage graph cannot be ordered (cycle, or a dangling depends_on)."""


# --------------------------------------------------------------------------- params

_SIMPLE_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "path": (str,),
    "enum": (str, int, float, bool),
    "secret_ref": (str,),
    "workflow_ref": (str,),
    "unit_id": (str,),
}

_SECRET_MASK = "<secret_ref:{name}>"


def _is_secret(spec: Mapping[str, Any]) -> bool:
    return bool(spec.get("secret")) or spec.get("type") == "secret_ref"


def _check_one(name: str, spec: Mapping[str, Any], value: Any) -> None:
    declared = str(spec.get("type"))
    allowed = _SIMPLE_TYPES.get(declared)
    if allowed is None:
        raise ParamError(f"param {name!r} declares unknown type {declared!r}")
    # JSON has one number tower but bool is an int in Python; a boolean passed where an
    # integer is declared is a real defect, not a coercion.
    if declared in {"integer", "number"} and isinstance(value, bool):
        raise ParamError(f"param {name!r} is {declared} but got boolean {value!r}")
    if not isinstance(value, allowed):
        raise ParamError(
            f"param {name!r} is declared {declared} but got {type(value).__name__}"
        )
    if declared == "path" and ("\\" in value or ".." in value):
        raise ParamError(
            f"param {name!r} is a path and must be repo-relative with forward slashes: {value!r}"
        )
    if "enum" in spec and value not in spec["enum"]:
        raise ParamError(f"param {name!r}={value!r} is not one of {spec['enum']}")
    if "pattern" in spec and isinstance(value, str):
        if re.search(str(spec["pattern"]), value) is None:
            raise ParamError(
                f"param {name!r}={value!r} fails pattern {spec['pattern']!r}"
            )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            raise ParamError(f"param {name!r}={value} < minimum {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise ParamError(f"param {name!r}={value} > maximum {spec['maximum']}")
    if isinstance(value, str):
        if "min_length" in spec and len(value) < spec["min_length"]:
            raise ParamError(
                f"param {name!r} length {len(value)} < min_length {spec['min_length']}"
            )
        if "max_length" in spec and len(value) > spec["max_length"]:
            raise ParamError(
                f"param {name!r} length {len(value)} > max_length {spec['max_length']}"
            )
    if isinstance(value, list):
        if "min_items" in spec and len(value) < spec["min_items"]:
            raise ParamError(
                f"param {name!r} has {len(value)} items < min_items {spec['min_items']}"
            )
        if "max_items" in spec and len(value) > spec["max_items"]:
            raise ParamError(
                f"param {name!r} has {len(value)} items > max_items {spec['max_items']}"
            )
        item_spec = spec.get("items")
        if isinstance(item_spec, Mapping):
            for i, item in enumerate(value):
                _check_one(f"{name}[{i}]", item_spec, item)


def bind_params(
    doc: Mapping[str, Any], supplied: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Type-check ``supplied`` against ``doc['params']`` and return the resolved binding.

    Secret params are masked in the RETURNED binding, so any downstream artifact derived
    from it carries the reference name only. Raises :class:`ParamError` on any violation,
    including an unknown param name (a typo'd param is silently ignored otherwise, which is
    how a run "succeeds" against a default nobody intended).
    """
    supplied = dict(supplied or {})
    specs: Mapping[str, Any] = doc.get("params") or {}
    unknown = sorted(set(supplied) - set(specs))
    if unknown:
        raise ParamError(f"unknown param(s) {unknown}; declared {sorted(specs)}")

    resolved: dict[str, Any] = {}
    for name in sorted(specs):
        spec = specs[name]
        if not isinstance(spec, Mapping):
            raise ParamError(f"param {name!r} spec is not an object")
        if name in supplied:
            value = supplied[name]
            _check_one(name, spec, value)
        elif "default" in spec:
            value = spec["default"]
            _check_one(name, spec, value)
        elif spec.get("required"):
            raise ParamError(f"required param {name!r} was not supplied")
        else:
            continue
        resolved[name] = _SECRET_MASK.format(name=name) if _is_secret(spec) else value
    return resolved


# ------------------------------------------------------------------------- topology


def _topo_order(
    stages: Sequence[Mapping[str, Any]], scope: str
) -> list[Mapping[str, Any]]:
    """Kahn ordering with a DECLARATION-order tie-break (so the result is deterministic)."""
    ids = [str(s.get("id")) for s in stages]
    position = {sid: i for i, sid in enumerate(ids)}
    if len(position) != len(ids):
        dupes = sorted({sid for sid in ids if ids.count(sid) > 1})
        raise TopologyError(f"{scope}: duplicate stage id(s) {dupes}")

    deps: dict[str, list[str]] = {}
    for stage in stages:
        sid = str(stage.get("id"))
        want = [str(d) for d in (stage.get("depends_on") or [])]
        missing = [d for d in want if d not in position]
        if missing:
            raise TopologyError(
                f"{scope}:{sid} depends_on {missing} which is not in this scope {ids}"
            )
        deps[sid] = want

    remaining = dict(deps)
    ordered: list[str] = []
    while remaining:
        ready = sorted(
            (sid for sid, want in remaining.items() if not set(want) & set(remaining)),
            key=lambda s: position[s],
        )
        if not ready:
            raise TopologyError(f"{scope}: dependency cycle among {sorted(remaining)}")
        for sid in ready:
            ordered.append(sid)
            del remaining[sid]

    by_id = {str(s.get("id")): s for s in stages}
    return [by_id[sid] for sid in ordered]


# ---------------------------------------------------------------------------- plan


@dataclass(frozen=True)
class PlanStep:
    stage_id: str
    kind: str
    scope: str
    depth: int
    role: str | None = None
    concurrency: int | None = None
    max_iterations: int | None = None
    barrier_mode: str | None = None
    gate_predicate: str | None = None
    tools: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    skipped_by_when: bool = False

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "scope": self.scope,
            "depth": self.depth,
        }
        for key in (
            "role",
            "concurrency",
            "max_iterations",
            "barrier_mode",
            "gate_predicate",
        ):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.tools:
            out["tools"] = list(self.tools)
        if self.produces:
            out["produces"] = list(self.produces)
        if self.skipped_by_when:
            out["skipped_by_when"] = True
        return out


@dataclass
class Plan:
    workflow_id: str
    workflow_version: str
    params: dict[str, Any] = field(default_factory=dict)
    steps: list[PlanStep] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    # ---- derived views a caller (or a test) can assert on
    @property
    def stage_order(self) -> list[str]:
        """Top-level stage ids in execution order (bodies excluded)."""
        return [s.stage_id for s in self.steps if s.scope == "/stages"]

    @property
    def all_stage_ids(self) -> list[str]:
        return [s.stage_id for s in self.steps]

    @property
    def executed_stage_order(self) -> list[str]:
        return [
            s.stage_id
            for s in self.steps
            if s.scope == "/stages" and not s.skipped_by_when
        ]

    @property
    def skipped(self) -> list[str]:
        return [s.stage_id for s in self.steps if s.skipped_by_when]

    @property
    def gates(self) -> list[PlanStep]:
        return [s for s in self.steps if s.kind == "gate"]

    @property
    def barriers(self) -> list[PlanStep]:
        return [s for s in self.steps if s.barrier_mode is not None]

    @property
    def human_checkpoints(self) -> list[PlanStep]:
        return [s for s in self.steps if s.kind == "human_checkpoint"]

    @property
    def max_parallel(self) -> int:
        """Peak declared concurrency: 1 when nothing fans out."""
        return max([1] + [s.concurrency for s in self.steps if s.concurrency])

    @property
    def artifacts(self) -> list[str]:
        seen: list[str] = []
        for step in self.steps:
            for path in step.produces:
                if path not in seen:
                    seen.append(path)
        return seen

    def kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for step in self.steps:
            counts[step.kind] = counts.get(step.kind, 0) + 1
        return dict(sorted(counts.items()))

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "params": self.params,
            "stage_order": self.stage_order,
            "skipped": self.skipped,
            "max_parallel": self.max_parallel,
            "kinds": self.kinds(),
            "artifacts": self.artifacts,
            "steps": [s.to_json() for s in self.steps],
            "edges": [list(e) for e in self.edges],
        }


def _produces_paths(stage: Mapping[str, Any]) -> tuple[str, ...]:
    out: list[str] = []
    for art in stage.get("produces") or []:
        if isinstance(art, Mapping) and art.get("path"):
            out.append(str(art["path"]))
    decision = stage.get("decision_artifact")
    if isinstance(decision, Mapping) and decision.get("path"):
        out.append(str(decision["path"]))
    return tuple(out)


def _eval_when(stage: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    rule = stage.get("when")
    if rule is None:
        return True
    try:
        return bool(_expr.evaluate(rule, dict(context)))
    except _expr.ExpressionError as exc:
        raise PlanError(
            f"stage {stage.get('id')!r}: `when` could not be evaluated: {exc}. "
            "Supply the fact in `facts=` - a condition that cannot be evaluated must not "
            "default to true."
        ) from exc


def plan_workflow(
    doc: Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
) -> Plan:
    """Type-check params, order every stage scope, and emit a deterministic plan."""
    if str(doc.get("dsl_version", "")).split(".")[0] != "1":
        raise PlanError(f"unsupported dsl_version {doc.get('dsl_version')!r}")
    bound = bind_params(doc, params)
    context: dict[str, Any] = {**bound, **dict(facts or {})}
    plan = Plan(
        workflow_id=str(doc.get("id")),
        workflow_version=str(doc.get("version")),
        params=dict(bound),
    )

    def walk(stages: Any, scope: str, depth: int, inherited_skip: bool) -> None:
        if not isinstance(stages, list) or not stages:
            raise PlanError(f"{scope}: expected a non-empty stage list")
        ordered = _topo_order([s for s in stages if isinstance(s, Mapping)], scope)
        previous: str | None = None
        for stage in ordered:
            sid = str(stage.get("id"))
            kind = str(stage.get("kind"))
            skipped = inherited_skip or not _eval_when(stage, context)
            gate = stage.get("gate")
            barrier = stage.get("barrier")
            plan.steps.append(
                PlanStep(
                    stage_id=sid,
                    kind=kind,
                    scope=scope,
                    depth=depth,
                    role=str(stage["role"]) if stage.get("role") else None,
                    concurrency=(
                        int(stage["max_concurrency"])
                        if stage.get("max_concurrency") is not None
                        else None
                    ),
                    max_iterations=(
                        int(stage["convergence"]["max_iterations"])
                        if isinstance(stage.get("convergence"), Mapping)
                        else None
                    ),
                    barrier_mode=(
                        str(barrier["mode"]) if isinstance(barrier, Mapping) else None
                    ),
                    gate_predicate=(
                        str(gate["predicate"])
                        if isinstance(gate, Mapping)
                        else (str(stage["gate_ref"]) if stage.get("gate_ref") else None)
                    ),
                    tools=tuple(str(t) for t in (stage.get("tool_permissions") or [])),
                    produces=_produces_paths(stage),
                    skipped_by_when=skipped,
                )
            )
            for dep in stage.get("depends_on") or []:
                plan.edges.append((str(dep), sid))
            if previous is not None and not (stage.get("depends_on") or []):
                pass  # an independent stage gets no synthetic edge: parallelism is real
            previous = sid

            if kind in {"fanout", "loop"} and isinstance(stage.get("body"), list):
                walk(stage["body"], f"{scope}/{sid}/body", depth + 1, skipped)
            if kind == "repair_loop":
                for slot in ("diagnose", "repair", "verify"):
                    sub = stage.get(slot)
                    if isinstance(sub, Mapping):
                        walk([sub], f"{scope}/{sid}/{slot}", depth + 1, skipped)

    walk(doc.get("stages"), "/stages", 0, False)
    return plan


# ------------------------------------------------------------------- policy surfaces


def requested_tools(doc: Mapping[str, Any]) -> list[str]:
    """Every tool token any role or any stage in the document asks for."""
    out: list[str] = []

    def add(tokens: Any) -> None:
        for token in tokens or []:
            text = str(token)
            if text not in out:
                out.append(text)

    for spec in (doc.get("roles") or {}).values():
        if isinstance(spec, Mapping):
            add(spec.get("tool_permissions"))

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            add(stage.get("tool_permissions"))
            if isinstance(stage.get("body"), list):
                walk(stage["body"])
            for slot in ("diagnose", "repair", "verify"):
                if isinstance(stage.get(slot), Mapping):
                    walk([stage[slot]])
            unit = stage.get("work_unit")
            if isinstance(unit, Mapping):
                add(unit.get("tool_permissions"))

    walk(doc.get("stages"))
    return out


def denied_tool_requests(doc: Mapping[str, Any]) -> list[tuple[str, str]]:
    """``(tool, reason)`` for every requested tool the tool_policy does not permit.

    This is the independent second signal on DSL-SEM-011: the validator walks roles and
    stages, this also walks the inline work units. An empty list from BOTH is the claim.
    """
    policy = doc.get("tool_policy") or {}
    default_deny = str(policy.get("default", "deny")) == "deny"
    allow = {str(t) for t in (policy.get("allow") or [])}
    deny = {str(t) for t in (policy.get("deny") or [])}
    out: list[tuple[str, str]] = []
    for token in requested_tools(doc):
        if token in deny:
            out.append((token, "explicitly denied by tool_policy.deny"))
        elif default_deny and token not in allow:
            out.append(
                (token, "absent from tool_policy.allow under a deny-by-default policy")
            )
    return out


def declared_artifacts(doc: Mapping[str, Any]) -> list[dict[str, str]]:
    """Every declared artifact: stage ``produces``, ``decision_artifact``, and ``outputs``."""
    rows: list[dict[str, str]] = []

    def add(where: str, art: Any) -> None:
        if isinstance(art, Mapping) and art.get("path") and art.get("schema_ref"):
            rows.append(
                {
                    "where": where,
                    "path": str(art["path"]),
                    "schema_ref": str(art["schema_ref"]),
                }
            )

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            sid = str(stage.get("id"))
            for art in stage.get("produces") or []:
                add(f"stage:{sid}", art)
            add(f"stage:{sid}/decision_artifact", stage.get("decision_artifact"))
            if isinstance(stage.get("body"), list):
                walk(stage["body"])
            for slot in ("diagnose", "repair", "verify"):
                if isinstance(stage.get(slot), Mapping):
                    walk([stage[slot]])

    walk(doc.get("stages"))
    for name, art in (doc.get("outputs") or {}).items():
        add(f"outputs:{name}", art)
    return rows


def declared_schema_refs(doc: Mapping[str, Any]) -> list[str]:
    """Deduped, declaration-ordered list of every schema reference the document names."""
    refs: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in refs:
            refs.append(value)

    for row in declared_artifacts(doc):
        add(row["schema_ref"])

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            unit = stage.get("work_unit")
            if isinstance(unit, Mapping):
                add(unit.get("output_schema"))
            if isinstance(stage.get("body"), list):
                walk(stage["body"])
            for slot in ("diagnose", "repair", "verify"):
                if isinstance(stage.get(slot), Mapping):
                    walk([stage[slot]])

    walk(doc.get("stages"))
    return refs


def unbounded_constructs(doc: Mapping[str, Any]) -> list[str]:
    """Loops without a max_iterations and fan-outs without a max_concurrency.

    The schema already requires both. This is the mechanically independent re-check: a
    document that satisfies the schema and this function has two signals, not one.
    """
    bad: list[str] = []

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            sid = str(stage.get("id"))
            if stage.get("kind") == "fanout" and not stage.get("max_concurrency"):
                bad.append(f"{sid}: fanout without max_concurrency")
            if stage.get("kind") == "loop":
                conv = stage.get("convergence")
                if not isinstance(conv, Mapping) or not conv.get("max_iterations"):
                    bad.append(f"{sid}: loop without convergence.max_iterations")
            if stage.get("kind") == "repair_loop" and not stage.get("max_attempts"):
                bad.append(f"{sid}: repair_loop without max_attempts")
            if stage.get("kind") == "human_checkpoint" and not stage.get("on_timeout"):
                bad.append(f"{sid}: human_checkpoint without on_timeout")
            if isinstance(stage.get("body"), list):
                walk(stage["body"])
            for slot in ("diagnose", "repair", "verify"):
                if isinstance(stage.get(slot), Mapping):
                    walk([stage[slot]])

    walk(doc.get("stages"))
    return bad


def check_stopping_rules(
    doc: Mapping[str, Any], context: Mapping[str, Any], applies_to: str | None = None
) -> dict[str, Any]:
    """Evaluate every stopping rule (workflow-level and council-level) against ``context``.

    ``minimum_conditions`` is a FLOOR: a rule whose floor is unmet cannot fire even when its
    own expression is true (spec 10762). Rules are reported in declaration order.
    """
    rows: list[dict[str, Any]] = []

    def consider(rule: Any, where: str) -> None:
        if not isinstance(rule, Mapping):
            return
        scope = str(rule.get("applies_to", "workflow"))
        if applies_to is not None and scope != applies_to:
            return
        row: dict[str, Any] = {
            "id": str(rule.get("id")),
            "where": where,
            "applies_to": scope,
            "on_stop": str(rule.get("on_stop", "complete")),
        }
        try:
            row["expression_true"] = bool(
                _expr.evaluate(rule.get("expression"), dict(context))
            )
        except _expr.ExpressionError as exc:
            row["expression_true"] = None
            row["error"] = str(exc)
        floor = rule.get("minimum_conditions")
        if floor is None:
            row["floor_met"] = True
        else:
            try:
                row["floor_met"] = bool(_expr.evaluate(floor, dict(context)))
            except _expr.ExpressionError as exc:
                row["floor_met"] = None
                row["error"] = str(exc)
        row["fires"] = bool(row["expression_true"]) and bool(row["floor_met"])
        rows.append(row)

    for rule in doc.get("stopping_rules") or []:
        consider(rule, "workflow")

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            for rule in stage.get("stopping_rules") or []:
                consider(rule, f"stage:{stage.get('id')}")
            if isinstance(stage.get("body"), list):
                walk(stage["body"])

    walk(doc.get("stages"))
    return {
        "rules": rows,
        "fired": [r["id"] for r in rows if r["fires"]],
        "blocked_by_floor": [
            r["id"] for r in rows if r["expression_true"] and not r["floor_met"]
        ],
        "errors": [r for r in rows if r.get("error")],
    }


def dry_run_report(
    doc: Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit exactly what ``dry_run.emits`` promises: plan, estimate, permissions, graph."""
    dry = doc.get("dry_run") or {}
    if dry.get("supported") is not True:
        raise PlanError(
            f"{doc.get('id')!r} does not declare dry_run.supported: true - the spec requires "
            "every workflow to be dry-runnable"
        )
    plan = plan_workflow(doc, params, facts)
    policy = doc.get("tool_policy") or {}
    report: dict[str, Any] = {
        "workflow_id": plan.workflow_id,
        "workflow_version": plan.workflow_version,
        "emits": list(dry.get("emits") or []),
        "side_effect_free": bool(dry.get("side_effect_free", True)),
        "plan": plan.to_json(),
        "estimate": dict(doc.get("estimate") or {}),
        "permission_report": {
            "default": str(policy.get("default", "deny")),
            "network": str(policy.get("network", "none")),
            "allow": list(policy.get("allow") or []),
            "deny": list(policy.get("deny") or []),
            "requested": requested_tools(doc),
            "requested_but_not_permitted": [
                {"tool": t, "reason": r} for t, r in denied_tool_requests(doc)
            ],
            "forbidden_in_dry_run": list(dry.get("forbid_tools") or []),
            "require_owner_approval": list(policy.get("require_owner_approval") or []),
        },
        "graph": {
            "nodes": plan.all_stage_ids,
            "edges": [list(e) for e in plan.edges],
        },
        "artifact_contract": declared_artifacts(doc),
        "unbounded_constructs": unbounded_constructs(doc),
    }
    return report


def secret_param_names(doc: Mapping[str, Any]) -> list[str]:
    return sorted(
        name
        for name, spec in (doc.get("params") or {}).items()
        if isinstance(spec, Mapping) and _is_secret(spec)
    )


def iter_work_units(doc: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    """``(stage_id, work_unit)`` for every inline work unit, at any nesting depth."""

    def walk(stages: Any):
        if not isinstance(stages, list):
            return
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            unit = stage.get("work_unit")
            if isinstance(unit, Mapping):
                yield str(stage.get("id")), unit
            if isinstance(stage.get("body"), list):
                yield from walk(stage["body"])
            for slot in ("diagnose", "repair", "verify"):
                if isinstance(stage.get(slot), Mapping):
                    yield from walk([stage[slot]])

    yield from walk(doc.get("stages"))
