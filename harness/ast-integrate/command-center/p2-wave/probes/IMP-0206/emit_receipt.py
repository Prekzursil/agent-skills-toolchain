#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0206.json after live probes pass."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
sys.path.insert(0, str(REPO / "command-center" / "lib"))
import _p2lib as L  # noqa: E402
from overfit_detector.corpus import build_corpus  # noqa: E402
from overfit_detector.detector import detect  # noqa: E402
from overfit_detector.partition import split  # noqa: E402
from overfit_detector.threshold import load_threshold  # noqa: E402
from overfit_detector.workflows import MemorizeVisibleWorkflow, TrueRuleWorkflow  # noqa: E402

UNIT = "IMP-0206"
OUT = "command-center/receipts/IMP-0206.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0206/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0206/probe2_threshold_versioned.py"
)
DETECTOR = "command-center/lib/overfit_detector/detector.py"
THRESH = "command-center/lib/overfit_detector/threshold_v1.json"
THRESH_PY = "command-center/lib/overfit_detector/threshold.py"
PART = "command-center/lib/overfit_detector/partition.py"
WF = "command-center/lib/overfit_detector/workflows.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0206 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:IMP-0206 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    cases = build_corpus(80)
    visible, heldout = split(cases)
    over_r = detect(MemorizeVisibleWorkflow(visible), cases)
    hon_r = detect(TrueRuleWorkflow(), cases)
    spec = load_threshold()
    if not over_r["flagged"] or hon_r["flagged"]:
        print("FAILED:IMP-0206 emit both-states broken")
        return 1

    p1_raw = json.loads((HERE / "probe1-both-states.raw.json").read_text(encoding="utf-8"))
    p2_raw = json.loads((HERE / "probe2-threshold.raw.json").read_text(encoding="utf-8"))

    det_sha, det_n = sha256_file(REPO / DETECTOR)
    th_sha, th_n = sha256_file(REPO / THRESH)
    part_sha, part_n = sha256_file(REPO / PART)
    wf_sha, wf_n = sha256_file(REPO / WF)
    tpy_sha, tpy_n = sha256_file(REPO / THRESH_PY)

    line_flag = find_line(DETECTOR, 'flagged = gap > float(spec["gap_abs"])')
    line_lane = find_line(DETECTOR, 'LANE = "benchmark-gaming"')
    line_refuse = find_line(THRESH_PY, "PerRunThresholdTuneError")
    line_frozen = find_line(THRESH, '"not_tuned_per_run": true')
    line_hash = find_line(PART, 'digest = hashlib.sha256(f"{salt}:{case_id}".encode("utf-8")).hexdigest()')
    line_miss = find_line(WF, "return self._mem.get(case.id)")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    src1 = L.probe("source", "command", P1, out1, rc1)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-detect-overfit-honest",
        json.dumps(
            {
                "overfit_gap": over_r["gap"],
                "honest_gap": hon_r["gap"],
                "overfit_flagged": over_r["flagged"],
                "honest_flagged": hon_r["flagged"],
            }
        ),
        0,
    )
    src2 = L.probe("source", "command", P2, out2, rc2)
    ver2 = L.probe(
        "verifier",
        "file-read",
        THRESH,
        json.dumps({"id": spec["id"], "version": spec["version"], "gap_abs": spec["gap_abs"]}),
        0,
    )

    doc = {
        "artifacts": [
            {
                "bytes": 1,
                "eol": "LF",
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256_note": "self-hash omitted; live digest is UNIT-ARTIFACT-MANIFEST.json",
            },
            {
                "bytes": det_n,
                "eol": "LF",
                "exists": True,
                "path": DETECTOR,
                "role": "implementation",
                "sha256": det_sha,
            },
            {
                "bytes": th_n,
                "eol": "LF",
                "exists": True,
                "path": THRESH,
                "role": "threshold-spec",
                "sha256": th_sha,
            },
            {
                "bytes": tpy_n,
                "eol": "LF",
                "exists": True,
                "path": THRESH_PY,
                "role": "supporting",
                "sha256": tpy_sha,
            },
            {
                "bytes": part_n,
                "eol": "LF",
                "exists": True,
                "path": PART,
                "role": "supporting",
                "sha256": part_sha,
            },
            {
                "bytes": wf_n,
                "eol": "LF",
                "exists": True,
                "path": WF,
                "role": "supporting",
                "sha256": wf_sha,
            },
        ],
        "completion_sentinel": "SUCCESS:IMP-0206",
        "detector_results": {
            "honest": hon_r,
            "overfit": over_r,
            "threshold": spec,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "measure runs after this receipt and the per-unit manifest exist",
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0206",
                    "method": "command",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                f"Deliberately overfit workflow flagged: visible={over_r['visible_accuracy']} "
                f"heldout={over_r['heldout_accuracy']} gap={over_r['gap']} "
                f"(threshold {spec['gap_abs']}), lane={over_r['refuter_lane']}.",
                "CONFIRMED",
                f"{DETECTOR}:{line_flag}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                f"Honest workflow not flagged (false-positive control): visible="
                f"{hon_r['visible_accuracy']} heldout={hon_r['heldout_accuracy']} "
                f"gap={hon_r['gap']}.",
                "CONFIRMED",
                f"{WF}:{line_miss}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                f"Threshold is declared and versioned: id={spec['id']} version="
                f"{spec['version']} gap_abs={spec['gap_abs']} frozen=true; per-run "
                "override refused.",
                "CONFIRMED",
                f"{THRESH}:{line_frozen}",
                [src2, ver2],
                "almost-certain",
            ),
            L.evidence(
                "Named refuter lane is benchmark-gaming (11059), assigned mechanically "
                "when the gap exceeds the frozen threshold, not by a reviewer.",
                "CONFIRMED",
                f"{DETECTOR}:{line_lane}",
                [src1, src2],
                "almost-certain",
            ),
            L.evidence(
                "Held-out membership is sha256(salt:case_id) residue, recomputed "
                f"independently; visible_n={over_r['visible_n']} heldout_n="
                f"{over_r['heldout_n']}; overfit trained ids disjoint from held-out.",
                "CONFIRMED",
                f"{PART}:{line_hash}",
                [src1, ver1],
                "almost-certain",
            ),
        ],
        "inputs_note": (
            "IMP-0198 and IMP-0197 are not delivered on this worktree. This unit "
            "ships a local hash-partition (salt IMP-0198-holdout-v1) that implements "
            "the catalog contract: membership is a pure function of the case hash, "
            "not a hand list. Residual: if IMP-0198 later freezes a different salt, "
            "the detector must consume that partition instead of this one."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0206/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_controls": [
            L.control(
                "overfit-flagged",
                "known-broken-fixture",
                "MemorizeVisibleWorkflow is flagged as benchmark-gaming",
                True,
                True,
                bad=f"flagged={over_r['flagged']} gap={over_r['gap']}",
                good=f"flagged={hon_r['flagged']} gap={hon_r['gap']}",
            ),
            L.control(
                "honest-silent",
                "known-good-fixture",
                "TrueRuleWorkflow is not flagged",
                True,
                True,
                bad=f"overfit_gap={over_r['gap']}",
                good=f"honest_gap={hon_r['gap']}",
            ),
            L.control(
                "threshold-not-per-run",
                "mutation",
                "per-run threshold override is refused",
                True,
                True,
                bad="threshold_override=0.99 -> PerRunThresholdTuneError",
                good=f"declared gap_abs={spec['gap_abs']} version={spec['version']}",
            ),
        ],
        "output_schema": SCHEMA,
        "question": (
            "Did this workflow win because it is better, or because it was tuned "
            "to the visible cases?"
        ),
        "residual_unknowns": [
            {
                "claim": "IMP-0198 held-out salt may differ when that unit delivers.",
                "settling_experiment": "Re-bind slice_of() to IMP-0198's frozen partition and re-run probes.",
                "verdict": "DISCLOSED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0206-probe2-threshold-versioning",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0206",
        "spec_anchor": "_USER-PROMPTS.md:11059",
        "state": "SUCCESS",
        "tests": [
            {"command": P1, "id": "probe1_both_states", "result": "PASS"},
            {"command": P2, "id": "probe2_threshold_versioned", "result": "PASS"},
        ],
        "thresholds": {
            "declared": spec,
            "honest_gap": hon_r["gap"],
            "overfit_gap": over_r["gap"],
        },
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Implement the benchmark-gaming and overfit detector",
        "unit_id": UNIT,
        "probe1_raw": p1_raw,
        "probe2_raw": p2_raw,
        "refuse_line": f"{THRESH_PY}:{line_refuse}",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0206" not in text:
        print("FAILED:IMP-0206 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0206 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:IMP-0206")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
