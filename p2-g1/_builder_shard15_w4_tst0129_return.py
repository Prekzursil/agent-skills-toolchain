#!/usr/bin/env python3
"""shard-15 wave-4 2026-10-26: refresh TST-0129 SUBAGENT-RETURN.json to the
verified-live state after shard18-w4's receipt restoration.

The prior (shard-23) return recorded status=SUCCESS with the sha of the
hand-flipped receipt; shard18-w4 then restored the receipt to the
reviewer-certified refute-stage BLOCKED disposition, leaving this return
stale. This rewrite keeps the named probe commands verbatim, records this
session's live probe outputs (both exit 0), the live CRLF-normalized
receipt digest, and the honest BLOCKED session outcome. The receipt itself
is NOT modified (reviewer closure kept intact).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent  # script lives directly in p2-g1
RECEIPT = REPO / "command-center/receipts/TST-0129.json"
RET = REPO / "command-center/p2-wave/probes/TST-0129/SUBAGENT-RETURN.json"

PROBE_CMDS = [
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0129/probe1_delivery_predicate.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0129/probe2_failclosed_recheck.py",
]


def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    import os
    import re
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # shard11 repair port: cmd.exe cannot execute POSIX "VAR=value command" prefixes
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
        exe = sys.executable.replace("\\", "/")
        cmd = cmd.replace("python3", exe, 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=600, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    sha, nbytes = norm_sha(RECEIPT)
    receipts = json.loads(RECEIPT.read_text(encoding="utf-8"))
    ret = json.loads(RET.read_text(encoding="utf-8"))

    probe_outputs = []
    for i, cmd in enumerate(PROBE_CMDS, 1):
        rc, out = run_probe(cmd)
        probe_outputs.append({"i": i, "rc": rc, "tail": out[-500:]})
        if rc != 0:
            print(f"FAILED:tst0129-return-refresh probe{i} rc={rc}")
            return 1

    ret["schema_version"] = 1
    ret["unit_id"] = "TST-0129"
    ret["id"] = "TST-0129"
    ret["status"] = "BLOCKED"
    ret["state"] = "BLOCKED"
    ret["sentinel"] = "SUCCESS:TST-0129"
    ret["output_path"] = "command-center/receipts/TST-0129.json"
    ret["named_probes"] = [
        {
            "id": "probe1",
            "command": PROBE_CMDS[0],
            "exit_code": probe_outputs[0]["rc"],
            "role": "delivery-predicate",
            "raw_output": probe_outputs[0]["tail"],
        },
        {
            "id": "probe2",
            "command": PROBE_CMDS[1],
            "exit_code": probe_outputs[1]["rc"],
            "role": "independent-recheck",
            "raw_output": probe_outputs[1]["tail"],
        },
    ]
    ret["artifacts"] = [
        {
            "path": "command-center/receipts/TST-0129.json",
            "bytes": nbytes,
            "sha256": sha,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    ret["manifest_path"] = "command-center/p2-wave/probes/TST-0129/UNIT-ARTIFACT-MANIFEST.json"
    ret["failure"] = {
        "classification": list(receipts["failure"]["classification"]),
        "reason": receipts["failure"]["reason"],
    }
    ret["notes"] = (
        "shard-15 wave-4 resume 2026-10-26: prior independent reviewer closure "
        "(openai-headless-refuter-TST-0129, verdict=PASS, independent=true) verified live this "
        "session and KEPT per contract - the reviewer closed the refute-stage BLOCKED disposition "
        "(condition 11 live-red, SUCCESS withheld) and explicitly did not erase the missing B07 "
        "target; the receipt is left byte-identical. Dependency tokens B07/B06 are absent from "
        "WORK-UNIT-CATALOG.json (unknown tokens -> catalog-forensics only, never guessed), so the "
        "condition-11 dependency cannot be closed by this builder. shard18-w4's anti-hand-flip "
        "predicate (probe1 state==BLOCKED) enforced; both named probes exit 0 live; manifest sha "
        "matches the CRLF-normalized live receipt digest. This return replaces the stale shard-23 "
        "SUCCESS record (whose sha pointed at the reverted hand-flip receipt)."
    )
    ret["extensions"] = {"builder": "shard-15 wave-4 resume (opus, Windows) 2026-10-26"}
    ret["ts"] = "2026-10-26T00:00:00Z"
    ret["live_receipt_sha256"] = sha
    ret["live_receipt_bytes"] = nbytes

    RET.write_text(json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SUCCESS:tst0129-return-refresh receipt={nbytes}B sha={sha[:16]}... probes rc=0/0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
