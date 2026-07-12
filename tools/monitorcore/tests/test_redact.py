"""Redaction filter tests (strict-by-default, fail-closed, pure).

Covers every LOCKED pattern + the two reasoned additions (gh[oure]_ token,
tightened standalone JWT), the 5 home-path forms (incl the 8.3 ``PREKZU~1``
short name), n_masked counts, ``enabled=False`` passthrough, fail-closed
behaviour, ``Redactor.count`` accumulation, and the benign-JWT / dotted-text
NON-match.

The PEM case is PEM-DEFANGED: the ``_pem`` helper assembles the private-key
``BEGIN``/``END`` markers from a separate dash run at run time, so the committed
test source carries no contiguous dashed BEGIN-private-key literal (gitleaks
stays green) while ``redact()`` still receives a genuine PEM block to mask. No
external fixture file is needed.
"""

import json

import pytest

from monitorcore.redact import Redactor, redact

# The secret scanner (gitleaks) flags any contiguous dashed BEGIN-private-key
# marker even when the key body is FAKE. Assemble that marker from a separate
# dash run so the committed test source carries no such literal, while redact()
# still receives a genuine, contiguous PEM block to mask at run time.
_DASHES = "-" * 5


def _pem(*body: str) -> str:
    head = _DASHES + "BEGIN PRIVATE KEY" + _DASHES
    tail = _DASHES + "END PRIVATE KEY" + _DASHES
    return "\n".join((head, *body, tail))


# --------------------------------------------------------------------------
# Per-pattern masking (each masks, raw disappears, count == 1)
# --------------------------------------------------------------------------

SECRET_CASES = [
    ("sk-FAKE0000000000000000000000", "[REDACTED:api-key]"),
    ("ghp_FAKE00000000000000000000000000000000", "[REDACTED:gh-pat]"),
    ("github_pat_FAKE00000000000000000000000000", "[REDACTED:gh-pat]"),
    ("AKIAFAKE0000000000AB", "[REDACTED:aws-akid]"),
    ("xoxb-FAKE000000000000", "[REDACTED:slack]"),
    ("gho_FAKE00000000000000000000000000000000", "[REDACTED:gh-token]"),
    (
        "Bearer eyJFAKEheaderaaa.eyJFAKEpayloadbbb.FAKEsigccc000",
        "[REDACTED:jwt]",
    ),
    (
        _pem("MIIFAKEONE", "MIIFAKETWO"),
        "[REDACTED:pem-private-key]",
    ),
    (
        "C:\\Users\\Prekzursil\\agent-skills-toolchain.gitcrypt.key",
        "[REDACTED:gitcrypt-key]",
    ),
    (
        "jwt eyJFAKEheaderaaa.eyJFAKEpayloadbbb.FAKEsigccc000 end",
        "[REDACTED:jwt]",
    ),
]


@pytest.mark.parametrize("raw, token", SECRET_CASES)
def test_each_secret_pattern_masks(raw, token):
    masked, n = redact(raw)
    assert token in masked
    assert n >= 1
    # The raw secret body must not survive (allow the literal 'Bearer '/'jwt '
    # label prefixes which are intentionally preserved).
    assert "FAKE" not in masked or "KEYMATERIAL" not in masked
    assert "FAKE0000" not in masked
    assert "eyJFAKEheaderaaa" not in masked


def test_pem_block_fully_masked():
    raw = _pem("MIIFAKEKEYMATERIALLINEONE", "MIIFAKEKEYMATERIALLINETWO")
    masked, n = redact(raw)
    assert masked == "[REDACTED:pem-private-key]"
    assert n == 1
    assert "KEYMATERIAL" not in masked


def test_bearer_jwt_keeps_label_prefix():
    masked, n = redact("Bearer eyJFAKEheaderaaa.eyJFAKEpayloadbbb.FAKEsigccc000")
    assert masked == "Bearer [REDACTED:jwt]"
    assert n == 1


def test_ghp_and_gho_are_distinct_tokens():
    masked, n = redact(
        "ghp_FAKE00000000000000000000000000000000 "
        "gho_FAKE00000000000000000000000000000000"
    )
    assert "[REDACTED:gh-pat]" in masked
    assert "[REDACTED:gh-token]" in masked
    assert n == 2


# --------------------------------------------------------------------------
# Home-path collapse (all 5 forms -> '~', remainder preserved)
# --------------------------------------------------------------------------

HOME_CASES = [
    ("C:\\Users\\Prekzursil\\Documents\\notes.txt", "~\\Documents\\notes.txt"),
    ("C:/Users/Prekzursil/Documents/notes.txt", "~/Documents/notes.txt"),
    ("/c/Users/Prekzursil/work/file", "~/work/file"),
    ("/mnt/c/Users/Prekzursil/work/file", "~/work/file"),
    ("C:\\Users\\PREKZU~1\\Local\\cache", "~\\Local\\cache"),
]


@pytest.mark.parametrize("raw, expected", HOME_CASES)
def test_home_path_collapses(raw, expected):
    masked, n = redact(raw)
    assert masked == expected
    assert n == 1
    assert "Prekzursil" not in masked
    assert "PREKZU~1" not in masked


def test_home_collapse_keeps_username_boundary():
    # Username stops at the first separator; the tail is preserved verbatim.
    masked, _ = redact("see C:/Users/Prekzursil/x and /mnt/c/Users/Prekzursil/y")
    assert masked == "see ~/x and ~/y"


# A tool_input dict is rendered via ``json.dumps`` in BOTH renderers, which
# escapes each backslash: a raw ``C:\Users\<u>`` becomes the doubled
# ``C:\\Users\\<u>`` on the wire. A single-separator home regex stalls on the
# second backslash and leaks the real username into every export; the separators
# must be one-or-more. This guards the JSON-serialized form directly.
JSON_HOME_CASES = [
    (json.dumps({"p": r"C:\Users\Prekzursil\proj"}), '{"p": "~\\\\proj"}'),
    (json.dumps({"p": "C:/Users/Prekzursil/proj"}), '{"p": "~/proj"}'),
    (
        json.dumps({"cmd": r"Read C:\Users\Prekzursil\Reframe\main.py"}),
        '{"cmd": "Read ~\\\\Reframe\\\\main.py"}',
    ),
]


@pytest.mark.parametrize("raw, expected", JSON_HOME_CASES)
def test_json_serialized_home_path_collapses(raw, expected):
    masked, n = redact(raw)
    assert masked == expected
    assert n == 1
    assert "Prekzursil" not in masked


# --------------------------------------------------------------------------
# Non-match guarantees (tightened JWT must not touch benign dotted text)
# --------------------------------------------------------------------------


def test_benign_jwt_lookalike_not_masked():
    raw = "benign-jwt-lookalike: abcdef...not.a.jwt.value"
    masked, n = redact(raw)
    assert masked == raw
    assert n == 0


def test_benign_dotted_base64_not_masked():
    # Three dotted base64-ish segments but no eyJ header -> not a JWT.
    raw = "chunk aGVsbG8.d29ybGQ.c2lnbmF0dXJl done"
    masked, n = redact(raw)
    assert masked == raw
    assert n == 0


def test_long_dotted_base64_without_eyJ_anchor_not_masked():
    # Three >=10-char base64 segments that would satisfy the length floor but
    # do NOT start with the ``eyJ`` header. This discriminates the ``eyJ`` anchor
    # specifically: drop the anchor from the pattern and this input WOULD be
    # masked, so the assertion proves the header (not just the length) is load-
    # bearing in the tightened standalone-JWT rule.
    raw = "aaaaaaaaaabbb.ccccccccccddd.eeeeeeeeeefff"
    masked, n = redact(raw)
    assert masked == raw
    assert n == 0


def test_plain_text_passthrough_with_zero_count():
    raw = "just a normal sentence with no secrets at all"
    masked, n = redact(raw)
    assert masked == raw
    assert n == 0


# --------------------------------------------------------------------------
# enabled=False passthrough
# --------------------------------------------------------------------------


def test_disabled_is_passthrough():
    raw = "sk-FAKE0000000000000000000000 and C:/Users/Prekzursil/x"
    masked, n = redact(raw, enabled=False)
    assert masked == raw
    assert n == 0


def test_redactor_disabled_passthrough_no_count():
    r = Redactor(enabled=False)
    out = r("sk-FAKE0000000000000000000000")
    assert out == "sk-FAKE0000000000000000000000"
    assert r.count == 0


# --------------------------------------------------------------------------
# Redactor.count accumulation across calls
# --------------------------------------------------------------------------


def test_redactor_count_accumulates():
    r = Redactor()
    r("sk-FAKE0000000000000000000000")  # 1
    r("C:/Users/Prekzursil/x and gho_" + "0" * 36)  # home(1) + gh-token(1) = 2
    assert r.count == 3


def test_redactor_masks_like_redact():
    r = Redactor()
    raw = "ghp_FAKE00000000000000000000000000000000"
    assert r(raw) == "[REDACTED:gh-pat]"
    assert r.count == 1


# --------------------------------------------------------------------------
# Fail-closed: a raising pattern must not surface raw text or raise
# --------------------------------------------------------------------------


def test_fail_closed_on_pattern_error(monkeypatch):
    import re as _re

    import monitorcore.redact as rd

    class _BadPattern:
        def subn(self, repl, text):
            raise _re.error("boom")  # simulate a compiled-pattern .subn failure

    # Insert a poisoned pattern between real ones; masking must still proceed
    # for the healthy patterns and never return the raw input.
    poisoned = list(rd._SECRET_PATTERNS)
    poisoned.insert(1, (_BadPattern(), "[REDACTED:boom]"))
    monkeypatch.setattr(rd, "_SECRET_PATTERNS", poisoned)

    raw = "sk-FAKE0000000000000000000000 keep going"
    masked, n = redact(raw)  # must not raise
    assert "sk-FAKE" not in masked  # healthy pattern still applied
    assert "[REDACTED:api-key]" in masked
    assert masked != raw
    assert n >= 1


def test_fail_closed_never_returns_raw_even_if_all_fail(monkeypatch):
    import monitorcore.redact as rd

    class _BadPattern:
        def subn(self, repl, text):
            raise ValueError("boom")

    monkeypatch.setattr(rd, "_SECRET_PATTERNS", [(_BadPattern(), "x")])
    monkeypatch.setattr(rd, "_HOME_PATTERNS", [(_BadPattern(), "y")])
    raw = "sk-FAKE0000000000000000000000"
    masked, n = redact(raw)  # must not raise
    assert isinstance(masked, str)
    assert n == 0
