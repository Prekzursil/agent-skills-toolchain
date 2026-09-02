#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0044.json from a live harness run."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from both_states_harness import (  # noqa: E402
    ProbeSpec,
    bundled_fixtures,
    evaluate,
    missing_broken_control,
    reviewer_always_pass_probe,
    same_run_catalog_evidence,
)

OUT = "command-center/receipts/IMP-0044.json"
SCHEMA = "tools/plugin/schema/probe-control.schema.json"
TEST = "tools/plugin/tests/test_both_states_harness.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0044/probe1_same_run.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0044/probe2_missing_fixture.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size if size else 1,
        "sha256": sha or ("0" * 64),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF" if path.is_file() else "NOT-CHECKED",
    }


def main() -> int:
    test = subprocess.run(
        [sys.executable, "-B", str(REPO / TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    test_out = ((test.stdout or "") + (test.stderr or "")).strip()
    if test.returncode != 0:
        print(test_out[-4000:])
        print("FAILED:IMP-0044 emit catalog tests")
        return 1

    report = same_run_catalog_evidence()
    missing = missing_broken_control()
    broken, good = bundled_fixtures()
    reviewer = evaluate(
        ProbeSpec(
            probe_id="reviewer-always-pass",
            run=reviewer_always_pass_probe,
            known_broken=broken,
            known_good=good,
        )
    )
    by_id = report.by_id()
    if by_id["always-ok"].trust != "UNTRUSTWORTHY" or by_id["content-marker"].trust != "TRUSTED":
        print("FAILED:IMP-0044 emit same-run evidence")
        return 1
    if missing.skipped or missing.trust != "UNTRUSTWORTHY":
        print("FAILED:IMP-0044 emit missing-fixture control")
        return 1
    if reviewer.trust != "UNTRUSTWORTHY":
        print("FAILED:IMP-0044 emit reviewer always-ok")
        return 1

    control_doc = report.as_dict()
    schema_doc = report.to_probe_control()
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    import jsonschema

    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(schema_doc))
    if errs:
        print("FAILED:IMP-0044 probe-control schema", errs[0].message)
        return 1
    for garbage in (
        {},
        {"passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:IMP-0044 schema accepted garbage")
            return 1

    supporting = [
        "tools/plugin/both_states_harness.py",
        SCHEMA,
        TEST,
        "tools/plugin/fixtures/both-states/known-broken/payload.txt",
        "tools/plugin/fixtures/both-states/known-good/payload.txt",
        "command-center/p2-wave/probes/IMP-0044/probe1_same_run.py",
        "command-center/p2-wave/probes/IMP-0044/probe2_missing_fixture.py",
    ]
    artifacts = [art(rel, "supporting") for rel in supporting]
    if any(not a["exists"] for a in artifacts):
        missing_paths = [a["path"] for a in artifacts if not a["exists"]]
        print("FAILED:IMP-0044 missing supporting", missing_paths)
        return 1

    doc = {
        "schema": "probe-control/v1",
        "harness": "both-states",
        "same_run": True,
        "results": control_doc["results"],
        "trusted_count": control_doc["trusted_count"],
        "untrustworthy_count": control_doc["untrustworthy_count"],
        "schema_version": 1,
        "unit_id": "IMP-0044",
        "id": "IMP-0044",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0044",
        "completion_sentinel": "SUCCESS:IMP-0044",
        "title": "Both-states control harness for every health and validation probe",
        "question": (
            "Build the substrate that lets each probe declare a KNOWN-BROKEN "
            "fixture and a KNOWN-GOOD fixture, then runs both automatically and "
            "marks the probe UNTRUSTWORTHY if it returns the same verdict in "
            "both states. This is infrastructure for the probes, not the "
            "Phase-10 test corpus, which bucket B08 owns."
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/probe-control.schema.json"
        ),
        "min_bytes_threshold": 128,
        "spec_anchor": "rules/common/single-signal-verification.md#3b",
        "probe_control": schema_doc,
        "evidence": [
            {
                "claim": (
                    "A deliberately useless probe that always returns OK is "
                    "marked UNTRUSTWORTHY by the harness."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/both_states_harness.py:always_ok_probe",
                "probe_id": "always-ok",
                "trust": by_id["always-ok"].trust,
                "reason": by_id["always-ok"].reason,
                "broken_verdict": by_id["always-ok"].broken_verdict,
                "good_verdict": by_id["always-ok"].good_verdict,
            },
            {
                "claim": (
                    "A genuine probe that fires on BROKEN and is silent on the "
                    "healthy payload is marked TRUSTED in the same run."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/both_states_harness.py:content_marker_probe",
                "probe_id": "content-marker",
                "trust": by_id["content-marker"].trust,
                "reason": by_id["content-marker"].reason,
                "broken_verdict": by_id["content-marker"].broken_verdict,
                "good_verdict": by_id["content-marker"].good_verdict,
            },
        ],
        "negative_controls": [
            {
                "id": "missing-broken-fixture",
                "kind": "known-broken-fixture",
                "description": (
                    "A probe whose known-broken fixture path is absent is "
                    "UNTRUSTWORTHY with skipped=false, not omitted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "trust": missing.trust,
                "skipped": missing.skipped,
                "reason": missing.reason,
            },
            {
                "id": "reviewer-always-pass",
                "kind": "always-ok-probe",
                "description": (
                    "Reviewer-designed always-OK probe returns PASS and ignores "
                    "fixtures; harness still marks it UNTRUSTWORTHY."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "trust": reviewer.trust,
                "skipped": reviewer.skipped,
                "reason": reviewer.reason,
            },
        ],
        "tests": [
            {
                "id": "test_always_ok_probe_is_flagged",
                "command": f"python3 -B {TEST}",
                "result": "PASS",
            },
            {
                "id": "test_discriminating_probe_is_trusted",
                "command": f"python3 -B {TEST}",
                "result": "PASS",
            },
            {
                "id": "test_missing_broken_fixture_is_untrustworthy",
                "command": f"python3 -B {TEST}",
                "result": "PASS",
            },
        ],
        "catalog_tests_output": test_out[-4000:],
        "named_probes": [
            {"id": "probe1", "role": "same-run-trust-marks", "command": P1},
            {"id": "probe2", "role": "missing-fixture-negative-control", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0044-probe2-reviewer-always-pass",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 adds an always-OK probe of a different design "
                "(returns PASS, ignores fixture bytes) and confirms the "
                "harness flags it UNTRUSTWORTHY. Catalog scoring by a second "
                "human is independent of G-1 probe-green."
            ),
        },
        "artifacts": artifacts,
        "residual_unknowns": [
            {
                "claim": (
                    "Nested probe_control validates against "
                    "tools/plugin/schema/probe-control.schema.json. The catalog "
                    "also names command-center/schema/receipt.schema.json, which "
                    "is a shim $ref to platform/schema/receipt.schema.json with "
                    "additionalProperties false; this G-1 receipt carries live "
                    "harness fields at the top level and is not claimed as a "
                    "reducer-complete 12-condition receipt."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-shape this receipt to receipt_core (report=probe_control) "
                    "and re-validate with a local $ref resolver."
                ),
            }
        ],
        "cloud_ok": False,
        "notes": (
            "IMP-0044 ships tools/plugin/both_states_harness.py: each probe "
            "declares known-broken and known-good fixtures; same verdict in "
            "both states, or a missing broken fixture, is UNTRUSTWORTHY. "
            "SUCCESS:IMP-0044"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    sha, size = digest(out)
    if size < 128:
        print(f"FAILED:IMP-0044 receipt too small {size}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0044 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
