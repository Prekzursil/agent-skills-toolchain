"""Independent per-decision review from raw file bytes.

Does not read the author's summary. Re-classifies planted and live
contradiction candidates with hand-written predicates (the retry-policy
pivot away from keyword search).
"""
from __future__ import annotations

from pathlib import Path


def _lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return [(i, line) for i, line in enumerate(text.splitlines(), 1)]


def _comment(path: Path, line: str) -> bool:
    s = line.lstrip()
    if path.suffix.lower() in {".yml", ".yaml", ".sh", ".py", ".ps1"}:
        return s.startswith("#")
    return False


def review_pr_only(path: Path) -> list[dict]:
    """PR-ONLY is contradicted by a live canary/marketplace release action."""
    hits = []
    rel = path.as_posix()
    for n, line in _lines(path):
        if _comment(path, line):
            continue
        low = line.lower()
        if "never a private canary" in low or "never a public marketplace" in low:
            continue
        if "rejected alternative" in low:
            continue
        if "binding remains pr-only" in low:
            continue
        if "quoting" in low and "pr-only" in low:
            continue
        assertive = False
        kind = "prose"
        if "binding release mode is private canary" in low:
            assertive = True
        elif "release mode is private canary" in low:
            assertive = True
        elif "release mode is public marketplace" in low:
            assertive = True
        elif "npm publish" in low:
            assertive = True
            kind = "ci-workflow" if path.suffix.lower() in {".yml", ".yaml"} else "script"
        elif "gh release create" in low:
            assertive = True
            kind = "ci-workflow" if path.suffix.lower() in {".yml", ".yaml"} else "script"
        elif "through the canary channel" in low:
            assertive = True
        if assertive:
            hits.append(
                {
                    "decision_id": "DEC-PR-ONLY",
                    "path": rel,
                    "line": n,
                    "snippet": line.strip()[:240],
                    "kind": kind,
                    "classification": "CONTRADICTS",
                }
            )
    return hits


def review_delete_all(path: Path) -> list[dict]:
    hits = []
    for n, line in _lines(path):
        if _comment(path, line):
            continue
        low = line.lower()
        if "retirement scope is keep-some" in low or "retirement scope is delete-partial" in low:
            hits.append(
                {
                    "decision_id": "DEC-DELETE-ALL",
                    "path": path.as_posix(),
                    "line": n,
                    "snippet": line.strip()[:240],
                    "kind": "prose",
                    "classification": "CONTRADICTS",
                }
            )
    return hits


def review_salvage(path: Path) -> list[dict]:
    hits = []
    for n, line in _lines(path):
        if _comment(path, line):
            continue
        low = line.lower()
        if "salvage home is tools/lib" in low or "salvage home = tools/lib" in low:
            continue
        if "salvage home is " in low:
            hits.append(
                {
                    "decision_id": "DEC-SALVAGE-HOME",
                    "path": path.as_posix(),
                    "line": n,
                    "snippet": line.strip()[:240],
                    "kind": "prose",
                    "classification": "CONTRADICTS",
                }
            )
    return hits


def review_no_remote(path: Path) -> list[dict]:
    hits = []
    for n, line in _lines(path):
        if _comment(path, line):
            continue
        low = line.lower()
        if "never create remotes" in low or "do not create remotes" in low:
            continue
        if "git remote add" in low or "create remotes first" in low:
            kind = "script" if path.suffix.lower() in {".sh", ".ps1", ".py"} else "prose"
            hits.append(
                {
                    "decision_id": "DEC-NO-REMOTE",
                    "path": path.as_posix(),
                    "line": n,
                    "snippet": line.strip()[:240],
                    "kind": kind,
                    "classification": "CONTRADICTS",
                }
            )
    return hits


REVIEWERS = {
    "DEC-PR-ONLY": review_pr_only,
    "DEC-DELETE-ALL": review_delete_all,
    "DEC-SALVAGE-HOME": review_salvage,
    "DEC-NO-REMOTE": review_no_remote,
}


def review_file(path: Path) -> list[dict]:
    out: list[dict] = []
    for fn in REVIEWERS.values():
        out.extend(fn(path))
    return out


def review_files(paths: list[Path]) -> list[dict]:
    out: list[dict] = []
    for p in paths:
        out.extend(review_file(p))
    return out
