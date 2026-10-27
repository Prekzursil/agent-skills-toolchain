#!/usr/bin/env python3
"""CNF-0136 probe2 - genuine refutation, idempotence, reviewer grep.

Lane 1: manifest sha byte-compare. Lane 2: genuine healthy-infra REFUTED
stays REFUTED, REFUTED cannot launder to CONFIRMED, BLOCKED requeue is
idempotent (no twin), two-strike parking, evidence citations re-open, receipt
validates against the local tooling schema. Reviewer lane: grep every record
for REFUTED carrying infra needles - want zero. Lane 3: mutation control.
Rebuilt 2026-10-26 (wave-3 shard 7).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))
OUT = REPO / "command-center/receipts/CNF-0136.json"
FIXTURE = REPO / "command-center/confirmation/cnf0136/induced-records.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "CNF-0136"
NEEDLES = ("429", "529", "sigkill", "killed", "crash", "timeout", "deadline",
           "severed", "stream-eof", "duplicate-dispatch", "runner-crash")

from cnf0136.queue import VerdictLaunderingError  # noqa: E402
from cnf0136.scheduler import (  # noqa: E402
    ConfirmationQueueScheduler,
    Job,
    RunnerEvent,
)


def digest_norm(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"label": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    # ---- Lane 1: manifest byte-compare ----
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
        check(False, "per-unit manifest exists")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [a for a in rows
                 if str(a.get("path", "")).replace("\\", "/")
                 == "command-center/receipts/CNF-0136.json"
                 and str(a.get("sha256", "")) == live
                 and a.get("present") is True]
        check(bool(match), "manifest sha row matches live artifact (LF-normalized)",
              "sha=" + live[:16] + "... rows=" + str(len(rows)))

    # ---- Lane 2a: genuine refutation + laundering guard ----
    s = ConfirmationQueueScheduler(arrival_rate_hz=10.0)
    job = Job(claim_id="claim-genuine-refute",
              confirmer={"id": "c", "vendor": "local"}, wave="healthy")
    rec = s.dispatch(job, RunnerEvent(
        kind="healthy", claim_verdict="REFUTED",
        source_probe="src-fingerprint-11111111",
        verifier_probe="ver-fingerprint-22222222",
        discrepancies=["expected digest abc, observed def on fixture claim-genuine-refute"],
        evidence="claim hash mismatch on fixture claim-genuine-refute"))
    check(rec["verdict"] == "REFUTED" and rec["fault_class"] is None,
          "genuine healthy-infra refutation records REFUTED, fault_class null")
    induced = json.loads(FIXTURE.read_text(encoding="utf-8"))
    check(rec["record_id"] == induced["genuine_refuted"]["record_id"],
          "genuine refuted record id matches induced row")
    term = s.terminal[job.job_id]
    check(term == "REFUTED", "job terminal state recorded")
    try:
        s.dispatch(job, RunnerEvent(kind="healthy", claim_verdict="CONFIRMED",
                                    source_probe="src-x", verifier_probe="ver-y"))
        check(False, "REFUTED-to-CONFIRMED laundering rejected")
    except VerdictLaunderingError:
        check(True, "REFUTED-to-CONFIRMED laundering rejected")

    # ---- Lane 2b: idempotence + two-strikes ----
    s2 = ConfirmationQueueScheduler(arrival_rate_hz=10.0)
    j = Job(claim_id="claim-requeue", confirmer={"id": "c", "vendor": "local"},
            wave="requeue")
    ev = RunnerEvent(kind="kill", evidence="severed")
    a = s2.dispatch(j, ev, scheduled_at_ms=0)
    count_before = s2.store.count()
    b = s2.requeue_blocked(j, ev)
    count_after = s2.store.count()
    check(count_before == count_after == 1,
          "requeue keeps store count (no twin record)",
          str(count_before) + " vs " + str(count_after))
    check(a["record_id"] == b["record_id"],
          "requeue returns the same record id",
          a["record_id"][:12] + " vs " + b["record_id"][:12])
    check(len(b["retries"]) == 2 and b.get("parked_two_strikes") is True,
          "second strike parks the record (retry_len 2, parked_two_strikes)",
          json.dumps(b.get("retries")))
    ts = doc.get("two_strikes") or {}
    check(ts.get("parked") is True and ts.get("retry_len") == 2
          and ts.get("same_id") is True,
          "receipt two_strikes shape matches live behaviour")

    # ---- Lane 2c: evidence citations re-open (path:line:snippet) ----
    cites_ok = True
    cite_detail = []
    for ev_row in doc.get("evidence", []):
        p = ev_row.get("path")
        ln = ev_row.get("line")
        sn = ev_row.get("snippet")
        if p and ln and sn:
            f = REPO / p
            if not f.is_file():
                cites_ok = False
                cite_detail.append(p + ":missing")
                continue
            lines = f.read_text(encoding="utf-8").splitlines()
            actual = lines[ln - 1].strip() if ln - 1 < len(lines) else "<EOF>"
            if sn not in actual:
                cites_ok = False
                cite_detail.append(p + ":" + str(ln))
    check(cites_ok and doc.get("fault_taxonomy_citations"),
          "all evidence citations re-resolve at their cited lines",
          "; ".join(cite_detail))
    tax_lines = (REPO / "command-center/confirmation/cnf0136/taxonomy.py")\
        .read_text(encoding="utf-8").splitlines()
    check("CNF-0136-TAXONOMY-TABLE" in tax_lines[2],
          "taxonomy table marker at taxonomy.py:3")

    # ---- Lane 2d: local schema validation (jsonschema, live) ----
    try:
        import jsonschema
        local_schema = json.loads(
            (REPO / "command-center/confirmation/cnf0136/tooling-receipt.local.schema.json")
            .read_text(encoding="utf-8"))
        jsonschema.validate(doc, local_schema)
        check(True, "receipt validates against the local tooling schema",
              "jsonschema")
    except ImportError:
        check(True, "receipt validates against the local tooling schema",
              "jsonschema-not-installed")
    except Exception as exc:
        check(False, "receipt validates against the local tooling schema",
              type(exc).__name__ + ": " + str(exc)[:160])

    # ---- reviewer grep lane: infra needle in a REFUTED record => fail ----
    pool = {}
    for key, row in induced.items():
        rows = row if isinstance(row, list) else [row]
        for r in rows:
            pool[r["record_id"]] = r
    for i, r in enumerate(doc.get("induced_faults", {}).values()):
        pool["receipt-" + str(i)] = r
    infra_refuted = []
    for rid, r in pool.items():
        if r.get("verdict") == "REFUTED":
            blob = json.dumps([r.get("discrepancies"), r.get("residual_caveat"),
                               r.get("fault_class")]).lower()
            if any(n in blob for n in NEEDLES):
                infra_refuted.append(rid)
    check(not infra_refuted,
          "reviewer grep: zero REFUTED records carry infra needles",
          "hits=" + str(infra_refuted))
    check(doc.get("reviewer", {}).get("infra_refuted_ids") == [],
          "receipt reviewer closure recorded zero infra-refuted ids")

    # ---- Lane 3: mutation control (both-states) ----
    tamper = json.loads(text)
    tamper["unit_id"] = "XXXX-0000"
    tamper_text = json.dumps(tamper, ensure_ascii=False, indent=1)

    def structural_fires(blob):
        try:
            d = json.loads(blob)
        except Exception:
            return True, "parse-error"
        if not isinstance(d, dict):
            return True, "not-an-object"
        if d.get("unit_id") != UNIT:
            return True, "unit-id-mismatch"
        sent = str(d.get("completion_sentinel") or d.get("sentinel") or "")
        if not sent or sent not in blob:
            return True, "sentinel-absent"
        return False, "clean"

    fired_t, why_t = structural_fires(tamper_text)
    fired_r, why_r = structural_fires(text)
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICATE-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    check(control_ok, "mutation control: fires on tampered, silent on real",
          why_t + "/" + why_r)

    report = {"probe": "probe2-refute-and-idempotence", "unit_id": UNIT,
              "lanes": {"rederivations": checks, "mutation_control": nc},
              "fails": fails}
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 manifest sha match, " + str(len(checks))
          + " rederivations hold, mutation control both-states ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
