from __future__ import annotations

import ctypes
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

import harness.workspace_integrity as workspace_integrity_module
from harness.adapters import normalize_event
from harness.models import HookEvent, HookResult
from harness.workspace_index import WorkspaceIndex
from harness.workspace_integrity import WorkspaceIntegrityModule


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
    (repo / "src" / "one").mkdir(parents=True)
    (repo / "src" / "two").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "notebooks").mkdir()
    (repo / "src" / "one" / "worker.py").write_text(
        "def existing_worker():\n    return 1\n",
        encoding="utf-8",
    )
    (repo / "src" / "one" / "service.py").write_text(
        "class SharedService:\n    pass\n",
        encoding="utf-8",
    )
    (repo / "src" / "existing.py").write_text("old = 1\n", encoding="utf-8")
    (repo / "docs" / "plan-v2.md").write_text("# plan\n", encoding="utf-8")
    _git(git_exe, "add", ".", cwd=repo)
    _git(git_exe, "commit", "-q", "-m", "fixture", cwd=repo)
    _settle()

    sibling_repo = tmp_path / "sibling"
    sibling_repo.mkdir()
    _git(git_exe, "init", "-q", cwd=sibling_repo)
    (sibling_repo / "other.py").write_text("VALUE = 1\n", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    state_root = tmp_path / "state"
    return {
        "repo": repo,
        "sibling_repo": sibling_repo,
        "outside": outside,
        "state_root": state_root,
    }


def _module(repo_tree: dict[str, Path], git_exe: Path) -> WorkspaceIntegrityModule:
    return WorkspaceIntegrityModule(
        state_root=repo_tree["state_root"],
        git_executable=git_exe,
    )


def _index(repo_tree: dict[str, Path], git_exe: Path) -> WorkspaceIndex:
    return WorkspaceIndex(
        state_root=repo_tree["state_root"],
        repo_path=repo_tree["repo"],
        git_executable=git_exe,
    )


def _event(
    cwd: Path,
    *,
    event_name: str,
    tool_name: str = "",
    tool_input: Any = None,
    provider: str = "codex",
    permission_mode: str = "default",
    session_id: str = "session-1",
    tool_id: str = "tool-1",
) -> HookEvent:
    raw: dict[str, Any] = {
        "session_id": session_id,
        "turn_id": "turn-1",
        "cwd": str(cwd),
        "hook_event_name": event_name,
        "permission_mode": permission_mode,
    }
    if tool_name:
        raw["tool_name"] = tool_name
        raw["tool_input"] = tool_input
        raw["tool_id"] = tool_id
    return normalize_event(raw, provider=provider, event_name=event_name)


def _run(module: WorkspaceIntegrityModule, event: HookEvent) -> HookResult:
    result = module.run(event)
    assert isinstance(result, HookResult)
    return result


def _settle() -> None:
    time.sleep(0.5)


def _start_session(module: WorkspaceIntegrityModule, repo: Path, session_id: str = "session-1") -> None:
    result = _run(module, _event(repo, event_name="SessionStart", session_id=session_id))
    assert result.action == "allow"
    _settle()


def _reservation_status(index: WorkspaceIndex, owner: str, operation_id: str) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT status FROM reservations WHERE owner = ? AND operation_id = ?",
            (owner, operation_id),
        ).fetchone()
    return None if row is None else str(row[0])


def _assert_blocked(result: HookResult, reason_code: str) -> None:
    assert result.action == "block"
    assert result.reason_code == reason_code


def _assert_failed_unknown(result: HookResult, event_name: str) -> None:
    assert result.status == f"FAILED:hook-{event_name.lower()}"
    assert result.action == "block"
    assert result.reason_code == "workspace_integrity_unknown"


def _health_status(index: WorkspaceIndex) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'health_status'"
        ).fetchone()
    return None if row is None else str(row[0])


def _assert_stale(index: WorkspaceIndex) -> None:
    assert _health_status(index) == "needs_refresh"


def _quote_ps(value: str | Path) -> str:
    return "'" + str(value) + "'"


def _short_path(path: Path) -> Path | None:
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if result == 0:
        return None
    short = Path(buffer.value)
    if short == path:
        return None
    return short


def test_session_start_builds_missing_index(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]

    result = _run(module, _event(repo, event_name="SessionStart"))

    assert result.action == "allow", result.to_dict()
    assert _index(repo_tree, git_exe).db_path.exists()
    assert _health_status(_index(repo_tree, git_exe)) == "ok"


def test_session_start_refreshes_stale_index(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    index.invalidate(reason="test stale")
    _assert_stale(index)

    result = _run(module, _event(repo, event_name="SessionStart"))

    assert result.action == "allow"
    assert _health_status(index) == "ok"


def test_session_start_preserves_live_owner_reservations(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="reserve-1",
            tool_input={
                "file_path": str(repo / "src" / "two" / "fresh.py"),
                "content": "VALUE = 1\n",
            },
        ),
    )
    assert pre.action == "allow"
    assert _reservation_status(index, "codex:session-1", "reserve-1") == "reserved"

    result = _run(module, _event(repo, event_name="SessionStart"))

    assert result.action == "allow"
    assert _reservation_status(index, "codex:session-1", "reserve-1") == "reserved"
    assert _health_status(index) == "ok"


@pytest.mark.parametrize(
    ("target", "reason_code"),
    [
        ("src/new_write.py", "allow"),
        ("../../outside/escape.py", "workspace_target_invalid"),
    ],
)
def test_write_inside_repo_and_escape_outside(
    repo_tree: dict[str, Path],
    git_exe: Path,
    target: str,
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    event = _event(
        repo / "src" / "one",
        event_name="PreToolUse",
        tool_name="Write",
        tool_id="write-path",
        tool_input={
            "file_path": target,
            "content": "VALUE = 1\n",
        },
    )

    result = _run(module, event)

    if reason_code == "allow":
        assert result.action == "allow"
    else:
        _assert_blocked(result, reason_code)


def test_write_blocks_cross_repo_target(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    sibling_repo = repo_tree["sibling_repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="cross-repo",
            tool_input={
                "file_path": str(sibling_repo / "cross.py"),
                "content": "VALUE = 1\n",
            },
        ),
    )

    _assert_blocked(result, "workspace_target_cross_repo")


def test_apply_patch_inside_repo_allows_and_escape_blocks(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    good = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="apply_patch",
            tool_id="patch-good",
            tool_input=(
                "*** Begin Patch\n"
                "*** Add File: src/two/patch_created.py\n"
                "+VALUE = 1\n"
                "*** End Patch\n"
            ),
        ),
    )
    bad = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="apply_patch",
            tool_id="patch-bad",
            tool_input=(
                "*** Begin Patch\n"
                "*** Add File: ../../outside/escape.py\n"
                "+VALUE = 1\n"
                "*** End Patch\n"
            ),
        ),
    )

    assert good.action == "allow"
    _assert_blocked(bad, "workspace_target_invalid")


@pytest.mark.parametrize(
    ("relative_path", "content", "reason_code"),
    [
        ("docs/plan-v3.md", "# next\n", "workspace_doc_family_conflict"),
        (
            "src/two/worker.py",
            "def another_worker():\n    return 2\n",
            "workspace_source_basename_conflict",
        ),
        (
            "src/two/alt_service.py",
            "class SharedService:\n    pass\n",
            "workspace_primary_symbol_conflict",
        ),
        (
            "newtop/fresh.py",
            "VALUE = 3\n",
            "workspace_top_level_slop",
        ),
    ],
)
def test_duplicate_and_slop_conflicts_block(
    repo_tree: dict[str, Path],
    git_exe: Path,
    relative_path: str,
    content: str,
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id=f"dup-{relative_path}",
            tool_input={
                "file_path": str(repo / relative_path),
                "content": content,
            },
        ),
    )

    _assert_blocked(result, reason_code)


def test_notebook_edit_is_hard_blocked(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="NotebookEdit",
            tool_id="nb-1",
            tool_input={"notebook_path": str(repo / "notebooks" / "analysis.ipynb")},
        ),
    )

    _assert_blocked(result, "workspace_notebook_edit_blocked")


@pytest.mark.parametrize(
    ("session_id", "tool_id", "reason_code"),
    [
        ("unknown", "tool-1", "workspace_session_unidentified"),
        ("session-1", "", "workspace_tool_id_missing"),
    ],
)
def test_pre_requires_identified_session_and_tool_id(
    repo_tree: dict[str, Path],
    git_exe: Path,
    session_id: str,
    tool_id: str,
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id=tool_id,
            session_id=session_id,
            tool_input={
                "file_path": str(repo / "src" / "two" / "ids.py"),
                "content": "VALUE = 1\n",
            },
        ),
    )

    _assert_blocked(result, reason_code)


def test_cancel_pre_resolves_reservation(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    event = _event(
        repo,
        event_name="PreToolUse",
        tool_name="Write",
        tool_id="cancel-1",
        tool_input={
            "file_path": str(repo / "src" / "two" / "cancelled.py"),
            "content": "VALUE = 1\n",
        },
    )
    pre = _run(module, event)
    assert pre.action == "allow"
    assert _reservation_status(index, "codex:session-1", "cancel-1") == "reserved"

    assert module.cancel_pre(event) is True
    assert _reservation_status(index, "codex:session-1", "cancel-1") == "resolved"

    replay = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="cancel-2",
            tool_input={
                "file_path": str(repo / "src" / "two" / "cancelled.py"),
                "content": "VALUE = 1\n",
            },
        ),
    )
    assert replay.action == "allow"
    assert _reservation_status(index, "codex:session-1", "cancel-2") == "reserved"

    same_id_replay = _run(module, event)
    _assert_blocked(same_id_replay, "workspace_replay_blocked")


def test_post_success_finalizes_reservation(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    target = repo / "src" / "two" / "finalized.py"
    content = "VALUE = 7\n"
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="finalize-1",
            tool_input={"file_path": str(target), "content": content},
        ),
    )
    assert pre.action == "allow"
    target.write_bytes(content.encode("utf-8"))
    _settle()

    post = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="finalize-1",
            tool_input={"file_path": str(target), "content": content},
        ),
    )

    assert post.action == "allow"
    assert _reservation_status(index, "codex:session-1", "finalize-1") == "completed"
    assert _health_status(index) == "ok"


def test_post_finalize_false_is_unknown_without_structured_index_outcome(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    target = repo / "src" / "two" / "mismatch.py"
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="mismatch-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )
    assert pre.action == "allow"
    target.write_bytes(b"VALUE = 2\n")
    _settle()

    post = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="mismatch-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )

    _assert_failed_unknown(post, "PostToolUse")
    _assert_stale(index)


def test_post_structured_invalidated_outcome_is_allowed(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    class FakeIndex:
        def finalize_success(self, *, owner: str, operation_id: str) -> dict[str, str]:
            return {"status": "invalidated"}

    monkeypatch.setattr(module, "_index_for_event", lambda *args, **kwargs: FakeIndex())
    result = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="structured-invalidated",
            tool_input={"file_path": str(repo / "src" / "two" / "fake.py"), "content": "VALUE = 1\n"},
        ),
    )

    assert result.action == "allow"


def test_post_failure_marks_needs_refresh(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    target = repo / "src" / "two" / "failed.py"
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="failed-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )
    assert pre.action == "allow"

    post = _run(
        module,
        _event(
            repo,
            event_name="PostToolUseFailure",
            tool_name="Write",
            tool_id="failed-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )

    assert post.action == "allow"
    _assert_stale(index)


def test_permission_denied_resolves_without_staling_index(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    target = repo / "src" / "two" / "denied.py"
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="denied-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )
    assert pre.action == "allow"

    post = _run(
        module,
        _event(
            repo,
            event_name="PermissionDenied",
            tool_name="Write",
            tool_id="denied-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )

    assert post.action == "allow"
    assert _reservation_status(index, "codex:session-1", "denied-1") == "resolved"
    assert _health_status(index) == "ok"


def test_duplicate_post_success_is_idempotent_and_preserves_sibling_reservation(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    completed_target = repo / "src" / "two" / "dup_complete.py"
    sibling_target = repo / "src" / "two" / "dup_sibling.py"

    first = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="dup-complete",
            tool_input={"file_path": str(completed_target), "content": "VALUE = 1\n"},
        ),
    )
    second = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="dup-sibling",
            tool_input={"file_path": str(sibling_target), "content": "VALUE = 2\n"},
        ),
    )
    assert first.action == "allow"
    assert second.action == "allow"
    completed_target.write_bytes(b"VALUE = 1\n")
    _settle()

    post = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="dup-complete",
            tool_input={"file_path": str(completed_target), "content": "VALUE = 1\n"},
        ),
    )
    replay = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="dup-complete",
            tool_input={"file_path": str(completed_target), "content": "VALUE = 1\n"},
        ),
    )

    assert post.action == "allow"
    assert replay.action == "allow"
    assert _reservation_status(index, "codex:session-1", "dup-complete") == "completed"
    assert _reservation_status(index, "codex:session-1", "dup-sibling") == "reserved"


def test_post_missing_tool_id_returns_failed_unknown_and_preserves_siblings(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    index = _index(repo_tree, git_exe)
    _start_session(module, repo)
    target = repo / "src" / "two" / "unknown_id.py"
    sibling = repo / "src" / "two" / "still_reserved.py"
    first = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="unknown-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )
    second = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="unknown-2",
            tool_input={"file_path": str(sibling), "content": "VALUE = 2\n"},
        ),
    )
    assert first.action == "allow"
    assert second.action == "allow"

    result = _run(
        module,
        _event(
            repo,
            event_name="PostToolUse",
            tool_name="Write",
            tool_id="",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )

    _assert_failed_unknown(result, "PostToolUse")
    assert _reservation_status(index, "codex:session-1", "unknown-1") == "reserved"
    assert _reservation_status(index, "codex:session-1", "unknown-2") == "reserved"
    assert _health_status(index) == "ok"


def test_post_index_construction_failure_returns_failed_unknown(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    target = repo / "src" / "two" / "broken_post.py"
    _start_session(module, repo)
    pre = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="broken-post-1",
            tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
        ),
    )
    assert pre.action == "allow"

    real_class = workspace_integrity_module.WorkspaceIndex

    class BrokenIndex:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise workspace_integrity_module.WorkspaceIndexFailure(
                "workspace_index_busy",
                "busy",
            )

    monkeypatch.setattr(workspace_integrity_module, "WorkspaceIndex", BrokenIndex)
    try:
        result = _run(
            module,
            _event(
                repo,
                event_name="PostToolUse",
                tool_name="Write",
                tool_id="broken-post-1",
                tool_input={"file_path": str(target), "content": "VALUE = 1\n"},
            ),
        )
    finally:
        monkeypatch.setattr(workspace_integrity_module, "WorkspaceIndex", real_class)

    _assert_failed_unknown(result, "PostToolUse")


def test_deadline_is_propagated_into_repo_discovery(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    module.set_deadline(time.monotonic() - 0.01)

    result = _run(module, _event(repo, event_name="SessionStart"))

    assert result.status == "FAILED:hook-sessionstart"
    assert result.reason_code == "workspace_index_deadline"


def test_deadline_can_expire_during_shell_parsing(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    original = module._shell_command

    def expire_then_return(payload: dict[str, Any]) -> str:
        module.set_deadline(time.monotonic() - 0.01)
        return original(payload)

    monkeypatch.setattr(module, "_shell_command", expire_then_return)
    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="deadline-shell",
            permission_mode="workspace-write",
            tool_input={
                "cmd": (
                    f"& {_quote_ps(module.git_executable)} "
                    "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                    "status --short --branch --untracked-files=all"
                )
            },
        ),
    )

    assert result.status == "FAILED:hook-pretooluse"
    assert result.reason_code == "workspace_index_deadline"


def test_deadline_can_expire_during_mutation_planning(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    original = module._planning_resolve_target

    def expire_then_resolve(raw_target: str, base_dir: Path, repo_root: Path):
        module.set_deadline(time.monotonic() - 0.01)
        return original(raw_target, base_dir, repo_root)

    monkeypatch.setattr(module, "_planning_resolve_target", expire_then_resolve)
    result = _run(
        module,
        _event(
            repo / "src",
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="deadline-write",
            tool_input={
                "file_path": "two/deadline.py",
                "content": "VALUE = 1\n",
            },
        ),
    )

    assert result.status == "FAILED:hook-pretooluse"
    assert result.reason_code == "workspace_index_deadline"


@pytest.mark.parametrize(
    ("tool_name", "provider", "permission_mode", "cwd_key", "reason_code"),
    [
        ("PowerShell", "codex", "workspace-write", "repo", "allow"),
        ("Bash", "codex", "workspace-write", "repo", "workspace_shell_transport"),
        ("PowerShell", "claude", "workspace-write", "repo", "workspace_shell_provider"),
        ("PowerShell", "codex", "danger-full-access", "repo", "workspace_shell_permission"),
        ("PowerShell", "codex", "workspace-write", "outside", "workspace_repo_unavailable"),
    ],
)
def test_shell_transport_and_repo_gates(
    repo_tree: dict[str, Path],
    git_exe: Path,
    tool_name: str,
    provider: str,
    permission_mode: str,
    cwd_key: str,
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    cwd = repo_tree[cwd_key]
    repo = repo_tree["repo"]
    _start_session(module, repo)
    command = (
        f"& {_quote_ps(module.git_executable)} "
        "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
        "status --short --branch --untracked-files=all"
    )

    result = _run(
        module,
        _event(
            cwd,
            event_name="PreToolUse",
            tool_name=tool_name,
            tool_id=f"shell-gate-{tool_name}-{provider}-{permission_mode}-{cwd_key}",
            provider=provider,
            permission_mode=permission_mode,
            tool_input={"cmd": command},
        ),
    )

    if reason_code == "allow":
        assert result.action == "allow"
    else:
        _assert_blocked(result, reason_code)


@pytest.mark.parametrize(
    "tool_input",
    [
        {
            "cmd": "",
            "workdir": "src",
        },
        {
            "cmd": (
                "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                "status --short --branch --untracked-files=all"
            ),
            "login": True,
        },
        {
            "workdir": "src",
        },
        {
            "cmd": (
                "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                "status --short --branch --untracked-files=all"
            ),
            "sandbox_permissions": [],
        },
        {
            "cmd": (
                "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                "status --short --branch --untracked-files=all"
            ),
            "additional_permissions": [],
        },
        {
            "cmd": (
                "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                "status --short --branch --untracked-files=all"
            ),
            "justification": {},
        },
        {
            "cmd": (
                "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                "status --short --branch --untracked-files=all"
            ),
            "prefix_rule": "git",
        },
    ],
)
def test_shell_blocks_malformed_payload(
    repo_tree: dict[str, Path],
    git_exe: Path,
    tool_input: dict[str, Any],
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-invalid",
            permission_mode="workspace-write",
            tool_input=tool_input,
        ),
    )

    _assert_blocked(result, "workspace_shell_invalid")


@pytest.mark.parametrize(
    ("tool_input", "reason_code"),
    [
        (
            {
                "cmd": (
                    "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                    "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                    "status --short --branch --untracked-files=all"
                ),
                "sandbox_permissions": "require_escalated",
            },
            "workspace_shell_permission",
        ),
        (
            {
                "cmd": (
                    "& 'C:\\Program Files\\Git\\cmd\\git.exe' "
                    "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
                    "status --short --branch --untracked-files=all"
                ),
                "additional_permissions": {"file_system": {"write": ["x"]}},
            },
            "workspace_shell_permission",
        ),
    ],
)
def test_shell_blocks_permission_overrides(
    repo_tree: dict[str, Path],
    git_exe: Path,
    tool_input: dict[str, Any],
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-permission-override",
            permission_mode="workspace-write",
            tool_input=tool_input,
        ),
    )

    _assert_blocked(result, reason_code)


def test_shell_blocks_escalation_and_filesystem_override(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    command = (
        f"& {_quote_ps(module.git_executable)} "
        "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
        "status --short --branch --untracked-files=all"
    )
    for tool_id, tool_input in [
        (
            "shell-escalated",
            {"cmd": command, "sandbox_permissions": "require_escalated"},
        ),
        (
            "shell-override",
            {"cmd": command, "additional_permissions": {"file_system": {"write": [str(repo / 'tmp')]}}},
        ),
    ]:
        result = _run(
            module,
            _event(
                repo,
                event_name="PreToolUse",
                tool_name="PowerShell",
                tool_id=tool_id,
                permission_mode="workspace-write",
                tool_input=tool_input,
            ),
        )
        _assert_blocked(result, "workspace_shell_permission")


def test_shell_exact_allowlist_accepts_git_rg_and_certutil(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    commands = [
        (
            "git",
            f"& {_quote_ps(module.git_executable)} "
            "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
            "status --short --branch --untracked-files=all",
        ),
        (
            "rg",
            f"& {_quote_ps(module.rg_executable)} "
            f"--no-config --files -- {_quote_ps(repo / 'src')}",
        ),
        (
            "certutil",
            f"& {_quote_ps(module.certutil_executable)} "
            f"-hashfile {_quote_ps(repo / 'src' / 'existing.py')} SHA256",
        ),
    ]
    for index, (_label, command) in enumerate(commands, start=1):
        result = _run(
            module,
            _event(
                repo,
                event_name="PreToolUse",
                tool_name="PowerShell",
                tool_id=f"shell-allow-{index}",
                permission_mode="workspace-write",
                tool_input={"cmd": command},
            ),
        )
        assert result.action == "allow"


def test_shell_blocks_other_repo_workdir_but_allows_short_alias_same_repo(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    sibling_repo = repo_tree["sibling_repo"]
    _start_session(module, repo)
    command = (
        f"& {_quote_ps(module.git_executable)} "
        "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
        "status --short --branch --untracked-files=all"
    )

    blocked = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-other-repo-workdir",
            permission_mode="workspace-write",
            tool_input={"cmd": command, "workdir": str(sibling_repo)},
        ),
    )

    _assert_blocked(blocked, "workspace_shell_workdir_repo")

    short_repo = _short_path(repo)
    if short_repo is None:
        pytest.skip("8.3 short-path aliases are unavailable on this volume")
    allowed = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-short-workdir",
            permission_mode="workspace-write",
            tool_input={"cmd": command, "workdir": str(short_repo)},
        ),
    )

    assert allowed.action == "allow"


def test_shell_rejects_repo_local_fake_rg_from_path(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = repo_tree["repo"]
    fake_rg = repo / "rg.exe"
    fake_rg.write_bytes(b"fake")
    monkeypatch.setenv("PATH", str(repo) + os.pathsep + os.environ["PATH"])
    module = WorkspaceIntegrityModule(
        state_root=repo_tree["state_root"],
        git_executable=git_exe,
    )
    _start_session(module, repo)
    command = (
        f"& {_quote_ps(fake_rg)} "
        f"--no-config --files -- {_quote_ps(repo / 'src')}"
    )

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-fake-rg",
            permission_mode="workspace-write",
            tool_input={"cmd": command},
        ),
    )

    _assert_blocked(result, "workspace_shell_unverified")


@pytest.mark.parametrize(
    ("command", "reason_code"),
    [
        (
            "& 'C:\\Program Files\\Git\\cmd\\git.exe'\n--no-pager",
            "workspace_shell_invalid",
        ),
        (
            "& 'C:\\Program Files\\Git\\cmd\\git.exe'\u0085--no-pager",
            "workspace_shell_invalid",
        ),
        (
            "& 'C:\\Program Files\\Git\\cmd\\git.exe'\u2028--no-pager",
            "workspace_shell_invalid",
        ),
        (
            "& 'C:\\Program Files\\Git\\cmd\\git.exe' --no-pager --no-optional-locks -c color.ui=never --literal-pathspecs & status",
            "workspace_shell_unverified",
        ),
    ],
)
def test_shell_rejects_control_separators_and_second_call_operator(
    repo_tree: dict[str, Path],
    git_exe: Path,
    command: str,
    reason_code: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id="shell-control",
            permission_mode="workspace-write",
            tool_input={"cmd": command},
        ),
    )

    _assert_blocked(result, reason_code)


def test_write_blocks_reserved_superscript_device_alias(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="reserved-superscript",
            tool_input={
                "file_path": str(repo / "src" / "COM¹.txt"),
                "content": "VALUE = 1\n",
            },
        ),
    )

    _assert_blocked(result, "workspace_target_invalid")


def test_write_blocks_oversized_payload(repo_tree: dict[str, Path], git_exe: Path) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    _start_session(module, repo)
    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="Write",
            tool_id="oversized-payload",
            tool_input={
                "file_path": str(repo / "src" / "two" / "oversized.py"),
                "content": "A" * 1_000_100,
            },
        ),
    )

    _assert_blocked(result, "workspace_op_limit")


@pytest.mark.parametrize(
    "command",
    [
        "contains-dollar",
        "rg-pre",
        "git-output",
        "pytest",
        "ruff",
    ],
)
def test_shell_blocks_unverified_bypass_commands(
    repo_tree: dict[str, Path],
    git_exe: Path,
    command: str,
) -> None:
    module = _module(repo_tree, git_exe)
    repo = repo_tree["repo"]
    pytest_exe = shutil.which("pytest")
    ruff_exe = shutil.which("ruff")
    _start_session(module, repo)

    if command == "contains-dollar":
        raw = (
            f"& {_quote_ps(module.git_executable)} "
            "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
            "status --short --branch --untracked-files=all $(whoami)"
        )
    elif command == "rg-pre":
        raw = (
            f"& {_quote_ps(module.rg_executable)} "
            f"--no-config --line-number --no-heading --color=never --pre preproc --regexp 'worker' -- {_quote_ps(repo / 'src')}"
        )
    elif command == "git-output":
        raw = (
            f"& {_quote_ps(module.git_executable)} "
            "--no-pager --no-optional-locks -c color.ui=never --literal-pathspecs "
            f"diff --no-ext-diff --no-textconv --stat --output out.txt -- {_quote_ps(repo / 'src')}"
        )
    elif command == "pytest":
        assert pytest_exe, "pytest executable is required"
        raw = f"& {_quote_ps(pytest_exe)} -p no:cacheprovider {_quote_ps(repo / 'src')}"
    else:
        assert ruff_exe, "ruff executable is required"
        raw = f"& {_quote_ps(ruff_exe)} --output-file out.txt"

    result = _run(
        module,
        _event(
            repo,
            event_name="PreToolUse",
            tool_name="PowerShell",
            tool_id=f"shell-bypass-{command}",
            permission_mode="workspace-write",
            tool_input={"cmd": raw},
        ),
    )

    _assert_blocked(result, "workspace_shell_unverified")


# UNIT-COMPLETE: workspace-integrity-tdd
