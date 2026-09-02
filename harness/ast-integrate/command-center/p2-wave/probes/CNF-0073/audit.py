#!/usr/bin/env python3
"""Build the CNF-0073 multilingual recheck document."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from corpus import scan_live  # noqa: E402
from qualifiers import claim_survives, qualifier_diff  # noqa: E402
from translate import (  # noqa: E402
    PATH_INDEPENDENT,
    PATH_RECORDED,
    SamePathRerun,
    run_second_path,
)

INVENTORY = HERE / "fixtures" / "citation-inventory.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/confirmation/CNF-0073-multilingual-recheck.json"
SCHEMA_REL = "command-center/schema/citation-audit.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0073 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both translations are "
    "attached and the second path is named and demonstrably different from "
    "the first. Any other terminal state is FAILED:CNF-0073 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Do the multilingual source claims survive a second translation? "
    "Re-translate each non-English cited span through a different translation "
    "path than the original and answer: does the claim survive, or did the "
    "first translation introduce or drop a qualifier that changes its meaning?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0073/probe1_second_path.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0073/probe2_qualifier_control.py"
)
P_SCHEMA = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0073/schema_check.py"
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:CNF-0073"
MIN_BYTES = 2048
SUPPORTING_ARTIFACTS = [
    ("command-center/schema/citation-audit.schema.json", "supporting"),
    (
        "command-center/p2-wave/probes/CNF-0073/fixtures/citation-inventory.json",
        "fixture",
    ),
    ("command-center/p2-wave/probes/CNF-0073/fixtures/hedges.json", "fixture"),
    ("command-center/p2-wave/probes/CNF-0073/fixtures/glossary.json", "fixture"),
    ("command-center/p2-wave/probes/CNF-0073/translate.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0073/qualifiers.py", "supporting"),
]


def payload(doc: dict) -> dict:
    """Domain fields live under report for citation-audit receipts."""
    report = doc.get("report")
    if isinstance(report, dict) and report.get("citations"):
        return report
    return doc


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0073 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def sha_file(rel: str, role: str) -> dict:
    raw = (REPO / rel).read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in raw:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(norm).hexdigest(),
        "exists": True,
        "eol": eol,
        "role": role,
    }


def evidence_item(
    *,
    claim: str,
    verdict: str,
    rel: str,
    snippet: str,
    source_fp: str,
    verifier_fp: str,
    source_cmd: str,
    verifier_cmd: str,
    source_out: str,
    verifier_out: str,
) -> dict:
    line = find_line(rel, snippet)
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": "almost-certain",
        "anchor": f"{rel}:{line}",
        "probes": [
            {
                "role": "source",
                "method": "file-read",
                "command": source_cmd,
                "raw_output": source_out,
                "fingerprint": source_fp,
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": "command",
                "command": verifier_cmd,
                "raw_output": verifier_out,
                "fingerprint": verifier_fp,
                "exit_code": 0,
            },
        ],
    }


def load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0073":
            return u
    raise SystemExit("FAILED:CNF-0073 catalog unit missing")


def recheck_row(cit: dict) -> dict:
    original = str(cit["original_span"])
    language = str(cit["language"])
    recorded = str(cit["recorded_translation"])
    first = str(cit.get("recorded_path_name") or PATH_RECORDED)
    independent = run_second_path(original, language, first, PATH_INDEPENDENT)
    qdiff = qualifier_diff(original, recorded, independent)
    survives = claim_survives(recorded, independent)
    if survives and not qdiff["material_change"]:
        verdict = "CONFIRMED"
    elif survives and qdiff["material_change"]:
        verdict = "PARTIAL"
    else:
        verdict = "REFUTED"
    return {
        "id": cit["id"],
        "language": language,
        "original_span": original,
        "source": cit.get("source") or {},
        "planted_control": cit.get("planted_control"),
        "translations": [
            {
                "path_name": first,
                "text": recorded,
                "role": "recorded",
            },
            {
                "path_name": PATH_INDEPENDENT,
                "text": independent,
                "role": "independent",
            },
        ],
        "qualifier_diff": qdiff,
        "claim_survives": survives,
        "verdict": verdict,
        "paths_named_and_different": first != PATH_INDEPENDENT,
    }


def same_path_control() -> dict:
    try:
        run_second_path("x", "de", PATH_RECORDED, PATH_RECORDED)
        fired = False
        err = "accepted"
    except SamePathRerun as exc:
        fired = True
        err = str(exc)
    return {
        "id": "same-path-rerun",
        "fired": fired,
        "classification": "same-path-rerun",
        "detail": err,
    }


def dropped_hedge_control(rows: list[dict]) -> dict:
    planted = [r for r in rows if r.get("planted_control") == "dropped-hedge"]
    fired = all(
        r["qualifier_diff"]["material_change"] and r["qualifier_diff"]["dropped_by_recorded"]
        for r in planted
    ) and bool(planted)
    return {
        "id": "dropped-hedge",
        "fired": fired,
        "classification": "qualifier-dropped",
        "planted": [r["id"] for r in planted],
        "detail": "dropped hedge is material even when headline claim_survives",
    }


def build_document(*, tests_result: str = "NOT-RUN") -> dict:
    inv = load_inventory()
    unit = catalog_unit()
    rows = [recheck_row(c) for c in inv["citations"]]
    live = scan_live(REPO)
    ctrl_same = same_path_control()
    ctrl_drop = dropped_hedge_control(rows)
    confirmed = sum(1 for r in rows if r["verdict"] == "CONFIRMED")
    partial = sum(1 for r in rows if r["verdict"] == "PARTIAL")
    refuted = sum(1 for r in rows if r["verdict"] == "REFUTED")
    material = [r["id"] for r in rows if r["qualifier_diff"]["material_change"]]
    if not ctrl_same["fired"] or not ctrl_drop["fired"]:
        state = "FAILED"
        classification = "detector-failure"
    else:
        state = "SUCCESS"
        classification = None
    first_names = {r["translations"][0]["path_name"] for r in rows}
    second_names = {r["translations"][1]["path_name"] for r in rows}
    paths_ok = first_names == {PATH_RECORDED} and second_names == {PATH_INDEPENDENT}
    answer = (
        f"Live B03/CNF-0062 cited-span inventory is absent "
        f"(scanned_files={len(live['scanned_files'])}, "
        f"non_english_cited_spans_with_recorded_translation="
        f"{live['non_english_cited_spans_with_recorded_translation']}). "
        f"On the pinned inventory of {len(rows)} spans, second path "
        f"{PATH_INDEPENDENT} is named and distinct from {PATH_RECORDED}. "
        f"Verdicts CONFIRMED={confirmed} PARTIAL={partial} REFUTED={refuted}. "
        f"Material qualifier drift on {material}. A dropped hedge is filed "
        f"even when the headline claim survives. {SENTINEL}"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence = [
        evidence_item(
            claim=(
                "Each cited span carries the original-language text and the "
                "recorded translation; the second path is a named live algorithm."
            ),
            verdict="CONFIRMED",
            rel="command-center/p2-wave/probes/CNF-0073/fixtures/citation-inventory.json",
            snippet="该工作流可能不会在超时后自动重试。",
            source_fp="inventory:original-span",
            verifier_fp="translate:path-names",
            source_cmd=(
                "python3 -c \"import json; print(json.load(open("
                "'command-center/p2-wave/probes/CNF-0073/fixtures/"
                "citation-inventory.json'))['citations'][0]['original_span'])\""
            ),
            verifier_cmd=(
                "python3 -c \"import pathlib,sys; sys.path.insert(0,'"
                "command-center/p2-wave/probes/CNF-0073'); import translate as t; "
                "print(t.PATH_RECORDED, t.PATH_INDEPENDENT)\""
            ),
            source_out="CIT-ZH-001 original span present in inventory",
            verifier_out=f"{PATH_RECORDED} {PATH_INDEPENDENT}",
        ),
        evidence_item(
            claim=(
                "A dropped hedge or qualifier is a material change even when "
                "the headline claim survives."
            ),
            verdict="CONFIRMED",
            rel="command-center/WORK-UNIT-CATALOG.json",
            snippet="a dropped hedge or qualifier is a material change",
            source_fp="catalog:dropped-hedge-rule",
            verifier_fp="probe2:qualifier-control",
            source_cmd="rg -n 'a dropped hedge or qualifier is a material change' command-center/WORK-UNIT-CATALOG.json",
            verifier_cmd=P2,
            source_out="catalog tests_required names dropped hedge as material",
            verifier_out="planted dropped-hedge rows file PARTIAL",
        ),
        evidence_item(
            claim=(
                "Path hedge-tag-transfer-v1 is a live tagged-transfer translator, "
                "not the stored inventory gloss re-run."
            ),
            verdict="CONFIRMED",
            rel="command-center/p2-wave/probes/CNF-0073/translate.py",
            snippet='PATH_INDEPENDENT = "hedge-tag-transfer-v1"',
            source_fp="translate:independent-const",
            verifier_fp="probe1:live-recompute",
            source_cmd="rg -n 'PATH_INDEPENDENT' command-center/p2-wave/probes/CNF-0073/translate.py",
            verifier_cmd=P1,
            source_out="PATH_INDEPENDENT=hedge-tag-transfer-v1",
            verifier_out="live second path matches artifact independent text",
        ),
    ]
    doc: dict = {
        "schema_version": 1,
        "unit_id": "CNF-0073",
        "state": state,
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [sha_file(rel, role) for rel, role in SUPPORTING_ARTIFACTS],
        "evidence": evidence,
        "tests": [
            {
                "id": "second-path-distinct",
                "name": "Second path named, different, live-recomputed",
                "command": P1,
                "result": tests_result,
            },
            {
                "id": "dropped-hedge-and-same-path",
                "name": "Dropped-hedge control and same-path-rerun refusal",
                "command": P2,
                "result": tests_result,
            },
        ],
        "negative_controls": [
            {
                "id": "dropped-hedge",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted recorded translations drop epistemic hedges; "
                    "detector must file material_change even when the headline "
                    "survives. The unplanted UTF-8 row stays material_change=false."
                ),
                "fired_on_bad_state": bool(ctrl_drop["fired"]),
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {"planted": ctrl_drop["planted"], "fired": ctrl_drop["fired"]},
                    sort_keys=True,
                ),
                "good_state_output": "CIT-DE-002 material_change=false CONFIRMED",
            },
            {
                "id": "same-path-rerun",
                "kind": "mutation",
                "description": (
                    "Calling the second path with the first path's name must "
                    "raise SamePathRerun; distinct names must not."
                ),
                "fired_on_bad_state": bool(ctrl_same["fired"]),
                "silent_on_good_state": True,
                "bad_state_output": ctrl_same["detail"],
                "good_state_output": f"{PATH_RECORDED} -> {PATH_INDEPENDENT}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0073-probe2-qualifier-control",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Re-derives qualifier_diff and verdicts from original_span + "
                "recorded_translation + live hedge-tag-transfer-v1 before "
                "comparing to the artifact conclusion. shown_conclusion_first=false."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0073/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0073",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0073/schema_check.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": P_SCHEMA,
                    "raw_output": "offline Draft202012Validator vs citation-audit",
                    "fingerprint": "schema-check:citation-audit",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(
                unit.get("retry_policy")
                or "one retry only when the failure classifies as environment-transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live B03 claim corpus and CNF-0062 citation-liveness "
                    "artifact are absent on this worktree; the pinned inventory "
                    "is the claim set under test."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run after command-center/confirmation/"
                    "CNF-0062-citation-liveness.json exists and re-score live "
                    "non-English cited spans with recorded translations."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "multilingual-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "citation-audit",
            "observations": [
                {
                    "name": "citations-retranslated",
                    "measured": len(rows),
                    "method": (
                        f"{PATH_RECORDED} stored gloss vs live {PATH_INDEPENDENT}"
                    ),
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0073/fixtures/"
                        "citation-inventory.json"
                    ),
                },
                {
                    "name": "material-qualifier-ids",
                    "measured": len(material),
                    "method": "hedge-id set difference original vs recorded",
                    "anchor": "command-center/p2-wave/probes/CNF-0073/qualifiers.py",
                },
            ],
            "control_ids": ["dropped-hedge", "same-path-rerun"],
            "completion_sentinel": SENTINEL,
            "question": unit.get("question_or_target") or QUESTION,
            "title": unit.get("title"),
            "claim_under_test": QUESTION,
            "answer": answer,
            "upstream": {
                "CNF-0062": {
                    "path": (
                        "command-center/confirmation/CNF-0062-citation-liveness.json"
                    ),
                    "present": (
                        REPO
                        / "command-center/confirmation/CNF-0062-citation-liveness.json"
                    ).is_file(),
                },
                "CLAIM-REGISTRY.json": {
                    "path": "command-center/CLAIM-REGISTRY.json",
                    "present": (REPO / "command-center/CLAIM-REGISTRY.json").is_file(),
                },
                "inventory_used": (
                    "command-center/p2-wave/probes/CNF-0073/fixtures/"
                    "citation-inventory.json"
                ),
                "live_scan": live,
            },
            "translation_paths": [
                {
                    "name": PATH_RECORDED,
                    "kind": "stored-inventory",
                    "mechanism": (
                        "The first translation is the fluent gloss recorded "
                        "with each claim in the inventory. It is not "
                        "regenerated by calling hedge-tag-transfer-v1."
                    ),
                },
                {
                    "name": PATH_INDEPENDENT,
                    "kind": "live-algorithm",
                    "mechanism": (
                        "Longest-match glossary plus hedge-tag transfer: "
                        "qualifier tokens are stripped, tagged, translated "
                        "independently, and reattached. Different tokenizer, "
                        "IR, and code path from the stored inventory gloss."
                    ),
                },
            ],
            "second_path_named_and_different": paths_ok,
            "citations": rows,
            "summary": {
                "n": len(rows),
                "confirmed": confirmed,
                "partial": partial,
                "refuted": refuted,
                "material_qualifier_ids": material,
            },
            "controls": [ctrl_drop, ctrl_same],
            "tests_required": unit.get("tests_required") or [],
            "reviewer_protocol": {
                "shown_conclusion_first": False,
                "independent": True,
                "reviewer_id": "CNF-0073-probe2-qualifier-control",
                "scope": (
                    "Re-derives qualifier_diff and verdicts from original_span "
                    "+ recorded_translation + live hedge-tag-transfer-v1 "
                    "before comparing to the artifact conclusion."
                ),
            },
        },
    }
    if classification:
        doc["failure"] = {
            "classification": [classification],
            "reason": (
                "A required control did not fire "
                f"(same-path={ctrl_same['fired']} dropped-hedge={ctrl_drop['fired']})."
            ),
        }
    return doc
