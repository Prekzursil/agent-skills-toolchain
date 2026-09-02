#!/usr/bin/env python3
"""Write command-center/wfa/WFA-0021-sweep-vendor-documentation.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402
import sweep as S  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0021-sweep-vendor-documentation.json"
SCHEMA = HERE / "sweep-report.schema.json"


def write_artifact() -> Path:
    sweep = S.run_sweep()
    doc = S.build_artifact(sweep)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        raise SystemExit(f"FAILED:WFA-0021 emit schema {errs[0].message}")
    if S.SENTINEL not in json.dumps(doc):
        raise SystemExit("FAILED:WFA-0021 emit sentinel")
    if not sweep["summary"]["unverified"]:
        raise SystemExit("FAILED:WFA-0021 emit expected UNVERIFIED rows")
    if "anthropic.claude-code.skills" not in sweep["summary"][
        "represented_in_reconstructed_index"
    ]:
        raise SystemExit("FAILED:WFA-0021 emit skills should be represented")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return OUT


def main() -> int:
    path = write_artifact()
    print(f"wrote {path.relative_to(REPO).as_posix()} bytes={path.stat().st_size}")
    print("SUCCESS:WFA-0021-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
