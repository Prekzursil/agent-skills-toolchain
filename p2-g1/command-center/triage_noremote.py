r"""Triage the two NO-REMOTE repos under source/_advver_M14: do they hold UNIQUE work?

The git-hygiene hook warns "this work exists nowhere else" for `chk` and `scratch`. That is a claim
about uniqueness, and it is testable: both have the same top-level layout as ast-integrate
(`agents`, `AGENTS.md`, `agent-self`, `ci`, `CLAUDE.md`, ...), so they look like working copies of
the toolchain rather than independent projects.

The owner standing decision on no-remote repos is TRIAGE FIRST, then decide -- explicitly do NOT
create remotes and do NOT push. So this measures and reports; it changes nothing, anywhere.

THE DISCRIMINATOR is the one lane B2 used for the monitorcore backup: content, LF-normalised, against
every version the real repo has. A file is only genuinely at risk if its bytes exist in neither the
reference worktree NOR that repo's history. Comparing mtimes or names would answer a different, much
weaker question.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REFERENCE = Path("C:/Users/Prekzursil/source/ast-integrate")
TARGETS = {
    "chk": Path("C:/Users/Prekzursil/source/_advver_M14/chk"),
    "scratch": Path("C:/Users/Prekzursil/source/_advver_M14/scratch"),
}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
}
MAX_BYTES = 4_000_000


def norm_digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def reference_digests() -> set[str]:
    """Every LF-normalised blob tracked in the reference repo's WORKTREE."""
    digests: set[str] = set()
    for rel in subprocess.run(
        ["git", "-C", str(REFERENCE), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split():
        path = REFERENCE / rel
        try:
            if path.is_file() and path.stat().st_size <= MAX_BYTES:
                digests.add(norm_digest(path.read_bytes()))
        except OSError:
            continue
    # A HISTORY PASS WAS HERE AND IS DELIBERATELY REMOVED. It ran `rev-list --objects --all` and
    # piped up to 20,000 shas through `cat-file --batch`, captured the whole stream in memory, and
    # then DISCARDED it -- the digests were never extracted. So it cost minutes and gigabytes to
    # contribute exactly nothing, and it is the reason the first run produced no output at all.
    # Dropping it makes the comparison WORKTREE-ONLY, which is strictly more conservative: a file
    # that exists only in deleted history will be reported as unique rather than silently cleared.
    # That direction of error is the safe one for a "is this work at risk" question.
    return digests


def walk(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if any(seg in SKIP_DIRS for seg in p.parts):
            continue
        if p.is_file():
            out.append(p)
    return out


def main() -> int:
    ref = reference_digests()
    if len(ref) < 1000:
        print(
            f"FAILED:triage-noremote reference set is only {len(ref)} blobs (fail closed)"
        )
        return 1
    # Control: a byte string that cannot be in the repo must be absent; a real file must be present.
    if norm_digest(b"zzz-not-in-any-repo-" + b"x" * 64) in ref:
        print("FAILED:triage-noremote control (bogus digest present)")
        return 1
    sentinel = REFERENCE / "command-center" / "close_verify.py"
    if sentinel.is_file() and norm_digest(sentinel.read_bytes()) not in ref:
        print(
            "FAILED:triage-noremote control (known-present file missing from reference set)"
        )
        return 1
    print(f"  reference: {len(ref)} LF-normalised blobs; controls PASS\n")

    for label, root in TARGETS.items():
        if not root.is_dir():
            print(f"  {label}: ABSENT at {root}")
            continue
        files = walk(root)
        # A content miss is NOT automatically work at risk, and reporting it as such would be an
        # overclaim. Split it, because the two cases have opposite consequences:
        #   VARIANT - the same relative path EXISTS in the reference, contents differ. An older or
        #             diverged COPY of a file that is safely in version control. Low risk.
        #   ORPHAN  - no file at that path in the reference at all. This is the only copy, and the
        #             only case where "this work exists nowhere else" is literally true.
        variants, orphans = [], []
        for p in files:
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
                if norm_digest(p.read_bytes()) in ref:
                    continue
                rel = p.relative_to(root)
                (variants if (REFERENCE / rel).exists() else orphans).append(str(rel))
            except OSError:
                continue
        print(
            f"  {label}: {len(files)} files | {len(variants)} VARIANT (path in repo, content "
            f"differs) | {len(orphans)} ORPHAN (no such path in repo)"
        )
        for rel in sorted(orphans)[:15]:
            print(f"      ORPHAN {rel}")
        if len(orphans) > 15:
            print(f"      ... and {len(orphans) - 15} more orphans")

    print(
        "\nSUCCESS:triage-noremote measured only -- nothing created, pushed, or deleted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
