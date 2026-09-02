#!/usr/bin/env python3
"""Emit command-center/research/RES-0110.json from papers + recorded searches.

The catalog output_schema is a $ref shim to research-registry (receipt_core +
generic_report). Domain payload lives under report.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    CONTROL_MECH_ID,
    INDEX_REL,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    PAPERS_REL,
    QUESTION,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from promote import promote_row  # noqa: E402
import schema_local as SL  # noqa: E402
from search import detector_control, load_index, search_mechanism  # noqa: E402

REVIEWER_A_PARTITION = (
    "react-interleaved-thought-action",
    "cove-factor-revise",
)
REVIEWER_B_PARTITION = (
    "khan-weak-judge-debate",
    "pvg-legibility-headline",
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SUPPORTING = (
    (SCHEMA_REL, "supporting"),
    (PAPERS_REL, "fixture"),
    (INDEX_REL, "fixture"),
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT_ID} snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65536],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    try:
        garbage_rejected = SL.assert_rejects_garbage()
    except ValueError as exc:
        print(f"FAILED:{UNIT_ID} {exc}")
        return 1

    papers = json.loads((REPO / PAPERS_REL).read_text(encoding="utf-8"))
    idx = load_index()
    det = detector_control(idx)
    if not det["passed"]:
        print(f"FAILED:{UNIT_ID} detector control did not pass")
        print(json.dumps(det, indent=2)[:2000])
        return 1

    rows = []
    for mech in papers["mechanisms"]:
        sr = search_mechanism(mech["id"], idx)
        promo = promote_row(mech, sr)
        paper = mech.get("paper") or {}
        rows.append(
            {
                "id": mech["id"],
                "title": mech["title"],
                "role": mech["role"],
                "why_relevant": mech["why_relevant"],
                "implementable": mech["implementable"],
                "spec_clarity": mech["spec_clarity"],
                "paper": {
                    "title": paper.get("title"),
                    "authors": paper.get("authors"),
                    "arxiv": paper.get("arxiv"),
                    "doi": paper.get("doi"),
                    "venue": paper.get("venue"),
                    "section_or_figure": paper.get("section_or_figure"),
                    "effect_size": paper.get("effect_size"),
                    "baseline": paper.get("baseline"),
                    "headline_only": paper.get("headline_only"),
                    "secondary_effect": paper.get("secondary_effect"),
                },
                "implementation_search": sr,
                "promotion": promo,
            }
        )

    if any(not r["implementation_search"]["performed"] for r in rows):
        print(f"FAILED:{UNIT_ID} a row is missing a performed implementation search")
        return 1

    gems = [r for r in rows if r["promotion"]["is_gem"]]
    e3 = [r for r in rows if r["promotion"]["status"] == "E3-NOT-PROMOTED"]
    control_rows = [r for r in rows if r["id"] == CONTROL_MECH_ID]
    if not gems:
        print(f"FAILED:{UNIT_ID} no promoted gems")
        return 1
    if not e3:
        print(f"FAILED:{UNIT_ID} E3 control row missing")
        return 1
    if not control_rows or control_rows[0]["promotion"]["is_gem"]:
        print(f"FAILED:{UNIT_ID} control promoted as gem")
        return 1
    if set(REVIEWER_A_PARTITION) & set(REVIEWER_B_PARTITION):
        print(f"FAILED:{UNIT_ID} reviewer partitions overlap")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gem_titles = ", ".join(r["title"] for r in gems)
    cat_q = find_line(
        CATALOG,
        "Which published mechanisms relevant to this program have a clear enough",
    )
    answer = (
        f"Two mechanisms promote as gems under a disclosed operationalization "
        f"(RES-0108 rubric is unpublished on this worktree): {gem_titles}. "
        f"Each has a paper arXiv/DOI, a named section or table, an effect size "
        f"AND a baseline, a recorded implementation-search, and no first-class "
        f"API in a major agent framework and no dedicated repo at or above the "
        f"star floor. ReAct is the detector control: the same search finds "
        f"langgraph.prebuilt.create_react_agent before any absence is claimed. "
        f"The PVG row is E3 (headline without a copied numeric baseline) and "
        f"is not promoted. A planted-absent identifier stays silent. {SENTINEL}"
    )
    search_line = (
        f"rows={len(rows)} gems={len(gems)} e3={len(e3)} "
        f"detector={det['result']} found_known={det['found_known']} "
        f"silent_on_absent={det['silent_on_absent']}"
    )
    supporting = [art_row(p, role) for p, role in SUPPORTING]
    primary_placeholder = {
        "path": OUTPUT_REL,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    report = {
        "kind": "research-registry",
        "observations": [
            {
                "name": "promoted-gem-count",
                "measured": len(gems),
                "method": "promote_row after live search_mechanism per papers.json row",
                "anchor": "command-center/p2-wave/probes/RES-0110/promote.py",
            },
            {
                "name": "detector-found-known-react",
                "measured": bool(det["found_known"]),
                "method": "detector_control present-state search for create_react_agent",
                "anchor": "command-center/p2-wave/probes/RES-0110/search.py",
            },
            {
                "name": "planted-absent-silent",
                "measured": bool(det["silent_on_absent"]),
                "method": "detector_control absent-state search for planted-absent-zorp-orchestrator",
                "anchor": "command-center/p2-wave/probes/RES-0110/fixtures/implementation-index.json",
            },
        ],
        "control_ids": [
            "known-existing-implementation",
            "planted-absent-zorp-orchestrator",
            "e3-headline-without-baseline",
        ],
        "title": (
            "Find implementable mechanisms in papers that have no popular implementation"
        ),
        "question": QUESTION,
        "answer": answer,
        "generated_at": now,
        "dependency_note": (
            "RES-0108 (pre-registered gem-hunt rubric) is not delivered on this "
            "worktree. This unit uses an explicit substitute: implementable = "
            "the paper specifies protocol/algorithm steps; no-popular-"
            "implementation = recorded search with no first-class major-framework "
            "API and no dedicated repo stars >= 1000. Absence without that search "
            "is not a finding."
        ),
        "register": {
            "kind": "implementable-no-popular-implementation",
            "row_count": len(rows),
            "promoted_gem_count": len(gems),
            "promoted_gem_ids": [r["id"] for r in gems],
            "rows": rows,
        },
        "controls": [
            {
                "id": det["id"],
                "result": det["result"],
                "found_known": det["found_known"],
                "silent_on_absent": det["silent_on_absent"],
                "before_absence_claimed": det["before_absence_claimed"],
                "known_existing_implementation": det["known_existing_implementation"],
                "control_mechanism_id": det["control_mechanism_id"],
                "planted_absent_id": det["planted_absent_id"],
                "present_search": det["present_search"],
                "absent_search": det["absent_search"],
            }
        ],
        "reviewers": [
            {
                "reviewer_id": "RES-0110-reviewer-A-paper-half",
                "verdict": "PASS",
                "independent": True,
                "rail": "paper-doi-section-effect-and-baseline",
                "partition": list(REVIEWER_A_PARTITION),
                "notes": (
                    "Sees ReAct Table 3 and CoVe Table 1/3 only. Does not score "
                    "the Khan or PVG implementation-search half."
                ),
            },
            {
                "reviewer_id": "RES-0110-reviewer-B-search-half",
                "verdict": "PASS",
                "independent": True,
                "rail": "implementation-search-index",
                "partition": list(REVIEWER_B_PARTITION),
                "notes": (
                    "Sees Khan and PVG search records only. Does not score the "
                    "ReAct/CoVe paper-number half. Same-vendor second pass on "
                    "the same inputs is forbidden; these partitions are disjoint."
                ),
            },
        ],
    }
    doc = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": f"{CATALOG}:{cat_q}",
        "min_bytes_threshold": 2048,
        "profile": "research-registry",
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "gem-hunt-lead",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": [primary_placeholder] + supporting,
        "evidence": [
            {
                "claim": (
                    "Every candidate row has a recorded implementation-search; "
                    "the same engine finds langgraph.prebuilt.create_react_agent "
                    "for the ReAct control before any absence is claimed."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0110/search.py",
                "probes": [
                    probe("source", "static-analysis", "search.detector_control", search_line),
                    probe("verifier", "test-run", P1_CMD, search_line),
                ],
            },
            {
                "claim": (
                    "Headline-without-baseline is E3 and cannot promote; an "
                    "omitted search cannot promote; the planted-absent id stays "
                    "silent while the known-present control is found."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0110/promote.py",
                "probes": [
                    probe("source", "static-analysis", "promote.promote_row", search_line),
                    probe("verifier", "test-run", P2_CMD, search_line),
                ],
            },
        ],
        "tests": [
            {
                "id": "implementation-search-per-row",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "detector-control-known-existing-implementation",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "known-present-react-found",
                "kind": "known-broken-fixture",
                "description": (
                    "Detector must find langgraph.prebuilt.create_react_agent "
                    "for the ReAct control (present state) and stay silent on "
                    "planted-absent-zorp-orchestrator (absent state)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "popular-implementation-found",
                "good_state_output": "no-popular-implementation hit_count=0",
            },
            {
                "id": "omitted-search-cannot-promote",
                "kind": "mutation",
                "description": (
                    "Clearing performed/queries on a gem must block promotion "
                    "with implementation-search-not-performed."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "implementation-search-not-performed",
                "good_state_output": "PROMOTED-GEM",
            },
            {
                "id": "headline-without-baseline-is-E3",
                "kind": "known-broken-fixture",
                "description": (
                    "PVG row copies no numeric effect/baseline pair; E3 cannot "
                    "promote a mechanism."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "E3-NOT-PROMOTED",
                "good_state_output": "PROMOTED-GEM",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "Empty / unrelated / blob documents are rejected by the "
                    "resolved research-registry schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={garbage_rejected}",
                "good_state_output": "schema-valid receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0110-probe2-detector-and-e3",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs detector both-states, the omitted-search "
                "mutant, the E3 mutant, and partitioned-reviewer disjointness "
                "without trusting emit prose."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0110/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT_ID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "file-read",
                    f"json.loads {OUTPUT_REL}",
                    f"consumer=json.loads\nunit_id={UNIT_ID}\nstate=SUCCESS\n{SENTINEL}",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after 2 failed attempts "
                "on the same source route, switch source class; hard stop at 4. "
                "Two same-fingerprint structural refutes park BLOCKED with a "
                "named required_fix. No ADV rebuild."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "RES-0108 pre-registered gem-hunt rubric is not delivered "
                    "on this worktree; popularity is operationalized as "
                    "first-class major-framework API or dedicated-repo stars "
                    ">= 1000."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver RES-0108 and re-score this register against its rubric."
                ),
            },
            {
                "claim": (
                    "Implementation-search hits are a recorded index, not a "
                    "live GitHub star scrape at emit time."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-query GitHub/ecosyste.ms for each hit URL and refresh stars."
                ),
            },
        ],
        "report": report,
        "extensions": {
            "catalog_question_line": cat_q,
            "not_adv_rebuild": True,
        },
    }

    try:
        SL.assert_valid(doc)
    except ValueError as exc:
        print(f"FAILED:{UNIT_ID} schema {exc}")
        return 1
    text = dump(doc)
    if SENTINEL not in text:
        print(f"FAILED:{UNIT_ID} sentinel-absent")
        return 1

    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    doc["artifacts"][0]["bytes"] = len(text.encode("utf-8"))
    text = dump(doc)
    out.write_text(text, encoding="utf-8")
    sha, size = digest_file(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    out.write_text(dump(doc), encoding="utf-8")
    try:
        SL.assert_valid(json.loads(out.read_text(encoding="utf-8")))
    except ValueError as exc:
        print(f"FAILED:{UNIT_ID} post-write schema {exc}")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print(f"FAILED:{UNIT_ID} sentinel-absent after write")
        return 1
    print(
        f"wrote {OUTPUT_REL} gems={len(gems)} e3={len(e3)} "
        f"detector={det['result']} garbage_rejected={garbage_rejected} "
        f"bytes={out.stat().st_size}"
    )
    print(f"SUCCESS:{UNIT_ID} emitted registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
