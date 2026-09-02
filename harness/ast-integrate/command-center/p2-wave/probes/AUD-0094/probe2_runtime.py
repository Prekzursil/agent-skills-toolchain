#!/usr/bin/env python3
"""Named probe 2: import graph + CI collection + reconstructed path joins.

Independent of probe 1. Catalog reviewer re-runs ONLY this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import ensure_fixtures  # noqa: E402
from inventory import REPO, load_inventory  # noqa: E402
from scan_runtime import control_verdict, scan_runtime  # noqa: E402


def run() -> dict:
    ensure_fixtures()
    inv = load_inventory()
    runtime = scan_runtime(REPO, inv["objects"])
    control = control_verdict(runtime)
    payload = {
        "pass": control["pass"],
        "probe": "probe2-runtime-resolution",
        "unit_id": "AUD-0094",
        "constructed_path": runtime["constructed_path"],
        "constructed_literal_absent": runtime["constructed_literal_absent"],
        "constructed_rebuilt": runtime["constructed_rebuilt"],
        "reconstructed_hit_count": len(runtime["reconstructed_hits"]),
        "import_hit_count": len(runtime["import_hits"]),
        "import_hits": runtime["import_hits"],
        "reconstructed_hits": runtime["reconstructed_hits"],
        "collection": {
            "exit_code": runtime["collection"]["exit_code"],
            "error_names_deleted": runtime["collection"]["error_names_deleted"],
            "ok": runtime["collection"]["ok"],
            "stderr_tail": (runtime["collection"].get("stderr") or "")[-800:],
            "command": runtime["collection"].get("command"),
        },
        "control": control,
        "git_recovered_count": inv["recovered_count"],
        "computed_not_asserted": True,
    }
    return payload


def main() -> int:
    payload = run()
    print(json.dumps(payload, sort_keys=True))
    ctrl = payload["control"]
    print(
        "rebuilt={0} literal_absent={1} collection_ok={2} named={3} import_hit={4}".format(
            ctrl["constructed_rebuilt"],
            ctrl["constructed_literal_absent"],
            ctrl["collection_error_on_deleted_import"],
            ctrl["error_names_deleted_module"],
            ctrl["import_graph_hit"],
        )
    )
    if not payload["pass"]:
        print("FAILED:AUD-0094-probe2 runtime resolution")
        return 1
    print("SUCCESS:AUD-0094-probe2 import graph and CI collection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
