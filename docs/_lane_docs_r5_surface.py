"""LANE DOCS round 5 -- measure the `scripts/...` reference surface in command docs.

v2. v1 of this file was WRONG and its number (34 missing) must not be cited. Two defects,
both found by reading its own output rather than by inspecting it:

  D1  the token regex anchored on `scripts/` ANYWHERE in a path, so
      `${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py`
      was reported as a missing `scripts/instinct-cli.py`. Substring, not path.
  D2  prose was treated as paths -- "coverage across scripts/hooks/lib. (tests/)" became a
      path `scripts/hooks/lib.` with a trailing period.

v1 also asserted, wrongly, that a bare `scripts/x` is systemic. In fact `scripts/` IS a real
repo directory with 86 tracked files, which is exactly why a dangling `scripts/hooks/...`
reference misleads: the parent is real.

CONTROL (3-state, mirroring docs/_lane_docs_detector.py). The extractor must give three
DIFFERENT answers, or it is inert:
  RESOLVES   scripts/longrun.ps1                                     -> present
  PREFIXED   ${CLAUDE_PLUGIN_ROOT}/skills/.../scripts/instinct-cli.py -> NOT a bare ref; its
             own full path resolves
  ABSENT     scripts/hooks/cost-tracker.js                            -> genuinely missing
A run where all three land in the same bucket proves the extractor is broken, not the docs.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# A path-ish token: no whitespace, must contain a slash. Bounded by quote/backtick/space/paren.
TOKEN = re.compile(r"[A-Za-z0-9._${}/\\~%-]*/[A-Za-z0-9._${}/\\~%-]*")
TRAILING_JUNK = re.compile(r"[.,;:)\]`\"']+$")


def tracked_repo_paths() -> set[str]:
    """Every path git tracks, forward-slashed. Named to not collide with the monitorcore helper."""
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout
    return {ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()}


def extract(line: str) -> list[str]:
    """Full path tokens on a line, cleaned of trailing prose punctuation."""
    out: list[str] = []
    for raw in TOKEN.findall(line):
        tok = TRAILING_JUNK.sub("", raw.strip().strip("`\"'"))
        if "/" in tok:
            out.append(tok)
    return out


def classify(tok: str, tracked: set[str]) -> tuple[str, str]:
    """(kind, path_checked). Only BARE-REPO tokens are held against the repo."""
    if tok.startswith(("~", "$HOME", "%USERPROFILE%")):
        return "HOME-SCOPED", tok
    if tok.startswith("${CLAUDE_PLUGIN_ROOT}/"):
        return "PLUGIN-ROOT", tok[len("${CLAUDE_PLUGIN_ROOT}/") :]
    if "${" in tok or tok.startswith(("/", "\\")) or ":" in tok:
        return "OTHER", tok
    if tok.startswith("scripts/"):
        return "BARE-REPO", tok
    return "OTHER", tok


def resolves(path: str, tracked: set[str]) -> bool:
    return path in tracked or (REPO / path).exists()


def run_control(tracked: set[str]) -> dict[str, object]:
    cases = {
        "RESOLVES": "`scripts/longrun.ps1`",
        "PREFIXED": 'python3 "${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py" status',
        "ABSENT": "the cost metrics emitted by `scripts/hooks/cost-tracker.js`.",
    }
    got: dict[str, object] = {}
    for name, line in cases.items():
        toks = extract(line)
        rows = []
        for t in toks:
            kind, path = classify(t, tracked)
            rows.append(
                {
                    "token": t,
                    "kind": kind,
                    "path": path,
                    "resolves": resolves(path, tracked),
                }
            )
        got[name] = rows
    return got


def main() -> int:
    tracked = tracked_repo_paths()

    control = run_control(tracked)
    # The control must produce three DIFFERENT outcomes.
    c_res = [r for r in control["RESOLVES"] if r["kind"] == "BARE-REPO"]  # type: ignore[index]
    c_pre = [r for r in control["PREFIXED"] if r["kind"] == "PLUGIN-ROOT"]  # type: ignore[index]
    c_abs = [r for r in control["ABSENT"] if r["kind"] == "BARE-REPO"]  # type: ignore[index]
    control_ok = (
        len(c_res) == 1
        and c_res[0]["resolves"] is True
        and len(c_pre) == 1
        and c_pre[0]["resolves"] is True
        and len(c_abs) == 1
        and c_abs[0]["resolves"] is False
        # and PREFIXED must NOT have produced a bare scripts/ token (that was D1)
        and not [r for r in control["PREFIXED"] if r["kind"] == "BARE-REPO"]  # type: ignore[index]
    )

    rows: list[dict[str, object]] = []
    for md in sorted((REPO / "commands").glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for tok in extract(line):
                kind, path = classify(tok, tracked)
                if kind != "BARE-REPO":
                    continue
                rows.append(
                    {
                        "doc": md.relative_to(REPO).as_posix(),
                        "line": i,
                        "token": tok,
                        "resolves_in_repo": resolves(path, tracked),
                    }
                )

    missing = [r for r in rows if not r["resolves_in_repo"]]
    by_doc: dict[str, int] = defaultdict(int)
    for r in missing:
        by_doc[str(r["doc"])] += 1

    report = {
        "control": control,
        "control_discriminates": control_ok,
        "bare_repo_refs": len(rows),
        "bare_repo_missing": len(missing),
        "missing_rows": missing,
        "missing_by_doc": dict(sorted(by_doc.items(), key=lambda kv: -kv[1])),
        "distinct_missing_paths": sorted({str(r["token"]) for r in missing}),
        "scripts_tracked_file_count": len(
            [p for p in tracked if p.startswith("scripts/")]
        ),
        "scripts_hooks_tracked_file_count": len(
            [p for p in tracked if p.startswith("scripts/hooks/")]
        ),
    }
    print(json.dumps(report, indent=2))

    if not control_ok:
        print("FAILED:docs-r5-surface control did NOT discriminate", file=sys.stderr)
        return 1
    print(
        f"SUCCESS:docs-r5-surface control=3-state-ok bare_refs={len(rows)} "
        f"missing={len(missing)} scripts_tracked={report['scripts_tracked_file_count']} "
        f"scripts_hooks_tracked={report['scripts_hooks_tracked_file_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
