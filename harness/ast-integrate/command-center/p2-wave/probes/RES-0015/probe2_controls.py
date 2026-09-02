#!/usr/bin/env python3
"""Probe 2: independent controls — second shell, string scan, value enums."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    classify,
    install_dir,
    invoke,
    scan_install_for,
    sh_invented,
    which_agent,
)
from flags import INVENTED_FLAG  # noqa: E402


def main() -> int:
    bin_path = which_agent()
    inst = install_dir(bin_path)

    py = invoke(bin_path, [INVENTED_FLAG])
    py_v, py_r = classify(py)
    sh = sh_invented(bin_path)

    if py_v != "rejected" or sh["verdict"] != "rejected":
        print("FAILED:RES-0015-probe2 invented flag not rejected on both shells")
        print(json.dumps({"python": py, "sh": sh}, indent=2)[:2000])
        return 1
    if py_r != sh["reason"]:
        print(
            "FAILED:RES-0015-probe2 invented reason mismatch "
            f"python={py_r} sh={sh['reason']}"
        )
        return 1

    # Mechanically different signal: byte search of shipped JS, not argv parse.
    ctrl = scan_install_for(inst, "control_request")
    if ctrl["total"] != 0:
        print("FAILED:RES-0015-probe2 control_request unexpectedly present")
        print(json.dumps(ctrl, indent=2)[:1500])
        return 1
    resp = scan_install_for(inst, "control_response")
    prompt = scan_install_for(inst, "permission-prompt-tool")

    of_ok = invoke(bin_path, ["--output-format", "stream-json"])
    of_bad = invoke(bin_path, ["--output-format", "res0015-not-a-format"])
    ok_v, ok_r = classify(of_ok)
    bad_v, bad_r = classify(of_bad)
    if ok_v != "accepted" or ok_r == "unknown-option":
        print("FAILED:RES-0015-probe2 stream-json value not accepted as known format")
        print(of_ok)
        return 1
    if "unknown-option" in (of_bad.get("stderr_tail") or ""):
        print("FAILED:RES-0015-probe2 invented format looked like an unknown FLAG")
        print(of_bad)
        return 1
    if "Allowed values" not in (of_bad.get("stderr_tail") or "") and "Invalid" not in (
        of_bad.get("stderr_tail") or ""
    ):
        print("FAILED:RES-0015-probe2 invented format did not hit the enum")
        print(of_bad)
        return 1
    if bad_r == ok_r and (of_bad.get("stderr_tail") or "") == (of_ok.get("stderr_tail") or ""):
        print("FAILED:RES-0015-probe2 output-format enum is silent in both states")
        return 1

    effort = invoke(bin_path, ["--effort"])
    perm = invoke(bin_path, ["--permission-mode"])
    inp = invoke(bin_path, ["--input-format"])
    for label, run in (("--effort", effort), ("--permission-mode", perm), ("--input-format", inp)):
        v, r = classify(run)
        if v != "rejected":
            print(f"FAILED:RES-0015-probe2 {label} expected rejected, got {v}/{r}")
            print(run)
            return 1

    print(
        json.dumps(
            {
                "python_invented": {"verdict": py_v, "reason": py_r, "shell": "python3-subprocess"},
                "sh_invented": {
                    "verdict": sh["verdict"],
                    "reason": sh["reason"],
                    "shell": sh["shell"],
                    "exit_code": sh["exit_code"],
                },
                "control_request_total": ctrl["total"],
                "control_response_total": resp["total"],
                "permission_prompt_tool_total": prompt["total"],
                "output_format_stream_json": {"verdict": ok_v, "reason": ok_r},
                "output_format_invented": {"verdict": bad_v, "reason": bad_r},
                "claude_control_flags_rejected": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:RES-0015-probe2 second-shell invented-flag control_request scan enum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
