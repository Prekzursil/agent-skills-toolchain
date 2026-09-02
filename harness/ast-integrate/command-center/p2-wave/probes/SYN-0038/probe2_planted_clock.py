#!/usr/bin/env python3
"""Probe 2: planted-clock detector control and in-advance declaration.

Verifier measurement. Distinct fingerprint from probe 1. Re-runs the
DETECTOR CONTROL: planted timestamp must FIRE and attribute clock; the
known-good two-run must be SILENT. A timestamp injected into a
deterministic stage without a pre-run declaration is undeclared-nondeterminism.
Does not re-check per-stage identity hashes against the receipt.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402
import schema_ctl as S  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0038.json"
SCHEMA = REPO / "command-center/schema/reproducibility-report.schema.json"


def main() -> int:
    exp = P.run_experiment(REPO)
    plant = exp["controls"]["planted_clock"]
    good = exp["controls"]["known_good_silent"]
    undecl = exp["controls"]["undeclared_arm"]
    live = exp["controls"]["live_clock_narrative"]
    fake = exp["controls"]["fake_clock_narrative"]
    out = {
        "probe": "probe2-planted-clock-declaration",
        "unit_id": "SYN-0038",
        "planted_clock_fired": plant["fired"],
        "planted_clock_cause": plant["cause"],
        "known_good_silent": good["silent"],
        "undeclared_would_fail": undecl["would_fail"],
        "undeclared_classification": undecl["classification"],
        "declaration_sha256_before_run": exp["declaration_sha256_before_run"],
        "narrative_was_declared": exp["checks"]["narrative_was_declared"],
        "live_clock_diverged": live["diverged"],
        "live_clock_cause": live["cause"],
        "fake_clock_identical": fake["identical"],
        "gate_clean_silent": exp["checks"]["gate_clean_silent"],
        "gate_cycle_fired": exp["checks"]["gate_cycle_fired"],
        "severity_inversion_fired": exp["checks"]["severity_inversion_fired"],
        "pass": bool(
            plant["fired"]
            and plant["cause"] == "clock"
            and good["silent"]
            and undecl["would_fail"]
            and undecl["classification"] == "undeclared-nondeterminism"
            and exp["checks"]["narrative_was_declared"]
            and live["diverged"]
            and live["cause"] == "clock"
            and fake["identical"]
            and exp["checks"]["gate_clean_silent"]
            and exp["checks"]["gate_cycle_fired"]
            and exp["checks"]["severity_inversion_fired"]
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        print("FAILED:SYN-0038-probe2 detector control")
        print(json.dumps(exp["checks"], sort_keys=True))
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:SYN-0038-probe2 receipt missing")
        return 1
    if not SCHEMA.is_file():
        print("FAILED:SYN-0038-probe2 schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = S.errors(doc)
    if errs:
        print("FAILED:SYN-0038-probe2 schema", errs[0])
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        if S.errors(garbage):
            print(f"garbage_rejected={list(garbage)[:1] or '{}'}")
            continue
        print("FAILED:SYN-0038-probe2 schema accepts garbage")
        return 1

    payload = S.domain(doc)
    rec_controls = {
        c["id"]: c for c in (payload.get("controls") or doc.get("controls") or [])
    }
    if rec_controls.get("planted-timestamp-clock", {}).get("verdict") != "fired":
        print("FAILED:SYN-0038-probe2 receipt planted clock not fired")
        return 1
    if rec_controls.get("known-good-two-run", {}).get("verdict") != "silent":
        print("FAILED:SYN-0038-probe2 receipt known-good not silent")
        return 1
    decl_sha = payload.get("declaration_sha256_before_run") or doc.get(
        "declaration_sha256_before_run"
    )
    if decl_sha != exp["declaration_sha256_before_run"]:
        print("FAILED:SYN-0038-probe2 declaration sha drift")
        return 1
    declared = payload.get("declared_nondeterministic_stages") or doc.get(
        "declared_nondeterministic_stages"
    ) or []
    if not all(d.get("declared_before_run") is True for d in declared):
        print("FAILED:SYN-0038-probe2 declaration not marked before-run")
        return 1
    ids = {d.get("id") for d in declared}
    if "model-authored-narrative" not in ids:
        print("FAILED:SYN-0038-probe2 narrative not declared in advance")
        return 1
    mismatches = payload.get("mismatches") or doc.get("mismatches") or []
    if not mismatches:
        print("FAILED:SYN-0038-probe2 no attributed mismatches")
        return 1
    if any(not m.get("attributed") for m in mismatches):
        print("FAILED:SYN-0038-probe2 unattributed mismatch")
        return 1
    causes = {m.get("cause") for m in mismatches}
    if "clock" not in causes:
        print("FAILED:SYN-0038-probe2 planted clock cause missing")
        return 1
    tests = {t["id"]: t for t in doc.get("tests") or []}
    needed = {
        "test_declared_deterministic_stages_hash_identically_across_two_runs",
        "test_nondeterministic_stages_are_declared_in_advance_not_discovered_after",
        "planted_nondeterminism_timestamp_attributed",
    }
    if not needed.issubset(tests):
        print("FAILED:SYN-0038-probe2 required tests missing")
        return 1
    if any(tests[i].get("result") != "PASS" for i in needed):
        print("FAILED:SYN-0038-probe2 required test not PASS")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["deterministic_all_identical"] = False
    if not S.errors(mutant):
        print("FAILED:SYN-0038-probe2 schema accepted identity-false mutant")
        return 1
    print("identity-false-mutant-rejected")

    print(
        f"planted_fired={plant['fired']} cause={plant['cause']} "
        f"good_silent={good['silent']} undeclared_fails={undecl['would_fail']} "
        f"live_diverged={live['diverged']}"
    )
    print("SUCCESS:SYN-0038-probe2 planted-clock detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
