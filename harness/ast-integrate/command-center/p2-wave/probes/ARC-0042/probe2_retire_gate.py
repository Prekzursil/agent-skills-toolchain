#!/usr/bin/env python3
"""Named probe 2: no-retirement-before-proof (different shell, different field).

Probe 1 reads payload sha256 via Python hashlib. This probe reads
Differential-Sha256 from a commit-message-shaped note via bash/awk, then
compares that field to the JSON retirement citation. Disagreement is BLOCKED.
Also rehearses allowed-when-cited vs refused-when-uncited.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from differential import run_all  # noqa: E402
from retire_gate import evaluate  # noqa: E402
from view import plan as domain  # noqa: E402

ART = REPO / "command-center/phase3/A6/MIGRATION.json"
SH = HERE / "probe2_retire_gate.sh"
NOTE = HERE / "fixtures" / "retirement.note"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0042-probe2 {msg}")
    return 1


def parse_awk(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line and line.split("=", 1)[0] in {
            "awk_n_rails",
            "awk_n_shas",
            "awk_mcp_sha",
            "awk_fan_sha",
            "awk_mail_sha",
        }:
            k, v = line.split("=", 1)
            out[k] = v.strip()
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("migration artifact missing")
    if not NOTE.is_file():
        return fail("retirement.note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    proc = subprocess.run(
        ["bash", str(SH)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(text)
    if proc.returncode != 0:
        return fail(f"awk rc={proc.returncode}")
    awk = parse_awk(text)

    live = run_all(REPO, HERE)
    passing = live["per_rail"]
    mcp_sha = passing["mcp-thread"]["sha256"]
    if awk.get("awk_mcp_sha") != mcp_sha:
        return fail(
            "readings disagree "
            f"awk_mcp_sha={awk.get('awk_mcp_sha')} python_sha={mcp_sha}"
        )
    if awk.get("awk_fan_sha") != passing["exec-fanout"]["sha256"]:
        return fail("awk/python disagree on exec-fanout sha")
    if awk.get("awk_mail_sha") != passing["agent-mail"]["sha256"]:
        return fail("awk/python disagree on agent-mail sha")

    payload = domain(doc)
    gate = (payload.get("tests") or {}).get("no_retirement_before_proof") or {}
    cited_sha = str(gate.get("cited_sha256") or "")
    cited_id = str(gate.get("cited_run_id") or "")
    if cited_sha != mcp_sha:
        return fail("artifact cited_sha256 drift vs live python digest")
    if gate.get("awk_sha256") != awk.get("awk_mcp_sha"):
        return fail("artifact awk_sha256 drift vs live awk")
    if gate.get("python_sha256") != mcp_sha:
        return fail("artifact python_sha256 drift")
    if cited_id != passing["mcp-thread"]["id"]:
        return fail("artifact cited_run_id drift")
    if awk.get("awk_mcp_sha") != gate.get("python_sha256"):
        return fail(
            "BLOCKED two readings disagree "
            f"awk={awk.get('awk_mcp_sha')} python={gate.get('python_sha256')}"
        )

    allowed = evaluate(
        {
            "rail_id": "mcp-thread",
            "differential_run_id": cited_id,
            "differential_sha256": cited_sha,
        },
        passing,
    )
    blocked = evaluate(
        {
            "rail_id": "mcp-thread",
            "differential_run_id": cited_id,
            "differential_sha256": "0" * 64,
        },
        passing,
    )
    if not allowed.get("allowed") or allowed.get("reason") != "PROOF-CITED":
        print(json.dumps(allowed, indent=2))
        return fail("cited retirement was not allowed")
    if blocked.get("allowed") or blocked.get("reason") != "RETIRE-WITHOUT-PROOF":
        print(json.dumps(blocked, indent=2))
        return fail("uncited retirement was not refused")
    if not gate.get("allowed_when_cited") or not gate.get("refused_when_uncited"):
        return fail("artifact retirement flags drift")

    out = {
        "probe": "probe2-retire-gate",
        "unit_id": "ARC-0042",
        "allowed_when_cited": True,
        "refused_when_uncited": True,
        "cited_run_id": cited_id,
        "awk_sha256": awk.get("awk_mcp_sha"),
        "python_sha256": mcp_sha,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"cited={cited_id} awk={awk.get('awk_mcp_sha')} "
        f"python={mcp_sha} refused_uncited=True"
    )
    print("SUCCESS:ARC-0042-probe2 retirement gate awk vs python")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
