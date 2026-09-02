#!/usr/bin/env python3
"""Index → edit declared permissions → activate, with grants printed.

Runs in a scratch copy of fixtures/estate. Does not mutate the committed
fixture. Activation-time must catch the escalation; index-time must let
it slip. Selection-time is recorded as the same slip class as index-time.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import gateway as G

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "estate"
SUBJECT = "skill.council"
ESCALATED = [G.BASE_GRANT, G.ESCALATED_GRANT]


def _copy_estate() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tmp = tempfile.TemporaryDirectory(prefix="arc0027-scratch-")
    dest = Path(tmp.name) / "estate"
    shutil.copytree(FIXTURE, dest)
    return tmp, dest


def _print_step(step: str, payload: dict[str, Any]) -> str:
    line = (
        f"GRANT {step} outcome={payload.get('outcome') or payload.get('check')} "
        f"declared={payload.get('declared')} "
        f"effective_grant={payload.get('effective_grant')} "
        f"epoch={payload.get('epoch')}"
    )
    print(line)
    return line


def run_epoch(estate: Path, epoch: G.Epoch) -> dict[str, Any]:
    gw = G.make_gateway(estate, epoch)
    printed: list[str] = []

    indexed = G.index_capabilities(gw)
    subject_row = next(r for r in indexed["rows"] if r["id"] == SUBJECT)
    printed.append(
        _print_step(
            "index",
            {
                "outcome": subject_row.get("check", "NOT-CHECKED"),
                "declared": subject_row["declared"],
                "effective_grant": subject_row.get("effective_grant", []),
                "epoch": epoch,
            },
        )
    )

    selected = G.select_capability(gw, SUBJECT)
    printed.append(
        _print_step(
            "select",
            {
                "outcome": selected.get("check", "NOT-CHECKED"),
                "declared": gw.read_declared(SUBJECT),
                "effective_grant": selected.get("effective_grant", []),
                "epoch": epoch,
            },
        )
    )

    on_disk = G.edit_declared(estate, SUBJECT, ESCALATED)
    printed.append(
        _print_step(
            "edit",
            {
                "outcome": "MUTATED",
                "declared": on_disk,
                "effective_grant": on_disk,
                "epoch": epoch,
            },
        )
    )

    activated = G.activate_skill(gw, SUBJECT)
    printed.append(
        _print_step(
            "activate",
            {
                "outcome": activated["outcome"],
                "declared": activated["declared"],
                "effective_grant": activated["effective_grant"],
                "epoch": epoch,
            },
        )
    )

    slipped = (
        epoch in ("index", "selection")
        and activated["outcome"] == "ALLOW"
        and G.ESCALATED_GRANT in activated["effective_grant"]
    )
    caught = (
        epoch == "activation"
        and activated["outcome"] == "DENY"
        and G.ESCALATED_GRANT in activated["declared"]
        and G.ESCALATED_GRANT not in activated["effective_grant"]
    )
    return {
        "epoch": epoch,
        "subject": SUBJECT,
        "grant_at_index": subject_row.get("effective_grant", subject_row["declared"]),
        "declared_after_edit": on_disk,
        "activate_outcome": activated["outcome"],
        "activate_effective_grant": activated["effective_grant"],
        "activate_declared": activated["declared"],
        "used_cache": activated["used_cache"],
        "slipped": slipped,
        "caught": caught,
        "printed": printed,
        "activation_record": activated,
    }


def both_states() -> dict[str, Any]:
    tmp, estate = _copy_estate()
    try:
        index_run = run_epoch(estate, "index")
    finally:
        tmp.cleanup()

    tmp2, estate2 = _copy_estate()
    try:
        activation_run = run_epoch(estate2, "activation")
    finally:
        tmp2.cleanup()

    tmp3, estate3 = _copy_estate()
    try:
        selection_run = run_epoch(estate3, "selection")
    finally:
        tmp3.cleanup()

    ok = bool(index_run["slipped"] and activation_run["caught"])
    return {
        "pass": ok,
        "index_slipped": bool(index_run["slipped"]),
        "activation_caught": bool(activation_run["caught"]),
        "selection_also_slips": bool(selection_run["slipped"]),
        "index": index_run,
        "activation": activation_run,
        "selection": selection_run,
        "scratch": "tempfile copy of fixtures/estate; committed fixture not mutated",
    }


if __name__ == "__main__":
    result = both_states()
    print(
        f"index_slipped={result['index_slipped']} "
        f"activation_caught={result['activation_caught']} "
        f"selection_also_slips={result['selection_also_slips']}"
    )
    raise SystemExit(0 if result["pass"] else 1)
