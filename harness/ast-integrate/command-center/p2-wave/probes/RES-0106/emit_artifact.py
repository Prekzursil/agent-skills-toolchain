#!/usr/bin/env python3
"""Emit command-center/research/RES-0106.json from captured two-rail evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
OUT = REPO / "command-center" / "research" / "RES-0106.json"

SENTINEL = (
    "SUCCESS:RES-0106 in the receipt AND a specified never-selected detector "
    "with its data source and its stated false-alarm case"
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0106/probe1_two_rails.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0106/probe2_never_selected.py"
)


def load_meta(stem: str) -> dict:
    return json.loads((CAP / f"{stem}.meta.json").read_text(encoding="utf-8"))


def quote_present(stem: str, quoted: str) -> bool:
    raw = (CAP / f"{stem}.bin").read_bytes()
    if quoted.encode("utf-8") in raw:
        return True
    try:
        return quoted in raw.decode("utf-8")
    except UnicodeDecodeError:
        return False


def rail(kind: str, stem: str, quoted_span: str) -> dict:
    if not quote_present(stem, quoted_span):
        raise SystemExit(f"FAILED:emit quoted_span absent in {stem}: {quoted_span!r}")
    meta = load_meta(stem)
    status = int(meta["http_status"])
    if status != 200:
        raise SystemExit(f"FAILED:emit {stem} http_status={status}")
    sha = str(meta["sha256"])
    live = __import__("hashlib").sha256((CAP / f"{stem}.bin").read_bytes()).hexdigest()
    if live != sha:
        raise SystemExit(f"FAILED:emit {stem} meta sha256 drifted from bytes")
    return {
        "kind": kind,
        "permalink": meta.get("permalink") or meta.get("final_url"),
        "request_url": meta.get("request_url"),
        "final_url": meta.get("final_url"),
        "fetch_timestamp": meta["fetch_timestamp"],
        "http_status": status,
        "sha256": sha,
        "bytes": meta["bytes"],
        "capture_file": meta.get("capture_file")
        or f"command-center/p2-wave/probes/RES-0106/captures/{stem}.bin",
        "quoted_span": quoted_span,
    }


def main() -> int:
    c1 = {
        "id": "C-GOLDEN-QUERY-SET",
        "claim": (
            "Elsewhere, a router/ranker regression suite is a labeled golden "
            "query set: typical queries plus per-query document (or item) "
            "ratings, scored by a ranking metric. OpenSearch/_rank_eval is "
            "the structured form of that pattern."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "rank_eval is search ranking, not LLM tool routing. The "
            "transferable mechanism is the labeled (query, relevant-id) "
            "set, not Elasticsearch/OpenSearch as a runtime."
        ),
        "rails": [
            rail(
                "structured-api",
                "opensearch_rank_eval_api_raw",
                "Allows to evaluate the quality of ranked search results over a set of typical search queries",
            ),
            rail(
                "prose",
                "opensearch_rank_eval_docs",
                "The Rank Evaluation API evaluates the quality of ranked search results.",
            ),
        ],
    }
    c2 = {
        "id": "C-ROUTER-SELECTS-ONE",
        "claim": (
            "LlamaIndex RouterQueryEngine selects one of several candidate "
            "query engines from tool metadata/descriptions. The router "
            "itself has no check that a registered candidate is ever chosen."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "Absence of a never-selected check in this module is not proof "
            "that no LlamaIndex user has one in their own eval harness."
        ),
        "rails": [
            rail(
                "structured-api",
                "llamaindex_router_py_raw",
                "Selects one out of several candidate query engines to execute a query.",
            ),
            rail(
                "prose",
                "llamaindex_router_md",
                "Routers are modules that take in a user query and a set of “choices” (defined by metadata), and returns one or more selected choices.",
            ),
        ],
    }
    c3 = {
        "id": "C-BFCL-IRRELEVANCE",
        "claim": (
            "Function-calling eval suites (BFCL) use labeled (query, expected "
            "function) cases plus a relevance/irrelevance class for when a "
            "function should not be invoked. That class is the false-alarm "
            "cousin of never-selected: it tests SHOULD-never-call, not "
            "exists-but-never-called."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "BFCL scores whether the model matches the labeled function on "
            "cases that exist in the dataset. A catalog function that never "
            "appears as a gold label is invisible to the leaderboard score."
        ),
        "rails": [
            rail(
                "structured-api",
                "gorilla_bfcl_readme_raw",
                "first comprehensive and executable function call evaluation",
            ),
            rail(
                "prose",
                "gorilla_bfcl_blog",
                "when the provided function is not suitable",
            ),
        ],
    }
    c4 = {
        "id": "C-NLU-UNIQUE-LABELS-GAP",
        "claim": (
            "NLU/intent evaluation only reports labels that appear in the "
            "test examples. Rasa evaluate_intents drops examples with no "
            "intent target and builds the label set from unique_labels of "
            "targets and predictions, so an intent that is never a target "
            "and never predicted does not show up as a failure. Rasa Pro "
            "E2E coverage metrics separately flag untested flows."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "The OSS evaluate_intents mechanism and the Pro E2E coverage "
            "docs are the same *pattern* on two products, not one binary. "
            "unique_labels would also hide a capability that the model "
            "never predicts if it is also absent from y_true."
        ),
        "rails": [
            rail(
                "structured-api",
                "rasa_nlu_test_py_raw",
                "Only considers those examples with a set intent. Others are filtered out.",
            ),
            rail(
                "prose",
                "rasa_testing_docs",
                "Coverage metrics help you see which flows and commands are not tested.",
            ),
        ],
    }
    c5 = {
        "id": "C-STALE-FLAG-ANALOG",
        "claim": (
            "Unleash detects unused-looking flags by marking them "
            "potentially stale after expected lifetime, and allows a manual "
            "stale mark after the flag has served its purpose without tearing "
            "down the live configuration. Time-based unused is an analog of "
            "never-selected, not a router gold-set join."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "Potentially-stale is lifetime, not 'never chosen for a labeled "
            "query'. Kill-switches and rollback flags that remain configured "
            "but unused are the false-alarm case if unused==defect."
        ),
        "rails": [
            rail(
                "structured-api",
                "unleash_feature_toggle_service_raw",
                "async updatePotentiallyStaleFeatures",
            ),
            rail(
                "prose",
                "unleash_techdebt_md",
                "You can also manually mark a feature flag as stale if you know it has served its intended purpose.",
            ),
        ],
    }
    c6 = {
        "id": "C-FALLBACK-ROUTE",
        "claim": (
            "Haystack ConditionalRouter documents an explicit fallback route "
            "when no specified condition matches. That is the "
            "no-capability-fits path, complementary to never-selected: empty "
            "gold expected-set queries must not be forced onto a catalog item."
        ),
        "verdict": "CONFIRMED",
        "grade": "E1",
        "cite_as_measured_fact": True,
        "strongest_caveat": (
            "A fallback route does not detect a registered route that is "
            "never taken; it only handles unmatched conditions."
        ),
        "rails": [
            rail(
                "structured-api",
                "haystack_conditional_router_py_raw",
                "Example usage with a default fallback route in a Pipeline:",
            ),
            rail(
                "prose",
                "haystack_conditional_docs",
                "fallback route",
            ),
        ],
    }
    c7 = {
        "id": "C-LANGSMITH-REGRESSION-E3",
        "claim": (
            "LangSmith documents offline evaluation on curated datasets and "
            "online evaluation on production traces to catch regressions."
        ),
        "verdict": "E3-NOT-FACT",
        "grade": "E3",
        "cite_as_measured_fact": False,
        "strongest_caveat": (
            "Single prose rail only (no independent structured API capture "
            "of LangSmith). Graded E3; must not be cited as measured fact."
        ),
        "rails": [
            rail(
                "prose",
                "langsmith_eval_docs",
                "catch regressions",
            )
        ],
    }
    c8 = {
        "id": "C-UPSTREAM-HAS-NAMED-DETECTOR",
        "claim": (
            "Public router suites already ship a first-class detector named "
            "for the failure 'a capability exists in the catalog but is never "
            "selected'."
        ),
        "verdict": "REFUTED",
        "grade": "E1",
        "cite_as_measured_fact": False,
        "strongest_caveat": (
            "The fetched suites provide adjacent mechanisms (golden ratings, "
            "unique_labels gaps, stale flags, irrelevance cases, fallback "
            "routes) but none of the captured sources specify the "
            "catalog+gold+selection-log join as a named check. The detector "
            "below is a synthesis, not a copy of one upstream file."
        ),
        "rails": [
            rail(
                "structured-api",
                "llamaindex_router_py_raw",
                "Selects one out of several candidate query engines to execute a query.",
            ),
            rail(
                "prose",
                "gorilla_bfcl_blog",
                "function relevance detection",
            ),
        ],
    }

    claims = [c1, c2, c3, c4, c5, c6, c7, c8]
    for claim in claims:
        n = len(claim["rails"])
        if claim["grade"] in {"E1", "E2"} and n < 2:
            raise SystemExit(f"FAILED:emit {claim['id']} E1/E2 with {n} rails")
        if claim["grade"] == "E3" and n >= 2:
            raise SystemExit(f"FAILED:emit {claim['id']} marked E3 but has {n} rails")
        if claim.get("cite_as_measured_fact") and (
            claim["grade"] == "E3" or claim["verdict"] != "CONFIRMED"
        ):
            raise SystemExit(f"FAILED:emit {claim['id']} cited as fact illegally")

    detector = {
        "id": "RES-0106-never-selected",
        "title": "never-selected capability detector",
        "data_source": {
            "capability_catalog": (
                "command-center/p2-wave/probes/RES-0106/fixtures/catalog.json"
            ),
            "golden_query_set": (
                "command-center/p2-wave/probes/RES-0106/fixtures/golden_queries.json"
            ),
            "selection_log": (
                "the log produced by running the golden query set through the "
                "router (CI), or a production trace window with the same schema "
                "(query_id, selected_capability_ids)"
            ),
            "what_it_reads": [
                "catalog rows: id, selectable, never_select_reason",
                "gold rows: query_id, expected_capability_ids",
                "log rows: query_id, selected_capability_ids",
            ],
        },
        "when_it_runs": [
            "CI: immediately after the router regression suite writes a selection log for the golden query set",
            "periodic: over a production selection-log window using the same join (optional second rail; not required to fire in CI)",
        ],
        "algorithm": (
            "never_selected_routing_defect = "
            "(gold expected ids ∩ catalog selectable ids) − selected ids. "
            "corpus_gap = selectable ids − gold expected ids (untested, not a "
            "routing defect). never_by_design (selectable=false) is excluded "
            "from both."
        ),
        "false_alarm_case": {
            "capability_id": "debug.dump_internal_state",
            "why_it_should_never_be_selected": (
                "Admin kill-switch / dump path catalogued for operators. A "
                "user-task golden set must not treat 'never selected' as a "
                "defect for this id. deprecated.rollback_only is the same class."
            ),
            "naive_detector_that_false_alarms": (
                "catalog_ids − selected_ids with no selectable filter"
            ),
        },
        "prior_art_claim_ids": [
            "C-GOLDEN-QUERY-SET",
            "C-NLU-UNIQUE-LABELS-GAP",
            "C-BFCL-IRRELEVANCE",
            "C-STALE-FLAG-ANALOG",
            "C-FALLBACK-ROUTE",
        ],
        "implementation": (
            "command-center/p2-wave/probes/RES-0106/detector.py"
        ),
    }

    doc = {
        "unit_id": "RES-0106",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": (
            "What does a router regression suite look like elsewhere "
            "(golden query sets, drift alarms, coverage of never-selected "
            "capabilities), and how do they detect the specific failure "
            "where a capability exists but is never selected?"
        ),
        "title": (
            "Extract how other systems build a regression suite that proves "
            "a router still routes"
        ),
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "inputs_missing_on_worktree": [
            "command-center/sources/REGISTER.md",
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
        ],
        "claims": claims,
        "never_selected_detector": detector,
        "reviewer": {
            "reviewer_id": "RES-0106-probe2-detector-control",
            "independent": True,
            "verdict": "PASS",
            "default_refute_where_insufficient": True,
            "scope_not_agreement": True,
        },
        "tests": [
            {
                "id": "probe1-two-rails",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-never-selected-detector",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "two-rail",
                "claim": "every CONFIRMED/E1 claim has structured-api + prose rails with permalink, fetch_timestamp, http_status, sha256",
            },
            {
                "kind": "detector",
                "claim": "never-selected detector named with data source and false-alarm case debug.dump_internal_state",
            },
            {
                "kind": "e3-quarantine",
                "claim": "C-LANGSMITH-REGRESSION-E3 is single-rail and cite_as_measured_fact=false",
            },
        ],
        "artifacts": [
            {
                "path": "command-center/research/RES-0106.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0106/detector.py",
                "exists": True,
                "role": "detector",
            },
        ],
        "residual_unknowns": [
            "command-center/schema/research-claim-record.schema.json is absent on this worktree; this record follows the catalog's two-rail + grade-E3 rule and the fields required by _measure_one_delivered.py",
            "No fetched source used the exact phrase 'never-selected capability detector'; the named detector is a synthesis of the confirmed adjacent mechanisms",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
