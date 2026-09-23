"""Tests for hub.redaction: outbound prompt scanning and value-free logging."""

from __future__ import annotations

import copy
import json
import random
import string
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub import redaction  # noqa: E402
from tests import conftest_hub as helpers  # noqa: E402

HF_ENV = "HUGGINGFACE_TOKEN_INFERENCE"
OR_ENV = "OPENROUTER_API_KEY_CODEX_SIDECAR"
HF_VALUE = "zq9" * 8
OR_VALUE = "or-value-" + "7" * 12
SHORT_VALUE = "abc"

ENVIRON = {
    HF_ENV: HF_VALUE,
    OR_ENV: OR_VALUE,
    "SHORT_ONE": SHORT_VALUE,
    "UNRELATED": "not-a-credential-value",
}
ENV_NAMES = [HF_ENV, OR_ENV, "SHORT_ONE", "UNSET_ONE"]

PATTERN_KINDS = (
    "huggingface",
    "github_token",
    "github_pat",
    "openrouter",
    "anthropic",
    "openai_project",
    "openai",
    "digitalocean",
    "aws_access_key",
    "slack",
    "private_key",
    "jwt",
)


def text_part(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def seeded_messages() -> tuple[list[dict[str, Any]], list[tuple[int, str, str, int]]]:
    """Twelve secrets across roles, string content and text parts.

    Returns the messages and the expected (index, path, kind, length) findings.
    """
    ghp = helpers.secret_like("github_token")
    orv1 = helpers.secret_like("openrouter")
    akia = helpers.secret_like("aws_access_key")
    jwt = helpers.secret_like("jwt")
    slack = helpers.secret_like("slack")
    pem = helpers.secret_like("private_key")
    pat = helpers.secret_like("github_pat")
    ant = helpers.secret_like("anthropic")
    dop = helpers.secret_like("digitalocean")
    hf_pattern = helpers.secret_like("huggingface")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "token is " + HF_VALUE + " keep it"},
        {
            "role": "user",
            "content": [
                text_part("plain text, short env value " + SHORT_VALUE),
                {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
                text_part("use " + ghp + " for github"),
            ],
        },
        {"role": "assistant", "content": OR_VALUE + " and " + orv1},
        {"role": "user", "content": "aws " + akia + " end"},
        {
            "role": "user",
            "content": [text_part("jwt " + jwt), text_part("slack " + slack)],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "key:\n" + pem + "\n"},
        {"role": "user", "content": pat},
        {"role": "user", "content": "anthropic " + ant},
        {"role": "user", "content": "do " + dop},
        {"role": "user", "content": "hf " + hf_pattern},
        {"role": "user", "content": None},
        {
            "role": "user",
            "content": [text_part("clean"), "not-a-part", {"type": "text"}],
        },
    ]
    expected = [
        (0, "content", "env:" + HF_ENV, len(HF_VALUE)),
        (1, "content[2].text", "pattern:github_token", len(ghp)),
        (2, "content", "env:" + OR_ENV, len(OR_VALUE)),
        (2, "content", "pattern:openrouter", len(orv1)),
        (3, "content", "pattern:aws_access_key", len(akia)),
        (4, "content[0].text", "pattern:jwt", len(jwt)),
        (4, "content[1].text", "pattern:slack", len(slack)),
        (5, "content", "pattern:private_key", len(pem)),
        (6, "content", "pattern:github_pat", len(pat)),
        (7, "content", "pattern:anthropic", len(ant)),
        (8, "content", "pattern:digitalocean", len(dop)),
        (9, "content", "pattern:huggingface", len(hf_pattern)),
    ]
    return messages, expected


@pytest.fixture
def redactor() -> redaction.Redactor:
    return redaction.Redactor(ENV_NAMES, ENVIRON)


def test_env_capture_ignores_short_and_unset(redactor: redaction.Redactor) -> None:
    assert redactor.env_names == (HF_ENV, OR_ENV)
    assert redactor.describe(HF_ENV) == HF_ENV + "(len=24)"
    assert redactor.describe("SHORT_ONE") == "SHORT_ONE(len=3)"
    assert redactor.describe("UNSET_ONE") == "UNSET_ONE(unset)"
    for name in ENV_NAMES:
        assert HF_VALUE not in redactor.describe(name)
        assert OR_VALUE not in redactor.describe(name)


def test_redactor_defaults_to_process_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_TEST_CRED", "value-" + "1" * 12)
    redactor = redaction.Redactor(["HUB_TEST_CRED"])
    assert redactor.env_names == ("HUB_TEST_CRED",)
    assert (
        redactor.redact_text("v: value-" + "1" * 12)
        == "v: <redacted:env:HUB_TEST_CRED>"
    )


def test_scan_messages_finds_twelve_seeded_secrets(
    redactor: redaction.Redactor,
) -> None:
    messages, expected = seeded_messages()
    findings = redactor.scan_messages(messages)
    assert [(f.index, f.path, f.kind, f.length) for f in findings] == expected
    assert len(findings) == 12
    assert findings[0].as_dict() == {
        "index": 0,
        "path": "content",
        "kind": "env:" + HF_ENV,
        "length": len(HF_VALUE),
    }


def test_redact_messages_replaces_hits_and_preserves_input(
    redactor: redaction.Redactor,
) -> None:
    messages, expected = seeded_messages()
    before = copy.deepcopy(messages)
    redacted, count = redactor.redact_messages(messages)
    assert count == 12
    assert messages == before
    dumped = json.dumps(redacted)
    for _, _, kind, _ in expected:
        assert "<redacted:" + kind + ">" in dumped
    assert HF_VALUE not in dumped
    assert OR_VALUE not in dumped
    assert helpers.secret_like("github_token") not in dumped
    assert redacted[0]["content"] == "token is <redacted:env:" + HF_ENV + "> keep it"
    assert redacted[1]["content"][1] == messages[1]["content"][1]
    assert redacted[1]["content"][0]["text"].endswith(SHORT_VALUE)
    assert redacted[2]["content"] == (
        "<redacted:env:" + OR_ENV + "> and <redacted:pattern:openrouter>"
    )
    assert redacted[10]["content"] is None
    assert redacted[11]["content"][1] == "not-a-part"
    assert redacted[11]["content"][2] == {"type": "text"}


def test_scan_and_redact_tolerate_non_list_input(
    redactor: redaction.Redactor,
) -> None:
    assert redactor.scan_messages("not a list") == []  # type: ignore[arg-type]
    assert redactor.scan_messages([42, "x", None]) == []  # type: ignore[list-item]
    assert redactor.redact_messages("nope") == ("nope", 0)  # type: ignore[arg-type]
    assert redactor.redact_messages([42]) == ([42], 0)  # type: ignore[list-item]


def test_env_value_wins_over_pattern_at_same_position() -> None:
    token = helpers.secret_like("huggingface")
    redactor = redaction.Redactor(["TOKEN_ENV"], {"TOKEN_ENV": token})
    hits = redactor.scan_text("use " + token + " now")
    assert [(hit.kind, hit.end - hit.start) for hit in hits] == [
        ("env:TOKEN_ENV", len(token))
    ]


def test_env_value_with_regex_metacharacters_matches_literally() -> None:
    value = "a.b*c(d)e+f?"
    redactor = redaction.Redactor(["META"], {"META": value})
    assert redactor.redact_text("x " + value + " y") == "x <redacted:env:META> y"
    assert redactor.redact_text("x aXbYc(d)e+f? y") == "x aXbYc(d)e+f? y"


@pytest.mark.parametrize("kind", PATTERN_KINDS)
def test_every_pattern_is_detected_once(kind: str) -> None:
    assert kind in redaction.SECRET_PATTERNS
    sample = helpers.secret_like(kind)
    hits = redaction.Redactor(()).scan_text("before " + sample + " after")
    assert [hit.kind for hit in hits] == ["pattern:" + kind]
    assert hits[0].end - hits[0].start == len(sample)


def test_pem_header_without_footer_redacts_to_end() -> None:
    dashes = "-" * 5
    head = dashes + "BEGIN EC PRIVATE" + " KEY" + dashes
    text = "cert:\n" + head + "\nAAAA\nBBBB"
    out = redaction.redact_text(text)
    assert out == "cert:\n<redacted:pattern:private_key>"


def test_common_prose_is_not_flagged() -> None:
    prose = " ".join(
        [
            "the ta" + "sk-list mentions",
            "hf" + "_transformers,",
            "gh" + "p_tokens in docs,",
            "a de" + "sk-side note,",
            "AK" + "IAS as a word,",
            "xox" + "b-style ids and",
            "ey" + "J.foo",
        ]
    )
    assert redaction.Redactor(()).scan_text(prose) == []
    assert redaction.redact_text(prose) == prose
    assert redaction.redact_text("") == ""


def test_redact_obj_masks_sensitive_keys_and_scrubs_values(
    redactor: redaction.Redactor,
) -> None:
    bearer = "Bearer " + "q" * 20
    payload = {
        "headers": {"Authorization": bearer, "Accept": "application/json"},
        "api_key": "k" * 12,
        "X-Api-Key": "m" * 12,
        "nested": [{"client_secret": "s" * 9, "Set-Cookie": "sid=1"}, "plain", 4],
        "content": "prompt with " + HF_VALUE + " inside",
        "count": 3,
        "flag": None,
        7: "numeric key " + helpers.secret_like("slack"),
        "token": {"inner": "t" * 10},
    }
    out = redactor.redact_obj(payload)
    assert out["headers"]["Authorization"] == "<redacted:key=authorization,len=27>"
    assert out["headers"]["Accept"] == "application/json"
    assert out["api_key"] == "<redacted:key=api_key,len=12>"
    assert out["X-Api-Key"] == "<redacted:key=x_api_key,len=12>"
    assert out["nested"][0]["client_secret"] == "<redacted:key=client_secret,len=9>"
    assert out["nested"][0]["Set-Cookie"] == "<redacted:key=set_cookie,len=5>"
    assert out["nested"][1:] == ["plain", 4]
    assert out["content"] == "prompt with <redacted:env:" + HF_ENV + "> inside"
    assert out["count"] == 3
    assert out["flag"] is None
    assert out[7] == "numeric key <redacted:pattern:slack>"
    structure_len = len(json.dumps({"inner": "t" * 10}))
    assert out["token"] == "<redacted:key=token,len=" + str(structure_len) + ">"
    assert payload["headers"]["Authorization"] == bearer
    assert redactor.redact_obj(("tuple", HF_VALUE)) == [
        "tuple",
        "<redacted:env:" + HF_ENV + ">",
    ]
    assert redactor.redact_obj(2.5) == 2.5


def test_module_level_helpers_use_patterns_only() -> None:
    sample = helpers.secret_like("openai")
    assert redaction.redact_text("k " + sample) == "k <redacted:pattern:openai>"
    assert redaction.redact_obj({"password": "p" * 8, "note": "fine"}) == {
        "password": "<redacted:key=password,len=8>",
        "note": "fine",
    }
    assert redaction.mask("pattern:openai") == "<redacted:pattern:openai>"
    assert redaction.is_sensitive_key("Proxy-Authorization") is True
    assert redaction.is_sensitive_key("model") is False


def test_generated_prompts_never_leak_through_logs_surface() -> None:
    rng = random.Random(20260902)
    alphabet = string.ascii_letters + string.digits + "-_"
    for _ in range(200):
        length = rng.randint(12, 48)
        value = "".join(rng.choice(alphabet) for _ in range(length))
        redactor = redaction.Redactor(["GEN_CRED"], {"GEN_CRED": value})
        assert value not in redactor.describe("GEN_CRED")
        assert redactor.describe("GEN_CRED") == "GEN_CRED(len=" + str(length) + ")"
        log_payload = {
            "authorization": "Bearer " + value,
            "token": value,
            "note": "prompt says " + value + " twice " + value,
            "parts": [value, {"x": value}],
        }
        dumped = json.dumps(redactor.redact_obj(log_payload))
        assert value not in dumped
        assert redactor.redact_text(value + " tail") == "<redacted:env:GEN_CRED> tail"
        assert redactor.scan_messages([{"role": "user", "content": value}])[0].kind == (
            "env:GEN_CRED"
        )
