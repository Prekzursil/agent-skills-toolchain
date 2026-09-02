#!/usr/bin/env python3
"""Probe 2: all three directions reported; independent os.walk matches.

A zero on any direction is accepted only when the same differ finds a
planted case of that class. EOL-only twins must not count as divergent.
Host trees are censused read-only; they are never mutated.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from differ import host_skill_roots, reconcile  # noqa: E402
from fixtures import (  # noqa: E402
    DIVERGENT_ID,
    EOL_ID,
    IDENTICAL_ID,
    LIVE_ONLY_ID,
    REPO_ONLY_ID,
    build_planted_pair,
)

SKIP = {".git", "__pycache__", ".mypy_cache", "node_modules", ".pytest_cache"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0083-probe2 {msg}")
    return 1


def lf_sha(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def independent_walk(root: Path) -> dict[str, str]:
    """Second census: os.walk + SKILL.md LF-hash. Does not import classify()."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        if "SKILL.md" not in filenames:
            continue
        skill_dir = Path(dirpath)
        rel = skill_dir.relative_to(root).as_posix()
        files: list[tuple[str, str]] = []
        for nested_dir, nested_names, nested_files in os.walk(skill_dir):
            nested_names[:] = [d for d in nested_names if d not in SKIP]
            nested_path = Path(nested_dir)
            if nested_path != skill_dir and "SKILL.md" in nested_files:
                nested_names[:] = []
                continue
            for name in nested_files:
                path = nested_path / name
                if not path.is_file():
                    continue
                rel_file = path.relative_to(skill_dir).as_posix()
                files.append((rel_file, lf_sha(path.read_bytes())))
        files.sort()
        payload = "".join(f"{k}={v}\n" for k, v in files).encode("utf-8")
        out[rel] = hashlib.sha256(payload).hexdigest()
    return out


def independent_classes(repo_root: Path, live_root: Path) -> dict[str, list[str]]:
    repo = independent_walk(repo_root)
    live = independent_walk(live_root)
    repo_ids, live_ids = set(repo), set(live)
    return {
        "repo_only": sorted(repo_ids - live_ids),
        "live_only": sorted(live_ids - repo_ids),
        "divergent": sorted(
            sid for sid in (repo_ids & live_ids) if repo[sid] != live[sid]
        ),
        "identical": sorted(
            sid for sid in (repo_ids & live_ids) if repo[sid] == live[sid]
        ),
    }


def zero_backed(count: int, planted_found: bool, label: str) -> dict[str, object]:
    return {
        "label": label,
        "count": count,
        "zero": count == 0,
        "planted_case_found": planted_found,
        "zero_allowed": (count > 0) or planted_found,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0083-p2-") as raw:
        roots = build_planted_pair(Path(raw))
        report = reconcile(roots["repo"], roots["live"])
        indep = independent_classes(roots["repo"], roots["live"])
        counts = report["counts"]
        repo_ids = [r["skill_id"] for r in report["repo_only"]]
        live_ids = [r["skill_id"] for r in report["live_only"]]
        div_ids = [r["skill_id"] for r in report["divergent"]]

        if counts["repo_only"] < 1 or counts["live_only"] < 1 or counts["divergent"] < 1:
            return fail(f"three directions not all non-zero: {counts}")
        if repo_ids != [REPO_ONLY_ID]:
            return fail(f"repo_only={repo_ids}")
        if live_ids != [LIVE_ONLY_ID]:
            return fail(f"live_only={live_ids}")
        if div_ids != [DIVERGENT_ID]:
            return fail(f"divergent={div_ids}")
        if IDENTICAL_ID not in report["identical"] or EOL_ID not in report["identical"]:
            return fail(f"identical missing twins: {report['identical']}")
        if EOL_ID in div_ids:
            return fail("EOL-only twin classified as content-divergent")

        if indep["repo_only"] != repo_ids:
            return fail(f"independent repo_only {indep['repo_only']} != {repo_ids}")
        if indep["live_only"] != live_ids:
            return fail(f"independent live_only {indep['live_only']} != {live_ids}")
        if indep["divergent"] != div_ids:
            return fail(f"independent divergent {indep['divergent']} != {div_ids}")

        empty = Path(raw) / "empty-a"
        empty_b = Path(raw) / "empty-b"
        empty.mkdir()
        empty_b.mkdir()
        empty_report = reconcile(empty, empty_b)
        if empty_report["counts"]["repo_only"] != 0:
            return fail("empty pair should have repo_only=0")
        empty_zero_ok = zero_backed(
            empty_report["counts"]["repo_only"],
            planted_found=(REPO_ONLY_ID in repo_ids),
            label="empty-repo-only",
        )
        if not empty_zero_ok["zero_allowed"]:
            return fail("empty zero was not backed by a planted case")

        host = host_skill_roots(REPO)
        host_pair = None
        host_counts = None
        repo_host = next(r for r in host if r["label"] == "repo-skills")
        live_host = next(r for r in host if r["label"] == "claude-live")
        if repo_host["is_dir"] or live_host["is_dir"]:
            host_pair = reconcile(Path(repo_host["path"]), Path(live_host["path"]))
            host_counts = host_pair["counts"]

        file_lists = {
            "repo_only": {r["skill_id"]: r["file_list"] for r in report["repo_only"]},
            "live_only": {r["skill_id"]: r["file_list"] for r in report["live_only"]},
            "divergent": {
                r["skill_id"]: {
                    "files_changed": r["files_changed"],
                    "file_list": r["file_list"],
                }
                for r in report["divergent"]
            },
        }
        payload = {
            "pass": True,
            "probe": "probe2-three-directions",
            "unit_id": "TST-0083",
            "counts": counts,
            "file_lists": file_lists,
            "identical": report["identical"],
            "independent_walk_matched": True,
            "eol_twin_not_divergent": True,
            "empty_zero_backed_by_plant": empty_zero_ok,
            "host_trees": host,
            "host_counts": host_counts,
            "routing": report["routing"],
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"counts repo_only={counts['repo_only']} "
            f"live_only={counts['live_only']} divergent={counts['divergent']} "
            f"eol_identical={EOL_ID in report['identical']}"
        )
        print("SUCCESS:TST-0083-probe2 all three directions reported")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
