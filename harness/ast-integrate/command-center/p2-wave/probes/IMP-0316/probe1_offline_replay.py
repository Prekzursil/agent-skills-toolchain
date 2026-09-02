#!/usr/bin/env python3
"""Probe 1: offline replay with egress blocked; lineage + event-range spot check.

Catalog tests_required[0] and evidence_requirement: replay under --offline
produces a complete lineage (rule, tally, evidence); three decisions match
their raw event-range vote tallies; inspect works for each recorded round.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from fixture import (  # noqa: E402
    RULE_CHAIR,
    RULE_MAJORITY,
    RULE_QUALIFIED,
    write_recorded,
)

UID = "IMP-0316"
RECEIPT = REPO / "command-center" / "receipts" / f"{UID}.json"
CLI = REPO / "tools" / "council" / "cli" / "audit.py"
FORBIDDEN = ("openai", "anthropic", "httpx", "requests", "aiohttp")
EXPECTED_RULES = {
    "D1": RULE_MAJORITY,
    "D2": RULE_CHAIR,
    "D3": RULE_QUALIFIED,
}


def run_cli(*args: str) -> tuple[int, dict]:
    cmd = [sys.executable, "-B", str(CLI), "--offline", *args]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    if proc.returncode != 0 and not parsed:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-1500:]
        print(f"FAILED:{UID}-probe1 cli rc={proc.returncode} {tail}")
    return proc.returncode, parsed


def forbidden_imports(src: str) -> list[str]:
    hits = []
    for name in FORBIDDEN:
        for prefix in (f"import {name}", f"from {name} ", f"from {name}."):
            if prefix in src:
                hits.append(name)
                break
    return hits


def check_receipt() -> str | None:
    if not RECEIPT.is_file():
        return "receipt missing"
    text = RECEIPT.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    if f"SUCCESS:{UID}" not in text:
        return "sentinel absent"
    return None


def main() -> int:
    artifact_path = write_recorded()
    hits = forbidden_imports(CLI.read_text(encoding="utf-8"))
    if hits:
        print(f"FAILED:{UID}-probe1 live-client import {hits}")
        return 1

    rc_lin, lineage = run_cli("lineage", str(artifact_path))
    if rc_lin != 0:
        return 1
    if lineage.get("live_model_call") is not False:
        print(f"FAILED:{UID}-probe1 live_model_call {lineage.get('live_model_call')}")
        return 1
    if not lineage.get("offline"):
        print(f"FAILED:{UID}-probe1 not offline")
        return 1
    guard = lineage.get("egress_guard") or {}
    if guard.get("egress_guard_live") is not True:
        print(f"FAILED:{UID}-probe1 egress guard not live {guard}")
        return 1
    entries = lineage.get("entries") or []
    if len(entries) != 3:
        print(f"FAILED:{UID}-probe1 expected 3 decisions got {len(entries)}")
        return 1
    if lineage.get("complete") is not True:
        print(f"FAILED:{UID}-probe1 lineage incomplete")
        return 1

    spot: list[dict] = []
    for entry in entries:
        did = str(entry.get("decision_id"))
        rule = entry.get("deciding_rule_id")
        if rule != EXPECTED_RULES.get(did):
            print(f"FAILED:{UID}-probe1 {did} rule {rule} != {EXPECTED_RULES.get(did)}")
            return 1
        if entry.get("tally_matches_event_range") is not True:
            print(f"FAILED:{UID}-probe1 {did} tally does not match event range")
            return 1
        evidence = entry.get("evidence") or []
        if not evidence or any(e.get("status") != "RESOLVED" for e in evidence):
            print(f"FAILED:{UID}-probe1 {did} evidence unresolved {evidence}")
            return 1
        if rule == "UNKNOWN":
            print(f"FAILED:{UID}-probe1 intact artifact reported UNKNOWN for {did}")
            return 1
        spot.append(
            {
                "decision_id": did,
                "deciding_rule_id": rule,
                "tally": entry.get("tally"),
                "tally_from_event_range": entry.get("tally_from_event_range"),
                "event_range": entry.get("event_range"),
                "evidence_seqs": [e.get("seq") for e in evidence],
            }
        )

    inspected: list[int] = []
    for rnd in (1, 2, 3):
        rc_ins, ins = run_cli("inspect", str(artifact_path), "--round", str(rnd))
        if rc_ins != 0 or ins.get("found") is not True:
            print(f"FAILED:{UID}-probe1 inspect round {rnd} {ins}")
            return 1
        got = (ins.get("decision") or {}).get("deciding_rule_id")
        if got != EXPECTED_RULES[f"D{rnd}"]:
            print(f"FAILED:{UID}-probe1 inspect round {rnd} rule mismatch {got}")
            return 1
        inspected.append(rnd)

    rc_rep, replayed = run_cli("replay", str(artifact_path))
    if rc_rep != 0 or replayed.get("complete_lineage") is not True:
        print(f"FAILED:{UID}-probe1 replay incomplete")
        return 1

    rec_err = check_receipt()
    if rec_err:
        print(f"FAILED:{UID}-probe1 {rec_err}")
        return 1

    report = {
        "probe": "probe1-offline-replay",
        "unit_id": UID,
        "pass": True,
        "offline": True,
        "egress_guard_live": True,
        "live_model_call": False,
        "decision_count": len(entries),
        "spot_check": spot,
        "inspected_rounds": inspected,
        "forbidden_imports": hits,
        "artifact": str(artifact_path.relative_to(REPO)),
    }
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    print(f"SUCCESS:{UID}-probe1 offline replay lineage and 3 event-range spot checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
