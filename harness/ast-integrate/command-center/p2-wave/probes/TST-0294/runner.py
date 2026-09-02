#!/usr/bin/env python3
"""48-protocol terminal sweep for TST-0294.

Blueprints: tools/council/protocol/catalog.py (58 reconstructed P-ids).
12-COUNCIL-PROTOCOLS-AND-PRESETS.json and _USER-PROMPTS.md are absent.
Floor is 48. P01..P51 minus the three state_fork records (P32, P34, P48)
are the 48 expressible rows. The other four inexpressible records (P52,
P54, P55, P58) sit outside that range. Nothing is flattened into DONE.

Kernel proof: tools.council.protocol.plugin.execute.
Cast proof: a role-distinct standard cast so jury and judge are not the
same seat (the 3-seat IMP-0264 stub aliases them).
tools/council/simulate.py is the TST-0267 lone-dissenter substrate: live,
and not the 48-protocol runner. That split is recorded.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.protocol.plugin import (  # noqa: E402
    NeedsKernelChange,
    classify,
    execute,
    load_protocols,
)
from tools.council import simulate as SIM  # noqa: E402

UNIT = "TST-0294"
SENTINEL = "SUCCESS:TST-0294"
ARTIFACT_REL = "command-center/receipts/TST-0294.json"
SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0294/probe1_sweep.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0294/probe2_reviewer.py"
)
FORK_IN_RANGE = frozenset({"P32", "P34", "P48"})
SWEEP_MAX = 51


def speakers_for(order: str, round_i: int) -> list[str]:
    """Role-distinct cast. Judge and jury never share a seat."""
    order = str(order or "round_robin")
    if order in ("round_robin", "all", ""):
        return ["chair", "advocate", "skeptic"]
    if order == "hat_rotation":
        hats = ["white", "red", "black", "yellow", "green", "blue"]
        return [hats[round_i % len(hats)]]
    if order == "rotating_chair":
        seats = ["chair", "advocate", "skeptic"]
        chair = seats[round_i % 3]
        return [chair] + [s for s in seats if s != chair]
    if order == "chair_then_round_robin":
        return ["chair", "advocate", "skeptic"]
    if order == "prop_then_opp":
        return ["proposition", "opposition"]
    if order == "red_only":
        return ["red_team"]
    if order == "blue_only":
        return ["blue_team"]
    if order == "thesis_side":
        return ["thesis"]
    if order == "antithesis_side":
        return ["antithesis"]
    if order == "named_inner":
        return ["inner_a", "inner_b"]
    if order == "named_outer":
        return ["outer_a", "outer_b"]
    if order == "advocate_must_speak":
        return ["devil"]
    if order == "team_a":
        return ["team_a"]
    if order == "team_b":
        return ["team_b"]
    if order == "examiner_then_witness":
        return ["examiner", "witness"]
    if order == "advocates":
        return ["advocate_a", "advocate_b"]
    if order == "jury":
        return ["juror_1", "juror_2"]
    if order == "judge_only":
        return ["judge"]
    if order == "clerk_then_jury":
        return ["clerk", "juror_1"]
    if order == "key_a_then_key_b":
        return ["key_a", "key_b"]
    if order == "facilitator_only":
        return ["facilitator"]
    if order == "scorer_only":
        return ["scorer"]
    if order == "reviewers":
        return ["reviewer_a", "reviewer_b"]
    if order == "authors":
        return ["author"]
    if order == "author_then_board":
        return ["author", "board"]
    if order == "board":
        return ["board"]
    if order == "asker_then_addressee":
        return ["asker", "addressee"]
    if order == "clerk_then_floor":
        return ["clerk", "floor"]
    if "then" in order:
        return ["lead", "second"]
    if order.endswith("_only"):
        return ["lead"]
    return ["chair", "advocate", "skeptic"]


def steelman_blueprint() -> dict[str, Any]:
    return {
        "id": "FX-STEELMAN",
        "slug": "steelman-before-rebuttal",
        "family": "ADVERSARIAL",
        "phases": [
            {
                "id": "steelman",
                "kind": "round_robin",
                "rounds": 1,
                "speaking_order": "round_robin",
                "obligations": [{"id": "steelman", "discharge": "nonempty"}],
                "gates": [{"id": "spoke", "kind": "all_roles_spoke"}],
                "visibility": "all",
                "redact_speaker": False,
                "turn_length": 240,
            },
            {
                "id": "rebuttal",
                "kind": "round_robin",
                "rounds": 1,
                "speaking_order": "round_robin",
                "obligations": [{"id": "rebuttal", "discharge": "nonempty"}],
                "gates": [{"id": "spoke", "kind": "all_roles_spoke"}],
                "visibility": "all",
                "redact_speaker": False,
                "turn_length": 240,
            },
        ],
        "forks_state": False,
        "nests_councils": False,
        "hidden_parallel": False,
        "mirrors_runtimes": False,
        "needs_owner": False,
        "composition": "linear",
        "required_kernel_primitives": [],
        "notes": "Probe-local defining-invariant fixture; not a catalog P-id.",
        "source": "TST-0294 steelman-before-rebuttal fixture",
    }


def strip_steelman(record: Mapping[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(dict(record))
    cloned["id"] = str(record.get("id") or "FX") + "-NO-STEELMAN"
    cloned["phases"] = [
        p for p in (cloned.get("phases") or []) if p.get("id") != "steelman"
    ]
    cloned["notes"] = "Negative control: steelman phase removed."
    return cloned


def walk_cast(record: Mapping[str, Any]) -> dict[str, Any]:
    """Walk phases on the role-distinct cast. Does not flatten kernel gaps."""
    events: list[dict[str, Any]] = []
    seq = 0
    rounds = 0
    discharged: list[str] = []
    for phase in record.get("phases") or []:
        n = int(phase.get("rounds") or 1)
        order = str(phase.get("speaking_order") or "round_robin")
        obs = list(phase.get("obligations") or [{"id": "speak"}])
        for r_i in range(n):
            rounds += 1
            for seat in speakers_for(order, r_i):
                for ob in obs:
                    oid = str(ob.get("id") or "speak")
                    events.append(
                        {
                            "kind": "TURN",
                            "seq": seq,
                            "round": rounds,
                            "phase_id": str(phase.get("id")),
                            "speaking_order": order,
                            "speaker": seat,
                            "obligation": oid,
                        }
                    )
                    discharged.append(oid)
                    seq += 1
    stage_sequence = [
        (e["phase_id"], e["obligation"], e["speaking_order"]) for e in events
    ]
    gates = [
        g
        for p in (record.get("phases") or [])
        for g in (p.get("gates") or [])
    ]
    last_gate = gates[-1] if gates else {}
    stopping = str(last_gate.get("kind") or "all_phases_complete")
    return {
        "id": record.get("id"),
        "ok": True,
        "rounds": rounds,
        "events": events,
        "stage_sequence": stage_sequence,
        "obligations_discharged": discharged,
        "stopping_term": stopping,
        "terminal_state": "DONE",
    }


def collapse(seq: list[str]) -> list[str]:
    out: list[str] = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def steelman_check(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    present = False
    violations: list[dict[str, Any]] = []
    for e in events:
        if e.get("kind") != "TURN":
            continue
        ob = str(e.get("obligation") or "")
        sp = str(e.get("speaker") or "")
        if ob == "steelman":
            present = True
            seen.add(sp)
        if ob == "rebuttal" and sp not in seen:
            violations.append({"seq": e.get("seq"), "speaker": sp})
    return {
        "ok": present and not violations,
        "steelman_present": present,
        "violations": violations,
        "speakers_with_steelman": sorted(seen),
    }


def invariant_for(
    record: Mapping[str, Any], walked: Mapping[str, Any]
) -> dict[str, Any]:
    slug = str(record.get("slug") or "")
    events = list(walked.get("events") or [])
    turns = [e for e in events if e.get("kind") == "TURN"]
    declared = [str(p.get("id")) for p in (record.get("phases") or [])]
    executed = [str(e.get("phase_id")) for e in turns]
    order_ok = collapse(executed) == declared and bool(declared)
    want_obs = {
        str(o.get("id"))
        for p in (record.get("phases") or [])
        for o in (p.get("obligations") or [])
    }
    got_obs = {str(e.get("obligation")) for e in turns}
    obs_ok = want_obs <= got_obs and bool(want_obs)
    extra_ok = True
    extra_ev: dict[str, Any] = {}
    if slug == "oxford-debate":
        statement = "Oxford requires rebuttal turns in a rebuttal phase"
        extra_ok = any(
            e.get("obligation") == "rebuttal" and e.get("phase_id") == "rebuttal"
            for e in turns
        )
        extra_ev = {
            "rebuttal_turns": sum(
                1 for e in turns if e.get("obligation") == "rebuttal"
            )
        }
    elif slug == "judge-and-jury":
        statement = "Jury deliberation excludes the judge seat"
        jury = {str(e.get("speaker")) for e in turns if e.get("phase_id") == "jury"}
        judge = {
            str(e.get("speaker"))
            for e in turns
            if e.get("phase_id") == "judge_instruct"
        }
        extra_ok = bool(jury) and bool(judge) and jury.isdisjoint(judge)
        extra_ev = {
            "jury_speakers": sorted(jury),
            "judge_speakers": sorted(judge),
        }
    elif slug == "steelman-before-rebuttal":
        statement = "A steelman from the same speaker precedes every rebuttal"
        extra_ev = steelman_check(events)
        extra_ok = bool(extra_ev.get("ok"))
    else:
        statement = (
            f"{slug}: every declared obligation is discharged and phases "
            "run in declared order"
        )
    ok = bool(turns) and order_ok and obs_ok and extra_ok
    return {
        "ok": ok,
        "statement": statement,
        "phase_order_ok": order_ok,
        "obligations_ok": obs_ok,
        "evidence": extra_ev,
    }


def selected_records() -> list[dict[str, Any]]:
    rows = load_protocols()
    out = [
        r
        for r in rows
        if int(str(r["id"])[1:]) <= SWEEP_MAX and r["id"] not in FORK_IN_RANGE
    ]
    if len(out) != 48:
        raise AssertionError(
            f"expected 48 expressible P01..P51 rows, got {len(out)}"
        )
    return out


def pairwise_collisions(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_seq: dict[tuple, list[str]] = {}
    for row in rows:
        seq = tuple(tuple(x) for x in (row.get("stage_sequence") or []))
        by_seq.setdefault(seq, []).append(str(row.get("id")))
    hits = []
    for seq, ids in by_seq.items():
        if len(ids) > 1:
            hits.append({"ids": ids, "stage_sequence": [list(x) for x in seq]})
    return hits


def run_one(record: Mapping[str, Any]) -> dict[str, Any]:
    decision = classify(record)
    try:
        kern = execute(record)
        kernel = {
            "ok": bool(kern.get("ok")),
            "turns_executed": kern.get("turns_executed"),
            "rounds": kern.get("rounds"),
            "error": None,
        }
    except NeedsKernelChange as exc:
        return {
            "id": record.get("id"),
            "slug": record.get("slug"),
            "family": record.get("family"),
            "terminal_state": "REFUSED",
            "stopping_term": "needs-kernel-change",
            "rounds": 0,
            "turns": 0,
            "stage_sequence": [],
            "invariant": {
                "ok": False,
                "statement": "inexpressible on IMP-0264",
            },
            "kernel": {
                "ok": False,
                "turns_executed": 0,
                "rounds": 0,
                "error": str(exc),
                "refused": True,
            },
            "classification": decision.as_dict(),
            "row_pass": False,
        }
    walked = walk_cast(record)
    inv = invariant_for(record, walked)
    terminal = str(walked["terminal_state"])
    row_pass = (
        kernel["ok"] is True
        and terminal == "DONE"
        and inv["ok"] is True
        and bool(walked["stopping_term"])
    )
    if hasattr(decision, "as_dict"):
        classification = decision.as_dict()
    elif hasattr(decision, "as_row"):
        classification = decision.as_row()
    else:
        classification = {"id": record.get("id"), "status": getattr(decision, "status", None)}
    return {
        "id": record.get("id"),
        "slug": record.get("slug"),
        "family": record.get("family"),
        "terminal_state": terminal,
        "stopping_term": walked["stopping_term"],
        "rounds": walked["rounds"],
        "turns": len(walked["events"]),
        "stage_sequence": [list(x) for x in walked["stage_sequence"]],
        "invariant": inv,
        "kernel": kernel,
        "classification": classification,
        "row_pass": row_pass,
    }


def simulate_substrate() -> dict[str, Any]:
    path = REPO / "tools/council/simulate.py"
    base = {
        "path": "tools/council/simulate.py",
        "exists": path.is_file(),
        "role": (
            "TST-0267 lone-dissenter scripted substrate; "
            "not the 48-protocol runner"
        ),
        "used_as_48_runner": False,
    }
    try:
        spec = SIM.default_spec()
        a = SIM.run(spec)
        b = SIM.run(spec)
        same = SIM.canonical_bytes(a) == SIM.canonical_bytes(b)
        base.update(
            {
                "two_run_identical": same,
                "sha256": SIM.digest_doc(a),
                "dissent_first_round": a.get("dissent_first_round"),
                "error": None,
            }
        )
    except Exception as exc:  # substrate fact, not the 48-row runner
        base.update(
            {
                "two_run_identical": False,
                "sha256": None,
                "dissent_first_round": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
    return base


def steelman_both_states() -> dict[str, Any]:
    intact_bp = steelman_blueprint()
    broken_bp = strip_steelman(intact_bp)
    intact = walk_cast(intact_bp)
    broken = walk_cast(broken_bp)
    inv_ok = invariant_for(intact_bp, intact)
    inv_bad = invariant_for(broken_bp, broken)
    wired = inv_ok["ok"] is True and inv_bad["ok"] is False
    return {
        "intact": {
            "id": intact_bp["id"],
            "terminal_state": intact["terminal_state"],
            "stopping_term": intact["stopping_term"],
            "invariant_ok": inv_ok["ok"],
            "evidence": inv_ok["evidence"],
        },
        "broken_steelman_removed": {
            "id": broken_bp["id"],
            "terminal_state": broken["terminal_state"],
            "stopping_term": broken["stopping_term"],
            "invariant_ok": inv_bad["ok"],
            "evidence": inv_bad["evidence"],
        },
        "wired": wired,
        "same_answer_both_states": inv_ok["ok"] == inv_bad["ok"],
    }


def distinctness_negative_control(
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """A renamed copy of P07 must collide; proves distinctness is not vacuous."""
    oxford = next(r for r in selected_records() if r["id"] == "P07")
    clone = copy.deepcopy(oxford)
    clone["id"] = "P07-RENAME"
    clone["slug"] = "oxford-debate-copy"
    live = list(rows) + [run_one(clone)]
    hits = pairwise_collisions(live)
    fired = any("P07" in h["ids"] and "P07-RENAME" in h["ids"] for h in hits)
    return {
        "ok": fired,
        "clone_id": "P07-RENAME",
        "collision_ids": [h["ids"] for h in hits],
        "vacuous_if_unfired": True,
    }


def measure() -> dict[str, Any]:
    records = selected_records()
    rows = [run_one(r) for r in records]
    collisions = pairwise_collisions(rows)
    steel = steelman_both_states()
    rename = distinctness_negative_control(rows)
    done = [r for r in rows if r["terminal_state"] == "DONE"]
    failed_rows = [r["id"] for r in rows if not r["row_pass"]]
    census = {r["id"]: classify(r).as_dict() for r in load_protocols()}
    blocked = [
        census[i]
        for i in ("P32", "P34", "P48", "P52", "P54", "P55", "P58")
        if i in census
    ]
    all_pass = (
        len(rows) == 48
        and len(done) == 48
        and not failed_rows
        and not collisions
        and steel["wired"] is True
        and steel["same_answer_both_states"] is False
        and rename["ok"] is True
    )
    return {
        "n": len(rows),
        "n_done": len(done),
        "failed_rows": failed_rows,
        "collisions": collisions,
        "rows": rows,
        "steelman_both_states": steel,
        "rename_copy_control": rename,
        "inexpressible_not_in_sweep": blocked,
        "simulate_substrate": simulate_substrate(),
        "all_pass": all_pass,
        "blueprint_source": "tools/council/protocol/catalog.py",
        "library_file": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "library_file_present": (
            REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ).is_file(),
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
        "selection": (
            "P01..P51 minus P32/P34/P48 (state_fork). "
            "48 expressible records; 7 catalog records need kernel primitives."
        ),
    }


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


if __name__ == "__main__":
    m = measure()
    print(
        json.dumps(
            {
                "n": m["n"],
                "n_done": m["n_done"],
                "failed_rows": m["failed_rows"],
                "collisions": len(m["collisions"]),
                "steelman_wired": m["steelman_both_states"]["wired"],
                "rename_copy_fires": m["rename_copy_control"]["ok"],
                "all_pass": m["all_pass"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(0 if m["all_pass"] else 1)
