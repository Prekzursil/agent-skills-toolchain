#!/usr/bin/env python3
"""IMP-0203 certification admission: schema + expiry against an injected clock.

A stored green decays. evaluate() never reads the wall clock. Callers must pass
`now` (UTC Z). Same (record, live corpus, live spec, now) always yields the
same status.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/certification-record.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL

VALID = "VALID"
STALE = "STALE"
INVALID = "INVALID"

REASON_CORPUS = "corpus_superseded"
REASON_SPEC = "spec_version_superseded"
REASON_EXPIRED = "expired"

_SCHEMA_CACHE: dict[str, Any] | None = None
_VALIDATOR: Draft7Validator | None = None


def load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def validator() -> Draft7Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        _VALIDATOR = Draft7Validator(load_schema())
    return _VALIDATOR


def schema_errors(record: Any) -> list[str]:
    errs = []
    for e in sorted(validator().iter_errors(record), key=lambda x: list(x.path)):
        path = ".".join(str(p) for p in e.path) or "<root>"
        errs.append(f"{path}: {e.message}")
    return errs


def parse_utc(stamp: str) -> datetime:
    """Parse YYYY-MM-DDTHH:MM:SSZ. No local time, no wall clock."""
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        raise ValueError(f"utc stamp must end with Z, got {stamp!r}")
    dt = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return dt.replace(tzinfo=timezone.utc)


def evaluate(
    record: Any,
    *,
    live_corpus_version: str,
    live_spec_version: str,
    now: str,
) -> dict[str, Any]:
    """Admit a certificate against a live context and an injected clock.

    INVALID  schema miss (including no evidence anchor)
    STALE    corpus/spec no longer live, or now >= expiry
    VALID    schema-ok, corpus and spec match live, now < expiry
    """
    errors = schema_errors(record)
    if errors:
        return {
            "status": INVALID,
            "reasons": ["schema_invalid"],
            "schema_errors": errors,
            "now": now,
            "live_corpus_version": live_corpus_version,
            "live_spec_version": live_spec_version,
        }
    reasons: list[str] = []
    if record["corpus_version"] != live_corpus_version:
        reasons.append(REASON_CORPUS)
    if record["spec_version"] != live_spec_version:
        reasons.append(REASON_SPEC)
    if parse_utc(now) >= parse_utc(record["expiry"]):
        reasons.append(REASON_EXPIRED)
    status = STALE if reasons else VALID
    return {
        "status": status,
        "reasons": reasons,
        "schema_errors": [],
        "now": now,
        "live_corpus_version": live_corpus_version,
        "live_spec_version": live_spec_version,
        "record_corpus_version": record["corpus_version"],
        "record_spec_version": record["spec_version"],
        "expiry": record["expiry"],
    }


def both_states_corpus(
    current: dict[str, Any],
    *,
    live_spec_version: str,
    now: str,
    superseded_corpus: str,
) -> dict[str, Any]:
    """Both-states: same certificate, current corpus VALID, superseded corpus STALE."""
    live = current["corpus_version"]
    good = evaluate(
        current,
        live_corpus_version=live,
        live_spec_version=live_spec_version,
        now=now,
    )
    bad = evaluate(
        current,
        live_corpus_version=superseded_corpus,
        live_spec_version=live_spec_version,
        now=now,
    )
    return {"current": good, "superseded": bad}
