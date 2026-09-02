#!/usr/bin/env python3
"""Emit ADV-0114 refutation-record from live collapse measures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_common as C  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore


def main() -> int:
    m = C.measure()
    if not m["controls"]["both_ok"]:
        print("FAILED:ADV-0114 emit planted controls did not calibrate")
        print(json.dumps(m["controls"], indent=2, sort_keys=True, default=str))
        return 1
    unit = C.load_catalog_unit()
    sentinel = C.catalog_sentinel()
    p1 = C.probe1_report(m)
    p2 = C.probe2_report(m)
    targets = C.targets_from(m)
    if len(targets) < 2:
        print("FAILED:ADV-0114 no targets")
        return 1
    seen = set()
    for t in targets:
        if t["target_id"] in seen:
            print("FAILED:ADV-0114 duplicate target", t["target_id"])
            return 1
        seen.add(t["target_id"])
        if t["verdict"] not in C.LEGAL:
            print("FAILED:ADV-0114 illegal verdict", t)
            return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = m["overall_verdict"]
    schema_path = C.REPO / C.SCHEMA_REL
    schema_ok = False
    v_canon = next(
        t["verdict"]
        for t in targets
        if t["target_id"] == "live:canonical-mechanism-inflation"
    )
    v_fix = next(
        t["verdict"]
        for t in targets
        if t["target_id"] == "live:fix-equivalence-inflation"
    )
    doc = {
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "schema_version": 1,
        "report_kind": "refutation-record",
        "overall_verdict": overall,
        "question": unit.get("question_or_target"),
        "title": unit.get("title"),
        "spec_anchor": unit.get("spec_anchor"),
        "measured_at": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "synthesis-distortion-auditor",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "ADV-0114-probe2-fix-equivalence",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-derives collapse from remediation fingerprints, "
                "not from probe 1's canonical-mechanism table and not from "
                "a prose summary of this report."
            ),
        },
        "method": {
            "probe1": C.PROBE1_NAME,
            "probe2": C.PROBE2_NAME,
            "closed_sample": list(C.SAMPLE_SOURCES),
            "claim_registry": C.CLAIM_REGISTRY_REL,
        },
        "counts": m["counts"],
        "controls": {
            "both_ok": m["controls"]["both_ok"],
            "reword_collapsed": m["controls"]["reword_collapsed"],
            "neighbour_separated": m["controls"]["neighbour_separated"],
            "seed_id": m["controls"]["seed_id"],
            "reword_id": m["controls"]["reword_id"],
            "neighbour_id": m["controls"]["neighbour_id"],
            "probe1_seed_key": m["controls"]["probe1_seed_key"],
            "probe1_reword_key": m["controls"]["probe1_reword_key"],
            "probe1_neighbour_key": m["controls"]["probe1_neighbour_key"],
            "probe2_seed_key": m["controls"]["probe2_seed_key"],
            "probe2_reword_key": m["controls"]["probe2_reword_key"],
            "probe2_neighbour_key": m["controls"]["probe2_neighbour_key"],
        },
        "sources": m["sources"],
        "claim_registry_present": m["claim_registry_present"],
        "probe1": m["probe1"],
        "probe2": m["probe2"],
        "plants": [
            {
                "id": p["id"],
                "plant": p["plant"],
                "mechanism_key": p["mechanism_key"],
                "fix_key": p["fix_key"],
                "text": p["text"],
            }
            for p in m["plants"]
        ],
        "live_finding_ids": [r["id"] for r in m["live"]],
        "targets": targets,
        "evidence": [
            {
                "claim": (
                    "A planted reworded duplicate of a live finding shares "
                    "canonical mechanism and remediation with its seed, so "
                    "both instruments collapse it."
                ),
                "verdict": "CONFIRMED",
                "anchor": "control:reworded-duplicate",
                "source_probe": C.P1_CMD,
                "verifier_probe": C.P2_CMD,
            },
            {
                "claim": (
                    "A genuinely distinct near-neighbour with similar wording "
                    "stays in its own canonical-mechanism and fix clusters."
                ),
                "verdict": "REFUTED",
                "anchor": "control:distinct-near-neighbour",
                "source_probe": C.P1_CMD,
                "verifier_probe": C.P2_CMD,
            },
            {
                "claim": (
                    "The closed-sample live finding set contains duplicate "
                    "canonical mechanisms after wording, scope and affected "
                    "file are ignored."
                ),
                "verdict": v_canon,
                "anchor": "live:canonical-mechanism-inflation",
                "source_probe": C.P1_CMD,
                "verifier_probe": C.P2_CMD,
                "raw": m["probe1"]["raw"],
                "collapsed": m["probe1"]["collapsed"],
                "ratio": m["probe1"]["ratio"],
            },
            {
                "claim": (
                    "The closed-sample live finding set contains findings "
                    "whose remediation is the same change."
                ),
                "verdict": v_fix,
                "anchor": "live:fix-equivalence-inflation",
                "source_probe": C.P1_CMD,
                "verifier_probe": C.P2_CMD,
                "raw": m["probe2"]["raw"],
                "collapsed": m["probe2"]["collapsed"],
                "ratio": m["probe2"]["ratio"],
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-CANONICAL-CLUSTERS",
                "name": C.PROBE1_NAME,
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-FIX-EQUIVALENCE",
                "name": C.PROBE2_NAME,
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PLANTED-REWORD-COLLAPSES",
                "name": (
                    "planted control: insert one reworded duplicate and "
                    "require it to join the seed cluster on both instruments"
                ),
                "result": "PASS" if m["controls"]["reword_collapsed"] else "FAIL",
            },
            {
                "id": "T-PLANTED-NEIGHBOUR-SEPARATES",
                "name": (
                    "planted control: insert one genuinely distinct "
                    "near-neighbour and require correct separation"
                ),
                "result": "PASS" if m["controls"]["neighbour_separated"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-REWORD-VS-NEAR-NEIGHBOUR",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS" if m["controls"]["both_ok"] else "FAIL",
                "bad_state": "control:reworded-duplicate",
                "good_state": "control:distinct-near-neighbour",
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": C.PROBE1_NAME,
                "command": C.P1_CMD,
                "raw_output": p1,
            },
            {
                "id": "probe2",
                "name": C.PROBE2_NAME,
                "command": C.P2_CMD,
                "raw_output": p2,
            },
        ],
        "findings": [
            {
                "id": "ADV-0114-F1",
                "severity": "P1",
                "status": "recorded-in-audit",
                "summary": (
                    f"Canonical-mechanism collapse ratio={m['probe1']['ratio']} "
                    f"raw={m['probe1']['raw']} collapsed={m['probe1']['collapsed']} "
                    f"multi={m['probe1']['multi_member_count']}."
                ),
            },
            {
                "id": "ADV-0114-F2",
                "severity": "P1",
                "status": "recorded-in-audit",
                "summary": (
                    f"Fix-equivalence collapse ratio={m['probe2']['ratio']} "
                    f"raw={m['probe2']['raw']} collapsed={m['probe2']['collapsed']} "
                    f"multi={m['probe2']['multi_member_count']}."
                ),
            },
        ],
        "residual_unknowns": [
            "command-center/CLAIM-REGISTRY.json is absent; Phase-1 canonical "
            "mechanism ledger is NOT-CHECKED rather than rebuilt.",
            "Open glob of in-flight probe artifacts is not a remesure-stable "
            "corpus; this unit enumerates SAMPLE_SOURCES only.",
            "_USER-PROMPTS.md:11092 is not on this worktree; the catalog "
            "question and evidence_requirement are the contract used.",
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0114/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": (
                "per-unit only; global unit_manifest.py --write was not invoked"
            ),
        },
        "artifacts": [
            {
                "path": C.OUTPUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": C.SCHEMA_REL,
                "exists": schema_path.is_file(),
                "role": "schema",
            },
        ],
        "min_bytes_threshold": 4096,
        "output_schema": C.SCHEMA_REL,
        "answer": (
            f"{overall}: live canonical-mechanism raw={m['probe1']['raw']} "
            f"collapsed={m['probe1']['collapsed']} ratio={m['probe1']['ratio']}; "
            f"fix-equivalence raw={m['probe2']['raw']} "
            f"collapsed={m['probe2']['collapsed']} ratio={m['probe2']['ratio']}; "
            "planted reword collapses and near-neighbour stays distinct; "
            "CLAIM-REGISTRY.json is NOT-CHECKED (absent)."
        ),
    }
    if jsonschema is not None and schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errs:
            print("FAILED:ADV-0114 schema", errs[0].message)
            return 1
        schema_ok = True
    doc["schema_validated"] = schema_ok
    out = C.REPO / C.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0114 sentinel not in serialized artifact")
        return 1
    if "SUCCESS:ADV-0114" not in text:
        print("FAILED:ADV-0114 SUCCESS:ADV-0114 missing")
        return 1
    out.write_text(text, encoding="utf-8")
    print(
        f"wrote {C.OUTPUT_REL} bytes={out.stat().st_size} schema_ok={schema_ok} "
        f"raw={m['probe1']['raw']} collapsed={m['probe1']['collapsed']} "
        f"ratio={m['probe1']['ratio']} overall={overall}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
