#!/usr/bin/env python3
"""Probe 2: retained checkpoints name two branches that change the plan.

Independent of probe 1's elimination-count: every survivor must have
fingerprint(branch_a) != fingerprint(branch_b), a named default in the
allowed set, and the live agentspec validator must discriminate the
HumanCheckpoint exit rule and the public-tor owner flag (both states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0172-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")

    live = E.score_all()
    keep = E.retained(live)
    if not keep:
        return fail("no retained checkpoints")
    art_keep = {
        r["id"]
        for r in (doc.get("minimal_checkpoint_set") or [])
        if isinstance(r, dict)
    }
    live_keep = {r["id"] for r in keep}
    if art_keep != live_keep:
        return fail(f"minimal set drifted artifact={art_keep} live={live_keep}")

    for row in keep:
        branches = row["branches"]
        if len(branches) != 2:
            return fail(f"{row['id']} does not name two branches")
        a, b = branches[0], branches[1]
        print(
            f"{row['id']} a={a['response']} b={b['response']} "
            f"diverge={row['plans_diverge']} hamming={row['hamming_distance']}"
        )
        if a["response"] == b["response"]:
            return fail(f"{row['id']} branch labels identical")
        if a["plan_fingerprint"] == b["plan_fingerprint"]:
            return fail(f"{row['id']} branch plans identical")
        if not row["plans_diverge"] or row["hamming_distance"] < 1:
            return fail(f"{row['id']} EVPI not positive")
        if row["default_if_unanswered"] not in row["allowed_responses"]:
            return fail(f"{row['id']} default not in allowed_responses")

    cands = E.candidates()
    tor = next(c for c in cands if c["id"] == "CP-TOR-OPT-IN")
    mutant = copy.deepcopy(tor)
    mutant["branch_b"] = copy.deepcopy(mutant["branch_a"])
    mutant["branch_b"]["label"] = "also-enable"
    mutant_row = E.score_one(mutant)
    print(
        f"mutant CP-TOR-OPT-IN identical-plan disposition="
        f"{mutant_row['disposition']} diverge={mutant_row['plans_diverge']}"
    )
    if mutant_row["retain"] or mutant_row["plans_diverge"]:
        return fail("identical-plan mutant was not eliminated")
    if mutant_row["disposition"] != "ELIMINATED-ZERO-EVPI":
        return fail("identical-plan mutant not ZERO-EVPI")

    dsl = E.live_dsl_signals()
    print(
        "dsl no_exit={fires} with_default_silent={silent} "
        "empty_responses={empty} tor_unflagged={tor_off} tor_flagged_silent={tor_on}".format(
            fires=dsl["human_checkpoint_no_exit"]["fires"],
            silent=dsl["human_checkpoint_with_default"]["no_exit_silent"],
            empty=dsl["human_checkpoint_empty_responses"]["fires"],
            tor_off=dsl["tor_unflagged"]["fires"],
            tor_on=dsl["tor_flagged"]["unflagged_silent"],
        )
    )
    if not dsl["human_checkpoint_no_exit"]["fires"]:
        return fail("human-checkpoint-no-exit did not fire")
    if not dsl["human_checkpoint_with_default"]["no_exit_silent"]:
        return fail("default_if_unanswered still flagged no-exit")
    if not dsl["human_checkpoint_empty_responses"]["fires"]:
        return fail("empty allowed_responses did not fire")
    if not dsl["tor_unflagged"]["fires"]:
        return fail("source-policy-tor-unflagged did not fire")
    if not dsl["tor_flagged"]["unflagged_silent"]:
        return fail("owner_tor_flag=true still unflagged")
    if "HumanCheckpoint" not in dsl["phase7_node_types"]:
        return fail("HumanCheckpoint missing from PHASE7_NODE_TYPES")
    if "public-tor" not in dsl["source_classes"]:
        return fail("public-tor missing from SOURCE_CLASSES")

    bind = E.catalog_bindings()
    answer = str((bind.get("oq3") or {}).get("answer") or "")
    print(f"oq3 state={bind['oq3'].get('state')} answer={answer!r}")
    if not answer.upper().startswith("PR-ONLY"):
        return fail("OQ-3 is not the PR-ONLY binding")
    release = next(r for r in live if r["id"] == "CP-RELEASE-MODE")
    if release["disposition"] != "ELIMINATED-ALREADY-SETTLED":
        return fail("CP-RELEASE-MODE not settled")
    if not release["plans_diverge"]:
        return fail("settled release-mode counterfactual should still diverge")

    print("SUCCESS:RES-0172-probe2 retained branches diverge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
