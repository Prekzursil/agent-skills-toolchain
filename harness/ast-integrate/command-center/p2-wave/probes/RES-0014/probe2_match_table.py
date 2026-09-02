#!/usr/bin/env python3
"""Probe 2: matched-issue table — discriminator per row; two rails; keyword-only excluded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import load_corpus  # noqa: E402
from digest import digest_file  # noqa: E402
from search import classify  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0014.json"
# Catalog output_schema is a generated shim ($ref only, empty required).
# Discriminating contract is unit-local — do not rebuild the shared family.
SCHEMA = HERE / "research-registry.schema.json"
CATALOG_SCHEMA = (
    REPO / "command-center" / "schema" / "research-registry.schema.json"
)

FORBIDDEN_MATCH_NUMBERS = {81551, 86809, 39468, 999001}


def _schema_required() -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return list(schema.get("required") or [])


def _missing_required(doc: dict, required: list[str]) -> list[str]:
    return [k for k in required if k not in doc]


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0014-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0014-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:RES-0014" not in text:
        print("FAILED:RES-0014-probe2 sentinel absent")
        return 1
    if "matched-issue table" not in text.lower() and "matched_issues" not in doc:
        print("FAILED:RES-0014-probe2 table absent")
        return 1

    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:RES-0014-probe2 unit-local schema missing")
        return 1
    if not CATALOG_SCHEMA.is_file():
        print("FAILED:RES-0014-probe2 catalog schema path missing")
        return 1
    required = _schema_required()
    missing = _missing_required(doc, required)
    if missing:
        print("FAILED:RES-0014-probe2 schema required missing", missing)
        return 1
    if not _missing_required({}, required):
        print("FAILED:RES-0014-probe2 schema silent on garbage")
        return 1

    rows = doc.get("matched_issues") or []
    if len(rows) < 3:
        print(f"FAILED:RES-0014-probe2 too few match rows {len(rows)}")
        return 1

    for row in rows:
        obs = str(row.get("discriminating_observation") or "").strip()
        if len(obs) < 40:
            print("FAILED:RES-0014-probe2 short discriminator", row.get("issue_ref"))
            return 1
        title = str(row.get("title") or "")
        if obs == title:
            print("FAILED:RES-0014-probe2 discriminator is title", row.get("issue_ref"))
            return 1
        up = str(row.get("upstream_reproduction") or "")
        loc = str(row.get("local_reproduction") or "")
        if len(up) < 24 or len(loc) < 24:
            print("FAILED:RES-0014-probe2 missing reproductions", row.get("issue_ref"))
            return 1
        if row.get("verdict") not in {"SAME-MECHANISM", "SAME-SYMPTOM"}:
            print("FAILED:RES-0014-probe2 verdict", row.get("issue_ref"), row.get("verdict"))
            return 1
        n = row.get("number")
        if n in FORBIDDEN_MATCH_NUMBERS:
            print("FAILED:RES-0014-probe2 forbidden match", n)
            return 1
        rails = row.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if "structured-api" not in kinds or "prose-html" not in kinds:
            print("FAILED:RES-0014-probe2 two rails missing", row.get("issue_ref"), kinds)
            return 1
        for rail in rails:
            rel = rail.get("path")
            sha = rail.get("sha256")
            if not rel or not sha:
                print("FAILED:RES-0014-probe2 rail incomplete", row.get("issue_ref"))
                return 1
            path = REPO / rel
            if not path.is_file():
                print("FAILED:RES-0014-probe2 rail file missing", rel)
                return 1
            live_sha, _ = digest_file(path)
            if live_sha != sha:
                print("FAILED:RES-0014-probe2 rail sha mismatch", rel)
                return 1
            if int(rail.get("http_status") or 0) != 200:
                print("FAILED:RES-0014-probe2 rail http", rel)
                return 1

    live = classify(load_corpus())
    live_refs = sorted(m["issue_ref"] for m in live["matches"])
    art_refs = sorted(m["issue_ref"] for m in rows)
    if live_refs != art_refs:
        print("FAILED:RES-0014-probe2 match set drifted", live_refs, art_refs)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-match-table",
                "unit_id": "RES-0014",
                "pass": True,
                "match_rows": len(rows),
                "same_mechanism": sum(1 for r in rows if r["verdict"] == "SAME-MECHANISM"),
                "same_symptom": sum(1 for r in rows if r["verdict"] == "SAME-SYMPTOM"),
                "schema_rejects_garbage": True,
                "forbidden_excluded": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"rows={len(rows)} discriminators=all rails=ok forbidden_excluded=True "
        "schema_rejects_garbage=True"
    )
    print("SUCCESS:RES-0014-probe2 matched-issue table discriminating observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
