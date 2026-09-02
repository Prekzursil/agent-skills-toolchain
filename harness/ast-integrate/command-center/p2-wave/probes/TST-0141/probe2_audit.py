#!/usr/bin/env python3
"""Named probe 2: independent permit-log audit + lock/CAS-removed mutation control.

Does not read SimBucket.tokens when scoring the log. Recomputes per-window
totals from issued permits, then confirms a mutant without CAS over-issues
and shrinks to a replayable schedule. The same colliding schedule is clean
on the CAS bucket.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import colliding_mutant_schedule, run_live_threads, run_mutation_control  # noqa: E402
from token_bucket import audit_permits, execute_schedule  # noqa: E402

ART = REPO / "command-center/receipts/TST-0141.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0141-probe2 {msg}")
    return 1


def main() -> int:
    mut = run_mutation_control()
    live = run_live_threads(atomic=True)
    live_audit = audit_permits(live["permit_log"], live["capacity"])

    rec = colliding_mutant_schedule()
    mutant_bucket, _actors, mutant_run = execute_schedule(
        rec.schedule, n_takers=2, capacity=1, mutant=True
    )
    mutant_audit = audit_permits(mutant_bucket.permit_dicts(), 1)

    cas_bucket, _cas_actors, cas_run = execute_schedule(
        rec.schedule, n_takers=2, capacity=1, mutant=False
    )
    cas_audit = audit_permits(cas_bucket.permit_dicts(), 1)

    summary = {
        "mutation_ok": mut["ok"],
        "padded_len": mut["padded_len"],
        "shrunk_len": mut["shrunk_len"],
        "shrunk_schedule": mut["shrunk_schedule"],
        "cas_control_ok": mut["cas_control_ok"],
        "live_ok": live["ok"],
        "live_granted": live["granted"],
        "live_tokens": live["tokens"],
        "live_audit": live_audit,
        "mutant_run_ok": mutant_run["ok"],
        "mutant_tokens": mutant_run["tokens"],
        "mutant_granted": mutant_run["granted"],
        "mutant_audit": mutant_audit,
        "cas_run_ok": cas_run["ok"],
        "cas_granted": cas_run["granted"],
        "cas_audit": cas_audit,
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str)[:8000])

    if not mut["ok"]:
        return fail(f"mutation control did not fire: {mut}")
    if mut["cas_control_ok"] is not True:
        return fail("CAS colliding schedule was not clean")
    if mut["shrunk_len"] >= mut["padded_len"]:
        return fail("shrinker did not shorten the padded counterexample")
    if live_audit.get("ok") is not True:
        return fail(f"independent live audit failed: {live_audit}")
    if live["granted"] > live["capacity"]:
        return fail("live threads over-issued")
    if live["tokens"] < 0:
        return fail("live threads went negative")
    if mutant_audit.get("ok") is True:
        return fail("independent audit of mutant log was silent (vacuous mutation)")
    if int(mutant_audit.get("total_granted") or 0) <= 1:
        return fail("mutant did not over-issue in the log")
    if cas_audit.get("ok") is not True:
        return fail(f"CAS log audit failed: {cas_audit}")
    if int(cas_run["granted"]) > 1:
        return fail("CAS colliding schedule over-issued")
    if mutant_run["ok"]:
        return fail("mutant colliding run was reported ok")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:TST-0141" not in text:
            return fail("sentinel absent")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if not (doc.get("mutation") or {}).get("ok"):
            return fail("receipt mutation.ok is not true")

    print(
        f"mutant_granted={mutant_run['granted']} mutant_tokens={mutant_run['tokens']} "
        f"shrunk_len={mut['shrunk_len']} live_granted={live['granted']} "
        f"live_audit_ok={live_audit['ok']} cas_granted={cas_run['granted']}"
    )
    print("SUCCESS:TST-0141-probe2 permit-log audit and CAS-removed mutation control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
