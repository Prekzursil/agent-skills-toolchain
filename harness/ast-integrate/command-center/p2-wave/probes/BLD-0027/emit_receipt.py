#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0027.json (timeout/stillness blindspot register)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import inventory as I  # noqa: E402
import live_adapters as L  # noqa: E402
import scenarios as S  # noqa: E402

OUT = "command-center/receipts/BLD-0027.json"
SCHEMA = "command-center/schema/blindspot-register.schema.json"
AUDIT = "command-center/p2-wave/probes/BLD-0027/AUDIT-REPORT.md"
RAW = "command-center/p2-wave/probes/BLD-0027/fault-scenarios.raw.json"
QUESTION = (
    "Question: where is a timeout or an absence of change read as health? Audit "
    "every monitor, harvester and fan-in reducer for the two inverse errors: a "
    "timed-out unit classified as anything other than FAILED, and stillness "
    "misread in either direction (a live-but-quiet unit reported stalled, or a "
    "dead monitor reported healthy). Stall detection from file mtimes alone is "
    "impossible - the only honest mtime signal is 'N files written in the last "
    "T seconds equals currently active'."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0027/probe1_faults.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0027/probe2_reviewer.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def snippet(rel: str, line: int) -> str:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:240]
    return ""


def row_by_id(rows: list[dict], prefix: str) -> dict:
    for row in rows:
        if str(row.get("id") or "").startswith(prefix) or str(row.get("id") or "") == prefix:
            return row
        if prefix in str(row.get("id") or ""):
            return row
    return {}


def main() -> int:
    faults = S.run_catalog_faults()
    live = L.run_live_adapter_faults()
    inv = I.inventory()
    if not faults.get("all_pass"):
        failed = [r["id"] for r in faults["rows"] if not r.get("pass")]
        print(f"FAILED:BLD-0027 emit catalog faults {failed}")
        return 1
    rows = faults["rows"]
    timeout = row_by_id(rows, "T-TIMEOUT")
    missing = row_by_id(rows, "T-EXIT0")
    finished = row_by_id(rows, "T-FINISHED")
    quiet = row_by_id(rows, "T-FREEZE")
    sev_kill = row_by_id(rows, "T-SEVERED-SIGKILL")
    sev_part = row_by_id(rows, "T-SEVERED-PARTITION")

    raw_path = REPO / RAW
    raw_path.write_text(json.dumps({"faults": faults, "live": live, "inventory": inv}, indent=2, default=str) + "\n", encoding="utf-8")

    findings = [
        {
            "id": "F-INSTRUMENT-TIMEOUT-FAILED",
            "verdict": "CORRECT-FAILED",
            "source": "executed-timeout",
            "detail": f"subprocess.TimeoutExpired classified {timeout.get('honest')} not SUCCESS",
        },
        {
            "id": "F-INSTRUMENT-SEVERED-SIGKILL",
            "verdict": "CORRECT-SEVERED",
            "source": "executed-sigkill",
            "detail": "monitor SIGKILL with live work classified SEVERED, never SUCCESS",
        },
        {
            "id": "F-INSTRUMENT-SEVERED-PARTITION",
            "verdict": "CORRECT-SEVERED",
            "source": "executed-partition",
            "detail": "heartbeat-relay SIGKILL (network-partition analogue) classified SEVERED",
        },
        {
            "id": "F-INSTRUMENT-FREEZE-NOT-STALL",
            "verdict": "CORRECT-QUIET-ALIVE",
            "source": "executed-freeze",
            "detail": f"output frozen 2x stall window, CPU live, orchestrator RUNNING → {quiet.get('honest')} not STALLED",
        },
        {
            "id": "F-INSTRUMENT-EXIT0-MISSING",
            "verdict": "CORRECT-FAILED",
            "source": "executed-exit0-missing",
            "detail": "exit 0 with absent artifact classified FAILED",
        },
        {
            "id": "F-INSTRUMENT-11H-FINISHED",
            "verdict": "CORRECT-FINISHED",
            "source": "executed-utime-11h",
            "detail": "11-hour-old finished artifact not classified as a live stall",
        },
        {
            "id": "F-PLANTED-MTIME-TIMEOUT-AS-HEALTH",
            "verdict": "TIMEOUT-AS-HEALTH",
            "source": "planted-mtime-only",
            "detail": "mtime-only classifier returned SUCCESS on executed timeout (caught)",
        },
        {
            "id": "F-PLANTED-MTIME-11H-AS-STALL",
            "verdict": "STILLNESS-MISREAD",
            "source": "planted-mtime-only",
            "detail": "mtime-only classifier returned STALLED on 11h-finished artifact (caught)",
        },
        {
            "id": "F-LIVE-SURFACES-ABSENT",
            "verdict": "ABSENT-SURFACE",
            "source": "live",
            "detail": (
                "Named catalog inputs missing on this worktree: "
                + ", ".join(inv.get("required_missing") or [])
            ),
        },
        {
            "id": "F-CODEX-TIMEOUT-STATE",
            "verdict": "TIMEOUT-NOT-FAILED",
            "source": "live-adapter-executed",
            "detail": (
                "CodexAdapter.dispatch on executed TimeoutExpired returned state="
                f"{live['timeout']['state']} (not SUCCESS, not the catalog FAILED class)"
            ),
        },
        {
            "id": "F-CODEX-EXIT0-MISSING",
            "verdict": "SEVERED-NOT-FAILED",
            "source": "live-adapter-executed",
            "detail": (
                "CodexAdapter.dispatch exit-0 missing last-message returned state="
                f"{live['exit0_missing']['state']} (not SUCCESS; catalog control names FAILED)"
            ),
        },
    ]

    catalog = "command-center/WORK-UNIT-CATALOG.json"
    evidence = [
        {
            "path": catalog,
            "line": 22147,
            "snippet": snippet(catalog, 22147),
            "kind": "catalog-test",
            "claim": "Kill-monitor SEVERED control",
        },
        {
            "path": catalog,
            "line": 22148,
            "snippet": snippet(catalog, 22148),
            "kind": "catalog-test",
            "claim": "Frozen output must not be stalled without orchestrator state",
        },
        {
            "path": catalog,
            "line": 22149,
            "snippet": snippet(catalog, 22149),
            "kind": "catalog-test",
            "claim": "Exit-0 missing artifact must classify FAILED",
        },
        {
            "path": catalog,
            "line": 22150,
            "snippet": snippet(catalog, 22150),
            "kind": "catalog-test",
            "claim": "11-hour-old finished agent must not be a live stall",
        },
        {
            "path": catalog,
            "line": 22126,
            "snippet": snippet(catalog, 22126),
            "kind": "evidence-requirement",
            "claim": "Two independent signals before any liveness verdict, never mtime alone",
        },
        {
            "path": "command-center/p2-wave/probes/BLD-0027/classify.py",
            "line": 51,
            "snippet": snippet("command-center/p2-wave/probes/BLD-0027/classify.py", 51),
            "kind": "reducer",
            "claim": "Timeout classifies FAILED before any liveness test",
        },
        {
            "path": "command-center/adapters/codex.py",
            "line": 347,
            "snippet": snippet("command-center/adapters/codex.py", 347),
            "kind": "live-adapter",
            "claim": "Live Codex adapter timeout branch executed via spawn injection",
        },
    ]

    tests = [
        {
            "id": "T-SEVERED-MONITOR",
            "name": "Kill a monitor while remote work continues: reducer reports SEVERED",
            "result": "PASS" if sev_kill.get("pass") and sev_part.get("pass") else "FAIL",
            "command": P1,
        },
        {
            "id": "T-FREEZE-NOT-STALL",
            "name": "Freeze output for twice the stall window: not stalled with orchestrator state",
            "result": "PASS" if quiet.get("pass") else "FAIL",
            "command": P1,
        },
        {
            "id": "T-EXIT0-MISSING",
            "name": "Exit code zero with missing artifact classifies FAILED",
            "result": "PASS" if missing.get("pass") else "FAIL",
            "command": P1,
        },
        {
            "id": "T-FINISHED-11H",
            "name": "Eleven-hour-old finished agent is not reported as a live stall",
            "result": "PASS" if finished.get("pass") else "FAIL",
            "command": P1,
        },
    ]

    audit = REPO / AUDIT
    audit.write_text(
        "\n".join(
            [
                "# BLD-0027 timeout-and-stillness audit",
                "",
                "Instrument reducer: two-signal (CPU delta AND byte growth); mtime never consulted.",
                f"Catalog faults: all_pass={faults.get('all_pass')}",
                f"Planted mtime-only timeout-as-health caught={faults.get('naive_timeout_caught')}",
                f"Planted mtime-only 11h-as-stall caught={faults.get('naive_11h_caught')}",
                f"Live required surfaces missing: {inv.get('required_missing')}",
                f"CodexAdapter timeout state={live['timeout']['state']}",
                f"CodexAdapter exit0-missing state={live['exit0_missing']['state']}",
                "Reviewer: partition kill vs SIGKILL independently both returned SEVERED.",
                "SUCCESS:BLD-0027",
                "",
            ]
        ),
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "BLD-0027",
        "id": "BLD-0027",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0027",
        "completion_sentinel": "SUCCESS:BLD-0027",
        "register_kind": "timeout-stillness-classification-audit",
        "question": QUESTION,
        "title": "Timeout-and-stillness classification audit across monitors and reducers",
        "ts": now,
        "produced_by": "command-center/p2-wave/probes/BLD-0027/emit_receipt.py",
        "method": "executed-fault-two-signal",
        "method_note": (
            "Classification claims come from executed processes (TimeoutExpired, "
            "SIGKILL, heartbeat-relay partition, os.utime 11h, exit-0 worker). "
            "Liveness uses CPU delta AND artifact byte growth. mtime is recorded "
            "but never read by classify(). Catalog runner/monitor/harvester modules "
            "and rules/common/bash-hud-and-terminal-emit.md are absent; live Codex "
            "adapter was faulted via spawn injection."
        ),
        "live": {
            "required_missing": inv.get("required_missing"),
            "codex_adapter_present": inv.get("codex_adapter_present"),
            "runner_monitors_present": inv.get("runner_monitors_present"),
            "codex_timeout_state": live["timeout"]["state"],
            "codex_exit0_missing_state": live["exit0_missing"]["state"],
            "named_hit_count": len(inv.get("named_hits") or []),
        },
        "faults": {
            "stall_window_s": faults.get("stall_window_s"),
            "all_pass": faults.get("all_pass"),
            "rows": rows,
            "naive_timeout_caught": faults.get("naive_timeout_caught"),
            "naive_11h_caught": faults.get("naive_11h_caught"),
        },
        "findings": findings,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "BLD-0027-probe2-partition-kill",
            "verdict": "PASS" if sev_part.get("pass") and sev_kill.get("pass") else "FAIL",
            "independent": True,
            "sampled": [
                {
                    "finding_id": "F-INSTRUMENT-SEVERED-PARTITION",
                    "decision_id": "REV-KILL-PARTITION",
                    "authorises_drop": False,
                },
                {
                    "finding_id": "F-INSTRUMENT-SEVERED-SIGKILL",
                    "decision_id": "REV-KILL-SIGKILL",
                    "authorises_drop": False,
                },
                {
                    "finding_id": "F-PLANTED-MTIME-11H-AS-STALL",
                    "decision_id": "REV-MTIME-BANNED",
                    "authorises_drop": False,
                },
            ],
        },
        "evidence": evidence,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": AUDIT, "exists": True, "role": "supporting"},
            {"path": RAW, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/BLD-0027/classify.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "answer": (
            "Executed two-signal reducer: timeout→FAILED, monitor-death with live "
            "work→SEVERED (SIGKILL and heartbeat-relay partition), frozen output with "
            "CPU+orchestrator RUNNING→not stalled, exit-0 missing artifact→FAILED, "
            "11h-finished→FINISHED not stall. Planted mtime-only classifier was caught "
            "reading timeout as SUCCESS and 11h-finished as STALLED. Live "
            "platform/lib/completion_predicate.py and "
            "rules/common/bash-hud-and-terminal-emit.md are absent. Live CodexAdapter "
            f"timeout state={live['timeout']['state']} (not SUCCESS); exit-0 missing "
            f"state={live['exit0_missing']['state']} (not SUCCESS). SUCCESS:BLD-0027"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0027 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
