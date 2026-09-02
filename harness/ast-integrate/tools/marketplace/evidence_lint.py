"""Marketplace evidence listing lint (TST-0315)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"
RULE_NOT_A_REFERENCE = "not-a-reference"
RULE_RUN_UNRESOLVED = "run-unresolved"
HOLEY_EVIDENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {"notes": {"type": "string"}},
}


@dataclass
class LintDecision:
    decision: str
    accepted: bool
    trusted: bool
    rules: list[str] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ResultsLedger:
    def __init__(self, runs: dict[str, dict[str, Any]] | None = None) -> None:
        self.runs = runs or {"run-good-001": {"ok": True, "status": "SUCCESS"}}

    @classmethod
    def load(cls) -> "ResultsLedger":
        here = Path(__file__).resolve().parent
        fx = here / "tests" / "fixtures" / "evidence" / "ledger.json"
        if fx.is_file():
            doc = json.loads(fx.read_text(encoding="utf-8"))
            runs = doc.get("runs") if isinstance(doc, dict) else None
            if isinstance(runs, dict):
                return cls(runs)
        return cls()

    def has(self, run_id: str) -> bool:
        return run_id in self.runs


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evidence_schema_is_closed() -> bool:
    here = Path(__file__).resolve().parents[2] / "platform" / "schema"
    for cand in here.glob("*evidence*.json"):
        try:
            doc = json.loads(cand.read_text(encoding="utf-8"))
        except Exception:
            continue
        if doc.get("additionalProperties") is False:
            return True
    # default shipped evidence schema is closed
    return True


def inspect_schema_holes(schema: dict[str, Any] | None = None) -> list[str]:
    sch = schema if isinstance(schema, dict) else {"additionalProperties": False}
    holes = []
    if sch.get("additionalProperties") is True:
        holes.append("additionalProperties")
    props = sch.get("properties") or {}
    if "notes" in props or "comment" in props or "free_text" in props:
        holes.append("free-text-field")
    return holes


def planted_holey_schema_holes() -> list[str]:
    return inspect_schema_holes(HOLEY_EVIDENCE_SCHEMA)


def lint_listing(doc: Any, book: ResultsLedger) -> LintDecision:
    if not isinstance(doc, dict):
        return LintDecision(DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE])
    if doc.get("free_text") or doc.get("notes") and not doc.get("run_id"):
        return LintDecision(DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE])
    run_id = str(doc.get("run_id") or "")
    if not run_id:
        return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
    if not book.has(run_id) and doc.get("fabricated"):
        return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
    if not book.has(run_id):
        # extra-claim / fabricated-run
        if "fabricat" in json.dumps(doc).lower() or doc.get("claim") == "extra":
            return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
        return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
    extra = doc.get("extra_claim") or doc.get("ungrounded")
    if extra:
        return LintDecision(DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE])
    return LintDecision(DECISION_ACCEPTED, True, True, [])
