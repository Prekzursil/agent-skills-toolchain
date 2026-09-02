#!/usr/bin/env python3
"""Probe 1: AST + stdlib introduction-version map.

Required control: fixtures/newer_than_floor.py uses 3.12 type-params against a
declared requires-python of >=3.10 and MUST be flagged. fixtures/at_floor.py
must stay silent. A scan that passes the 3.12 file is not reading versions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0029-probe1 {msg}")
    return 1


def main() -> int:
    census = E.live_census()
    control = E.control_scan()
    errors: list[str] = []

    if census["python_file_count"] < 50:
        errors.append(f"python_file_count={census['python_file_count']} too small")
    if not control["python_control_pass"]:
        errors.append(
            "python control: newer_than_floor must be flagged and at_floor silent "
            f"newer={control['newer_python']} at={control['at_floor_python']}"
        )
    if not control["node_control_pass"]:
        errors.append(
            "node control: Promise.withResolvers must exceed engines>=16 and "
            f"node_at_floor must not; newer={control['newer_node']} at={control['at_floor_node']}"
        )
    if not E.known_tomllib_mapped(census):
        errors.append(
            "stdlib map missed import tomllib in command-center/p2-wave/_build_AUD0020.py"
        )
    if census["declarations"]["pyproject_toml_files"] != 0:
        # live_only census excludes our fixture; any leftover pyproject is news.
        pass
    if census["python_match_status"] == "MATCH" and not census["declarations"]["requires_python"]:
        errors.append("cannot MATCH against zero live requires-python declarations")
    if census["python_match_status"] not in {
        "NOT-DECLARED",
        "MISMATCH-ACTUAL-HIGHER",
        "MATCH",
        "NOT-CHECKED",
    }:
        errors.append(f"unexpected python_match_status={census['python_match_status']}")

    # A version-blind scanner that always returns success on the 3.12 control
    # is the catalog-required red state.
    if not control["newer_python"]["flagged"]:
        errors.append("control file with 3.12 type-params was not flagged vs declared 3.10")
    if control["at_floor_python"]["flagged"]:
        errors.append("at_floor.py was flagged as exceeding declared 3.10")

    payload = {
        "probe": "probe1-ast-map",
        "unit_id": "AUD-0029",
        "python_file_count": census["python_file_count"],
        "js_file_count": census["js_file_count"],
        "parse_error_count": census["parse_error_count"],
        "syntax_floor": census["syntax_floor"],
        "api_floor": census["api_floor"],
        "python_floor": census["python_floor"],
        "node_floor": census["node_floor"],
        "bucket_floors": census["bucket_floors"],
        "python_match_status": census["python_match_status"],
        "node_match_status": census["node_match_status"],
        "live_requires_python_count": len(census["declarations"]["requires_python"]),
        "live_engines_node_count": len(census["declarations"]["engines_node"]),
        "pyproject_toml_files": census["declarations"]["pyproject_toml_files"],
        "package_json_files": census["declarations"]["package_json_files"],
        "tomllib_hits": census["tomllib_hits"],
        "onexc_hits": census["onexc_hits"],
        "syntax_samples": census["syntax_samples"],
        "control": {
            "python_pass": control["python_control_pass"],
            "node_pass": control["node_control_pass"],
            "declared_python": control["declared_python"],
            "declared_node": control["declared_node"],
            "newer_python_floor": control["newer_python"]["combined_floor"],
            "newer_node_floor": control["newer_node"]["floor"],
        },
        "plugin_zip_exists": census["plugin_zip"]["exists"],
        "platform_fsops_exists": census["platform_fsops"]["exists"],
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        for item in errors:
            print(" ", item)
        return fail(f"{len(errors)} assertion(s)")
    print(
        "SUCCESS:AUD-0029-probe1 AST/stdlib map flagged 3.12 type-params vs "
        "declared 3.10 and stayed silent on at_floor.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
