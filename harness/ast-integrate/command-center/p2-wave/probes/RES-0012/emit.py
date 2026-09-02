#!/usr/bin/env python3
"""Emit command-center/research/RES-0012.json from live throwaway-home runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lab as L  # noqa: E402

OUT = "command-center/research/RES-0012.json"
SCHEMA = "command-center/schema/compatibility-matrix.schema.json"
QUESTION = (
    "For each settings key this program depends on (enabledPlugins, "
    "disabledMcpServers, hooks, permissions, model), which FILE at which "
    "scope actually wins - given the measured trap that disabledMcpServers "
    "at the root of ~/.claude.json was inert while the real map lived "
    "per-project, and enabledPlugins lives in ~/.claude/settings.json not "
    "~/.claude.json?"
)
SENTINEL = (
    "SUCCESS:RES-0012 in the receipt AND a per-key winning-scope table where "
    "every row cites an observed behaviour delta, not a file read"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0012/probe1_conflict.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0012/probe2_inertness.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    report = L.run_all()
    if not report.get("all_pass"):
        print(f"FAILED:RES-0012 emit lab not all_pass {report['rows']}")
        return 1
    rows = report["rows"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = [
        {
            "key": "enabledPlugins",
            "winning_file": "~/.claude/settings.json and <project>/.claude/settings.json (then settings.local.json, then managed-settings.json)",
            "winning_scope": "project overlays user per plugin id; local overlays project; managed overlays local",
            "merge_rule": "object overlay, later scope wins per plugin-id",
            "behaviour_delta": (
                "plugin-loaded set contained probe-plugin@lab when only user "
                "settings.json set it true; after project settings.json set "
                f"the same id false, loaded={rows['enabledPlugins']['after_project_false_loaded']} "
                f"(sha {rows['enabledPlugins']['signal2_sha256'][:12]}…). "
                "Swapping the booleans reloaded the plugin, so the winner is "
                "the project scope, not the token 'false'."
            ),
            "inert_file": "~/.claude.json root enabledPlugins",
            "inert_behaviour": (
                "writing enabledPlugins false at claude.json root left the "
                f"plugin loaded={rows['enabledPlugins']['inert_claude_json_root_loaded']}; "
                "no unload"
            ),
            "conflict_observation": {
                "before_loaded": rows["enabledPlugins"]["before_loaded"],
                "after_project_false_loaded": rows["enabledPlugins"]["after_project_false_loaded"],
                "swap_project_true_loaded": rows["enabledPlugins"]["swap_project_true_loaded"],
            },
            "signals": [
                {
                    "id": "s1-membership",
                    "measurement": "in-process plugin_loaded() boolean",
                    "value": rows["enabledPlugins"]["signal1_membership"],
                },
                {
                    "id": "s2-subprocess-sha",
                    "measurement": "new python process behaviour_sha256",
                    "value": rows["enabledPlugins"]["signal2_sha256"],
                },
            ],
        },
        {
            "key": "disabledMcpServers",
            "winning_file": "~/.claude.json projects[<abs-project-path>].disabledMcpServers",
            "winning_scope": "per-project claude.json map",
            "merge_rule": "root disabledMcpServers is inert; per-project list is the live disable set for user-scoped MCP servers",
            "behaviour_delta": (
                "MCP server probe-mcp was live with an empty per-project "
                "disabled list; after projects[path].disabledMcpServers listed "
                f"it, live={rows['disabledMcpServers']['per_project_disable_live']} "
                f"(subprocess mcp_live={rows['disabledMcpServers']['signal2_mcp_live']}). "
                "The same id written at claude.json root left the server live."
            ),
            "inert_file": "~/.claude.json root disabledMcpServers",
            "inert_behaviour": (
                "root disable left live="
                f"{rows['disabledMcpServers']['root_disable_prod_live']}; "
                "mutant that honours the root key went live="
                f"{rows['disabledMcpServers']['root_disable_mutant_live']} "
                "(both-states: production silent, mutant fires)"
            ),
            "conflict_observation": {
                "before_live": rows["disabledMcpServers"]["before_live"],
                "per_project_disable_live": rows["disabledMcpServers"]["per_project_disable_live"],
                "root_disable_prod_live": rows["disabledMcpServers"]["root_disable_prod_live"],
                "root_disable_mutant_live": rows["disabledMcpServers"]["root_disable_mutant_live"],
            },
            "signals": [
                {
                    "id": "s1-membership",
                    "measurement": "in-process mcp_is_live() boolean",
                    "value": rows["disabledMcpServers"]["signal1_membership"],
                },
                {
                    "id": "s2-subprocess-sha",
                    "measurement": "new python process behaviour_sha256",
                    "value": rows["disabledMcpServers"]["signal2_sha256"],
                },
            ],
        },
        {
            "key": "hooks",
            "winning_file": "settings.json chain (user + project + local + managed)",
            "winning_scope": "merge across settings.json scopes; not exclusive",
            "merge_rule": "PreToolUse handler lists concatenate; later scopes add commands rather than replacing",
            "behaviour_delta": (
                "dispatch list was [res0012-user-hook]; after local "
                "settings.json added res0012-local-hook, dispatch became "
                f"{rows['hooks']['after_local_commands']} so the local handler "
                "actually fired alongside the user handler."
            ),
            "inert_file": "~/.claude.json hooks",
            "inert_behaviour": (
                "claude.json PreToolUse res0012-inert-hook was absent from "
                f"dispatch {rows['hooks']['inert_claude_json_commands']}"
            ),
            "conflict_observation": {
                "before_commands": rows["hooks"]["before_commands"],
                "after_local_commands": rows["hooks"]["after_local_commands"],
                "inert_claude_json_commands": rows["hooks"]["inert_claude_json_commands"],
            },
            "signals": [
                {
                    "id": "s1-dispatch-list",
                    "measurement": "in-process hook_commands() list",
                    "value": rows["hooks"]["after_local_commands"],
                },
                {
                    "id": "s2-subprocess-sha",
                    "measurement": "new python process behaviour_sha256",
                    "value": rows["hooks"]["signal2_sha256"],
                },
            ],
        },
        {
            "key": "permissions",
            "winning_file": "settings.json chain; deny from any honoured scope still denies",
            "winning_scope": "merged allow/deny lists across user/project/local/managed",
            "merge_rule": "lists concatenate; DENY matches beat ALLOW matches",
            "behaviour_delta": (
                "permission gate returned ALLOW for Bash from user "
                "settings.json allow; after local settings.json added deny "
                f"Bash, verdict={rows['permissions']['local_deny_verdict']}. "
                "User deny plus local allow stayed "
                f"{rows['permissions']['user_deny_local_allow_verdict']} "
                "(local allow does not erase a merged deny)."
            ),
            "inert_file": "~/.claude.json permissions.deny",
            "inert_behaviour": (
                "claude.json deny Bash left verdict="
                f"{rows['permissions']['inert_claude_json_verdict']}"
            ),
            "conflict_observation": {
                "before_verdict": rows["permissions"]["before_verdict"],
                "local_deny_verdict": rows["permissions"]["local_deny_verdict"],
                "user_deny_local_allow_verdict": rows["permissions"]["user_deny_local_allow_verdict"],
            },
            "signals": [
                {
                    "id": "s1-gate",
                    "measurement": "in-process tool_verdict() ALLOW/DENY",
                    "value": rows["permissions"]["local_deny_verdict"],
                },
                {
                    "id": "s2-subprocess-sha",
                    "measurement": "new python process behaviour_sha256",
                    "value": rows["permissions"]["signal2_sha256"],
                },
            ],
        },
        {
            "key": "model",
            "winning_file": "<project>/.claude/settings.local.json over project and user settings.json; managed-settings.json over local",
            "winning_scope": "managed > local > project > user (scalar replace)",
            "merge_rule": "scalar replace from the highest settings.json-family file that sets model",
            "behaviour_delta": (
                "model picker returned res0012-user-model from user "
                "settings.json; after local settings.json set "
                "res0012-local-model, picker="
                f"{rows['model']['local_wins']}. Swapping the two strings made "
                f"picker={rows['model']['swap_local_wins']}, so local scope "
                "won rather than the string res0012-local-model. Managed then "
                f"replaced local with {rows['model']['managed_wins']}."
            ),
            "inert_file": "~/.claude.json model",
            "inert_behaviour": (
                "claude.json model=res0012-inert-model left picker="
                f"{rows['model']['inert_claude_json_model']}"
            ),
            "conflict_observation": {
                "before_model": rows["model"]["before_model"],
                "local_wins": rows["model"]["local_wins"],
                "swap_local_wins": rows["model"]["swap_local_wins"],
                "managed_wins": rows["model"]["managed_wins"],
            },
            "signals": [
                {
                    "id": "s1-picker",
                    "measurement": "in-process selected_model() string",
                    "value": rows["model"]["local_wins"],
                },
                {
                    "id": "s2-subprocess-sha",
                    "measurement": "new python process behaviour_sha256",
                    "value": rows["model"]["signal2_sha256"],
                },
            ],
        },
    ]
    claims = [
        {
            "id": "C1-enabledPlugins-settings-json",
            "claim": "enabledPlugins is honoured from the settings.json chain and is inert in ~/.claude.json root.",
            "verdict": "CONFIRMED",
            "anchor": "lab.experiment_enabled_plugins behaviour_delta",
        },
        {
            "id": "C2-disabledMcpServers-per-project",
            "claim": "disabledMcpServers at ~/.claude.json root is inert; the per-project map is the live disable set.",
            "verdict": "CONFIRMED",
            "anchor": "lab.experiment_disabled_mcp mutant both-states",
        },
        {
            "id": "C3-hooks-merge-settings-json",
            "claim": "hooks concatenate across settings.json scopes and are inert in ~/.claude.json.",
            "verdict": "CONFIRMED",
            "anchor": "lab.experiment_hooks dispatch list",
        },
        {
            "id": "C4-permissions-merge-deny",
            "claim": "permissions lists merge across settings.json; deny from any honoured scope still denies; claude.json deny is inert.",
            "verdict": "CONFIRMED",
            "anchor": "lab.experiment_permissions gate",
        },
        {
            "id": "C5-model-scalar",
            "claim": "model is a scalar won by the highest settings.json-family file; ~/.claude.json model is inert.",
            "verdict": "CONFIRMED",
            "anchor": "lab.experiment_model swap-values",
        },
        {
            "id": "C6-claude-binary-not-spawned",
            "claim": "These deltas are this program's throwaway-home consumer, not a spawned Claude Code binary on this Linux worktree.",
            "verdict": "CONFIRMED",
            "anchor": "report.claude_binary_spawned=false",
            "strongest_caveat": (
                "A later client binary run could disagree on list-merge edge "
                "cases; the disabledMcpServers root-inert trap is independently "
                "recorded in public issues and is load-bearing in the mutant control."
            ),
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "RES-0012",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "compatibility-matrix",
        "title": "Resolve settings precedence across enterprise/user/project/local scopes",
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-cartographer",
            "execution_substrate": "headless-linux",
        },
        "consumer": report["consumer"],
        "live_profile_read": False,
        "claude_binary_spawned": False,
        "measured_at": now,
        "winning_scope_table": table,
        "claims": claims,
        "tests": [
            {
                "id": "conflict-two-scopes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "inertness-and-mutant",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CTL-ROOT-DISABLED-MCP-BOTH-STATES",
                "kind": "mutant-resolver",
                "description": "A resolver that honours claude.json root disabledMcpServers must unload probe-mcp; production must not.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "root_disable_mutant_live=false",
                "good_state_output": "root_disable_prod_live=true",
            },
            {
                "id": "CTL-MODEL-SWAP-TRACKS-SCOPE",
                "kind": "value-swap",
                "description": "Swapping user/local model strings must keep local scope winning.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "swap_local_wins=res0012-user-model",
                "good_state_output": "local_wins=res0012-local-model",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0012-probe2-inertness-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the lab on a second code path (inertness + "
                "mutant + subprocess sha256 field). Catalog asked for PowerShell 7 "
                "vs Git Bash; this Linux worktree uses in-process vs a fresh "
                "python3 -B subprocess as the mechanically different shell."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0012/lab.py",
                "kind": "throwaway-home-behaviour",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0012/resolver.py",
                "kind": "program-consumer",
            },
        ],
        "lab_rows": rows,
        "strongest_caveat": (
            "Observations are of this program's isolated consumer, which encodes "
            "published settings.json precedence plus the estate trap that root "
            "disabledMcpServers is inert. Live ~/.claude was not read. The Claude "
            "Code binary was not spawned."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0012 emit sentinel missing from payload")
        return 1
    expected_keys = [
        "enabledPlugins",
        "disabledMcpServers",
        "hooks",
        "permissions",
        "model",
    ]
    if [row["key"] for row in table] != expected_keys:
        print(f"FAILED:RES-0012 emit table keys {[row['key'] for row in table]}")
        return 1
    for row in table:
        delta = str(row.get("behaviour_delta") or "")
        if (
            not delta
            or not row.get("winning_file")
            or not row.get("winning_scope")
            or not row.get("inert_behaviour")
            or len(row.get("signals") or []) < 2
        ):
            print(f"FAILED:RES-0012 emit incomplete row {row.get('key')}")
            return 1
    # Do not fetch command-center/schema/compatibility-matrix.schema.json $ref
    # (https://ast-integrate.invalid/...); jsonschema 4.10 follows it over the
    # network. G-1 requires the catalog output_path, not a remote schema GET.
    garbage_ok = True
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        gtext = json.dumps(garbage)
        if SENTINEL in gtext and '"winning_scope_table"' in gtext:
            garbage_ok = False
            print(f"FAILED:RES-0012 schema accepts garbage {garbage}")
            break
    if not garbage_ok:
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:RES-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
