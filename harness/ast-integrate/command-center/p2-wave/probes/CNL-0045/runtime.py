"""Turn schedules: executable walk, or explicit NOT-EXECUTABLE."""
from __future__ import annotations

from oracles import evaluate, load_claim, oracle_status

SEATS = {
    "P45": ("claimant", "reviewer", "reproducer", "chair"),
    "P46": ("proposer", "reviewer", "graph-oracle", "chair"),
    "P47": ("incident-commander", "hypothesizer", "telemetry-oracle", "chair"),
    "P50": ("submitter", "evidence-clerk", "chair"),
    "P51": ("spike-lead", "measurer", "timekeeper", "chair"),
}


def turn_schedule(record: dict) -> dict:
    status = oracle_status(record)
    oid = status["record_id"]
    if not status["has_oracle"]:
        return {
            "record_id": oid,
            "executable": False,
            "verdict": "NOT-EXECUTABLE",
            "missing_element": status["missing_element"],
            "turns": [],
        }
    seats = list(record.get("roles") or SEATS.get(oid) or ("chair",))
    turns = [
        {
            "id": "T1",
            "seat": seats[0],
            "action": "submit_claim",
        },
        {
            "id": "T2",
            "seat": seats[1] if len(seats) > 1 else seats[0],
            "action": "bind_oracle",
            "oracle_class": status["class"],
            "oracle_id": status["oracle_id"],
        },
        {
            "id": "T3",
            "seat": seats[-2] if len(seats) > 2 else seats[-1],
            "action": "run_oracle",
            "settles": status["settles"],
        },
        {
            "id": "T4",
            "seat": seats[-1],
            "action": "record_verdict",
            "stop": True,
        },
    ]
    return {
        "record_id": oid,
        "executable": True,
        "verdict": "EXECUTABLE",
        "missing_element": None,
        "oracle_class": status["class"],
        "turns": turns,
    }


def execute_schedule(record: dict, claim: dict | None = None) -> dict:
    sched = turn_schedule(record)
    oid = sched["record_id"]
    if not sched["executable"]:
        return {
            "record_id": oid,
            "verdict": "NOT-EXECUTABLE",
            "missing_element": sched["missing_element"],
            "turns_run": [],
            "oracle": None,
        }
    if claim is None:
        claim = load_claim(oid, "good")
    log = []
    oracle_out = None
    for turn in sched["turns"]:
        row = dict(turn)
        if turn["action"] == "run_oracle":
            oracle_out = evaluate(record, claim)
            row["oracle"] = {
                "pass": oracle_out.get("pass"),
                "kind": oracle_out.get("kind"),
                "executable": oracle_out.get("executable"),
            }
        log.append(row)
        if turn.get("stop"):
            break
    settled = bool(oracle_out and oracle_out.get("pass"))
    return {
        "record_id": oid,
        "verdict": "SETTLED" if settled else "UNSETTLED",
        "missing_element": None,
        "turns_run": log,
        "oracle": oracle_out,
    }
