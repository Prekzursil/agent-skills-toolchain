#!/usr/bin/env python3
"""WFA-0048 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0048-adapter-slash-command.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0048" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0048"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    cl = lr.get("classifications") or []
    na = sum(1 for c in cl if c.get("verdict") == "ALIAS")
    no = sum(1 for c in cl if c.get("verdict") == "OWN-PROCEDURE")
    chk(na + no == len(cl) == 31, "classification-partition-mismatch",
        "alias=%s own=%s total=%s" % (na, no, len(cl)))
    fc = lr.get("floor_carry") or {}
    chk(fc.get("alias_count") == na and fc.get("own_procedure_count") == no
        and fc.get("collapsed_count") == no and fc.get("raw_count") == 31,
        "floor-carry-vs-recount-mismatch",
        "claimed=%s/%s recount=%s/%s" % (fc.get("alias_count"), fc.get("own_procedure_count"), na, no))
    edges = lr.get("alias_edges") or []
    chk(len(edges) == na, "alias-edge-count-mismatch", "edges=%s alias=%s" % (len(edges), na))
    chk(all(e.get("added_stage_count") == 0 for e in edges),
        "alias-edge-adds-stages")
    proofs = lr.get("independent_alias_proofs") or []
    chk(len(proofs) == na and all(p.get("alias_ok") is True and p.get("added_stage_count") == 0
                                  for p in proofs),
        "independent-alias-proof-failed")
    ir = lr.get("ir_records") or []
    chk(len(ir) == 31 and all(r.get("classification") in ("ALIAS", "OWN-PROCEDURE") for r in ir),
        "ir-records-inconsistent")
    dc = lr.get("detector_control") or {}
    chk(dc.get("known_alias", {}).get("verdict") == "ALIAS"
        and dc.get("known_own_procedure", {}).get("verdict") == "OWN-PROCEDURE",
        "detector-known-controls-failed")

def mutate(doc, lr):
    lr["floor_carry"]["alias_count"] = lr["floor_carry"]["alias_count"] + 1


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0048-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0048-adapter-slash-command.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0048-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0048-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
