"""Regression proof: JSON-quoted credentials must not bypass redaction.

`ci/harness` is ruff-EXCLUDED and has no pytest lane in CI, so this file doubles
as a runnable proof:

    python ci/harness/tests/test_redaction_json_credentials.py

Measured 2026-07-26 against the live module BEFORE the fix:
  password=abcdefghijklmnopqr            -> caught
  {"password":"abcdefghijklmnopqr"}      -> returned BYTE-FOR-BYTE
  password=!CorrectHorseBatteryStaple123 -> returned unchanged
  Authorization: Basic dXNlcjpTdXBlclNlY3JldCE= -> returned unchanged

Cause: after the key came a QUOTE, which is in neither [A-Za-z0-9_-] nor \\s, so the
[:=] separator never matched; the value class also excluded punctuation; and only
Bearer was covered, not Basic. `{"api_key":...}` and `{"token":"ghp_..."}` survived
only because their VALUES match vendor-prefix patterns — the key-based rule was blind.

This matters because redact_text guards set_goal before it writes to the event
ledger, so a JSON credential reached durable storage in plaintext.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CI = Path(__file__).resolve().parent.parent.parent  # .../ci
if str(_CI) not in sys.path:
    sys.path.insert(0, str(_CI))

from harness.redaction import contains_secret, redact_text  # noqa: E402

MUST_CATCH = [
    ("unquoted key", "password=abcdefghijklmnopqr"),
    ("json quoted key", '{"password":"abcdefghijklmnopqr"}'),
    ("json with spaces", '{ "password" : "abcdefghijklmnopqr" }'),
    ("punctuation-leading value", "password=!CorrectHorseBatteryStaple123"),
    ("basic auth header", "Authorization: Basic dXNlcjpTdXBlclNlY3JldCE="),
    ("bearer still works", "Authorization: Bearer abcdefghijklmnopqrstuvwx"),
    ("json api_key", '{"api_key":"sk_live_abcdefghijklmnop"}'),
    ("yaml style", "client_secret: abcdefghijklmnopqrst"),
]

# Over-redaction is a real cost: the ledger and the goal re-anchor become unreadable.
MUST_NOT_CATCH = [
    ("prose mentioning password", "the password field is required on the signup form"),
    ("prose mentioning token", "rotate the token before Friday, see the runbook"),
    ("short value", "secret: this is a short one"),
    ("doc reference", "api_key handling is covered in guides/security.md"),
    ("env var name only", "Set the PASSWORD environment variable at startup"),
    ("code reference", "password = os.environ['APP_PASSWORD']"),
    ("constant assignment", "TOKEN_REFRESH_INTERVAL = 3600  # seconds"),
]


def test_credentials_are_caught() -> None:
    for label, s in MUST_CATCH:
        assert contains_secret(s), f"contains_secret missed: {label} -> {s!r}"
        assert redact_text(s) != s, f"redact_text left it intact: {label} -> {s!r}"


def test_benign_prose_is_not_over_redacted() -> None:
    for label, s in MUST_NOT_CATCH:
        assert redact_text(s) == s, f"over-redacted: {label} -> {redact_text(s)!r}"


def test_the_specific_json_bypass_that_was_reported() -> None:
    """The exact payload that was returned byte-for-byte before the fix."""
    s = '{"password":"abcdefghijklmnopqr"}'
    out = redact_text(s)
    assert out != s, "the reported JSON bypass is open again"
    assert "abcdefghijklmnopqr" not in out, f"secret value survived redaction: {out!r}"


def test_redaction_removes_the_value_not_just_the_key() -> None:
    for _, s in MUST_CATCH:
        out = redact_text(s)
        assert "[REDACTED]" in out, f"no redaction marker in {out!r}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{'FAILED' if failures else 'PASS'}: {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
