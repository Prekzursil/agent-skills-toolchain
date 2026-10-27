"""Lane SYNTH read-only probe. Writes NOTHING. Gitignored scratch (.gitignore:70)."""
import json, os, re, sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
CAT = os.path.join(ROOT, "command-center", "WORK-UNIT-CATALOG.json")

with open(CAT, encoding="utf-8") as fh:
    cat = json.load(fh)

out = {"top_keys": sorted(cat.keys())}

# --- register items -------------------------------------------------------
reg = None
for k in cat:
    if "register" in k.lower() or k in ("items", "register_items"):
        reg = k
        break
out["register_key_guess"] = reg

def collect(obj):
    """Find every dict that has an id matching R-[AHMB]\\d+."""
    found = {}
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            i = cur.get("id")
            if isinstance(i, str) and re.fullmatch(r"R-[AHMB]\d+", i):
                found[i] = cur
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return found

items = collect(cat)
out["register_item_count"] = len(items)
out["register_ids"] = sorted(items)

# state / disposition histogram
def statekey(d):
    for k in ("state", "status", "disposition"):
        if k in d:
            return "%s=%s" % (k, d[k])
    return "NO-STATE-FIELD"

hist = {}
for i, d in items.items():
    hist.setdefault(statekey(d), []).append(i)
out["state_histogram"] = {k: len(v) for k, v in sorted(hist.items())}
out["closed_or_done"] = sorted(
    i for i, d in items.items()
    if str(statekey(d)).lower().find("close") >= 0 or str(statekey(d)).lower().find("done") >= 0
)

# who declares a dependency on R-A03 / R-M13 / R-A01 / R-H06 / R-M18
for target in ("R-A03", "R-A01", "R-M13", "R-H06", "R-M18", "R-A28", "R-A29", "R-A30"):
    dependents = []
    for i, d in items.items():
        deps = d.get("dependencies") or d.get("deps") or []
        if isinstance(deps, str):
            deps = [deps]
        if any(target == str(x) or target in str(x) for x in deps):
            dependents.append(i)
    out.setdefault("dependents", {})[target] = sorted(dependents)

# owner gates declared on register items
gates = {}
for i, d in items.items():
    g = d.get("owner_gate") or d.get("owner_question") or d.get("gate")
    if g:
        gates.setdefault(str(g), []).append(i)
out["owner_gate_on_items"] = {k: sorted(v) for k, v in sorted(gates.items())}

# owner_questions block
oq = cat.get("owner_questions")
if isinstance(oq, list):
    out["owner_questions"] = [
        {"id": q.get("id"), "state": q.get("state"), "blocks": q.get("blocks")}
        for q in oq
    ]
elif isinstance(oq, dict):
    out["owner_questions"] = {
        k: {"state": v.get("state"), "blocks": v.get("blocks")} for k, v in oq.items()
    }

# work_units_meta echo
wm = cat.get("work_units_meta")
if isinstance(wm, dict):
    out["work_units_meta"] = {
        k: wm[k] for k in wm
        if k in ("target", "shortfall", "status", "pre_merge_items", "known_defects_at_merge")
    }

print(json.dumps(out, indent=1, ensure_ascii=True)[:12000])
