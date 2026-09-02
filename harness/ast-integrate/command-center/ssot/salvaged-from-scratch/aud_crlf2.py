import subprocess

# Built from ordinals so no escape can be mangled by the writing tool or the f-string.
CRLF = bytes([13, 10])
LF = bytes([10])

REPO = "C:/Users/Prekzursil/source/ast-integrate"
REV = "673cd180"

# CONTROL FIRST -- my previous run used b'\\r\\n' (four literal chars) and reported 0
# everywhere; the control caught it.  Prove the counter fires before trusting a zero.
good = bytes([97, 13, 10, 98, 13, 10, 99, 13, 10])
bad = bytes([97, 10, 98, 10])
print(f"CONTROL known-CRLF buffer -> {good.count(CRLF)} (want 3)")
print(f"CONTROL known-LF   buffer -> {bad.count(CRLF)} (want 0)")
assert good.count(CRLF) == 3 and bad.count(CRLF) == 0, "detector broken, refusing to report"
print("control PASSED\n")

PATHS = [
    "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md",
    "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md",
    "docs/mcp-audit/MCP-CAPABILITY-AND-DISPOSITION.md",
    "docs/mcp-audit/DISPOSITION-TABLE.md",
    "command-center/mcp-audit/disposition.json",
    "command-center/mcp-audit/ruff-census.json",
    "command-center/mcp-audit/_r3_gate_sweep.out.txt",
    "command-center/mcp-audit/_r3_redproof_liveness.py",
    "command-center/mcp-audit/_r3_gate_sweep.py",
    "command-center/mcp-audit/_r3_hunt.py",
    "command-center/mcp-audit/_r2_dod_check.py",
    "command-center/mcp-audit/rank_disposition.py",
    "command-center/mcp-audit/_r2_redproof_invariants.py",
    "AGENTS.md",
    "README.md",
]
print(f"{'path':56} {'blobB':>7} {'CRLF':>6} {'bareLF':>7}")
for p in PATHS:
    out = subprocess.run(["git", "show", f"{REV}:{p}"], cwd=REPO, capture_output=True)
    if out.returncode != 0:
        print(f"{p:56} MISSING")
        continue
    b = out.stdout
    crlf = b.count(CRLF)
    print(f"{p:56} {len(b):>7} {crlf:>6} {b.count(LF) - crlf:>7}")
