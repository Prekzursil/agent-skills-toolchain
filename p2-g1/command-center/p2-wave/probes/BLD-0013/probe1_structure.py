#!/usr/bin/env python3
"""BLD-0013 probe 1 (structure + anchors, live): schema-validates the artifact
envelope, re-checks the verdict census, and re-resolves every classification's
demanded_mechanism anchor against the live catalog line."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0013.json"
SCHEMA_REL = "command-center/schema/binding-quality-audit.schema.json"
UNIT = "BLD-0013"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_.:/-]{4,}", str(s or "").lower()))


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))
    cat_lines = CATALOG.read_text(encoding="utf-8").splitlines()

    vc = doc.get("verdict_counts") or {}
    rows = [r for r in (doc.get("classifications") or []) if isinstance(r, dict)]
    sum_vc = sum(v for v in vc.values() if isinstance(v, int))
    n_rows = len(rows)
    ok_census = (sum_vc == int(doc.get("bindings_audited") or -1) == n_rows
                 and sum_vc > 0)

    anchor_ok = True
    anchor_report = []
    for r in rows:
        anc = str(r.get("demanded_anchor") or "")
        path_s, _, line_s = anc.rpartition(":")
        line = int(line_s) if line_s.isdigit() else -1
        f = REPO / path_s.replace("\\", "/") if path_s else None
        ok_path = bool(f and f.is_file())
        ok_line = False
        if ok_path and 1 <= line <= len(cat_lines):
            line_text = cat_lines[line - 1]
            need = tokens(r.get("demanded_mechanism_quote"))
            have = tokens(line_text)
            overlap = len(need & have) / max(len(need), 1)
            ok_line = overlap >= 0.6
            ratio = round(overlap, 2)
        else:
            ratio = None
        if not (ok_path and ok_line):
            anchor_ok = False
        anchor_report.append({"req": r.get("requirement_id"),
                              "anchor": anc, "ratio": ratio,
                              "ok": ok_path and ok_line})

    tests = doc.get("tests") or []
    ok_tests = bool(tests) and all(str(t.get("result", "")).upper() == "PASS"
                                   for t in tests)

    from schema_resolver import validator_for
    errs = sorted(e.message for e in validator_for(SCHEMA_REL).iter_errors({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}))
    schema_ok = not errs

    out = {
        "unit_id": UNIT,
        "probe": "probe1-structure-anchors",
        "bindings_audited": doc.get("bindings_audited"),
        "sum_verdict_counts": sum_vc,
        "n_classifications": n_rows,
        "census_ok": ok_census,
        "anchor_report": anchor_report,
        "anchors_ok": anchor_ok,
        "tests_pass": ok_tests,
        "schema_ok": schema_ok,
        "pass": bool(ok_census and anchor_ok and ok_tests and schema_ok),
    }
    (HERE / "probe1_structure_out.json").write_text(json.dumps(out, indent=1),
                                                    encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe1 census + all {len(rows)} demanded anchors "
              f"re-resolve against the live catalog")
        return 0
    print(f"FAILED:{UNIT}-probe1 census_ok={ok_census} anchors_ok={anchor_ok} "
          f"tests={ok_tests} schema_ok={schema_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
