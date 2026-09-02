#!/usr/bin/env python3
"""Probe 1: stale advisory GREEN is STALE/DECAYED and re-run (both-states).

BAD: naive cache reuses last week's GREEN.
GOOD: decay-aware auditor labels STALE, re-runs against today's advisory DB.
FRESH (within TTL): reuse is allowed; detector stays silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import runner  # noqa: E402
import supply_chain as S  # noqa: E402

OUT = HERE / "probe1-stale-advisory.raw.json"
NOW = 1_700_000_000


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0240-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, sort_keys=True, default=str)[:2000])
    return 1


def main() -> int:
    registered = contract.register_all()
    if registered["rejected_count"] or "wf.engineering.dependency-supply-chain-audit" not in registered["accepted"]:
        return fail("blueprint-not-registered", registered)

    lock = S.load_lockfile()
    db_today = S.load_advisory_db()
    db_prior = {"db_epoch": NOW - 8 * 86400, "advisories": []}

    stored_green = S.scan_lockfile(lock, db_prior, now_epoch=NOW - 8 * 86400)
    if stored_green["verdict"] != "GREEN" or stored_green["finding_count"] != 0:
        return fail("prior-scan-not-green", stored_green)

    live_stale = S.audit(stored_green, now_epoch=NOW, lockfile=lock, advisory_db=db_today)
    if live_stale.get("classification") != "STALE" or not live_stale.get("decayed"):
        return fail("stale-not-decayed", live_stale)
    if live_stale.get("action") != "RE-RUN" or live_stale.get("reused") or not live_stale.get("re_run"):
        return fail("stale-not-rerun", live_stale)
    if live_stale.get("verdict") != "RED":
        return fail("rerun-did-not-observe-live-advisory", live_stale)
    live_gate = S.reuse_gate(live_stale, stored_green, now_epoch=NOW)
    if not live_gate["ok"] or live_gate["fired"]:
        return fail("live-stale-gate-fired", live_gate)

    naive = S.naive_reuse(stored_green, now_epoch=NOW)
    naive_gate = S.reuse_gate(naive, stored_green, now_epoch=NOW)
    if naive_gate["ok"] or not naive_gate["fired"] or naive_gate["reason"] != "stale-green-reused":
        return fail("naive-reuse-not-caught", {"naive": naive, "gate": naive_gate})

    fresh_scan = S.scan_lockfile(lock, db_today, now_epoch=NOW - 60)
    fresh_live = S.audit(fresh_scan, now_epoch=NOW, lockfile=lock, advisory_db=db_today)
    if fresh_live.get("classification") != "FRESH" or fresh_live.get("action") != "ACCEPT-FRESH":
        return fail("fresh-not-accepted", fresh_live)
    fresh_gate = S.reuse_gate(fresh_live, fresh_scan, now_epoch=NOW)
    if not fresh_gate["ok"] or fresh_gate["fired"]:
        return fail("fresh-gate-fired", fresh_gate)

    smokes = runner.smoke_all()
    if not smokes["ok"]:
        return fail("smoke-all", smokes)

    doc = {
        "pass": True,
        "probe": "probe1-stale-advisory",
        "unit_id": "IMP-0240",
        "now_epoch": NOW,
        "ttl_seconds": S.TTL_BY_CLASS["advisory-live"],
        "injected_clock": True,
        "wall_clock_consulted": False,
        "stored_green_age_seconds": 8 * 86400,
        "live_stale": {
            "classification": live_stale["classification"],
            "decayed": live_stale["decayed"],
            "action": live_stale["action"],
            "re_run": live_stale["re_run"],
            "reused": live_stale["reused"],
            "prior_verdict": live_stale["prior_verdict"],
            "verdict": live_stale["verdict"],
            "fresh_finding_count": live_stale["fresh_scan"]["finding_count"],
        },
        "naive_reuse_caught": True,
        "fresh_accepted": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "blueprints_registered": registered["accepted"],
        "smokes_ok": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        "stale=STALE decayed=True rerun=True naive_caught=True "
        "fresh=ACCEPT-FRESH smokes_ok=True"
    )
    print("SUCCESS:IMP-0240-probe1 stale advisory scan re-run, never reused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
