#!/usr/bin/env python3
"""Probe 2: corruption control fails as designed; exit-code-only is rejected."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0039-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = H.report_body(doc)
    controls = doc.get("controls") or body.get("controls") or {}
    ctrl = controls.get("corruption") or {}
    if ctrl.get("probe_failed_as_designed") is not True:
        print("FAILED:CNF-0039-probe2 artifact corruption flag false")
        return 1
    if controls.get("exit_code_only_postcondition_rejected") is not True:
        print("FAILED:CNF-0039-probe2 artifact did not reject exit-code-only")
        return 1

    wheel = H.write_wheel()
    install_root = HERE / "_install-probe2"
    if install_root.exists():
        shutil.rmtree(install_root)
    H.install_wheel(wheel, install_root)
    scratch = HERE / "_scratch-probe2"
    if scratch.exists():
        shutil.rmtree(scratch)
    out_dir = scratch / "out"
    cwd = scratch / "cwd"
    out_dir.mkdir(parents=True)
    cwd.mkdir(parents=True)

    run = H.run_cli(
        pythonpath=str(install_root.resolve()),
        journey="catalog-export",
        out=out_dir / "catalog-export.out",
        cwd=cwd,
    )
    if run["exit_code"] != 0:
        print("FAILED:CNF-0039-probe2 could not produce a good file", run)
        return 1
    produced = Path(run["produced"])
    result = H.corruption_control(produced)
    print(result["verbatim_output"])
    if not result["probe_failed_as_designed"]:
        print("FAILED:CNF-0039-probe2 corruption control did not fail as designed")
        return 1
    if result.get("good_pass") is not True:
        print("FAILED:CNF-0039-probe2 good-state silent (control is one-sided)")
        return 1
    if result.get("corrupt_pass") is not False:
        print("FAILED:CNF-0039-probe2 corrupt file still passed")
        return 1

    exit_only = H.reject_exit_code_only()
    print(f"exit_code_only rejected={exit_only['rejected']} reason={exit_only['reason']}")
    if not exit_only["rejected"]:
        print("FAILED:CNF-0039-probe2 exit-code-only was accepted")
        return 1

    print("SUCCESS:CNF-0039-probe2 corruption control and exit-code-only rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
