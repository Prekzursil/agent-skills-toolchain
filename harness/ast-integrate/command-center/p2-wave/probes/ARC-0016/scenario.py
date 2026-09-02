"""Executable escape-hatch + blast-radius scenario for ARC-0016.

Against the live A2 generator (ARC-0010):
  1. Typed registry refuses opaque_body.
  2. A hatch that copies opaque_body reintroduces hand-edit drift.
  3. One shared-path generator bug is counted across generate() outputs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "hatch-run"

import hatch as H  # noqa: E402


def run_scenario() -> dict[str, Any]:
    registry = H.load_registry()
    refusal = H.typed_rejects_opaque_body(registry)
    blast = H.blast_radius(registry)
    FIX.mkdir(parents=True, exist_ok=True)
    drift = H.run_drift_demo(FIX, registry)
    n = int(blast["generated_file_count"])
    affected = int(blast["files_affected_by_one_shared_path_bug"])
    blast_ok = (
        blast.get("computed_not_asserted") is True
        and n >= 8
        and affected == n
        and len(blast.get("affected_paths") or []) == n
    )
    typed_ok = refusal.get("rejected") is True
    drift_ok = drift.get("hatch_reintroduces_drift") is True
    passed = typed_ok and drift_ok and blast_ok
    return {
        "pass": passed,
        "typed_rejects_hatch": typed_ok,
        "typed_refusal": refusal,
        "hatch_reintroduces_drift": drift_ok,
        "drift": drift,
        "blast_radius": blast,
        "blast_radius_equals_file_count": blast_ok,
        "generated_file_count": n,
        "files_affected_by_one_shared_path_bug": affected,
    }


if __name__ == "__main__":
    import json
    import sys

    result = run_scenario()
    print(json.dumps({k: result[k] for k in sorted(result)}, indent=2, sort_keys=True))
    if not result.get("pass"):
        print("FAILED:ARC-0016-scenario")
        raise SystemExit(1)
    print("SUCCESS:ARC-0016-scenario")
    raise SystemExit(0)
