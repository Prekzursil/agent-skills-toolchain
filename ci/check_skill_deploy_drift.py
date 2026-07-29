"""L10 skill-deploy drift reporter -- the missing vault->live half of the sync architecture.

WHY THIS EXISTS
---------------
The repo already ships three sync scripts and NONE of them can answer "is the
LOADED skill set stale?":

  * ``scripts/sync-skills.ps1``   repo ``skills/``          -> ``~/.agents/skills``
  * ``scripts/sync-from-live.ps1`` ``~/.agents/skills``     -> repo ``.agents/skills``
  * ``ci/check_skill_dual_write.py`` repo ``skills/``  <->  repo ``.agents/skills``

``~/.claude/skills`` is a SYMLINK to ``~/.claude/skills.daily``, and that curated
subset is what Claude actually loads each session.  MEASURED 2026-07-29: not one
script in ``scripts/`` or ``ci/`` writes to ``skills.daily`` (probe:
``Select-String -Path scripts/* ci/* -Pattern 'skills\\.daily' -SimpleMatch`` ->
0 hits).  The deploy step into the loaded tree is performed BY HAND, which is why
it drifts.

WHY IT REPORTS AND REFUSES TO COPY
----------------------------------
The obvious "fix" -- copy the vault over the live tree -- is DESTRUCTIVE here.
Measured across the 79 shared skills of the live tree: 37 identical, **0 where
the vault is a strict superset**, 8 live-ahead and 34 diverged.  A blind
vault->live sync would have destroyed live-unique content in 42 of 79 skills.
Concretely, ``codex-databricks-fanout/SKILL.md`` is 214 live lines vs 335 vault
lines -- which looks like pure staleness -- yet the live copy holds 61 unique
non-blank lines the vault does not, including a whole ``## 9. Harness paths``
section and a measured 48-way fan-out result.

So direction is derived TWO-DIRECTIONALLY from unique-line sets and the tool
emits a ``safe_to_deploy`` list that contains only files where one side is a
strict superset of the other.  Everything else is a human merge.  mtime is never
consulted: a copy updates mtime without changing content, so mtime measures the
last COPY, not the newer CONTENT.

Line endings are normalised (CRLF/CR -> LF) before every comparison, because the
live tree is written by Windows editors and the repo blob is LF
(``rules/common/windows-shell.md`` #8b).

Exit codes:
    0  no drift (or, with --require-safe, nothing unsafe to deploy)
    1  drift found
    2  usage error

Usage:
    # Is the loaded set stale against the canonical vault?
    python ci/check_skill_deploy_drift.py \
        --left ~/.claude/skills.daily --right ~/.agents/skills

    # Machine-readable, for a deploy wrapper to consume.
    python ci/check_skill_deploy_drift.py --left A --right B --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

#: Directory names that never carry skill CONTENT.  Excluded from every verdict
#: so a lint cache cannot be reported as authored work.
NOISE_DIRS = frozenset(
    {".git", ".ruff_cache", "__pycache__", "node_modules", ".pytest_cache", ".venv"}
)

#: Filename shapes that are byproducts, not content.  ``.bak-<tag>`` snapshots and
#: the Windows ``Zone.Identifier`` alternate-data-stream artifact both showed up in
#: the live tree and would otherwise inflate the live-ahead count.
NOISE_SUFFIXES = ("Zone.Identifier",)
NOISE_INFIXES = (".bak-",)

IDENTICAL = "IDENTICAL"
LEFT_AHEAD = "LEFT-AHEAD"
RIGHT_AHEAD = "RIGHT-AHEAD"
DIVERGED = "DIVERGED"
REORDER_ONLY = "REORDER-ONLY"
LEFT_ONLY_FILE = "LEFT-ONLY-FILE"
RIGHT_ONLY_FILE = "RIGHT-ONLY-FILE"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2


def normalise(data: bytes) -> bytes:
    """Collapse CRLF and lone CR to LF so EOL style is never mistaken for drift."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def is_noise(rel: str) -> bool:
    """True when a skill-relative path is a byproduct rather than content."""
    parts = rel.split("/")
    if any(part in NOISE_DIRS for part in parts):
        return True
    leaf = parts[-1]
    return leaf.endswith(NOISE_SUFFIXES) or any(inf in leaf for inf in NOISE_INFIXES)


def read_normalised(path: Path) -> bytes | None:
    """Normalised bytes, or ``None`` when the path cannot be read.

    ``None`` is never treated as equal to another ``None``: two unreadable files
    comparing equal is the defect ``sync-from-live.ps1`` documents as
    "TWO UNREADABLE FILES COMPARED EQUAL".
    """
    try:
        return normalise(path.read_bytes())
    except OSError:
        return None


def content_digest(path: Path) -> str | None:
    data = read_normalised(path)
    return None if data is None else hashlib.sha256(data).hexdigest()


def significant_lines(data: bytes) -> set[str]:
    """Distinct non-blank lines, for the two-directional direction test."""
    text = data.decode("utf-8", errors="replace")
    return {line for line in text.split("\n") if line.strip()}


def classify_pair(left: Path, right: Path) -> str:
    """Direction of difference between two counterpart files.

    Derived from unique-line SET membership in BOTH directions.  A one-directional
    read cannot see two-directional divergence -- the measured blind spot that made
    six LLM agents misclassify 31 diverged files as safe to overwrite.
    """
    left_data = read_normalised(left)
    right_data = read_normalised(right)
    if left_data is None or right_data is None:
        return DIVERGED
    if left_data == right_data:
        return IDENTICAL
    left_lines = significant_lines(left_data)
    right_lines = significant_lines(right_data)
    left_only = left_lines - right_lines
    right_only = right_lines - left_lines
    if not left_only and not right_only:
        return REORDER_ONLY
    if left_only and right_only:
        return DIVERGED
    return LEFT_AHEAD if left_only else RIGHT_AHEAD


def skill_names(root: Path) -> set[str]:
    """Directories under ``root`` that hold a ``SKILL.md``."""
    if not root.is_dir():
        return set()
    return {d.name for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").is_file()}


def skill_files(root: Path, name: str, include_noise: bool = False) -> dict[str, Path]:
    """``{skill-relative posix path: absolute Path}`` for one skill."""
    base = root / name
    out: dict[str, Path] = {}
    if not base.is_dir():
        return out
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        if not include_noise and is_noise(rel):
            continue
        out[rel] = path
    return out


def _folded(verdicts: set[str]) -> str:
    """Fold per-file verdicts into one verdict for the whole skill."""
    if not verdicts:
        return IDENTICAL
    if verdicts == {REORDER_ONLY}:
        return REORDER_ONLY
    left = bool(verdicts & {LEFT_AHEAD, LEFT_ONLY_FILE})
    right = bool(verdicts & {RIGHT_AHEAD, RIGHT_ONLY_FILE})
    if DIVERGED in verdicts or (left and right):
        return DIVERGED
    return LEFT_AHEAD if left else RIGHT_AHEAD


def compare_skill(
    left_root: Path, right_root: Path, name: str, include_noise: bool = False
) -> dict[str, str]:
    """Per-file verdicts for one skill.  Identical files are omitted."""
    left = skill_files(left_root, name, include_noise)
    right = skill_files(right_root, name, include_noise)
    files: dict[str, str] = {}
    for rel in sorted(set(left) | set(right)):
        if rel not in left:
            files[rel] = RIGHT_ONLY_FILE
        elif rel not in right:
            files[rel] = LEFT_ONLY_FILE
        else:
            verdict = classify_pair(left[rel], right[rel])
            if verdict != IDENTICAL:
                files[rel] = verdict
    return files


def reconcile(
    left_root: Path, right_root: Path, include_noise: bool = False
) -> dict[str, object]:
    """Full two-directional report between two skill roots."""
    left_names = skill_names(left_root)
    right_names = skill_names(right_root)
    shared = sorted(left_names & right_names)

    skills: dict[str, object] = {}
    summary = {
        IDENTICAL: 0,
        LEFT_AHEAD: 0,
        RIGHT_AHEAD: 0,
        DIVERGED: 0,
        REORDER_ONLY: 0,
    }
    safe_to_deploy: list[str] = []
    needs_merge: list[str] = []

    for name in shared:
        files = compare_skill(left_root, right_root, name, include_noise)
        verdict = _folded(set(files.values()))
        summary[verdict] += 1
        skills[name] = {"verdict": verdict, "files": files}
        for rel, file_verdict in files.items():
            target = f"{name}/{rel}"
            if file_verdict in (RIGHT_AHEAD, RIGHT_ONLY_FILE):
                safe_to_deploy.append(target)
            elif file_verdict in (DIVERGED, LEFT_AHEAD, LEFT_ONLY_FILE):
                needs_merge.append(target)

    return {
        "left_root": str(left_root),
        "right_root": str(right_root),
        "left_skill_count": len(left_names),
        "right_skill_count": len(right_names),
        "shared_skill_count": len(shared),
        "left_only_skills": sorted(left_names - right_names),
        "right_only_skills": sorted(right_names - left_names),
        "summary": summary,
        "safe_to_deploy": sorted(safe_to_deploy),
        "needs_merge": sorted(needs_merge),
        "skills": skills,
    }


def _report(report: dict[str, object]) -> None:
    summary = report["summary"]
    assert isinstance(summary, dict)
    print(f"LEFT  {report['left_root']}  ({report['left_skill_count']} skills)")
    print(f"RIGHT {report['right_root']}  ({report['right_skill_count']} skills)")
    print(f"shared: {report['shared_skill_count']}")
    for key in (IDENTICAL, RIGHT_AHEAD, LEFT_AHEAD, DIVERGED, REORDER_ONLY):
        print(f"  {key:14s} {summary[key]}")
    safe = report["safe_to_deploy"]
    merge = report["needs_merge"]
    assert isinstance(safe, list) and isinstance(merge, list)
    print(f"\nSAFE TO DEPLOY right->left ({len(safe)} files):")
    for rel in safe:
        print(f"  + {rel}")
    print(f"\nNEEDS A HUMAN MERGE ({len(merge)} files) -- never blind-copy these:")
    for rel in merge:
        print(f"  ! {rel}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="skill deploy drift reporter")
    ap.add_argument("--left", required=True, help="the DEPLOYED/loaded tree")
    ap.add_argument("--right", required=True, help="the tree claimed authoritative")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--include-noise",
        action="store_true",
        help="count caches and .bak- snapshots as content (default: excluded)",
    )
    ap.add_argument(
        "--require-safe",
        action="store_true",
        help="exit 0 unless a file needs a human merge (a deploy wrapper's precondition)",
    )
    ns = ap.parse_args(argv)

    left_root = Path(ns.left).expanduser()
    right_root = Path(ns.right).expanduser()
    for root in (left_root, right_root):
        if not root.is_dir():
            sys.stderr.write(f"not a directory: {root}\n")
            return EXIT_USAGE

    report = reconcile(left_root, right_root, ns.include_noise)
    if ns.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _report(report)

    needs_merge = report["needs_merge"]
    safe = report["safe_to_deploy"]
    assert isinstance(needs_merge, list) and isinstance(safe, list)
    if ns.require_safe:
        return EXIT_OK if not needs_merge else EXIT_DRIFT
    return EXIT_OK if not needs_merge and not safe else EXIT_DRIFT


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
