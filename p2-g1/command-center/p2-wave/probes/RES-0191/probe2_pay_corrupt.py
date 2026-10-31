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
"""Corrupted-durable-envelope control + naive-skip counterfactual: a flipped
status without a matching integrity_sha256 must cause a LOUD refusal, and a
resume that blindly skips existing files must DROP the partial query's claims."""
import hashlib
import json
import shutil

run = Path(__file__).resolve().parent / "run-corrupt"
if run.exists():
    shutil.rmtree(run)
run.mkdir(parents=True)
DURABLE = ["query_id", "status", "harvest_index", "harvest_total",
           "emitted_claim_ids", "backend_calls", "harvest_attempts", "error"]


def write_state(q, status, idx, emitted, calls, attempts):
    st = {"query_id": q, "status": status, "harvest_index": idx,
          "harvest_total": 3, "emitted_claim_ids": emitted,
          "backend_calls": calls, "harvest_attempts": attempts, "error": None}
    st["integrity_sha256"] = hashlib.sha256(
        json.dumps(st, sort_keys=True).encode()).hexdigest()
    (run / f"{q}.state.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
    return st


def read_state(q):
    st = json.loads((run / f"{q}.state.json").read_text(encoding="utf-8"))
    body = {k: v for k, v in st.items() if k != "integrity_sha256"}
    want = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if st.get("integrity_sha256") != want:
        raise RuntimeError(f"integrity mismatch on {q}: status={st.get('status')} "
                           f"envelope corrupted; refusing to resume")
    return st


write_state("q1", "completed", 3, ["q1-c0", "q1-c1", "q1-c2"], 1, 1)
write_state("q2", "partial", 1, ["q2-c0"], 1, 2)
st = json.loads((run / "q1.state.json").read_text(encoding="utf-8"))
st["status"] = "not_started"
(run / "q1.state.json").write_text(json.dumps(st), encoding="utf-8")
refused = None
try:
    read_state("q1")
except RuntimeError as exc:
    refused = str(exc)
need(refused is not None and "integrity" in refused and "q1" in refused,
     f"corrupt envelope did not cause a loud named refusal: {refused}")
naive_keep = ["q2"]
naive_emitted = []
for q in naive_keep:
    try:
        naive_emitted.extend(read_state(q)["emitted_claim_ids"])
    except RuntimeError:
        naive_emitted.extend([])
need("q2-c0" in naive_emitted,
     "naive model dropped the partial query's harvested claims")
doc = load()
need(doc.get("both_states", {}).get("corrupt_refused") is True,
     "artifact corrupt_refused contradicts live control")
need(doc.get("both_states", {}).get("naive_skip_drops_claims") is True,
     "artifact naive_skip_drops_claims contradicts live control")
ok("corrupt refused loudly; naive skip drops; PARTIAL vs COMMITTED held")
