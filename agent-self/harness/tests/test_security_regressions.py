from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.adapters import normalize_event
from harness.dispatcher import HarnessDispatcher
from harness.ledger import EventLedger, project_key
from harness.modules import SanitizedCheckpointModule
from harness.redaction import contains_secret, redact_text


PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
PRIVATE_BODY_SENTINEL
YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo=
-----END PRIVATE KEY-----"""


def _event(tmp_path: Path, name: str, **overrides):
    payload = {
        "session_id": "secret-session",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": name,
    }
    payload.update(overrides)
    return normalize_event(payload, provider="codex", event_name=name)


def test_private_key_redaction_removes_header_body_and_footer():
    redacted = redact_text(f"before\n{PRIVATE_KEY}\nafter")

    assert contains_secret(PRIVATE_KEY)
    assert "PRIVATE KEY" not in redacted
    assert "PRIVATE_BODY_SENTINEL" not in redacted
    assert "YWJjZGVm" not in redacted
    assert "[REDACTED]" in redacted
    assert redacted.endswith("after")


def test_unterminated_private_key_redacts_everything_after_header():
    redacted = redact_text(
        "safe prefix\n-----BEGIN RSA PRIVATE KEY-----\nPRIVATE_BODY_SENTINEL\nmore body"
    )

    assert redacted == "safe prefix\n[REDACTED]"


@pytest.mark.parametrize(
    "label",
    [
        "DSA PRIVATE KEY",
        "ENCRYPTED PRIVATE KEY",
        "PGP PRIVATE KEY BLOCK",
        "SSH2-ENCRYPTED PRIVATE KEY",
    ],
)
def test_all_private_key_envelopes_are_detected_and_fully_redacted(label):
    secret = (
        f"-----BEGIN {label}-----\n"
        "PRIVATE_BODY_SENTINEL\n"
        f"-----END {label}-----"
    )

    redacted = redact_text(f"before\n{secret}\nafter")

    assert contains_secret(secret)
    assert label not in redacted
    assert "PRIVATE_BODY_SENTINEL" not in redacted
    assert redacted == "before\n[REDACTED]\nafter"


@pytest.mark.parametrize(
    "secret",
    [
        "AKIAIOSFODNN7EXAMPLE",
        "ASIAIOSFODNN7EXAMPLE",
    ],
)
def test_aws_access_key_ids_are_detected_and_redacted(secret):
    assert contains_secret(secret)
    assert secret not in redact_text(secret)


@pytest.mark.parametrize(
    "assignment",
    [
        "AWS_SECRET_ACCESS_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        "AWS_SESSION_TOKEN=abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        "GOOGLE_API_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        "SERVICE_PASSWORD: abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        "SECRET_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD",
    ],
)
def test_secret_bearing_assignments_are_detected_and_redacted(assignment):
    assert contains_secret(assignment)
    assert assignment.split("=", 1)[-1] not in redact_text(assignment)


@pytest.mark.parametrize(
    "secret",
    [
        "xoxb-123456789012-123456789012-abcdefghijklmnopqrstuvwxyz",
        "sk_live_abcdefghijklmnopqrstuvwxyz123456",
        "glpat-abcdefghijklmnopqrstuvwxyz123456",
        "npm_abcdefghijklmnopqrstuvwxyz123456",
        "AIzaabcdefghijklmnopqrstuvwxyz123456789",
    ],
)
def test_common_provider_tokens_are_detected_and_redacted(secret):
    assert contains_secret(secret)
    assert secret not in redact_text(secret)


@pytest.mark.parametrize(
    "path",
    [
        r"D:/Projects/SecretClient/file.txt",
        r"C:\Users\John Doe\Secret Client\file.txt",
        r"\\server\private-share\Secret Client\file.txt",
        "/mnt/c/Users/John Doe/Secret Client/file.txt",
        "/opt/private/Secret Client/file.txt",
        "cwd:/opt/private/Secret Client/file.txt",
    ],
)
def test_checkpoint_path_redaction_never_leaks_absolute_path_tails(path):
    redacted = redact_text(f"artifact={path} and trailing prose", redact_paths=True)

    assert "SecretClient" not in redacted
    assert "Secret Client" not in redacted
    assert "file.txt" not in redacted
    assert "[PATH]" in redacted


def test_project_key_contains_only_hash_not_repository_basename():
    key = project_key(r"D:\Projects\SecretClient")

    assert key.startswith("project-")
    assert "SecretClient" not in key


def test_secret_block_stops_goal_and_checkpoint_persistence(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    checkpoint_root = tmp_path / "checkpoints"
    monkeypatch.setenv("BASIC_MEMORY_CHECKPOINT_DIR", str(checkpoint_root))
    dispatcher = HarnessDispatcher(state_root=state_root)
    payload = {
        "session_id": "secret-session",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": "UserPromptSubmit",
        "prompt": f"Persist this task and credential:\n{PRIVATE_KEY}",
    }

    result = dispatcher.dispatch(payload, provider="codex", event_name="UserPromptSubmit")

    ledger = EventLedger(state_root)
    # Owner directive 2026-07-11: the user's prompt is no longer hard-blocked; the
    # secret is redacted at store-time, so the prompt is processed but nothing
    # sensitive lands raw in the ledger goal, ledger state, or a checkpoint.
    assert result.action != "block"
    goal = ledger.goal(str(tmp_path))
    assert goal  # the (redacted) goal IS persisted now — the prompt was processed
    assert "PRIVATE_BODY_SENTINEL" not in goal
    assert "PRIVATE_BODY_SENTINEL" not in json.dumps(ledger.state(str(tmp_path)))
    assert not checkpoint_root.exists()


def test_labeled_secret_block_never_becomes_a_goal(tmp_path):
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(state_root=state_root)
    assignment = "AWS_SECRET_ACCESS_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    payload = {
        "session_id": "secret-session",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": "UserPromptSubmit",
        "prompt": f"Please remember this credential: {assignment}",
    }

    result = dispatcher.dispatch(payload, provider="codex", event_name="UserPromptSubmit")

    # Owner directive 2026-07-11: redact-not-block — the prompt is processed, but the
    # labeled secret is redacted before it can become a persisted goal or ledger state.
    assert result.action != "block"
    goal = EventLedger(state_root).goal(str(tmp_path))
    assert goal
    assert assignment not in goal
    assert assignment not in json.dumps(EventLedger(state_root).state(str(tmp_path)))


def test_checkpoint_redacts_private_key_body_from_remember_buffer(tmp_path):
    ledger = EventLedger(tmp_path / "state", legacy_root=tmp_path / "no-legacy")
    remember = tmp_path / ".remember"
    remember.mkdir()
    (remember / "now.md").write_text(PRIVATE_KEY, encoding="utf-8")
    vault = tmp_path / "vault"

    SanitizedCheckpointModule(ledger, vault=vault).run(
        _event(tmp_path, "PreCompact", trigger="manual")
    )

    content = next(vault.glob("checkpoint-*.md")).read_text(encoding="utf-8")
    assert "PRIVATE_BODY_SENTINEL" not in content
    assert "PRIVATE KEY" not in content
    assert "[REDACTED]" in content
