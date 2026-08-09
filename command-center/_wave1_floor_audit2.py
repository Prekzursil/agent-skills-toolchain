"""WAVE 1 FLOOR AUDIT - addendum probes.

A. Do the $id-chained schemas resolve when all platform/schema docs are loaded
   into one referencing.Registry?  (compile != usable)
B. Which schema paths do the 2,007 catalogued work units point their
   output_schema at, and does each of those paths EXIST on disk?
C. ralph-loop name-collision: is the vault SKILL.md a copy of anything the
   ralph-loop PLUGIN ships?  (exact byte + similarity algorithm, with a
   detector control proving the comparator can see a known-present match)
"""

from __future__ import annotations

import collections
import difflib
import hashlib
import json
import re
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
SCHEMA_DIR = PLATFORM / "schema"

out: dict = {}

# --------------------------------------------------------------------------- A
docs = {}
for p in sorted(SCHEMA_DIR.glob("*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(d, dict) and d.get("$schema"):
        docs[p.name] = d

resources = []
for name, d in docs.items():
    if d.get("$id"):
        resources.append((d["$id"], Resource.from_contents(d)))
registry = Registry()
for _uri, _res in resources:
    registry = registry.with_resource(uri=_uri, resource=_res)

rows = []
for name, d in docs.items():
    rec = {"file": name, "$id": d.get("$id")}
    try:
        Draft202012Validator.check_schema(d)
        rec["compiles"] = True
    except jsonschema.exceptions.SchemaError as exc:
        rec["compiles"] = False
        rec["compile_error"] = str(exc)[:300]
    try:
        Draft202012Validator(d).is_valid({})
        rec["usable_standalone"] = True
    except Exception as exc:
        rec["usable_standalone"] = False
        rec["standalone_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    try:
        Draft202012Validator(d, registry=registry).is_valid({})
        rec["usable_with_registry"] = True
    except Exception as exc:
        rec["usable_with_registry"] = False
        rec["registry_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    rows.append(rec)

out["A_schema_resolution"] = {
    "schema_documents": len(docs),
    "ids_registered": len(resources),
    "compile_pass": sum(1 for r in rows if r.get("compiles")),
    "usable_standalone": sum(1 for r in rows if r.get("usable_standalone")),
    "usable_with_registry": sum(1 for r in rows if r.get("usable_with_registry")),
    "standalone_failures": [r["file"] for r in rows if not r.get("usable_standalone")],
    "registry_failures": [r["file"] for r in rows if not r.get("usable_with_registry")],
    "per_file": rows,
}

# --------------------------------------------------------------------------- B
cat = json.loads(
    (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
wus = cat["work_units"]
pathpat = re.compile(r"([A-Za-z0-9_./\-]+\.schema\.json)")
counter: collections.Counter = collections.Counter()
for w in wus:
    val = w.get("output_schema")
    blob = val if isinstance(val, str) else json.dumps(val)
    for m in pathpat.findall(blob or ""):
        counter[m] += 1

path_rows = []
for pth, n in counter.most_common():
    direct = REPO / pth
    basename = Path(pth).name
    alts = sorted(
        str(q.relative_to(REPO)).replace("\\", "/")
        for q in REPO.rglob(basename)
        if ".git" not in q.parts
    )
    path_rows.append(
        {
            "referenced_path": pth,
            "unit_references": n,
            "exists_at_referenced_path": direct.exists(),
            "basename_found_elsewhere": alts,
        }
    )
out["B_output_schema_paths"] = {
    "work_units_in_catalog": len(wus),
    "distinct_schema_paths_referenced": len(path_rows),
    "paths_that_exist": sum(1 for r in path_rows if r["exists_at_referenced_path"]),
    "paths_missing": sum(1 for r in path_rows if not r["exists_at_referenced_path"]),
    "unit_references_to_missing_paths": sum(
        r["unit_references"] for r in path_rows if not r["exists_at_referenced_path"]
    ),
    "command_center_schema_dir_exists": (REPO / "command-center" / "schema").exists(),
    "per_path": path_rows,
}

# --------------------------------------------------------------------------- C
vault = Path("C:/Users/Prekzursil/.agents/skills/ralph-loop/SKILL.md")
plugin_roots = [
    Path(
        "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official/plugins/ralph-loop"
    ),
    Path(
        "C:/Users/Prekzursil/.claude/plugins/cache/claude-plugins-official/ralph-loop"
    ),
]
vb = vault.read_bytes() if vault.exists() else b""
vt = vb.decode("utf-8", "replace")
comp = []
for root in plugin_roots:
    if not root.is_dir():
        comp.append({"root": str(root), "exists": False})
        continue
    for q in root.rglob("*.md"):
        b = q.read_bytes()
        comp.append(
            {
                "root": str(root).replace("\\", "/"),
                "exists": True,
                "file": str(q.relative_to(root)).replace("\\", "/"),
                "bytes": len(b),
                "sha256_16": hashlib.sha256(b).hexdigest()[:16],
                "byte_identical_to_vault": b == vb,
                "similarity_to_vault": round(
                    difflib.SequenceMatcher(
                        None, vt, b.decode("utf-8", "replace")
                    ).ratio(),
                    4,
                ),
            }
        )
# detector control: the comparator must score 1.0 on the vault file vs itself
ctl = round(difflib.SequenceMatcher(None, vt, vt).ratio(), 4)
out["C_ralph_loop_collision"] = {
    "vault_skill": str(vault),
    "vault_exists": vault.exists(),
    "vault_bytes": len(vb),
    "vault_sha256_16": hashlib.sha256(vb).hexdigest()[:16],
    "plugin_ships_a_SKILL_md": any(
        c.get("file", "").lower().endswith("skill.md") for c in comp
    ),
    "plugin_markdown_files_compared": len([c for c in comp if "file" in c]),
    "max_similarity_found": max(
        [c["similarity_to_vault"] for c in comp if "file" in c] or [0]
    ),
    "any_byte_identical": any(c.get("byte_identical_to_vault") for c in comp),
    "detector_control_self_similarity_must_be_1_0": ctl,
    "comparisons": comp,
}

print(json.dumps(out, indent=2, default=str))
