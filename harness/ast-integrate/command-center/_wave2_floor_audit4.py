#!/usr/bin/env python
"""Pass 4: catalog-defect deltas vs the pinned ground truth, git-tracking census of the
Wave-2 deliverables, and the forge id-collision check."""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
CC = REPO / "command-center"
LIB = PLATFORM / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(CC))
from _wave2_floor_audit import load_json_safe  # noqa: E402

OUT = CC / "WAVE2-FLOOR-AUDIT.json"
# the pattern the work-unit schema enforces on output_schema
SCHEMA_PATTERN = re.compile(
    r"^(?:https?://[^\s#]+(?:#\S*)?|[A-Za-z0-9._][A-Za-z0-9._\-/]*\.json(?:#\S*)?)$"
)
PATHISH = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:schema\.json|json)")


def catalog_defect_deltas() -> dict:
    doc, e = load_json_safe(CC / "WORK-UNIT-CATALOG.json")
    if e:
        return {"error": e}
    units = doc.get("work_units") or []
    ids = {u.get("id") for u in units}

    pattern_fail = [
        u["id"] for u in units if not SCHEMA_PATTERN.match(str(u.get("output_schema") or ""))
    ]
    # loadability: every path token in the value must exist AND parse as JSON
    unloadable, loadable = [], []
    for u in units:
        v = str(u.get("output_schema") or "")
        toks = [t.replace("\\", "/") for t in PATHISH.findall(v)]
        if not toks:
            unloadable.append(u["id"])
            continue
        ok = True
        for t in toks:
            p = REPO / t
            if not p.is_file():
                ok = False
                break
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                ok = False
                break
        (loadable if ok else unloadable).append(u["id"])

    # dependency refs
    bad_dep = []
    for u in units:
        deps = u.get("depends_on") or u.get("dependencies") or []
        if isinstance(deps, str):
            deps = [deps]
        for d in deps:
            d = str(d)
            if d in ids:
                continue
            if re.fullmatch(r"B\d\d?", d):
                continue
            bad_dep.append({"unit": u["id"], "dep": d})

    # completion sentinel names own id
    bad_sent = []
    for u in units:
        s = str(u.get("completion_sentinel") or "")
        if u.get("id") and u["id"] not in s:
            bad_sent.append({"unit": u["id"], "sentinel": s[:90]})

    # assigned_model_vendor_role canonical shape
    roles = Counter(str(u.get("assigned_model_vendor_role") or "") for u in units)
    canon = re.compile(r"^[a-z0-9-]+/[a-z0-9.-]+/[a-z0-9-]+$")
    noncanon = {k: v for k, v in roles.items() if not canon.match(k)}
    return {
        "work_units": len(units),
        "output_schema_pattern_fail": len(pattern_fail),
        "output_schema_unloadable": len(unloadable),
        "output_schema_loadable": len(loadable),
        "dependency_refs_unresolvable": len(bad_dep),
        "dependency_refs_sample": bad_dep[:8],
        "completion_sentinel_not_naming_own_unit": len(bad_sent),
        "completion_sentinel_sample": bad_sent[:5],
        "assigned_model_vendor_role_distinct": len(roles),
        "assigned_model_vendor_role_noncanonical_units": sum(noncanon.values()),
        "assigned_model_vendor_role_noncanonical_shapes": len(noncanon),
        "noncanonical_role_sample": dict(list(noncanon.items())[:6]),
        "PINNED_GROUND_TRUTH": {
            "unloadable_output_schema_refs": 159,
            "unresolvable_dependency_refs": 41,
            "completion_sentinels_not_naming_own_unit": 96,
            "noncanonical_assigned_model_vendor_role": 128,
        },
    }


def git_tracking_census() -> dict:
    def run(*a: str) -> str:
        return subprocess.run(
            ["git", *a], cwd=str(REPO), capture_output=True, text=True
        ).stdout

    head = run("rev-parse", "--short", "HEAD").strip()
    branch = run("rev-parse", "--abbrev-ref", "HEAD").strip()
    census = {}
    for d in (
        "platform/workflows",
        "platform/architecture",
        "platform/lib/foundry",
        "command-center/schema",
        "platform/schema",
        "platform/lib/wfdsl",
        "platform/lib/councilspec",
        "platform/lib/council_protocols",
        "platform/lib/workflows",
        "platform/council",
        "platform/registry",
    ):
        tracked = [x for x in run("ls-files", d).splitlines() if x]
        dirty = [x for x in run("status", "--porcelain", "-uall", "--", d).splitlines() if x]
        on_disk = [p for p in (REPO / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts] if (REPO / d).exists() else []
        census[d] = {
            "files_on_disk": len(on_disk),
            "git_tracked": len(tracked),
            "dirty_or_untracked": len(dirty),
            "fully_untracked": len(tracked) == 0 and len(on_disk) > 0,
        }
    total_dirty = len([x for x in run("status", "--porcelain", "-uall").splitlines() if x])
    return {
        "branch": branch,
        "head": head,
        "repo_wide_dirty_or_untracked_entries": total_dirty,
        "per_directory": census,
    }


def forged_id_collision() -> dict:
    fd = PLATFORM / "workflows" / "forged"
    rows = []
    for p in sorted(fd.glob("*.workflow.json")):
        d, e = load_json_safe(p)
        if e:
            continue
        rows.append(
            {
                "file": p.name,
                "id": d.get("id"),
                "stages": len(d.get("stages") or []),
                "rejected_filename": p.name.startswith("REJECTED."),
                "verdict_in_doc": (
                    ((d.get("x_extensions") or {}).get("foundry") or {}).get("verdict")
                    or ((d.get("x_extensions") or {}).get("foundry") or {}).get(
                        "certification", {}
                    ).get("verdict")
                ),
            }
        )
    byid: dict[str, list] = {}
    for r in rows:
        byid.setdefault(r["id"], []).append(r)
    return {
        "docs": rows,
        "colliding_ids": {
            k: v for k, v in byid.items() if len(v) > 1
        },
        "risk": "a loader keyed on workflow id cannot distinguish the CERTIFIED 9-stage fusion from the REJECTED 18-stage union: all three carry id fused.dc5b5f0b10f7",
    }


def main() -> int:
    prev, e = load_json_safe(OUT)
    if e:
        return 1
    prev["pass"] = 4
    prev["generated_at_utc"] = _dt.datetime.now(_dt.UTC).isoformat()
    prev["check7_catalog_defect_deltas"] = catalog_defect_deltas()
    prev["check8_git_tracking"] = git_tracking_census()
    prev["check9_forged_id_collision"] = forged_id_collision()
    OUT.write_text(json.dumps(prev, indent=1), encoding="utf-8")
    for k in ("check7_catalog_defect_deltas", "check8_git_tracking", "check9_forged_id_collision"):
        print(f"=== {k} ===")
        print(json.dumps(prev[k], indent=1)[:3000])
        print()
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
