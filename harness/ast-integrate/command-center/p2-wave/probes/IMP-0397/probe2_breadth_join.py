#!/usr/bin/env python3
"""Probe 2: breadth denominator, session join key, unscoped-join mutation."""
from __future__ import annotations

import copy
import json

import jsonschema

from harness import (
    CONTRACT,
    RECEIPT,
    SCHEMA,
    SENTINEL,
    T,
    load_events,
    load_indexed,
    live_report,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0397-probe2 {msg}")
    return 1


def main() -> int:
    events = load_events()
    indexed = load_indexed()
    if len(indexed) != 16:
        return fail(f"indexed count {len(indexed)} want 16")

    report = live_report()
    breadth = report["breadth"]
    if breadth["indexed"] != 16:
        return fail(f"indexed denominator {breadth['indexed']} want 16")
    if breadth["offered"] != 4:
        return fail(f"offered numerator {breadth['offered']} want 4")
    if abs(float(breadth["fraction"]) - 0.25) > 1e-9:
        return fail(f"fraction {breadth['fraction']} want 0.25")
    stmt = breadth["denominator_statement"]
    if "4" not in stmt or "16" not in stmt:
        return fail("denominator_statement does not name both counts")
    if "cap.unused.alpha" in breadth["offered_ids"]:
        return fail("June-only cap.unused.alpha counted in July offered set")
    for cid in ("cap.lint", "cap.test", "cap.docs", "cap.security"):
        if cid not in breadth["offered_ids"]:
            return fail(f"{cid} missing from July offered set")

    jk = report["join_key"]
    if jk.get("name") != "session_id" or jk.get("scope") != "session":
        return fail(f"join_key not session-scoped: {jk}")
    if jk.get("value_kind") != "opaque-hash":
        return fail("join_key is not an opaque hash")
    for rec in report["records"]:
        if rec.get("join_key_scope") != "session":
            return fail("record join_key_scope is not session")
        if str(rec.get("join_key") or "").startswith("raw-sess"):
            return fail("raw session id used as join key")

    try:
        T.join_sessions(events, key="user_id")
    except T.JoinError:
        refused_unscoped = True
    else:
        return fail("join_sessions accepted user_id without allow_unscoped")

    contaminates = T.unscoped_join_contaminates(events)
    if not contaminates.get("unscoped_join_loses_session_outcomes"):
        return fail(f"user_id join did not contaminate sessions: {contaminates}")
    if contaminates["user_join_count"] >= contaminates["session_join_count"]:
        return fail("user_id join did not collapse session cardinality")

    lint = next(
        (
            r
            for r in report["correlation"]["per_capability"]
            if r["capability_id"] == "cap.lint"
        ),
        None,
    )
    if lint is None or lint.get("delta") is None or float(lint["delta"]) <= 0:
        return fail("cap.lint offer/success delta is not positive on the fixture")

    if not RECEIPT.is_file() or not SCHEMA.is_file() or not CONTRACT.is_file():
        return fail("receipt or schema missing")
    # Catalog output_schema is a generated $ref shim (no local join-key
    # constraint, remote $ref). The discriminating contract lives beside the
    # probes so unscoped join_key is a ValidationError, not a resolve miss.
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    receipt_text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(receipt_text)
    validator.validate(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {doc.get('state')}")
    if SENTINEL not in receipt_text:
        return fail("sentinel absent")
    rb = doc.get("breadth") or {}
    if int(rb.get("offered")) != 4 or int(rb.get("indexed")) != 16:
        return fail("receipt breadth does not match live 4/16")

    garbage_ok = False
    try:
        validator.validate({"totally": "unrelated"})
    except jsonschema.ValidationError:
        garbage_ok = True
    if not garbage_ok:
        return fail("schema accepted garbage document")

    mutant = copy.deepcopy(doc)
    mutant["join_key"]["scope"] = "user"
    mutant["join_key"]["name"] = "user_id"
    scoped_ok = False
    try:
        validator.validate(mutant)
    except jsonschema.ValidationError:
        scoped_ok = True
    if not scoped_ok:
        return fail("schema accepted user-scoped join_key")

    print(
        "breadth="
        + stmt
        + " join="
        + str(jk["name"])
        + "/"
        + str(jk["scope"])
        + " unscoped_refused="
        + str(refused_unscoped)
        + " collapsed="
        + str(contaminates["collapsed"])
        + " lint_delta="
        + str(lint["delta"])
        + " schema_ok=True"
    )
    print("SUCCESS:IMP-0397-probe2 breadth-join session-key unscoped-mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
