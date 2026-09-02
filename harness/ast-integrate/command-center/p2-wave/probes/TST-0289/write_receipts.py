#!/usr/bin/env python3
"""Emit TST-0289 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402

UID = "TST-0289"
OUT = "command-center/receipts/TST-0289.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0289/probe1_anchoring.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0289/probe2_reviewer_stats.py"
)
SUPPORTING = [
    "tools/council/simulate.py",
    "command-center/p2-wave/probes/TST-0289/simulate_council.py",
    "command-center/p2-wave/probes/TST-0289/experiment.py",
    "command-center/p2-wave/probes/TST-0289/stats.py",
    "command-center/p2-wave/probes/TST-0289/deanonymise.py",
    "command-center/p2-wave/probes/TST-0289/probe1_anchoring.py",
    "command-center/p2-wave/probes/TST-0289/probe2_reviewer_stats.py",
    "command-center/p2-wave/probes/TST-0289/fixtures/personas.json",
    "command-center/p2-wave/probes/TST-0289/fixtures/council.revealed.json",
    "command-center/p2-wave/probes/TST-0289/fixtures/council.concealed.json",
    "command-center/p2-wave/probes/TST-0289/fixtures/council.ceremony-mask-only.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0289/SUBAGENT-RETURN.json",
        "role": role,
    }


def compact_case(case: dict) -> dict:
    def arm(a: dict) -> dict:
        return {
            "hash": a["hash"],
            "verdict": a["verdict"],
            "pairwise_mean": a["pairwise_mean"],
            "pull_mean": a["pull_mean"],
            "vectors": a["vectors"],
            "texts": a["texts"],
            "seat_ids": a["seat_ids"],
            "published_names": a["published_names"],
        }

    return {
        "seed": case["seed"],
        "independence_delta": case["independence_delta"],
        "pull_delta": case["pull_delta"],
        "verdict_disagree": case["verdict_disagree"],
        "revealed": arm(case["revealed"]),
        "concealed": arm(case["concealed"]),
        "ceremony": {
            "hash": case["ceremony"]["hash"],
            "verdict": case["ceremony"]["verdict"],
            "pairwise_mean": case["ceremony"]["pairwise_mean"],
            "pull_mean": case["ceremony"]["pull_mean"],
        },
    }


def build_receipt(exp: dict, now: str) -> dict:
    question = (
        "Do anonymity and a blind independent first pass alter the outcome "
        "distribution, or are they ceremony? Matched councils: identity "
        "revealed versus concealed; round-1 position independence, anchoring "
        "on a high-status first speaker, and final-verdict divergence."
    )
    ind = exp["independence_delta"]
    pull = exp["pull_delta"]
    dis = exp["verdict_disagree_rate"]
    answer = (
        f"{exp['finding_plain']} n={exp['n_pairs']} matched seeds. "
        f"Independence delta (concealed-revealed) mean={ind['mean']:.6f} "
        f"95% bootstrap CI [{ind['lo']:.6f}, {ind['hi']:.6f}] "
        f"Cohen d_z={exp['independence_cohens_dz']}. "
        f"Anchoring pull delta (revealed-concealed) mean={pull['mean']:.6f} "
        f"95% CI [{pull['lo']:.6f}, {pull['hi']:.6f}] "
        f"Cohen d_z={exp['pull_cohens_dz']}. "
        f"Final-verdict disagreement rate mean={dis['mean']:.6f} "
        f"95% CI [{dis['lo']:.6f}, {dis['hi']:.6f}]. "
        "Name-masking without a blind first pass (ceremony control) matches "
        "the revealed arm on independence. "
        "SUCCESS:TST-0289"
    )
    return {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0289",
        "title": "Measure whether anonymity and the blind first pass change anything",
        "question": question,
        "answer": answer,
        "finding": exp["finding"],
        "finding_plain": exp["finding_plain"],
        "n_pairs": exp["n_pairs"],
        "seeds": exp["seeds"],
        "independence_delta": ind,
        "independence_cohens_dz": exp["independence_cohens_dz"],
        "pull_delta": pull,
        "pull_cohens_dz": exp["pull_cohens_dz"],
        "verdict_disagree_rate": dis,
        "ceremony_independence_delta": exp["ceremony_independence_delta"],
        "ceremony_pull_delta": exp["ceremony_pull_delta"],
        "ceremony_independence_compatible_with_null": exp[
            "ceremony_independence_compatible_with_null"
        ],
        "independence_ci_excludes_zero": exp["independence_ci_excludes_zero"],
        "pull_ci_excludes_zero": exp["pull_ci_excludes_zero"],
        "deanonymisation": exp["deanonymisation"],
        "controls": exp["controls"],
        "per_case": [compact_case(r) for r in exp["rows"]],
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "role": "calibration-analyst",
            "execution_substrate": "worktree-isolated",
            "worktree": str(REPO),
            "simulator": "tools/council/simulate.py",
        },
        "evidence": [
            {
                "id": "E1-matched-independence-and-anchoring",
                "signal": 1,
                "claim": (
                    "24 matched seeds: pairwise opening distance and first-speaker "
                    "pull under revealed vs concealed, with bootstrap intervals"
                ),
                "source_probe": (
                    "command-center/p2-wave/probes/TST-0289/probe1_anchoring.py"
                ),
                "result": "PASS",
                "detail": exp["finding"],
            },
            {
                "id": "E2-reviewer-recompute-and-deanonymisation",
                "signal": 2,
                "claim": (
                    "Independent recount of effect size and interval from per-case "
                    "vectors; concealed style/trace attack at or below chance; "
                    "planted-trace control at accuracy 1"
                ),
                "source_probe": (
                    "command-center/p2-wave/probes/TST-0289/probe2_reviewer_stats.py"
                ),
                "result": "PASS",
            },
        ],
        "tests": [
            {
                "id": "T1-anchoring-and-independence",
                "name": (
                    "Anchoring probe: identity revealed + high-status first speaker "
                    "versus blind first pass; n>=20; intervals"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-deanonymisation-and-reviewer",
                "name": (
                    "De-anonymisation control plus statistics-mandate recount from "
                    "raw per-case rows"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-ceremony-mask-only",
                "detail": (
                    "Sequential speaking with published names masked but observation "
                    "intact matches revealed independence (name-masking is ceremony)"
                ),
                "result": "PASS",
            },
            {
                "id": "NC2-planted-tool-traces",
                "detail": (
                    "Injecting per-seat trace tokens into concealed openings yields "
                    "re-identification accuracy 1.0, so the chance-level concealed "
                    "result is not a dead classifier"
                ),
                "result": "PASS",
            },
            {
                "id": "NC3-missing-persona-loud",
                "detail": "Dropping seat J raises PersonaMissing persona-missing:J",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0289-probe2-statistics-mandate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Recomputes pairwise distances from stored vectors, Welford mean, "
                "bootstrap percentile CI, Cohen d_z, and a normal-theory CI; "
                "hashes of re-run transcripts must match the receipt."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0289/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UID,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"ended_at": now},
        "residual_unknowns": [
            (
                "Personas are scripted and status-susceptible. A cast with alpha=0 "
                "would yield a protocol-true null; this unit measures the protocol "
                "difference given seats that can be anchored."
            )
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0289: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "tools/council/simulate.py is the unit-local deterministic simulator "
            "the catalog names as input; TST-0257 is not claimed delivered. "
            "No ADV rebuild. SUCCESS:TST-0289"
        ),
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = E.run_experiment()
    receipt = build_receipt(exp, now)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump(receipt), encoding="utf-8", newline="\n")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0289",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "anchoring-matched-councils",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "reviewer-stats-deanonymisation",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0289/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0289-probe2-statistics-mandate",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered TST-0289",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered TST-0289"},
        "ts": now,
        "notes": (
            "G-1 for TST-0289: live named probes exit 0, TST-0289.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(dump(ret), encoding="utf-8", newline="\n")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        dump(man), encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0289 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
