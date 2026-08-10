"""P11 independent confirmation - W1-06: the 12/12 mutation battery.

Wave 1 claimed `12 killed, 0 survived, exit 0`. This probe runs the SAME shipped tool from
TWO sets of bytes and compares:

  arm HEAD   - `git cat-file -p <named-commit>:platform/lib/_mutation_selfcheck.py`
  arm WT     - the working tree file (a Wave-4 lane modified it; the change is UNCOMMITTED)

`git cat-file -p` is used deliberately: `git archive` returns CRLF on this box and the working
tree is CRLF, so hashing/serving working-tree bytes would not be the committed bytes.

The module is exec'd with `__file__` pre-seeded so its own HERE/REPO_ROOT/PLATFORM resolution
points at the real platform tree. Nothing under platform/ is modified - the tool copies to a
throwaway tempdir by construction.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
REL = "platform/lib/_mutation_selfcheck.py"
ANCHOR = "04e4736c"  # named commit = end of Wave 3. NOT a moving reference.


def committed_bytes(rev: str, rel: str) -> str:
    out = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("utf-8")


def run_source(src: str, label: str) -> dict[str, object]:
    ns: dict[str, object] = {
        "__name__": f"p11_mut_{label}",
        "__file__": str(REPO / REL),
    }
    buf = io.StringIO()
    rc: int | str
    try:
        with redirect_stdout(buf):
            exec(compile(src, f"<{label}:{REL}>", "exec"), ns)  # noqa: S102
            rc = ns["main"]()  # type: ignore[operator]
    except Exception as exc:  # pragma: no cover - reported, not swallowed
        return {
            "arm": label,
            "exception": f"{type(exc).__name__}: {exc}",
            "raw": buf.getvalue()[-2000:],
        }
    text = buf.getvalue()
    # The tool prints a JSON report then a terminal marker line.
    report: dict[str, object] = {}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            report = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            report = {}
    marker = ""
    for line in text.splitlines():
        if line.startswith(("SUCCESS:", "FAILED:")):
            marker = line
    rows = report.get("rows", []) if isinstance(report, dict) else []
    importable = (
        [bool(r.get("mutant_importable")) for r in rows]
        if isinstance(rows, list)
        else []
    )
    return {
        "arm": label,
        "exit_code": rc,
        "terminal_marker": marker,
        "killed_count": report.get("killed_count"),
        "survived": report.get("survived"),
        "mutants_importable": sum(1 for x in importable if x),
        "mutants_total": len(importable),
        "first_row_tail": (
            rows[0].get("tail") if rows and isinstance(rows[0], dict) else ""
        ),
    }


def main() -> int:
    result: dict[str, object] = {
        "claim": "W1-06 mutation battery 12/12 killed, 0 survived, exit 0",
        "anchor_commit": ANCHOR,
        "file": REL,
        "arms": [],
    }
    head_src = committed_bytes(ANCHOR, REL)
    wt_src = (REPO / REL).read_text(encoding="utf-8")
    result["bytes_differ_head_vs_worktree"] = head_src != wt_src
    result["worktree_is_uncommitted_change"] = (
        subprocess.run(
            ["git", "diff", "--quiet", "--", REL], cwd=str(REPO), check=False
        ).returncode
        != 0
    )

    arms = result["arms"]
    assert isinstance(arms, list)
    arms.append(run_source(head_src, "HEAD_committed_bytes"))
    arms.append(run_source(wt_src, "WORKTREE_uncommitted"))

    out = REPO / "command-center" / "P11-MUTATION-BOTHSTATES.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    ok = arms[0].get("killed_count") != 12 and arms[1].get("killed_count") == 12
    print(
        "SUCCESS:p11-mutation-bothstates BROKEN-at-HEAD/GREEN-in-worktree"
        if ok
        else "FAILED:p11-mutation-bothstates unexpected arm pattern"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
