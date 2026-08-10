"""Loading and MUTATION helpers for the bp-7 flagship tests.

The mutation half is the point. A test that only asserts a property holds on the real document
cannot distinguish "the property is enforced" from "my predicate always returns True". Each
mutator here breaks exactly ONE structural property, and the paired test requires the SAME
predicate to go False - and to say why. A mutation that is rejected by the JSON Schema before the
predicate runs would prove nothing about the predicate, so :func:`assert_still_schema_valid`
exists for the cases where the mutated document must remain schema-valid to be a fair control.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent
REPO_ROOT = HERE.parents[2]
for _p in (str(HERE), str(LIB_ROOT)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"


def load(blueprint_id: str) -> dict[str, Any]:
    """Load a COMMITTED blueprint document from disk.

    Deliberately reads the artifact rather than calling the builder: the JSON files are the
    deliverable, so a test that passes against the builder while the committed file has drifted
    would be measuring the wrong bytes. ``bp7_build.py --check`` covers the drift direction.
    """
    path = WORKFLOW_DIR / f"{blueprint_id}.json"
    if not path.is_file():
        raise AssertionError(f"blueprint {blueprint_id!r} is not on disk at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_stage(doc: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Locate a stage anywhere in the document and return the LIVE dict (mutable in place)."""
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("id") == stage_id and "kind" in node:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc.get("stages"))
    if not found:
        raise AssertionError(f"stage {stage_id!r} not found - the mutation targets a stage that moved")
    return found[0]


# ----------------------------------------------------------------------------- mutators


def mutate(doc: dict[str, Any], mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Deep-copy then apply one mutator, so the caller's document is never damaged."""
    clone = copy.deepcopy(doc)
    mutator(clone)
    return clone


def drop_dependency(stage_id: str, dependency: str) -> Callable[[dict[str, Any]], None]:
    """Remove one edge from a stage's ``depends_on`` - the classic 'gate bypassed' mutation."""

    def apply(doc: dict[str, Any]) -> None:
        st = find_stage(doc, stage_id)
        deps = list(st.get("depends_on") or [])
        if dependency not in deps:
            raise AssertionError(
                f"mutation is stale: {stage_id!r} does not depend on {dependency!r}, so removing it proves nothing"
            )
        st["depends_on"] = [d for d in deps if d != dependency]

    return apply


def weaken_gate(gate_name: str, expression: str) -> Callable[[dict[str, Any]], None]:
    """Replace a named library gate's expression with a weaker one."""

    def apply(doc: dict[str, Any]) -> None:
        gates = doc.get("gates") or {}
        if gate_name not in gates:
            raise AssertionError(f"mutation is stale: no gate {gate_name!r} in the gate library")
        gates[gate_name]["expression"] = expression

    return apply


def set_gate_on_fail(gate_name: str, on_fail: str) -> Callable[[dict[str, Any]], None]:
    def apply(doc: dict[str, Any]) -> None:
        gates = doc.get("gates") or {}
        if gate_name not in gates:
            raise AssertionError(f"mutation is stale: no gate {gate_name!r}")
        gates[gate_name]["on_fail"] = on_fail

    return apply


def set_stage_role(stage_id: str, role: str) -> Callable[[dict[str, Any]], None]:
    def apply(doc: dict[str, Any]) -> None:
        find_stage(doc, stage_id)["role"] = role

    return apply


def grant_role_write_paths(role: str, paths: list[str]) -> Callable[[dict[str, Any]], None]:
    """Give a second role app-source write access - the 'two authors' mutation."""

    def apply(doc: dict[str, Any]) -> None:
        roles = doc.get("roles") or {}
        if role not in roles:
            raise AssertionError(f"mutation is stale: no role {role!r}")
        roles[role]["write_paths"] = paths

    return apply


def drop_stage_when(stage_id: str) -> Callable[[dict[str, Any]], None]:
    """Remove a stage's router/guard condition, so it runs unconditionally."""

    def apply(doc: dict[str, Any]) -> None:
        st = find_stage(doc, stage_id)
        if "when" not in st:
            raise AssertionError(f"mutation is stale: {stage_id!r} has no `when` to remove")
        del st["when"]

    return apply


def duplicate_fanout_body_task(stage_id: str, new_id: str) -> Callable[[dict[str, Any]], None]:
    """Add a SECOND scoring task to a fan-out body - breaks one-call-per-item."""

    def apply(doc: dict[str, Any]) -> None:
        st = find_stage(doc, stage_id)
        body = st.get("body")
        if not isinstance(body, list) or not body:
            raise AssertionError(f"mutation is stale: {stage_id!r} has no fan-out body")
        extra = copy.deepcopy(body[0])
        extra["id"] = new_id
        if isinstance(extra.get("work_unit"), dict):
            extra["work_unit"]["id"] = "DAT-9999"
        body.append(extra)

    return apply


def drop_work_unit_input(stage_id: str, needle: str) -> Callable[[dict[str, Any]], None]:
    """Remove an input from a stage's embedded work unit."""

    def apply(doc: dict[str, Any]) -> None:
        wu = find_stage(doc, stage_id).get("work_unit")
        if not isinstance(wu, dict):
            raise AssertionError(f"mutation is stale: {stage_id!r} carries no inline work unit")
        before = list(wu.get("inputs") or [])
        after = [i for i in before if needle not in str(i)]
        if after == before:
            raise AssertionError(f"mutation is stale: no input matching {needle!r} on {stage_id!r}")
        wu["inputs"] = after or ["params.placeholder"]

    return apply


def drop_replay_forbidden_source(source: str) -> Callable[[dict[str, Any]], None]:
    def apply(doc: dict[str, Any]) -> None:
        replay = doc.get("replay") or {}
        before = list(replay.get("forbid_nondeterministic_sources") or [])
        if source not in before:
            raise AssertionError(f"mutation is stale: replay does not forbid {source!r}")
        replay["forbid_nondeterministic_sources"] = [s for s in before if s != source]

    return apply


def retarget_repair_loop(stage_id: str, target: list[str]) -> Callable[[dict[str, Any]], None]:
    def apply(doc: dict[str, Any]) -> None:
        find_stage(doc, stage_id)["target"] = target

    return apply


# ------------------------------------------------------------------------- fair-control


def assert_still_schema_valid(doc: dict[str, Any]) -> None:
    """A mutated document must remain SCHEMA-valid for the control to isolate the predicate.

    If the schema already rejects the mutation, the predicate was never exercised and a passing
    negative test would be measuring the schema, not the check under test.
    """
    from wfdsl import schemas  # imported lazily so this module stays importable standalone

    errs = list(schemas.workflow_validator().iter_errors(doc))
    if errs:
        first = errs[0]
        where = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise AssertionError(
            "the mutated document is not schema-valid, so this control does not isolate the "
            f"predicate: {where} [{first.validator}] {str(first.message)[:160]}"
        )
