#!/usr/bin/env python
"""Golden acceptance test for the self-calibration hooks.

Proves the wiring is NOT a silent no-op (the user's exact named failure: "reports healthy,
silently does nothing"). Uses NON-SYMMETRIC fixtures (the AXIS-GOTCHA lesson: a symmetric
fixture can pass while the logic is inverted). Run:  python test_hooks.py
Exit 0 = all pass.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

H = pathlib.Path.home() / ".claude" / "hooks"
results = []


def run_hook(script, payload, env=None):
    p = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                       capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    return p.stdout


def check(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


# 1. recall-first FIRES on a substantial prompt
o = run_hook(H / "inquisitiveness" / "prompt-guard.py", {"prompt":
    "please reverse engineer the battle cats event scheduler and find exactly where the "
    "date gate is verified inside the binary so events render correctly"})
check("recall-first injects on a substantial prompt", "Recall-first" in o)

# 2a. fingerprint TRIPS on 3x identical (tool,args,output) RE-tool calls
fp = H / "anti-degen" / "fingerprint.py"
sid = "golden-" + os.urandom(3).hex()
pay = {"session_id": sid, "tool_name": "mcp__ida-pro-mcp__decompile",
       "tool_input": {"addr": "0x1000"}, "tool_response": "identical output"}
out3 = ""
for _ in range(3):
    out3 = run_hook(fp, pay)
check("fingerprint trips on 3x identical RE-tool call", "repeated" in out3.lower())

# 2b. NON-SYMMETRIC: when the OUTPUT changes (progress), it must stay SILENT
sid2 = "golden2-" + os.urandom(3).hex()
last = "x"
for i in range(3):
    last = run_hook(fp, {**pay, "session_id": sid2, "tool_response": f"different {i}"})
check("fingerprint stays SILENT when output changes (real progress)", last.strip() == "")

# 3. falsify-check FIRES on a write-op at the falsify cadence
o = run_hook(H / "goal-reinject" / "reinject.py",
             {"tool_name": "Write", "session_id": "golden-fz", "cwd": "."},
             env={"GOAL_FALSIFY_INTERVAL": "1", "GOAL_REINJECT_COUNTER_ROOT": tempfile.mkdtemp()})
check("falsify-check fires on a write-op", "FALSIFY-CHECK" in o)

# 4. capture-writer MIRRORS a milestone into .beads/knowledge (success-gated, no CI exit needed)
tmp = tempfile.mkdtemp()
(pathlib.Path(tmp) / ".beads" / "knowledge").mkdir(parents=True)
env = {"EVENT_LEDGER_ROOT": os.path.join(tmp, "ledger")}
subprocess.run([sys.executable, "-c",
                "import sys;sys.path.insert(0,r'%s');import ledger;"
                "ledger.append(r'%s','milestone',text='cracked the date gate at sub_525AB0')"
                % (str(H / "event-ledger"), tmp)],
               env={**os.environ, **env})
run_hook(H / "event-ledger" / "stop-hook.py", {"cwd": tmp}, env=env)
dec = pathlib.Path(tmp) / ".beads" / "knowledge" / "decisions.jsonl"
got = dec.read_text(encoding="utf-8") if dec.exists() else ""
check("capture-writer mirrors a milestone into .beads/knowledge", "cracked the date gate" in got)

print("\n%d/%d PASS" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
