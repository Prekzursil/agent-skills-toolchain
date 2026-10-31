import pathlib
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
REV = "673cd180"
PATHS = [
    "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md",
    "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md",
    "docs/mcp-audit/MCP-CAPABILITY-AND-DISPOSITION.md",
    "docs/mcp-audit/DISPOSITION-TABLE.md",
    "command-center/mcp-audit/disposition.json",
    "command-center/mcp-audit/ruff-census.json",
    "command-center/mcp-audit/_r3_redproof_liveness.py",
    "command-center/mcp-audit/_r3_gate_sweep.py",
    "command-center/mcp-audit/_r3_hunt.py",
    "command-center/mcp-audit/_r2_dod_check.py",
    "command-center/mcp-audit/rank_disposition.py",
    "command-center/mcp-audit/_r2_redproof_invariants.py",
    "command-center/mcp-audit/_r3_gate_sweep.out.txt",
]
print(f"{'path':58} {'blob B':>8} {'CRLF':>6}")
for p in PATHS:
    out = subprocess.run(
        ["git", "show", f"{REV}:{p}"], cwd=REPO, capture_output=True
    )
    if out.returncode != 0:
        print(f"{p:58} MISSING FROM BLOB")
        continue
    b = out.stdout
    print(f"{p:58} {len(b):>8} {b.count(b'\\r\\n'):>6}")

# CONTROL: the counter must be able to report non-zero.  Feed it a known-CRLF buffer.
ctl = b"a\r\nb\r\nc\r\n"
print(f"\nCONTROL known-CRLF buffer -> count={ctl.count(b'\\r\\n')} (want 3); "
      f"known-LF buffer -> count={b'a\\nb\\n'.count(b'\\r\\n')} (want 0)")

# Second control, mechanically different: the builder's own claim was that AGENTS.md
# reads 112 CRLF.  Re-measure it independently.
for p in ("AGENTS.md", "README.md"):
    out = subprocess.run(["git", "show", f"{REV}:{p}"], cwd=REPO, capture_output=True)
    if out.returncode == 0:
        print(f"{p:58} {len(out.stdout):>8} {out.stdout.count(b'\\r\\n'):>6}")
