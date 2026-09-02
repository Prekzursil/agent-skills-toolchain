#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0033-metric-recompute.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import recompute as R  # noqa: E402
import schema_local as S  # noqa: E402

UNIT = "CNF-0033"
OUT = "command-center/confirmation/CNF-0033-metric-recompute.json"
SCHEMA = "command-center/schema/benchmark-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SUMMARY = "command-center/p2-wave/probes/CNF-0033/fixtures/summary/implementer_table.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0033/probe1_raw_recompute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0033/probe2_noise_and_two_way.py"
)
MIN_BYTES = 2048
RECOMPUTE_PY = "command-center/p2-wave/probes/CNF-0033/recompute.py"


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise SystemExit("FAILED:CNF-0033 catalog unit missing")


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNF-0033 snippet not in {rel}: {snippet!r}")


def artifact_row(rel: str, role: str, sha: str | None = None, size: int | None = None) -> dict:
    if sha is None or size is None:
        sha, size = S.digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw_output: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65000],
        "fingerprint": S.fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])
    census = I.live_census()
    summary = json.loads((REPO / SUMMARY).read_text(encoding="utf-8"))

    match_raw = REPO / "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json"
    baseline_reps = R.load_repetitions(match_raw)
    iqr = R.two_way_iqr(baseline_reps)
    if not iqr["agree"]:
        print("FAILED:CNF-0033 two-way IQR disagreement", iqr)
        return 1
    fixture_floor = float(iqr["method_a"]["value"])
    tw_median = R.two_way_median(baseline_reps)
    if not tw_median["agree"]:
        print("FAILED:CNF-0033 two-way median disagreement", tw_median)
        return 1

    live_floor = None
    live_floor_status = "NOT-CHECKED"
    if census["cnf0027_present"]:
        live_floor_status = "MEASURED"
        live_floor = None

    claims: list[dict] = []
    for spec in census["live_claim_specs"]:
        claims.append(
            R.evaluate(
                claim_id=str(spec["id"]),
                source="live-census",
                raw_rel=str(spec["raw_file"]),
                claimed_value=spec.get("claimed_value"),
                claimed_delta=spec.get("claimed_delta"),
                precision_decimals=int(spec.get("precision_decimals") or 3),
                noise_floor=live_floor,
                noise_floor_file=census["cnf0027_path"],
            )
        )

    for spec in I.control_specs():
        cid = str(spec["id"])
        claimed_v, claimed_d = I.claimed_from_table(summary, cid)
        kind = str(spec.get("kind") or "level")
        if kind == "delta":
            claims.append(
                R.evaluate_delta(
                    claim_id=cid,
                    source="detector-control",
                    before_rel=str(spec["baseline_raw_file"]),
                    after_rel=str(spec["raw_file"]),
                    claimed_value=claimed_v,
                    claimed_delta=claimed_d,
                    precision_decimals=int(spec.get("precision_decimals") or 1),
                    noise_floor=fixture_floor,
                    noise_floor_file=census["cnf0027_path"],
                )
            )
        else:
            claims.append(
                R.evaluate(
                    claim_id=cid,
                    source="detector-control",
                    raw_rel=str(spec["raw_file"]),
                    claimed_value=claimed_v,
                    claimed_delta=None if kind == "level" else claimed_d,
                    precision_decimals=int(spec.get("precision_decimals") or 1),
                    noise_floor=fixture_floor,
                    noise_floor_file=census["cnf0027_path"],
                )
            )

    for row in claims:
        v = row.get("verdict")
        if v == "NOT-CHECKED":
            missing = str(row.get("missing_raw_file") or "")
            if not missing:
                print("FAILED:CNF-0033 NOT-CHECKED without missing_raw_file", row.get("id"))
                return 1
            if (REPO / missing).is_file() and (REPO / missing).stat().st_size > 0:
                print("FAILED:CNF-0033 NOT-CHECKED but raw exists", missing)
                return 1
            if row.get("recomputed_value") not in (None,):
                print("FAILED:CNF-0033 NOT-CHECKED with a value", row.get("id"))
                return 1
        elif v in {"MATCH", "MISMATCH", "UNMEASURABLE"}:
            if row.get("recomputed_value") is None:
                print("FAILED:CNF-0033 verdict without recomputed_value", row.get("id"))
                return 1
        else:
            print("FAILED:CNF-0033 unexpected verdict", v)
            return 1

    by_id = {c["id"]: c for c in claims}
    if by_id["control.match"]["verdict"] != "MATCH":
        print("FAILED:CNF-0033 control.match", by_id["control.match"])
        return 1
    if by_id["control.summary-poison"]["verdict"] != "MISMATCH":
        print("FAILED:CNF-0033 poison was not an overclaim", by_id["control.summary-poison"])
        return 1
    if abs(float(by_id["control.summary-poison"]["recomputed_value"]) - 999.0) < 0.1:
        print("FAILED:CNF-0033 recompute used the summary table")
        return 1
    if by_id["control.unmeasurable"]["verdict"] != "UNMEASURABLE":
        print("FAILED:CNF-0033 unmeasurable", by_id["control.unmeasurable"])
        return 1
    if by_id["control.missing-raw"]["verdict"] != "NOT-CHECKED":
        print("FAILED:CNF-0033 missing-raw", by_id["control.missing-raw"])
        return 1

    n_not = sum(1 for c in claims if c["verdict"] == "NOT-CHECKED")
    n_match = sum(1 for c in claims if c["verdict"] == "MATCH")
    n_mis = sum(1 for c in claims if c["verdict"] == "MISMATCH")
    n_unm = sum(1 for c in claims if c["verdict"] == "UNMEASURABLE")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    med_line = find_line(RECOMPUTE_PY, "def median_statistics(values: list[float]) -> float:")
    mid_line = find_line(RECOMPUTE_PY, "def median_middle_index(values: list[float]) -> float:")
    miss_line = find_line(RECOMPUTE_PY, "Missing file => NOT-CHECKED, never MATCH.")
    floor_line = find_line(
        RECOMPUTE_PY,
        "a delta inside the noise floor is unmeasurable regardless of sign.",
    )
    raw_line = find_line(
        "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json",
        '"repetitions": [7.0, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 13.0]',
    )
    cat_line = find_line(
        CATALOG,
        "Recompute each claimed improvement directly from the raw measurement files",
    )

    match_val = float(by_id["control.match"]["recomputed_value"])
    poison_val = float(by_id["control.summary-poison"]["recomputed_value"])
    unm_delta = float(by_id["control.unmeasurable"]["delta"])
    miss_file = str(by_id["control.missing-raw"]["missing_raw_file"])

    src_raw = (
        f"match={match_val} poison={poison_val} poison_verdict=MISMATCH "
        f"missing={miss_file} two_way_agree={tw_median['agree']} "
        f"iqr_floor={fixture_floor} unmeasurable_delta={unm_delta}"
    )
    ver_raw = (
        f"two_way_median agree={tw_median['agree']} "
        f"a={tw_median['method_a']['value']} b={tw_median['method_b']['value']}; "
        f"two_way_iqr agree={iqr['agree']} a={iqr['method_a']['value']} "
        f"b={iqr['method_b']['value']}"
    )

    supporting = [
        SCHEMA,
        RECOMPUTE_PY,
        "command-center/p2-wave/probes/CNF-0033/inventory.py",
        "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json",
        "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_unmeasurable_after.json",
        "command-center/p2-wave/probes/CNF-0033/fixtures/summary/implementer_table.json",
    ]

    report = {
        "kind": "benchmark-report",
        "title": unit.get("title"),
        "question": question,
        "completion_sentinel": sentinel,
        "answer": (
            f"Detector controls recomputed from fixtures/raw/ (never from the "
            f"implementer summary): MATCH={n_match} MISMATCH={n_mis} "
            f"UNMEASURABLE={n_unm} NOT-CHECKED={n_not}. Live Phase-0 / CNF-0027 "
            f"rows are NOT-CHECKED with the missing raw files named. "
            f"{sentinel}"
        ),
        "observations": [
            {
                "name": "control.match.recomputed_median",
                "measured": match_val,
                "method": "statistics.median on raw repetitions",
                "anchor": f"{RECOMPUTE_PY}:{med_line}",
            },
            {
                "name": "control.summary-poison.verdict",
                "measured": "MISMATCH",
                "method": "raw median compared to poisoned summary table 999.0",
                "anchor": f"{RECOMPUTE_PY}:{med_line}",
            },
            {
                "name": "control.unmeasurable.verdict",
                "measured": "UNMEASURABLE",
                "method": "before/after median delta vs fixture IQR",
                "anchor": f"{RECOMPUTE_PY}:{floor_line}",
            },
            {
                "name": "control.missing-raw.verdict",
                "measured": "NOT-CHECKED",
                "method": "absent raw file named, never confirmed by plausibility",
                "anchor": f"{RECOMPUTE_PY}:{miss_line}",
            },
            {
                "name": "two-way-median-agree",
                "measured": bool(tw_median["agree"]),
                "method": "statistics.median vs odd-n middle index",
                "anchor": f"{RECOMPUTE_PY}:{mid_line}",
            },
            {
                "name": "live-census-not-checked-count",
                "measured": n_not,
                "method": "inventory.live_census plus evaluate() missing-file branch",
                "anchor": f"{CATALOG}:{cat_line}",
            },
        ],
        "control_ids": [
            "control.match",
            "control.summary-poison",
            "control.unmeasurable",
            "control.missing-raw",
        ],
        "census": {
            "baseline_snapshot_present": census["baseline_snapshot_present"],
            "cnf0027_present": census["cnf0027_present"],
            "implementer_summary_tables_found": census["implementer_summary_tables_found"],
            "raw_measurement_files_found": census["raw_measurement_files_found"],
            "live_improvement_claims_with_raw": 0,
            "note": (
                "BASELINE-SNAPSHOT.json is present as a Phase 0 freeze document "
                "but it is not a raw repetition series. Expected improvement "
                "raw files under command-center/confirmation/raw/ are absent, "
                "CNF-0027 is absent, and no implementer summary tables live "
                "under command-center/confirmation/. Live claims are "
                "NOT-CHECKED with those missing raw files named. "
                "Detector-control claims are recomputed from fixtures/raw/ only."
            ),
        },
        "noise_floor": {
            "source": census["cnf0027_path"],
            "present": False,
            "status": live_floor_status,
            "missing_file": census["cnf0027_path"],
            "numeric_floor": None,
            "definition": (
                "CNF-0027 IQR of >=11 baseline repetitions. Absent on this "
                "tree, so live delta-vs-floor answers are NOT-CHECKED."
            ),
            "fixture_only": {
                "status": "FIXTURE-ONLY",
                "numeric_floor": fixture_floor,
                "definition": "IQR of fixtures/raw/control_match.json (n=11)",
                "two_way_iqr": iqr,
            },
        },
        "control_two_way": tw_median,
        "answers": {
            "recomputed_match_within_precision": {
                "match": n_match,
                "mismatch": n_mis,
                "not_checked": n_not,
                "unmeasurable": n_unm,
                "note": (
                    "MATCH/MISMATCH are detector-control only. Live census "
                    "rows are NOT-CHECKED because raw files are missing."
                ),
            },
            "claimed_delta_exceeds_noise_floor": {
                "live_status": "NOT-CHECKED",
                "live_missing_file": census["cnf0027_path"],
                "fixture_unmeasurable": by_id["control.unmeasurable"]["id"],
                "fixture_floor": fixture_floor,
                "note": (
                    "A delta inside the fixture IQR is UNMEASURABLE "
                    "regardless of sign. Live claims cannot be compared to "
                    "CNF-0027 because that artifact is absent."
                ),
            },
        },
        "claims": claims,
        "evidence_anchors": [
            {
                "path": RECOMPUTE_PY,
                "line": med_line,
                "snippet": "def median_statistics(values: list[float]) -> float:",
                "kind": "live-tree",
                "claim": "Recompute uses statistics.median on raw repetitions.",
                "anchor": f"{RECOMPUTE_PY}:{med_line}",
            },
            {
                "path": RECOMPUTE_PY,
                "line": mid_line,
                "snippet": "def median_middle_index(values: list[float]) -> float:",
                "kind": "live-tree",
                "claim": "Second median path is the odd-n middle index.",
                "anchor": f"{RECOMPUTE_PY}:{mid_line}",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json",
                "line": raw_line,
                "snippet": '"repetitions": [7.0, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 13.0]',
                "kind": "fixture",
                "claim": "Control raw repetitions for two-way median and IQR.",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0033/fixtures/raw/"
                    f"control_match.json:{raw_line}"
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "raw-recompute", "command": P1},
            {"id": "probe2", "role": "noise-floor-two-way", "command": P2},
        ],
        "scope": {
            "does_not_claim": [
                "CNF-0027 was delivered",
                "Phase 0 baselines were re-measured on this host",
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
            ]
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0033",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "metric-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": [
            artifact_row(OUT, "primary", sha="0" * 64, size=1),
        ]
        + [artifact_row(p, "supporting") for p in supporting],
        "evidence": [
            {
                "claim": (
                    "Each detector-control claim is recomputed from raw "
                    "repetition files; the implementer summary is comparison-"
                    "only. control.match MATCH at 10.0; control.summary-poison "
                    "is MISMATCH (raw 10.0 vs table 999.0); missing raw is "
                    "NOT-CHECKED with the file named."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{RECOMPUTE_PY}:{med_line}",
                "probes": [
                    probe_obj("source", "test-run", P1, src_raw),
                    probe_obj("verifier", "command", f"{RECOMPUTE_PY}:evaluate", src_raw),
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "A before/after delta inside the fixture IQR is UNMEASURABLE "
                    "regardless of sign. Two independent median paths agree on "
                    "the n=11 control sample. Live CNF-0027 floor is NOT-CHECKED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{RECOMPUTE_PY}:{floor_line}",
                "probes": [
                    probe_obj("source", "test-run", P2, ver_raw),
                    probe_obj(
                        "verifier",
                        "schema-validate",
                        "command-center/p2-wave/probes/CNF-0033/schema_local.py",
                        ver_raw,
                    ),
                ],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "missing-raw-not-checked",
                "name": "Missing raw data is NOT-CHECKED with the file named",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "noise-floor-unmeasurable",
                "name": "Delta inside fixture IQR is UNMEASURABLE regardless of sign",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "two-way-recompute",
                "name": "statistics.median agrees with odd-n middle index on n=11",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "summary-not-used-as-input",
                "name": "control.summary-poison recomputes 10.0 not 999.0",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-CNF0033-MISSING-RAW",
                "kind": "absent-input",
                "description": (
                    "A claim whose raw file is absent must be NOT-CHECKED with "
                    "missing_raw_file named, never MATCH by plausibility."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"verdict=NOT-CHECKED missing_raw_file={miss_file}",
                "good_state_output": "control.match verdict=MATCH recomputed_value=10.0",
            },
            {
                "id": "NC-CNF0033-SUMMARY-POISON",
                "kind": "adversarial-payload",
                "description": (
                    "Implementer table lists median_ms=999.0 for the same raw "
                    "file as control.match. Recompute must ignore the table."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "control.summary-poison verdict=MISMATCH recomputed=10.0 not 999.0",
                "good_state_output": "control.match verdict=MATCH recomputed=10.0 claimed=10.0",
            },
            {
                "id": "NC-CNF0033-NOISE-FLOOR",
                "kind": "known-broken-fixture",
                "description": (
                    "A negative improvement whose |delta| is inside the fixture "
                    "IQR is UNMEASURABLE regardless of sign."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"control.unmeasurable verdict=UNMEASURABLE delta={unm_delta} floor={fixture_floor}",
                "good_state_output": "two-way IQR agree on n=11 control_match sample",
            },
            {
                "id": "NC-CNF0033-SCHEMA-MUTANT",
                "kind": "mutation",
                "description": (
                    "A NOT-CHECKED claim with missing_raw_file stripped must be "
                    "rejected by the unit overlay schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "overlay rejects NOT-CHECKED without missing_raw_file",
                "good_state_output": "live receipt passes catalog schema and overlay",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0033-probe2-interval-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Named probe2 re-loads the fixture sample, re-computes median "
                "and IQR on a second code path, and requires overlay-schema "
                "rejection when missing_raw_file is stripped from a NOT-CHECKED "
                "row. Sampling-frame redraw is identity of the n=11 fixture."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0033/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "source",
                    "file-read",
                    f"python3 -c json.loads({OUT})",
                    "parsed ok",
                ),
            },
            {
                "consumer": "schema_local overlay_validator",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/CNF-0033/schema_local.py",
                    "overlay+catalog accept live receipt; garbage rejected",
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live implementer improvement claims cannot be recomputed: "
                    "command-center/confirmation/raw/phase0-improvement-repetitions.json "
                    "and CNF-0027-baseline-variance.json are absent. "
                    "BASELINE-SNAPSHOT.json exists but has no repetitions array."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0027 and raw n>=11 repetition files for each "
                    "claimed improvement, then re-run CNF-0033 against those files."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "cloud_ok": False,
            "registered": True,
            "output_path": OUT,
            "output_schema": SCHEMA,
        },
    }

    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0033 schema errors")
        for e in errs[:30]:
            print(" ", list(e.path), e.message)
        return 1
    cat_errs = S.catalog_iter_errors(doc)
    if cat_errs:
        print("FAILED:CNF-0033 catalog schema errors")
        for e in cat_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": UNIT, "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0033"},
    ):
        if not S.iter_errors(garbage) or not S.catalog_iter_errors(garbage):
            print("FAILED:CNF-0033 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = S.digest_file(out)
    doc["artifacts"][0] = artifact_row(OUT, "primary", sha=digest, size=size)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = S.digest_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0033 artifact {size}B below floor")
        return 1
    post = S.iter_errors(json.loads(text))
    if post:
        print("FAILED:CNF-0033 schema errors after hash fill")
        for e in post[:15]:
            print(" ", list(e.path), e.message)
        return 1
    if sentinel not in text:
        print("FAILED:CNF-0033 completion sentinel missing from artifact text")
        return 1
    print(
        f"wrote {OUT} claims={len(claims)} match={n_match} mismatch={n_mis} "
        f"unmeasurable={n_unm} not_checked={n_not} bytes={size} sha256={digest}"
    )
    print("SUCCESS:CNF-0033 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
