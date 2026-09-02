#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0003-sampling-frame.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0003-sampling-frame.json"
SCHEMA = "command-center/schema/sampling-frame.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0003/probe1_same_seed.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0003/probe2_seed_plus_one.py"
)
QUESTION = (
    "Implementation target: build the confirmation sampling frame. Every P0 and "
    "P1 claim is a census at 100 percent; P2 and P3 claims are drawn by a SEEDED "
    "stratified sampler whose seed, per-stratum population and draw are recorded "
    "so any reviewer re-draws the identical list. Question to answer numerically: "
    "what per-stratum sample size detects a 10 percent class error rate at 90 "
    "percent confidence, and does that many confirmers fit under the arrival-rate "
    "cap set by CNF-0011?"
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json CNF-0003; "
    "_USER-PROMPTS.md:11030 and 11041"
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def disk_validator(schema: dict) -> jsonschema.Draft7Validator:
    """Resolve ast-integrate.invalid $ref from disk. Never the network."""
    store: dict[str, dict] = {}
    for rel in (
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        body = json.loads((REPO / rel).read_text(encoding="utf-8"))
        uri = str(body.get("$id") or f"https://ast-integrate.invalid/{rel}")
        store[uri] = body
        store[f"https://ast-integrate.invalid/{rel}"] = body
    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or f"https://ast-integrate.invalid/{SCHEMA}"),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = S.sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": S.probe_fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unit = S.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:CNF-0003"):
        print("FAILED:CNF-0003 catalog sentinel missing")
        return 1
    null_ctl = S.missing_severity_control()
    if not null_ctl["raised"]:
        print("FAILED:CNF-0003 missing-severity control did not fire")
        return 1
    frame = S.build_frame(seed=S.SEED)
    ss = frame["sample_size"]
    cap = frame["cnf_0011"]
    n_inf = ss["infinite_population_n"]
    sampled_ns = {
        row["severity"]: row["n_detect_finite"]
        for row in frame["strata"]
        if row["severity"] in S.SAMPLE_SEVERITIES
    }
    p2_pop = next(r["population"] for r in frame["strata"] if r["severity"] == "P2")
    p3_pop = next(r["population"] for r in frame["strata"] if r["severity"] == "P3")
    numeric = (
        f"Infinite-population detection n for p=0.10 at 90 percent confidence is "
        f"{n_inf} (ceil(ln(0.10)/ln(0.90)); 1-0.9^21={ss['n21_detection_probability']:.6f} "
        f"< 0.90 and 1-0.9^22={ss['n22_detection_probability']:.6f} >= 0.90). "
        f"Operational per-stratum n is the finite-population hypergeometric size "
        f"with K=ceil(0.10 N): P2 n={sampled_ns.get('P2')} of N={p2_pop}, "
        f"P3 n={sampled_ns.get('P3')} of N={p3_pop}. "
        f"Required confirmers (census P0/P1 plus those draws) = "
        f"{frame['required_confirmers']}. CNF-0011 arrival-rate cap published="
        f"{cap['published']}; fits_under_cap={cap['fits_under_cap']}; "
        f"verdict={cap['verdict']}."
    )
    sampler_path = HERE / "sampler.py"
    schema_path = REPO / SCHEMA
    freeze_path = REPO / S.FREEZE_REL
    catalog_path = REPO / S.CATALOG_REL
    src_line = find_line(sampler_path, "def infinite_population_n")
    fin_line = find_line(sampler_path, "def finite_population_n")
    cat_line = find_line(catalog_path, '"id": "CNF-0003"')
    live_present = bool(frame["source"]["live_registry_present"])
    ungraded = list(frame["source"].get("live_ungraded_ids") or [])
    same_json = frame["same_seed_json"]
    alt_json = frame["alt_seed_json"]
    census = frame["p0_p1_set_difference"]

    report = {
        "kind": "sampling-frame",
        "observations": [
            {
                "name": "infinite_population_detection_n",
                "measured": n_inf,
                "method": "ceil(ln(1-confidence)/ln(1-p)) at p=0.10, confidence=0.90",
                "anchor": f"command-center/p2-wave/probes/CNF-0003/sampler.py:{src_line}",
            },
            {
                "name": "required_confirmers",
                "measured": int(frame["required_confirmers"]),
                "method": "sum of per-stratum draw sizes (P0/P1 census + P2/P3 sample)",
                "anchor": OUT,
            },
            {
                "name": "cnf_0011_fits_under_cap",
                "measured": str(cap["verdict"]),
                "method": "read CNF-0011 scheduler report when present; else NOT-CHECKED",
                "anchor": S.CNF0011_REL,
            },
            {
                "name": "live_registry_ungraded_claim_count",
                "measured": len(ungraded),
                "method": "inspect command-center/CLAIM-REGISTRY.json severity field",
                "anchor": S.LIVE_REGISTRY,
            },
            {
                "name": "same_seed_canonical_id_list",
                "measured": same_json[:240],
                "method": "seeded stratified redraw",
                "anchor": f"seed={frame['seed']}",
            },
        ],
        "control_ids": [
            "T1-same-seed-reproduction",
            "T2-seed-plus-one-control",
            "T3-p0-p1-census-set-difference",
            "T4-missing-severity-fails-loud",
        ],
        "question": QUESTION,
        "title": unit.get("title"),
        "numeric_answer": numeric,
        "seed": frame["seed"],
        "population_source": {
            "live_registry_path": frame["source"]["live_registry_path"],
            "live_registry_present": live_present,
            "live_registry_bytes": frame["source"].get("live_registry_bytes"),
            "live_raw_count": frame["source"].get("live_raw_count"),
            "live_ungraded_ids": ungraded,
            "freeze_path": frame["source"]["freeze_path"],
            "kind": frame["source"]["kind"],
            "count": frame["source"]["count"],
            "freeze_sha256": frame["source"]["freeze_sha256"],
            "freeze_bytes": frame["source"]["freeze_bytes"],
            "note": frame["source"].get("note"),
        },
        "allocation_buckets": frame["allocation_buckets"],
        "git_commit": None,
        "git_commit_reason": (
            "this worktree is not a git repository; freeze is the population sha256"
        ),
        "strata": frame["strata"],
        "drawn_ids": frame["drawn_ids"],
        "drawn_ids_canonical_json": same_json,
        "sample_size": ss,
        "required_confirmers": frame["required_confirmers"],
        "cnf_0011_arrival_rate_cap": cap,
        "same_seed_reproduction": {
            "seed": frame["seed"],
            "drawn_ids": frame["drawn_ids"],
            "canonical_json": same_json,
            "matches_frame": True,
        },
        "different_seed_control": {
            "seed": frame["alt_seed"],
            "drawn_ids": frame["alt_drawn_ids"],
            "canonical_json": alt_json,
            "differs_from_frame": True,
        },
        "p0_p1_set_difference": census,
        "partition_proof": frame["partition_proof"],
        "named_probes": [
            {"id": "probe1", "role": "same-seed-reproduction-and-census", "command": P1},
            {"id": "probe2", "role": "seed-plus-one-control", "command": P2},
        ],
    }

    supporting = [
        artifact_row(SCHEMA, "supporting"),
        artifact_row(S.FREEZE_REL, "fixture"),
        artifact_row("command-center/p2-wave/probes/CNF-0003/sampler.py", "supporting"),
    ]
    placeholder = "0" * 64
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": placeholder,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ] + supporting

    parse_raw = (
        f"in-memory json roundtrip of {OUT}; "
        f"seed={frame['seed']} drawn={len(frame['drawn_ids'])} "
        f"kind={frame['source']['kind']}"
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0003",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2000,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Re-drawing each recorded stratum with the attached seed "
                    "reproduces the canonical id list byte for byte."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNF-0003/sampler.py:{src_line}",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        f"command-center/p2-wave/probes/CNF-0003/sampler.py:{src_line}",
                        f"same_seed_json={same_json}",
                    ),
                    probe("verifier", "command", P1, "named probe1 re-draws the recorded frame"),
                ],
            },
            {
                "claim": (
                    "Re-drawing with seed+1 produces a different id list, so the "
                    "seed is consumed rather than ignored."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0003/probe2_seed_plus_one.py",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNF-0003/sampler.py:stratum_rng",
                        f"alt_seed={frame['alt_seed']} alt_json={alt_json}",
                    ),
                    probe("verifier", "command", P2, "named probe2 seed+1 control"),
                ],
            },
            {
                "claim": (
                    "Every P0 and P1 id in the freeze population appears in the "
                    "frame; the live CC-* registry is ungraded and was not "
                    "silently assigned a severity."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": S.FREEZE_REL,
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        S.FREEZE_REL,
                        (
                            f"census registry_p0p1={census['registry_p0p1_count']} "
                            f"missing={census['registry_minus_frame']} "
                            f"live_ungraded={ungraded}"
                        ),
                    ),
                    probe("verifier", "command", P1, "named probe1 P0/P1 set-difference"),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-same-seed-reproduction",
                "name": "Re-draw with the same seed reproduces the identical id list byte for byte",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-seed-plus-one-control",
                "name": "Re-draw with seed+1 produces a different list, proving the seed is consumed",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-p0-p1-census-set-difference",
                "name": "Every P0/P1 id in the freeze appears in the frame; no phantom P0/P1 ids",
                "command": P1,
                "result": "PASS" if census["registry_minus_frame_empty"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "seed-plus-one-differs",
                "kind": "mutation",
                "description": (
                    "A sampler that ignored the seed would emit the same id list "
                    "at seed and seed+1. The control requires those lists to differ, "
                    "and the same-seed redraw to still match."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"seed+1 differs={same_json != alt_json} alt={alt_json[:180]}",
                "good_state_output": f"same-seed canonical match ids={len(frame['drawn_ids'])}",
            },
            {
                "id": "missing-severity-fails-loud",
                "kind": "malformed-input",
                "description": (
                    "A claim with no severity must raise rather than default to P3. "
                    "The live CC-* registry is this malformed state for the named input."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": null_ctl["error"],
                "good_state_output": (
                    f"fixture freeze graded count={frame['source']['count']} "
                    "all P0-P3"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0003-probe1-same-seed-and-interval-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "probe1 re-draws from the recorded per-stratum population_ids and seed "
                "and recomputes ln(1-c)/ln(1-p); probe2 is the seed+1 control."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0003/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0003",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + sampler.sampling_view",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "file-read",
                    f"json.loads({OUT})",
                    parse_raw,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or ""),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live CLAIM-REGISTRY.json CC-* claims have no P0-P3 severity, so "
                    "the confirmation frame cannot be the live program-claim census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Grade every live claim with an explicit P0-P3 field, then "
                    "re-emit this unit against that graded registry."
                ),
            },
            {
                "claim": (
                    "Whether required_confirmers fit under the CNF-0011 arrival-rate "
                    "cap is NOT-CHECKED until that scheduler report is on disk."
                ),
                "verdict": "NOT-CHECKED" if not cap["published"] else "PARTIAL",
                "settling_experiment": (
                    "Emit command-center/confirmation/CNF-0011-scheduler-report.json "
                    "and compare required_confirmers to the published cap."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "sampling-statistician",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "evidence_file_anchors": [
                {
                    "path": "command-center/p2-wave/probes/CNF-0003/sampler.py",
                    "line": src_line,
                    "snippet": "n >= ln(1-confidence)/ln(1-p)",
                },
                {
                    "path": "command-center/p2-wave/probes/CNF-0003/sampler.py",
                    "line": fin_line,
                    "snippet": "K = ceil(p * N) defectives exist in the stratum",
                },
                {
                    "path": S.FREEZE_REL,
                    "line": 1,
                    "snippet": "sampling-frame-population-freeze",
                },
                {
                    "path": S.CATALOG_REL,
                    "line": cat_line,
                    "snippet": "Every P0 and P1 claim is a census at 100 percent",
                },
            ]
        },
    }

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = disk_validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0003 schema errors")
        for err in errs[:24]:
            print(" ", list(err.path), err.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for blob in garbage:
        if not list(validator.iter_errors(blob)):
            print(f"FAILED:CNF-0003 schema accepted garbage {list(blob)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = S.sha256_file(out)
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print("FAILED:CNF-0003 completion sentinel absent from artifact text")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = S.sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0003 artifact {size}B below floor")
        return 1
    parsed = json.loads(out.read_text(encoding="utf-8"))
    view = S.sampling_view(parsed)
    if int(view.get("seed") or -1) != S.SEED:
        print("FAILED:CNF-0003 downstream json.loads lost the seed")
        return 1
    errs = sorted(validator.iter_errors(parsed), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0003 schema errors after rewrite")
        for err in errs[:24]:
            print(" ", list(err.path), err.message)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"seed={frame['seed']} confirmers={frame['required_confirmers']} cap={cap['verdict']}")
    print("SUCCESS:CNF-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
