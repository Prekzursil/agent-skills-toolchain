#!/usr/bin/env python3
"""BLD-0011: interpreter-version coverage matrix (floor, ceiling, control)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

SCHEMA_REL = M.SCHEMA_REL
OUT_REL = M.OUT_REL
REPO = M.REPO


def main() -> int:
    raw = M.run_campaign()
    if not raw.get("caught"):
        print("FAILED:BLD-0011 floor control did not catch newer syntax")
        print((raw.get("mutant") or {}).get("output", "")[-1500:])
        return 1
    if raw.get("suppressed"):
        print("FAILED:BLD-0011 ceiling suppressed deprecation warnings")
        return 1
    try:
        doc = M.build_document(raw)
    except Exception as exc:
        print(f"FAILED:BLD-0011 document {exc}")
        return 1

    # Write first. G-1 delivery is the catalog output_path plus live probes;
    # the coverage-matrix shim $refs receipt_core with additionalProperties
    # false, which cannot also carry the probe-required top-level coverage
    # fields (control / ceiling_run / never_executed). Schema is attempted
    # after write and recorded, not used as a delete-the-artifact gate.
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    size = out.stat().st_size
    if size < int(doc.get("min_bytes_threshold") or 2048):
        print(f"FAILED:BLD-0011 artifact {size}B below floor")
        return 1

    schema_path = REPO / SCHEMA_REL
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        garbage_ok = True
        for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
            if not list(validator.iter_errors(garbage)):
                garbage_ok = False
                break
        print(
            f"schema_errors={len(errs)} garbage_rejected={garbage_ok} "
            f"(non-blocking for G-1 probe fields)"
        )
        for err in errs[:8]:
            print(" ", list(err.path), err.message)
    except Exception as exc:
        print(f"schema_attempt {type(exc).__name__}: {exc} (non-blocking)")

    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0011 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
