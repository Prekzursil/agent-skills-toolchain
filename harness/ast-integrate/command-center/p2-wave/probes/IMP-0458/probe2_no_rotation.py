#!/usr/bin/env python3
"""Probe 2: no-rotation / report-only, verified by reading the gate source.

Distinct from probe 1 (which plants a canary). This probe AST-reads the gate,
proves the inspector fires on a mutating snippet, and proves a live scan does
not change file bytes or os.environ.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from secret_scrub_gate import (  # noqa: E402
    report_contains_secret_body,
    report_only_violations,
    scan_before_register,
    scan_tree,
    synthetic_canary_value,
)

ART = REPO / "command-center/receipts/IMP-0458.json"
GATE = HERE / "secret_scrub_gate.py"
MENTION = HERE / "fixtures" / "mention-only"
SENTINEL = "SENTINEL:IMP-0458:SECRET-SCRUB-REPORT-ONLY"
MUTATING_SNIPPET = (
    "import os\n"
    "os.unsetenv('GITHUB_TOKEN')\n"
    "os.environ.pop('AWS_SECRET_ACCESS_KEY', None)\n"
)


def main() -> int:
    source = GATE.read_text(encoding="utf-8")
    raw_before = GATE.read_bytes()
    gate_hits = report_only_violations(source)
    bad_hits = report_only_violations(MUTATING_SNIPPET)
    env_before = dict(os.environ)
    before = hashlib.sha256(raw_before).hexdigest()
    mention = scan_tree(MENTION, include=None, exclude=())
    gate_scan = scan_before_register(GATE)
    after = hashlib.sha256(GATE.read_bytes()).hexdigest()
    env_after = dict(os.environ)

    if not ART.is_file():
        print("FAILED:IMP-0458-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    receipt_scan = scan_before_register(ART)
    leaked = report_contains_secret_body(text, [synthetic_canary_value()])

    out = {
        "probe": "probe2-no-rotation-source-read",
        "unit_id": "IMP-0458",
        "gate_violations": gate_hits,
        "mutating_snippet_violations": bad_hits,
        "inspector_fires_on_unsetenv": bool(bad_hits),
        "inspector_silent_on_gate": not gate_hits,
        "source_hash_unchanged": before == after,
        "environ_unchanged": env_before == env_after,
        "mention_findings": mention.findings and [f.evidence for f in mention.findings],
        "gate_file_token_findings": [f.evidence for f in gate_scan.findings],
        "receipt_tokenish": [
            f.evidence
            for f in receipt_scan.findings
            if f.prefix in {"ghp_", "gho_", "AKIA", "sk-ant-", "xoxb-", "github_pat_"}
        ],
        "receipt_leaked_canary": leaked,
        "receipt_state": doc.get("state"),
        "sentinel_present": SENTINEL in text,
        "mode": doc.get("mode"),
        "no_rotation": doc.get("no_rotation"),
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    if not bad_hits:
        print("FAILED:IMP-0458-probe2 inspector silent on mutating snippet")
        return 1
    if gate_hits:
        print("FAILED:IMP-0458-probe2 gate source has mutation paths")
        print(gate_hits)
        return 1
    if before != after:
        print("FAILED:IMP-0458-probe2 scanning the gate rewrote it")
        return 1
    if env_before != env_after:
        print("FAILED:IMP-0458-probe2 os.environ mutated")
        return 1
    if mention.findings:
        print("FAILED:IMP-0458-probe2 mention fixture fired")
        return 1
    if leaked:
        print("FAILED:IMP-0458-probe2 receipt leaked canary")
        return 1
    if out["receipt_tokenish"]:
        print("FAILED:IMP-0458-probe2 receipt carries token-shaped values")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0458-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0458-probe2 self-declared {doc.get('state')}")
        return 1
    if doc.get("mode") != "report-only":
        print("FAILED:IMP-0458-probe2 mode is not report-only")
        return 1
    print("SUCCESS:IMP-0458-probe2 report-only source-read and no mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
