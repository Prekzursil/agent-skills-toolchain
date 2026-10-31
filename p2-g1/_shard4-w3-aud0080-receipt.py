#!/usr/bin/env python3
"""shard4-w3: write command-center/receipts/AUD-0080.json (builder BLOCKED receipt).

Prior builder died before writing this receipt. Artifact + probes + manifest
already verify green under _measure_one_delivered.py (SUCCESS:delivered AUD-0080).
receipt_core forbids state=SUCCESS without reviewer.verdict=PASS + independent=true;
the probe self-review inside SUBAGENT-RETURN.json is not an independent reviewer,
so the receipt is BLOCKED with failure.classification ["reviewer-absent"],
matching the 11 sibling receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.cwd()
OUT = "command-center/audit/AUD-0080-permission-surface-audit.json"
P1 = ("PYTHONDONTWRITEBYTECODE=1 python3 -B "
      "command-center/p2-wave/probes/AUD-0080/probe1_allow_merge.py")
P2 = ("PYTHONDONTWRITEBYTECODE=1 python3 -B "
      "command-center/p2-wave/probes/AUD-0080/probe2_matcher_bypass.py")
SENTINEL = ("SUCCESS:AUD-0080 emitted only when the artifact at output_path "
            "exists, is non-empty, parses against output_schema, and both named "
            "probes are recorded with their verbatim output")
RETRY_POLICY = ("two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically "
                "different detectors before a third attempt")


def digest(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    eol = "CRLF" if b"\r\n" in raw else "LF"
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    c = cmd
    exe = str(sys.executable).replace("\\", "/")
    c = c.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    p = subprocess.run(c, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, env=env, timeout=2400)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    out_path = REPO / OUT
    sha, nbytes, eol = digest(out_path)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    state = str(doc.get("state", "")).upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:receipt artifact self-declared {state}")
        return 1

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:receipt probes rc1={rc1} rc2={rc2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    man_path = REPO / "command-center/p2-wave/probes/AUD-0080/UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == "AUD-0080"]
    match = [a for a in rows
             if a.get("path") == OUT and a.get("sha256") == sha and a.get("present") is True]
    if not match:
        print("FAILED:receipt manifest-sha-mismatch")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "artifacts": [
            {"bytes": nbytes, "eol": eol, "exists": True, "path": OUT,
             "role": "primary", "sha256": sha}
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/AUD-0080/SUBAGENT-RETURN.json",
                "claim": "Both named probes re-ran live this run and exited 0.",
                "confidence": "almost-certain",
                "probes": [
                    {"command": P1, "exit_code": rc1, "fingerprint": fp(P1),
                     "method": "command", "raw_output": t1, "role": "source"},
                    {"command": P2, "exit_code": rc2, "fingerprint": fp(P2),
                     "method": "command", "raw_output": t2, "role": "verifier"},
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/AUD-0080/UNIT-ARTIFACT-MANIFEST.json",
                "claim": "UNIT-ARTIFACT-MANIFEST.json carries a sha256 row matching the live artifact (CRLF normalized).",
                "confidence": "almost-certain",
                "probes": [
                    {"command": "compare UNIT-ARTIFACT-MANIFEST.json row sha256 for AUD-0080 against live artifact",
                     "fingerprint": fp("compare-" + OUT), "method": "byte-compare",
                     "raw_output": f"manifest sha256 == live artifact sha256 ({sha[:16]}...)",
                     "role": "source"},
                    {"command": f"recompute sha256 of {OUT} after CRLF->LF normalization",
                     "fingerprint": fp("recompute-" + OUT), "method": "byte-compare",
                     "raw_output": f"recomputed digest equals manifest row ({sha[:16]}...)",
                     "role": "verifier"},
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "failure": {
            "blocked_on": "independent-reviewer-wave",
            "classification": ["reviewer-absent"],
            "reason": ("builder-only state: artifact delivered, both named probes "
                       "exit 0, manifest sha256 matches the live artifact; "
                       "receipt_core forbids state=SUCCESS without "
                       "reviewer.verdict=PASS and independent=true, so only the "
                       "independent reviewer closes this unit."),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/AUD-0080/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 1024,
        "notes": ("resume-complete: prior run delivered artifact + probe scripts and "
                  "died before receipts; probes re-ran live (exit 0); return/manifest "
                  "already verified on disk and receipt written this run. Not "
                  "owner-gated (catalog owner_approval_required=false)."),
        "produced_by": {
            "execution_substrate": "local-serialized",
            "model": "claude-opus-5-5",
            "role": "builder-shard4-w3",
            "vendor": "anthropic",
        },
        "retry": {"attempts": [], "count": 0, "policy": RETRY_POLICY},
        "reviewer": {
            "independent": False,
            "notes": "builder shard4-w3 delivered; independent closure pending",
            "reviewer_id": "pending-independent-reviewer",
            "verdict": "NOT-REVIEWED",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "catalog:AUD-0080",
        "state": "BLOCKED",
        "timestamps": {"ended_at": now, "started_at": now},
        "unit_id": "AUD-0080",
    }
    out = REPO / "command-center/receipts/AUD-0080.json"
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"receipt written sha256={sha} bytes={nbytes} probes rc1={rc1} rc2={rc2}")
    print("SUCCESS:shard4-w3 AUD-0080 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
