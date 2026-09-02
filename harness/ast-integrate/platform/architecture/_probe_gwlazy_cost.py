#!/usr/bin/env python3
"""Cost model for gateway/lazy-activation: eager-load bytes vs lazy-load bytes,
per control plane, measured on disk. Also: does a single execution entry point exist today?

Terminal state: SUCCESS:gwlazy-cost / FAILED:gwlazy-cost <reason>
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_cost_out.json"
res: dict = {"probe": "gwlazy-cost"}


def tot(paths) -> tuple[int, int]:
    ps = [p for p in paths if p.is_file()]
    return len(ps), sum(p.stat().st_size for p in ps)


planes = {}

# council plane
n, b = tot((REPO / "platform/council/protocols").rglob("*.councilspec.json"))
planes["council_protocols"] = {"files": n, "bytes": b, "mean_bytes": b // max(1, n)}
n, b = tot((REPO / "platform/council/presets").rglob("*.councilspec.json"))
planes["council_presets"] = {"files": n, "bytes": b, "mean_bytes": b // max(1, n)}

# schema plane: physical control plane vs generated shims
phys = [
    REPO / "platform/schema/receipt.schema.json",
    REPO / "platform/schema/artifact-class-profiles.schema.json",
    REPO / "command-center/schema/_meta/json-schema-2020-12.json",
]
n, b = tot(phys)
planes["schema_physical_control_plane"] = {"files": n, "bytes": b}
shims = [
    p
    for p in (REPO / "command-center/schema").rglob("*.json")
    if p.is_file() and p.resolve() not in {q.resolve() for q in phys if q.exists()}
]
n, b = tot(shims)
planes["schema_generated_shims"] = {"files": n, "bytes": b, "mean_bytes": b // max(1, n)}

n, b = tot((REPO / "platform/schema").glob("*.schema.json"))
planes["platform_schema_all"] = {"files": n, "bytes": b}

# registry plane
n, b = tot((REPO / "platform/registry").glob("*.json"))
planes["registry"] = {"files": n, "bytes": b}

# lib plane (shippable code only, no _probe/_gen scratch)
libs = [
    p
    for p in (REPO / "platform/lib").rglob("*.py")
    if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("_")
]
n, b = tot(libs)
planes["lib_shippable_py"] = {"files": n, "bytes": b}
libs_test = [p for p in libs if p.name.startswith("test_")]
n, b = tot(libs_test)
planes["lib_test_py"] = {"files": n, "bytes": b}

# catalog
cat = REPO / "command-center/WORK-UNIT-CATALOG.json"
planes["catalog"] = {"files": 1, "bytes": cat.stat().st_size}
res["planes"] = planes

# ---- eager vs lazy for a SINGLE work unit -------------------------------
d = json.loads(cat.read_text(encoding="utf-8"))
wus = d["work_units"]
one = wus[0]
one_bytes = len(json.dumps(one).encode())
res["single_unit_bytes_mean"] = sum(len(json.dumps(w).encode()) for w in wus) // len(wus)
res["single_unit_bytes_first"] = one_bytes
res["catalog_eager_bytes"] = planes["catalog"]["bytes"]
res["catalog_lazy_amplification"] = round(
    planes["catalog"]["bytes"] / max(1, res["single_unit_bytes_mean"]), 1
)

# one council protocol vs all
res["council_eager_bytes"] = planes["council_protocols"]["bytes"] + planes["council_presets"]["bytes"]
res["council_lazy_bytes_one_protocol_plus_one_preset"] = (
    planes["council_protocols"]["mean_bytes"] + planes["council_presets"]["mean_bytes"]
)
res["council_lazy_amplification"] = round(
    res["council_eager_bytes"] / max(1, res["council_lazy_bytes_one_protocol_plus_one_preset"]), 1
)

# one schema resolution vs all
res["schema_eager_bytes"] = (
    planes["schema_generated_shims"]["bytes"] + planes["schema_physical_control_plane"]["bytes"]
)
res["schema_lazy_bytes_one_class"] = (
    planes["schema_generated_shims"]["mean_bytes"]
    + planes["schema_physical_control_plane"]["bytes"]
)
res["schema_lazy_note"] = (
    "the physical control plane must load for ANY class, so lazy saves only shim bytes"
)

# ---- is there a single execution entry point today? --------------------
entry_candidates = []
for pat in ("**/run*.py", "**/dispatch*.py", "**/orchestrat*.py", "**/execute*.py", "**/gateway*.py", "**/router*.py"):
    for p in REPO.rglob(pat.replace("**/", "")):
        if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts:
            entry_candidates.append(str(p.relative_to(REPO)).replace("\\", "/"))
res["execution_entry_point_candidates_in_repo"] = sorted(set(entry_candidates))

# every module with an argparse/__main__ = a separate CLI door
doors = []
for p in REPO.rglob("*.py"):
    if not p.is_file() or "__pycache__" in p.parts:
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    if "__main__" in t and ("argparse" in t or "sys.argv" in t):
        doors.append(str(p.relative_to(REPO)).replace("\\", "/"))
res["cli_doors_total"] = len(doors)
res["cli_doors_shippable"] = sorted(x for x in doors if "/_" not in x and not Path(x).name.startswith("_"))
res["cli_doors_scratch_count"] = len(doors) - len(res["cli_doors_shippable"])

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2))
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-cost")
