"""WFA-0086 intake corpus: 15 REPAIR candidates + 13 REPAIRED-route blueprints.

The Windows 284-record registry is not on this Linux worktree. These ids are
namespaced wfa0086-* so they cannot be confused with wf-saved-* registry ids.
Each subject is an executable broken workflow whose failure is reproduced red
before any repair is attempted.
"""
from __future__ import annotations

from typing import Any

# Distinctive strings probes and emit can anchor.
NO_REPAIR_WITHOUT_RED = (
    "no repair may begin on a candidate whose failure was not first reproduced red"
)
UNREPRODUCIBLE_RECLASSIFY = (
    "a candidate whose failure cannot be reproduced is reclassified rather than repaired blind"
)
RED_TEST_KEPT_AS_REGRESSION = (
    "the red test must be kept and become the regression for that repair"
)
CAPTURE_BLOCKER_AS_FAILING_TEST = (
    "capture the known blocker as a failing test"
)

EXPECTED_GOOD = (
    "exit 0 and write a non-empty JSON object "
    '{"ok": true, "id": "<subject-id>"} at the contracted artifact path'
)

RUNNER = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0086/runner.py"
)

# defect_id -> (short name, observed wrong behaviour)
DEFECTS: dict[str, tuple[str, str]] = {
    "green_not_live": (
        "green-not-live",
        "exit 0 with no artifact on disk (exit code zero alone is never success)",
    ),
    "malformed_json": (
        "malformed-json",
        "exit 0 writing a non-JSON payload at the artifact path",
    ),
    "wall_clock": (
        "wall-clock",
        "artifact embeds time.time() so two runs cannot replay",
    ),
    "unseeded_random": (
        "unseeded-random",
        "artifact embeds unseeded random.random() so replay diverges",
    ),
    "job_receipt": (
        "fire-and-forget",
        "returns a background job-id receipt instead of waiting for the artifact",
    ),
    "no_agent_timeout": (
        "fan-out-deadlock",
        "parallel barrier has no per-agent timeout; a hung unit deadlocks the cohort",
    ),
    "fanin_accepts_invalid": (
        "schema-invalid-fanin",
        "fan-in accepts a schema-invalid sibling result as success",
    ),
    "digest_missing_file": (
        "phantom-digest",
        "reports a sha256 for a path that does not exist",
    ),
    "shared_index": (
        "shared-git-index",
        "two repairs share one lock/index file so a sibling add can sweep work",
    ),
    "string_interp": (
        "string-interpolated-args",
        "command line built by f-string interpolation; a space in the id splits argv",
    ),
    "env_path": (
        "env-dependent-path",
        "artifact path assembled from $HOME so machines diverge",
    ),
    "crlf_hash": (
        "crlf-hash-lie",
        "writes CRLF bytes while claiming an LF digest",
    ),
    "swallowed_exception": (
        "swallowed-exception",
        "except: pass then exit 0, hiding the failure",
    ),
    "memory_only_partial": (
        "memory-only-partial",
        "partial result held in memory; nothing durable on disk (write-as-you-go missed)",
    ),
    "inline_prompt_overflow": (
        "inline-prompt-overflow",
        "oversized inline prompt dispatched on the command line instead of a prompt file",
    ),
}

REPAIR_CANDIDATES: list[tuple[str, str]] = [
    ("wfa0086-c01-green-not-live", "green_not_live"),
    ("wfa0086-c02-malformed-json", "malformed_json"),
    ("wfa0086-c03-wall-clock", "wall_clock"),
    ("wfa0086-c04-unseeded-random", "unseeded_random"),
    ("wfa0086-c05-job-receipt", "job_receipt"),
    ("wfa0086-c06-no-agent-timeout", "no_agent_timeout"),
    ("wfa0086-c07-fanin-invalid", "fanin_accepts_invalid"),
    ("wfa0086-c08-phantom-digest", "digest_missing_file"),
    ("wfa0086-c09-shared-index", "shared_index"),
    ("wfa0086-c10-string-interp", "string_interp"),
    ("wfa0086-c11-env-path", "env_path"),
    ("wfa0086-c12-crlf-hash", "crlf_hash"),
    ("wfa0086-c13-swallowed", "swallowed_exception"),
    ("wfa0086-c14-memory-partial", "memory_only_partial"),
    ("wfa0086-c15-prompt-overflow", "inline_prompt_overflow"),
]

# 13 blueprints: by_route REPAIR and by_state REPAIRED, still failing.
REPAIRED_ROUTE: list[tuple[str, str]] = [
    ("wfa0086-b01-repaired-green-not-live", "green_not_live"),
    ("wfa0086-b02-repaired-malformed", "malformed_json"),
    ("wfa0086-b03-repaired-wall-clock", "wall_clock"),
    ("wfa0086-b04-repaired-random", "unseeded_random"),
    ("wfa0086-b05-repaired-job-receipt", "job_receipt"),
    ("wfa0086-b06-repaired-no-timeout", "no_agent_timeout"),
    ("wfa0086-b07-repaired-fanin", "fanin_accepts_invalid"),
    ("wfa0086-b08-repaired-phantom-digest", "digest_missing_file"),
    ("wfa0086-b09-repaired-shared-index", "shared_index"),
    ("wfa0086-b10-repaired-interp", "string_interp"),
    ("wfa0086-b11-repaired-env-path", "env_path"),
    ("wfa0086-b12-repaired-crlf", "crlf_hash"),
    ("wfa0086-b13-repaired-swallowed", "swallowed_exception"),
]

CONTROL_UNREPRODUCIBLE_ID = "wfa0086-ctrl-cannot-reproduce"
CONTROL_NO_RED_ID = "wfa0086-ctrl-no-red-test"


def _subject(
    sid: str,
    defect: str,
    kind: str,
    classification: str,
    *,
    claimed_state: str | None = None,
    route: str | None = None,
    has_command: bool = True,
) -> dict[str, Any]:
    short, observed = DEFECTS[defect]
    rec: dict[str, Any] = {
        "id": sid,
        "kind": kind,
        "classification": classification,
        "defect": defect,
        "defect_short": short,
        "family": "WFA-0086-intake-fixture",
        "expected": EXPECTED_GOOD.replace("<subject-id>", sid),
        "claimed_wrong": observed,
        "artifact_rel": f"command-center/p2-wave/probes/WFA-0086/scratch/{sid}/result.json",
        "has_command": has_command,
        "command": f"{RUNNER} {sid}" if has_command else "",
    }
    if claimed_state:
        rec["claimed_state"] = claimed_state
    if route:
        rec["route"] = route
    return rec


def catalog() -> list[dict[str, Any]]:
    rows = [
        _subject(sid, defect, "candidate-REPAIR", "REPAIR")
        for sid, defect in REPAIR_CANDIDATES
    ]
    rows.extend(
        _subject(
            sid,
            defect,
            "blueprint-REPAIRED-route",
            "REPAIR",
            claimed_state="REPAIRED",
            route="REPAIR",
        )
        for sid, defect in REPAIRED_ROUTE
    )
    return rows


def control_unreproducible() -> dict[str, Any]:
    rec = _subject(
        CONTROL_UNREPRODUCIBLE_ID,
        "green_not_live",
        "candidate-REPAIR",
        "REPAIR",
    )
    rec["defect"] = "actually_good"
    rec["claimed_wrong"] = "claimed green-not-live but the command meets expected"
    rec["expected"] = EXPECTED_GOOD.replace("<subject-id>", CONTROL_UNREPRODUCIBLE_ID)
    return rec


def control_no_red() -> dict[str, Any]:
    rec = _subject(
        CONTROL_NO_RED_ID,
        "green_not_live",
        "candidate-REPAIR",
        "REPAIR",
        has_command=False,
    )
    rec["claimed_wrong"] = "no command was supplied so the failure was never reproduced"
    return rec


def by_id() -> dict[str, dict[str, Any]]:
    out = {r["id"]: r for r in catalog()}
    out[CONTROL_UNREPRODUCIBLE_ID] = control_unreproducible()
    out[CONTROL_NO_RED_ID] = control_no_red()
    return out
