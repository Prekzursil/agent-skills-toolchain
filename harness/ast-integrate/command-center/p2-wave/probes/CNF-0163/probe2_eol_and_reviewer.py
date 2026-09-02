#!/usr/bin/env python3
"""Named probe 2: EOL-agnostic resolution + independent ten-anchor review.

Signal 1 is the planted CRLF worktree / LF blob control. Signal 2 is a second
resolver that calls git cat-file itself (or reads the worktree when git is
absent) and compares ten anchors against resolve.classify.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixture import make_fixture, worktree_cr_construct  # noqa: E402
from harvest import harvest  # noqa: E402
from resolve import (  # noqa: E402
    VERDICT_DRIFTED,
    VERDICT_MISSING,
    VERDICT_RESOLVED,
    VERDICT_WORKTREE,
    classify,
    git_cat_file,
    split_lines,
)

ART = REPO / "command-center/receipts/CNF-0163.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0163-probe2 {msg}")
    return 1


def independent_verdict(
    repo: Path,
    path: str,
    line: int,
    construct: str | None,
    revision: str | None,
) -> str:
    """Second implementation: cat-file + EOL split, no classify()."""
    blob = git_cat_file(repo, revision, path) if revision else None
    blob_lines = split_lines(blob) if blob is not None else None
    wt_path = repo / path
    wt = wt_path.read_bytes() if wt_path.is_file() else None
    wt_lines = split_lines(wt) if wt is not None else None
    needle = (construct or "").replace("\r", "")

    def at(lines, n):
        if lines is None or n < 1 or n > len(lines):
            return None
        return lines[n - 1].replace("\r", "")

    def find(lines):
        if not lines or not needle:
            return []
        return [i for i, ln in enumerate(lines, 1) if needle in ln.replace("\r", "")]

    blob_line = at(blob_lines, line)
    wt_line = at(wt_lines, line)
    blob_ok = blob_line is not None and (not needle or needle in blob_line)
    wt_ok = wt_line is not None and (not needle or needle in wt_line)
    elsewhere = find(blob_lines)
    if blob_ok:
        return VERDICT_RESOLVED
    if elsewhere:
        return VERDICT_DRIFTED
    if wt_ok:
        return VERDICT_WORKTREE
    return VERDICT_MISSING


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNF-0163" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    src = (HERE / "resolve.py").read_text(encoding="utf-8")
    if "cat-file" not in src:
        return fail("resolve.py does not call cat-file")
    if "'archive'" in src or '"archive"' in src:
        return fail("resolve.py must not invoke the archive porcelain")

    with make_fixture() as fix:
        cr = worktree_cr_construct(fix, 1)
        if "\r" not in cr:
            return fail("EOL construct lost CR before the test")
        eol = classify(
            fix.repo,
            path=fix.eol_rel,
            line=1,
            construct=cr,
            revision=fix.rev_b,
        )
        if eol.verdict != VERDICT_RESOLVED:
            return fail(f"CRLF manufactured a non-resolve verdict {eol.verdict}")
        naive_blob = git_cat_file(fix.repo, fix.rev_b, fix.eol_rel)
        if naive_blob is None:
            return fail("eol blob missing")
        if b"\r\n" in naive_blob:
            return fail("eol blob unexpectedly CRLF; cat-file should return LF")
        if cr.encode("utf-8") in naive_blob:
            return fail("CR construct should not be a raw substring of the LF blob")

        sample = [
            (
                "present",
                fix.repo,
                fix.evidence_rel,
                1,
                "ALPHA-CONSTRUCT",
                fix.rev_a,
            ),
            (
                "past-eof",
                fix.repo,
                fix.evidence_rel,
                999,
                "PAST-EOF-SENTINEL",
                fix.rev_a,
            ),
            (
                "worktree-only",
                fix.repo,
                fix.evidence_rel,
                5,
                "WORKTREE-ONLY-CONSTRUCT",
                fix.rev_b,
            ),
            (
                "drift",
                fix.repo,
                fix.evidence_rel,
                1,
                "ALPHA-CONSTRUCT",
                fix.rev_b,
            ),
            (
                "eol",
                fix.repo,
                fix.eol_rel,
                1,
                cr,
                fix.rev_b,
            ),
        ]

        live = harvest(REPO)
        for i, a in enumerate(live[:5]):
            sample.append(
                (
                    f"live-{i}",
                    REPO,
                    a.path,
                    a.line,
                    a.construct,
                    a.revision,
                )
            )
        if len(sample) < 10:
            return fail(f"reviewer sample {len(sample)} < 10")
        sample = sample[:10]

        compared = []
        for name, repo, path, line, construct, rev in sample:
            tool = classify(
                repo, path=path, line=line, construct=construct, revision=rev
            )
            indep = independent_verdict(repo, path, line, construct, rev)
            ok = tool.verdict == indep
            compared.append(
                {
                    "id": name,
                    "path": path,
                    "line": line,
                    "tool": tool.verdict,
                    "independent": indep,
                    "match": ok,
                }
            )
            if not ok:
                return fail(f"reviewer mismatch {name} tool={tool.verdict} indep={indep}")

    summary = {
        "probe": "probe2-eol-and-reviewer",
        "unit_id": "CNF-0163",
        "pass": True,
        "eol_verdict": VERDICT_RESOLVED,
        "reviewer_compared": len(compared),
        "reviewer_matches": sum(1 for c in compared if c["match"]),
        "rows": compared,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0163-probe2 EOL-agnostic resolve and ten-anchor review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
