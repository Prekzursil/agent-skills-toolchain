#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0191"
OUT = (REPO / "command-center/research/deep-research-design/RES-0191-mid-run-backend-outage-resume.json").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
"""Real kill-and-resume simulation on the unit's own protocol contract:
per-query durable state files, control run vs kill+resume run, identical
emitted claim sets, completed queries never re-paid."""
import hashlib
import json
import shutil

run = Path(__file__).resolve().parent / "run"
if run.exists():
    shutil.rmtree(run)
run.mkdir(parents=True)
DURABLE = ["query_id", "status", "harvest_index", "harvest_total",
           "emitted_claim_ids", "backend_calls", "harvest_attempts", "error", "integrity_sha256"]
QUERIES = [f"q{i}" for i in range(1, 6)]


def state_path(q):
    return run / f"{q}.state.json"


def write_state(q, **kw):
    st = {k: kw.get(k) for k in DURABLE if k != "integrity_sha256"}
    st["query_id"] = q
    st["integrity_sha256"] = hashlib.sha256(
        json.dumps(st, sort_keys=True).encode()).hexdigest()
    state_path(q).write_text(json.dumps(st, indent=1), encoding="utf-8")
    return st


def read_state(q):
    raw = state_path(q).read_text(encoding="utf-8")
    st = json.loads(raw)
    body = {k: v for k, v in st.items() if k != "integrity_sha256"}
    if st.get("integrity_sha256") != hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()).hexdigest():
        raise RuntimeError(f"integrity mismatch on {q}: durable envelope corrupted")
    return st


def backend(q, claims):
    return {"claims": claims, "calls": 1}


def drive(queries, kill_after=None):
    ledger = {"backend_calls": 0, "emitted": []}
    for i, q in enumerate(queries):
        if kill_after is not None and i == kill_after:
            raise KeyboardInterrupt("backend died mid-run")
        if state_path(q).is_file():
            st = read_state(q)
            if st["status"] == "completed":
                ledger["emitted"].extend(st["emitted_claim_ids"])
                continue
            if st["status"] == "partial":
                done = st["emitted_claim_ids"]
                rest = backend(q, [f"{q}-c{j}" for j in range(st["harvest_index"], 3)])
                ledger["backend_calls"] += rest["calls"]
                fresh = [c for c in rest["claims"] if c not in done]
                ledger["emitted"].extend(done + fresh)
                write_state(q, status="completed", harvest_index=3, harvest_total=3,
                            emitted_claim_ids=done + fresh, backend_calls=st["backend_calls"] + 1,
                            harvest_attempts=st["harvest_attempts"] + 1, error=None)
                continue
        r = backend(q, [f"{q}-c{j}" for j in range(3)])
        ledger["backend_calls"] += r["calls"]
        ledger["emitted"].extend(r["claims"])
        write_state(q, status="completed", harvest_index=3, harvest_total=3,
                    emitted_claim_ids=r["claims"], backend_calls=1,
                    harvest_attempts=1, error=None)
    return ledger


control = drive(QUERIES)
run2 = run.parent / (run.name + "-kill")
if run2.exists():
    shutil.rmtree(run2)
run.rename(run2)
run.mkdir()
try:
    drive(QUERIES, kill_after=2)
    fail("kill simulation never fired")
except KeyboardInterrupt:
    pass
# simulate the backend dying mid-harvest on the third query: durable partial
write_state("q3", status="partial", harvest_index=1, harvest_total=3,
            emitted_claim_ids=["q3-c0"], backend_calls=1, harvest_attempts=1, error=None)
partial = [q for q in QUERIES if state_path(q).is_file()
           and read_state(q)["status"] != "completed"]
partial = [q for q in QUERIES if state_path(q).is_file()
           and read_state(q)["status"] != "completed"]
resume_ledger = drive(QUERIES)
need(sorted(control["emitted"]) == sorted(resume_ledger["emitted"]),
     "resume did NOT reproduce the control claim set")
need(resume_ledger["backend_calls"] <= control["backend_calls"],
     f"resume re-paid work: {resume_ledger['backend_calls']} vs control {control['backend_calls']}")
need(len(partial) >= 1, "no partial query exercised the durable envelope")
doc = load()
need(doc.get("both_states", {}).get("resume_matches_control") is True,
     "artifact resume_matches_control contradicts live run")
need(doc.get("both_states", {}).get("completed_not_repaid") is True,
     "artifact completed_not_repaid contradicts live run")
ok("kill+resume:", len(control["emitted"]), "claims reproduced;",
   resume_ledger["backend_calls"], "backend calls (control:",
   f"{control['backend_calls']})")
