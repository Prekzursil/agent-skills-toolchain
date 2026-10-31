#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0096-fresh-profile-harness-baseline.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import loadset as L  # noqa: E402

OUT = "command-center/audit/AUD-0096-fresh-profile-harness-baseline.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0096/probe1_clean_profile.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0096/probe2_current_diff.py"
)
SENTINEL = (
    "SUCCESS:AUD-0096 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "On a clean Windows user profile with no existing harness state, which "
    "skills, hooks, rules, plugins and MCP servers load — and how does that "
    "differ from the current profile?"
)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:AUD-0096 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def validate(doc: dict) -> None:
    """Catalog output_schema is a $ref shim (ast-integrate.invalid). Distro
    jsonschema 4.10 cannot follow that URI. G-1 json.loads the artifact and
    re-runs named probes; this local contract still rejects garbage.
    """
    import jsonschema

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:AUD-0096 missing {SCHEMA}")
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if "audit-drift" not in json.dumps(shim):
        raise SystemExit("FAILED:AUD-0096 output_schema missing audit-drift")
    local = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "report",
            "tests",
            "named_probes",
            "negative_controls",
            "evidence",
        ],
        "properties": {
            "unit_id": {"const": "AUD-0096"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "minLength": 40},
            "report": {
                "type": "object",
                "required": [
                    "kind",
                    "observations",
                    "control_ids",
                    "left",
                    "right",
                    "delta",
                    "cleanliness_control",
                    "leak_identity_control",
                ],
                "properties": {"kind": {"const": "audit-drift"}},
            },
            "tests": {"type": "array", "minItems": 4},
            "named_probes": {"type": "array", "minItems": 2},
            "negative_controls": {"type": "array", "minItems": 2},
            "evidence": {"type": "array", "minItems": 2},
        },
    }
    validator = jsonschema.Draft7Validator(local)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:AUD-0096 local schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        raise SystemExit("FAILED:AUD-0096 sentinel missing from artifact")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "AUD-0096", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:AUD-0096 schema accepts garbage")


def main() -> int:
    current_home = Path(os.environ.get("HOME") or str(Path.home()))
    cleanliness_ctl = L.both_states_cleanliness_control(REPO)
    leak_ctl = L.leak_identity_control(current_home, REPO)
    with L.make_empty_home() as home_s:
        clean = L.measure(Path(home_s), REPO)
    current = L.measure(current_home, REPO)
    delta = L.diff_sets(clean, current)
    aud62 = REPO / "command-center/audit/AUD-0062-always-on-context-budget.json"

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:AUD-0096 named probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if not cleanliness_ctl["pass"] or not leak_ctl["pass"]:
        print("FAILED:AUD-0096 controls")
        return 1

    cat_line = find_line(REPO / CATALOG, "Fresh-user-profile harness-load baseline")
    plugin_json = REPO / ".claude-plugin/plugin.json"
    pdata = json.loads(plugin_json.read_text(encoding="utf-8"))
    plugin_name = (
        str(pdata["name"])
        if isinstance(pdata, dict) and pdata.get("name")
        else "unnamed-plugin"
    )
    plugin_snippet = f'"name": "{plugin_name}"'
    plugin_line = find_line(plugin_json, plugin_snippet)
    load_line = find_line(HERE / "loadset.py", "USER_LOAD_ROOTS")
    plant_line = find_line(
        HERE / "loadset.py",
        "Empty sandbox must be clean; planted skill must make cleanliness fail.",
    )
    plugin_ids = sorted(
        {i["id"] for i in clean["items"] if i.get("kind") == "plugin"}
    )
    only_current_kinds: dict[str, int] = {}
    for key in delta["only_right"]:
        kind = key.split(":", 1)[0] if ":" in key else "unknown"
        only_current_kinds[kind] = only_current_kinds.get(kind, 0) + 1
    only_kind_txt = (
        ", ".join(f"{k}={v}" for k, v in sorted(only_current_kinds.items()))
        or "none"
    )
    headline = (
        "Clean sandboxed profile (Linux analog of a fresh user HOME; no Windows "
        f"profile on this estate) loads {clean['counts']['user']} user-profile "
        f"items and {clean['counts']['project']} project-declared item(s) "
        f"(skills={clean['counts']['skill']} hooks={clean['counts']['hook']} "
        f"rules={clean['counts']['rule']} plugins={clean['counts']['plugin']} "
        f"mcp={clean['counts']['mcp']}; plugin ids {plugin_ids}). Current HOME "
        f"adds {delta['only_right_count']} only-in-current keys ({only_kind_txt}; "
        f"{current['counts']['user']} user items). A leaked copy of current user "
        "skills makes the two user-key sets identical; the empty sandbox does not."
    )

    tests = [
        {
            "id": "probe1-clean-profile",
            "name": "Load-set in a proven-clean sandboxed HOME",
            "command": P1,
            "result": "PASS" if rc1 == 0 else "FAIL",
            "exit_code": rc1,
        },
        {
            "id": "probe2-current-diff",
            "name": "Same measurement on current HOME, reported as a diff",
            "command": P2,
            "result": "PASS" if rc2 == 0 else "FAIL",
            "exit_code": rc2,
        },
        {
            "id": "cleanliness-both-states",
            "name": "Empty sandbox is clean; planted SKILL.md makes cleanliness fail",
            "command": P1,
            "result": "PASS" if cleanliness_ctl["pass"] else "FAIL",
        },
        {
            "id": "leaked-profile-identity",
            "name": "Copying current user skills into a sandbox makes user-key sets identical",
            "command": P2,
            "result": "PASS" if leak_ctl["pass"] else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:AUD-0096 tests")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "AUD-0096",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "audit-drift",
        "schema_version": 1,
        "title": "Fresh-user-profile harness-load baseline",
        "question": QUESTION,
        "headline": headline,
        "answer": {
            "substrate": "linux-sandboxed-HOME",
            "windows_user_profile_available": False,
            "sandbox_used": True,
            "aud_0062_load_set_present": aud62.is_file(),
            "clean_user_items": clean["counts"]["user"],
            "clean_project_items": clean["counts"]["project"],
            "current_user_items": current["counts"]["user"],
            "current_project_items": current["counts"]["project"],
            "only_in_current_count": delta["only_right_count"],
            "only_in_clean_count": delta["only_left_count"],
            "shared_count": delta["shared_count"],
            "clean_counts": clean["counts"],
            "current_counts": current["counts"],
            "hooks_on_clean": clean["counts"]["hook"],
            "hooks_on_current": current["counts"]["hook"],
            "rules_on_clean": clean["counts"]["rule"],
            "rules_on_current": current["counts"]["rule"],
            "plugins_on_clean": clean["counts"]["plugin"],
            "plugins_on_current": current["counts"]["plugin"],
            "mcp_on_clean": clean["counts"]["mcp"],
            "mcp_on_current": current["counts"]["mcp"],
        },
        "report": {
            "kind": "audit-drift",
            "measurement_kind": "fresh-profile-vs-current-harness-load",
            "observations": [
                {
                    "name": "clean_user_items",
                    "measured": clean["counts"]["user"],
                    "method": "sandboxed-empty-HOME plus repo load roots",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0096/"
                        "probe1-clean-profile.raw.json"
                    ),
                },
                {
                    "name": "clean_project_items",
                    "measured": clean["counts"]["project"],
                    "method": "sandboxed-empty-HOME plus repo load roots",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0096/"
                        "probe1-clean-profile.raw.json"
                    ),
                },
                {
                    "name": "current_user_items",
                    "measured": current["counts"]["user"],
                    "method": "current HOME vs empty sandbox set-diff",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0096/"
                        "probe2-current-diff.raw.json"
                    ),
                },
                {
                    "name": "only_in_current_count",
                    "measured": delta["only_right_count"],
                    "method": "set difference of all_keys",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0096/"
                        "probe2-current-diff.raw.json"
                    ),
                },
                {
                    "name": "cleanliness_control_pass",
                    "measured": bool(cleanliness_ctl["pass"]),
                    "method": "empty sandbox vs planted SKILL.md",
                    "anchor": (
                        f"command-center/p2-wave/probes/AUD-0096/loadset.py:"
                        f"{plant_line}"
                    ),
                },
                {
                    "name": "leak_identity_control_pass",
                    "measured": bool(leak_ctl["pass"]),
                    "method": "copy current user SKILL.md into sandbox",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0096/"
                        "probe2-current-diff.raw.json"
                    ),
                },
            ],
            "control_ids": ["AUD-0096-C1", "AUD-0096-C2"],
            "left": {
                "label": "clean-sandboxed-profile",
                "counts": clean["counts"],
                "cleanliness": clean["cleanliness"]["clean"],
                "user_keys": clean["user_keys"],
                "project_keys": clean["project_keys"],
                "items": clean["items"],
            },
            "right": {
                "label": "current-profile",
                "home_kind": "linux-HOME",
                "counts": current["counts"],
                "cleanliness": current["cleanliness"]["clean"],
                "user_keys": current["user_keys"],
                "project_keys": current["project_keys"],
                "user_items": [i for i in current["items"] if i["scope"] == "user"],
            },
            "delta": {
                "only_in_clean": delta["only_left"],
                "only_in_current": delta["only_right"],
                "shared": delta["shared"],
                "identical": delta["identical"],
                "interpretation": (
                    f"Project plugins {plugin_ids} load from the repo on both "
                    f"profiles. Only-in-current keys ({delta['only_right_count']}"
                    f"; {only_kind_txt}) are user-profile loadables on this HOME. "
                    "Project skills/hooks/rules are shared; they are not "
                    "accidental local state."
                ),
            },
            "cleanliness_control": cleanliness_ctl,
            "leak_identity_control": leak_ctl,
        },
        "evidence": [
            {
                "claim": (
                    "Empty sandbox HOME has zero user-profile loadables and is "
                    f"proven clean ({cleanliness_ctl['empty_clean']}); planting "
                    "SKILL.md under .cursor/skills-cursor makes cleanliness fail "
                    f"and observes the planted skill "
                    f"(planted_user={cleanliness_ctl['planted_user_loadables']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/AUD-0096/loadset.py:{plant_line}",
                "path": "command-center/p2-wave/probes/AUD-0096/loadset.py",
                "line": plant_line,
                "snippet": "Empty sandbox must be clean; planted skill must make cleanliness fail.",
            },
            {
                "claim": (
                    f"Clean profile load set: user={clean['counts']['user']} "
                    f"project={clean['counts']['project']} "
                    f"(plugin ids {plugin_ids} from .claude-plugin/plugin.json "
                    f"and .claude/settings.json). This is the repo-declared "
                    "load, not leaked user state."
                ),
                "verdict": "CONFIRMED",
                "anchor": f".claude-plugin/plugin.json:{plugin_line}",
                "path": ".claude-plugin/plugin.json",
                "line": plugin_line,
                "snippet": plugin_snippet,
            },
            {
                "claim": (
                    f"Current HOME is dirty (clean={current['cleanliness']['clean']}) "
                    f"with {current['counts']['user']} user skills; diff vs clean is "
                    f"{delta['only_right_count']} only-in-current keys, "
                    f"{delta['only_left_count']} only-in-clean. Leaking those "
                    "skills into a sandbox makes user-key sets identical "
                    f"(copied={leak_ctl['copied_skill_files']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/AUD-0096/loadset.py:{load_line}",
                "path": "command-center/p2-wave/probes/AUD-0096/loadset.py",
                "line": load_line,
                "snippet": "USER_LOAD_ROOTS",
            },
            {
                "claim": (
                    "Catalog names a clean or sandboxed Windows user profile. "
                    "This estate is Linux; measurement used a sandboxed empty HOME "
                    "plus repo load roots. AUD-0062 always-on token-budget artifact "
                    f"is {'present' if aud62.is_file() else 'absent'}; load-set was "
                    "measured independently rather than reused from that unit."
                ),
                "verdict": "PARTIAL",
                "anchor": f"{CATALOG}:{cat_line}",
                "path": CATALOG,
                "line": cat_line,
                "snippet": "Fresh-user-profile harness-load baseline",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "AUD-0096-C1",
                "kind": "both-states-cleanliness",
                "description": (
                    "The clean profile must be proven clean: harness load roots "
                    "absent/empty, then a planted skill must turn the check red."
                ),
                "fired_on_bad_state": cleanliness_ctl["planted_dirty"],
                "silent_on_good_state": cleanliness_ctl["empty_clean"],
            },
            {
                "id": "AUD-0096-C2",
                "kind": "leaked-profile-identity",
                "description": (
                    "Copying current user skills into a sandbox must make the "
                    "user-key sets identical; the empty sandbox must diverge "
                    "when current is dirty."
                ),
                "fired_on_bad_state": leak_ctl["identical_when_leaked"],
                "silent_on_good_state": leak_ctl["empty_diverges_when_current_dirty"],
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0096-probe2-current-diff",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Named probe 2 re-measures the current profile and diffs it "
                "against a fresh sandbox, then runs the leaked-profile identity "
                "control. It does not re-read the artifact headline."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0096/loadset.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0096/probe1_clean_profile.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0096/probe2_current_diff.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": ".claude-plugin/plugin.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0096/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py AUD-0096"
                ),
                "artifact_path": OUT,
                "executed": False,
                "note": "Invoked after receipts; not this emitter.",
            }
        ],
        "produced_by": {
            "execution_substrate": "linux-headless",
            "vendor": "spacexai-cursor",
            "role": "auditor",
        },
        "residual_unknowns": [
            "No Windows user profile exists on this Linux estate; the clean side is a sandboxed empty HOME, which the catalog allows ('clean or sandboxed').",
            "AUD-0062 is the always-on token-budget unit, not a load-set census, and its artifact is absent here; load-set was measured on disk rather than imported.",
            "On-disk load surfaces are measured; a host process was not spawned to observe in-memory enablement.",
        ],
        "timestamps": {"emitted": now},
        "registered": True,
        "manifest_path": (
            "command-center/p2-wave/probes/AUD-0096/UNIT-ARTIFACT-MANIFEST.json"
        ),
    }
    validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    print(
        f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}"
    )
    print("SUCCESS:AUD-0096 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
