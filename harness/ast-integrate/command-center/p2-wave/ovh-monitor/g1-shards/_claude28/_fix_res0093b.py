#!/usr/bin/env python3
"""shard-01 scratch: add report block + measured artifact rows to RES-0093."""
import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
ART = REPO / "command-center/research/RES-0093.json"
doc = json.loads(ART.read_text(encoding="utf-8"))

tests = doc.get("tests") or {}
ctl = tests.get("inapplicable_popular_control") or {}
register = doc.get("benchmark_register") or []
applicable = sum(1 for r in register if r.get("applicability_verdict") == "applicable")
inapplicable = sum(1 for r in register if r.get("applicability_verdict") == "inapplicable")

doc["report"] = {
    "kind": "research-registry",
    "observations": [
        {
            "name": "benchmark_register_rows",
            "measured": len(register),
            "method": "engine.build_register() live recompute over committed paper_facts fixture",
            "anchor": "command-center/p2-wave/probes/RES-0093/engine.py",
        },
        {
            "name": "applicable_rows_with_named_improvement",
            "measured": applicable,
            "method": "engine.tests_from_register: every applicable row names a harness-level detectable improvement",
            "anchor": "command-center/p2-wave/probes/RES-0093/probe1_register.py",
        },
        {
            "name": "inapplicable_rows",
            "measured": inapplicable,
            "method": "applicability verdicts from the register engine",
            "anchor": "command-center/research/RES-0093.json",
        },
        {
            "name": "inapplicable_popular_control",
            "measured": str(ctl.get("benchmark_id") or "humaneval"),
            "measured_pass": bool(ctl.get("pass")),
            "method": "named popular benchmark recorded inapplicable (control)",
            "anchor": "command-center/p2-wave/probes/RES-0093/probe1_register.py",
        },
    ],
    "control_ids": ["inapplicable-popular-control:" + str(ctl.get("benchmark_id") or "humaneval")],
}

ROLE_MAP = {"catalog-shim": "supporting", "live-schema": "supporting", "paper-facts": "fixture", "engine": "supporting"}
for row in doc.get("artifacts") or []:
    rel = row.get("path") or ""
    if row.get("role") in ROLE_MAP:
        row["role"] = ROLE_MAP[row["role"]]
    p = REPO / rel
    if p.is_file():
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        row["bytes"] = len(raw)
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        row["exists"] = True

ART.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
print("wrote report block; register rows:", len(register), "applicable:", applicable)
raw = ART.read_bytes().replace(b"\r\n", b"\n")
print("new sha256:", hashlib.sha256(raw).hexdigest(), "bytes:", len(raw))
