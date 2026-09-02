#!/usr/bin/env python3
"""Probe 1: expressibility of three live blueprints of different shapes.

Each source blueprint is encoded end to end. Any inexpressible construct is
a schema defect. Encoded instances must validate. Dry-run plans of the
encoding must equal compile_plan of the source (lossless for plan fields).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dsl as D  # noqa: E402

GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
]


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0082-probe1 {msg}")
    return 1


def main() -> int:
    schema = D.load_contract()
    v = D.validator(schema)
    for i, g in enumerate(GARBAGE):
        errs = list(v.iter_errors(g))
        print(f"garbage[{i}] rejected={bool(errs)} n={len(errs)}")
        if not errs:
            return fail(f"schema-vacuous garbage[{i}]")

    constructs = D.schema_constructs()
    print(
        "constructs optional_defined="
        f"{constructs['optional_defined']} certified_defined="
        f"{constructs['certified_defined']}"
    )
    if not constructs["optional_defined"]:
        return fail(f"optional-constructs-missing:{constructs['missing_optional']}")
    if not constructs["certified_defined"]:
        return fail(f"certified-constructs-missing:{constructs['missing_certified']}")

    rows = D.encode_corpus()
    if len(rows) != 3:
        return fail(f"expected-3-blueprints got={len(rows)}")
    shapes = [r["shape"] for r in rows]
    print(f"shapes={shapes}")
    if len(set(shapes)) != 3:
        return fail("shapes-not-distinct")

    shas = []
    for row in rows:
        print(
            f"encode id={row['id']} shape={row['shape']} "
            f"inexpressible={row['inexpressible']} "
            f"schema_errors={len(row['schema_errors'])} "
            f"plan={row['plan_sha256'][:16]} raw={row['raw_plan_sha256'][:16]} "
            f"kinds={row['plan_kinds']}"
        )
        if row["inexpressible"]:
            return fail(f"schema-defect:{row['source_path']}:{row['inexpressible']}")
        if row["schema_errors"]:
            return fail(
                f"encoded-rejected:{row['source_path']}:"
                + " | ".join(row["schema_errors"][:6])
            )
        if row["plan_sha256"] != row["raw_plan_sha256"]:
            return fail(f"lossy-encoding:{row['source_path']}")
        shas.append(row["plan_sha256"])

    if len(set(shas)) != 3:
        return fail(f"plans-not-distinct:{shas}")

    print("SUCCESS:ARC-0082-probe1 three-shape expressibility lossless")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
