"""Security-critical tests for the always-on redaction / control-strip layer.

The load-bearing assertion in this file is negative: a realistic token-bearing
config must produce output in which the secret VALUE appears nowhere.
"""

from __future__ import annotations

import pytest

from mcpctl import safety

# Built at runtime so the literal never sits in the repo as a scannable secret.
FAKE_GH_PAT = "ghp_" + "A" * 36
FAKE_XAI = "xai-" + "B" * 40
FAKE_GEMINI = "AIza" + "C" * 35
FAKE_OPENAI = "sk-" + "D" * 32
FAKE_OPAQUE = "E" * 44


def test_strip_controls_removes_esc_bel_c1_and_del():
    raw = "a\x1b[31mb\x07c\x7fd\x9be\x00f"
    out = safety.strip_controls(raw)
    assert out == "a[31mbcdef"
    for bad in ("\x1b", "\x07", "\x7f", "\x9b", "\x00"):
        assert bad not in out


def test_strip_controls_keeps_tab_lf_cr():
    assert safety.strip_controls("a\tb\nc\rd") == "a\tb\nc\rd"


@pytest.mark.parametrize(
    ("secret", "label"),
    [
        (FAKE_GH_PAT, "gh-pat"),
        (FAKE_XAI, "xai-key"),
        (FAKE_GEMINI, "google-key"),
        (FAKE_OPENAI, "api-key"),
    ],
)
def test_redact_text_masks_each_known_shape(secret: str, label: str):
    out = safety.redact_text(f"token={secret} tail")
    assert secret not in out
    assert label in out
    assert "tail" in out


def test_redact_text_masks_opaque_assignment_without_a_known_prefix():
    """The shape monitorcore's pattern set cannot see: an unprefixed long token."""
    out = safety.redact_text(f"Authorization: Bearer {FAKE_OPAQUE}")
    assert FAKE_OPAQUE not in out
    assert "opaque" in out


def test_redact_text_leaves_short_values_alone():
    assert safety.redact_text("api_key=short") == "api_key=short"


def test_redact_text_collapses_the_home_directory():
    out = safety.redact_text(r"C:\Users\someone\.codex\config.toml")
    assert "someone" not in out
    assert out.startswith("~")


def test_safe_is_redact_then_strip_controls():
    out = safety.safe(f"\x1b]8;;http://x\x07{FAKE_GH_PAT}")
    assert FAKE_GH_PAT not in out
    assert "\x1b" not in out
    assert "\x07" not in out


def test_env_fields_reports_names_and_classification_never_values():
    env = {
        "TAVILY_API_KEY": FAKE_OPENAI,
        "FB_PAGE_ACCESS_TOKEN": "",
        "XAI_API_KEY": "${XAI_API_KEY}",
        "AWS_REGION": "eu-central-1",
    }
    fields = safety.env_fields(env)
    assert [(f.name, f.kind) for f in fields] == [
        ("AWS_REGION", "present"),
        ("FB_PAGE_ACCESS_TOKEN", "absent"),
        ("TAVILY_API_KEY", "present"),
        ("XAI_API_KEY", "reference"),
    ]
    rendered = repr(fields)
    for value in env.values():
        if value and not value.startswith("${"):
            assert value not in rendered


def test_env_fields_tolerates_a_non_mapping_env_block():
    assert safety.env_fields(None) == ()
    assert safety.env_fields(["not", "a", "mapping"]) == ()


def test_env_fields_stringifies_and_sanitises_a_hostile_var_name():
    fields = safety.env_fields({"A\x1b]0;pwn\x07B": "x"})
    assert len(fields) == 1
    assert fields[0].name == "A]0;pwnB"
