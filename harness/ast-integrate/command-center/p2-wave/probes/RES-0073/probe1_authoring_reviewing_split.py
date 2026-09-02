#!/usr/bin/env python3
"""Probe 1: authoring-versus-reviewing split, sample size, named selection bias."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0073-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sample = doc.get("sample") or {}
    n_tools = int(sample.get("n_tools") or 0)
    print(f"n_tools={n_tools}")
    if n_tools != 5:
        return fail(f"sample size n_tools={n_tools} expected 5 dual-surface tools")
    tools = sample.get("tools") or []
    ids = [t.get("id") for t in tools if isinstance(t, dict)]
    if len(ids) != 5 or len(set(ids)) != 5:
        return fail(f"tool ids not 5 unique: {ids}")
    bias = str(sample.get("selection_bias") or "")
    bias_name = str(sample.get("selection_bias_name") or "")
    print(f"selection_bias_name={bias_name}")
    if "english-public-git-and-forum-complainers" not in bias_name:
        return fail("selection bias not named")
    if "over-represents" not in bias or "probability sample" not in bias:
        return fail("selection bias text does not name the obvious skew")
    avr = doc.get("authoring_versus_reviewing") or {}
    auth = avr.get("authoring") or {}
    rev = avr.get("reviewing") or {}
    print(
        "authoring_claims="
        f"{auth.get('n_claims')} reviewing_claims={rev.get('n_claims')} "
        f"answer_differs={avr.get('answer_differs')}"
    )
    if int(auth.get("n_claims") or 0) < 1:
        return fail("authoring evidence bucket empty")
    if int(rev.get("n_claims") or 0) < 1:
        return fail("reviewing evidence bucket empty")
    if avr.get("answer_differs") is not True:
        return fail("answer_differs is not true")
    why = str(avr.get("answer_differs_because") or "")
    if "authoring" not in why.lower() or "review" not in why.lower():
        return fail("split explanation does not discuss both activities")
    claims = doc.get("claims") or []
    auth_ids = set(auth.get("claim_ids") or [])
    rev_ids = set(rev.get("claim_ids") or [])
    if auth_ids & rev_ids:
        return fail(f"claim ids overlap authoring and reviewing: {auth_ids & rev_ids}")
    by_id = {c.get("claim_id"): c for c in claims if isinstance(c, dict)}
    for cid in auth_ids:
        row = by_id.get(cid) or {}
        if row.get("activity") != "authoring" or not row.get("cited_as_measured_fact"):
            return fail(f"{cid} is not surviving authoring evidence")
    for cid in rev_ids:
        row = by_id.get(cid) or {}
        if row.get("activity") != "reviewing" or not row.get("cited_as_measured_fact"):
            return fail(f"{cid} is not surviving reviewing evidence")
    if int(sample.get("n_authoring_surviving_claims") or -1) != len(auth_ids):
        return fail("sample.n_authoring_surviving_claims mismatch")
    if int(sample.get("n_reviewing_surviving_claims") or -1) != len(rev_ids):
        return fail("sample.n_reviewing_surviving_claims mismatch")
    print("split_ok=True sample_size=5 bias_named=True")
    print("SUCCESS:RES-0073-probe1 authoring-versus-reviewing split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
