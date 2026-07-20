"""Tests for the proxy-mcp credential-scrubbing layer.

The sentinel values below are fabricated and non-functional.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redaction  # noqa: E402

SENTINEL = "FAKE-SENTINEL-NOTAREALTOKEN-0000"


class TestMask:
    def test_mask_hides_value_and_reports_length(self) -> None:
        out = redaction.mask(SENTINEL)
        assert SENTINEL not in out
        assert f"len={len(SENTINEL)}" in out
        assert out.startswith("<redacted:sha256=")

    def test_mask_is_stable_for_equal_values(self) -> None:
        assert redaction.mask(SENTINEL) == redaction.mask(SENTINEL)

    def test_mask_differs_for_different_values(self) -> None:
        assert redaction.mask(SENTINEL) != redaction.mask(SENTINEL + "x")

    def test_mask_does_not_double_wrap(self) -> None:
        once = redaction.mask(SENTINEL)
        assert redaction.mask(once) == once

    def test_mask_handles_non_string(self) -> None:
        assert "<redacted:" in redaction.mask({"a": 1})


class TestSensitiveKeys:
    @pytest.mark.parametrize(
        "name",
        ["Authorization", "authorization", "Cookie", "Set-Cookie", "X-API-Key"],
    )
    def test_header_names_are_sensitive(self, name: str) -> None:
        assert redaction._is_sensitive_key(name, header=True)

    @pytest.mark.parametrize(
        "name",
        ["password", "access_token", "client_secret", "apiKey", "private_key"],
    )
    def test_body_fields_are_sensitive(self, name: str) -> None:
        assert redaction._is_sensitive_key(name)

    @pytest.mark.parametrize("name", ["User-Agent", "Content-Type", "url", "method"])
    def test_benign_names_are_not_sensitive(self, name: str) -> None:
        assert not redaction._is_sensitive_key(name, header=True)


class TestRedactObj:
    def test_scrubs_header_block(self) -> None:
        flow = {
            "request": {
                "method": "GET",
                "url": "http://example.com/",
                "headers": {
                    "User-Agent": "curl/8.20.0",
                    "Authorization": f"Bearer {SENTINEL}",
                    "Cookie": f"session={SENTINEL}",
                },
            }
        }
        out = json.dumps(redaction.redact_obj(flow))
        assert SENTINEL not in out
        # Benign metadata must survive -- redaction must not destroy usefulness.
        assert "curl/8.20.0" in out
        assert "example.com" in out
        assert "GET" in out

    def test_scrubs_nested_body_fields(self) -> None:
        payload = {
            "body": {
                "user": "alice",
                "password": SENTINEL,
                "nested": {"api_key": SENTINEL},
            }
        }
        out = json.dumps(redaction.redact_obj(payload))
        assert SENTINEL not in out
        assert "alice" in out

    def test_scrubs_query_string_in_url(self) -> None:
        out = redaction.redact_obj({"url": f"http://x.com/a?token={SENTINEL}&page=2"})
        assert SENTINEL not in json.dumps(out)
        assert "page=2" in out["url"]

    def test_scrubs_inside_lists(self) -> None:
        out = json.dumps(redaction.redact_obj([{"token": SENTINEL}, {"ok": "keep"}]))
        assert SENTINEL not in out
        assert "keep" in out

    def test_scrubs_credentials_embedded_in_a_body_string(self) -> None:
        """A JSON body arrives as an opaque string; secrets inside it must still go.

        Regression: an echo endpoint reflected the request Authorization header
        back inside the response body, and an OAuth endpoint returns
        access_token the same way -- the highest-value secrets of all.
        """
        body = json.dumps({"headers": {"Authorization": f"Bearer {SENTINEL}"}})
        out = json.dumps(redaction.redact_obj({"body_preview": body}))
        assert SENTINEL not in out

    def test_scrubs_oauth_token_response_body(self) -> None:
        body = json.dumps(
            {"access_token": SENTINEL, "token_type": "bearer", "expires_in": 3600}
        )
        out = json.dumps(redaction.redact_obj({"body": body}))
        assert SENTINEL not in out
        assert "3600" in out

    def test_scrubs_raw_header_block_in_a_body_string(self) -> None:
        body = f"POST /x HTTP/1.1\r\nAuthorization: Bearer {SENTINEL}\r\nAccept: */*"
        out = json.dumps(redaction.redact_obj({"body": body}))
        assert SENTINEL not in out

    def test_non_json_body_string_survives(self) -> None:
        out = redaction.redact_obj({"body": "<html><body>hello</body></html>"})
        assert out["body"] == "<html><body>hello</body></html>"


class TestHarNameValuePairs:
    """HAR models headers/cookies as name/value pair objects, not mappings.

    Regression: a real HAR export shipped the sentinel in cleartext at
    log.entries[0].request.headers[4].value because key-based matching only
    ever saw a key literally called "value".
    """

    def test_scrubs_har_header_pair(self) -> None:
        pair = {"name": "Authorization", "value": f"Bearer {SENTINEL}"}
        out = redaction.redact_obj(pair)
        assert SENTINEL not in json.dumps(out)
        assert out["name"] == "Authorization"  # name is diagnostic, keep it

    def test_scrubs_har_cookie_pair(self) -> None:
        out = redaction.redact_obj({"name": "session", "value": SENTINEL})
        assert SENTINEL not in json.dumps(out)

    def test_benign_har_pair_survives(self) -> None:
        pair = {"name": "User-Agent", "value": "curl/8.20.0"}
        assert redaction.redact_obj(pair) == pair

    def test_scrubs_full_har_entry_list(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "http://x.com/",
                            "headers": [
                                {"name": "User-Agent", "value": "curl/8.20.0"},
                                {
                                    "name": "Authorization",
                                    "value": f"Bearer {SENTINEL}",
                                },
                            ],
                            "cookies": [{"name": "session", "value": SENTINEL}],
                        }
                    }
                ]
            }
        }
        out = json.dumps(redaction.redact_obj(har))
        assert SENTINEL not in out
        assert "curl/8.20.0" in out


class TestInlineHeaderForms:
    """Credentials also appear mid-line, not just at the start of a header line.

    Regression: upstream renders a reproducible shell command per flow
    (curl ... -H 'Authorization: Bearer ...'). A line-anchored pattern missed it
    and the token shipped in cleartext inside the curl_command field.
    """

    def test_scrubs_curl_command_string(self) -> None:
        cmd = (
            "curl -X GET 'http://httpbin.org/get' -H 'User-Agent: curl/8.20.0' "
            f"-H 'Authorization: Bearer {SENTINEL}'"
        )
        out = redaction.redact_obj({"curl_command": cmd})
        assert SENTINEL not in json.dumps(out)
        assert "curl/8.20.0" in out["curl_command"]

    def test_scrubs_inline_cookie(self) -> None:
        out = redaction.redact_obj(
            {"cmd": f"curl -H 'Cookie: session={SENTINEL}' http://x"}
        )
        assert SENTINEL not in json.dumps(out)


class TestRedactObjExtra:
    def test_non_string_scalars_pass_through(self) -> None:
        assert redaction.redact_obj({"status_code": 200, "ok": True}) == {
            "status_code": 200,
            "ok": True,
        }


class TestRedactText:
    def test_scrubs_json_payload(self) -> None:
        payload = json.dumps({"headers": {"Authorization": f"Bearer {SENTINEL}"}})
        assert SENTINEL not in redaction.redact_text(payload)

    def test_scrubs_unparseable_payload_via_regex_fallback(self) -> None:
        blob = f"GET /x\r\nAuthorization: Bearer {SENTINEL}\r\nAccept: */*\r\n"
        out = redaction.redact_text(blob)
        assert SENTINEL not in out
        assert "Accept" in out

    def test_empty_payload_is_returned_unchanged(self) -> None:
        assert redaction.redact_text("") == ""


class TestToggle:
    def test_enabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PROXY_MCP_REDACT", raising=False)
        assert redaction.redaction_enabled()

    @pytest.mark.parametrize("value", ["off", "0", "false", "no", "OFF"])
    def test_explicit_opt_out(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("PROXY_MCP_REDACT", value)
        assert not redaction.redaction_enabled()

    def test_unrecognised_value_stays_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed: an unparseable setting must not silently disable scrubbing."""
        monkeypatch.setenv("PROXY_MCP_REDACT", "maybe")
        assert redaction.redaction_enabled()
