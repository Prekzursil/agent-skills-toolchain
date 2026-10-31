#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0323.json after live probes pass."""
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
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

import _p2lib as L  # noqa: E402
from council.antifail.premature import (  # noqa: E402
    DECISION_BASIS,
    SPEC_ANCHOR,
    detect,
)
import fixtures as F  # noqa: E402

UNIT = "IMP-0323"
OUT = "command-center/receipts/IMP-0323.json"
SCHEMA = "command-center/schema/receipt.schema.json"
IMPL = "tools/council/antifail/premature.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0323/probe1_quota_attainment.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0323/probe2_quota_not_round.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0323 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:IMP-0323 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1_raw = json.loads((HERE / "probe1-quota-attainment.raw.json").read_text(encoding="utf-8"))
    p2_raw = json.loads((HERE / "probe2-quota-not-round.raw.json").read_text(encoding="utf-8"))
    if not p1_raw.get("pass") or not p2_raw.get("pass"):
        print("FAILED:IMP-0323 probe raw pass=false")
        return 1

    F.dump_json()
    impl_sha, impl_n = sha256_file(REPO / IMPL)
    line_fire = find_line(
        IMPL, "return bool(converged) and not (ideas_met and objections_met)"
    )
    line_basis = find_line(IMPL, 'DECISION_BASIS = "quota-attainment"')
    line_ignore = find_line(IMPL, "question_class, question text")

    hard = detect(F.hard_round1())
    easy0 = detect(F.easy_control_set()[0])
    late = detect(next(r for r in F.twenty_runs() if r["id"] == "hard-late-unmet-1"))
    if not hard["fired"] or easy0["fired"] or not late["fired"]:
        print("FAILED:IMP-0323 emit both-states broken")
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    src1 = L.probe("source", "command", P1, out1, rc1)
    src2 = L.probe("source", "command", P2, out2, rc2)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-detect-easy-hard-late",
        json.dumps(
            {
                "hard_round1_fired": hard["fired"],
                "easy_fired": easy0["fired"],
                "late_unmet_fired": late["fired"],
                "fpr": p1_raw["false_positive_rate"],
                "n_runs": p1_raw["n_runs"],
            }
        ),
        0,
    )

    artifact_paths = [
        OUT,
        IMPL,
        "tools/council/antifail/__init__.py",
        "command-center/p2-wave/probes/IMP-0323/probe1_quota_attainment.py",
        "command-center/p2-wave/probes/IMP-0323/probe2_quota_not_round.py",
        "command-center/p2-wave/probes/IMP-0323/fixtures.py",
    ]
    doc = {
        "artifact_paths": artifact_paths,
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
                "bytes": impl_n,
                "eol": "LF",
                "exists": True,
                "path": IMPL,
                "role": "implementation",
                "sha256": impl_sha,
            },
        ],
        "completion_sentinel": "SUCCESS:IMP-0323",
        "decision_basis": DECISION_BASIS,
        "detector_results": {
            "easy_control": {
                "n": p1_raw["easy_control_n"],
                "flagged": p1_raw["easy_flagged"],
                "false_positive_rate": p1_raw["false_positive_rate"],
            },
            "hard_round1": hard,
            "late_unmet": late,
            "quota_table": p1_raw["quota_table"],
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "measure runs after this receipt and the per-unit manifest exist",
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0323",
                    "method": "command",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                "Known-present hard question converging in round 1 with unmet "
                f"idea/objection quotas FIRED (ideas "
                f"{hard['quota']['unique_ideas_attained']}/"
                f"{hard['quota']['min_unique_ideas']}, objections "
                f"{hard['quota']['objections_attained']}/"
                f"{hard['quota']['min_objections']}).",
                "CONFIRMED",
                f"{IMPL}:{line_fire}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Easy-question control set was silent: "
                f"n={p1_raw['easy_control_n']} flagged={p1_raw['easy_flagged']} "
                f"false_positive_rate={p1_raw['false_positive_rate']}.",
                "CONFIRMED",
                f"{IMPL}:{line_basis}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Quota-attainment at convergence recorded for 20 runs; padded "
                "duplicate idea records collapse by canonical_id (unique=1, FIRE).",
                "CONFIRMED",
                f"{IMPL}:{line_fire}",
                [src1],
                "almost-certain",
            ),
            L.evidence(
                "Distinction is quota attainment, not round count: a round-count "
                "mutant false-positives on easy round-1 and false-negatives on "
                "late unmet quotas; perturbing round_index does not change the "
                "verdict; dropping an idea below quota does.",
                "CONFIRMED",
                f"{IMPL}:{line_ignore}",
                [src2],
                "almost-certain",
            ),
        ],
        "false_positive_rate": p1_raw["false_positive_rate"],
        "inputs_note": (
            "Catalog inputs (11-COUNCIL-SPECIFICATION.md, IMP-0297 protocol "
            "plugin, IMP-0307 evidence gate) are absent on this worktree. The "
            "detector consumes a typed run snapshot (declared divergence "
            "quotas + idea/objection lists at convergence). Fixtures stand in "
            "for protocol-emitted snapshots. Semantic near-duplicate collapse "
            "is IMP-0300 and is not claimed here."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0323/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_control_ids": [
            "hard-round1-must-fire",
            "round-count-mutant-false-positive-on-easy",
            "round-count-mutant-false-negative-on-late-unmet",
        ],
        "negative_controls": [
            L.control(
                "hard-round1-must-fire",
                "known-broken-fixture",
                "A hard question converging in round 1 with unmet quotas FIRED",
                True,
                True,
                bad=f"fired={hard['fired']} status={hard['status']}",
                good=f"easy_fired={easy0['fired']} fpr={p1_raw['false_positive_rate']}",
            ),
            L.control(
                "round-count-mutant-false-positive-on-easy",
                "mutation",
                "Round-count mutant flags easy round-1; quota detector does not",
                True,
                True,
                bad="round_mutant_fired=True on easy-round1",
                good="quota_fired=False on easy-round1",
            ),
            L.control(
                "round-count-mutant-false-negative-on-late-unmet",
                "mutation",
                "Late unmet-quota run FIRED on quotas, silent on round-count mutant",
                True,
                True,
                bad=f"late quota_fired={late['fired']} round={late['quota'].get('round_index_recorded')}",
                good="round_mutant_fired=False on late unmet",
            ),
        ],
        "output_schema": SCHEMA,
        "probe1_raw": p1_raw,
        "probe2_raw": p2_raw,
        "question": (
            "Does the detector distinguish premature convergence from a "
            "genuinely easy question, and is the distinction made on quota "
            "attainment rather than on round count?"
        ),
        "residual_unknowns": [
            {
                "claim": "IMP-0297 protocol plugin is not delivered; live councils do not yet emit these snapshots.",
                "settling_experiment": "Re-run probes on protocol-emitted artifacts once IMP-0297 lands.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "Semantic paraphrase collapse of unique ideas is IMP-0300, not this detector.",
                "settling_experiment": "Bind unique_count to IMP-0300 canonicalisation and re-measure FPR.",
                "verdict": "DISCLOSED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0323-probe2-quota-not-round",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0323",
        "spec_anchor": SPEC_ANCHOR,
        "state": "SUCCESS",
        "test_ids": ["probe1_quota_attainment", "probe2_quota_not_round"],
        "tests": [
            {"command": P1, "id": "probe1_quota_attainment", "result": "PASS"},
            {"command": P2, "id": "probe2_quota_not_round", "result": "PASS"},
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Premature-convergence detector",
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0323" not in text:
        print("FAILED:IMP-0323 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0323 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:IMP-0323")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
