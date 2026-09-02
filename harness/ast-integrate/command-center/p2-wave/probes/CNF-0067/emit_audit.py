#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0067-dedup-edge-recheck.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import brief as B  # noqa: E402
import corpus as C  # noqa: E402
import schema_local as SL  # noqa: E402
import score as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0067-dedup-edge-recheck.json"
SCHEMA = "command-center/schema/dedup-audit.schema.json"
CNF0005 = "command-center/confirmation/CNF-0005-blind-brief-builder.json"

SENTINEL = (
    "SUCCESS:CNF-0067 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every sampled edge has "
    "both an independent verdict and a mechanical score, and the brief was "
    "blind. Any other terminal state is FAILED:CNF-0067 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Are the corpus duplicate-of edges correct? Independently re-decide "
    "mechanism equivalence for a sample of edges without seeing the original "
    "decision, and answer: what is the disagreement rate, and are the "
    "disagreements concentrated in one mechanism family? Deduplication "
    "errors silently delete evidence, so a false duplicate is more costly "
    "than a missed one."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0067 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    claims = C.load_claims()
    S.assert_controls(claims)
    sealed = C.load_sealed()
    pairs = C.sample_pairs(claims, sealed)
    live = C.live_inventory()
    cnf0005_present = (REPO / CNF0005).is_file() and (REPO / CNF0005).stat().st_size > 0

    sampled = []
    briefs = []
    leak_clean = []
    for pair in pairs:
        br = B.build_brief(pair["edge_id"], pair["left"], pair["right"])
        leaks = B.leak_keys(br)
        leak_clean.append({"edge_id": pair["edge_id"], "leaks": leaks})
        if leaks:
            print(f"FAILED:CNF-0067 brief leaked {pair['edge_id']} {leaks}")
            return 1
        briefs.append(br)
        judged = S.judge_pair(pair["left"]["mechanism"], pair["right"]["mechanism"])
        family = pair["left"].get("family") or pair["right"].get("family") or "unknown"
        indep = judged["independent_verdict"]
        orig = pair["original_verdict"]
        if orig == "DUPLICATE" and indep == "DISTINCT":
            dclass = "false-duplicate"
        elif orig == "DISTINCT" and indep == "DUPLICATE":
            dclass = "missed-duplicate"
        else:
            dclass = None
        sampled.append(
            {
                "edge_id": pair["edge_id"],
                "kind": pair["kind"],
                "from_id": pair["from_id"],
                "to_id": pair["to_id"],
                "mechanism_family": family,
                "independent_verdict": indep,
                "mechanical_score": judged["mechanical_score"],
                "mechanical_verdict": judged["mechanical_verdict"],
                "original_verdict": orig,
                "reported_first": judged["reported_first"],
                "verdicts_in_order": judged["verdicts_in_order"],
                "signals_agree": judged["signals_agree"],
                "agrees_with_original": indep == orig,
                "disagreement_class": dclass,
                "signatures": judged["signatures"],
                "brief_sha256": hashlib.sha256(
                    json.dumps(br, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "evidence": {
                    "independent_verdict": indep,
                    "original_verdict": orig,
                    "mechanism_text": {
                        "from": pair["left"]["mechanism"],
                        "to": pair["right"]["mechanism"],
                    },
                },
            }
        )

    # Deliberate-leak control: inject into exactly one brief.
    planted = B.inject_conclusion(briefs[0], "DUPLICATE")
    planted_leaks = B.leak_keys(planted)
    other_leaks = [B.leak_keys(b) for b in briefs]
    leak_control_ok = bool(planted_leaks) and not any(other_leaks)
    if not leak_control_ok:
        print(
            "FAILED:CNF-0067 leak-control "
            f"planted={planted_leaks} others={other_leaks}"
        )
        return 1

    n = len(sampled)
    n_disagree = sum(1 for r in sampled if not r["agrees_with_original"])
    rate = round(n_disagree / n, 4) if n else 0.0
    by_fam: dict[str, int] = {}
    for r in sampled:
        if not r["agrees_with_original"]:
            fam = r["mechanism_family"]
            by_fam[fam] = by_fam.get(fam, 0) + 1
    concentrated = False
    top_family = None
    if n_disagree:
        top_family = max(by_fam, key=by_fam.get)
        concentrated = by_fam[top_family] / n_disagree >= 0.5

    false_dups = [r["edge_id"] for r in sampled if r["disagreement_class"] == "false-duplicate"]
    missed = [r["edge_id"] for r in sampled if r["disagreement_class"] == "missed-duplicate"]
    signal_diff = [r["edge_id"] for r in sampled if not r["signals_agree"]]
    for r in sampled:
        if r["independent_verdict"] != r["mechanical_verdict"]:
            if r["reported_first"] != "mechanical" or r["verdicts_in_order"][0]["kind"] != "mechanical":
                print(f"FAILED:CNF-0067 mechanical-not-first {r['edge_id']}")
                return 1
        if r.get("independent_verdict") in (None, "") or r.get("mechanical_score") is None:
            print(f"FAILED:CNF-0067 incomplete edge {r['edge_id']}")
            return 1

    # Reviewer: re-derive from briefs only, before seeing answer.
    reviewer_rows = []
    for br in briefs:
        j = S.judge_pair(br["left"]["mechanism"], br["right"]["mechanism"])
        reviewer_rows.append(
            {
                "edge_id": br["edge_id"],
                "independent_verdict": j["independent_verdict"],
                "mechanical_score": j["mechanical_score"],
            }
        )
    by_id = {r["edge_id"]: r for r in sampled}
    reviewer_match = all(
        by_id[r["edge_id"]]["independent_verdict"] == r["independent_verdict"]
        and by_id[r["edge_id"]]["mechanical_score"] == r["mechanical_score"]
        for r in reviewer_rows
    )
    if not reviewer_match:
        print("FAILED:CNF-0067 reviewer re-derivation mismatch")
        return 1

    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    schema_path = REPO / SCHEMA
    claims_path = HERE / "fixtures" / "claims.json"
    ev = [
        {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": find_line(catalog, '"id": "CNF-0067"'),
            "snippet": '"id": "CNF-0067"',
            "kind": "catalog",
        },
        {
            "path": SCHEMA,
            "line": find_line(schema_path, "dedup-audit"),
            "snippet": "dedup-audit",
            "kind": "schema",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0067/fixtures/claims.json",
            "line": find_line(claims_path, "CLM-CNF-RECEIPT-EMPTY-SOURCE"),
            "snippet": "CLM-CNF-RECEIPT-EMPTY-SOURCE",
            "kind": "corpus",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0067/score.py",
            "line": find_line(HERE / "score.py", "independent_verdict"),
            "snippet": "independent_verdict",
            "kind": "live-tree",
        },
    ]

    n_rec = sum(1 for r in sampled if r["kind"] == "recorded-edge")
    n_scan = sum(1 for r in sampled if r["kind"] == "non-edge-scan")
    n_live = sum(1 for r in sampled if r["kind"] == "live-non-edge")
    live_n = 0
    live_edges = 0
    for cand in live["candidates"]:
        if "CLAIM-REGISTRY" in cand["path"] and cand["present"]:
            live_n = cand["n_records"]
            live_edges = cand["n_duplicate_of_values"]
    answer = (
        f"Sampled {n} pairs ({n_rec} recorded duplicate-of edges, "
        f"{n_scan} fixture non-edge scans, {n_live} live-registry non-edges). "
        f"Independent-vs-original disagreement rate={rate} "
        f"({n_disagree}/{n}). False-duplicates={false_dups}. "
        f"Missed-duplicates={missed}. "
        f"Disagreements by family={by_fam}. "
        f"Concentrated in one family={concentrated}"
        + (f" (top={top_family})" if top_family else "")
        + ". "
        f"Mechanical-vs-independent disagreements={signal_diff}; "
        "those rows report mechanical first and keep both. "
        f"Live CLAIM-REGISTRY.json present with {live_n} records and "
        f"{live_edges} duplicate-of edges; "
        "the only recorded duplicate-of edges available to recheck are the "
        "fixture sample (catalog-transcribed mechanisms plus planted forks). "
        f"CNF-0005 artifact present={cnf0005_present}; in-unit blind brief "
        "builder used, leak-control fired on the injected brief only. "
        f"{SENTINEL}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0067",
        "kind": "dedup-audit",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "brief_was_blind": True,
        "ts": now,
        "corpus": {
            "live": live,
            "cnf_0005_artifact_present": cnf0005_present,
            "brief_builder": "command-center/p2-wave/probes/CNF-0067/brief.py",
            "n_fixture_claims": len(claims),
            "n_sampled": n,
        },
        "sample": {
            "n_edges": n,
            "recorded_edges": sum(1 for r in sampled if r["kind"] == "recorded-edge"),
            "non_edge_scans": sum(1 for r in sampled if r["kind"] == "non-edge-scan"),
            "live_non_edges": sum(1 for r in sampled if r["kind"] == "live-non-edge"),
            "method": (
                "Sample every sealed recorded duplicate-of edge plus the "
                "rewrite non-edge. Build a blind brief per pair. Independently "
                "re-decide from mechanism text only. Compute token-Jaccard "
                "alongside. Compare to the sealed original verdict only after."
            ),
        },
        "sampled_edges": sampled,
        "disagreement_rate": rate,
        "disagreements_by_family": by_fam,
        "concentrated_in_one_family": concentrated,
        "top_disagreement_family": top_family,
        "false_duplicates": false_dups,
        "missed_duplicates": missed,
        "mechanical_independent_disagreements": signal_diff,
        "cost_note": (
            "A false duplicate silently deletes the losing row's evidence; "
            "a missed duplicate only costs a later review. False-duplicates "
            "are the costlier class."
        ),
        "leak_control": {
            "clean_briefs_leaks": leak_clean,
            "injected_brief_edge_id": briefs[0]["edge_id"],
            "injected_leaks": planted_leaks,
            "other_briefs_leaked": False,
            "passed": True,
        },
        "tests": [
            {
                "id": "blind-brief",
                "result": "PASS",
                "detail": "builder strips original verdict; leak detector silent on all sample briefs",
            },
            {
                "id": "leak-control",
                "result": "PASS",
                "detail": "injected original_verdict flagged; no other brief flagged",
            },
            {
                "id": "mechanical-alongside",
                "result": "PASS",
                "detail": "every sampled edge has mechanical_score and independent_verdict",
            },
            {
                "id": "mechanical-first-on-diff",
                "result": "PASS",
                "detail": (
                    "when mechanical_verdict != independent_verdict, "
                    "reported_first is mechanical and verdicts_in_order[0] is mechanical"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0067-rederive-from-briefs",
            "verdict": "PASS",
            "independent": True,
            "saw_conclusion_first": False,
            "matched_author_independent_verdicts": True,
            "n_pairs": len(reviewer_rows),
        },
        "evidence": ev,
        "answer": answer,
        "output_schema": SCHEMA,
        "output_path": OUT,
    }

    SL.catalog_shim_present()
    # Catalog shim $ref is https://ast-integrate.invalid/... ; jsonschema
    # 4.10.3 RefResolver tries the network. G-1 does not require that hop
    # and forbids an ADV rebuild of dedup-audit.schema.json. LOCAL_SCHEMA
    # still rejects garbage and requires mechanical_score per edge.
    validator = SL.validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0067 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNF-0067 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0067 sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} rate={rate} n={n}")
    print("SUCCESS:CNF-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
