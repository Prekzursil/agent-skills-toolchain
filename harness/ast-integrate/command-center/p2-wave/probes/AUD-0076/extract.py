"""Probe 1 logic: extract imperative owner statements into a requirement list."""
from __future__ import annotations

import re
from typing import Any

from common import BINDING_SEEDS, PLANTED_TEXT, PLANTED_TOKEN, find_line
from corpus import scratch_with_plant

IMPERATIVE = re.compile(
    r"\b(must|shall|never|do not|don't|required|binding|PR-ONLY|"
    r"DELETE-ALL|triage first|default to Opus)\b",
    re.I,
)


def _req(
    rid: str,
    text: str,
    source: str,
    needles: tuple[str, ...] | list[str],
    provenance: str,
) -> dict[str, Any]:
    return {
        "id": rid,
        "text": " ".join(text.split()),
        "source": source,
        "needles": list(needles),
        "provenance": provenance,
        "planted": PLANTED_TOKEN in text,
    }


def extract_from_owner_questions(catalog: dict, catalog_text: str) -> list[dict]:
    out: list[dict] = []
    for q in catalog.get("owner_questions") or []:
        if not isinstance(q, dict):
            continue
        if str(q.get("state") or "") != "ANSWERED":
            continue
        qid = str(q.get("id") or "")
        answer = str(q.get("answer") or "").strip()
        detail = str(q.get("answer_detail") or "").strip()
        text = str(q.get("text") or "").strip()
        body = detail or answer
        if not body:
            continue
        snippet = qid
        line = find_line(catalog_text, f'"id": "{qid}"')
        needles = [qid, answer[:80]] if answer else [qid]
        needles = [n for n in needles if n]
        out.append(
            _req(
                f"REQ-{qid}",
                f"{qid}: {body}",
                f"{'command-center/WORK-UNIT-CATALOG.json'}:{line}"
                if line > 0
                else "command-center/WORK-UNIT-CATALOG.json owner_questions",
                tuple(needles),
                str(q.get("answer_provenance") or "answered-owner-question"),
            )
        )
        # Keep unused `text` referenced so the question wording is in the record.
        out[-1]["question_text"] = text
    return out


def extract_from_disposition_items(catalog: dict, catalog_text: str) -> list[dict]:
    out: list[dict] = []
    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        disp = str(item.get("disposition") or "")
        if disp not in {"DROPPED-BY-OWNER", "SUPERSEDED"}:
            continue
        iid = str(item.get("id") or "")
        ev = str(item.get("disposition_evidence") or item.get("evidence") or "")
        if not ev or not IMPERATIVE.search(ev):
            continue
        line = find_line(catalog_text, f'"id": "{iid}"')
        out.append(
            _req(
                f"REQ-ITEM-{iid}",
                f"{iid} ({disp}): {ev}",
                f"command-center/WORK-UNIT-CATALOG.json:{line}"
                if line > 0
                else f"command-center/WORK-UNIT-CATALOG.json items {iid}",
                (iid, ev[:96]),
                f"catalog-item disposition={disp}",
            )
        )
    return out


def extract_binding_seeds(catalog_text: str) -> list[dict]:
    out: list[dict] = []
    for seed in BINDING_SEEDS:
        hits = [n for n in seed["needles"] if n in catalog_text]
        if not hits:
            continue
        line = find_line(catalog_text, hits[0])
        out.append(
            _req(
                seed["id"],
                seed["text"],
                f"command-center/WORK-UNIT-CATALOG.json:{line}"
                if line > 0
                else "command-center/WORK-UNIT-CATALOG.json",
                seed["needles"],
                "catalog-quoted binding owner decision",
            )
        )
    return out


def extract_planted(scratch_text: str) -> dict | None:
    if PLANTED_TOKEN not in scratch_text:
        return None
    line = find_line(scratch_text, PLANTED_TOKEN)
    return _req(
        "REQ-PLANTED-CANARY",
        PLANTED_TEXT,
        f"scratch-transcript:{line}" if line > 0 else "scratch-transcript",
        (PLANTED_TOKEN,),
        "synthetic-control",
    )


def extract_requirements(
    catalog: dict,
    catalog_text: str,
    surface_text: str,
    *,
    include_plant: bool = False,
) -> list[dict]:
    """Extract owner-imperative requirements from the recoverable corpus.

    Structured catalog rows are the precision path. Binding seeds are admitted
    only when their needles exist in the catalog blob (computed, not asserted).
    The planted canary is admitted only from a scratch copy.
    """
    seen: set[str] = set()
    rows: list[dict] = []
    for row in (
        extract_from_owner_questions(catalog, catalog_text)
        + extract_from_disposition_items(catalog, catalog_text)
        + extract_binding_seeds(catalog_text)
    ):
        key = row["id"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if include_plant:
        planted = extract_planted(scratch_with_plant(surface_text) if PLANTED_TOKEN not in surface_text else surface_text)
        if planted is not None:
            rows.append(planted)
    rows.sort(key=lambda r: r["id"])
    return rows


def live_and_scratch_extract(catalog: dict, catalog_text: str, surface_text: str) -> dict:
    live = extract_requirements(catalog, catalog_text, surface_text, include_plant=False)
    scratch = extract_requirements(
        catalog,
        catalog_text,
        scratch_with_plant(surface_text),
        include_plant=True,
    )
    planted_ids = [r["id"] for r in scratch if r.get("planted")]
    return {
        "live": live,
        "scratch": scratch,
        "planted_extracted": bool(planted_ids),
        "planted_ids": planted_ids,
        "live_count": len(live),
        "scratch_count": len(scratch),
    }
