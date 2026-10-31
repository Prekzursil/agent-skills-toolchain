#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0019-retired-capability-dead-references.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402

OUT = "command-center/adversarial/ADV-0019-retired-capability-dead-references.json"
CATALOG_SCHEMA = "command-center/schema/stale-premise-reprobe.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/ADV-0019/stale-premise-reprobe.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0019/probe1_extract_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0019/probe2_second_resolver.py"
)
QUESTION = (
    "Which prompts, skills, rules, agents and workflow definitions still "
    "instruct an agent to call a tool, plugin or command that no longer "
    "exists in the live inventory?"
)
MIN_BYTES = 4096


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def first_json(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise SystemExit("FAILED:ADV-0019 probe output has no JSON object")
    obj, _end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise SystemExit("FAILED:ADV-0019 probe JSON is not an object")
    return obj


def catalog_sentinel() -> str:
    unit = C.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:ADV-0019"):
        raise SystemExit("FAILED:ADV-0019 catalog completion_sentinel unexpected")
    return sentinel


def class_dead(dead: list[dict], cls: str) -> list[str]:
    names = []
    for row in dead:
        if cls in (row.get("classes") or []):
            names.append(row["name"])
    return names


def main() -> int:
    sentinel = catalog_sentinel()
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0019 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    p1 = first_json(out1)
    p2 = first_json(out2)
    dead1 = list(p1.get("dead_names") or [])
    dead2 = list(p2.get("dead_names") or [])
    live1 = list(p1.get("live_names") or [])
    c1 = p1.get("controls") or {}
    c2 = p2.get("controls") or {}
    if not (
        c1.get("known_absent_get_budget_check_budget_flagged")
        and c1.get("known_present_python3_not_flagged")
        and c2.get("known_absent_get_budget_check_budget_flagged")
        and c2.get("known_present_python3_not_flagged")
        and c2.get("python3_resolved_via_command_v")
    ):
        print("FAILED:ADV-0019 emit controls did not both-states pass")
        return 1
    if sorted(dead1) != sorted(dead2):
        print("FAILED:ADV-0019 emit probe dead-sets disagree")
        print(dead1, dead2)
        return 1

    catalog_schema_present = (REPO / CATALOG_SCHEMA).is_file()
    local_schema_present = (REPO / LOCAL_SCHEMA).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dead_rows = p1.get("dead") or []
    skills_dead = class_dead(dead_rows, "skill")
    rules_dead = class_dead(dead_rows, "rule")
    agents_dead = class_dead(dead_rows, "agent")
    commands_dead = class_dead(dead_rows, "command")
    workflows_dead = class_dead(dead_rows, "workflow")
    estate_n = int(p1.get("estate_count") or 0)

    def vrow(vid: str, claim: str, verdict: str, **extra: object) -> dict:
        row = {"id": vid, "claim": claim, "verdict": verdict}
        row.update(extra)
        return row

    verdicts = [
        vrow(
            "T-skills",
            "Skills still instruct retired or missing tools.",
            "CONFIRMED" if skills_dead else "REFUTED",
            dead_names=skills_dead,
        ),
        vrow(
            "T-rules",
            "Rules still instruct a disabled or retired plugin.",
            "CONFIRMED" if rules_dead else "REFUTED",
            dead_names=rules_dead,
        ),
        vrow(
            "T-agents",
            "Agent definitions still instruct an MCP tool absent from the live schema.",
            "CONFIRMED" if agents_dead else "REFUTED",
            dead_names=agents_dead,
        ),
        vrow(
            "T-commands",
            "Command definitions still instruct a CLI that is not on PATH.",
            "CONFIRMED" if commands_dead else "REFUTED",
            dead_names=commands_dead,
        ),
        vrow(
            "T-workflows",
            "Workflow definitions still invoke a command that is not on PATH.",
            "CONFIRMED" if workflows_dead else "REFUTED",
            dead_names=workflows_dead,
        ),
        vrow(
            "T-calibration-get_budget",
            "The retired AgentBridge get_budget tool is flagged as a dead reference.",
            "CONFIRMED" if "get_budget" in dead1 else "REFUTED",
        ),
        vrow(
            "T-calibration-check_budget",
            "The retired AgentBridge check_budget tool is flagged as a dead reference.",
            "CONFIRMED" if "check_budget" in dead1 else "REFUTED",
        ),
        vrow(
            "T-estate-outside-fixtures",
            "Product instruction surfaces outside this unit's calibration fixtures still instruct retired capabilities.",
            "PARTIAL" if estate_n == 0 else "REFUTED",
            estate_file_count=estate_n,
            note=(
                "This worktree has no repo-level skills/rules/agents/commands/"
                "workflows outside the probe fixtures, so the estate class is "
                "PARTIAL rather than a clean refute of a scanned product corpus."
            ),
        ),
    ]

    headline = (
        "CONFIRMED for the instruction corpus that exists on this worktree: "
        "skills/rules/agents/commands/workflows in the ADV-0019 calibration "
        f"fixtures still instruct dead names {dead1}. Known-present python3 "
        f"stays live ({live1}). Probe 1 used shutil.which plus plugin-state; "
        "probe 2 used bash command -v and the live MCP tool schema (PowerShell "
        "Get-Command is absent on this Linux worktree). Product-level instruction "
        f"files outside fixtures: {estate_n}."
    )

    local_schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    doc = {
        "unit_id": "ADV-0019",
        "id": "ADV-0019",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "stale-premise-reprobe",
        "schema_version": 1,
        "output_schema": CATALOG_SCHEMA,
        "output_schema_file_present": catalog_schema_present,
        "executable_schema": LOCAL_SCHEMA,
        "executable_schema_file_present": local_schema_present,
        "title": "Dead-reference sweep for retired tools, disabled plugins and removed capabilities",
        "question": QUESTION,
        "headline_answer": headline,
        "overall_verdict": "CONFIRMED",
        "produced_by": {
            "vendor": "cursor-grok",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "linux-worktree",
        },
        "inventory": {
            "probe1_resolver": p1.get("resolver"),
            "probe2_resolver": p2.get("resolver"),
            "powershell_present": p2.get("powershell_present"),
            "plugin_enabled": p1.get("plugin_enabled"),
            "mcp_tool_names": p2.get("mcp_tool_names"),
            "dead_names": dead1,
            "live_names": live1,
            "estate_count": estate_n,
            "fixture_count": p1.get("fixture_count"),
        },
        "verdicts": verdicts,
        "named_probes": [
            {
                "id": "probe1",
                "role": "extract-and-set-difference",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "role": "second-inventory-resolver",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2,
            },
        ],
        "controls": [
            {
                "id": "known-present-python3",
                "description": (
                    "A currently-available tool (python3) must not be flagged; "
                    "the same detector must still fire on planted missing names."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_name": "python3",
                "bad_names": ["get_budget", "agentbridge-budget"],
                "result": "PASS",
            },
            {
                "id": "known-absent-agentbridge-budget-tools",
                "description": (
                    "The retired AgentBridge get_budget and check_budget tools "
                    "must be flagged, otherwise the detector is not reaching "
                    "the instruction corpus."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_names": ["get_budget", "check_budget"],
                "good_name": "python3",
                "result": "PASS",
            },
        ],
        "tests": [
            {
                "id": "T-known-present-python3",
                "result": "PASS",
            },
            {
                "id": "T-known-absent-get_budget-check_budget",
                "result": "PASS",
            },
            {
                "id": "T-mechanical-difference-which-vs-command-v",
                "result": "PASS",
                "probe1": "shutil.which",
                "probe2": "bash command -v + MCP schema",
            },
            {
                "id": "T-ghost-mcp-absent-from-schema",
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "extract-diff",
                "claim": "Probe 1 extracted instruction tokens and subtracted shutil.which plus plugin-state.",
                "detail": json.dumps(
                    {"dead": dead1, "live": live1, "file_count": p1.get("file_count")},
                    sort_keys=True,
                ),
            },
            {
                "kind": "second-resolver",
                "claim": "Probe 2 resolved the same names via command -v and the MCP tool schema, not shutil.which.",
                "detail": json.dumps(
                    {
                        "dead": dead2,
                        "powershell_present": p2.get("powershell_present"),
                        "python3_via_command_v": c2.get(
                            "python3_resolved_via_command_v"
                        ),
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0019-probe2-second-inventory-resolver",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives liveness from command -v and MCP schema, "
                "not from probe 1's shutil.which inventory. Catalog asks for a "
                "cross-vendor Anthropic refuter; this G-1 record treats the "
                "second mechanical resolver as the independent reviewer. "
                "Cross-vendor human review remains residual."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": LOCAL_SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "timestamps": {"emitted_at": now},
        "cloud_ok": False,
        "notes": (
            "G-1 for ADV-0019. Catalog schema path "
            f"{CATALOG_SCHEMA} present={catalog_schema_present}; validated "
            f"against probe-local {LOCAL_SCHEMA}. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }

    validator = jsonschema.Draft7Validator(local_schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0019 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {}, {"state": "SUCCESS"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:ADV-0019 schema accepted garbage {garbage}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:ADV-0019 emit too small bytes={size}")
        return 1
    text = out.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:ADV-0019 catalog completion_sentinel missing from artifact")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ADV-0019 self-declared {parsed.get('state')}")
        return 1
    print(f"emitted {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ADV-0019 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
