#!/usr/bin/env python3
"""Shard-17 w2 reviewer: schema-validate the 12 artifacts via the BLESSED
instrument (platform/lib/schema_resolver.py) - disk-only, repo-confined,
fail-closed. Records per-unit resolve() details + full error lists."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as SR  # noqa: E402

CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u.get("id"): u for u in CAT["work_units"]}
IDS = [
    "RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
]

out = {}
for uid in IDS:
    decl = units[uid].get("output_schema")
    doc = json.loads((REPO / units[uid]["output_path"].replace("\\", "/")).read_text(encoding="utf-8"))
    entry = {}
    try:
        res = SR.resolve(decl)
        entry["resolved"] = res.as_dict()
    except Exception as exc:  # noqa: BLE001
        entry["resolved"] = None
        entry["resolve_error"] = f"{type(exc).__name__}: {exc}"
        entry["errors"] = ["resolve-failed"]
        out[uid] = entry
        print(f"{uid}: RESOLVE-FAIL {entry['resolve_error'][:160]}")
        continue
    try:
        errs = SR.validate_artifact(doc, decl)
    except Exception as exc:  # noqa: BLE001
        entry["errors"] = [f"validator-error: {type(exc).__name__}: {exc}"]
        errs = entry["errors"]
    entry["error_count"] = len(errs)
    entry["errors"] = errs
    status = "OK" if not errs else f"VIOLATIONS={len(errs)}"
    print(f"{uid}: {status} class={entry['resolved']['artifact_class']} "
          f"pinned={entry['resolved']['report_kind_pinned']} "
          f"phys={entry['resolved']['physical_path']}#{entry['resolved']['physical_fragment']}")
    for e in errs[:3]:
        print(f"    - {e[:200]}")
    out[uid] = entry

dst = Path(r"C:\Users\Prekzursil\p2-g1\_rev-w2-shard17\schema-resolver-results.json")
dst.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print("WROTE:", dst)
