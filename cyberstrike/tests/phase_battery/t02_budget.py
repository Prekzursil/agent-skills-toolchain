#!/usr/bin/env python3
"""T-2 budget + stale-payload - byte budget and dead-token greps.

G-11=C puts budgets IN TEXT now; deploy-phase3.md asserts the Phase-3 pair
(AGENTS + CONTEXT) totals <= 7500 B and carries zero stale-session tokens.

Runnable NOW against the staged drafts (pre-switch target = AGENTS.new.md +
CONTEXT.new.md). After the Phase-3 switch, `--target live` (or auto) checks
the real AGENTS.md/CONTEXT.md. The CURRENT live pair (AGENTS.md+config.md+
CONTEXT.md+instructions-*.md, 32,829 B across the instruction set) is recorded
as baseline context only - it is pre-switch by design and is NOT the assert
target (claims scoped to measured evidence, per C2 discipline).

Stale tokens (from the audit's contaminated-session findings):
  ses_f9c9ab90 (stale session id) - FINAL-REPORT_2026-09-03 (dead runbook) -
  "Daybreak Red" (phantom registered model, fixed by Phase-1 CF-01).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO,
    SUCCESS,
    FAILED,
    VerdictRecorder,
    read_text,
)

BUDGET_BYTES = 7500
STALE_TOKENS = ("ses_f9c9ab90", "FINAL-REPORT_2026-09-03", "Daybreak Red")


def target_files(mode: str) -> list[Path]:
    new_pair = [REPO / "AGENTS.new.md", REPO / "CONTEXT.new.md"]
    live_pair = [REPO / "AGENTS.md", REPO / "CONTEXT.md"]
    if mode == "drafts":
        return new_pair
    if mode == "live":
        return live_pair
    # auto: drafts while the switch hasn't happened (AGENTS.new.md present and
    # different from live AGENTS.md), live afterwards.
    if (REPO / "AGENTS.new.md").exists() and read_text(
        REPO / "AGENTS.new.md"
    ) != read_text(REPO / "AGENTS.md"):
        return new_pair
    return live_pair


def baseline_files() -> list[Path]:
    return [
        REPO / n
        for n in (
            "AGENTS.md",
            "config.md",
            "CONTEXT.md",
            "instructions-recon.md",
            "instructions-fullpower-estate.md",
        )
    ]


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    opts = opts or {}
    mode = opts.get("target", "auto")
    files = target_files(mode)
    missing = [f.name for f in files if not f.exists()]
    if missing:
        rec.record("T-2", FAILED, reason=f"target files missing: {missing}")
        return FAILED

    total = sum(f.stat().st_size for f in files)
    stale_hits = {
        f.name: {t: read_text(f).count(t) for t in STALE_TOKENS} for f in files
    }
    any_stale = any(c for per_file in stale_hits.values() for c in per_file.values())
    budget_ok = total <= BUDGET_BYTES
    stale_ok = not any_stale

    rec.hit(
        "T-2",
        "budget",
        target=mode,
        files=[f.name for f in files],
        total_bytes=total,
        budget_bytes=BUDGET_BYTES,
        within=total <= BUDGET_BYTES,
    )
    for fname, per_file in stale_hits.items():
        for tok, c in per_file.items():
            if c:
                rec.hit("T-2", "stale_token", file=fname, token=tok, count=c)
    # baseline context (informational, pre-switch payload)
    bl = baseline_files()
    bl_total = sum(f.stat().st_size for f in bl if f.exists())
    rec.hit(
        "T-2",
        "baseline_context",
        files=[f.name for f in bl],
        total_bytes=bl_total,
        note="pre-switch instruction set; not the assert target",
    )

    ok = budget_ok and stale_ok
    rec.record(
        "T-2",
        SUCCESS if ok else FAILED,
        details={
            "target_mode": mode,
            "total_bytes": total,
            "budget_bytes": BUDGET_BYTES,
            "stale_token_hits": stale_hits,
            "baseline_live_instruction_set_bytes": bl_total,
        },
        anchors=files,
        reason=None
        if ok
        else ("over budget" if not budget_ok else "stale tokens present"),
    )
    return SUCCESS if ok else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=("auto", "drafts", "live"), default="auto")
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-2"}) as rec:
        status = run(rec, {"target": args.target})
        print(f"T-2 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
