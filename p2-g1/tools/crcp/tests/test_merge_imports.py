"""Import smoke tests for APIs supplied by the merged CRCP modules."""

from __future__ import annotations

import unittest

from crcp.health import full_health
from crcp.singleton import acquire_singleton_lock
from crcp.spool import EventSpool, event_key
from crcp.sse_contract import classify_sse


class MergeImportTests(unittest.TestCase):
    def test_required_merge_surfaces_import(self) -> None:
        for surface in (
            EventSpool,
            event_key,
            acquire_singleton_lock,
            classify_sse,
            full_health,
        ):
            with self.subTest(surface=surface.__name__):
                self.assertTrue(callable(surface))


if __name__ == "__main__":
    unittest.main()
