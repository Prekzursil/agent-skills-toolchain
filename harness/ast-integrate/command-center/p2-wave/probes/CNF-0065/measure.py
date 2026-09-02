"""Run local equivalents and classify each cited number."""
from __future__ import annotations

from typing import Any

import citations as C
import harness as H
import stats as S


def _measured_ok(raw: list, median, q1, q3, iqr) -> dict:
    return {
        "status": "measured",
        "repetitions": len(raw),
        "raw": raw,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
    }


def _not_run() -> dict:
    return {
        "status": "not-run",
        "repetitions": 0,
        "raw": [],
        "median": None,
        "q1": None,
        "q3": None,
        "iqr": None,
    }


def noise_floor() -> dict:
    raw = H.measure_repetitions(H.null_loop_ms, H.REPS)
    block = S.interval_block(raw)
    return {
        "cnf0027_artifact": "command-center/confirmation/CNF-0027-baseline-variance.json",
        "cnf0027_present": C.CNF0027.is_file(),
        "method": "11-rep null-loop time.perf_counter IQR on this host (CNF-0027 absent)",
        "repetitions": H.REPS,
        "raw_ms": raw,
        "median_ms": block["median"],
        "iqr_ms": block["iqr"],
        "interval": block,
        "origin": "this-unit-null-loop",
    }


def classify(claim: dict, floor: dict) -> dict:
    metric = claim["metric"]
    inferred: list[str] = []
    missing = claim.get("missing_prerequisite")
    row: dict[str, Any] = {
        "id": claim["id"],
        "origin": claim["origin"],
        "source": claim["source"],
        "cited_value": claim["cited_value"],
        "cited_unit": claim["cited_unit"],
        "disclosed_conditions": list(claim.get("disclosed_conditions") or []),
        "inferred_conditions": inferred,
        "tolerance": None,
        "missing_prerequisite": None,
    }

    if metric == "sha256-empty":
        raw = H.measure_repetitions(H.sha256_empty_hex, H.REPS)
        if any(x != H.EMPTY_SHA256 for x in raw):
            raise RuntimeError("sha256 empty digest not stable")
        cited = str(claim["cited_value"]).lower()
        got = raw[0].lower()
        row["measured"] = _measured_ok(raw, got, None, None, 0.0)
        row["verdict"] = "REPRODUCED" if cited == got else "NOT-REPRODUCIBLE"
        if row["verdict"] != "REPRODUCED":
            row["missing_prerequisite"] = (
                "FIPS empty-message vector mismatch on this hashlib"
            )
        return row

    if metric == "json-wire-size":
        default_n = H.json_wire_size(compact=False)
        compact_n = H.json_wire_size(compact=True)
        cited = int(claim["cited_value"])
        raw = H.measure_repetitions(lambda: H.json_wire_size(compact=True), H.REPS)
        row["measured"] = _measured_ok(raw, compact_n, compact_n, compact_n, 0.0)
        row["measurement_notes"] = {
            "default_dumps_bytes": default_n,
            "compact_sorted_bytes": compact_n,
            "default_matches_cited": default_n == cited,
            "compact_matches_cited": compact_n == cited,
        }
        if compact_n == cited and default_n != cited:
            inferred.extend(list(claim.get("undisclosed_conditions_required") or []))
            row["inferred_conditions"] = inferred
            row["verdict"] = "CONDITIONALLY-REPRODUCIBLE"
        elif compact_n == cited and default_n == cited:
            row["verdict"] = "REPRODUCED"
        else:
            row["verdict"] = "NOT-REPRODUCIBLE"
            row["missing_prerequisite"] = "encoder flags that yield the cited byte count"
        return row

    if metric in {"private-edit-acc", "aider-repo-map-accuracy-delta", "cnf0027-noise-floor"}:
        row["measured"] = _not_run()
        row["verdict"] = "NOT-REPRODUCIBLE"
        row["missing_prerequisite"] = missing or "named missing prerequisite"
        return row

    if metric == "null-loop-iqr-ms":
        raw = list(floor["raw_ms"])
        block = S.interval_block(raw)
        cited = float(claim["cited_value"])
        row["measured"] = _measured_ok(
            raw, block["median"], block["q1"], block["q3"], block["iqr"]
        )
        row["tolerance"] = block["iqr"]
        if cited <= block["iqr"]:
            row["verdict"] = "NOISE-DOMINATED"
            row["inferred_conditions"] = [
                "single-sample timing",
                "warmup discarded and not reported",
            ]
        else:
            row["verdict"] = "NOT-REPRODUCIBLE"
            row["missing_prerequisite"] = (
                "pinned quiesced host plus CNF-0027 noise floor larger than the cited delta"
            )
        return row

    raise KeyError(metric)


def run_all() -> dict:
    planted = C.load_planted()
    claims = C.frame()
    ids = [c["id"] for c in claims]
    seed = int(planted["seed"])
    k = int(planted.get("k") or len(ids))
    sampled = C.sample_ids(ids, seed, k)
    floor = noise_floor()
    by_id = {c["id"]: c for c in claims}
    classified = [classify(by_id[i], floor) for i in sampled]
    return {
        "frame_ids": ids,
        "seed": seed,
        "k": k,
        "sampled_ids": sampled,
        "noise_floor": floor,
        "claims": classified,
        "corpus_absences": C.corpus_absences(),
        "redraw": C.sample_ids(ids, seed, k),
    }
