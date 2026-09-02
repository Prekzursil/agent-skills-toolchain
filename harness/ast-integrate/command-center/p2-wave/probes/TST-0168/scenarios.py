"""Live scenarios for TST-0168: both-states, race amplification, mutants."""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))

import handled_ledger as HL  # noqa: E402

SEED = 168
N_RACE = 20
ITEMS = HL.default_items(8)


def _gold(base: Path) -> dict[str, Any]:
    wf = HL.make_workflow(base / "gold", ITEMS)
    wf.run()
    inv = HL.inspect(wf.ledger)
    expected = [HL.child_id_for(i) for i in ITEMS]
    receipts_ok = all(inv["receipts"].get(cid) == 1 for cid in expected)
    return {
        "derived_ids": inv["derived_ids"],
        "expected_ids": expected,
        "receipts": inv["receipts"],
        "receipt_total": inv["receipt_total"],
        "event_count": inv["event_count"],
        "ok": bool(
            inv["ok"]
            and inv["derived_ids"] == expected
            and receipts_ok
            and inv["unowned"] == []
        ),
    }


def _resume_from(base: Path, name: str, stop_before: int | None) -> dict[str, Any]:
    wf = HL.make_workflow(base / name, ITEMS)
    wf.run(stop_before=stop_before)
    # Crash: drop the in-memory workflow, keep only the file.
    path = wf.ledger.path
    ledger = HL.HandledLedger(path)
    wf2 = HL.DynamicFanOut(ledger, items=list(ITEMS))
    result = wf2.resume()
    gold_ids = [HL.child_id_for(i) for i in ITEMS]
    final = result["final"]
    receipts_ok = all(final["receipts"].get(cid) == 1 for cid in gold_ids)
    no_dup = not final["dup_receipts"] and not final["dup_executes"]
    no_unowned = final["unowned"] == []
    children_equal = result["children_equal"]
    final_ids_ok = final["derived_ids"] == gold_ids
    return {
        "stop_before": stop_before,
        "ticks_total": len(wf2.plan()),
        "children_before": result["children_before"],
        "children_after": result["children_after"],
        "children_equal": children_equal,
        "spawns_created_on_resume": result["spawns_created_on_resume"],
        "claims_on_resume": result["claims_on_resume"],
        "final_ids": final["derived_ids"],
        "final_receipts": final["receipts"],
        "final_unowned": final["unowned"],
        "dup_receipts": final["dup_receipts"],
        "dup_executes": final["dup_executes"],
        "receipt_total": final["receipt_total"],
        "ok": bool(
            children_equal
            and final_ids_ok
            and receipts_ok
            and no_dup
            and no_unowned
        ),
    }


def run_both_states(base: Path) -> dict[str, Any]:
    gold = _gold(base)
    wf_probe = HL.make_workflow(base / "plan", ITEMS)
    first_spawn = wf_probe.first_spawn_tick()
    n_ticks = len(wf_probe.plan())
    before_fanout = _resume_from(base, "before-fanout", first_spawn)
    after_complete = _resume_from(base, "after-complete", n_ticks)
    # After-complete resume must not add receipts.
    gold_receipts = gold["receipt_total"]
    after_receipts = after_complete["receipt_total"]
    no_extra_receipts = after_receipts == gold_receipts
    after_complete["no_extra_receipts"] = no_extra_receipts
    after_complete["ok"] = bool(after_complete["ok"] and no_extra_receipts)
    ok = bool(gold["ok"] and before_fanout["ok"] and after_complete["ok"])
    return {
        "gold": gold,
        "before_fanout": before_fanout,
        "after_complete": after_complete,
        "first_spawn_tick": first_spawn,
        "n_ticks": n_ticks,
        "ok": ok,
    }


def race_ticks() -> tuple[list[int], int, int]:
    plan = HL.tick_plan(ITEMS)
    first = next(i for i, t in enumerate(plan) if t[0] == "spawn")
    last = max(i for i, t in enumerate(plan) if t[0] == "receipt")
    interior = list(range(first, last + 1))
    if len(interior) < N_RACE:
        raise RuntimeError(f"need {N_RACE} interior ticks, have {len(interior)}")
    points = sorted(random.Random(SEED).sample(interior, N_RACE))
    return points, first, last


def run_race(base: Path) -> dict[str, Any]:
    gold = _gold(base)
    points, first, last = race_ticks()
    rows: list[dict[str, Any]] = []
    all_ok = True
    for i, tick in enumerate(points):
        row = _resume_from(base, f"race-{i:02d}-t{tick}", tick)
        row["tick"] = tick
        match_gold = row["final_ids"] == gold["derived_ids"]
        row["match_gold"] = match_gold
        row["ok"] = bool(row["ok"] and match_gold)
        if not row["ok"]:
            all_ok = False
        rows.append(row)
    return {
        "seed": SEED,
        "n": len(points),
        "ticks": points,
        "first_spawn_tick": first,
        "last_receipt_tick": last,
        "gold_ids": gold["derived_ids"],
        "rows": rows,
        "ok": bool(all_ok and gold["ok"] and len(points) == N_RACE),
    }


def mutant_skip_claim(base: Path) -> dict[str, Any]:
    wf = HL.make_workflow(base / "mutant-skip-claim", ITEMS)
    first_claim = next(i for i, t in enumerate(wf.plan()) if t[0] == "claim")
    wf.run(stop_before=first_claim)
    ledger = HL.HandledLedger(wf.ledger.path)
    wf2 = HL.DynamicFanOut(ledger, items=list(ITEMS))
    result = wf2.resume(claim=False, continue_run=False)
    inv = result["after_rederive"]
    fired = bool(inv["unowned"])
    return {
        "stop_before": first_claim,
        "unowned": inv["unowned"],
        "fired_on_bad": fired,
        "ok": fired,
        "detail": "resume without claim leaves spawned children unowned",
    }


def mutant_double_receipt(base: Path) -> dict[str, Any]:
    wf = HL.make_workflow(base / "mutant-double-receipt", ITEMS)
    wf.run()
    cid = HL.child_id_for(ITEMS[0])
    refused = False
    try:
        wf.ledger.append(
            {
                "kind": "child_receipt",
                "tick": None,
                "child_id": cid,
                "source": "mutant",
            }
        )
    except HL.DuplicateReceiptError:
        refused = True
    # Plant the duplicate anyway so the detector can see it.
    wf.ledger.append(
        {
            "kind": "child_receipt",
            "tick": None,
            "child_id": cid,
            "source": "mutant",
        },
        allow_duplicate_receipt=True,
    )
    inv = HL.inspect(wf.ledger)
    fired = bool(inv["dup_receipts"])
    return {
        "child_id": cid,
        "ledger_refused_second_receipt": refused,
        "dup_receipts": inv["dup_receipts"],
        "fired_on_bad": fired,
        "ok": bool(refused and fired),
        "detail": "second receipt is refused by the ledger and counted by inspect",
    }


def mutant_silent_on_good(base: Path) -> dict[str, Any]:
    """Same detectors must be silent on an uninterrupted good run."""
    gold = _gold(base / "mutant-good")
    unowned_silent = gold["ok"] and gold["derived_ids"]
    inv_path = base / "mutant-good" / "gold"
    wf = HL.make_workflow(inv_path, ITEMS)
    wf.run()
    inv = HL.inspect(wf.ledger)
    return {
        "unowned_silent": inv["unowned"] == [],
        "dup_silent": not inv["dup_receipts"] and not inv["dup_executes"],
        "ok": bool(inv["ok"] and unowned_silent),
    }


def run_mutants(base: Path) -> dict[str, Any]:
    skip = mutant_skip_claim(base)
    dup = mutant_double_receipt(base)
    good = mutant_silent_on_good(base)
    return {
        "skip_claim": skip,
        "double_receipt": dup,
        "silent_on_good": good,
        "ok": bool(skip["ok"] and dup["ok"] and good["ok"]),
    }


def run_all(base: Path) -> dict[str, Any]:
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    both = run_both_states(base / "both")
    race = run_race(base / "race")
    mutants = run_mutants(base / "mutants")
    ok = bool(both["ok"] and race["ok"] and mutants["ok"])
    return {
        "both_states": both,
        "race": race,
        "mutants": mutants,
        "n_items": len(ITEMS),
        "items": list(ITEMS),
        "ok": ok,
    }
