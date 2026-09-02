#!/usr/bin/env python3
"""Council v1→v2 envelope migration with named refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SOURCE_VERSION = 1
TARGET_VERSION = 2
MIGRATION_ID = "council-envelope-v1-to-v2"
SHAPE_CHANGE_PROPERTY = "participants"

V1_PROPERTIES = [
    "schema_version",
    "id",
    "title",
    "purpose",
    "participants",
    "roles",
    "engagement",
    "budgets",
    "evidence",
    "voting",
    "stopping",
    "outcomes",
    "integrity",
]
V1_REQUIRED = [p for p in V1_PROPERTIES if p != "schema_version"]

FIELD_MAPPING = [
    {"v1": "schema_version", "v2": "schema_version", "transform": "identity"},
    {"v1": "id", "v2": "charter.id", "transform": "wrap-charter"},
    {"v1": "title", "v2": "charter.title", "transform": "wrap-charter"},
    {"v1": "purpose", "v2": "charter.purpose", "transform": "wrap-charter"},
    {"v1": "participants", "v2": "participants", "transform": "names_to_seats"},
    {"v1": "roles", "v2": "roles", "transform": "identity"},
    {"v1": "engagement", "v2": "engagement", "transform": "identity"},
    {"v1": "budgets", "v2": "budgets", "transform": "identity"},
    {"v1": "evidence", "v2": "evidence", "transform": "identity"},
    {"v1": "voting", "v2": "voting", "transform": "wrap-method"},
    {"v1": "stopping", "v2": "stopping", "transform": "identity"},
    {"v1": "outcomes", "v2": "outcomes", "transform": "identity"},
    {"v1": "integrity", "v2": "integrity", "transform": "identity"},
]


class MigrationRequired(Exception):
    pass


def refusal_message(source: int, target: int, mid: str) -> str:
    return (
        f"MIGRATION-REQUIRED source_version={source} target_version={target} "
        f"migration_id={mid}"
    )


def is_unmigrated(spec: dict[str, Any]) -> bool:
    """True when ``spec`` still carries a pre-v2 envelope (or no version at all)."""
    return spec.get("schema_version", SOURCE_VERSION) != TARGET_VERSION


def run_with_gate(
    spec: dict[str, Any],
    ballots: dict[str, str] | None = None,
    *,
    version_check: bool = True,
) -> dict[str, Any]:
    """Run the v2 runtime behind the migration gate and report what happened.

    Returns an envelope rather than raising so callers can tell the three states
    apart: ``ok`` (a decision was produced), ``error`` (``"MigrationRequired"``
    when the gate refused an un-migrated envelope) and ``silent_run`` (a decision
    was produced for an un-migrated envelope because the gate was bypassed with
    ``version_check=False`` — the failure mode the gate exists to prevent).
    """
    try:
        result = execute_v2(spec, ballots or {}, version_check=version_check)
    except MigrationRequired as exc:
        return {
            "ok": False,
            "silent_run": False,
            "error": type(exc).__name__,
            "message": str(exc),
            "result": None,
            "version_check": version_check,
        }
    return {
        "ok": True,
        "silent_run": is_silent_run(spec, result),
        "error": None,
        "message": None,
        "result": result,
        "version_check": version_check,
    }


def is_silent_run(spec: dict[str, Any], outcome: Any = None) -> bool:
    """Classify an execution outcome for ``spec`` as a silent run or not.

    A silent run is a v2 decision produced for an envelope that was never
    migrated. ``outcome`` may be the decision dict the runtime returned, the
    ``MigrationRequired`` refusal it raised, or ``None`` (in which case the
    question is whether running ``spec`` unchecked *would* be silent).
    """
    if not is_unmigrated(spec):
        return False
    if outcome is None:
        return True
    if isinstance(outcome, BaseException):
        return False
    if isinstance(outcome, dict):
        decided = outcome.get("decision") is not None or outcome.get("status") == "decided"
        return bool(decided and outcome.get("runtime", "v2") == "v2")
    return False


def refuse_unmigrated(doc: dict[str, Any]) -> None:
    ver = doc.get("schema_version", SOURCE_VERSION)
    if ver != TARGET_VERSION:
        raise MigrationRequired(refusal_message(SOURCE_VERSION, TARGET_VERSION, MIGRATION_ID))


def canonical(doc: dict[str, Any]) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def migrate_v1_to_v2(v1: dict[str, Any]) -> dict[str, Any]:
    seats = [{"id": name, "role": "member"} for name in v1.get("participants") or []]
    voting = v1.get("voting")
    if isinstance(voting, str):
        voting = {"method": voting}
    return {
        "schema_version": TARGET_VERSION,
        "charter": {
            "id": v1.get("id"),
            "title": v1.get("title"),
            "purpose": v1.get("purpose"),
        },
        "participants": seats,
        "roles": v1.get("roles"),
        "engagement": v1.get("engagement"),
        "budgets": v1.get("budgets"),
        "evidence": v1.get("evidence"),
        "voting": voting,
        "stopping": v1.get("stopping"),
        "outcomes": v1.get("outcomes"),
        "integrity": v1.get("integrity"),
        "meta": {"migration_id": MIGRATION_ID, "source_version": SOURCE_VERSION},
    }


def demote_v2_to_v1(v2: dict[str, Any]) -> dict[str, Any]:
    charter = v2.get("charter") or {}
    seats = v2.get("participants") or []
    names = [s.get("id") for s in seats if isinstance(s, dict)]
    voting = v2.get("voting")
    if isinstance(voting, dict):
        voting = voting.get("method")
    return {
        "schema_version": SOURCE_VERSION,
        "id": charter.get("id"),
        "title": charter.get("title"),
        "purpose": charter.get("purpose"),
        "participants": names,
        "roles": v2.get("roles"),
        "engagement": v2.get("engagement"),
        "budgets": v2.get("budgets"),
        "evidence": v2.get("evidence"),
        "voting": voting,
        "stopping": v2.get("stopping"),
        "outcomes": v2.get("outcomes"),
        "integrity": v2.get("integrity"),
    }


def execute_v1(spec: dict[str, Any], ballots: dict[str, str]) -> dict[str, Any]:
    tally: dict[str, int] = {}
    for vote in ballots.values():
        tally[vote] = tally.get(vote, 0) + 1
    decision = max(tally.items(), key=lambda kv: (kv[1], kv[0] != "defer"))[0]
    if "freeze" in tally and tally["freeze"] >= (len(ballots) + 1) // 2:
        decision = "freeze"
    return {
        "decision": decision,
        "method": spec.get("voting") if isinstance(spec.get("voting"), str) else "majority",
        "runtime": "v1",
        "schema_version": SOURCE_VERSION,
        "seated_votes": len(ballots),
        "status": "decided",
        "tally": tally,
    }


def execute_v2(
    spec: dict[str, Any],
    ballots: dict[str, str],
    *,
    version_check: bool = False,
) -> dict[str, Any]:
    if version_check:
        refuse_unmigrated(spec)
    tally: dict[str, int] = {}
    for vote in ballots.values():
        tally[vote] = tally.get(vote, 0) + 1
    decision = "freeze" if tally.get("freeze", 0) >= (len(ballots) + 1) // 2 else max(tally, key=tally.get)
    method = (spec.get("voting") or {}).get("method") if isinstance(spec.get("voting"), dict) else "majority"
    return {
        "decision": decision,
        "method": method,
        "runtime": "v2",
        "schema_version": TARGET_VERSION,
        "seated_votes": len(ballots),
        "status": "decided",
        "tally": tally,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "refuse":
        print("usage: migrate.py refuse <v1.json>", file=sys.stderr)
        return 2
    path = Path(args[1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    try:
        refuse_unmigrated(doc)
    except MigrationRequired as exc:
        print(str(exc), file=sys.stderr)
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
