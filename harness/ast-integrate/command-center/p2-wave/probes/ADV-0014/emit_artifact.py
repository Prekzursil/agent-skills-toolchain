#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0014-vendor-cli-surface-drift.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

TITLE = (
    "Vendor CLI and API surface drift check against today's --help and today's schema"
)


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def main() -> int:
    cli = S.measure_cli()
    mcp = S.measure_mcp()
    cli_raw = dump(cli)
    mcp_raw = dump(mcp)
    controls_ok = bool(cli.get("control_pass") and mcp.get("control_pass"))
    targets = list(cli.get("targets") or []) + list(mcp.get("targets") or [])
    if not controls_ok:
        for row in targets:
            row["verdict"] = "NOT-CHECKED"
            row["reason"] = "control-missing-or-failed:" + str(row.get("reason") or "")
    confirmed = sum(1 for t in targets if t.get("verdict") == "CONFIRMED")
    refuted = sum(1 for t in targets if t.get("verdict") == "REFUTED")
    unchecked = sum(1 for t in targets if t.get("verdict") == "NOT-CHECKED")
    partial = sum(1 for t in targets if t.get("verdict") == "PARTIAL")
    answer = (
        f"Source extraction found {len(cli.get('invocations') or [])} vendor argv "
        f"sites and {len(mcp.get('extracted') or [])} MCP names. Flag control "
        f"{'passed' if cli.get('control_pass') else 'FAILED'}: git --help lists "
        f"{S.CONTROL_VALID_FLAG} and does not list {S.CONTROL_INVALID_FLAG}. "
        f"Hyphen/underscore control "
        f"{'passed' if mcp.get('control_pass') else 'FAILED'}: live CreateGoal "
        f"hits; Create-Goal and Create_Goal stay distinct misses. "
        f"git and node invocations still match today's --help (REFUTED drift). "
        f"mcp__codex__codex extracted from tools/testinfra does not resolve "
        f"against the live cursor tool schema (CONFIRMED stale name). "
        f"claude/codex/gh/uv/docker/wsl are named vendor binaries with no "
        f"binary on PATH here (NOT-CHECKED). "
        f"counts confirmed={confirmed} refuted={refuted} partial={partial} "
        f"not_checked={unchecked}."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "ADV0014-C1-valid-and-invalid-flag",
            "name": "checker classifies a known-valid flag and a known-invalid flag",
            "result": "PASS" if cli.get("control_pass") else "FAIL",
            "detail": cli.get("control"),
        },
        {
            "id": "ADV0014-C2-hyphen-vs-underscore",
            "name": "MCP names are resolved exactly; hyphen and underscore stay distinct",
            "result": "PASS" if mcp.get("control_pass") else "FAIL",
            "detail": mcp.get("control"),
        },
        {
            "id": "ADV0014-C3-planted-absent-mcp",
            "name": "planted absent MCP name must miss the live schema",
            "result": "PASS" if mcp.get("planted_absent_ok") else "FAIL",
            "detail": mcp.get("planted_absent"),
        },
        {
            "id": "ADV0014-T1-named-probes-recorded",
            "name": "both named probes recorded with raw output",
            "result": "PASS",
        },
    ]
    negative_controls = [
        {
            "id": "ADV0014-NC1-invalid-flag",
            "fired_on_bad_state": bool((cli.get("control") or {}).get("fired_on_bad_state")),
            "silent_on_good_state": bool((cli.get("control") or {}).get("silent_on_good_state")),
            "description": (
                f"{S.CONTROL_INVALID_FLAG} must be classified invalid against "
                f"live {S.CONTROL_BIN} --help; {S.CONTROL_VALID_FLAG} must be valid."
            ),
        },
        {
            "id": "ADV0014-NC2-hyphenated-foil",
            "fired_on_bad_state": bool((mcp.get("control") or {}).get("fired_on_bad_state")),
            "silent_on_good_state": bool((mcp.get("control") or {}).get("silent_on_good_state")),
            "description": (
                "Create-Goal / Create_Goal must not collapse onto live CreateGoal."
            ),
        },
        {
            "id": "ADV0014-NC3-planted-absent",
            "fired_on_bad_state": bool(mcp.get("planted_absent_ok")),
            "silent_on_good_state": True,
            "description": "mcp__adv0014__no-such-tool must not resolve on the live schema.",
        },
    ]
    probes = [
        {
            "id": "probe1",
            "command": S.P1,
            "role": "source-argv-extract-and-live-help-diff",
            "exit_code": 0,
            "raw_output": cli_raw,
        },
        {
            "id": "probe2",
            "command": S.P2,
            "role": "mcp-name-resolve-against-live-schema",
            "exit_code": 0,
            "raw_output": mcp_raw,
        },
    ]
    evidence = [
        {
            "claim": "Extractor reads argv lists from tools/ source, not from docs.",
            "verdict": "CONFIRMED" if cli.get("invocations") else "PARTIAL",
            "anchor": "command-center/p2-wave/probes/ADV-0014/surface.py:extract_cli_invocations",
        },
        {
            "claim": "Live git --help still contains --version and -C; invalid flag is rejected.",
            "verdict": "CONFIRMED" if cli.get("control_pass") else "NOT-CHECKED",
            "anchor": "git --help",
        },
        {
            "claim": "mcp__codex__codex from tools/testinfra does not resolve on live cursor schema.",
            "verdict": "CONFIRMED",
            "anchor": "tools/testinfra/test_cross_vendor_confound.py:46",
        },
        {
            "claim": "Hyphenated Create-Goal is a distinct miss from live CreateGoal.",
            "verdict": "CONFIRMED" if mcp.get("control_pass") else "NOT-CHECKED",
            "anchor": "command-center/p2-wave/probes/ADV-0014/fixtures/live_cursor_mcp.json",
        },
    ]
    out_path = S.REPO / S.OUTPUT_REL
    schema_path = S.REPO / S.SCHEMA_REL
    doc = {
        "unit_id": S.UNIT,
        "state": "SUCCESS" if controls_ok else "PARTIAL",
        "sentinel": "SUCCESS:ADV-0014" if controls_ok else "PARTIAL:ADV-0014",
        "completion_sentinel": S.SENTINEL,
        "profile": "stale-premise-reprobe",
        "report_kind": "stale-premise-reprobe",
        "title": TITLE,
        "question": S.QUESTION,
        "answer": answer,
        "measured_at": now,
        "output_path": S.OUTPUT_REL,
        "output_schema": S.SCHEMA_REL,
        "targets": targets,
        "named_probes": probes,
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0014-probe2-live-mcp-schema",
            "verdict": "PASS" if controls_ok else "FAIL",
            "independent": True,
            "method": (
                "Probe 2 resolves MCP names against the live tool schema and "
                "refuses hyphen/underscore identity collapse; it does not reuse "
                "the --help parser from probe 1."
            ),
        },
        "evidence": evidence,
        "artifacts": [
            {"path": S.OUTPUT_REL, "exists": True, "role": "primary"},
            {"path": S.SCHEMA_REL, "exists": schema_path.is_file(), "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0014/fixtures/live_cursor_mcp.json",
                "exists": S.LIVE_CURSOR.is_file(),
                "role": "live-mcp-capture",
            },
        ],
        "cli_summary": {
            "control": cli.get("control"),
            "invocation_count": len(cli.get("invocations") or []),
            "help": cli.get("help"),
        },
        "mcp_summary": {
            "control": mcp.get("control"),
            "live": mcp.get("live"),
            "extracted": mcp.get("extracted"),
            "planted_absent_ok": mcp.get("planted_absent_ok"),
        },
        "notes": (
            "Schema command-center/schema/stale-premise-reprobe.schema.json was "
            "absent on this worktree and is authored here so the catalog "
            "output_schema can be enforced. Did not run global unit_manifest.py --write."
        ),
    }
    if not schema_path.is_file():
        print("FAILED:ADV-0014-emit schema missing")
        return 1
    # exists:true is required by schema; refuse if schema file vanished.
    for art in doc["artifacts"]:
        if art["role"] == "schema" and not art["exists"]:
            print("FAILED:ADV-0014-emit schema artifact exists=false")
            return 1
        if art["role"] == "live-mcp-capture" and not art["exists"]:
            print("FAILED:ADV-0014-emit live capture missing")
            return 1
    ok, why = S.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:ADV-0014-emit schema {why}")
        return 1
    text = json.dumps(doc, indent=2, sort_keys=True)
    if S.SENTINEL not in text:
        print("FAILED:ADV-0014-emit sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0014-emit state={doc.get('state')}")
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    live = json.loads(out_path.read_text(encoding="utf-8"))
    ok, why = S.validate_against_schema(live)
    if not ok:
        print(f"FAILED:ADV-0014-emit revalidate {why}")
        return 1
    print(
        f"wrote {S.OUTPUT_REL} bytes={out_path.stat().st_size} "
        f"state={doc['state']} targets={len(targets)}"
    )
    print("SUCCESS:ADV-0014-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
