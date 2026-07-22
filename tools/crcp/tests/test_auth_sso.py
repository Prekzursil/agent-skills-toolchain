from __future__ import annotations

import re
import unittest
import urllib.parse
from unittest import mock

from crcp import auth_sso


class AuthSsoTests(unittest.TestCase):
    def test_pkce_challenge_length_and_format(self) -> None:
        verifier = auth_sso.generate_code_verifier()
        challenge = auth_sso.code_challenge_s256(verifier)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertEqual(len(challenge), 43)
        self.assertRegex(challenge, re.compile(r"^[A-Za-z0-9_-]{43}$"))

    def test_authorize_url_has_required_pkce_fields(self) -> None:
        url = auth_sso.build_authorize_url(
            "http://127.0.0.1:1455/auth/callback",
            client_id="test-public-client",
            scopes="openid offline_access",
            state="expected-state",
            nonce="expected-nonce",
            code_challenge="A" * 43,
        )
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query["code_challenge"], ["A" * 43])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["client_id"], ["test-public-client"])

    def test_state_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(auth_sso.CallbackError, "state mismatch"):
            auth_sso.parse_callback_query(
                "code=one-time-code&state=wrong-state",
                expected_state="right-state",
            )

    @mock.patch("crcp.auth_sso.exchange_code_for_tokens")
    def test_offline_code_completion_mocks_network(self, exchange: mock.Mock) -> None:
        exchange.return_value = {"expires_in": 3600}
        result = auth_sso.run_sso_login(
            open_browser=False,
            code="one-time-code",
            code_verifier="v" * 64,
        )
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["auth_summary"]["expires_in"], 3600)
        exchange.assert_called_once()


if __name__ == "__main__":
    unittest.main()
