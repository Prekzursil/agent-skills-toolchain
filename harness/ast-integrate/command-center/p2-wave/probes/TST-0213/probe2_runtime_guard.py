#!/usr/bin/env python3
"""TST-0213 probe2: runtime guard refuses a planted mutation in a test build."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.lib.credential_mutation import (  # noqa: E402
    attempt_planted_mutation,
    policy_anchor,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0213-probe2 {msg}")
    return 1


def main() -> int:
    unguarded = attempt_planted_mutation(guarded=False)
    guarded = attempt_planted_mutation(guarded=True)
    policy = policy_anchor()
    js_cmd = [
        "node",
        str(REPO / "tools/lib/security.mjs"),
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        js_cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    js_text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    summary = {
        "probe": "probe2-runtime-guard",
        "unguarded": unguarded,
        "guarded": guarded,
        "policy": policy,
        "security_mjs_exit": proc.returncode,
        "security_mjs_tail": js_text[-1500:],
    }
    print(json.dumps(summary, sort_keys=True))
    if not unguarded.get("reachable"):
        return fail("unguarded planted revoke_token was not reachable (vacuous guard)")
    if not guarded.get("refused"):
        return fail("runtime guard did not refuse planted revoke_token")
    if not guarded.get("cites_policy"):
        return fail("refusal did not cite AGENTS.md:9")
    if not policy.get("phrase_present") or not policy.get("agents_md9_cited"):
        return fail(f"policy anchor missing: {policy}")
    if proc.returncode != 0:
        return fail(f"security.mjs exit {proc.returncode}: {js_text[-500:]}")
    if "SUCCESS:security.mjs" not in js_text:
        return fail("security.mjs missing SUCCESS sentinel")
    print("SUCCESS:TST-0213-probe2 runtime guard refused planted mutation; AGENTS.md:9 cited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
