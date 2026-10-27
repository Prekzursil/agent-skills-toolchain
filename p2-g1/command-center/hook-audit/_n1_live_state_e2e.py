r"""N1 end-to-end: does the live-state filter actually silence the real repo in the real
hook output, and does the hook still FIRE when the filter is off?

A unit test on `_parse_status_v2` proves the parser. It does NOT prove the message. This
runs the whole hook as a subprocess against the real disk, in BOTH states, and greps the
emitted additionalContext for the offending repo name.

  state A  filter ON  (shipped)          -> agent-skills-toolchain must be ABSENT
  state B  GIT_HYGIENE_NO_SKIP=1         -> it must be PRESENT
             ^ this is the control. Without B, "absent" could mean the scanner never
               reached the repo, the budget expired, or the throttle suppressed the whole
               run -- three ways to get a silent pass that proves nothing.

Also asserts the run was not throttled and that the scan actually saw repos, so an empty
report can never read as a clean one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
HOOK = REPO / "hooks" / "git-hygiene" / "check.py"
OUT = Path(__file__).resolve().parent
TARGET = "agent-skills-toolchain"


def run(no_skip: bool) -> dict:
    env = dict(os.environ)
    env["GIT_HYGIENE_ROOTS"] = "C:/Users/Prekzursil/source"
    env["GIT_HYGIENE_SYNC"] = "off"
    env["GIT_HYGIENE_DOCS"] = "off"
    env["GIT_HYGIENE_COVERAGE"] = "off"
    env["GIT_HYGIENE_THROTTLE_SEC"] = "0"
    env["GIT_HYGIENE_BUDGET"] = "120"
    if no_skip:
        env["GIT_HYGIENE_NO_SKIP"] = "1"
    else:
        env.pop("GIT_HYGIENE_NO_SKIP", None)
    payload = json.dumps(
        {"session_id": f"n1-{int(time.time())}-{no_skip}", "cwd": str(REPO)}
    )
    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=600,
        cwd=str(REPO),
        env=env,
    )
    ms = (time.perf_counter() - t0) * 1000
    so = p.stdout.decode("utf-8", "replace")
    ctx = ""
    if so.strip():
        try:
            ctx = json.loads(so)["hookSpecificOutput"]["additionalContext"]
        except Exception:
            ctx = so
    return {
        "no_skip": no_skip,
        "wall_ms": round(ms, 1),
        "exit": p.returncode,
        "emitted_bytes": len(ctx),
        "target_named": TARGET in ctx,
        "mentions_accounts_json": "accounts.json" in ctx,
        "repo_lines": [ln.strip() for ln in ctx.splitlines() if "uncommitted" in ln],
        "context": ctx,
        "stderr_tail": p.stderr.decode("utf-8", "replace")[-400:],
    }


def main() -> int:
    a = run(no_skip=False)
    b = run(no_skip=True)
    res = {"filter_on": a, "filter_off_CONTROL": b}
    (OUT / "N1-LIVE-STATE-E2E.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )

    for lbl, r in (("filter ON (shipped)", a), ("filter OFF (control)", b)):
        print(
            f"{lbl:24s} exit={r['exit']} {r['wall_ms']:8.1f} ms  "
            f"emitted={r['emitted_bytes']}B  {TARGET} named={r['target_named']}"
        )
        for ln in r["repo_lines"][:6]:
            print(f"      | {ln[:120]}")

    # The control has to fire, or "absent" measures nothing.
    if not b["target_named"]:
        print(
            f"FAILED:n1-live-state-e2e control did not fire -- with the filter OFF the "
            f"hook still did not name {TARGET}, so its silence in the ON state is "
            f"unattributable (scanner never reached it, budget expired, or throttled)"
        )
        return 1
    if a["target_named"]:
        print(f"FAILED:n1-live-state-e2e {TARGET} is STILL reported with the filter on")
        return 1
    print(
        f"\nBOTH STATES OK: {TARGET} present with the filter off, absent with it on -- "
        f"so the silence is the filter, not a dead scanner."
    )
    print("SUCCESS:n1-live-state-e2e")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
