"""Run the SOTA corpus re-derivation on the 48-wide Databricks rail.

  python e2e/run_derive.py --dry-run
  python e2e/run_derive.py --shard 0 --quota-ok
  python e2e/run_derive.py --all --quota-ok

Replaces a local fan-out measured at ~37 min/result and width 7 (~31 h for what remains)
with Codex units at width 48, off-box, where neither RAM pressure nor a session death
touches the work. Quota is a judgement, not an API: omitting --quota-ok refuses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import ceiling as ceiling_mod  # noqa: E402
from harness.lanes import derive, research  # noqa: E402

PLAN = Path(__file__).resolve().parent / "_sota_workunits.json"
DONE = Path(__file__).resolve().parent / "_R_derive_done.json"
SHARD_SIZE = 48


def landed_on_dbfs() -> set[str]:
    """Unit ids whose artifact already exists on DBFS.

    Makes --all idempotent: a poller killed mid-programme (routine on this box) can be
    relaunched without resubmitting finished shards. Killing the poller never stops the
    remote job, so its artifacts are real work that must not be paid for twice.
    Returns an empty set on any failure -- unknown means "assume nothing landed", which
    costs a re-run rather than silently skipping unfinished work.
    """
    import os
    import subprocess

    try:
        r = subprocess.run(
            [
                "databricks",
                "fs",
                "ls",
                "dbfs:/tmp/R-derive/results",
                "--profile",
                "bolt-datascience",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
            env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
        return {
            ln.strip()[:-3]
            for ln in (r.stdout or "").splitlines()
            if ln.strip().endswith(".md")
        }
    except Exception:  # noqa: BLE001
        return set()


def _drain(limit_polls: int = 120) -> bool:
    """Block until OUR fan-out is idle.

    Counts only codex-fanout runs: this is a SHARED Bolt production workspace, so a
    workspace-wide active count returns fraud_driver / payment_method_payments and never
    reaches zero — gating on it once left the whole shard chain silently unlaunched.
    An unreadable probe returns -1, which is treated as BUSY, so two waves are never
    stacked onto a 48-slot rail.
    """
    import subprocess
    import time

    here = Path(__file__).resolve().parent
    for _ in range(limit_polls):
        r = subprocess.run(
            [sys.executable, str(here / "my_active_runs.py")],
            capture_output=True,
            text=True,
            timeout=200,
            check=False,
        )
        line = (r.stdout or "").strip().splitlines()[:1]
        if line and line[0].strip() == "0":
            return True
        time.sleep(30)
    return False


def load_pending(plan_path: Path, done_path: Path, *, check_dbfs: bool = True):
    """Units not already adjudicated locally OR already landed on DBFS."""
    entries = json.loads(plan_path.read_text(encoding="utf-8"))
    done = set()
    if done_path.is_file():
        try:
            done = set(json.loads(done_path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — a corrupt skip-list must not drop the run
            done = set()
    all_units = derive.derive_units([e for e in entries if e["id"] not in done])
    landed = landed_on_dbfs() if check_dbfs else set()
    pending = [u for u in all_units if u.id not in landed]
    if landed:
        print(
            f"[derive] {len(all_units) - len(pending)} unit(s) already on DBFS — skipping"
        )
    return pending, len(entries), len(done)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_derive.py")
    p.add_argument("--plan", default=str(PLAN))
    p.add_argument("--done", default=str(DONE))
    q = p.add_mutually_exclusive_group()
    q.add_argument("--quota-ok", dest="quota", action="store_const", const=True)
    q.add_argument("--quota-exhausted", dest="quota", action="store_const", const=False)
    p.add_argument("--shard", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(quota=None)
    args = p.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.is_file():
        print(f"FAILED:derive config error — no plan at {plan_path}")
        return 2

    # Drain BEFORE computing what is pending. A wave already in flight has not written its
    # artifacts yet, so computing the pending set first would re-queue the units it is
    # currently doing. Wait for the rail to go idle, then look at what actually landed.
    if not args.dry_run:
        print("[derive] waiting for the rail to drain before planning...")
        if not _drain():
            print(
                "FAILED:derive rail still busy after 60 min — not planning against a "
                "moving target"
            )
            return 1

    units, total, skipped = load_pending(
        plan_path, Path(args.done), check_dbfs=not args.dry_run
    )
    shards = research.shard(units, SHARD_SIZE) if units else []
    print(
        f"[derive] {total} corpus units; {skipped} already adjudicated locally; "
        f"{len(units)} pending across {len(shards)} shard(s) of <={SHARD_SIZE}"
    )

    if args.dry_run:
        for i, s in enumerate(shards):
            stale = sum(1 for u in s if u.meta.get("stale"))
            print(f"  shard {i}: {len(s):3} units ({stale} with a CHANGED target)")
        print("SUCCESS:derive dry-run (nothing submitted)")
        return 0

    if not shards:
        print("SUCCESS:derive nothing pending")
        return 0

    ok, reason = ceiling_mod.check_wave(
        min(SHARD_SIZE, len(units)), ceiling_mod.DEFAULT, args.quota
    )
    if not ok:
        print(f"FAILED:derive refused by wave ceiling — {reason}")
        return 1

    if args.shard is None and not args.all:
        print("FAILED:derive pick --shard N, --all, or --dry-run")
        return 2
    targets = range(len(shards)) if args.all else [args.shard]
    for i in targets:
        if not 0 <= i < len(shards):
            print(f"FAILED:derive shard {i} out of range 0..{len(shards) - 1}")
            return 2

    from harness.lanes import run_E  # noqa: PLC0415 — late: touches the rail

    worst = 0
    for i in targets:
        s = shards[i]
        if not _drain():
            print(
                f"FAILED:derive rail still busy after 60 min — refusing to stack shard {i}"
            )
            return 1
        print(f"\n=== derive shard {i}/{len(shards) - 1}: {len(s)} units ===")
        verdicts = run_E.submit_and_gate(s, f"derive-shard{i}")
        # A submit rejection is not a partial result — the cluster never ran. Abort the
        # whole chain rather than blindly firing the next shard at the same broken config.
        if verdicts and all(v[0] == "SUBMIT-FAILED" for v in verdicts.values()):
            print(
                f"FAILED:derive shard{i} submit rejected — aborting chain, no cluster ran"
            )
            return 2
        # submit_and_gate returns {id: (verdict, path)} — a dict of TUPLES. Comparing the
        # tuple to "DONE" is silently always False; that bug reported 0/48 for six
        # consecutive shards whose artifacts were fine.
        done_n = sum(
            1
            for v in (verdicts or {}).values()
            if (v[0] if isinstance(v, (tuple, list)) and v else v) == "DONE"
        )
        print(
            f"{'SUCCESS' if done_n == len(s) else 'PARTIAL'}:derive shard{i} "
            f"{done_n}/{len(s)} DONE"
        )
        if done_n != len(s):
            worst = 1
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
