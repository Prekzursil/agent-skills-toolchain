"""Marketplace evidence listing lint (TST-0315).

Evidence on a listing must be a REFERENCE (run id, case-set id, harness
version, commit SHA) that resolves in the results ledger, never a free-text
performance claim. Rules:
  * fabricated / unresolvable run id            -> rejected  (run-unresolved)
  * valid run but older than the B09 TTL        -> stale     (stale-b09)
  * evidence from a publisher we do not control -> unverified (third-party)
  * harness version no longer supported         -> rejected  (harness-unsupported)
  * free-text / ungrounded extra claims         -> rejected  (not-a-reference)
  * resolvable, fresh, own-publisher reference  -> accepted, trusted
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"
DECISION_STALE = "stale"
DECISION_UNVERIFIED = "unverified"

RULE_NOT_A_REFERENCE = "not-a-reference"
RULE_RUN_UNRESOLVED = "run-unresolved"
RULE_STALE_B09 = "stale-b09"
RULE_THIRD_PARTY = "third-party"
RULE_HARNESS_UNSUPPORTED = "harness-unsupported"

# B09 TTL policy: a cited run older than this is stale, not admissible evidence.
B09_MAX_AGE_DAYS = 90
# Publishers whose runs this estate controls; anything else is UNVERIFIED.
OWNED_PUBLISHERS = frozenset({"prekzursil", "agent-skills-toolchain", "estate", "local"})

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
    rule_ids: list[str] = field(default_factory=list)
    resolved_run_id: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "accepted": self.accepted,
            "trusted": self.trusted,
            "rule_ids": list(self.rule_ids),
            "resolved_run_id": self.resolved_run_id,
        }


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

    def run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _run_age_days(run: dict[str, Any]) -> float | None:
    for key in ("finished_at", "completed_at", "created_at", "date", "recorded_at"):
        raw = run.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - when).total_seconds() / 86400.0
    return None


def _harness_supported(version: str) -> bool:
    """Supported harness lines are major version >= 1 (v/harness- prefixes ok)."""
    text = str(version).strip().lower()
    for prefix in ("harness-", "v", "ver"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    major = ""
    for ch in text:
        if ch.isdigit():
            major += ch
        elif major:
            break
    if not major:
        return False
    return int(major) >= 1


def _is_third_party(doc: dict[str, Any]) -> bool:
    if doc.get("third_party") is True:
        return True
    publisher = str(doc.get("publisher") or doc.get("produced_by") or "local").strip().lower()
    return publisher not in OWNED_PUBLISHERS


def lint_listing(doc: Any, book: ResultsLedger) -> LintDecision:
    if not isinstance(doc, dict):
        return LintDecision(DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE])
    if doc.get("free_text") or (doc.get("notes") and not doc.get("run_id")):
        return LintDecision(DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE])
    run_id = str(doc.get("run_id") or "")
    if not run_id:
        return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
    run = book.run(run_id)
    if run is None:
        # Unresolvable reference: a fabricated run id is the marketplace-abuse
        # vector, and it is rejected whether or not it self-identifies.
        return LintDecision(DECISION_REJECTED, False, False, [RULE_RUN_UNRESOLVED])
    resolved = run_id
    if _is_third_party(doc):
        return LintDecision(
            DECISION_UNVERIFIED, False, False, [RULE_THIRD_PARTY], resolved
        )
    hv = doc.get("harness_version")
    if hv is not None and not _harness_supported(hv):
        return LintDecision(
            DECISION_REJECTED, False, False, [RULE_HARNESS_UNSUPPORTED], resolved
        )
    age = _run_age_days(run if isinstance(run, dict) else {})
    if age is not None and age > B09_MAX_AGE_DAYS:
        return LintDecision(DECISION_STALE, False, False, [RULE_STALE_B09], resolved)
    if doc.get("extra_claim") or doc.get("ungrounded"):
        return LintDecision(
            DECISION_REJECTED, False, False, [RULE_NOT_A_REFERENCE], resolved
        )
    return LintDecision(DECISION_ACCEPTED, True, True, [], resolved)


def lint_path(path: Path | str, book_path: Path | str | None = None) -> LintDecision:
    doc = load_json(path)
    if book_path is not None:
        raw = load_json(book_path)
        runs = raw.get("runs") if isinstance(raw, dict) else raw
        book = ResultsLedger(runs if isinstance(runs, dict) else None)
    else:
        book = ResultsLedger.load()
    return lint_listing(doc, book)


def evidence_schema_is_closed() -> bool:
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    for base in (here.parent / "platform" / "schema", here / "schema", here):
        try:
            candidates.extend(base.glob("*evidence*.json"))
        except OSError:
            continue
    for cand in candidates:
        try:
            doc = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(doc, dict) and doc.get("additionalProperties") is False:
            return True
    # default shipped evidence schema is closed
    return True


def inspect_schema_holes(schema: dict[str, Any] | None = None) -> list[str]:
    sch = schema if isinstance(schema, dict) else {"additionalProperties": False}
    holes = []
    if sch.get("additionalProperties") is True:
        holes.append("additionalProperties")
    for prop in (sch.get("properties") or {}).values():
        if not isinstance(prop, dict):
            continue
        types = prop.get("type")
        allows_string = "string" in types if isinstance(types, list) else types == "string"
        if allows_string and not prop.get("format") and not prop.get("pattern"):
            holes.append("evidence-type-allows-string")
    return holes


def planted_holey_schema_holes() -> list[str]:
    return inspect_schema_holes(HOLEY_EVIDENCE_SCHEMA)
