"""Shared assertions for the blueprints/bp-1 tests (blueprints 1-12 of 96).

Every helper here answers a MECHANICAL question, so the tests never rest on a reading of the
JSON: schema validity comes from the repo's own validator, the stage order comes from the
reference planner, mechanism distinctness is a set computation, and schema references are
resolved through the shipped resolver rather than by eyeballing a path.

``both_states`` is the load-bearing helper. A test that only asserts the healthy state proves
nothing about the check; every mutation control here asserts GREEN before the mutation and RED
after it, in the same test, so a probe that is silent in both states cannot pass.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent
for _p in (str(LIB_ROOT), str(HERE)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp1_build as B  # noqa: E402
import bp1_dryrun as D  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

REPO_ROOT = LIB_ROOT.parents[1]
WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"

#: the twelve ids this unit owns, in blueprint-card order
BP1_IDS: tuple[str, ...] = (
    "bp-res-01-grounded-evidence-cascade",
    "bp-res-02-multilingual-native-index-fusion",
    "bp-res-03-academic-corpus-consolidation",
    "bp-res-04-claim-decomposition-verification",
    "bp-res-05-briefed-fact-reprobe-council",
    "bp-res-06-longitudinal-verdict-refresh",
    "bp-gem-01-wide-lens-gem-sweep",
    "bp-gem-02-anti-overfit-candidate-gate",
    "bp-gem-03-obscure-channel-miner",
    "bp-gem-04-marketplace-catalogue-tax-audit",
    "bp-gem-05-executed-corpus-archaeology-mine",
    "bp-brn-01-two-peer-cross-vendor-idea-fanout",
)

FLAGSHIP_IDS: tuple[str, ...] = (
    "bp-res-01-grounded-evidence-cascade",
    "bp-res-04-claim-decomposition-verification",
    "bp-res-05-briefed-fact-reprobe-council",
    "bp-gem-02-anti-overfit-candidate-gate",
    "bp-gem-05-executed-corpus-archaeology-mine",
    "bp-brn-01-two-peer-cross-vendor-idea-fanout",
)


def load(bp_id: str) -> dict[str, Any]:
    """Load the COMMITTED JSON from disk - the artifact a runner would consume."""
    path = WORKFLOW_DIR / f"{bp_id}.json"
    assert path.is_file(), (
        f"{path} does not exist; run platform/lib/workflows/bp1_build.py"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(doc: Mapping[str, Any]) -> list[str]:
    errs = sorted(
        schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    return schemas.error_summary(errs, limit=8)


def semantic_violations(doc: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for rule in semantics.check_workflow(doc):
        if rule.severity == "violation" and rule.violations:
            out.append(f"{rule.rule}: {rule.violations[:3]}")
    return out


def is_conformant(doc: Mapping[str, Any]) -> bool:
    """The single healthy-state predicate every mutation control flips."""
    return not schema_errors(doc) and not semantic_violations(doc)


def example(doc: Mapping[str, Any]) -> dict[str, Any]:
    return dict(doc["x_extensions"]["worked_example"])


def plan_from_example(doc: Mapping[str, Any], **overrides: Any) -> D.Plan:
    ex = example(doc)
    params = dict(ex["params"])
    params.update(overrides.pop("params", {}) or {})
    facts = dict(ex.get("facts", {}))
    facts.update(overrides.pop("facts", {}) or {})
    return D.plan_workflow(doc, params, facts)


def mechanism_set(doc: Mapping[str, Any]) -> set[str]:
    return {str(m) for m in doc["x_extensions"]["mechanism_signature"]}


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def gate_expressions(doc: Mapping[str, Any]) -> dict[str, str]:
    """gate id -> its expression text (only gates that carry one)."""
    out: dict[str, str] = {}
    for name, gate in (doc.get("gates") or {}).items():
        if isinstance(gate, Mapping) and isinstance(gate.get("expression"), str):
            out[str(name)] = gate["expression"]
    return out


def stage(doc: Mapping[str, Any], stage_id: str) -> dict[str, Any]:
    for _path, st in semantics.iter_stages(doc):
        if str(st.get("id")) == stage_id:
            return dict(st)
    raise AssertionError(f"stage {stage_id!r} not found in {doc.get('id')}")


def work_units(doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(u["id"]): dict(u) for _sid, u in D.iter_work_units(doc)}


def both_states(
    doc: Mapping[str, Any],
    mutate: Callable[[dict[str, Any]], None],
    check: Callable[[Mapping[str, Any]], bool],
    label: str,
) -> None:
    """Assert ``check`` is TRUE on the real document and FALSE after ``mutate``.

    A probe that is silent in both states measures nothing, so both directions are asserted
    here rather than only the healthy one. ``mutate`` receives a deep copy: the on-disk
    document is never touched.
    """
    assert check(doc) is True, (
        f"{label}: the check is already FALSE on the unmutated document, so its failure after "
        "mutation would prove nothing"
    )
    mutated = copy.deepcopy(dict(doc))
    mutate(mutated)
    assert check(mutated) is False, (
        f"{label}: the check STILL PASSES on the mutated document - it does not actually "
        "measure the property it claims to"
    )


def stopping_both_states(doc: Mapping[str, Any], control: Mapping[str, Any]) -> None:
    """One declared stopping-rule control: fires on one context, does not on the other."""
    rule_id = str(control["rule"])
    fires = D.check_stopping_rules(doc, control["fires_on"])
    nofire = D.check_stopping_rules(doc, control["does_not_fire_on"])
    assert not fires["errors"], (
        f"{rule_id}: unevaluated identifiers in fires_on: {fires['errors']}"
    )
    assert not nofire["errors"], (
        f"{rule_id}: unevaluated identifiers in does_not_fire_on: {nofire['errors']}"
    )
    row_fire = next(r for r in fires["rules"] if r["id"] == rule_id)
    row_no = next(r for r in nofire["rules"] if r["id"] == rule_id)
    assert row_fire["fires"] is True, (
        f"{rule_id}: did not fire on its declared firing context"
    )
    assert row_no["fires"] is False, (
        f"{rule_id}: fired on its declared NON-firing context"
    )


def resolve_schema_ref(ref: str) -> Any:
    """Compile a declared schema reference through the shipped resolver (fails closed)."""
    import schema_resolver  # noqa: PLC0415 - imported lazily so a missing resolver is visible

    return schema_resolver.validator_for(ref)


def declared_schema_refs(doc: Mapping[str, Any]) -> list[str]:
    return D.declared_schema_refs(doc)


__all__ = [
    "B",
    "D",
    "BP1_IDS",
    "FLAGSHIP_IDS",
    "REPO_ROOT",
    "WORKFLOW_DIR",
    "both_states",
    "declared_schema_refs",
    "example",
    "gate_expressions",
    "is_conformant",
    "jaccard",
    "load",
    "mechanism_set",
    "plan_from_example",
    "resolve_schema_ref",
    "schema_errors",
    "semantic_violations",
    "stage",
    "stopping_both_states",
    "work_units",
]
