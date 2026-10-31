#!/usr/bin/env python3
"""TST-0194 probe1 -- case-only duplicate manifest entries are caught at BUILD
time, with both paths named; the case-distinct-but-non-colliding manifest
builds (both-states control). Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packer as PK  # noqa: E402

UNIT = "TST-0194"
RUN = HERE / ".run-p1"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)

    colliding = {
        "Lib/Hooks.py": b"# hooks A\n",
        "lib/hooks.py": b"# hooks B (case-variant)\n",
        "README.md": b"readme\n",
    }
    err = None
    named: list[str] = []
    try:
        PK.build(colliding, RUN / "pack-colliding")
    except PK.PackerBuildError as e:
        err = str(e)
        named = list(e.colliding)
    both_named = set(named) == {"Lib/Hooks.py", "lib/hooks.py"}

    distinct = {
        "Lib/Hooks.py": b"# hooks\n",
        "lib/utils.py": b"# utils (case-distinct prefix, no collision)\n",
        "README.md": b"readme\n",
    }
    built = None
    try:
        built = PK.build(distinct, RUN / "pack-distinct")
    except PK.PackerBuildError as e:
        err = str(e)

    payload = {
        "probe": "probe1-build-rejects",
        "unit_id": UNIT,
        "pass": err is not None and both_named and built is not None,
        "colliding_manifest": {
            "build_failed": err is not None,
            "error_names_both_paths": named,
            "error_text": err,
        },
        "distinct_manifest": {
            "built": built is not None,
            "files": sorted(p.relative_to(built).as_posix() for p in built.rglob("*") if p.is_file()) if built else [],
        },
        "signals": {
            "a_packer_exit_and_message": err,
            "b_casefold_set_vs_raw_set": {
                "raw_distinct": len({p for p in colliding}),
                "casefold_distinct": len({p.casefold() for p in colliding}),
            },
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 build_rejects=True both_named=%s distinct_builds=True"
              % (UNIT, both_named))
        return 0
    print("FAILED:%s-probe1 err=%s named=%s built=%s" % (UNIT, err is not None, named, built is not None))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
