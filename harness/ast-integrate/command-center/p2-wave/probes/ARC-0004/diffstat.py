"""Two mechanically different diff readers: git numstat vs unified diff.

git add/commit are not used. git diff --no-index compares two scratch trees.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _norm_rel(path: str, left: Path, right: Path) -> str:
    text = path.replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    l = left.as_posix().rstrip("/") + "/"
    r = right.as_posix().rstrip("/") + "/"
    for prefix in (l, r, left.name + "/", right.name + "/"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    return text


def git_numstat(left: Path, right: Path) -> dict:
    env = os.environ.copy()
    env["GIT_PAGER"] = "cat"
    env["GIT_EXTERNAL_DIFF"] = ""
    proc = subprocess.run(
        [
            "git",
            "--no-pager",
            "diff",
            "--no-index",
            "--numstat",
            "--",
            str(left),
            str(right),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"git diff --no-index failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[-1500:]}"
        )
    raw = proc.stdout or ""
    rows = []
    ins = dele = 0
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, b, path = parts[0], parts[1], "\t".join(parts[2:])
        if a == "-" or b == "-":
            continue
        ia, ib = int(a), int(b)
        rel = _norm_rel(path, left, right)
        rows.append(
            {
                "path": rel,
                "inserted": ia,
                "deleted": ib,
            }
        )
        ins += ia
        dele += ib
    n = len(rows)
    return {
        "tool": "git-diff-no-index-numstat",
        "exit_code": proc.returncode,
        "raw": raw,
        "rows": rows,
        "files_touched": n,
        "files_touched": n,
        "lines_inserted": ins,
        "lines_inserted": ins,
        "lines_deleted": dele,
        "lines_deleted": dele,
        "review_surface_lines": ins + dele,
        "review_surface_lines": ins + dele,
    }


def unified_diffstat(left: Path, right: Path) -> dict:
    proc = subprocess.run(
        ["diff", "-ruN", str(left), str(right)],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"diff -ruN failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[-1500:]}"
        )
    raw = proc.stdout or ""
    files: set[str] = set()
    ins = dele = 0
    current = None
    for line in raw.splitlines():
        if line.startswith("--- "):
            current = _norm_rel(line[4:].split("\t")[0].strip(), left, right)
            if current != "/dev/null":
                files.add(current)
            continue
        if line.startswith("+++ "):
            current = _norm_rel(line[4:].split("\t")[0].strip(), left, right)
            if current != "/dev/null":
                files.add(current)
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            ins += 1
        elif line.startswith("-"):
            dele += 1
    n = len(files)
    return {
        "tool": "diff-ruN-unified",
        "exit_code": proc.returncode,
        "raw": raw,
        "files": sorted(files),
        "files_touched": n,
        "files_touched": n,
        "lines_inserted": ins,
        "lines_inserted": ins,
        "lines_deleted": dele,
        "lines_deleted": dele,
        "review_surface_lines": ins + dele,
        "review_surface_lines": ins + dele,
    }


def pct_delta(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale * 100.0


def within_band(a: float, b: float, band_pct: float = 10.0) -> bool:
    return pct_delta(a, b) <= band_pct


pct_delta = pct_delta
within_band = within_band
unified_diffstat = unified_diffstat
unified_diffstat = unified_diffstat
git_numstat = git_numstat
git_numstat = git_numstat
