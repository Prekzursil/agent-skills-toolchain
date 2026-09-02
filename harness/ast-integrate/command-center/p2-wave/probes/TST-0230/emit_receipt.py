#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0230.json from live named probes.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
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
sys.path.insert(0, str(REPO / "tools"))

from bench.nonempty import (  # noqa: E402
    CONTROL_BYTES,
    DECLARED_FLOOR,
    ESTATE_SEED_IDS,
    MIN_TIMING_DELTA_NS,
    control_case,
    empty_case,
    estate_seed_router_empty,
    estate_seed_suite_empty,
    mutant_score_empty,
    naive_score,
    run_case,
    run_suite,
    timing_separation,
)

UNIT = "TST-0230"
OUT = "command-center/receipts/TST-0230.json"
SENTINEL = "SUCCESS:TST-0230"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/benchmark_result"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0230/probe1_empty_flagged_not_scored.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0230/probe2_seeds_and_timing.py"
)
QUESTION = (
    "Does every benchmark case run on a non-empty input above a declared "
    "floor, so a green cannot be produced by measuring nothing? PASS requires "
    "a per-case input-size assertion plus one control case with known "
    "non-zero work whose timing must sit measurably above noise."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    if "SUCCESS:TST-0230-probe1" not in t1:
        print("FAILED:TST-0230 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0230-probe2" not in t2:
        print("FAILED:TST-0230 emit probe2 sentinel missing")
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0230 emit probe JSON pass=false")
        return 1

    empty = run_case(empty_case())
    mutant = mutant_score_empty(empty_case())
    control = run_case(control_case())
    naive_r = naive_score(estate_seed_router_empty())
    naive_s = naive_score(estate_seed_suite_empty())
    live_r = run_case(estate_seed_router_empty())
    live_s = run_case(estate_seed_suite_empty())
    suite = run_suite(
        [estate_seed_router_empty(), estate_seed_suite_empty(), control_case()]
    )
    timing = timing_separation()
    if empty.get("status") != "FLAGGED" or "score" in empty:
        print("FAILED:TST-0230 emit empty case was scored")
        return 1
    if control.get("status") != "SCORED":
        print("FAILED:TST-0230 emit control was not scored")
        return 1
    if not timing.get("separated"):
        print("FAILED:TST-0230 emit timing not separated", timing)
        return 1
    if live_r.get("status") != "FLAGGED" or live_s.get("status") != "FLAGGED":
        print("FAILED:TST-0230 emit seeds not flagged")
        return 1
    if naive_r.get("status") != "SCORED" or naive_s.get("status") != "SCORED":
        print("FAILED:TST-0230 emit naive seeds were not historically green")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec("verifier", "mutant-score-empty", P1, t1, c1)
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec("verifier", "naive-estate-seeds", P2, t2, c2)

    impl = artifact_row("tools/bench/nonempty.py", "primary-implementation")
    supporting = [
        "tools/bench/schema/nonempty-result.schema.json",
        "tools/bench/__init__.py",
        "command-center/p2-wave/probes/TST-0230/probe1_empty_flagged_not_scored.py",
        "command-center/p2-wave/probes/TST-0230/probe2_seeds_and_timing.py",
        "command-center/p2-wave/probes/TST-0230/fixtures/empty.json",
        "command-center/p2-wave/probes/TST-0230/fixtures/below-floor.json",
        "command-center/p2-wave/probes/TST-0230/fixtures/control.json",
        "command-center/p2-wave/probes/TST-0230/fixtures/seed-router-empty.json",
        "command-center/p2-wave/probes/TST-0230/fixtures/seed-suite-empty.json",
        "command-center/p2-wave/probes/TST-0230/emit_receipt.py",
    ]
    artifacts = [impl] + [artifact_row(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:{UNIT} emit missing {missing}")
        return 1

    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Every benchmark case has a proven non-empty input",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0230; "
            "_USER-PROMPTS.md:11021 / :10656-10657 / :11385 "
            "(file absent on this sparse worktree)"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": (
            "tools/bench/nonempty.py is the per-case input-size gate. Every "
            "result row records input_bytes and input_items against a declared "
            f"floor min_bytes={DECLARED_FLOOR['min_bytes']} "
            f"min_items={DECLARED_FLOOR['min_items']}. Empty or below-floor "
            "cases are FLAGGED with no score field. A 64KiB control hashes "
            f"{CONTROL_BYTES} bytes x 250 rounds and times "
            f"delta_ns={timing['delta_ns']} above the empty path "
            f"(min {MIN_TIMING_DELTA_NS} ns). Two estate seeds that used to "
            "score empty input as a numeric green are now FLAGGED. "
            "SUCCESS:TST-0230"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "registered": True,
        "implementation": {
            "gate": "tools/bench/nonempty.py:run_case",
            "schema": "tools/bench/schema/nonempty-result.schema.json",
            "floor": {
                "min_bytes": DECLARED_FLOOR["min_bytes"],
                "min_items": DECLARED_FLOOR["min_items"],
            },
            "rule": (
                "FLAGGED rows omit score. SCORED rows record input_bytes, "
                "input_items, elapsed_ns, digest. Naive historical scorer "
                "still emits score=0 on empty input as the detector control."
            ),
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md:11021": "absent on this sparse worktree",
            "routing-benchmark.yml": "absent; estate seeds reconstructed as fixtures",
            "tools/bench/evaluate.py": (
                "present; scores cell identity with no case payload — left "
                "unchanged so TST-0320 resume matching stays deterministic. "
                "This unit's gate is the independent nonempty path."
            ),
            "two_estate_empty_greens": list(ESTATE_SEED_IDS),
        },
        "declared_floor": {
            "min_bytes": DECLARED_FLOOR["min_bytes"],
            "min_items": DECLARED_FLOOR["min_items"],
        },
        "live_gate": {
            "empty": {
                "status": empty["status"],
                "reason_id": empty["reason_id"],
                "input_bytes": empty["input_bytes"],
                "input_items": empty["input_items"],
                "score_present": "score" in empty,
            },
            "control": {
                "status": control["status"],
                "input_bytes": control["input_bytes"],
                "input_items": control["input_items"],
                "elapsed_ns": control["elapsed_ns"],
                "score": control["score"],
            },
            "mutant_scores_empty": mutant.get("status") == "SCORED"
            and mutant.get("score") == 0,
            "estate_seeds": {
                "ids": list(ESTATE_SEED_IDS),
                "naive_router_score": naive_r.get("score"),
                "naive_suite_score": naive_s.get("score"),
                "live_router": live_r.get("status"),
                "live_suite": live_s.get("status"),
            },
            "suite": {
                "flagged_n": suite["flagged_n"],
                "scored_n": suite["scored_n"],
                "all_counts_recorded": suite["all_counts_recorded"],
            },
            "timing": {
                "empty_median_ns": timing["empty_median_ns"],
                "control_median_ns": timing["control_median_ns"],
                "delta_ns": timing["delta_ns"],
                "min_delta_ns": timing["min_delta_ns"],
                "separated": timing["separated"],
                "control_bytes": timing["control_bytes"],
                "work_units_control": timing["work_units_control"],
                "work_units_empty": timing["work_units_empty"],
            },
        },
        "tests": [
            {
                "id": "detector-control-empty-flagged-not-scored",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": (
                    "An intentionally empty case must be FLAGGED, not scored."
                ),
            },
            {
                "id": "regression-seed-two-empty-greens",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": (
                    "Two estate benches that measured EMPTY inputs and returned "
                    "a clean meaningless green are reconstructed; live gate flags "
                    "both; control timing sits above noise."
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Per-case input_bytes and input_items are recorded on every "
                    "row, including FLAGGED empty rows (bytes=0, items=0) and "
                    f"the scored control (bytes={control['input_bytes']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/nonempty.py:run_case",
                "confidence": "almost-certain",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "Control case timing is above the empty path: "
                    f"empty_median_ns={timing['empty_median_ns']} "
                    f"control_median_ns={timing['control_median_ns']} "
                    f"delta_ns={timing['delta_ns']} "
                    f"(floor {MIN_TIMING_DELTA_NS} ns)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/nonempty.py:timing_separation",
                "confidence": "almost-certain",
                "probes": [p2, p2v],
            },
            {
                "claim": (
                    "Detector control: mutant_score_empty stamps score=0 on the "
                    "empty case (status=SCORED); live run_case omits score "
                    f"(status={empty['status']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/nonempty.py:mutant_score_empty",
                "confidence": "almost-certain",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    f"Regression seeds {list(ESTATE_SEED_IDS)}: naive_score "
                    f"emits score=0 SCORED; live gate FLAGGED both."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/nonempty.py:naive_score",
                "confidence": "almost-certain",
                "probes": [p2, p2v],
            },
        ],
        "negative_controls": [
            {
                "id": "mutant-score-empty",
                "kind": "both-states",
                "description": (
                    "A mutant that scores empty input as 0 produces a "
                    "meaningless green. Live gate must FLAG and omit score."
                ),
                "fired_on_bad_state": bool(j1.get("mutant_scores_empty")),
                "silent_on_good_state": bool(j1.get("live_disagrees_with_mutant")),
            },
            {
                "id": "naive-estate-empty-green",
                "kind": "both-states",
                "description": (
                    "Historical harnesses scored two empty-input benches green. "
                    "Live gate flags both seeds."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(j2.get("live_disagrees_with_mutant")),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0230-probe2-seeds-and-timing",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a second path: estate-seed reconstruction plus "
                "an independent timing median, not the probe-1 mutant. Catalog "
                "asks for a cross-vendor reviewer plus a Claude reviewer; those "
                "human passes are residual and are not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0230/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "role": "empty-flagged-not-scored", "command": P1},
            {"id": "probe2", "role": "seeds-and-timing", "command": P2},
        ],
        "artifacts": artifacts,
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A cross-vendor plus Claude "
                    "reviewer pair in a fresh context has not scored this unit."
                ),
            },
            {
                "id": "evaluate-py-still-payload-free",
                "text": (
                    "tools/bench/evaluate.py still scores the cell four-tuple "
                    "with no payload so TST-0320 kill/resume matching stays "
                    "deterministic. Tournament cells do not yet flow through "
                    "run_case. Settling experiment: wrap evaluate_cell with "
                    "the nonempty gate without breaking TST-0320 probes."
                ),
            },
            {
                "id": "spec-file-absent",
                "text": (
                    "_USER-PROMPTS.md is not on this worktree. The gate "
                    "implements the catalog target."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a human adversarial reviewer in a fresh context scored PASS",
            "tools/bench/evaluate.py now refuses empty payloads",
        ],
        "notes": (
            "G-1 for TST-0230: live named probes exit 0, "
            "receipts/TST-0230.json state=SUCCESS with SUCCESS:TST-0230, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. cloud ok=true is not delivery. No ADV rebuild. "
            "SUCCESS:TST-0230"
        ),
        "ts": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:TST-0230 emit catalog sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0230 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0230 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
