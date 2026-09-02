#!/usr/bin/env python3
"""Probe 1: re-run the live denial matrix and require loud-or-degraded plus granted control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

import harness as H
import inventory as I
import overclaim as O

HERE = Path(__file__).resolve().parent
REPO = I.REPO
ART = REPO / I.OUT_REL
SCHEMA = REPO / I.SCHEMA_REL
LOUD = {"loud-failure", "degraded-artifact"}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0117-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    sent = I.sentinel()
    if sent not in text:
        print("FAILED:CNF-0117-probe1 sentinel-absent")
        return 1
    if I.TOKEN_VALUE in text:
        print("FAILED:CNF-0117-probe1 fixture token present in artifact")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print(f"FAILED:CNF-0117-probe1 schema-invalid {errs[0].message}")
        return 1
    ok, why = O.check(doc)
    if not ok:
        print(f"FAILED:CNF-0117-probe1 overclaim {why}")
        return 1
    live = H.measure(include_mutant=True)
    if not live["control"]["success"] or live["control"]["artifact_degraded"] is not False:
        print("FAILED:CNF-0117-probe1 granted control did not produce a non-degraded artifact")
        return 1
    if live["control"]["exit_code"] != 0:
        print("FAILED:CNF-0117-probe1 control exit", live["control"]["exit_code"])
        return 1
    live_by = {row["dependency_id"]: row for row in live["denials"]}
    art_by = {row["dependency_id"]: row for row in doc.get("denials") or []}
    if set(live_by) != set(art_by):
        print(f"FAILED:CNF-0117-probe1 denial id mismatch live={sorted(live_by)} art={sorted(art_by)}")
        return 1
    for dep_id, row in live_by.items():
        recorded = art_by[dep_id]
        if row["classification"] not in LOUD:
            print(f"FAILED:CNF-0117-probe1 live {dep_id} {row['classification']}")
            return 1
        if row["classification"] != recorded["classification"]:
            print(
                f"FAILED:CNF-0117-probe1 {dep_id} live={row['classification']} art={recorded['classification']}"
            )
            return 1
        if row["kind"] == "credential" and row["deny_method"] != "unset-variable-in-subprocess":
            print(f"FAILED:CNF-0117-probe1 {dep_id} credential not unset")
            return 1
    enrich = live_by["perm-enrichment-write"]
    if enrich["produced_artifact"] is not True or enrich["artifact_marked_degraded"] is not True:
        print("FAILED:CNF-0117-probe1 enrichment denial did not mark artifact degraded")
        return 1
    if not live["credential_safety"]["no_real_credential_modified"]:
        print("FAILED:CNF-0117-probe1 real credential mtime changed")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0117-probe1 self-declared", doc.get("state"))
        return 1
    print(
        "control_ok=True denials="
        f"{len(live_by)} all_loud_or_degraded={live['all_denials_loud_or_degraded']} "
        f"enrich_degraded={enrich['artifact_marked_degraded']}"
    )
    print("SUCCESS:CNF-0117-probe1 denial matrix re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
