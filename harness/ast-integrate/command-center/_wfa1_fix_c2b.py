"""C2 final: parse the VIOLATIONS tuple with ast (exact algorithm, not a regex)
and cross-check against a second, mechanically different counter (line-based
extraction of the literal block). Both must agree before I report a number.
"""

import ast
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


v = blob("tools/agentspec/agentspec/validate.py") or ""

# --- signal A: AST ---
ids_ast = None
tree = ast.parse(v)
for node in ast.walk(tree):
    if (
        isinstance(node, ast.AnnAssign)
        and getattr(node.target, "id", None) == "VIOLATIONS"
    ):
        ids_ast = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if getattr(t, "id", None) == "VIOLATIONS":
                ids_ast = [
                    e.value for e in node.value.elts if isinstance(e, ast.Constant)
                ]

# --- signal B: raw text block slice ---
m = re.search(r"VIOLATIONS[^=]*=\s*\((.*?)\)\s*\n", v, re.S)
ids_txt = re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []

print(f"signal A (ast)   n={len(ids_ast or [])}")
print(f"signal B (regex) n={len(ids_txt)}")
print(f"AGREE: {sorted(ids_ast or []) == sorted(ids_txt)}")
print()
for i, x in enumerate(ids_ast or [], 1):
    print(f"  {i:>3}. {x}")

rd = blob("tools/agentspec/README.md") or ""
claim = re.search(r"closed\s+(\d+)-id", rd)
print(
    f"\nREADME claim = {claim.group(1) if claim else '?'}   measured = {len(ids_ast or [])}"
)
print(
    "VERDICT: CONFIRMED"
    if claim and int(claim.group(1)) == len(ids_ast or [])
    else "VERDICT: MISMATCH -> report both numbers"
)

# detector control: the same AST walker must find a DIFFERENT known tuple, and
# must return nothing for a name that does not exist.
found_other = False
for node in ast.walk(tree):
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target
        nm = getattr(tgt, "id", None)
        if (
            nm
            and nm != "VIOLATIONS"
            and isinstance(getattr(node, "value", None), (ast.Tuple, ast.List))
        ):
            print(f"[CTRL] walker also finds tuple/list '{nm}' -> walker works")
            found_other = True
            break
print(
    f"[CTRL] known-absent name 'NOPE_VIOLATIONS' found = "
    f"{any(getattr(getattr(n, 'target', None), 'id', None) == 'NOPE_VIOLATIONS' for n in ast.walk(tree))} (must be False)"
)
if not found_other:
    print("[CTRL] no second tuple in this module (control inconclusive on that leg)")
