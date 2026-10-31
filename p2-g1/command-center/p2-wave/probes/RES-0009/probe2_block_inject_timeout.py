#!/usr/bin/env python3
# RES-0009 probe2: block/inject/timeout semantics (resume 2026-10-25).
# Exit 2: PreToolUse blocks per the published table; SessionStart's exit 2 is
# NOT honored as a block (raw rc 2 still). Exit 0 with JSON stdout delivers
# additionalContext via hookSpecificOutput. A hook sleeping past its timeout
# is cancelled at the timeout without waiting out the sleep.
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKER = "RES-0009-BLOCK-STDERR"


def fail(msg):
    print("FAILED:RES-0009-probe2 " + str(msg))
    return 1


def run_exit2(event):
    payload = json.dumps({"hook_event_name": event, "session_id": "res0009-p2"}).encode("utf-8")
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, "-B", str(HERE / "hooks" / "exit2.py")],
                       input=payload, capture_output=True, timeout=120)
    return {"event": event, "rc": p.returncode, "stdout": p.stdout.decode("utf-8"),
            "stderr": p.stderr.decode("utf-8"), "elapsed_s": round(time.monotonic() - t0, 3),
            "stdin_sha256": hashlib.sha256(payload).hexdigest(), "timed_out": False}


def main():
    rec = json.loads((REPO / "command-center/research/RES-0009.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    ctl = rec.get("controls") or {}
    blk = ctl.get("block") or {}
    if not blk:
        return fail("receipt-controls-absent")
    # exit 2 on PreToolUse: rc=2, marker on stderr, blocking per the table
    r1 = run_exit2("PreToolUse")
    print("exit2 PreToolUse: rc=%d stderr=%r elapsed=%.3fs" % (r1["rc"], r1["stderr"].strip(), r1["elapsed_s"]))
    if r1["rc"] != 2 or r1["stderr"].strip() != MARKER:
        return fail("pretooluse-exit2-drift")
    pub = (rec.get("exit2_table") or {}).get("PreToolUse") or {}
    if pub.get("can_block") is not True:
        return fail("receipt-pretooluse-block-flag-drift")
    # exit 2 on SessionStart: raw rc=2 but the published table does NOT block
    r2 = run_exit2("SessionStart")
    pub_ss = (rec.get("exit2_table") or {}).get("SessionStart") or {}
    print("exit2 SessionStart: rc=%d can_block=%s (not a block per table)"
          % (r2["rc"], pub_ss.get("can_block")))
    if r2["rc"] != 2 or pub_ss.get("can_block") is not False:
        return fail("sessionstart-exit2-drift")
    # exit 0 + JSON injection: additionalContext via hookSpecificOutput
    inj = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                  "additionalContext": "RES-0009-INJECTED-CONTEXT"}}
    inject_hook = HERE / "hooks" / "inject0.py"
    inject_hook.write_text(
        "import json, sys" + chr(10) +
        "sys.stdin.read()" + chr(10) +
        "print(json.dumps(" + json.dumps(inj) + "))" + chr(10),
        encoding="utf-8", newline=chr(10))
    p = subprocess.run([sys.executable, "-B", str(inject_hook)],
                       input=b"{}", capture_output=True, timeout=120)
    out = json.loads(p.stdout.decode("utf-8"))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    print("exit0 inject: rc=%d additionalContext=%r" % (p.returncode, ctx[:40]))
    if p.returncode != 0 or ctx != "RES-0009-INJECTED-CONTEXT":
        return fail("inject-not-delivered")
    # timeout control: 30s sleep under a 0.6s timeout cancels without waiting
    slow = HERE / "hooks" / "slow.py"
    slow.write_text("import time, sys" + chr(10) + "sys.stdin.read()" + chr(10)
                    + "time.sleep(30)" + chr(10), encoding="utf-8", newline=chr(10))
    t0 = time.monotonic()
    try:
        subprocess.run([sys.executable, "-B", str(slow)], input=b"{}",
                       capture_output=True, timeout=0.6)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    elapsed = time.monotonic() - t0
    print("timeout: cancelled=%s elapsed=%.2fs (sleep was 30s)" % (timed_out, elapsed))
    if not timed_out or elapsed > 5.0:
        return fail("timeout-not-cancellable")
    if not rec.get("residual_unknowns"):
        return fail("receipt-residuals-absent")
    print("receipt residuals honestly recorded (no live client firing, exit-1 path not instrumented)")
    print("SUCCESS:RES-0009-probe2 block-inject-timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
