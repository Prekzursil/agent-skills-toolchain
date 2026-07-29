"""Program R entry point: the ~500-unit autonomous research fan-out.

  python e2e/run_research.py --dry-run              # plan only, spend nothing
  python e2e/run_research.py --shard 0 --quota-ok   # run one 48-unit wave
  python e2e/run_research.py --all --quota-ok       # every shard, sequentially

500 units cannot run as one wave: the R9 ceiling caps a wave at 48 concurrent, so the
programme is 11 sequential shards. Each shard is gated independently, which is deliberate —
it is the natural stopping point between waves if quota or spend turns out worse than
expected.

Quota is a judgement, not an API. Omitting --quota-ok refuses, which is the correct
outcome when you cannot tell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # repo root (contains harness/)

from engine import ceiling as ceiling_mod  # noqa: E402
from harness.lanes import research  # noqa: E402

PLAN = Path(__file__).resolve().parent / "_R_plan.json"
SHARD_SIZE = 48


def verdict_of(value) -> str:
    """Extract the verdict string from a submit_and_gate entry.

    submit_and_gate returns {unit_id: (verdict, path)} — a dict of TUPLES. Comparing the
    tuple directly to "DONE" is silently always False, which is exactly what happened:
    six consecutive shards reported 0/48 DONE while every one of their artifacts passed
    both gates. Accept a bare string too, so a future change to either shape still counts
    correctly rather than failing closed-and-silent.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)) and value:
        return str(value[0])
    return ""


def load_units(plan_path: Path):
    """Expand the tiered plan into Units, preserving plan order (deterministic shards)."""
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    units = []
    for entry in data.get("plan", []):
        units.extend(research.research_units([entry["target"]], entry["lenses"]))
    return units, data


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_research.py")
    p.add_argument("--plan", default=str(PLAN))
    q = p.add_mutually_exclusive_group()
    q.add_argument("--quota-ok", dest="quota", action="store_const", const=True)
    q.add_argument("--quota-exhausted", dest="quota", action="store_const", const=False)
    p.add_argument("--shard", type=int, help="run a single shard by index")
    p.add_argument("--all", action="store_true", help="run every shard sequentially")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(quota=None)
    args = p.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.is_file():
        print(
            f"FAILED:research config error — no plan at {plan_path}. "
            f"Run: python e2e/build_research_targets.py"
        )
        return 2

    units, meta = load_units(plan_path)
    shards = research.shard(units, SHARD_SIZE)
    print(
        f"[research] {len(units)} units across {len(shards)} shards of <={SHARD_SIZE}"
    )
    print(f"[research] harness bundle : {meta.get('harness_bundle')}")
    print(f"[research] toolchain clone: {meta.get('toolchain_clone')}")

    if args.dry_run:
        for i, s in enumerate(shards):
            tiers = sorted({u.meta["target"].split("/")[0] for u in s})
            print(f"  shard {i:2}: {len(s):3} units  {','.join(tiers)[:60]}")
        print("SUCCESS:research dry-run (nothing submitted)")
        return 0

    # R9: every shard is a wave and every wave passes the ceiling. quota=None refuses.
    ceiling = ceiling_mod.DEFAULT
    ok, reason = ceiling_mod.check_wave(SHARD_SIZE, ceiling, args.quota)
    if not ok:
        print(f"FAILED:research refused by wave ceiling — {reason}")
        return 1

    if args.shard is None and not args.all:
        print("FAILED:research pick --shard N, --all, or --dry-run")
        return 2

    targets = range(len(shards)) if args.all else [args.shard]
    for i in targets:
        if not 0 <= i < len(shards):
            print(f"FAILED:research shard {i} out of range 0..{len(shards) - 1}")
            return 2

    from harness.lanes import run_E  # noqa: PLC0415 — imported late; touches the rail

    worst = 0
    for i in targets:
        s = shards[i]
        print(f"\n=== shard {i}/{len(shards) - 1}: {len(s)} units ===")
        verdicts = run_E.submit_and_gate(s, f"research-shard{i}")
        # submit_and_gate returns {unit_id: (verdict, path)} — a dict of TUPLES, not of
        # strings. Comparing the tuple to "DONE" is silently always False, which reported
        # 0/48 DONE for six consecutive shards whose artifacts all passed both gates.
        done = sum(1 for v in (verdicts or {}).values() if verdict_of(v) == "DONE")
        print(
            f"{'SUCCESS' if done == len(s) else 'PARTIAL'}:research shard{i} {done}/{len(s)} DONE"
        )
        if done != len(s):
            worst = 1
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
