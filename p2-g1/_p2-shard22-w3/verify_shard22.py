#!/usr/bin/env python3
"""Shard-22 final verification: for each of the 12 units,
  * probe dir has SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json
  * both named probes re-run live and exit 0
  * manifest primary row sha256 == CRLF-normalized sha of the live receipt
  * receipt: parses, unit_id, state=BLOCKED, failure.classification==[reviewer-absent],
    reviewer is null (no self-certified verdict), completion sentinel literal present
    (ready for the independent reviewer's closure), report.kind matches the schema pin
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = [
    "TST-0174", "TST-0175", "TST-0176", "TST-0178", "TST-0179", "TST-0180",
    "TST-0181", "TST-0185", "TST-0188", "TST-0190", "TST-0193", "TST-0194",
]
KIND = {
    "TST-0174": "cache_report", "TST-0175": "cache_report", "TST-0176": "cache_report",
    "TST-0178": "cache_report", "TST-0179": "parser_report", "TST-0180": "parser_report",
    "TST-0181": "parser_report", "TST-0185": "parser_report", "TST-0188": "shell_report",
    "TST-0190": "shell_report", "TST-0193": "shell_report", "TST-0194": "portability_report",
}


def sha_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    failures = []
    for uid in UNITS:
        pdir = PROBES / uid
        ret = pdir / "SUBAGENT-RETURN.json"
        man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        receipt = REPO / "command-center" / "receipts" / f"{uid}.json"
        problems = []
        if not (ret.is_file() and man.is_file() and receipt.is_file()):
            problems.append("missing-files")
        else:
            r = json.loads(receipt.read_text(encoding="utf-8"))
            if r.get("unit_id") != uid and r.get("id") != uid:
                problems.append("unit-id")
            if r.get("state") != "BLOCKED":
                problems.append("state=" + str(r.get("state")))
            if (r.get("failure") or {}).get("classification") != ["reviewer-absent"]:
                problems.append("classification")
            if r.get("reviewer") is not None:
                problems.append("reviewer-not-null (self-certified?)")
            if f"SUCCESS:{uid}" not in receipt.read_text(encoding="utf-8"):
                problems.append("sentinel-absent")
            if (r.get("report") or {}).get("kind") != KIND[uid]:
                problems.append("report-kind")
            m = json.loads(man.read_text(encoding="utf-8"))
            rows = [a for a in m.get("artifacts", []) if a.get("unit_id") == uid]
            live = sha_lf(receipt)
            if not any(
                a.get("path") == f"command-center/receipts/{uid}.json"
                and a.get("sha256") == live
                and a.get("present") is True
                for a in rows
            ):
                problems.append("manifest-sha-mismatch")
            # live probe re-run
            rd = json.loads(ret.read_text(encoding="utf-8"))
            for np in rd.get("named_probes", []):
                cmd = np["command"]
                while True:
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
                    if m is None:
                        break
                    cmd = cmd[m.end():]
                cmd = cmd.replace("python3", sys.executable, 1)
                p = subprocess.run(
                    cmd.split(),
                    cwd=str(REPO), capture_output=True, text=True, timeout=2700,
                )
                if p.returncode != 0:
                    problems.append(f"probe-exit:{np['id']}={p.returncode}")
        if problems:
            failures.append((uid, problems))
            print(f"FAILED:verify {uid} {problems}")
        else:
            print(f"SUCCESS:verify {uid} probes-live sha={live[:12]}")
    print("---")
    if failures:
        print(f"FAILED:shard22-verify units_failed={len(failures)}")
        return 1
    print(f"SUCCESS:shard22-verify all {len(UNITS)} units built-awaiting-review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
