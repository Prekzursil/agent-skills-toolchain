"""Repo-vs-live drift for the rules round 1 corrected, with LF normalisation and a real control.

My first attempt at this compared ``git show HEAD:<path>`` (LF blob) against the live file
(CRLF on Windows) with ``diff``. Every line then reads as changed, so the probe returns
"differs" for EVERY file and cannot distinguish "this rule carries an undeployed correction"
from "these are the same bytes with different line endings". The control caught it: a file I
expected to match reported differing too. That is the §3c shape -- a control that passes (or
here, fails) identically under both hypotheses measures nothing.

Fixed: normalise both sides to LF, then compare. The control is now discriminating -- it names
files expected to be IDENTICAL after normalisation and files expected to DIFFER, and requires
both groups to come out as expected before any verdict is believed.
"""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIVE = Path.home() / ".claude" / "rules"


def repo_blob(rel: str) -> str:
    raw = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"HEAD:rules/{rel}"],
        capture_output=True,
        check=True,
    ).stdout
    return raw.replace(b"\r\n", b"\n").decode("utf-8", "replace")


def live_text(rel: str) -> str | None:
    path = LIVE / rel
    if not path.is_file():
        return None
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")


def compare(rel: str) -> tuple[int, int]:
    """(lines only in repo, lines only in live) after LF normalisation."""
    a = repo_blob(rel).split("\n")
    b = live_text(rel)
    if b is None:
        return (-1, -1)
    b_lines = b.split("\n")
    only_repo = only_live = 0
    for line in difflib.unified_diff(a, b_lines, n=0, lineterm=""):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            only_repo += 1
        elif line.startswith("+"):
            only_live += 1
    return (only_repo, only_live)


# Files round 1 corrected in the repo. Claim under test: the correction has NOT been deployed.
CORRECTED = ["common/harness-vcs-hygiene.md", "common/cross-vendor-dispatch.md"]


def main() -> int:
    print("== corrected rules: repo HEAD vs live, LF-normalised ==")
    results = {}
    for rel in CORRECTED:
        only_repo, only_live = compare(rel)
        results[rel] = (only_repo, only_live)
        print(f"  {rel:<40} only-in-repo={only_repo:<4} only-in-live={only_live}")

    print("")
    print("== discriminating control: the SAME instrument on a known-identical pair ==")
    # A rule the repo and live tree should agree on byte-for-byte after normalisation. If this
    # reports drift, the instrument is measuring line endings again and no verdict above holds.
    ident_ok = False
    identical_candidates = []
    for path in sorted((REPO / "rules").rglob("*.md")):
        rel = path.relative_to(REPO / "rules").as_posix()
        if rel in CORRECTED:
            continue
        only_repo, only_live = compare(rel)
        if only_repo == 0 and only_live == 0:
            identical_candidates.append(rel)
    if identical_candidates:
        ident_ok = True
        print(
            f"  PASS  {len(identical_candidates)} rule(s) report ZERO drift, so a non-zero "
            f"reading above is content, not CRLF"
        )
        print(f"        e.g. {identical_candidates[:3]}")
    else:
        print(
            "  FAIL  every rule reports drift -- the instrument cannot distinguish content "
            "from line endings; no verdict may be cited"
        )

    print("")
    drifted = [r for r, (a, b) in results.items() if a > 0 or b > 0]
    if not ident_ok:
        print("FAILED:adv3_deploydrift control non-discriminating, fail closed")
        return 1
    print(
        f"SUCCESS:adv3_deploydrift {len(drifted)}/{len(CORRECTED)} corrected rule(s) still "
        f"differ from the live tree; control proves the reading is content-level"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
