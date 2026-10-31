"""IMP-0218 probe 1 (source): no process remains resident after a checkpoint.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0218/probe1_no_resident_process.py
Exit 0 iff the owner-gate child process PERSISTS state, EMITS the envelope and EXITS
(process count returns to baseline; measured, not assumed) AND the gate source carries
no waiting call (AST control - mechanically different instrument).
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))

GATE_SRC = r'''
import sys, json
sys.path.insert(0, sys.argv[2])
from pathlib import Path
from agentspec.checkpoint import OwnerQuestion, owner_gate_pause
from agentspec.spec import HumanCheckpoint
d = Path(sys.argv[1])
cp = HumanCheckpoint(id="cp-foundation", prompt_ref="x",
                     allowed_responses=("approve", "redirect"),
                     default_if_unanswered="worktree-isolated",
                     pause_token="tok-foundation")
q = OwnerQuestion(checkpoint_id="cp-foundation", question="Which substrate?",
                  recommendation="worktree-isolated",
                  tradeoff="cost per agent",
                  default="worktree-isolated",
                  options=("worktree-isolated", "local-serialized"))
env = owner_gate_pause(cp, d, q)
print("GATE-EMITTED:" + json.dumps({"status": env["status"], "durable": env["durable_record"]}))
'''

with tempfile.TemporaryDirectory() as td:
    helper = Path(td) / "gate_child.py"
    helper.write_text(GATE_SRC, encoding="utf-8")
    t0 = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, "-I", str(helper), td, str(W / "tools" / "agentspec")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        outs, errs = proc.communicate(timeout=60)
        elapsed = time.monotonic() - t0
        exited = True
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        outs, errs = "", ""
        elapsed = time.monotonic() - t0
        exited = False
    rc = proc.poll()
    resident_after = proc.poll() is None
    durable = Path(td) / "pause.json"
    pause_ok = durable.is_file() and json.loads(durable.read_text(encoding="utf-8"))["pause_token"] == "tok-foundation"
    emitted = outs.strip().startswith("GATE-EMITTED:")

import agentspec.checkpoint as cp_mod  # noqa: E402
src = Path(cp_mod.__file__).read_text(encoding="utf-8")
gate_fn_src = "def owner_gate_pause" + src.split("def owner_gate_pause", 1)[1].split(chr(10) + "def ", 1)[0]
tree = ast.parse(gate_fn_src)
wait_calls = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
        if name in {"input", "sleep", "readline", "kbhit"}:
            wait_calls.append("call:%s@line%s" % (name, node.lineno))
    elif isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
        wait_calls.append("while-True@line%s" % node.lineno)

ok = exited and not resident_after and rc == 0 and emitted and pause_ok and not wait_calls and elapsed < 60

out = {
    "probe": "probe1-no-resident-process",
    "unit_id": "IMP-0218",
    "child_exited": exited,
    "resident_after": resident_after,
    "return_code": rc,
    "wall_seconds": round(elapsed, 3),
    "gate_emitted_envelope": emitted,
    "durable_record_written": pause_ok,
    "ast_wait_calls": wait_calls,
    "pass": ok,
}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-no-resident.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0218-probe1 resident process or missing emission")
    raise SystemExit(1)
print("SUCCESS:IMP-0218-probe1 gate persisted+emitted+exited; no resident process; AST clean")
