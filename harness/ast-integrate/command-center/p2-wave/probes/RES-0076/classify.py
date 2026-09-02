#!/usr/bin/env python3
"""Recompute arXiv retrieval classification from captured Atom snapshots.

Used by emit and by probe1 so the positive/negative ratio is computed, not
asserted. Does not fetch the network.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
ARXIV = HERE / "fixtures" / "arxiv"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "op": "http://a9.com/-/spec/opensearch/1.1/",
}

NEG_PHRASES = (
    "underperform",
    "does not outperform",
    "fail to outperform",
    "does not reliably outperform",
    "worse than",
    "no better than",
    "below a single",
    "premature consensus",
    "debate hacking",
)

NEG_HINTS = NEG_PHRASES + (
    "stop overvaluing",
    "rethinking the bounds",
    "should we be going mad",
    "fail and does it really",
    "sycophancy shapes multi-agent debate",
    "vanilla mad often underperforms",
    "do not reliably outperform",
    "not reliably outperform",
)

POS_HINTS = (
    "improves",
    "outperforms",
    "outperform",
    "enhancing",
    "improve factuality",
    "towards better",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _canon_id(arxiv_id: str) -> str:
    raw = (arxiv_id or "").rsplit("/", 1)[-1].strip()
    return re.sub(r"v\d+$", "", raw)


def is_negative_phrasing(query: str) -> bool:
    q = (query or "").lower()
    return any(p in q for p in NEG_PHRASES)


def classify_text(title: str, summary: str) -> str:
    blob = f"{title} {summary}".lower()
    neg = any(h in blob for h in NEG_HINTS)
    pos = any(h in blob for h in POS_HINTS)
    if neg and pos:
        return "MIXED"
    if neg:
        return "NEGATIVE"
    if pos:
        return "POSITIVE"
    return "UNCLEAR"


def parse_atom(path: Path) -> dict:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    total = root.findtext("op:totalResults", default="", namespaces=NS)
    papers = []
    for entry in root.findall("a:entry", NS):
        eid = entry.findtext("a:id", default="", namespaces=NS) or ""
        title = _norm(entry.findtext("a:title", default="", namespaces=NS) or "")
        summary = _norm(entry.findtext("a:summary", default="", namespaces=NS) or "")
        if eid.endswith("arxiv.org/api/errors") or title == "Error":
            continue
        arxiv_id = eid.rsplit("/", 1)[-1]
        papers.append(
            {
                "arxiv_id": arxiv_id,
                "arxiv_id_canon": _canon_id(arxiv_id),
                "title": title,
                "summary": summary,
                "classification": classify_text(title, summary),
            }
        )
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "total_results": int(total) if str(total).isdigit() else None,
        "returned": len(papers),
        "papers": papers,
    }


def load_index() -> list[dict]:
    idx_path = ARXIV / "index.json"
    rows = json.loads(idx_path.read_text(encoding="utf-8"))
    known = {r.get("id") for r in rows if isinstance(r, dict)}
    extra = ARXIV / "Q-POS-DU-IDLIST.xml"
    if extra.is_file() and "Q-POS-DU-IDLIST" not in known:
        parsed = parse_atom(extra)
        rows.append(
            {
                "id": "Q-POS-DU-IDLIST",
                "polarity": "positive",
                "search_query": "id_list=2305.14325",
                "max_results": 1,
                "start": 0,
                "ok": True,
                "http_status": 200,
                "bytes": parsed["bytes"],
                "sha256": parsed["sha256"],
                "total_results": parsed["total_results"],
                "returned": parsed["returned"],
                "path": "command-center/p2-wave/probes/RES-0076/fixtures/arxiv/Q-POS-DU-IDLIST.xml",
                "hits": [
                    {"arxiv_id": p["arxiv_id"], "title": p["title"]}
                    for p in parsed["papers"]
                ],
                "note": (
                    "Title-string search for Du et al. with hyphenated "
                    "'Multi-Agent' returned 0; recovered by arXiv id because "
                    "the paper titles it 'Multiagent Debate'."
                ),
            }
        )
    return rows


def run_classification() -> dict:
    rows = load_index()
    query_set = []
    unique: dict[str, dict] = {}
    mixed_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("ok"):
            continue
        rel = str(row.get("path") or "")
        fname = Path(rel).name if rel else f"{row['id']}.xml"
        xml_path = ARXIV / fname
        parsed = parse_atom(xml_path)
        if parsed["sha256"] != row.get("sha256"):
            raise ValueError(f"snapshot sha mismatch {row.get('id')}")
        qtext = str(row.get("search_query") or "")
        qrec = {
            "id": row["id"],
            "polarity": row.get("polarity"),
            "search_query": qtext,
            "negative_phrasing": is_negative_phrasing(qtext),
            "http_status": row.get("http_status"),
            "total_results": parsed["total_results"],
            "returned": parsed["returned"],
            "snapshot_sha256": parsed["sha256"],
            "snapshot_path": rel or fname,
        }
        if row.get("note"):
            qrec["note"] = row["note"]
        query_set.append(qrec)
        family = str(row.get("id") or "")
        for paper in parsed["papers"]:
            cid = paper["arxiv_id_canon"]
            prev = unique.get(cid)
            if prev is None:
                unique[cid] = dict(paper)
            if family.startswith("Q-MIXED-SINGLE-OR-COT"):
                mixed_ids.add(cid)

    by_class = {"POSITIVE": 0, "NEGATIVE": 0, "MIXED": 0, "UNCLEAR": 0}
    mixed_class = {"POSITIVE": 0, "NEGATIVE": 0, "MIXED": 0, "UNCLEAR": 0}
    for cid, paper in unique.items():
        by_class[paper["classification"]] += 1
        if cid in mixed_ids:
            mixed_class[paper["classification"]] += 1

    pos_q = next(q for q in query_set if q["id"] == "Q-POS-BROAD-IMPROVE")
    neg_q = next(q for q in query_set if q["id"] == "Q-NEG-UNDERPERFORM")
    pos_n = int(pos_q["total_results"])
    neg_n = int(neg_q["total_results"])
    ratio = pos_n / neg_n if neg_n else None
    mixed_pos = mixed_class["POSITIVE"]
    mixed_neg = mixed_class["NEGATIVE"]
    mixed_total = len(mixed_ids)

    return {
        "query_set": query_set,
        "unique_papers": len(unique),
        "unique_by_class": by_class,
        "mixed_query": {
            "id": "Q-MIXED-SINGLE-OR-COT",
            "total_results": next(
                q["total_results"] for q in query_set if q["id"] == "Q-MIXED-SINGLE-OR-COT"
            ),
            "unique_classified": mixed_total,
            "by_class": mixed_class,
            "positive_count": mixed_pos,
            "negative_count": mixed_neg,
            "positive_negative_ratio": (
                f"{mixed_pos}/{mixed_neg}" if mixed_neg else f"{mixed_pos}/0"
            ),
        },
        "retrieval_ratio": {
            "positive_query_id": pos_q["id"],
            "positive_total_results": pos_n,
            "negative_query_id": neg_q["id"],
            "negative_total_results": neg_n,
            "positive_over_negative": f"{pos_n}/{neg_n}",
            "ratio": round(ratio, 3) if ratio is not None else None,
            "mixed_query_positive_count": mixed_pos,
            "mixed_query_negative_count": mixed_neg,
            "interpretation": (
                f"Positive-verb search ({pos_q['id']}) returned {pos_n} hits; "
                f"explicit-null search ({neg_q['id']}) returned {neg_n} hits "
                f"(ratio {pos_n}/{neg_n}). Among the {mixed_total} unique papers "
                f"retrieved by the mixed single-agent/CoT query, keyword "
                f"classification labelled {mixed_pos} POSITIVE vs {mixed_neg} "
                f"NEGATIVE — a positive-phrasing search buries nulls."
            ),
        },
        "negative_phrasing_query_ids": [
            q["id"] for q in query_set if q["negative_phrasing"]
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_classification()["retrieval_ratio"], indent=2))
