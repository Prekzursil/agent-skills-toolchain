"""Executable oracles: test / build / measurement, or none."""
from __future__ import annotations

import hashlib
import json
import operator
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ORACLE_CLASSES = frozenset({"test", "build", "measurement"})
PREDICATE_KINDS = frozenset(
    {
        "reproduction",
        "import_graph",
        "telemetry",
        "evidence_admit",
        "spike_measurement",
    }
)
OPS = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


def load_claim(record_id: str, state: str) -> dict:
    path = HERE / "fixtures" / "claims" / f"{record_id}.{state}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def predicate_of(record: dict) -> dict | None:
    pred = (record.get("oracle") or {}).get("predicate")
    return pred if isinstance(pred, dict) else None


def evaluable(pred: dict | None) -> bool:
    return isinstance(pred, dict) and pred.get("kind") in PREDICATE_KINDS


def oracle_status(record: dict) -> dict:
    oid = str(record.get("id") or "")
    oracle = record.get("oracle") if isinstance(record.get("oracle"), dict) else {}
    cls = oracle.get("class")
    missing = oracle.get("missing_element")
    pred = predicate_of(record)
    overclaim = cls in ORACLE_CLASSES and not evaluable(pred)
    if cls in ORACLE_CLASSES and evaluable(pred):
        return {
            "record_id": oid,
            "has_oracle": True,
            "verdict": "HAS-ORACLE",
            "class": cls,
            "oracle_id": oracle.get("id"),
            "settles": oracle.get("settles"),
            "predicate_kind": pred.get("kind") if pred else None,
            "overclaim": False,
            "missing_element": None,
        }
    if not missing:
        if overclaim:
            missing = "oracle.predicate.kind in {reproduction,import_graph,telemetry,evidence_admit,spike_measurement}"
        elif cls not in ORACLE_CLASSES:
            missing = "oracle.class in {test,build,measurement}"
        else:
            missing = "oracle.predicate"
    return {
        "record_id": oid,
        "has_oracle": False,
        "verdict": "NO-ORACLE",
        "class": cls,
        "oracle_id": oracle.get("id"),
        "settles": None,
        "predicate_kind": None,
        "overclaim": overclaim,
        "missing_element": str(missing),
    }


def _cmp(left: Any, op: str, right: Any) -> bool:
    fn = OPS.get(op)
    if fn is None:
        raise ValueError(f"unknown op {op!r}")
    return bool(fn(left, right))


def _run_op(step: dict) -> Any:
    op = step.get("op")
    if op == "sum":
        return sum(step.get("xs") or [])
    if op == "identity":
        return step.get("value")
    if op == "sha256":
        raw = str(step.get("input") or "").encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    raise ValueError(f"unknown procedure op {op!r}")


def pred_reproduction(claim: dict) -> dict:
    actual = None
    for step in claim.get("procedure") or []:
        actual = _run_op(step)
    claimed = claim.get("claimed_output")
    ok = actual == claimed
    return {"pass": ok, "actual": actual, "claimed": claimed, "kind": "reproduction"}


def pred_import_graph(claim: dict) -> dict:
    edges = {tuple(e) for e in (claim.get("edges") or [])}
    forbidden = [tuple(e) for e in (claim.get("forbidden") or [])]
    violations = [list(e) for e in forbidden if e in edges]
    return {
        "pass": len(violations) == 0,
        "violations": violations,
        "kind": "import_graph",
    }


def pred_telemetry(claim: dict) -> dict:
    pred = claim.get("predicate") or {}
    metrics = claim.get("metrics") or {}
    key = pred.get("key")
    ok = _cmp(metrics.get(key), pred.get("op"), pred.get("value"))
    return {
        "pass": ok,
        "observed": metrics.get(key),
        "predicate": pred,
        "kind": "telemetry",
    }


def pred_evidence_admit(claim: dict) -> dict:
    payload = str(claim.get("payload") or "").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    declared = str(claim.get("sha256") or "")
    schema_ok = bool(claim.get("schema_ok"))
    ok = digest == declared and schema_ok
    return {
        "pass": ok,
        "digest": digest,
        "declared": declared,
        "schema_ok": schema_ok,
        "kind": "evidence_admit",
    }


def pred_spike_measurement(claim: dict) -> dict:
    deadline = claim.get("deadline_s")
    finished = claim.get("finished_s")
    on_time = finished is not None and deadline is not None and finished <= deadline
    gate = claim.get("pass_if") or {}
    measurement = claim.get("measurement") or {}
    measured_ok = _cmp(measurement.get(gate.get("key")), gate.get("op"), gate.get("value"))
    ok = bool(on_time) and bool(measured_ok)
    return {
        "pass": ok,
        "on_time": bool(on_time),
        "measured_ok": bool(measured_ok),
        "finished_s": finished,
        "deadline_s": deadline,
        "kind": "spike_measurement",
    }


PREDICATES = {
    "reproduction": pred_reproduction,
    "import_graph": pred_import_graph,
    "telemetry": pred_telemetry,
    "evidence_admit": pred_evidence_admit,
    "spike_measurement": pred_spike_measurement,
}


def evaluate(record: dict, claim: dict) -> dict:
    status = oracle_status(record)
    if not status["has_oracle"]:
        return {
            "pass": False,
            "executable": False,
            "verdict": "NOT-EXECUTABLE",
            "missing_element": status["missing_element"],
            "record_id": status["record_id"],
        }
    kind = status["predicate_kind"]
    fn = PREDICATES[kind]
    out = fn(claim)
    out["executable"] = True
    out["record_id"] = status["record_id"]
    out["oracle_class"] = status["class"]
    return out
