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
    secret = f"-----BEGIN {label}-----\nPRIVATE_BODY_SENTINEL\n-----END {label}-----"

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


# Regression proof for the JSON-credential bypass fixed in #222 / #226. The fix
# landed WITHOUT a test in this CI-gated suite, and `ci/harness/tests/` (which does
# carry one) is named in no workflow, so nothing here was protecting it. Mutation-
# measured 2026-07-29 by reverting the three redaction.py patterns: all 56 redaction
# tests in this tree stayed GREEN while `{"password":"abcdefghijklmnopqr"}` was
# returned byte-for-byte, `password=!CorrectHorse...` passed (the old value class
# excluded punctuation), and `Authorization: Basic <b64>` passed (only Bearer was
# covered). This matters because redact_text guards set_goal before the event ledger
# persists it (modules.py `set_goal(..., redact_text(prompt))`, ledger.py set_goal).
@pytest.mark.parametrize(
    ("label", "payload", "secret"),
    [
        ("json compact", '{"password":"abcdefghijklmnopqr"}', "abcdefghijklmnopqr"),
        ("json spaced", '{"password": "abcdefghijklmnopqr"}', "abcdefghijklmnopqr"),
        ("json api_key", '{"api_key":"abcdefghijklmnopqrst"}', "abcdefghijklmnopqrst"),
        (
            "punctuation-leading value",
            "password=!CorrectHorseBatteryStaple123",
            "!CorrectHorseBatteryStaple123",
        ),
        (
            "basic auth header",
            "Authorization: Basic dXNlcjpTdXBlclNlY3JldCE=",
            "dXNlcjpTdXBlclNlY3JldCE=",
        ),
    ],
)
def test_structured_credentials_are_detected_and_their_value_redacted(
    label, payload, secret
):
    assert contains_secret(payload), f"contains_secret missed {label}: {payload!r}"

    redacted = redact_text(payload)

    assert secret not in redacted, f"{label} value survived: {redacted!r}"
    assert "[REDACTED]" in redacted, f"{label} left unmarked: {redacted!r}"


def test_structured_tool_input_mapping_is_scanned_not_only_flat_text():
    """A non-string tool input is JSON-serialized before it is scanned."""
    mapping = {"command": "deploy", "password": "abcdefghijklmnopqr"}

    assert contains_secret(mapping)
    assert "abcdefghijklmnopqr" not in redact_text(json.dumps(mapping))


# Over-redaction has a real cost: the ledger goal and the re-anchor become unreadable.
# A pattern widened until everything matches would pass the cases above and fail here.
@pytest.mark.parametrize(
    "prose",
    [
        "the password field is required on the signup form",
        "rotate the token before Friday, see the runbook",
        "api_key handling is covered in guides/security.md",
        "Set the PASSWORD environment variable at startup",
        "TOKEN_REFRESH_INTERVAL = 3600  # seconds",
    ],
)
def test_benign_prose_naming_a_credential_field_is_not_over_redacted(prose):
    assert redact_text(prose) == prose


def test_json_credential_in_a_prompt_never_becomes_a_persisted_goal(tmp_path):
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(state_root=state_root)
    payload = {
        "session_id": "secret-session",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": "UserPromptSubmit",
        "prompt": 'Store this config: {"password":"abcdefghijklmnopqr"}',
    }

    result = dispatcher.dispatch(
        payload, provider="codex", event_name="UserPromptSubmit"
    )

    # Redact-not-block, as with the labeled-assignment sibling above: the prompt is
    # processed, but the credential must not reach the durable goal or ledger state.
    assert result.action != "block"
    ledger = EventLedger(state_root)
    goal = ledger.goal(str(tmp_path))
    assert goal
    assert "abcdefghijklmnopqr" not in goal
    assert "abcdefghijklmnopqr" not in json.dumps(ledger.state(str(tmp_path)))


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

    result = dispatcher.dispatch(
        payload, provider="codex", event_name="UserPromptSubmit"
    )

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

    result = dispatcher.dispatch(
        payload, provider="codex", event_name="UserPromptSubmit"
    )

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


# --- cross-session verification-evidence leakage (D-wu-24) -------------------
# A completion claim must be substantiated only by evidence the CLAIMING session
# produced. Claude Code sends prompt_id rather than turn_id, so its events used to
# normalize to turn_id="" -- which the ledger reads as "matches every turn". A
# sibling session's green pytest receipt therefore satisfied this session's gate.
# These payloads deliberately carry NO turn_id, reproducing that live Claude shape.


def _claim_gate_outcome(root: Path, prover_session: str):
    """Session A edits a file, `prover_session` runs pytest, then A claims done."""
    project = root / "proj"
    (project / ".git").mkdir(parents=True)
    cwd = str(project)
    dispatcher = HarnessDispatcher(state_root=root / "state")

    dispatcher.dispatch(
        {
            "session_id": "sess-A",
            "cwd": cwd,
            "tool_name": "Write",
            "tool_input": {"file_path": str(project / "x.py")},
            "tool_response": "ok",
        },
        provider="claude",
        event_name="PostToolUse",
    )
    dispatcher.dispatch(
        {
            "session_id": prover_session,
            "cwd": cwd,
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
            "tool_response": {"exit_code": 0, "stdout": "1 passed in 0.10s"},
        },
        provider="claude",
        event_name="PostToolUse",
    )
    return dispatcher.dispatch(
        {
            "session_id": "sess-A",
            "cwd": cwd,
            "last_assistant_message": "Fixed; all tests passed.",
        },
        provider="claude",
        event_name="Stop",
    )


def test_completion_gate_ignores_another_sessions_verification_receipt(tmp_path):
    leaked = _claim_gate_outcome(tmp_path, prover_session="sess-B")

    assert leaked.action == "inject"
    assert leaked.reason_code == "unverified_completion_claim"
    assert any(
        "without recent objective verification" in text
        for text in leaked.additional_context
    )


def test_completion_gate_still_accepts_the_claiming_sessions_own_receipt(tmp_path):
    # The other half of the guard: scoping evidence to the session must NOT make the
    # gate fire on every Claude Stop (no Claude event carries a turn_id). A session
    # that proved its own claim stays silent.
    owned = _claim_gate_outcome(tmp_path, prover_session="sess-A")

    assert owned.action == "allow"
    assert owned.reason_code == "ok"


def test_evidence_turn_id_prefers_host_turn_then_session_then_declines(tmp_path):
    explicit = _event(tmp_path, "Stop", turn_id="turn-9", session_id="sess-1")
    assert explicit.evidence_turn_id == "turn-9"

    first = _event(tmp_path, "Stop", turn_id="", session_id="sess-1")
    second = _event(tmp_path, "Stop", turn_id="", session_id="sess-2")
    assert first.evidence_turn_id.startswith("session-")
    assert first.evidence_turn_id != second.evidence_turn_id

    # normalize_event defaults a missing session_id to the literal "unknown", which
    # every unidentified session shares, so it can scope nothing: decline instead of
    # minting a token that would silently re-merge those sessions.
    unidentified = _event(tmp_path, "Stop", turn_id="", session_id="")
    assert unidentified.session_id == "unknown"
    assert unidentified.evidence_turn_id == ""
