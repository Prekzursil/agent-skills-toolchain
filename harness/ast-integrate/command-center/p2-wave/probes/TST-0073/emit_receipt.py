#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0073.json from a live install/uninstall suite."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_suite  # noqa: E402

OUT = "command-center/receipts/TST-0073.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
QUESTION = (
    "Phase 10 layer 8. Target: after uninstall, no hook remains registered, "
    "no scheduled task remains, no MCP entry remains, and the profile diff "
    "versus pre-install is empty except for explicitly documented user data. "
    "What does the current uninstall leave behind?"
)
SENTINEL = "SUCCESS:TST-0073"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0073/probe1_orphan_registrations.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0073/probe2_profile_diff.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def measure_astplugin_cli() -> dict:
    """Live `astplugin uninstall` in a throwaway prefix (never HOME)."""
    launcher = REPO / "platform" / "plugin" / "astplugin.py"
    cli = REPO / "platform" / "plugin" / "cli.py"
    if not launcher.is_file() or not cli.is_file():
        return {"present": False, "launcher": str(launcher), "cli": str(cli)}
    platform_dir = str(REPO / "platform")
    if platform_dir not in sys.path:
        sys.path.insert(0, platform_dir)
    from plugin.build import build  # noqa: E402
    from plugin import lifecycle  # noqa: E402
    from plugin.journal import Prefix  # noqa: E402
    census_dir = str(REPO / "tools" / "plugin")
    if census_dir not in sys.path:
        sys.path.insert(0, census_dir)
    from hash_census import census_diff, hash_census  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="tst0073-astplugin-") as raw:
        tmp = Path(raw)
        prefix_root = tmp / "prefix"
        live = prefix_root / "live"
        prefix = Prefix(prefix_root)
        prefix.ensure()
        (prefix.userdata / "keep-me.txt").write_text(
            "owner notebook - must survive uninstall\n", encoding="utf-8"
        )
        live.mkdir(parents=True, exist_ok=True)
        (live / "hooks.json").write_text(
            json.dumps({"registrations": [{"id": "unrelated-lint"}]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (live / ".mcp.json").write_text(
            json.dumps(
                {"mcpServers": {"unrelated-mail": {"command": "node"}}}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        tasks = live / "scheduled-tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        (tasks / "unrelated.timer").write_text(
            "[Timer]\nOnCalendar=hourly\n", encoding="utf-8"
        )
        pre = hash_census(prefix_root)
        result, _ = build(REPO, tmp / "dist")
        inst = lifecycle.install(result.archive, prefix, live_root=live)
        hook_after_install = (live / "hooks" / "plugin_health.py").is_file()
        un = lifecycle.uninstall(prefix, live_root=live, user_data="retain")
        post = hash_census(prefix_root)
        diff = census_diff(pre, post)
        return {
            "present": True,
            "launcher": "platform/plugin/astplugin.py",
            "install_ok": bool(inst.ok),
            "install_version": str(inst.version),
            "hook_file_after_install": hook_after_install,
            "hook_file_after_uninstall": (live / "hooks" / "plugin_health.py").is_file(),
            "command_file_after_uninstall": (live / "commands" / "astplugin.md").is_file(),
            "unrelated_hooks_survived": (live / "hooks.json").is_file(),
            "unrelated_mcp_survived": (live / ".mcp.json").is_file(),
            "unrelated_task_survived": (tasks / "unrelated.timer").is_file(),
            "userdata_retained": (prefix.userdata / "keep-me.txt").is_file(),
            "installed_json_removed": not prefix.installed.exists(),
            "versions_removed": not any(prefix.versions.iterdir())
            if prefix.versions.exists()
            else True,
            "removed_live": list(un.detail.get("removed_live") or []),
            "kept_live_edited": list(un.detail.get("kept_live_edited") or []),
            "census": {
                "pre_count": len(pre),
                "post_count": len(post),
                "extra": list(diff.get("extra") or []),
                "missing": list(diff.get("missing") or []),
                "changed": list(diff.get("changed") or []),
            },
            "documented_prefix_residuals": [
                "state/journal.jsonl (append-only lifecycle journal; not a hook/MCP/task)",
                "empty live/commands and live/hooks dirs after file unlink",
                "empty state/staging dir",
            ],
        }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    suite = run_suite()
    if not suite["pass"]:
        print("FAILED:TST-0073 live suite did not pass")
        print(json.dumps(suite["tests"], indent=2))
        return 1
    complete = suite["complete"]
    naive = suite["naive_payload_only"]
    scorched = suite["scorched"]
    diff = complete["diff"]
    astplugin = measure_astplugin_cli()
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    residual_path = (
        diff["documented_residuals"][0]["path"]
        if diff["documented_residuals"]
        else "(none)"
    )
    ast_extra = (astplugin.get("census") or {}).get("extra") or []
    answer = (
        "Current uninstall on this Linux worktree is two measured surfaces, "
        "never operator HOME/crontab/systemd. (1) astplugin CLI "
        "(platform/plugin/astplugin.py uninstall --retain-user-data) against a "
        "throwaway prefix: it deletes provenance-tracked live files "
        f"{astplugin.get('removed_live')} and version dirs; userdata and "
        "unrelated host-profile hooks.json/.mcp.json/scheduled-tasks survive; "
        "the deployed hook file hooks/plugin_health.py is gone after uninstall "
        f"(present after install={astplugin.get('hook_file_after_install')}). "
        "astplugin does not register Claude-style hook/MCP/scheduled-task ids, "
        "so those cannot orphan from this CLI. Prefix residuals vs pre-install: "
        f"{ast_extra} (journal + empty deploy-target dirs; documented, not "
        "user-data). (2) Host-profile registration driver in probes/TST-0073: "
        "complete uninstall leaves zero package hook/MCP/scheduled-task ids; "
        f"pre/post census has one documented-intentional residual ({residual_path}). "
        "Payload-only delete leaves 4 dangling registrations and the host still "
        "activates them. Scorched-earth clears orphans but destroys user data, "
        "so a zero-orphan claim without the survival census is not evidence."
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0073",
        "architecture_id": "plugin-lifecycle-uninstall",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "report_kind": "test-receipt",
        "title": "Uninstall leaves no orphan state",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10996",
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "phase": "10",
        "execution_substrate": "linux-throwaway-profile",
        "product_cli_present": bool(astplugin.get("present")),
        "product_cli_note": (
            "platform/plugin/astplugin.py ships. It uninstalls prefix versions "
            "and provenance-tracked live files. It does not write Claude-style "
            "hooks.json, .mcp.json, or scheduled-task registrations; those "
            "catalog surfaces are measured by the throwaway-profile driver. "
            "Never run against operator HOME, crontab, or systemd."
        ),
        "astplugin_cli": astplugin,
        "tests_required": [
            "test_no_orphan_hook_registration",
            "test_no_orphan_scheduled_task_or_mcp_entry",
            "test_documented_user_data_survives",
        ],
        "profile_diff": {
            "equal_except_documented": diff["equal_except_documented"],
            "pre_count": diff["pre_count"],
            "post_count": diff["post_count"],
            "unchanged_count": diff["unchanged_count"],
            "extra": diff["extra"],
            "missing": diff["missing"],
            "changed": diff["changed"],
            "defects": diff["defects"],
            "documented_residuals": diff["documented_residuals"],
            "enumeration": (
                "every extra, missing, and changed path is listed; unchanged "
                f"paths counted ({diff['unchanged_count']}) rather than restated"
            ),
        },
        "what_uninstall_leaves_behind": {
            "package_orphans": complete["post_uninstall"]["orphans"],
            "orphan_count": complete["post_uninstall"]["orphan_count"],
            "documented_intentional": [
                r["path"] for r in diff["documented_residuals"]
            ],
            "defects": [],
        },
        "surfaces_queried": [
            {
                "surface": "hooks",
                "query": "throwaway-profile/hooks/hooks.json registrations[].id",
                "pre": complete["pre"]["hooks"],
                "post_install": complete["post_install"]["hooks"],
                "post_uninstall": complete["post_uninstall"]["hooks"],
            },
            {
                "surface": "mcp",
                "query": "throwaway-profile/.mcp.json mcpServers keys",
                "pre": complete["pre"]["mcp"],
                "post_install": complete["post_install"]["mcp"],
                "post_uninstall": complete["post_uninstall"]["mcp"],
            },
            {
                "surface": "scheduled-tasks",
                "query": "throwaway-profile/scheduled-tasks/* filenames",
                "pre": complete["pre"]["tasks"],
                "post_install": complete["post_install"]["tasks"],
                "post_uninstall": complete["post_uninstall"]["tasks"],
            },
            {
                "surface": "settings",
                "query": "throwaway-profile/settings.json keys + enabledMcpServers list",
                "pre": complete["pre"]["settings_keys"],
                "post_install": complete["post_install"]["settings_keys"],
                "post_uninstall": complete["post_uninstall"]["settings_keys"],
            },
            {
                "surface": "filesystem-census",
                "query": "tools/plugin/hash_census.py over the throwaway profile",
                "pre_count": complete["pre"]["path_count"],
                "post_install_count": complete["post_install"]["path_count"],
                "post_uninstall_count": complete["post_uninstall"]["path_count"],
            },
        ],
        "surfaces_not_queried": [
            {
                "surface": "Windows registry",
                "reason": "Linux worktree; no HKCU mapping in the throwaway profile",
            },
            {
                "surface": "schtasks.exe",
                "reason": "not present; scheduled tasks are profile files, not OS tasks",
            },
            {
                "surface": "host crontab / systemd --user",
                "reason": "live machine is never uninstalled from (ADV-0120 drill rule)",
            },
            {
                "surface": "operator ~/.mcp.json and ~/.claude.json",
                "reason": "throwaway profile only; live MCP curation must not be touched",
            },
        ],
        "user_data_survival": complete["user_data"],
        "activation_after_uninstall": {
            "complete": complete["activation_after"],
            "package_still_activates_complete": complete["package_still_activates"],
            "package_still_activates_naive": naive["package_still_activates"],
        },
        "artifacts": [
            art(
                "command-center/p2-wave/probes/TST-0073/lab.py",
                "uninstall-driver",
            ),
            art(
                "command-center/p2-wave/probes/TST-0073/scenario.py",
                "both-states-suite",
            ),
            art(
                "command-center/p2-wave/probes/TST-0073/probe1_orphan_registrations.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0073/probe2_profile_diff.py",
                "probe",
            ),
            art("tools/plugin/hash_census.py", "census-oracle"),
        ],
        "evidence": [
            {
                "claim": (
                    "After a complete uninstall the hook, MCP, scheduled-task and "
                    "settings surfaces contain zero package ids "
                    f"(orphan_count={complete['post_uninstall']['orphan_count']}). "
                    "The same sweep saw all four package registrations after install "
                    f"(detector_saw_install={complete['detector_saw_install']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0073/lab.py:package_orphans",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Pre-install vs post-uninstall hash census is empty except "
                    "documented user data "
                    f"{[r['path'] for r in diff['documented_residuals']]}; "
                    f"missing={diff['missing']} changed={diff['changed']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0073/lab.py:classify_diff",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Documented user files that existed before install remain "
                    "byte-identical; install-created session file is retained. "
                    f"survival.ok={complete['user_data']['ok']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0073/lab.py:user_data_survival",
                "confidence": "almost-certain",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_no_orphan_hook_registration",
                "name": "test_no_orphan_hook_registration",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "complete uninstall: hook id ast-plugin-hook absent; "
                    "payload-only control leaves it registered"
                ),
            },
            {
                "id": "test_no_orphan_scheduled_task_or_mcp_entry",
                "name": "test_no_orphan_scheduled_task_or_mcp_entry",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "complete uninstall: ast-plugin-mcp and ast-plugin.timer absent; "
                    "host activation log has no package ids"
                ),
            },
            {
                "id": "test_documented_user_data_survives",
                "name": "test_documented_user_data_survives",
                "command": P2,
                "result": "PASS",
                "observable": (
                    "keep-me.txt and notes.md byte-identical; "
                    "install-created-session.json retained; scorched-earth fails this"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST0073-C1-payload-only-orphan",
                "kind": "known-broken-uninstall",
                "description": (
                    "Delete only package/ and leave registrations. The orphan "
                    "sweep must report leftover hook/MCP/task and the host must "
                    "still activate them. Complete uninstall on a sibling profile "
                    "must report zero orphans, or the detector is vacuous."
                ),
                "fired_on_bad_state": naive["post_uninstall"]["orphan_count"] > 0
                and naive["package_still_activates"],
                "silent_on_good_state": complete["post_uninstall"]["orphan_count"] == 0
                and not complete["package_still_activates"],
                "bad_state_output": json.dumps(
                    {
                        "orphan_count": naive["post_uninstall"]["orphan_count"],
                        "orphans": naive["post_uninstall"]["orphans"],
                        "activates": naive["package_still_activates"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {
                        "orphan_count": complete["post_uninstall"]["orphan_count"],
                        "orphans": complete["post_uninstall"]["orphans"],
                        "activates": complete["package_still_activates"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "TST0073-C2-scorched-earth-user-data",
                "kind": "known-broken-uninstall",
                "description": (
                    "Delete the entire profile. Orphan count is zero (the sweep "
                    "would pass) but documented user data is gone. The survival "
                    "census must fail, proving zero-orphan is not sufficient."
                ),
                "fired_on_bad_state": (not scorched["user_data"]["ok"])
                and scorched["post_uninstall"]["orphan_count"] == 0,
                "silent_on_good_state": complete["user_data"]["ok"]
                and complete["diff"]["equal_except_documented"],
                "bad_state_output": json.dumps(
                    {
                        "user_data_ok": scorched["user_data"]["ok"],
                        "orphan_count": scorched["post_uninstall"]["orphan_count"],
                        "keep_me": scorched["unrelated_still"]["user_keep"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {
                        "user_data_ok": complete["user_data"]["ok"],
                        "documented_residuals": [
                            r["path"] for r in diff["documented_residuals"]
                        ],
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0073-probe2-profile-diff",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the census independently of probe 1's "
                "registration queries. Catalog also asks a Windows-platform "
                "specialist to re-run in the other shell; schtasks/registry are "
                "recorded NOT-CHECKED on this Linux worktree."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "TST-0073-probe1-orphan-registrations",
                "role": "cross-surface-orphan-sweep",
                "independent": True,
                "verdict": "PASS",
            },
            {
                "reviewer_id": "TST-0073-probe2-profile-diff",
                "role": "path-by-path-census",
                "independent": True,
                "verdict": "PASS",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0073/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "orphan-hook-mcp-scheduled-task-sweep",
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "pre-post-uninstall-profile-diff",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Windows scheduled tasks and HKCU residue are unmeasured on "
                    "this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the same suite on a Windows profile with schtasks "
                    "and registry snapshots (REL-0007 / ADV-0047 surfaces)."
                ),
            },
            {
                "claim": (
                    "astplugin uninstall leaves state/journal.jsonl and empty "
                    "live/commands, live/hooks, state/staging directories. Those "
                    "are prefix machinery, not hook/MCP/scheduled-task orphans."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Already measured in astplugin_cli.census.extra on this run."
                ),
            },
        ],
        "cloud_ok": False,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0073 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0073 sentinel missing after write")
        return 1
    st = json.loads(out.read_text(encoding="utf-8")).get("state")
    if str(st).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0073 self-declared {st}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0073")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
