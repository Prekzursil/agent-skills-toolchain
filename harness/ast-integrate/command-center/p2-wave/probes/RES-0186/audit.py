#!/usr/bin/env python3
"""Citation census + support audit of one completed research artifact.

Target: command-center/research/RES-0069.json (every claims[].source_lineage
entry; rails[] is a duplicate of source_lineage and is not double-counted).

Per citation, three binary questions:
  (a) resolve: snapshot exists, sha256 matches, capture HTTP 200, URL+timestamp
  (b) assertion still present: quoted span is in the searchable snapshot body
  (c) SUPPORT the citing sentence, not merely same-topic

Support is judged against the quoted span. NON-SUPPORTING rows quote both the
citing sentence and the cited text.

A missed detector-control injection means the reported support rate is an
upper bound only.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE_REL = "command-center/research/RES-0069.json"
SOURCE = REPO / SOURCE_REL
UNIT_ID = "RES-0186"
SENTINEL = "SUCCESS:RES-0186"
QUESTION = (
    "For a completed research artifact, what fraction of its citations "
    "(a) resolve at all, (b) resolve to content that still contains the "
    "cited assertion, and (c) actually SUPPORT the sentence they are "
    "attached to rather than merely being topically adjacent - measured "
    "over every citation in one real artifact, not a sample?"
)

# Phrases that must appear in the quoted span for SUPPORT of that attachment.
# Missing every phrase => TOPICALLY-ADJACENT (span may still be in the source).
SUPPORT_NEED_ANY: dict[tuple[str, str], tuple[str, ...]] = {
    ("C-AZURE-UNTIL", "gh_azure_docs_until"): ("prevent endless loops",),
    ("C-AZURE-UNTIL", "learn_azure_until"): ("prevent endless loops",),
    ("C-AZURE-UNTIL-LIMITS", "gh_azure_limits"): ("default: 60", "60"),
    ("C-AZURE-UNTIL-LIMITS", "learn_azure_limits"): ("default: 60", "60"),
    ("C-N8N-OPTIONAL", "gh_n8n_split"): ("infinite loop",),
    ("C-N8N-OPTIONAL", "raw_n8n_split"): (
        "termination condition never matches",
        "infinite loop",
    ),
    ("C-LANGGRAPH-RECURSION", "gh_langgraph_errors"): ("prevents infinite loops",),
    ("C-LANGGRAPH-RECURSION", "docs_langgraph_errors"): (
        "recursion_limit",
        "graphrecursionerror",
        "prevents infinite loops",
    ),
    ("C-AIRFLOW-SENSOR", "gh_airflow_sensor_tasksdk"): ("timeout",),
    ("C-AIRFLOW-SENSOR", "raw_airflow_docs_sensors"): (
        "before failing",
        "timeout",
        "maximum time",
    ),
    ("C-AIRFLOW-DEFAULT-TIMEOUT", "gh_airflow_config_yml"): ("7 days", "604800"),
    ("C-AIRFLOW-DEFAULT-TIMEOUT", "raw_airflow_config_yml"): ("604800",),
    ("C-SFN-CHOICE-QUOTA", "gh_cdk_choice"): (
        "25,000",
        "25000",
        "until",
        "while",
        "native",
        "quota",
    ),
    ("C-SFN-CHOICE-QUOTA", "raw_sfn_quotas_md"): ("25,000", "25000"),
    ("C-TEMPORAL-FOREVER", "gh_temporal_continue_encyc"): ("forever", "continue-as-new"),
    ("C-TEMPORAL-FOREVER", "raw_temporal_timeouts"): ("workflow timeouts",),
    ("C-DURABLE-ETERNAL", "gh_durable_md"): ("indefinitely", "eternal"),
    ("C-DURABLE-ETERNAL", "learn_durable_eternal"): ("infinite loop",),
}

NEVER_EXPRESSIBLE = (
    "never expressible",
    "every surveyed engine",
    "mandatory finite iteration cap",
)
UNBOUNDED = (
    "infinite loop",
    "run forever",
    "run indefinitely",
    "stuck in an infinite",
    "do not recommend setting workflow timeouts",
)

ABSENT_QUOTE = "ZXCV-0186-deliberately-absent-quote-not-in-any-source"
TOPICAL_SPAN = "from __future__ import annotations"
FAKE_SNAP = "command-center/p2-wave/probes/RES-0186/no-such-snapshot.bin"
FAKE_SHA = "0" * 64

# Three mismatched citations injected into a COPY of the artifact.
INJECTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "INJ-QUOTE-ABSENT",
        "claim_id": "C-AZURE-UNTIL",
        "source_id": "gh_azure_docs_until",
        "mode": "quote-absent",
        "expect_class": "ASSERTION-ABSENT",
    },
    {
        "id": "INJ-UNRESOLVED",
        "claim_id": "C-N8N-OPTIONAL",
        "source_id": "raw_n8n_split",
        "mode": "unresolved",
        "expect_class": "UNRESOLVED",
    },
    {
        "id": "INJ-TOPICAL",
        "claim_id": "C-AIRFLOW-SENSOR",
        "source_id": "gh_airflow_sensor_tasksdk",
        "mode": "topical-adjacent",
        "expect_class": "TOPICALLY-ADJACENT",
    },
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def norm(text: str) -> str:
    return " ".join(str(text or "").lower().replace('"', "").replace("'", "").split())


def is_github_contents(raw: bytes) -> bool:
    if not raw.lstrip().startswith(b"{"):
        return False
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and doc.get("encoding") == "base64" and "content" in doc


def searchable_text(raw: bytes) -> str:
    if is_github_contents(raw):
        doc = json.loads(raw.decode("utf-8"))
        blob = base64.b64decode(doc["content"])
        return blob.decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def load_source(path: Path | None = None) -> dict[str, Any]:
    p = path or SOURCE
    return json.loads(p.read_text(encoding="utf-8"))


def extract_citations(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every claims[].source_lineage attachment. rails[] is ignored (duplicate)."""
    rows: list[dict[str, Any]] = []
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        cid = str(claim.get("id") or "")
        citing = str(claim.get("claim") or "")
        verdict = str(claim.get("verdict") or "")
        for idx, src in enumerate(claim.get("source_lineage") or []):
            if not isinstance(src, dict):
                continue
            rows.append(
                {
                    "citation_id": f"{cid}#{src.get('id') or idx}",
                    "claim_id": cid,
                    "claim_verdict": verdict,
                    "citing_sentence": citing,
                    "source_id": str(src.get("id") or ""),
                    "kind": str(src.get("kind") or ""),
                    "request_url": src.get("request_url"),
                    "final_url": src.get("final_url") or src.get("request_url"),
                    "permalink": src.get("permalink"),
                    "fetched_at": src.get("fetched_at"),
                    "http_status": src.get("http_status"),
                    "declared_sha256": src.get("sha256"),
                    "declared_bytes": src.get("bytes"),
                    "snapshot": src.get("snapshot"),
                    "snippet": src.get("snippet") or "",
                    "github_contents": src.get("github_contents"),
                    "raw_source": src,
                }
            )
    return rows


def lineage_complete(row: dict[str, Any]) -> bool:
    url = row.get("final_url") or row.get("permalink") or row.get("request_url")
    return bool(url) and bool(row.get("fetched_at")) and bool(row.get("declared_sha256"))


def resolve_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    rel = str(row.get("snapshot") or "").replace("\\", "/")
    path = REPO / rel if rel else None
    out: dict[str, Any] = {
        "snapshot_rel": rel,
        "snapshot_present": bool(path and path.is_file()),
        "live_sha256": None,
        "live_bytes": None,
        "sha_match": False,
        "capture_http_200": row.get("http_status") == 200,
        "lineage_complete": lineage_complete(row),
        "searchable_chars": 0,
        "body_error": None,
    }
    if not out["snapshot_present"]:
        out["resolved"] = False
        return out
    assert path is not None
    raw = path.read_bytes()
    live = sha256_bytes(raw)
    out["live_sha256"] = live
    out["live_bytes"] = len(raw.replace(b"\r\n", b"\n"))
    out["sha_match"] = live == str(row.get("declared_sha256") or "")
    try:
        body = searchable_text(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError) as exc:
        out["body_error"] = f"{type(exc).__name__}:{exc}"
        out["resolved"] = False
        return out
    out["searchable_chars"] = len(body)
    out["_body"] = body
    out["resolved"] = (
        out["sha_match"]
        and out["capture_http_200"]
        and out["lineage_complete"]
        and out["body_error"] is None
    )
    return out


def support_class(citing: str, snippet: str, claim_id: str, source_id: str) -> str:
    citing_n = norm(citing)
    snip_n = norm(snippet)
    if any(m in citing_n for m in NEVER_EXPRESSIBLE) and any(
        m in snip_n for m in UNBOUNDED
    ):
        return "CONTRADICTING"
    key = (claim_id, source_id)
    need = SUPPORT_NEED_ANY.get(key)
    if need is None:
        if claim_id.startswith("C-ALL-ENGINES"):
            return "TOPICALLY-ADJACENT"
        raise KeyError(f"no support rule for {key}")
    if any(norm(p) in snip_n for p in need):
        return "SUPPORTING"
    return "TOPICALLY-ADJACENT"


def audit_one(row: dict[str, Any]) -> dict[str, Any]:
    citing = row["citing_sentence"]
    snippet = str(row.get("snippet") or "")
    res = resolve_snapshot(row)
    body = res.pop("_body", "")
    assertion_present = bool(snippet) and snippet in body if body else False
    if not res["resolved"]:
        sclass = "UNRESOLVED"
    elif not assertion_present:
        sclass = "ASSERTION-ABSENT"
    else:
        sclass = support_class(
            citing, snippet, row["claim_id"], row["source_id"]
        )
    supporting = sclass == "SUPPORTING"
    non_supporting = sclass != "SUPPORTING"
    rec = {
        "citation_id": row["citation_id"],
        "claim_id": row["claim_id"],
        "claim_verdict": row["claim_verdict"],
        "source_id": row["source_id"],
        "kind": row["kind"],
        "citing_sentence": citing,
        "cited_text": snippet,
        "final_url": row.get("final_url"),
        "permalink": row.get("permalink"),
        "fetched_at": row.get("fetched_at"),
        "declared_sha256": row.get("declared_sha256"),
        "resolve": res,
        "resolved": bool(res["resolved"]),
        "assertion_present": assertion_present,
        "support_class": sclass,
        "supporting": supporting,
        "non_supporting": non_supporting,
    }
    if non_supporting:
        rec["non_supporting_quotes"] = {
            "citing_sentence": citing,
            "cited_text": snippet,
        }
    return rec


def apply_injections(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    by_claim = {c["id"]: c for c in mutant["claims"]}
    for inj in INJECTIONS:
        claim = by_claim[inj["claim_id"]]
        found = False
        for src in claim["source_lineage"]:
            if src.get("id") == inj["source_id"]:
                found = True
                if inj["mode"] == "quote-absent":
                    src["snippet"] = ABSENT_QUOTE
                elif inj["mode"] == "unresolved":
                    src["sha256"] = FAKE_SHA
                    src["snapshot"] = FAKE_SNAP
                    src["http_status"] = 404
                elif inj["mode"] == "topical-adjacent":
                    src["snippet"] = TOPICAL_SPAN
                break
        if not found:
            raise KeyError(f"injection target missing: {inj}")
    return mutant


def rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        raise ValueError("census empty")
    n_res = sum(1 for r in rows if r["resolved"])
    n_assert = sum(1 for r in rows if r["assertion_present"])
    n_sup = sum(1 for r in rows if r["supporting"])
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["support_class"]] = by_class.get(r["support_class"], 0) + 1
    return {
        "n_citations": n,
        "n_resolved": n_res,
        "n_assertion_present": n_assert,
        "n_supporting": n_sup,
        "n_non_supporting": n - n_sup,
        "by_class": by_class,
        "fraction_resolve": n_res / n,
        "fraction_assertion_present": n_assert / n,
        "fraction_supporting": n_sup / n,
        "fraction_assertion_present_given_resolved": (
            n_assert / n_res if n_res else None
        ),
        "fraction_supporting_given_resolved": (n_sup / n_res if n_res else None),
        "sampled": False,
        "double_counted_rails": False,
    }


def audit_document(doc: dict[str, Any]) -> dict[str, Any]:
    extracted = extract_citations(doc)
    audited = [audit_one(r) for r in extracted]
    n_rails = sum(len(c.get("rails") or []) for c in doc.get("claims") or [])
    return {
        "source_unit_id": doc.get("unit_id") or doc.get("id"),
        "source_path": SOURCE_REL,
        "census_field": "claims[].source_lineage",
        "rails_duplicate_count": n_rails,
        "citations": audited,
        "rates": rates(audited),
    }


def injection_hits(audited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits = []
    by_id = {r["citation_id"]: r for r in audited}
    for inj in INJECTIONS:
        cid = f"{inj['claim_id']}#{inj['source_id']}"
        row = by_id.get(cid)
        got = row["support_class"] if row else "MISSING"
        caught = got == inj["expect_class"]
        hits.append(
            {
                "injection_id": inj["id"],
                "citation_id": cid,
                "mode": inj["mode"],
                "expect_class": inj["expect_class"],
                "got_class": got,
                "caught": caught,
            }
        )
    return hits


def detector_control(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = apply_injections(doc)
    result = audit_document(mutant)
    hits = injection_hits(result["citations"])
    missed = [h for h in hits if not h["caught"]]
    return {
        "n_injected": len(INJECTIONS),
        "n_caught": sum(1 for h in hits if h["caught"]),
        "all_caught": not missed,
        "missed": missed,
        "hits": hits,
        "support_rate_is_upper_bound": bool(missed),
        "mutant_rates": result["rates"],
    }


def run_audit() -> dict[str, Any]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE_REL)
    src_sha, src_bytes = sha256_file(SOURCE)
    doc = load_source()
    live = audit_document(doc)
    control = detector_control(doc)
    return {
        "source": {
            "path": SOURCE_REL,
            "unit_id": doc.get("unit_id"),
            "state": doc.get("state"),
            "sha256": src_sha,
            "bytes": src_bytes,
            "n_claims": len(doc.get("claims") or []),
        },
        "audit": live,
        "detector_control": control,
    }


def compact_citation(row: dict[str, Any]) -> dict[str, Any]:
    keep = {
        k: row[k]
        for k in (
            "citation_id",
            "claim_id",
            "claim_verdict",
            "source_id",
            "kind",
            "citing_sentence",
            "cited_text",
            "final_url",
            "permalink",
            "fetched_at",
            "declared_sha256",
            "resolved",
            "assertion_present",
            "support_class",
            "supporting",
            "non_supporting",
        )
        if k in row
    }
    keep["resolve"] = {
        k: row["resolve"][k]
        for k in (
            "snapshot_rel",
            "snapshot_present",
            "live_sha256",
            "live_bytes",
            "sha_match",
            "capture_http_200",
            "lineage_complete",
            "searchable_chars",
            "resolved",
        )
        if k in row["resolve"]
    }
    if row.get("non_supporting_quotes"):
        keep["non_supporting_quotes"] = row["non_supporting_quotes"]
    return keep
