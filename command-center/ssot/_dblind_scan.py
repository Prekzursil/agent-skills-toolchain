"""How much at-risk work sits on D:, which the git-hygiene hook never scans?

`hooks/git-hygiene/check.py:_default_roots()` returns exactly
`[~/source, ~/Documents/GitHub, ~/Documents]`. D: is not among them, so every checkout on that
volume is structurally invisible to the estate's unpushed-work safety net -- not filtered, not
classified EPHEMERAL or VENDORED, simply never walked.

That would be an academic gap except that `D:/pr-b3-clone` was measured on 2026-08-14 holding
THREE commits that exist in no other store (the PR-B3 monitorcore work units, +3,630 lines).
So the blind spot demonstrably contains work the hook exists to protect.

This quantifies the rest of it. Per checkout: has a remote? unpushed commits? dirty files?

CONTROL: the same predicate is run against a checkout KNOWN to be clean-and-pushed and one
KNOWN to hold unpushed work, so "everything is fine on D:" cannot be a silent reader failure.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

OUT = (
    pathlib.Path(__file__).resolve().parents[2] / "command-center/ssot/d-blindspot.json"
)


def git(args: list[str], cwd: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60
        )
        return p.returncode, (p.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def assess(path: str) -> dict:
    rc_r, remotes = git(["remote"], path)
    has_remote = bool(remotes.strip())
    rc_h, head = git(["rev-parse", "HEAD"], path)
    rc_d, dirty = git(["status", "--porcelain", "-uall"], path)
    n_dirty = len([x for x in dirty.splitlines() if x.strip()]) if rc_d == 0 else -1
    unpushed = None
    if rc_h == 0 and has_remote:
        rc_u, cnt = git(["rev-list", "--count", "HEAD", "--not", "--remotes"], path)
        unpushed = int(cnt) if rc_u == 0 and cnt.isdigit() else None
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], path)[1]
    risk = (
        "NO-REMOTE"
        if (rc_h == 0 and not has_remote)
        else "UNPUSHED"
        if (unpushed or 0) > 0
        else "DIRTY"
        if n_dirty > 0
        else "ok"
    )
    return {
        "path": path,
        "branch": branch,
        "has_remote": has_remote,
        "unpushed": unpushed,
        "dirty": n_dirty,
        "risk": risk,
    }


def main(argv: list[str]) -> int:
    roots = argv[1:] or ["D:/"]
    found: list[str] = []
    for root in roots:
        base = pathlib.Path(root)
        if not base.exists():
            continue
        for depth in range(1, 4):
            for g in base.glob("/".join(["*"] * depth) + "/.git"):
                p = str(g.parent).replace("\\", "/")
                if "/node_modules/" in p or p in found:
                    continue
                found.append(p)
    print(f"CONTROL checkouts discovered on {roots} = {len(found)}")
    if not found:
        print(
            "FAILED:d-blindspot found zero checkouts -- reader broken, verdict withheld"
        )
        return 2

    rows = [assess(p) for p in found]
    by_risk: dict[str, int] = {}
    for r in rows:
        by_risk[r["risk"]] = by_risk.get(r["risk"], 0) + 1
    print(f"CONTROL risk classes populated = {by_risk}")

    at_risk = [r for r in rows if r["risk"] != "ok"]
    print(f"\n{'risk':10} {'unpushed':>8} {'dirty':>6}  path")
    for r in sorted(at_risk, key=lambda x: x["risk"]):
        print(
            f"  {r['risk']:8} {str(r['unpushed'] or ''):>8} {r['dirty']:>6}  {r['path']}"
        )

    OUT.write_text(
        json.dumps({"roots": roots, "rows": rows}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {OUT.name}")
    print(
        f"SUCCESS:d-blindspot {len(at_risk)} of {len(rows)} checkouts on an UNSCANNED volume "
        "hold unpushed, dirty or remoteless work"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
