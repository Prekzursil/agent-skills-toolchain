#!/usr/bin/env python3
"""Probe 1: every census anchor resolves; FENCED requires the fence construct."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
from fence import BEGIN  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0049.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
NEED = {
    "fetched-web-pages",
    "mcp-tool-results",
    "marketplace-package-descriptions",
    "imported-workflow-definitions",
    "council-transcripts-and-participant-artifacts",
    "pr-and-issue-bodies",
    "repository-supplied-agent-config",
}


def main() -> int:
    live = C.census()
    ids = {r["id"] for r in live}
    if ids != NEED:
        print(f"FAILED:BLD-0049-probe1 ingress set {sorted(ids)}")
        return 1
    for r in live:
        site = r["production_site"]
        if r["production_concatenation"] == "ABSENT":
            if site is not None or r["production_fencing"] != "ABSENT-SITE":
                print("FAILED:BLD-0049-probe1 absent row misshapen", r)
                return 1
            continue
        rel, line = C.parse_site(site)
        got = C.line_text(rel, line)
        if r["snippet"] not in got and got.strip() != r["snippet"]:
            print(f"FAILED:BLD-0049-probe1 snippet drift {site} {got!r}")
            return 1
        has = C.site_has_fence(rel, line)
        if r["production_fencing"] == "FENCED" and not has:
            print(f"FAILED:BLD-0049-probe1 FENCED without construct {site}")
            return 1
        if r["production_fencing"] == "UNFENCED" and has:
            print(f"FAILED:BLD-0049-probe1 UNFENCED but fence present {site}")
            return 1
        if BEGIN in got and r["production_fencing"] != "FENCED":
            print(f"FAILED:BLD-0049-probe1 fence token on cited line {site}")
            return 1
    irel, iline = C.parse_site(live[0]["instrument_site"])
    if BEGIN not in C.line_text(irel, iline) and BEGIN not in (REPO / irel).read_text(encoding="utf-8"):
        print("FAILED:BLD-0049-probe1 instrument missing fence construct")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0049-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:BLD-0049-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0049" not in text:
        print("FAILED:BLD-0049-probe1 sentinel-absent")
        return 1
    rec_ids = [r["id"] for r in doc.get("ingresses") or []]
    if rec_ids != [r["id"] for r in live]:
        print(f"FAILED:BLD-0049-probe1 receipt ingresses {rec_ids}")
        return 1
    for live_row, rec in zip(live, doc["ingresses"]):
        if rec.get("production_site") != live_row["production_site"]:
            print("FAILED:BLD-0049-probe1 site mismatch", rec, live_row)
            return 1
        if rec.get("production_fencing") != live_row["production_fencing"]:
            print("FAILED:BLD-0049-probe1 fencing mismatch", rec)
            return 1
        if rec.get("production_fencing") == "FENCED":
            print("FAILED:BLD-0049-probe1 production FENCED overclaim")
            return 1
    schema_path = REPO / "command-center/schema/threat-coverage-matrix.schema.json"
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:BLD-0049-probe1 schema", errs[0].message)
        return 1
    garbage = jsonschema.Draft7Validator(schema).is_valid({"totally": "unrelated"})
    if garbage:
        print("FAILED:BLD-0049-probe1 schema vacuous")
        return 1
    print(
        f"ingresses={len(live)} present={sum(1 for r in live if r['production_concatenation']=='PRESENT')} "
        f"unfenced={sum(1 for r in live if r['production_fencing']=='UNFENCED')}"
    )
    print("SUCCESS:BLD-0049-probe1 census anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
