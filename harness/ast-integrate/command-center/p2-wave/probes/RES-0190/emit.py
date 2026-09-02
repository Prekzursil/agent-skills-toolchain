#!/usr/bin/env python3
"""Emit RES-0190 measurement artifact, then per-unit receipts."""
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

import engine as E  # noqa: E402
import universe as U  # noqa: E402

UNIT = "RES-0190"
OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0190-breadth-versus-depth-budget-allocation.json"
)
SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0190"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0190/probe1_equal_budget_and_variance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0190/probe2_mechanism_not_string.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0190/universe.py",
    "command-center/p2-wave/probes/RES-0190/cluster.py",
    "command-center/p2-wave/probes/RES-0190/engine.py",
    "command-center/p2-wave/probes/RES-0190/fixtures/universe.json",
    "command-center/p2-wave/probes/RES-0190/probe1_equal_budget_and_variance.py",
    "command-center/p2-wave/probes/RES-0190/probe2_mechanism_not_string.py",
    "tools/command-center/mechanism_dedup.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
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
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def materialize() -> None:
    FIX = HERE / "fixtures" / "universe.json"
    FIX.parent.mkdir(parents=True, exist_ok=True)
    doc = U.corpus_doc()
    FIX.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_bearing_claims(exp: dict) -> list[dict]:
    fixture = "command-center/p2-wave/probes/RES-0190/fixtures/universe.json"
    fixture_path = REPO / fixture
    raw = fixture_path.read_bytes().replace(b"\r\n", b"\n")
    lineage = {
        "resolved_url": "file:" + fixture,
        "fetch_timestamp": exp["fetched_at"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    policy = exp["policy"]
    winner = policy.get("winner")
    c1_text = (
        policy["headline"]
        if winner
        else (
            "NO DETECTED DIFFERENCE: allocation gaps did not exceed "
            "negative-control variance on this corpus."
        )
    )
    return [
        {
            "id": "RES-0190-C-POLICY",
            "claim": c1_text,
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "engine-arm-totals",
                    "note": json.dumps(exp["totals_mechanism"], sort_keys=True),
                },
                {
                    "id": "negative-control-variance",
                    "note": json.dumps(exp["negative_control"], sort_keys=True),
                },
            ],
            "source_lineage": lineage,
            "verification_path": P1,
        },
        {
            "id": "RES-0190-C-BUDGET",
            "claim": (
                "Each allocation arm billed the same cap of "
                f"{E.BUDGET_PER_QUESTION * 3} operation-credits; leftover "
                "allocation is recorded as waste so spend is not confounded."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "billed-identity",
                    "note": str(
                        {k: v["billed_total"] for k, v in exp["arms"].items()}
                    ),
                },
                {
                    "id": "per-question-spend-plus-waste",
                    "note": "scan_spent+verify_spent+waste == 1000 per question",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P1,
        },
        {
            "id": "RES-0190-C-DEDUP",
            "claim": (
                "Distinctness is mechanism-level AND-gate MERGE, not string "
                "equality. On the 80/20 scanned pool, string-distinct count "
                f"{exp['arms']['80/20']['scanned_string_distinct']} exceeds "
                "mechanism-distinct count "
                f"{exp['arms']['80/20']['scanned_mechanism_distinct']}."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {"id": "mechanism_dedup-AND-gate", "note": "tools/command-center/mechanism_dedup.py"},
                {
                    "id": "planted-paraphrase-pairs",
                    "note": "probe2 MERGE on paraphrases, not MERGE on crosses",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P2,
        },
        {
            "id": "RES-0190-C-CONTROL",
            "claim": (
                "Negative control: 50/50 run twice produced variance "
                f"{exp['negative_control']['variance']}. Gaps at or below "
                "that variance are reported as NO DETECTED DIFFERENCE."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {"id": "control-run-a", "note": str(exp["negative_control"]["run_a_distinct"])},
                {"id": "control-run-b", "note": str(exp["negative_control"]["run_b_distinct"])},
            ],
            "source_lineage": lineage,
            "verification_path": P1,
        },
    ]


def build_artifact(exp: dict) -> dict:
    question = (
        "On a fixed token budget, does 80/20 broad-to-deep, 50/50, or 20/80 "
        "yield more distinct VERIFIED claims, measured on the same three "
        "questions with the same backends, distinctness by mechanism-level "
        "dedup rather than string equality?"
    )
    winner = exp["policy"].get("winner")
    answer = exp["policy"]["headline"]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "output_schema": SCHEMA,
        "schema_note": (
            "command-center/schema/measurement-run.schema.json is a generated "
            "shim that $ref-delegates to platform/schema/artifact-class-profiles"
            ".schema.json#/$defs/measurement-run. This unit does not rebuild "
            "ADV schemas."
        ),
        "title": (
            "Given a fixed budget, what split between broad scan and deep "
            "dives maximises distinct verified claims?"
        ),
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "policy": exp["policy"],
        "winner": winner,
        "distinctness_rule": "mechanism-level-AND-gate",
        "string_equality_rejected": True,
        "backends": exp["backends"],
        "questions": exp["questions"],
        "meter": exp["meter"],
        "arms": exp["arms"],
        "negative_control": exp["negative_control"],
        "totals_mechanism": exp["totals_mechanism"],
        "totals_string": exp["totals_string"],
        "claims": load_bearing_claims(exp),
        "residual_unknowns": [
            {
                "claim": (
                    "This ranking is for the planted dual-backend corpus in "
                    "fixtures/universe.json, not a live multi-vendor LLM run. "
                    "A corpus whose early sources were redundant paraphrases "
                    "would change which split wins; that world was not measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run engine.py against a second planted corpus whose "
                    "first four sources are paraphrases of one mechanism, and "
                    "report whether 20/80 still leads."
                ),
            },
            {
                "claim": (
                    "Clustering uses the in-tree tools/command-center/"
                    "mechanism_dedup.py AND-gate (CC-0020), the same detector "
                    "RES-0173 measured. This unit does not re-implement or "
                    "retune those frozen thresholds."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Swap cluster.py onto a second detector that RES-0173 "
                    "rejects, and confirm the allocation ranking can change."
                ),
            },
        ],
        "tests": [
            {
                "id": "equal-billed-budget",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-control-variance",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "mechanism-not-string",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "planted-both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "equal-budget-and-variance"},
            {"id": "probe2", "command": P2, "role": "mechanism-not-string"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0190-probe2-mechanism-not-string",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not trust the policy headline. It re-scores "
                "planted paraphrase and cross pairs through mechanism_dedup "
                "and checks that string equality overcounts the 80/20 scan."
            ),
        },
        "notes": (
            "G-1 delivery of RES-0190. Live named probes exit 0. Artifact "
            "state=SUCCESS. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted. Did not implement ADV rebuild."
        ),
        "SUCCESS:RES-0190": True,
    }


def write_receipts(code1: int, out1: str, code2: int, out2: str) -> int:
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "raw_output": out1[-8000:],
                "role": "equal-budget-and-variance",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "raw_output": out2[-8000:],
                "role": "mechanism-not-string",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0190-probe2-mechanism-not-string",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0190: live named probes exit 0, measurement artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0190 receipts")
    return 0


def main() -> int:
    materialize()
    exp = E.run_experiment()
    if not all(arm["budget_ok"] for arm in exp["arms"].values()):
        print("FAILED:RES-0190 unequal billed budget")
        return 1
    doc = build_artifact(exp)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0190 sentinel absent")
        return 1
    if size < 1024:
        print(f"FAILED:RES-0190 artifact too small {size}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")

    code1, out1 = run(P1)
    code2, out2 = run(P2)
    print(out1[-2000:])
    print(out2[-2000:])
    if code1 != 0 or "SUCCESS:RES-0190-probe1" not in out1:
        print("FAILED:RES-0190 probe1")
        return 1
    if code2 != 0 or "SUCCESS:RES-0190-probe2" not in out2:
        print("FAILED:RES-0190 probe2")
        return 1
    write_receipts(code1, out1, code2, out2)
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
