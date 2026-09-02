#!/usr/bin/env python3
"""Citation fabrication detector for ADV-0080.

Probe 1 (span containment): resolve a citation to a document body and search
for text that supports the attached claim. Records MATCHED span or NOT-FOUND.

Probe 2 (metadata resolution): resolve a scholarly identifier against a
bibliographic catalog and compare title/author/year to the citation as written.
Never reads document bodies — mechanically different from probe 1.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted.json"
METADATA = HERE / "fixtures" / "metadata.json"
CAPTURES = REPO / "command-center" / "p2-wave" / "probes" / "RES-0047" / "captures"

STOP = frozenset(
    """a an the of and or to in for is that this with on at by from as be are was
    were it its they their them we our you your not no if then than so such any
    all each both into over after before about between through during without
    within also only more most other some can may must should would could did
    does doing been being have has had do will shall page et al states state
    appears appear cited claim claims""".split()
)

ALIASES = {
    "checksum": "cksum",
    "checksums": "cksum",
    "sha-256": "sha256",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm_ws(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (text or "").lower())
    out = []
    for t in raw:
        t = ALIASES.get(t, t.replace("-", ""))
        if t in STOP or len(t) < 3:
            continue
        out.append(t)
    return out


def extract_doi(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"(10\.\d{4,9}/[^\s\"<>]+)", url, re.I)
    if not m:
        return ""
    return m.group(1).rstrip(").,;").lower()


def load_metadata() -> dict[str, dict]:
    doc = load_json(METADATA)
    recs = {}
    for k, v in (doc.get("records") or doc.get("records") or {}).items():
        recs[k.lower()] = v
    return recs


def read_body(rel_or_abs: str | None) -> tuple[str | None, str]:
    if not rel_or_abs:
        return None, "no-body-path"
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = REPO / rel_or_abs
    if not path.is_file():
        return None, "body-absent"
    try:
        raw = path.read_bytes()
    except OSError:
        return None, "body-unreadable"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return "", "body-empty"
    return text, "ok"


def longest_claim_substring(claim: str, body: str) -> str:
    c = norm_ws(claim).lower()
    b = norm_ws(body).lower()
    if len(c) < 24:
        return c if c and c in b else ""
    words = c.split()
    for n in range(min(14, len(words)), 3, -1):
        for i in range(0, len(words) - n + 1):
            frag = " ".join(words[i : i + n])
            if len(frag) >= 24 and frag in b:
                return frag
    return ""


def span_containment(claim: str, body: str | None, body_status: str) -> dict:
    if body is None:
        return {
            "probe": "span-containment",
            "status": "NOT-FOUND",
            "reason": body_status,
            "matched_span": None,
            "token_coverage": 0.0,
            "supports": False,
        }
    if not str(body).strip():
        return {
            "probe": "span-containment",
            "status": "NOT-FOUND",
            "reason": "body-empty",
            "matched_span": None,
            "token_coverage": 0.0,
            "supports": False,
        }
    claim_toks = tokens(claim)
    body_set = set(tokens(body))
    hit = [t for t in claim_toks if t in body_set]
    coverage = (len(hit) / len(claim_toks)) if claim_toks else 0.0
    span = longest_claim_substring(claim, body)
    distinctive = [t for t in hit if len(t) >= 5]
    supports = bool(span) or (coverage >= 0.40 and len(distinctive) >= 2)
    return {
        "probe": "span-containment",
        "status": "MATCHED" if supports else "NOT-FOUND",
        "reason": "span" if span else ("token-coverage" if supports else "no-support"),
        "matched_span": span or None,
        "token_coverage": round(coverage, 4),
        "matched_tokens": hit[:24],
        "supports": supports,
        "body_chars": len(body),
        "body_sha256": sha256_text(body),
    }


def _surname(name: str) -> str:
    parts = re.findall(r"[A-Za-z]+", name or "")
    return parts[-1].lower() if parts else ""


def metadata_resolution(pair: dict, catalog: dict[str, dict]) -> dict:
    doi = (pair.get("doi") or extract_doi(pair.get("url") or "")).lower()
    cited_title = pair.get("cited_title") or ""
    cited_authors = pair.get("cited_authors") or []
    cited_year = pair.get("cited_year")
    if not doi:
        return {
            "probe": "metadata-resolution",
            "status": "NO-IDENTIFIER",
            "reason": "no-doi",
            "doi": "",
            "resolved": False,
            "identity_match": None,
            "mismatches": [],
        }
    rec = catalog.get(doi)
    if rec is None:
        return {
            "probe": "metadata-resolution",
            "status": "UNRESOLVED",
            "reason": "doi-not-in-catalog",
            "doi": doi,
            "resolved": False,
            "identity_match": False,
            "mismatches": ["unregistered-or-unknown-doi"],
        }
    mismatches: list[str] = []
    rec_title = rec.get("title") or ""
    rec_year = rec.get("year")
    rec_authors = rec.get("authors") or []
    if cited_title:
        ct = set(tokens(cited_title))
        rt = set(tokens(rec_title))
        if ct and rt:
            overlap = len(ct & rt) / max(len(ct), 1)
            if overlap < 0.4:
                mismatches.append("title")
        elif tokens(cited_title) and not (set(tokens(cited_title)) & set(tokens(rec_title))):
            mismatches.append("title")
    if cited_year not in (None, "") and rec_year not in (None, ""):
        try:
            if int(cited_year) != int(rec_year):
                mismatches.append("year")
        except (TypeError, ValueError):
            mismatches.append("year")
    if cited_authors:
        cited_surnames = {_surname(a) for a in cited_authors if a}
        rec_surnames = {_surname(a) for a in rec_authors if a}
        if cited_surnames and rec_surnames and not (cited_surnames & rec_surnames):
            mismatches.append("authors")
    match = not mismatches
    return {
        "probe": "metadata-resolution",
        "status": "MATCH" if match else "MISMATCH",
        "reason": "identity-ok" if match else "identity-mismatch",
        "doi": doi,
        "resolved": True,
        "identity_match": match,
        "mismatches": mismatches,
        "resolved_title": rec_title,
        "resolved_year": rec_year,
        "resolved_authors": rec_authors,
        "cited_title": cited_title,
        "cited_year": cited_year,
        "cited_authors": cited_authors,
    }


def harvest_res0047() -> list[dict]:
    path = REPO / "command-center" / "research" / "RES-0047.json"
    if not path.is_file():
        return []
    rec = load_json(path)
    pairs = []
    for ev in rec.get("evidence") or []:
        claim = ev.get("claim") or ""
        eid = ev.get("id") or "E"
        for rail in ev.get("rails") or []:
            cap = rail.get("capture_id") or rail.get("capture_id") or ""
            url = rail.get("permalink") or ""
            body_rel = None
            if cap:
                cand = CAPTURES / f"{cap}.body"
                if cand.is_file():
                    body_rel = cand.relative_to(REPO).as_posix()
            pairs.append(
                {
                    "id": f"corpus-RES-0047-{eid}-{cap or 'rail'}",
                    "set": "corpus",
                    "planted_kind": None,
                    "expect_fabricated": False,
                    "claim": claim,
                    "url": url,
                    "doi": extract_doi(url),
                    "cited_title": "",
                    "cited_authors": [],
                    "cited_year": None,
                    "body_rel": body_rel,
                    "source_artifact": "command-center/research/RES-0047.json",
                    "capture_id": cap,
                }
            )
    return pairs


def harvest_res0092() -> list[dict]:
    path = REPO / "command-center" / "research" / "RES-0092.json"
    if not path.is_file():
        return []
    rec = load_json(path)
    pairs = []
    for row in rec.get("source_lineage") or rec.get("source_lineage") or []:
        pid = row.get("id") or "src"
        rel = row.get("path") or ""
        doi = extract_doi(rel)
        body_rel = None
        if rel and not rel.startswith("http") and (REPO / rel).is_file():
            body_rel = rel
        pairs.append(
            {
                "id": f"corpus-RES-0092-{pid}",
                "set": "corpus",
                "planted_kind": None,
                "expect_fabricated": False,
                "claim": row.get("note") or "",
                "url": rel,
                "doi": doi,
                "cited_title": "",
                "cited_authors": [],
                "cited_year": None,
                "body_rel": body_rel,
                "source_artifact": "command-center/research/RES-0092.json",
            }
        )
    for c in rec.get("claims") or []:
        cid = c.get("id") or "C"
        anchor = c.get("anchor") or c.get("anchor") or ""
        body_rel = None
        if anchor and not str(anchor).startswith("http") and "[" not in str(anchor):
            if (REPO / anchor).is_file():
                body_rel = anchor
        pairs.append(
            {
                "id": f"corpus-RES-0092-claim-{cid}",
                "set": "corpus",
                "planted_kind": None,
                "expect_fabricated": False,
                "claim": c.get("claim") or "",
                "url": anchor,
                "doi": extract_doi(anchor),
                "cited_title": "",
                "cited_authors": [],
                "cited_year": None,
                "body_rel": body_rel,
                "source_artifact": "command-center/research/RES-0092.json",
            }
        )
    return pairs


def load_all_pairs() -> list[dict]:
    planted = load_json(PLANTED).get("pairs") or []
    return list(planted) + harvest_res0047() + harvest_res0092()


def evaluate_pair(pair: dict, catalog: dict[str, dict]) -> dict:
    body, body_status = read_body(pair.get("body_rel"))
    span = span_containment(pair.get("claim") or "", body, body_status)
    meta = metadata_resolution(pair, catalog)
    reasons: list[str] = []
    fabricated = False
    if span["status"] == "NOT-FOUND":
        if pair.get("set") == "planted" or body is not None:
            fabricated = True
            reasons.append("span-not-found")
        else:
            reasons.append("body-unavailable")
    if meta["status"] == "UNRESOLVED" and pair.get("doi"):
        fabricated = True
        reasons.append("doi-unresolved")
    if meta["status"] == "MISMATCH":
        fabricated = True
        reasons.append("metadata-mismatch")
    expected = pair.get("expect_fabricated")
    detected_ok = None
    if expected is True:
        detected_ok = bool(fabricated)
    elif expected is False:
        detected_ok = not bool(fabricated)
    return {
        "id": pair.get("id"),
        "set": pair.get("set"),
        "planted_kind": pair.get("planted_kind"),
        "expect_fabricated": expected,
        "claim": pair.get("claim"),
        "url": pair.get("url"),
        "doi": pair.get("doi") or "",
        "source_artifact": pair.get("source_artifact"),
        "span": span,
        "metadata": meta,
        "fabricated": fabricated,
        "reasons": reasons,
        "detected_as_expected": detected_ok,
    }


def run_detector() -> dict:
    catalog = load_metadata()
    pairs = load_all_pairs()
    rows = [evaluate_pair(p, catalog) for p in pairs]
    planted = [r for r in rows if r["set"] == "planted"]
    planted_fab = [r for r in planted if r["expect_fabricated"] is True]
    genuine = [r for r in planted if r["expect_fabricated"] is False]
    detected = [r for r in planted_fab if r["fabricated"]]
    missed = [r for r in planted_fab if not r["fabricated"]]
    false_pos = [r for r in genuine if r["fabricated"]]
    recall = (len(detected) / len(planted_fab)) if planted_fab else 0.0
    corpus = [r for r in rows if r["set"] == "corpus"]
    corpus_supported = [r for r in corpus if r["span"].get("supports")]
    corpus_unavail = [
        r
        for r in corpus
        if r["span"].get("reason") in {"no-body-path", "body-absent"}
    ]
    return {
        "unit_id": "ADV-0080",
        "n_pairs": len(rows),
        "n_planted": len(planted),
        "n_planted_fabricated": len(planted_fab),
        "n_detected": len(detected),
        "n_missed": len(missed),
        "n_false_positives": len(false_pos),
        "planted_recall": round(recall, 4),
        "planted_recall_reported": True,
        "all_planted_detected": bool(planted_fab) and not missed and not false_pos,
        "missed_ids": [r["id"] for r in missed],
        "false_positive_ids": [r["id"] for r in false_pos],
        "n_corpus": len(corpus),
        "n_corpus_supported": len(corpus_supported),
        "n_corpus_body_unavailable": len(corpus_unavail),
        "rows": rows,
    }


# Names imported by the two named probes.
run_detector = run_detector
load_all_pairs = load_all_pairs
load_metadata = load_metadata
metadata_resolution = metadata_resolution


if __name__ == "__main__":
    doc = run_detector()
    slim = {k: v for k, v in doc.items() if k != "rows"}
    print(json.dumps(slim, sort_keys=True))
    print(
        f"recall={doc['planted_recall']} "
        f"detected={doc['n_detected']}/{doc['n_planted_fabricated']}"
    )
