#!/usr/bin/env python3
"""Adversarial reviewer: both-states, stuck-fire, inverted pack, schema garbage."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from detector import REPO, evaluate_pack
from fixtures import ensure_fixtures

SCHEMA = REPO / "command-center/schema/measurement-run.schema.json"


def _schema_rejects_garbage() -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    garbage = [
        {"totally": "unrelated"},
        {"unit_id": "RES-0188", "state": "SUCCESS"},
        "not-an-object",
    ]
    rejected = 0
    messages: list[str] = []
    for g in garbage:
        try:
            jsonschema.validate(g, schema)
            messages.append(f"accepted:{g!r}")
        except (jsonschema.ValidationError, jsonschema.SchemaError, TypeError) as exc:
            rejected += 1
            messages.append(type(exc).__name__)
    return {
        "rejected": rejected,
        "tried": len(garbage),
        "ok": rejected == len(garbage),
        "messages": messages,
    }


def review() -> dict:
    paths = ensure_fixtures()
    known = evaluate_pack(paths["known-case"])
    inverted = evaluate_pack(paths["inverted"])
    reconciled = evaluate_pack(paths["reconciled"])
    schema = _schema_rejects_garbage()

    stale = next(p for p in known["premises"] if p["id"] == "P-STALE-MNN-OPEN")
    current = next(p for p in known["premises"] if p["id"] == "P-CURRENT-MECH-REPREFIX")
    both_states = bool(stale["fire"]) and (not current["fire"])
    silence_both = (not stale["fire"]) and (not current["fire"])
    stuck_fire = bool(stale["fire"]) and bool(current["fire"])

    inv_stale = next(p for p in inverted["premises"] if p["id"] == "P-STALE-MNN-OPEN")
    inv_cur = next(p for p in inverted["premises"] if p["id"] == "P-CURRENT-MECH-REPREFIX")
    inverted_ok = (not inv_stale["fire"]) and bool(inv_cur["fire"])

    rec_fire = any(p["fire"] for p in reconciled["premises"])
    reconciled_silent = not rec_fire

    two_signals = all(len(p.get("signals") or []) >= 2 for p in known["premises"])

    notes = []
    if silence_both:
        notes.append("both-states silence: detector measures nothing")
    if stuck_fire:
        notes.append("stuck-fire: current premise also fired")
    if not inverted_ok:
        notes.append("inverted pack did not invert verdicts")
    if rec_fire:
        notes.append("reconciled pack still fired")
    if not schema["ok"]:
        notes.append("schema failed to reject garbage")
    if not two_signals:
        notes.append("a load-bearing premise has fewer than two signals")

    ok = (
        both_states
        and inverted_ok
        and reconciled_silent
        and schema["ok"]
        and two_signals
        and known["ok"]
        and inverted["ok"]
        and reconciled["ok"]
    )
    return {
        "reviewer_id": "RES-0188-adversarial-both-states-and-schema",
        "independent": True,
        "verdict": "PASS" if ok else "REFUTED",
        "both_states": {
            "stale_fired": stale["fire"],
            "current_silent": not current["fire"],
            "ok": both_states,
        },
        "inverted": {
            "open_claim_silent": not inv_stale["fire"],
            "reprefix_claim_fired": inv_cur["fire"],
            "ok": inverted_ok,
        },
        "reconciled_silent": reconciled_silent,
        "schema_garbage_rejected": schema,
        "two_signals_per_claim": two_signals,
        "codex_reproduction": {
            "attempted": False,
            "reason": (
                "No Codex MCP/CLI on this isolated worker. Headline counts are "
                "reproduced by probe2's independent tokenizer, not by a second vendor."
            ),
        },
        "notes": notes,
        "ok": ok,
    }
