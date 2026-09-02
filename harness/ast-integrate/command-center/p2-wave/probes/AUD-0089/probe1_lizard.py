#!/usr/bin/env python3
"""Probe 1: lizard 1.17.10 report at CCN threshold 15 over the baseline set."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = str(HERE / "vendor") + os.pathsep + os.environ.get("PYTHONPATH", "")

import lib  # noqa: E402


def main() -> int:
    liz_ver, _rad_ver = lib.ensure_vendor()
    files = lib.discover_python()
    list_path = HERE / "probe1-source-files.txt"
    list_path.write_text("\n".join(lib.rel_of(p) for p in files) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(lib.VENDOR)
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "lizard",
        "-C",
        "15",
        "-l",
        "python",
        "-i",
        "-1",
        "-f",
        str(list_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(lib.REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=165,
    )
    raw = ((proc.stdout or "") + (proc.stderr or "")).strip()
    (HERE / "probe1-lizard.raw.txt").write_text(raw + "\n", encoding="utf-8")

    rows = lib.lizard_functions(files)
    control = lib.fixture_control()
    over = lib.over_threshold(rows)
    top = lib.top_row(rows)
    payload = {
        "ccn_threshold": lib.CCN_THRESHOLD,
        "cli_command": " ".join(cmd),
        "cli_exit_code": proc.returncode,
        "control": control,
        "file_count": len(files),
        "function_count": len(rows),
        "histogram": lib.histogram(rows),
        "lizard_version": liz_ver,
        "n_over_ccn_15": len(over),
        "over_ccn_15": over,
        "pinned_lizard": lib.PINNED_LIZARD,
        "probe": "probe1-lizard",
        "top": top,
        "unit_id": "AUD-0089",
    }
    lib.dump(HERE / "probe1-lizard.json", payload)
    print(json.dumps(
        {
            "cli_exit_code": proc.returncode,
            "control_fired": control["fired_on_bad_state"],
            "control_silent": control["silent_on_good_state"],
            "file_count": len(files),
            "function_count": len(rows),
            "lizard_version": liz_ver,
            "n_over_ccn_15": len(over),
            "top": top,
        },
        indent=2,
        sort_keys=True,
    ))
    if raw:
        print("--- lizard -C 15 tail ---")
        print("\n".join(raw.splitlines()[-12:]))
    if liz_ver != lib.PINNED_LIZARD:
        print("FAILED:AUD-0089-probe1 lizard version mismatch")
        return 1
    if proc.returncode not in (0,):
        print(f"FAILED:AUD-0089-probe1 lizard CLI exit {proc.returncode}")
        return 1
    if not files or not rows:
        print("FAILED:AUD-0089-probe1 empty lizard report")
        return 1
    if not control["fired_on_bad_state"] or not control["silent_on_good_state"]:
        print("FAILED:AUD-0089-probe1 planted CCN control did not discriminate")
        return 1
    print(
        f"SUCCESS:AUD-0089-probe1 lizard {liz_ver} -C {lib.CCN_THRESHOLD} "
        f"files={len(files)} funcs={len(rows)} over15={len(over)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
