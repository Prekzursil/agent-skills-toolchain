#!/usr/bin/env python3
"""Probe 1: walker must not import the manifest writer; fixture catches hash/absent drift."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALKER_PATH = HERE / "walker.py"


def load_walker():
    spec = importlib.util.spec_from_file_location("cnf0122_walker", WALKER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:CNF-0122-probe1 cannot load walker.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cnf0122_walker"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    walker = load_walker()
    leaked = [
        name
        for name in sys.modules
        if name == "render"
        or name.endswith(".render")
        or "unit_manifest" in name.split(".")
    ]
    if leaked:
        print("FAILED:CNF-0122-probe1 walker import leaked writer modules: " + str(leaked))
        return 1
    indep = walker.independence_report()
    if not indep.get("independent") or indep.get("imports_manifest_writer"):
        print("FAILED:CNF-0122-probe1 walker imports the manifest writer: " + json.dumps(indep))
        return 1
    if indep.get("forbidden_imports"):
        print("FAILED:CNF-0122-probe1 forbidden imports: " + str(indep["forbidden_imports"]))
        return 1

    control = walker.run_unmanifested_control()
    if control["expected_mismatch"] not in control["hash_mismatch_paths"]:
        print("FAILED:CNF-0122-probe1 hash mismatch not reported: " + json.dumps(control["hash_mismatch_paths"]))
        return 1
    if control["expected_absent"] not in control["absent_paths"]:
        print("FAILED:CNF-0122-probe1 manifested-but-absent not reported: " + json.dumps(control["absent_paths"]))
        return 1
    if control["expected_matching"] not in control["matching_paths"]:
        print("FAILED:CNF-0122-probe1 matching file not kept: " + json.dumps(control["matching_paths"]))
        return 1
    basis = control["comparison"].get("hash_basis")
    if basis != walker.HASH_BASIS:
        print("FAILED:CNF-0122-probe1 hash basis is not worktree bytes: " + str(basis))
        return 1
    if control["comparison"].get("committed_bytes_used_for_comparison"):
        print("FAILED:CNF-0122-probe1 comparison used committed bytes")
        return 1
    src = walker.walker_source_anchor()
    if "walker.py:" not in src:
        print("FAILED:CNF-0122-probe1 walker source missing file:line: " + src)
        return 1
    print(
        json.dumps(
            {
                "independent": True,
                "hash_mismatch_reported": True,
                "absent_reported": True,
                "matching_kept": True,
                "hash_basis": basis,
                "walker_source": src,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0122-probe1 walker independent of writer; fixture hash and absent drift reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
