#!/usr/bin/env python3
"""Probe 2: re-run the CRLF detector; confirm WSL bash fails the known-broken fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runner as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0105-shell-interpreter-conformance.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0105-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0105-probe2 self-declared", doc.get("state"))
        return 1

    fixtures = R.write_fixtures()
    interps = R.discover_interpreters()
    crlf = R.run_crlf_control(interps, fixtures["crlf"])
    apos = R.run_apostrophe_control(interps, fixtures["apostrophe"])
    posix = R.run_posix_path_control(interps, fixtures["ok_lf"])
    implicit = R.parse_shebang(fixtures["implicit"]) is None

    if not crlf["wsl_bash_failed"]:
        print("FAILED:CNF-0105-probe2 CRLF fixture did not fail under wsl-bash")
        print(json.dumps(crlf["wsl_run"], indent=2))
        return 1
    if not crlf["git_bash_standin_passed"]:
        print("FAILED:CNF-0105-probe2 CRLF fixture did not pass under git-bash stand-in")
        print(json.dumps(crlf["git_bash_run"], indent=2))
        return 1
    if not apos["invoked_by_path"] or apos["inlined_into_command_body"]:
        print("FAILED:CNF-0105-probe2 apostrophe not invoked by PATH")
        print(json.dumps(apos, indent=2, default=str)[:2000])
        return 1
    if not apos["script_contains_apostrophe"]:
        print("FAILED:CNF-0105-probe2 fixture has no apostrophe")
        return 1
    if posix["argument"] != R.POSIX_ARG or posix["exit_code"] != 0:
        print("FAILED:CNF-0105-probe2 posix path control")
        print(json.dumps(posix, indent=2, default=str)[:2000])
        return 1
    if not implicit:
        print("FAILED:CNF-0105-probe2 implicit shebang not flagged")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    art_crlf = ((doc.get("controls") or {}).get("crlf") or {}) or (
        (report.get("controls") or {}).get("crlf") or {}
    )
    if art_crlf.get("wsl_bash_failed") is not True:
        print("FAILED:CNF-0105-probe2 artifact does not record wsl CRLF failure")
        return 1
    print(json.dumps({
        "wsl_bash_failed": True,
        "git_bash_standin_passed": True,
        "wsl_error": crlf["wsl_run"]["first_error_line"],
        "apostrophe_by_path": True,
        "posix_arg": posix["argument"],
        "implicit_flagged": True,
    }, sort_keys=True))
    print("SUCCESS:CNF-0105-probe2 CRLF detector fired on known-broken fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
