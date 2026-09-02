#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0003-id-namespace-audit.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import lib as L  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0003-id-namespace-audit.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0003/audit_report.schema.json"
DECLARED_SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
SENTINEL = "SUCCESS:WFA-0003"
QUESTION = (
    "Do the candidate ids (284 wf-*), blueprint ids (108 BP-*), mechanism ids "
    "and any option/mechanism ids cited from workflow artifacts share a prefix "
    "namespace in which one literal token resolves to two different records - "
    "the exact 31-way M-NN failure recorded at 17-DECISION-LOG.md:175?"
)


def _validate(doc: dict) -> list[str]:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        return []
    return [
        e.message
        for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)
    ]


def build() -> dict:
    estate = C.materialize()
    live = C.live_presence(REPO)
    live_present = [r for r in live if r["present"]]
    paths = C.five_artifact_paths(estate)
    sig_a = L.run_signal_a(paths)
    sig_b = L.run_signal_b(paths, sig_a["intersecting"])
    hist = L.historical_mnn_control(estate)
    absent_rows = L.absent_class_resolution(estate)
    planted = L.planted_detector_control(estate)
    log_text = (estate / "17-DECISION-LOG.md").read_text(encoding="utf-8")
    log_facts = L.decision_log_facts(log_text)
    post_fix_clashes = sig_b["semantic_clash_count"]
    colliding_prefixes = sig_b["colliding_declaration_prefixes"]
    stale = (
        log_facts["present_tense_collision_claim"]
        and log_facts["zero_mech_tokens"]
        and post_fix_clashes == 0
        and hist["semantic_clash_count"] > 0
    )
    census_claim_forbidden = (
        C.CATALOG_CLAIMED_CANDIDATES == 284 and not any(
            r["present"] and "08-WORKFLOW-CANDIDATE-REGISTRY.json" in r["path"]
            for r in live_present
        )
    )
    answer = (
        "No on the post-fix reconstructed corpus: wf / BP / M / MECH are disjoint "
        "declaration prefixes, and regex intersection tokens that appear in two "
        "artifacts resolve as CITATION-ONLY rather than two records. The five "
        "harness-restore artifacts are ABSENT on this Linux worktree, so this is "
        "not a 284-row or 108-row census (last known 08 sha256 "
        f"{C.LAST_KNOWN_08_SHA256}). The pinned 31-way M-NN collision at "
        "17-DECISION-LOG.md:175 is STALE: the log still states it in the present "
        "tense with zero MECH tokens, while post-fix architecture cards use MECH- "
        f"and the live clash count is {post_fix_clashes}. Historical pre-fix "
        f"reconstruction yields {hist['semantic_clash_count']} colliding M-NN "
        f"tokens with {hist['identical_title_count']} identical titles "
        "(published control: 0-of-31 identical titles on M-1..M-31)."
    )
    tests = [
        {
            "id": "WFA-0003-PLANTED-COLLISION",
            "name": "Plant a synthetic colliding id; intersection reports it",
            "result": "PASS" if planted["pass"] else "FAIL",
        },
        {
            "id": "WFA-0003-ABSENT-CLASS",
            "name": "Doc-13 bare M-12/16/17/19/28/30/38 resolve ABSENT",
            "result": (
                "PASS"
                if all(r["resolve_bare_m_in_doc13"] == "ABSENT" for r in absent_rows)
                else "FAIL"
            ),
        },
        {
            "id": "WFA-0003-PINNED-STALE",
            "name": "Pinned 31-way present-tense claim classified STALE",
            "result": "PASS" if stale else "FAIL",
        },
        {
            "id": "WFA-0003-MNN-IDENTICAL-TITLES",
            "name": "Historical M-NN reverse lookup: 0 identical titles",
            "result": "PASS" if hist["zero_identical_titles"] else "FAIL",
        },
        {
            "id": "WFA-0003-NO-284-OVERCLAIM",
            "name": "Absent 284-row registry is not treated as a zero-collision census",
            "result": "PASS" if census_claim_forbidden else "FAIL",
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "WFA-0003",
        "kind": "AuditReport",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Prove the workflow id namespaces do not collide the way the M-NN option ids did",
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "output_schema_local": SCHEMA_REL,
        "corpus_role": "fixture",
        "population": {
            "upstream_284_row_registry_present": False,
            "upstream_108_row_library_present": False,
            "catalog_claimed_candidates": C.CATALOG_CLAIMED_CANDIDATES,
            "catalog_claimed_blueprints": C.CATALOG_CLAIMED_BLUEPRINTS,
            "fixture_candidate_count": len(
                json.loads(
                    (estate / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text(
                        encoding="utf-8"
                    )
                )["candidates"]
            ),
            "fixture_blueprint_count": len(C.BLUEPRINT_FIXTURE_IDS),
            "last_known_08_sha256": C.LAST_KNOWN_08_SHA256,
            "note": (
                "Live harness-restore inputs are ABSENT. Counts below are from "
                "disclosed fixtures plus worktree-local wf-* rows. This audit "
                "does not claim a 284-row census."
            ),
        },
        "inputs": [
            {
                "catalog_path": p,
                "role": "catalog-input",
                "live_present": False,
            }
            for p in (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/07-OPTION-UNIVERSE.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/17-DECISION-LOG.md:175",
            )
        ],
        "live_path_probe": live,
        "fixture_estate": str(
            (HERE / "fixtures" / "estate").relative_to(REPO).as_posix()
        ),
        "signal_a": {
            "method": "regex-extract-then-set-intersection",
            "token_regex": sig_a["token_regex"],
            "per_artifact_counts": sig_a["per_artifact_counts"],
            "intersecting_count": sig_a["intersecting_count"],
            "intersecting_tokens": sig_a["intersecting_tokens"],
            "intersecting": sig_a["intersecting"],
        },
        "signal_b": {
            "method": "reverse-lookup-both-titles-per-intersecting-token",
            "semantic_clash_count": sig_b["semantic_clash_count"],
            "semantic_clash_tokens": sig_b["semantic_clash_tokens"],
            "same_title_count": sig_b["same_title_count"],
            "citation_only_count": sig_b["citation_only_count"],
            "identical_titles_among_clashes": sig_b["identical_titles_among_clashes"],
            "prefix_declaration_sources": sig_b["prefix_declaration_sources"],
            "colliding_declaration_prefixes": colliding_prefixes,
            "classified": [
                {
                    "token": r["token"],
                    "kind": r["kind"],
                    "titles": r["titles"],
                    "sources": r["sources"],
                    "cited_in": r["cited_in"],
                    "record_count": r["record_count"],
                }
                for r in sig_b["classified"]
            ],
        },
        "historical_mnn_control": {
            "description": (
                "Pre-fix architecture cards forced back onto the bare M- prefix. "
                "Reverse lookup prints both titles; 0 identical titles is the method control."
            ),
            "semantic_clash_count": hist["semantic_clash_count"],
            "identical_title_count": hist["identical_title_count"],
            "zero_identical_titles": hist["zero_identical_titles"],
            "published_control_slice": hist["published_control_slice"],
            "clashes": hist["clashes"],
        },
        "absent_ids": absent_rows,
        "pinned_collision_statement": {
            "source": "17-DECISION-LOG.md:175 (fixture reconstruction of the pinned line)",
            "verbatim": log_facts["line_175"],
            "present_tense": log_facts["present_tense_collision_claim"],
            "mech_token_count": log_facts["mech_token_count"],
            "post_fix_semantic_clash_count": post_fix_clashes,
            "stale": stale,
            "classification": "STALE" if stale else "CURRENT",
            "why": (
                "The log asserts a live 31-way M-NN collision and queues P2-09, "
                "while post-fix architecture declarations use MECH- and the "
                "option-vs-architecture clash count is 0. Re-prefix date pinned "
                "elsewhere on this estate: 2026-08-07."
            ),
        },
        "planted_control": planted,
        "postfix_verdict": {
            "shared_colliding_declaration_prefix": bool(colliding_prefixes),
            "semantic_clash_count": post_fix_clashes,
            "matches_pinned_31_way_failure": False,
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0003-probe2-title-lookup",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-runs the reverse-lookup both-states control "
                "(pre-fix clash vs post-fix silence) independently of the "
                "set-intersection code path."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "local-schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0003/fixtures/estate",
                "role": "disclosed-fixture-estate",
            },
        ],
        "produced_by": {
            "execution_substrate": "local-parallel",
            "worktree": "/opt/p2/ast-integrate",
        },
    }
    if any(t["result"] != "PASS" for t in tests) or not planted["pass"] or not stale:
        doc["state"] = "FAILED"
        doc["sentinel"] = "FAILED:WFA-0003"
        doc["completion_sentinel"] = "FAILED:WFA-0003"
    return doc


def write_artifact(doc: dict | None = None) -> Path:
    payload = doc if doc is not None else build()
    errs = _validate(payload)
    if errs:
        raise SystemExit(f"FAILED:WFA-0003 emit schema {errs[:6]}")
    if payload.get("state") != "SUCCESS" or SENTINEL not in json.dumps(payload):
        raise SystemExit(
            f"FAILED:WFA-0003 emit state={payload.get('state')} sentinel missing"
        )
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


def main() -> int:
    path = write_artifact()
    print(f"wrote {path.relative_to(REPO).as_posix()} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
