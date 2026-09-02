#!/usr/bin/env python3
"""Probe 2: evidence gate — E3 cannot promote; baseline strip goes red.

Promoted mechanisms must carry DOI (or arXiv), section/figure, effect size,
AND baseline. Adversarial reviewer default is REFUTED; every CONFIRMED claim
states its strongest caveat. Anchors resolve to file:line.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

ART = REPO / C.OUT_REL


def resolve_anchor(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{rel}:{line} out of range"
    if snippet not in lines[line - 1] and snippet not in "\n".join(
        lines[max(0, line - 2) : line + 1]
    ):
        return False, f"{rel}:{line} snippet miss"
    return True, f"{rel}:{line}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0111-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        print("FAILED:RES-0111-probe2 sentinel absent")
        return 1

    mechs = doc.get("mechanisms") or []
    if len(mechs) < 1:
        print("FAILED:RES-0111-probe2 no promoted mechanisms")
        return 1
    for m in mechs:
        row = {
            "promoted": True,
            "decision": "MAPPED",
            "evidence_tier": m.get("evidence_tier") or "E2",
            "doi": m.get("doi"),
            "section_or_figure": m.get("section_or_figure"),
            "effect_size": m.get("effect_size"),
            "baseline": m.get("baseline"),
            "failure_class_id": m.get("failure_class_id"),
        }
        ok, why = C.promoted_ok(row)
        print(f"promoted {m.get('primitive')} ok={ok} {why}")
        if not ok:
            print("FAILED:RES-0111-probe2 promoted row failed gate")
            return 1
        mutant = copy.deepcopy(row)
        mutant["baseline"] = None
        mok, mwhy = C.promoted_ok(mutant)
        print(f"  baseline-stripped ok={mok} {mwhy}")
        if mok:
            print("FAILED:RES-0111-probe2 baseline-stripped still promoted")
            return 1

    e3 = doc.get("e3_records") or []
    if len(e3) < 1:
        print("FAILED:RES-0111-probe2 no E3 records")
        return 1
    e3_prims = {r.get("primitive") for r in e3}
    if "fencing tokens" not in e3_prims:
        print("FAILED:RES-0111-probe2 fencing tokens not graded E3")
        return 1
    promo_prims = {m.get("primitive") for m in mechs}
    overlap = e3_prims & promo_prims
    if overlap:
        print(f"FAILED:RES-0111-probe2 E3 also promoted {overlap}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:RES-0111-probe2 reviewer not independent")
        return 1
    if rev.get("default") != "REFUTED":
        print("FAILED:RES-0111-probe2 reviewer default is not REFUTED")
        return 1

    claims = doc.get("claims") or []
    refuted = [c for c in claims if c.get("verdict") == "REFUTED"]
    confirmed = [c for c in claims if c.get("verdict") == "CONFIRMED"]
    if len(refuted) < 1:
        print("FAILED:RES-0111-probe2 no REFUTED claims (reviewer was not adversarial)")
        return 1
    for c in confirmed:
        if not str(c.get("strongest_caveat") or "").strip():
            print(f"FAILED:RES-0111-probe2 CONFIRMED {c.get('id')} missing caveat")
            return 1
    eos = next((c for c in claims if c.get("id") == "C-EOS-MAP"), None)
    if eos is None or eos.get("verdict") != "REFUTED":
        print("FAILED:RES-0111-probe2 exactly-once overclaim not REFUTED")
        return 1

    for i, row in enumerate(doc.get("evidence") or []):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = resolve_anchor(rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:RES-0111-probe2 unresolved evidence anchor")
            return 1

    schema_path = HERE / "research-claim-record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.validate(doc, schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    rejected = False
    try:
        jsonschema.validate(garbage, schema)
    except jsonschema.ValidationError:
        rejected = True
    print(f"schema_rejects_garbage={rejected}")
    if not rejected:
        print("FAILED:RES-0111-probe2 schema accepts garbage")
        return 1

    print("SUCCESS:RES-0111-probe2 evidence gate, E3-cannot-promote, reviewer default REFUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
