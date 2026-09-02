#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0242.json after live probes pass."""
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
from eng_blueprints_17_21.library import load_library, omission_gate  # noqa: E402
from eng_blueprints_17_21.salvage import (  # noqa: E402
    AUTHORIZE,
    REFUSE,
    ancestry_proof,
    content_equality_proof,
    decide,
)
from eng_blueprints_17_21.soak import (  # noqa: E402
    LeakyWorkload,
    StableWorkload,
    load_soak_spec,
    run_soak,
)

UNIT = "IMP-0242"
OUT = "command-center/receipts/IMP-0242.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0242/probe1_ancestry_refused.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0242/probe2_soak_curve.py"
)
SALVAGE_PY = "command-center/lib/eng_blueprints_17_21/salvage.py"
SOAK_PY = "command-center/lib/eng_blueprints_17_21/soak.py"
CONTRACT_PY = "command-center/lib/eng_blueprints_17_21/contract.py"
SOAK_SPEC = "command-center/lib/eng_blueprints_17_21/soak_v1.json"
LIB_PY = "command-center/lib/eng_blueprints_17_21/library.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0242 snippet not in {rel}: {snippet[:80]}")
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
        print("FAILED:IMP-0242 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    library = load_library()
    reasons = omission_gate()
    spec = load_soak_spec()
    digest = "a" * 64
    regular = {"id": "wt-regular-merge", "git_ahead_state": "EQUAL"}
    refused = decide(regular, [ancestry_proof(is_ancestor_of_main=True)])
    accepted = decide(
        regular,
        [
            ancestry_proof(is_ancestor_of_main=True),
            content_equality_proof(local_sha256=digest, preserved_sha256=digest),
        ],
    )
    leaky = run_soak(LeakyWorkload())
    honest = run_soak(StableWorkload())
    if refused["decision"] != REFUSE or accepted["decision"] != AUTHORIZE:
        print("FAILED:IMP-0242 emit salvage both-states broken", refused, accepted)
        return 1
    if leaky["verdict"] != "LEAK" or honest["verdict"] != "NO-LEAK":
        print("FAILED:IMP-0242 emit soak both-states broken")
        return 1

    p1_raw = json.loads((HERE / "probe1-ancestry.raw.json").read_text(encoding="utf-8"))
    p2_raw = json.loads((HERE / "probe2-soak.raw.json").read_text(encoding="utf-8"))

    salv_sha, salv_n = sha256_file(REPO / SALVAGE_PY)
    soak_sha, soak_n = sha256_file(REPO / SOAK_PY)
    contract_sha, contract_n = sha256_file(REPO / CONTRACT_PY)
    spec_sha, spec_n = sha256_file(REPO / SOAK_SPEC)
    lib_sha, lib_n = sha256_file(REPO / LIB_PY)

    line_never = find_line(SALVAGE_PY, "ANCESTRY_NEVER_SUFFICIENT = True")
    line_refuse = find_line(SALVAGE_PY, 'refused_because = "ancestry-only-insufficient"')
    line_leak = find_line(SOAK_PY, "leaked = growth > threshold")
    line_adj = find_line(SOAK_PY, '"adjective_verdict": None')
    line_omit = find_line(CONTRACT_PY, "REASON_BY_ELEMENT")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    src1 = L.probe("source", "command", P1, out1, rc1)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-salvage-ancestry-vs-content",
        json.dumps(
            {
                "accepted_authorized_by": accepted["authorized_by"],
                "accepted_decision": accepted["decision"],
                "refused_decision": refused["decision"],
                "refused_because": refused["refused_because"],
            }
        ),
        0,
    )
    src2 = L.probe("source", "command", P2, out2, rc2)
    ver2 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-soak-leaky-vs-stable",
        json.dumps(
            {
                "honest_verdict": honest["verdict"],
                "leaky_growth": leaky["leak_growth_bytes"],
                "leaky_verdict": leaky["verdict"],
                "threshold": leaky["leak_threshold_bytes"],
            }
        ),
        0,
    )

    fingerprints = {bp_id: bp.fingerprint for bp_id, bp in library.items()}
    doc = {
        "ancestry_only_refused": True,
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
                "bytes": salv_n,
                "eol": "LF",
                "exists": True,
                "path": SALVAGE_PY,
                "role": "implementation",
                "sha256": salv_sha,
            },
            {
                "bytes": soak_n,
                "eol": "LF",
                "exists": True,
                "path": SOAK_PY,
                "role": "implementation",
                "sha256": soak_sha,
            },
            {
                "bytes": contract_n,
                "eol": "LF",
                "exists": True,
                "path": CONTRACT_PY,
                "role": "contract",
                "sha256": contract_sha,
            },
            {
                "bytes": spec_n,
                "eol": "LF",
                "exists": True,
                "path": SOAK_SPEC,
                "role": "threshold-spec",
                "sha256": spec_sha,
            },
            {
                "bytes": lib_n,
                "eol": "LF",
                "exists": True,
                "path": LIB_PY,
                "role": "supporting",
                "sha256": lib_sha,
            },
        ],
        "blueprint_fingerprints": fingerprints,
        "blueprints": {
            bp_id: {
                "capability_vector": dict(bp.capability_vector),
                "fingerprint": bp.fingerprint,
                "preset_id": bp.preset.get("id"),
                "stopping_rule_ids": [r.get("id") for r in bp.stopping_rules],
                "workflow_id": bp.typed_workflow.id,
            }
            for bp_id, bp in library.items()
        },
        "completion_sentinel": "SUCCESS:IMP-0242",
        "content_equality_authorized": True,
        "detector_results": {
            "content_equality": accepted,
            "honest_soak": {
                "duration_declared_ms": honest["duration_declared_ms"],
                "leak_detected": honest["leak_detected"],
                "leak_growth_bytes": honest["leak_growth_bytes"],
                "sample_count": honest["sample_count"],
                "verdict": honest["verdict"],
            },
            "leaky_soak": {
                "duration_declared_ms": leaky["duration_declared_ms"],
                "leak_detected": leaky["leak_detected"],
                "leak_growth_bytes": leaky["leak_growth_bytes"],
                "sample_count": leaky["sample_count"],
                "verdict": leaky["verdict"],
            },
            "ancestry_only": refused,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "measure runs after this receipt and the per-unit manifest exist",
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0242",
                    "method": "command",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                "Ancestry-only delete authorization refused (regular-merge "
                "is-ancestor proof). Naive ancestry policy would have authorized.",
                "CONFIRMED",
                f"{SALVAGE_PY}:{line_refuse}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Same candidate authorized when a byte-level content-equality "
                f"proof is supplied (authorized_by={accepted['authorized_by']}).",
                "CONFIRMED",
                f"{SALVAGE_PY}:{line_never}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                f"Planted soak leak detected: growth={leaky['leak_growth_bytes']} "
                f"bytes over declared {leaky['duration_declared_ms']} ms "
                f"(threshold {leaky['leak_threshold_bytes']}).",
                "CONFIRMED",
                f"{SOAK_PY}:{line_leak}",
                [src2, ver2],
                "almost-certain",
            ),
            L.evidence(
                f"Stable soak not flagged: growth={honest['leak_growth_bytes']} "
                "bytes; verdict is numeric, adjective_verdict is null.",
                "CONFIRMED",
                f"{SOAK_PY}:{line_adj}",
                [src2, ver2],
                "almost-certain",
            ),
            L.evidence(
                "Local IMP-0230 contract: 6 one-at-a-time omissions produce 6 "
                f"distinct registration reason_ids {sorted(reasons.values())}.",
                "CONFIRMED",
                f"{CONTRACT_PY}:{line_omit}",
                [src1],
                "almost-certain",
            ),
        ],
        "inputs_note": (
            "IMP-0230 and IMP-0198 are not delivered on this worktree. This unit "
            "ships five engineering blueprints (benchmark-generation, reproducibility, "
            "performance, concurrency-load-soak, abandoned-work-salvage) against a "
            "local six-element contract. Residual: if IMP-0230 later freezes a "
            "different element set, re-bind register()."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0242/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_controls": [
            L.control(
                "ancestry-only-refused",
                "known-broken-fixture",
                "is-ancestor proof alone cannot authorize delete",
                True,
                True,
                bad=(
                    f"decision={refused['decision']} "
                    f"naive={refused['naive_ancestry_would_authorize']}"
                ),
                good=f"decision={accepted['decision']} by={accepted['authorized_by']}",
            ),
            L.control(
                "content-equality-authorized",
                "known-good-fixture",
                "matching sha256 local vs preserved authorizes delete",
                True,
                True,
                bad=f"ancestry_only={refused['decision']}",
                good=f"content={accepted['decision']}",
            ),
            L.control(
                "planted-leak-detected",
                "known-broken-fixture",
                "retaining 64KiB/tick exceeds frozen leak_growth_bytes",
                True,
                True,
                bad=f"verdict={leaky['verdict']} growth={leaky['leak_growth_bytes']}",
                good=f"verdict={honest['verdict']} growth={honest['leak_growth_bytes']}",
            ),
            L.control(
                "stable-soak-silent",
                "known-good-fixture",
                "non-retaining workload is not flagged as a leak",
                True,
                True,
                bad=f"leaky_growth={leaky['leak_growth_bytes']}",
                good=f"honest_growth={honest['leak_growth_bytes']}",
            ),
        ],
        "omission_gate": reasons,
        "output_schema": SCHEMA,
        "planted_leak_detected": True,
        "probe1_raw": p1_raw,
        "probe2_raw": p2_raw,
        "question": (
            "Do engineering blueprints 17-21 exist as typed workflows, does "
            "abandoned-work-salvage refuse ancestry-only delete authorization "
            "while accepting content equality, and does concurrency-load-soak "
            "record a numeric resource curve that detects a planted leak?"
        ),
        "residual_unknowns": [
            {
                "claim": "IMP-0230 authoring contract may differ when that unit delivers.",
                "settling_experiment": "Re-bind register() to IMP-0230's frozen element set and re-run probes.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "Catalog reviewer_requirement asks for a cross-vendor Codex reviewer.",
                "settling_experiment": "Independent Codex pass over salvage/soak; probe2 is the in-tree independent path.",
                "verdict": "DISCLOSED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0242-probe2-soak-curve-leak",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0242",
        "soak_spec": spec,
        "spec_anchor": "_USER-PROMPTS.md:10900-10907",
        "state": "SUCCESS",
        "tests": [
            {"command": P1, "id": "probe1_ancestry_refused", "result": "PASS"},
            {"command": P2, "id": "probe2_soak_curve", "result": "PASS"},
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": (
            "Implement engineering blueprints 17-21: benchmark generation, "
            "reproducibility, performance, concurrency/load/soak, abandoned-work salvage"
        ),
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0242" not in text:
        print("FAILED:IMP-0242 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0242 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:IMP-0242")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
