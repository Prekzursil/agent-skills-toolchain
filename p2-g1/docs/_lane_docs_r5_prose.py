"""LANE DOCS round 5 -- split the 16 dangling `scripts/...` refs into PROSE vs CODE-BLOCK.

Why this split decides the gate's scope:

  PROSE       "the cost metrics emitted by `scripts/hooks/cost-tracker.js`" -- the document
              ASSERTS this path exists. That is a doc-vs-reality claim and is gateable.
  CODE BLOCK  "node scripts/orchestrate-worktrees.js plan.json" -- an invocation the user runs
              from whatever cwd the command targets. Gating it would fire on every vendored
              command doc whose implementation lives in the deployed harness, which is the
              false-positive class that gets a gate disabled within a week.

CONTROL: the fence tracker must give DIFFERENT answers for the same token inside and outside a
fence, or it is inert.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[A-Za-z0-9._${}/\\~%-]*/[A-Za-z0-9._${}/\\~%-]*")
TRAILING_JUNK = re.compile(r"[.,;:)\]`\"']+$")
FENCE = re.compile(r"^\s*(```|~~~)")


def tracked_repo_paths() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout
    return {ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()}


def bare_scripts_tokens(line: str) -> list[str]:
    out = []
    for raw in TOKEN.findall(line):
        tok = TRAILING_JUNK.sub("", raw.strip().strip("`\"'"))
        if tok.startswith("scripts/") and "/" in tok and "${" not in tok:
            out.append(tok)
    return out


def scan(text: str) -> list[tuple[int, str, bool]]:
    """(lineno, token, in_fence) for every bare scripts/ token."""
    rows: list[tuple[int, str, bool]] = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        for tok in bare_scripts_tokens(line):
            rows.append((i, tok, in_fence))
    return rows


def main() -> int:
    tracked = tracked_repo_paths()

    # --- CONTROL: same token, inside vs outside a fence -> must differ -------------------
    ctrl_text = "prose `scripts/hooks/cost-tracker.js` here\n```bash\nnode scripts/hooks/cost-tracker.js\n```\n"
    ctrl = scan(ctrl_text)
    ctrl_prose = [r for r in ctrl if not r[2]]
    ctrl_code = [r for r in ctrl if r[2]]
    control_ok = len(ctrl_prose) == 1 and len(ctrl_code) == 1

    prose_rows: list[dict[str, object]] = []
    code_rows: list[dict[str, object]] = []
    for md in sorted((REPO / "commands").glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, tok, in_fence in scan(text):
            resolves = tok in tracked or (REPO / tok).exists()
            if resolves:
                continue
            row = {"doc": md.relative_to(REPO).as_posix(), "line": lineno, "token": tok}
            (code_rows if in_fence else prose_rows).append(row)

    report = {
        "control_prose_hits": len(ctrl_prose),
        "control_code_hits": len(ctrl_code),
        "control_discriminates": control_ok,
        "prose_missing": len(prose_rows),
        "prose_rows": prose_rows,
        "code_block_missing": len(code_rows),
        "code_block_docs": sorted({str(r["doc"]) for r in code_rows}),
    }
    print(json.dumps(report, indent=2))
    if not control_ok:
        print(
            "FAILED:docs-r5-prose fence control did not discriminate", file=sys.stderr
        )
        return 1
    print(
        f"SUCCESS:docs-r5-prose control=ok prose_missing={len(prose_rows)} "
        f"code_block_missing={len(code_rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
