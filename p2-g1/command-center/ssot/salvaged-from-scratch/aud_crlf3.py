import subprocess

CRLF = bytes([13, 10])
LF = bytes([10])
REPO = "C:/Users/Prekzursil/source/ast-integrate"

good = bytes([97, 13, 10, 98, 13, 10])
assert good.count(CRLF) == 2, "detector broken"
print("control PASSED (known-CRLF buffer -> 2)\n")

# Round 2's committed table, verbatim, with the number it printed under "CRLF lines".
ROUND2_TABLE = {
    "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md": 248,
    "command-center/mcp-audit/ruff-census.json": 28,
    "docs/mcp-audit/MCP-FLEET-AUDIT.md": 355,
    "README.md": 328,
    "AGENTS.md": 112,
}
# H1: those are CRLF counts -> at the round-2 commit each file should show that many CRLF.
# H2: those are LINE counts mislabelled -> each file shows that many LF and ZERO CRLF.
print("Measured at the ROUND-2 commit 630bb8af (the state round 2 described):")
print(f"{'path':48} {'r2 said':>8} {'CRLF':>6} {'LF':>6}  H1? H2?")
h1 = h2 = 0
for p, n in ROUND2_TABLE.items():
    out = subprocess.run(
        ["git", "show", f"630bb8af:{p}"], cwd=REPO, capture_output=True
    )
    if out.returncode != 0:
        print(f"{p:48} MISSING AT 630bb8af")
        continue
    b = out.stdout
    c, l = b.count(CRLF), b.count(LF)
    a, d = (c == n), (l == n and c == 0)
    h1 += a
    h2 += d
    print(f"{p:48} {n:>8} {c:>6} {l:>6}  {'Y' if a else 'n'}   {'Y' if d else 'n'}")
print(f"\nH1 (numbers are CRLF counts) matches {h1}/{len(ROUND2_TABLE)}")
print(f"H2 (numbers are LINE counts, 0 CRLF) matches {h2}/{len(ROUND2_TABLE)}")

print("\n--- does commit 7aa86f16 exist, and did it touch README.md? ---")
for args in (["cat-file", "-t", "7aa86f16"],
             ["log", "--oneline", "-1", "7aa86f16"],
             ["show", "--stat", "--oneline", "7aa86f16"]):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    print(f"$ git {' '.join(args)}  -> rc={r.returncode}")
    print((r.stdout or r.stderr).strip()[:500])
