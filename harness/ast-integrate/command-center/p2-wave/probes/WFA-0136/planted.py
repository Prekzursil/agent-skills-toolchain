"""Planted paraphrase and planted-distinct pair for WFA-0136.

Anchor is the live WFA-0136 catalog row. The paraphrase keeps that row's
mechanism string (material identity) and rewrites the prose so token-Jaccard
falls in the distinct band. The distinct plant uses a mechanism that does
not appear in the catalog.
"""
from __future__ import annotations

ANCHOR_ID = "WFA-0136"
PARAPHRASE_ID = "WFA-0136-PLANT-PARAPHRASE"
DISTINCT_ID = "WFA-0136-PLANT-DISTINCT"
DISTINCT_MECHANISM = (
    "lunar-tide-gated-teapot-scheduler-never-inspects-workflow-catalogs"
)

PARAPHRASE_TITLE = (
    "Angle-space ledger proving each library card is a different machine"
)
PARAPHRASE_QUESTION = (
    "Emit an explicit ledger showing each library card is a different machine, "
    "using angle-between-vectors rather than shared-token counts, since a total "
    "restatement of one machine lands in the same lexical band as a new machine. "
    "Name every card-pair the vector test marks as near copies while shared-token "
    "Jaccard called them far, and check that each leftover pair still carries a "
    "clause pointing at a machine-level split rather than a diction split."
)
DISTINCT_TITLE = (
    "Teapot steeping schedule driven by lunar tide tables"
)
DISTINCT_QUESTION = (
    "Steep ceramic pots against published tide tables and never open a foundry "
    "library, a work-unit catalog, or an archaeology schema pack."
)


def plants_from_anchor(anchor: dict) -> tuple[dict, dict]:
    mech = str(anchor.get("mechanism") or "").strip()
    if not mech:
        raise ValueError("anchor WFA-0136 has empty mechanism; cannot plant a paraphrase")
    paraphrase = {
        "id": PARAPHRASE_ID,
        "title": PARAPHRASE_TITLE,
        "question_or_target": PARAPHRASE_QUESTION,
        "mechanism": mech,
        "not_a_duplicate_because": "",
        "output_path": "",
        "source": "planted-mutant",
        "plant": "paraphrase",
        "anchor_id": ANCHOR_ID,
    }
    distinct = {
        "id": DISTINCT_ID,
        "title": DISTINCT_TITLE,
        "question_or_target": DISTINCT_QUESTION,
        "mechanism": DISTINCT_MECHANISM,
        "not_a_duplicate_because": "",
        "output_path": "",
        "source": "planted-mutant",
        "plant": "distinct",
        "anchor_id": ANCHOR_ID,
    }
    return paraphrase, distinct
