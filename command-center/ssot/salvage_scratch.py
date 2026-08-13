"""Incrementally rescue files that exist ONLY in the no-remote scratch working copy.

WHY THIS EXISTS. `~/source/_advver_M14/scratch` is a working copy of this repo with ZERO commits
and NO remote. Nine concurrent lanes write artifacts into it -- including verification
deliverables. Anything unique there is one `rm -rf` from gone, and a retire-safe verdict was very
nearly published on that directory while it was under active write (see NO-REMOTE-REPO-TRIAGE.md).

WHAT "UNIQUE" MEANS HERE, precisely: the file's blob hash is absent from the CANONICAL object
store, which `git cat-file --batch-check` searches across all history -- not just HEAD. So a file
whose exact content was ever committed anywhere is skipped.

WHAT THIS DOES NOT DO. It does not modify, move or delete anything in the source directory, and it
does not decide whether the content matters. It copies bytes with metadata preserved and stops.
Judging the content is a human's job; the copies are snapshots of LIVE files and may be partial.

IDEMPOTENT: a file already present in the salvage directory with the same size is skipped, so this
can run every few minutes without churning the index.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRATCH = Path("C:/Users/Prekzursil/source/_advver_M14/scratch")
CANON = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
DEST = Path(__file__).resolve().parent / "salvaged-from-scratch"

#: Regenerable or vendored noise: never worth rescuing, and it dwarfs the real payload.
SKIP_PARTS = {
    ".git",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    ".pytest_cache",
}


def candidate_files() -> list[Path]:
    out = []
    for p in SCRATCH.rglob("*"):
        if not p.is_file():
            continue
        if SKIP_PARTS & set(p.relative_to(SCRATCH).parts):
            continue
        if p.suffix in {".pyc", ".pyo"}:
            continue
        out.append(p)
    return out


def blob_hashes(paths: list[Path]) -> list[str]:
    """git hash-object for many paths in ONE process (per-file spawns are far too slow)."""
    if not paths:
        return []
    stdin = "\n".join(str(p) for p in paths)
    r = subprocess.run(
        ["git", "hash-object", "--stdin-paths"],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return r.stdout.split()


def missing_from_canonical(shas: list[str]) -> set[str]:
    """Which of these blobs does the canonical store NOT have, anywhere in history?"""
    if not shas:
        return set()
    r = subprocess.run(
        [
            "git",
            "-C",
            str(CANON),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype)",
        ],
        input="\n".join(shas),
        capture_output=True,
        text=True,
    )
    missing = set()
    for line, sha in zip(r.stdout.splitlines(), shas):
        if "blob" not in line.split():
            missing.add(sha)
    return missing


def main() -> int:
    if not SCRATCH.is_dir():
        print(f"SUCCESS:salvage-scratch source absent, nothing to do ({SCRATCH})")
        return 0

    files = candidate_files()
    shas = blob_hashes(files)
    if len(shas) != len(files):
        # Fail closed: a misaligned zip would rescue the wrong files or skip real ones.
        print(
            f"FAILED:salvage-scratch hash count {len(shas)} != file count {len(files)} "
            "-- refusing to act on a misaligned mapping"
        )
        return 1

    missing = missing_from_canonical(shas)
    DEST.mkdir(parents=True, exist_ok=True)

    copied = skipped = 0
    total = 0
    for path, sha in zip(files, shas):
        if sha not in missing:
            continue
        rel = path.relative_to(SCRATCH)
        target = DEST / rel
        if target.exists() and target.stat().st_size == path.stat().st_size:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
        total += path.stat().st_size

    # Count FILES, not blob hashes. Two files with identical content share one sha, so
    # len(missing) undercounts and reads as a contradiction next to `copied` -- which is exactly
    # the shape of a broken detector even when it is benign. Report both, labelled.
    unique_files = sum(1 for sha in shas if sha in missing)
    print(
        f"  scanned {len(files)} file(s); {unique_files} file(s) unique to scratch "
        f"across {len(missing)} distinct blob(s)"
    )
    print(f"  copied {copied}, already current {skipped}, {total} byte(s) new")
    print(
        "  NOTE: previously salvaged content is now IN canonical, so it stops counting as "
        "unique. A file reappearing here means its content CHANGED since the last run."
    )
    print("SUCCESS:salvage-scratch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
