"""Frozen shared contract for the Codex-on-Databricks fan-out harness."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

RAIL = {
    "policy_id": "0002189219BF8EF3",
    "node_type_id": "r5d.2xlarge",
    "spark_version": "15.4.x-scala2.12",
    "concurrency": 48,
    "stagger_s": "3.0",
    "scope": "codex-harness-prekzursil",
    "profile": "bolt-datascience",
    "notebook": "/Users/costin.ionescu@bolt.eu/codex-batch/batch_runner",
    "instance_profile": "arn:aws:iam::287845475429:instance-profile/datascience-instance-profile",
    "s3_log_dest": "s3://bolt-databricks-logs/cluster-logs/bolt-datascience",
    "s3_region": "eu-central-1",
}
# version OBSERVED not pinned — node install is `npm install -g @openai/codex` (latest).
CODEX = {"model": "gpt-5.6-sol", "effort": "ultra", "cli_version_at_proof": "0.144.6"}

PER_LANE_FLOORS = {
    "coverage": 1024,
    "smoke": 1024,
    "default": 1024,
}  # all >= node's 1024 gate


def floor_for(lane: str) -> int:
    return PER_LANE_FLOORS.get(lane, PER_LANE_FLOORS["default"])


SENTINEL_TAIL_BYTES = 600
"""How far from the end the completion sentinel must appear -- the single source of truth for both
gates (and_gate_artifact here and the structural gate in gate.py).

Measured in bytes, not lines: agents append trailing prose of unpredictable line length, and a
line-based window silently widens on a file with long lines.
"""


LANE_SCHEMAS = {
    "coverage": {
        "file",
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_pushed",
    },
    "smoke": {"echo"},
}
SKELETON = "UNKNOWN - not yet measured"  # ASCII — cp1252-safe round trip


@dataclass(frozen=True)
class Unit:
    id: str
    lane: str
    prompt: str
    artifact: str
    timeout_s: int = 900
    meta: dict = field(default_factory=dict)


def and_gate_artifact(unit_id, artifact, min_bytes=1024) -> tuple[bool, str, int]:
    """Clauses 2-4: exists AND >= min_bytes AND sentinel in last SENTINEL_TAIL_BYTES bytes.
    Ported from the proven completion_predicate.py (passed the 67/67 run)."""
    artifact = Path(artifact)
    if not artifact.is_file():
        return False, "no-artifact", 0
    size = artifact.stat().st_size
    if size < min_bytes:
        return False, f"artifact-too-small-{size}", size
    try:
        tail = artifact.read_bytes()[-SENTINEL_TAIL_BYTES:].decode(
            "utf-8", errors="replace"
        )
    except OSError as e:
        return False, f"unreadable-{e}", size
    if f"UNIT-COMPLETE: {unit_id}" not in tail:
        return False, "missing-UNIT-COMPLETE", size
    return True, "and-gate-pass", size


def schema_valid(unit: Unit, artifact) -> tuple[bool, str]:
    """Clause 5: artifact carries every required lane field AND is not an all-UNKNOWN skeleton
    (which means the unit died before measuring). Reads utf-8; the ASCII sentinel round-trips
    even from a platform-default write, so the guard cannot be silently defeated on cp1252."""
    artifact = Path(artifact)
    if not artifact.is_file():
        return False, "no-artifact"
    text = artifact.read_text(encoding="utf-8", errors="replace")
    required = LANE_SCHEMAS.get(unit.lane, set())
    missing = sorted(f for f in required if f not in text)
    if missing:
        return False, "schema-missing-fields:" + ",".join(missing)
    # per-FIELD skeleton check (not a raw count): flag only when EVERY required field's own line
    # still holds the sentinel. A raw `text.count(SKELETON) >= len(required)` false-FAILs a
    # single-field lane (smoke) on one incidental sentinel occurrence in free prose.
    if required and sum(
        1
        for f in required
        if re.search(rf"^\s*{re.escape(f)}\s*:.*{re.escape(SKELETON)}", text, re.M)
    ) >= len(required):
        return False, "all-unknown-skeleton"
    return True, "schema-ok"
