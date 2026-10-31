"""Patch main() verdict gate to read the adjudication field (line-targeted)."""
import io

P = r"C:\Users\Prekzursil\p2-g1\_rev2-w2-shard2\close_shard2_w2.py"
lines = io.open(P, encoding="utf-8").read().splitlines(True)
for i, ln in enumerate(lines):
    if 'if codex and codex.get("verdict") == "PASS":' in ln:
        indent = ln[: len(ln) - len(ln.lstrip())]
        lines[i] = (
            indent + 'codex_pass = bool(codex) and str(codex.get('
            '"primary_reviewer_adjudication", "")).startswith("PASS")\n'
            + indent + "if codex_pass:\n"
        )
        print("patched line", i + 1)
io.open(P, "w", encoding="utf-8", newline="\n").write("".join(lines))
