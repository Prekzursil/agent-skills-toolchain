#!/usr/bin/env python3
"""Probe 2: two-rail evidence, capture rehash, E-tier mutation control."""
from __future__ import annotations

import copy
import json
import sys

import lib as L


def fail(msg: str) -> int:
    print(f"FAILED:RES-0064-probe2 {msg}")
    return 1


def claim_errors(claims: list, index: dict) -> list[str]:
    by_id = L.rail_by_id(index)
    errs: list[str] = []
    if not isinstance(claims, list) or len(claims) < 8:
        return [f"claims too few: {0 if not isinstance(claims, list) else len(claims)}"]
    for claim in claims:
        cid = claim.get("claim_id")
        tier = claim.get("evidence_tier")
        verdict = claim.get("reviewer_verdict")
        rails = claim.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if verdict == "SURVIVES" and tier in {"E1", "E2"}:
            if "structured-api" not in kinds or "prose-source" not in kinds:
                errs.append(f"{cid}: SURVIVES {tier} lacks two rail kinds {kinds}")
            if len(rails) < 2:
                errs.append(f"{cid}: SURVIVES {tier} has <2 rails")
        if verdict == "SURVIVES" and tier in {"E3", "E4"}:
            errs.append(f"{cid}: SURVIVES at {tier}")
        for rail in rails:
            if not isinstance(rail, dict):
                errs.append(f"{cid}: rail not object")
                continue
            if rail.get("http_status") != 200 and tier in {"E1", "E2"}:
                errs.append(f"{cid}/{rail.get('id')}: http {rail.get('http_status')}")
            path = L.REPO / str(rail.get("capture_path") or "")
            if not path.is_file():
                errs.append(f"{cid}/{rail.get('id')}: missing {path}")
                continue
            live = L.sha256_file(path)
            if live != rail.get("sha256"):
                errs.append(
                    f"{cid}/{rail.get('id')}: sha mismatch live={live[:12]} art={str(rail.get('sha256'))[:12]}"
                )
            if not rail.get("local"):
                cap = by_id.get(rail.get("id"))
                if cap and cap.get("sha256") != rail.get("sha256"):
                    errs.append(f"{cid}/{rail.get('id')}: index sha != artifact sha")
            quote = str(rail.get("quote") or "")
            if quote and quote not in path.read_bytes().replace(b"\r\n", b"\n").decode(
                "utf-8", "replace"
            ):
                errs.append(f"{cid}/{rail.get('id')}: quote not in capture")
    return errs


def main() -> int:
    art = L.load_artifact()
    index = L.load_index()
    claims = art.get("claims") or []
    good = claim_errors(claims, index)
    if good:
        return fail("good claims: " + "; ".join(good[:8]))

    mutant = copy.deepcopy(claims)
    target = None
    for claim in mutant:
        if (
            claim.get("reviewer_verdict") == "SURVIVES"
            and claim.get("evidence_tier") == "E2"
            and len(claim.get("rails") or []) >= 2
        ):
            claim["rails"] = claim["rails"][:1]
            target = claim.get("claim_id")
            break
    if target is None:
        return fail("no E2 claim to mutate")
    bad = claim_errors(mutant, index)
    if not bad:
        return fail(f"dropped rail on {target} still accepted as E2 SURVIVES")

    # Quotes for CWL File/Directory and RO-Crate CreateAction must appear.
    needles = {
        "prose-cwl-clt-html": ["CWLType", "File"],
        "raw-wdl-spec-11": ["must be typed"],
        "prose-nextflow-process": ["function arguments"],
        "prose-snakemake-rules": ["input files, output files"],
        "prose-rocrate-provenance-spec": ["CreateAction"],
        "prose-nf-prov-readme": ["Workflow Run RO-Crate"],
    }
    by_id = L.rail_by_id(index)
    for rid, wanted in needles.items():
        row = by_id.get(rid)
        if not row or row.get("http_status") != 200:
            return fail(f"capture {rid} not 200")
        text = L.capture_text(row)
        miss = [n for n in wanted if n not in text]
        if miss:
            return fail(f"{rid} missing {miss}")

    print(
        json.dumps(
            {
                "probe": "probe2-two-rails",
                "claims": len(claims),
                "survives_e2": sum(
                    1
                    for c in claims
                    if c.get("reviewer_verdict") == "SURVIVES"
                    and c.get("evidence_tier") in {"E1", "E2"}
                ),
                "mutated_claim": target,
                "mutation_errs": bad[:4],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0064-probe2 two-rail evidence and mutation control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
