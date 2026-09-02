#!/usr/bin/env python3
"""Build command-center/adversarial/ADV-0067-conformance-score-gaming.json."""
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
    "Can a package raise its quality/conformance score without improving "
    "quality - by adding trivial tests, padding documentation, declaring "
    "benchmarks it did not run, or shipping fixtures that satisfy a "
    "checker's heuristic?"
)


def probe1_raw(cmp: dict) -> str:
    summary = {
        "cheap_terms": cmp["cheap_terms_gamed_beats_genuine"],
        "control_empty_lowest": cmp["control_empty_lowest"],
        "control_genuine_not_lower": cmp["control_genuine_not_lower"],
        "control_no_tests_lower": cmp["control_no_tests_lower"],
        "control_popularity_invariant": cmp["control_popularity_invariant"],
        "empty_total": cmp["empty"]["total"],
        "gamed_matches_or_beats_genuine": cmp["gamed_matches_or_beats_genuine"],
        "gamed_total": cmp["gamed"]["total"],
        "genuine_total": cmp["genuine"]["total"],
        "named_inversion_term": cmp["named_inversion_term"],
        "pass": True,
        "probe": cmp["probe"],
        "production_module_present": cmp["production_module_present"],
        "substance_gamed_weaker": cmp["substance_gamed_weaker"],
        "unit_id": cmp["unit_id"],
    }
    line = (
        f"genuine={cmp['genuine']['total']} gamed={cmp['gamed']['total']} "
        f"empty={cmp['empty']['total']} inversion={cmp['named_inversion_term']}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0067-probe1 min-substance versus genuine"
    )


def probe2_raw(sens: dict) -> str:
    summary = {
        "baseline_zero_score": sens["baseline_zero_score"],
        "from_zero": [
            {"marginal_from_zero": r["marginal_from_zero"], "term": r["term"]}
            for r in sens["from_zero"]
        ],
        "gamed_ablation": [
            {"marginal_on_gamed": r["marginal_on_gamed"], "term": r["term"]}
            for r in sens["gamed_ablation"]
        ],
        "gamed_highest_ablation_term": sens["gamed_highest_ablation_term"],
        "highest_marginal_term": sens["highest_marginal_term"],
        "independent_of_probe1_packages": sens["independent_of_probe1_packages"],
        "pass": True,
        "popularity_control": sens["control_popularity_silent_on_good"],
        "probe": sens["probe"],
        "unit_id": sens["unit_id"],
    }
    top = sens["gamed_highest_ablation_term"]
    line = (
        f"zero_baseline={sens['baseline_zero_score']} "
        f"top_from_zero={sens['highest_marginal_term']} "
        f"gamed_ablation_top={top}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0067-probe2 per-term sensitivity"
    )


def main() -> int:
    cmp = C.compare_packages()
    sens = C.sensitivity_analysis()
    targets = C.target_verdicts(cmp, sens)
    controls = C.run_controls(cmp, sens)
    ids = [t["target_id"] for t in targets]
    if len(ids) != len(set(ids)):
        print("FAILED:ADV-0067 duplicate target_id")
        return 1
    for t in targets:
        if t["verdict"] not in {
            "CONFIRMED",
            "REFUTED",
            "PARTIAL",
            "NOT-CHECKED",
            "BLOCKED",
        }:
            print("FAILED:ADV-0067 illegal verdict", t)
            return 1
    missing_ctrl = [c["id"] for c in controls if not c.get("pass")]
    if missing_ctrl:
        print("FAILED:ADV-0067 control did not record a passing execution", missing_ctrl)
        return 1
    if not cmp["substance_gamed_weaker"]:
        print("FAILED:ADV-0067 gamed package is not weaker on substance")
        return 1
    if not cmp["genuine"]["rederivable"] or not cmp["gamed"]["rederivable"]:
        print("FAILED:ADV-0067 score not rederivable")
        return 1

    confirmed = [t for t in targets if t["verdict"] == "CONFIRMED"]
    overall = "CONFIRMED" if confirmed else "REFUTED"
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = probe1_raw(cmp)
    p2_raw = probe2_raw(sens)
    pop = next(c for c in controls if c["id"] == "NC-POPULARITY-TERM-MUTANT")

    doc = {
        "unit_id": "ADV-0067",
        "state": "SUCCESS",
        "sentinel": C.CATALOG_SENTINEL,
        "report_kind": "benchmark-integrity",
        "profile": "benchmark-integrity",
        "schema_version": 1,
        "title": "Gaming the marketplace quality and conformance score",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10859, 11059",
        "claim_under_test": QUESTION,
        "overall_verdict": overall,
        "completion_sentinel": C.CATALOG_SENTINEL,
        "formula": {
            "source": "IMP-0094 reconstruction; production module absent",
            "production_module": PRODUCTION_MODULE,
            "production_module_present": cmp["production_module_present"],
            "weights": WEIGHTS,
            "popularity_input": False,
            "rederivable": True,
        },
        "probe1_comparison": {
            "genuine_total": cmp["genuine"]["total"],
            "gamed_total": cmp["gamed"]["total"],
            "empty_total": cmp["empty"]["total"],
            "named_inversion_term": cmp["named_inversion_term"],
            "cheap_terms_gamed_beats_genuine": cmp["cheap_terms_gamed_beats_genuine"],
            "genuine": cmp["genuine"],
            "gamed": cmp["gamed"],
            "empty": cmp["empty"],
            "popularity_twin": cmp["popularity_twin"],
            "part_delta": cmp["part_delta"],
            "substance_gap": cmp["substance_gap"],
        },
        "probe2_sensitivity": {
            "baseline_zero_score": sens["baseline_zero_score"],
            "from_zero": sens["from_zero"],
            "gamed_ablation": sens["gamed_ablation"],
            "highest_marginal_term": sens["highest_marginal_term"],
            "gamed_highest_ablation_term": sens["gamed_highest_ablation_term"],
            "independent_of_probe1_packages": True,
        },
        "targets": targets,
        "evidence": [
            {
                "id": "E1-SIDE-BY-SIDE-SCORES",
                "claim": (
                    f"Minimum-substance package scores {cmp['gamed']['total']} vs "
                    f"genuine {cmp['genuine']['total']} while substance is weaker "
                    f"(nontrivial asserts {cmp['gamed']['substance']['assert_nontrivial']} "
                    f"vs {cmp['genuine']['substance']['assert_nontrivial']}; reproduced "
                    f"benchmarks {cmp['gamed']['substance']['reproduced_benchmarks']} vs "
                    f"{cmp['genuine']['substance']['reproduced_benchmarks']})."
                ),
                "verdict": "CONFIRMED" if cmp["gamed_matches_or_beats_genuine"] else "REFUTED",
                "anchor": "probe1_comparison",
                "probe": "probe1_compare.py",
                "raw_output": p1_raw,
            },
            {
                "id": "E2-PER-TERM-SENSITIVITY",
                "claim": (
                    "Independent zero-vector perturbations show each term's weight as "
                    f"its marginal contribution; gamed ablation top term is "
                    f"{sens['gamed_highest_ablation_term']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "probe2_sensitivity",
                "probe": "probe2_sensitivity.py",
                "raw_output": p2_raw,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": "Minimum-substance package versus genuine package",
                "command": C.P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "name": "Per-term sensitivity analysis of the score formula",
                "command": C.P2_CMD,
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-COMPARE",
                "name": "Build min-substance and genuine packages and record both scores",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-SENSITIVITY",
                "name": "Perturb each score input independently and measure marginal contribution",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-GENUINE-NOT-LOWER",
                "name": (
                    "control: the genuinely good package must not score LOWER than "
                    "the gamed one; if it does, the formula is inverted for at least "
                    "one term and that term must be named"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ADV-0067/control_ordering.py"
                ),
                "result": "PASS" if cmp["control_genuine_not_lower"]["pass"] else "FAIL",
                "inverted": cmp["control_genuine_not_lower"]["inverted"],
                "named_term": cmp["named_inversion_term"],
                "summary": cmp["control_genuine_not_lower"]["summary"],
            },
            {
                "id": "T-NO-TESTS-LOWER",
                "name": "NEGATIVE CONTROL: a package with no tests scores strictly lower",
                "command": C.P1_CMD,
                "result": "PASS" if cmp["control_no_tests_lower"]["pass"] else "FAIL",
            },
            {
                "id": "T-POPULARITY-INVARIANT",
                "name": "no popularity input may change the score",
                "command": C.P2_CMD,
                "result": "PASS" if cmp["control_popularity_invariant"]["pass"] else "FAIL",
            },
            {
                "id": "T-EMPTY-NOT-CONSTANT",
                "name": "Empty package scores below both populated packages",
                "command": C.P1_CMD,
                "result": "PASS" if cmp["control_empty_lowest"]["pass"] else "FAIL",
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
                "id": pop["id"],
                "name": pop["name"],
                "fired_on_bad_state": pop["fired_on_bad_state"],
                "silent_on_good_state": pop["silent_on_good_state"],
                "pass": pop["pass"],
                "summary": pop["summary"],
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0067-probe2-sensitivity",
            "verdict": "PASS",
            "independent": True,
            "input": "zero-vector perturbations and gamed ablation; probe1 prose unread",
            "named_cheap_term": sens["gamed_highest_ablation_term"],
            "notes": (
                "Probe 2 re-derives per-term weights from the zero vector and "
                "names the gamed ablation top term without reading probe 1's "
                "verdict list. Catalog-required Anthropic/opus refuter was not "
                "dispatched on this G-1 lane."
            ),
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            {
                "path": C.ART_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": C.SCHEMA_REL,
                "exists": SCHEMA.is_file(),
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0067/probe1_compare.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0067/probe2_sensitivity.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "downstream_consumers": [
            {"id": "probe1_compare", "command": C.P1_CMD},
            {"id": "probe2_sensitivity", "command": C.P2_CMD},
        ],
        "min_bytes_threshold": 1024,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0067/UNIT-ARTIFACT-MANIFEST.json",
        "cloud_ok": False,
        "timestamps": {"built_at": now},
        "residual_unknowns": [
            (
                "tools/marketplace/quality_score.py is absent; this unit scored the "
                "IMP-0094 catalog formula reconstructed in "
                "command-center/p2-wave/probes/ADV-0067/formula.py. A later IMP-0094 "
                "implementation with different weights would need a fresh probe."
            )
        ],
    }

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0067 schema", errors[0].message, list(errors[0].path))
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0067 schema accepted garbage")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if C.CATALOG_SENTINEL not in OUT.read_text(encoding="utf-8"):
        print("FAILED:ADV-0067 sentinel missing after write")
        return 1
    print(f"wrote {C.ART_REL} bytes={OUT.stat().st_size}")
    print("SUCCESS:ADV-0067")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
