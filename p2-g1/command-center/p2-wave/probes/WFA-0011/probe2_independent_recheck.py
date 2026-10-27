#!/usr/bin/env python3
"""WFA-0011 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0011-md-json-mirror-parity.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0011" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0011"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    cp = lr.get("control_pairs") or {}
    for pair in ("08", "09"):
        p = cp.get(pair) or {}
        chk(p.get("json_record_n") == p.get("markdown_heading_n") == 36,
            "pair-%s-parity-mismatch" % pair,
            "json=%s md=%s" % (p.get("json_record_n"), p.get("markdown_heading_n")))
    lpc = lr.get("live_pair_compares") or []
    chk(len(lpc) == 2 and all(x.get("unread") is True and x.get("invented") is False
                              and x.get("reason") == "path-absent-on-this-worktree"
                              for x in lpc),
        "live-pairs-not-honestly-unread")
    ns = lr.get("newer_side") or {}
    chk(ns.get("assumed_json") is False and ns.get("honest_collapsed_to_mutant") is False,
        "newer-side-rule-violated")
    # the honest rule reports the CLOCK-derived newer side, never assumes json
    for k in ("injected_json_newer", "injected_markdown_newer", "injected_tie"):
        row = ns.get(k) or {}
        chk(row.get("assumed_json") is False, "newer-case-%s-assumed-json" % k)
        ju, mu = row.get("json_unix"), row.get("markdown_unix")
        derived = "json" if ju > mu else ("markdown" if mu > ju else "tie")
        chk(row.get("newer") == derived, "newer-case-%s-clock-derived-mismatch" % k,
            "recorded=%s derived=%s" % (row.get("newer"), derived))
    mutant = ns.get("json_always_wins_mutant") or {}
    chk(mutant.get("assumed_json") is True and mutant.get("newer") == "json",
        "json-always-wins-mutant-not-recorded-as-bad-arm")
    neg = lr.get("negative_controls") or []
    chk(any(nc.get("silent_on_honest_regex") is True for nc in neg),
        "planted-non-id-heading-control-absent")
    chk(lr.get("corpus_mode") == "fixture-control", "corpus-mode")

def mutate(doc, lr):
    lr["control_pairs"]["08"]["json_record_n"] += 1


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0011-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0011-md-json-mirror-parity.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0011-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0011-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
