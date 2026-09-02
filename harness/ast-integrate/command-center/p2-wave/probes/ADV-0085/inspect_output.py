"""Inspect a workflow-run envelope into score components and substance."""
from __future__ import annotations

from typing import Any, Mapping

from formula import ANCHOR_SATURATION

GOLD: dict[str, dict[str, Any]] = {
    "C1": {
        "answerable": True,
        "answer": "42",
        "anchors": ["oracle.py:10"],
        "recovery": False,
        "abstain": False,
    },
    "C2": {
        "answerable": True,
        "answer": "alpha",
        "anchors": ["spec.md:4"],
        "recovery": False,
        "abstain": False,
    },
    "C3": {
        "answerable": True,
        "answer": "commit-abc",
        "anchors": ["oracle.py:10"],
        "recovery": False,
        "abstain": False,
    },
    "C4": {
        "answerable": True,
        "answer": "deny",
        "anchors": ["spec.md:4"],
        "recovery": False,
        "abstain": False,
    },
    "C5": {
        "answerable": True,
        "answer": "retry-ok",
        "anchors": ["harness.py:88"],
        "recovery": True,
        "abstain": False,
    },
    "C6": {
        "answerable": False,
        "answer": None,
        "anchors": [],
        "recovery": False,
        "abstain": True,
    },
}

GOLD_IDS = tuple(GOLD.keys())
ANSWERABLE_IDS = tuple(cid for cid, row in GOLD.items() if row["answerable"])
REQUIRED_ENVELOPE = ("schema_version", "status", "cases")
ALLOWED_STATUS = {"ok", "abstain", "error", "recovered"}


def _as_cases(doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = doc.get("cases")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        if cid:
            out[cid] = row
    return out


def schema_valid(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    for key in REQUIRED_ENVELOPE:
        if key not in doc:
            return False
    if doc.get("schema_version") != 1:
        return False
    if str(doc.get("status") or "") not in ALLOWED_STATUS:
        return False
    cases = doc.get("cases")
    if not isinstance(cases, list) or not cases:
        return False
    seen: set[str] = set()
    for row in cases:
        if not isinstance(row, dict):
            return False
        cid = row.get("id")
        if not isinstance(cid, str) or not cid or cid in seen:
            return False
        seen.add(cid)
        if "answer" not in row or "abstain" not in row or "recovered" not in row:
            return False
        if "evidence_anchors" not in row:
            return False
        if not isinstance(row.get("abstain"), bool):
            return False
        if not isinstance(row.get("recovered"), bool):
            return False
        if row.get("answer") is not None and not isinstance(row.get("answer"), str):
            return False
        anchors = row.get("evidence_anchors")
        if not isinstance(anchors, list) or any(not isinstance(a, str) for a in anchors):
            return False
    return True


def unique_anchors(cases: Mapping[str, Mapping[str, Any]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for row in cases.values():
        for item in row.get("evidence_anchors") or []:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text and text not in seen:
                seen.add(text)
                found.append(text)
    return found


def coverage_ratio(cases: Mapping[str, Mapping[str, Any]]) -> float:
    n = len(unique_anchors(cases))
    return min(n / float(ANCHOR_SATURATION), 1.0)


def recovery_ratio(doc: Mapping[str, Any], cases: Mapping[str, Mapping[str, Any]]) -> float:
    """Naive recovery: total abstention or a trusted recovered flag.

    Missing gold cases fail closed. Envelope status `error` fails closed.
    """
    if str(doc.get("status") or "") == "error":
        return 0.0
    if any(gid not in cases for gid in GOLD_IDS):
        return 0.0
    if all(bool(cases[gid].get("abstain")) for gid in GOLD_IDS):
        return 1.0
    if any(bool(cases[gid].get("recovered")) for gid in GOLD_IDS):
        return 1.0
    if str(doc.get("status") or "") == "recovered":
        return 1.0
    return 0.0


def usability_ratio(valid: bool, cases: Mapping[str, Mapping[str, Any]]) -> float:
    if not valid or not cases:
        return 0.0
    if all(bool(row.get("abstain")) for row in cases.values()):
        return 1.0
    for row in cases.values():
        answer = row.get("answer")
        if isinstance(answer, str) and answer.strip():
            return 1.0
        anchors = row.get("evidence_anchors") or []
        if any(isinstance(a, str) and a.strip() for a in anchors):
            return 1.0
    return 0.0


def oracle_correctness(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    hits = 0
    details = []
    for cid in ANSWERABLE_IDS:
        gold = GOLD[cid]
        row = cases.get(cid) or {}
        abstain = bool(row.get("abstain"))
        recovered_needed = bool(gold.get("recovery"))
        recovered = bool(row.get("recovered"))
        answer = row.get("answer") if isinstance(row.get("answer"), str) else ""
        ok = (not abstain) and answer.strip() == str(gold["answer"])
        if recovered_needed:
            ok = ok and recovered
        if ok:
            hits += 1
        details.append({"id": cid, "correct": ok})
    n = len(ANSWERABLE_IDS)
    return {
        "hits": hits,
        "n": n,
        "ratio": round(hits / n, 6) if n else 0.0,
        "details": details,
    }


def resolving_anchor_rate(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cited = unique_anchors(cases)
    allowed: set[str] = set()
    for row in GOLD.values():
        for item in row.get("anchors") or []:
            allowed.add(str(item))
    resolving = [a for a in cited if a in allowed]
    if not cited:
        return {"cited": 0, "resolving": 0, "ratio": 0.0, "cited_ids": [], "resolving_ids": []}
    return {
        "cited": len(cited),
        "resolving": len(resolving),
        "ratio": round(len(resolving) / len(cited), 6),
        "cited_ids": cited,
        "resolving_ids": resolving,
    }


def answer_char_count(cases: Mapping[str, Mapping[str, Any]]) -> int:
    total = 0
    for row in cases.values():
        answer = row.get("answer")
        if isinstance(answer, str):
            total += len(answer)
        notes = row.get("notes")
        if isinstance(notes, str):
            total += len(notes)
    return total


def inspect_envelope(doc: Any) -> dict[str, Any]:
    valid = schema_valid(doc)
    cases = _as_cases(doc) if isinstance(doc, dict) else {}
    oracle = oracle_correctness(cases)
    resolving = resolving_anchor_rate(cases)
    components = {
        "correctness": 1.0 if valid else 0.0,
        "coverage": coverage_ratio(cases) if valid else 0.0,
        "recovery": recovery_ratio(doc, cases) if valid else 0.0,
        "usability": usability_ratio(valid, cases),
    }
    substance_ratio = round(0.7 * oracle["ratio"] + 0.3 * resolving["ratio"], 6)
    return {
        "schema_valid": valid,
        "components": components,
        "oracle": oracle,
        "resolving_anchors": resolving,
        "unique_anchors": unique_anchors(cases) if valid else [],
        "answer_chars": answer_char_count(cases),
        "substance": {
            "oracle_correctness": oracle["ratio"],
            "resolving_anchor_rate": resolving["ratio"],
            "ratio": substance_ratio,
            "answerable_hits": oracle["hits"],
            "answerable_n": oracle["n"],
        },
        "case_ids": sorted(cases),
        "status": doc.get("status") if isinstance(doc, dict) else None,
    }
