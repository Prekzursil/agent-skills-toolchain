#!/usr/bin/env python3
"""Probe 1: both translations attached; second path named and live-recomputed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from translate import PATH_INDEPENDENT, PATH_RECORDED, hedge_tag_transfer  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0073-multilingual-recheck.json"
SCHEMA = REPO / "command-center/schema/citation-audit.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0073-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0073":
        print("FAILED:CNF-0073-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0073" not in text:
        print("FAILED:CNF-0073-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0073-probe1 self-declared", doc.get("state"))
        return 1

    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0073-probe1 schema", errs[0].message)
        return 1

    paths = doc.get("translation_paths") or []
    names = [p.get("name") for p in paths]
    kinds = {p.get("name"): p.get("kind") for p in paths}
    if PATH_RECORDED not in names or PATH_INDEPENDENT not in names:
        print(f"FAILED:CNF-0073-probe1 paths not named {names}")
        return 1
    if kinds.get(PATH_RECORDED) == kinds.get(PATH_INDEPENDENT):
        print("FAILED:CNF-0073-probe1 path kinds are not mechanically different")
        return 1
    if not doc.get("second_path_named_and_different"):
        print("FAILED:CNF-0073-probe1 second_path_named_and_different false")
        return 1

    citations = doc.get("citations") or []
    if len(citations) < 2:
        print(f"FAILED:CNF-0073-probe1 citations={len(citations)}")
        return 1
    for row in citations:
        trans = row.get("translations") or []
        if len(trans) < 2:
            print(f"FAILED:CNF-0073-probe1 {row.get('id')} missing translations")
            return 1
        rec, indep = trans[0], trans[1]
        if rec.get("role") != "recorded" or indep.get("role") != "independent":
            print(f"FAILED:CNF-0073-probe1 {row.get('id')} roles {rec.get('role')} {indep.get('role')}")
            return 1
        if not rec.get("text") or not indep.get("text"):
            print(f"FAILED:CNF-0073-probe1 {row.get('id')} empty translation")
            return 1
        if rec.get("path_name") == indep.get("path_name"):
            print(f"FAILED:CNF-0073-probe1 {row.get('id')} same-path-rerun")
            return 1
        live = hedge_tag_transfer(row["original_span"], row.get("language"))
        if live != indep.get("text"):
            print(f"FAILED:CNF-0073-probe1 {row.get('id')} live second path drift")
            print(f"  artifact={indep.get('text')!r}")
            print(f"  live={live!r}")
            return 1
        print(
            f"{row['id']} paths={rec['path_name']!r}->{indep['path_name']!r} "
            f"live_match=True verdict={row.get('verdict')}"
        )
    print(f"citations={len(citations)} second_path={PATH_INDEPENDENT}")
    print("SUCCESS:CNF-0073-probe1 second path named different live-recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
