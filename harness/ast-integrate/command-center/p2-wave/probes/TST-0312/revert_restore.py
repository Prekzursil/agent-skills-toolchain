"""Two-signal automatic-revert restore checker for TST-0312.

Signal 1 (benchmark): re-run the fixture bench; |delta vs baseline| must
fall within the measured null-delta variance floor.

Signal 2 (path): the work tree on affected paths, including untracked
cache/generated files, must match the pre-change commit tree. A git
checkout that leaves residue is a path FAIL, not a restore.

Restore is RESTORED only when both signals agree. One signal alone is
SINGLE_SIGNAL_REJECTED — the single-signal failure this unit exists to
catch. All git work stays in a disposable directory; the host worktree
is never mutated.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
KERNEL_REL = "src/kernel.py"
CACHE_REL = ".cache/score.json"
WEIGHT_RE = re.compile(r"^WEIGHT\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.M)

RESTORED = "RESTORED"
SINGLE_SIGNAL_REJECTED = "SINGLE_SIGNAL_REJECTED"
NOT_RESTORED = "NOT_RESTORED"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def read_weight(repo: Path) -> float:
    text = (repo / KERNEL_REL).read_text(encoding="utf-8")
    match = WEIGHT_RE.search(text)
    if match is None:
        raise ValueError(f"no WEIGHT assignment in {KERNEL_REL}")
    return float(match.group(1))


def worktree_files(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        rel = path.relative_to(repo).as_posix()
        out[rel] = sha256_bytes(path.read_bytes())
    return out


def measure_variance_floor(repo: Path, n: int = 10) -> dict[str, Any]:
    values = [read_weight(repo) for _ in range(n)]
    mean = statistics.fmean(values)
    std = statistics.pstdev(values)
    return {
        "n": n,
        "values": values,
        "mean": mean,
        "std": std,
        "floor": std,
        "source": (
            "fixture-null-delta: identical config repeated n times on the "
            "isolated kernel. Live TST-0297/B03 variance-floor record is ABSENT."
        ),
    }


def combine(bench_ok: bool, path_ok: bool) -> str:
    if bench_ok and path_ok:
        return RESTORED
    if bench_ok or path_ok:
        return SINGLE_SIGNAL_REJECTED
    return NOT_RESTORED


def gate_truth_table() -> list[dict[str, Any]]:
    rows = []
    for bench_ok, path_ok, want in (
        (True, True, RESTORED),
        (True, False, SINGLE_SIGNAL_REJECTED),
        (False, True, SINGLE_SIGNAL_REJECTED),
        (False, False, NOT_RESTORED),
    ):
        got = combine(bench_ok, path_ok)
        rows.append(
            {
                "bench_ok": bench_ok,
                "path_ok": path_ok,
                "got": got,
                "want": want,
                "pass": got == want,
            }
        )
    return rows


def init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "tst-0312@local")
    git(root, "config", "user.name", "TST-0312")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.autocrlf", "false")


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def build_baseline(repo: Path) -> dict[str, Any]:
    init_repo(repo)
    src = repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    kernel = (FIXTURES / "kernel_baseline.py").read_bytes()
    (repo / KERNEL_REL).write_bytes(kernel)
    sha = commit_all(repo, "baseline: WEIGHT=10")
    floor = measure_variance_floor(repo)
    metric = read_weight(repo)
    tree = worktree_files(repo)
    record = {
        "id": "B08-fixture-TST-0312",
        "commit_sha": sha,
        "dirty": git(repo, "status", "--porcelain").stdout.strip() != "",
        "provisional": False,
        "metric_name": "kernel_weight",
        "metric": metric,
        "variance_floor": floor,
        "tree": tree,
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "impl": platform.python_implementation(),
        },
        "source": (
            "isolated fixture git repo. Live TST-0302/B08 immutable baseline "
            "records and tools/bench/ are ABSENT on this worktree."
        ),
    }
    if record["dirty"]:
        record["provisional"] = True
        raise RuntimeError("baseline captured dirty; record would be PROVISIONAL")
    if record["metric"] != 10.0:
        raise RuntimeError(f"baseline metric {record['metric']} != 10.0")
    return record


def apply_real_change(repo: Path, write_cache: bool = False) -> str:
    changed = (FIXTURES / "kernel_changed.py").read_bytes()
    (repo / KERNEL_REL).write_bytes(changed)
    sha = commit_all(repo, "change: WEIGHT=25")
    if write_cache:
        cache = repo / CACHE_REL
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes((FIXTURES / "cache_residue.json").read_bytes())
    return sha


def checkout_tracked(repo: Path, sha: str, paths: list[str]) -> None:
    git(repo, "checkout", sha, "--", *paths)


def path_signal(
    repo: Path, baseline: dict[str, Any]
) -> dict[str, Any]:
    pre = str(baseline["commit_sha"])
    diff = git(repo, "diff", "--name-only", pre, "--", KERNEL_REL).stdout.split()
    now = worktree_files(repo)
    base_tree: dict[str, str] = dict(baseline["tree"])
    extra = sorted(set(now) - set(base_tree))
    missing = sorted(set(base_tree) - set(now))
    changed = sorted(
        rel for rel in base_tree if rel in now and now[rel] != base_tree[rel]
    )
    path_ok = not diff and not extra and not missing and not changed
    return {
        "ok": path_ok,
        "pre_change_sha": pre,
        "git_diff_paths": diff,
        "extra": extra,
        "missing": missing,
        "content_changed": changed,
        "residue": extra,
    }


def bench_signal(repo: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    current = read_weight(repo)
    floor = float(baseline["variance_floor"]["floor"])
    base = float(baseline["metric"])
    delta = current - base
    return {
        "ok": abs(delta) <= floor,
        "current": current,
        "baseline": base,
        "delta": delta,
        "floor": floor,
    }


def evaluate(repo: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    bench = bench_signal(repo, baseline)
    path = path_signal(repo, baseline)
    verdict = combine(bool(bench["ok"]), bool(path["ok"]))
    return {
        "benchmark": bench,
        "path": path,
        "verdict": verdict,
        "restored": verdict == RESTORED,
        "single_signal": verdict == SINGLE_SIGNAL_REJECTED,
    }


def materialize_tree(repo: Path, tree_bytes: dict[str, bytes]) -> None:
    live = worktree_files(repo)
    want = set(tree_bytes)
    for rel in list(live):
        if rel not in want:
            (repo / rel).unlink()
    for rel, data in tree_bytes.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def snapshot_bytes(repo: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for rel in worktree_files(repo):
        out[rel] = (repo / rel).read_bytes()
    return out


def scenario_restore_real_change(work: Path) -> dict[str, Any]:
    """Revert a real change; both signals must agree the baseline is restored."""
    repo = work / "restore"
    baseline = build_baseline(repo)
    pre_tree = snapshot_bytes(repo)
    changed_sha = apply_real_change(repo, write_cache=False)
    mid = evaluate(repo, baseline)
    if mid["restored"]:
        raise RuntimeError("change was invisible to the two-signal checker")
    checkout_tracked(repo, str(baseline["commit_sha"]), [KERNEL_REL])
    # Tracked checkout of a committed change leaves the index/worktree
    # matching baseline for KERNEL_REL; no untracked residue in this scenario.
    post = evaluate(repo, baseline)
    return {
        "id": "restore-real-change",
        "baseline_sha": baseline["commit_sha"],
        "changed_sha": changed_sha,
        "pre_change_tree_files": sorted(pre_tree),
        "during_change": {
            "verdict": mid["verdict"],
            "benchmark_delta": mid["benchmark"]["delta"],
            "path_extra": mid["path"]["extra"],
            "path_content_changed": mid["path"]["content_changed"],
        },
        "after_revert": post,
        "pass": post["restored"]
        and post["benchmark"]["ok"]
        and post["path"]["ok"]
        and not post["single_signal"],
        "both_signals_agree_restored": post["restored"],
    }


def scenario_residue(work: Path) -> dict[str, Any]:
    """Checkout tracked files but leave a generated cache; residue must fire."""
    repo = work / "residue"
    baseline = build_baseline(repo)
    apply_real_change(repo, write_cache=True)
    if not (repo / CACHE_REL).is_file():
        raise RuntimeError("cache residue was not planted")
    checkout_tracked(repo, str(baseline["commit_sha"]), [KERNEL_REL])
    post = evaluate(repo, baseline)
    bench_only = combine(True, False)  # what a metric-only gate would emit
    absorbed = post["benchmark"]["ok"] and not post["path"]["ok"]
    return {
        "id": "residue-control",
        "after_tracked_checkout": post,
        "residue_paths": post["path"]["residue"],
        "cache_still_present": (repo / CACHE_REL).is_file(),
        "detected_not_absorbed": (
            post["verdict"] == SINGLE_SIGNAL_REJECTED
            and absorbed
            and CACHE_REL in post["path"]["residue"]
        ),
        "bench_only_would_claim": bench_only,
        "pass": (
            post["verdict"] == SINGLE_SIGNAL_REJECTED
            and absorbed
            and CACHE_REL in post["path"]["residue"]
            and post["benchmark"]["ok"]
            and not post["path"]["ok"]
        ),
    }


def scenario_single_signal_gate() -> dict[str, Any]:
    rows = gate_truth_table()
    return {
        "id": "single-signal-gate",
        "rows": rows,
        "or_is_rejected": all(
            r["pass"] for r in rows if not (r["bench_ok"] and r["path_ok"])
        ),
        "pass": all(r["pass"] for r in rows),
    }


def scenario_invertible(work: Path) -> dict[str, Any]:
    """Revert of a revert returns to the changed bytes (operation is not lossy)."""
    repo = work / "invert"
    baseline = build_baseline(repo)
    baseline_bytes = snapshot_bytes(repo)
    apply_real_change(repo, write_cache=False)
    changed_bytes = snapshot_bytes(repo)
    changed_metric = read_weight(repo)
    # Revert to baseline by materializing the recorded pre-change tree.
    materialize_tree(repo, baseline_bytes)
    git(repo, "add", "-A")
    reverted_sha = commit_all(repo, "revert to baseline snapshot")
    after_revert = evaluate(repo, baseline)
    # Revert of that revert: materialize the recorded changed tree.
    materialize_tree(repo, changed_bytes)
    git(repo, "add", "-A")
    restored_change_sha = commit_all(repo, "revert of revert")
    back = worktree_files(repo)
    want = {rel: sha256_bytes(data) for rel, data in changed_bytes.items()}
    metric_back = read_weight(repo)
    return {
        "id": "revert-of-revert",
        "after_first_revert_restored": after_revert["restored"],
        "first_revert_sha": reverted_sha,
        "second_revert_sha": restored_change_sha,
        "changed_metric": changed_metric,
        "metric_after_revert_of_revert": metric_back,
        "tree_matches_changed_state": back == want,
        "lossy": back != want,
        "pass": (
            after_revert["restored"]
            and back == want
            and metric_back == changed_metric
            and metric_back == 25.0
        ),
    }


def run_all(work: Path) -> dict[str, Any]:
    gate = scenario_single_signal_gate()
    restore = scenario_restore_real_change(work)
    residue = scenario_residue(work)
    invert = scenario_invertible(work)
    ok = bool(
        gate["pass"] and restore["pass"] and residue["pass"] and invert["pass"]
    )
    return {
        "ok": ok,
        "gate": gate,
        "restore": restore,
        "residue": residue,
        "invert": invert,
        "tools_bench_present": (HERE.parents[3] / "tools" / "bench").is_dir(),
        "live_b08_records_present": False,
        "live_b03_floor_present": False,
    }


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tst0312-self-") as tmp:
        result = run_all(Path(tmp))
    print(json.dumps({k: result[k] for k in ("ok", "tools_bench_present")}, sort_keys=True))
    print(
        "restore={restore} residue={residue} invert={invert} gate={gate}".format(
            restore=result["restore"]["pass"],
            residue=result["residue"]["pass"],
            invert=result["invert"]["pass"],
            gate=result["gate"]["pass"],
        )
    )
    if not result["ok"]:
        print("FAILED:TST-0312 revert_restore self-check")
        return 1
    print("SUCCESS:TST-0312 revert_restore self-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
