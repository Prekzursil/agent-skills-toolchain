#!/usr/bin/env python3
"""TST-0345 SUT: parallel-test isolation (temp root, worktree, write trace, git guard).

Estate defect this unit closes: file-disjoint parallel test workers share one
git index and one temp root, so a broad `git add -A` sweeps a sibling's work.
pytest-xdist, command-center/TEST-REGISTRY.json, and production git-worktree
tooling are absent from this worktree; this module is the contracted test-program
isolation layer the named probes measure.

Scratch git operations stay under the session temp directory. The live tree is
never used as a git worktree or index.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REAL_GIT = "/usr/bin/git"
N_WORKERS_DEFAULT = 4
N_WRITES_DEFAULT = 16
HOLD_NS = 50_000_000  # keep worker windows overlapping after the barrier


def _rmtree(path: Path) -> None:
    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IRWXU)
            func(p)
        except OSError:
            pass

    if path.exists():
        shutil.rmtree(path, onerror=onerror)


def run_git(
    cwd: Path | str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    use = dict(env if env is not None else os.environ)
    use.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    return subprocess.run(
        [REAL_GIT, *args],
        cwd=str(cwd),
        env=use,
        text=True,
        capture_output=True,
        check=False,
    )


def run_git_checked(cwd: Path | str, *args: str) -> str:
    p = run_git(cwd, *args)
    if p.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed rc={p.returncode}: "
            f"{(p.stderr or p.stdout or '')[-800:]}"
        )
    return (p.stdout or "").strip()


def install_git_guard(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    git_path = bin_dir / "git"
    git_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "from git_wrapper import main\n"
        "raise SystemExit(main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    git_path.chmod(git_path.stat().st_mode | stat.S_IEXEC)
    return bin_dir


@dataclass
class WorkerSpec:
    worker_id: str
    temp_root: str
    worktree: str
    git_dir: str
    index_file: str
    guard_bin: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def make_seed_repo(parent: Path) -> Path:
    seed = parent / "seed"
    seed.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "TST-0345"
    env["GIT_AUTHOR_EMAIL"] = "tst0345@local"
    env["GIT_COMMITTER_NAME"] = "TST-0345"
    env["GIT_COMMITTER_EMAIL"] = "tst0345@local"
    p = subprocess.run(
        [REAL_GIT, "init", "-b", "main"],
        cwd=str(seed),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git init failed: {p.stderr}")
    for key, val in (("user.email", "tst0345@local"), ("user.name", "TST-0345")):
        subprocess.run(
            [REAL_GIT, "config", key, val],
            cwd=str(seed),
            env=env,
            check=True,
            capture_output=True,
        )
    (seed / "README").write_text("tst-0345 seed\n", encoding="utf-8")
    subprocess.run(
        [REAL_GIT, "add", "README"],
        cwd=str(seed),
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [REAL_GIT, "commit", "-m", "seed"],
        cwd=str(seed),
        env=env,
        check=True,
        capture_output=True,
    )
    return seed


class IsolationSession:
    def __init__(self, root: Path):
        self.root = root
        self.seed = make_seed_repo(root)
        self.guard_bin = install_git_guard(root / "guard-bin")

    def close(self) -> None:
        _rmtree(self.root)

    def _worktree_meta(self, worktree: Path) -> tuple[str, str]:
        git_dir = run_git_checked(worktree, "rev-parse", "--absolute-git-dir")
        index_file = run_git_checked(worktree, "rev-parse", "--git-path", "index")
        index_path = Path(index_file)
        if not index_path.is_absolute():
            index_path = (worktree / index_path).resolve()
        else:
            index_path = Path(os.path.realpath(index_path))
        return os.path.realpath(git_dir), str(index_path)

    def allocate_isolated(self, n: int) -> list[WorkerSpec]:
        specs: list[WorkerSpec] = []
        for i in range(n):
            wid = f"w{i}"
            temp_root = self.root / "workers" / wid
            temp_root.mkdir(parents=True, exist_ok=True)
            worktree = temp_root / "worktree"
            p = run_git(self.seed, "worktree", "add", "--detach", str(worktree), "HEAD")
            if p.returncode != 0:
                raise RuntimeError(f"worktree add failed: {p.stderr}")
            git_dir, index_file = self._worktree_meta(worktree)
            specs.append(
                WorkerSpec(
                    worker_id=wid,
                    temp_root=os.path.realpath(temp_root),
                    worktree=os.path.realpath(worktree),
                    git_dir=git_dir,
                    index_file=index_file,
                    guard_bin=str(self.guard_bin),
                )
            )
        return specs

    def allocate_colliding_temp_root(self, n: int = 2) -> list[WorkerSpec]:
        shared = self.root / "collision" / "shared-temp"
        shared.mkdir(parents=True, exist_ok=True)
        shared_r = os.path.realpath(shared)
        specs: list[WorkerSpec] = []
        for i in range(n):
            wid = f"c{i}"
            worktree = shared / f"wt-{wid}"
            worktree.mkdir(parents=True, exist_ok=True)
            specs.append(
                WorkerSpec(
                    worker_id=wid,
                    temp_root=shared_r,
                    worktree=os.path.realpath(worktree),
                    git_dir="",
                    index_file="",
                    guard_bin=str(self.guard_bin),
                )
            )
        return specs


def worker_env(spec: WorkerSpec | dict[str, str]) -> dict[str, str]:
    d = spec.to_dict() if isinstance(spec, WorkerSpec) else spec
    env = os.environ.copy()
    env["PATH"] = d["guard_bin"] + os.pathsep + env.get("PATH", "")
    env["TST0345_REAL_GIT"] = REAL_GIT
    env["TST0345_WORKER_ID"] = d["worker_id"]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if d.get("index_file"):
        env["GIT_INDEX_FILE"] = d["index_file"]
    return env


def _hold_overlap(t0: int) -> None:
    while time.time_ns() < t0 + HOLD_NS:
        time.sleep(0.005)


def _isolated_job(
    spec: dict[str, str], n_writes: int, barrier: Any, q: Any
) -> None:
    barrier.wait()
    t0 = time.time_ns()
    writes: list[str] = []
    art = Path(spec["worktree"]) / "artifacts" / spec["worker_id"]
    art.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    for i in range(n_writes):
        p = art / f"shard-{i:04d}.txt"
        p.write_text(f"{spec['worker_id']}:{i}:{pid}\n", encoding="utf-8")
        writes.append(os.path.realpath(p))
    _hold_overlap(t0)
    t1 = time.time_ns()
    q.put(
        {
            "worker_id": spec["worker_id"],
            "pid": pid,
            "temp_root": os.path.realpath(spec["temp_root"]),
            "worktree": os.path.realpath(spec["worktree"]),
            "git_dir": spec.get("git_dir") or "",
            "index_file": spec.get("index_file") or "",
            "t0_ns": t0,
            "t1_ns": t1,
            "writes": writes,
        }
    )


def _collision_job(
    spec: dict[str, str], filename: str, barrier: Any, q: Any
) -> None:
    barrier.wait()
    t0 = time.time_ns()
    p = Path(spec["temp_root"]) / filename
    p.write_text(f"{spec['worker_id']}:{os.getpid()}\n", encoding="utf-8")
    _hold_overlap(t0)
    t1 = time.time_ns()
    q.put(
        {
            "worker_id": spec["worker_id"],
            "pid": os.getpid(),
            "temp_root": os.path.realpath(spec["temp_root"]),
            "worktree": os.path.realpath(spec["worktree"]),
            "git_dir": spec.get("git_dir") or "",
            "index_file": spec.get("index_file") or "",
            "t0_ns": t0,
            "t1_ns": t1,
            "writes": [os.path.realpath(p)],
        }
    )


def _join_all(procs: list[multiprocessing.Process], timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    for p in procs:
        remaining = max(0.1, deadline - time.time())
        p.join(timeout=remaining)
    alive = [p.pid for p in procs if p.is_alive()]
    if alive:
        for p in procs:
            if p.is_alive():
                p.terminate()
        raise RuntimeError(f"worker processes still alive: {alive}")
    if any(p.exitcode not in (0, None) for p in procs):
        raise RuntimeError(
            "worker exit codes: " + ", ".join(f"{p.pid}={p.exitcode}" for p in procs)
        )


def audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) < 2:
        raise ValueError("audit requires at least two workers")
    temp_roots = [os.path.realpath(r["temp_root"]) for r in records]
    worktrees = [os.path.realpath(r["worktree"]) for r in records]
    git_dirs = [os.path.realpath(r["git_dir"]) for r in records if r.get("git_dir")]
    index_files = [
        os.path.realpath(r["index_file"]) for r in records if r.get("index_file")
    ]
    pids = [r["pid"] for r in records]

    shared_temp_roots = len(set(temp_roots)) < len(temp_roots)
    shared_worktrees = len(set(worktrees)) < len(worktrees)
    shared_git_dirs = bool(git_dirs) and len(set(git_dirs)) < len(git_dirs)
    shared_indexes = bool(index_files) and len(set(index_files)) < len(index_files)
    distinct_pids = len(set(pids)) == len(pids)

    write_sets = [set(os.path.realpath(p) for p in r["writes"]) for r in records]
    intersection: set[str] = set()
    pairwise: list[dict[str, Any]] = []
    for i in range(len(write_sets)):
        for j in range(i + 1, len(write_sets)):
            common = sorted(write_sets[i] & write_sets[j])
            pairwise.append(
                {
                    "a": records[i]["worker_id"],
                    "b": records[j]["worker_id"],
                    "common_count": len(common),
                    "common": common[:12],
                }
            )
            intersection |= set(common)

    escapes: list[dict[str, str]] = []
    for rec, wset in zip(records, write_sets):
        root = os.path.realpath(rec["temp_root"])
        prefix = root.rstrip(os.sep) + os.sep
        for p in wset:
            if p != root and not p.startswith(prefix):
                escapes.append({"worker_id": rec["worker_id"], "path": p})

    starts = [int(r["t0_ns"]) for r in records]
    ends = [int(r["t1_ns"]) for r in records]
    overlapped = max(starts) < min(ends)

    isolated = (
        not shared_temp_roots
        and not shared_worktrees
        and not shared_git_dirs
        and not shared_indexes
        and not intersection
        and not escapes
        and distinct_pids
    )
    return {
        "worker_count": len(records),
        "shared_temp_roots": shared_temp_roots,
        "shared_worktrees": shared_worktrees,
        "shared_git_dirs": shared_git_dirs,
        "shared_indexes": shared_indexes,
        "distinct_pids": distinct_pids,
        "write_path_intersection": sorted(intersection),
        "write_path_intersection_empty": len(intersection) == 0,
        "pairwise": pairwise,
        "escapes": escapes,
        "overlapped": overlapped,
        "t0_ns_max": max(starts),
        "t1_ns_min": min(ends),
        "isolated": isolated,
        "collision_detected": shared_temp_roots
        or shared_worktrees
        or bool(intersection),
    }


def write_path_map(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rec in sorted(records, key=lambda r: r["worker_id"]):
        writes = [os.path.realpath(p) for p in rec["writes"]]
        out[rec["worker_id"]] = {
            "pid": rec["pid"],
            "temp_root": os.path.realpath(rec["temp_root"]),
            "worktree": os.path.realpath(rec["worktree"]),
            "git_dir": rec.get("git_dir") or "",
            "index_file": rec.get("index_file") or "",
            "write_count": len(writes),
            "writes": writes,
            "t0_ns": rec["t0_ns"],
            "t1_ns": rec["t1_ns"],
        }
    return out


def run_isolated_concurrent(
    n_workers: int = N_WORKERS_DEFAULT, n_writes: int = N_WRITES_DEFAULT
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0345-iso-"))
    sess = IsolationSession(tmp)
    try:
        specs = sess.allocate_isolated(n_workers)
        ctx = multiprocessing.get_context("fork")
        barrier = ctx.Barrier(n_workers)
        q: Any = ctx.Queue()
        procs = [
            ctx.Process(
                target=_isolated_job, args=(s.to_dict(), n_writes, barrier, q)
            )
            for s in specs
        ]
        for p in procs:
            p.start()
        _join_all(procs)
        records = [q.get(timeout=5) for _ in specs]
        audit = audit_records(records)
        return {
            "mode": "isolated-concurrent",
            "n_workers": n_workers,
            "n_writes": n_writes,
            "records": records,
            "write_path_map": write_path_map(records),
            "audit": audit,
        }
    finally:
        sess.close()


def run_collision_control() -> dict[str, Any]:
    """Force two workers onto one temp root; audit must detect it.

    Subtest A: same temp root, disjoint filenames — file-path intersection may
    be empty; shared_temp_roots must still fire (that check is load-bearing).
    Subtest B: same temp root, same filename — write-path intersection fires.
    """
    tmp = Path(tempfile.mkdtemp(prefix="tst0345-col-"))
    sess = IsolationSession(tmp)
    try:
        ctx = multiprocessing.get_context("fork")

        def _run(filenames: list[str]) -> dict[str, Any]:
            specs = sess.allocate_colliding_temp_root(len(filenames))
            barrier = ctx.Barrier(len(specs))
            q: Any = ctx.Queue()
            procs = [
                ctx.Process(
                    target=_collision_job, args=(s.to_dict(), fn, barrier, q)
                )
                for s, fn in zip(specs, filenames)
            ]
            for p in procs:
                p.start()
            _join_all(procs)
            records = [q.get(timeout=5) for _ in specs]
            return {"records": records, "audit": audit_records(records)}

        disjoint = _run(["agent-a.bin", "agent-b.bin"])
        same_file = _run(["collision.txt", "collision.txt"])
        disjoint_detected = bool(disjoint["audit"]["shared_temp_roots"])
        same_detected = bool(same_file["audit"]["write_path_intersection"]) or bool(
            same_file["audit"]["shared_temp_roots"]
        )
        return {
            "mode": "collision-control",
            "disjoint_files_shared_root": {
                "shared_temp_roots": disjoint["audit"]["shared_temp_roots"],
                "write_path_intersection_empty": disjoint["audit"][
                    "write_path_intersection_empty"
                ],
                "write_path_map": write_path_map(disjoint["records"]),
                "detected": disjoint_detected,
            },
            "same_file_shared_root": {
                "shared_temp_roots": same_file["audit"]["shared_temp_roots"],
                "write_path_intersection": same_file["audit"][
                    "write_path_intersection"
                ],
                "write_path_map": write_path_map(same_file["records"]),
                "detected": same_detected,
            },
            "detector_fired": disjoint_detected and same_detected,
        }
    finally:
        sess.close()


def _cached_names(cwd: Path, env: dict[str, str] | None = None) -> list[str]:
    p = subprocess.run(
        [REAL_GIT, "diff", "--cached", "--name-only"],
        cwd=str(cwd),
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    return [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]


def run_staging_refusal() -> dict[str, Any]:
    """Guarded worker staging is refused; unguarded shared-index add sweeps siblings."""
    tmp = Path(tempfile.mkdtemp(prefix="tst0345-stg-"))
    sess = IsolationSession(tmp)
    try:
        specs = sess.allocate_isolated(2)
        a, b = specs
        (Path(a.worktree) / "agent-a.txt").write_text("payload-a\n", encoding="utf-8")
        (Path(b.worktree) / "agent-b.txt").write_text("payload-b\n", encoding="utf-8")

        env_a = worker_env(a)
        attempted = subprocess.run(
            ["git", "add", "-A"],
            cwd=a.worktree,
            env=env_a,
            text=True,
            capture_output=True,
        )
        guarded_text = (attempted.stderr or "") + (attempted.stdout or "")
        env_idx_a = os.environ.copy()
        env_idx_a["GIT_INDEX_FILE"] = a.index_file
        env_idx_b = os.environ.copy()
        env_idx_b["GIT_INDEX_FILE"] = b.index_file
        cached_a = _cached_names(Path(a.worktree), env=env_idx_a)
        cached_b = _cached_names(Path(b.worktree), env=env_idx_b)

        shared = sess.root / "unguarded-shared"
        p = run_git(sess.seed, "worktree", "add", "--detach", str(shared), "HEAD")
        if p.returncode != 0:
            raise RuntimeError(f"unguarded worktree add failed: {p.stderr}")
        (shared / "agent-a.txt").write_text("payload-a\n", encoding="utf-8")
        (shared / "agent-b.txt").write_text("payload-b\n", encoding="utf-8")
        add = run_git(shared, "add", "-A")
        if add.returncode != 0:
            raise RuntimeError(f"unguarded git add failed: {add.stderr}")
        unguarded_cached = _cached_names(shared)

        refused = (
            attempted.returncode != 0
            and "TST-0345" in guarded_text
            and "add" in guarded_text
        )
        sibling_protected = (
            "agent-a.txt" not in cached_a and "agent-b.txt" not in cached_a
        )
        unguarded_sweeps = (
            "agent-a.txt" in unguarded_cached and "agent-b.txt" in unguarded_cached
        )
        return {
            "mode": "staging-refusal",
            "guarded_attempt": {
                "argv": ["git", "add", "-A"],
                "cwd": a.worktree,
                "returncode": attempted.returncode,
                "stderr": (attempted.stderr or "")[-500:],
                "refused": refused,
            },
            "index_after_guarded": {
                "worker_a_cached": cached_a,
                "worker_b_cached": cached_b,
                "sibling_not_staged": sibling_protected,
            },
            "unguarded_shared_index_control": {
                "cached": unguarded_cached,
                "swept_both_siblings": unguarded_sweeps,
                "real_git": REAL_GIT,
            },
            "pass": refused and sibling_protected and unguarded_sweeps,
        }
    finally:
        sess.close()


def dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
