#!/usr/bin/env python3
"""Probe 2: recorded triple is CHALLENGED; mutants drop to UNCHALLENGED; recount.

Both-states: the live classifier must fire on a recorded query+result_set+verdict
and stay silent when any one of those three is removed. Independent recount of
command-center/research/**/*.json claims arrays must match the artifact.
Reviewer defaults to REFUTED if evidence is insufficient.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import CHALLENGED, UNCHALLENGED, classify  # noqa: E402
from contract import OUT_REL, SCHEMA_REL, SENTINEL, UNIT  # noqa: E402
from controls import CAVEAT_ONLY, HOWEVER_ONLY, RECORDED_TRIPLE  # noqa: E402
from inventory import load_population  # noqa: E402
import lineage as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def drop(obj: dict, key: str) -> dict:
    out = copy.deepcopy(obj)
    rec = out.get("counterevidence_search")
    if isinstance(rec, dict) and key in rec:
        rec.pop(key)
    return out


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact-missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text and f"SUCCESS:{UNIT}" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return fail(f"schema:{exc.message}")

    pos = classify(RECORDED_TRIPLE)
    however = classify(HOWEVER_ONLY)
    caveat = classify(CAVEAT_ONLY)
    no_query = classify(drop(RECORDED_TRIPLE, "query"))
    no_results = classify(drop(RECORDED_TRIPLE, "result_set"))
    no_verdict = classify(drop(RECORDED_TRIPLE, "verdict"))
    print(
        f"recorded={pos['status']} however={however['status']} caveat={caveat['status']} "
        f"drop_query={no_query['status']} drop_results={no_results['status']} "
        f"drop_verdict={no_verdict['status']}"
    )
    if pos["status"] != CHALLENGED:
        return fail("recorded-triple-not-challenged")
    if however["status"] != UNCHALLENGED:
        return fail("however-not-unchallenged")
    if caveat["status"] != UNCHALLENGED:
        return fail("caveat-only-not-unchallenged")
    if no_query["status"] != UNCHALLENGED:
        return fail("drop-query-still-challenged")
    if no_results["status"] != UNCHALLENGED:
        return fail("drop-result_set-still-challenged")
    if no_verdict["status"] != UNCHALLENGED:
        return fail("drop-verdict-still-challenged")

    live = load_population(REPO)
    cov = doc.get("coverage") or {}
    if live["n"] != cov.get("population_n"):
        return fail(f"population-drift live={live['n']} art={cov.get('population_n')}")
    if live["challenged_n"] != cov.get("challenged_n"):
        return fail("challenged-n-drift")
    if live["unchallenged_n"] != cov.get("unchallenged_n"):
        return fail("unchallenged-n-drift")
    if not live["extractor_agreement"]["agree"]:
        return fail("extractor-disagreement")
    art_ids = {r.get("id") for r in (doc.get("conclusions") or [])}
    live_ids = {r["id"] for r in live["conclusions"]}
    if art_ids != live_ids:
        return fail(f"conclusion-id-drift extra={sorted(art_ids - live_ids)[:4]} missing={sorted(live_ids - art_ids)[:4]}")
    for row in live["conclusions"]:
        if row["status"] != "UNCHALLENGED" and row["status"] != "CHALLENGED":
            return fail(f"bad-status {row['id']}")

    # Artifact must not mix labeled controls into the coverage fraction.
    labeled_ids = {HOWEVER_ONLY["id"], RECORDED_TRIPLE["id"], CAVEAT_ONLY["id"]}
    mixed = labeled_ids & live_ids
    if mixed:
        return fail(f"controls-mixed-into-population {mixed}")

    if not (doc.get("challenge_rule") or "").strip():
        return fail("challenge-rule-unstated")

    claims = doc.get("claims") or []
    if len(claims) < 3:
        return fail("claims-short")
    for claim in claims:
        if claim.get("verdict") not in {"CONFIRMED", "REFUTED", "PARTIAL", "INFERRED"}:
            return fail(f"verdict-{claim.get('id')}")
        sigs = claim.get("signals") or []
        if len(sigs) < 2:
            return fail(f"single-signal-{claim.get('id')}")
        urls = {s.get("url") for s in sigs}
        if len(urls) < 2:
            return fail(f"dependent-urls-{claim.get('id')}")
        for s in sigs:
            sha = s.get("sha256")
            snip = s.get("snippet")
            path = s.get("path")
            cid = s.get("capture_id")
            if not sha or not snip:
                return fail(f"incomplete-signal-{claim.get('id')}")
            if cid in L.CAPTURES:
                cap = L.load_capture(cid)
                if cap["sha256"] != sha:
                    return fail(f"capture-sha-drift-{cid}")
                if snip not in cap["text"]:
                    return fail(f"capture-snippet-{cid}")
            elif path:
                p = REPO / path
                if not p.is_file():
                    return fail(f"signal-path-missing {path}")
                live_sha, _, raw = L.digest_file(p)
                if live_sha != sha:
                    return fail(f"file-sha-drift {path}")
                if snip.encode("utf-8") not in raw and snip not in raw.decode("utf-8", errors="replace"):
                    return fail(f"file-snippet {path}")

    revs = doc.get("reviewers") or []
    if not revs:
        return fail("reviewers-absent")
    for r in revs:
        if r.get("independent") is not True or r.get("default_to_refuted") is not True:
            return fail("reviewer-not-default-refuted")
        if r.get("verdict") != "PASS":
            return fail("reviewer-not-pass")

    if (doc.get("distinct_from") or {}).get("id") != "RES-0022":
        return fail("distinct-from-RES-0022-unstated")

    frac = cov.get("coverage_fraction")
    print(
        json.dumps(
            {
                "probe": "probe2-recorded-triple-and-recount",
                "unit_id": UNIT,
                "recorded_status": CHALLENGED,
                "mutants_unchallenged": True,
                "population_n": live["n"],
                "challenged_n": live["challenged_n"],
                "coverage_fraction": frac,
                "extractor_agree": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe2 recorded=CHALLENGED mutants=UNCHALLENGED "
        f"n={live['n']} challenged={live['challenged_n']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
