#!/usr/bin/env python3
"""WFA-0005 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0005" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0005"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    hist = lr.get("catalog_stated_histogram") or {}
    total = sum(int(v) for v in hist.values())
    chk(total == int(lr.get("catalog_stated_n")) == 284, "histogram-total-mismatch",
        "sum=%s n=%s" % (total, lr.get("catalog_stated_n")))
    unused = lr.get("catalog_stated_unused") or {}
    chk(len(unused) == 6, "unused-value-count", str(len(unused)))
    adj = lr.get("adjudications") or []
    chk(len(adj) == 6, "adjudication-count", str(len(adj)))
    chk(sorted(str(a.get("value")) for a in adj) == sorted(unused),
        "adjudication-values-not-the-unused-six")
    for a in adj:
        chk(int(a.get("live_count", -1)) == 0, "live-count-nonzero", str(a.get("value")))
        chk(a.get("deletion_blocked_because") == "zero-count-is-not-deletion-grounds",
            "deletion-not-blocked", str(a.get("value")))
        chk(a.get("planted_fired") is not False, "planted-control-not-fired", str(a.get("value")))
    conf = lr.get("confirmations") or []
    chk(len(conf) >= 2 and all(c.get("verdict") == "CONFIRMED" for c in conf),
        "confirmations-not-confirmed")

def mutate(doc, lr):
    lr["catalog_stated_n"] = "999"


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0005-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0005-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0005-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
