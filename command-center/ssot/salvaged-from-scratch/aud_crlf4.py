import subprocess

CRLF = bytes([13, 10])
LF = bytes([10])
REPO = "C:/Users/Prekzursil/source/ast-integrate"
assert bytes([13, 10, 13, 10]).count(CRLF) == 2, "detector broken"
print("control PASSED\n")

# The shipped sentence (ROUND3-DEFECT-CLOSURE.md:228-230) says the .md/.json blobs
# "carry CRLF (ROUND3-DEFECT-CLOSURE.md 278, disposition.json 840)".
# Test the two numbers it names, at the commit where each was written.
CASES = [
    ("bfec0543", "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md", 278),
    ("0d3c9e93", "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md", 278),
    ("673cd180", "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md", 278),
    ("bfec0543", "command-center/mcp-audit/disposition.json", 840),
    ("673cd180", "command-center/mcp-audit/disposition.json", 840),
]
print(f"{'rev':10} {'path':46} {'claimed':>8} {'CRLF':>6} {'LF':>6}")
for rev, p, claimed in CASES:
    b = subprocess.run(
        ["git", "show", f"{rev}:{p}"], cwd=REPO, capture_output=True
    ).stdout
    print(f"{rev:10} {p:46} {claimed:>8} {b.count(CRLF):>6} {b.count(LF):>6}")

print("\nInterpretation test: is the claimed number the CRLF count or the LINE count?")
for rev, p, claimed in CASES:
    b = subprocess.run(
        ["git", "show", f"{rev}:{p}"], cwd=REPO, capture_output=True
    ).stdout
    print(f"  {rev} {p.split('/')[-1]:32} "
          f"claimed=={b.count(CRLF)} (CRLF)? {claimed == b.count(CRLF)}   "
          f"claimed=={b.count(LF)} (lines)? {claimed == b.count(LF)}")
