#!/usr/bin/env python3
"""Discriminating contract for RES-0140 measurement-run."""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SENTINEL = "SUCCESS:RES-0140"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UID = "RES-0140"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
BANDS = frozenset(
    {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}
)


def fail(why: str) -> tuple[bool, str]:
    return False, why


def check(doc: object, repo: Path | None = None) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return fail("not-object")
    if str(doc.get("unit_id") or "") != UID:
        return fail("unit_id")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if st != "SUCCESS":
        return fail(f"state:{st}")
    if SENTINEL not in str(doc.get("sentinel") or "") and SENTINEL not in str(doc):
        return fail("sentinel-absent")
    if str(doc.get("report_kind") or "") != "measurement-run":
        return fail("report_kind")
    if int(doc.get("sample_size") or 0) != 20:
        return fail("sample-size")
    items = doc.get("per_item") or []
    if not isinstance(items, list) or len(items) != 20:
        return fail("per_item-count")
    ids = [i.get("id") for i in items if isinstance(i, dict)]
    if len(set(ids)) != 20:
        return fail("per_item-ids")
    classes = {}
    subjects = {}
    rest = []
    for it in items:
        if not isinstance(it, dict):
            return fail("per_item-row")
        sc = it.get("source_class")
        classes[sc] = classes.get(sc, 0) + 1
        subjects.setdefault(it.get("subject"), set()).add(sc)
        if it.get("role") == "restatement-control":
            rest.append(it)
        if int(it.get("tokens_consumed") or 0) < 1:
            return fail(f"tokens:{it.get('id')}")
        if it.get("tokenizer_ne_chars_div_4") is not True:
            return fail(f"chars-div-4:{it.get('id')}")
        lin = it.get("lineage") or {}
        if not isinstance(lin, dict):
            return fail("lineage")
        if not SHA_RE.match(str(lin.get("sha256") or "")):
            return fail(f"lineage-sha:{it.get('id')}")
        if not lin.get("fetch_timestamp"):
            return fail(f"lineage-ts:{it.get('id')}")
        if not lin.get("resolved_url"):
            return fail(f"lineage-url:{it.get('id')}")
        if not lin.get("independent_verification_path"):
            return fail(f"lineage-verify:{it.get('id')}")
        if repo is not None:
            cap = lin.get("capture_path")
            if not cap:
                return fail(f"capture-path:{it.get('id')}")
            p = repo / str(cap)
            if not p.is_file():
                return fail(f"capture-missing:{cap}")
    if classes.get("official-docs") != 6 or classes.get("blog-post") != 6:
        return fail(f"class-counts:{classes}")
    if classes.get("transcript") != 8:
        return fail(f"transcript-count:{classes}")
    if len(rest) != 2:
        return fail("restatement-count")
    for subj, have in subjects.items():
        if "official-docs" in have and "blog-post" in have and "transcript" not in have:
            return fail(f"subject-missing-transcript:{subj}")
    ctrl = doc.get("restatement_control") or {}
    if not isinstance(ctrl, dict) or ctrl.get("both_collapse") is not True:
        return fail("restatement-did-not-collapse")
    if int(ctrl.get("n") or 0) != 2:
        return fail("restatement-n")
    for row in ctrl.get("rows") or []:
        if int(row.get("unique_after_collapse", 1)) != 0:
            return fail(f"restatement-unique:{row.get('transcript_id')}")
        if int(row.get("inflated_if_undeduped") or 0) < 1:
            return fail("restatement-empty-inflated")
    tok = doc.get("tokenizer") or {}
    if tok.get("pin") != "res-0140-gpt2-regex-unigram/v1":
        return fail("tokenizer-pin")
    if tok.get("not_chars_div_4") is not True:
        return fail("tokenizer-flag")
    two = doc.get("two_signal") or {}
    if two.get("every_item_tokenizer_ne_chars_div_4") is not True:
        return fail("two-signal-chars4")
    if two.get("tokens_ne_bytes") is not True:
        return fail("two-signal-bytes")
    th = doc.get("threshold") or {}
    if th.get("id") != "T-DEFAULT-SOURCE-CLASS-2026-08-24":
        return fail("threshold-id")
    if "stay_in_default_source_class_set" not in th:
        return fail("threshold-verdict-absent")
    cmp_ = doc.get("comparison") or {}
    for key in (
        "transcript_incremental_honest_per_10k",
        "official_docs_incremental_per_10k",
        "blog_incremental_per_10k",
        "transcript_intra_inflated_per_10k",
    ):
        if key not in cmp_:
            return fail(f"comparison-missing:{key}")
    inflated = float(cmp_["transcript_intra_inflated_per_10k"])
    honest = float(cmp_["transcript_incremental_honest_per_10k"])
    # Inflated restatement-inclusive intra yield must exceed honest incremental
    # yield, proving that counting restatements inflates the figure.
    if inflated <= honest:
        return fail("inflation-not-demonstrated")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 2:
        return fail("claims")
    measured = [c for c in claims if c.get("cited_as_measured_fact")]
    if len(measured) < 2:
        return fail("measured-facts")
    for c in measured:
        rails = c.get("source_lineage") or []
        if not isinstance(rails, list) or len(rails) < 2:
            return fail(f"single-rail:{c.get('id')}")
        band = str(c.get("sherman_kent_band") or "")
        if band not in BANDS:
            return fail(f"band:{c.get('id')}")
        if c.get("evidence_tier") not in {"E1", "E2"}:
            return fail(f"tier:{c.get('id')}")
    for c in claims:
        if c.get("evidence_tier") == "E3" and c.get("cited_as_measured_fact"):
            return fail(f"e3-as-fact:{c.get('id')}")
        band = str(c.get("sherman_kent_band") or "")
        if band not in BANDS:
            return fail(f"band:{c.get('id')}")
    if not str(doc.get("answer") or "") or len(str(doc.get("answer"))) < 80:
        return fail("answer-thin")
    return True, "ok"
