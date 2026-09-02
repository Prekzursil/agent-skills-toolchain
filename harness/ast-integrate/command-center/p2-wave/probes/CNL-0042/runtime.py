"""Executable GENERATE vs CRITIQUE scheduler and leak detector.

A round's mode is a token, not a prompt instruction. Critique speech acts
inside GENERATE fire. The idea bag is append-only and freezes at
GENERATE_CLOSED; critique may annotate but cannot decrement the count.
"""
from __future__ import annotations

from typing import Any

GENERATE = "GENERATE"
CRITIQUE = "CRITIQUE"
PROCESS = "PROCESS"
GATE = "GENERATE_CLOSED"

DROP_ACTS = frozenset({"drop_idea", "kill_delete", "pop_bag"})


def classify_act(record: dict, act: str) -> str:
    if act in DROP_ACTS:
        return "DROP"
    if act in (record.get("counting_acts") or []):
        return "COUNT"
    if act in (record.get("generate_acts") or []):
        return "GENERATE_OK"
    if act in (record.get("critique_acts") or []):
        return "CRITIQUE_OK"
    if act in {"white_hat", "red_hat", "yellow_hat", "blue_hat", "pass"}:
        return "PROCESS"
    return "UNKNOWN"


def run_schedule(record: dict, schedule: dict) -> dict:
    """Execute a turn schedule. Return counts, freeze snapshot, and findings."""
    findings: list[dict[str, Any]] = []
    bag: list[dict[str, Any]] = []
    annotations: dict[str, list[str]] = {}
    frozen = False
    snapshot: int | None = None
    generate_saw_critique_context = False

    for rnd in schedule.get("rounds") or []:
        mode = str(rnd.get("mode") or "")
        rid = str(rnd.get("id") or "")
        if mode == GATE:
            frozen = True
            snapshot = len(bag)
            continue
        for i, turn in enumerate(rnd.get("turns") or []):
            act = str(turn.get("act") or "")
            kind = classify_act(record, act)
            loc = f"{record['id']}:{rid}:{i}:{act}"
            if turn.get("feed_critique_into_generate"):
                generate_saw_critique_context = True
                findings.append(
                    {
                        "code": "CRITIQUE_CONTEXT_IN_GENERATE",
                        "at": loc,
                        "detail": "annotation store was visible to a GENERATE turn",
                    }
                )
            if kind == "DROP":
                findings.append(
                    {
                        "code": "IDEA_COUNT_SUPPRESSION",
                        "at": loc,
                        "detail": "critique attempted to remove an idea from the bag",
                    }
                )
                continue
            if mode == GENERATE:
                if kind in {"CRITIQUE_OK", "DROP"}:
                    findings.append(
                        {
                            "code": "CRITIQUE_ACT_IN_GENERATE",
                            "at": loc,
                            "detail": f"{act} is a CRITIQUE act inside GENERATE",
                        }
                    )
                    continue
                if kind == "COUNT":
                    if frozen:
                        findings.append(
                            {
                                "code": "EMIT_AFTER_GATE",
                                "at": loc,
                                "detail": "counting emit after GENERATE_CLOSED",
                            }
                        )
                    else:
                        iid = f"{record['id']}-{len(bag)+1}"
                        bag.append(
                            {
                                "id": iid,
                                "act": act,
                                "body": turn.get("body") or iid,
                            }
                        )
            elif mode == CRITIQUE:
                if kind == "COUNT":
                    findings.append(
                        {
                            "code": "COUNTING_EMIT_IN_CRITIQUE",
                            "at": loc,
                            "detail": "counting emit in CRITIQUE does not increment the bag",
                        }
                    )
                    continue
                if not frozen:
                    findings.append(
                        {
                            "code": "CRITIQUE_BEFORE_GATE",
                            "at": loc,
                            "detail": "CRITIQUE round ran before GENERATE_CLOSED",
                        }
                    )
                target = str(turn.get("target") or (bag[-1]["id"] if bag else ""))
                annotations.setdefault(target, []).append(act)
            elif mode == PROCESS:
                if kind == "COUNT":
                    findings.append(
                        {
                            "code": "COUNTING_EMIT_IN_PROCESS",
                            "at": loc,
                            "detail": "process hats/roles cannot increment the idea bag",
                        }
                    )
            else:
                findings.append(
                    {
                        "code": "UNKNOWN_MODE",
                        "at": loc,
                        "detail": mode,
                    }
                )

    if snapshot is None:
        findings.append(
            {
                "code": "MISSING_GENERATE_CLOSED",
                "at": record["id"],
                "detail": "schedule has no GENERATE_CLOSED gate",
            }
        )
        snapshot = len(bag)

    fired = bool(findings)
    annotation_n = sum(len(v) for v in annotations.values())
    return {
        "record_id": record["id"],
        "record_id": record["id"],
        "slug": record.get("slug"),
        "fired": fired,
        "findings": findings,
        "idea_count": snapshot,
        "idea_count": snapshot,
        "bag_len": len(bag),
        "annotation_n": annotation_n,
        "annotation_n": annotation_n,
        "frozen": frozen,
        "frozen": frozen,
        "generate_saw_critique_context": generate_saw_critique_context,
        "silent": not fired,
        "silent": not fired,
    }


def leak_check(record: dict, schedule: dict) -> dict:
    """FIRES on planted critique-in-generate; SILENT on a clean GENERATE-then-gate-then-CRITIQUE."""
    result = run_schedule(record, schedule)
    return {
        "record_id": record["id"],
        "fired": result["fired"],
        "silent": result["silent"],
        "codes": sorted({f["code"] for f in result["findings"]}),
        "findings": result["findings"],
        "idea_count": result["idea_count"],
        "idea_count": result["idea_count"],
    }


run_schedule = run_schedule
leak_check = leak_check
run_schedule = run_schedule
leak_check = leak_check
