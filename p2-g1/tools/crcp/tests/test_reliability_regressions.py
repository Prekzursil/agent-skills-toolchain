"""Regressions for false-success and credential-leak defects in the CRCP rails.

Every test here failed against the code immediately before the commit that added
this file.  Each one pins a specific way a CRCP call used to claim success (or
silently widen credential exposure) while the underlying operation had not
actually succeeded safely:

* ``bus``          - an MCP tool execution error read as an ordinary return value
* ``auth_broker``  - a pre-existing browser on the CDP port adopted as our launch
* ``auth``         - bearer credentials replayed across an origin-changing redirect
* ``dead_letter``  - two different events merged because ONE weak id matched
* ``__main__``     - a local report-write error inverting a committed send
* ``auth_sso``     - an HTTP 200 with no credential reported as a completed login
* ``capabilities`` - a lease already expired at the moment claim_lease returned
* ``envelope``     - a sha256: reference published without storing the bytes
"""

from __future__ import annotations

import json
import subprocess
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from crcp import (
    artifact_store,
    auth,
    auth_broker,
    auth_sso,
    bus,
    capabilities,
    dead_letter,
    envelope,
    http_secure,
)
from crcp.__main__ import main


# --------------------------------------------------------------------------
# bus: an MCP tool error must not read as a successful send
# --------------------------------------------------------------------------


def _mcp_error_response() -> dict[str, Any]:
    return {
        "result": {
            "isError": True,
            "content": [{"type": "text", "text": "permission denied"}],
        }
    }


class BusToolErrorTests(unittest.TestCase):
    def test_tool_text_raises_on_inner_execution_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            bus._tool_text(_mcp_error_response())

    def test_tool_text_still_returns_text_on_success(self) -> None:
        ok = {"result": {"content": [{"type": "text", "text": "delivered"}]}}
        self.assertEqual(bus._tool_text(ok), "delivered")

    def test_publish_envelope_does_not_report_ok_for_a_failed_send(self) -> None:
        class _Rpc:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                pass

            def initialize(self) -> None:
                return None

            def call(self, method: str, _params: dict) -> dict[str, Any] | None:
                if method == "tools/call":
                    return _mcp_error_response()
                return None

        with (
            mock.patch.object(bus, "AgentMailRpc", _Rpc),
            mock.patch.object(
                bus,
                "load_or_register_bridge_agent",
                return_value=("BridgeAgent", "tok"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "permission denied"):
                bus.publish_envelope({"id": "env-1"}, to_agents=["Receiver"])

    def test_registration_recovery_survives_a_tool_error(self) -> None:
        """Raising on isError must not skip the post-register sqlite recovery."""

        class _Rpc:
            def call(self, _method: str, _params: dict) -> dict[str, Any]:
                return _mcp_error_response()

        with self.assertRaisesRegex(RuntimeError, "could not register bridge agent"):
            bus.load_or_register_bridge_agent(
                _Rpc(),  # type: ignore[arg-type]
                "some-project",
                db=Path("/nonexistent/storage.sqlite3"),
            )


# --------------------------------------------------------------------------
# auth_broker: never adopt a browser we did not launch
# --------------------------------------------------------------------------


class LaunchBrowserPortOwnershipTests(unittest.TestCase):
    def test_occupied_cdp_port_is_refused_before_launching(self) -> None:
        incumbent = {
            "Browser": "PREEXISTING/1",
            "webSocketDebuggerUrl": "ws://old/session",
        }
        with (
            mock.patch.object(auth_broker, "_http_json", return_value=incumbent),
            mock.patch.object(auth_broker, "prepare_profile_dir") as prepare,
            mock.patch.object(subprocess, "Popen") as popen,
        ):
            with self.assertRaisesRegex(auth_broker.BrokerError, "PREEXISTING/1"):
                auth_broker.launch_browser(profile_dir=Path("unused"), port=59321)
        popen.assert_not_called()
        prepare.assert_not_called()

    def test_child_that_exited_is_not_reported_as_the_live_browser(self) -> None:
        version = {"Browser": "Chrome/1", "webSocketDebuggerUrl": "ws://new/session"}
        probe_results: list[Any] = [urllib.error.URLError("closed"), version]

        def _probe(*_args: Any, **_kwargs: Any) -> Any:
            outcome = probe_results.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        dead_child = mock.Mock(pid=4242, returncode=1)
        dead_child.poll.return_value = 1
        with (
            mock.patch.object(auth_broker, "_http_json", side_effect=_probe),
            mock.patch.object(auth_broker, "prepare_profile_dir"),
            mock.patch.object(auth_broker, "_find_browser", return_value=("x", "x")),
            mock.patch.object(subprocess, "Popen", return_value=dead_child),
        ):
            with self.assertRaisesRegex(auth_broker.BrokerError, "exited with code 1"):
                auth_broker.launch_browser(profile_dir=Path("unused"), port=59322)


# --------------------------------------------------------------------------
# auth: the bridge probe must use the credential-stripping transport
# --------------------------------------------------------------------------


class _FakeResponse:
    status = 200

    def read(self, _size: int | None = None) -> bytes:
        return b'{"object": "user"}'

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None


class BridgeStatusTransportTests(unittest.TestCase):
    def test_bridge_probe_goes_through_open_url_not_bare_urlopen(self) -> None:
        self.assertIs(auth.open_url, http_secure.open_url)
        seen: list[urllib.request.Request] = []

        def _open_url(request: urllib.request.Request, **_kw: Any) -> _FakeResponse:
            seen.append(request)
            return _FakeResponse()

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "auth.json").write_text(
                json.dumps({"tokens": {"access_token": "tok", "account_id": "acct"}}),
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    auth,
                    "codex_auth_status",
                    return_value={"status": "LOGGED_IN", "signals": []},
                ),
                mock.patch.object(auth, "open_url", _open_url),
                mock.patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError("bare urlopen leaks credentials"),
                ),
            ):
                out = auth.chatgpt_bridge_status(codex_home=home)

        self.assertEqual(out["status"], "LOGGED_IN")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer tok")

    def test_open_url_drops_credentials_on_a_cross_origin_redirect(self) -> None:
        request = urllib.request.Request(
            "https://chatgpt.com/backend-api/me",
            headers={"Authorization": "Bearer tok", "ChatGPT-Account-Id": "acct"},
        )
        redirected = http_secure._redirect_request(
            request, "https://ab.chatgpt.com/collect", 302
        )
        headers = {name.lower() for name in redirected.headers}
        self.assertNotIn("authorization", headers)
        self.assertNotIn("chatgpt-account-id", headers)


# --------------------------------------------------------------------------
# dead_letter: one weak matching id must not merge two different events
# --------------------------------------------------------------------------


def _record(event_key: str, envelope_id: str, conversation_id: str) -> dict[str, Any]:
    return {
        "event_key": event_key,
        "envelope_id": envelope_id,
        "conversation_id": conversation_id,
        "state": "dead_letter",
    }


class DeadLetterCollisionTests(unittest.TestCase):
    def _fixture(self, tmp: str, destination: dict[str, Any]) -> tuple[Path, Path]:
        dead = Path(tmp) / "dead"
        spool = Path(tmp) / "spool"
        dead.mkdir()
        spool.mkdir()
        source = _record("source-event", "source-id", "shared-conversation")
        (dead / "same-name.json").write_text(json.dumps(source), encoding="utf-8")
        (spool / "same-name.json").write_text(json.dumps(destination), encoding="utf-8")
        return dead, spool

    def test_conflicting_event_and_envelope_ids_are_not_treated_as_a_duplicate(
        self,
    ) -> None:
        other = _record("different-event", "different-id", "shared-conversation")
        with TemporaryDirectory() as tmp:
            dead, spool = self._fixture(tmp, other)
            with self.assertRaises(FileExistsError):
                dead_letter.requeue_dead_letter(dead, "same-name.json", spool)
            self.assertTrue(
                (dead / "same-name.json").is_file(),
                "the only copy of the source event was destroyed",
            )
            self.assertEqual(
                json.loads((spool / "same-name.json").read_text(encoding="utf-8"))[
                    "event_key"
                ],
                "different-event",
            )

    def test_a_genuine_duplicate_still_deduplicates(self) -> None:
        same = _record("source-event", "source-id", "shared-conversation")
        with TemporaryDirectory() as tmp:
            dead, spool = self._fixture(tmp, same)
            result = dead_letter.requeue_dead_letter(dead, "same-name.json", spool)
            self.assertTrue(result["already_spooled"])
            self.assertFalse((dead / "same-name.json").exists())


# --------------------------------------------------------------------------
# __main__: a committed send must not be reported as a failure
# --------------------------------------------------------------------------


class ChatgptSendExitStatusTests(unittest.TestCase):
    def test_report_write_failure_does_not_invert_a_committed_send(self) -> None:
        sends: list[str] = []

        def _send_message(text: str, **_kwargs: Any) -> dict[str, Any]:
            sends.append(text)
            return {"success": True, "status": "SUCCESS"}

        original_write_text = Path.write_text

        def _write_text(self: Path, *args: Any, **kwargs: Any) -> int:
            if self.name == "chatgpt_send_last.json":
                raise PermissionError(13, "Permission denied", str(self))
            return original_write_text(self, *args, **kwargs)

        with (
            mock.patch("crcp.write_path.send_message", _send_message),
            mock.patch.object(Path, "write_text", _write_text),
        ):
            code = main(["chatgpt", "send", "probe", "--new"])

        self.assertEqual(code, 0)
        self.assertEqual(sends, ["probe"], "the send must run exactly once")

    def test_a_failed_send_still_exits_nonzero(self) -> None:
        with (
            mock.patch(
                "crcp.write_path.send_message",
                return_value={"success": False, "status": "FAILED"},
            ),
            mock.patch.object(Path, "write_text", lambda *_a, **_k: 0),
        ):
            self.assertEqual(main(["chatgpt", "send", "probe", "--new"]), 1)


# --------------------------------------------------------------------------
# auth_sso: an HTTP 200 with no credential is not a completed login
# --------------------------------------------------------------------------


class _TokenResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _TokenResponse:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None


class SsoTokenExchangeTests(unittest.TestCase):
    def _exchange(self, body: dict[str, Any]) -> dict[str, Any]:
        with mock.patch.object(
            urllib.request, "urlopen", return_value=_TokenResponse(body)
        ):
            return auth_sso.exchange_code_for_tokens(
                "one-time-code",
                verifier="v" * 64,
                redirect_uri="http://127.0.0.1:1455/auth/callback",
            )

    def test_empty_object_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no usable credential"):
            self._exchange({})

    def test_metadata_without_a_credential_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no usable credential"):
            self._exchange({"expires_in": 3600})

    def test_oauth_error_is_rejected_without_echoing_the_description(self) -> None:
        with self.assertRaises(RuntimeError) as caught:
            self._exchange(
                {"error": "invalid_grant", "error_description": "secret-ish detail"}
            )
        self.assertIn("invalid_grant", str(caught.exception))
        self.assertNotIn("secret-ish detail", str(caught.exception))

    def test_a_real_bundle_is_accepted(self) -> None:
        tokens = self._exchange({"access_token": "at", "expires_in": 3600})
        self.assertEqual(tokens["access_token"], "at")

    def test_run_sso_login_propagates_the_rejection(self) -> None:
        with mock.patch.object(
            urllib.request, "urlopen", return_value=_TokenResponse({})
        ):
            with self.assertRaisesRegex(RuntimeError, "no usable credential"):
                auth_sso.run_sso_login(
                    open_browser=False,
                    code="one-time-code",
                    code_verifier="v" * 64,
                )


# --------------------------------------------------------------------------
# capabilities: a granted lease must still be live when claim_lease returns
# --------------------------------------------------------------------------


class ClaimLeaseClockTests(unittest.TestCase):
    def test_lease_is_still_live_after_a_slow_lock_acquisition(self) -> None:
        clock = {"now": 100.0}
        original_enter = capabilities._StateLock.__enter__
        contended = {"pending": True}

        def _slow_enter(lock: Any) -> Any:
            acquired = original_enter(lock)
            # Model exactly ONE contended acquisition that outlasts the
            # requested TTL; later acquisitions are uncontended.
            if contended["pending"]:
                contended["pending"] = False
                clock["now"] += 2.0
            return acquired

        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "capabilities.json"
            registry = capabilities.CapabilityRegistry(
                state, clock=lambda: clock["now"]
            )
            name = registry.supported_names()[0]
            with mock.patch.object(capabilities._StateLock, "__enter__", _slow_enter):
                self.assertTrue(registry.claim_lease(name, "owner-A", ttl_s=1.0))
                self.assertFalse(
                    registry.is_available(name),
                    "claim_lease returned true for an already-expired lease",
                )
                self.assertFalse(
                    registry.claim_lease(name, "owner-B", ttl_s=1.0),
                    "a second owner replaced a lease that was just granted",
                )

    def test_an_expired_lease_is_still_reclaimable(self) -> None:
        clock = {"now": 100.0}
        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "capabilities.json"
            registry = capabilities.CapabilityRegistry(
                state, clock=lambda: clock["now"]
            )
            name = registry.supported_names()[0]
            self.assertTrue(registry.claim_lease(name, "owner-A", ttl_s=1.0))
            clock["now"] += 5.0
            self.assertTrue(registry.is_available(name))
            self.assertTrue(registry.claim_lease(name, "owner-B", ttl_s=1.0))


# --------------------------------------------------------------------------
# envelope: never advertise a content address the store cannot resolve
# --------------------------------------------------------------------------


class EnvelopePayloadStorageTests(unittest.TestCase):
    def test_a_published_sha256_reference_is_retrievable(self) -> None:
        with TemporaryDirectory() as tmp:
            payload = Path(tmp) / "chatgpt_delta.json"
            payload.write_bytes(b'{"delta": "hello"}')
            store = artifact_store.ArtifactStore(Path(tmp) / "artifacts")
            with mock.patch.object(artifact_store, "_default_store", store):
                env = envelope.make_envelope(
                    from_rail="chatgpt",
                    to_rail="codex",
                    intent="handoff",
                    payload_ref=str(payload),
                )
                self.assertTrue(env["payload_ref"].startswith("sha256:"))
                self.assertEqual(env["completion"], "SUCCESS")
                self.assertEqual(store.get(env["payload_ref"]), b'{"delta": "hello"}')
            self.assertTrue(envelope.validate_envelope(env)[0])

    def test_an_unstorable_payload_does_not_advertise_a_content_address(self) -> None:
        with TemporaryDirectory() as tmp:
            payload = Path(tmp) / "chatgpt_delta.json"
            payload.write_bytes(b'{"delta": "hello"}')
            # A regular FILE where the store root must be a directory: put_bytes
            # cannot succeed, so no sha256: promise may be emitted.
            blocked = Path(tmp) / "not-a-directory"
            blocked.write_bytes(b"")
            store = artifact_store.ArtifactStore(blocked)
            with mock.patch.object(artifact_store, "_default_store", store):
                env = envelope.make_envelope(
                    from_rail="chatgpt",
                    to_rail="codex",
                    intent="handoff",
                    payload_ref=str(payload),
                )
            self.assertEqual(env["payload_ref"], str(payload))
            self.assertNotIn("payload_sha256", env)

    def test_an_already_addressed_reference_is_passed_through(self) -> None:
        digest = "a" * 64
        env = envelope.make_envelope(
            from_rail="chatgpt",
            to_rail="codex",
            intent="handoff",
            payload_ref=f"sha256:{digest}",
        )
        self.assertEqual(env["payload_ref"], f"sha256:{digest}")


if __name__ == "__main__":
    unittest.main()
