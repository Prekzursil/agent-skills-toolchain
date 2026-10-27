#!/usr/bin/env python3
# RES-0004 probe1: recheck controls (resume 2026-10-25).
# 1. fresh-process rehash of the whole store (runner_rehash.py subprocess).
# 2. mutated-stored-byte control: one XORed blob byte -> SNAPSHOT-CORRUPT.
# 3. missing-quote-unchanged-source control -> CLAIM-WAS-WRONG, NOT
#    SOURCE-CHANGED (the classifier must never confuse a lying claim with a
#    changed source).
# 4. intact entry with present anchors -> CLAIM-HOLDS.
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("res0004_store", REPO / "command-center/lib/evidence_snapshot/store.py")
S = importlib.util.module_from_spec(spec)
sys.modules["res0004_store"] = S
spec.loader.exec_module(S)
spec2 = importlib.util.spec_from_file_location("res0004_recheck", REPO / "command-center/lib/evidence_snapshot/recheck.py")
R = importlib.util.module_from_spec(spec2)
sys.modules["res0004_recheck"] = R
spec2.loader.exec_module(R)


def fail(msg):
    print("FAILED:RES-0004-probe1 " + str(msg))
    return 1


def main():
    # 1. fresh process
    p = subprocess.run([sys.executable, "-B", str(HERE / "runner_rehash.py")],
                       capture_output=True, text=True, timeout=600)
    print((p.stdout or p.stderr).strip().splitlines()[-2] if p.stdout or p.stderr else "no output")
    if p.returncode != 0:
        return fail("fresh-process-rehash-failed")
    idx = S.load_index()
    anchor_entry = next(e for e in idx["entries"] if e["shape"] == "js-rendered")
    plain_entry = next(e for e in idx["entries"] if e["shape"] == "redirect-chain")
    body = S.blob_path(anchor_entry).read_bytes()
    tmp = Path(tempfile.mkdtemp(prefix="res0004-p1-"))
    try:
        # 2. mutated stored byte -> SNAPSHOT-CORRUPT
        mutated = bytearray(body)
        mutated[len(mutated) // 2] ^= 0x01
        mutated_path = tmp / "mutated-blob"
        mutated_path.write_bytes(bytes(mutated))
        e_mut = dict(anchor_entry, archive_relpath=str(mutated_path))
        if R.classify(e_mut, body) != "SNAPSHOT-CORRUPT":
            return fail("mutated-byte-not-detected")
        print("mutated-stored-byte: SNAPSHOT-CORRUPT fired")
        # 3. absent quote on unchanged source -> CLAIM-WAS-WRONG
        e_wrong = dict(anchor_entry, archive_relpath=str(tmp / "intact-copy"),
                       quote="this string appears nowhere in the captured body")
        shutil.copyfile(S.blob_path(anchor_entry), e_wrong["archive_relpath"])
        if R.classify(e_wrong, body) != "CLAIM-WAS-WRONG":
            return fail("missing-quote-misclassified:" + R.classify(e_wrong, body))
        print("missing-quote-unchanged-source: CLAIM-WAS-WRONG fired (not SOURCE-CHANGED)")
        # 4. intact anchors -> CLAIM-HOLDS
        e_hold = dict(anchor_entry, archive_relpath=str(S.blob_path(anchor_entry)))
        if R.classify(e_hold, body) != "CLAIM-HOLDS":
            return fail("intact-entry-not-holds:" + R.classify(e_hold, body))
        print("intact-entry: CLAIM-HOLDS")
        rec = json.loads((REPO / "command-center/research/RES-0004.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if "SUCCESS:RES-0004" not in json.dumps(rec):
            return fail("sentinel-absent")
        nc = {c.get("id") for c in rec.get("negative_controls") or []}
        if not {"mutated-stored-byte", "missing-quote-unchanged-source"} <= nc:
            return fail("receipt-negative-controls-drift")
        print("SUCCESS:RES-0004-probe1 recheck-controls")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
