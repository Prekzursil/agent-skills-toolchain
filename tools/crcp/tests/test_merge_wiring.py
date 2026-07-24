"""Offline integration contracts for the merged CRCP durability surfaces."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from crcp.singleton import acquire_singleton_lock
from crcp.spool import EventSpool, event_key
from crcp.sse_contract import COMPLETE, ERROR, UNCERTAIN_ACCEPTED, classify_sse


COMPLETE_FIXTURE = """data: {"message":{"status":"in_progress"}}

data: {"message":{"status":"finished_successfully","end_turn":true}}

data: [DONE]

"""
TRUNCATED_FIXTURE = """data: {"message":{"status":"in_progress"}}

data: {"delta":"partial output"}

"""
ERROR_FIXTURE = """event: error
data: {"error":{"message":"upstream failed"}}

"""


class MergeWiringTests(unittest.TestCase):
    def test_put_observed_is_idempotent_for_same_event_key(self) -> None:
        payload = {"text": "publish once", "sequence": 1}
        # ignore_cleanup_errors: SQLite on Windows can briefly hold the file handle
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            database = Path(directory) / "spool.sqlite3"
            spool = EventSpool(database)

            first = spool.put_observed("conversation-1", 100, payload)
            replay = spool.put_observed("conversation-1", 100, payload)

            self.assertEqual(first, event_key("conversation-1", 100, payload))
            self.assertEqual(replay, first)
            self.assertEqual(spool.get(first)["event_key"], first)
            with sqlite3.connect(database) as connection:
                count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 1)
            del spool

    def test_sse_complete_fixture_is_complete(self) -> None:
        self.assertEqual(classify_sse(200, COMPLETE_FIXTURE), COMPLETE)

    def test_sse_truncated_fixture_is_uncertain(self) -> None:
        self.assertEqual(classify_sse(200, TRUNCATED_FIXTURE), UNCERTAIN_ACCEPTED)

    def test_sse_error_fixture_is_error(self) -> None:
        self.assertEqual(classify_sse(200, ERROR_FIXTURE), ERROR)

    def test_singleton_lock_can_be_acquired_and_released_locally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner_path = Path(directory) / "crcp.owner.json"
            lease = acquire_singleton_lock(owner_path)
            self.assertTrue(owner_path.is_file())
            lease.release()
            self.assertFalse(owner_path.exists())


if __name__ == "__main__":
    unittest.main()
