#!/usr/bin/env python3
"""Named probe 1: planted secret body is grepped absent; the record remains.

Two independent signals (catalog evidence_requirement):
  (1) GNU grep -F over the written JSONL returns no match for the secret body
  (2) the same file still parses as a JSONL record carrying unit_id, error_code,
      ts, and the correlation id that referenced the secret
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import jsonl_log as jl  # noqa: E402

PLANTED_SECRET = "ghp_SYNTHETICNOTAREALTOKENIMP0056xx"
ART = REPO / "command-center" / "receipts" / "IMP-0056.json"


def grep_body(path: Path, body: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["grep", "-F", body, str(path)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    if ART.is_file():
        receipt = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0056" not in receipt:
            print("FAILED:IMP-0056-probe1 receipt sentinel absent")
            return 1
        doc = json.loads(receipt)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0056-probe1 self-declared:{st}")
            return 1

    with tempfile.TemporaryDirectory(prefix="imp0056-p1-") as tmp:
        path = Path(tmp) / "plugin.jsonl"
        log = jl.JsonlLogger(path, unit_id="IMP-0056", redact=True)
        corr = "corr-imp0056-probe1"
        written = log.write(
            "PLUGIN.AUTH.DENIED",
            event="auth-failed",
            correlation_id=corr,
            message=f"presented token={PLANTED_SECRET}",
            nested={"token": PLANTED_SECRET, "ok": False},
        )
        raw = path.read_text(encoding="utf-8")
        rc_secret, out_secret = grep_body(path, PLANTED_SECRET)
        rc_corr, _ = grep_body(path, corr)

    records = [json.loads(line) for line in raw.splitlines() if line]
    if rc_secret != 1:
        print("FAILED:IMP-0056-probe1 grep found planted body (signal 1)")
        print(out_secret[:500])
        return 1
    if PLANTED_SECRET in raw:
        print("FAILED:IMP-0056-probe1 python read found planted body")
        return 1
    if rc_corr != 0:
        print("FAILED:IMP-0056-probe1 correlation id missing (signal 2 / dropped event)")
        return 1
    if len(records) != 1:
        print(f"FAILED:IMP-0056-probe1 record_count={len(records)}")
        return 1
    rec = records[0]
    for key in ("ts", "unit_id", "error_code"):
        if not rec.get(key):
            print(f"FAILED:IMP-0056-probe1 missing {key}")
            return 1
    if rec["unit_id"] != "IMP-0056":
        print("FAILED:IMP-0056-probe1 unit_id", rec["unit_id"])
        return 1
    if rec["error_code"] != "PLUGIN.AUTH.DENIED":
        print("FAILED:IMP-0056-probe1 error_code", rec["error_code"])
        return 1
    if rec["fields"]["correlation_id"] != corr:
        print("FAILED:IMP-0056-probe1 correlation drifted")
        return 1
    if written["fields"]["nested"]["ok"] is not False:
        print("FAILED:IMP-0056-probe1 nested non-secret value dropped")
        return 1

    out = {
        "probe": "probe1-secret-body",
        "unit_id": "IMP-0056",
        "grep_secret_exit": rc_secret,
        "grep_secret_hits": 0,
        "grep_correlation_exit": rc_corr,
        "record_count": len(records),
        "record_kept": True,
        "error_code": rec["error_code"],
        "has_ts": bool(rec.get("ts")),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0056-probe1 secret body grepped absent; record kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
