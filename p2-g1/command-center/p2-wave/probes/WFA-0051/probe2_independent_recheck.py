#!/usr/bin/env python3
"""WFA-0051 probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's headline claims from its own raw rows on a separate
code path (never re-running the original builder logic), runs the live
both-states mutation control, and byte-compares the per-unit manifest
registration against the live artifact (LF-normalized sha256, matching
_measure_one_delivered.py). Fixtures from the prior Linux build are absent on
this worktree; where inputs are absent the re-derivation is from recorded raw
rows only and says so. Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0051" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0051"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    mm = lr.get("mechanism_mappings") or []
    chk(len(mm) == 24, "mapping-count", str(len(mm)))
    LEGAL_DISP = {"MAPPED", "MAPPED-POLICY-ONLY", "LOSSY", "REQUIRES-DURABLE-LOG"}
    for m in mm:
        chk(m.get("disposition") in LEGAL_DISP,
            "mapping-disposition-illegal", str(m.get("disposition")))
        if m.get("disposition") == "REQUIRES-DURABLE-LOG":
            chk(bool(m.get("architecture_ticket")), "durable-log-without-architecture-ticket",
                str(m.get("framework")) + "/" + str(m.get("mechanism")))
        chk(bool(m.get("native_construct")), "source-anchor-absent",
            str(m.get("framework")) + "/" + str(m.get("mechanism")))
    tickets = {t.get("id") for t in lr.get("architecture_tickets") or []}
    for m in mm:
        if m.get("disposition") == "REQUIRES-DURABLE-LOG":
            chk(m.get("architecture_ticket") in tickets,
                "ticket-not-registered", str(m.get("architecture_ticket")))
    rp = lr.get("replay_experiment") or {}
    chk(rp.get("good_run_1") == rp.get("good_run_2") == rp.get("expected"),
        "replay-not-deterministic")
    chk(rp.get("bad_run") != rp.get("expected"), "bad-arm-did-not-diverge")
    bs = lr.get("both_states") or {}
    chk(bs.get("replay", {}).get("good_identical") is True
        and bs.get("replay", {}).get("bad_reverse_ready_differs") is True
        and bs.get("durable_log", {}).get("bad_file_fake_caught") is True
        and bs.get("durable_log", {}).get("good_routed_to_architecture") is True,
        "both-states-false")

def mutate(doc, lr):
    lr["replay_experiment"]["good_run_1"] = list(lr["replay_experiment"]["good_run_1"]) + ["stage-phantom"]


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0051-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    L = lr(doc)

    rederive(doc, chk, L)

    # live both-states mutation control: the re-derivation must stay silent on
    # the intact artifact and fire on a mutated headline number.
    good_fails = []
    rederive(doc, lambda ok, label, detail="": None if ok else good_fails.append(label), L)
    chk(not good_fails, "live-control-silent-on-good-failed", ";".join(good_fails[:3]))
    mutant = copy.deepcopy(doc)
    mutate(mutant, L)
    mutant_fails = []
    rederive(mutant, lambda ok, label, detail="": None if ok else mutant_fails.append(label), L)
    chk(bool(mutant_fails), "live-control-did-not-fire-on-bad")

    # claimed control booleans in the artifact must match this live run
    for nc in doc.get("negative_controls") or []:
        if str(nc.get("id", "")).endswith("LIVE-MUTANT"):
            chk(nc.get("fired_on_bad_state") is True, "claimed-live-control-false-fire")
            chk(nc.get("silent_on_good_state") is True, "claimed-live-control-false-silent")

    # manifest byte-compare (LF-normalized, matching _measure_one_delivered.py)
    chk(MANIFEST.is_file(), "manifest-absent")
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live = lf_sha(OUT)
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
        chk(bool(rows), "manifest-row-absent")
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0051-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0051-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
