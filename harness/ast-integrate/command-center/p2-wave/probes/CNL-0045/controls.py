"""Coverage check, planted-bad mutation, both-states and negative control."""
from __future__ import annotations

import copy
import json

from family import EXPECTED_N, FAMILY, NAMED_IDS, family_members, member_ids
from oracles import evaluable, oracle_status, predicate_of
from runtime import execute_schedule, turn_schedule

ORACLE_CLASSES = frozenset({"test", "build", "measurement"})


def coverage_findings(records: list[dict]) -> list[dict]:
    findings: list[dict] = []
    members = family_members(records)
    ids = member_ids(members)
    if len(members) != EXPECTED_N:
        findings.append(
            {
                "kind": "family-count-mismatch",
                "got": len(members),
                "want": EXPECTED_N,
                "ids": ids,
            }
        )
    if sorted(ids) != sorted(NAMED_IDS):
        findings.append(
            {
                "kind": "family-id-set-mismatch",
                "got": sorted(ids),
                "want": sorted(NAMED_IDS),
            }
        )
    named = set(NAMED_IDS)
    for rec in records:
        rid = str(rec.get("id") or "")
        fam = rec.get("family")
        if rid in named and fam != FAMILY:
            findings.append(
                {
                    "kind": "family-misassignment",
                    "id": rid,
                    "family": fam,
                }
            )
        if fam == FAMILY and rid not in named:
            findings.append({"kind": "unexpected-family-member", "id": rid})
        oracle = rec.get("oracle") if isinstance(rec.get("oracle"), dict) else {}
        cls = oracle.get("class")
        if cls in ORACLE_CLASSES and not evaluable(predicate_of(rec)):
            findings.append(
                {
                    "kind": "overclaim-oracle",
                    "id": rid,
                    "class": cls,
                }
            )
    for rec in members:
        rid = str(rec.get("id") or "")
        sched = turn_schedule(rec)
        if sched["executable"]:
            if not sched.get("turns"):
                findings.append({"kind": "empty-turn-schedule", "id": rid})
        else:
            if sched.get("verdict") != "NOT-EXECUTABLE":
                findings.append(
                    {
                        "kind": "missing-schedule-or-not-executable",
                        "id": rid,
                    }
                )
            if not sched.get("missing_element"):
                findings.append(
                    {
                        "kind": "not-executable-missing-element-blank",
                        "id": rid,
                    }
                )
        status = oracle_status(rec)
        if status["overclaim"]:
            if not any(
                f.get("kind") == "overclaim-oracle" and f.get("id") == rid
                for f in findings
            ):
                findings.append({"kind": "overclaim-oracle", "id": rid})
    covered = len(members)
    if covered != EXPECTED_N and not any(
        f.get("kind") == "family-count-mismatch" for f in findings
    ):
        findings.append(
            {
                "kind": "coverage-count",
                "got": covered,
                "want": EXPECTED_N,
            }
        )
    return findings


def planted_bad(records: list[dict]) -> list[dict]:
    recs = copy.deepcopy(records)
    kept = []
    for rec in recs:
        rid = rec.get("id")
        if rid == "P51":
            continue
        if rid == "P45":
            rec["family"] = "DELIBERATIVE"
        if rid == "P48":
            rec["oracle"] = {"class": "test"}
        kept.append(rec)
    return kept


def both_states(records: list[dict]) -> dict:
    good = coverage_findings(records)
    bad = coverage_findings(planted_bad(records))
    return {
        "silent_on_good": len(good) == 0,
        "fires_on_bad": len(bad) > 0,
        "good_findings": good,
        "bad_findings": bad,
        "bad_kinds": sorted({str(f.get("kind")) for f in bad}),
    }


def negative_control(records: list[dict]) -> dict:
    """What the check does on the state it is meant to reject."""
    findings = coverage_findings(planted_bad(records))
    return {
        "meant_to_reject": (
            "P45 family mis-assigned to DELIBERATIVE; P51 dropped; "
            "P48 class=test with no evaluable predicate (overclaim)"
        ),
        "result": "FIRES" if findings else "SILENT",
        "finding_count": len(findings),
        "verbatim": json.dumps(findings, sort_keys=True),
        "findings": findings,
    }


def oracle_both_states(record: dict) -> dict:
    status = oracle_status(record)
    rid = status["record_id"]
    if not status["has_oracle"]:
        good_run = execute_schedule(record, {"planted": True})
        return {
            "record_id": rid,
            "has_oracle": False,
            "good": good_run,
            "bad": None,
            "silent_on_good": good_run.get("verdict") == "NOT-EXECUTABLE",
            "fires_on_bad": True,
        }
    from oracles import load_claim

    good = execute_schedule(record, load_claim(rid, "good"))
    bad = execute_schedule(record, load_claim(rid, "bad"))
    return {
        "record_id": rid,
        "has_oracle": True,
        "good": {"verdict": good.get("verdict"), "pass": (good.get("oracle") or {}).get("pass")},
        "bad": {"verdict": bad.get("verdict"), "pass": (bad.get("oracle") or {}).get("pass")},
        "silent_on_good": good.get("verdict") == "SETTLED",
        "fires_on_bad": bad.get("verdict") == "UNSETTLED",
    }
