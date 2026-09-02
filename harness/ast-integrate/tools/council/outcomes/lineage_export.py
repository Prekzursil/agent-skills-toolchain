"""Council decision lineage: supersession markers on overturn."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_LIVE = "LIVE"
STATUS_SUPERSEDED = "SUPERSEDED"
DEFAULT_LOG_REL = "command-center/design/council/decision-lineage.jsonl"

REQUIRED_FIELDS = (
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


class LineageSchemaError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def question_key(question: str) -> str:
    return hashlib.sha256(str(question).strip().encode("utf-8")).hexdigest()


def empty_log() -> dict[str, Any]:
    return {"schema": "council-lineage/v1", "entries": []}


def sample_binding(
    decision_id: str,
    council_id: str,
    question: str,
    verdict: str,
    *,
    tally: dict[str, int] | None = None,
    dissents: list | None = None,
    inputs: list | None = None,
    rule_id: str = "majority-of-seated-voters",
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "council_id": council_id,
        "question": question,
        "verdict": verdict,
        "tally": dict(tally or {"for": 0, "against": 0, "abstain": 0}),
        "dissents": list(dissents or []),
        "inputs": list(inputs or []),
        "deciding_rule": rule_id,
        "rule_id": rule_id,
    }


def validate_record(record: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_FIELDS if k not in record]
    if missing:
        raise LineageSchemaError(f"missing fields {missing}")
    if not record.get("deciding_rule"):
        raise LineageSchemaError("deciding_rule required")
    if record.get("tally") is None:
        raise LineageSchemaError("tally required")


def build_record(binding: dict[str, Any], supersedes: str | None = None) -> dict[str, Any]:
    rule = binding.get("deciding_rule") or binding.get("rule_id")
    if not rule:
        raise LineageSchemaError("deciding_rule required")
    if binding.get("tally") is None:
        raise LineageSchemaError("tally required")
    rec = {
        "decision_id": binding["decision_id"],
        "council_id": binding["council_id"],
        "question": binding["question"],
        "question_key": binding.get("question_key") or question_key(binding["question"]),
        "verdict": binding["verdict"],
        "inputs": list(binding.get("inputs") or []),
        "deciding_rule": rule,
        "tally": dict(binding["tally"]),
        "dissents": list(binding.get("dissents") or []),
        "supersedes": [supersedes] if supersedes else list(binding.get("supersedes") or []),
        "superseded_by": binding.get("superseded_by"),
        "status": binding.get("status") or STATUS_LIVE,
        "recorded_at": binding.get("recorded_at") or _now(),
    }
    validate_record(rec)
    return rec


def append_binding(doc: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    rec = build_record(binding)
    doc.setdefault("entries", []).append(rec)
    return rec


def mark_predecessor(older: dict[str, Any], newer_id: str) -> None:
    older["status"] = STATUS_SUPERSEDED
    older["superseded_by"] = newer_id


def commit_overturn(
    doc: dict[str, Any],
    newer_binding: dict[str, Any],
    older_id: str,
    mark: bool = True,
) -> dict[str, Any]:
    newer = build_record(newer_binding, supersedes=older_id)
    if older_id not in newer["supersedes"]:
        newer["supersedes"].append(older_id)
    doc.setdefault("entries", []).append(newer)
    if mark:
        for entry in doc["entries"]:
            if entry.get("decision_id") == older_id:
                mark_predecessor(entry, newer["decision_id"])
    return newer


@dataclass
class ContradictionScan:
    fired: bool = False
    live_count: int = 0
    conflicts: list = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fired": self.fired,
            "live_count": self.live_count,
            "conflicts": list(self.conflicts),
        }


def scan_live_contradictions(doc: dict[str, Any]) -> ContradictionScan:
    live = [e for e in doc.get("entries") or [] if e.get("status") == STATUS_LIVE]
    by_q: dict[str, list] = {}
    for e in live:
        by_q.setdefault(e.get("question_key") or question_key(e.get("question") or ""), []).append(e)
    conflicts = []
    for key, rows in by_q.items():
        verdicts = {r.get("verdict") for r in rows}
        if len(verdicts) > 1:
            conflicts.append({"question_key": key, "ids": [r["decision_id"] for r in rows]})
    return ContradictionScan(
        fired=bool(conflicts),
        live_count=len(live),
        conflicts=conflicts,
    )


def save_log(doc: dict[str, Any], path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = ["# Council lineage", ""]
    for entry in doc.get("entries") or []:
        md_lines.append(f"## {entry.get('decision_id')}")
        md_lines.append(f"status: {entry.get('status')}")
        if entry.get("superseded_by"):
            md_lines.append(f"SUPERSEDED by `{entry['superseded_by']}`")
        if entry.get("supersedes"):
            md_lines.append("supersedes: " + ", ".join(f"`{s}`" for s in entry["supersedes"]))
        md_lines.append("")
    dest.with_suffix(".md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
