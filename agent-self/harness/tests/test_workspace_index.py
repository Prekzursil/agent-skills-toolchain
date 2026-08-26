from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from harness.workspace_index import (
    ASSERT_FRESH_DEADLINE_SEC,
    MAX_OP_DIRS,
    MAX_OP_FILES,
    MAX_PLAN_POSTIMAGE_BYTES,
    MAX_POSTIMAGE_BYTES,
    MAX_RELEVANT_FILE_BYTES,
    MAX_SESSION_FILES,
    MutationOp,
    MutationPlan,
    WorkspaceIndex,
    WorkspaceIndexFailure,
    resolve_repo_identity,
)


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
    _git(git_exe, "init", cwd=repo)
    _git(git_exe, "config", "user.email", "tests@example.com", cwd=repo)
    _git(git_exe, "config", "user.name", "Harness Tests", cwd=repo)
    (repo / "src" / "one").mkdir(parents=True)
    (repo / "src" / "two").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "src" / "one" / "worker.py").write_text(
        "def alpha():\n    return 1\n\nasync def beta():\n    return 2\n\nclass SharedService:\n    pass\n",
        encoding="utf-8",
    )
    (repo / "src" / "one" / "service.py").write_text(
        "class ExistingService:\n    pass\n",
        encoding="utf-8",
    )
    (repo / "docs" / "plan-v2.md").write_text("# plan\n", encoding="utf-8")
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(git_exe, "add", ".", cwd=repo)
    _git(git_exe, "commit", "-m", "fixture", cwd=repo)
    return {"repo": repo, "state_root": tmp_path / "state"}


def _index(repo_tree: dict[str, Path], git_exe: Path) -> WorkspaceIndex:
    return WorkspaceIndex(
        state_root=repo_tree["state_root"],
        repo_path=repo_tree["repo"],
        git_executable=git_exe,
    )


def _plan(owner: str, operation_id: str, *ops: MutationOp) -> MutationPlan:
    return MutationPlan(owner=owner, operation_id=operation_id, operations=tuple(ops))


def _reserve_in_child(index: WorkspaceIndex, git_exe: Path, plan: MutationPlan) -> None:
    script = """
import json
import os
import sys
sys.path.insert(0, os.environ["AGENT_SELF_ROOT"])
from harness.workspace_index import MutationOp, MutationPlan, WorkspaceIndex

payload = json.loads(os.environ["PLAN_JSON"])
index = WorkspaceIndex(
    state_root=os.environ["STATE_ROOT"],
    repo_path=os.environ["REPO_ROOT"],
    git_executable=os.environ["GIT_EXE"],
)
plan = MutationPlan(
    owner=payload["owner"],
    operation_id=payload["operation_id"],
    operations=tuple(MutationOp(**item) for item in payload["operations"]),
)
print(index.reserve(plan).status)
"""
    env = os.environ.copy()
    env["AGENT_SELF_ROOT"] = str(Path(__file__).resolve().parents[2])
    env["STATE_ROOT"] = str(index.state_root)
    env["REPO_ROOT"] = str(index.repo.repo_root)
    env["GIT_EXE"] = str(git_exe)
    env["PLAN_JSON"] = __import__("json").dumps(
        {
            "owner": plan.owner,
            "operation_id": plan.operation_id,
            "operations": [
                {
                    "kind": op.kind,
                    "path": op.path,
                    "postimage": op.postimage,
                    "source_path": op.source_path,
                }
                for op in plan.operations
            ],
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert completed.stdout.strip() == "reserved"


def _hold_db_lock(
    index: WorkspaceIndex, ready: Path, release: Path
) -> subprocess.Popen[str]:
    script = """
import os
import sqlite3
import time
conn = sqlite3.connect(os.environ["DB_PATH"], timeout=0, isolation_level=None)
conn.execute("BEGIN IMMEDIATE")
with open(os.environ["READY_PATH"], "w", encoding="utf-8") as fh:
    fh.write("ready")
while not os.path.exists(os.environ["RELEASE_PATH"]):
    time.sleep(0.05)
conn.rollback()
conn.close()
"""
    env = os.environ.copy()
    env["DB_PATH"] = str(index.db_path)
    env["READY_PATH"] = str(ready)
    env["RELEASE_PATH"] = str(release)
    return subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _create_hardlink_or_skip(source: Path, link_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, link_path)
    except (AttributeError, NotImplementedError, OSError) as exc:
        pytest.skip(f"hardlink creation unavailable: {exc}")


def _init_legacy_identity_schema(index: WorkspaceIndex) -> None:
    index.root.mkdir(parents=True, exist_ok=True)
    if index.db_path.exists():
        index.db_path.unlink()
    with sqlite3.connect(index.db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE watch_entries(
                path TEXT PRIMARY KEY,
                entry_kind TEXT NOT NULL,
                top_level TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                ctime_ns INTEGER NOT NULL,
                size INTEGER,
                inode INTEGER NOT NULL,
                device INTEGER NOT NULL,
                child_count INTEGER,
                child_signature TEXT
            );
            CREATE TABLE directories(
                path TEXT PRIMARY KEY,
                top_level TEXT NOT NULL
            );
            CREATE TABLE files(
                path TEXT PRIMARY KEY,
                dir_path TEXT NOT NULL,
                basename TEXT NOT NULL,
                top_level TEXT NOT NULL,
                kind TEXT NOT NULL
            );
            CREATE TABLE doc_families(
                family TEXT NOT NULL,
                path TEXT NOT NULL,
                PRIMARY KEY(family, path)
            );
            CREATE TABLE source_basenames(
                basename TEXT NOT NULL,
                path TEXT NOT NULL,
                PRIMARY KEY(basename, path)
            );
            CREATE TABLE symbols(
                symbol TEXT NOT NULL,
                path TEXT NOT NULL,
                PRIMARY KEY(symbol, path)
            );
            CREATE TABLE reservations(
                owner TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                postimage_hash TEXT NOT NULL,
                generation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                PRIMARY KEY(owner, operation_id)
            );
            CREATE TABLE reservation_claims(
                owner TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                claim_kind TEXT NOT NULL,
                claim_key TEXT NOT NULL,
                claim_path TEXT NOT NULL,
                PRIMARY KEY(owner, operation_id, claim_kind, claim_key),
                FOREIGN KEY(owner, operation_id) REFERENCES reservations(owner, operation_id) ON DELETE CASCADE
            );
            CREATE INDEX reservation_claim_lookup ON reservation_claims(claim_kind, claim_key);
            """
        )
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            [
                ("schema_version", "2"),
                ("repo_root", str(index.repo.repo_root)),
                ("git_dir", str(index.repo.git_dir)),
                ("common_dir", str(index.repo.common_dir)),
                ("refreshed_at", "legacy"),
                ("generation", "legacy"),
                ("health_status", "ok"),
                ("health_reason", ""),
                ("health_updated_at", "legacy"),
            ],
        )
        conn.commit()


def _watch_identity_row(index: WorkspaceIndex, path: str) -> sqlite3.Row:
    with sqlite3.connect(index.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                path,
                device,
                inode,
                typeof(device) AS device_type,
                typeof(inode) AS inode_type
            FROM watch_entries
            WHERE path = ?
            """,
            (path,),
        ).fetchone()
    assert row is not None
    return row


def _watch_schema_types(index: WorkspaceIndex) -> dict[str, str]:
    with sqlite3.connect(index.db_path) as conn:
        conn.row_factory = sqlite3.Row
        return {
            str(row["name"]): str(row["type"]).upper()
            for row in conn.execute("PRAGMA table_info(watch_entries)").fetchall()
        }


def _reservation_status(
    index: WorkspaceIndex, owner: str, operation_id: str
) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT status FROM reservations WHERE owner = ? AND operation_id = ?",
            (owner, operation_id),
        ).fetchone()
    return None if row is None else str(row[0])


def _reservation_generation(
    index: WorkspaceIndex, owner: str, operation_id: str
) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT generation FROM reservations WHERE owner = ? AND operation_id = ?",
            (owner, operation_id),
        ).fetchone()
    return None if row is None else str(row[0])


def _meta_value(index: WorkspaceIndex, key: str) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row[0])


def _reservation_plan_json(
    index: WorkspaceIndex, owner: str, operation_id: str
) -> str | None:
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT plan_json FROM reservations WHERE owner = ? AND operation_id = ?",
            (owner, operation_id),
        ).fetchone()
    return None if row is None else str(row[0])


def test_fake_dot_git_directory_fails_but_real_repo_resolves(
    tmp_path: Path,
    git_exe: Path,
) -> None:
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / ".git").mkdir()
    with pytest.raises(WorkspaceIndexFailure, match="git"):
        resolve_repo_identity(fake, git_executable=git_exe)

    real = tmp_path / "real"
    real.mkdir()
    _git(git_exe, "init", cwd=real)
    identity = resolve_repo_identity(real, git_executable=git_exe)
    assert identity.repo_root == real.resolve()


def test_real_worktree_repo_is_supported(tmp_path: Path, git_exe: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(git_exe, "init", cwd=repo)
    _git(git_exe, "config", "user.email", "tests@example.com", cwd=repo)
    _git(git_exe, "config", "user.name", "Harness Tests", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(git_exe, "add", ".", cwd=repo)
    _git(git_exe, "commit", "-m", "base", cwd=repo)
    worktree = tmp_path / "worktree"
    _git(git_exe, "worktree", "add", str(worktree), cwd=repo)

    identity = resolve_repo_identity(worktree, git_executable=git_exe)
    assert identity.repo_root == worktree.resolve()
    assert identity.common_dir.name == ".git"


def test_resolve_repo_identity_caps_git_timeout_to_deadline(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_timeouts: list[float] = []
    anchor = repo_tree["repo"].resolve()
    git_dir = (repo_tree["repo"] / ".git").resolve()

    def tracked_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        timeout = kwargs.get("timeout")
        if timeout is not None:
            seen_timeouts.append(float(timeout))
        time.sleep(0.02)
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout=(f"{anchor}\n{git_dir}\n{git_dir}\ntrue\n"),
            stderr="",
        )

    monkeypatch.setattr("harness.workspace_index.subprocess.run", tracked_run)
    deadline = time.monotonic() + 0.5

    identity = resolve_repo_identity(
        repo_tree["repo"],
        git_executable=git_exe,
        deadline_monotonic=deadline,
    )

    assert identity.repo_root == repo_tree["repo"].resolve()
    assert seen_timeouts
    assert all(0 < timeout <= 0.5 for timeout in seen_timeouts)


def test_trusted_git_discovery_timeout_maps_to_deadline(
    repo_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_commands: list[str] = []

    def tracked_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = str(args[0][0])
        seen_commands.append(command)
        if command.lower() == "where.exe":
            raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))
        raise AssertionError("git rev-parse should not run after where.exe timeout")

    monkeypatch.setattr("harness.workspace_index.subprocess.run", tracked_run)

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        resolve_repo_identity(
            repo_tree["repo"],
            deadline_monotonic=time.monotonic() + 0.1,
        )
    assert excinfo.value.code == "workspace_index_deadline"
    assert seen_commands == ["where.exe"]


def test_refresh_indexes_all_top_level_symbols_not_just_first(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    receipt = index.refresh()
    assert receipt.symbol_count >= 3
    with sqlite3.connect(index.db_path) as conn:
        rows = conn.execute(
            "SELECT symbol FROM symbols WHERE path = ? ORDER BY symbol",
            ("src/one/worker.py",),
        ).fetchall()
    assert [row[0] for row in rows] == ["SharedService", "alpha", "beta"]


def test_same_size_restored_mtime_mutation_and_known_change_both_trip_freshness(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    worker = repo_tree["repo"] / "src" / "one" / "worker.py"
    original = worker.stat()
    worker.write_text(
        "def omega():\n    return 1\n\nasync def beta():\n    return 2\n\nclass SharedService:\n    pass\n",
        encoding="utf-8",
    )
    os.utime(worker, ns=(original.st_atime_ns, original.st_mtime_ns))
    with pytest.raises(WorkspaceIndexFailure) as same_size_exc:
        index.assert_fresh()
    assert same_size_exc.value.code == "workspace_index_stale"

    index.refresh()
    (repo_tree["repo"] / "src" / "two" / "fresh.py").write_text(
        "class Fresh:\n    pass\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceIndexFailure) as control_exc:
        index.assert_fresh()
    assert control_exc.value.code == "workspace_index_stale"


def test_assert_fresh_and_reserve_do_not_rewalk_repo(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()

    def forbidden_walk(*args, **kwargs):
        raise AssertionError("os.walk must not be used after refresh")

    monkeypatch.setattr("harness.workspace_index.os.walk", forbidden_walk)
    started = time.perf_counter()
    index.assert_fresh()
    assert time.perf_counter() - started < ASSERT_FRESH_DEADLINE_SEC
    result = index.reserve(
        _plan(
            "owner-a",
            "op-a",
            MutationOp(
                kind="add",
                path="src/two/new.py",
                postimage="class NewThing:\n    pass\n",
            ),
        )
    )
    assert result.status == "reserved"
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-b",
                "op-b",
                MutationOp(
                    kind="add",
                    path="scratch/new.py",
                    postimage="class Slop:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_top_level_slop"


def test_public_lifecycle_methods_respect_instance_deadline(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.deadline_monotonic = time.monotonic() - 0.01

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.assert_fresh()
    assert excinfo.value.code == "workspace_index_deadline"


def test_absolute_deadline_overrides_soft_freshness_cutoff(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.deadline_monotonic = time.monotonic() + 30
    monkeypatch.setattr("harness.workspace_index.ASSERT_FRESH_DEADLINE_SEC", 0.0)
    index.assert_fresh()


def test_soft_freshness_cutoff_still_applies_without_absolute_deadline(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    monkeypatch.setattr("harness.workspace_index.ASSERT_FRESH_DEADLINE_SEC", 0.0)

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.assert_fresh()
    assert excinfo.value.code == "workspace_index_deadline"


def test_refresh_propagates_deadline_to_repo_traversal(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_index = __import__("harness.workspace_index", fromlist=["_iter_repo"])
    real_iter_repo = workspace_index._iter_repo

    def sleepy_iter_repo(
        repo_root: Path,
        *,
        deadline_monotonic: float | None = None,
    ) -> Any:
        assert deadline_monotonic is not None
        time.sleep(0.05)
        if time.monotonic() >= deadline_monotonic:
            raise WorkspaceIndexFailure(
                "workspace_index_deadline",
                "deadline exceeded during repo traversal",
            )
        yield from real_iter_repo(repo_root, deadline_monotonic=deadline_monotonic)

    monkeypatch.setattr("harness.workspace_index._iter_repo", sleepy_iter_repo)

    index = _index(repo_tree, git_exe)
    index.deadline_monotonic = time.monotonic() + 0.01
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.refresh()
    assert excinfo.value.code == "workspace_index_deadline"


def test_cross_process_reservation_blocks_same_path(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    _reserve_in_child(
        index,
        git_exe,
        _plan(
            "owner-a",
            "op-a",
            MutationOp(
                kind="add",
                path="src/two/claimed.py",
                postimage="class ChildClaim:\n    pass\n",
            ),
        ),
    )
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-b",
                "op-b",
                MutationOp(
                    kind="add",
                    path="src/two/claimed.py",
                    postimage="class MainClaim:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_path_conflict"


def test_cross_process_reservation_blocks_same_symbol_on_different_path(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    _reserve_in_child(
        index,
        git_exe,
        _plan(
            "owner-a",
            "op-a",
            MutationOp(
                kind="add",
                path="src/two/first.py",
                postimage="class SharedFuture:\n    pass\n",
            ),
        ),
    )
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-b",
                "op-b",
                MutationOp(
                    kind="add",
                    path="src/two/second.py",
                    postimage="class SharedFuture:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_primary_symbol_conflict"


def test_exact_retry_is_idempotent_but_hash_mismatch_fails(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    plan = _plan(
        "owner-a",
        "op-a",
        MutationOp(
            kind="add",
            path="src/two/retry.py",
            postimage="class Retryable:\n    pass\n",
        ),
    )
    first = index.reserve(plan)
    second = index.reserve(plan)
    assert first.status == "reserved"
    assert second.status == "idempotent"

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-a",
                "op-a",
                MutationOp(
                    kind="add",
                    path="src/two/retry.py",
                    postimage="class RetryableChanged:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_retry_mismatch"


def test_resolve_replay_is_idempotent_and_preserves_same_owner_siblings(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "resolve-a",
            MutationOp(
                kind="add",
                path="src/two/resolve-a.py",
                postimage="class ResolveA:\n    pass\n",
            ),
        )
    )
    sibling = index.reserve(
        _plan(
            "owner-a",
            "resolve-b",
            MutationOp(
                kind="add",
                path="src/two/resolve-b.py",
                postimage="class ResolveB:\n    pass\n",
            ),
        )
    )
    assert sibling.status == "reserved"
    assert index.resolve(owner="owner-a", operation_id="resolve-a")
    assert _reservation_status(index, "owner-a", "resolve-b") == "reserved"
    assert index.resolve(owner="owner-a", operation_id="resolve-a")
    assert _reservation_status(index, "owner-a", "resolve-b") == "reserved"
    assert index.resolve(owner="owner-a", operation_id="resolve-b")


def test_shared_new_directory_claim_is_deduped(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    result = index.reserve(
        _plan(
            "owner-a",
            "shared-dir",
            MutationOp(
                kind="add",
                path="src/shared/a.py",
                postimage="class A:\n    pass\n",
            ),
            MutationOp(
                kind="add",
                path="src/shared/b.py",
                postimage="class B:\n    pass\n",
            ),
        )
    )
    assert result.status == "reserved"
    stored = _reservation_plan_json(index, "owner-a", "shared-dir")
    assert stored is not None
    assert "class A" not in stored
    assert "class B" not in stored


def test_invalid_utf8_and_oversized_relevant_files_fail_closed(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    bad_index = _index(repo_tree, git_exe)
    (repo_tree["repo"] / "src" / "two" / "bad.py").write_bytes(b"\xff\xfe")
    with pytest.raises(WorkspaceIndexFailure) as decode_exc:
        bad_index.refresh()
    assert decode_exc.value.code == "workspace_index_uncertain"

    good_index = _index(repo_tree, git_exe)
    (repo_tree["repo"] / "src" / "two" / "bad.py").unlink()
    (repo_tree["repo"] / "docs" / "huge.md").write_text(
        "x" * (MAX_RELEVANT_FILE_BYTES + 1),
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceIndexFailure) as size_exc:
        good_index.refresh()
    assert size_exc.value.code == "workspace_index_uncertain"


def test_connect_locked_maps_to_busy(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()

    def locked_connect(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("harness.workspace_index.sqlite3.connect", locked_connect)
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.assert_fresh()
    assert excinfo.value.code == "workspace_index_busy"


def test_post_connect_lock_contention_maps_to_busy_with_control(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    ready = repo_tree["state_root"] / "post-connect-ready"
    release = repo_tree["state_root"] / "post-connect-release"
    proc = _hold_db_lock(index, ready, release)
    try:
        deadline = time.time() + 10
        while not ready.exists():
            assert proc.poll() is None
            assert time.time() < deadline
            time.sleep(0.05)
        with pytest.raises(WorkspaceIndexFailure) as excinfo:
            index.refresh()
        assert excinfo.value.code == "workspace_index_busy"
    finally:
        release.write_text("release", encoding="utf-8")
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, (stdout, stderr)
    index.refresh()


def test_begin_immediate_nonbusy_operational_error_is_not_busy(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)

    class _FailingConn:
        def execute(self, _sql: str) -> None:
            raise sqlite3.OperationalError("disk I/O error")

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index._begin_immediate(_FailingConn())  # type: ignore[arg-type]
    assert excinfo.value.code == "workspace_index_corrupt"


def test_deadline_armed_connections_install_progress_handler(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.deadline_monotonic = time.monotonic() + 30
    real_connect = sqlite3.connect
    progress_calls: list[tuple[bool, int]] = []

    class _ConnProxy:
        def __init__(self, conn: sqlite3.Connection):
            self._conn = conn

        @property
        def row_factory(self) -> Any:
            return self._conn.row_factory

        @row_factory.setter
        def row_factory(self, value: Any) -> None:
            self._conn.row_factory = value

        def set_progress_handler(self, handler: Any, steps: int) -> None:
            progress_calls.append((handler is not None, steps))
            self._conn.set_progress_handler(handler, steps)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._conn, name)

    def tracked_connect(*args: Any, **kwargs: Any) -> _ConnProxy:
        return _ConnProxy(real_connect(*args, **kwargs))

    monkeypatch.setattr("harness.workspace_index.sqlite3.connect", tracked_connect)
    index.assert_fresh()
    assert progress_calls
    assert progress_calls[0][0] is True
    assert progress_calls[0][1] > 0


def test_non_move_source_path_is_rejected(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    for plan in (
        _plan(
            "owner-a",
            "bad-add-source",
            MutationOp(
                kind="add",
                path="src/two/add-with-source.py",
                source_path="src/one/service.py",
                postimage="class AddWithSource:\n    pass\n",
            ),
        ),
        _plan(
            "owner-a",
            "bad-update-source",
            MutationOp(
                kind="update",
                path="src/one/service.py",
                source_path="src/one/worker.py",
                postimage="class ExistingService:\n    pass\n",
            ),
        ),
        _plan(
            "owner-a",
            "bad-delete-source",
            MutationOp(
                kind="delete",
                path="src/one/service.py",
                source_path="src/one/worker.py",
            ),
        ),
    ):
        with pytest.raises(WorkspaceIndexFailure) as excinfo:
            index.reserve(plan)
        assert excinfo.value.code == "workspace_index_uncertain"


def test_postimage_size_limits_fail_closed(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    with pytest.raises(WorkspaceIndexFailure) as per_op_exc:
        index.reserve(
            _plan(
                "owner-a",
                "too-large-postimage",
                MutationOp(
                    kind="add",
                    path="src/two/too-large.py",
                    postimage="x" * (MAX_POSTIMAGE_BYTES + 1),
                ),
            )
        )
    assert per_op_exc.value.code == "workspace_op_limit"

    chunk = (MAX_PLAN_POSTIMAGE_BYTES // 3) + 1
    with pytest.raises(WorkspaceIndexFailure) as aggregate_exc:
        index.reserve(
            _plan(
                "owner-a",
                "too-large-plan",
                MutationOp(
                    kind="add",
                    path="src/two/aggregate-a.py",
                    postimage="x" * chunk,
                ),
                MutationOp(
                    kind="add",
                    path="src/two/aggregate-b.py",
                    postimage="y" * chunk,
                ),
                MutationOp(
                    kind="add",
                    path="src/two/aggregate-c.py",
                    postimage="z" * chunk,
                ),
            )
        )
    assert aggregate_exc.value.code == "workspace_op_limit"


def test_corrupt_database_and_foreign_key_violation_fail_closed(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.db_path.write_text("not a sqlite database", encoding="utf-8")
    with pytest.raises(WorkspaceIndexFailure) as corrupt_exc:
        index.assert_fresh()
    assert corrupt_exc.value.code == "workspace_index_corrupt"

    index.db_path.unlink()
    index = _index(repo_tree, git_exe)
    index.refresh()
    with sqlite3.connect(index.db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            """
            INSERT INTO reservation_claims(owner, operation_id, claim_kind, claim_key, claim_path)
            VALUES('ghost', 'ghost', 'file', 'src/two/ghost.py', 'src/two/ghost.py')
            """
        )
        conn.commit()
    with pytest.raises(WorkspaceIndexFailure) as fk_exc:
        index.assert_fresh()
    assert fk_exc.value.code == "workspace_index_corrupt"


def test_db_header_probe_is_bounded_to_16_bytes(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()

    class _HeaderReader:
        def __init__(self, fh: Any, sink: list[int]):
            self._fh = fh
            self._sink = sink

        def read(self, size: int = -1) -> bytes:
            self._sink.append(size)
            return self._fh.read(size)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._fh, name)

        def __enter__(self) -> "_HeaderReader":
            self._fh.__enter__()
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return self._fh.__exit__(exc_type, exc, tb)

    real_open = Path.open
    captured_reads: list[int] = []

    def tracked_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = real_open(self, *args, **kwargs)
        if self == index.db_path and args and "b" in str(args[0]):
            return _HeaderReader(handle, captured_reads)
        return handle

    def forbidden_read_bytes(self: Path) -> bytes:
        raise AssertionError(
            "Path.read_bytes must not be used for sqlite header probes"
        )

    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)

    index.assert_fresh()
    assert 16 in captured_reads
    assert all(size in {16, MAX_RELEVANT_FILE_BYTES + 1} for size in captured_reads)


def test_lock_contention_fails_closed_as_busy(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    ready = repo_tree["state_root"] / "ready"
    release = repo_tree["state_root"] / "release"
    proc = _hold_db_lock(index, ready, release)
    try:
        deadline = time.time() + 10
        while not ready.exists():
            assert proc.poll() is None
            assert time.time() < deadline
            time.sleep(0.05)
        with pytest.raises(WorkspaceIndexFailure) as excinfo:
            index.reserve(
                _plan(
                    "owner-a",
                    "op-a",
                    MutationOp(
                        kind="add",
                        path="src/two/busy.py",
                        postimage="class Busy:\n    pass\n",
                    ),
                )
            )
        assert excinfo.value.code == "workspace_index_busy"
    finally:
        release.write_text("release", encoding="utf-8")
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, (stdout, stderr)


def test_refresh_lock_contention_fails_closed_as_busy_with_control(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    receipt = index.refresh()
    ready = repo_tree["state_root"] / "refresh-ready"
    release = repo_tree["state_root"] / "refresh-release"
    proc = _hold_db_lock(index, ready, release)
    try:
        deadline = time.time() + 10
        while not ready.exists():
            assert proc.poll() is None
            assert time.time() < deadline
            time.sleep(0.05)
        with pytest.raises(WorkspaceIndexFailure) as excinfo:
            index.refresh()
        assert excinfo.value.code == "workspace_index_busy"
    finally:
        release.write_text("release", encoding="utf-8")
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, (stdout, stderr)
    second = index.refresh()
    assert second.file_count == receipt.file_count


def test_alias_and_reparse_escape_are_rejected(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    with pytest.raises(WorkspaceIndexFailure) as dot_exc:
        index.reserve(
            _plan(
                "owner-a",
                "dot",
                MutationOp(
                    kind="update",
                    path="src/one/service.py.",
                    postimage="class ExistingService:\n    pass\n",
                ),
            )
        )
    assert dot_exc.value.code == "workspace_index_uncertain"

    with pytest.raises(WorkspaceIndexFailure) as case_exc:
        index.reserve(
            _plan(
                "owner-a",
                "case",
                MutationOp(
                    kind="update",
                    path="src/ONE/service.py",
                    postimage="class ExistingService:\n    pass\n",
                ),
            )
        )
    assert case_exc.value.code == "workspace_index_uncertain"

    outside = repo_tree["repo"].parent / "outside"
    outside.mkdir()
    link = repo_tree["repo"] / "src" / "jump"
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if completed.returncode != 0:
                pytest.skip("junction creation unavailable")
        else:
            link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(WorkspaceIndexFailure) as link_exc:
            index.reserve(
                _plan(
                    "owner-a",
                    "link",
                    MutationOp(
                        kind="add",
                        path="src/jump/escape.py",
                        postimage="class Escape:\n    pass\n",
                    ),
                )
            )
        assert link_exc.value.code == "workspace_index_uncertain"
        reparse_index = WorkspaceIndex(
            state_root=repo_tree["state_root"] / "reparse",
            repo_path=repo_tree["repo"],
            git_executable=git_exe,
        )
        with pytest.raises(WorkspaceIndexFailure) as refresh_exc:
            reparse_index.refresh()
        assert refresh_exc.value.code == "workspace_index_uncertain"
    finally:
        if link.exists():
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "rmdir", str(link)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                link.unlink()


def test_move_destination_overwrite_blocks(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    (repo_tree["repo"] / "src" / "two" / "existing.py").write_text(
        "class Existing:\n    pass\n",
        encoding="utf-8",
    )
    index.refresh()
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-a",
                "move",
                MutationOp(
                    kind="move",
                    path="src/two/existing.py",
                    source_path="src/one/service.py",
                    postimage="class ExistingService:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_index_uncertain"


def test_directory_operands_are_rejected_for_file_only_operations(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    nested = repo_tree["repo"] / "src" / "two" / "dir-node"
    nested.mkdir()
    (nested / "child.txt").write_text("child\n", encoding="utf-8")
    target_dir = repo_tree["repo"] / "src" / "two" / "move-target-dir"
    target_dir.mkdir()
    index.refresh()

    cases = [
        _plan(
            "owner-a",
            "dir-update",
            MutationOp(
                kind="update",
                path="src/two/dir-node",
                postimage="class NoDir:\n    pass\n",
            ),
        ),
        _plan(
            "owner-a",
            "dir-delete",
            MutationOp(
                kind="delete",
                path="src/two/dir-node",
            ),
        ),
        _plan(
            "owner-a",
            "dir-move-source",
            MutationOp(
                kind="move",
                path="src/two/moved.py",
                source_path="src/two/dir-node",
                postimage="class Moved:\n    pass\n",
            ),
        ),
        _plan(
            "owner-a",
            "dir-move-target",
            MutationOp(
                kind="move",
                path="src/two/move-target-dir",
                source_path="src/one/service.py",
                postimage="class ExistingService:\n    pass\n",
            ),
        ),
    ]
    for plan in cases:
        with pytest.raises(WorkspaceIndexFailure) as excinfo:
            index.reserve(plan)
        assert excinfo.value.code == "workspace_index_uncertain"


def test_root_file_updates_and_deletes_are_allowed_but_new_root_add_is_blocked(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()

    update_receipt = index.reserve(
        _plan(
            "owner-a",
            "root-update",
            MutationOp(
                kind="update",
                path="README.md",
                postimage="# updated fixture\n",
            ),
        )
    )
    assert update_receipt.status == "reserved"
    assert index.resolve(owner="owner-a", operation_id="root-update")

    delete_receipt = index.reserve(
        _plan(
            "owner-a",
            "root-delete",
            MutationOp(
                kind="delete",
                path="README.md",
            ),
        )
    )
    assert delete_receipt.status == "reserved"
    assert index.resolve(owner="owner-a", operation_id="root-delete")

    with pytest.raises(WorkspaceIndexFailure) as root_add_exc:
        index.reserve(
            _plan(
                "owner-a",
                "root-add",
                MutationOp(
                    kind="add",
                    path="NEWROOT.md",
                    postimage="# new root\n",
                ),
            )
        )
    assert root_add_exc.value.code == "workspace_top_level_slop"

    dir_add_receipt = index.reserve(
        _plan(
            "owner-a",
            "dir-add",
            MutationOp(
                kind="add",
                path="docs/guide-v2.md",
                postimage="# guide\n",
            ),
        )
    )
    assert dir_add_receipt.status == "reserved"


def test_refresh_rebuilds_legacy_identity_storage_schema(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    _init_legacy_identity_schema(index)

    with pytest.raises(WorkspaceIndexFailure) as stale_exc:
        index.assert_fresh()
    assert stale_exc.value.code == "workspace_index_stale"

    index.refresh()

    with sqlite3.connect(index.db_path) as conn:
        schema_version = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    types = _watch_schema_types(index)
    assert types["device"] == "TEXT"
    assert types["inode"] == "TEXT"
    assert schema_version is not None
    assert str(schema_version[0]) == "3"
    index.assert_fresh()


def test_failed_legacy_rebuild_does_not_expose_partial_v3_schema(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    _init_legacy_identity_schema(index)

    workspace_index = __import__("harness.workspace_index", fromlist=["WorkspaceIndex"])
    real_file_index_rows = workspace_index.WorkspaceIndex._file_index_rows
    ready = threading.Event()
    release = threading.Event()
    result: dict[str, BaseException | None] = {"exc": None}

    def failing_file_index_rows(
        self: WorkspaceIndex,
        relative_file: Path,
        physical: Path,
    ) -> dict[str, object]:
        ready.set()
        assert release.wait(timeout=10)
        raise WorkspaceIndexFailure(
            "workspace_index_uncertain",
            "injected scan failure",
        )

    monkeypatch.setattr(
        "harness.workspace_index.WorkspaceIndex._file_index_rows",
        failing_file_index_rows,
    )

    def run_refresh() -> None:
        try:
            index.refresh()
        except BaseException as exc:  # pragma: no cover - stored for assertions
            result["exc"] = exc

    thread = threading.Thread(target=run_refresh)
    thread.start()
    assert ready.wait(timeout=10)

    schema_version_during = None
    with sqlite3.connect(index.db_path) as conn:
        schema_version_during = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    types_during = _watch_schema_types(index)
    assert schema_version_during is not None
    assert str(schema_version_during[0]) == "2"
    assert types_during["device"] == "INTEGER"
    assert types_during["inode"] == "INTEGER"

    release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert isinstance(result["exc"], WorkspaceIndexFailure)
    assert result["exc"].code == "workspace_index_uncertain"

    with sqlite3.connect(index.db_path) as conn:
        schema_version_after = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    types_after = _watch_schema_types(index)
    assert schema_version_after is not None
    assert str(schema_version_after[0]) == "2"
    assert types_after["device"] == "INTEGER"
    assert types_after["inode"] == "INTEGER"

    monkeypatch.setattr(
        "harness.workspace_index.WorkspaceIndex._file_index_rows",
        real_file_index_rows,
    )
    index.refresh()
    rebuilt_types = _watch_schema_types(index)
    assert rebuilt_types["device"] == "TEXT"
    assert rebuilt_types["inode"] == "TEXT"


def test_numeric_only_leading_zero_identity_roundtrips_as_text(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    notice = repo_tree["repo"] / "NOTICE"
    notice.write_text("seed notice\n", encoding="utf-8")

    workspace_index = __import__("harness.workspace_index", fromlist=["_file_identity"])
    real_file_identity = workspace_index._file_identity
    forced_identity = ("vol:00000001", "idx:0029000000593762")

    def forced_file_identity(path: Path, stats: os.stat_result) -> tuple[str, str]:
        if Path(path).name == "NOTICE":
            return forced_identity
        return real_file_identity(path, stats)

    monkeypatch.setattr("harness.workspace_index._file_identity", forced_file_identity)

    index.refresh()
    row = _watch_identity_row(index, "NOTICE")
    assert str(row["device"]) == forced_identity[0]
    assert str(row["inode"]) == forced_identity[1]
    assert str(row["device_type"]) == "text"
    assert str(row["inode_type"]) == "text"

    receipt = index.reserve(
        _plan(
            "owner-a",
            "numeric-identity-probe",
            MutationOp(
                kind="add",
                path="src/two/numeric-identity-probe.py",
                postimage="class NumericIdentityProbe:\n    pass\n",
            ),
        )
    )
    assert receipt.status == "reserved"
    assert index.resolve(owner="owner-a", operation_id="numeric-identity-probe")


def test_alphanumeric_identity_roundtrips_as_text(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    license_file = repo_tree["repo"] / "LICENSE"
    license_file.write_text("seed license\n", encoding="utf-8")

    workspace_index = __import__("harness.workspace_index", fromlist=["_file_identity"])
    real_file_identity = workspace_index._file_identity
    forced_identity = ("vol:00ab00cd", "idx:00ff000000aa00bb")

    def forced_file_identity(path: Path, stats: os.stat_result) -> tuple[str, str]:
        if Path(path).name == "LICENSE":
            return forced_identity
        return real_file_identity(path, stats)

    monkeypatch.setattr("harness.workspace_index._file_identity", forced_file_identity)

    index.refresh()
    row = _watch_identity_row(index, "LICENSE")
    assert str(row["device"]) == forced_identity[0]
    assert str(row["inode"]) == forced_identity[1]
    assert str(row["device_type"]) == "text"
    assert str(row["inode_type"]) == "text"
    index.assert_fresh()


def test_root_other_file_transient_identity_mismatch_is_retried(
    repo_tree: dict[str, Path],
    git_exe: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index(repo_tree, git_exe)
    notice = repo_tree["repo"] / "NOTICE"
    notice.write_text("seed notice\n", encoding="utf-8")
    index.refresh()

    workspace_index = __import__("harness.workspace_index", fromlist=["_file_identity"])
    real_file_identity = workspace_index._file_identity
    seen = {"NOTICE": 0}

    def flaky_file_identity(path: Path, stats: os.stat_result) -> tuple[str, str]:
        if Path(path).name == "NOTICE" and seen["NOTICE"] == 0:
            seen["NOTICE"] += 1
            return ("deadbeef", "deadbeef")
        return real_file_identity(path, stats)

    monkeypatch.setattr("harness.workspace_index._file_identity", flaky_file_identity)

    receipt = index.reserve(
        _plan(
            "owner-a",
            "root-update-transient-identity",
            MutationOp(
                kind="update",
                path="NOTICE",
                postimage="updated notice\n",
            ),
        )
    )
    assert receipt.status == "reserved"


def test_root_other_file_replacement_still_fails_closed(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    notice = repo_tree["repo"] / "NOTICE"
    notice.write_text("seed notice\n", encoding="utf-8")
    index.refresh()

    replacement = repo_tree["repo"] / "NOTICE.replacement"
    replacement.write_text("seed notice\n", encoding="utf-8")
    os.replace(replacement, notice)

    with pytest.raises(WorkspaceIndexFailure) as stale_exc:
        index.assert_fresh()
    assert stale_exc.value.code == "workspace_index_stale"


def test_finalize_replay_is_idempotent_and_preserves_same_owner_siblings(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "finalize-a",
            MutationOp(
                kind="add",
                path="src/two/finalize-a.py",
                postimage="class FinalizeA:\n    pass\n",
            ),
        )
    )
    sibling = index.reserve(
        _plan(
            "owner-a",
            "finalize-b",
            MutationOp(
                kind="add",
                path="src/two/finalize-b.py",
                postimage="class FinalizeB:\n    pass\n",
            ),
        )
    )
    assert sibling.status == "reserved"
    (repo_tree["repo"] / "src" / "two" / "finalize-a.py").write_text(
        "class FinalizeA:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="finalize-a")
    assert _reservation_status(index, "owner-a", "finalize-b") == "reserved"
    assert index.finalize_success(owner="owner-a", operation_id="finalize-a")
    assert _reservation_status(index, "owner-a", "finalize-b") == "reserved"
    (repo_tree["repo"] / "src" / "two" / "finalize-b.py").write_text(
        "class FinalizeB:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="finalize-b")
    index.assert_fresh()


def test_root_only_repo_update_and_delete_finalize_succeed(
    tmp_path: Path,
    git_exe: Path,
) -> None:
    repo = tmp_path / "rootonly"
    repo.mkdir()
    _git(git_exe, "init", cwd=repo)
    _git(git_exe, "config", "user.email", "tests@example.com", cwd=repo)
    _git(git_exe, "config", "user.name", "Harness Tests", cwd=repo)
    (repo / "README.md").write_text("# root only\n", encoding="utf-8")
    _git(git_exe, "add", ".", cwd=repo)
    _git(git_exe, "commit", "-m", "fixture", cwd=repo)
    index = WorkspaceIndex(
        state_root=tmp_path / "state",
        repo_path=repo,
        git_executable=git_exe,
    )
    index.refresh()

    update_plan = _plan(
        "owner-a",
        "root-only-update",
        MutationOp(
            kind="update",
            path="README.md",
            postimage="# updated root only\n",
        ),
    )
    index.reserve(update_plan)
    (repo / "README.md").write_text(
        "# updated root only\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="root-only-update")
    index.assert_fresh()

    delete_plan = _plan(
        "owner-a",
        "root-only-delete",
        MutationOp(
            kind="delete",
            path="README.md",
        ),
    )
    index.reserve(delete_plan)
    (repo / "README.md").unlink()
    assert index.finalize_success(owner="owner-a", operation_id="root-only-delete")
    index.assert_fresh()

    with pytest.raises(WorkspaceIndexFailure) as root_add_exc:
        index.reserve(
            _plan(
                "owner-a",
                "root-only-add",
                MutationOp(
                    kind="add",
                    path="NEWROOT.md",
                    postimage="# still blocked\n",
                ),
            )
        )
    assert root_add_exc.value.code == "workspace_top_level_slop"


def test_finalize_rejects_unexpected_sibling_directory_delta(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()

    good_plan = _plan(
        "owner-a",
        "good-update",
        MutationOp(
            kind="update",
            path="src/one/service.py",
            postimage="class ExistingService:\n    pass\n\nclass Good:\n    pass\n",
        ),
    )
    index.reserve(good_plan)
    (repo_tree["repo"] / "src" / "one" / "service.py").write_text(
        "class ExistingService:\n    pass\n\nclass Good:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="good-update")
    index.assert_fresh()

    rogue_plan = _plan(
        "owner-a",
        "rogue-update",
        MutationOp(
            kind="update",
            path="src/one/service.py",
            postimage="class ExistingService:\n    pass\n\nclass Better:\n    pass\n",
        ),
    )
    index.reserve(rogue_plan)
    (repo_tree["repo"] / "src" / "one" / "service.py").write_text(
        "class ExistingService:\n    pass\n\nclass Better:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    (repo_tree["repo"] / "src" / "one" / "worker.py").write_text(
        "def gamma():\n    return 1\n",
        encoding="utf-8",
        newline="\n",
    )
    assert not index.finalize_success(owner="owner-a", operation_id="rogue-update")
    assert _reservation_status(index, "owner-a", "rogue-update") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"
    assert "unexpected directory state" in str(_meta_value(index, "health_reason"))


def test_op_and_session_limits_fail_closed(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    too_many_files = _plan(
        "owner-a",
        "files",
        *[
            MutationOp(
                kind="add",
                path=f"src/two/generated-{i}.py",
                postimage=f"class Generated{i}:\n    pass\n",
            )
            for i in range(MAX_OP_FILES + 1)
        ],
    )
    with pytest.raises(WorkspaceIndexFailure) as files_exc:
        index.reserve(too_many_files)
    assert files_exc.value.code == "workspace_op_limit"

    for i in range(MAX_OP_FILES + 1):
        (repo_tree["repo"] / "src" / "two" / f"update-limit-{i}.py").write_text(
            "class Seed:\n    pass\n",
            encoding="utf-8",
        )
        (repo_tree["repo"] / "src" / "two" / f"delete-limit-{i}.py").write_text(
            "class Seed:\n    pass\n",
            encoding="utf-8",
        )
    index.refresh()

    too_many_updates = _plan(
        "owner-a",
        "updates",
        *[
            MutationOp(
                kind="update",
                path=f"src/two/update-limit-{i}.py",
                postimage=f"class Updated{i}:\n    pass\n",
            )
            for i in range(MAX_OP_FILES + 1)
        ],
    )
    with pytest.raises(WorkspaceIndexFailure) as updates_exc:
        index.reserve(too_many_updates)
    assert updates_exc.value.code == "workspace_op_limit"

    too_many_deletes = _plan(
        "owner-a",
        "deletes",
        *[
            MutationOp(
                kind="delete",
                path=f"src/two/delete-limit-{i}.py",
            )
            for i in range(MAX_OP_FILES + 1)
        ],
    )
    with pytest.raises(WorkspaceIndexFailure) as deletes_exc:
        index.reserve(too_many_deletes)
    assert deletes_exc.value.code == "workspace_op_limit"

    too_many_dirs = _plan(
        "owner-a",
        "dirs",
        *[
            MutationOp(
                kind="add",
                path=f"src/slop{i}/new-{i}.py",
                postimage=f"class Slop{i}:\n    pass\n",
            )
            for i in range(MAX_OP_DIRS + 1)
        ],
    )
    with pytest.raises(WorkspaceIndexFailure) as dirs_exc:
        index.reserve(too_many_dirs)
    assert dirs_exc.value.code == "workspace_op_limit"

    for slot in range(8):
        index.reserve(
            _plan(
                "owner-a",
                f"slot-{slot}",
                MutationOp(
                    kind="add",
                    path=f"src/two/session-{slot}.py",
                    postimage=f"class Session{slot}:\n    pass\n",
                ),
            )
        )
    with pytest.raises(WorkspaceIndexFailure) as unresolved_exc:
        index.reserve(
            _plan(
                "owner-a",
                "slot-8",
                MutationOp(
                    kind="add",
                    path="src/two/session-8.py",
                    postimage="class Session8:\n    pass\n",
                ),
            )
        )
    assert unresolved_exc.value.code == "workspace_session_limit"


def test_update_and_delete_claims_count_toward_session_file_limit(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    for i in range(MAX_SESSION_FILES):
        if i % 2 == 0:
            (repo_tree["repo"] / "src" / "two" / f"existing-update-{i}.py").write_text(
                "class Seed:\n    pass\n", encoding="utf-8"
            )
        else:
            (repo_tree["repo"] / "src" / "two" / f"existing-delete-{i}.py").write_text(
                "class Seed:\n    pass\n", encoding="utf-8"
            )
    extra = repo_tree["repo"] / "src" / "two" / "existing-overflow.py"
    extra.write_text("class Seed:\n    pass\n", encoding="utf-8")
    index.refresh()
    index.deadline_monotonic = time.monotonic() + 30

    for batch in range(MAX_SESSION_FILES // MAX_OP_FILES):
        operations: list[MutationOp] = []
        start = batch * MAX_OP_FILES
        stop = start + MAX_OP_FILES
        for i in range(start, stop):
            if i % 2 == 0:
                operations.append(
                    MutationOp(
                        kind="update",
                        path=f"src/two/existing-update-{i}.py",
                        postimage=f"class Updated{i}:\n    pass\n",
                    )
                )
            else:
                operations.append(
                    MutationOp(
                        kind="delete",
                        path=f"src/two/existing-delete-{i}.py",
                    )
                )
        assert (
            index.reserve(_plan("owner-a", f"claim-batch-{batch}", *operations)).status
            == "reserved"
        )
    with pytest.raises(WorkspaceIndexFailure) as overflow_exc:
        index.reserve(
            _plan(
                "owner-a",
                "claim-overflow",
                MutationOp(
                    kind="update",
                    path="src/two/existing-overflow.py",
                    postimage="class Overflow:\n    pass\n",
                ),
            )
        )
    assert overflow_exc.value.code == "workspace_session_limit"


def test_reserve_rejects_existing_hardlinked_target_file(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    target = repo_tree["repo"] / "src" / "one" / "service.py"

    control = index.reserve(
        _plan(
            "owner-a",
            "hardlink-control",
            MutationOp(
                kind="update",
                path="src/one/service.py",
                postimage="class ExistingService:\n    pass\n",
            ),
        )
    )
    assert control.status == "reserved"
    assert index.resolve(owner="owner-a", operation_id="hardlink-control")

    outside_link = repo_tree["repo"].parent / "outside-hardlinks" / "service.py"
    _create_hardlink_or_skip(target, outside_link)

    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.reserve(
            _plan(
                "owner-a",
                "hardlink-target",
                MutationOp(
                    kind="update",
                    path="src/one/service.py",
                    postimage="class ExistingService:\n    pass\n",
                ),
            )
        )
    assert excinfo.value.code == "workspace_index_uncertain"


def test_finalize_rejects_hardlink_race_on_update_target(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    target = repo_tree["repo"] / "src" / "one" / "service.py"
    index.reserve(
        _plan(
            "owner-a",
            "hardlink-race",
            MutationOp(
                kind="update",
                path="src/one/service.py",
                postimage="class ExistingService:\n    value = 2\n",
            ),
        )
    )
    outside_link = repo_tree["repo"].parent / "outside-hardlinks-race" / "service.py"
    _create_hardlink_or_skip(target, outside_link)
    target.write_text(
        "class ExistingService:\n    value = 2\n",
        encoding="utf-8",
        newline="\n",
    )

    assert not index.finalize_success(owner="owner-a", operation_id="hardlink-race")
    assert _reservation_status(index, "owner-a", "hardlink-race") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"


def test_finalize_success_and_needs_refresh_paths(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    base_generation = _meta_value(index, "generation")
    add_plan = _plan(
        "owner-a",
        "finalize-add",
        MutationOp(
            kind="add",
            path="src/two/nested/final.py",
            postimage="class Final:\n    pass\n",
        ),
    )
    index.reserve(add_plan)
    nested_dir = repo_tree["repo"] / "src" / "two" / "nested"
    nested_dir.mkdir(parents=True)
    (nested_dir / "final.py").write_text(
        "class Final:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="finalize-add")
    assert _reservation_status(index, "owner-a", "finalize-add") == "completed"
    assert _meta_value(index, "generation") != base_generation
    index.assert_fresh()

    update_plan = _plan(
        "owner-a",
        "finalize-update",
        MutationOp(
            kind="update",
            path="src/two/nested/final.py",
            postimage="class FinalRenamed:\n    pass\n",
        ),
    )
    index.reserve(update_plan)
    (nested_dir / "final.py").write_text(
        "class FinalRenamed:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="finalize-update")
    index.assert_fresh()

    move_plan = _plan(
        "owner-a",
        "finalize-move",
        MutationOp(
            kind="move",
            path="src/two/final-moved.py",
            source_path="src/two/nested/final.py",
            postimage="class FinalRenamed:\n    pass\n",
        ),
    )
    index.reserve(move_plan)
    (repo_tree["repo"] / "src" / "two" / "final-moved.py").write_text(
        "class FinalRenamed:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    (nested_dir / "final.py").unlink()
    assert index.finalize_success(owner="owner-a", operation_id="finalize-move")
    index.assert_fresh()

    delete_plan = _plan(
        "owner-a",
        "finalize-delete",
        MutationOp(
            kind="delete",
            path="src/two/final-moved.py",
        ),
    )
    index.reserve(delete_plan)
    (repo_tree["repo"] / "src" / "two" / "final-moved.py").unlink()
    assert index.finalize_success(owner="owner-a", operation_id="finalize-delete")
    index.assert_fresh()
    with sqlite3.connect(index.db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM files WHERE path = 'src/two/final-moved.py'"
        ).fetchone()
    assert row is None

    bad_plan = _plan(
        "owner-a",
        "finalize-bad",
        MutationOp(
            kind="add",
            path="src/two/final-bad.py",
            postimage="class FinalBad:\n    pass\n",
        ),
    )
    index.reserve(bad_plan)
    (repo_tree["repo"] / "src" / "two" / "final-bad.py").write_text(
        "class Drifted:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert not index.finalize_success(owner="owner-a", operation_id="finalize-bad")
    assert _reservation_status(index, "owner-a", "finalize-bad") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"
    assert (
        _meta_value(index, "health_reason")
        == "postimage mismatch: src/two/final-bad.py"
    )
    with pytest.raises(WorkspaceIndexFailure) as stale_exc:
        index.assert_fresh()
    assert stale_exc.value.code == "workspace_index_stale"
    with pytest.raises(WorkspaceIndexFailure) as reserve_exc:
        index.reserve(
            _plan(
                "owner-b",
                "blocked-while-stale",
                MutationOp(
                    kind="add",
                    path="src/two/blocked.py",
                    postimage="class Blocked:\n    pass\n",
                ),
            )
        )
    assert reserve_exc.value.code == "workspace_index_stale"


def test_mark_needs_refresh_updates_status(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "crash",
            MutationOp(
                kind="add",
                path="src/two/crash.py",
                postimage="class Crash:\n    pass\n",
            ),
        )
    )
    assert index.mark_needs_refresh(
        owner="owner-a",
        operation_id="crash",
        reason="synthetic crash",
    )
    assert _reservation_status(index, "owner-a", "crash") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"
    assert _meta_value(index, "health_reason") == "synthetic crash"
    with pytest.raises(WorkspaceIndexFailure) as stale_exc:
        index.reserve(
            _plan(
                "owner-b",
                "blocked",
                MutationOp(
                    kind="add",
                    path="src/two/blocked.py",
                    postimage="class Blocked:\n    pass\n",
                ),
            )
        )
    assert stale_exc.value.code == "workspace_index_stale"
    index.refresh()
    assert _meta_value(index, "health_status") == "ok"


def test_mark_needs_refresh_replay_is_idempotent(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "needs-refresh-replay",
            MutationOp(
                kind="add",
                path="src/two/replay.py",
                postimage="class Replay:\n    pass\n",
            ),
        )
    )
    assert index.mark_needs_refresh(
        owner="owner-a",
        operation_id="needs-refresh-replay",
        reason="first synthetic crash",
    )
    assert index.mark_needs_refresh(
        owner="owner-a",
        operation_id="needs-refresh-replay",
        reason="replayed synthetic crash",
    )
    assert (
        _reservation_status(index, "owner-a", "needs-refresh-replay") == "needs_refresh"
    )
    assert _meta_value(index, "health_status") == "needs_refresh"


def test_invalidate_blocks_reserve_until_explicit_refresh(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "lost-post",
            MutationOp(
                kind="add",
                path="src/two/lost.py",
                postimage="class Lost:\n    pass\n",
            ),
        )
    )
    assert index.invalidate(reason="missing post hook")
    assert _reservation_status(index, "owner-a", "lost-post") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"
    assert _meta_value(index, "health_reason") == "missing post hook"
    with pytest.raises(WorkspaceIndexFailure) as reserve_exc:
        index.reserve(
            _plan(
                "owner-b",
                "blocked-after-invalidate",
                MutationOp(
                    kind="add",
                    path="src/two/blocked.py",
                    postimage="class Blocked:\n    pass\n",
                ),
            )
        )
    assert reserve_exc.value.code == "workspace_index_stale"
    index.refresh()
    assert _meta_value(index, "health_status") == "ok"
    retry = index.reserve(
        _plan(
            "owner-b",
            "after-refresh",
            MutationOp(
                kind="add",
                path="src/two/after-refresh.py",
                postimage="class AfterRefresh:\n    pass\n",
            ),
        )
    )
    assert retry.status == "reserved"


def test_abandon_owner_releases_only_that_owner_claims(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "abandon-me",
            MutationOp(
                kind="add",
                path="src/two/abandon-me.py",
                postimage="class AbandonMe:\n    pass\n",
            ),
        )
    )
    assert index.abandon_owner(owner="owner-a")
    assert _reservation_status(index, "owner-a", "abandon-me") == "abandoned"
    index.refresh()
    assert _meta_value(index, "health_status") == "ok"


def test_abandon_owner_does_not_clear_other_active_reservations(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "abandon-a",
            MutationOp(
                kind="add",
                path="src/two/abandon-a.py",
                postimage="class AbandonA:\n    pass\n",
            ),
        )
    )
    index.reserve(
        _plan(
            "owner-b",
            "keep-b",
            MutationOp(
                kind="add",
                path="src/two/keep-b.py",
                postimage="class KeepB:\n    pass\n",
            ),
        )
    )
    assert index.abandon_owner(owner="owner-a")
    assert _reservation_status(index, "owner-a", "abandon-a") == "abandoned"
    assert _reservation_status(index, "owner-b", "keep-b") == "reserved"
    with pytest.raises(WorkspaceIndexFailure) as refresh_exc:
        index.refresh()
    assert refresh_exc.value.code == "workspace_index_stale"


def test_abandon_owner_stale_write_invalidates_all_reservations(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "crashed-owner",
            MutationOp(
                kind="add",
                path="src/two/crashed-owner.py",
                postimage="class CrashedOwner:\n    pass\n",
            ),
        )
    )
    other = index.reserve(
        _plan(
            "owner-b",
            "other-live",
            MutationOp(
                kind="add",
                path="src/two/other-live.py",
                postimage="class OtherLive:\n    pass\n",
            ),
        )
    )
    assert other.status == "reserved"
    (repo_tree["repo"] / "src" / "two" / "crashed-owner.py").write_text(
        "class CrashedOwner:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert not index.abandon_owner(owner="owner-a")
    assert _reservation_status(index, "owner-a", "crashed-owner") == "needs_refresh"
    assert _reservation_status(index, "owner-b", "other-live") == "needs_refresh"
    assert _meta_value(index, "health_status") == "needs_refresh"
    assert _meta_value(index, "health_reason") is not None
    assert "abandon_owner invalidated" in str(_meta_value(index, "health_reason"))
    with pytest.raises(WorkspaceIndexFailure) as finalize_exc:
        index.finalize_success(owner="owner-b", operation_id="other-live")
    assert finalize_exc.value.code == "workspace_index_stale"
    with pytest.raises(WorkspaceIndexFailure) as reserve_exc:
        index.reserve(
            _plan(
                "owner-c",
                "blocked-until-refresh",
                MutationOp(
                    kind="add",
                    path="src/two/blocked-until-refresh.py",
                    postimage="class BlockedUntilRefresh:\n    pass\n",
                ),
            )
        )
    assert reserve_exc.value.code == "workspace_index_stale"
    index.refresh()
    assert _meta_value(index, "health_status") == "ok"


def test_refresh_blocks_while_active_reservation_exists(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    index.reserve(
        _plan(
            "owner-a",
            "active-refresh-block",
            MutationOp(
                kind="add",
                path="src/two/active.py",
                postimage="class Active:\n    pass\n",
            ),
        )
    )
    with pytest.raises(WorkspaceIndexFailure) as excinfo:
        index.refresh()
    assert excinfo.value.code == "workspace_index_stale"


def test_finalize_rebases_disjoint_active_reservation(
    repo_tree: dict[str, Path],
    git_exe: Path,
) -> None:
    index = _index(repo_tree, git_exe)
    index.refresh()
    first = _plan(
        "owner-a",
        "first",
        MutationOp(
            kind="add",
            path="src/two/a.py",
            postimage="class First:\n    pass\n",
        ),
    )
    second = _plan(
        "owner-b",
        "second",
        MutationOp(
            kind="add",
            path="docs/notes-v3.md",
            postimage="# notes\n",
        ),
    )
    first_receipt = index.reserve(first)
    second_receipt = index.reserve(second)
    assert first_receipt.generation == second_receipt.generation
    (repo_tree["repo"] / "src" / "two" / "a.py").write_text(
        "class First:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-a", operation_id="first")
    rebased_generation = _reservation_generation(index, "owner-b", "second")
    assert rebased_generation is not None
    assert rebased_generation != second_receipt.generation
    (repo_tree["repo"] / "docs" / "notes-v3.md").write_text(
        "# notes\n",
        encoding="utf-8",
        newline="\n",
    )
    assert index.finalize_success(owner="owner-b", operation_id="second")
    index.assert_fresh()
