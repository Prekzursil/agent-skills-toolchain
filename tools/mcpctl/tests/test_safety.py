"""Security-critical tests for the always-on redaction / control-strip layer.

The load-bearing assertion in this file is negative: a realistic token-bearing
config must produce output in which the secret VALUE appears nowhere.
"""

from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import cast

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


def test_safe_masks_a_secret_with_control_bytes_ADJACENT_to_it():
    """The easy case: controls sit beside the token, so the token stays intact."""
    out = safety.safe(f"\x1b]8;;http://x\x07{FAKE_GH_PAT}")
    assert FAKE_GH_PAT not in out
    assert "\x1b" not in out
    assert "\x07" not in out


@pytest.mark.parametrize(
    "sep",
    ["\x1b", "\x07", "\x00", "\x7f", "\x9b"],
    ids=["esc", "bel", "nul", "del", "c1"],
)
@pytest.mark.parametrize(
    "token",
    [FAKE_GH_PAT, FAKE_XAI, FAKE_GEMINI, FAKE_OPENAI],
    ids=["ghp", "xai", "gemini", "openai"],
)
def test_safe_masks_a_secret_with_a_control_byte_INTERLEAVED_inside_it(
    token: str, sep: str
):
    """The bypass: a control byte INSIDE the token must not defeat redaction.

    Order matters. If ``redact`` runs first it matches against text that still holds
    the control byte -- no secret pattern's character class admits C0/C1/DEL, so
    nothing matches -- and a later ``strip_controls`` then REASSEMBLES the clean,
    complete secret into the output. The sanitiser would destroy the very evidence
    that should have triggered the mask, so ``safe`` must strip FIRST, then match.
    """
    poisoned = token[:10] + sep + token[10:]
    out = safety.safe(f"401 Unauthorized: Bearer {poisoned}")
    assert token not in out, (
        f"the clean secret was reassembled verbatim after stripping {sep!r}"
    )
    assert sep not in out
    assert "[REDACTED" in out


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


def test_load_upstream_success_path_is_covered_without_the_sibling_tree():
    """Coverage of the import-succeeds branch must not depend on tools/monitorcore.

    ``tests/test_safety_contract.py`` also exercises this path against the REAL sibling
    package (that is its job -- drift detection), but it hard-fails if that tree is
    absent. Covering the branch here with synthetic stubs keeps the coverage gate a
    property of mcpctl alone.
    """
    stub_textsafe = cast(
        "ModuleType", SimpleNamespace(strip_controls=lambda s: f"stripped:{s}")
    )
    stub_redact = cast(
        "ModuleType", SimpleNamespace(redact=lambda s: (f"masked:{s}", 3))
    )
    modules = {"monitorcore.textsafe": stub_textsafe, "monitorcore.redact": stub_redact}

    upstream = safety.load_upstream(lambda name: modules[name])

    assert upstream is not None
    assert upstream.strip_controls("x") == "stripped:x"
    assert upstream.redact("y") == ("masked:y", 3)
