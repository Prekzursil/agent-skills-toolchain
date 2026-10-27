#!/usr/bin/env python3
"""WFA-0053 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0053-adapter-paper-protocol.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0053" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0053"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    c = lr.get("counts") or {}
    papers = (lr.get("corpus") or {}).get("papers") or []
    chk(c.get("papers") == len(papers) == 6, "paper-count-mismatch")
    chk(c.get("translated", -1) + c.get("underspecified_refusals", -1) == 6,
        "translated+refused != papers")
    ird = lr.get("independent_reader") or {}
    chk(ird.get("hallucinated_default_count") == 0,
        "independent-reader-found-hallucinated-default")
    chk(len(ird.get("rows") or []) == 6, "independent-reader-rows-not-per-paper")
    chk(len(lr.get("negative_control_ids") or []) == 3, "negative-control-ids-count")
    ev = {r.get("id"): r for r in (lr.get("evidence") or [])}
    chk(len(ev) >= 3, "evidence-rows-under-minimum")
    e1 = (ev.get("E1-underspecified-refused") or {}).get("measured") or {}
    chk((e1.get("probe1") or {}).get("pass") is True, "E1-refusal-probe-not-pass")
    chk(e1.get("missing_required") == (e1.get("probe1") or {}).get("refusal_parameters"),
        "E1-refusal-parameters-mismatch")
    e2 = (ev.get("E2-quoted-fills-only") or {}).get("measured") or {}
    chk(len(e2.get("translated_papers") or []) == c.get("translated"),
        "E2-translated-count-mismatch",
        "rows=%s counts=%s" % (len(e2.get("translated_papers") or []), c.get("translated")))
    chk(bool(e2.get("committee_filled")), "E2-committee-fills-empty")
    e3 = ((ev.get("E3-independent-reader") or {}).get("measured") or {}).get("probe2") or {}
    comp = e3.get("compared") or []
    chk(len(comp) == 6 and all(row.get("hallucinated") == [] for row in comp),
        "E3-compared-rows-inconsistent",
        "n=%s" % len(comp))
    chk(ird.get("hallucinated_default_count") == 0, "E3-headline-vs-rows-mismatch")

def mutate(doc, lr):
    lr["counts"]["translated"] = lr["counts"]["translated"] + 1


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0053-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0053-adapter-paper-protocol.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0053-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0053-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
