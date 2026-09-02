#!/usr/bin/env python3
"""Probe 1: ranking citation must be source file:line, not the blog."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / "command-center/research/RES-0028.json"
BLOG_MARKERS = ("aider.chat/2023/10/22", "blog description", "docs/repomap.html")


def fail(msg: str) -> int:
    print(f"FAILED:RES-0028-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:RES-0028" not in text:
        return fail("sentinel absent")

    loc = E.ranking_loci()
    live_citation = E.file_line_citation()
    ranking = doc.get("ranking_algorithm") or {}
    cited = str(ranking.get("cited_at_source_file_line") or "")
    print(f"live_snapshot_citation={live_citation}")
    print(f"artifact_citation={cited}")
    print(f"snapshot_line_text={loc['pagerank_primary_text']}")
    if cited != live_citation:
        return fail(f"citation drift artifact={cited} snapshot={live_citation}")
    if not cited.startswith("aider/repomap.py:"):
        return fail("ranking citation is not aider/repomap.py:LINE")
    if int(ranking.get("source_line") or 0) != loc["pagerank_primary_line"]:
        return fail("source_line does not match snapshot pagerank line")
    if "nx.pagerank" not in str(ranking.get("source_line_text") or ""):
        return fail("cited line text is not nx.pagerank")
    if ranking.get("not_a_blog_description") is not True:
        return fail("artifact did not mark ranking citation as source rather than blog")
    # Blog may be discussed elsewhere; it must not be the ranking locator.
    locator = cited.lower()
    if any(m in locator for m in BLOG_MARKERS):
        return fail("ranking locator is a blog/docs URL")
    fixture = (HERE / "fixtures" / "aider-repomap.py").read_text(encoding="utf-8")
    lines = fixture.splitlines()
    idx = loc["pagerank_primary_line"] - 1
    if idx < 0 or idx >= len(lines):
        return fail("pagerank line out of range")
    if "nx.pagerank" not in lines[idx]:
        return fail("frozen snapshot line is not nx.pagerank")
    claims = {c["claim_id"]: c for c in (doc.get("claims") or [])}
    m1 = claims.get("RES-0028-M1-PAGERANK-SYMBOL-GRAPH")
    if not m1:
        return fail("pagerank mechanism claim missing")
    if live_citation not in str(m1.get("statement") or ""):
        return fail("M1 statement dropped the file:line citation")
    lineage = m1.get("source_lineage") or {}
    if int(lineage.get("http_status") or 0) != 200:
        return fail("M1 source_lineage http_status not 200")
    if lineage.get("sha256") != loc["sha256"]:
        return fail("M1 source_lineage sha256 != frozen snapshot")
    tests = {t["id"]: t for t in (doc.get("tests") or [])}
    if tests.get("T1", {}).get("blog_rejected_as_ranking_citation") is not True:
        return fail("T1 did not reject the blog as the ranking citation")
    print("ranking_is_source_file_line=True blog_not_used_as_locator=True")
    print("SUCCESS:RES-0028-probe1 ranking cited at source file:line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
