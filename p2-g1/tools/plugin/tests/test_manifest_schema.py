#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import manifest_schema as ms  # noqa: E402


def main() -> int:
    live = ms.live_manifest_object()
    schema = ms.load_schema()
    result = ms.validate_file(ms.MANIFEST_PATH)
    assert result["ok"], result
    assert result["libraries_agree"]
    assert result["jsonschema"]["library"] != result["fastjsonschema"]["library"]
    rows = ms.six_mutations(live, schema)
    assert len(rows) == 6
    print("SUCCESS:IMP-0006-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
