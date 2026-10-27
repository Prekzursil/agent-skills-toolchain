"""Extract EXACT stop-rule / termination text for the candidates where guessing
would be fabrication: rtv-pdr rounds, ese-gate escalation threshold, the two
gates' verdict conditions, agentrail retry/stop_condition, agentspec oracle.
"""

import re
import subprocess

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"


def blob(path):
    r = subprocess.run(
        ["git", "--git-dir", MIRROR, "cat-file", "-p", f"{REF}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or "") if r.returncode == 0 else None


def live(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def show(title, text, pats, ctx=0, limit=14):
    print(f"\n===== {title} =====")
    if not text:
        print("  (unreadable)")
        return
    lines = text.splitlines()
    hits = 0
    for i, ln in enumerate(lines):
        if any(re.search(p, ln, re.I) for p in pats):
            for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
                print(f"  {j + 1:>4}: {lines[j].strip()[:170]}")
            hits += 1
            if hits >= limit:
                print("  ... (truncated)")
                break
    if not hits:
        print("  no match")


show(
    "rtv-pdr rounds / winner / termination",
    blob("workflows/rtv-pdr.js"),
    [r"\brounds?\b", r"\bwinner\b", r"while\b", r"until\b", r"\bn\s*=", r"tournament"],
    limit=20,
)

show(
    "ese-gate escalate decision + threshold",
    blob("tools/ese-gate/ese_gate.py"),
    [r"escalate", r"threshold", r"entropy\s*[<>=]", r"def _build_verdict"],
    limit=20,
)

show(
    "plan-gate verdict / blocking condition",
    live(r"C:\Users\Prekzursil\.claude\workflows\plan-gate.mjs"),
    [r"blocking", r"verdict", r"FAIL", r"PASS"],
    limit=18,
)

show(
    "design-gate verdict / blocking condition",
    live(r"C:\Users\Prekzursil\.claude\workflows\design-gate.mjs"),
    [r"blocking", r"verdict", r"approve"],
    limit=14,
)

show(
    "agentrail error.stop_condition / retry",
    blob("tools/agentrail/agentrail/runner.py"),
    [r"stop_condition", r"retry_instruction", r"terminal"],
    limit=16,
)

show(
    "agentspec oracle completion (AND-gate)",
    blob("tools/agentspec/agentspec/oracle.py"),
    [r"def ", r"exit", r"receipt", r"and\b"],
    limit=22,
)

show(
    "codex-auth-research-fanout UNIT-COMPLETE gate",
    live(r"C:\Users\Prekzursil\.claude\workflows\codex-auth-research-fanout.mjs"),
    [r"UNIT-COMPLETE", r"AND-gate", r"resume"],
    limit=16,
)
