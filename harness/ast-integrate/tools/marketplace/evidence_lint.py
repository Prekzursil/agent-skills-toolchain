"""Marketplace benchmark-evidence lint (TST-0315).

A listing may carry benchmark evidence only as a *reference* into the results
ledger: ``{"run_id", "case_set_id", "harness_version", "commit_sha"}``. Free
text, extra keys and references that do not resolve are rejected. A resolved
run that is B09-expired is flagged STALE (never ACCEPTED); a run produced by a
publisher we do not control is UNVERIFIED (never trusted).

Decision precedence when several findings fire: reject > stale > unverified.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARKETPLACE_ROOT = Path(__file__).resolve().parent
EVIDENCE_SCHEMA_PATH = MARKETPLACE_ROOT / "schema" / "benchmark-evidence.schema.json"
LISTING_SCHEMA_PATH = MARKETPLACE_ROOT / "schema" / "listing-evidence.schema.json"
DEFAULT_LEDGER_PATH = MARKETPLACE_ROOT / "data" / "evidence-ledger.fixture.json"

DECISION_ACCEPTED = "ACCEPTED"
DECISION_REJECTED = "REJECTED"
DECISION_STALE = "STALE"
DECISION_UNVERIFIED = "UNVERIFIED"

RULE_NOT_A_REFERENCE = "evidence-not-a-reference"
RULE_ADDITIONAL_PROPERTIES = "evidence-additional-properties"
RULE_MISSING_KEYS = "evidence-missing-reference-keys"
RULE_MALFORMED = "evidence-reference-malformed"
RULE_RUN_UNRESOLVED = "evidence-run-unresolved"
RULE_REFERENCE_MISMATCH = "evidence-reference-mismatch"
RULE_HARNESS_UNSUPPORTED = "evidence-harness-unsupported"
RULE_STALE_B09 = "evidence-run-stale-b09"
RULE_THIRD_PARTY = "evidence-third-party-unverified"

SEVERITY_REJECT = "reject"
SEVERITY_STALE = "stale"
SEVERITY_UNVERIFIED = "unverified"

REFERENCE_KEYS = ("run_id", "case_set_id", "harness_version", "commit_sha")

# A deliberately open schema used by the probes to show the hole inspector
# fires: evidence may be a string, extra keys are allowed, no key is
# constrained and the required list is incomplete.
HOLEY_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": ["object", "string"],
    "additionalProperties": True,
    "required": ["run_id"],
    "properties": {
        "run_id": {"type": "string"},
        "case_set_id": {"type": "string"},
        "harness_version": {"type": "string"},
        "commit_sha": {"type": "string"},
        "claim": {"type": "string"},
        "notes": {"type": "string"},
    },
}


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "message": self.message,
            "rule_id": self.rule_id,
            "severity": self.severity,
        }


@dataclass
class LintDecision:
    decision: str
    accepted: bool
    trusted: bool
    listing_name: str | None = None
    resolved_run_id: str | None = None
    findings: list[Finding] = field(default_factory=list)
    schema_holes: list[str] = field(default_factory=list)

    @property
    def rule_ids(self) -> list[str]:
        return [f.rule_id for f in self.findings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "decision": self.decision,
            "findings": [f.to_dict() for f in self.findings],
            "listing_name": self.listing_name,
            "resolved_run_id": self.resolved_run_id,
            "rule_ids": self.rule_ids,
            "schema_holes": list(self.schema_holes),
            "trusted": self.trusted,
        }


@dataclass
class LedgerRun:
    run_id: str
    case_set_id: str
    harness_version: str
    commit_sha: str
    publisher: str
    recorded_at: str
    b09_expires_at: str

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "LedgerRun":
        return cls(
            run_id=str(doc["run_id"]),
            case_set_id=str(doc.get("case_set_id", "")),
            harness_version=str(doc.get("harness_version", "")),
            commit_sha=str(doc.get("commit_sha", "")),
            publisher=str(doc.get("publisher", "")),
            recorded_at=str(doc.get("recorded_at", "")),
            b09_expires_at=str(doc.get("b09_expires_at", "")),
        )


class ResultsLedger:
    """The results ledger a listing's evidence must resolve into."""

    def __init__(
        self,
        runs: dict[str, LedgerRun],
        supported_harness_versions: set[str],
        first_party_publishers: set[str],
        as_of: str,
        path: Path | None = None,
    ) -> None:
        self.by_run = dict(runs)
        self.supported_harness_versions = set(supported_harness_versions)
        self.first_party_publishers = set(first_party_publishers)
        self.as_of = as_of
        self.path = path

    @classmethod
    def from_dict(cls, doc: dict[str, Any], path: Path | None = None) -> "ResultsLedger":
        if not isinstance(doc, dict) or not isinstance(doc.get("runs"), list):
            raise ValueError("results ledger must be an object with a 'runs' list")
        runs: dict[str, LedgerRun] = {}
        for raw in doc["runs"]:
            run = LedgerRun.from_dict(raw)
            if run.run_id in runs:
                raise ValueError(f"duplicate run_id in ledger: {run.run_id}")
            runs[run.run_id] = run
        return cls(
            runs,
            set(doc.get("supported_harness_versions", [])),
            set(doc.get("first_party_publishers", [])),
            str(doc.get("as_of", "")),
            path,
        )

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ResultsLedger":
        p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        return cls.from_dict(load_json(p), p)

    def resolve(self, run_id: str) -> LedgerRun | None:
        return self.by_run.get(run_id)

    def has(self, run_id: str) -> bool:
        return run_id in self.by_run

    def is_b09_expired(self, run: LedgerRun) -> bool:
        # ISO-8601 UTC timestamps compare lexically; the ledger carries its own
        # as_of so the verdict does not drift with the wall clock.
        return bool(run.b09_expires_at) and bool(self.as_of) and run.b09_expires_at <= self.as_of

    def is_first_party(self, run: LedgerRun) -> bool:
        return run.publisher in self.first_party_publishers


def load_evidence_schema(path: Path | str | None = None) -> dict[str, Any]:
    return load_json(Path(path) if path is not None else EVIDENCE_SCHEMA_PATH)


def inspect_schema_holes(schema: dict[str, Any] | None = None) -> list[str]:
    """Return the ways ``schema`` lets non-reference evidence through.

    An empty list means the schema is closed: evidence is an object with
    exactly the four reference keys, each constrained by a pattern.
    """
    sch = schema if schema is not None else load_evidence_schema()
    holes: list[str] = []
    typ = sch.get("type")
    types = typ if isinstance(typ, list) else [typ]
    if "string" in types or typ is None:
        holes.append("evidence-type-allows-string")
    elif types != ["object"]:
        holes.append("evidence-type-not-object")
    if sch.get("additionalProperties") is not False:
        holes.append("evidence-additionalProperties-not-false")
    props = sch.get("properties") or {}
    extra = sorted(k for k in props if k not in REFERENCE_KEYS)
    if extra:
        holes.append("evidence-extra-properties:" + ",".join(extra))
    for key in REFERENCE_KEYS:
        spec = props.get(key)
        if not isinstance(spec, dict):
            holes.append(f"evidence-{key}-missing")
            continue
        if spec.get("type") != "string" or not spec.get("pattern"):
            holes.append(f"evidence-{key}-unconstrained-string")
    required = sch.get("required") or []
    if any(key not in required for key in REFERENCE_KEYS):
        holes.append("evidence-required-keys-incomplete")
    return holes


def evidence_schema_is_closed(schema: dict[str, Any] | None = None) -> bool:
    return inspect_schema_holes(schema) == []


def planted_holey_schema_holes() -> list[str]:
    return inspect_schema_holes(HOLEY_EVIDENCE_SCHEMA)


def _pattern_for(schema: dict[str, Any], key: str) -> re.Pattern[str] | None:
    spec = (schema.get("properties") or {}).get(key) or {}
    pat = spec.get("pattern")
    return re.compile(pat) if isinstance(pat, str) else None


def _reject(name: str | None, finding: Finding, holes: list[str]) -> LintDecision:
    return LintDecision(
        DECISION_REJECTED, False, False, name, None, [finding], holes
    )


def lint_listing(
    doc: Any,
    book: ResultsLedger,
    schema: dict[str, Any] | None = None,
) -> LintDecision:
    sch = schema if schema is not None else load_evidence_schema()
    holes = inspect_schema_holes(sch)
    name = doc.get("name") if isinstance(doc, dict) else None
    if isinstance(name, str) is False:
        name = None
    if not isinstance(doc, dict) or "evidence" not in doc:
        return _reject(
            name,
            Finding(RULE_NOT_A_REFERENCE, SEVERITY_REJECT, "listing carries no evidence reference"),
            holes,
        )
    evidence = doc["evidence"]
    if isinstance(evidence, str):
        return _reject(
            name,
            Finding(
                RULE_NOT_A_REFERENCE,
                SEVERITY_REJECT,
                "evidence is a free-text string, not a ledger reference",
            ),
            holes,
        )
    if not isinstance(evidence, dict):
        return _reject(
            name,
            Finding(
                RULE_NOT_A_REFERENCE,
                SEVERITY_REJECT,
                f"evidence must be a reference object, got {type(evidence).__name__}",
            ),
            holes,
        )
    allowed = set((sch.get("properties") or {}).keys()) or set(REFERENCE_KEYS)
    extra = sorted(k for k in evidence if k not in allowed)
    if extra:
        return _reject(
            name,
            Finding(
                RULE_ADDITIONAL_PROPERTIES,
                SEVERITY_REJECT,
                "evidence has non-reference keys (open hole if schema allowed them): "
                + ",".join(extra),
            ),
            holes,
        )
    required = list(sch.get("required") or REFERENCE_KEYS)
    missing = [k for k in required if k not in evidence]
    if missing:
        return _reject(
            name,
            Finding(
                RULE_MISSING_KEYS,
                SEVERITY_REJECT,
                "evidence reference is missing keys: " + ",".join(missing),
            ),
            holes,
        )
    for key in REFERENCE_KEYS:
        value = evidence.get(key)
        pat = _pattern_for(sch, key)
        if not isinstance(value, str) or (pat is not None and not pat.fullmatch(value)):
            return _reject(
                name,
                Finding(
                    RULE_MALFORMED,
                    SEVERITY_REJECT,
                    f"evidence {key} {value!r} does not match the reference grammar",
                ),
                holes,
            )

    run_id = evidence["run_id"]
    run = book.resolve(run_id)
    if run is None:
        return _reject(
            name,
            Finding(
                RULE_RUN_UNRESOLVED,
                SEVERITY_REJECT,
                f"run_id {run_id!r} is not in the results ledger",
            ),
            holes,
        )

    findings: list[Finding] = []
    mismatched = [
        key
        for key in ("case_set_id", "harness_version", "commit_sha")
        if getattr(run, key) and evidence[key] != getattr(run, key)
    ]
    if mismatched:
        findings.append(
            Finding(
                RULE_REFERENCE_MISMATCH,
                SEVERITY_REJECT,
                f"evidence cites run {run_id!r} but "
                + ",".join(mismatched)
                + " disagree with the ledger row",
            )
        )
    if run.harness_version not in book.supported_harness_versions:
        findings.append(
            Finding(
                RULE_HARNESS_UNSUPPORTED,
                SEVERITY_REJECT,
                f"harness_version {run.harness_version!r} is no longer supported",
            )
        )
    if book.is_b09_expired(run):
        findings.append(
            Finding(
                RULE_STALE_B09,
                SEVERITY_STALE,
                "run exists in the ledger but is B09-expired; flag STALE, do not accept",
            )
        )
    if not book.is_first_party(run):
        findings.append(
            Finding(
                RULE_THIRD_PARTY,
                SEVERITY_UNVERIFIED,
                f"evidence produced by publisher {run.publisher!r} we do not control; "
                "mark UNVERIFIED, do not silently trust",
            )
        )

    severities = {f.severity for f in findings}
    if SEVERITY_REJECT in severities:
        decision = DECISION_REJECTED
    elif SEVERITY_STALE in severities:
        decision = DECISION_STALE
    elif SEVERITY_UNVERIFIED in severities:
        decision = DECISION_UNVERIFIED
    else:
        decision = DECISION_ACCEPTED
    accepted = decision == DECISION_ACCEPTED
    return LintDecision(decision, accepted, accepted, name, run.run_id, findings, holes)


def lint_path(
    listing_path: Path | str,
    book_path: Path | str | None = None,
    schema_path: Path | str | None = None,
) -> LintDecision:
    book = ResultsLedger.load(book_path)
    schema = load_evidence_schema(schema_path)
    return lint_listing(load_json(listing_path), book, schema)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("listing", help="marketplace listing JSON")
    ap.add_argument("--ledger", default=None, help="results ledger JSON")
    ap.add_argument("--schema", default=None, help="evidence reference schema JSON")
    ns = ap.parse_args(argv)
    decision = lint_path(ns.listing, ns.ledger, ns.schema)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0 if decision.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
