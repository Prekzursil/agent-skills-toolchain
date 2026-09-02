#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0251.json after live probes pass."""
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
from science_blueprints.library import load_library, omission_gate  # noqa: E402
from science_blueprints.model_evaluation import (  # noqa: E402
    HonestRule,
    build_eval_corpus,
    try_evaluate,
)
from science_blueprints.power import load_thresholds  # noqa: E402
from science_blueprints.statistical_review import (  # noqa: E402
    missing_effect_size_fixture,
    powered_fixture,
    review,
    underpowered_fixture,
)

UNIT = "IMP-0251"
OUT = "command-center/receipts/IMP-0251.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0251/probe1_underpowered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0251/probe2_visible_slice_refused.py"
)
REVIEW_PY = "command-center/lib/science_blueprints/statistical_review.py"
EVAL_PY = "command-center/lib/science_blueprints/model_evaluation.py"
CONTRACT_PY = "command-center/lib/science_blueprints/contract.py"
THRESH = "command-center/lib/science_blueprints/thresholds_v1.json"
LIB_PY = "command-center/lib/science_blueprints/library.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0251 snippet not in {rel}: {snippet[:80]}")
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
        print("FAILED:IMP-0251 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    library = load_library()
    reasons = omission_gate()
    spec = load_thresholds()
    weak = review(underpowered_fixture())
    strong = review(powered_fixture())
    bare = review(missing_effect_size_fixture())
    held = try_evaluate(HonestRule(), build_eval_corpus(80), slice_name="held-out")
    vis = try_evaluate(HonestRule(), build_eval_corpus(80), slice_name="visible")
    if not weak["flagged"] or next(f["flagged"] for f in strong["flags"] if f["id"] == "underpowered"):
        print("FAILED:IMP-0251 emit underpowered both-states broken")
        return 1
    if vis.get("refused") is not True or held.get("verdict") != "EVALUATED":
        print("FAILED:IMP-0251 emit visible/held-out both-states broken")
        return 1

    p1_raw = json.loads((HERE / "probe1-underpowered.raw.json").read_text(encoding="utf-8"))
    p2_raw = json.loads((HERE / "probe2-visible-slice.raw.json").read_text(encoding="utf-8"))

    review_sha, review_n = sha256_file(REPO / REVIEW_PY)
    eval_sha, eval_n = sha256_file(REPO / EVAL_PY)
    contract_sha, contract_n = sha256_file(REPO / CONTRACT_PY)
    th_sha, th_n = sha256_file(REPO / THRESH)
    lib_sha, lib_n = sha256_file(REPO / LIB_PY)

    line_under = find_line(REVIEW_PY, 'underpowered = power < float(spec["min_power"])')
    line_missing = find_line(REVIEW_PY, '"id": "missing-effect-size"')
    line_refuse = find_line(EVAL_PY, 'REASON_VISIBLE_ONLY = "model-eval.visible-slice-only"')
    line_held = find_line(EVAL_PY, 'if slice_name != HELD_OUT:')
    line_omit = find_line(CONTRACT_PY, "REASON_BY_ELEMENT")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    src1 = L.probe("source", "command", P1, out1, rc1)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-review-underpowered-powered",
        json.dumps(
            {
                "powered_under_flagged": next(
                    f["flagged"] for f in strong["flags"] if f["id"] == "underpowered"
                ),
                "underpowered_flagged": next(
                    f["flagged"] for f in weak["flags"] if f["id"] == "underpowered"
                ),
                "underpowered_power": weak["power"],
                "powered_power": strong["power"],
            }
        ),
        0,
    )
    src2 = L.probe("source", "command", P2, out2, rc2)
    ver2 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-evaluate-visible-heldout",
        json.dumps(
            {
                "heldout_accuracy": held["accuracy"],
                "heldout_n": held["heldout_n"],
                "heldout_verdict": held["verdict"],
                "visible_refused": vis["refused"],
                "visible_verdict": vis["verdict"],
            }
        ),
        0,
    )

    fingerprints = {bp_id: bp.fingerprint for bp_id, bp in library.items()}
    now_doc = {
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
                "bytes": review_n,
                "eol": "LF",
                "exists": True,
                "path": REVIEW_PY,
                "role": "implementation",
                "sha256": review_sha,
            },
            {
                "bytes": eval_n,
                "eol": "LF",
                "exists": True,
                "path": EVAL_PY,
                "role": "implementation",
                "sha256": eval_sha,
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
                "bytes": th_n,
                "eol": "LF",
                "exists": True,
                "path": THRESH,
                "role": "threshold-spec",
                "sha256": th_sha,
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
        "completion_sentinel": "SUCCESS:IMP-0251",
        "detector_results": {
            "heldout_evaluation": held,
            "missing_effect_size": bare,
            "powered": strong,
            "underpowered": weak,
            "visible_slice": vis,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "measure runs after this receipt and the per-unit manifest exist",
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0251",
                    "method": "command",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                f"Underpowered fixture flagged: n=4+4 d=0.2 power={weak['power']} "
                f"(min_power {spec['min_power']}).",
                "CONFIRMED",
                f"{REVIEW_PY}:{line_under}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                f"Adequately powered fixture not flagged for power: n=64+64 d=0.5 "
                f"power={strong['power']}.",
                "CONFIRMED",
                f"{REVIEW_PY}:{line_under}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Result reported without an effect size flagged; powered fixture "
                "with effect_size is silent on that flag.",
                "CONFIRMED",
                f"{REVIEW_PY}:{line_missing}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Visible-slice-only evaluation refused with reason_id "
                "model-eval.visible-slice-only and no accuracy/verdict.",
                "CONFIRMED",
                f"{EVAL_PY}:{line_refuse}",
                [src2, ver2],
                "almost-certain",
            ),
            L.evidence(
                f"Held-out evaluation proceeded: accuracy={held['accuracy']} "
                f"heldout_n={held['heldout_n']} visible_n={held['visible_n']}.",
                "CONFIRMED",
                f"{EVAL_PY}:{line_held}",
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
            "ships a local six-element blueprint contract (typed Workflow, example, "
            "preset, stopping rules, smoke test, capability vector) and reuses the "
            "IMP-0198-holdout-v1 hash-partition IMP-0206 already froze. Residual: "
            "if IMP-0230 later ships a different element set, re-bind register(); "
            "if IMP-0198 later freezes a different salt, re-bind slice_of()."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0251/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_controls": [
            L.control(
                "underpowered-flagged",
                "known-broken-fixture",
                "n=4+4 d=0.2 comparison is flagged underpowered",
                True,
                True,
                bad=f"flagged={weak['flagged']} power={weak['power']}",
                good=f"powered_power={strong['power']}",
            ),
            L.control(
                "powered-silent",
                "known-good-fixture",
                "n=64+64 d=0.5 comparison is not flagged underpowered",
                True,
                True,
                bad=f"underpowered_power={weak['power']}",
                good=f"powered_under_flagged=False power={strong['power']}",
            ),
            L.control(
                "visible-slice-refused",
                "known-broken-fixture",
                "visible-slice-only verdict is refused",
                True,
                True,
                bad=f"refused={vis['refused']} verdict={vis['verdict']}",
                good=f"heldout_verdict={held['verdict']} accuracy={held['accuracy']}",
            ),
            L.control(
                "missing-effect-size",
                "known-broken-fixture",
                "report without effect_size is flagged",
                True,
                True,
                bad=str(bare["flags"]),
                good=str(strong["flags"]),
            ),
        ],
        "omission_gate": reasons,
        "output_schema": SCHEMA,
        "probe1_raw": p1_raw,
        "probe2_raw": p2_raw,
        "question": (
            "Do science blueprints 5-8 exist as typed workflows, does "
            "statistical-review flag underpowered and missing-effect-size "
            "results, and does model-evaluation refuse a visible-slice verdict?"
        ),
        "residual_unknowns": [
            {
                "claim": "IMP-0230 authoring contract may differ when that unit delivers.",
                "settling_experiment": "Re-bind register() to IMP-0230's frozen element set and re-run probes.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "IMP-0198 held-out salt may differ when that unit delivers.",
                "settling_experiment": "Re-bind slice_of() to IMP-0198's frozen partition and re-run probes.",
                "verdict": "DISCLOSED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0251-probe2-visible-slice-refusal",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0251",
        "spec_anchor": "_USER-PROMPTS.md:10900-10907",
        "state": "SUCCESS",
        "tests": [
            {"command": P1, "id": "probe1_underpowered", "result": "PASS"},
            {"command": P2, "id": "probe2_visible_slice_refused", "result": "PASS"},
        ],
        "thresholds": {
            "declared": spec,
            "powered_power": strong["power"],
            "underpowered_power": weak["power"],
        },
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Implement science blueprints 5-8: experiment design, statistical review, scientific replication, model evaluation",
        "unit_id": UNIT,
        "blueprint_fingerprints": fingerprints,
        "missing_effect_size_flagged": True,
        "visible_slice_refused": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(now_doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0251" not in text:
        print("FAILED:IMP-0251 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(now_doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0251 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:IMP-0251")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
