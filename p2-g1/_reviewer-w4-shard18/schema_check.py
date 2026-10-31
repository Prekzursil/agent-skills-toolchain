#!/usr/bin/env python3
"""Re-validate the 12 shard18-w4 artifacts with the CORRECT jsonschema draft
(2020-12 via validator_for), resolving wrapper $ref and $defs pointers the way
the schema declares. Controls against the Draft7Validator pass in battery.py.
"""
import json
from pathlib import Path

import jsonschema
from jsonschema.validators import validator_for

REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ["TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
         "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138"]


def validate_one(ref, doc):
    filepart, _, frag = ref.partition("#")
    schema_path = REPO / filepart
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    target = schema
    if frag:
        for part in [x for x in frag.split("/") if x]:
            target = target[part.replace("~1", "/").replace("~0", "~")]
    resolver = jsonschema.RefResolver(base_uri=schema_path.resolve().as_uri(),
                                      referrer=schema)
    cls = validator_for(target if not frag else schema)
    if frag:
        cls = validator_for(target)
    cls.check_schema(target)
    validator = cls(target, resolver=resolver)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    return errors


def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    cmap = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and "id" in u}
    out_lines = []
    for uid in UNITS:
        unit = cmap[uid]
        doc = json.loads((REPO / unit["output_path"]).read_text(encoding="utf-8"))
        try:
            errors = validate_one(unit["output_schema"], doc)
        except Exception as exc:
            out_lines.append("%s VALIDATE-ERROR %s: %s" % (uid, type(exc).__name__, str(exc)[:200]))
            continue
        if errors:
            e0 = errors[0]
            out_lines.append("%s SCHEMA-FAIL (%d errors) first: %s at %s" % (
                uid, len(errors), str(e0.message)[:160], "/".join(map(str, e0.path))[:120]))
            for e in errors[1:4]:
                out_lines.append("    also: %s at %s" % (str(e.message)[:120], "/".join(map(str, e.path))[:100]))
        else:
            out_lines.append("%s SCHEMA-OK" % uid)
    print("\n".join(out_lines))
    (Path(__file__).parent / "schema-validation.txt").write_text(
        "\n".join(out_lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
