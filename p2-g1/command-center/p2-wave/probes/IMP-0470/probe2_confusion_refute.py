#!/usr/bin/env python3
"""IMP-0470 probe2: confusion matrix before/after + independent file-digest signal.

Mechanically different signal from probe1: full confusion-matrix arithmetic on
the historical corpus in both modes, plus a sha256 digest of the live library
compared against the receipt-recorded artifact hash (CRLF-normalized).
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def fail(msg):
    print("FAILED:IMP-0470-probe2 " + str(msg))
    return 1


def load(mod, rel):
    spec = importlib.util.spec_from_file_location(mod, REPO / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


def main():
    lib = load("use_vs_mention", "hooks/_shared/use_vs_mention.py")
    corpus = load("imp0470_corpus", "command-center/p2-wave/probes/IMP-0470/corpus.py")
    hist = [r for r in corpus.HISTORICAL if r.get("label") == "mention"]
    before = lib.confusion_matrix(hist, mode="naive")
    after = lib.confusion_matrix(hist, mode="role")
    surviving = [r["id"] for r in lib.surviving_false_positives(hist)]
    print("fp_rate_before=" + str(before["false_positive_rate"])
          + " fp_rate_after=" + str(after["false_positive_rate"])
          + " surviving=" + json.dumps(surviving))
    if before["fp"] != 16 or before["tn"] != 0:
        return fail("before-matrix:" + str(before["fp"]) + "/" + str(before["tn"]))
    if after["fp"] != 0 or after["tn"] != 16:
        return fail("after-matrix:" + str(after["fp"]) + "/" + str(after["tn"]))
    if surviving:
        return fail("surviving-fps:" + json.dumps(surviving))
    # negative control: naive payload-text must fire on every historical mention,
    # or the before/after contrast measures nothing (known-broken fixture).
    if sum(1 for r in before["rows"] if r["fires"]) != 16:
        return fail("negative-control-naive-not-firing")
    lib_path = REPO / "hooks/_shared/use_vs_mention.py"
    live_sha = hashlib.sha256(lib_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    rec = json.loads((REPO / "command-center/receipts/IMP-0470.json").read_text(encoding="utf-8"))
    rec_sha = None
    for a in rec.get("artifacts") or []:
        if isinstance(a, dict) and str(a.get("path", "")).endswith("use_vs_mention.py"):
            rec_sha = a.get("sha256")
    if not rec_sha:
        return fail("receipt-library-sha-absent")
    # sha256 is PROVENANCE, not a freeze: the library is shared and other lanes
    # revise it. Fail only if the receipt's behavioral claims stop reproducing;
    # report a provenance mismatch honestly as information.
    if rec_sha == live_sha:
        print("library sha256=" + live_sha + " provenance=match")
    else:
        print("library sha256=" + live_sha
              + " receipt_recorded=" + rec_sha
              + " provenance=MATCH-FALSE library-revised-since-closure"
              + " (behavioral claims re-verified live below)")
        mm = rec.get("measurement") or {}
        if mm.get("fp_rate_before") != 1.0 or mm.get("fp_rate_after") != 0.0:
            return fail("receipt-fp-numbers-drift-under-revised-library")
    m = rec.get("measurement") or {}
    if m.get("fp_rate_before") != 1.0 or m.get("fp_rate_after") != 0.0:
        return fail("receipt-fp-numbers-drift")
    if m.get("surviving_false_positives") != []:
        return fail("receipt-surviving-drift")
    print("SUCCESS:IMP-0470-probe2 confusion-refute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
