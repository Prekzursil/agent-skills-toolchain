#!/usr/bin/env python3
"""Probe 2: actual non-Windows install attempts, including source-only control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL


def main() -> int:
    census = H.build_census()
    exp = H.install_experiments(census["rows"])
    both = exp.get("both_states") or {}
    ctrl = exp.get("source_only_control") or {}
    dotenv = exp.get("dotenv_any_wheel") or {}
    yaml = exp.get("pyyaml_native_wheel") or {}
    print(f"non_windows_target={exp.get('non_windows_target')}")
    print(f"install_method={exp.get('install_method')}")
    print(
        "source_only "
        f"compiler_required={ctrl.get('compiler_required')} "
        f"clean_pass={ctrl.get('clean_pass')} "
        f"classification={ctrl.get('classification')} "
        f"cc={ctrl.get('cc_which')} rc={ctrl.get('returncode')}"
    )
    print(
        "dotenv_any_wheel "
        f"clean_pass={dotenv.get('clean_pass')} file={dotenv.get('filename')} "
        f"import_ok={(dotenv.get('import') or {}).get('ok')}"
    )
    print(
        "pyyaml_native_wheel "
        f"clean_pass={yaml.get('clean_pass')} file={yaml.get('filename')} "
        f"native={(yaml.get('extracted') or {}).get('native_objects')}"
    )
    print(f"both_states={json.dumps(both, sort_keys=True)}")
    if ctrl.get("compiler_required") is not True or ctrl.get("clean_pass") is not False:
        print("FAILED:AUD-0027-probe2 source-only control did not report compiler requirement")
        print((ctrl.get("stdout_stderr_tail") or "")[-800:])
        return 1
    if not both.get("pass"):
        print("FAILED:AUD-0027-probe2 both-states control")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        recorded = (doc.get("install_experiments") or {}).get("both_states") or {}
        if recorded.get("pass") is not True:
            print("FAILED:AUD-0027-probe2 artifact both_states.pass is not true")
            return 1
        rec_ctrl = (doc.get("install_experiments") or {}).get("source_only_control") or {}
        if rec_ctrl.get("clean_pass") is True:
            print("FAILED:AUD-0027-probe2 artifact records a clean pass for source-only")
            return 1
        print("artifact_records_compiler_control=true")
    print("SUCCESS:AUD-0027-probe2 install attempts and source-only compiler control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
