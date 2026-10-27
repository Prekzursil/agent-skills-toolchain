"""Shared helpers for the bp-2 blueprint tests (blueprints 13-24, design cards BP-BRN-02..BP-REQ-02).

Scoped DELIBERATELY to this unit's twelve ids. Sibling units are writing into the same
``platform/workflows`` directory concurrently, so a glob-based test would go red on another
agent's half-written file and report a defect that is not ours. ``BP2_IDS`` is the whole
contract surface.

What lives here
---------------
* ``load(bp_id)``                  - parse one blueprint by id
* ``schema_errors`` / ``semantic`` - the two validation layers the DSL ships
* ``schema_ref_failures``          - every ``schema_ref`` / ``output_schema`` must RESOLVE AND
  COMPILE through ``platform/lib/schema_resolver.py``; a declared-but-dangling ref is exactly
  the P1 the substrate unit closed and a blueprint must not re-open it
* ``param_schema`` + ``worked_example_errors`` - compile the blueprint's OWN typed params into
  a draft-2020-12 schema and validate its worked examples against it, so a worked example is a
  checkable artifact rather than prose
* ``fingerprint``                  - a purely MECHANICAL structural signature used to prove
  material distinctness (stage-kind multiset, barrier modes, gate predicates, fan-out sources
  and concurrency, loop convergence shape, policy shape). No LLM judgement: an exact algorithm
  answers an exact question.
* ``assert_mutation_caught``       - the BOTH-STATES control. Asserts the unmutated document
  passes every layer AND that the mutated document is rejected by the declared layer. A probe
  that is silent in both states measures nothing, so each test proves its own detector fires.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_ROOT = REPO_ROOT / "platform" / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from jsonschema import Draft202012Validator  # noqa: E402

import schema_resolver as _resolver  # noqa: E402
from wfdsl import schemas as _schemas  # noqa: E402
from wfdsl import semantics as _semantics  # noqa: E402

WF_DIR = REPO_ROOT / "platform" / "workflows"

#: the twelve blueprints this unit owns, in design-card order (global indices 13-24 of 108)
BP2_IDS: dict[str, str] = {
    "bp-brn-02-diverge-then-converge": "bp-brn-02-diverge-then-converge.json",
    "bp-brn-03-constraint-inversion": "bp-brn-03-constraint-inversion.json",
    "bp-brn-04-analogy-transfer": "bp-brn-04-analogy-transfer.json",
    "bp-cnc-01-five-persona-design-council": "bp-cnc-01-five-persona-design-council.json",
    "bp-cnc-02-two-peer-cross-vendor-debate": "bp-cnc-02-two-peer-cross-vendor-debate.json",
    "bp-cnc-03-semantic-entropy-escalation": "bp-cnc-03-semantic-entropy-escalation.json",
    "bp-cnc-04-full-text-adversarial-sibling-review": "bp-cnc-04-full-text-adversarial-sibling-review.json",
    "bp-cnc-05-governance-decision-gate": "bp-cnc-05-governance-decision-gate.json",
    "bp-cnc-06-weighted-rubric-jury": "bp-cnc-06-weighted-rubric-jury.json",
    "bp-cnc-07-probe-wins-split-verdict-resolver": "bp-cnc-07-probe-wins-split-verdict-resolver.json",
    "bp-req-01-program-scale-extensive-grill": "bp-req-01-program-scale-extensive-grill.json",
    "bp-req-02-recursive-decision-ledger-walk": "bp-req-02-recursive-decision-ledger-walk.json",
}

FLAGSHIP_IDS: frozenset[str] = frozenset(
    {
        "bp-cnc-01-five-persona-design-council",
        "bp-cnc-03-semantic-entropy-escalation",
        "bp-cnc-04-full-text-adversarial-sibling-review",
        "bp-cnc-06-weighted-rubric-jury",
        "bp-cnc-07-probe-wins-split-verdict-resolver",
        "bp-req-01-program-scale-extensive-grill",
    }
)

#: the six spec categories (_USER-PROMPTS.md:10902-10907), slugified
SPEC_CATEGORIES: frozenset[str] = frozenset(
    {
        "research-and-evidence",
        "engineering-and-reliability",
        "security-governance-and-risk",
        "product-design-and-strategy",
        "data-science-knowledge-and-creative-work",
        "collective-intelligence-and-meta-workflows",
    }
)


def path_for(bp_id: str) -> Path:
    if bp_id not in BP2_IDS:
        raise KeyError(f"{bp_id!r} is not a bp-2 blueprint; known: {sorted(BP2_IDS)}")
    return WF_DIR / BP2_IDS[bp_id]


def load(bp_id: str) -> dict[str, Any]:
    return json.loads(path_for(bp_id).read_text(encoding="utf-8"))


def find_stage(doc: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """The LIVE stage dict inside ``doc`` (nested stages included), so a mutation sticks.

    Tests address stages by id rather than by list index on purpose: an index is a positional
    assumption that silently retargets when a stage is inserted, and a mutation control that
    quietly mutates the wrong stage is a detector failure wearing a green tick.
    """
    for _, st in _semantics.iter_stages(doc):
        if st.get("id") == stage_id:
            return st  # type: ignore[return-value]
    raise AssertionError(
        f"stage {stage_id!r} not found; have {[s.get('id') for _, s in _semantics.iter_stages(doc)]}"
    )


# ------------------------------------------------------------------ validation layers


def schema_errors(doc: dict[str, Any]) -> list[str]:
    errs = sorted(
        _schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    return _schemas.error_summary(errs, limit=10)


def semantic(doc: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(violations, advisories) as ``rule: subject -> detail`` strings."""
    viol: list[str] = []
    adv: list[str] = []
    for r in _semantics.check_workflow(doc):
        bucket = viol if r.severity == "violation" else adv
        for subject, detail in r.violations:
            bucket.append(f"{r.rule}: {subject} -> {detail}")
    return viol, adv


def iter_schema_refs(node: Any) -> list[str]:
    out: list[str] = []

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                if k in {"schema_ref", "output_schema"} and isinstance(v, str):
                    out.append(v)
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    return out


def schema_ref_failures(doc: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for ref in sorted(set(iter_schema_refs(doc))):
        try:
            _resolver.validator_for(ref)
        except Exception as exc:  # noqa: BLE001 - any failure is a dangling ref
            bad.append(f"{ref} -> {type(exc).__name__}: {str(exc)[:140]}")
    return bad


# ------------------------------------------------------- params -> JSON Schema compiler

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "path": "string",
    "secret_ref": "string",
    "workflow_ref": "string",
    "unit_id": "string",
}


def _compile_param(spec: dict[str, Any]) -> dict[str, Any]:
    """One DSL param_spec -> one draft-2020-12 subschema."""
    if isinstance(spec.get("schema"), dict):
        # the documented escape hatch: an inline JSON Schema wins outright
        return copy.deepcopy(spec["schema"])

    ptype = spec.get("type")
    out: dict[str, Any] = {}
    if ptype == "enum":
        out["enum"] = list(spec.get("enum", []))
        return out
    mapped = _TYPE_MAP.get(str(ptype))
    if mapped:
        out["type"] = mapped
    for src, dst in (
        ("min_length", "minLength"),
        ("max_length", "maxLength"),
        ("min_items", "minItems"),
        ("max_items", "maxItems"),
        ("minimum", "minimum"),
        ("maximum", "maximum"),
        ("pattern", "pattern"),
    ):
        if src in spec:
            out[dst] = spec[src]
    if isinstance(spec.get("items"), dict):
        out["items"] = _compile_param(spec["items"])
    if isinstance(spec.get("properties"), dict):
        out["properties"] = {
            k: _compile_param(v) for k, v in spec["properties"].items()
        }
    return out


def param_schema(doc: dict[str, Any]) -> dict[str, Any]:
    params = doc.get("params", {}) or {}
    required = [
        n for n, s in params.items() if isinstance(s, dict) and s.get("required")
    ]
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {n: _compile_param(s) for n, s in params.items()},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = sorted(required)
    return schema


def worked_examples(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return list((doc.get("x_extensions", {}) or {}).get("worked_examples", []) or [])


def worked_example_errors(doc: dict[str, Any]) -> list[str]:
    """Validate every worked example's params against the blueprint's own param contract.

    Returns a LIST, never raises. An uncompilable param contract (for instance a corrupted
    inline-schema escape hatch) is a finding to report, not an exception to propagate: a helper
    that throws makes every caller's both-states control crash instead of measuring, which is a
    detector failure rather than a finding.
    """
    try:
        schema = param_schema(doc)
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - report, do not propagate
        return [
            f"param contract does not compile: {type(exc).__name__}: {str(exc)[:200]}"
        ]
    validator = Draft202012Validator(schema)
    problems: list[str] = []
    examples = worked_examples(doc)
    if not examples:
        return ["no worked example present (the spec requires at least one)"]
    for i, ex in enumerate(examples):
        name = ex.get("name", f"example-{i}")
        if not isinstance(ex.get("params"), dict):
            problems.append(f"{name}: no params block")
            continue
        for err in sorted(
            validator.iter_errors(ex["params"]), key=lambda e: list(e.absolute_path)
        ):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            problems.append(
                f"{name}: params/{loc}: [{err.validator}] {err.message[:160]}"
            )
        for field in ("expected_terminal_state", "walkthrough"):
            if not str(ex.get(field, "")).strip():
                problems.append(f"{name}: missing {field}")
    return problems


def all_layer_failures(doc: dict[str, Any]) -> dict[str, list[str]]:
    viol, adv = semantic(doc)
    return {
        "schema": schema_errors(doc),
        "semantic": viol,
        "advisory": adv,
        "schema_refs": schema_ref_failures(doc),
        "worked_examples": worked_example_errors(doc),
    }


# ------------------------------------------------------------- structural fingerprint


def fingerprint(doc: dict[str, Any]) -> dict[str, Any]:
    """A MECHANICAL structural signature. Exact algorithm, no judgement.

    Two blueprints with the same fingerprint are structurally interchangeable, which is the
    operational meaning of "renamed copy". Distinctness is asserted over this, not over prose.
    """
    stages = [st for _, st in _semantics.iter_stages(doc)]
    kinds = Counter(str(st.get("kind")) for st in stages)

    barrier_modes: list[str] = []
    fanout_shape: list[str] = []
    loop_shape: list[str] = []
    for st in stages:
        b = st.get("barrier")
        if isinstance(b, dict):
            barrier_modes.append(f"{b.get('mode')}/{b.get('on_partial')}")
        if st.get("kind") == "fanout":
            over = st.get("over") or {}
            fanout_shape.append(
                f"{over.get('source')}:mc={st.get('max_concurrency')}:onfail={st.get('on_item_failure')}"
            )
        if st.get("kind") == "loop":
            conv = st.get("convergence") or {}
            body_kinds = ",".join(
                sorted(
                    str(b.get("kind"))
                    for b in (st.get("body") or [])
                    if isinstance(b, dict)
                )
            )
            loop_shape.append(
                f"max={conv.get('max_iterations')}:nprog={conv.get('no_progress_rounds')}"
                f":onfail={conv.get('on_no_convergence')}:body={body_kinds}"
            )

    gates = doc.get("gates", {}) or {}
    gate_shape = sorted(
        f"{g.get('predicate')}/blocking={bool(g.get('blocking', True))}/{g.get('on_fail')}"
        for g in gates.values()
        if isinstance(g, dict)
    )

    replay = doc.get("replay") or {}
    resume = doc.get("resume") or {}
    retry = doc.get("retry_policy") or {}
    failure = doc.get("failure_policy") or {}
    routing = doc.get("model_routing") or {}
    cache = doc.get("cache") or {}

    return {
        "stage_kinds": dict(sorted(kinds.items())),
        "barrier_modes": sorted(barrier_modes),
        "fanout_shape": sorted(fanout_shape),
        "loop_shape": sorted(loop_shape),
        "gate_shape": gate_shape,
        "has_subworkflow": bool(doc.get("subworkflows")),
        "conditional_stages": sorted(
            str(st.get("id")) for st in stages if "when" in st
        ),
        "replay_deterministic": bool(replay.get("deterministic")),
        "replay_verify": replay.get("verify"),
        "resume_granularity": resume.get("granularity")
        if resume.get("enabled")
        else "disabled",
        "retry_strategy": retry.get("strategy"),
        "on_failure": failure.get("on_failure"),
        "routing_strategy": routing.get("strategy"),
        "cache_scope": cache.get("scope") if cache.get("enabled") else "disabled",
        "network": (doc.get("tool_policy") or {}).get("network"),
        "stopping_rule_ids": sorted(
            str(r.get("id")) for r in (doc.get("stopping_rules") or [])
        ),
    }


def fingerprint_key(doc: dict[str, Any]) -> str:
    return json.dumps(fingerprint(doc), sort_keys=True)


# ------------------------------------------------------------- both-states mutation control

#: ``advisory`` is included because all twelve blueprints are held at ZERO advisories, so the
#: good-state arm is genuinely clean on that layer too and a mutation may legitimately target it
#: (DSL-SEM-014, the councilspec cross-implementation check, is advisory by design).
LAYERS = ("schema", "semantic", "advisory", "schema_refs", "worked_examples")


def assert_mutation_caught(
    bp_id: str,
    mutate: Callable[[dict[str, Any]], None],
    expect_layer: str,
    *,
    what: str,
) -> None:
    """BOTH-STATES control.

    Arm 1 (known-good): the unmutated blueprint must pass every layer.
    Arm 2 (known-broken): ``mutate`` must make ``expect_layer`` non-empty.

    Without arm 1 a green arm 2 could be an always-failing checker; without arm 2 a green
    arm 1 could be an always-passing one. Both are required for the check to mean anything.
    """
    if expect_layer not in LAYERS:
        raise AssertionError(
            f"expect_layer must be one of {LAYERS}, got {expect_layer!r}"
        )

    good = load(bp_id)
    good_failures = all_layer_failures(good)
    for layer in LAYERS:
        assert not good_failures[layer], (
            f"GOOD-STATE ARM FAILED for {bp_id}: layer {layer} is not clean before mutation, "
            f"so this control cannot distinguish the two states. {good_failures[layer][:3]}"
        )

    broken = load(bp_id)
    mutate(broken)
    assert broken != good, f"mutation {what!r} on {bp_id} changed nothing"
    broken_failures = all_layer_failures(broken)
    assert broken_failures[expect_layer], (
        f"BROKEN-STATE ARM FAILED for {bp_id}: mutation {what!r} was NOT caught by layer "
        f"{expect_layer}. A detector silent in the broken state measures nothing. "
        f"Other layers reported: "
        f"{ {k: v[:2] for k, v in broken_failures.items() if v} }"
    )
