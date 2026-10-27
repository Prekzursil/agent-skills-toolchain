"""Every credential-bearing request must use the allowlisted transport.

Blast-radius cover for the auth_broker bearer-exfiltration defect. The broker was
the caller-controlled-URL case; these are the same primitive at other sites:

* ``crcp/auth.py`` — hardcoded URL, but ``urllib.request.urlopen`` FORWARDS the
  ``Authorization`` header across a cross-host 3xx (proven executably below on a
  loopback sink), so the redirect target is effectively attacker-choosable.
* ``crcp/sentinel.py`` — ``_browser_headers`` attaches the live bearer and the URL
  is built from ``bridge.base``, a constructor parameter, i.e. caller-controlled.

``crcp/http_secure.open_url`` is the repo's existing correct primitive: it
validates every hop against an allowlist and drops credential headers on a
cross-origin redirect. These tests assert the credentialed call sites route
through it and that a regression back to raw ``urlopen`` fails loudly.

No real credential is used. The only network I/O is to ephemeral 127.0.0.1
servers created and torn down inside a single test.
"""

from __future__ import annotations

import http.server
import json
import pathlib
import shutil
import tempfile
import threading
import unittest
import urllib.request
from typing import Any
from unittest import mock

from crcp import auth, http_secure, sentinel

FAKE_TOKEN = "sk-FAKE-SYNTHETIC-NOT-A-REAL-TOKEN-0000000000"


class StdlibRedirectLeakTests(unittest.TestCase):
    """The premise: urllib really does carry Authorization across hosts.

    If this ever fails, the motivation for the other tests in this file has
    changed and they must be re-derived rather than trusted.
    """

    def test_urlopen_forwards_authorization_across_hosts(self) -> None:
        seen: list[str] = []
        servers: list[http.server.HTTPServer] = []

        class Sink(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                seen.append(self.headers.get("Authorization") or "")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *_a: Any) -> None:
                pass

        sink = http.server.HTTPServer(("127.0.0.1", 0), Sink)
        servers.append(sink)
        sink_port = sink.server_address[1]

        class Redirector(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{sink_port}/sink")
                self.end_headers()

            def log_message(self, *_a: Any) -> None:
                pass

        origin = http.server.HTTPServer(("127.0.0.1", 0), Redirector)
        servers.append(origin)

        for srv in servers:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: [s.shutdown() for s in servers])

        req = urllib.request.Request(
            f"http://127.0.0.1:{origin.server_address[1]}/backend-api/me",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)

        self.assertEqual(len(seen), 1)
        self.assertIn(
            FAKE_TOKEN,
            seen[0],
            "premise changed: urllib no longer forwards Authorization cross-host",
        )


class SecureTransportPolicyTests(unittest.TestCase):
    def test_open_url_refuses_off_allowlist_before_any_io(self) -> None:
        req = urllib.request.Request("https://evil.example/steal")
        with self.assertRaises(http_secure.URLSecurityError):
            http_secure.open_url(req)

    def test_credential_headers_are_in_the_cross_origin_drop_set(self) -> None:
        for name in ("authorization", "chatgpt-account-id", "cookie"):
            self.assertIn(name, http_secure._CROSS_ORIGIN_SENSITIVE_HEADERS)


class _Recorder:
    """Stands in for open_url; records the Request it was handed."""

    def __init__(self, payload: bytes = b"{}", status: int = 200) -> None:
        self.requests: list[urllib.request.Request] = []
        self._payload = payload
        self._status = status

    def __call__(self, req: Any, *, timeout: float | None = None) -> Any:
        self.requests.append(req)
        return self

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *_a: Any) -> bool:
        return False

    def read(self, *_a: Any) -> bytes:
        return self._payload

    @property
    def status(self) -> int:
        return self._status


class AuthProbeUsesSecureTransportTests(unittest.TestCase):
    """crcp/auth.py chatgpt_bridge_status must not use raw urlopen."""

    def _fake_codex_home(self) -> Any:
        tmp = tempfile.mkdtemp(prefix="crcp-egress-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        home = pathlib.Path(tmp)
        (home / "auth.json").write_text(
            json.dumps(
                {"tokens": {"access_token": FAKE_TOKEN, "account_id": "acct-fake"}}
            ),
            encoding="utf-8",
        )
        return home

    def test_bearer_probe_routes_through_open_url(self) -> None:
        recorder = _Recorder(b'{"object": "user"}')

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("raw urlopen used for a credential-bearing request")

        with (
            mock.patch.object(auth, "open_url", recorder),
            mock.patch.object(urllib.request, "urlopen", _explode),
            mock.patch.object(
                auth, "codex_auth_status", lambda *_a, **_k: {"status": "LOGGED_IN"}
            ),
            mock.patch.object(auth, "decode_jwt_claims", lambda _t: {}),
        ):
            report = auth.chatgpt_bridge_status(codex_home=self._fake_codex_home())

        self.assertEqual(len(recorder.requests), 1)
        sent = recorder.requests[0]
        self.assertEqual(sent.full_url, "https://chatgpt.com/backend-api/me")
        self.assertEqual(sent.get_header("Authorization"), f"Bearer {FAKE_TOKEN}")
        self.assertEqual(report["status"], "LOGGED_IN")


class _FakeBridge:
    """Minimal ChatGPTBridge stand-in with a caller-chosen base."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def _maybe_reload(self) -> None:
        pass


class SentinelUsesSecureTransportTests(unittest.TestCase):
    """crcp/sentinel.py carries the live bearer to a caller-controlled base URL."""

    def _patched_headers(self) -> Any:
        return mock.patch.object(
            sentinel,
            "_browser_headers",
            lambda *_a, **_k: {
                "Authorization": f"Bearer {FAKE_TOKEN}",
                "Content-Type": "application/json",
            },
        )

    def test_prepare_routes_through_open_url(self) -> None:
        recorder = _Recorder(b"{}")

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("raw urlopen used for a credential-bearing request")

        with (
            self._patched_headers(),
            mock.patch.object(sentinel, "open_url", recorder),
            mock.patch.object(urllib.request, "urlopen", _explode),
        ):
            sentinel.sentinel_prepare(_FakeBridge("https://chatgpt.com"))

        self.assertEqual(len(recorder.requests), 1)

    def test_prepare_refuses_attacker_supplied_base(self) -> None:
        """A caller-chosen base must be rejected by the transport, not dialled."""
        with self._patched_headers():
            with self.assertRaises(http_secure.URLSecurityError):
                sentinel.sentinel_prepare(_FakeBridge("https://evil.example"))

    def test_finalize_routes_through_open_url(self) -> None:
        recorder = _Recorder(b"{}")

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("raw urlopen used for a credential-bearing request")

        with (
            self._patched_headers(),
            mock.patch.object(sentinel, "open_url", recorder),
            mock.patch.object(urllib.request, "urlopen", _explode),
        ):
            result = sentinel.try_finalize(
                _FakeBridge("https://chatgpt.com"),
                prepare_token="p",
                proof_token="pr",
                turnstile_token="t",
                device_id="d",
                session_id="s",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(len(recorder.requests), 1)

    def test_finalize_refuses_attacker_supplied_base(self) -> None:
        with self._patched_headers():
            with self.assertRaises(http_secure.URLSecurityError):
                sentinel.try_finalize(
                    _FakeBridge("https://evil.example"),
                    prepare_token="p",
                    proof_token="pr",
                    turnstile_token="t",
                    device_id="d",
                    session_id="s",
                )


class CliSurfacesRefusalReasonTests(unittest.TestCase):
    """A credential-egress refusal must be distinguishable from a browser fault."""

    def test_safe_message_opt_in_is_surfaced(self) -> None:
        from crcp import __main__ as cli
        from crcp.auth_broker import CredentialScopeError

        printed: list[Any] = []
        with mock.patch.object(cli, "_print_json", printed.append):
            code = cli.main(["auth", "broker", "--url", "https://evil.example/steal"])

        self.assertEqual(code, 1)
        error = printed[-1]["error"]
        self.assertEqual(error["kind"], "credential_scope")
        self.assertEqual(error["type"], CredentialScopeError.__name__)
        self.assertIn("refusing to attach", error["message"])
        self.assertIn("--no-bearer", error["message"])

    def test_ordinary_failures_stay_redacted(self) -> None:
        from crcp import __main__ as cli

        printed: list[Any] = []
        with mock.patch.object(cli, "_print_json", printed.append):
            with mock.patch.object(
                cli, "cmd_auth_status", side_effect=RuntimeError(FAKE_TOKEN)
            ):
                code = cli.main(["auth", "status"])

        self.assertEqual(code, 1)
        error = printed[-1]["error"]
        self.assertEqual(error["kind"], "runtime")
        self.assertNotIn(FAKE_TOKEN, error["message"])
        self.assertIn("details suppressed", error["message"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
