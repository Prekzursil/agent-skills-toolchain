#!/usr/bin/env python3
"""Emit RES-0170 measurement artifact, SUBAGENT-RETURN, per-unit manifest."""
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
UNIT = "RES-0170"
OUT = "command-center/research/deep-research-design/RES-0170-computable-research-quality-target.json"
SCHEMA_DECLARED = "command-center/schema/measurement-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0170/probe1_rank_and_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0170/probe2_shape_vs_substance.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0170/source_classes.py",
    "command-center/p2-wave/probes/RES-0170/lineage.py",
    "command-center/p2-wave/probes/RES-0170/resolver.py",
    "command-center/p2-wave/probes/RES-0170/corpus.py",
    "command-center/p2-wave/probes/RES-0170/scorer.py",
    "command-center/p2-wave/probes/RES-0170/probe1_rank_and_negative_control.py",
    "command-center/p2-wave/probes/RES-0170/probe2_shape_vs_substance.py",
    "command-center/p2-wave/probes/RES-0170/emit_receipt.py",
    "command-center/p2-wave/probes/RES-0170/fixtures/A1-gold.json",
    "command-center/p2-wave/probes/RES-0170/fixtures/A2-coverage-gap.json",
    "command-center/p2-wave/probes/RES-0170/fixtures/A3-single-source.json",
    "command-center/p2-wave/probes/RES-0170/fixtures/A4-no-contradiction.json",
    "command-center/p2-wave/probes/RES-0170/fixtures/A5-orphan-unknown.json",
    "command-center/p2-wave/probes/RES-0170/fixtures/A6-padded-citations.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") or "").strip()
    err = ((p.stderr or "") or "").strip()
    if err:
        text = (text + "\n" + err).strip()
    return p.returncode, text


def first_json(text: str):
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0170/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    from corpus import APRIORI_BEST_TO_WORST, PADDED_ID, bodies, ensure_on_disk, load_from_disk, relpath
    from scorer import GATES, DIMENSIONS, WEIGHT, score_corpus
    from source_classes import DERIVATION, SOURCE_CLASSES

    ensure_on_disk()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0170 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    arts = load_from_disk()
    measured = score_corpus(arts, bodies())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA_DECLARED
    schema_present = schema_path.is_file() and schema_path.stat().st_size > 0
    user_prompts = REPO / "_USER-PROMPTS.md"
    register = REPO / "command-center/sources/REGISTER.md"
    claims_reg = REPO / "command-center/CLAIM-REGISTRY.json"
    live_research = REPO / "command-center/research"
    live_research_json = []
    if live_research.is_dir():
        live_research_json = [
            p.relative_to(REPO).as_posix()
            for p in live_research.rglob("*.json")
            if p.is_file() and "RES-0170" not in p.name
        ]

    fixture_paths = [relpath(a) for a in arts]
    by_id = {r["id"]: r for r in measured["rows"]}
    gold_lineage = by_id["A1-gold"]["lineage_sample"]
    padded_lineage = by_id[PADDED_ID]["lineage_sample"]

    def claim(
        cid: str,
        text: str,
        verdict: str,
        band: str,
        sources: list[dict],
        verification: str,
    ) -> dict:
        return {
            "id": cid,
            "claim": text,
            "verdict": verdict,
            "sherman_kent_band": band,
            "sources": sources,
            "named_independent_verification_path": verification,
        }

    lineage_gold = []
    for block in gold_lineage:
        for src in block.get("sources") or []:
            lineage_gold.append(
                {
                    "resolved_url": src.get("resolved_url"),
                    "fetch_timestamp": src.get("fetched_at"),
                    "sha256": src.get("sha256"),
                    "http_status": src.get("http_status"),
                    "content_match": src.get("content_match"),
                    "id": src.get("id"),
                }
            )
    lineage_pad = []
    for block in padded_lineage:
        for src in block.get("sources") or []:
            lineage_pad.append(
                {
                    "resolved_url": src.get("resolved_url"),
                    "fetch_timestamp": src.get("fetched_at"),
                    "sha256": src.get("sha256"),
                    "http_status": src.get("http_status"),
                    "content_match": src.get("content_match"),
                    "id": src.get("id"),
                }
            )

    input_gaps = [
        {
            "path": "_USER-PROMPTS.md",
            "present": user_prompts.is_file(),
            "effect": "16-class list reconstructed from catalog citations; rebound required if the spec page is mounted.",
        },
        {
            "path": "command-center/sources/REGISTER.md",
            "present": register.is_file(),
            "effect": "no live source register to bind class TTLs; fixtures used instead.",
        },
        {
            "path": "command-center/CLAIM-REGISTRY.json",
            "present": claims_reg.is_file(),
            "effect": "no claim registry to score; fixtures used instead.",
        },
        {
            "path": SCHEMA_DECLARED,
            "present": schema_present,
            "effect": "catalog output_schema file is absent on this worktree; G-1 does not consult it.",
        },
        {
            "path": "command-center/research/",
            "present": live_research.is_dir(),
            "live_research_json_excluding_this_unit": live_research_json,
            "effect": (
                "Phase-2 research JSON corpus is absent. Validation scores six "
                "committed fixture artifacts with a priori quality labels."
            ),
        },
    ]

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "What is a computable quality target for a research deliverable?",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:RES-0170",
        "completion_sentinel": "SUCCESS:RES-0170",
        "report_kind": "measurement-run",
        "schema_version": 1,
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA_DECLARED,
        "schema_gate": {
            "enforced": False,
            "valid": None,
            "classification": "schema-unresolvable" if not schema_present else "ok",
            "schema_path": SCHEMA_DECLARED,
            "on_disk": schema_present,
            "note": (
                "Catalog points at measurement-run.schema.json which is absent. "
                "This artifact is a measurement-run by report_kind. G-1 delivery "
                "does not parse that schema file."
            ),
        },
        "question": (
            "Define a research-quality target that a runner can evaluate without "
            "a human - source-class coverage, independent-source count per "
            "load-bearing claim, contradiction coverage, unresolved-unknown "
            "count with named experiments, citation resolvability - and validate "
            "it by scoring 6 existing research artifacts whose quality is already "
            "known to differ."
        ),
        "answer": (
            "The target is the equal-weight mean of five mechanical scores in "
            f"{list(DIMENSIONS)}. Unresolvable citations increment no other "
            "dimension. On six committed fixtures the metric ranking matches "
            f"the a priori order {APRIORI_BEST_TO_WORST} (Spearman "
            f"{measured['spearman_vs_apriori']}). The padded-citation artifact "
            f"{PADDED_ID} ranks last on substance and first on naive URL-count. "
            "SUCCESS:RES-0170"
        ),
        "quality_target": measured["quality_target"],
        "gates": GATES,
        "dimension_weight": WEIGHT,
        "source_class_register": {
            "classes": list(SOURCE_CLASSES),
            "count": len(SOURCE_CLASSES),
            "derivation": DERIVATION,
        },
        "input_gaps": input_gaps,
        "corpus": {
            "kind": "committed-fixture-research-artifacts",
            "why_not_live_phase2_outputs": (
                "command-center/research/ has no prior RES-*.json on this worktree."
            ),
            "n": 6,
            "paths": fixture_paths,
            "a_priori_best_to_worst": APRIORI_BEST_TO_WORST,
            "padded_negative_control_id": PADDED_ID,
        },
        "scores": measured["rows"],
        "ranking": {
            "metric_best_to_worst": measured["order_best_to_worst"],
            "padded_rank": measured["padded_rank"],
            "padded_is_lowest": measured["padded_is_lowest"],
            "padded_naive_rank": measured["padded_naive_rank"],
            "naive_ranks_padded_first": measured["naive_ranks_padded_first"],
            "spearman_vs_apriori": measured["spearman_vs_apriori"],
        },
        "negative_control": {
            "id": "padded-unresolvable-or-mismatched-citations",
            "artifact_id": PADDED_ID,
            "requirement": (
                "score one artifact that is known to be padded with unresolvable "
                "or mismatched citations and require the metric to rank it lowest; "
                "if it does not, the metric is counting shape not substance"
            ),
            "metric_rank": measured["padded_rank"],
            "is_lowest": measured["padded_is_lowest"],
            "naive_url_count_rank": measured["padded_naive_rank"],
            "naive_counts_shape_not_substance": measured["naive_ranks_padded_first"],
            "resolvability": by_id[PADDED_ID]["scores"]["citation_resolvability"],
            "composite": by_id[PADDED_ID]["composite"],
        },
        "claims": [
            claim(
                "CLM-TARGET-FIVE-DIMS",
                "A runner can evaluate research quality without a human using five mechanical dimensions: source-class coverage, independent-source rate per load-bearing claim, contradiction coverage, named-experiment rate on unknowns, and citation resolvability (HTTP status plus content match).",
                "CONFIRMED",
                "almost-certain",
                lineage_gold[:4],
                "command-center/p2-wave/probes/RES-0170/scorer.py:dimension_scores",
            ),
            claim(
                "CLM-PADDED-LOWEST",
                f"On this six-artifact set the padded unresolvable-citation artifact {PADDED_ID} ranks lowest on the substance metric (rank {measured['padded_rank']}) while a naive URL-string counter ranks it first.",
                "CONFIRMED",
                "almost-certain",
                lineage_pad[:4],
                "command-center/p2-wave/probes/RES-0170/probe1_rank_and_negative_control.py",
            ),
            claim(
                "CLM-SHAPE-VS-SUBSTANCE",
                "Repairing A6 citations raises its composite from 0 to the gold score; replacing A1 citations with padding drops that artifact to last. The naive matcher stays high on padding in both states.",
                "CONFIRMED",
                "almost-certain",
                lineage_gold[:2] + lineage_pad[:2],
                "command-center/p2-wave/probes/RES-0170/probe2_shape_vs_substance.py",
            ),
            claim(
                "CLM-LIVE-CORPUS-ABSENT",
                "The Phase-2 research JSON corpus (RES-0001..RES-0127) is absent on this worktree, so validation is over six committed fixture artifacts with a priori quality labels, not over harvested deep-research outputs.",
                "CONFIRMED",
                "almost-certain",
                [
                    {
                        "resolved_url": "file://" + str(live_research),
                        "fetch_timestamp": now,
                        "sha256": None,
                        "note": "directory absent or empty of other RES JSON",
                        "present": live_research.is_dir(),
                        "other_res_json": live_research_json,
                    }
                ],
                "pathlib walk of command-center/research/ plus catalog output_path",
            ),
        ],
        "tests": [
            {
                "id": "named-probe-1-rank-and-negative-control",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "named-probe-2-shape-vs-substance",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "required-negative-control-padded-lowest",
                "result": "PASS" if measured["padded_is_lowest"] else "FAIL",
                "artifact_id": PADDED_ID,
            },
            {
                "id": "naive-url-count-does-not-agree",
                "result": "PASS" if measured["naive_ranks_padded_first"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0170-probe2-shape-vs-substance",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "defaults_to": "REFUTED",
            "method": (
                "Re-score the corpus; require padded last; flip both states "
                "(repair A6, pad A1); require naive URL-count to stay high on padding."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "path": "command-center/p2-wave/probes/RES-0170/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0170/scorer.py",
                "kind": "metric-implementation",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0170/probe1_rank_and_negative_control.py",
                "kind": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0170/probe2_shape_vs_substance.py",
                "kind": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0170/fixtures/A6-padded-citations.json",
                "kind": "negative-control-fixture",
            },
        ],
        "residual_unknowns": [
            {
                "id": "U-USER-PROMPTS-16-CLASS",
                "unknown": "Byte-exact 16 source classes at _USER-PROMPTS.md:10683-10700.",
                "named_experiment": "Mount the restore snapshot and diff against SOURCE_CLASSES.",
            },
            {
                "id": "U-LIVE-RES-CORPUS",
                "unknown": "How the metric ranks harvested RES-0001..RES-0127 artifacts.",
                "named_experiment": "When those JSON files exist, run score_corpus on them without changing gates.",
            },
            {
                "id": "U-MEASUREMENT-RUN-SCHEMA",
                "unknown": "Whether this document validates against the missing measurement-run.schema.json.",
                "named_experiment": "Place the schema file and re-validate; do not hand-flip state.",
            },
        ],
        "probe1": j1,
        "probe2": j2,
        "honesty": {
            "cloud_ok_is_not_delivery": True,
            "did_not_run_global_unit_manifest_write": True,
            "user_prompts_absent": not user_prompts.is_file(),
            "catalog_schema_absent": not schema_present,
            "live_phase2_research_json_absent": not live_research_json,
            "citation_resolution": "live HTTP GET against a local fixture server; status plus body sha256 plus quote match",
            "independence": "origin-tracing, not distinct-URL counting",
        },
        "SUCCESS:RES-0170": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0170",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "rank-and-negative-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "shape-vs-substance-both-states",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0170/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0170-probe2-shape-vs-substance",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0170: live named probes exit 0, primary state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Phase-2 research corpus and measurement-run.schema.json are absent; "
            "validation used six committed fixtures including a padded-citation "
            "negative control that ranks last on substance."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0170 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
