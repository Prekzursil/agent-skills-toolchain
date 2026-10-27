#!/usr/bin/env python3
"""Measure the on-disk facts the gateway/lazy-activation architecture doc must cite.

Scope: repo C:/Users/Prekzursil/source/ast-integrate at whatever HEAD is checked out,
plus READ-ONLY reads of the live harness control planes under C:/Users/Prekzursil/.claude.
Writes nothing outside platform/architecture/.
Terminal state: SUCCESS:gwlazy-inventory / FAILED:gwlazy-inventory <reason>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
HOME = Path("C:/Users/Prekzursil")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_inventory_out.json"

res: dict = {"probe": "gwlazy-inventory", "repo": str(REPO)}


def sh(*args: str) -> str:
    try:
        p = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True, timeout=120)
        return (p.stdout or "").strip()
    except Exception as exc:  # pragma: no cover
        return f"ERROR:{exc}"


def count_files(root: Path, pat: str = "*") -> int:
    if not root.exists():
        return -1
    return sum(1 for p in root.rglob(pat) if p.is_file() and "__pycache__" not in p.parts)


# ---- 1. git identity -------------------------------------------------------
res["head_sha"] = sh("git", "rev-parse", "HEAD")
res["head_subject"] = sh("git", "log", "-1", "--format=%s")
res["dc90d64a_is_ancestor_of_head"] = (
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", "dc90d64a", "HEAD"],
        cwd=str(REPO), capture_output=True,
    ).returncode
    == 0
)
res["commits_since_dc90d64a"] = sh("git", "rev-list", "--count", "dc90d64a..HEAD")

# ---- 2. Wave 1 file counts (the reuse-vs-replace denominator) --------------
tree = {}
tree["platform/schema/*.schema.json"] = sorted(
    p.name for p in (REPO / "platform/schema").glob("*.schema.json")
)
tree["platform/schema_all_json"] = count_files(REPO / "platform/schema", "*.json")
tree["platform/lib_py"] = count_files(REPO / "platform/lib", "*.py")
tree["platform/lib_py_nonprobe"] = sum(
    1
    for p in (REPO / "platform/lib").rglob("*.py")
    if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("_")
)
tree["platform/lib_packages"] = sorted(
    p.name for p in (REPO / "platform/lib").iterdir() if p.is_dir() and p.name != "__pycache__"
)
tree["platform/council/protocols"] = count_files(REPO / "platform/council/protocols", "*.councilspec.json")
tree["platform/council/presets"] = count_files(REPO / "platform/council/presets", "*.councilspec.json")
tree["platform/registry_json"] = count_files(REPO / "platform/registry", "*.json")
tree["command-center/schema shims"] = count_files(REPO / "command-center/schema", "*.json")
tree["platform/corpus"] = count_files(REPO / "platform/corpus")
res["wave1_tree"] = tree

# candidates
cand = 0
for i in range(1, 6):
    f = REPO / f"platform/registry/workflow-candidates-{i}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        for key in ("candidates", "items", "workflows"):
            if isinstance(d, dict) and isinstance(d.get(key), list):
                cand += len(d[key])
                break
        else:
            if isinstance(d, list):
                cand += len(d)
res["registry_candidate_count"] = cand

# ---- 3. the catalog: units, phases, output_schema fan-in ------------------
cat_p = REPO / "command-center/WORK-UNIT-CATALOG.json"
cat = json.loads(cat_p.read_text(encoding="utf-8"))
wus = cat.get("work_units", [])
res["catalog"] = {
    "path": str(cat_p),
    "bytes": cat_p.stat().st_size,
    "work_units": len(wus),
    "items_separate_register": len(cat.get("items", [])),
    "top_level_keys": sorted(cat.keys()),
}
ph = Counter(str(w.get("phase")) for w in wus)
res["catalog"]["units_per_phase"] = dict(sorted(ph.items(), key=lambda kv: -kv[1]))
res["catalog"]["distinct_phases"] = len(ph)

# output_schema fan-in: distinct logical paths vs total references
def schema_ref(w):
    v = w.get("output_schema")
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("$ref") or v.get("path") or json.dumps(v, sort_keys=True)[:120]
    return None


refs = [schema_ref(w) for w in wus]
present = [r for r in refs if r]
res["catalog"]["output_schema_refs_total"] = len(present)
res["catalog"]["output_schema_refs_missing"] = len(refs) - len(present)
base = [r.split("#", 1)[0] for r in present]
res["catalog"]["output_schema_distinct_logical_paths"] = len(set(base))
res["catalog"]["output_schema_distinct_with_fragment"] = len(set(present))
top = Counter(base).most_common(8)
res["catalog"]["output_schema_hottest_paths"] = top
# fan-in ratio: refs per distinct physical control-plane file
res["catalog"]["fanin_refs_per_logical_path"] = round(len(present) / max(1, len(set(base))), 2)

# substrate / execution-substrate + model-vendor-role spread (routing keys)
res["catalog"]["substrates"] = dict(
    Counter(str(w.get("execution_substrate")) for w in wus).most_common(12)
)
res["catalog"]["assigned_roles_distinct"] = len(
    {str(w.get("assigned_model_vendor_role")) for w in wus}
)
# timeouts: the budget model input
tmo = [w.get("timeout") for w in wus if isinstance(w.get("timeout"), (int, float))]
res["catalog"]["timeout_numeric_count"] = len(tmo)
res["catalog"]["timeout_sum_seconds"] = sum(tmo) if tmo else None
tmo_s = [w.get("timeout") for w in wus if isinstance(w.get("timeout"), str)]
res["catalog"]["timeout_string_count"] = len(tmo_s)
res["catalog"]["timeout_string_samples"] = sorted(set(tmo_s))[:8]

# dependency graph shape (a gateway needs a DAG frontier)
deps = [w.get("dependencies") or [] for w in wus]
res["catalog"]["units_with_zero_deps"] = sum(1 for d in deps if not d)
res["catalog"]["dependency_edges"] = sum(len(d) for d in deps if isinstance(d, list))

# ---- 4. schema substrate: the in-repo gateway precedent -------------------
sub = REPO / "platform/schema/SUBSTRATE-RESOLUTION-STATUS.json"
if sub.exists():
    s = json.loads(sub.read_text(encoding="utf-8"))
    res["substrate_status"] = {
        k: s.get(k)
        for k in (
            "references_resolving",
            "references_unresolved",
            "distinct_logical_files",
            "distinct_logical_files_resolving",
            "physical_control_plane",
            "generated_shims",
        )
        if k in s
    }
    res["substrate_status_keys"] = sorted(s.keys())

# ---- 5. LIVE harness control planes (read-only) ---------------------------
live = {}
man = HOME / ".claude/hooks/_dispatch/manifest.json"
if man.exists():
    m = json.loads(man.read_text(encoding="utf-8"))
    ev = m.get("events", m)
    per = {}
    if isinstance(ev, dict):
        for name, body in ev.items():
            if not isinstance(body, dict):
                continue
            checks = body.get("checks") or body.get("hooks") or []
            per[name] = {
                "checks": len(checks) if isinstance(checks, list) else None,
                "settings_timeout": body.get("settings_timeout"),
                "wall_cap": body.get("wall_cap", "ABSENT"),
                "budgets": [c.get("timeout") for c in checks] if isinstance(checks, list) else None,
            }
    live["manifest_events"] = per
    live["manifest_event_count"] = len(per)
    live["manifest_total_checks"] = sum(v["checks"] or 0 for v in per.values())

settings = HOME / ".claude/settings.json"
if settings.exists():
    st = json.loads(settings.read_text(encoding="utf-8"))
    hooks = st.get("hooks", {})
    live["settings_hook_events"] = sorted(hooks.keys())
    live["settings_hook_event_count"] = len(hooks)
    n = 0
    for _e, lst in hooks.items():
        if isinstance(lst, list):
            for entry in lst:
                n += len((entry or {}).get("hooks", []) or [])
    live["settings_total_registered_commands"] = n
    ep = st.get("enabledPlugins", {})
    live["enabledPlugins_true"] = sum(1 for v in ep.values() if v is True)
    live["enabledPlugins_total"] = len(ep)

disp = HOME / ".claude/hooks/_dispatch/dispatch.py"
if disp.exists():
    txt = disp.read_text(encoding="utf-8", errors="replace")
    live["dispatch_py_bytes"] = len(txt.encode())
    live["dispatch_py_lines"] = txt.count("\n") + 1
    live["dispatch_py_has_or_empty_coercion"] = 'or ""' in txt
    live["dispatch_py_wall_cap_tokens"] = txt.count("_wall_cap")
    live["dispatch_py_pass2_tokens"] = txt.lower().count("pass 2")

for label, p in (
    ("claude_skills", HOME / ".claude/skills"),
    ("agents_skills", HOME / ".agents/skills"),
    ("claude_plugins_marketplaces", HOME / ".claude/plugins"),
):
    if p.exists():
        live[label + "_dir_count"] = sum(1 for c in p.iterdir() if c.is_dir())
        live[label + "_SKILL_md_count"] = sum(1 for _ in p.rglob("SKILL.md"))
res["live_control_planes"] = live

OUT.write_text(json.dumps(res, indent=2, sort_keys=False), encoding="utf-8")
print(json.dumps(res, indent=2)[:9000])
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-inventory")
