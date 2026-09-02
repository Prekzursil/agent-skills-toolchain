#!/usr/bin/env python3
"""Fixture git repo, condition-6 receipts, git cat-file, and shape-only control.

Signal (a): live `_c6_evidence` via `evaluate(..., scope=[6])` against the
fixture worktree (filesystem at the recorded revision).
Signal (b): independent `git cat-file -p <rev>:<path>` plus line count.
Negative control: a regex that only checks `path:digits` accepts off-by-1000.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "platform" / "lib"
sys.path.insert(0, str(LIB))

import completion_predicate as cp  # noqa: E402

UNIT = "TST-0147"
OUT_REL = "command-center/receipts/TST-0147.json"
SENTINEL = "SUCCESS:TST-0147"
FIXTURE_LINES = 20
GOOD_LINE = 10
OFF_BY_1000 = GOOD_LINE + 1000
TARGET_REL = "anchor_target.txt"
MISSING_REL = "no-such-tst-0147.txt"
SHAPE_ONLY = re.compile(r"^.+:\d+$")
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0147/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0147/probe2_cat_file_and_shape.py"
)


def git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_AUTHOR_NAME"] = "TST-0147"
    env["GIT_AUTHOR_EMAIL"] = "tst-0147@invalid"
    env["GIT_COMMITTER_NAME"] = "TST-0147"
    env["GIT_COMMITTER_EMAIL"] = "tst-0147@invalid"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _git(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        timeout=20,
        env=env,
    )


@contextmanager
def fixture_git_repo() -> Iterator[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0147-git-"))
    env = git_env(tmp)
    try:
        lines = [f"anchor-line-{i:02d}" for i in range(1, FIXTURE_LINES + 1)]
        (tmp / TARGET_REL).write_text("\n".join(lines) + "\n", encoding="utf-8")
        init = _git(["-c", "init.defaultBranch=main", "init"], tmp, env)
        if init.returncode != 0:
            raise RuntimeError((init.stderr or b"").decode("utf-8", "replace"))
        add = _git(["add", TARGET_REL], tmp, env)
        if add.returncode != 0:
            raise RuntimeError((add.stderr or b"").decode("utf-8", "replace"))
        commit = _git(
            ["-c", "commit.gpgsign=false", "commit", "-m", "tst-0147 fixture"],
            tmp,
            env,
        )
        if commit.returncode != 0:
            raise RuntimeError((commit.stderr or b"").decode("utf-8", "replace"))
        rev_p = _git(["rev-parse", "HEAD"], tmp, env)
        rev = (rev_p.stdout or b"").decode("utf-8").strip()
        yield {
            "root": tmp,
            "rev": rev,
            "path": TARGET_REL,
            "line_count": FIXTURE_LINES,
            "good_line": GOOD_LINE,
            "bad_line": OFF_BY_1000,
            "good_text": f"anchor-line-{GOOD_LINE:02d}",
            "missing_path": MISSING_REL,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def two_probes(path: str) -> list[dict]:
    return [
        {"role": "source", "method": "file-read", "command": f"stat {path}"},
        {"role": "verifier", "method": "sha256", "command": f"sha256sum {path}"},
    ]


def evidence_receipt(anchor: str) -> dict:
    path = anchor.rsplit(":", 1)[0]
    return {
        "state": "SUCCESS",
        "evidence": [
            {
                "claim": "fixture file:line names live evidence",
                "verdict": "CONFIRMED",
                "anchor": anchor,
                "probes": two_probes(path),
            }
        ],
    }


def condition6(repo: Path, anchor: str) -> dict:
    verdict = cp.evaluate(evidence_receipt(anchor), repo=repo, scope=[6])
    row = next(c for c in verdict.conditions if c.n == 6)
    return {
        "anchor": anchor,
        "outcome": row.outcome,
        "basis": row.basis,
        "verdict": verdict.verdict,
        "evidence_pointer": row.evidence_pointer,
        "resolver": cp.resolve_file_line(repo, *cp.parse_file_line_anchor(anchor)),
    }


def shape_only_accepts(anchor: str) -> bool:
    """Known-broken checker: regex on path:digits, no blob or line count."""
    return bool(SHAPE_ONLY.fullmatch((anchor or "").strip()))


def cat_file(cwd: Path, rev: str, path: str) -> dict:
    spec = f"{rev}:{path}"
    proc = subprocess.run(
        ["git", "-C", str(cwd), "cat-file", "-p", spec],
        capture_output=True,
        timeout=20,
    )
    stdout = proc.stdout or b""
    stderr = (proc.stderr or b"").decode("utf-8", "replace")
    return {
        "command": f"git cat-file -p {spec}",
        "spec": spec,
        "returncode": int(proc.returncode),
        "stdout_bytes": stdout,
        "stderr": stderr[-400:],
    }


def classify_cat_file(blob: dict, line: int) -> dict:
    if blob["returncode"] != 0:
        return {
            "classification": "MISSING",
            "line_count": 0,
            "blob_line": None,
            "command": blob["command"],
            "spec": blob["spec"],
            "returncode": blob["returncode"],
            "stderr": blob["stderr"],
        }
    n = cp._line_count(blob["stdout_bytes"])
    text = blob["stdout_bytes"].replace(b"\r\n", b"\n").decode("utf-8", "replace").splitlines()
    if line < 1 or line > n:
        cls = "BEYOND-EOF"
        blob_line = None
    else:
        cls = "OK"
        blob_line = text[line - 1]
    return {
        "classification": cls,
        "line_count": n,
        "blob_line": blob_line,
        "command": blob["command"],
        "spec": blob["spec"],
        "returncode": blob["returncode"],
    }


def git_resolve(cwd: Path, rev: str, path: str, line: int) -> dict:
    return classify_cat_file(cat_file(cwd, rev, path), line)


def measure_condition6() -> dict:
    """Probe-1 payload: both-states of live condition 6 (filesystem resolver)."""
    with fixture_git_repo() as fx:
        good_a = f"{fx['path']}:{fx['good_line']}"
        bad_a = f"{fx['path']}:{fx['bad_line']}"
        miss_a = f"{fx['missing_path']}:1"
        good = condition6(fx["root"], good_a)
        bad = condition6(fx["root"], bad_a)
        missing = condition6(fx["root"], miss_a)
        silent_on_good = good["outcome"] == cp.PASS
        fired_on_off_by_1000 = bad["outcome"] == cp.FALSE
        fired_on_missing = missing["outcome"] == cp.FALSE
        passed = silent_on_good and fired_on_off_by_1000 and fired_on_missing
        return {
            "method": "completion_predicate.evaluate scope=[6] against fixture worktree",
            "sut": "platform/lib/completion_predicate.py:_c6_evidence",
            "fixture_rev": fx["rev"],
            "fixture_path": fx["path"],
            "fixture_line_count": fx["line_count"],
            "good_line": fx["good_line"],
            "bad_line": fx["bad_line"],
            "good": good,
            "off_by_1000": bad,
            "missing": missing,
            "silent_on_good": silent_on_good,
            "fired_on_off_by_1000": fired_on_off_by_1000,
            "fired_on_missing": fired_on_missing,
            "pass": passed,
        }


def measure_git_and_shape() -> dict:
    """Probe-2 payload: git cat-file plus shape-only negative control."""
    with fixture_git_repo() as fx:
        good = git_resolve(fx["root"], fx["rev"], fx["path"], fx["good_line"])
        bad = git_resolve(fx["root"], fx["rev"], fx["path"], fx["bad_line"])
        missing = git_resolve(fx["root"], fx["rev"], fx["missing_path"], 1)
        good_a = f"{fx['path']}:{fx['good_line']}"
        bad_a = f"{fx['path']}:{fx['bad_line']}"
        miss_a = f"{fx['missing_path']}:1"
        shape_good = shape_only_accepts(good_a)
        shape_bad = shape_only_accepts(bad_a)
        shape_missing = shape_only_accepts(miss_a)
        blob_ok = good.get("blob_line") == fx["good_text"]
        git_ok = (
            good["classification"] == "OK"
            and bad["classification"] == "BEYOND-EOF"
            and missing["classification"] == "MISSING"
            and blob_ok
        )
        shape_fails_this_test = shape_bad is True and shape_missing is True
        passed = git_ok and shape_good is True and shape_fails_this_test
        return {
            "method": "git cat-file -p <rev>:<path> plus line-count",
            "fixture_rev": fx["rev"],
            "fixture_path": fx["path"],
            "fixture_line_count": fx["line_count"],
            "good_line": fx["good_line"],
            "bad_line": fx["bad_line"],
            "good_text": fx["good_text"],
            "good": {k: v for k, v in good.items() if k != "stdout_bytes"},
            "off_by_1000": {k: v for k, v in bad.items() if k != "stdout_bytes"},
            "missing": {k: v for k, v in missing.items() if k != "stdout_bytes"},
            "blob_text_ok": blob_ok,
            "git_ok": git_ok,
            "shape_only_accepts_good": shape_good,
            "shape_only_accepts_off_by_1000": shape_bad,
            "shape_only_accepts_missing": shape_missing,
            "shape_only_fails_this_test": shape_fails_this_test,
            "pass": passed,
        }


def measure() -> dict:
    c6 = measure_condition6()
    git = measure_git_and_shape()
    catalog_pass = bool(c6["pass"] and git["pass"])
    return {
        "condition6": c6,
        "git_and_shape": git,
        "catalog_pass": catalog_pass,
        "target_verdict": "CONFIRMED" if catalog_pass else "REFUTED",
    }
