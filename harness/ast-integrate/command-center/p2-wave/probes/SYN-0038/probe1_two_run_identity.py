#!/usr/bin/env python3
"""Probe 1: two isolated-worktree runs of declared-deterministic stages.

Source measurement. Distinct fingerprint from probe 2. Re-runs the pipeline
and requires byte-identical CRLF-normalised hashes, then checks those hashes
against the receipt. Does not re-evaluate the planted-clock detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402
import schema_ctl as S  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0038.json"
SENTINEL_PREFIX = "SUCCESS:SYN-0038"


def main() -> int:
    exp = P.run_experiment(REPO)
    stages = {s["id"]: s for s in exp["stages"]}
    out = {
        "probe": "probe1-two-run-identity",
        "unit_id": "SYN-0038",
        "worktrees_used": exp["worktrees_used"],
        "deterministic_all_identical": exp["checks"]["deterministic_all_identical"],
        "crlf_normalized": exp["checks"]["crlf_normalized"],
        "crlf_naive_hashes_differ": exp["controls"]["crlf"]["naive_hashes_differ"],
        "temp_path_not_in_payload": exp["checks"]["temp_path_not_in_payload"],
        "join_clean_all_zero": exp["checks"]["join_clean_all_zero"],
        "stage_ids": sorted(stages),
        "stage_hashes": {
            sid: {"run1": stages[sid]["sha256_run1"], "run2": stages[sid]["sha256_run2"]}
            for sid in sorted(stages)
        },
        "pinned_input_sha256": exp["pinned_input_sha256"],
        "recorded_seed": exp["recorded_seed"],
        "pass": bool(
            exp["checks"]["deterministic_all_identical"]
            and exp["checks"]["crlf_normalized"]
            and exp["checks"]["temp_path_not_in_payload"]
            and exp["worktrees_used"] == 2
            and len(stages) == 6
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        print("FAILED:SYN-0038-probe1 two-run identity")
        print(json.dumps(exp["checks"], sort_keys=True))
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:SYN-0038-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0038-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL_PREFIX not in text:
        print("FAILED:SYN-0038-probe1 sentinel absent")
        return 1
    payload = S.domain(doc)
    rec_stages = {s["id"]: s for s in payload.get("stages") or doc.get("stages") or []}
    if set(rec_stages) != set(stages):
        print("FAILED:SYN-0038-probe1 stage id set drift")
        return 1
    for sid, live in stages.items():
        rec = rec_stages[sid]
        if rec.get("sha256_run1") != live["sha256_run1"]:
            print(f"FAILED:SYN-0038-probe1 {sid} run1 hash drift")
            return 1
        if rec.get("sha256_run2") != live["sha256_run2"]:
            print(f"FAILED:SYN-0038-probe1 {sid} run2 hash drift")
            return 1
        if rec.get("identical") is not True:
            print(f"FAILED:SYN-0038-probe1 {sid} not identical in receipt")
            return 1
    pin = payload.get("pinned_input_sha256") or doc.get("pinned_input_sha256")
    if pin != exp["pinned_input_sha256"]:
        print("FAILED:SYN-0038-probe1 pinned input sha drift")
        return 1
    seed = payload.get("recorded_seed") or doc.get("recorded_seed")
    if seed != exp["recorded_seed"]:
        print("FAILED:SYN-0038-probe1 seed drift")
        return 1
    identical = payload.get("deterministic_all_identical")
    if identical is None:
        identical = doc.get("deterministic_all_identical")
    if identical is not True:
        print("FAILED:SYN-0038-probe1 receipt deterministic_all_identical")
        return 1
    src = str(payload.get("source_probe") or doc.get("source_probe") or "")
    ver = str(payload.get("verifier_probe") or doc.get("verifier_probe") or "")
    if len(src) < 16 or len(ver) < 16 or src == ver:
        print("FAILED:SYN-0038-probe1 source/verifier probe collision")
        return 1
    print(
        f"identical={out['deterministic_all_identical']} "
        f"crlf={out['crlf_normalized']} stages={len(stages)} "
        f"worktrees={out['worktrees_used']}"
    )
    print("SUCCESS:SYN-0038-probe1 two-run deterministic identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
