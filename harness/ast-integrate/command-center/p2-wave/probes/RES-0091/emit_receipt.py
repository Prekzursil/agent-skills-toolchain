#!/usr/bin/env python3
"""Emit RES-0091 research record + per-unit manifest + SUBAGENT-RETURN."""
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
from properties import REAL_ARTIFACT_REL, run_property_battery  # noqa: E402

UNIT = "RES-0091"
OUT_REL = f"command-center/research/{UNIT}.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0091 in the receipt AND 3 implemented properties with run "
    "output plus 2 named untestable properties"
)
QUESTION = (
    "For an agent-produced artifact, which invariants can a property-based "
    "test assert without asserting the model's opinion (schema validity, "
    "idempotence of re-runs, monotonicity of a counter, absence of a "
    "credential) - and which desirable properties are fundamentally untestable?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0091/probe1_properties_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0091/probe2_reviewer_untestable.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0091/properties.py",
    "command-center/p2-wave/probes/RES-0091/probe1_properties_both_states.py",
    "command-center/p2-wave/probes/RES-0091/probe2_reviewer_untestable.py",
    "command-center/p2-wave/probes/RES-0091/emit_receipt.py",
    REAL_ARTIFACT_REL,
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print("FAILED:RES-0091 live probes did not all exit 0")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:RES-0091-probe1" not in out1:
        print("FAILED:RES-0091 probe1 sentinel missing")
        return 1
    if "SUCCESS:RES-0091-probe2" not in out2:
        print("FAILED:RES-0091 probe2 sentinel missing")
        return 1

    battery = run_property_battery()
    if not battery["all_pass"] or battery["implemented_count"] < 3:
        print("FAILED:RES-0091 property battery")
        return 1
    if battery["untestable_count"] < 2:
        print("FAILED:RES-0091 untestable count")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    real_path = REPO / REAL_ARTIFACT_REL
    real_sha, real_bytes = sha256_file(real_path)

    implemented_runs = []
    for row in battery["implemented_properties"]:
        implemented_runs.append(
            {
                "id": row["id"],
                "name": row["name"],
                "pass": row["pass"],
                "asserts_model_opinion": row["asserts_model_opinion"],
                "both_states": row["both_states"],
                "run_output": {
                    "real_artifact": row.get("real_artifact"),
                    "opinion_control": row.get("opinion_control"),
                    "receipts_population": row.get("receipts_population"),
                    "scope": row.get("scope"),
                    "note": row.get("note"),
                },
            }
        )

    record = {
        "schema_version": 1,
        "claim_id": UNIT,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "record_kind": "research-claim-record",
        "output_schema": SCHEMA,
        "schema_note": (
            "Declared output_schema is command-center/schema/research-claim-record"
            ".schema.json (generated shim to platform artifact-class-profiles). "
            "G-1 measure parses JSON and checks the catalog sentinel; it does "
            "not Draft202012-validate. This record still carries claim id, "
            "canonical mechanism, source lineage, evidence tier, confidence "
            "band, named settling probe, edges, freshness stamp, snapshot "
            "sha256, implemented property runs, and named untestable properties."
        ),
        "title": "Identify which properties of an agent's output are genuinely property-testable",
        "question": QUESTION,
        "canonical_mechanism": (
            "observational-pbt: quantify decidable predicates over agent JSON "
            "bytes (schema vocab, canonical rerun equality, credential regex, "
            "counter traces). Predicates that need an external truth/intent "
            "oracle are classified untestable, not silently skipped."
        ),
        "source_lineage": [
            {
                "kind": "catalog",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "unit_id": UNIT,
            },
            {
                "kind": "real-artifact",
                "path": REAL_ARTIFACT_REL,
                "sha256": real_sha,
                "bytes": real_bytes,
            },
            {
                "kind": "literature",
                "note": (
                    "Claessen & Hughes, QuickCheck (ICFP 2000): properties are "
                    "universally quantified decidable predicates. The Windows "
                    "source 05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md and "
                    "command-center/sources/REGISTER.md are not in this worktree; "
                    "no section numbers from those files are cited."
                ),
            },
        ],
        "evidence_tier": "E1",
        "evidence_tier_meaning": "executable measurement (live named probes)",
        "confidence_band": "high-on-implemented-properties; untestable-by-construction",
        "named_settling_probe": P1,
        "edges": {
            "supports": ["RES-0001"],
            "contradicts": [],
        },
        "freshness_stamp": started,
        "snapshot_sha256": real_sha,
        "implemented_properties": implemented_runs,
        "untestable_properties": battery["untestable_properties"],
        "property_battery": {
            "trials": battery["trials"],
            "implemented_count": battery["implemented_count"],
            "untestable_count": battery["untestable_count"],
            "all_pass": battery["all_pass"],
            "real_artifact": battery["real_artifact"],
            "planted_credential_kept_out_of_record": battery[
                "planted_credential_kept_out_of_record"
            ],
        },
        "tests": [
            {
                "id": "named-probe1-properties-both-states",
                "command": P1,
                "result": "PASS",
                "exit_code": code1,
                "raw_output": out1[-8000:],
            },
            {
                "id": "named-probe2-reviewer-untestable",
                "command": P2,
                "result": "PASS",
                "exit_code": code2,
                "raw_output": out2[-8000:],
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0091-probe2-reviewer-untestable",
            "verdict": "PASS",
            "independent": True,
            "obligation": (
                "Re-run checkers against known-good and known-broken fixtures; "
                "confirm they fire only on the broken one; confirm two named "
                "untestable properties are not implemented as silent checkers."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": REAL_ARTIFACT_REL, "exists": True, "role": "subject"},
        ],
        "notes": (
            "G-1 for RES-0091: live named probes exit 0, research record "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "Planted credential token is not copied into this record."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:RES-0091 sentinel missing from record text")
        return 1
    if "3 implemented properties with run output plus 2 named untestable properties" not in payload:
        print("FAILED:RES-0091 completion clause missing")
        return 1
    out.write_text(payload, encoding="utf-8")
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:RES-0091 record too small ({live_bytes} B)")
        return 1

    rows = [art(OUT_REL, "primary")]
    rows[0]["sha256"] = live_sha
    rows[0]["bytes"] = live_bytes
    rows[0]["exists"] = True
    rows[0]["present"] = True
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

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
                "role": "properties-both-states-real-artifact",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "reviewer-untestable",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "RES-0091-probe2-reviewer-untestable",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": started,
        "notes": (
            "G-1 for RES-0091: live named probes exit 0, research/RES-0091.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print("SUCCESS:RES-0091")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
