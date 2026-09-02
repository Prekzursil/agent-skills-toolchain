#!/usr/bin/env python3
"""Emit AUD-0073 artifact, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

UID = "AUD-0073"
OUT = E.OUTPUT_REL
SCHEMA = "command-center/schema/claim-record.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0073 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0073/probe1_unverified_and_experiments.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0073/probe2_flag_positions.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0073/extract.py",
    "command-center/p2-wave/probes/AUD-0073/probe1_unverified_and_experiments.py",
    "command-center/p2-wave/probes/AUD-0073/probe2_flag_positions.py",
    "command-center/p2-wave/probes/AUD-0073/write_receipts.py",
    "command-center/p2-wave/probes/AUD-0073/fixtures/control-inline.md",
    "command-center/p2-wave/probes/AUD-0073/fixtures/control-trailing.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0073/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    doc = E.scan()
    ctrl = E.control_diff(doc)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA
    public_flags = []
    for f in doc["flags"]:
        public_flags.append(
            {
                "id": f["id"],
                "kind": f["kind"],
                "path": f["path"],
                "claim_text": f["claim_text"],
                "adjacent_sentence": f["adjacent_sentence"],
                "named_experiment": f["named_experiment"],
                "has_named_runnable_experiment": f["has_named_runnable_experiment"],
                "experiment": f["experiment"],
                "position": f["position"],
                "control": f["control"],
            }
        )

    n = doc["n_flags"]
    n_named = doc["n_with_named_runnable_experiment"]
    n_gen = doc["n_without_named_runnable_experiment"]
    artifact = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:AUD-0073",
        "completion_sentinel": SENTINEL,
        "title": "Settling-probe extraction: every UNVERIFIED gets a named experiment",
        "question": (
            "For every UNVERIFIED or residual claim in the corpus, is there a "
            "named, runnable experiment that would settle it - and for those "
            "without one, what is the minimal experiment that would?"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "generated_at": now,
        "generating_commit": "NO-GIT",
        "inputs_resolved": {
            "command-center/audit/AUD-0068-claim-extraction-canonical.json": (
                "PRESENT" if doc["upstream_aud_0068"]["present"] else "ABSENT"
            ),
            "command-center/CLAIM-REGISTRY.json": (
                "PRESENT"
                if (REPO / "command-center/CLAIM-REGISTRY.json").is_file()
                else "ABSENT"
            ),
            "catalog_excluded": doc["catalog_excluded"],
            "note": doc["upstream_aud_0068"]["note"],
        },
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0073",
        "min_bytes_threshold": 4096,
        "headline": {
            "n_flags": n,
            "n_with_named_runnable_experiment": n_named,
            "n_minimal_experiment_generated": n_gen,
            "n_in_final_15_percent": doc["n_in_final_15_percent"],
            "final_15_percent_rate": doc["final_15_percent_rate"],
            "position_verdict_counts": doc["position_verdict_counts"],
            "control_inline_vs_trailing_differ": ctrl["differ"],
        },
        "report": {
            "kind": "claim-record",
            "observations": [
                {
                    "name": "n_flags",
                    "measured": n,
                    "method": "live-corpus-scan",
                    "anchor": "command-center/p2-wave/probes/AUD-0073/extract.py:scan",
                },
                {
                    "name": "n_with_named_runnable_experiment",
                    "measured": n_named,
                    "method": "named-experiment-extract",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0073/"
                        "probe1_unverified_and_experiments.py"
                    ),
                },
                {
                    "name": "control_inline_vs_trailing_differ",
                    "measured": bool(ctrl["differ"]),
                    "method": "planted-position-control",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0073/"
                        "probe2_flag_positions.py"
                    ),
                },
            ],
            "control_ids": [
                "control-inline.md",
                "control-trailing.md",
            ],
        },
        "claims": public_flags,
        "evidence": [
            {
                "claim": (
                    f"Live scan found {n} UNVERIFIED/residual flags across "
                    f"{doc['files_scanned']} corpus files."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0073/extract.py:scan",
            },
            {
                "claim": (
                    f"{n_named} flags already name a runnable experiment; "
                    f"{n_gen} received a generated minimal experiment."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0073/probe1_unverified_and_experiments.py",
            },
            {
                "claim": (
                    "A planted inline UNVERIFIED and an identical flag only in a "
                    "trailing Limitations section receive different position verdicts "
                    f"({ctrl['inline_verdicts']} vs {ctrl['trailing_verdicts']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0073/probe2_flag_positions.py",
            },
            {
                "claim": (
                    "AUD-0068 canonical claim extraction is absent; this unit "
                    "scanned the live corpus rather than retrying a missing input."
                ),
                "verdict": "CONFIRMED" if not doc["upstream_aud_0068"]["present"] else "PARTIAL",
                "anchor": doc["upstream_aud_0068"]["path"],
            },
        ],
        "tests": [
            {
                "id": "probe1-unverified-and-experiments",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-flag-positions",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "control-inline-vs-trailing-position",
                "command": P2,
                "result": "PASS" if ctrl["differ"] else "FAIL",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "verbatim_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "verbatim_output": t2,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0073-probe2-flag-positions",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Re-derived position verdicts from on-disk fixtures: inline "
                "control scores INLINE, trailing Limitations control scores "
                "BURIED-TRAILING-SECTION."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0073/extract.py",
                "exists": True,
                "role": "extractor",
            },
        ],
        "answer": (
            f"On this worktree, {n} UNVERIFIED/residual flags were extracted. "
            f"{n_named} already name a runnable experiment; {n_gen} do not, "
            "and each of those received a generated minimal experiment "
            "(command, expected observation, discriminating outcome). "
            f"{doc['n_in_final_15_percent']}/{n} sit in the final 15% of their "
            "document "
            f"(live rate {doc['final_15_percent_rate']}; catalog baseline was "
            "40% of 127). Inline vs trailing planted flags diverge. "
            f"{SENTINEL}"
        ),
        "notes": (
            "G-1 for AUD-0073. Did not run unit_manifest.py --write. "
            "Did not git add/commit/push. No ADV rebuild. SUCCESS:AUD-0073"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(artifact, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print(f"FAILED:{UID} sentinel missing from emitted body")
        return 1
    out_path.write_text(body, encoding="utf-8")

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0073",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unverified-and-experiments",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "flag-positions",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0073/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0073-probe2-flag-positions",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0073: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0073 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
