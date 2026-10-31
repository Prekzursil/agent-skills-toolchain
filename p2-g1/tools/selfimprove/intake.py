"""Self-improve intake with reproduction gate (IMP-0371)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA_PATH = Path(__file__).resolve().parent / "candidate.schema.json"
KINDS = {"failure", "opportunity"}


class GateBlocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def scripted_trials(flags: Iterable[bool]) -> list[bool]:
    return [bool(x) for x in flags]


def classify_repeat(n: int, m: int) -> str:
    if m <= 0:
        return "unreproduced"
    if n <= 0:
        return "unreproduced"
    if n == m:
        return "confirmed"
    return "flaky"


def candidate_schema_errors(doc: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = list(schema.get("required") or [])
    errs = [f"missing:{k}" for k in required if k not in doc]
    kind = doc.get("kind")
    if "kind" in doc and kind not in KINDS:
        errs.append("bad-kind")
    return errs


class Intake:
    def __init__(self, enforce_reproduction_gate: bool = True) -> None:
        self.enforce = bool(enforce_reproduction_gate)
        self.candidates: dict[str, dict[str, Any]] = {}
        self._issued: dict[str, str] = {}
        self._advanced: list[str] = []

    def observe(self, candidate_id: str, kind: str, summary: str, source: str) -> dict[str, Any]:
        cand = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "kind": kind,
            "observation": {"summary": summary, "source": source},
            "stage": "observed",
            "repeat_count": {"n": 0, "m": 0, "observed": "0/0"},
            "classification": "observed",
            "baseline_accepted": False,
        }
        self.candidates[candidate_id] = cand
        return cand

    def snapshot(self, candidate_id: str) -> dict[str, Any]:
        return dict(self.candidates[candidate_id])

    def reproduce(self, candidate_id: str, trials: Iterable[bool], attempts: int, command: str) -> dict[str, Any]:
        flags = list(trials)[:attempts]
        n = sum(1 for x in flags if x)
        m = int(attempts)
        cls = classify_repeat(n, m)
        cand = self.candidates[candidate_id]
        cand["repeat_count"] = {"n": n, "m": m, "observed": f"{n}/{m}"}
        cand["classification"] = cls
        cand["baseline_accepted"] = cls == "confirmed"
        cand["stage"] = "flaky" if cls == "flaky" else ("reproduced" if cls == "confirmed" else "unreproduced")
        cand["reproduce_command"] = command
        self._issued[candidate_id] = cls
        return cand

    def advance_to_implementation(self, candidate_id: str) -> dict[str, Any]:
        cand = self.candidates[candidate_id]
        issued = self._issued.get(candidate_id)
        if self.enforce:
            if cand.get("stage") == "observed" and issued is None:
                raise GateBlocked("missing-reproduction-receipt")
            if issued == "flaky" or cand.get("classification") == "flaky":
                raise GateBlocked("flaky-not-accepted-as-baseline")
            if issued != "confirmed":
                if issued == "unreproduced" or cand.get("classification") == "unreproduced":
                    raise GateBlocked("unreproduced-not-accepted-as-baseline")
                raise GateBlocked("missing-reproduction-receipt")
        self._advanced.append(candidate_id)
        cand["stage"] = "implementation"
        return cand

    def stage_gate_audit(self) -> dict[str, Any]:
        without = [
            cid
            for cid in self._advanced
            if self._issued.get(cid) != "confirmed"
        ]
        held = self.enforce and not without
        return {
            "held": held,
            "advanced_without_confirmed_receipt": without,
            "enforce": self.enforce,
        }
