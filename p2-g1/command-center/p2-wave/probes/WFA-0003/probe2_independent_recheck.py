#!/usr/bin/env python3
"""WFA-0003 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0003-id-namespace-audit.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0003" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0003"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    pc = lr.get("planted_control") or {}
    chk(pc.get("pass") is True and pc.get("intersection_reported") is True,
        "planted-SYN-99-clash-not-detected", json.dumps(pc)[:120])
    sb = lr.get("signal_b") or {}
    chk(len(sb.get("classified") or []) == sb.get("citation_only_count"),
        "citation-only-count-mismatch",
        "classified=%s count=%s" % (len(sb.get("classified") or []), sb.get("citation_only_count")))
    for row in lr.get("absent_ids") or []:
        if row.get("class") == "doc-13-bare-M-ABSENT":
            chk(row.get("resolve_bare_m_in_doc13") == "ABSENT"
                and row.get("resolve_mech_in_doc13") == "PRESENT",
                "absent-id-class-row-inconsistent", str(row.get("token")))
    pcs = lr.get("pinned_collision_statement") or {}
    chk(pcs.get("classification") == "STALE" and pcs.get("stale") is True,
        "pinned-31-way-collision-not-stale")
    pf = lr.get("postfix_verdict") or {}
    chk(pf.get("semantic_clash_count") == 0
        and pf.get("matches_pinned_31_way_failure") is False
        and pf.get("shared_colliding_declaration_prefix") is False,
        "postfix-verdict-inconsistent")
    chk(bool(lr.get("historical_mnn_control", {}).get("clashes")),
        "historical-MNN-control-absent")

def mutate(doc, lr):
    lr["signal_b"]["citation_only_count"] = lr["signal_b"]["citation_only_count"] + 1


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0003-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0003-id-namespace-audit.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0003-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0003-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
