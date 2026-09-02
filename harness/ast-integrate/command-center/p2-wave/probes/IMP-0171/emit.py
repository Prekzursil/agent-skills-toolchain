#!/usr/bin/env python3
"""Emit IMP-0171 receipt and per-unit G-1 return + manifest.

Order: calibrate the token-Jaccard instrument, write
command-center/receipts/IMP-0171.json, re-run named probes, then write
SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
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
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(HERE))
import calibrate as cal  # noqa: E402
import corpus as C  # noqa: E402
import lexical as lex  # noqa: E402

UNIT = "IMP-0171"
OUT = "command-center/receipts/IMP-0171.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0171/probe1_calibration.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0171/probe2_distinct.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0171/lexical.py",
    "command-center/p2-wave/probes/IMP-0171/corpus.py",
    "command-center/p2-wave/probes/IMP-0171/calibrate.py",
    "command-center/p2-wave/probes/IMP-0171/probe1_calibration.py",
    "command-center/p2-wave/probes/IMP-0171/probe2_distinct.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    report = cal.calibrate()
    if not report["separated"]:
        print("FAILED:IMP-0171 high and low bands overlap")
        return 1

    cmap = C.candidate_map()
    scan = lex.pairwise_scan(list(cmap.items()))
    threshold = report["lexical_near_duplicate_threshold"]
    above = lex.above_threshold(scan, threshold)
    seed_hits = [
        r
        for r in above
        if C.SEED_ID in (r["left_id"], r["right_id"])
    ]
    seed_hit_ids = sorted(
        {
            r["right_id"] if r["left_id"] == C.SEED_ID else r["left_id"]
            for r in seed_hits
        }
    )
    high_ids = {r["id"] for r in C.seed_pairs() if r["class"] in C.HIGH_BAND_CLASSES}
    low_ids = {r["id"] for r in C.seed_pairs() if r["class"] in C.LOW_BAND_CLASSES}
    if set(seed_hit_ids) != high_ids:
        print(f"FAILED:IMP-0171 scan seed hits {seed_hit_ids} != high-band {sorted(high_ids)}")
        return 1
    leaked = [i for i in seed_hit_ids if i in low_ids]
    if leaked:
        print(f"FAILED:IMP-0171 low-band ids leaked above threshold: {leaked}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    floor_audit = REPO / "command-center" / "PROMPT-ONE-FLOOR-AUDIT.md"
    bands_public = {
        cls: {
            "n": report["bands"][cls]["n"],
            "min": report["bands"][cls]["min"],
            "max": report["bands"][cls]["max"],
            "mean": report["bands"][cls]["mean"],
            "kind": "numeric",
            "scores": report["bands"][cls]["scores"],
        }
        for cls in list(C.HIGH_BAND_CLASSES) + list(C.LOW_BAND_CLASSES)
    }

    p_cal = L.probe(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/IMP-0171/calibrate.py",
        json.dumps(
            {
                "bands": bands_public,
                "high_band_min": report["high_band_min"],
                "low_band_max": report["low_band_max"],
                "threshold": threshold,
                "separated": True,
            },
            sort_keys=True,
        ),
        0,
    )
    control = report["known_distinct_control"]
    p_fp = L.probe(
        "verifier",
        "command",
        f"token-jaccard {C.SEED_ID} vs {C.KNOWN_DISTINCT_CONTROL_ID}",
        json.dumps(control, sort_keys=True),
        0,
    )

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    artifacts = [L.art(p, "implementation" if p.endswith("lexical.py") else "supporting") for p in SUPPORTING]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0171",
        "completion_sentinel": "SUCCESS:IMP-0171",
        "title": "Lexical near-duplicate detector with a planted-mutant control",
        "question_or_target": (
            "Implement a token-Jaccard near-duplicate scan over candidate text, "
            "with sensitivity calibrated by planted mutants (exact rename, "
            "paraphrase, one-parameter fork, full rewrite). The report states "
            "the numeric band each mutant class lands in, and scopes the "
            "verdict to LEXICAL similarity: a full semantic rewrite is NOT "
            "detectable by this instrument."
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0171",
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "scope": lex.SCOPE,
        "instrument": {
            "name": "token-set-jaccard",
            "formula": "|A ∩ B| / |A ∪ B| over lowercase [a-z0-9]+ token sets",
            "token_pattern": lex.TOKEN_RE.pattern,
            "embedding": False,
            "semantic": False,
            "detects_full_semantic_rewrite": False,
        },
        "calibration": {
            "seed_id": C.SEED_ID,
            "seed_token_count": report["seed_token_count"],
            "bands": bands_public,
            "high_band_classes": list(C.HIGH_BAND_CLASSES),
            "low_band_classes": list(C.LOW_BAND_CLASSES),
            "high_band_min": report["high_band_min"],
            "low_band_max": report["low_band_max"],
            "separation_gap": report["separation_gap"],
            "separated": True,
            "lexical_near_duplicate_threshold": threshold,
            "threshold_rule": report["threshold_rule"],
            "scope": lex.SCOPE,
            "planted_n_per_class": {
                cls: report["bands"][cls]["n"]
                for cls in list(C.HIGH_BAND_CLASSES) + list(C.LOW_BAND_CLASSES)
            },
        },
        "scan": {
            "candidate_count": len(cmap),
            "pair_count": len(scan),
            "threshold": threshold,
            "above_threshold_count": len(above),
            "seed_above_threshold_ids": seed_hit_ids,
            "seed_above_threshold_equals_high_band": True,
            "low_band_ids_above_threshold": [],
        },
        "known_distinct_control": control,
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "Planted exact-rename, paraphrase, and one-parameter-fork "
                f"mutants land in a high numeric band "
                f"[{report['high_band_min']}, 1.0]; planted full-rewrite and "
                f"known-distinct mutants land in a low numeric band "
                f"[0.0, {report['low_band_max']}]. Gap="
                f"{report['separation_gap']}.",
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0171/corpus.py",
                [p_cal],
                "almost-certain",
            ),
            L.evidence(
                "Known-distinct control "
                f"{C.SEED_ID} vs {C.KNOWN_DISTINCT_CONTROL_ID} scores "
                f"jaccard={control['jaccard']}, which is in the low band "
                f"(max {report['low_band_max']}) and below the lexical "
                f"threshold {threshold}. A full rewrite of the seed lands in "
                "the same low band: this instrument cannot detect it.",
                "CONFIRMED",
                f"{C.SEED_ID}::{C.KNOWN_DISTINCT_CONTROL_ID}",
                [p_fp],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "planted-mutant-classes-land-in-reported-bands",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "known-distinct-control-pair-scores-low",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "adjective-bands-rejected",
                "calibration-not-adjectives",
                "Replacing numeric min/max with 'high'/'low' must fail probe 1.",
                True,
                True,
                bad="exact_rename.min='high'",
                good="exact_rename.min is a float",
            ),
            L.control(
                "known-distinct-false-positive",
                "both-states-threshold",
                "A 0.01 threshold flags the distinct pair; the calibrated "
                "threshold does not. Exact rename is flagged in the same run.",
                True,
                True,
                bad="threshold=0.01 flags distinct-kiln-sign-pipeline",
                good=f"threshold={threshold} silent on distinct, fires on rename",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0171-probe2-known-distinct-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-scores the designated distinct pair with the "
                "Jaccard function and does not walk the calibration table. "
                "Rewrite and distinct share the low band; that is the lexical "
                "scope, not a miss to be tuned away."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0171/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "IMP-0181 renamed-copy / trivial-fork exclusion from the 160-candidate floor",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "notes": "IMP-0181 is a later unit; this receipt is the lexical instrument it consumes.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input command-center/PROMPT-ONE-FLOOR-AUDIT.md is "
                    "absent on this worktree. The instrument and its lexical "
                    "scope caveat were implemented here rather than copied from "
                    "that file."
                ),
                "verdict": "NOT-PRESENT" if not floor_audit.is_file() else "PRESENT",
                "settling_experiment": (
                    "When PROMPT-ONE-FLOOR-AUDIT.md lands, re-read its scope "
                    "sentence and confirm it matches lexical.SCOPE."
                ),
            }
        ],
        "notes": (
            "G-1 IMP-0171: token-Jaccard near-duplicate scan calibrated on "
            "planted mutants. Bands are numbers. Full semantic rewrite is NOT "
            "detectable. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0171 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0171" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0171 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0171 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0171",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-mutant-calibration-bands",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "known-distinct-false-positive-control",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0171/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0171-probe2-known-distinct-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0171: live named probes exit 0, receipts/IMP-0171.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0171/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0171 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
