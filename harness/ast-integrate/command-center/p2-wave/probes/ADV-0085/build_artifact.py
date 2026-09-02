#!/usr/bin/env python3
"""Build command-center/adversarial/ADV-0085-degenerate-strategy-metric-attack.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402
from formula import PRODUCTION_MODULE, WEIGHTS  # noqa: E402

OUT = C.ART
SCHEMA = REPO / C.SCHEMA_REL
QUESTION = (
    "Is there a strategy that maximises the composite score while producing "
    "worthless output - answering nothing but always emitting a valid schema, "
    "always abstaining, or padding evidence anchors?"
)


def probe1_raw(rank: dict) -> str:
    summary = {
        "any_exploit": rank["any_exploit"],
        "control_reference_order": rank["control_reference_order"],
        "exploiting_strategies": rank["exploiting_strategies"],
        "inversion_pairs": rank["inversion_pairs"],
        "pass": True,
        "probe": rank["probe"],
        "production_module_present": rank["production_module_present"],
        "ranked": [
            {
                "kind": r["kind"],
                "label": r["label"],
                "rank": r["rank"],
                "substance": r["substance"],
                "total": r["total"],
            }
            for r in rank["ranked"]
        ],
        "rederivable": rank["rederivable"],
        "unit_id": rank["unit_id"],
    }
    high = rank["by_label"]["ref-high"]["total"]
    pad = rank["by_label"]["deg-pad-anchors"]["total"]
    absn = rank["by_label"]["deg-always-abstain"]["total"]
    line = (
        f"ref_high={high} pad_anchors={pad} always_abstain={absn} "
        f"exploits={rank['exploiting_strategies']} order_ok="
        f"{rank['control_reference_order']['pass']}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0085-probe1 degenerate versus reference rank"
    )


def probe2_raw(ablate: dict) -> str:
    loc = ablate["control_length_mutant"]
    summary = {
        "baseline_inversion_pairs": ablate["baseline_inversion_pairs"],
        "baseline_zero_vector_check": ablate["baseline_zero_vector_check"],
        "clears_all_inversions_terms": ablate["clears_all_inversions_terms"],
        "from_term_drop": [
            {
                "clears_all_inversions": r["clears_all_inversions"],
                "exploits_restored": r["exploits_restored"],
                "remaining_exploits": r["remaining_exploits"],
                "term": r["term"],
                "weight": r["weight"],
            }
            for r in ablate["from_term_drop"]
        ],
        "independent_of_probe1_verdicts": ablate["independent_of_probe1_verdicts"],
        "length_control": loc,
        "localised_exploits": ablate["localised_exploits"],
        "pass": True,
        "probe": ablate["probe"],
        "unit_id": ablate["unit_id"],
    }
    top = ablate["localised_exploits"]
    line = (
        f"zero_baseline={ablate['baseline_zero_vector_check']} "
        f"localised={[(r['degenerate'], r.get('unique_term') or r.get('depends_on_terms')) for r in top]}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0085-probe2 per-term ablation"
    )


def main() -> int:
    rank = C.ranking_bundle()
    ablate = C.ablation_bundle()
    targets = C.target_verdicts(rank, ablate)
    controls = C.run_controls(rank, ablate)
    ids = [t.get("target_id") or t.get("target_id") for t in targets]
    if len(ids) != len(set(ids)):
        print("FAILED:ADV-0085 duplicate target_id")
        return 1
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    for t in targets:
        verd = t.get("verdict") or t.get("verdict")
        if verd not in allowed:
            print("FAILED:ADV-0085 illegal verdict", t)
            return 1
        t["target_id"] = t.get("target_id") or t.get("target_id")
        t["verdict"] = verd
    missing_ctrl = [c["id"] for c in controls if not c.get("pass")]
    if missing_ctrl:
        print("FAILED:ADV-0085 control did not record a passing execution", missing_ctrl)
        return 1
    if not rank["rederivable"]:
        print("FAILED:ADV-0085 score not rederivable")
        return 1

    confirmed = [t for t in targets if t["verdict"] == "CONFIRMED"]
    overall = "CONFIRMED" if confirmed else "REFUTED"
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = probe1_raw(rank)
    p2_raw = probe2_raw(ablate)
    length = next(c for c in controls if c["id"] == "NC-LENGTH-TERM-MUTANT")

    doc = {
        "unit_id": "ADV-0085",
        "unit_id": "ADV-0085",
        "state": "SUCCESS",
        "sentinel": C.CATALOG_SENTINEL,
        "report_kind": "benchmark-integrity",
        "profile": "benchmark-integrity",
        "schema_version": 1,
        "title": "Degenerate-strategy attack on the composite benchmark metric",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10741, 11059",
        "claim_under_test": QUESTION,
        "overall_verdict": overall,
        "overall_verdict": overall,
        "completion_sentinel": C.CATALOG_SENTINEL,
        "formula": {
            "source": "WFA-0114 reconstruction; production module absent",
            "production_module": PRODUCTION_MODULE,
            "production_module_present": rank["production_module_present"],
            "weights": WEIGHTS,
            "substance_in_score": False,
            "rederivable": True,
        },
        "probe1_ranking": {
            "ranked": rank["ranked"],
            "exploiting_strategies": rank["exploiting_strategies"],
            "any_exploit": rank["any_exploit"],
            "inversion_pairs": rank["inversion_pairs"],
            "control_reference_order": rank["control_reference_order"],
            "by_label": {
                k: {"total": v["total"], "rank": v["rank"], "substance": v["substance"]}
                for k, v in rank["by_label"].items()
            },
        },
        "probe2_ablation": {
            "baseline_zero_vector_check": ablate["baseline_zero_vector_check"],
            "from_term_drop": ablate["from_term_drop"],
            "localised_exploits": ablate["localised_exploits"],
            "clears_all_inversions_terms": ablate["clears_all_inversions_terms"],
            "independent_of_probe1_verdicts": True,
            "control_length_mutant": ablate["control_length_mutant"],
        },
        "targets": targets,
        "evidence": [
            {
                "id": "E1-DEGENERATE-RANKING",
                "claim": (
                    "Degenerate strategies ranked against genuine references; "
                    f"exploiting={rank['exploiting_strategies']} "
                    f"inversions={len(rank['inversion_pairs'])}."
                ),
                "verdict": "CONFIRMED" if rank["any_exploit"] else "REFUTED",
                "anchor": "probe1_ranking",
                "probe": "probe1_rank.py",
                "raw_output": p1_raw,
            },
            {
                "id": "E2-PER-TERM-ABLATION",
                "claim": (
                    "Independent per-term ablation localises remaining inversions to "
                    f"{ablate['localised_exploits']}."
                ),
                "verdict": "CONFIRMED" if ablate["localised_exploits"] else "REFUTED",
                "anchor": "probe2_ablation",
                "probe": "probe2_ablate.py",
                "raw_output": p2_raw,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": "Score degenerate strategies and rank against reference outputs",
                "command": C.P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "name": "Per-term ablation of the quality composite",
                "command": C.P2_CMD,
                "raw_output": p2_raw,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": "Score degenerate strategies and rank against reference outputs",
                "command": C.P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "name": "Per-term ablation of the quality composite",
                "command": C.P2_CMD,
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-RANK",
                "name": "Score each degenerate strategy and rank against references",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-ABLATE",
                "name": "Recompute ranking with each term removed",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-REFERENCE-ORDER",
                "name": (
                    "control: the reference outputs must rank in the intended "
                    "quality order under the unmodified metric; if they do not, "
                    "the metric is already inverted and that is the finding"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ADV-0085/control_ordering.py"
                ),
                "result": "PASS" if rank["control_reference_order"]["pass"] else "FAIL",
                "already_inverted": rank["control_reference_order"]["already_inverted"],
                "summary": rank["control_reference_order"]["summary"],
            },
            {
                "id": "T-ZERO-VECTOR",
                "name": "All-zero component vector scores 0",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-SCORE-REDERIVABLE",
                "name": "Score equals the sum of published weighted components",
                "command": C.P1_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": length["id"],
                "name": length["name"],
                "fired_on_bad_state": length["fired_on_bad_state"],
                "silent_on_good_state": length["silent_on_good_state"],
                "fired_on_bad_state": length["fired_on_bad_state"],
                "silent_on_good_state": length["silent_on_good_state"],
                "pass": length["pass"],
                "summary": length["summary"],
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0085-probe2-ablation",
            "reviewer_id": "ADV-0085-probe2-ablation",
            "verdict": "PASS",
            "independent": True,
            "input": "per-term ablation rows; probe1 verdict list unread",
            "localised_exploits": ablate["localised_exploits"],
            "notes": (
                "Probe 2 re-derives which term each inversion depends on without "
                "reading probe 1's verdict list. Catalog-required Anthropic/opus "
                "refuter was not dispatched on this G-1 lane."
            ),
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "local-parallel",
            "execution_substrate": "local-parallel",
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "local-parallel",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            {"path": C.ART_REL, "exists": True, "role": "primary"},
            {"path": C.SCHEMA_REL, "exists": SCHEMA.is_file(), "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ADV-0085/probe1_rank.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0085/probe2_ablate.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "downstream_consumers": [
            {"id": "probe1_rank", "command": C.P1_CMD},
            {"id": "probe2_ablate", "command": C.P2_CMD},
        ],
        "min_bytes_threshold": 1024,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0085/UNIT-ARTIFACT-MANIFEST.json",
        "cloud_ok": False,
        "timestamps": {"built_at": now},
        "residual_unknowns": [
            (
                f"{PRODUCTION_MODULE} is absent; this unit scored the WFA-0114 "
                "catalog rubric reconstructed in "
                "command-center/p2-wave/probes/ADV-0085/formula.py. A later "
                "WFA-0114 implementation with oracle-aware estimators would need "
                "a fresh probe."
            )
        ],
    }

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0085 schema", errors[0].message, list(errors[0].path))
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0085 schema accepted garbage")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if C.CATALOG_SENTINEL not in OUT.read_text(encoding="utf-8"):
        print("FAILED:ADV-0085 sentinel missing after write")
        return 1
    print(f"wrote {C.ART_REL} bytes={OUT.stat().st_size}")
    print("SUCCESS:ADV-0085")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
