from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import harness.dispatcher as dispatcher_mod
from harness.adapters import render_output
from harness.dispatcher import HarnessDispatcher
from harness.models import HookResult
from harness.modules import build_advisory_modules, build_default_modules
from harness.workspace_index import WorkspaceIndex
from harness.workspace_integrity import WorkspaceIntegrityModule


def _pre(tmp_path: Path) -> dict[str, object]:
    return {
        "session_id": "sess-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "tool_name": "Write",
        "tool_use_id": "tool-1",
        "tool_input": {"file_path": str(tmp_path / "x.py")},
        "hook_event_name": "PreToolUse",
    }


def _terminal_records(state_root: Path) -> list[dict[str, object]]:
    log = state_root / "terminal.jsonl"
    if not log.exists():
        return []
    return [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _reservation_status(
    index: WorkspaceIndex, owner: str, operation_id: str
) -> str | None:
    import sqlite3

    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT status FROM reservations WHERE owner = ? AND operation_id = ?",
            (owner, operation_id),
        ).fetchone()
    return None if row is None else str(row[0])


def _health_status(index: WorkspaceIndex) -> str | None:
    import sqlite3

    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'health_status'"
        ).fetchone()
    return None if row is None else str(row[0])


@pytest.fixture(scope="module")
def git_exe() -> Path:
    path = shutil.which("git")
    assert path, "git executable is required"
    return Path(path).resolve(strict=True)


def _git(git_exe: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(git_exe), "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def repo_tree(tmp_path: Path, git_exe: Path) -> dict[str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(git_exe, "init", "-q", cwd=repo)
    _git(git_exe, "config", "user.email", "tests@example.com", cwd=repo)
    _git(git_exe, "config", "user.name", "Harness Tests", cwd=repo)
    (repo / "src").mkdir()
    (repo / "src" / "existing.py").write_text("old = 1\n", encoding="utf-8")
    _git(git_exe, "add", ".", cwd=repo)
    _git(git_exe, "commit", "-q", "-m", "fixture", cwd=repo)
    return {"repo": repo, "state_root": tmp_path / "state"}


def _workspace_event(repo: Path, *, tool_id: str = "tool-1") -> dict[str, object]:
    return {
        "session_id": "session-1",
        "turn_id": "turn-1",
        "cwd": str(repo),
        "tool_name": "Write",
        "tool_use_id": tool_id,
        "tool_input": {
            "file_path": str(repo / "src" / "new.py"),
            "content": "VALUE = 1\n",
        },
        "hook_event_name": "PreToolUse",
    }


class _FakeWorkspace:
    name = "workspace_integrity"
    failure_policy = "closed"

    def __init__(self) -> None:
        self.cancel_calls = 0
        self.deadlines: list[float | None] = []

    @staticmethod
    def applies(_event) -> bool:
        return True

    @staticmethod
    def failure_result(event, phase: str) -> HookResult:
        return HookResult(
            status=f"FAILED:hook-{event.event.lower()}",
            action="block",
            reason_code=f"workspace_{phase}",
            additional_context=[phase],
            continuation=None,
        )

    def set_deadline(self, deadline: float | None) -> None:
        self.deadlines.append(deadline)

    def run(self, _event) -> HookResult:
        return HookResult.success()

    def cancel_pre(self, _event) -> bool:
        self.cancel_calls += 1
        return True


def test_build_default_modules_keeps_workspace_first_and_splits_advisory(tmp_path):
    default_modules = build_default_modules(tmp_path)
    advisory_modules = build_advisory_modules(tmp_path)

    assert default_modules
    assert getattr(default_modules[0], "name", "") == "workspace_integrity"
    assert [getattr(module, "name", "") for module in default_modules[1:]] == [
        getattr(module, "name", "") for module in advisory_modules
    ]


def test_advisory_block_cancels_workspace_reservation(tmp_path, monkeypatch):
    class _BlockingAdvisory:
        name = "secret_guard"

        def run(self, _event) -> HookResult:
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["blocked later"],
            )

    workspace = _FakeWorkspace()
    monkeypatch.setattr(
        dispatcher_mod._modules, "WorkspaceIntegrityModule", _FakeWorkspace
    )
    dispatcher = HarnessDispatcher(
        modules=[workspace, _BlockingAdvisory()],
        state_root=tmp_path / "state",
    )

    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )

    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert result.additional_context == ["blocked later"]
    assert workspace.cancel_calls == 1


def test_advisory_exception_is_recorded_as_terminal_failure(tmp_path):
    class _ExplodingAdvisory:
        name = "late_guard"

        def run(self, _event) -> HookResult:
            raise RuntimeError("boom")

    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(
        modules=[_ExplodingAdvisory()],
        state_root=state_root,
    )

    result = dispatcher.dispatch(
        {"cwd": str(tmp_path), "hook_event_name": "Stop"},
        provider="codex",
        event_name="Stop",
    )

    assert result.status == "FAILED:hook-stop"
    assert result.action == "allow"
    assert result.reason_code == "internal_error"
    assert _terminal_records(state_root)[0]["failed_modules"] == ["late_guard"]


def test_non_reserving_block_does_not_attempt_workspace_cancel(tmp_path, monkeypatch):
    class _BlockingAdvisory:
        name = "secret_guard"

        def run(self, _event) -> HookResult:
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["blocked later"],
            )

    workspace = _FakeWorkspace()
    monkeypatch.setattr(
        dispatcher_mod._modules, "WorkspaceIntegrityModule", _FakeWorkspace
    )
    dispatcher = HarnessDispatcher(
        modules=[workspace, _BlockingAdvisory()],
        state_root=tmp_path / "state",
    )

    result = dispatcher.dispatch(
        {
            "session_id": "sess-1",
            "turn_id": "turn-1",
            "cwd": str(tmp_path),
            "tool_name": "WebFetch",
            "tool_use_id": "tool-1",
            "tool_input": {"url": "https://example.com"},
            "hook_event_name": "PreToolUse",
        },
        provider="codex",
        event_name="PreToolUse",
    )

    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert workspace.cancel_calls == 0


@pytest.mark.parametrize(
    ("mode", "expected_failure"),
    [
        ("false", "workspace_cancel_false"),
        ("raise", "workspace_cancel_exception"),
    ],
)
def test_cancel_failure_invalidates_reservation_and_marks_terminal_failed(
    tmp_path, mode: str, expected_failure: str, monkeypatch
):
    class _BlockingAdvisory:
        name = "secret_guard"

        def run(self, _event) -> HookResult:
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["blocked later"],
            )

    class _CancelFailWorkspace(_FakeWorkspace):
        def __init__(self) -> None:
            super().__init__()

        def cancel_pre(self, _event) -> bool:
            self.cancel_calls += 1
            if mode == "raise":
                raise RuntimeError("cancel boom")
            return False

    state_root = tmp_path / "state"
    workspace = _CancelFailWorkspace()
    monkeypatch.setattr(
        dispatcher_mod._modules,
        "WorkspaceIntegrityModule",
        _CancelFailWorkspace,
    )
    dispatcher = HarnessDispatcher(
        modules=[workspace, _BlockingAdvisory()],
        state_root=state_root,
    )

    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )

    assert result.status == "FAILED:hook-pretooluse"
    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert workspace.cancel_calls == 1
    assert expected_failure in _terminal_records(state_root)[0]["failed_modules"]


@pytest.mark.parametrize(
    ("mode", "expected_failure"),
    [
        ("false", "workspace_cancel_false"),
        ("raise", "workspace_cancel_exception"),
    ],
)
def test_cancel_failure_invalidates_real_workspace_index(
    repo_tree: dict[str, Path],
    git_exe: Path,
    mode: str,
    expected_failure: str,
    monkeypatch,
):
    class _BlockingAdvisory:
        name = "secret_guard"

        def run(self, _event) -> HookResult:
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["blocked later"],
            )

    repo = repo_tree["repo"]
    state_root = repo_tree["state_root"]
    workspace = WorkspaceIntegrityModule(
        state_root=state_root,
        git_executable=git_exe,
    )
    session_start = {
        "session_id": "session-1",
        "turn_id": "turn-0",
        "cwd": str(repo),
        "hook_event_name": "SessionStart",
        "source": "startup",
    }
    assert (
        workspace.run(
            dispatcher_mod.normalize_event(
                session_start, provider="codex", event_name="SessionStart"
            )
        ).action
        == "allow"
    )

    if mode == "raise":

        def _cancel(_event):
            raise RuntimeError("cancel boom")
    else:

        def _cancel(_event):
            return False

    workspace.cancel_pre = _cancel  # type: ignore[method-assign]
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "10000")

    dispatcher = HarnessDispatcher(
        modules=[workspace, _BlockingAdvisory()],
        state_root=state_root,
    )
    result = dispatcher.dispatch(
        _workspace_event(repo, tool_id=f"tool-{mode}"),
        provider="codex",
        event_name="PreToolUse",
    )

    assert result.status == "FAILED:hook-pretooluse"
    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert expected_failure in _terminal_records(state_root)[0]["failed_modules"]

    index = WorkspaceIndex(
        state_root=state_root,
        repo_path=repo,
        git_executable=git_exe,
    )
    assert _health_status(index) == "needs_refresh"
    assert _reservation_status(index, "codex:session-1", f"tool-{mode}") == (
        "needs_refresh"
    )


def test_budget_exhaustion_skips_later_advisory_modules(tmp_path, monkeypatch):
    calls: list[str] = []

    class _SlowAdvisory:
        name = "slow_advisory"

        def set_deadline(self, _deadline: float | None) -> None:
            pass

        def run(self, _event) -> HookResult:
            calls.append("slow")
            time.sleep(0.05)
            return HookResult.success()

    class _NeverRunAdvisory:
        name = "never_run"

        def run(self, _event) -> HookResult:
            calls.append("never")
            return HookResult.success()

    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "20")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(
        modules=[_SlowAdvisory(), _NeverRunAdvisory()],
        state_root=state_root,
    )

    result = dispatcher.dispatch(
        {"cwd": str(tmp_path), "hook_event_name": "Stop"},
        provider="codex",
        event_name="Stop",
    )

    assert result.status == "FAILED:hook-stop"
    assert calls == ["slow"]
    assert _terminal_records(state_root)[0]["failed_modules"] == ["advisory_deadline"]


def test_workspace_late_result_is_rejected_before_ingest(tmp_path, monkeypatch):
    calls: list[str] = []

    class _SlowWorkspace(_FakeWorkspace):
        def run(self, _event) -> HookResult:
            calls.append("workspace")
            time.sleep(0.05)
            return HookResult.success()

    class _NeverRunAdvisory:
        name = "never_run"

        def run(self, _event) -> HookResult:
            calls.append("advisory")
            return HookResult.success(
                action="inject",
                reason_code="lexical_recall",
                additional_context=["should not run"],
            )

    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "20")
    monkeypatch.setattr(
        dispatcher_mod._modules, "WorkspaceIntegrityModule", _SlowWorkspace
    )
    workspace = _SlowWorkspace()
    dispatcher = HarnessDispatcher(
        modules=[workspace, _NeverRunAdvisory()],
        state_root=tmp_path / "state",
    )

    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )

    assert result.status == "FAILED:hook-pretooluse"
    assert result.action == "block"
    assert result.reason_code == "workspace_deadline"
    assert calls == ["workspace"]
    assert _terminal_records(tmp_path / "state")[0]["failed_modules"] == [
        "workspace_integrity"
    ]


def test_grok_stop_inject_uses_native_additional_context():
    rendered = render_output(
        HookResult.success(action="inject", additional_context=["carry this forward"]),
        provider="grok",
        event_name="Stop",
    )
    assert rendered == {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "carry this forward",
        }
    }
