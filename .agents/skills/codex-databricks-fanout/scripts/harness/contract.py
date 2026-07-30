"""Frozen shared contract for the Codex-on-Databricks fan-out harness."""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Node sizing: r5d.2xlarge (8 vCPU / 64 GB) runs the concurrency=48 fan-out ~6x
# CPU-oversubscribed. The policy allows node_type_id: unlimited, BUT ALSO caps
# dbus_per_hour at 18 (validation error, measured 2026-07-27) -- so the ceiling is DBU,
# not vCPU. r6id.32xlarge is 32.64 DBU (rejected); r6id.16xlarge (64 vCPU / 512 GB)
# validates under the cap and is the largest that does -- ~1.3 cores + 10 GB per unit at
# 48-wide, 8x the old node. Override with DERIVE_NODE_TYPE for a smaller/cheaper run
# (DERIVE_NODE_TYPE=r5d.2xlarge restores the previous sizing).
_NODE = os.environ.get("DERIVE_NODE_TYPE", "r6id.16xlarge")

RAIL = {
    "policy_id": "0002189219BF8EF3",
    "node_type_id": _NODE,
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
# [G3-FIX #3] version OBSERVED not pinned -- node install is `npm install -g
# @openai/codex` (latest). The node runs `codex exec --ignore-user-config`, so
# ~/.codex/config.toml does NOT apply there -- the owner's fast + max-efficiency +
# full-permission profile must be passed EXPLICITLY via -c on the command.
CODEX = {
    "model": "gpt-5.6-sol",
    "effort": "ultra",
    "cli_version_at_proof": "0.144.6",
    # NOT "fast": codex 0.145 has NO `fast` config key ("fast-mode" is only a
    # TUI/status-line state); service_tier=priority is the headless-exec
    # fast/priority-serving lever.
    "service_tier": "priority",
    # approval_policy + sandbox_mode record the INTENDED posture; the node APPLIES perms
    # via the `--dangerously-bypass-approvals-and-sandbox` FLAG, not via -c.
    "approval_policy": "never",
    "sandbox_mode": "danger-full-access",
}


def node_codex_flags() -> str:
    """The -c flags the node's `codex exec` carries BEYOND its permission flag (because
    --ignore-user-config drops ~/.codex/config.toml). The node bypasses approvals+sandbox
    via the `--dangerously-bypass-approvals-and-sandbox` FLAG (not -c); these -c restore
    the owner's fast (priority tier) + ultra-effort profile. Applied + verified on the
    live batch_runner 2026-07-24."""
    return (
        f"-c service_tier={CODEX['service_tier']} "
        f"-c model_reasoning_effort={CODEX['effort']}"
    )


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


DEFAULT_UNIT_TIMEOUT_S = 900
"""Default per-unit wall-clock cap handed to the node's `codex exec` (the Unit.timeout_s default).

A positive int, NOT None, even though `Unit.timeout_s` is typed `int | None` and the owner's stated
posture is "no timeout". `build_batch` emits the `timeout_s` key UNCONDITIONALLY, so ANY None --
default or explicit -- reaches the node as `"timeout_s": null`, and `batch_runner.py`'s
`int(u.get("timeout_s", 2400))` then raises
`TypeError: int() argument must be ... not 'NoneType'`: the key EXISTS, so the node's own 2400
fallback never applies and every unit fails. Executable-proven 2026-07-29.

So the `int | None` type makes the no-cap posture EXPRESSIBLE but not yet usable end-to-end -- it is
blocked on one line at that call site (`int(u.get("timeout_s") or 2400)`). Until then this default
stays at the value the harness has always shipped.
"""


LANE_SCHEMAS = {
    # patch_file is REQUIRED: the node is ephemeral, so a commit reported only as a local
    # sha in branch_ready is lost work. The gate must see the export was at least
    # attempted (a failed export reports `patch_file: none`, which is honest and still
    # gates).
    #
    # branch_ready, NOT the older `branch_pushed`: R1 forbids a write token on the node, so
    # the node clones READ-ONLY and commits LOCALLY -- a field named `branch_pushed` would
    # assert a push that cannot happen. Any producer or consumer still emitting/expecting
    # `branch_pushed` fails clause 5 against this schema.
    "coverage": {
        "file",
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_ready",
        "patch_file",
    },
    # Research units are READ-ONLY: no branch, no patch -- the artifact IS the deliverable.
    # `confidence` is required so an unevidenced claim cannot pass as a measured one.
    "research": {
        "target",
        "lens",
        "findings",
        "severity",
        "evidence",
        "recommendation",
        "confidence",
    },
    # Derive units re-adjudicate an existing finding; READ-ONLY, so no branch and no patch.
    # `actionable` is required so a STILL_TRUE verdict must commit to whether it is worth
    # acting on, rather than leaving that inference to the harvester.
    "derive": {"unit", "verdict", "severity", "evidence", "targets", "actionable"},
    "smoke": {"echo"},
}
SKELETON = "UNKNOWN - not yet measured"  # [G3-FIX #1] ASCII -- cp1252-safe round trip


@dataclass(frozen=True)
class Unit:
    id: str
    lane: str
    prompt: str
    artifact: str
    # `int | None`: None = NO per-unit node cap (the owner's "no timeout" posture), kept
    # expressible. The DEFAULT is deliberately DEFAULT_UNIT_TIMEOUT_S and not None, and a
    # None passed here is not yet usable end-to-end -- see that constant's docstring.
    timeout_s: int | None = DEFAULT_UNIT_TIMEOUT_S
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
    # [G5-FIX] per-FIELD skeleton check (not a raw count): flag only when EVERY required field's
    # own line still holds the sentinel. A raw `text.count(SKELETON) >= len(required)` false-FAILs
    # a single-field lane (smoke) on one incidental sentinel occurrence in free prose.
    if required and sum(
        1
        for f in required
        if re.search(rf"^\s*{re.escape(f)}\s*:.*{re.escape(SKELETON)}", text, re.M)
    ) >= len(required):
        return False, "all-unknown-skeleton"
    return True, "schema-ok"
