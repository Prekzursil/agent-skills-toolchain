#!/usr/bin/env python3
"""Probe 2: no-impact questions REMOVED; remaining asks are one-at-a-time.

Independent recount: every spec-named action has a mapping row, trigger ids
match the table in gates.py, empty-trigger actions are REMOVED, a planted
completeness question is REMOVED, and each ASK carries a recommendation and
a default. Live artifact presented_now is a single foundation question.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gates as G  # noqa: E402

ART = REPO / G.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0077-probe2 {msg}")
    return 1


def main() -> int:
    baited = G.classify(REPO, include_completeness_bait=True)
    live = G.classify(REPO)

    bait = baited.get("completeness_bait") or {}
    print(
        f"completeness_bait disposition={bait.get('disposition')} "
        f"id={bait.get('id')}"
    )
    if bait.get("disposition") != "REMOVED":
        return fail("completeness question was asked rather than removed")
    if bait.get("id") in [r["id"] for r in baited["ask"]]:
        return fail("completeness bait leaked into ASK queue")

    empty = [
        r["action"] for r in live["action_rows"] if not G.TRIGGERS[r["action"]]
    ]
    print("empty_trigger_actions", json.dumps(empty))
    for action in empty:
        row = next(r for r in live["action_rows"] if r["action"] == action)
        if row["disposition"] != "REMOVED":
            return fail(
                f"{action} has no trigger but disposition={row['disposition']}"
            )

    expected_empty = {
        "credential_rotation",
        "security_posture",
        "public_repositories",
    }
    if set(empty) != expected_empty:
        return fail(f"empty-trigger set drifted: {empty}")

    for action, pairs in G.TRIGGERS.items():
        row = next(r for r in live["action_rows"] if r["action"] == action)
        got = [t["id"] for t in row["triggering_units"]]
        want = [p[0] for p in pairs]
        print(f"recount {action}: want={want} got={got}")
        if got != want:
            return fail(f"trigger recount mismatch for {action}")

    if len(live["action_rows"]) != 7:
        return fail("spec-named action coverage is not 7")
    mapped = {r["action"] for r in live["action_rows"]}
    if mapped != set(G.SPEC_ACTIONS):
        return fail(f"mapping actions {mapped} != spec list")

    asks = live["ask"]
    if len(asks) < 2:
        return fail("need at least two ASK rows to prove one-at-a-time deferral")
    for row in asks:
        if not row.get("recommendation") or not row.get("default_if_unanswered"):
            return fail(f"{row['id']} missing recommendation or default")
        if row.get("decision_log_checked") is not True:
            return fail(f"{row['id']} not checked against decision log")
    presented = live["presented_now"]
    if presented is None or presented["id"] != asks[0]["id"]:
        return fail("presented_now is not the first remaining foundation question")
    if set(live["deferred_ask_ids"]) != {r["id"] for r in asks[1:]}:
        return fail("deferred ids are not exactly the non-presented ASK rows")
    if presented["id"] in live["deferred_ask_ids"]:
        return fail("presented question also deferred")

    if not ART.is_file():
        return fail("live artifact missing")
    raw = ART.read_text(encoding="utf-8")
    if G.SENTINEL not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    q = doc.get("ask_queue") or {}
    if q.get("presentation_rule") != "one_foundation_question_at_a_time":
        return fail("presentation_rule missing")
    if not q.get("presented_now") or q["presented_now"].get("id") != presented["id"]:
        return fail("artifact presented_now drifted from classifier")
    if not q["presented_now"].get("recommendation"):
        return fail("presented question has no recommendation")
    if not q["presented_now"].get("default_if_unanswered"):
        return fail("presented question has no default")
    if q.get("deferred_ids") != live["deferred_ask_ids"]:
        return fail("artifact deferred_ids drifted")

    art_actions = [r["action"] for r in doc.get("action_unit_map") or []]
    if art_actions != list(G.SPEC_ACTIONS):
        return fail("artifact action_unit_map order/coverage drifted")

    extra_flag = [
        u["id"]
        for u in live["owner_flag_units"]
        if not u["in_spec_trigger_table"]
    ]
    print("owner_flag_outside_trigger_table", extra_flag)
    for uid in extra_flag:
        if f"Q-{uid}" in [r["id"] for r in live["action_rows"]]:
            return fail(f"{uid} asked for completeness")

    print(
        f"presented={presented['id']} deferred={live['deferred_ask_ids']} "
        f"removed={[r.get('action') or r.get('id') for r in live['removed']]}"
    )
    print("SUCCESS:WFA-0077-probe2 remove-completeness one-at-a-time recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
