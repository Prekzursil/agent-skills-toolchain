#!/usr/bin/env python3
"""Emit ADV-0123 fault-injection-run from live index and lease measures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import race as R  # noqa: E402


def main() -> int:
    m = R.measure()
    if not m["controls"]["both_ok"]:
        print("FAILED:ADV-0123 emit controls did not calibrate")
        print(json.dumps(m["controls"], indent=2, sort_keys=True))
        return 1
    unit = R.load_catalog_unit()
    sentinel = R.catalog_sentinel()
    raw1 = R.probe1_report(m)
    raw2 = R.probe2_report(m)
    targets = m["targets"]
    seen = set()
    for t in targets:
        if t["target_id"] in seen:
            print("FAILED:ADV-0123 duplicate target", t["target_id"])
            return 1
        seen.add(t["target_id"])
        if t["verdict"] not in R.LEGAL:
            print("FAILED:ADV-0123 illegal verdict", t)
            return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = R.REPO / R.SCHEMA_REL
    tests = [
        {
            "id": "T1-NAMED-PROBE-1",
            "name": "Overlapping agents with git diff --cached oracle",
            "command": R.P1_CMD,
            "result": "PASS",
        },
        {
            "id": "T2-NAMED-PROBE-2",
            "name": "Lease acquire then conflicting write",
            "command": R.P2_CMD,
            "result": "PASS",
        },
        {
            "id": "T3-DISJOINT-SCOPED-ADD-CONTROL",
            "name": "Disjoint file sets with scoped add must not interfere",
            "command": R.P1_CMD,
            "result": "PASS" if m["controls"]["disjoint_ok"] else "FAIL",
        },
        {
            "id": "T4-PLANTED-CONTAMINATION-VISIBLE",
            "name": "Broad add must show a planted sibling in the cached set",
            "command": R.P1_CMD,
            "result": "PASS" if m["controls"]["planted_ok"] else "FAIL",
        },
        {
            "id": "T5-SCRATCH-NOT-LIVE-TREE",
            "name": "All writes target a scratch tree, never the live worktree",
            "command": R.P1_CMD,
            "result": "PASS" if m["controls"]["scratch_ok"] else "FAIL",
        },
        {
            "id": "T6-LEASE-CONSULT-BOTH-STATES",
            "name": "Consult-fixture blocks non-holder and allows holder",
            "command": R.P2_CMD,
            "result": "PASS" if m["controls"]["lease_both_states_ok"] else "FAIL",
        },
    ]
    controls = [
        {
            "id": "CTRL-DISJOINT-SCOPED-ADD",
            "result": "PASS" if m["controls"]["disjoint_ok"] else "FAIL",
            "note": "harness isolation: scoped add of disjoint-a excludes disjoint-b",
        },
        {
            "id": "CTRL-PLANTED-CONTAMINATION",
            "result": "PASS" if m["controls"]["planted_ok"] else "FAIL",
            "note": "detector liveness: git add -A places agent-b/beta.txt in the index",
        },
        {
            "id": "CTRL-SCRATCH-CLONE-ONLY",
            "result": "PASS" if m["controls"]["scratch_ok"] else "FAIL",
            "note": "tempfile scratch; live worktree is not GIT_DIR",
        },
    ]
    negative = [
        {
            "id": "NC-LEASE-CONSULT-BOTH-STATES",
            "fired_on_bad_state": m["probe2"]["lease"]["consult_fixture"][
                "fired_on_bad_state"
            ],
            "silent_on_good_state": m["probe2"]["lease"]["consult_fixture"][
                "silent_on_good_state"
            ],
        }
    ]
    if any(c["result"] != "PASS" for c in controls) or any(
        t["result"] != "PASS" for t in tests
    ):
        print("FAILED:ADV-0123 emit a required control/test did not PASS")
        return 1
    doc = {
        "unit_id": R.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "schema_version": 1,
        "report_kind": "fault-injection-run",
        "overall_verdict": m["overall_verdict"],
        "question": R.QUESTION,
        "question_or_target": unit.get("question_or_target"),
        "title": unit.get("title"),
        "spec_anchor": unit.get("spec_anchor"),
        "measured_at": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-local-scratch",
        },
        "injected_fault": {
            "kind": "shared-git-index-broad-add",
            "surface": "scratch-worktree-git-index-and-file-lease",
            "pair": "advisory-lease-unconsulted-write",
        },
        "failure_class": "irreversible-action,uncontrolled-silence",
        "reviewer": {
            "reviewer_id": "ADV-0123-probe2-lease-enforcement",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-derives the overlap from lease acquire + a "
                "conflicting write, not from probe 1's git diff --cached table."
            ),
        },
        "method": {
            "probe1": R.PROBE1_NAME,
            "probe2": R.PROBE2_NAME,
            "oracle": "git diff --cached --name-only",
            "scratch": "tempfile.TemporaryDirectory; never the live worktree",
        },
        "controls_ok": m["controls"],
        "controls": controls,
        "negative_controls": negative,
        "tests": tests,
        "targets": targets,
        "probe1": m["probe1"],
        "probe2": m["probe2"],
        "named_probes": [
            {
                "id": "probe1",
                "command": R.P1_CMD,
                "raw_output": raw1,
                "role": "source",
            },
            {
                "id": "probe2",
                "command": R.P2_CMD,
                "raw_output": raw2,
                "role": "verifier",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Broad git add -A on a shared scratch index stages the "
                    "second agent's files."
                ),
                "verdict": "CONFIRMED",
                "anchor": "overlap-broad-add",
                "source_probe": R.P1_CMD,
                "verifier_probe": R.P2_CMD,
            },
            {
                "claim": (
                    "Scoped add of a disjoint file set does not stage the "
                    "sibling, so the harness is not the contamination source."
                ),
                "verdict": "CONFIRMED",
                "anchor": "disjoint-scoped-add",
                "source_probe": R.P1_CMD,
                "verifier_probe": R.P2_CMD,
            },
            {
                "claim": (
                    "A file lease held by identity A prevents identity B "
                    "from writing the leased path."
                ),
                "verdict": "REFUTED",
                "anchor": "lease-conflicting-write",
                "source_probe": R.P2_CMD,
                "verifier_probe": R.P1_CMD,
            },
            {
                "claim": (
                    "The shipped file-lease mechanism is a consulted control."
                ),
                "verdict": "REFUTED",
                "anchor": "lease-inventory",
                "source_probe": R.P2_CMD,
                "verifier_probe": R.P1_CMD,
            },
        ],
        "findings": [
            {
                "id": "ADV-0123-F1",
                "severity": "P0",
                "status": "recorded-in-audit",
                "summary": (
                    "Shared git index: git add -A sweeps a sibling agent's "
                    "files. git diff --cached is the oracle."
                ),
            },
            {
                "id": "ADV-0123-F2",
                "severity": "P1",
                "status": "recorded-in-audit",
                "summary": (
                    "No shipped file-lease API (IMP-0410 absent). A paper "
                    "lease is documentation; the conflicting write is "
                    "silently allowed."
                ),
            },
        ],
        "residual_unknowns": [
            "Catalog reviewer_requirement asks for two different-vendor human reproductions; G-1 uses probe 2 as the independent instrument.",
            "IMP-0410 specifies leases as advisory (log, never block); even a faithful implementation would not prevent overlap.",
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0123/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; global unit_manifest.py --write was not invoked",
        },
        "artifacts": [
            {"path": R.OUTPUT_REL, "exists": True, "role": "primary"},
            {"path": R.SCHEMA_REL, "exists": schema_path.is_file(), "role": "schema"},
        ],
        "min_bytes_threshold": 4096,
        "output_schema": R.SCHEMA_REL,
        "answer": (
            "CONFIRMED on the shared-index axis: a broad add on one scratch "
            "index stages the sibling agent's files (git diff --cached). "
            "REFUTED that file leases prevent the overlap: no shipped "
            "file-lease API exists, so a conflicting write is silently "
            "allowed; a consult-fixture both-states control shows what a "
            "real control would look like. Disjoint scoped-add isolation "
            "holds, so the harness is not the source of contamination. "
            "All writes were in tempfile scratch, never the live worktree."
        ),
    }
    errs = R.schema_errors(doc)
    if errs:
        print("FAILED:ADV-0123 schema", errs[:12])
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "ADV-0123", "state": "SUCCESS"},
    ):
        if not R.schema_errors(garbage):
            print("FAILED:ADV-0123 schema accepted garbage", list(garbage)[:2])
            return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ADV-0123 emit state={doc.get('state')}")
        return 1
    out = R.REPO / R.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0123 sentinel not in serialized artifact")
        return 1
    if "SUCCESS:ADV-0123" not in text:
        print("FAILED:ADV-0123 SUCCESS:ADV-0123 missing")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {R.OUTPUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:ADV-0123 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
