#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

G = Path(__file__).resolve().parent
REPO = G.parents[3]
IDS = [ln.strip() for ln in (G / "shard-07.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
rows: dict[str, dict] = {}
for name in ("_shard07_g1_measure.jsonl", "_shard07_g1_remeasure.jsonl"):
    p = G / name
    print("EVIDENCE_FILE", p.name, "exists", p.is_file(), "bytes", p.stat().st_size if p.is_file() else 0)
    if not p.is_file():
        continue
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        n += 1
        rows[rec["id"]] = rec
    print("EVIDENCE_ROWS", p.name, n)

ok = [u for u in IDS if rows.get(u, {}).get("ok")]
fail = [u for u in IDS if u in rows and not rows[u].get("ok")]
missing = [u for u in IDS if u not in rows]
print("ASSIGNED", len(IDS), "MERGED", len(rows), "OK", len(ok), "FAIL", len(fail), "UNMEASURED", missing)
print("OK_IDS", " ".join(ok))
print("FAIL_IDS", " ".join(fail))

rem = G / "shard-07.remaining.txt"
rb = rem.read_bytes()
print("REMAINING_BYTES", len(rb), "SHA256", hashlib.sha256(rb).hexdigest())
print("REMAINING_CRLF", rb.count(b"\r\n"), "LF", rb.count(b"\n"))
print("REMAINING_LIST", rem.read_text(encoding="utf-8").replace("\r\n", "\n").strip().replace("\n", " "))

impl = [
    "tools/marketplace/moderation.py",
    "tools/marketplace/storage.py",
    "tools/marketplace/spdx.py",
    "tools/marketplace/data/spdx-license-list-3.25.0.json",
    "tools/plugin/payload_paths.py",
    "tools/plugin-cache-reaper/cache.py",
    "tools/command-center/claim_gate.py",
    "tools/command-center/codex_mcp_recovery.py",
    "tools/command-center/tests/test_codex_mcp_recovery.py",
    "tools/agentspec/agentspec/packs.py",
    "tools/agentspec/agentspec/semver.py",
    "tools/blueprint_conformance/harness.py",
    "tools/work-unit-adapters/register.py",
    "tools/work-unit-adapters/claude.py",
    "tools/work-unit-adapters/codex.py",
    "tools/work-unit-adapters/dispatch.py",
    "tools/monitorcore/monitorcore/program_pane.py",
    "tools/monitorcore/monitorcore/readonly.py",
    "tools/monitorcore/monitorcore/census.py",
    "tools/council/participants/select_calibrated.py",
    "tools/council/topology/redblue.py",
    "tools/council/topology/fishbowl.py",
    "tools/council/stopping/minimum.py",
    "tools/hook_load/load_probe.py",
    "tools/router/rule_matcher.py",
    "command-center/p2-wave/probes/ADV-0068/probe1_mass_reports.py",
    "command-center/p2-wave/probes/ADV-0090/probe1_attempt_history.py",
    "command-center/p2-wave/probes/ADV-0113/probe1_gate_submit.py",
]
print("IMPL")
for rel in impl:
    p = REPO / rel
    print(" ", "PRESENT" if p.is_file() else "ABSENT", p.stat().st_size if p.is_file() else 0, rel)

print("LAST_LINES")
for uid in IDS:
    rec = rows.get(uid) or {}
    print(uid, rec.get("last") or "NO-MEASURE")
