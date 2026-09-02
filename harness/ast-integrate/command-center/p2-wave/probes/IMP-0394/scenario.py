#!/usr/bin/env python3
"""Shared fixtures and measurements for IMP-0394 named probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.router.budget import select_by_score_only  # noqa: E402
from tools.router.overrides import (  # noqa: E402
    PRECEDENCE_TABLE,
    apply_overrides,
    classify,
    load_overlay,
    printed_precedence,
)

ART = REPO / "command-center/receipts/IMP-0394.json"
INDEX = HERE / "fixtures/capability-index.json"
USER = HERE / "fixtures/user.settings.json"
PROJ_A = HERE / "fixtures/project-a.settings.json"
PROJ_B = HERE / "fixtures/project-b.settings.json"

BAN_ID = "cap.banned-high"
UNBANNED_ID = "cap.unbanned-high"
PIN_ID = "cap.pinned-low"
PROJ_PIN = "cap.proj-a-pin"
PROJ_BAN = "cap.proj-a-ban"
PLAIN_ID = "cap.plain"
SENTINEL = "SENTINEL:IMP-0394:OVERRIDES-PRECEDENCE-FIXED"

# IMP-0392 k=40 above-threshold adversarial case; token_cost 100 => 5 slots at 500.
FLOOD_N = 40
FLOOD_SCORE = 0.90
TOKEN = 100
BUDGET_CEILING = 500
WIDE_CEILING = 10000


def load_named() -> list[dict[str, Any]]:
    doc = json.loads(INDEX.read_text(encoding="utf-8"))
    return list(doc["capabilities"])


def flood_candidates(n: int = FLOOD_N) -> list[dict[str, Any]]:
    return [
        {
            "capability_id": f"cap.flood-{i:02d}",
            "score": FLOOD_SCORE,
            "token_cost": TOKEN,
        }
        for i in range(1, n + 1)
    ]


def overlay_a():
    return load_overlay(USER, PROJ_A, "proj-a")


def overlay_b():
    return load_overlay(USER, PROJ_B, "proj-b")


def ids_of(rows: list[dict[str, Any]]) -> list[str]:
    return [r["capability_id"] for r in rows]


def require_receipt() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:IMP-0394 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0394 receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0394 self-declared {st}")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0394 sentinel absent")
    if doc.get("unit_id") != "IMP-0394":
        raise SystemExit(f"FAILED:IMP-0394 unit_id {doc.get('unit_id')}")
    printed = str(doc.get("printed_precedence") or "")
    if "1. owner.ban" not in printed or "5. router.score" not in printed:
        raise SystemExit("FAILED:IMP-0394 receipt precedence not printed")
    return doc


def measure_ban_beats_score() -> dict[str, Any]:
    """Owner ban excludes score 0.99; unbanned 0.99 is admitted (negative control)."""
    named = load_named()
    ov = overlay_a()
    decision = apply_overrides(named, ov, WIDE_CEILING)
    banned = next(c for c in named if c["capability_id"] == BAN_ID)
    unbanned = next(c for c in named if c["capability_id"] == UNBANNED_ID)
    if float(banned["score"]) != 0.99:
        raise AssertionError("fixture score for banned-high is not 0.99")
    table = printed_precedence()
    layers_ok = [row["layer"] for row in PRECEDENCE_TABLE] == [
        "owner.ban",
        "project.ban",
        "owner.pin",
        "project.pin",
        "router.score",
    ]
    owner_ban_layer = classify(BAN_ID, ov)
    project_tried_to_pin = BAN_ID in ov.project_pin
    admitted = set(decision["admitted_ids"])
    excluded_map = {r["capability_id"]: r for r in decision["excluded"]}
    return {
        "printed_precedence": table,
        "precedence_layers_in_order": layers_ok,
        "banned_id": BAN_ID,
        "banned_score": float(banned["score"]),
        "banned_admitted": BAN_ID in admitted,
        "banned_layer": owner_ban_layer,
        "banned_excluded_row": excluded_map.get(BAN_ID),
        "project_pin_attempted_on_banned": project_tried_to_pin,
        "unbanned_id": UNBANNED_ID,
        "unbanned_score": float(unbanned["score"]),
        "unbanned_admitted": UNBANNED_ID in admitted,
        "unbanned_layer": classify(UNBANNED_ID, ov),
        "plain_layer": classify(PLAIN_ID, ov),
        "plain_admitted": PLAIN_ID in admitted,
        "decision_echoes_printed_table": decision["printed_precedence"] == table,
        "pass": (
            layers_ok
            and owner_ban_layer == "owner.ban"
            and BAN_ID not in admitted
            and project_tried_to_pin
            and UNBANNED_ID in admitted
            and classify(UNBANNED_ID, ov) == "router.score"
            and classify(PLAIN_ID, ov) == "router.score"
            and PLAIN_ID in admitted
            and decision["printed_precedence"] == table
            and "1. owner.ban" in table
            and "5. router.score" in table
        ),
    }


def measure_pin_survives_budget() -> dict[str, Any]:
    """Pinned low-score cap survives the k=40 / ceiling=500 flood; score-only drops it."""
    named = [c for c in load_named() if c["capability_id"] == PIN_ID]
    flood = flood_candidates()
    candidates = named + flood
    ov = overlay_a()
    decision = apply_overrides(candidates, ov, BUDGET_CEILING)
    control = select_by_score_only(candidates, BUDGET_CEILING)
    pin_in_override = PIN_ID in decision["admitted_ids"]
    pin_in_score_only = PIN_ID in control["admitted_ids"]
    pin_layer = classify(PIN_ID, ov)
    admitted_flood = [
        i for i in decision["admitted_ids"] if i.startswith("cap.flood-")
    ]
    return {
        "ceiling": BUDGET_CEILING,
        "flood_n": len(flood),
        "pin_id": PIN_ID,
        "pin_score": float(named[0]["score"]),
        "pin_layer": pin_layer,
        "pin_in_override_admitted": pin_in_override,
        "pin_in_score_only_admitted": pin_in_score_only,
        "override_admitted_ids": decision["admitted_ids"],
        "score_only_admitted_ids": control["admitted_ids"],
        "override_flood_count": len(admitted_flood),
        "score_only_flood_count": len(
            [i for i in control["admitted_ids"] if i.startswith("cap.flood-")]
        ),
        "pass": (
            pin_layer == "owner.pin"
            and pin_in_override
            and not pin_in_score_only
            and len(control["admitted_ids"]) == 5
            and PIN_ID in decision["admitted_ids"]
        ),
    }


def measure_project_keying() -> dict[str, Any]:
    """Project A pin/ban must not appear in project B's decision."""
    named = load_named()
    a = apply_overrides(named, overlay_a(), WIDE_CEILING)
    b = apply_overrides(named, overlay_b(), WIDE_CEILING)
    a_ids = set(a["admitted_ids"])
    b_ids = set(b["admitted_ids"])
    return {
        "project_a": a["project_id"],
        "project_b": b["project_id"],
        "session_key_a": a["session_key"],
        "session_key_b": b["session_key"],
        "proj_pin_in_a": PROJ_PIN in a_ids,
        "proj_pin_in_b": PROJ_PIN in b_ids,
        "proj_ban_in_a": PROJ_BAN in a_ids,
        "proj_ban_in_b": PROJ_BAN in b_ids,
        "proj_ban_layer_a": a["layers"].get(PROJ_BAN),
        "proj_ban_layer_b": b["layers"].get(PROJ_BAN),
        "proj_pin_layer_a": a["layers"].get(PROJ_PIN),
        "proj_pin_layer_b": b["layers"].get(PROJ_PIN),
        "owner_ban_in_a": BAN_ID in a_ids,
        "owner_ban_in_b": BAN_ID in b_ids,
        "pass": (
            a["project_id"] == "proj-a"
            and b["project_id"] == "proj-b"
            and a["session_key"] != b["session_key"]
            and PROJ_PIN in a_ids
            and PROJ_PIN not in b_ids
            and PROJ_BAN not in a_ids
            and PROJ_BAN in b_ids
            and BAN_ID not in a_ids
            and BAN_ID not in b_ids
            and a["layers"].get(PROJ_PIN) == "project.pin"
            and b["layers"].get(PROJ_PIN) == "router.score"
            and a["layers"].get(PROJ_BAN) == "project.ban"
            and b["layers"].get(PROJ_BAN) == "router.score"
        ),
    }


def worked_examples() -> list[dict[str, Any]]:
    """One worked example per printed precedence level."""
    named = load_named()
    a = apply_overrides(named, overlay_a(), WIDE_CEILING)
    b = apply_overrides(named, overlay_b(), WIDE_CEILING)
    pin = measure_pin_survives_budget()
    return [
        {
            "rank": 1,
            "layer": "owner.ban",
            "input": {"capability_id": BAN_ID, "score": 0.99},
            "project": "proj-a",
            "result": "excluded",
            "why": (
                "owner ban beats score 0.99 and also beats project-a pinning the same id"
            ),
            "layer_observed": a["layers"][BAN_ID],
            "admitted": BAN_ID in a["admitted_ids"],
        },
        {
            "rank": 2,
            "layer": "project.ban",
            "input": {"capability_id": PROJ_BAN, "score": 0.88},
            "project_a_admitted": PROJ_BAN in a["admitted_ids"],
            "project_b_admitted": PROJ_BAN in b["admitted_ids"],
            "why": "project-a ban excludes 0.88; sibling project-b still admits it",
            "layer_a": a["layers"][PROJ_BAN],
            "layer_b": b["layers"][PROJ_BAN],
        },
        {
            "rank": 3,
            "layer": "owner.pin",
            "input": {"capability_id": PIN_ID, "score": 0.01},
            "ceiling": BUDGET_CEILING,
            "flood_n": FLOOD_N,
            "pin_in_override": pin["pin_in_override_admitted"],
            "pin_in_score_only": pin["pin_in_score_only_admitted"],
            "why": "score-only ceiling drops the 0.01 pin; owner.pin keeps it",
        },
        {
            "rank": 4,
            "layer": "project.pin",
            "input": {"capability_id": PROJ_PIN, "score": 0.0},
            "project_a_admitted": PROJ_PIN in a["admitted_ids"],
            "project_b_admitted": PROJ_PIN in b["admitted_ids"],
            "why": "project-a pin admits score 0.0; sibling project-b does not leak the pin",
            "layer_a": a["layers"][PROJ_PIN],
            "layer_b": b["layers"][PROJ_PIN],
        },
        {
            "rank": 5,
            "layer": "router.score",
            "input": {"capability_id": PLAIN_ID, "score": 0.5},
            "admitted": PLAIN_ID in a["admitted_ids"],
            "layer_observed": a["layers"][PLAIN_ID],
            "why": "no override: cap.plain stays on the score path and does not enter ban/pin",
        },
    ]
