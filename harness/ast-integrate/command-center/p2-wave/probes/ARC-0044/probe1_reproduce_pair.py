#!/usr/bin/env python3
"""Probe 1: produce both vendor artifacts; both pass; semantics differ.

Both-states: harness predicate accepts Claude-confirm (no write) and
Codex-auto (write). effect.digest identity guard FAIL-CLOSES only on the split.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A6/REFUTATION.json"
CLAUDE = REPO / "command-center/p2-wave/probes/ARC-0044/artifacts/runs/claude-confirm.json"
CODEX = REPO / "command-center/p2-wave/probes/ARC-0044/artifacts/runs/codex-auto.json"


def main() -> int:
    run = S.run_scenario()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:ARC-0044-probe1 scenario did not reproduce the SUCCESS split")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0044-probe1 REFUTATION.json missing")
        return 1
    if not CLAUDE.is_file() or not CODEX.is_file():
        print("FAILED:ARC-0044-probe1 vendor artifacts missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0044-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("both_predicate_pass") is True
        and rec.get("semantic_divergence") is True
        and rec.get("guard_would_fail_loudly") is True
        and rec.get("claude_writes_applied") == 0
        and rec.get("codex_writes_applied") == 1
    )
    if not rec_ok:
        print("FAILED:ARC-0044-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0044-probe1 procedure too short")
        return 1
    qd = doc.get("quoted_divergence") or {}
    if not qd.get("claude_quote") or not qd.get("codex_quote"):
        print("FAILED:ARC-0044-probe1 divergence not quoted")
        return 1
    if qd.get("claude_quote") == qd.get("codex_quote"):
        print("FAILED:ARC-0044-probe1 quotes are identical")
        return 1
    live_c = json.loads(CLAUDE.read_text(encoding="utf-8"))
    live_x = json.loads(CODEX.read_text(encoding="utf-8"))
    if live_c.get("writes_applied") != 0 or live_x.get("writes_applied") != 1:
        print("FAILED:ARC-0044-probe1 live artifacts do not split")
        return 1
    if str(qd.get("claude-confirm", {}).get("effect_digest")) != live_c.get("effect_digest"):
        print("FAILED:ARC-0044-probe1 quoted Claude digest mismatch")
        return 1
    if str(qd.get("codex-auto", {}).get("effect_digest")) != live_x.get("effect_digest"):
        print("FAILED:ARC-0044-probe1 quoted Codex digest mismatch")
        return 1
    if "SUCCESS:ARC-0044" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0044-probe1 sentinel absent")
        return 1
    print(
        "predicate_both="
        f"{run.get('both_predicate_pass')} split={run.get('semantic_divergence')} "
        f"guard_loud={run.get('guard_would_fail_loudly')} "
        f"writes={run.get('claude_writes_applied')}/{run.get('codex_writes_applied')}"
    )
    print("SUCCESS:ARC-0044-probe1 vendor-pair SUCCESS split reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
