#!/usr/bin/env python3
"""TST-0181 probe1 -- a $schema key must not change which hooks load.

Both-states: identical loaded set and count with and without the $schema key.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hooks_loader as HL  # noqa: E402

UNIT = "TST-0181"
RUN = HERE / ".run-p1"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    (RUN / "hooks").mkdir(parents=True)
    for i in range(3):
        (RUN / "hooks" / ("h%d.py" % i)).write_text("# hook %d\n" % i)
    with_schema = {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "hooks": {
            "alpha": {"command": "run-alpha", "file": "h0.py"},
            "beta": {"command": "run-beta", "file": "h1.py"},
            "gamma": {"command": "run-gamma", "file": "h2.py"},
        },
    }
    without_schema = {k: v for k, v in with_schema.items() if k != "$schema"}
    (RUN / "with.json").write_text(json.dumps(with_schema), encoding="utf-8")
    (RUN / "without.json").write_text(json.dumps(without_schema), encoding="utf-8")

    a = HL.load_hooks(RUN / "with.json", RUN / "hooks")
    b = HL.load_hooks(RUN / "without.json", RUN / "hooks")
    same_set = a["loaded"] == b["loaded"]
    same_count = len(a["loaded"]) == len(b["loaded"]) == 3
    schema_ignored = not a.get("crashed_on_schema")

    payload = {
        "probe": "probe1-schema-neutral",
        "unit_id": UNIT,
        "pass": same_set and same_count and schema_ignored,
        "with_schema": {"count": len(a["loaded"]), "names": sorted(a["loaded"])},
        "without_schema": {"count": len(b["loaded"]), "names": sorted(b["loaded"])},
        "identical_loaded_set": same_set,
        "identical_count": same_count,
        "schema_did_not_crash_loader": schema_ignored,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 count_with=%d count_without=%d identical_set=%s"
              % (UNIT, len(a["loaded"]), len(b["loaded"]), same_set))
        return 0
    print("FAILED:%s-probe1 with=%d without=%d identical=%s"
          % (UNIT, len(a["loaded"]), len(b["loaded"]), same_set))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
