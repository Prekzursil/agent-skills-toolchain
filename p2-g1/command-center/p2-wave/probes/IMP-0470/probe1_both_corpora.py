#!/usr/bin/env python3
"""IMP-0470 probe1: both-corpora role re-verification (resume 2026-10-25).

Re-runs the shipped use-vs-mention library over the rebuilt corpus and checks
the receipt-recorded properties: historical mentions n=16 role_fires=0; use
corpus n=17 role_silent=0. Also re-checks the receipt numbers and sentinel.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def fail(msg):
    print("FAILED:IMP-0470-probe1 " + str(msg))
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
    mention = [r for r in corpus.HISTORICAL if r.get("label") == "mention"]
    if len(mention) != 16:
        return fail("mention-corpus-size:" + str(len(mention)))
    if len(corpus.USE) != 17:
        return fail("use-corpus-size:" + str(len(corpus.USE)))
    role_fires = [r["id"] for r in mention if lib.classify_record(r, mode="role")["fires"]]
    use_silent = [r["id"] for r in corpus.USE if not lib.classify_record(r, mode="role")["fires"]]
    print("mention_fires=" + json.dumps(role_fires) + " use_silent=" + json.dumps(use_silent))
    if role_fires:
        return fail("role-fires-on-historical-mentions:" + json.dumps(role_fires))
    if use_silent:
        return fail("role-silent-on-uses:" + json.dumps(use_silent))
    rec = json.loads((REPO / "command-center/receipts/IMP-0470.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if "SENTINEL:IMP-0470:ROLE-BASED-DETECTION" not in json.dumps(rec):
        return fail("sentinel-absent")
    m = rec.get("measurement") or {}
    if m.get("mention", {}).get("role_fires") != 0 or m.get("use", {}).get("role_silent") != 0:
        return fail("receipt-role-numbers-drift")
    if m.get("historical", {}).get("n") != 16:
        return fail("receipt-historical-n-drift")
    print("SUCCESS:IMP-0470-probe1 both-corpora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
