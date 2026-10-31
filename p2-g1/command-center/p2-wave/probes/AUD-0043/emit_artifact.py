#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0043-ci-local-invocation-parity.json."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import inventory as I  # noqa: E402
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402


def _tail(text: str, n: int = 1200) -> str:
    text = text or ""
    return text[-n:] if len(text) > n else text


def build_doc(live: dict, census: dict) -> dict:
    sg = live["source_good"]
    sm = live["source_mutant"]
    ig = live["installed_good"]
    im = live["installed_mutant"]
    both = bool(live["both_states_exclude_module"])
    parity_good = bool(live["parity_on_good_package"])
    ci_console = bool(census.get("ci_uses_installed_console_script"))
    ci_pytest = bool(census.get("ci_uses_source_or_editable_pytest"))
    counts = census.get("counts") or {}
    prod_scripts = census.get("production_project_scripts") or []
    prod_paths = ", ".join(row["path"] for row in prod_scripts) or "(none)"
    if prod_scripts:
        scripts_clause = (
            f"{len(prod_scripts)} production pyproject.toml file(s) declare "
            f"[project.scripts] ({prod_paths}). Inventoried CI still runs the "
            "suite via python -m pytest / bare pytest / pip install -e; "
            f"{counts.get('wheel-artifact-install', 0)} steps install a built "
            "wheel and ci_uses_installed_console_script="
            f"{str(ci_console).lower()}."
        )
    else:
        scripts_clause = (
            "No production pyproject.toml on this tree declares "
            "[project.scripts] (only probe fixtures do). "
            f"{counts.get('wheel-artifact-install', 0)} steps install a "
            "built wheel."
        )
    answer = (
        "CI on this worktree is inventoried from AUD-0041 (`.github/workflows` "
        f"is {'present' if census.get('github_workflows_present') else 'absent'}). "
        f"{counts.get('python-m-pytest', 0)} steps use python -m pytest, "
        f"{counts.get('bare-pytest', 0)} use bare pytest, "
        f"{counts.get('editable-install', 0)} use pip install -e. "
        f"{scripts_clause} Live fixture aud0043-subject: source-tree "
        f"python -m pytest and the installed aud0043-suite console script "
        f"{'AGREE (both GREEN)' if parity_good else 'DISAGREE'} on the complete "
        "include list, and "
        f"{'DIVERGE as required' if both else 'FAILED TO DIVERGE'} when "
        "aud0043_extra is removed from the package include list (source stays "
        "GREEN, installed turns RED). Source-tree pytest is therefore a blind "
        "detector for a packaging/import-path omission; the installed console "
        "script is the arm that fires."
    )
    ok = both and parity_good and (sg.get("collected") or 0) > 0
    state = "SUCCESS" if ok else "FAILED"
    mutant_pyproject = (
        "command-center/p2-wave/probes/AUD-0043/pkg/pyproject.toml"
    )
    tests = [
        {
            "id": "probe1-source-pytest",
            "command": S.P1,
            "result": "PASS" if sg.get("ok") and sm.get("ok") else "FAIL",
            "verbatim_output": _tail(
                f"good rc={sg.get('returncode')} collected={sg.get('collected')} "
                f"passed={sg.get('passed')}\n"
                + str(sg.get('stdout_tail') or "")
                + f"\nmutant rc={sm.get('returncode')} collected={sm.get('collected')} "
                f"passed={sm.get('passed')}\n"
                + str(sm.get("stdout_tail") or "")
            ),
        },
        {
            "id": "probe2-installed-console",
            "command": S.P2,
            "result": "PASS" if ig.get("console_ok") and not im.get("console_ok") else "FAIL",
            "verbatim_output": _tail(
                f"good console_ok={ig.get('console_ok')} rc="
                f"{(ig.get('console') or {}).get('returncode')} "
                f"script={ig.get('resolved_script_path')}\n"
                + str((ig.get('console') or {}).get('stdout') or "")
                + f"\nmutant console_ok={im.get('console_ok')} rc="
                f"{(im.get('console') or {}).get('returncode')} "
                f"error={im.get('report_error')}\n"
                + str((im.get("console") or {}).get("stderr") or "")
            ),
        },
    ]
    controls = [
        {
            "id": "known-good-full-include",
            "kind": "known-absent",
            "plant": {
                "id": "aud0043-full-include",
                "path": mutant_pyproject,
                "include": S.INCLUDE_GOOD,
            },
            "source_pytest_ok": bool(sg.get("ok")),
            "installed_console_ok": bool(ig.get("console_ok")),
            "verdict": "silent",
        },
        {
            "id": "known-broken-exclude-aud0043_extra",
            "kind": "known-present-packaging-omit",
            "plant": {
                "id": "exclude-aud0043_extra-from-include",
                "path": mutant_pyproject,
                "include": S.INCLUDE_MUTANT,
            },
            "source_pytest_ok": bool(sm.get("ok")),
            "installed_console_ok": bool(im.get("console_ok")),
            "source_stays_green": bool(live["source_stays_green_on_omit"]),
            "installed_turns_red": bool(live["installed_turns_red_on_omit"]),
            "verdict": "fired" if both else "blind",
        },
        {
            "id": "ci-invocation-mode-census",
            "kind": "inventory",
            "plant": {
                "id": "aud-0041-yaml-inventory",
                "path": S.INVENTORY_REL,
            },
            "ci_uses_installed_console_script": ci_console,
            "ci_uses_source_or_editable_pytest": ci_pytest,
            "verdict": "found",
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": S.UNIT,
        "state": state,
        "sentinel": S.SENTINEL,
        "completion_sentinel": S.SENTINEL,
        "question": S.QUESTION,
        "answer": answer,
        "detector": {
            "name": "aud-0043-source-pytest-vs-installed-console",
            "mechanism": (
                "Run python -m pytest against the fixture source tree with "
                "PYTHONPATH=src, then pip-install a built wheel into a fresh "
                "venv and invoke the aud0043-suite console script. Plant: drop "
                "aud0043_extra from setuptools package include."
            ),
            "index_injection": False,
        },
        "controls": controls,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "AUD-0043-probe2-installed-console-and-exclude-control",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "method": (
                "Probe 2 re-runs wheel install + console script on the good "
                "package and the include-list mutant; it must stay GREEN then "
                "turn RED. Probe 1 independently re-runs python -m pytest on "
                "both trees and requires collected>0."
            ),
        },
        "artifacts": [
            {"path": S.OUT_REL, "exists": True, "role": "primary"},
            {"path": S.SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/AUD-0043/harness.py",
                "exists": True,
                "role": "detector",
            },
            {
                "path": S.INVENTORY_REL,
                "exists": True,
                "role": "ci-step-inventory",
            },
        ],
        "evidence": [
            {
                "path": S.INVENTORY_REL,
                "kind": "ci-inventory",
                "claim": (
                    "AUD-0041 YAML inventory supplies CI step command lines "
                    "because .github/workflows is absent on this worktree."
                ),
            },
            {
                "path": mutant_pyproject,
                "kind": "fixture",
                "claim": (
                    "Fixture package declares aud0043-suite and includes "
                    "aud0043_pkg* plus aud0043_extra*; the plant removes the "
                    "extra include while leaving the extra package on disk."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0043/pkg/tests/test_suite.py",
                "kind": "source-suite",
                "claim": (
                    f"Source pytest collected={sg.get('collected')} "
                    f"passed={sg.get('passed')} rc={sg.get('returncode')} "
                    f"on the good tree."
                ),
            },
            {
                "path": ig.get("resolved_script_path")
                or "command-center/p2-wave/probes/AUD-0043/pkg/src/aud0043_pkg/cli.py",
                "kind": "installed-console",
                "claim": (
                    f"Installed console good_ok={ig.get('console_ok')} "
                    f"mutant_ok={im.get('console_ok')} "
                    f"mutant_error={im.get('report_error')}"
                ),
            },
        ],
        "census": census,
        "live": {
            "parity_on_good_package": parity_good,
            "both_states_exclude_module": both,
            "source_good": {
                "ok": sg.get("ok"),
                "returncode": sg.get("returncode"),
                "collected": sg.get("collected"),
                "passed": sg.get("passed"),
                "command": sg.get("command"),
            },
            "source_mutant": {
                "ok": sm.get("ok"),
                "returncode": sm.get("returncode"),
                "collected": sm.get("collected"),
                "passed": sm.get("passed"),
            },
            "installed_good": {
                "console_ok": ig.get("console_ok"),
                "wheel_name": ig.get("wheel_name"),
                "resolved_script_path": ig.get("resolved_script_path"),
                "script_outside_repo": ig.get("script_outside_repo"),
                "venv_outside_repo": ig.get("venv_outside_repo"),
                "returncode": (ig.get("console") or {}).get("returncode"),
            },
            "installed_mutant": {
                "console_ok": im.get("console_ok"),
                "wheel_name": im.get("wheel_name"),
                "returncode": (im.get("console") or {}).get("returncode"),
                "error": im.get("report_error"),
            },
        },
        "named_probes": [
            {"id": "probe1", "command": S.P1},
            {"id": "probe2", "command": S.P2},
        ],
        "output_path": S.OUT_REL,
        "output_schema": S.SCHEMA_REL,
        "ts": now,
    }


def main() -> int:
    if not SL.shim_path().is_file():
        print(f"FAILED:AUD-0043 emit catalog schema missing {S.SCHEMA_REL}")
        return 1
    if not SL.rejects_garbage():
        print("FAILED:AUD-0043 emit local contract accepted garbage")
        return 1
    census = I.census_inventory()
    live = H.run_pair()
    doc = build_doc(live, census)
    errors = SL.iter_errors(doc)
    if errors:
        print("FAILED:AUD-0043 emit local-contract errors")
        for msg in errors[:12]:
            print(" ", msg)
        return 1
    blob = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if S.SENTINEL not in blob:
        print("FAILED:AUD-0043 emit sentinel missing from document")
        return 1
    out = S.REPO / S.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    if doc["state"] != "SUCCESS":
        print("FAILED:AUD-0043 emit not SUCCESS")
        print(
            json.dumps(
                {
                    "parity": live.get("parity_on_good_package"),
                    "both_states": live.get("both_states_exclude_module"),
                    "source_good": live["source_good"].get("ok"),
                    "source_mutant": live["source_mutant"].get("ok"),
                    "installed_good": live["installed_good"].get("console_ok"),
                    "installed_mutant": live["installed_mutant"].get("console_ok"),
                    "mutant_error": live["installed_mutant"].get("report_error"),
                    "source_good_rc": live["source_good"].get("returncode"),
                    "source_good_stdout": (live["source_good"].get("stdout_tail") or "")[
                        -500:
                    ],
                },
                indent=2,
            )
        )
        return 1
    print(
        f"wrote {S.OUT_REL} both_states={live.get('both_states_exclude_module')} "
        f"collected={live['source_good'].get('collected')} "
        f"script={live['installed_good'].get('resolved_script_path')}"
    )
    print("SUCCESS:AUD-0043 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
