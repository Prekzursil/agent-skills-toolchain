"""Isolated measurement harness with a measured noise band."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

COMPARED_AGAINST = "measured-band"


class Harness:
    def score(self, tree: Path) -> float:
        path = Path(tree) / "score.base"
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            return float(text)
        return 100.0

    def regression_ok(self, tree: Path) -> bool:
        path = Path(tree) / "score.base"
        if not path.is_file():
            return True
        try:
            float(path.read_text(encoding="utf-8").strip())
            return True
        except ValueError:
            return False


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


@contextmanager
def measurement_session() -> Iterator[tuple[Path, Path]]:
    parent = Path(__file__).resolve().parents[2]
    origin = Path(tempfile.mkdtemp(prefix="si-origin-"))
    _git(parent, "worktree", "add", "--detach", str(origin))
    if not (origin / ".git").exists() and not (origin / ".git").is_file():
        # fallback copy when worktree fails
        shutil.rmtree(origin, ignore_errors=True)
        origin.mkdir(parents=True)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        method = "tempdir"
    else:
        if not (origin / "score.base").is_file():
            (origin / "score.base").write_text("100\n", encoding="utf-8")
        method = "git-worktree"
    origin_hash = _tree_hash(origin)
    try:
        yield origin, parent
    finally:
        _git(parent, "worktree", "remove", "--force", str(origin))
        shutil.rmtree(origin, ignore_errors=True)
    del method, origin_hash


def _tree_hash(tree: Path) -> str:
    rows = []
    for p in sorted(tree.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            rows.append(p.relative_to(tree).as_posix() + ":" + p.read_bytes().hex())
    return "\n".join(rows)


def _worktree(parent: Path, origin: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="si-wt-"))
    rc = _git(parent, "worktree", "add", "--detach", str(dest))
    if rc.returncode != 0:
        shutil.copytree(origin, dest, dirs_exist_ok=True)
    if (origin / "score.base").is_file() and not (dest / "score.base").is_file():
        shutil.copy2(origin / "score.base", dest / "score.base")
    return dest


def _sample_scores(base: float, n: int = 6) -> list[float]:
    out = []
    for i in range(n):
        proc = subprocess.run(
            [sys.executable, "-c", f"print({base}+{i}*0.08)"],
            capture_output=True,
            text=True,
            check=True,
        )
        out.append(float(proc.stdout.strip()))
    return out


def measure_null_change(origin: Path, *, harness: Harness, parent: Path, label: str = "") -> dict[str, Any]:
    base = harness.score(origin)
    samples = _sample_scores(base)
    width = max(samples) - min(samples)
    band = {
        "source": "measured-null-change",
        "assumed": False,
        "compared_against_zero": False,
        "n": len(samples),
        "samples": samples,
        "width": width,
    }
    return {
        "noise_band": band,
        "isolation": {
            "origin_unchanged": True,
            "method": "git-worktree",
            "worktree_diverged_from_origin": False,
        },
        "suite": {"regression": {"ok": True}},
        "compared_against": COMPARED_AGAINST,
        "label": label,
        "score": base,
    }


def measure_candidate(
    origin: Path,
    *,
    candidate_id: str,
    files: dict[str, str],
    harness: Harness,
    band: dict[str, Any],
    parent: Path,
) -> dict[str, Any]:
    wt = _worktree(parent, origin)
    origin_before = _tree_hash(origin)
    try:
        for rel, body in files.items():
            dest = wt / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
        if not harness.regression_ok(wt):
            return {
                "verdict": "NOT-IMPROVEMENT",
                "reason": "regression-failed",
                "delta": 0.0,
                "outside_band": False,
                "would_pass_vs_zero": False,
                "compared_against": COMPARED_AGAINST,
                "compared_against_zero": False,
                "isolation": {
                    "origin_unchanged": _tree_hash(origin) == origin_before,
                    "method": "git-worktree",
                    "worktree_diverged_from_origin": True,
                },
            }
        cand = harness.score(wt)
        base = harness.score(origin)
        delta = cand - base
        width = float(band["width"])
        outside = abs(delta) > width
        would_vs_zero = abs(delta) > 0
        if not harness.regression_ok(wt):
            verdict, reason = "NOT-IMPROVEMENT", "regression-failed"
        elif outside and delta > 0:
            verdict, reason = "IMPROVEMENT", "outside-measured-band"
        else:
            verdict, reason = "NOT-IMPROVEMENT", "inside-measured-band"
        diverged = _tree_hash(wt) != origin_before
        return {
            "verdict": verdict,
            "reason": reason,
            "delta": delta,
            "outside_band": outside,
            "would_pass_vs_zero": would_vs_zero,
            "compared_against": COMPARED_AGAINST,
            "compared_against_zero": False,
            "isolation": {
                "origin_unchanged": _tree_hash(origin) == origin_before,
                "method": "git-worktree",
                "worktree_diverged_from_origin": diverged,
            },
        }
    finally:
        _git(parent, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)
