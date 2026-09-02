"""Shared ADV-0067 helpers: fixtures, comparison, sensitivity, controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formula import (
    PRODUCTION_MODULE,
    TERM_IDS,
    WEIGHTS,
    score_from_components,
    score_with_popularity_term,
)
from package_inspect import inspect_package

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
ART_REL = "command-center/adversarial/ADV-0067-conformance-score-gaming.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/benchmark-integrity.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0067 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0067 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0067/probe1_compare.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0067/probe2_sensitivity.py"
)

GAMED_README = (
    "# Quality\n\n## Overview\n## Install\n## Usage\n## API\n## License\n\n"
    + ("quality conformance excellence marketplace rating. " * 40)
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def production_module_present() -> bool:
    return (REPO / PRODUCTION_MODULE).is_file()


def ensure_fixtures() -> dict[str, Path]:
    """Materialise the four fixture packages with deterministic bytes."""
    genuine = FIXTURES / "genuine"
    gamed = FIXTURES / "gamed"
    empty = FIXTURES / "empty"
    popular = FIXTURES / "popularity_twin"

    _write_json(
        genuine / "manifest.json",
        {
            "name": "genuine-quality-pack",
            "version": "2.1.0",
            "entrypoint": "src/plugin.py",
            "downloads": 12,
        },
    )
    _write(
        genuine / "src/plugin.py",
        (
            "def add(left: int, right: int) -> int:\n"
            "    return left + right\n\n"
            "def checksum(values):\n"
            "    total = 0\n"
            "    for item in values:\n"
            "        total = (total + int(item)) % 1000003\n"
            "    return total\n\n"
            "ENTRY = add\n"
        ),
    )
    _write(
        genuine / "tests/test_plugin.py",
        (
            "from src.plugin import add, checksum\n\n"
            "def test_add_identity():\n"
            "    assert add(2, 3) == 5\n"
            "    assert add(-1, 1) == 0\n\n"
            "def test_checksum_stable():\n"
            "    assert checksum([1, 2, 3]) == checksum([1, 2, 3])\n"
            "    assert checksum([10]) == 10\n"
        ),
    )
    _write(
        genuine / "README.md",
        (
            "# genuine-quality-pack\n\n"
            "## Purpose\n\n"
            "Implements integer addition and a small checksum used by the "
            "marketplace fixture so reviewers can re-run behaviour, not just "
            "open a file that exists.\n\n"
            "## Install\n\n"
            "Place the package root on PYTHONPATH and import src.plugin.\n\n"
            "## Usage\n\n"
            "Call add(2, 3) and expect 5. checksum walks a sequence of ints.\n\n"
            "## Tests\n\n"
            "tests/test_plugin.py asserts those identities.\n\n"
            "## Provenance\n\n"
            "Builder id and materials are in provenance.json; the SBOM lists "
            "the two Python modules that actually shipped.\n"
        ),
    )
    _write_json(
        genuine / "sbom.json",
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [
                {"name": "genuine-quality-pack", "version": "2.1.0", "type": "library"},
                {"name": "src/plugin.py", "type": "file"},
                {"name": "tests/test_plugin.py", "type": "file"},
            ],
        },
    )
    _write_json(
        genuine / "provenance.json",
        {
            "_type": "https://in-toto.io/Statement/v1",
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "buildType": "https://example.invalid/genuine-build",
                    "externalParameters": {"entry": "src/plugin.py"},
                },
                "runDetails": {"builder": {"id": "https://example.invalid/builders/genuine"}},
            },
            "subject": [{"name": "genuine-quality-pack", "digest": {"sha256": "not-a-secret"}}],
        },
    )
    _write_json(genuine / "advisories.json", {"open": []})
    _write_json(
        genuine / "benchmarks.json",
        {
            "benchmarks": [
                {
                    "id": "add-micro",
                    "declared": True,
                    "reproduction": {
                        "executed": True,
                        "within_tolerance": True,
                        "runs": 3,
                        "observed": [5, 5, 5],
                    },
                },
                {
                    "id": "checksum-micro",
                    "declared": True,
                    "reproduction": {
                        "executed": True,
                        "within_tolerance": True,
                        "runs": 2,
                        "observed": [10, 10],
                    },
                },
            ]
        },
    )

    _write_json(
        gamed / "manifest.json",
        {
            "name": "min-substance-max-score",
            "version": "0.0.1",
            "entrypoint": "src/plugin.py",
            "downloads": 0,
        },
    )
    _write(gamed / "src/plugin.py", "ENTRY = None\n")
    _write(
        gamed / "tests/test_plugin.py",
        (
            "def test_placeholder_a():\n"
            "    assert True\n\n"
            "def test_placeholder_b():\n"
            "    assert True\n\n"
            "def test_placeholder_c():\n"
            "    assert 1\n"
        ),
    )
    _write(gamed / "README.md", GAMED_README)
    _write_json(gamed / "sbom.json", {"bomFormat": "CycloneDX"})
    _write_json(
        gamed / "provenance.json",
        {"_type": "https://in-toto.io/Statement/v1"},
    )
    _write_json(gamed / "advisories.json", {"open": []})
    _write_json(
        gamed / "benchmarks.json",
        {
            "benchmarks": [
                {"id": "claimed-fast", "declared": True},
                {"id": "claimed-correct", "declared": True},
                {"id": "claimed-scale", "declared": True},
            ]
        },
    )

    _write_json(empty / "manifest.json", {"name": ""})

    for src, dst in (
        (genuine / "manifest.json", popular / "manifest.json"),
        (genuine / "src/plugin.py", popular / "src/plugin.py"),
        (genuine / "tests/test_plugin.py", popular / "tests/test_plugin.py"),
        (genuine / "README.md", popular / "README.md"),
        (genuine / "sbom.json", popular / "sbom.json"),
        (genuine / "provenance.json", popular / "provenance.json"),
        (genuine / "advisories.json", popular / "advisories.json"),
        (genuine / "benchmarks.json", popular / "benchmarks.json"),
    ):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    man = json.loads((popular / "manifest.json").read_text(encoding="utf-8"))
    man["downloads"] = 9_000_000
    man["name"] = "genuine-quality-pack-popular"
    _write_json(popular / "manifest.json", man)

    return {
        "genuine": genuine,
        "gamed": gamed,
        "empty": empty,
        "popularity_twin": popular,
    }


def scored_package(label: str, root: Path) -> dict[str, Any]:
    inspected = inspect_package(root)
    scored = score_from_components(inspected["components"])
    return {
        "label": label,
        "root": str(root.relative_to(REPO)).replace("\\", "/"),
        "inspected": inspected,
        "score": scored,
        "total": scored["total"],
    }


def compare_packages() -> dict[str, Any]:
    paths = ensure_fixtures()
    genuine = scored_package("genuine", paths["genuine"])
    gamed = scored_package("gamed", paths["gamed"])
    empty = scored_package("empty", paths["empty"])
    popular = scored_package("popularity_twin", paths["popularity_twin"])

    genuine_total = genuine["total"]
    gamed_total = gamed["total"]
    empty_total = empty["total"]
    popular_total = popular["total"]

    part_delta = {}
    cheap_terms = []
    for term in TERM_IDS:
        g_part = gamed["score"]["parts"][term]
        q_part = genuine["score"]["parts"][term]
        delta = round(g_part - q_part, 6)
        part_delta[term] = {
            "genuine": q_part,
            "gamed": g_part,
            "gamed_minus_genuine": delta,
        }
        if delta > 0:
            cheap_terms.append(term)
    cheap_terms.sort(key=lambda t: (-part_delta[t]["gamed_minus_genuine"], t))

    inverted = genuine_total < gamed_total
    named_inversion_term = cheap_terms[0] if inverted and cheap_terms else None
    ordering_holds = genuine_total >= gamed_total
    ordering_recorded = ordering_holds or bool(named_inversion_term)

    g_sub = genuine["inspected"]["substance"]
    a_sub = gamed["inspected"]["substance"]
    substance_gap = {
        "assert_nontrivial": {
            "genuine": g_sub["assert_nontrivial"],
            "gamed": a_sub["assert_nontrivial"],
        },
        "unique_doc_tokens": {
            "genuine": g_sub["unique_doc_tokens"],
            "gamed": a_sub["unique_doc_tokens"],
        },
        "reproduced_benchmarks": {
            "genuine": g_sub["reproduced_benchmarks"],
            "gamed": a_sub["reproduced_benchmarks"],
        },
        "src_loc": {"genuine": g_sub["src_loc"], "gamed": a_sub["src_loc"]},
    }

    no_tests = dict(genuine["inspected"]["components"])
    no_tests["test_presence"] = 0.0
    no_tests["test_pass_rate"] = 0.0
    no_tests_total = score_from_components(no_tests)["total"]

    return {
        "probe": "probe1-min-substance-versus-genuine",
        "unit_id": "ADV-0067",
        "production_module": PRODUCTION_MODULE,
        "production_module_present": production_module_present(),
        "formula": "IMP-0094-reconstruction+declared-benchmark-term",
        "genuine": {
            "total": genuine_total,
            "parts": genuine["score"]["parts"],
            "components": genuine["score"]["components"],
            "raw_components": genuine["inspected"]["components"],
            "substance": g_sub,
            "root": genuine["root"],
            "rederivable": genuine["score"]["rederivable"],
        },
        "gamed": {
            "total": gamed_total,
            "parts": gamed["score"]["parts"],
            "components": gamed["score"]["components"],
            "raw_components": gamed["inspected"]["components"],
            "substance": a_sub,
            "root": gamed["root"],
            "rederivable": gamed["score"]["rederivable"],
        },
        "empty": {"total": empty_total, "root": empty["root"]},
        "popularity_twin": {
            "total": popular_total,
            "downloads": popular["inspected"]["downloads"],
            "root": popular["root"],
        },
        "part_delta": part_delta,
        "cheap_terms_gamed_beats_genuine": cheap_terms,
        "named_inversion_term": named_inversion_term,
        "control_genuine_not_lower": {
            "pass": ordering_recorded,
            "ordering_holds": ordering_holds,
            "genuine": genuine_total,
            "gamed": gamed_total,
            "inverted": inverted,
            "named_term": named_inversion_term,
            "summary": (
                "genuine scored lower than gamed; inverted/cheap term is "
                + (named_inversion_term or "unidentified")
                if inverted
                else "genuine scored at least as high as gamed"
            ),
        },
        "control_empty_lowest": {
            "pass": empty_total < genuine_total and empty_total < gamed_total,
            "empty": empty_total,
            "genuine": genuine_total,
            "gamed": gamed_total,
        },
        "control_no_tests_lower": {
            "pass": no_tests_total < genuine_total,
            "with_tests": genuine_total,
            "without_tests": no_tests_total,
        },
        "control_popularity_invariant": {
            "pass": abs(popular_total - genuine_total) < 1e-9,
            "genuine": genuine_total,
            "popularity_twin": popular_total,
        },
        "substance_gap": substance_gap,
        "gamed_matches_or_beats_genuine": gamed_total >= genuine_total,
        "substance_gamed_weaker": (
            a_sub["assert_nontrivial"] < g_sub["assert_nontrivial"]
            and a_sub["reproduced_benchmarks"] < g_sub["reproduced_benchmarks"]
            and a_sub["src_loc"] <= g_sub["src_loc"]
        ),
    }


def zero_components() -> dict[str, Any]:
    return {
        "conformance_pass_rate": 0.0,
        "test_presence": 0.0,
        "test_pass_rate": 0.0,
        "documentation_completeness": 0.0,
        "sbom_present": 0.0,
        "provenance_present": 0.0,
        "advisory_cleanliness": 0.0,
        "declared_benchmarks": 0,
        "downloads": 0,
    }


def max_for_term(term: str) -> dict[str, Any]:
    row = zero_components()
    if term == "declared_benchmarks":
        row["declared_benchmarks"] = 3
    elif term == "test_pass_rate":
        row["test_presence"] = 1.0
        row["test_pass_rate"] = 1.0
    else:
        row[term] = 1.0
    return row


def sensitivity_analysis() -> dict[str, Any]:
    """Perturb each score input independently from the zero vector (probe 2)."""
    baseline = score_from_components(zero_components())
    rows = []
    for term in TERM_IDS:
        bumped = max_for_term(term)
        scored = score_from_components(bumped)
        # Isolate test_pass_rate's own weight: max_for_term also turns presence on.
        if term == "test_pass_rate":
            presence_only = zero_components()
            presence_only["test_presence"] = 1.0
            presence_score = score_from_components(presence_only)["total"]
            marginal = round(scored["total"] - presence_score, 6)
        else:
            marginal = round(scored["total"] - baseline["total"], 6)
        rows.append(
            {
                "term": term,
                "weight": WEIGHTS[term],
                "score_at_max": scored["total"],
                "marginal_from_zero": marginal,
                "cheap_recipe": CHEAP_RECIPES[term],
            }
        )
    ranked = sorted(rows, key=lambda r: (-r["marginal_from_zero"], r["term"]))

    cmp = compare_packages()
    gamed_comp = cmp["gamed"]["components"]
    drop_rows = []
    for term in TERM_IDS:
        dropped = dict(cmp["gamed"]["raw_components"])
        if term == "declared_benchmarks":
            dropped["declared_benchmarks"] = 0
        elif term == "test_pass_rate":
            dropped["test_pass_rate"] = 0.0
        elif term == "test_presence":
            dropped["test_presence"] = 0.0
            dropped["test_pass_rate"] = 0.0
        else:
            dropped[term] = 0.0
        drop_score = score_from_components(dropped)["total"]
        drop_rows.append(
            {
                "term": term,
                "gamed_score": cmp["gamed"]["total"],
                "score_with_term_zeroed": drop_score,
                "marginal_on_gamed": round(cmp["gamed"]["total"] - drop_score, 6),
            }
        )
    drop_ranked = sorted(drop_rows, key=lambda r: (-r["marginal_on_gamed"], r["term"]))

    pop_good = abs(cmp["popularity_twin"]["total"] - cmp["genuine"]["total"]) < 1e-9
    gamed_raw = cmp["gamed"]["raw_components"]
    pop_bad_gamed = score_with_popularity_term({**gamed_raw, "downloads": 0})
    pop_bad_popular = score_with_popularity_term(
        {**cmp["genuine"]["raw_components"], "downloads": 9_000_000}
    )
    pop_mutant_fires = pop_bad_popular > pop_bad_gamed and not (
        abs(pop_bad_popular - pop_bad_gamed) < 1e-9
    )

    cheapest = [r["term"] for r in ranked if r["marginal_from_zero"] > 0]
    return {
        "probe": "probe2-per-term-sensitivity",
        "unit_id": "ADV-0067",
        "baseline_zero_score": baseline["total"],
        "independent_of_probe1_packages": True,
        "from_zero": ranked,
        "gamed_ablation": drop_ranked,
        "cheapest_terms_by_marginal": cheapest,
        "highest_marginal_term": ranked[0]["term"] if ranked else None,
        "gamed_highest_ablation_term": drop_ranked[0]["term"] if drop_ranked else None,
        "control_popularity_silent_on_good": {
            "pass": pop_good,
            "fired_on_bad_state": bool(pop_mutant_fires),
            "silent_on_good_state": pop_good,
            "good_genuine": cmp["genuine"]["total"],
            "good_popularity_twin": cmp["popularity_twin"]["total"],
            "mutant_popularity_twin": pop_bad_popular,
            "mutant_gamed": pop_bad_gamed,
        },
        "gamed_components": gamed_comp,
    }


CHEAP_RECIPES = {
    "conformance_pass_rate": (
        "Ship a named entrypoint file and parseable JSON stubs; the checker "
        "never executes the entrypoint."
    ),
    "test_presence": "Add tests/test_*.py; the checker counts files, not behaviour.",
    "test_pass_rate": "Fill those files with `assert True`; pass rate stays 1.0.",
    "documentation_completeness": (
        "Pad README.md past 800 bytes and add five markdown headings."
    ),
    "sbom_present": "Write sbom.json containing only {\"bomFormat\": \"CycloneDX\"}.",
    "provenance_present": "Write provenance.json containing only an in-toto type tag.",
    "advisory_cleanliness": "Ship advisories.json with an empty open list.",
    "declared_benchmarks": (
        "Declare three benchmark ids with no reproduction.executed field."
    ),
}


def target_verdicts(cmp: dict[str, Any], sens: dict[str, Any]) -> list[dict[str, Any]]:
    gamed_ge = cmp["gamed_matches_or_beats_genuine"]
    weaker = cmp["substance_gamed_weaker"]
    cheap = cmp["cheap_terms_gamed_beats_genuine"]
    pop = cmp["control_popularity_invariant"]["pass"]
    empty_ok = cmp["control_empty_lowest"]["pass"]
    no_tests_ok = cmp["control_no_tests_lower"]["pass"]
    docs_gamed = cmp["gamed"]["parts"]["documentation_completeness"]
    docs_gen = cmp["genuine"]["parts"]["documentation_completeness"]
    bench_delta = cmp["part_delta"]["declared_benchmarks"]["gamed_minus_genuine"]
    tests_trivial = cmp["gamed"]["substance"]["assert_trivial"] > 0 and cmp["gamed"]["substance"]["assert_nontrivial"] == 0
    sbom_small = cmp["gamed"]["substance"]["sbom_bytes"] < cmp["genuine"]["substance"]["sbom_bytes"]
    return [
        {
            "target_id": "trivial-tests-inflate-score",
            "verdict": "CONFIRMED" if tests_trivial and gamed_ge and weaker else "REFUTED",
            "summary": (
                "Gamed package uses only trivial asserts and still captures the "
                "full test_presence and test_pass_rate terms."
            ),
        },
        {
            "target_id": "padded-documentation-inflate-score",
            "verdict": "CONFIRMED" if docs_gamed >= docs_gen and weaker else "REFUTED",
            "summary": (
                "Byte/heading completeness lets padded README match genuine docs."
            ),
        },
        {
            "target_id": "unreproduced-benchmark-declarations",
            "verdict": "CONFIRMED" if bench_delta > 0 else "REFUTED",
            "summary": (
                "Declaring three unreproduced benchmarks raises declared_benchmarks "
                f"by {bench_delta} points over two reproduced genuine claims."
            ),
        },
        {
            "target_id": "fixture-heuristic-sbom-provenance",
            "verdict": "CONFIRMED" if sbom_small and gamed_ge else "REFUTED",
            "summary": (
                "Empty CycloneDX/in-toto stubs set sbom_present and provenance_present."
            ),
        },
        {
            "target_id": "genuine-scores-lower-than-gamed",
            "verdict": "CONFIRMED" if cmp["control_genuine_not_lower"]["inverted"] else "REFUTED",
            "summary": cmp["control_genuine_not_lower"]["summary"],
            "named_term": cmp["named_inversion_term"],
        },
        {
            "target_id": "popularity-changes-score",
            "verdict": "REFUTED" if pop else "CONFIRMED",
            "summary": (
                "A 9e6-download twin of the genuine package scores identically."
            ),
        },
        {
            "target_id": "empty-package-not-constant-high",
            "verdict": "CONFIRMED" if empty_ok else "REFUTED",
            "summary": "Empty fixture scores strictly below both populated packages.",
        },
        {
            "target_id": "no-tests-must-score-lower",
            "verdict": "CONFIRMED" if no_tests_ok else "REFUTED",
            "summary": "Zeroing test_presence on the genuine component vector lowers the score.",
        },
        {
            "target_id": "live-production-quality-score-module",
            "verdict": "CONFIRMED" if not production_module_present() else "REFUTED",
            "summary": (
                f"{PRODUCTION_MODULE} is absent; probes scored the reconstructed formula."
                if not production_module_present()
                else f"{PRODUCTION_MODULE} is present."
            ),
        },
        {
            "target_id": "declared-benchmarks-is-a-cheap-term",
            "verdict": "CONFIRMED" if "declared_benchmarks" in cheap or bench_delta > 0 else "REFUTED",
            "summary": (
                "Sensitivity and side-by-side parts name declared_benchmarks as "
                "cheap to max without reproduction."
            ),
            "sensitivity_top": sens.get("highest_marginal_term"),
            "gamed_ablation_top": sens.get("gamed_highest_ablation_term"),
        },
    ]


def run_controls(cmp: dict[str, Any], sens: dict[str, Any]) -> list[dict[str, Any]]:
    pop = sens["control_popularity_silent_on_good"]
    return [
        {
            "id": "NC-POPULARITY-TERM-MUTANT",
            "name": "Popularity must not change the real score; a mutant term must fire",
            "fired_on_bad_state": pop["fired_on_bad_state"],
            "silent_on_good_state": pop["silent_on_good_state"],
            "pass": bool(pop["fired_on_bad_state"] and pop["silent_on_good_state"]),
            "summary": (
                "Good formula: genuine == popularity twin. Mutant formula that "
                "adds a downloads bonus scores the twin higher."
            ),
        },
        {
            "id": "CTRL-GENUINE-NOT-LOWER",
            "name": "Genuinely good package must not score lower than the gamed one",
            "pass": cmp["control_genuine_not_lower"]["pass"],
            "fired_on_bad_state": cmp["control_genuine_not_lower"]["inverted"],
            "silent_on_good_state": cmp["control_genuine_not_lower"]["ordering_holds"],
            "named_term": cmp["named_inversion_term"],
            "summary": cmp["control_genuine_not_lower"]["summary"],
        },
        {
            "id": "CTRL-EMPTY-LOWEST",
            "name": "Empty package scores below genuine and gamed",
            "pass": cmp["control_empty_lowest"]["pass"],
            "fired_on_bad_state": True,
            "silent_on_good_state": cmp["control_empty_lowest"]["pass"],
            "summary": "Constant-high formula would fail this control.",
        },
        {
            "id": "CTRL-NO-TESTS-LOWER",
            "name": "Package with no tests scores strictly lower than identical with tests",
            "pass": cmp["control_no_tests_lower"]["pass"],
            "fired_on_bad_state": True,
            "silent_on_good_state": cmp["control_no_tests_lower"]["pass"],
            "summary": "IMP-0094 negative control on the reconstructed formula.",
        },
    ]
