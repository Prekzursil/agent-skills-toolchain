"""Shared test infrastructure for the bp-3 flagship end-to-end tests.

What "end-to-end" covers here, stated precisely so the flagship label is not an overclaim:
each test loads the SHIPPED blueprint JSON, validates it against workflow-dsl.schema.json plus
the 14 semantic rules, asserts the blueprint's own mechanism-bearing invariants by READING them
out of the document (never by hardcoding them), executes that blueprint's declared worked
example through the real primitive in ``mechanisms.py``, executes the declared negative controls,
and finally runs a both-states mutation control proving the invariant assertions FAIL on a
mutated copy.

What it does NOT cover, and no test here claims otherwise: no live agent, model, or tool is
invoked. There is no workflow RUNNER in this repo yet, so a test cannot execute a blueprint
against real subagents. These tests verify the DEFINITION and its mechanical decision procedure.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"
SHARED_DIR = WORKFLOW_DIR / "_shared"


def load_blueprint(bp_id: str) -> dict[str, Any]:
    path = WORKFLOW_DIR / f"{bp_id}.workflow.json"
    if not path.is_file():
        path = SHARED_DIR / f"{bp_id}.subworkflow.json"
    assert path.is_file(), f"blueprint not on disk: {bp_id} (looked in {WORKFLOW_DIR})"
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(doc: dict[str, Any]) -> list[str]:
    from wfdsl import schemas

    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in schemas.workflow_validator().iter_errors(doc)
    ]


def semantic_violations(doc: dict[str, Any]) -> list[str]:
    from wfdsl import semantics

    out = []
    for r in semantics.check_workflow(doc):
        if r.severity == "violation":
            out += [f"{r.rule} {v[0]}: {v[1]}" for v in r.violations]
    return out


def assert_contract_valid(doc: dict[str, Any]) -> None:
    """Every blueprint must satisfy the JSON-Schema layer AND the semantic layer."""
    assert schema_errors(doc) == [], schema_errors(doc)
    assert semantic_violations(doc) == [], semantic_violations(doc)


# --------------------------------------------------------------------------- doc navigation


def stages(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every stage, including nested bodies and repair-loop sub-stages, in document order."""
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if "id" in node and "kind" in node:
                out.append(node)
            for key in ("body", "diagnose", "repair", "verify"):
                if key in node:
                    walk(node[key])

    walk(doc.get("stages", []))
    return out


def stage(doc: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for st in stages(doc):
        if st.get("id") == stage_id:
            return st
    raise AssertionError(f"no stage {stage_id!r}; have {[s.get('id') for s in stages(doc)]}")


def stage_ids(doc: dict[str, Any]) -> list[str]:
    return [str(s.get("id")) for s in stages(doc)]


def gate_expressions(doc: dict[str, Any]) -> dict[str, str]:
    """gate name -> its expression text, for gates that carry one."""
    return {
        name: str(spec.get("expression"))
        for name, spec in (doc.get("gates") or {}).items()
        if isinstance(spec, dict) and isinstance(spec.get("expression"), str)
    }


def worked_example(doc: dict[str, Any]) -> dict[str, Any]:
    ex = ((doc.get("x_extensions") or {}).get("worked_example")) or {}
    assert ex, f"{doc.get('id')} declares no worked example"
    for field in ("name", "narrative", "mechanism", "input", "expected"):
        assert ex.get(field), f"{doc.get('id')} worked example is missing {field!r}"
    return ex


def stopping_expressions(doc: dict[str, Any]) -> list[Any]:
    return [r.get("expression") for r in doc.get("stopping_rules") or []]


# ------------------------------------------------------------------- both-states mutation control


def both_states_control(
    doc: dict[str, Any],
    invariant: Callable[[dict[str, Any]], None],
    mutate: Callable[[dict[str, Any]], None],
    label: str,
) -> None:
    """Prove the invariant is not vacuous: it must PASS on the shipped doc and FAIL on a mutant.

    A probe that is silent in both states measures nothing. This helper is the mechanised form of
    that rule, so every flagship test carries its own control rather than trusting the assertion.
    """
    invariant(doc)  # must hold on the shipped blueprint
    mutant = copy.deepcopy(doc)
    mutate(mutant)
    with pytest.raises(AssertionError):
        invariant(mutant)
        pytest.fail(f"both-states control {label!r} did not fire: the invariant is vacuous")


def declared_stopping_rule(doc: dict[str, Any], rule_id: str) -> dict[str, Any]:
    for r in doc.get("stopping_rules") or []:
        if r.get("id") == rule_id:
            return r
    raise AssertionError(
        f"no stopping rule {rule_id!r}; have {[r.get('id') for r in doc.get('stopping_rules') or []]}"
    )
