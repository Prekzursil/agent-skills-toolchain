"""Contracts for deterministic event identity and restart-safe deduplication."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from event_spool import EventSpool, make_event_key


class EventKeyContractTests(unittest.TestCase):
    def test_same_logical_event_has_same_key(self) -> None:
        first = make_event_key("conv-1", "2026-07-20T00:00:00Z", {"b": 2, "a": 1})
        replay = make_event_key("conv-1", "2026-07-20T00:00:00Z", {"a": 1, "b": 2})
        self.assertEqual(first, replay)

    def test_each_identity_component_changes_key(self) -> None:
        base = make_event_key("conv-1", 100, {"text": "one"})
        self.assertNotEqual(base, make_event_key("conv-2", 100, {"text": "one"}))
        self.assertNotEqual(base, make_event_key("conv-1", 101, {"text": "one"}))
        self.assertNotEqual(base, make_event_key("conv-1", 100, {"text": "two"}))

    def test_duplicate_replay_has_one_durable_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.sqlite3"
            key = make_event_key("conv-1", 100, {"text": "once"})
            with EventSpool(path) as spool:
                self.assertTrue(spool.observe(key, {"text": "once"}))
                self.assertFalse(spool.observe(key, {"text": "once"}))
                spool.transition(key, "spooled")
                spool.transition(key, "publishing")
            with EventSpool(path) as restarted:
                self.assertFalse(restarted.observe(key, {"text": "once"}))
                self.assertEqual(restarted.count(), 1)
                self.assertEqual(restarted.state(key), "publishing")
                restarted.transition(key, "acked")

    def test_state_machine_rejects_skipped_transition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with EventSpool(Path(directory) / "events.sqlite3") as spool:
                key = make_event_key("conv-1", 100, {})
                spool.observe(key, {})
                with self.assertRaises(ValueError):
                    spool.transition(key, "acked")


if __name__ == "__main__":
    unittest.main()
