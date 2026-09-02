#!/usr/bin/env python3
"""Probe 1: 58 refs terminal; 12 batched questions; no guess; controls fire."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
import extract  # noqa: E402
import packet  # noqa: E402

ART = REPO / "command-center/receipts/CC-0023.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0023-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CC-0023":
        return fail(f"unit_id={doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:CC-0023" not in blob:
        return fail("sentinel-absent")
    if doc.get("did_not_guess") is not True:
        return fail("did_not_guess")
    if doc.get("silent_rewrites") != 0:
        return fail("silent_rewrites")

    written = corpus.write_fixtures(HERE / "fixtures")
    doc_rows = extract.extract_tree(
        [written[n] for n in corpus.DOC_FILES], root=HERE / "fixtures"
    )
    control_rows = extract.extract_tree(
        [written["controls.md"]], root=HERE / "fixtures"
    )
    questions, refs = packet.group_undecidable(doc_rows)

    if len(refs) != 58:
        return fail(f"live undecidable={len(refs)} want=58")
    if len(questions) != 12:
        return fail(f"live questions={len(questions)} want=12")
    if len(doc.get("references") or []) != 58:
        return fail(f"artifact references={len(doc.get('references') or [])}")
    if len(doc.get("questions") or []) != 12:
        return fail(f"artifact questions={len(doc.get('questions') or [])}")

    art_ids = {r["id"] for r in doc["references"]}
    live_ids = {r["id"] for r in refs}
    if art_ids != live_ids:
        return fail(f"reference-id drift extra={art_ids-live_ids} missing={live_ids-art_ids}")

    for row in doc["references"]:
        if row.get("verdict") != "UNDECIDABLE":
            return fail(f"{row['id']} verdict={row.get('verdict')}")
        if row.get("terminal_state") not in {"DEFERRED", "OWNER-ANSWERED"}:
            return fail(f"{row['id']} terminal={row.get('terminal_state')}")
        if row.get("resolved_namespace"):
            return fail(f"{row['id']} guessed resolved_namespace={row.get('resolved_namespace')}")
        if row["terminal_state"] == "DEFERRED" and len(row.get("impact_statement") or "") < 40:
            return fail(f"{row['id']} DEFERRED missing impact")
        if row["terminal_state"] == "OWNER-ANSWERED" and not row.get("owner_answer"):
            return fail(f"{row['id']} OWNER-ANSWERED without owner_answer")

    for q in doc["questions"]:
        if q["question"].count("?") != 1:
            return fail(f"{q['id']} not one foundation-level question")
        for key in (
            "recommendation",
            "strongest_tradeoff",
            "default_if_unanswered",
        ):
            if len(q.get(key) or "") < 20:
                return fail(f"{q['id']} missing {key}")
        if len(q.get("reference_ids") or []) < 1:
            return fail(f"{q['id']} empty cluster")

    # Grouping control: 58 refs batched, not 58 questions.
    if len(doc["questions"]) == 58:
        return fail("owner asked 58 times")
    if len(doc["questions"]) != 12:
        return fail("not 12 decisions")

    # False-positive: MECH-NN is not a bare M-NN.
    if any(r["token"] == "M-16" and "MECH" in (r.get("raw_token") or "") for r in doc_rows):
        return fail("MECH-16 reported as bare M-16")

    # Controls: uniquely held numbers resolve; mentions do not join the 58.
    resolvable = [r for r in control_rows if r["verdict"] == "RESOLVES-ONE"]
    tokens_ok = {r["token"] for r in resolvable}
    if "M-33" not in tokens_ok or "M-34" not in tokens_ok:
        return fail(f"resolvable control tokens={tokens_ok}")
    mentioned = {r["token"] for r in control_rows if r["verdict"] == "UNDECIDABLE"}
    if mentioned:
        return fail(f"mention leaked into UNDECIDABLE {mentioned} {control_rows}")

    print(
        json.dumps(
            {
                "probe": "probe1-terminal-and-grouping",
                "undecidable": len(refs),
                "questions": len(questions),
                "terminal_deferred": sum(
                    1 for r in doc["references"] if r["terminal_state"] == "DEFERRED"
                ),
                "guessed": 0,
                "controls_resolves_one": sorted(tokens_ok),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0023-probe1 terminal states grouping no-guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
