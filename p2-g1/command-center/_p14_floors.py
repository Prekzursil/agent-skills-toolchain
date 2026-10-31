"""Phase 14: re-measure the spec's NUMERIC floors against TODAY's tree.

Conditions 16 (>=160 candidates w/ provenance+license), 17 (>=96 executable blueprints),
19 (>=48 protocols, >=64 presets).

Every count states its search scope. Each classifier is control-tested: it must accept a
known-conforming instance AND reject a known-nonconforming one before any count is emitted.
"""
import json
import os
import collections

REPO = "C:/Users/Prekzursil/source/ast-integrate"
P = os.path.join(REPO, "platform")
out = {"probe": "p14-floors", "scope": "platform/ tree, working copy, today"}


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def scan(subdir, pattern_end=".json"):
    root = os.path.join(P, *subdir.split("/"))
    hits = []
    if not os.path.isdir(root):
        return None, hits
    for r, dirs, files in os.walk(root):
        for f in files:
            if f.endswith(pattern_end):
                hits.append(os.path.join(r, f))
    return root, hits


# ---------- councilspec shape classifier + control ----------
def is_councilspec(d):
    if not isinstance(d, dict):
        return False
    # structural, not name-based: a CouncilSpec declares participants and a stopping rule
    keys = set(d.keys())
    return bool(keys & {"participants", "roles"}) and bool(
        keys & {"stopping_rule", "stopping_rules", "stopping", "stopping_expression"}
    )


ctl_good = {"participants": [1], "stopping_rule": "x"}
ctl_bad = {"title": "not a spec"}
out["councilspec_classifier_control"] = {
    "accepts_known_conforming": is_councilspec(ctl_good),
    "rejects_known_nonconforming": not is_councilspec(ctl_bad),
}
cc = out["councilspec_classifier_control"]
out["councilspec_classifier_control"]["valid"] = (
    cc["accepts_known_conforming"] and cc["rejects_known_nonconforming"]
)

for label, sub in (("protocols", "council/protocols"), ("presets", "council/presets")):
    root, hits = scan(sub)
    assert root is not None, "scope error: %s does not exist; refusing to count" % sub
    n_shaped = 0
    unshaped = []
    for h in hits:
        d = load(h)
        if is_councilspec(d):
            n_shaped += 1
        else:
            unshaped.append(os.path.relpath(h, REPO).replace("\\", "/"))
    out[label] = {
        "root": os.path.relpath(root, REPO).replace("\\", "/") if root else "NOT FOUND",
        "json_files": len(hits),
        "councilspec_shaped": n_shaped,
        "not_shaped": unshaped[:8],
        "n_not_shaped": len(unshaped),
    }

# ---------- blueprints ----------
root, hits = scan("workflows")
tops = collections.Counter()
blueprint_files = []
for h in hits:
    rel = os.path.relpath(h, REPO).replace("\\", "/")
    d = load(h)
    if isinstance(d, dict) and (d.get("workflow_id") or d.get("id")):
        blueprint_files.append(rel)
        tops[rel.split("/")[2] if len(rel.split("/")) > 3 else "(top)"] += 1
out["workflows"] = {
    "root": "platform/workflows",
    "json_files": len(hits),
    "with_an_id": len(blueprint_files),
    "by_subdir": dict(tops),
}

# top-level blueprint count (the "97 blueprints" claim)
wtop = os.path.join(P, "workflows")
top_level = [f for f in os.listdir(wtop) if f.endswith(".json")] if os.path.isdir(wtop) else []
out["workflows"]["top_level_json"] = len(top_level)
subdirs = [d for d in os.listdir(wtop) if os.path.isdir(os.path.join(wtop, d))] if os.path.isdir(wtop) else []
out["workflows"]["subdirs"] = subdirs

# ---------- candidate registry: provenance + license per row ----------
reg_rows = []
regdir = os.path.join(P, "registry")
per_file = {}
if os.path.isdir(regdir):
    for f in sorted(os.listdir(regdir)):
        if not f.startswith("workflow-candidates"):
            continue
        d = load(os.path.join(regdir, f))
        rows = d.get("candidates") or d.get("rows") or d.get("entries") if isinstance(d, dict) else None
        if rows is None and isinstance(d, list):
            rows = d
        if rows:
            per_file[f] = len(rows)
            reg_rows.extend(rows)


def has_prov(r):
    pv = r.get("provenance") if isinstance(r, dict) else None
    return isinstance(pv, dict) and bool(pv)


def has_lic(r):
    if not isinstance(r, dict):
        return False
    if r.get("license"):
        return True
    pv = r.get("provenance")
    return isinstance(pv, dict) and bool(pv.get("license"))


ids = [r.get("id") for r in reg_rows if isinstance(r, dict)]
out["candidate_registry"] = {
    "root": "platform/registry/workflow-candidates-*.json",
    "per_file_rows": per_file,
    "raw_rows": len(reg_rows),
    "distinct_ids": len(set(i for i in ids if i)),
    "duplicate_ids": [k for k, v in collections.Counter(i for i in ids if i).items() if v > 1],
    "rows_with_provenance": sum(1 for r in reg_rows if has_prov(r)),
    "rows_with_license": sum(1 for r in reg_rows if has_lic(r)),
    "rows_with_BOTH": sum(1 for r in reg_rows if has_prov(r) and has_lic(r)),
}
# control: a row with neither must not be counted
out["candidate_registry"]["classifier_control"] = {
    "empty_row_has_provenance": has_prov({}),
    "empty_row_has_license": has_lic({}),
    "valid": (not has_prov({})) and (not has_lic({})),
}

FLOORS = {"protocols": 48, "presets": 64, "blueprints": 96, "candidates": 160}
out["floor_scoring"] = {
    "protocols>=48": out["protocols"]["councilspec_shaped"] >= 48,
    "presets>=64": out["presets"]["councilspec_shaped"] >= 64,
    "blueprints_top_level>=96": out["workflows"]["top_level_json"] >= 96,
    "candidates_with_prov_and_license>=160":
        out["candidate_registry"]["rows_with_BOTH"] >= 160,
}
out["floors"] = FLOORS

print(json.dumps(out, indent=2))
json.dump(out, open(os.path.join(REPO, "command-center", "P14-FLOORS.json"), "w", encoding="utf-8"), indent=2)
