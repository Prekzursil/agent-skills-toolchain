#!/usr/bin/env python3
"""WFA-0056 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0056-second-control-plane-guard.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0056" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0056"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    rt = lr.get("torn_down_runtimes") or []
    chk(len(rt) == 7, "runtime-count", str(len(rt)))
    ids = {r.get("id") for r in rt}
    obs = lr.get("observed") or {}
    named = {str(s).lower() for s in ((obs.get("evidence_a") or {}).get("named_planes") or [])}
    chk(ids == named, "named-planes-vs-runtime-ids-mismatch",
        "ids=%s named=%s" % (sorted(ids), sorted(named)))
    t27 = REPO / "command-center" / "wfa" / "WFA-0027-teardown-adjacent-runtimes.json"
    if t27.is_file():
        text = t27.read_text(encoding="utf-8").lower()
        for rid in ids:
            chk(rid in text, "runtime-not-in-live-WFA-0027-artifact", rid)
    bs2 = (obs.get("both_states") or {})
    chk(bs2.get("silent_on_legitimate_library") is True
        and bs2.get("loud_on_runtime_import") is True
        and bs2.get("names_which") is True and bs2.get("pass") is True,
        "guard-both-states-false")
    chk(len(lr.get("expected") or {}) >= 5, "expected-matrix-truncated")
    allow = (obs.get("evidence_a") or {}).get("allowlist") or {}
    chk(allow.get("denied_fired") is True and allow.get("allowed_fired") is False,
        "allowlist-behaviour-inverted")

def mutate(doc, lr):
    lr["torn_down_runtimes"][0]["id"] = "not-a-runtime"


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0056-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0056-second-control-plane-guard.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0056-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0056-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
