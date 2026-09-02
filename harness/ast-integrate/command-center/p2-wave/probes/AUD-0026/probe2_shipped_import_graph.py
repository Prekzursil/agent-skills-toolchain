#!/usr/bin/env python3
"""Named probe 2: import graph of shippable modules vs declared-dev names.

Independent of probe 1's sidecar. Re-parses manifests and walks AST imports
of shippable (non-test, not packaging-excluded) modules. A shipped import of
a dev-only package is a packaging defect.

Control: shipped fixture importing pytest is flagged; test-only pytest is not.
Mutant: disabling the shippable filter flags the test import (detector can go red).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import split as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0026-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud0026-p2-") as raw:
        control = S.run_control(Path(raw) / "fx")
    if not control["shipped_dev_import_flagged"]:
        return fail("shipped fixture importing pytest was not flagged")
    if not control["test_dev_import_silent"]:
        return fail("test-only pytest import was flagged")
    if not control["shipped_runtime_import_silent"]:
        return fail("shipped import of runtime dep rich was flagged")
    if not control["mutant_no_test_filter_flags_test_import"]:
        return fail("mutant with shippable-filter disabled did not flag test import")
    if not control["pass"]:
        return fail("fixture control failed")

    plugin = S.live_plugin_scan()
    leaks = plugin["leaks"]
    shipped_third = plugin["shipped_third_party"]
    payload = {
        "probe": "probe2-shippable-import-graph",
        "unit_id": "AUD-0026",
        "plugin_root": plugin["plugin_root"],
        "py_file_count": plugin["py_file_count"],
        "shipped_import_count": plugin["shipped_import_count"],
        "shipped_third_party_count": len(shipped_third),
        "shipped_third_party": shipped_third,
        "packaging_defects": leaks,
        "packaging_defect_count": len(leaks),
        "control_shipped_dev_import_flagged": True,
        "control_test_dev_import_silent": True,
        "control_shipped_runtime_import_silent": True,
        "control_mutant_flags_test_import": True,
        "control_leaks": control["leaks"],
        "pass": True,
    }
    (HERE / "probe2-import-graph.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0026-probe2 shippable import graph "
        f"defects={len(leaks)} shipped_third_party={len(shipped_third)} "
        "control_shipped_flagged=True control_test_silent=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
