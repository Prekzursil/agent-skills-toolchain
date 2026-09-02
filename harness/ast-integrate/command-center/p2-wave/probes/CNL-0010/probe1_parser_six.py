#!/usr/bin/env python3
"""Probe 1: parser over the six required examples + unsat rejected at parse time."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import grammar as G  # noqa: E402
import staticcheck as S  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0010-stopping-expression-grammar-and-static-validation.schema.json"
)
EXAMPLES = HERE / "fixtures" / "examples.json"
METRICS = HERE / "fixtures" / "metrics.json"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:CNL-0010-probe1 artifact missing")
        return 1
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNL-0010" not in text:
        print("FAILED:CNL-0010-probe1 sentinel-absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0010-probe1 self-declared:{st}")
        return 1
    fx = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)

    rows = []
    for ex in fx["required_six"]:
        r = S.check(ex["surface"], metrics)
        schema_errs = list(validator.iter_errors(r.tree)) if r.tree is not None else ["no-tree"]
        row = {
            "id": ex["id"],
            "surface": ex["surface"],
            "code": r.code,
            "schema_ok": schema_errs == [],
        }
        rows.append(row)
        print(f"E {ex['id']} code={r.code} schema_ok={row['schema_ok']} surface={ex['surface']}")
        if r.code != "OK" or schema_errs:
            print(f"FAILED:CNL-0010-probe1 example {ex['id']} not accepted")
            if schema_errs and schema_errs != ["no-tree"]:
                print(" ", schema_errs[0].message)
            return 1

    bad = S.check(fx["planted_bad_unsat"]["surface"], metrics)
    print(
        f"UNSAT surface={fx['planted_bad_unsat']['surface']!r} code={bad.code} detail={bad.detail}"
    )
    if bad.code != "UNSATISFIABLE":
        print("FAILED:CNL-0010-probe1 x AND NOT x was not rejected as UNSATISFIABLE")
        return 1

    for ex in fx["extra_forms"]:
        r = S.check(ex["surface"], metrics)
        print(f"G {ex['id']} code={r.code} surface={ex['surface']}")
        if r.code != "OK":
            print(f"FAILED:CNL-0010-probe1 extra form {ex['id']} not accepted")
            return 1
        schema_errs = list(validator.iter_errors(r.tree))
        if schema_errs:
            print(f"FAILED:CNL-0010-probe1 extra form {ex['id']} schema {schema_errs[0].message}")
            return 1

    rec = doc.get("x-cnl-0010") or {}
    claimed = rec.get("counts") or {}
    if claimed.get("required_six_parsed_ok") != 6:
        print("FAILED:CNL-0010-probe1 artifact count mismatch")
        return 1

    print(f"parsed_ok={len(rows)} unsat_rejected={bad.code}")
    print("SUCCESS:CNL-0010-probe1 parser six + unsat parse-time reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
