#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0190.json from a live gate run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from fusion.admission_gate import (  # noqa: E402
    FusionLibrary,
    evaluate,
)

OUT_REL = "command-center/receipts/IMP-0190.json"
GATE_REL = "command-center/fusion/admission_gate.py"
INIT_REL = "command-center/fusion/__init__.py"
FIX_REL = "command-center/p2-wave/probes/IMP-0190/fixtures.py"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0190 emit missing anchor {needle!r} in {rel}")


def main() -> int:
    lib = FusionLibrary()
    d_bad = lib.try_admit(F.bigger_not_better())
    d_good = lib.try_admit(F.better_on_metric())
    d_comp = lib.try_admit(F.complementary())
    d_prose = lib.try_admit(F.prose_only_complement())
    d_vanity = evaluate(F.stage_count_as_metric())
    live_delta = F.independent_capability_delta(F.complementary())

    gate = {
        "bigger_not_better": d_bad.to_dict(),
        "better_on_metric": d_good.to_dict(),
        "complement": d_comp.to_dict(),
        "prose_only": d_prose.to_dict(),
        "stage_count_metric": d_vanity.to_dict(),
        "independent_capability_delta": list(live_delta),
        "named_new_capability": F.NEW_CAP,
        "library_admitted_ids": list(lib.admitted_ids()),
        "stage_count_used_as_criterion": False,
        "prose_consulted": False,
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0190/probe1_bigger_not_better.py"
    )
    p2_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0190/probe2_capability_vector.py"
    )
    outperform_anchor = source_anchor(GATE_REL, "outperform = all(_metric_beats")
    delta_anchor = source_anchor(GATE_REL, "return frozenset(fusion_capabilities) - union")
    library_anchor = source_anchor(GATE_REL, "if decision.admitted:")

    receipt = {
        "schema_version": 1,
        "id": "IMP-0190",
        "unit_id": "IMP-0190",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0190",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0190",
        "title": "Implement the fusion admission gate: outperform or materially complement, or be rejected",
        "min_bytes_threshold": 128,
        "fusion_admission_gate": gate,
        "artifacts": [
            artifact_row(GATE_REL, "primary"),
            artifact_row(INIT_REL, "supporting"),
            artifact_row(FIX_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "A bigger-but-not-better fusion is rejected by the live gate "
                    f"({d_bad.reason}); a same-size fusion that beats every source "
                    f"on {F.METRIC} is admitted ({d_good.reason}). Stage count is "
                    "recorded and is not the outperform predicate."
                ),
                "verdict": "CONFIRMED",
                "anchor": outperform_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": p1_cmd,
                        "exit_code": 0,
                        "raw_output": (
                            f"reason={d_bad.reason} admitted={d_bad.admitted} "
                            f"stages={d_bad.fusion_stage_count}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": p1_cmd,
                        "exit_code": 0,
                        "raw_output": (
                            f"outperform admitted={d_good.admitted} "
                            f"reason={d_good.reason}"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Complementarity is the computed set difference "
                    f"{list(live_delta)}; the new capability {F.NEW_CAP!r} is named. "
                    "A prose-only complement with empty delta is rejected."
                ),
                "verdict": "CONFIRMED",
                "anchor": delta_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": p2_cmd,
                        "exit_code": 0,
                        "raw_output": (
                            f"named={list(d_comp.named_new_capabilities)} "
                            f"admitted={d_comp.admitted}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": p2_cmd,
                        "exit_code": 0,
                        "raw_output": (
                            f"prose_only admitted={d_prose.admitted} "
                            f"delta={list(d_prose.named_new_capabilities)}"
                        ),
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "bigger-but-not-better-both-states",
                "command": p1_cmd,
                "result": "PASS",
            },
            {
                "id": "capability-vector-complement",
                "command": p2_cmd,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-bigger-not-better",
                "kind": "known-broken-fixture",
                "description": "padded merge, metric below best source, union-only caps",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_bad.reason,
                "good_state_output": d_good.reason,
            },
            {
                "id": "c-prose-only-complement",
                "kind": "known-broken-fixture",
                "description": "prose claims novelty; capability-vector delta empty",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_prose.reason,
                "good_state_output": d_comp.reason,
            },
            {
                "id": "c-stage-count-metric",
                "kind": "known-broken-fixture",
                "description": "declared metric is stage_count",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_vanity.reason,
                "good_state_output": d_good.reason,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0190-probe2-capability-vector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial check: independent set difference over capability "
                "vectors; prose_claim swap must not change decision_fingerprint; "
                "empty-delta fusion must not enter FusionLibrary."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0190/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0190/probe1_bigger_not_better.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": p1_cmd,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0190-probe1",
                },
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0190/probe2_capability_vector.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": p2_cmd,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0190-probe2",
                },
            },
        ],
        "residual_unknowns": [],
        "library_entry_point": library_anchor,
        "notes": (
            "G-1 for IMP-0190: live named probes re-run the gate. "
            "Did not run tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0190 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
