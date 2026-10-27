"""LANE B / R-M07 probe: what does the deny-credential-reads hook actually COST per call?

Read-only. Feeds the hook a synthetic PreToolUse Read payload on a NON-sensitive path and
times the whole process, N times, against two baselines:
  * `python -c pass`            -> pure interpreter-spawn floor
  * the hook with the guard ON  -> the matching path (does the toggle change the cost?)
Also reports whether HARNESS_CREDENTIAL_GUARD is set anywhere the hook would see it.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "deny-credential-reads" / "deny.py"
LIVE_HOOK = Path(os.path.expanduser("~")) / ".claude" / "hooks" / "deny-credential-reads" / "deny.py"

PAYLOAD = json.dumps(
    {"tool_name": "Read", "tool_input": {"file_path": str(REPO / "README.md")}}
).encode()

N = 7


def timed(argv, payload, env=None) -> list[float]:
    out = []
    for _ in range(N):
        t0 = time.perf_counter()
        subprocess.run(argv, input=payload, capture_output=True, env=env)
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def summ(xs):
    return {
        "n": len(xs),
        "median_ms": round(statistics.median(xs), 1),
        "min_ms": round(min(xs), 1),
        "max_ms": round(max(xs), 1),
    }


base_env = dict(os.environ)
base_env.pop("HARNESS_CREDENTIAL_GUARD", None)
on_env = dict(base_env)
on_env["HARNESS_CREDENTIAL_GUARD"] = "1"

res = {
    "guard_env_set_in_this_process": os.environ.get("HARNESS_CREDENTIAL_GUARD"),
    "hook_repo": str(HOOK),
    "hook_live_exists": LIVE_HOOK.is_file(),
    "interpreter_floor_python_c_pass": summ(timed([sys.executable, "-c", "pass"], b"")),
    "hook_guard_OFF_read_nonsensitive": summ(
        timed([sys.executable, str(HOOK)], PAYLOAD, base_env)
    ),
    "hook_guard_ON_read_nonsensitive": summ(
        timed([sys.executable, str(HOOK)], PAYLOAD, on_env)
    ),
}
if LIVE_HOOK.is_file():
    res["live_hook_guard_OFF"] = summ(timed([sys.executable, str(LIVE_HOOK)], PAYLOAD, base_env))

# detector control: the hook MUST deny a sensitive path when the guard is ON
sens = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "C:/tmp/.env"}}).encode()
p_on = subprocess.run([sys.executable, str(HOOK)], input=sens, capture_output=True, env=on_env)
p_off = subprocess.run([sys.executable, str(HOOK)], input=sens, capture_output=True, env=base_env)
res["control_sensitive_guard_ON_stdout"] = p_on.stdout.decode()[:180]
res["control_sensitive_guard_OFF_stdout"] = p_off.stdout.decode()[:180]

print(json.dumps(res, indent=2))
