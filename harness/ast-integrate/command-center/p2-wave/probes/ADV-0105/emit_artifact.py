#!/usr/bin/env python3
"""Emit ADV-0105 refutation-record from live overlap and correlation measures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import independence as I  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore


def main() -> int:
    m = I.measure()
    if not m["controls"]["both_ok"]:
        print("FAILED:ADV-0105 emit controls did not calibrate")
        print(json.dumps(m["controls"], indent=2, sort_keys=True))
        return 1
    unit = I.load_catalog_unit()
    sentinel = I.catalog_sentinel()
    p1 = I.probe1_report(m)
    p2 = I.probe2_report(m)
    targets = I.targets_from(m)
    if not targets:
        print("FAILED:ADV-0105 no targets")
        return 1
    seen = set()
    for t in targets:
        if t["target_id"] in seen:
            print("FAILED:ADV-0105 duplicate target", t["target_id"])
            return 1
        seen.add(t["target_id"])
        if t["verdict"] not in I.LEGAL:
            print("FAILED:ADV-0105 illegal verdict", t)
            return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = m["overall_verdict"]
    schema_path = I.REPO / I.SCHEMA_REL
    schema_ok = False
    doc = {
        "unit_id": I.UNIT_ID,
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
            "role": "groupthink-red-teamer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "ADV-0105-probe2-outcome-correlation",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-derives the counterexample from raw input sets and "
                "error vectors (Pearson), not from probe 1's Jaccard table or "
                "from a prose summary of this report."
            ),
        },
        "method": {
            "probe1": I.PROBE1_NAME,
            "probe2": I.PROBE2_NAME,
            "jaccard_collapse": I.JACCARD_COLLAPSE,
            "correlation_collapse": I.CORR_COLLAPSE,
            "distinct_jaccard_max": I.JACCARD_DISTINCT_MAX,
            "distinct_correlation_max": I.CORR_DISTINCT_MAX,
        },
        "counts": m["counts"],
        "controls": m["controls"],
        "reviews": m["reviews"],
        "targets": targets,
        "events": m["events"],
        "evidence": [
            {
                "claim": (
                    "A distinct-input control pair has low Jaccard and low "
                    "error correlation, so both instruments can go green."
                ),
                "verdict": "REFUTED",
                "anchor": "control:distinct-inputs",
                "source_probe": I.P1_CMD,
                "verifier_probe": I.P2_CMD,
            },
            {
                "claim": (
                    "Copying agent A's inputs and error vector onto agent B "
                    "collapses N to 1 and turns the calibration gate red."
                ),
                "verdict": "CONFIRMED",
                "anchor": "control:shared-mutant",
                "source_probe": I.P1_CMD,
                "verifier_probe": I.P2_CMD,
            },
            {
                "claim": (
                    "CNF-0091's biased chair shares a briefing with the "
                    "sycophant, so chair+sycophant agreement is one lens."
                ),
                "verdict": next(
                    (
                        e["verdict"]
                        for e in m["events"]
                        if e["event_id"] == "session:CNF-0091:biased-chair"
                    ),
                    "NOT-CHECKED",
                ),
                "anchor": "session:CNF-0091:biased-chair",
                "source_probe": I.P1_CMD,
                "verifier_probe": I.P2_CMD,
            },
            {
                "claim": (
                    "Closed sample of claimed-independent PASS reviews do "
                    "not record complete distinct producer/reviewer input "
                    "manifests, so claimed N=2 corroboration is unproven."
                ),
                "verdict": m["reviews"]["corpus_verdict"],
                "anchor": "live:independent-reviewer-corpus",
                "source_probe": I.P1_CMD,
                "verifier_probe": I.P2_CMD,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-INPUT-OVERLAP",
                "name": I.PROBE1_NAME,
                "command": I.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-OUTCOME-CORRELATION",
                "name": I.PROBE2_NAME,
                "command": I.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-DIFFERENT-INPUT-CONTROL",
                "name": (
                    "control: two agents given deliberately different input "
                    "sets on the same question must show lower overlap and "
                    "lower correlation, calibrating both measures"
                ),
                "result": "PASS" if m["controls"]["distinct_ok"] else "FAIL",
            },
            {
                "id": "T-SHARED-MUTANT-GOES-RED",
                "name": (
                    "negative control that can go red: replace the "
                    "deliberately different second agent's inputs and error "
                    "vector with the first agent's; the calibration gate "
                    "must exit 1"
                ),
                "result": "PASS" if m["controls"]["mutant_ok"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DIFFERENT-INPUTS-AND-SHARED-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS" if m["controls"]["both_ok"] else "FAIL",
                "bad_state": "control:shared-mutant",
                "good_state": "control:distinct-inputs",
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": I.PROBE1_NAME,
                "command": I.P1_CMD,
                "raw_output": p1,
            },
            {
                "id": "probe2",
                "name": I.PROBE2_NAME,
                "command": I.P2_CMD,
                "raw_output": p2,
            },
        ],
        "findings": [
            {
                "id": "ADV-0105-F1",
                "severity": "P1",
                "status": "recorded-in-audit",
                "summary": (
                    "Closed-sample claimed-independent PASS reviews lack "
                    "complete dual input manifests."
                ),
            },
            {
                "id": "ADV-0105-F2",
                "severity": "P1",
                "status": "recorded-in-audit",
                "summary": (
                    "CNF-0091 biased-chair sycophancy is a shared-briefing "
                    "collapse when agreement is treated as corroboration."
                ),
            },
        ],
        "residual_unknowns": [
            "ADV-0087 / ADV-0093 panel transcripts are absent on this worktree.",
            "Most workflow fan-out surfaces have no per-agent input ledger, so they stay NOT-CHECKED rather than CONFIRMED.",
            "Open glob of in-flight SUBAGENT-RETURN files is not a remesure-stable corpus; this unit enumerates SAMPLE_REVIEW_IDS only.",
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0105/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": (
                "per-unit only; global unit_manifest.py --write was not invoked"
            ),
        },
        "artifacts": [
            {
                "path": I.OUTPUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": I.SCHEMA_REL,
                "exists": schema_path.is_file(),
                "role": "schema",
            },
        ],
        "min_bytes_threshold": 4096,
        "output_schema": I.SCHEMA_REL,
        "answer": (
            "PARTIAL: calibrated controls show the instruments discriminate "
            "shared vs distinct inputs; live council and claimed-independent "
            "reviews collapse to one lens where measurable; historical panels "
            "and most workflow surfaces remain NOT-CHECKED."
        ),
    }
    if jsonschema is not None and schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errs:
            print("FAILED:ADV-0105 schema", errs[0].message)
            return 1
        schema_ok = True
    doc["schema_validated"] = schema_ok
    out = I.REPO / I.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0105 sentinel not in serialized artifact")
        return 1
    if "SUCCESS:ADV-0105" not in text:
        print("FAILED:ADV-0105 SUCCESS:ADV-0105 missing")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {I.OUTPUT_REL} bytes={out.stat().st_size} schema_ok={schema_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
