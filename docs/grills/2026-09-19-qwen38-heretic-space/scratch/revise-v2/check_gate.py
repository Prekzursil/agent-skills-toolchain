"""Mechanical checks on gate.sh: every <<'PYEOF' heredoc and every python -c one-liner must parse (ast.parse)."""
import ast, re, sys, subprocess, pathlib
p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "gate.sh")
src = p.read_text()
r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else "FAIL " + r.stderr)
blocks = re.findall(r"<<'PYEOF'.*?\n(.*?)\nPYEOF", src, re.S)
ok = 0
for i, b in enumerate(blocks, 1):
    try: ast.parse(b); ok += 1
    except SyntaxError as e: print("heredoc", i, "FAIL", e); print(b[:300])
print(f"heredocs: {ok}/{len(blocks)} parse")
ones = re.findall(r"""-c '((?:[^'\\]|\\.)*)'""", src)
ok1 = 0
for o in ones:
    try: ast.parse(o); ok1 += 1
    except SyntaxError as e: print("one-liner FAIL", e, o[:120])
print(f"one-liners: {ok1}/{len(ones)} parse")
sys.exit(0 if r.returncode == 0 and ok == len(blocks) and ok1 == len(ones) else 1)
