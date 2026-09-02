#!/usr/bin/env python3
"""Probe 2: dual-rail evidence, live capture hashes, API order inequality, local contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

COUNT_FIELDS = {"download_count", "downloads", "downloadCount", "installs", "install_count"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0060-probe2 {msg}")
    return 1


def rail_body(rail: dict) -> str:
    path = C.REPO / str(rail["path"]).replace("\\", "/")
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    art_path = C.REPO / C.OUT_REL
    if not art_path.is_file():
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")

    claims = doc.get("claims") or []
    if len(claims) < 4:
        return fail("too few claims")
    measured = 0
    for claim in claims:
        cid = str(claim.get("id") or "")
        tier = str(claim.get("evidence_tier") or "")
        rails = claim.get("rails") or []
        if not isinstance(rails, list) or not rails:
            return fail(f"{cid} has no rails")
        kinds = [str(r.get("kind") or "") for r in rails if isinstance(r, dict)]
        if tier == "E1":
            if len(rails) < 2:
                return fail(f"{cid} E1 with <2 rails")
            if not ({"api", "prose"} <= set(kinds)):
                return fail(f"{cid} E1 missing api+prose kinds {kinds}")
            if claim.get("measured_fact") is not True:
                return fail(f"{cid} E1 not marked measured_fact")
            measured += 1
        elif tier == "E3":
            if claim.get("measured_fact") is True:
                return fail(f"{cid} E3 cited as measured fact")
        for rail in rails:
            if not isinstance(rail, dict):
                return fail(f"{cid} rail not object")
            span = str(rail.get("quoted_span") or "")
            if len(span) < 8:
                return fail(f"{cid} quoted_span too short")
            body = rail_body(rail)
            if span not in body:
                return fail(f"{cid} quoted_span not in {rail.get('path')}")
            live_sha, live_n = C.digest_file(C.REPO / str(rail["path"]).replace("\\", "/"))
            if live_sha != str(rail.get("sha256") or ""):
                return fail(f"{cid} rail sha256 mismatch {rail.get('path')}")
            if int(rail.get("http_status") or 0) != 200:
                return fail(f"{cid} rail http_status {rail.get('http_status')}")
            if live_n <= 0:
                return fail(f"{cid} empty rail body")

    if measured < 5:
        return fail(f"too few measured E1 claims n={measured}")

    rel = C.vscode_ranked_ids("vscode-api-sort-relevance")
    ins = C.vscode_ranked_ids("vscode-api-sort-installs")
    rel_n = C.vscode_installs("vscode-api-sort-relevance")
    ins_n = C.vscode_installs("vscode-api-sort-installs")
    if len(rel) < 5 or len(ins) < 5:
        return fail("vscode API lists too short")
    if rel == ins:
        return fail("relevance order equals install order")
    if ins_n != sorted(ins_n, reverse=True):
        return fail("install sort is not descending install counts")
    obs = {}
    for claim in claims:
        if claim.get("id") == "C-VS-DEFAULT-NEQ-INSTALLS":
            obs = claim.get("observation") or {}
    if obs.get("relevance_top8") != rel or obs.get("installs_top8") != ins:
        return fail("artifact observation does not match live capture order")
    if obs.get("orders_equal") is not False:
        return fail("observation.orders_equal is not False")

    jb_html = C.capture_text("jetbrains-docs-ranking")
    if "log10(1 + 5 * downloads_count)" not in jb_html:
        return fail("jetbrains formula absent from ranking docs")
    jb_api = C.capture_text("jetbrains-api-search")
    if '"downloads":' not in jb_api:
        return fail("jetbrains API missing downloads field")

    src = C.capture_text("pypi-warehouse-search-source")
    if "SEARCH_FIELDS = [" not in src:
        return fail("pypi SEARCH_FIELDS missing")
    start = src.index("SEARCH_FIELDS = [")
    end = src.index("]", start)
    fields_blob = src[start:end]
    for bad in COUNT_FIELDS:
        if bad in fields_blob:
            return fail(f"pypi SEARCH_FIELDS contains count field {bad}")
    if "download_url" not in fields_blob:
        return fail("pypi SEARCH_FIELDS missing expected download_url URL field")

    unit = C.catalog_unit("IMP-0102")
    target = str(unit.get("question_or_target") or "")
    if "with no popularity term" not in target:
        return fail("IMP-0102 contract missing no-popularity term")
    fixture = json.loads(
        (C.REPO / "tools/marketplace/fixture/registry/index.json").read_text(encoding="utf-8")
    )
    keys = {k.lower() for k in C.nested_keys(fixture)}
    overlap = keys & {k.lower() for k in C.POPULARITY_KEYS}
    if overlap:
        return fail(f"fixture has popularity keys {sorted(overlap)}")

    index = C.load_index()
    if len(index) < 10:
        return fail("capture index too small")
    for row in index:
        p = C.REPO / str(row["path"]).replace("\\", "/")
        if not p.is_file() or p.stat().st_size <= 0:
            return fail(f"capture missing {row.get('id')}")
        if row.get("http_status") != 200:
            return fail(f"capture not HTTP 200 {row.get('id')}")

    print(
        f"e1_measured={measured} vscode_rel!={ins[:3]} vs {rel[:3]} "
        f"installs_desc={ins_n[:3]}"
    )
    print("SUCCESS:RES-0060-probe2 dual-rail and API control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
