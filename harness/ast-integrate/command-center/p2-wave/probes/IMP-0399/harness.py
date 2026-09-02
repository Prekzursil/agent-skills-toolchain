#!/usr/bin/env python3
"""Router mutation harness for IMP-0399.

Mutations (contracted four):
  1. corrupt_description  — rewrite cap.ledger description
  2. delete_trigger_row   — drop T-SECRET-CWD
  3. invert_precedence    — swap owner-ban with semantic-score
  4. unpin_embedding      — clear pin + force popularity fallback

Control (known-caught, proves the harness can observe redness):
  drop_capability_ledger

Fifth (adversarial refuter design):
  catchall_trigger        — always-fire row pointing at cap.weather
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from router import load_config
from suite import run_suite

Mutator = Callable[[dict[str, Any]], dict[str, str]]


def _corrupt_description(cfg: dict[str, Any]) -> dict[str, str]:
    found = False
    for cap in cfg["capabilities"]:
        if cap["id"] == "cap.ledger":
            cap["description"] = (
                "Seasonal alpine snow-depth outlook for ski resorts."
            )
            found = True
            break
    if not found:
        raise RuntimeError("cap.ledger missing; cannot corrupt description")
    return {
        "target": "cap.ledger.description",
        "unprotected_if_green": (
            "A description rewrite that maps ledger queries onto an unrelated "
            "domain still yields the labelled ledger set — the suite does not "
            "pin selection to description content."
        ),
    }


def _delete_trigger_row(cfg: dict[str, Any]) -> dict[str, str]:
    before = len(cfg["triggers"])
    cfg["triggers"] = [r for r in cfg["triggers"] if r.get("id") != "T-SECRET-CWD"]
    if len(cfg["triggers"]) != before - 1:
        raise RuntimeError("T-SECRET-CWD was not deleted")
    return {
        "target": "triggers[T-SECRET-CWD]",
        "unprotected_if_green": (
            "Deleting the cwd_prefix trigger still selects cap.secrets on "
            "q-secret-cwd — the suite is not bound to that trigger row."
        ),
    }


def _invert_precedence(cfg: dict[str, Any]) -> dict[str, str]:
    order = list(cfg["precedence"]["order"])
    try:
        i = order.index("owner-ban")
        j = order.index("semantic-score")
    except ValueError as exc:
        raise RuntimeError("precedence order missing contracted rules") from exc
    order[i], order[j] = order[j], order[i]
    cfg["precedence"]["order"] = order
    return {
        "target": "precedence.order owner-ban vs semantic-score",
        "unprotected_if_green": (
            "A banned capability with a near-perfect description match is "
            "still excluded even after owner-ban is ordered after "
            "semantic-score — the suite does not observe precedence."
        ),
    }


def _unpin_embedding(cfg: dict[str, Any]) -> dict[str, str]:
    cfg["embed_pin"] = {
        "pinned": False,
        "model_id": "",
        "digest": "",
        "encoder_id": "",
    }
    return {
        "target": "embed_pin",
        "unprotected_if_green": (
            "Clearing the embedding pin still reports PINNED and still "
            "matches description paraphrases — the suite does not require a "
            "pinned encoder identity and silently accepts popularity fallback."
        ),
    }


def _drop_capability_ledger(cfg: dict[str, Any]) -> dict[str, str]:
    cfg["capabilities"] = [
        c for c in cfg["capabilities"] if c.get("id") != "cap.ledger"
    ]
    cfg["triggers"] = [
        r for r in cfg["triggers"] if r.get("capability") != "cap.ledger"
    ]
    return {
        "target": "capabilities[cap.ledger] (control)",
        "unprotected_if_green": (
            "Removing cap.ledger from the index did not turn the suite red — "
            "the harness cannot observe redness at all."
        ),
    }


def _catchall_trigger(cfg: dict[str, Any]) -> dict[str, str]:
    cfg["triggers"] = list(cfg["triggers"]) + [
        {
            "id": "T-CATCHALL-WEATHER",
            "kind": "always",
            "pattern": "",
            "capability": "cap.weather",
        }
    ]
    return {
        "target": "triggers[T-CATCHALL-WEATHER] (fifth/adversarial)",
        "unprotected_if_green": (
            "An always-fire trigger injecting cap.weather into every query "
            "did not disturb exact-set checks or negatives."
        ),
    }


def _identity(cfg: dict[str, Any]) -> dict[str, str]:
    return {
        "target": "none (identity)",
        "unprotected_if_green": "n/a — identity must stay green",
    }


CONTRACTED: list[tuple[str, Mutator]] = [
    ("corrupt_description", _corrupt_description),
    ("delete_trigger_row", _delete_trigger_row),
    ("invert_precedence", _invert_precedence),
    ("unpin_embedding", _unpin_embedding),
]
CONTROL = ("drop_capability_ledger", _drop_capability_ledger)
FIFTH = ("catchall_trigger", _catchall_trigger)
IDENTITY = ("identity", _identity)


def _run_one(name: str, mut: Mutator, base: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    meta = mut(cfg)
    result = run_suite(cfg)
    observed = "RED" if result["red"] else "GREEN"
    expected_red = name != "identity"
    killed = result["red"] if expected_red else (not result["red"])
    survived = expected_red and not result["red"]
    row = {
        "mutation": name,
        "target": meta["target"],
        "expected_red": expected_red,
        "observed": observed,
        "killed": bool(result["red"]) if expected_red else False,
        "survived": survived,
        "n_failures": result["n_failures"],
        "failure_ids": [f["id"] for f in result["failures"][:12]],
        "unprotected_if_survived": meta["unprotected_if_green"] if survived else None,
    }
    return row


def run_harness(base: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(base) if base is not None else load_config()
    clean = run_suite(cfg)
    contracted_rows = [_run_one(n, m, cfg) for n, m in CONTRACTED]
    control_row = _run_one(*CONTROL, cfg)
    fifth_row = _run_one(*FIFTH, cfg)
    identity_row = _run_one(*IDENTITY, cfg)

    survivors = [r["mutation"] for r in contracted_rows if r["survived"]]
    killed = [r["mutation"] for r in contracted_rows if r["killed"]]
    control_caught = control_row["observed"] == "RED"
    harness_can_observe_red = control_caught
    identity_green = identity_row["observed"] == "GREEN"

    detector_broken = (not clean["green"]) or (not harness_can_observe_red)
    all_four_green = all(r["observed"] == "GREEN" for r in contracted_rows)

    return {
        "clean_suite_green": bool(clean["green"]),
        "clean_n_failures": clean["n_failures"],
        "clean_failure_ids": [f["id"] for f in clean["failures"][:12]],
        "corpus": {
            "id": (cfg.get("corpus") or {}).get("id"),
            "n_items": clean["n_items"],
            "n_negatives": clean["n_negatives"],
            "negative_fraction": clean["negative_fraction"],
            "popularity_top3": clean["popularity_top3"],
            "baseline_exact_set_rate": clean["baseline_exact_set_rate"],
            "imp0398_receipt_present": bool(
                (cfg.get("corpus") or {}).get("imp0398_receipt_present")
            ),
        },
        "contracted": contracted_rows,
        "killed": killed,
        "survivors": survivors,
        "n_contracted": 4,
        "n_killed": len(killed),
        "n_survived": len(survivors),
        "control": control_row,
        "fifth": fifth_row,
        "identity": identity_row,
        "harness_can_observe_red": harness_can_observe_red,
        "identity_stays_green": identity_green,
        "detector_broken": detector_broken,
        "suite_stayed_green_on_all_four": all_four_green,
        "answer": (
            f"{len(survivors)} of 4 contracted mutations SURVIVE; "
            f"{len(killed)} of 4 KILLED; "
            f"control={'KILLED' if control_caught else 'MISSED'}; "
            f"fifth={'KILLED' if fifth_row['observed']=='RED' else 'SURVIVED'}."
        ),
    }


def assert_harness_healthy(report: dict[str, Any]) -> None:
    if not report["clean_suite_green"]:
        raise AssertionError(
            f"clean suite is RED: {report.get('clean_failure_ids')}"
        )
    if not report["harness_can_observe_red"]:
        raise AssertionError("control mutation stayed GREEN; harness is blind")
    if not report["identity_stays_green"]:
        raise AssertionError("identity mutation went RED; harness is always-red")
    if report["suite_stayed_green_on_all_four"]:
        raise AssertionError(
            "all four contracted mutations stayed GREEN — broken detector"
        )
    if report["n_killed"] < 1:
        raise AssertionError("zero contracted mutations caught — detector failure")
