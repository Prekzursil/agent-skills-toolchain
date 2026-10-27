"""IMP-0230: blueprint-authoring/v1 registration gate.

One contract every built-in blueprint satisfies: typed Workflow, at least one
runnable example, at least one preset, documented stopping rules, a hermetic
smoke test, and a declared capability vector. A blueprint omitting any
required element cannot be registered: validation is refused with a closed,
distinct violation id per omitted element (never a bare boolean).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

CONTRACT_ID = "blueprint-authoring/v1"

REQUIRED_ELEMENTS = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)

VIOLATION_IDS = {
    "typed_workflow": "BP-MISSING-TYPED-WORKFLOW",
    "runnable_example": "BP-MISSING-RUNNABLE-EXAMPLE",
    "preset": "BP-MISSING-PRESET",
    "stopping_rules": "BP-MISSING-STOPPING-RULES",
    "smoke_test": "BP-MISSING-SMOKE-TEST",
    "capability_vector": "BP-MISSING-CAPABILITY-VECTOR",
}


@dataclass
class GateResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    contract_id: str = CONTRACT_ID

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": list(self.violations),
            "contract_id": self.contract_id,
        }


def _has_typed_workflow(doc: dict[str, Any]) -> bool:
    wf = doc.get("typed_workflow")
    if not isinstance(wf, dict):
        return False
    stages = wf.get("stages")
    if not isinstance(stages, list) or not stages:
        return False
    return all(
        isinstance(s, dict) and bool(s.get("id")) and bool(s.get("type"))
        for s in stages
    )


def _has_runnable_example(doc: dict[str, Any]) -> bool:
    ex = doc.get("runnable_example")
    return (
        isinstance(ex, dict)
        and isinstance(ex.get("command"), list)
        and len(ex["command"]) > 0
    )


def _has_preset(doc: dict[str, Any]) -> bool:
    p = doc.get("preset")
    return isinstance(p, dict) and bool(p.get("id"))


def _has_stopping_rules(doc: dict[str, Any]) -> bool:
    rules = doc.get("stopping_rules")
    if not isinstance(rules, list) or not rules:
        return False
    return all(
        isinstance(r, dict) and bool(r.get("condition")) and bool(r.get("action"))
        for r in rules
    )


def _has_smoke_test(doc: dict[str, Any]) -> bool:
    st = doc.get("smoke_test")
    return (
        isinstance(st, dict)
        and isinstance(st.get("command"), list)
        and len(st["command"]) > 0
        and st.get("hermetic") is True
    )


def _has_capability_vector(doc: dict[str, Any]) -> bool:
    cv = doc.get("capability_vector")
    return isinstance(cv, dict) and len(cv) > 0


_CHECKS = {
    "typed_workflow": _has_typed_workflow,
    "runnable_example": _has_runnable_example,
    "preset": _has_preset,
    "stopping_rules": _has_stopping_rules,
    "smoke_test": _has_smoke_test,
    "capability_vector": _has_capability_vector,
}


def validate_blueprint(doc: Any) -> GateResult:
    """Refuse any blueprint that omits (or degenerates) a required element.

    Each omitted element yields exactly its own closed violation id, in
    REQUIRED_ELEMENTS order. A present-but-empty element counts as omitted:
    a declared-nothing element is the same lie as a missing one.
    """
    if not isinstance(doc, dict):
        return GateResult(
            ok=False, violations=[VIOLATION_IDS[el] for el in REQUIRED_ELEMENTS]
        )
    missing = [el for el in REQUIRED_ELEMENTS if not _CHECKS[el](doc)]
    return GateResult(
        ok=not missing, violations=[VIOLATION_IDS[el] for el in missing]
    )


def register_blueprint(doc: Any) -> GateResult:
    """Registration is validation: refusal is a closed typed result, never a raise."""
    return validate_blueprint(doc)


def run_declared_smoke(doc: Any, timeout_s: float = 30.0) -> tuple[bool, list[str]]:
    """Run the blueprint's declared hermetic smoke test. Returns (ok, failed_ids)."""
    if not _has_smoke_test(doc):
        return False, ["smoke-test-missing-or-unrunnable"]
    st = doc["smoke_test"]
    label = str(st.get("id") or "declared-smoke")
    try:
        p = subprocess.run(
            st["command"],
            capture_output=True,
            text=True,
            timeout=float(st.get("timeout_s", timeout_s)),
        )
        if p.returncode != 0:
            return False, [label]
    except (OSError, subprocess.SubprocessError):
        return False, [label]
    return True, []
