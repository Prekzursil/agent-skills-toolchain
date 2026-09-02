#!/usr/bin/env python3
"""Named probe 2: both-states mutants (missing script; missing runtime dep)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0028-clean-venv-install.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0028-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0028-probe2 self-declared", doc.get("state"))
        return 1

    live = H.run_mutants()
    missing_script = live["missing_script"]
    missing_dep = live["missing_runtime_dependency"]
    if not missing_script["blind_spot_demonstrated"]:
        print("FAILED:CNF-0028-probe2 missing-script blind spot not demonstrated")
        print(json.dumps(missing_script, indent=2)[:2000])
        return 1
    if not missing_dep["surfaced_in_clean_venv"]:
        print("FAILED:CNF-0028-probe2 missing runtime dep did not surface in clean venv")
        print(json.dumps(missing_dep, indent=2)[:2000])
        return 1
    if missing_dep["in_tree_host_python_m_ok"] is not True:
        print("FAILED:CNF-0028-probe2 in-tree control did not stay green")
        return 1
    if missing_dep["clean_venv_console_ok"] or missing_dep["clean_venv_python_m_ok"]:
        print("FAILED:CNF-0028-probe2 clean venv masked missing dep")
        return 1

    stderr = missing_dep.get("clean_venv_stderr") or ""
    if "jsonschema" not in stderr and "ModuleNotFoundError" not in stderr:
        print("FAILED:CNF-0028-probe2 missing-dep stderr did not name the gap")
        print(stderr[-800:])
        return 1

    print(
        "missing_script_blind_spot=True "
        "in_tree_masks_missing_dep=True "
        "clean_venv_surfaces_missing_dep=True"
    )
    print("SUCCESS:CNF-0028-probe2 both-states packaging controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
