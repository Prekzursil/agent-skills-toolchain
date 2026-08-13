r"""B3 - CONTROLLED A/B: the shipped (fixed) wire-check vs the HEAD (unfixed) copy, run
back-to-back against the SAME working tree, so the cost delta is attributable to the
change and not to the tree having grown since the research lane measured 13,342 ms.

Why this is needed: a single post-fix reading of 70,657 ms cannot distinguish
  H1 the encoding fix made wire-check slower (blanked diffs used to mean zero symbols
     to resolve, so the fix buys back real work), from
  H2 the working tree simply holds far more changed/untracked files now.
Both would produce the same number. Running BOTH binaries over the SAME tree in the same
minute separates them: under H2 the two numbers converge, under H1 they diverge.

The unfixed copy comes from `git show HEAD:hooks/wire-check/check.py` (the stored BLOB --
`git archive` would hand back CRLF on Windows and is the wrong route).

Writes B3-AB-BUDGET.json. Fails closed if either arm produced no timing.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).resolve().parent
BUDGET_S = 25  # hooks/_dispatch/manifest.json -> Stop -> wire-check.timeout

_SHAPES = (
    re.compile(r"`([^`]+)\(\)` \(added in ([^)]+)\) is referenced 0x"),
    re.compile(r"route '([^']+)' \(added in ([^)]+)\) is linked/navigated 0x"),
    re.compile(r"`([^`]+)` looks like a versioned fork but no live v1 `([^`]+)`"),
    re.compile(r"symbol `([^`]+)` looks versioned but base `([^`]+)` is referenced 0x"),
)


def parse_findings(ctx: str) -> list[dict]:
    """Parse ALL FOUR emitted shapes. A parser that knows only one shape reports
    finding_count=0 next to emitted=True -- a self-contradiction, i.e. a detector
    failure, which is exactly what the first version of this probe did."""
    out: list[dict] = []
    for i, rx in enumerate(_SHAPES):
        for m in rx.finditer(ctx):
            out.append({"shape": i, "subject": m.group(1), "detail": m.group(2)})
    return out


def run_hook(script: Path, tag: str) -> dict:
    payload = json.dumps(
        {"session_id": "b3-" + tag, "cwd": str(REPO), "stop_hook_active": False}
    )
    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, str(script)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=1800,
        cwd=str(REPO),
    )
    ms = (time.perf_counter() - t0) * 1000
    so = p.stdout.decode("utf-8", "replace")
    ctx = ""
    if so.strip():
        try:
            ctx = json.loads(so)["hookSpecificOutput"]["additionalContext"]
        except Exception:
            ctx = so
    f = parse_findings(ctx)
    return {
        "arm": tag,
        "script": str(script),
        "wall_ms": round(ms, 1),
        "budget_s": BUDGET_S,
        "pct_of_budget": round(100.0 * (ms / 1000.0) / BUDGET_S, 1),
        "over_budget": ms / 1000.0 > BUDGET_S,
        "exit": p.returncode,
        "emitted": bool(ctx),
        "finding_count": len(f),
        "findings": f,
        "context": ctx,
        "self_consistent": bool(ctx) == (len(f) > 0),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # HEAD blob -> the unfixed arm.
    blob = subprocess.run(
        ["git", "-C", str(REPO), "show", "HEAD:hooks/wire-check/check.py"],
        capture_output=True,
        timeout=60,
    )
    if blob.returncode != 0 or not blob.stdout:
        print("FAILED:b3-ab-budget could not read HEAD blob of check.py")
        return 1
    unfixed = OUT / "_b3_check_head.py"
    unfixed.write_bytes(blob.stdout)  # bytes, so no newline re-encoding
    had_encoding = b'encoding="utf-8"' in blob.stdout
    fixed = REPO / "hooks" / "wire-check" / "check.py"

    rows = []
    # Interleave A,B,A,B so a background load spike cannot land on one arm only.
    for rnd in (1, 2):
        rows.append({**run_hook(unfixed, f"HEAD-unfixed-r{rnd}"), "round": rnd})
        rows.append({**run_hook(fixed, f"worktree-fixed-r{rnd}"), "round": rnd})

    res = {
        "head_blob_already_had_encoding_kwarg": had_encoding,
        "note": "if head_blob_already_had_encoding_kwarg is true the A arm is NOT a"
        " control and this whole comparison is void",
        "runs": rows,
    }
    (OUT / "B3-AB-BUDGET.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(
        f"HEAD blob already contains encoding= kwarg: {had_encoding}  (must be False)"
    )
    print(
        f"{'arm':26s} {'wall_ms':>10s} {'%budget':>8s} {'over':>5s} {'finds':>6s} consistent"
    )
    for r in rows:
        print(
            f"{r['arm']:26s} {r['wall_ms']:10.1f} {r['pct_of_budget']:7.1f}% "
            f"{str(r['over_budget']):>5s} {r['finding_count']:6d} {r['self_consistent']}"
        )
    if not rows or any(r["wall_ms"] <= 0 for r in rows):
        print("FAILED:b3-ab-budget an arm produced no timing")
        return 1
    if had_encoding:
        print("FAILED:b3-ab-budget the A arm is not an unfixed control")
        return 1
    print("SUCCESS:b3-ab-budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
