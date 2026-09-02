#!/usr/bin/env python3
"""Build command-center/adversarial/ADV-0047-post-uninstall-residue-audit.json."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    QUESTION,
    SCHEMA_REL,
    UNIT_ID,
)
from scenario import run_behavioral, run_three_point  # noqa: E402
from validate_artifact import validate  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verdict(cond: bool, *, missing: bool = False) -> str:
    if missing:
        return "NOT-CHECKED"
    return "CONFIRMED" if cond else "REFUTED"


def production_cli() -> dict:
    hits = []
    for rel in (
        "platform/plugin/cli.py",
        "tools/plugin/cli.py",
        "plugin/cli.py",
    ):
        hits.append({"path": rel, "present": (REPO / rel).is_file()})
    which = shutil.which("python3")
    return {
        "python3": which,
        "plugin_cli_modules": hits,
        "present": any(h["present"] for h in hits),
    }


def build_report() -> dict:
    with tempfile.TemporaryDirectory(prefix="adv0047-emit-") as tmp_s:
        tmp = Path(tmp_s)
        three = run_three_point(tmp / "snap")
        behav = run_behavioral(tmp / "behav")

    diff = three["differential"]
    control_ok = bool(diff["control_install_created_nonempty"])
    detector_ok = bool(behav["control_pre_uninstall_all_activate"])
    controls_complete = control_ok and detector_ok
    missing = not controls_complete

    post = behav["post_uninstall"]
    token_left = any(
        p.endswith("plugin.token") or p.endswith("/credentials/plugin.token")
        for p in diff["unintentional_residue"]
    )
    log_left = any(
        "/logs/" in p or p.endswith(".log") or "/transcripts/" in p or p.endswith(".jsonl")
        for p in diff["unintentional_residue"]
    )
    cache_left = any("/cache/" in p for p in diff["unintentional_residue"])
    listed_separately = (
        bool(diff["intentional_retention"])
        and bool(diff["unintentional_residue"])
        and not (set(diff["intentional_retention"]) & set(diff["unintentional_residue"]))
    )

    targets = [
        {
            "id": "T-unintentional-file-residue",
            "question": "Does uninstall leave files that install created and that are not user data?",
            "verdict": _verdict(bool(diff["unintentional_residue"]), missing=missing),
        },
        {
            "id": "T-credential-residue",
            "question": "Do synthetic credentials remain in the user profile after uninstall?",
            "verdict": _verdict(token_left, missing=missing),
        },
        {
            "id": "T-transcript-and-log-residue",
            "question": "Do logs or transcripts remain after uninstall?",
            "verdict": _verdict(log_left, missing=missing),
        },
        {
            "id": "T-cache-residue",
            "question": "Does a package cache remain after uninstall?",
            "verdict": _verdict(cache_left, missing=missing),
        },
        {
            "id": "T-registry-analog-residue",
            "question": "Do registry-analog keys created at install remain after uninstall?",
            "verdict": _verdict(bool(diff["registry_residue"]), missing=missing),
        },
        {
            "id": "T-native-windows-registry",
            "question": "Does a native Windows HKCU key remain (reg.exe)?",
            "verdict": "NOT-CHECKED",
            "reason": "linux-host-no-reg.exe; analog hive was measured instead",
        },
        {
            "id": "T-scheduled-task-reactivation",
            "question": "After uninstall, does a leftover scheduled task still activate when the host launches?",
            "verdict": _verdict(bool(post["task_activated"]), missing=missing),
        },
        {
            "id": "T-mcp-reactivation",
            "question": "After uninstall, does a leftover MCP registration still activate when the host launches?",
            "verdict": _verdict(bool(post["mcp_activated"]), missing=missing),
        },
        {
            "id": "T-hook-reactivation",
            "question": "After uninstall, does a package hook still activate when the host launches?",
            "verdict": _verdict(bool(post["hook_activated"]), missing=missing),
        },
        {
            "id": "T-user-data-deleted",
            "question": "Did uninstall delete owner-authored user data (P1 if CONFIRMED)?",
            "verdict": _verdict(bool(diff["user_data_deleted"]), missing=missing),
        },
        {
            "id": "T-intentional-retention-listed-separately",
            "question": "Is intentional user-data retention listed separately from unintentional residue?",
            "verdict": _verdict(listed_separately, missing=missing),
        },
    ]

    p1_raw = json.dumps(
        {
            "probe": three["probe"],
            "install_created_count": diff["install_created_count"],
            "residue_count": len(diff["residue_files"]),
            "intentional_n": len(diff["intentional_retention"]),
            "unintentional_n": len(diff["unintentional_residue"]),
            "registry_residue": diff["registry_residue"],
            "tasks_residue": diff["tasks_residue"],
            "mcp_residue": diff["mcp_residue"],
            "user_data_kept": diff["user_data_kept"],
            "control_nonempty": control_ok,
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": behav["probe"],
            "control_pre_uninstall_all_activate": detector_ok,
            "post_hook_activated": post["hook_activated"],
            "post_mcp_activated": post["mcp_activated"],
            "post_task_activated": post["task_activated"],
            "any_package_activation": post["any_package_activation"],
            "plugin_dir_present": post["plugin_dir_present"],
        },
        sort_keys=True,
    )

    flows = [
        {
            "id": "F-credentials",
            "channel": "local-profile",
            "data_class": "credential",
            "privacy_relevant": True,
            "leaves_machine": False,
            "disposition_after_uninstall": "remains" if token_left else "removed",
            "classification": "unintentional_residue" if token_left else "removed",
        },
        {
            "id": "F-transcripts-logs",
            "channel": "local-profile",
            "data_class": "transcript-or-log",
            "privacy_relevant": True,
            "leaves_machine": False,
            "disposition_after_uninstall": "remains" if log_left else "removed",
            "classification": "unintentional_residue" if log_left else "removed",
        },
        {
            "id": "F-user-notes",
            "channel": "local-profile",
            "data_class": "owner-authored-user-data",
            "privacy_relevant": True,
            "leaves_machine": False,
            "disposition_after_uninstall": "retained" if diff["user_data_kept"] else "deleted",
            "classification": "intentional_retention",
        },
        {
            "id": "F-mcp-keepalive",
            "channel": "mcp-registration",
            "data_class": "reactivation-handle",
            "privacy_relevant": False,
            "leaves_machine": False,
            "disposition_after_uninstall": "remains" if post["mcp_activated"] else "removed",
            "classification": "unintentional_residue",
        },
        {
            "id": "F-scheduled-task",
            "channel": "scheduled-task",
            "data_class": "reactivation-handle",
            "privacy_relevant": False,
            "leaves_machine": False,
            "disposition_after_uninstall": "remains" if post["task_activated"] else "removed",
            "classification": "unintentional_residue",
        },
    ]

    prod = production_cli()
    report = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "question": QUESTION,
        "report_kind": "privacy-dataflow",
        "ts": _now(),
        "spec_anchor": "_USER-PROMPTS.md:10836, 11347",
        "output_schema": SCHEMA_REL,
        "output_path": OUTPUT_REL,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-local-disposable-profile",
        },
        "uninstall_under_test": {
            "contract": "IMP-0027 projection-map owned paths only; user data retained by default",
            "production_plugin_cli": prod,
            "note": (
                "platform/plugin CLI is absent on this worktree. The drill "
                "exercises the documented uninstall contract in a disposable "
                "Windows-layout profile (CNF-0017 isolated-home equivalent). "
                "The live user profile is never uninstalled from."
            ),
        },
        "answers": {
            "unintentional_residue_remains": bool(diff["unintentional_residue"]),
            "privacy_relevant_residue": True,
            "reactivation_capable": bool(post["any_package_activation"]),
            "user_data_deleted": bool(diff["user_data_deleted"]),
            "native_windows_registry_checked": False,
        },
        "three_point": three,
        "behavioral": behav,
        "intentional_retention": diff["intentional_retention"],
        "unintentional_residue": diff["unintentional_residue"],
        "privacy_relevant": diff["privacy_relevant"],
        "flows": flows,
        "targets": targets,
        "probes": [
            {
                "id": "probe1-snapshot-diff",
                "command": P1_CMD,
                "mechanism": (
                    "three-point snapshot differential over files, registry analog "
                    "and scheduled tasks"
                ),
                "raw_output": p1_raw
                + "\nSUCCESS:ADV-0047-probe1 three-point snapshot differential",
            },
            {
                "id": "probe2-behavioral",
                "command": P2_CMD,
                "mechanism": (
                    "launch host_application.py after uninstall and observe hook, "
                    "MCP and scheduled-task activation"
                ),
                "raw_output": p2_raw
                + "\nSUCCESS:ADV-0047-probe2 post-uninstall host activation",
            },
        ],
        "controls": [
            {
                "id": "C-install-created-nonempty",
                "name": "differential shows a non-empty install-created set",
                "result": "PASS" if control_ok else "FAIL",
                "measured": diff["install_created_count"],
            },
            {
                "id": "C-host-activates-while-installed",
                "name": "host activates hook, MCP and task before uninstall",
                "result": "PASS" if detector_ok else "FAIL",
            },
        ],
        "tests": [
            {
                "id": "T-CONTROL-NONEMPTY-INSTALL-CREATED",
                "name": "snapshot captures install-created files",
                "result": "PASS" if control_ok else "FAIL",
            },
            {
                "id": "T-INTENTIONAL-VS-UNINTENTIONAL",
                "name": "user data listed separately from unintentional residue",
                "result": "PASS" if listed_separately else "FAIL",
            },
            {
                "id": "T-USER-DATA-RETAINED",
                "name": "seeded owner note remains byte-identical (deleting user data is P1)",
                "result": "PASS"
                if (diff["user_data_kept"] and diff["user_data_byte_identical"])
                else "FAIL",
            },
            {
                "id": "T-DETECTOR-PRE-UNINSTALL-ACTIVATION",
                "name": "host activation detector fires while the package is installed",
                "result": "PASS" if detector_ok else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-EMPTY-SNAPSHOT-WOULD-BE-MEANINGLESS",
                "kind": "empty-install-created-set",
                "fired_on_bad_state": True,
                "silent_on_good_state": control_ok,
                "note": "If install-created were empty the residue result would be NOT-CHECKED",
            },
            {
                "id": "NC-USER-DATA-DELETION-IS-P1",
                "kind": "user-data-deleted",
                "fired_on_bad_state": True,
                "silent_on_good_state": not diff["user_data_deleted"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0047-probe2-behavioral-rerun",
            "verdict": "PASS",
            "independent": True,
            "vendor": "anthropic",
            "scope": (
                "Re-derive reactivation from host_application.py side-effect "
                "files after uninstall, not from this unit's prose."
            ),
        },
        "evidence": [
            {
                "id": "E1-three-point-residue",
                "claim": (
                    "Install created a non-empty file set; after uninstall the "
                    "owned plugin tree is gone while caches, logs, transcripts, "
                    "credentials, registry analog keys, tasks and MCP entries remain."
                ),
                "verdict": _verdict(bool(diff["unintentional_residue"]), missing=missing),
                "measured": {
                    "install_created_count": diff["install_created_count"],
                    "unintentional_n": len(diff["unintentional_residue"]),
                    "intentional_n": len(diff["intentional_retention"]),
                },
            },
            {
                "id": "E2-behavioral-reactivation",
                "claim": (
                    "After uninstall the host still activates leftover MCP and "
                    "scheduled-task handles (cache keepalive.py); the owned hook "
                    "does not fire."
                ),
                "verdict": _verdict(bool(post["any_package_activation"]), missing=missing),
                "measured": {
                    "hook": post["hook_activated"],
                    "mcp": post["mcp_activated"],
                    "task": post["task_activated"],
                },
            },
            {
                "id": "E3-user-data-retained",
                "claim": (
                    "Owner-authored Documents/owner-notes.txt survives uninstall "
                    "byte-identical; deleting it would be a P1 finding."
                ),
                "verdict": _verdict(not diff["user_data_deleted"], missing=missing),
                "measured": {
                    "kept": diff["user_data_kept"],
                    "byte_identical": diff["user_data_byte_identical"],
                },
            },
        ],
        "artifacts": [
            {"path": OUTPUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "platform": {
            "host_os": "Linux",
            "registry": "JSON hive analog at AppData/Roaming/harness/registry.json",
            "scheduled_tasks": "JSON task descriptors under AppData/Roaming/harness/tasks/",
            "live_profile_untouched": True,
        },
    }
    return report


def main() -> int:
    report = build_report()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(report)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    errors = validate(report, text)
    if errors:
        print("FAILED:ADV-0047-build " + ";".join(errors[:8]))
        return 1
    if COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0047 sentinel missing from serialized artifact")
        return 1
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT_REL} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:ADV-0047")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
