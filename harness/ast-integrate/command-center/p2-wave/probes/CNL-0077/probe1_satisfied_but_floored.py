#!/usr/bin/env python3
"""Probe 1: satisfied-but-floored continues and records why; both-states fire.

Catalog tests_required:
  * a satisfied-but-floored fixture must continue and record why
  * negative control recorded verbatim: state what the check does on the
    state it is meant to reject
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import floor as F  # noqa: E402

ART = HERE.parents[2] / "design/council/CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md"


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0077-probe1 {msg}")
    return 1


def payload(doc: dict) -> dict:
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else doc


def main() -> int:
    floored = load_fix("satisfied-but-floored")
    d = F.evaluate(floored["spec"], floored["state"], floored["stop_expression_true"])
    print(
        json.dumps(
            {
                "fixture": floored["id"],
                "action": d["action"],
                "reason": d["reason"],
                "floors_unmet": [x["id"] for x in d["floors_unmet"]],
                "stop_expression_true": d["stop_expression_true"],
            },
            sort_keys=True,
        )
    )
    if d["action"] != F.CONTINUE:
        return fail(f"floored-did-not-continue action={d['action']}")
    if d["reason"] != F.STOP_BLOCKED_BY_FLOOR:
        return fail(f"floored-reason={d['reason']}")
    unmet_ids = [x["id"] for x in d["floors_unmet"]]
    for need in (
        "min_rounds",
        "min_independent_briefs",
        "min_evidence_items",
        "mandated_roles_spoken",
    ):
        if need not in unmet_ids:
            return fail(f"audit-missing-floor {need} got={unmet_ids}")
    if not d["would_fire_without_floor"]:
        return fail("audit-did-not-record-satisfied-stop")

    met = load_fix("floors-met-stop-true")
    d2 = F.evaluate(met["spec"], met["state"], met["stop_expression_true"])
    print(
        json.dumps(
            {
                "fixture": met["id"],
                "action": d2["action"],
                "reason": d2["reason"],
                "floors_unmet": [x["id"] for x in d2["floors_unmet"]],
            },
            sort_keys=True,
        )
    )
    if d2["action"] != F.TERMINATE or d2["reason"] != F.FIRE:
        return fail(f"over-block floors-met action={d2['action']} reason={d2['reason']}")
    if d2["floors_unmet"]:
        return fail(f"floors-met still unmet {d2['floors_unmet']}")

    silent = load_fix("stop-false-floors-unmet")
    d3 = F.evaluate(silent["spec"], silent["state"], silent["stop_expression_true"])
    print(
        json.dumps(
            {
                "fixture": silent["id"],
                "action": d3["action"],
                "reason": d3["reason"],
            },
            sort_keys=True,
        )
    )
    if d3["reason"] == F.STOP_BLOCKED_BY_FLOOR:
        return fail("stop-false emitted STOP-BLOCKED-BY-FLOOR")
    if d3["action"] != F.CONTINUE or d3["reason"] != F.SILENT:
        return fail(f"stop-false unexpected {d3['action']} {d3['reason']}")

    dup = load_fix("duplicate-briefs-not-independent")
    d4 = F.evaluate(dup["spec"], dup["state"], dup["stop_expression_true"])
    dup_unmet = [x["id"] for x in d4["floors_unmet"]]
    print(
        json.dumps(
            {
                "fixture": dup["id"],
                "action": d4["action"],
                "reason": d4["reason"],
                "floors_unmet": dup_unmet,
                "independent_briefs": F.count_independent_briefs(dup["state"]["briefs"]),
            },
            sort_keys=True,
        )
    )
    if "min_independent_briefs" not in dup_unmet:
        return fail("duplicate-briefs counted as independent")
    if d4["reason"] != F.STOP_BLOCKED_BY_FLOOR:
        return fail(f"duplicate-briefs reason={d4['reason']}")

    # Negative control: the state the check is meant to reject is a
    # satisfied stop that TERMINATES with floors unmet. Disable the gate
    # and the same fixture must stop (FC-11338 manifests). Recorded verbatim.
    ungated_spec = dict(floored["spec"])
    ungated_spec["gate_enabled"] = False
    d_off = F.evaluate(ungated_spec, floored["state"], True)
    negative_control = (
        "NEGATIVE CONTROL (verbatim): on the state it is meant to reject "
        "(stop_expression_true=true, floors unmet, gate_enabled=false) the "
        f"check observes action={d_off['action']} reason={d_off['reason']}. "
        "That is PREMATURE-STOP / FC-11338. With the gate on, the same "
        f"fixture observes action={d['action']} reason={d['reason']}."
    )
    print(negative_control)
    if d_off["action"] != F.TERMINATE or d_off["reason"] != F.PREMATURE_STOP:
        return fail(f"ungated-did-not-stop-early {d_off}")
    if d_off["floors_unmet"] == []:
        return fail("ungated still reported no unmet floors (detector would be silent)")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNL-0077" not in text:
            return fail("artifact-sentinel-absent")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact-self-declared {doc.get('state')}")
        recorded = payload(doc).get("satisfied_but_floored") or {}
        if recorded.get("reason") != F.STOP_BLOCKED_BY_FLOOR:
            return fail("artifact-drift-floored-reason")
        if recorded.get("action") != F.CONTINUE:
            return fail("artifact-drift-floored-action")

    print("SUCCESS:CNL-0077-probe1 satisfied-but-floored audit and both-states gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
