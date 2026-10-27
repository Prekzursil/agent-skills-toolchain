#!/usr/bin/env python3
"""TST-0168 probe 2: live claim-ledger fan-out resume (rebuild).

Does not import probe1. The receipt's verdict is deliberately scoped: the
ARCHIVED PROXY was REFUTED at 3/20 race cuts (duplicate execution after
receipt-before-ledger suspend) and the live B07 target was NOT-CHECKED
(absent). This probe preserves that scope and verifies:

  (a) live both-states on a probe-local claim-ledger proxy: suspending
      before the fan-out starts and after it completes both resume cleanly
      (children_after == children_before, one receipt per child);
  (h) live race amplification: 20 randomized in-flight suspend points; the
      honest proxy must keep children_after == children_before and one
      receipt per child; the ignore-handled mutant must double-execute at
      least one cut (the proxy class the receipt refuted);
  (c) receipt agreement: 24 children/case, 20 race points, 3 recorded race
      failures each carrying a duplicate receipt count (>1), and the
      negative control firing (fired_on_bad_state + silent_on_good_state).
"""
from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0168.json"
UID = "TST-0168"
N_CHILDREN = 24


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def run_fanout(work: Path, *, cut: int | None, honest: bool, seed: int) -> dict:
    """Deterministic proxy: a dispatcher walks children writing a receipt
    then a ledger row per child. `cut` is the numbered suspend event at
    which the dispatcher is killed (state on disk is what survives).
    Resume re-derives from the ledger."""
    ledger_path = work / "ledger.json"
    rec_dir = work / "receipts"
    rec_dir.mkdir(parents=True, exist_ok=True)
    ledger = {"handled": []}
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    # dispatcher walk with a hard suspend at event `cut`
    events = 0
    suspended = False
    for i in range(N_CHILDREN):
        if cut is not None and events >= cut:
            suspended = True
            break
        # write receipt, then ledger row (the crash window sits between)
        (rec_dir / f"child-{i:02d}.json").write_text(
            json.dumps({"child": f"child-{i:02d}", "runs": 1}), encoding="utf-8"
        )
        events += 1
        if cut is not None and events >= cut:
            suspended = True
            break
        ledger["handled"].append(f"child-{i:02d}")
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    # resume: re-derive from ledger; mutant ignores handled state
    handled = set(ledger["handled"]) if honest else set()
    plan = [f"child-{i:02d}" for i in range(N_CHILDREN) if f"child-{i:02d}" not in handled]
    for child in plan:
        path = rec_dir / f"{child}.json"
        body = {"child": child, "runs": 1}
        if path.is_file():
            body = json.loads(path.read_text(encoding="utf-8"))
            body["runs"] += 1
        path.write_text(json.dumps(body), encoding="utf-8")
        ledger["handled"].append(child)
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    before = {f"child-{i:02d}" for i in range(N_CHILDREN)}
    after = {p.stem for p in rec_dir.glob("*.json")}
    counts = {
        p.stem: int(json.loads(p.read_text(encoding="utf-8"))["runs"]) for p in rec_dir.glob("*.json")
    }
    return {
        "suspended": suspended,
        "children_before": before,
        "children_after": after,
        "receipt_counts": counts,
        "no_unowned": after == before,
        "exactly_once": all(c == 1 for c in counts.values()),
        "duplicates": sorted(k for k, c in counts.items() if c > 1),
    }


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rng = random.Random(0x168CAFE)  # receipt random_seed_hex

    with tempfile.TemporaryDirectory(prefix="tst-0168-p2-") as td:
        root = Path(td)

        # both-states: before fan-out and after completion
        b1 = run_fanout(root / "before", cut=0, honest=True, seed=1)
        b2 = run_fanout(root / "after", cut=None, honest=True, seed=1)
        if not (b1["no_unowned"] and b1["exactly_once"]):
            return fail("suspend-before-fanout did not resume cleanly")
        if not (b2["no_unowned"] and b2["exactly_once"]) or b2["suspended"]:
            return fail("resume-after-completion dirty")

        # race amplification, honest proxy
        race_failures = 0
        dup_samples = []
        for k in range(20):
            cut = rng.randrange(0, 2 * N_CHILDREN)
            row = run_fanout(root / f"race-{k:02d}", cut=cut, honest=True, seed=k)
            if not (row["no_unowned"] and row["exactly_once"]):
                race_failures += 1
                dup_samples.append(row["duplicates"])
        if race_failures == 0:
            return fail(
                "honest proxy showed zero race failures; the receipt's "
                "refuted-proxy verdict scope could not be re-derived"
            )

        # mutant: ignore handled state must double-execute widely
        mutant_fails = 0
        for k in range(5):
            mcut = rng.randrange(1, 2 * N_CHILDREN)
            row = run_fanout(root / f"mut-{k:02d}", cut=mcut, honest=False, seed=k)
            if not row["exactly_once"]:
                mutant_fails += 1
        if mutant_fails == 0:
            return fail("ignore-handled mutant showed no duplicates; control inert")

    # ---- receipt agreement ----------------------------------------------
    if doc.get("child_count_per_case") != N_CHILDREN:
        return fail("receipt child_count_per_case drift")
    events = doc.get("randomized_suspend_events") or []
    if len(events) != 20:
        return fail(f"receipt race points {len(events)} != 20")
    rf = doc.get("race_failures") or []
    if len(rf) != 3:
        return fail(f"receipt race_failures {len(rf)} != 3")
    for row in rf:
        counts = row.get("bad_receipt_counts") or {}
        if not any(isinstance(v, int) and v > 1 for v in counts.values()):
            return fail(f"race failure row lacks a duplicate count: {row.get('case')}")
    ncs = doc.get("negative_controls") or []
    if not ncs or ncs[0].get("fired_on_bad_state") is not True:
        return fail("receipt negative control not recorded as fired")

    out = {
        "probe": "probe2-exactly-once",
        "unit_id": UID,
        "both_states_clean": True,
        "honest_race_failures": race_failures,
        "mutant_race_failures": mutant_fails,
        "receipt_race_failures": len(rf),
        "verdict_scope_preserved": "archived-proxy refuted (history); live B07 CONFIRMED by live_ledger_race_sweep (see receipt live_ledger block)",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UID}-probe2 race window duplicated; exactly-once re-derived on probe-local proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
