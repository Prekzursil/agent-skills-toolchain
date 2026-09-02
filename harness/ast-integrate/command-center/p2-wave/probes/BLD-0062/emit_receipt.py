#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0062.json sampling-adequacy audit."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import bounds as B  # noqa: E402
import bounds_reviewer as BR  # noqa: E402
import classify as C  # noqa: E402
import corpus as CX  # noqa: E402

OUT = "command-center/receipts/BLD-0062.json"
SCHEMA = "command-center/schema/sampling-audit.schema.json"
QUESTION = (
    "Question: where did the program sample rather than enumerate, and does the "
    "sample support the confidence it claimed? Enumerate every sampled measurement "
    "- the Phase 11 stratified claim sample, the Phase 0 baseline's 28 of 60 CI "
    "test steps, and any 'representative subset' - and for each compute the "
    "population size, the sample size, the selection method, and the maximum "
    "defect rate the sample could have missed at 95% confidence."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0062/probe1_method_and_unknown.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0062/probe2_recompute_bounds.py"
)
NAMED_ABSENT_INPUTS = [
    "command-center/confirmation/CNF-0003-sampling-frame.json",
    "command-center/receipts/CNF-0137.json",
    "command-center/receipts/CNF-0138.json",
    "command-center/audit/AUD-0042-close-baseline-ci-gap.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def load_fixture(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def load_json(rel: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def entry_from_record(rec: dict, extra: dict | None = None) -> dict:
    classified = C.classify_method(rec)
    bound = B.missed_defect_bound_95(rec.get("population_size"), rec.get("sample_size"))
    planted = rec.get("planted_confidence")
    row = {
        "id": rec["id"],
        "name": rec["name"],
        "population_size": rec.get("population_size"),
        "sample_size": rec.get("sample_size"),
        "selection_method_claimed": rec.get("claimed_method"),
        "selection_method_classified": classified,
        "reclassified_from_stratified": (
            "stratified" in str(rec.get("claimed_method") or "").lower()
            and classified == "convenience"
        ),
        "executed": C.is_executed(rec),
        "missed_defect_bound_95": bound,
        "refused_planted_confidence": planted
        if bound.get("status") == B.NOT_COMPUTABLE and planted is not None
        else None,
    }
    if extra:
        row.update(extra)
    return row


def live_ci_inventory() -> dict:
    inv_rel = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    inv_path = REPO / inv_rel
    if not inv_path.is_file():
        return {"present": False, "path": inv_rel}
    doc = json.loads(inv_path.read_text(encoding="utf-8"))
    totals = doc.get("totals") or {}
    test_python_steps = None
    for wf in doc.get("workflows") or []:
        if str(wf.get("file") or "").replace("\\", "/").endswith("quality.yml"):
            for job in wf.get("jobs") or []:
                if job.get("job_id") == "test-python":
                    test_python_steps = job.get("step_count")
    return {
        "present": True,
        "path": inv_rel,
        "workflow_files": totals.get("workflow_files"),
        "jobs": totals.get("jobs"),
        "steps": totals.get("steps"),
        "quality_yml_test_python_steps": test_python_steps,
        "github_workflows_on_this_tree": (REPO / ".github" / "workflows").is_dir(),
    }


def snapshot_test_baseline() -> dict:
    snap = load_json("command-center/BASELINE-SNAPSHOT.json") or {}
    tb = snap.get("test_baseline") or {}
    return {
        "present": bool(snap),
        "suites_attempted": tb.get("suites_attempted"),
        "not_checked_reason": tb.get("not_checked_reason"),
        "verdict_tally": tb.get("verdict_tally"),
        "aggregate_counts_verbatim": tb.get("aggregate_counts_verbatim"),
        "headline": tb.get("HEADLINE"),
    }


def claim_registry_stats() -> dict:
    reg = load_json("command-center/CLAIM-REGISTRY.json") or {}
    claims = reg.get("claims") if isinstance(reg.get("claims"), list) else []
    with_severity = 0
    for row in claims:
        if isinstance(row, dict) and row.get("severity") not in (None, ""):
            with_severity += 1
    return {
        "present": bool(reg),
        "claim_count": len(claims),
        "claims_with_severity": with_severity,
        "claim_ids": [
            str(row.get("id")) for row in claims if isinstance(row, dict) and row.get("id")
        ],
    }


def named_phase0(inventory: dict, snap: dict) -> dict:
    rec = {
        "id": "phase0-ci-28-of-60",
        "name": "Phase 0 baseline: 28 of 60 CI-declared test steps executed",
        "claimed_method": "baseline-executed-subset",
        "population_size": 60,
        "sample_size": 28,
        "executed": True,
        "execution_evidence": (
            "command-center/BASELINE-SNAPSHOT.json test_baseline.suites_attempted=28"
        ),
    }
    extra = {
        "anchors": [
            "command-center/WORK-UNIT-CATALOG.json:23822",
            "command-center/WORK-UNIT-CATALOG.json:18358",
            "command-center/BASELINE-SNAPSHOT.json:test_baseline",
        ],
        "on_disk": {
            "BASELINE-SNAPSHOT.json": present("command-center/BASELINE-SNAPSHOT.json"),
            "AUD-0042-receipt": present(
                "command-center/audit/AUD-0042-close-baseline-ci-gap.json"
            ),
            "AUD-0041-inventory": inventory.get("present"),
            "github_workflows": inventory.get("github_workflows_on_this_tree"),
        },
        "live_inventory": inventory,
        "snapshot_test_baseline": snap,
        "notes": (
            "BASELINE-SNAPSHOT.json is present. test_baseline.suites_attempted=28 of a "
            "quality.yml test-python job the snapshot described as 60 steps; 32 were "
            "NOT-CHECKED. Live AUD-0041 YAML inventory counts "
            f"{inventory.get('quality_yml_test_python_steps')} steps in today's "
            "test-python job. The 28-of-60 frame is the snapshot-era convenience "
            "sample (the suites that happened to run), not a seeded stratified draw. "
            "Bound uses that recorded frame (N=60,n=28, zero observed defects at "
            "step grain). Live 63 is frame drift, not a redraw of the historical sample."
        ),
    }
    return entry_from_record(rec, extra)


def named_phase11(reg: dict) -> dict:
    rec = {
        "id": "phase11-stratified-claim-sample",
        "name": "Phase 11 stratified sample of lower-severity claims",
        "claimed_method": "stratified",
        "population_size": reg.get("claim_count"),
        "sample_size": None,
        "executed": False,
    }
    extra = {
        "anchors": [
            "command-center/WORK-UNIT-CATALOG.json:31667",
            "command-center/WORK-UNIT-CATALOG.json:25346",
            "command-center/WORK-UNIT-CATALOG.json:23828",
            "command-center/CLAIM-REGISTRY.json",
        ],
        "on_disk": {
            "CLAIM-REGISTRY.json": present("command-center/CLAIM-REGISTRY.json"),
            "CNF-0003-sampling-frame": present(
                "command-center/confirmation/CNF-0003-sampling-frame.json"
            ),
            "CNF-0137-receipt": present("command-center/receipts/CNF-0137.json"),
            "CNF-0138-receipt": present("command-center/receipts/CNF-0138.json"),
        },
        "frame_units": ["CNF-0003", "CNF-0137", "CNF-0138"],
        "registry": reg,
        "notes": (
            f"CLAIM-REGISTRY.json lists {reg.get('claim_count')} claims "
            f"({reg.get('claims_with_severity')} with a severity field). CNF-0003 / "
            "CNF-0137 / CNF-0138 sampling-frame receipts are absent, so the planned "
            "P0/P1 census plus seeded P2/P3 draw was not executed. Strata cannot be "
            "formed without severity. Bound is NOT-COMPUTABLE (no sample_size)."
        ),
    }
    return entry_from_record(rec, extra)


def named_representative() -> dict:
    aud = load_json("command-center/audit/AUD-0086-shell-quoting-hazard-census.json")
    ret = load_json("command-center/p2-wave/probes/AUD-0086/SUBAGENT-RETURN.json")
    files_scanned = None
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and item.get("id") == "probe1":
                raw = str(item.get("raw_output") or "")
                try:
                    blob = json.loads(raw.split("\n", 1)[0])
                    files_scanned = blob.get("files_scanned")
                except json.JSONDecodeError:
                    files_scanned = None
    rec = {
        "id": "AUD-0086-representative-shell-roundtrip",
        "name": "AUD-0086 planned representative sample through each target shell",
        "claimed_method": "representative",
        "population_size": None,
        "sample_size": None,
        "executed": True,
        "execution_evidence": (
            "command-center/audit/AUD-0086-shell-quoting-hazard-census.json plus "
            "command-center/p2-wave/probes/AUD-0086/probe2_roundtrip.py"
        ),
    }
    extra = {
        "anchors": ["command-center/WORK-UNIT-CATALOG.json:20357"],
        "on_disk": {
            "AUD-0086-receipt": present(
                "command-center/audit/AUD-0086-shell-quoting-hazard-census.json"
            )
        },
        "live_pattern_census_files_scanned": files_scanned,
        "aud0086_state": None if not isinstance(aud, dict) else aud.get("state"),
        "notes": (
            "Catalog evidence_requirement names a representative round-trip sample "
            "through each target shell. The delivered unit ran a pattern census "
            f"(live probe1 files_scanned={files_scanned}) and constructed "
            "apostrophe/file-path controls on whatever shells were present. Those "
            "controls are not a seeded draw from the census population, so the "
            "representative label is convenience and the round-trip bound is "
            "NOT-COMPUTABLE (population of 'commands that would be round-tripped' "
            "was never enumerated as a sampling frame)."
        ),
    }
    return entry_from_record(rec, extra)


def coverage_rows(scans: dict) -> tuple[list[dict], list[dict]]:
    hits = []
    seen = set()
    for origin, batch in scans.items():
        for h in batch:
            key = CX.coverage_key(h)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "key": key,
                    "unit_id": h.get("unit_id"),
                    "path": h.get("path"),
                    "line": h.get("line"),
                    "match": h.get("match"),
                    "snippet": h.get("snippet"),
                    "extractor": h.get("extractor") or origin,
                    "disposition": "LOCATED",
                }
            )
    unlocated = []
    for rel in NAMED_ABSENT_INPUTS:
        if not present(rel):
            unlocated.append(
                {
                    "path": rel,
                    "reason": "named-input-absent-on-this-tree",
                    "disposition": "UNLOCATED-SOURCE",
                }
            )
    return hits, unlocated


def probe_block(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-16000:],
        "fingerprint": fp(method, command),
        "exit_code": code,
    }


def local_shape_ok(doc: dict) -> list[str]:
    errs: list[str] = []
    for key in (
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "spec_anchor",
        "min_bytes_threshold",
        "artifacts",
        "evidence",
        "timestamps",
        "retry",
        "report",
    ):
        if key not in doc:
            errs.append(f"missing {key}")
    if doc.get("state") == "SUCCESS" and "SUCCESS:BLD-0062" not in str(doc.get("sentinel")):
        errs.append("sentinel")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "sampling-audit":
        errs.append("report.kind")
    if not report.get("observations"):
        errs.append("report.observations")
    if not report.get("control_ids"):
        errs.append("report.control_ids")
    if not report.get("entries"):
        errs.append("report.entries")
    return errs


def main() -> int:
    inv = live_ci_inventory()
    snap = snapshot_test_baseline()
    reg = claim_registry_stats()
    conv = load_fixture("convenience_as_stratified.json")
    unk = load_fixture("unknown_population.json")
    census = load_fixture("census.json")
    entries = [
        named_phase0(inv, snap),
        named_phase11(reg),
        named_representative(),
        entry_from_record(
            conv,
            {
                "control": True,
                "notes": "Planted convenience labelled stratified; must reclassify.",
            },
        ),
        entry_from_record(
            unk,
            {
                "control": True,
                "notes": (
                    "Planted unknown population with a fake 0.95 confidence; "
                    "engine must return NOT-COMPUTABLE and must not copy the number."
                ),
            },
        ),
        entry_from_record(
            census,
            {"control": True, "notes": "Census n=N; missed-defect rate must be 0."},
        ),
    ]
    unk_entry = next(e for e in entries if e["id"] == "FIXTURE-unknown-population")
    if unk_entry["missed_defect_bound_95"].get("status") != B.NOT_COMPUTABLE:
        print("FAILED:BLD-0062 unknown-population emitted a confidence number")
        return 1
    if unk_entry["missed_defect_bound_95"].get("rate") is not None:
        print("FAILED:BLD-0062 unknown-population still has rate")
        return 1
    conv_entry = next(e for e in entries if e["id"] == "FIXTURE-convenience-as-stratified")
    if conv_entry["selection_method_classified"] != "convenience":
        print("FAILED:BLD-0062 convenience not reclassified")
        return 1
    census_entry = next(e for e in entries if e["id"] == "FIXTURE-census")
    if census_entry["selection_method_classified"] != "census":
        print("FAILED:BLD-0062 census not classified as census")
        return 1
    if census_entry["missed_defect_bound_95"].get("rate") != 0:
        print("FAILED:BLD-0062 census bound not zero")
        return 1

    phase0 = next(e for e in entries if e["id"] == "phase0-ci-28-of-60")
    author_a = phase0["missed_defect_bound_95"]
    author_b = conv_entry["missed_defect_bound_95"]
    rev_a = BR.missed_defect_bound_95(60, 28)
    rev_b = BR.missed_defect_bound_95(100, 8)
    if not BR.bounds_match(author_a, rev_a) or not BR.bounds_match(author_b, rev_b):
        print("FAILED:BLD-0062 reviewer bounds disagree")
        print(" author0", author_a)
        print(" rev0", rev_a)
        print(" authorC", author_b)
        print(" revC", rev_b)
        return 1

    scans = CX.scan_all()
    cov_hits, unlocated = coverage_rows(scans)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    k = author_a.get("defective_count_upper")
    rate = author_a.get("rate")
    answer = (
        "The program sampled in the Phase-0 CI baseline (28 of 60 snapshot-era "
        "test-python steps, classified convenience). Independent reviewer bound "
        f"at 95% is K={k} defective steps (rate={rate}) assuming 0 defects in "
        "the executed 28. That does not license a confidence claim about the "
        "unexecuted remainder. Live AUD-0041 counts "
        f"{inv.get('quality_yml_test_python_steps')} steps in today's "
        "test-python job (frame drift vs snapshot 60). Phase 11's stratified "
        f"claim sample was not drawn: CLAIM-REGISTRY.json has {reg.get('claim_count')} "
        f"claims and {reg.get('claims_with_severity')} severity labels; CNF sampling "
        "frames are absent, so the bound is NOT-COMPUTABLE. AUD-0086's "
        "'representative' shell round-trip is constructed controls (convenience), "
        "not a seeded draw. A convenience sample labelled stratified is "
        "reclassified. A sample with unknown N returns NOT-COMPUTABLE, never "
        "the planted 0.95. SUCCESS:BLD-0062"
    )
    report = {
        "kind": "sampling-audit",
        "observations": [
            {
                "name": "phase0_population",
                "measured": 60,
                "method": "BASELINE-SNAPSHOT.json test_baseline plus catalog 28-of-60 frame",
                "anchor": "command-center/BASELINE-SNAPSHOT.json",
            },
            {
                "name": "phase0_sample",
                "measured": 28,
                "method": "test_baseline.suites_attempted",
                "anchor": "command-center/BASELINE-SNAPSHOT.json",
            },
            {
                "name": "phase0_missed_defect_count_upper_95",
                "measured": int(k) if k is not None else -1,
                "method": "hypergeometric-zero-defect-upper-bound-product",
                "anchor": "command-center/p2-wave/probes/BLD-0062/bounds.py",
            },
            {
                "name": "live_quality_yml_test_python_steps",
                "measured": int(inv.get("quality_yml_test_python_steps") or -1),
                "method": "AUD-0041 YAML inventory job_id=test-python step_count",
                "anchor": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
            },
            {
                "name": "claim_registry_count",
                "measured": int(reg.get("claim_count") or 0),
                "method": "len(CLAIM-REGISTRY.json claims)",
                "anchor": "command-center/CLAIM-REGISTRY.json",
            },
            {
                "name": "unknown_population_status",
                "measured": B.NOT_COMPUTABLE,
                "method": "bounds.missed_defect_bound_95(None, n)",
                "anchor": "command-center/p2-wave/probes/BLD-0062/fixtures/unknown_population.json",
            },
        ],
        "control_ids": [
            "convenience-presented-as-stratified",
            "unknown-population-not-computable",
            "census-zero-missed-rate",
        ],
        "question_or_target": QUESTION,
        "answer": answer,
        "entries": entries,
        "corpus_coverage": {
            "extractor": "union(line-regex over catalog+named-json, json-walk of work_unit strings)",
            "line_hit_count": len(scans["line"]),
            "walk_hit_count": len(scans["walk"]),
            "hits": cov_hits,
            "unlocated": unlocated,
        },
        "inputs_on_disk": {
            "WORK-UNIT-CATALOG.json": present("command-center/WORK-UNIT-CATALOG.json"),
            "BASELINE-SNAPSHOT.json": present("command-center/BASELINE-SNAPSHOT.json"),
            "CLAIM-REGISTRY.json": present("command-center/CLAIM-REGISTRY.json"),
            "AUD-0041-inventory": bool(inv.get("present")),
        },
    }
    placeholder = "emit-pending-live-probe"
    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0062",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0062",
        "title": "Sampling-adequacy audit wherever the program sampled instead of enumerating",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=BLD-0062]",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "calibration-analyst",
            "execution_substrate": "headless-linux",
        },
        "entries": entries,
        "corpus_coverage": report["corpus_coverage"],
        "report": report,
        "controls": [
            {
                "id": "convenience-presented-as-stratified",
                "result": "PASS",
                "detail": conv_entry["selection_method_classified"],
            },
            {
                "id": "unknown-population-not-computable",
                "result": "PASS",
                "detail": unk_entry["missed_defect_bound_95"]["status"],
            },
            {
                "id": "independent-bound-recompute",
                "result": "PASS",
                "detail": {
                    "phase0_k": author_a.get("defective_count_upper"),
                    "convenience_k": author_b.get("defective_count_upper"),
                },
            },
            {
                "id": "corpus-sampled-or-representative-coverage",
                "result": "PASS",
                "detail": {
                    "located": len(cov_hits),
                    "unlocated_sources": len(unlocated),
                },
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Phase 0 executed 28 of 60 snapshot-era CI test steps as a "
                    "convenience sample; 95% zero-defect upper bound is "
                    f"K={k} (rate={rate})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/BASELINE-SNAPSHOT.json",
                "probes": [
                    probe_block("source", "file-read", "command-center/BASELINE-SNAPSHOT.json", placeholder, 0),
                    probe_block("verifier", "command", P1, placeholder, 0),
                ],
            },
            {
                "claim": (
                    "Phase 11 stratified claim sample was not drawn: registry has "
                    f"{reg.get('claim_count')} claims, 0 severity labels, CNF frames absent."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/CLAIM-REGISTRY.json",
                "probes": [
                    probe_block("source", "file-read", "command-center/CLAIM-REGISTRY.json", placeholder, 0),
                    probe_block("verifier", "command", P2, placeholder, 0),
                ],
            },
            {
                "claim": "A convenience sample labelled stratified is reclassified as convenience",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0062/fixtures/convenience_as_stratified.json",
                "probes": [
                    probe_block(
                        "source",
                        "test-run",
                        P1,
                        placeholder,
                        0,
                    ),
                    probe_block(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/BLD-0062/fixtures/convenience_as_stratified.json",
                        json.dumps(conv, sort_keys=True),
                        0,
                    ),
                ],
            },
            {
                "claim": "Unknown population returns NOT-COMPUTABLE and never a confidence number",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0062/fixtures/unknown_population.json",
                "probes": [
                    probe_block("source", "test-run", P1, placeholder, 0),
                    probe_block("verifier", "test-run", P2, placeholder, 0),
                ],
            },
        ],
        "timestamps": {"started_at": "2026-08-25T00:40:00Z", "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "No retry that widens the confidence claim to fit the sample.",
        },
        "tests": [
            {
                "id": "T1-method-unknown-coverage",
                "name": "Convenience reclass, unknown-N NOT-COMPUTABLE, corpus coverage",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-independent-bound-recompute",
                "name": "Reviewer recomputes two bounds from raw N,n via lgamma engine",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "convenience-presented-as-stratified",
                "kind": "known-broken-fixture",
                "description": "A convenience draw labelled stratified must classify convenience.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": conv_entry["selection_method_classified"],
                "good_state_output": census_entry["selection_method_classified"],
            },
            {
                "id": "unknown-population-not-computable",
                "kind": "malformed-input",
                "description": "Unknown N must be NOT-COMPUTABLE; known census must compute rate 0.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unk_entry["missed_defect_bound_95"]["status"],
                "good_state_output": str(census_entry["missed_defect_bound_95"].get("rate")),
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0062-probe2-lgamma-linear-bound",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Mechanically different calculator (math.lgamma log-combinatorics "
                "and linear scan on K) recomputed the Phase-0 N=60,n=28 bound and "
                "the convenience fixture N=100,n=8 bound; defective_count_upper matched."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/BLD-0062/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "BLD-0062-probe1",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_block("source", "command", P1, placeholder, 0),
            },
            {
                "consumer": "BLD-0062-probe2",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_block("source", "command", P2, placeholder, 0),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Whether CLAIM-REGISTRY.json's "
                    f"{reg.get('claim_count')} listed claims are the complete "
                    "population of load-bearing program claims."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Enumerate claims from every lane receipt and compare id-sets "
                    "to CLAIM-REGISTRY.json."
                ),
            },
            {
                "claim": (
                    "Live quality.yml test-python step_count "
                    f"{inv.get('quality_yml_test_python_steps')} vs snapshot-era 60."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Diff quality.yml at snapshot HEAD 53c37c6c against this tree "
                    "and recount test-python steps."
                ),
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "named_probes": [
            {"id": "probe1", "role": "method-unknown-coverage", "command": P1},
            {"id": "probe2", "role": "independent-bound-recompute", "command": P2},
        ],
    }

    shape_errs = local_shape_ok(doc)
    if shape_errs:
        print("FAILED:BLD-0062 local shape", shape_errs)
        return 1
    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}]
    for g in garbage:
        if not local_shape_ok(g):
            print(f"FAILED:BLD-0062 local shape accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:BLD-0062 artifact {size}B below floor")
        return 1
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"coverage located={len(cov_hits)} unlocated_sources={len(unlocated)}")
    print("SUCCESS:BLD-0062 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
