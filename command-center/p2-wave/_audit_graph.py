"""AUDIT (independent): re-derive the tools/ import graph and cycles with my OWN AST walk + SCC.

Independent of the builder's resolver. Includes a planted-cycle control (both states).
"""
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


def modname(p: Path) -> str:
    rel = p.relative_to(REPO).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect(root):
    mods = {}
    for p in root.rglob("*.py"):
        if any(s in p.parts for s in SKIP):
            continue
        mods[modname(p)] = p
    return mods


mods = collect(TOOLS)
print(f"  .py files under tools/ (skipping {sorted(SKIP)}) : {len(mods)}")

edges = set()
unparseable = 0
for name, p in mods.items():
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        unparseable += 1
        continue
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Import):
            targets = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            targets = [node.module]
        for t in targets:
            # longest-prefix match against known internal modules
            best = None
            for cand in mods:
                if (t == cand or t.startswith(cand + ".") or cand.endswith("." + t)) and (
                    best is None or len(cand) > len(best)
                ):
                    best = cand
            if best and best != name:
                edges.add((name, best))

print(f"  unparseable files      : {unparseable}")
print(f"  internal import edges  : {len(edges)}      (builder: 265)")


def sccs(nodes, edg):
    adj = {n: [] for n in nodes}
    for a, b in edg:
        adj[a].append(b)
    idx = {}
    low = {}
    on = {}
    st = []
    out = []
    counter = [0]

    def strong(v):
        work = [(v, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                idx[node] = low[node] = counter[0]
                counter[0] += 1
                st.append(node)
                on[node] = True
            recurse = False
            for i in range(pi, len(adj[node])):
                w = adj[node][i]
                if w not in idx:
                    work[-1] = (node, i + 1)
                    work.append((w, 0))
                    recurse = True
                    break
                elif on.get(w):
                    low[node] = min(low[node], idx[w])
            if recurse:
                continue
            if low[node] == idx[node]:
                comp = []
                while True:
                    w = st.pop()
                    on[w] = False
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    out.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for n in nodes:
        if n not in idx:
            strong(n)
    return out


cyc = sccs(list(mods), edges)
print(f"  cycles (SCC size>1)    : {len(cyc)}      (builder: 1)")
for c in cyc:
    print(f"     {c}")

# CONTROL, both states
ctl_nodes = ["x.a", "x.b"]
print(f"  CONTROL planted cycle  : {len(sccs(ctl_nodes, {('x.a','x.b'),('x.b','x.a')}))} cycle(s) -> must be 1 (FIRES)")
print(f"  CONTROL acyclic pair   : {len(sccs(ctl_nodes, {('x.a','x.b')}))} cycle(s) -> must be 0 (SILENT)")

fanin = {}
for a, b in edges:
    fanin[b] = fanin.get(b, 0) + 1
top = sorted(fanin.items(), key=lambda kv: -kv[1])[:5]
print(f"  top fan-in             : {top}")

art = json.loads((REPO / "command-center/audit/AUD-0030-import-graph-cycles.json").read_text(encoding="utf-8"))
rep = art.get("report", {})
print()
print(f"  BUILDER artifact report keys: {sorted(rep.keys())[:14]}")
