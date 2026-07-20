"""Contracts ensuring CRCP reports do not retain authentication material."""

from __future__ import annotations

import json
import unittest

from redact import REDACTED, redact


class RedactionContractTests(unittest.TestCase):
    def test_sensitive_fields_are_redacted_recursively(self) -> None:
        source = {
            "authorization": "Bearer example-access-value",
            "nested": {
                "sentinel_prepare_token": "example-prepare-value",
                "x-conduit-token": "example-conduit-value",
            },
            "safe": "keep me",
        }
        result = redact(source)
        self.assertEqual(result["authorization"], REDACTED)
        self.assertEqual(result["nested"]["sentinel_prepare_token"], REDACTED)
        self.assertEqual(result["nested"]["x-conduit-token"], REDACTED)
        self.assertEqual(result["safe"], "keep me")
        self.assertNotEqual(source["authorization"], REDACTED)

    def test_bearer_and_jwt_values_inside_text_are_redacted(self) -> None:
        jwt = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJmaXh0dXJlIn0.signature"
        result = redact(f"Authorization: Bearer abc.def-123; jwt={jwt}")
        self.assertNotIn("abc.def-123", result)
        self.assertNotIn(jwt, result)
        self.assertIn(REDACTED, result)

    def test_secret_url_query_values_are_redacted(self) -> None:
        result = redact("https://example.invalid/stream?resume_token=resume-value&limit=2")
        self.assertNotIn("resume-value", result)
        self.assertIn("limit=2", result)

    def test_serialized_output_contains_no_fixture_secrets(self) -> None:
        source = {
            "proof_token": "proof-value",
            "items": [{"password": "password-value"}, "Bearer bearer-value"],
        }
        encoded = json.dumps(redact(source))
        for secret in ("proof-value", "password-value", "bearer-value"):
            self.assertNotIn(secret, encoded)


if __name__ == "__main__":
    unittest.main()
