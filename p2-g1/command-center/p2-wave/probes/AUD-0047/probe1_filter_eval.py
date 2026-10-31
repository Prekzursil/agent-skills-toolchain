#!/usr/bin/env python3
"""Probe 1: evaluate each path filter against the gate's protected-file list.

Required control: a fixture workflow with paths-ignore excluding a protected
file must produce a miss. A gate that stays silent on that fixture is blind.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from eval_audit import scan  # noqa: E402
from path_filter import github_glob_match, would_run  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0047-probe1 {msg}")
    return 1


def main() -> int:
    errors: list[str] = []

    if not github_glob_match("*.js", "foo.js"):
        errors.append("*.js should match foo.js")
    if github_glob_match("*.js", "bar/foo.js"):
        errors.append("*.js must not match bar/foo.js (GitHub glob, not gitignore)")
    if not github_glob_match("**/*.js", "bar/foo.js"):
        errors.append("**/*.js should match bar/foo.js")
    if not github_glob_match("docs/**", "docs/a.md"):
        errors.append("docs/** should match docs/a.md")
    if github_glob_match("src/**", "protected/secret.py"):
        errors.append("src/** must not match protected/secret.py")
    if not github_glob_match("protected/secret.py", "protected/secret.py"):
        errors.append("literal path should match itself")
    if not github_glob_match(".gitattributes", ".gitattributes"):
        errors.append("literal dotfile path must match itself (shard4-w4 regression lock)")

    ignore_event = {
        "event": "push",
        "paths": [],
        "paths-ignore": ["docs/**", "protected/secret.py"],
        "has_path_filter": True,
    }
    if would_run(ignore_event, ["protected/secret.py"]):
        errors.append("paths-ignore of the only changed file must skip")
    if not would_run(ignore_event, ["src/app.py"]):
        errors.append("paths-ignore must still run when a non-ignored file changes")
    if not would_run(ignore_event, ["protected/secret.py", "src/app.py"]):
        errors.append("mixed commit must still run under paths-ignore")

    result = scan()
    live_dir = (REPO / ".github" / "workflows").is_dir()
    if bool(result["live_workflows_dir_exists"]) != live_dir:
        errors.append(
            "live_workflows_dir_exists disagrees with disk "
            f"(scan={result['live_workflows_dir_exists']} disk={live_dir})"
        )
    if live_dir:
        yml = list((REPO / ".github" / "workflows").glob("*.yml"))
        yaml_files = list((REPO / ".github" / "workflows").glob("*.yaml"))
        expected = len(yml) + len(yaml_files)
        if result["live_workflow_count"] != expected:
            errors.append(
                f"live_workflow_count={result['live_workflow_count']} "
                f"but {expected} yml/yaml files exist under .github/workflows"
            )
        if result["live_workflow_count"] == 0:
            errors.append(
                ".github/workflows exists but scan reported live_workflow_count=0"
            )
        for row in result.get("live_rows") or []:
            if row.get("has_path_filter") and not row.get("protected_files"):
                errors.append(
                    f"{row.get('id')} has a path filter but no declared protected set"
                )
    if not result["control_paths_ignore_miss_reported"]:
        errors.append(
            "control: evaluator did not report a miss for protected/secret.py "
            "deliberately listed in fixture-control-miss paths-ignore"
        )

    miss_ids = {
        (m["workflow_id"], m["protected_file"]) for m in result["misses"]
    }
    if ("fixture-control-miss", "src/app.py") in miss_ids:
        errors.append("src/app.py is not ignored; reporting it as a miss is a false positive")
    if ("fixture-control-hit", "protected/secret.py") in miss_ids:
        errors.append("control-hit listed protected/**; secret.py must not be a miss")
    if ("fixture-control-unfiltered", "src/app.py") in miss_ids:
        errors.append("unfiltered workflow must not produce a miss")
    if ("fixture-control-narrow", "protected/secret.py") not in miss_ids:
        errors.append("narrow paths: src/** must miss protected/secret.py")
    if ("fixture-control-narrow", "src/app.py") in miss_ids:
        errors.append("narrow paths must still see src/app.py")

    on_true = [
        r
        for r in result["fixture_rows"]
        if r.get("yaml_on_was_boolean_true") and r.get("workflow_exists")
    ]
    parsed_on = [
        r for r in result["fixture_rows"] if r.get("events") and r.get("workflow_exists")
    ]
    if not parsed_on:
        errors.append("failed to parse any fixture on: block (YAML True-key pitfall?)")
    # Bare `on:` is a YAML 1.1 boolean key. Surviving that (events still parsed)
    # is required; treating the boolean key as a parse failure would be wrong.
    if not on_true:
        errors.append("expected PyYAML to store bare on: as True on at least one fixture")
    lost = [r["id"] for r in on_true if not r.get("events")]
    if lost:
        errors.append(f"extract_on missed boolean-True on: key for {lost}")

    if errors:
        for item in errors:
            print(" ", item)
        return fail(f"{len(errors)} assertion(s)")

    payload = {
        "probe": "probe1-filter-eval",
        "unit_id": "AUD-0047",
        "pass": True,
        "control_paths_ignore_miss_reported": True,
        "fixture_miss_count": result["fixture_miss_count"],
        "live_workflow_count": result["live_workflow_count"],
        "live_workflows_dir_exists": result["live_workflows_dir_exists"],
        "live_miss_count": result["live_miss_count"],
        "live_with_path_filter": result["live_with_path_filter"],
        "misses": result["misses"],
        "aud41_workflow_count": result["aud41"].get("workflow_count"),
        "aud41_live_yaml_present_count": result["aud41"].get("live_yaml_present_count"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0047-probe1 path-filter evaluator reported the "
        "paths-ignore control miss"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
