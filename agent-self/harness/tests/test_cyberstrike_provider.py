from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from harness import dispatcher as dispatcher_module
from harness.adapters import normalize_event, render_output
from harness.dispatcher import _parse_args
from harness.models import HookResult
from harness.registration import build_hooks


def _event_schema() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "schemas" / "hook-event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _hook_result_schema() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "schemas" / "hook-result.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_hook_result_matches_schema(document: dict[str, object]) -> None:
    schema = _hook_result_schema()
    assert set(schema["required"]).issubset(document)
    assert set(document).issubset(schema["properties"])
    assert re.fullmatch(schema["properties"]["status"]["pattern"], document["status"])
    assert document["action"] in schema["properties"]["action"]["enum"]
    assert re.fullmatch(
        schema["properties"]["reason_code"]["pattern"], document["reason_code"]
    )
    contexts = document["additional_context"]
    assert isinstance(contexts, list)
    assert len(contexts) <= schema["properties"]["additional_context"]["maxItems"]
    assert all(isinstance(item, str) for item in contexts)
    assert all(
        len(item) <= schema["properties"]["additional_context"]["items"]["maxLength"]
        for item in contexts
    )
    if "continuation" in document:
        assert document["continuation"] is None or isinstance(
            document["continuation"], str
        )


class _Module:
    def __init__(self, name: str, result: HookResult):
        self.name = name
        self._result = result

    def run(self, _event) -> HookResult:
        return self._result


def test_cyberstrike_normalizes_to_the_shared_contract(tmp_path):
    common = {
        "session_id": "session-1",
        "turn_id": "turn-2",
        "cwd": str(tmp_path),
        "permission_mode": "bypassPermissions",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_use_id": "tool-3",
        "tool_input": {"command": "pytest -q"},
        "tool_response": {"exit_code": 0, "output": "12 passed"},
    }

    cyberstrike = normalize_event(
        common, provider="cyberstrike", event_name="PostToolUse"
    )
    codex = normalize_event(common, provider="codex", event_name="PostToolUse")

    assert cyberstrike.provider == "cyberstrike"
    assert cyberstrike.to_dict() == codex.to_dict() | {"provider": "cyberstrike"}


def test_cyberstrike_render_output_returns_the_raw_hook_result_contract():
    result = HookResult.success(
        action="continue",
        reason_code="handoff_pending",
        additional_context=["Queue this for the next real turn."],
        continuation="resume on the next turn",
    )

    assert (
        render_output(result, provider="cyberstrike", event_name="Stop")
        == result.to_dict()
    )


def test_dispatcher_cli_accepts_cyberstrike_provider():
    args = _parse_args(["--provider", "cyberstrike", "--event", "Stop"])

    assert args.provider == "cyberstrike"
    assert args.event == "Stop"


def test_cyberstrike_main_bounds_aggregated_contexts_to_schema_limit(
    monkeypatch, tmp_path, capsys
):
    contexts = [f"context-{index:02d}" for index in range(20)]
    modules = [
        _Module(
            f"module-{index:02d}",
            HookResult.success(
                action="inject",
                reason_code="goal_reinjection",
                additional_context=[context],
            ),
        )
        for index, context in enumerate(contexts)
    ]
    monkeypatch.setattr(
        dispatcher_module, "build_default_modules", lambda _root: modules
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "cyberstrike-session",
                    "turn_id": "turn-1",
                    "cwd": str(tmp_path),
                    "hook_event_name": "Stop",
                }
            )
        ),
    )
    state_root = tmp_path / "state"

    rc = dispatcher_module.main(
        [
            "--provider",
            "cyberstrike",
            "--event",
            "Stop",
            "--state-root",
            str(state_root),
        ]
    )

    assert rc == 0
    rendered = json.loads(capsys.readouterr().out)
    _assert_hook_result_matches_schema(rendered)
    assert rendered["additional_context"][:15] == contexts[:15]
    assert len(rendered["additional_context"]) == 16
    overflow = rendered["additional_context"][15]
    assert "HOOK RESULT OVERFLOW:" in overflow
    assert "omitted=5" in overflow
    assert "overflow_sha256=" in overflow
    assert "first_omitted=context-15" in overflow


def test_cyberstrike_subprocess_records_terminal_provider(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    state_root = tmp_path / "state"
    payload = {
        "session_id": "cyberstrike-session",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
    }

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "cyberstrike",
            "--event",
            "Stop",
            "--state-root",
            str(state_root),
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
        env={
            **os.environ,
            "AGENT_HARNESS_STATE_ROOT": str(state_root),
            "BASIC_MEMORY_CHECKPOINT_DIR": str(tmp_path / "checkpoints"),
            "AGENT_HARNESS_RECALL_INDEX": str(tmp_path / "missing-index.json"),
        },
    )

    assert completed.returncode == 0, completed.stderr
    rendered = json.loads(completed.stdout)
    _assert_hook_result_matches_schema(rendered)
    terminal = [
        json.loads(line)
        for line in (state_root / "terminal.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ][-1]
    assert terminal["provider"] == "cyberstrike"
    assert terminal["event"] == "Stop"
    assert terminal["terminal"] == rendered["status"]


def test_hook_event_schema_provider_enum_includes_cyberstrike():
    provider_enum = _event_schema()["properties"]["provider"]["enum"]

    assert set(provider_enum) == {"claude", "codex", "grok", "cyberstrike"}


def test_registration_still_refuses_cyberstrike_hook_generation():
    with pytest.raises(ValueError, match="unsupported provider: cyberstrike"):
        build_hooks("cyberstrike")
