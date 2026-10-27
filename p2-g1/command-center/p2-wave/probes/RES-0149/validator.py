"""Two-signal validator for proof-of-impossibility records.

Signal 1: jsonschema Draft-07 against RECORD_SCHEMA.
Signal 2: a hand-rolled walk that does not call jsonschema.

Both must reject empty exhausted_sources and a missing falsifier.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator, ValidationError

from record_schema import RECORD_KIND, RECORD_SCHEMA, SHERMAN_KENT_BANDS


def schema_errors(record: Any, schema: dict | None = None) -> list[str]:
    sch = schema if schema is not None else RECORD_SCHEMA
    validator = Draft7Validator(sch)
    out: list[str] = []
    for err in validator.iter_errors(record):
        path = ".".join(str(p) for p in err.path) or "$"
        out.append(f"{path}: {err.message}")
    return out


def semantic_errors(record: Any) -> list[str]:
    """Independent of jsonschema. Defaults to reject on missing structure."""
    errs: list[str] = []
    if not isinstance(record, dict):
        return ["$: record is not an object"]
    if record.get("record_kind") != RECORD_KIND:
        errs.append("record_kind: must be proof-of-impossibility")
    question = record.get("question")
    if not isinstance(question, str) or len(question) < 24:
        errs.append("question: missing or too short")
    sources = record.get("exhausted_sources")
    if not isinstance(sources, list):
        errs.append("exhausted_sources: missing")
    elif len(sources) == 0:
        errs.append(
            "exhausted_sources-empty-not-found-masquerade: "
            "empty exhausted_sources is not-found, not impossibility"
        )
    else:
        for i, item in enumerate(sources):
            if not isinstance(item, dict):
                errs.append(f"exhausted_sources[{i}]: not an object")
                continue
            if not str(item.get("source_class") or "").strip():
                errs.append(f"exhausted_sources[{i}].source_class: missing")
            queries = item.get("queries")
            if not isinstance(queries, list) or len(queries) < 1:
                errs.append(
                    f"exhausted_sources[{i}].queries: "
                    "need at least one exact query with a count"
                )
                continue
            for j, q in enumerate(queries):
                if not isinstance(q, dict):
                    errs.append(f"exhausted_sources[{i}].queries[{j}]: not an object")
                    continue
                if not str(q.get("query") or "").strip():
                    errs.append(f"exhausted_sources[{i}].queries[{j}].query: missing")
                rc = q.get("result_count")
                if not isinstance(rc, int) or isinstance(rc, bool) or rc < 0:
                    errs.append(
                        f"exhausted_sources[{i}].queries[{j}].result_count: "
                        "need a non-negative integer count"
                    )
    barrier = record.get("access_barrier")
    if not isinstance(barrier, dict):
        errs.append("access_barrier: missing")
    else:
        if not str(barrier.get("kind") or "").strip():
            errs.append("access_barrier.kind: missing")
        if not str(barrier.get("description") or "").strip():
            errs.append("access_barrier.description: missing")
    retry = record.get("retry_after")
    if not isinstance(retry, str) or len(retry) < 20:
        errs.append("retry_after: missing ISO-8601 expiry")
    falsifier = record.get("falsifier")
    if "falsifier" not in record:
        errs.append("falsifier-absent: a record without a falsifier cannot be overturned")
    elif not isinstance(falsifier, dict):
        errs.append("falsifier: must be an object")
    else:
        obs = falsifier.get("single_observation")
        how = falsifier.get("how_it_overturns")
        if not isinstance(obs, str) or len(obs.strip()) < 16:
            errs.append("falsifier.single_observation: missing or too thin")
        if not isinstance(how, str) or len(how.strip()) < 16:
            errs.append("falsifier.how_it_overturns: missing or too thin")
    claims = record.get("claims")
    if not isinstance(claims, list) or len(claims) < 1:
        errs.append("claims: need at least one load-bearing claim")
    else:
        for i, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errs.append(f"claims[{i}]: not an object")
                continue
            band = claim.get("sherman_kent_band")
            if band not in SHERMAN_KENT_BANDS:
                errs.append(f"claims[{i}].sherman_kent_band: not a Sherman-Kent band")
            lineage = claim.get("lineage")
            if not isinstance(lineage, list) or len(lineage) < 1:
                errs.append(f"claims[{i}].lineage: missing")
            else:
                for k, lin in enumerate(lineage):
                    if not isinstance(lin, dict):
                        errs.append(f"claims[{i}].lineage[{k}]: not an object")
                        continue
                    if not str(lin.get("resolved_url") or "").strip():
                        errs.append(f"claims[{i}].lineage[{k}].resolved_url: missing")
                    if not str(lin.get("fetch_timestamp") or "").strip():
                        errs.append(f"claims[{i}].lineage[{k}].fetch_timestamp: missing")
                    sha = str(lin.get("sha256_of_fetched_bytes") or "")
                    if len(sha) != 64:
                        errs.append(
                            f"claims[{i}].lineage[{k}].sha256_of_fetched_bytes: "
                            "need sha256 of fetched bytes"
                        )
            path = claim.get("independent_verification_path")
            if not isinstance(path, str) or len(path) < 8:
                errs.append(f"claims[{i}].independent_verification_path: missing")
            signals = claim.get("signals")
            if not isinstance(signals, list) or len(signals) < 2:
                errs.append(
                    f"claims[{i}].signals: need two mechanically independent signals"
                )
    return errs


def evaluate(record: Any, schema: dict | None = None) -> dict:
    s_err = schema_errors(record, schema)
    m_err = semantic_errors(record)
    return {
        "accepted": not s_err and not m_err,
        "schema_errors": s_err,
        "semantic_errors": m_err,
        "schema_rejected": bool(s_err),
        "semantic_rejected": bool(m_err),
    }


def accepted(record: Any, schema: dict | None = None) -> bool:
    return bool(evaluate(record, schema)["accepted"])


class RecordValidationError(ValueError):
    pass


def validate_or_raise(record: Any, schema: dict | None = None) -> None:
    result = evaluate(record, schema)
    if result["accepted"]:
        return
    raise RecordValidationError(
        "schema="
        + "; ".join(result["schema_errors"][:6])
        + " semantic="
        + "; ".join(result["semantic_errors"][:6])
    )


def schema_is_vacuous(schema: dict | None = None) -> bool:
    """True when Draft-07 accepts garbage — the detector would be silent."""
    sch = schema if schema is not None else RECORD_SCHEMA
    try:
        Draft7Validator(sch).validate({"totally": "unrelated", "n": 999999})
    except ValidationError:
        return False
    return True
