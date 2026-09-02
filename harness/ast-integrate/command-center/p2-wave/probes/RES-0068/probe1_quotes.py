#!/usr/bin/env python3
"""Probe 1: every engine claim has two live rails and quotes in captured bytes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    COMPLETION_SENTINEL,
    MIN_BYTES,
    NOT_DELIVERING,
    SENTINEL,
    UID,
    grade_claim,
    load_harvest_index,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0068-probe1 {msg}")
    return 1


def main() -> int:
    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    raw = ARTIFACT.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < MIN_BYTES:
        return fail("artifact-too-small")
    text = raw.decode("utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("not-object")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if COMPLETION_SENTINEL not in text:
        return fail("completion-sentinel-absent")
    if doc.get("unit_id") != UID:
        return fail("unit-id")
    claims = doc.get("claims") or []
    if len(claims) < 4:
        return fail("too-few-claims")
    idx = load_harvest_index()
    engines_with_quotes = []
    for c in claims:
        if not isinstance(c, dict):
            return fail("claim-not-object")
        g = grade_claim(c, idx)
        print(
            f"claim {c.get('claim_id')} rails={g['ok_rails']} "
            f"tier={g['tier']} citable={g['citable_as_measured_fact']} "
            f"problems={g['problems']}"
        )
        if not g["citable_as_measured_fact"] or g["ok_rails"] < 2:
            return fail(f"claim-not-e2:{c.get('claim_id')}")
        q = str(c.get("quoted_barrier_policy") or "")
        if len(q) < 16:
            return fail(f"empty-barrier-quote:{c.get('claim_id')}")
        engines_with_quotes.append(str(c.get("engine")))
    named = str(doc.get("named_engine_exhibiting_local_no_timeout_pathology") or "")
    if named != "Celery":
        return fail(f"named-pathology-engine:{named!r}")
    patho = [
        c
        for c in claims
        if isinstance(c, dict) and c.get("matches_local_no_timeout_pathology") is True
    ]
    if not any(str(c.get("engine", "")).startswith("Celery") for c in patho):
        return fail("celery-not-marked-pathology")
    print(
        f"engines_quoted={len(engines_with_quotes)} "
        f"named_pathology={named} completion_sentinel=True"
    )
    print("SUCCESS:RES-0068-probe1 quoted barrier policies, two rails, Celery named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
