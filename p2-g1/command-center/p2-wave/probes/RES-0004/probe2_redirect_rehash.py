#!/usr/bin/env python3
# RES-0004 probe2: redirect-chain capture + in-probe fresh rehash (2026-10-25).
# The store must record the known 301 chain docs.claude.com/en/docs/claude-code/*
# -> code.claude.com/docs/en/* with (from, status, to, reason), final_url on the
# target host, and a blob that re-hashes to its recorded sha256 IN THIS PROCESS
# as well (a second, mechanically different signal from the subprocess runner).
# Also asserts all three captured shapes exist (301 chain, js-rendered, raw file)
# and that the receipt records the same chain.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("res0004_store", REPO / "command-center/lib/evidence_snapshot/store.py")
S = importlib.util.module_from_spec(spec)
sys.modules["res0004_store"] = S
spec.loader.exec_module(S)


def fail(msg):
    print("FAILED:RES-0004-probe2 " + str(msg))
    return 1


def main():
    idx = S.load_index()
    shapes = sorted(e["shape"] for e in idx["entries"])
    print("shapes=" + json.dumps(shapes))
    if shapes != ["js-rendered", "raw-file", "redirect-chain"]:
        return fail("shape-coverage:" + json.dumps(shapes))
    entry = next(e for e in idx["entries"] if e["shape"] == "redirect-chain")
    chain = entry.get("redirect_chain") or []
    if not chain:
        return fail("redirect-chain-absent")
    hop = chain[0]
    print("redirect_chain[0]: %d %s -> %s (%s)"
          % (hop.get("status"), hop.get("from"), hop.get("to"), hop.get("reason")))
    if hop.get("status") != 301:
        return fail("hop-status-not-301")
    if "docs.claude.com" not in hop.get("from", ""):
        return fail("hop-from-not-docs-host")
    if "code.claude.com" not in hop.get("to", "") or hop["to"] != entry.get("final_url"):
        return fail("hop-to-mismatch:" + str(entry.get("final_url")))
    # in-probe rehash (second signal besides the fresh process runner)
    rh = S.rehash_entry(entry)
    print("redirect blob rehash: ok=%s sha256=%s bytes=%d"
          % (rh["ok"], rh["sha256"][:16], rh["bytes"]))
    if not rh["ok"]:
        return fail("redirect-blob-rehash-mismatch")
    rec = json.loads((REPO / "command-center/research/RES-0004.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if "301" not in json.dumps(rec) or "code.claude.com" not in json.dumps(rec):
        return fail("receipt-redirect-record-absent")
    ru = rec.get("residual_unknowns") or []
    if not any(u.get("verdict") == "NOT-CHECKED" for u in ru):
        return fail("receipt-30-day-not-checked-residual-missing")
    print("receipt residual: 30-calendar-day wait NOT-CHECKED (byte-mutation + live refetch now)")
    print("SUCCESS:RES-0004-probe2 redirect-and-rehash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
