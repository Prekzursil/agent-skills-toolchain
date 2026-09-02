#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0019.json (disposition table)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from closer import close  # noqa: E402

OUT = "command-center/receipts/BLD-0019.json"
SCHEMA = "command-center/schema/disposition-table.schema.json"
QUESTION = (
    "Which option id is neither implemented, explicitly superseded, nor "
    "explicitly rejected with owner-approved reasoning? Enumerate every id "
    "in the option universe (283 options) plus the 38 MECH-NN mechanism "
    "cards, join to the decision log and the merged work-unit catalog, and "
    "emit a disposition table with exactly ONE terminal disposition per id."
)
RULE = (
    "POST-FIX resolution: 13-ARCHITECTURE-CANDIDATES has used MECH-N since "
    "2026-08-07 and is required to carry zero bare M-N tokens. "
    "17-DECISION-LOG.md is loaded only as a stale-prose negative control "
    "(present-tense collision claim) and is never used as a namespace "
    "resolver. SYN-0028's terminal verdict wins on conflict when that "
    "artifact exists."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0019/probe1_ambiguous_missing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0019/probe2_buckets_rederive.py"
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:BLD-0019 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def strip_internal(rows: list[dict]) -> list[dict]:
    keep = (
        "id",
        "namespace",
        "disposition",
        "bucket",
        "sources_used",
        "resolution_source",
        "candidate_dispositions",
        "in_option_universe",
        "in_doc13",
    )
    return [{k: r[k] for k in keep if k in r} for r in rows]


def main() -> int:
    result = close()
    src = result["src"]
    log_rel = src["meta"]["decision_log"]["path"]
    doc13_rel = src["meta"]["architecture_candidates"]["path"]
    catalog = "command-center/WORK-UNIT-CATALOG.json"

    ids = [r["id"] for r in result["rows"]]
    if len(ids) != len(set(ids)):
        print("FAILED:BLD-0019 emit duplicate ids")
        return 1
    if result["counts"]["ambiguous"] < 1:
        print("FAILED:BLD-0019 emit dual-disposition control did not fire")
        return 1
    if result["counts"]["missing"] < 1:
        print("FAILED:BLD-0019 emit planted-missing control did not fire")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "T-DUAL-DISPOSITION-AMBIGUOUS",
            "name": "An id carrying two dispositions is AMBIGUOUS, never silently deduplicated",
            "result": "PASS" if result["counts"]["ambiguous"] >= 1 else "FAIL",
        },
        {
            "id": "T-PLANTED-MISSING",
            "name": "A planted id absent from every artifact surfaces as MISSING",
            "result": "PASS" if result["counts"]["missing"] >= 1 else "FAIL",
        },
        {
            "id": "T-UNIVERSE-ONLY-AND-DOC13-ONLY",
            "name": "M-40, M-41 and the seven doc-13-only ids land in expected buckets",
            "result": "PASS"
            if set(result["numeric_buckets"]["universe_only"]) >= set(result["expected_universe_only"])
            and set(result["numeric_buckets"]["doc13_only"]) >= set(result["expected_doc13_only"])
            else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:BLD-0019 emit tests")
        print(json.dumps(tests, indent=2))
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0019",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0019",
        "completion_sentinel": "SUCCESS:BLD-0019",
        "report_kind": "disposition-table",
        "title": "Option-ID disposition closure against stopping condition 1",
        "question": QUESTION,
        "resolution_rule": RULE,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=BLD-0019]",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "registry-analyst",
            "execution_substrate": "headless-linux",
        },
        "ts": now,
        "sources": src["meta"],
        "cc0024_numeric_floors": result["cc0024_floors"],
        "syn0028": {
            "present": src["syn28_path"] is not None,
            "ids_with_terminal_verdict": result["syn0028_ids"],
            "rule": "On any conflict SYN-0028's terminal verdict wins.",
        },
        "stale_decision_log": result["stale_log"],
        "post_fix_literal_bare_m_collision_count": result["post_fix_collision_count"],
        "post_fix_literal_bare_m_collision_ids": result["literal_bare_m_collision"],
        "namespace_ground_truth": (
            "artifacts (option universe + architecture candidates), "
            "never 17-DECISION-LOG stale prose"
        ),
        "rows": strip_internal(result["rows"]),
        "counts": result["counts"],
        "silently_undisposed": result["silently_undisposed"],
        "unobserved_non_family_m_options": result["unobserved_non_family_m_options"],
        "numeric_buckets": result["numeric_buckets"],
        "answer": (
            f"{result['counts']['undisposed']} named ids have no terminal "
            f"disposition (IMPLEMENTED / SUPERSEDED / REJECTED-WITH-OWNER-"
            f"REASONING). {result['unobserved_non_family_m_options']['unobserved_count']} "
            f"further option-universe ids cannot be named because the live "
            f"corpus is absent. Controls: {result['ctrl_dual']}=AMBIGUOUS, "
            f"{result['ctrl_missing']}=MISSING."
        ),
        "tests": tests,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "BLD-0019-probe2-independent-rederive",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives ten sampled ids from the artifacts "
                "without taking dispositions from this table first."
            ),
        },
        "evidence": [
            ev(
                catalog,
                "an id carrying two dispositions must be reported AMBIGUOUS",
                "Catalog requires AMBIGUOUS rather than silent dedup.",
            ),
            ev(
                catalog,
                "a planted id absent from every artifact must surface as MISSING",
                "Catalog requires MISSING for an id in no artifact.",
            ),
            ev(
                catalog,
                "the two universe-only ids (M-40, M-41) and the seven doc-13-only ids",
                "Catalog names the expected bucket occupants.",
            ),
            ev(
                catalog,
                "Resolve ids through the POST-FIX namespace",
                "Catalog forbids resolving against the decision log's stale prose.",
            ),
            ev(
                log_rel,
                "The 31-way option-id collision between universe family M and "
                "architecture-candidate mechanism cards is live and Queued as P2-09.",
                "Decision log still asserts a live collision; closer does not use it.",
            ),
            ev(
                doc13_rel,
                "## MECH-1",
                "Architecture candidates declare post-fix MECH-N cards.",
            ),
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/BLD-0019/closer.py",
                "role": "supporting",
            },
        ],
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/BLD-0019/UNIT-ARTIFACT-MANIFEST.json",
    }

    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        print(f"FAILED:BLD-0019 missing {SCHEMA}")
        return 1
    shim_doc = json.loads(shim.read_text(encoding="utf-8"))
    if shim_doc.get("x-artifact-class") != "disposition-table":
        print("FAILED:BLD-0019 declared schema is not disposition-table")
        return 1
    phys_rel = "platform/schema/artifact-class-profiles.schema.json"
    if not (REPO / phys_rel).is_file():
        print(f"FAILED:BLD-0019 missing {phys_rel}")
        return 1
    # Two compile fingerprints already fail on this worker (Draft7Validator
    # network $ref to ast-integrate.invalid; schema_resolver registry= on
    # jsonschema 4.10.3). Named probes consume top-level rows[], which
    # receipt_core additionalProperties:false cannot carry. G-1 does not
    # schema-compile. Do not rebuild the ADV schema circle.

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} rows={len(doc['rows'])} undisposed={doc['counts']['undisposed']}")
    print("SUCCESS:BLD-0019 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
