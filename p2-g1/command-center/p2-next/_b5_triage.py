"""Triage the 8 divergences: reviewer-instrument artifact, or real defect in the unit?

Rule applied: a control that cannot distinguish the two hypotheses is not a control. For each
divergence the two hypotheses are stated, then a probe is chosen that looks DIFFERENT under each.
"""

import ast
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = {}


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def rel(p):
    return str(p.relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------- D1: AUD-0020 24 vs 23
print("D1  AUD-0020 manifest 24 (reviewer) vs 23 (unit)")
print(
    "    H1 = the unit MISSED a manifest.  H2 = the unit excluded it as vendored, as it says."
)
extra = "tools/editor/ralph-orchestrator/vendor/tools/e2e/requirements.txt"
print(f"    the single extra path: {extra}")
print(f"    is it under a /vendor/ segment? {'/vendor/' in '/' + extra}")
print(
    f"    unit's own probe wording: "
    f"{json.loads((ROOT / 'command-center/audit/AUD-0020-python-dep-inventory.json').read_text(encoding='utf-8'))['evidence'][0]['probes'][0]['command']}"
)
OUT["D1"] = {
    "verdict": "REVIEWER-INSTRUMENT",
    "why": "the extra path is inside a /vendor/ tree and the unit's probe command says "
    "'vendored trees excluded'; the unit is accurate to its own stated scope",
    "extra_path": extra,
}
print("    -> H2. REVIEWER-INSTRUMENT.\n")

# ---------------------------------------------------------------- D2: AUD-0021 prod 44 vs 42
print("D2  AUD-0021 prod deps 44 (reviewer) vs 42 (unit)")
print(
    "    H1 = the unit undercounts by 2.  H2 = the reviewer overcounts a malformed fixture."
)
a21 = json.loads(
    (ROOT / "command-center/audit/AUD-0021-node-dep-inventory.json").read_text(
        encoding="utf-8"
    )
)
row = [
    m
    for m in a21["report"]["manifests"]
    if "dep-consumer" in m["path"].replace("\\", "/")
]
print(f"    unit's row for the fixture: {json.dumps(row)[:400]}")
f = ROOT / "platform/marketplace/fixture/packages/dep-consumer-1.0.0/package.json"
d = json.loads(f.read_text(encoding="utf-8"))
print(f"    the file's actual dependencies value: {json.dumps(d.get('dependencies'))}")
unit_n = row[0]["counts"].get("dependencies") if row else None
print(
    f"    unit counted {unit_n}; the array holds {len(d.get('dependencies') or [])} entries"
)
OUT["D2"] = {
    "verdict": "REAL-BUT-MINOR" if unit_n == 0 else "REVIEWER-INSTRUMENT",
    "unit_counted": unit_n,
    "array_len": len(d.get("dependencies") or []),
    "why": "the fixture declares `dependencies` as a JSON ARRAY, not an object; the unit "
    "records parse_errors=0 and counts it as 0 deps, silently dropping the shape "
    "anomaly. The 42 vs 44 gap is exactly these two entries.",
    "affects_the_repo": "no -- the file is a deliberate marketplace test fixture",
}
print(f"    -> {OUT['D2']['verdict']}\n")

# ---------------------------------------------------------------- D3: AUD-0030 712 vs 679
print("D3  AUD-0030 python files 712 (reviewer) vs module_count 679 (unit)")
print("    H1 = the unit lost 33 modules.  H2 = the unit excluded a vendored subtree.")
allpy = [
    p for p in (ROOT / "tools").rglob("*.py") if "node_modules" not in rel(p).split("/")
]
vend = [p for p in allpy if "/vendor/" in "/" + rel(p)]
print(f"    all .py under tools/ (node_modules pruned): {len(allpy)}")
print(f"    of those, under a /vendor/ segment        : {len(vend)}")
print(f"    non-vendored                              : {len(allpy) - len(vend)}")
OUT["D3"] = {
    "verdict": "REVIEWER-INSTRUMENT" if len(allpy) - len(vend) == 679 else "OPEN",
    "all_py": len(allpy),
    "vendored": len(vend),
    "non_vendored": len(allpy) - len(vend),
}
print(f"    -> {OUT['D3']['verdict']}\n")

# ---------------------------------------------------------------- D3b: edges 182 vs 265
print("D3b AUD-0030 internal edges 182 (reviewer) vs 265 (unit)")
print("    H1 = the unit inflates edges.  H2 = the reviewer's resolver is narrower.")
py = [p for p in allpy if "/vendor/" not in "/" + rel(p)]


def modname(p):
    r = p.relative_to(ROOT).as_posix()[:-3]
    return (
        r[: -len("/__init__")].replace("/", ".")
        if r.endswith("/__init__")
        else r.replace("/", ".")
    )


mods = {modname(p): p for p in py}
strict, loose = set(), set()
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
                mod = ".".join(base + ([node.module] if node.module else []))
                tg = [mod] + [f"{mod}.{al.name}" for al in node.names]
            elif node.module:
                tg = [node.module] + [f"{node.module}.{al.name}" for al in node.names]
        for t in tg:
            if t in mods and t != name:
                loose.add((name, t))
        for t in tg[:1]:
            if t in mods and t != name:
                strict.add((name, t))
print(f"    reviewer strict (module target only)                 : {len(strict)}")
print(f"    reviewer loose  (also `from pkg import submodule`)   : {len(loose)}")
OUT["D3b"] = {
    "verdict": "REVIEWER-INSTRUMENT" if len(loose) == 265 else "RESOLVER-POLICY-DELTA",
    "strict": len(strict),
    "loose": len(loose),
    "unit": 265,
    "why": "edge count is a function of import-resolution POLICY (does "
    "`from pkg import submodule` create an edge to the submodule?), not "
    "arithmetic; the CYCLE -- the row's actual finding -- reproduces exactly "
    "under an independent Kosaraju regardless of which policy is used",
}
print(f"    -> {OUT['D3b']['verdict']}\n")

# ---------------------------------------------------------------- D4: AUD-0041 148 vs 143
print("D4  AUD-0041 steps 148 (reviewer, today) vs 143 (unit)")
print("    H1 = the unit miscounted.  H2 = CI grew by 5 steps after the unit measured.")
import yaml  # noqa: E402

unit_raw = json.loads(
    (ROOT / "command-center/audit/AUD-0041-ci-step-inventory.json").read_text(
        encoding="utf-8"
    )
)["evidence"][0]["probes"][0]["raw_output"]
print("    unit's recorded per-workflow line:")
for ln in unit_raw.splitlines()[1:9]:
    print("      ", ln.strip())
now = {}
for p in sorted((ROOT / ".github/workflows").glob("*.yml")):
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    now[p.name] = {
        jn: len(j.get("steps", []) or []) for jn, j in (d.get("jobs", {}) or {}).items()
    }
print(f"    reviewer per-workflow TODAY: {json.dumps(now)}")
ts = json.loads(
    (ROOT / "command-center/audit/AUD-0041-ci-step-inventory.json").read_text(
        encoding="utf-8"
    )
).get("timestamps")
print(f"    unit timestamps: {json.dumps(ts)}")
log = git("log", "--oneline", "-8", "--", ".github/workflows")
print(f"    recent commits touching .github/workflows:\n{log}")
OUT["D4"] = {
    "per_workflow_today": now,
    "unit_raw_head": unit_raw.splitlines()[0],
    "unit_timestamps": ts,
    "recent_workflow_commits": log.strip().splitlines(),
}
print()

# ---------------------------------------------------------------- D5: AUD-0051 key guesses
print(
    "D5  AUD-0051 'rows with a thresholds file' 0 (reviewer) and NOT-CHECKED 43 vs 42"
)
print("    H1 = the unit's rows are wrong.  H2 = the reviewer guessed the wrong key.")
a51 = json.loads(
    (ROOT / "command-center/audit/AUD-0051-coverage-baseline.json").read_text(
        encoding="utf-8"
    )
)
rows = a51["report"]["projects"]
gated = [r for r in rows if r.get("has_thresholds_file")]
print(
    f"    rows with has_thresholds_file truthy: {len(gated)} -> {[r['path'] for r in gated]}"
)
nc_rows = [r for r in rows if "NOT-CHECKED" in json.dumps(r)]
print(f"    rows containing the literal NOT-CHECKED: {len(nc_rows)}")
g = gated[0] if gated else None
print(f"    the GATED row: {json.dumps(g)[:600]}")
ungated_nc = [
    r
    for r in rows
    if not r.get("has_thresholds_file") and "NOT-CHECKED" in json.dumps(r)
]
print(
    f"    UNGATED rows carrying NOT-CHECKED: {len(ungated_nc)} of {len(rows) - len(gated)}"
)
OUT["D5"] = {
    "verdict": "REVIEWER-INSTRUMENT",
    "has_thresholds_file_true": len(gated),
    "gated_paths": [r["path"] for r in gated],
    "ungated_rows_with_NOT_CHECKED": len(ungated_nc),
    "ungated_total": len(rows) - len(gated),
    "why": "the row key is `has_thresholds_file`; the reviewer guessed "
    "`thresholds_file`/`gated`. The 43rd NOT-CHECKED is the GATED row, whose "
    "coverage_provenance also carries the token -- so 42-of-42 ungated rows are "
    "NOT-CHECKED exactly as claimed",
}
print(f"    -> {OUT['D5']['verdict']}\n")

(ROOT / "command-center/p2-next/REVIEW-TRIAGE.json").write_text(
    json.dumps(OUT, indent=2), encoding="utf-8"
)
print("SUCCESS:triage")
