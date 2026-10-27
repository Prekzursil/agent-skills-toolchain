#!/usr/bin/env python3
"""w4s3 reviewer: THIRD instrument - the program-canonical schema_resolver."""
from __future__ import annotations
import importlib.util, json, os, sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
IDS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
       "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]

os.environ["AST_INTEGRATE_ROOT"] = str(REPO)
spec = importlib.util.spec_from_file_location(
    "schema_resolver", REPO / "platform" / "lib" / "schema_resolver.py")
sr = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = sr
spec.loader.exec_module(sr)

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

out = {}
for uid in IDS:
    u = byid[uid]
    art = json.loads((REPO / str(u["output_path"]).replace("\\", "/")).read_text(encoding="utf-8"))
    errs = sr.validate_artifact(art, u["output_schema"])
    out[uid] = {"output_schema": u["output_schema"], "error_count": len(errs), "errors": errs[:12]}
    print(f"{uid}: {len(errs)} error(s) via program schema_resolver (AST_INTEGRATE_ROOT=p2-g1)")
    for e in errs[:5]:
        print("   ", e[:190])

(HERE / "canonical_resolver_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote", HERE / "canonical_resolver_results.json")
