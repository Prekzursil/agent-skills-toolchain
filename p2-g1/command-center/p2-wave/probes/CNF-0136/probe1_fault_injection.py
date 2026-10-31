#!/usr/bin/env python3
"""CNF-0136 probe1 - fault injection against the live scheduler.

Central invariant: kill / crash / 429 storm / timeout / duplicate map to
BLOCKED with a named prerequisite - never CONFIRMED, never REFUTED. Every
scenario row is compared cellwise to induced-records.json. Rebuilt
2026-10-26 (wave-3 shard 7) after the original probe tree was lost; the
scheduler under test is the original module, untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))
OUT = REPO / "command-center/receipts/CNF-0136.json"
FIXTURE = REPO / "command-center/confirmation/cnf0136/induced-records.json"
UNIT = "CNF-0136"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

from cnf0136.record import mint_record_id  # noqa: E402
from cnf0136.scheduler import (  # noqa: E402
    ConfirmationQueueScheduler,
    Job,
    RunnerEvent,
    mark_in_flight,
)
from cnf0136.taxonomy import map_fault  # noqa: E402


def build_sched():
    return ConfirmationQueueScheduler(arrival_rate_hz=10.0)


def scenario(job_id_wave, claim, kind, evidence=""):
    s = build_sched()
    job = Job(claim_id=claim, confirmer={"id": "cnf0136-probe", "vendor": "local"},
              wave=job_id_wave)
    s.dispatch(job, RunnerEvent(kind=kind, evidence=evidence))
    return s, job


def cellwise(rec, row):
    """Compare the live record against the on-disk induced row."""
    diffs = []
    for k in ("verdict", "fault_class", "named_prerequisite",
              "quota_posture", "job_id", "claim_id"):
        if rec.get(k) != row.get(k):
            diffs.append(k + ": " + repr(rec.get(k)) + " vs " + repr(row.get(k)))
    return diffs


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    check(doc.get("unit_id") == UNIT, "unit_id matches catalog unit")
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "artifact not self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact non-empty")
    check(OUT.stat().st_size >= int(doc.get("min_bytes_threshold") or 0),
          "artifact above min_bytes_threshold")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel present in artifact text")
    induced = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # arrival_rate_hz is a required scheduler input (spec:10577-10578)
    for bad in (None, 0, -1.0):
        try:
            ConfirmationQueueScheduler(arrival_rate_hz=bad)
            check(False, "arrival_rate_hz=" + repr(bad) + " rejected")
        except ValueError:
            check(True, "arrival_rate_hz=" + repr(bad) + " rejected")
    # ---- fault scenarios, cellwise vs induced-records.json ----
    scenarios = [
        ("kill", "claim-kill", "kill", "runner SIGKILLed mid-stream"),
        ("crash", "claim-crash", "crash", "runner crashed: stream-eof"),
        ("storm", "claim-429-0", "http-429", "HTTP 429 storm"),
        ("to", "claim-timeout", "timeout", "deadline 30s exceeded"),
    ]
    for wave, claim, kind, ev in scenarios:
        s, job = scenario(wave, claim, kind, ev)
        recs = s.store.records()
        if len(recs) != 1:
            check(False, "single record for " + kind)
            continue
        rec = recs[0]
        key = {"kill": "severed-stream", "crash": "runner-crash-as-severed-stream",
               "storm": "quota-429-storm", "to": "timeout-<n>s"}[wave]
        row = induced[key]
        d = cellwise(rec, row)
        check(not d, "live " + kind + " record matches induced row cellwise",
              "; ".join(d))
        want_id = row.get("record_id")
        check(rec["record_id"] == want_id,
              "record id mint matches induced row: " + kind,
              "got " + rec["record_id"][:12] + " want " + str(want_id)[:12])
        check(rec["verdict"] == "BLOCKED", "infra event maps to BLOCKED: " + kind)
    # duplicate dispatch while in flight (twin dispatch of a live job)
    s = build_sched()
    job = Job(claim_id="claim-dup", confirmer={"id": "c", "vendor": "local"}, wave="dup")
    mark_in_flight(s, job)
    r2 = s.dispatch(job, RunnerEvent(kind="healthy", claim_verdict="CONFIRMED",
                                     discrepancies=["would-have-confirmed"]))
    check(r2["verdict"] == "BLOCKED" and r2["fault_class"] == "duplicate-dispatch",
          "duplicate dispatch parks as BLOCKED duplicate-dispatch",
          r2["verdict"] + "/" + str(r2["fault_class"]))
    check(r2["named_prerequisite"] == "dedupe-confirmation-job-id",
          "duplicate parks with named prerequisite dedupe-confirmation-job-id")
    check(r2["record_id"] == induced["duplicate-dispatch"]["record_id"],
          "duplicate record id matches induced row")
    check(r2["discrepancies"] == ["would-have-confirmed"],
          "duplicate record carries the would-have-confirmed discrepancy")

    # 429 storm burst: 8 jobs, exactly 100ms stagger gaps
    sb = build_sched()
    jobs = [Job(claim_id="claim-429-%d" % i, confirmer={"id": "c", "vendor": "local"},
                wave="storm") for i in range(8)]
    batch = sb.dispatch_batch(jobs, lambda j: RunnerEvent(kind="http-429",
                                                          evidence="429 storm"))
    gaps = [batch[i]["scheduled_at_ms"] - batch[i - 1]["scheduled_at_ms"]
            for i in range(1, 8)]
    check(gaps == [100] * 7 and batch[0]["scheduled_at_ms"] == 0,
          "burst stagger slots are exactly [0,100,...,700]", str(gaps))
    check(sb.stagger_interval_ms("any") == 100, "stagger interval is 100ms at 10Hz")
    check(all(r["verdict"] == "BLOCKED" for r in batch),
          "all 8 burst records BLOCKED (never REFUTED)")
    check(all(r["quota_posture"] == "NOT-CHECKED" for r in batch),
          "unmeasurable quota emitted as NOT-CHECKED, never a number")
    burst_rows = induced["quota_429_storm_burst"]
    ids_live = [r["record_id"] for r in batch]
    ids_want = [r["record_id"] for r in burst_rows]
    check(ids_live == ids_want, "burst record ids match induced burst rows in order")
    for live, row in zip(batch, burst_rows):
        d = cellwise(live, row)
        check(not d, "burst row cellwise match", "; ".join(d))

    # every infra record in the fixture is BLOCKED, never CONFIRMED/REFUTED
    infra_bad = []
    for key, row in induced.items():
        rows = row if isinstance(row, list) else [row]
        for r in rows:
            if r.get("fault_class") and r.get("verdict") != "BLOCKED":
                infra_bad.append(key)
    check(not infra_bad, "no induced infra record carries a non-BLOCKED verdict",
          str(infra_bad))

    report = {
        "probe": "probe1-fault-injection",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "checks": checks,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 fault injection maps every infra fault to BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
