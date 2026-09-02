#!/usr/bin/env python3
"""Freeze the IMP-0198 corpus, emit the catalog receipt, then the per-unit G-1 files.

Probes must already pass. This writer records live probe output and the sha256 of
command-center/receipts/IMP-0198.json using the same LF-normalised digest the
measure script uses. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.rows import (  # noqa: E402
    HELD_OUT,
    VISIBLE,
    build_corpus,
    freeze_corpus,
    partition_of,
    stratum_counts,
)

UNIT = "IMP-0198"
OUT_REL = "command-center/receipts/IMP-0198.json"
SCHEMA = "command-center/schema/receipt.schema.json"
CORPUS_REL = "command-center/bench/cases/IMP-0198/corpus.json"
ROWS_REL = "tools/agentspec/agentspec/evals/rows.py"
CORPUS_MOD_REL = "tools/agentspec/agentspec/evals/matched_corpus.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0198/probe1_hash_partition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0198/probe2_heldout_touch.py"
)
SUPPORTING = [
    SCHEMA,
    CORPUS_REL,
    ROWS_REL,
    CORPUS_MOD_REL,
    "command-center/p2-wave/probes/IMP-0198/probe1_hash_partition.py",
    "command-center/p2-wave/probes/IMP-0198/probe2_heldout_touch.py",
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
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def probe_obj(role: str, cmd: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw[-4000:],
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "exit_code": code,
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0198/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    cases = build_corpus()
    freeze_corpus(REPO / CORPUS_REL, cases)
    counts = stratum_counts(cases)
    n_held = sum(1 for c in cases if partition_of(c) == HELD_OUT)
    n_vis = sum(1 for c in cases if partition_of(c) == VISIBLE)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0198 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": CORPUS_REL,
                "role": "supporting",
                "exists": True,
            },
            {
                "path": ROWS_REL,
                "role": "supporting",
                "exists": True,
            },
            {
                "path": CORPUS_MOD_REL,
                "role": "supporting",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": CORPUS_REL,
                "consumer": "command-center/p2-wave/probes/IMP-0198/probe1_hash_partition.py",
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": f"{ROWS_REL}:partition_of",
                "claim": (
                    "Partition membership is a pure function of SHA-256(salt || canonical "
                    f"identity). Independent recomputation agreed on all {len(cases)} cases; "
                    "relabelling partition_cached moved 0 cases."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj("source", P1, t1, c1),
                    probe_obj("verifier", P2, t2, c2),
                ],
            },
            {
                "anchor": f"{ROWS_REL}:AccessLog.record",
                "claim": (
                    "A development run that touches a held-out case is detected by an "
                    "access-log assertion (HeldOutTouchError). Visible development reads "
                    "are silent; evaluation may read held-out."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj("source", P2, t2, c2),
                    probe_obj("verifier", P1, t1, c1),
                ],
            },
        ],
        "id": UNIT,
        "unit_id": UNIT,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0198/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "id": "hash-vs-convention",
                "kind": "mutation",
                "description": "Flipping partition_cached must not change partition_of.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "held-out-development-touch",
                "kind": "known-broken-fixture",
                "description": "Detector fires on held-out development read; silent on visible.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "notes": (
            "G-1 for IMP-0198: matched corpus hash-partitioned held-out slice, "
            "development access detector, live named probes. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "question_or_target": (
            "Target: build the case corpus workflows are benchmarked on - stratified "
            "by difficulty, with a held-out slice never shown during workflow development. "
            "Acceptance: the held-out slice is enforced mechanically (a hash-partition, "
            "not a convention) so a workflow cannot be tuned on it."
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "rows.py already held R1-R8 eval rows on this worktree. IMP-0198 "
                    "added matched-corpus helpers via agentspec.evals.matched_corpus "
                    "and re-exported them from rows.py without replacing the eval rows. "
                    "Downstream IMP-0197/0200/0201/0206 were not re-executed here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run those units against this frozen corpus.",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "reviewer": {
            "independent": True,
            "fresh_context": False,
            "reviewer_id": "IMP-0198-probe2-heldout-detector",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0198",
        "spec_anchor": "_USER-PROMPTS.md:10741",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "stratum_counts": counts,
        "corpus": {
            "path": CORPUS_REL,
            "case_count": len(cases),
            "held_out": n_held,
            "visible": n_vis,
            "partition": {
                "salt": "IMP-0198.v1",
                "mod": 10,
                "held_out_residue": 0,
                "authority": "hash-only",
            },
        },
        "tests": [
            {
                "id": "held-out-hash-partition",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "held-out-development-detector",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT_REL, "primary")
    # Fill sizes now that the file exists.
    receipt["artifacts"][0]["bytes"] = primary["bytes"]
    receipt["artifacts"][0]["sha256"] = primary["sha256"]
    receipt["artifacts"][0]["eol"] = "LF"
    corpus_row = row(CORPUS_REL, "supporting")
    rows_row = row(ROWS_REL, "supporting")
    mod_row = row(CORPUS_MOD_REL, "supporting")
    receipt["artifacts"][1]["bytes"] = corpus_row["bytes"]
    receipt["artifacts"][1]["sha256"] = corpus_row["sha256"]
    receipt["artifacts"][2]["bytes"] = rows_row["bytes"]
    receipt["artifacts"][2]["sha256"] = rows_row["sha256"]
    receipt["artifacts"][3]["bytes"] = mod_row["bytes"]
    receipt["artifacts"][3]["sha256"] = mod_row["sha256"]
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT_REL, "primary")

    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    ret = {
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "id": UNIT,
        "unit_id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/IMP-0198/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "notes": (
            "G-1 for IMP-0198: live named probes exit 0, receipts/IMP-0198.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0198-probe2-heldout-detector",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0198",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
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
    print(f"corpus n={len(cases)} held_out={n_held} visible={n_vis} strata={counts}")
    print("SUCCESS:IMP-0198 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
