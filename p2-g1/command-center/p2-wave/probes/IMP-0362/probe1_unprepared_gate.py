#!/usr/bin/env python3
"""IMP-0362 probe1: the prep gate blocks an unprepared participant.

Both-states: a seat with no artifact, an unparseable artifact, or empty notes
is refused via UnpreparedError; a genuinely prepared seat (resolvable source
anchor + successful Read tool-call + notes sharing a distinctive token with
the fetched bytes) is allowed to speak, and no assertion detector fires on it.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.prep import (  # noqa: E402
    FIRED_ASSERT_WITHOUT_TOOL_CALLS,
    PrepGate,
    UnpreparedError,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0362-probe1 {msg}")
    return 1


def build_prepared(root: Path) -> None:
    seat = root / "alice"
    seat.mkdir(parents=True)
    (seat / "brief.md").write_text(
        "The quorum floor for HIGH is five seats and the reviewer count is two. "
        "Evidence standard peer-reviewed-only applies.\n", encoding="utf-8")
    (seat / "notes.md").write_text(
        "Alice notes: the quorum floor detail above is the load-bearing line.\n",
        encoding="utf-8")
    (seat / "prep.json").write_text(json.dumps({
        "seat": "alice", "notes": "notes.md", "sources": ["brief.md"],
    }), encoding="utf-8")
    (seat / "tool_log.json").write_text(json.dumps({"tool_calls": [
        {"tool": "Read", "target": "brief.md", "status": "ok"},
    ]}), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gate = PrepGate(root)

        # Bad state 1: no artifact at all.
        (root / "bob").mkdir()
        try:
            gate.require_prepared("bob")
            return fail("no-artifact-seat-allowed")
        except UnpreparedError as exc:
            if "preparation-artifact-absent-or-unparseable" not in exc.reasons:
                return fail(f"wrong-reason:{exc.reasons}")

        # Bad state 2: artifact present but unparseable.
        (root / "carol-empty").mkdir()
        (root / "carol-empty" / "prep.json").write_text("{nope", encoding="utf-8")
        try:
            gate.require_prepared("carol-empty")
            return fail("unparseable-artifact-allowed")
        except UnpreparedError:
            pass

        # Bad state 3: notes absent while anchors named.
        (root / "dave").mkdir()
        (root / "dave" / "prep.json").write_text(json.dumps({
            "sources": ["brief.md"],
        }), encoding="utf-8")
        try:
            gate.require_prepared("dave")
            return fail("notes-absent-allowed")
        except UnpreparedError as exc:
            if "notes-absent-or-empty" not in exc.reasons:
                return fail(f"wrong-reason-2:{exc.reasons}")

        # Bad state 4: honest missing fetch -> anchor-without-successful-fetch,
        # NOT the assertion-detector (the honest case has its own reason).
        (root / "erin").mkdir()
        (root / "erin" / "prep.json").write_text(json.dumps({
            "sources": ["brief.md"], "notes": "notes.md",
        }), encoding="utf-8")
        (root / "erin" / "notes.md").write_text("some real notes\n", encoding="utf-8")
        try:
            gate.require_prepared("erin")
            return fail("no-fetch-allowed")
        except UnpreparedError as exc:
            if "anchor-without-successful-fetch" not in exc.reasons:
                return fail(f"wrong-reason-3:{exc.reasons}")
            if FIRED_ASSERT_WITHOUT_TOOL_CALLS in exc.reasons:
                return fail("honest-missing-misclassified-as-assertion")

        # Good state: fully prepared seat speaks.
        build_prepared(root)
        verdict = gate.require_prepared("alice")
        if verdict.get("allowed_to_speak") is not True:
            return fail("prepared-seat-refused")
        gate.before_turn("alice")

    print(json.dumps({
        "probe": "probe1-unprepared-gate", "unit_id": "IMP-0362", "pass": True,
        "refusals": ["artifact-absent", "artifact-unparseable",
                     "notes-absent", "fetch-missing"],
        "good_state_allowed": "alice",
    }, sort_keys=True))
    print("SUCCESS:IMP-0362-probe1 gate blocks unprepared seats; prepared seat speaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
