#!/usr/bin/env python3
"""Independent reviewer w2s16 - READ-ONLY verification sweep (2026-10-26).

For each of the 12 shard-16 units:
  1. artifact at catalog output_path: exists, non-empty, parses as JSON dict
  2. not self-declared BLOCKED/FAILED (state field)
  3. receipt closure state: reviewer.verdict / independent / state consistency
  4. live sha256 (CRLF->LF normalized) vs probes/<id>/UNIT-ARTIFACT-MANIFEST.json row
  5. output_schema validation (jsonschema, draft auto-detected)
NO writes here. Probes are run by the sibling script run_probes.py.
"""
import hashlib
import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

UNITS = [
    "IMP-0470", "IMP-0478",
    "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020", "REL-0021", "REL-0022",
    "RES-0004", "RES-0009", "RES-0011",
]


def norm_sha(p: Path) -> str:
    data = p.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in catalog["work_units"]}
    report = {}
    any_fail = False
    for uid in UNITS:
        entry = {"checks": {}, "fail": []}
        cat = byid.get(uid)
        if cat is None:
            entry["fail"].append("catalog-entry-missing")
            report[uid] = entry
            any_fail = True
            continue
        out_rel = cat.get("output_path")
        schema_rel = cat.get("output_schema")
        entry["output_path"] = out_rel
        entry["output_schema_ref"] = schema_rel
        art = REPO / out_rel
        # 1. artifact present/non-empty/parses
        if not art.exists():
            entry["fail"].append("artifact-missing")
        elif art.stat().st_size == 0:
            entry["fail"].append("artifact-empty")
        else:
            try:
                doc = json.loads(art.read_text(encoding="utf-8"))
                if not isinstance(doc, dict):
                    entry["fail"].append("artifact-not-dict")
                else:
                    entry["checks"]["parses-dict"] = True
            except Exception as exc:
                entry["fail"].append(f"artifact-unparseable: {exc}")
                doc = None
        # 2. self-block
        state = doc.get("state") if isinstance(doc, dict) else None
        entry["state"] = state
        if state in ("BLOCKED", "FAILED"):
            entry["fail"].append(f"self-blocked state={state}")
        else:
            entry["checks"]["no-failure-block"] = True
        # 3. receipt closure posture
        rev = doc.get("reviewer") if isinstance(doc, dict) else None
        entry["reviewer"] = {
            "verdict": (rev or {}).get("verdict"),
            "independent": (rev or {}).get("independent"),
            "reviewer_id": (rev or {}).get("reviewer_id"),
        }
        if state == "SUCCESS":
            if (rev or {}).get("verdict") == "PASS" and (rev or {}).get("independent") is True:
                entry["checks"]["receipt-core-success-gate"] = True
            else:
                entry["fail"].append(
                    "receipt-core-violation: SUCCESS without reviewer PASS+independent"
                )
        else:
            entry["needs_closure"] = True
        # 4. sha vs manifest
        live = norm_sha(art)
        entry["live_sha256"] = live
        entry["live_bytes"] = art.stat().st_size
        man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_p.exists():
            entry["fail"].append("unit-manifest-missing")
        else:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = [a for a in man.get("artifacts", []) if a.get("path") == out_rel]
            if not rows:
                entry["fail"].append("manifest-row-for-output-path-missing")
            else:
                row = rows[0]
                entry["manifest_sha"] = row.get("sha256")
                entry["manifest_bytes"] = row.get("bytes")
                if row.get("sha256") == live:
                    entry["checks"]["manifest-sha-match"] = True
                else:
                    entry["fail"].append(
                        f"manifest-sha-mismatch declared={row.get('sha256')} live={live}"
                    )
        # 5. schema validation
        sp = REPO / schema_rel
        if not sp.exists():
            entry["fail"].append(f"schema-file-missing: {schema_rel}")
        elif isinstance(doc, dict):
            try:
                schema = json.loads(sp.read_text(encoding="utf-8"))
                V = jsonschema.validators.validator_for(schema)
                V.check_schema(schema)
                errs = sorted(V(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
                if errs:
                    entry["schema_error_count"] = len(errs)
                    entry["schema_errors_first"] = [
                        "/".join(str(x) for x in e.absolute_path) + ": " + e.message
                        for e in errs[:8]
                    ]
                    entry["fail"].append(f"output_schema-errors={len(errs)}")
                else:
                    entry["checks"]["output_schema-valid"] = True
            except Exception as exc:
                entry["fail"].append(f"schema-validation-crash: {exc}")
        if entry["fail"]:
            any_fail = True
        report[uid] = entry

    (Path(__file__).parent / "readonly-sweep.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8"
    )
    for uid, e in report.items():
        st = "PASS-SOFAR" if not e.get("fail") else "FAIL " + "; ".join(e["fail"])
        print(f"{uid}: state={e.get('state')} closure_needed={e.get('needs_closure', False)} -> {st}")
    print("ANY-FAIL" if any_fail else "ALL-CLEAN-SOFAR")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
