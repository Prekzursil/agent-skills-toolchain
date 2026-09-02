#!/usr/bin/env python3
"""Named probe 1: live clean-venv wheel install, both routes, repo not on sys.path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0028-clean-venv-install.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0028-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    SC.validate_or_die(doc)
    if H.CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0028-probe1 catalog sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0028":
        print("FAILED:CNF-0028-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0028-probe1 self-declared", doc.get("state"))
        return 1

    live = H.run_good()
    if not live["good"]:
        print("FAILED:CNF-0028-probe1 live good-package run failed")
        print(
            json.dumps(
                {
                    "console_ok": live["console_ok"],
                    "python_m_ok": live["python_m_ok"],
                    "repo_on_sys_path": live["repo_on_sys_path"],
                    "console_hits": live["console_repo_hits"],
                    "python_m_hits": live["python_m_repo_hits"],
                    "script_exists": live["script_exists"],
                    "console_stderr": live["console"]["stderr"][-800:],
                    "python_m_stderr": live["python_m"]["stderr"][-800:],
                    "console_payload": live["console_payload"],
                    "python_m_payload": live["python_m_payload"],
                },
                indent=2,
            )
        )
        return 1
    if live["repo_on_sys_path"]:
        print("FAILED:CNF-0028-probe1 repo on sys.path")
        return 1
    if live["console_payload"] != H.PAYLOAD_TOKEN:
        print("FAILED:CNF-0028-probe1 console payload", live["console_payload"])
        return 1
    if live["python_m_payload"] != H.PAYLOAD_TOKEN:
        print("FAILED:CNF-0028-probe1 python -m payload", live["python_m_payload"])
        return 1
    if not live["script_outside_repo"] or not live["venv_outside_repo"]:
        print("FAILED:CNF-0028-probe1 venv or script inside repo")
        return 1

    view = SC.report_view(doc)
    repo_flag = view.get("repo_on_sys_path", doc.get("repo_on_sys_path"))
    if repo_flag is not False:
        print("FAILED:CNF-0028-probe1 artifact repo_on_sys_path not false")
        return 1
    console_sp = view.get("sys_path_console_script") or doc.get("sys_path_console_script")
    pym_sp = view.get("sys_path_python_m") or doc.get("sys_path_python_m")
    if not console_sp or not pym_sp:
        print("FAILED:CNF-0028-probe1 artifact missing printed sys.path")
        return 1

    print(
        "live_console_ok=True live_python_m_ok=True repo_on_sys_path=False "
        f"payload={live['console_payload']!r} script={live['resolved_script_path']}"
    )
    print("SUCCESS:CNF-0028-probe1 clean-venv both routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
