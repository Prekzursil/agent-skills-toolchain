#!/usr/bin/env python
"""_b9_crlf_split.py -- WHY did the blob and the worktree disagree about formatting?

THE ANSWER TURNED OUT NOT TO BE CRLF AT ALL, and this probe is what ruled it out. An early
`_b9_format_tracked.py` flagged 5 tracked files on the blob while a worktree
`ruff format --check .` flagged 1. Two very different root causes produce that:

  A. the blob is LF and ruff makes a different decision on LF than on CRLF
     (windows-shell 8b) -- fix: run ruff and commit the result.
  B. the blob itself CONTAINS CRLF -- committed with Windows line endings -- and ruff is
     normalising them; the fix belongs with .gitattributes / the file's owner.

Measured: **every blob is LF (0 CRLF), including all four suspects**, so B is refuted and A
alone cannot explain a file that is clean under CRLF and dirty under identical LF content.
That contradiction is what sent me back to the instrument, where the real cause was: the
temp tree was missing `tools/mcp/patent-search-mcp/pyproject.toml`, so those four modules
were formatted against settings that do not govern them. They are CLEAN; the probe was
wrong. `_b9_format_tracked.py` now materialises every tracked ruff config and asserts parity
(control C4), and re-reports 1 offender, agreeing with the worktree.

Kept, unedited in substance, because the self-contradiction it exposed -- a probe whose
controls all passed while it read an environment the real gate never sees -- is the finding.
Control: a KNOWN-clean tracked file is in the same table, so "0 crlf" is shown to be a value
this probe can actually produce rather than its only output.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)

# The 5 the FIRST (config-blind) version of _b9_format_tracked.py flagged. Only the first is
# real; the four patent-search modules are the false reds the missing nested config produced.
SUSPECTS = [
    "command-center/hook-audit/_g5_vendorcaps.py",
    "tools/mcp/patent-search-mcp/patent_api.py",
    "tools/mcp/patent-search-mcp/server.py",
    "tools/mcp/patent-search-mcp/tests/test_patent_api.py",
    "tools/mcp/patent-search-mcp/tests/test_server.py",
]
CONTROL_CLEAN = "command-center/hook-audit/check_citations.py"


def blob_bytes(rel: str) -> bytes:
    return subprocess.run(
        ["git", "show", f":{rel}"], cwd=REPO, capture_output=True, check=True
    ).stdout


def main() -> int:
    rows = []
    for rel in [*SUSPECTS, CONTROL_CLEAN]:
        b = blob_bytes(rel)
        wt = (REPO / rel).read_bytes() if (REPO / rel).exists() else b""
        rows.append(
            {
                "path": rel,
                "role": "control-clean" if rel == CONTROL_CLEAN else "suspect",
                "blob_bytes": len(b),
                "blob_crlf": b.count(b"\r\n"),
                "worktree_bytes": len(wt),
                "worktree_crlf": wt.count(b"\r\n"),
            }
        )
    for r in rows:
        print(
            f"{r['role']:14s} blob_crlf={r['blob_crlf']:5d} wt_crlf={r['worktree_crlf']:5d}  {r['path']}"
        )
    blob_crlf_offenders = [
        r for r in rows if r["role"] == "suspect" and r["blob_crlf"] > 0
    ]
    verdict = "B_BLOB_HAS_CRLF" if blob_crlf_offenders else "NOT_B_NO_BLOB_CARRIES_CRLF"
    out = {
        "probe": "_b9_crlf_split.py",
        "rows": rows,
        "verdict": verdict,
        "resolved_cause": (
            "neither A nor B: the four patent-search suspects were false reds from a temp "
            "tree missing tools/mcp/patent-search-mcp/pyproject.toml. Only "
            "_g5_vendorcaps.py was genuinely unformatted."
        ),
        "genuinely_unformatted": ["command-center/hook-audit/_g5_vendorcaps.py"],
    }
    (HERE / "B9-CRLF-SPLIT.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"SUCCESS:crlf-split verdict={verdict} blob_crlf_offenders={len(blob_crlf_offenders)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
