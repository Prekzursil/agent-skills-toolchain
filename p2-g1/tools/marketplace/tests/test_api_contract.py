#!/usr/bin/env python3
"""IMP-0074 API contract conformance (reference + strict clients)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.api import RegistryApi  # noqa: E402
from marketplace.clients import (  # noqa: E402
    ClientError,
    RegistryClient,
    StrictRegistryClient,
    load_contract,
    validate_against_def,
)

INDEX = json.loads((REPO / "tools/marketplace/fixtures/index.json").read_text(encoding="utf-8"))
DEFS = load_contract()["$defs"]


class TestApiContract(unittest.TestCase):
    def setUp(self):
        self.api = RegistryApi(INDEX)
        self.ref = RegistryClient(self.api)
        self.strict = StrictRegistryClient(self.api)

    def test_index_ok(self):
        body = self.ref.index()
        self.assertEqual(body["name"], "conformance-fixture-registry")
        self.assertTrue(body["endpoints"])

    def test_list_pagination_distinguishable(self):
        full = self.ref.list_plugins()
        self.assertEqual(full["total"], 4)
        page1 = self.ref.list_plugins({"limit": "2"})
        self.assertEqual(len(page1["plugins"]), 2)
        self.assertIn("next_cursor", page1)
        cur = page1["next_cursor"]
        page2 = self.ref.list_plugins({"limit": "2", "cursor": cur})
        self.assertEqual(len(page2["plugins"]), 2)
        self.assertNotIn("next_cursor", page2)
        self.assertNotEqual(
            {p["name"] for p in page1["plugins"]},
            {p["name"] for p in page2["plugins"]},
        )

    def test_get_missing_and_invalid(self):
        with self.assertRaises(ClientError) as cm:
            self.ref.get_plugin("nope-missing-plugin")
        self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(ClientError) as cm2:
            self.ref.get_plugin("INVALID NAME")
        self.assertIn(cm2.exception.code, ("invalid_name", "invalid_request"))

    def test_search_successes_and_errors(self):
        hits = self.ref.search({"q": "alpha"})
        self.assertEqual(len(hits["results"]), 1)
        empty = self.ref.search({"q": "zzz-unmatched"})
        self.assertEqual(empty["results"], [])
        self.assertNotIn("next_cursor", empty)
        for bad in ({}, {"q": "  "}):
            with self.assertRaises(ClientError) as cm:
                self.ref.search(bad)
            self.assertEqual(cm.exception.status, 400)

    def test_limit_and_cursor_errors(self):
        for q in ({"limit": "0"}, {"limit": "5000"}, {"cursor": "!!!"}):
            with self.assertRaises(ClientError) as cm:
                self.ref.list_plugins(q)
            self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(ClientError):
            self.ref.search({"q": "alpha", "cursor": "!!!"})
        tolerated = self.ref.list_plugins({"spot": "1"})
        self.assertEqual(tolerated["total"], 4)

    def test_unknown_endpoint_404(self):
        status, schema, body = self.api.dispatch("/v9/none", {})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "unknown_endpoint")

    def test_strict_client_passes_clean_responses(self):
        body_a = self.strict.index()
        body_b = self.strict.list_plugins({"limit": "2"})
        body_c = self.strict.search({"q": "alpha"})
        self.assertTrue(body_a and body_b and body_c)

    def test_missing_required_fails_both(self):
        _, _, body = self.api.get_plugin("alpha")
        mutated = json.loads(json.dumps(body))
        del mutated["plugin"]["description"]
        for strict in (False, True):
            errs = validate_against_def("plugin_response", mutated, DEFS, strict=strict)
            self.assertTrue(errs, "missing required must fail for strict=" + str(strict))

    def test_extra_field_discriminates(self):
        _, _, body = self.api.get_plugin("alpha")
        mutated = json.loads(json.dumps(body))
        mutated["plugin"]["undocumented_bonus"] = 1
        ref_errs = validate_against_def("plugin_response", mutated, DEFS, strict=False)
        strict_errs = validate_against_def("plugin_response", mutated, DEFS, strict=True)
        self.assertEqual(ref_errs, [])
        self.assertTrue(strict_errs)

    def test_truncated_vs_empty(self):
        page = self.ref.list_plugins({"limit": "2"})
        self.assertIn("next_cursor", page)
        empty = self.ref.search({"q": "zzz-unmatched"})
        self.assertEqual(empty["results"], [])
        self.assertNotIn("next_cursor", empty)


if __name__ == "__main__":
    unittest.main(verbosity=1)
