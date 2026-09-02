#!/usr/bin/env python3
"""TST-0104 probe 1: protected service survives; orphan reaped; reasons logged.

Live processes: agent-mail (health), live-but-idle session worker, genuine
orphan of a dead session. Under planted RSS ceiling the kill set excludes
the protected list; GET /health still returns 200 after the orphan is
SIGKILL'd. Below the ceiling the kill set is empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from scenario import run_live  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0104.json"
SENTINEL = "SUCCESS:TST-0104"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0104-probe1 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    return None


def test_protected_service_survives_the_guard(r: dict) -> str | None:
    d = r["mail_decision"]
    if d["action"] != r["spare"] or d["reason"] != r["expected_mail_reason"]:
        return f"mail not spared: {d}"
    if r["mail_pid"] in r["kill_set"] or r["kill_set_hits_protected"]:
        return f"kill set hit protected list: {r['kill_set']}"
    if not r["mail_alive_after"]:
        return "agent-mail pid gone after guard"
    if r["health_after_status"] != 200 or r["health_after_service"] != "agent-mail":
        return (
            f"health after guard status={r['health_after_status']} "
            f"service={r['health_after_service']}"
        )
    return None


def test_genuine_orphan_is_reaped(r: dict) -> str | None:
    idle = r["idle_decision"]
    orphan = r["orphan_decision"]
    if idle["action"] != r["spare"] or idle["reason"] != r["expected_idle_reason"]:
        return f"live-idle not spared: {idle}"
    if r["idle_death_proven"] or not r["idle_alive_after"]:
        return f"live-idle treated as dead: proven={r['idle_death_proven']}"
    if orphan["action"] != r["kill"] or orphan["reason"] != r["expected_orphan_reason"]:
        return f"orphan not selected: {orphan}"
    if not r["orphan_death_proven"]:
        return "orphan death not proven by two-signal AND"
    if r["orphan_alive_after"] or r["orphan_pid"] not in r["kill_set"]:
        return (
            f"orphan not reaped alive={r['orphan_alive_after']} "
            f"kill_set={r['kill_set']}"
        )
    if not r["below_ceiling_all_spare"] or r["below_ceiling_kill_set"]:
        return f"below-ceiling kill set not empty: {r['below_ceiling_kill_set']}"
    return None


def test_kill_selection_is_logged_with_a_reason_per_pid(r: dict) -> str | None:
    if not r["reasons_complete"]:
        return "kill log missing a pid or a reason"
    by_pid = {d["pid"]: d for d in r["report"]["decisions"]}
    for pid in (r["mail_pid"], r["idle_pid"], r["orphan_pid"]):
        if pid not in by_pid or not by_pid[pid].get("reason"):
            return f"no reason for pid {pid}"
    return None


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)
    r = run_live(apply=True)
    tests = [
        ("test_protected_service_survives_the_guard", test_protected_service_survives_the_guard),
        ("test_genuine_orphan_is_reaped", test_genuine_orphan_is_reaped),
        (
            "test_kill_selection_is_logged_with_a_reason_per_pid",
            test_kill_selection_is_logged_with_a_reason_per_pid,
        ),
    ]
    results = {}
    for name, fn in tests:
        msg = fn(r)
        if msg:
            return fail(f"{name}: {msg}")
        results[name] = "PASS"
    payload = {
        "pass": True,
        "probe": "probe1-protected-survives-orphan-reaped",
        "unit_id": "TST-0104",
        "tests": results,
        "mail_pid": r["mail_pid"],
        "idle_pid": r["idle_pid"],
        "orphan_pid": r["orphan_pid"],
        "kill_set": r["kill_set"],
        "protected_list": r["protected_list"],
        "kill_set_hits_protected": r["kill_set_hits_protected"],
        "health_after_status": r["health_after_status"],
        "health_after_service": r["health_after_service"],
        "mail_alive_after": r["mail_alive_after"],
        "idle_alive_after": r["idle_alive_after"],
        "orphan_alive_after": r["orphan_alive_after"],
        "mail_reason": r["mail_decision"]["reason"],
        "idle_reason": r["idle_decision"]["reason"],
        "orphan_reason": r["orphan_decision"]["reason"],
        "below_ceiling_kill_set": r["below_ceiling_kill_set"],
        "committed_as_bytes": r["pressure"]["committed_as_bytes"],
        "mem_available_bytes": r["pressure"]["mem_available_bytes"],
        "commit_is_not_working_set": r["pressure"]["commit_is_not_working_set"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "protected=SPARE orphan=KILL idle=SPARE health=200 "
        f"kill_set={r['kill_set']} protected_list={r['protected_list']}"
    )
    print("SUCCESS:TST-0104-probe1 protected service survived; orphan reaped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
