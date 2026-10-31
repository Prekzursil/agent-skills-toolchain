#!/usr/bin/env python3
# REL-0006 probe1: N-1 retrievability precondition (resume 2026-10-25).
# Rebuilds the fixture release store, fetches n-1.zip, requires sha equality
# against ROLLBACK-MANIFEST.md BEFORE any downgrade, and proves the corrupt
# control is refused (recorded negative control corrupt-n1-blocks-before-
# downgrade).
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0006_drill", HERE / "drill.py")
D = importlib.util.module_from_spec(spec)
sys.modules["rel0006_drill"] = D
spec.loader.exec_module(D)


def fail(msg):
    print("FAILED:REL-0006-probe1 " + str(msg))
    return 1


def main():
    store = Path(tempfile.mkdtemp(prefix="rel0006-store-"))
    work = Path(tempfile.mkdtemp(prefix="rel0006-work-"))
    try:
        recorded = D.build_store(store)
        check = D.fetch_and_check(store, work, corrupt=False)
        print("fetched_sha256=" + check["fetched_sha256"])
        print("manifest_sha256=" + check["manifest_sha256"] + " match=" + str(check["match"]))
        if not check["match"] or check["fetched_sha256"] != recorded:
            return fail("retrievability-sha-mismatch")
        corrupt = D.fetch_and_check(store, work, corrupt=True)
        print("corrupt_fetched_sha256=" + corrupt["fetched_sha256"]
              + " corrupt_match=" + str(corrupt["match"]))
        if corrupt["match"]:
            return fail("corrupt-control-not-refused")
        rec = json.loads((REPO / "command-center/receipts/REL-0006.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if "SUCCESS:REL-0006" not in json.dumps(rec):
            return fail("sentinel-absent")
        r = rec.get("retrievability") or {}
        if r.get("match") is not True or r.get("corrupt_control_blocked") is not True:
            return fail("receipt-retrievability-numbers-drift")
        print("SUCCESS:REL-0006-probe1 retrievability-precondition")
        return 0
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
