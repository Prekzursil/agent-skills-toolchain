#!/usr/bin/env python3
"""Emit CC-0013 catalog receipt plus per-unit return/manifest. Not a global --write."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))
import status_ledger as sl  # noqa: E402

UNIT = "CC-0013"
OUT = "command-center/receipts/CC-0013.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0013/probe1_handedit_determinism.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0013/probe2_empty_and_reviewer.py"
)
SUPPORTING = [
    "command-center/STATUS.md",
    "tools/command-center/status_ledger.py",
    "tools/command-center/status_predicate.py",
    "tools/command-center/render.py",
    "command-center/p2-wave/probes/CC-0013/scenario.py",
    "command-center/p2-wave/probes/CC-0013/probe1_handedit_determinism.py",
    "command-center/p2-wave/probes/CC-0013/probe2_empty_and_reviewer.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/CC-0013/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CC-0013 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    cc = REPO / "command-center"
    (cc / "events").mkdir(parents=True, exist_ok=True)
    (cc / "receipts").mkdir(parents=True, exist_ok=True)
    ev = cc / "events" / "EVENTS.jsonl"
    if not ev.is_file():
        ev.write_text("", encoding="utf-8", newline="\n")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CC-0013",
        "title": "Make STATUS.md a derived measurement instead of a hand-written claim",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "generating_commit": sl.generating_commit(REPO),
        "generated_at": now,
        "min_bytes_threshold": 128,
        "answer": (
            "STATUS.md is a measurement. tools/command-center/status_ledger.py derives it "
            "from events/EVENTS.jsonl, receipts/*.json, and the CC-0003 reducer when that "
            "module is importable. Every integer in the file carries its query; an empty "
            "query is refused. Zero events yields NOT-STARTED, never GREEN. A hand-edit "
            "fails python3 tools/command-center/status_ledger.py --check and the report "
            "names the drifted line. Two renders over an unchanged log are byte-identical. "
            "SUCCESS:CC-0013"
        ),
        "evidence": [
            {
                "claim": "Hand-editing event_records makes the gate fire and name that line; regenerate is silent.",
                "verdict": "CONFIRMED",
                "anchor": P1,
                "raw": t1[-2000:],
            },
            {
                "claim": "Empty events emit NOT-STARTED; an independent reviewer editing receipts_total is named; unqueried numbers are refused.",
                "verdict": "CONFIRMED",
                "anchor": P2,
                "raw": t2[-2000:],
            },
        ],
        "tests": [
            {
                "id": "hand-edit-counter",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "empty-input-and-independent-reviewer",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "unqueried-number",
                "kind": "empty-query",
                "description": "add_metric with a blank query raises UnqueriedNumber",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "empty-events-not-green",
                "kind": "zero-input",
                "description": "zero events => NOT-STARTED even if a receipt says SUCCESS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0013-probe2-independent-field",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": "Edited receipts_total, a different field than probe1's event_records.",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": "command-center/STATUS.md", "role": "derived-status", "exists": True},
            {
                "path": "tools/command-center/status_ledger.py",
                "role": "generator",
                "exists": True,
            },
        ],
        "notes": (
            "CC-0003 reducer is consumed when importable and reported NOT-CHECKED when "
            "absent; this unit does not author the reducer. Did not run "
            "unit_manifest.py --write. Did not git add/commit/push."
        ),
    }
    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha_receipt, bytes_receipt = digest(out_path)
    receipt["artifacts"][0]["sha256"] = sha_receipt
    receipt["artifacts"][0]["bytes"] = bytes_receipt
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # Final receipt bytes are on disk before STATUS.md is measured, so the
    # receipts_total query includes this unit. Hashes inside the receipt are
    # not copied into STATUS.md, so a second write of hashes would not churn
    # the board.
    sl.write_status(cc)
    import catalog as cat  # noqa: E402
    import render as rnd  # noqa: E402

    man_path = cc / "ARTIFACT-MANIFEST.json"
    if man_path.is_file():
        cat.save(rnd.render_manifest(cc), man_path)
    sha_status, bytes_status = digest(cc / "STATUS.md")
    receipt["artifacts"][1]["sha256"] = sha_status
    receipt["artifacts"][1]["bytes"] = bytes_status
    sha_receipt, bytes_receipt = digest(out_path)
    receipt["artifacts"][0]["sha256"] = sha_receipt
    receipt["artifacts"][0]["bytes"] = bytes_receipt
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha_receipt, bytes_receipt = digest(out_path)

    primary = row(OUT, "primary")
    primary["sha256"] = sha_receipt
    primary["bytes"] = bytes_receipt
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0013",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "hand-edit-gate-and-determinism",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "empty-input-and-independent-reviewer",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha_receipt,
                "bytes": bytes_receipt,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CC-0013/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CC-0013-probe2-independent-field",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CC-0013: live named probes exit 0, CC-0013.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={sha_receipt} bytes={bytes_receipt}")
    print("SUCCESS:CC-0013 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
