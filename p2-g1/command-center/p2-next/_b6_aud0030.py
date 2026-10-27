"""Resolve AUD-0030's two open deltas: module_count 679 and edge_count 265."""

import ast
import json
import pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]


def rel(p):
    return str(p.relative_to(ROOT)).replace("\\", "/")


allpy = [p for p in (ROOT / "tools").rglob("*.py")]
print(f"raw .py under tools/                        : {len(allpy)}")
buckets = Counter()
for p in allpy:
    r = rel(p)
    seg = set(r.split("/"))
    tag = "clean"
    for marker in (
        "node_modules",
        "vendor",
        "site-packages",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".tox",
        "third_party",
    ):
        if marker in seg:
            tag = marker
            break
    buckets[tag] += 1
print(f"by exclusion bucket: {dict(buckets)}")
target = 679
for combo_name, keep in [
    ("node_modules only", lambda r: "node_modules" not in r.split("/")),
    ("nm + vendor", lambda r: not ({"node_modules", "vendor"} & set(r.split("/")))),
    (
        "nm + vendor + venv",
        lambda r: not ({"node_modules", "vendor", ".venv", "venv"} & set(r.split("/"))),
    ),
    (
        "nm + vendor + venv + build/dist",
        lambda r: (
            not (
                {"node_modules", "vendor", ".venv", "venv", "build", "dist"}
                & set(r.split("/"))
            )
        ),
    ),
    (
        "nm + vendor + __pycache__",
        lambda r: not ({"node_modules", "vendor", "__pycache__"} & set(r.split("/"))),
    ),
]:
    n = sum(1 for p in allpy if keep(rel(p)))
    print(f"  {combo_name:<34}: {n}  {'<== MATCHES 679' if n == target else ''}")


# maybe the unit counted MODULES (dedup after __init__ collapsing) not FILES
def modname(p, base):
    r = p.relative_to(ROOT).as_posix()[:-3]
    return (
        r[: -len("/__init__")].replace("/", ".")
        if r.endswith("/__init__")
        else r.replace("/", ".")
    )


for label, keep in [
    ("nm+vendor", lambda r: not ({"node_modules", "vendor"} & set(r.split("/"))))
]:
    ps = [p for p in allpy if keep(rel(p))]
    names = {modname(p, ROOT) for p in ps}
    print(
        f"  distinct module NAMES after __init__ collapse ({label}): {len(names)} "
        f"(files={len(ps)}, collisions={len(ps) - len(names)})"
    )

print()
print("=== edge resolution policy sweep ===")
py = [p for p in allpy if not ({"node_modules", "vendor"} & set(rel(p).split("/")))]
mods = {}
for p in py:
    mods[modname(p, ROOT)] = p
# ALSO index each module by every sys.path-relative suffix, which is how these packages import
# themselves (a file in tools/monitorcore/ does `from monitorcore.redact import x`).
suffix_index = defaultdict(set)
for full in mods:
    parts = full.split(".")
    for i in range(len(parts)):
        suffix_index[".".join(parts[i:])].add(full)


def collect(policy):
    edges = set()
    for name, p in mods.items():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        pkg = name.rsplit(".", 1)[0] if "." in name else ""
        for node in ast.walk(tree):
            tg = []
            if isinstance(node, ast.Import):
                tg = [al.name for al in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg.split(".")
                    base = (
                        base[: len(base) - (node.level - 1)] if node.level > 1 else base
                    )
                    m = ".".join(base + ([node.module] if node.module else []))
                    tg = [m] + [f"{m}.{al.name}" for al in node.names]
                elif node.module:
                    tg = [node.module] + (
                        [f"{node.module}.{al.name}" for al in node.names]
                        if policy in ("loose", "suffix")
                        else []
                    )
            for t in tg:
                if policy == "suffix":
                    for cand in suffix_index.get(t, ()):
                        if cand != name:
                            edges.add((name, cand))
                elif t in mods and t != name:
                    edges.add((name, t))
    return edges


for pol in ("strict", "loose", "suffix"):
    e = collect(pol)
    print(
        f"  policy={pol:<7} edges={len(e)}  {'<== MATCHES 265' if len(e) == 265 else ''}"
    )

sfx = collect("suffix")
adj, radj = defaultdict(list), defaultdict(list)
for s, d in sfx:
    adj[s].append(d)
    radj[d].append(s)


def kosaraju(nodes):
    seen, order = set(), []
    for n in nodes:
        if n in seen:
            continue
        seen.add(n)
        st = [(n, iter(adj[n]))]
        while st:
            v, it = st[-1]
            nx = next(it, None)
            if nx is None:
                order.append(v)
                st.pop()
            elif nx not in seen:
                seen.add(nx)
                st.append((nx, iter(adj[nx])))
    seen2, out = set(), []
    for n in reversed(order):
        if n in seen2:
            continue
        st, g = [n], []
        seen2.add(n)
        while st:
            v = st.pop()
            g.append(v)
            for w in radj[v]:
                if w not in seen2:
                    seen2.add(w)
                    st.append(w)
        out.append(g)
    return out


cyc = sorted(sorted(c) for c in kosaraju(list(mods)) if len(c) > 1)
print(f"  cycles under the WIDEST (suffix) policy: {len(cyc)} -> {cyc}")
a30 = json.loads(
    (ROOT / "command-center/audit/AUD-0030-import-graph-cycles.json").read_text(
        encoding="utf-8"
    )
)
print(f"  unit's cycles                          : {a30['report']['cycles']}")
same = cyc == sorted(sorted(c) for c in a30["report"]["cycles"])
print(f"  cycle finding INVARIANT across every resolver policy tried: {same}")
json.dump(
    {
        "module_bucket_counts": dict(buckets),
        "edge_policy_sweep": {
            p: len(collect(p)) for p in ("strict", "loose", "suffix")
        },
        "cycle_invariant_across_policies": same,
        "cycles_widest_policy": cyc,
    },
    open(
        ROOT / "command-center/p2-next/REVIEW-AUD0030-DEEP.json", "w", encoding="utf-8"
    ),
    indent=2,
)
print("SUCCESS:aud0030-deep")
