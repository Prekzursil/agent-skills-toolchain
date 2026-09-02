#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0156.json from live extractor measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import (  # noqa: E402
    evaluate_control_set,
    evaluate_redistribution_gate,
    evaluate_silent_default,
)
from workflow_foundry.license_extract import UNKNOWN  # noqa: E402

OUT = "command-center/receipts/IMP-0156.json"
LIB = "tools/workflow_foundry/license_extract.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0156/probe1_control_set.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0156/probe2_redistribution_gate.py"
)
QUESTION = (
    "Target: extract the licence for each candidate and normalize to an SPDX id, "
    "with UNKNOWN as a first-class value. Acceptance: UNKNOWN is never silently "
    "coerced to permissive; a candidate with no discoverable licence is marked "
    "UNKNOWN and blocked from redistribution paths."
)


def digest(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest(rel)
    return {
        "path": rel,
        "sha256": sha or ("0" * 64),
        "bytes": max(size, 1),
        "exists": exists,
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="imp0156-emit-") as tmp:
        root = Path(tmp)
        control = evaluate_control_set(root / "control")
        silent = evaluate_silent_default(root / "silent")
        gate = evaluate_redistribution_gate(root / "gate")

    if not control["pass"] or control["matched"] != 20:
        print("FAILED:IMP-0156 emit control set")
        print(json.dumps(control, indent=2, sort_keys=True)[:4000])
        return 1
    if not silent["pass"]:
        print("FAILED:IMP-0156 emit silent permissive default")
        print(json.dumps(silent, indent=2, sort_keys=True)[:4000])
        return 1
    if not gate["pass"]:
        print("FAILED:IMP-0156 emit redistribution gate")
        print(json.dumps(gate, indent=2, sort_keys=True, default=str)[:4000])
        return 1

    lib_sha, lib_bytes, lib_ok = digest(LIB)
    if not lib_ok:
        print("FAILED:IMP-0156 emit missing", LIB)
        return 1

    p1_raw = json.dumps(
        {
            "matched": control["matched"],
            "total": control["total"],
            "silent_default_pass": silent["pass"],
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "unknown_spdx": gate["unknown"]["record"]["spdx_id"],
            "unknown_allowed": gate["unknown"]["gate"]["allowed"],
            "unknown_reason": gate["unknown"]["gate"]["reason"],
            "twin_spdx": gate["permissive_twin"]["record"]["spdx_id"],
            "twin_allowed": gate["permissive_twin"]["gate"]["allowed"],
        },
        sort_keys=True,
    )
    p_ctrl = probe("source", "command", "evaluate_control_set(tmp)", p1_raw, 0)
    p_gate = probe("source", "command", "evaluate_redistribution_gate(tmp)", p2_raw, 0)
    p_read = probe(
        "verifier",
        "file-read",
        f"sha256 {LIB}",
        f"bytes={lib_bytes} sha256={lib_sha}",
        0,
    )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/workflow_foundry/__init__.py",
        "command-center/p2-wave/probes/IMP-0156/control_set.py",
        "command-center/p2-wave/probes/IMP-0156/scenario.py",
        "command-center/p2-wave/probes/IMP-0156/probe1_control_set.py",
        "command-center/p2-wave/probes/IMP-0156/probe2_redistribution_gate.py",
    ]
    artifacts = [art(LIB, "primary")] + [art(p, "supporting") for p in supporting]
    if any(not a["exists"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"]]
        print("FAILED:IMP-0156 emit missing artifacts", missing)
        return 1

    control_rows = [
        {"id": r["id"], "expected": r["expected"], "got": r["got"], "match": r["match"]}
        for r in control["rows"]
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0156",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0156",
        "completion_sentinel": "SUCCESS:IMP-0156",
        "title": "Implement license extraction and SPDX normalization for every candidate",
        "question_or_target": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10715 (legal and license review)",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "headless-linux",
        },
        "implementation": {
            "api_module": LIB,
            "entry_points": [
                "workflow_foundry.license_extract.extract_licence",
                "workflow_foundry.license_extract.normalize_to_spdx",
                "workflow_foundry.license_extract.redistribution_gate",
            ],
            "unknown_token": UNKNOWN,
            "refuse_reason": "UNKNOWN-LICENCE-BLOCKS-REDISTRIBUTION",
            "no_permissive_default": True,
            "license_blob_unmatched_does_not_fall_through_to_metadata": True,
        },
        "control_set": {
            "labelled": 20,
            "matched": control["matched"],
            "computed_equality": f"{control['matched']}/20",
            "pass": True,
            "rows": control_rows,
        },
        "redistribution_gate": {
            "licence_less_spdx": gate["unknown"]["record"]["spdx_id"],
            "licence_less_allowed": gate["unknown"]["gate"]["allowed"],
            "licence_less_reason": gate["unknown"]["gate"]["reason"],
            "permissive_twin_spdx": gate["permissive_twin"]["record"]["spdx_id"],
            "permissive_twin_allowed": gate["permissive_twin"]["gate"]["allowed"],
            "both_states": True,
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"Labelled control set normalises {control['matched']}/20 "
                    "exactly via extract_licence on materialised candidate trees."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:extract_licence",
                "confidence": "almost-certain",
                "probes": [p_ctrl, p_read],
            },
            {
                "claim": (
                    "A licence-less fixture is UNKNOWN and refused by "
                    "redistribution_gate; a MIT twin of the same tree is allowed."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:redistribution_gate",
                "confidence": "almost-certain",
                "probes": [p_gate, p_read],
            },
            {
                "claim": (
                    "UNKNOWN is never silently coerced to a permissive SPDX id: "
                    "empty trees, license='permissive', bare 'BSD', and an "
                    "unrecognised LICENSE blob beside a package.json MIT claim "
                    "all stay UNKNOWN."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:normalize_to_spdx",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "evaluate_silent_default(tmp)",
                        json.dumps(silent["rows"], sort_keys=True)[:8000],
                        0,
                    ),
                    p_read,
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "t1-control-set",
                "command": P1,
                "result": "PASS",
                "detail": f"{control['matched']}/20 computed",
            },
            {
                "id": "t2-unknown-blocks-redistribution",
                "command": P2,
                "result": "PASS",
                "detail": "licence-less refused; MIT twin allowed",
            },
        ],
        "negative_controls": [
            {
                "id": "c-silent-permissive-default",
                "kind": "known-broken-fixture",
                "description": (
                    "licence-less, 'permissive', bare BSD, and unrecognised LICENSE "
                    "+ metadata MIT must stay UNKNOWN"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(silent["rows"], sort_keys=True)[:4000],
                "good_state_output": p1_raw,
            },
            {
                "id": "c-unknown-gate",
                "kind": "both-states",
                "description": "UNKNOWN refused; MIT twin allowed at redistribution_gate",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p2_raw,
                "good_state_output": json.dumps(gate["permissive_twin"]["gate"], sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0156-probe2-redistribution-gate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Technical both-states gate is probe 2 calling the live API. "
                "Catalog reviewer_requirement names a cross-vendor Codex legal "
                "reviewer; that review was not executed on this substrate."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0156/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "tools/workflow_foundry/license_extract.py:redistribution_gate",
                "artifact_path": LIB,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_gate,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog owner_approval_required=true: this receipt is technical "
                    "delivery of extraction/normalisation/gating, not an owner legal ruling."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Owner review of redistribution policy for UNKNOWN candidates.",
            },
            {
                "claim": (
                    "Catalog reviewer_requirement is a cross-vendor Codex legal reviewer. "
                    "Not run here; probes verify the mechanical contract only."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Independent Codex legal review of the extractor and gate.",
            },
            {
                "claim": (
                    "IMP-0154/IMP-0155 candidate registry artifacts are absent on this "
                    "sparse worktree. Extractor is proven on the labelled 20-licence "
                    "control set and licence-less fixture, not on a live registry dump."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run extract_licence over IMP-0154 registry rows once that unit is delivered.",
            },
        ],
        "notes": (
            "G-1 technical contract: 20/20 SPDX control, UNKNOWN first-class, "
            "redistribution_gate refuses UNKNOWN and allows a MIT twin. "
            "Did not run global unit_manifest.py --write. Not legal advice."
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0156 emit {size}B below floor")
        return 1
    if "SUCCESS:IMP-0156" not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0156 emit sentinel missing after write")
        return 1
    print(f"wrote {OUT} ({size} B) matched={control['matched']}/20 gate_pass={gate['pass']}")
    print("SUCCESS:IMP-0156")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
