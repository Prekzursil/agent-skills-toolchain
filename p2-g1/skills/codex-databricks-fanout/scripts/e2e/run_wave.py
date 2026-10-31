#!/usr/bin/env python3
"""UNATTENDED wave driver — the entry point a cron calls.

This is the only path that applies the R9 ceiling (engine.ceiling). The interactive drivers
(run_runnability.py, run_fanout.py) deliberately do NOT, because harness.submit_and_gate's
no-timeout default is correct when a human is watching: a hard cap once produced a false
TIMEOUT on a wave whose artifacts were complete and gate-valid.

An unattended run has nobody to ask, so every gate here fails CLOSED. The wave is refused —
loudly, with a reason — rather than started on an assumption.

Quota is caller-supplied via --quota-ok/--quota-unknown because no budget API exists
(AgentBridge's get_budget was retired with the daemon). Omitting it means unknown, which
refuses. That is deliberate: a cron that silently assumes budget is the failure R9 exists to
prevent.

Usage:
    python e2e/run_wave.py <repo> <gaps.json> --quota-ok
    python e2e/run_wave.py <repo> <gaps.json> --quota-ok --max-units 12 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # repo root (contains harness/)
from engine import ceiling as ceiling_mod
from harness.lanes import run_E


def build_ceiling(args) -> ceiling_mod.WaveCeiling:
    d = ceiling_mod.DEFAULT
    return ceiling_mod.WaveCeiling(
        max_units=args.max_units if args.max_units is not None else d.max_units,
        max_concurrent=args.max_concurrent
        if args.max_concurrent is not None
        else d.max_concurrent,
        wall_clock_s=args.wall_clock_s
        if args.wall_clock_s is not None
        else d.wall_clock_s,
        per_unit_watchdog_s=(
            args.watchdog_s if args.watchdog_s is not None else d.per_unit_watchdog_s
        ),
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_wave.py")
    p.add_argument("repo")
    p.add_argument("gaps")
    q = p.add_mutually_exclusive_group()
    q.add_argument("--quota-ok", dest="quota", action="store_const", const=True)
    q.add_argument("--quota-exhausted", dest="quota", action="store_const", const=False)
    p.add_argument("--max-units", type=int)
    p.add_argument("--max-concurrent", type=int)
    p.add_argument("--wall-clock-s", type=int)
    p.add_argument("--watchdog-s", type=int)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="apply the ceiling and report, but do not fan out",
    )
    args = p.parse_args(argv)

    gaps_path = Path(args.gaps)
    if not gaps_path.exists():
        print(
            f"FAILED:wave-{args.repo} gaps file not found: {gaps_path}", file=sys.stderr
        )
        return 2
    gaps = json.loads(gaps_path.read_text(encoding="utf-8")).get("gaps", [])

    cap = build_ceiling(args)
    ok, reason = ceiling_mod.check_wave(
        n_units=len(gaps), ceiling=cap, quota_ok=getattr(args, "quota", None)
    )
    print(
        f"[wave:{args.repo}] units={len(gaps)} ceiling={cap} quota={getattr(args, 'quota', None)}"
    )
    if not ok:
        # Terminal state, per the cross-tool contract: a refusal is a result, not silence.
        print(
            f"FAILED:wave-{args.repo} ceiling refused the wave: {reason}",
            file=sys.stderr,
        )
        return 1
    print(f"[wave:{args.repo}] ceiling ok")

    if args.dry_run:
        print(
            f"SUCCESS:wave-{args.repo} dry-run — ceiling passed, {len(gaps)} unit(s) not dispatched"
        )
        return 0

    verdicts = run_E.run_coverage_fanout(args.repo, gaps)
    done = sum(1 for v in verdicts.values() if v[0] == "DONE")
    print(
        f"SUCCESS:wave-{args.repo} {done}/{len(verdicts)} DONE"
        if done == len(verdicts)
        else f"FAILED:wave-{args.repo} {done}/{len(verdicts)} DONE"
    )
    return 0 if done == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
