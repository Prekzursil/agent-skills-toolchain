"""AUDIT: decisive check of the ONE claimed cycle: tools.crcp.crcp.sentinel <-> write_path.

Reads the two files' import statements directly. No graph, no SCC, no resolver -- just the source.
Also stress-tests my own SCC from _audit_graph.py on a 3-cycle to rule out an instrument bug.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
cand = [
    REPO / "tools/crcp/crcp/sentinel.py",
    REPO / "tools/crcp/crcp/write_path.py",
]
print("=== does the claimed cycle pair even exist on disk? ===")
for c in cand:
    print(f"  {c.relative_to(REPO).as_posix():<40} exists={c.is_file()}")

print()
print("=== raw import statements in each ===")
for c in cand:
    if not c.is_file():
        continue
    tree = ast.parse(c.read_text(encoding="utf-8", errors="replace"))
    print(f"--- {c.name} ---")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                print(f"    line {node.lineno}: import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            print(
                f"    line {node.lineno}: from {'.' * node.level}{node.module or ''} import "
                f"{', '.join(a.name for a in node.names)}"
            )

print()
print("=== is tools/crcp inside my scanned set? ===")
allpy = [p for p in (REPO / "tools").rglob("*.py") if "__pycache__" not in p.parts]
crcp = [p for p in allpy if "crcp" in p.parts]
print(f"  total .py under tools/ : {len(allpy)}")
print(f"  .py under a 'crcp' dir : {len(crcp)}")
for p in crcp[:12]:
    print(f"     {p.relative_to(REPO).as_posix()}")

print()
print("=== INSTRUMENT CONTROL: my SCC on a 3-cycle and a 2-cycle ===")
import importlib.util  # noqa: E402  (deliberate late import: section-local probe)

s = importlib.util.spec_from_file_location(
    "ag", REPO / "command-center/p2-wave/_audit_graph.py"
)
# don't exec (it runs the full scan); re-implement the check inline instead using networkx-free DFS


def find_cycles(nodes, edges):
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)
    color, out = {}, []

    def dfs(u, stack):
        color[u] = 1
        stack.append(u)
        for v in adj[u]:
            if color.get(v, 0) == 1:
                out.append(stack[stack.index(v) :] + [v])
            elif color.get(v, 0) == 0:
                dfs(v, stack)
        stack.pop()
        color[u] = 2

    for n in nodes:
        if color.get(n, 0) == 0:
            dfs(n, [])
    return out


print(f"  2-cycle a<->b : {find_cycles(['a', 'b'], [('a', 'b'), ('b', 'a')])}")
print(
    f"  3-cycle a>b>c>a : {find_cycles(['a', 'b', 'c'], [('a', 'b'), ('b', 'c'), ('c', 'a')])}"
)
print(f"  acyclic a>b   : {find_cycles(['a', 'b'], [('a', 'b')])}")
