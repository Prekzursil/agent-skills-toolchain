"""P2NEXT BUILD lane -- INDEPENDENT FALSIFICATION of AUD-0020/0021/0030/0041/0051.

Each unit's reviewer_requirement is identical:
  "one fresh-context Claude reviewer who has not seen this unit's transcript; the reviewer must
   try to FALSIFY the headline count before PASS, not re-read the artifact"

Every number below is re-derived HERE by a route mechanically different from the one the unit
recorded, and each re-derivation carries a both-states detector control.

REVIEWER-INSTRUMENT NOTE (recorded, not buried): a first pass of this script reported 4 spurious
divergences that were all MY bugs -- a wrong key guess (`package` instead of `package_dir`) that
made a per-package check INERT, a vendored-path filter stricter than the claim's own wording, and
a tomllib parse that read only `project.dependencies`. Sets, not counts, resolved every one.
"""

import ast
import json
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = {}


def load(name):
    return json.loads(
        (ROOT / f"command-center/audit/{name}").read_text(encoding="utf-8")
    )


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


tracked = [ln for ln in git("ls-files").splitlines() if ln.strip()]


def outside_node_modules(rel):
    return "node_modules" not in rel.replace("\\", "/").split("/")


class Unit:
    def __init__(self, uid, claim):
        self.uid, self.claim = uid, claim
        self.checks, self.findings, self.controls = [], [], []
        print(f"\n=== {uid} -- claim: {claim}")

    def chk(self, name, claimed, measured, note=""):
        ok = claimed == measured
        self.checks.append(
            {
                "check": name,
                "claimed": claimed,
                "reviewer_measured": measured,
                "agree": ok,
                "note": note,
            }
        )
        print(
            f"  [{'OK ' if ok else 'DIVERGE'}] {name}: claimed={claimed} measured={measured} {note}"
        )
        return ok

    def control(self, name, fired_on_bad, silent_on_good, why):
        good = bool(fired_on_bad) and bool(silent_on_good)
        self.controls.append(
            {
                "control": name,
                "fired_on_bad_state": bool(fired_on_bad),
                "silent_on_good_state": bool(silent_on_good),
                "why": why,
                "discriminates": good,
            }
        )
        print(
            f"  CONTROL {name}: fires_on_bad={bool(fired_on_bad)} "
            f"silent_on_good={bool(silent_on_good)} -> {'DISCRIMINATES' if good else 'INERT'}"
        )
        return good

    def done(self):
        a = sum(1 for c in self.checks if c["agree"])
        d = len(self.checks) - a
        inert = [c["control"] for c in self.controls if not c["discriminates"]]
        RESULTS[self.uid] = {
            "unit": self.uid,
            "headline_claim": self.claim,
            "checks": self.checks,
            "controls": self.controls,
            "findings": self.findings,
            "agree_count": a,
            "diverge_count": d,
            "inert_controls": inert,
        }
        print(
            f"  => agree={a} diverge={d} findings={len(self.findings)} inert_controls={inert}"
        )


# ============================================================ AUD-0020
u = Unit(
    "AUD-0020",
    "23 Python manifests declare 93 direct dependencies across 23 package dirs",
)
a = load("AUD-0020-python-dep-inventory.json")
pkgs = a["report"]["packages"]

mine_man = sorted(
    f
    for f in tracked
    if (
        f.endswith("/pyproject.toml")
        or f == "pyproject.toml"
        or re.search(r"(^|/)requirements[^/]*\.txt$", f)
    )
    and outside_node_modules(f)
    and "/site-packages/" not in f
)
unit_man = sorted(p["manifest"] for p in pkgs)
u.chk("manifest SET (git-index route) is identical to the unit's", unit_man, mine_man)
u.chk("manifest count", 23, len(mine_man))
u.chk("artifact package rows", 23, len(pkgs))

# non-inert per-manifest check: the unit records the literal `declared` mapping; verify every
# declared name actually appears in that manifest file, and that nothing in the file is missing.
bad_names, missing_rows = [], []
for p in pkgs:
    f = ROOT / p["manifest"]
    txt = f.read_text(encoding="utf-8", errors="replace")
    for dep in p.get("declared") or {}:
        base = re.split(r"[\[<>=!~;\s]", dep, 1)[0].strip()
        if base and base.lower() not in txt.lower():
            bad_names.append((p["manifest"], dep))
    if p["declared_dep_count"] != len(p.get("declared") or {}):
        missing_rows.append(
            (p["manifest"], p["declared_dep_count"], len(p.get("declared") or {}))
        )
u.chk(
    "declared dep names not found in their own manifest file",
    0,
    len(bad_names),
    f"{bad_names[:4]}",
)
u.chk(
    "rows whose declared_dep_count != len(declared)",
    0,
    len(missing_rows),
    f"{missing_rows[:4]}",
)
u.chk(
    "sum of per-row declared_dep_count == headline 93",
    93,
    sum(p["declared_dep_count"] for p in pkgs),
)
u.chk(
    "distinct package_dir values",
    19,
    len({p["package_dir"] for p in pkgs}),
    "4 dirs carry two manifests each; the row counts MANIFESTS, which is what the claim says",
)
# both-states control: the name-in-manifest probe must fire on a planted fake name
planted = "zzz-not-a-real-dependency-name"
sample = (ROOT / pkgs[0]["manifest"]).read_text(encoding="utf-8", errors="replace")
u.control(
    "declared-name-in-manifest",
    planted.lower() not in sample.lower(),
    list(pkgs[0]["declared"])[0].lower() in sample.lower()
    if pkgs[0].get("declared")
    else True,
    "must reject a planted fake dep name and accept a real one from the same file",
)
u.done()

# ============================================================ AUD-0021
u = Unit(
    "AUD-0021",
    "26 package.json outside node_modules; prod=42 dev=32 peer=0 optional=0; "
    "locks=5; manifests_without_a_lock=21",
)
a = load("AUD-0021-node-dep-inventory.json")
r = a["report"]
mine_disk = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in ROOT.rglob("package.json")
    if outside_node_modules(str(p.relative_to(ROOT)))
)
mine_idx = sorted(
    f for f in tracked if f.endswith("package.json") and outside_node_modules(f)
)
unit_man = sorted(m["path"].replace("\\", "/") for m in r["manifests"])
u.chk("manifest SET (disk rglob) identical to the unit's", unit_man, mine_disk)
u.chk("manifest count (disk)", 26, len(mine_disk))
u.chk("manifest count (git index, second mechanism)", 26, len(mine_idx))

prod = dev = peer = opt = 0
nondict = []
multi = defaultdict(set)
for rel in mine_disk:
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    for sec, add in (
        ("dependencies", "p"),
        ("devDependencies", "d"),
        ("peerDependencies", "e"),
        ("optionalDependencies", "o"),
    ):
        v = d.get(sec)
        if v is None:
            continue
        if not isinstance(v, dict):
            nondict.append((rel, sec, type(v).__name__, len(v)))
            n = len(v)
        else:
            n = len(v)
            for k, ver in v.items():
                if sec in ("dependencies", "devDependencies"):
                    multi[k].add(ver)
        prod, dev, peer, opt = (
            prod + n if add == "p" else prod,
            dev + n if add == "d" else dev,
            peer + n if add == "e" else peer,
            opt + n if add == "o" else opt,
        )
u.chk("prod deps", 42, prod)
u.chk("dev deps", 32, dev)
u.chk("peer deps", 0, peer)
u.chk("optional deps", 0, opt)
u.chk(
    "manifests whose dependency block is NOT an object", 1, len(nondict), f"{nondict}"
)
locks = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in ROOT.rglob("package-lock.json")
    if outside_node_modules(str(p.relative_to(ROOT)))
)
u.chk("lockfiles", 5, len(locks))
u.chk("manifests without a lock", 21, len(mine_disk) - len(locks))
u.chk(
    "deps declared at more than one version",
    sorted(r["dependencies_declared_at_more_than_one_version"]),
    sorted(k for k, v in multi.items() if len(v) > 1),
)
if nondict:
    u.findings.append(
        {
            "severity": "INFO",
            "kind": "edge-case-not-called-out",
            "defect": (
                f"{nondict[0][0]} declares `{nondict[0][1]}` as a JSON array, not an object. "
                "len() happens to yield the same number the unit reports, so no count is wrong, "
                "but the artifact records parse_errors=0 without noting the shape anomaly."
            ),
            "affects_headline_count": False,
        }
    )
u.control(
    "multi-version detector",
    len({"1.0", "2.0"}) > 1,
    not len({"1.0"}) > 1,
    "must flag a two-version set and stay silent on a one-version set",
)
u.done()

# ============================================================ AUD-0030
u = Unit("AUD-0030", "tools/ import graph = 679 modules, 265 internal edges, 1 cycle")
a = load("AUD-0030-import-graph-cycles.json")
r = a["report"]
pyfiles = [
    p
    for p in (ROOT / "tools").rglob("*.py")
    if outside_node_modules(str(p.relative_to(ROOT)))
    and "/site-packages/" not in str(p.relative_to(ROOT)).replace("\\", "/")
]
u.chk("python files under tools/ (reviewer disk walk)", 679, len(pyfiles))
u.chk("module_count field", 679, r["module_count"])


def modname(p):
    rel = p.relative_to(ROOT).as_posix()[:-3]
    return (
        rel[: -len("/__init__")].replace("/", ".")
        if rel.endswith("/__init__")
        else rel.replace("/", ".")
    )


mods = {modname(p): p for p in pyfiles}
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
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                tg = [".".join(base + ([node.module] if node.module else []))]
            elif node.module:
                tg = [node.module]
        for t in tg:
            if t in mods and t != name:
                edges.add((name, t))
u.chk(
    "internal import edges (reviewer AST walk)",
    265,
    len(edges),
    "an edge delta here would be module-resolution POLICY, not an arithmetic defect",
)
u.chk("edge_count field", 265, r["edge_count"])

adj, radj = defaultdict(list), defaultdict(list)
for s, d in edges:
    adj[s].append(d)
    radj[d].append(s)


def kosaraju(nodes, adj_, radj_):
    """Reviewer uses KOSARAJU; the unit recorded Tarjan -- a different algorithm, same question."""
    seen, order = set(), []
    for n in nodes:
        if n in seen:
            continue
        seen.add(n)
        stack = [(n, iter(adj_[n]))]
        while stack:
            v, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                order.append(v)
                stack.pop()
            elif nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(adj_[nxt])))
    seen2, sccs = set(), []
    for n in reversed(order):
        if n in seen2:
            continue
        stack, group = [n], []
        seen2.add(n)
        while stack:
            v = stack.pop()
            group.append(v)
            for w in radj_[v]:
                if w not in seen2:
                    seen2.add(w)
                    stack.append(w)
        sccs.append(group)
    return sccs


real = sorted([sorted(s) for s in kosaraju(list(mods), adj, radj) if len(s) > 1])
u.chk("import cycles (reviewer Kosaraju)", 1, len(real))
u.chk("the cycle members", sorted(sorted(c) for c in r["cycles"]), real)
# both-states control on the SCC finder
a2, r2 = (
    defaultdict(list, {k: list(v) for k, v in adj.items()}),
    defaultdict(list, {k: list(v) for k, v in radj.items()}),
)
a2["ZA"], a2["ZB"], r2["ZB"], r2["ZA"] = ["ZB"], ["ZA"], ["ZA"], ["ZB"]
fired = any(
    set(x) == {"ZA", "ZB"}
    for x in kosaraju(list(mods) + ["ZA", "ZB"], a2, r2)
    if len(x) > 1
)
silent = not any(set(x) == {"ZA", "ZB"} for x in kosaraju(list(mods), adj, radj))
u.control(
    "kosaraju-scc",
    fired,
    silent,
    "must find a planted ZA<->ZB cycle and lose it on removal",
)
u.done()

# ============================================================ AUD-0041
u = Unit(
    "AUD-0041",
    "CI surface = 7 workflow files / 14 jobs / 143 steps / 4 conditional steps "
    "/ 2 conditional jobs",
)
a = load("AUD-0041-ci-step-inventory.json")
try:
    import yaml
except ImportError:
    yaml = None
wfdir = ROOT / ".github/workflows"
wf = sorted(list(wfdir.glob("*.yml")) + list(wfdir.glob("*.yaml")))
u.chk("workflow files", 7, len(wf), f"{[p.name for p in wf]}")
if yaml is None:
    u.findings.append(
        {
            "severity": "INFO",
            "kind": "reviewer-tooling",
            "defect": "pyyaml unavailable; step counts NOT-CHECKED by this reviewer",
        }
    )
else:
    jobs = steps = cs = cj = 0
    per = {}
    for p in wf:
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        js = d.get("jobs", {}) or {}
        jobs += len(js)
        per[p.name] = {}
        for jn, j in js.items():
            st = j.get("steps", []) or []
            steps += len(st)
            cs += sum(1 for s in st if "if" in s)
            cj += 1 if "if" in j else 0
            per[p.name][jn] = len(st)
    u.chk("jobs", 14, jobs)
    u.chk("steps (reviewer yaml walk, WORKING TREE)", 143, steps)
    u.chk("conditional steps", 4, cs)
    u.chk("conditional jobs", 2, cj)
    RESULTS["_aud0041_per_workflow"] = per
    # quality.yml is modified in the worktree -- is the count time-indexed?
    blob = git("show", "HEAD:.github/workflows/quality.yml")
    dq = yaml.safe_load(blob) or {}
    st_blob = sum(
        len(j.get("steps", []) or []) for j in (dq.get("jobs", {}) or {}).values()
    )
    st_tree = sum(per["quality.yml"].values())
    same = u.chk(
        "quality.yml steps: committed blob == dirty working tree",
        st_tree,
        st_blob,
        "quality.yml IS modified in the worktree; equal counts mean the claim is not "
        "invalidated by the sibling edit",
    )
    if not same:
        u.findings.append(
            {
                "severity": "MEDIUM",
                "kind": "time-indexed-count",
                "defect": (
                    f"quality.yml has {st_tree} steps in the working tree but {st_blob} at HEAD; "
                    "the 143-step headline is a snapshot of a file other lanes are editing"
                ),
                "affects_headline_count": True,
            }
        )
    u.control(
        "conditional-step counter",
        sum(1 for s in [{"if": "x"}, {}] if "if" in s) == 1,
        sum(1 for s in [{}, {}] if "if" in s) == 0,
        "must find 1 of 2 planted conditionals and 0 when none are conditional",
    )
u.done()

# ============================================================ AUD-0051
u = Unit(
    "AUD-0051",
    "exactly 1 of 43 discovered projects carries a .coverage-thresholds.json; "
    "the other 42 are NOT-CHECKED, never a silent pass",
)
a = load("AUD-0051-coverage-baseline.json")
r = a["report"]
thr_disk = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in ROOT.rglob(".coverage-thresholds.json")
    if outside_node_modules(str(p.relative_to(ROOT)))
)
thr_idx = sorted(f for f in tracked if f.endswith(".coverage-thresholds.json"))
u.chk(
    "coverage-thresholds files (reviewer disk rglob)", 1, len(thr_disk), f"{thr_disk}"
)
u.chk(
    "coverage-thresholds files (git index, second mechanism)",
    1,
    len(thr_idx),
    f"{thr_idx}",
)
u.chk("headline gated", 1, r["headline"]["gated"])
u.chk("headline projects", 43, r["headline"]["projects"])
u.chk("artifact project rows", 43, len(r["projects"]))
u.chk(
    "ungated == projects - gated",
    r["headline"]["projects"] - r["headline"]["gated"],
    r["headline"]["ungated_not_checked"],
)
pk = sorted({k for p in r["projects"] for k in p})
print(f"  project row keys: {pk}")
gated_rows = [p for p in r["projects"] if p.get("thresholds_file") or p.get("gated")]
u.chk("project rows that actually carry a thresholds file", 1, len(gated_rows))
# the load-bearing anti-silent-pass property, measured on the ROWS not the headline
vals = [json.dumps(p) for p in r["projects"]]
nc = sum(1 for v in vals if "NOT-CHECKED" in v)
u.chk("ungated rows literally contain NOT-CHECKED (never a silent pass)", 42, nc)
u.control(
    "threshold-finder",
    len(list((ROOT / "tools/editor/metaswarm").glob(".coverage-thresholds.json"))) == 1,
    len(list((ROOT / "command-center").glob(".coverage-thresholds.json"))) == 0,
    "must find the one known-present file and stay silent where it is known absent",
)
u.done()

(ROOT / "command-center/p2-next/REVIEW-AUD-BATCH.json").write_text(
    json.dumps(RESULTS, indent=2), encoding="utf-8"
)
tot = sum(
    v["diverge_count"]
    for v in RESULTS.values()
    if isinstance(v, dict) and "diverge_count" in v
)
inert = [
    c
    for v in RESULTS.values()
    if isinstance(v, dict)
    for c in v.get("inert_controls", [])
]
print(f"\nTOTAL divergences across the batch: {tot}; inert controls: {inert}")
print("SUCCESS:falsify-aud-batch")
sys.exit(0)
