"""Both-states tests for the typed handoff API (IMP-0414).

Runnable as a script (emit.py invokes this file with python3 -B) and as pytest.
The live catalog receipt is not required: every case builds its payload here.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handoff as H  # noqa: E402

SENTINEL = "SENTINEL:IMP-0414:HANDOFF-TYPED-ONLY"
RAW = (
    "=== previous agent stdout ===\n"
    "Paste this blob as the next agent's prefix.\n"
    "untyped transcript body\n"
)


def _goal(**extra):
    body = {
        "statement": "typed handoff only",
        "exact_target": "raw string rejected at the boundary",
        "reanchored": True,
    }
    body.update(extra)
    return H.make_section(
        "goal",
        "Re-anchored goal",
        body,
        anchors=[{"path": "tools/command-center/handoff.py", "claim": "boundary"}],
        id="goal",
    )


def _context():
    return H.make_section(
        "context",
        "Context",
        {"replaced_practice": "raw-output prefix passing"},
        id="context",
    )


class TestHandoffBoundary(unittest.TestCase):
    def test_raw_string_raises_at_accept(self):
        with self.assertRaises(H.HandoffBoundaryError) as ctx:
            H.accept_handoff(RAW)
        self.assertTrue(ctx.exception.trace.get("refused") is True)
        self.assertEqual(ctx.exception.trace.get("error_type"), "HandoffBoundaryError")
        self.assertEqual(ctx.exception.trace.get("payload_type"), "str")
        self.assertEqual(ctx.exception.trace.get("boundary"), "typed-handoff")

    def test_raw_bytes_raises_at_accept(self):
        with self.assertRaises(H.HandoffBoundaryError):
            H.accept_handoff(RAW.encode("utf-8"))

    def test_raw_string_raises_at_prefix(self):
        with self.assertRaises(H.HandoffBoundaryError):
            H.prefix_for_next_agent(RAW)

    def test_schema_rejects_string_root(self):
        errors = H.validate_document(RAW)
        self.assertTrue(errors, "schema accepted a raw string root")

    def test_capture_refusal_both_boundaries(self):
        a = H.capture_refusal(RAW)
        self.assertTrue(a.get("refused") is True)
        p = H.capture_refusal(RAW, via="prefix_for_next_agent")
        self.assertTrue(p.get("refused") is True)
        self.assertIn("prefix_for_next_agent", p.get("reason", ""))


class TestHandoffCompleteness(unittest.TestCase):
    def test_missing_goal_raises(self):
        with self.assertRaises(H.HandoffCompletenessError) as ctx:
            H.accept_handoff(
                unit_id="IMP-0414",
                sentinel=SENTINEL,
                sections=[_context()],
            )
        self.assertIn("goal", str(ctx.exception).lower())

    def test_schema_rejects_nongoal_first(self):
        drifted = {
            "kind": "typed-handoff",
            "schema_version": 1,
            "unit_id": "IMP-0414",
            "state": "SUCCESS",
            "sentinel": SENTINEL,
            "sections": [
                {
                    "id": "context",
                    "kind": "context",
                    "ordinal": 1,
                    "title": "Goal drifted off the top",
                    "body": {"note": "first section is not goal"},
                    "evidence_anchors": [],
                }
            ],
        }
        errors = H.validate_document(drifted)
        self.assertTrue(errors, "schema accepted a handoff whose section 1 is not goal")
        sample = errors[0]
        self.assertIn("'goal' was expected", sample)

    def test_valid_typed_handoff_passes_schema(self):
        live = H.accept_handoff(
            unit_id="IMP-0414",
            state="SUCCESS",
            sentinel=SENTINEL,
            sections=[_context(), _goal()],
        )
        errors = H.validate_document(live.to_dict())
        self.assertEqual(errors, [])
        prefix = H.prefix_for_next_agent(live)
        self.assertEqual(prefix[0]["kind"], "goal")
        self.assertEqual(prefix[0]["ordinal"], 1)
        self.assertFalse(any(isinstance(item, (str, bytes, bytearray)) for item in prefix))


class TestGoalReanchor(unittest.TestCase):
    def test_goal_passed_last_becomes_section_1(self):
        live = H.accept_handoff(
            unit_id="IMP-0414",
            sentinel=SENTINEL,
            sections=[_context(), _goal()],
        )
        sections = live.to_dict()["sections"]
        self.assertEqual(sections[0]["kind"], "goal")
        self.assertEqual(sections[0]["ordinal"], 1)
        self.assertEqual(sections[1]["kind"], "context")
        self.assertEqual(sections[1]["ordinal"], 2)

    def test_accept_dict_roundtrip_keeps_goal_first(self):
        live = H.accept_handoff(
            unit_id="IMP-0414",
            sentinel=SENTINEL,
            sections=[_context(), _goal()],
        )
        again = H.accept_handoff(live.to_dict())
        self.assertEqual(again.to_dict()["sections"][0]["kind"], "goal")


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
