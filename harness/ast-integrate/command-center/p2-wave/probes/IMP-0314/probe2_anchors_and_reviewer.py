#!/usr/bin/env python3
"""Probe 2: independent reviewer from the tests; stat every cited path/URL.

Starts from the six-shape tests, not an author summary. Re-imports the
production module. Every cited file path is stated; missing paths remain in
the report. http(s) URLs are parsed, not fetched. A document-level mutant
must FIRE on legit-cross-ref while production stays SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.artifacts import evidence_map as M  # noqa: E402
import fixtures as F  # noqa: E402

PROD = REPO / "tools/council/artifacts/evidence_map.py"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0314-probe2 {msg}")
    return 1


def main() -> int:
    if not PROD.is_file():
        return _fail("production module missing")
    src = PROD.read_text(encoding="utf-8")
    if "distinct_url_count" in src and "CITE_KINDS" not in src:
        return _fail("module looks like a URL counter")
    if "CITE_KINDS" not in src or "NOT-CHECKED" not in src:
        return _fail("production module missing cite-kind cycle detector")

    F.dump_json()
    reports = {fid: M.analyse(doc, repo=REPO) for fid, doc in F.all_shapes().items()}
    missing_doc = F.missing_path()
    missing_rep = M.analyse(missing_doc, repo=REPO)

    rerun_fire = all(reports[i]["status"] == "FIRE" for i in F.FIRE_IDS)
    rerun_silent = all(reports[i]["status"] == "SILENT" for i in F.SILENT_IDS)
    print(f"reviewer_rerun_fire={rerun_fire} reviewer_rerun_silent={rerun_silent}")
    if not rerun_fire or not rerun_silent:
        return _fail("reviewer six-shape re-run failed")

    fires = sum(1 for i in F.SILENT_IDS if reports[i]["fired"])
    rate = fires / len(F.SILENT_IDS)
    if not isinstance(rate, float) or rate != 0.0:
        return _fail(f"reviewer FPR not 0.0 (got {rate!r})")
    print(f"reviewer_false_positive_rate={rate}")

    legit = F.legit_cross_ref()
    if not M.naive_document_cycle_fires(legit):
        return _fail("mutant document-cycle did not fire on legit-cross-ref")
    if reports["legit-cross-ref"]["fired"]:
        return _fail("production fired on distinct-fact cross-ref")
    print("reviewer_legit_cross_ref_distinguished=True")

    # Stat every cited file path; parse every URL.
    cited_paths = {F.FACT_A, F.FACT_B, F.MEAS, F.MISSING}
    stated_values = []
    for fid, doc in list(F.all_shapes().items()) + [("missing-path", missing_doc)]:
        anchors = (M.analyse(doc, repo=REPO).get("anchor_resolution") or {}).get("anchors") or []
        for row in anchors:
            stated_values.append(row)
            print(
                f"anchor fixture={fid} value={row.get('value')} "
                f"kind={row.get('kind')} present={row.get('present')} "
                f"stat_attempted={row.get('stat_attempted')} "
                f"fetched={row.get('fetched')}"
            )
            if row.get("kind") == "url" or str(row.get("value") or "").startswith(
                ("http://", "https://")
            ):
                if row.get("fetched") is True:
                    return _fail("http(s) URL was fetched")
                if row.get("scheme") not in {"http", "https"} and not str(
                    row.get("value") or ""
                ).startswith(("http://", "https://")):
                    return _fail(f"URL row missing scheme: {row}")
            if row.get("kind") == "path" or (
                row.get("stat_attempted") is True and row.get("kind") != "url"
            ):
                if row.get("stat_attempted") is not True:
                    return _fail(f"path not stated: {row.get('value')}")

    present_paths = {
        str(r.get("value"))
        for r in stated_values
        if r.get("present") is True and r.get("stat_attempted") is True
    }
    for rel in (F.FACT_A, F.FACT_B, F.MEAS):
        if rel not in present_paths:
            return _fail(f"did not stat present fixture {rel}")
        live = REPO / rel
        if not live.is_file():
            return _fail(f"fixture file missing on disk {rel}")

    missing_rows = [
        r
        for r in (missing_rep.get("anchor_resolution") or {}).get("anchors") or []
        if str(r.get("value")) == F.MISSING
    ]
    if not missing_rows:
        return _fail("missing path dropped from resolution report")
    if missing_rows[0].get("present") is not False:
        return _fail("missing path reported present")
    print(f"missing_path_reported present={missing_rows[0].get('present')}")

    claims = missing_rep.get("claims") or []
    if not claims:
        return _fail("missing-path fixture mapped zero claims")
    mapped = [c for c in claims if c.get("claim_id") == "claim-M"]
    if not mapped or mapped[0].get("anchor_count", 0) < 1:
        return _fail("claim-M not mapped to the missing-path anchor")

    linear = reports["linear"]
    claim_ids = {c["claim_id"] for c in linear.get("claims") or []}
    if "claim-L" not in claim_ids or "syn-L" not in claim_ids:
        return _fail(f"linear claims not mapped: {claim_ids}")
    claim_l = next(c for c in linear["claims"] if c["claim_id"] == "claim-L")
    if claim_l["unanchored"]:
        return _fail("claim-L unanchored; inbound evidence path should attach")

    url_rows = [
        r
        for r in stated_values
        if r.get("kind") == "url" or str(r.get("value") or "").startswith("https://")
    ]
    if len(url_rows) < 3:
        return _fail(f"expected parsed URLs on cyclic fixtures, got {len(url_rows)}")

    print("SUCCESS:IMP-0314-probe2 anchors-stated reviewer-from-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
