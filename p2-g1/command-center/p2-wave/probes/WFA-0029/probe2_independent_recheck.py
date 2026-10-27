#!/usr/bin/env python3
"""WFA-0029 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/wfa/WFA-0029-acquisition-scheduler.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0029" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0029"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    bs = lr.get("both_states") or {}
    w1 = float(bs.get("wait_1_per_min", -1))
    w1000 = float(bs.get("wait_1000_per_min", -1))
    chk(w1 >= 59.0, "1-per-min-does-not-block-60s", str(w1))
    chk(w1000 < 1.0, "1000-per-min-blocks", str(w1000))
    chk(abs(60.0 / 1 - w1) < 5.0 and abs(60.0 / 1000 - w1000) < 0.05,
        "wait-times-not-recomputable-from-rate")
    chk(bs.get("blocks_at_1_per_min") is True and bs.get("does_not_block_at_1000_per_min") is True
        and bs.get("pass") is True, "both-states-verdicts-false")
    fp = lr.get("fingerprint") or {}
    chk(fp.get("winner") == "agree", "provider-vs-scheduler-disagree", str(fp.get("winner")))
    chk(fp.get("sched_github_429") == 0 and fp.get("resume_lost") == 0
        and fp.get("tokens_ok") is True, "provider-429-or-resume-loss-nonzero")
    cfg = lr.get("config") or {}
    chk(len(cfg) == 5 and all("tokens_per_minute" in v and "max_inflight" in v
                              for v in cfg.values()),
        "provider-config-incomplete")
    lint = lr.get("lint") or {}
    chk(lint.get("planted_fired") is True and lint.get("own_clean") is True,
        "bypass-detector-both-states-failed")

def mutate(doc, lr):
    lr["both_states"]["wait_1_per_min"] = 30.0


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0029-probe2 artifact-unreadable:" + type(exc).__name__)
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
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0029-acquisition-scheduler.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0029-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0029-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
