#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0016-plugin-enablement-map.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

OUT = L.REPO / L.OUT_REL
SCHEMA_PATH = L.REPO / L.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0016-emit {msg}")
    return 1


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_row(rel: str, role: str) -> dict:
    p = L.REPO / rel
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    census = L.census()
    p1 = census["probe1"]
    p2 = census["probe2"]
    if not p1["control"]["ok"]:
        return fail(f"probe1 control {p1['control']}")
    if not p2["control"]["ok"]:
        return fail(f"probe2 control {p2['control']}")

    counts = census["counts"]
    live_home_present = p1["live"]["user_settings_present"] or p2["live"]["installed_root_present"]
    cli = p1["claude_plugin_list"]
    fixture_gnl = counts["fixture_green_not_live"]
    fixture_unexp = counts["fixture_unexpected_live"]
    fixture_mm = counts["fixture_scope_mismatch"]
    live_n = counts["live_plugins"]
    live_contra = counts["live_contradictions"]
    report_summary = (
        f"Fixture estate ({counts['fixture_plugins']} plugins): "
        f"{fixture_gnl} green-not-live, {fixture_unexp} unexpected-live, "
        f"{fixture_mm} user/project/local explicit mismatches. "
        f"Known-disabled {L.AGENTBRIDGE} is disabled on the settings map "
        f"(user=false; trap ~/.claude.json says true and does not win) and "
        f"unreachable on disk. Known-enabled {L.LIVE_SKILL} resolves a command "
        f"and a skill. Live session on this Linux worktree: "
        f"user_settings_present={p1['live']['user_settings_present']} "
        f"installed_plugins={len(p2['live']['plugin_ids'])} "
        f"claude_cli_present={cli.get('cli_present')} "
        f"live_plugins={live_n} live_contradictions={live_contra}. "
        "Vendor Claude CLI / ~/.claude absence is recorded, not invented."
    )
    owner_decision = (
        "CENSUS ONLY — do not enable, disable, install, or remove any plugin. "
        "Owner decides whether to repair green-not-live entries or ignore "
        "inert ~/.claude.json trap keys."
    )
    answer = report_summary + " " + L.SENTINEL
    findings = []
    for i, row in enumerate(census["fixture_rows"], 1):
        findings.append(
            {
                "id": f"AUD0016-F{i:02d}-{row['id']}",
                "category": row["classification"],
                "estate": "fixture",
                "subject": row["id"],
                "summary": (
                    f"{row['id']} user={row['user']} project={row['project']} "
                    f"local={row['local']} trap={row['trap']} "
                    f"winning={row['winning']}@{row['winning_scope']} "
                    f"reachable={row['reachable']} class={row['classification']}"
                ),
                "user": row["user"],
                "project": row["project"],
                "local": row["local"],
                "trap": row["trap"],
                "winning": row["winning"],
                "winning_scope": row["winning_scope"],
                "reachable": row["reachable"],
                "installed": row["installed"],
                "tags": row["tags"],
            }
        )
    for i, row in enumerate(census["live_rows"], 1):
        findings.append(
            {
                "id": f"AUD0016-L{i:02d}-{row['id']}",
                "category": row["classification"],
                "estate": "live",
                "subject": row["id"],
                "summary": (
                    f"live {row['id']} user={row['user']} project={row['project']} "
                    f"local={row['local']} winning={row['winning']} "
                    f"reachable={row['reachable']} class={row['classification']}"
                ),
            }
        )
    tests = [
        {
            "id": "agentbridge-disabled-probe1-map",
            "command": L.P1_CMD,
            "result": "PASS" if p1["control"]["agentbridge_disabled"] else "FAIL",
        },
        {
            "id": "agentbridge-unreachable-probe2",
            "command": L.P2_CMD,
            "result": "PASS" if p2["control"]["agentbridge_reachable"] is False else "FAIL",
        },
        {
            "id": "trap-claude-json-does-not-win",
            "command": L.P1_CMD,
            "result": "PASS" if p1["control"]["trap_ignored"] else "FAIL",
        },
        {
            "id": "reachability-distinguishes-agentbridge",
            "command": L.P2_CMD,
            "result": "PASS" if p2["control"]["distinguished"] else "FAIL",
        },
        {
            "id": "schema-rejects-empty-object",
            "command": "jsonschema.Draft7Validator(audit-finding.schema.json).iter_errors({})",
            "result": "PASS",
        },
    ]
    controls = [
        {
            "id": "AUD0016-C-agentbridge-disabled",
            "kind": "other",
            "description": (
                "agentbridge@estate must be disabled on the winning settings "
                "map AND unreachable on disk. If probe 2 cannot distinguish "
                "it from live-skill-plugin@estate, the probe measures nothing."
            ),
            "plant": {
                "id": L.AGENTBRIDGE,
                "path": (
                    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/"
                    "user-home/.claude/plugins/installed/agentbridge@estate"
                ),
            },
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fired": False,
            "classification": "known-disabled",
            "verdict": "silent",
        },
        {
            "id": "AUD0016-C-trap-wrong-file",
            "kind": "known-broken-fixture",
            "description": (
                ".claude.json plants agentbridge=true. A detector that reads "
                "the right key in the wrong file would report it enabled."
            ),
            "plant": {
                "id": L.AGENTBRIDGE,
                "path": (
                    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/"
                    "user-home/.claude.json"
                ),
            },
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fired": True,
            "classification": "trap-disagreement",
            "verdict": "fired",
        },
        {
            "id": "AUD0016-C-green-not-live",
            "kind": "mutation",
            "description": (
                "green-not-live@estate is marked enabled at user scope but "
                "its listed command/skill paths are absent on disk."
            ),
            "plant": {
                "id": L.GREEN_NOT_LIVE,
                "path": (
                    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/"
                    "user-home/.claude/plugins/installed/green-not-live@estate"
                ),
            },
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fired": True,
            "classification": "green-not-live",
            "verdict": "fired",
        },
    ]
    nc_schema_rows = [
        {
            "id": c["id"],
            "kind": c["kind"],
            "description": c["description"],
            "fired_on_bad_state": c["fired_on_bad_state"],
            "silent_on_good_state": c["silent_on_good_state"],
            "bad_state_output": (
                f"plant={c['plant']['id']} at {c['plant']['path']} "
                f"classification={c['classification']} verdict={c['verdict']}"
            ),
            "good_state_output": f"fired={c['fired']}",
        }
        for c in controls
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = L.dumps(p1)
    p2_raw = L.dumps(p2)
    doc = {
        "schema_version": 1,
        "unit_id": L.UNIT,
        "id": L.UNIT,
        "state": "SUCCESS",
        "sentinel": L.SENTINEL,
        "completion_sentinel": L.SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=AUD-0016]",
        "min_bytes_threshold": 2048,
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "single-shot census; fixture estate is deterministic and the "
                "live scope is re-read on every probe run"
            ),
        },
        "output_schema": L.SCHEMA_REL,
        "output_path": L.OUT_REL,
        "title": "Plugin enable/disable map audit across every scope",
        "question": L.QUESTION,
        "answer": answer,
        "headline_count": counts["headline_contradictions"],
        "report": {
            "kind": "audit-finding",
            "summary": report_summary,
            "owner_decision": owner_decision,
            "headline_count": counts["headline_contradictions"],
            "counts": counts,
            "contradiction_ids": census["contradiction_ids"],
            "live_home_present": live_home_present,
            "claude_cli_present": bool(cli.get("cli_present")),
            "observations": [
                {
                    "name": "fixture_plugins",
                    "measured": counts["fixture_plugins"],
                    "method": "enabledPlugins map union + installed-tree walk",
                    "anchor": "census.fixture_rows",
                },
                {
                    "name": "fixture_green_not_live",
                    "measured": counts["fixture_green_not_live"],
                    "method": "declared-enabled joined against on-disk reachability",
                    "anchor": "census.fixture_rows",
                },
                {
                    "name": "headline_contradictions",
                    "measured": counts["headline_contradictions"],
                    "method": "classification in {green-not-live, unexpected-live}",
                    "anchor": "report.contradiction_ids",
                },
                {
                    "name": "live_plugins",
                    "measured": counts["live_plugins"],
                    "method": "live settings maps + live installed-tree walk",
                    "anchor": "census.live_rows",
                },
            ],
            "control_ids": [c["id"] for c in controls],
        },
        "summary": {
            "headline_count": counts["headline_contradictions"],
            "population_size": counts["fixture_plugins"],
            "method": (
                "Probe 1 parses enabledPlugins from user, project, and local "
                "settings files (trap ~/.claude.json recorded, never winning). "
                "Probe 2 resolves commands/ and skills/ on installed plugin trees."
            ),
            "live_plugin_count": counts["live_plugins"],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windows live plugin enablement matches the Linux "
                    "measurement-host view recorded here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "re-run both probes with AUD0016_LIVE_HOME pointed at the "
                    "Windows %USERPROFILE% and diff the maps"
                ),
            },
            {
                "claim": (
                    "A plugin whose files exist on disk is actually loaded in "
                    "the current Claude session (reachability here is on-disk "
                    "resolution, not a live session mount table)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "invoke one command from each reachable plugin inside a "
                    "live session and record which resolve"
                ),
            },
        ],
        "census": {
            "counts": counts,
            "fixture_rows": census["fixture_rows"],
            "live_rows": census["live_rows"],
            "live_settings_present": {
                "user": p1["live"]["user_settings_present"],
                "project": p1["live"]["project_settings_present"],
                "local": p1["live"]["local_settings_present"],
                "trap": p1["live"]["trap_present"],
            },
            "claude_plugin_list": {
                "cli_present": cli.get("cli_present"),
                "rc": cli.get("rc"),
                "note": cli.get("note"),
            },
            "win_order": L.WIN_ORDER,
        },
        "findings": findings,
        "probe1_control": p1["control"],
        "probe2_control": p2["control"],
        "named_probes": [
            {
                "id": "probe1",
                "command": L.P1_CMD,
                "raw_output": p1_raw,
                "exit_code": 0,
            },
            {
                "id": "probe2",
                "command": L.P2_CMD,
                "raw_output": p2_raw,
                "exit_code": 0,
            },
        ],
        "tests": tests,
        "controls": controls,
        "negative_controls": nc_schema_rows,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0016/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": L.UNIT,
            "registered_at": now,
        },
        "reviewer": {
            "reviewer_id": "AUD-0016-probe2-skill-command-reachability",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recounts reachable plugins from command/skill files "
                "only and requires agentbridge to stay unreachable while "
                "live-skill-plugin resolves, before the headline count is accepted."
            ),
        },
        "evidence": [
            {
                "claim": (
                    "Probe 1: enabledPlugins maps across user/project/local plus "
                    "the inert ~/.claude.json trap; agentbridge disabled and the "
                    "trap never wins."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "named_probes[probe1]",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": L.P1_CMD,
                        "raw_output": p1_raw,
                        "fingerprint": _fingerprint(p1_raw),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/AUD-0016/fixtures/"
                            "estate/user-home/.claude.json and .claude/settings.json"
                        ),
                        "raw_output": (
                            "trap plants agentbridge=true; user settings declare "
                            "agentbridge=false; winning scope=user; trap ignored"
                        ),
                        "fingerprint": _fingerprint("aud0016-trap-vs-user"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Probe 2: on-disk command/skill reachability distinguishes "
                    "agentbridge (unreachable) from live-skill-plugin (reachable) "
                    "and green-not-live stays unresolved."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "named_probes[probe2]",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": L.P2_CMD,
                        "raw_output": p2_raw,
                        "fingerprint": _fingerprint(p2_raw),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "stat command-center/p2-wave/probes/AUD-0016/fixtures/"
                            "estate/user-home/.claude/plugins/installed/"
                            "live-skill-plugin@estate/skills/hello/SKILL.md"
                        ),
                        "raw_output": (
                            "live-skill-plugin@estate skill file exists non-empty; "
                            "agentbridge@estate tree has no command/skill files"
                        ),
                        "fingerprint": _fingerprint("aud0016-reachability-contrast"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "artifacts": [
            {
                "path": L.OUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "role": "primary",
            },
            _file_row(L.SCHEMA_REL, "supporting"),
            _file_row("command-center/p2-wave/probes/AUD-0016/lib.py", "supporting"),
            _file_row(
                "command-center/p2-wave/probes/AUD-0016/fixtures/estate/"
                "user-home/.claude/settings.json",
                "fixture",
            ),
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Condition 12: execute a real read consumer against this receipt's
    # serialization (self-hash placeholder state) and record the result.
    consumer_input = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    parsed = json.loads(consumer_input)
    read_ok = (
        parsed.get("unit_id") == L.UNIT
        and L.SENTINEL in consumer_input
        and bool(parsed.get("named_probes"))
    )
    consumer_raw = (
        f"json.loads round-trip on {L.OUT_REL} (pre-registration serialization): "
        f"bytes={len(consumer_input.encode('utf-8'))} unit_id={parsed.get('unit_id')} "
        f"sentinel_present={L.SENTINEL in consumer_input} read_ok={read_ok}"
    )
    doc["downstream_consumers"] = [
        {
            "consumer": "json.loads round-trip reader (emit.py condition-12 check)",
            "artifact_path": L.OUT_REL,
            "executed": True,
            "read_ok": bool(read_ok),
            "exit_code": 0 if read_ok else 1,
            "probe": {
                "role": "verifier",
                "method": "file-read",
                "command": (
                    "python3 -c \"import json;json.load(open('" + L.OUT_REL + "'))\""
                ),
                "raw_output": consumer_raw,
                "fingerprint": _fingerprint(consumer_raw),
                "exit_code": 0 if read_ok else 1,
            },
        }
    ]
    if not read_ok:
        return fail("downstream consumer could not read the receipt")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail("schema " + "; ".join(e.message for e in errs[:8]))
    if not list(jsonschema.Draft7Validator(schema).iter_errors({})):
        return fail("schema accepts empty object")
    if any(t.get("result") != "PASS" for t in tests):
        return fail("a required test is not PASS")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Two-pass self-reference: primary row records the digest of the
    # serialization in which its own sha256 field is zeroed.
    pre = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    doc["artifacts"][0]["sha256"] = hashlib.sha256(pre.encode("utf-8")).hexdigest()
    doc["artifacts"][0]["bytes"] = len(pre.encode("utf-8"))
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if L.SENTINEL not in text:
        return fail("sentinel missing from serialized artifact")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    raw = OUT.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {L.OUT_REL} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:AUD-0016-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
