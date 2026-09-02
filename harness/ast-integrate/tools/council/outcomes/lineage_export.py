#!/usr/bin/env python3
"""Council decision lineage: supersession markers on overturn (IMP-0351).

Every council decision is exported as a *lineage record* into the program decision log.
When a later council overturns an earlier one, :func:`commit_overturn` appends the newer
record with ``supersedes=[older_id]`` and -- unless the caller explicitly declines with
``mark=False`` -- stamps the older row ``status=SUPERSEDED`` / ``superseded_by=<newer_id>``.
:func:`scan_live_contradictions` is the both-states detector: two LIVE rows answering the
same question differently make it FIRE with the exact id pairs; an empty log, unrelated
questions, or a marked overturn keep it SILENT.

Record schema (:data:`REQUIRED_FIELDS`, machine form :data:`LINEAGE_RECORD_SCHEMA`):
``decision_id``, ``council_id``, ``question``, ``question_key`` (normalised question hash),
``verdict``, ``inputs`` (``[{kind, ref}]``), ``deciding_rule``, ``tally`` (name -> count),
``dissents`` (``[{actor, claim}]``), ``supersedes`` (ids), ``superseded_by`` (id or null),
``status`` (LIVE | SUPERSEDED) and ``recorded_at`` (UTC ISO-8601; honours
``SOURCE_DATE_EPOCH`` so exports can be reproducible).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping

STATUS_LIVE = "LIVE"
STATUS_SUPERSEDED = "SUPERSEDED"
STATUSES: tuple[str, ...] = (STATUS_LIVE, STATUS_SUPERSEDED)
LOG_SCHEMA = "council-lineage/v1"
DEFAULT_LOG_REL = "command-center/decision-log/council-lineage.json"
SCHEMA_REL = "tools/council/outcomes/lineage_record.schema.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "decision_id",
    "council_id",
    "question",
    "question_key",
    "verdict",
    "inputs",
    "deciding_rule",
    "tally",
    "dissents",
    "supersedes",
    "superseded_by",
    "status",
    "recorded_at",
)

_RECORDED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

LINEAGE_RECORD_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_REL,
    "title": "council lineage record",
    "type": "object",
    "additionalProperties": True,
    "required": list(REQUIRED_FIELDS),
    "properties": {
        "decision_id": {"type": "string", "minLength": 1},
        "council_id": {"type": "string", "minLength": 1},
        "question": {"type": "string", "minLength": 1},
        "question_key": {"type": "string", "minLength": 1},
        "verdict": {"type": "string", "minLength": 1},
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "ref"],
                "properties": {
                    "kind": {"type": "string", "minLength": 1},
                    "ref": {"type": "string", "minLength": 1},
                },
            },
        },
        "deciding_rule": {"type": "string", "minLength": 1},
        "tally": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {"type": "integer", "minimum": 0},
        },
        "dissents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["actor", "claim"],
                "properties": {
                    "actor": {"type": "string", "minLength": 1},
                    "claim": {"type": "string", "minLength": 1},
                },
            },
        },
        "supersedes": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "superseded_by": {"type": ["string", "null"], "minLength": 1},
        "status": {"type": "string", "enum": list(STATUSES)},
        "recorded_at": {"type": "string", "pattern": _RECORDED_AT_RE.pattern},
    },
}


class LineageSchemaError(ValueError):
    """A lineage record or log operation violates the lineage contract."""


# --------------------------------------------------------------------------- helpers
def _normalise_question(question: str) -> str:
    text = re.sub(r"[^0-9a-z]+", " ", str(question).casefold())
    return " ".join(text.split())


def question_key(question: str) -> str:
    """Stable key for a question: SHA-256 of its normalised text (case/punctuation-insensitive)."""
    normalised = _normalise_question(question)
    if not normalised:
        raise LineageSchemaError("question is empty")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _recorded_at() -> str:
    """UTC timestamp; ``SOURCE_DATE_EPOCH`` pins it for reproducible exports."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.strip().isdigit():
        moment = datetime.fromtimestamp(int(epoch.strip()), tz=timezone.utc)
    else:
        moment = datetime.now(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_verdict(verdict: Any) -> str:
    return " ".join(str(verdict).casefold().split())


def empty_log() -> dict[str, Any]:
    """A fresh council lineage log."""
    return {"schema": LOG_SCHEMA, "entries": []}


def sample_binding(
    decision_id: str,
    council_id: str,
    question: str,
    verdict: str,
    *,
    tally: Mapping[str, int] | None = None,
    dissents: Iterable[Mapping[str, Any]] | None = None,
    inputs: Iterable[Mapping[str, Any]] | None = None,
    rule_id: str = "majority-of-seated-voters",
) -> dict[str, Any]:
    """A council binding (the pre-export decision) in the shape :func:`build_record` accepts."""
    return {
        "decision_id": decision_id,
        "council_id": council_id,
        "question": question,
        "verdict": verdict,
        "tally": dict(tally) if tally is not None else {"for": 0, "against": 0, "abstain": 0},
        "dissents": [dict(d) for d in (dissents or [])],
        "inputs": [dict(i) for i in (inputs or [])],
        "deciding_rule": rule_id,
        "rule_id": rule_id,
    }


# --------------------------------------------------------------------------- records
def _require_text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise LineageSchemaError(f"{name} required (non-empty string)")
    return value


def validate_record(record: Mapping[str, Any]) -> None:
    """Raise :class:`LineageSchemaError` unless ``record`` is a complete, coherent lineage record."""
    if not isinstance(record, Mapping):
        raise LineageSchemaError("record is not an object")
    missing = [name for name in REQUIRED_FIELDS if name not in record]
    if missing:
        raise LineageSchemaError(f"missing fields {missing}")
    decision_id = _require_text(record, "decision_id")
    _require_text(record, "council_id")
    _require_text(record, "question")
    _require_text(record, "question_key")
    _require_text(record, "verdict")
    _require_text(record, "deciding_rule")

    inputs = record.get("inputs")
    if not isinstance(inputs, list):
        raise LineageSchemaError("inputs must be a list")
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise LineageSchemaError(f"inputs[{index}] is not an object")
        for name in ("kind", "ref"):
            if not isinstance(item.get(name), str) or not item[name].strip():
                raise LineageSchemaError(f"inputs[{index}].{name} required")

    tally = record.get("tally")
    if not isinstance(tally, Mapping) or not tally:
        raise LineageSchemaError("tally required (non-empty object of counts)")
    for name, count in tally.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise LineageSchemaError(f"tally[{name!r}] must be a non-negative integer")

    dissents = record.get("dissents")
    if not isinstance(dissents, list):
        raise LineageSchemaError("dissents must be a list")
    for index, item in enumerate(dissents):
        if not isinstance(item, Mapping):
            raise LineageSchemaError(f"dissents[{index}] is not an object")
        for name in ("actor", "claim"):
            if not isinstance(item.get(name), str) or not item[name].strip():
                raise LineageSchemaError(f"dissents[{index}].{name} required")

    supersedes = record.get("supersedes")
    if not isinstance(supersedes, list) or any(
        not isinstance(s, str) or not s.strip() for s in supersedes
    ):
        raise LineageSchemaError("supersedes must be a list of decision ids")
    if decision_id in supersedes:
        raise LineageSchemaError("a decision cannot supersede itself")

    superseded_by = record.get("superseded_by")
    if superseded_by is not None and (not isinstance(superseded_by, str) or not superseded_by.strip()):
        raise LineageSchemaError("superseded_by must be a decision id or null")
    if superseded_by == decision_id:
        raise LineageSchemaError("a decision cannot be superseded by itself")

    status = record.get("status")
    if status not in STATUSES:
        raise LineageSchemaError(f"status must be one of {list(STATUSES)}, got {status!r}")
    if status == STATUS_SUPERSEDED and superseded_by is None:
        raise LineageSchemaError("SUPERSEDED rows must name superseded_by")
    if status == STATUS_LIVE and superseded_by is not None:
        raise LineageSchemaError("LIVE rows cannot carry superseded_by")

    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str) or not _RECORDED_AT_RE.match(recorded_at):
        raise LineageSchemaError("recorded_at must be UTC ISO-8601 (YYYY-MM-DDTHH:MM:SSZ)")


def build_record(binding: Mapping[str, Any], supersedes: str | None = None) -> dict[str, Any]:
    """Export a council binding as a validated lineage record.

    ``deciding_rule`` (or legacy ``rule_id``) and ``tally`` are mandatory: a decision that
    cannot say how it was decided is not exportable.
    """
    if not isinstance(binding, Mapping):
        raise LineageSchemaError("binding is not an object")
    rule = binding.get("deciding_rule") or binding.get("rule_id")
    if not isinstance(rule, str) or not rule.strip():
        raise LineageSchemaError("deciding_rule required")
    if binding.get("tally") is None:
        raise LineageSchemaError("tally required")
    for name in ("decision_id", "council_id", "question", "verdict"):
        _require_text(binding, name)
    predecessor_ids = list(binding.get("supersedes") or [])
    if supersedes and supersedes not in predecessor_ids:
        predecessor_ids.append(supersedes)
    record = {
        "decision_id": binding["decision_id"],
        "council_id": binding["council_id"],
        "question": binding["question"],
        "question_key": binding.get("question_key") or question_key(binding["question"]),
        "verdict": binding["verdict"],
        "inputs": [dict(i) for i in (binding.get("inputs") or [])],
        "deciding_rule": rule,
        "tally": dict(binding["tally"]) if isinstance(binding["tally"], Mapping) else binding["tally"],
        "dissents": [dict(d) for d in (binding.get("dissents") or [])],
        "supersedes": predecessor_ids,
        "superseded_by": binding.get("superseded_by"),
        "status": binding.get("status") or STATUS_LIVE,
        "recorded_at": binding.get("recorded_at") or _recorded_at(),
    }
    validate_record(record)
    return record


def find_entry(doc: Mapping[str, Any], decision_id: str) -> dict[str, Any] | None:
    """The log entry with ``decision_id``, or ``None``."""
    for entry in doc.get("entries") or []:
        if isinstance(entry, dict) and entry.get("decision_id") == decision_id:
            return entry
    return None


def append_binding(doc: dict[str, Any], binding: Mapping[str, Any]) -> dict[str, Any]:
    """Export ``binding`` and append it to ``doc``; decision ids are unique within a log."""
    record = build_record(binding)
    if find_entry(doc, record["decision_id"]) is not None:
        raise LineageSchemaError(f"decision {record['decision_id']!r} is already in the log")
    doc.setdefault("entries", []).append(record)
    return record


def mark_predecessor(doc: dict[str, Any], older_id: str, newer_id: str) -> dict[str, Any]:
    """Stamp the older entry SUPERSEDED by ``newer_id`` and link the newer entry back to it.

    Raises :class:`LineageSchemaError` when the older entry is absent or already superseded
    by a different decision. Returns the marked older entry.
    """
    if older_id == newer_id:
        raise LineageSchemaError("a decision cannot supersede itself")
    older = find_entry(doc, older_id)
    if older is None:
        raise LineageSchemaError(f"cannot mark {older_id!r}: not in the log")
    current = older.get("superseded_by")
    if older.get("status") == STATUS_SUPERSEDED and current not in (None, newer_id):
        raise LineageSchemaError(f"{older_id!r} is already superseded by {current!r}")
    older["status"] = STATUS_SUPERSEDED
    older["superseded_by"] = newer_id
    newer = find_entry(doc, newer_id)
    if newer is not None:
        newer.setdefault("supersedes", [])
        if older_id not in newer["supersedes"]:
            newer["supersedes"].append(older_id)
    return older


def commit_overturn(
    doc: dict[str, Any],
    newer_binding: Mapping[str, Any],
    older_id: str,
    mark: bool = True,
) -> dict[str, Any]:
    """Append the overturning decision; with ``mark`` the predecessor is stamped SUPERSEDED.

    ``mark=False`` deliberately leaves two LIVE rows behind so
    :func:`scan_live_contradictions` can be shown to fire; it is the negative control, not
    a supported steady state.
    """
    if find_entry(doc, older_id) is None:
        raise LineageSchemaError(f"cannot overturn {older_id!r}: not in the log")
    newer = build_record(newer_binding, supersedes=older_id)
    if find_entry(doc, newer["decision_id"]) is not None:
        raise LineageSchemaError(f"decision {newer['decision_id']!r} is already in the log")
    doc.setdefault("entries", []).append(newer)
    if mark:
        mark_predecessor(doc, older_id, newer["decision_id"])
    return newer


# --------------------------------------------------------------------------- contradiction scan
@dataclass(frozen=True)
class ContradictionPair:
    """Two LIVE decisions answering the same question differently."""

    question_key: str
    left_id: str
    right_id: str
    left_verdict: str
    right_verdict: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContradictionScan:
    """Result of :func:`scan_live_contradictions`."""

    fired: bool = False
    live_count: int = 0
    questions_scanned: int = 0
    pairs: list[ContradictionPair] = field(default_factory=list)

    @property
    def conflicts(self) -> list[dict[str, Any]]:
        """Pairs grouped per question: ``[{question_key, ids}]``."""
        grouped: dict[str, list[str]] = {}
        for pair in self.pairs:
            ids = grouped.setdefault(pair.question_key, [])
            for decision_id in (pair.left_id, pair.right_id):
                if decision_id not in ids:
                    ids.append(decision_id)
        return [{"question_key": key, "ids": ids} for key, ids in grouped.items()]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fired": self.fired,
            "live_count": self.live_count,
            "questions_scanned": self.questions_scanned,
            "pairs": [pair.as_dict() for pair in self.pairs],
            "conflicts": self.conflicts,
        }


def scan_live_contradictions(doc: Mapping[str, Any]) -> ContradictionScan:
    """FIRE when two LIVE rows share a question_key but not a verdict; SILENT otherwise."""
    live = [
        entry
        for entry in doc.get("entries") or []
        if isinstance(entry, Mapping) and entry.get("status") == STATUS_LIVE
    ]
    by_question: dict[str, list[Mapping[str, Any]]] = {}
    for entry in live:
        key = entry.get("question_key") or question_key(entry.get("question") or "")
        by_question.setdefault(str(key), []).append(entry)
    pairs: list[ContradictionPair] = []
    for key in sorted(by_question):
        rows = by_question[key]
        for left, right in combinations(rows, 2):
            if _norm_verdict(left.get("verdict")) == _norm_verdict(right.get("verdict")):
                continue
            pairs.append(
                ContradictionPair(
                    question_key=key,
                    left_id=str(left.get("decision_id")),
                    right_id=str(right.get("decision_id")),
                    left_verdict=str(left.get("verdict")),
                    right_verdict=str(right.get("verdict")),
                )
            )
    return ContradictionScan(
        fired=bool(pairs),
        live_count=len(live),
        questions_scanned=len(by_question),
        pairs=pairs,
    )


# --------------------------------------------------------------------------- persistence
def render_markdown(doc: Mapping[str, Any]) -> str:
    """Human-readable lineage: one section per decision, supersession markers spelled out."""
    lines = ["# Council lineage", "", f"schema: `{doc.get('schema', LOG_SCHEMA)}`", ""]
    for entry in doc.get("entries") or []:
        lines.append(f"## {entry.get('decision_id')}")
        lines.append(f"- council: `{entry.get('council_id')}`")
        lines.append(f"- question: {entry.get('question')}")
        lines.append(f"- verdict: {entry.get('verdict')}")
        lines.append(f"- deciding_rule: `{entry.get('deciding_rule')}`")
        tally = entry.get("tally") or {}
        lines.append("- tally: " + ", ".join(f"{k}={v}" for k, v in tally.items()))
        lines.append(f"- status: {entry.get('status')}")
        if entry.get("superseded_by"):
            lines.append(f"- SUPERSEDED by `{entry['superseded_by']}`")
        if entry.get("supersedes"):
            lines.append("- supersedes: " + ", ".join(f"`{s}`" for s in entry["supersedes"]))
        for dissent in entry.get("dissents") or []:
            lines.append(f"- dissent ({dissent.get('actor')}): {dissent.get('claim')}")
        lines.append(f"- recorded_at: {entry.get('recorded_at')}")
        lines.append("")
    scan = scan_live_contradictions(doc)
    lines.append("## Contradiction scan")
    lines.append(f"- fired: {str(scan.fired).lower()}; live rows: {scan.live_count}")
    for pair in scan.pairs:
        lines.append(
            f"- CONTRADICTION `{pair.left_id}` ({pair.left_verdict}) vs "
            f"`{pair.right_id}` ({pair.right_verdict})"
        )
    lines.append("")
    return "\n".join(lines)


def save_log(doc: Mapping[str, Any], path: str | Path) -> Path:
    """Write the log as sorted JSON plus a sibling ``.md`` rendering; returns the JSON path."""
    for entry in doc.get("entries") or []:
        validate_record(entry)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    dest.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8")
    return dest


def load_log(path: str | Path) -> dict[str, Any]:
    """Read a log written by :func:`save_log`, validating every record."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        raise LineageSchemaError(f"{path} is not a council lineage log")
    for entry in doc["entries"]:
        validate_record(entry)
    return doc


__all__ = [
    "DEFAULT_LOG_REL",
    "LINEAGE_RECORD_SCHEMA",
    "LOG_SCHEMA",
    "REQUIRED_FIELDS",
    "SCHEMA_REL",
    "STATUSES",
    "STATUS_LIVE",
    "STATUS_SUPERSEDED",
    "ContradictionPair",
    "ContradictionScan",
    "LineageSchemaError",
    "append_binding",
    "build_record",
    "commit_overturn",
    "empty_log",
    "find_entry",
    "load_log",
    "mark_predecessor",
    "question_key",
    "render_markdown",
    "sample_binding",
    "save_log",
    "scan_live_contradictions",
    "validate_record",
]
