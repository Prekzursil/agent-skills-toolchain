"""Coverage / artifact / count checks with both-states and negative-control faces."""
from __future__ import annotations

from copy import deepcopy


def count_check(family_ids: list[str], expected_n: int = 7) -> dict:
    n = len(family_ids)
    unique = len(set(family_ids))
    fired = n != expected_n or unique != n
    return {
        "id": "family-count",
        "fired": fired,
        "silent": not fired,
        "got": n,
        "unique": unique,
        "expected": expected_n,
        "reason": None
        if not fired
        else f"family-count-mismatch got={n} unique={unique} expected={expected_n}",
    }


def coverage_check(verdicts: list[dict], family_ids: list[str]) -> dict:
    have = {v.get("record_id") for v in verdicts}
    want = set(family_ids)
    missing = sorted(want - have)
    extra = sorted(have - want)
    incomplete = [
        v["record_id"]
        for v in verdicts
        if v.get("executability") not in {"EXECUTABLE", "NOT-EXECUTABLE"}
    ]
    not_exec_without_missing = [
        v["record_id"]
        for v in verdicts
        if v.get("executability") == "NOT-EXECUTABLE" and not v.get("missing_element")
    ]
    fired = bool(missing or extra or incomplete or not_exec_without_missing)
    reason = None
    if missing:
        reason = f"coverage-missing:{','.join(missing)}"
    elif extra:
        reason = f"coverage-extra:{','.join(extra)}"
    elif incomplete:
        reason = f"coverage-incomplete-verdict:{','.join(incomplete)}"
    elif not_exec_without_missing:
        reason = f"not-executable-unnamed-missing:{','.join(not_exec_without_missing)}"
    return {
        "id": "family-coverage",
        "fired": fired,
        "silent": not fired,
        "missing": missing,
        "extra": extra,
        "reason": reason,
    }


def artifact_check(verdicts: list[dict]) -> dict:
    bad = []
    for v in verdicts:
        if v.get("executability") != "EXECUTABLE":
            continue
        art = v.get("artifact") or {}
        if not art.get("name") or not art.get("keys"):
            bad.append(v.get("record_id"))
    fired = bool(bad)
    return {
        "id": "concrete-artifact",
        "fired": fired,
        "silent": not fired,
        "record_ids": bad,
        "missing_element": "concrete_artifact" if fired else None,
        "reason": None
        if not fired
        else f"executable-without-artifact:{','.join(bad)}",
    }


def run_checks(verdicts: list[dict], family_ids: list[str], expected_n: int = 7) -> dict:
    parts = [
        count_check(family_ids, expected_n),
        coverage_check(verdicts, family_ids),
        artifact_check(verdicts),
    ]
    fired = [p for p in parts if p["fired"]]
    return {
        "fired": bool(fired),
        "silent": not fired,
        "parts": parts,
        "reasons": [p["reason"] for p in fired],
    }


def plant_missing_artifact(verdicts: list[dict], record_id: str = "P40") -> list[dict]:
    planted = deepcopy(verdicts)
    for v in planted:
        if v.get("record_id") == record_id:
            v["executability"] = "EXECUTABLE"
            v["artifact"] = {"name": "", "keys": [], "produced": None}
            v["plant"] = "empty-concrete-artifact"
    return planted


def plant_wrong_count(family_ids: list[str]) -> list[str]:
    return [i for i in family_ids if i != "P44"]


def both_states(verdicts: list[dict], family_ids: list[str], expected_n: int = 7) -> dict:
    good = run_checks(verdicts, family_ids, expected_n)
    bad_verdicts = plant_missing_artifact(verdicts)
    bad = run_checks(bad_verdicts, family_ids, expected_n)
    return {
        "known_good": good,
        "planted_bad": bad,
        "plant": "P40 EXECUTABLE with empty concrete artifact",
        "ok": good["silent"] is True and bad["fired"] is True,
    }


def negative_control(verdicts: list[dict], family_ids: list[str]) -> dict:
    planted = plant_missing_artifact(verdicts)
    result = artifact_check(planted)
    verbatim = (
        "artifact_check(planted-bad P40 EXECUTABLE with empty artifact) -> "
        f"fired={result['fired']} reason={result['reason']} "
        f"record_ids={result['record_ids']} missing_element={result['missing_element']}"
    )
    return {
        "rejected_state": "P40 marked EXECUTABLE but concrete artifact name/keys empty",
        "check": "concrete-artifact",
        "result": result,
        "verbatim": verbatim,
    }
