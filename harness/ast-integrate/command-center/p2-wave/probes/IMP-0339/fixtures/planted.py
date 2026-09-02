"""Planted idea ledger for IMP-0339.

Eight ideas clear the maturity bar and carry high held-out quality.
Twelve fail the bar and carry low held-out quality, with long titles so a
title-length decorative bar prefers them.
Four are high-quality decoys that fail the bar (if the bar read the held-out
label it would promote them).
"""

from __future__ import annotations

from typing import Any

ANCHOR_A = "command-center/p2-wave/probes/IMP-0339/fixtures/anchors/claim-a.md"
ANCHOR_B = "command-center/p2-wave/probes/IMP-0339/fixtures/anchors/claim-b.md"
LONG = " PADDING-SLOGAN" * 20

EXPECTED_PROMOTED = [
    "IDEA-M01",
    "IDEA-M02",
    "IDEA-M03",
    "IDEA-M04",
    "IDEA-M05",
    "IDEA-M06",
    "IDEA-M07",
    "IDEA-M08",
]
EXPECTED_DROPPED = [
    "IDEA-D01",
    "IDEA-D02",
    "IDEA-D03",
    "IDEA-D04",
    "IDEA-X01",
    "IDEA-X02",
    "IDEA-X03",
    "IDEA-X04",
    "IDEA-X05",
    "IDEA-X06",
    "IDEA-X07",
    "IDEA-X08",
    "IDEA-X09",
    "IDEA-X10",
    "IDEA-X11",
    "IDEA-X12",
]


def _mature(
    idea_id: str,
    title: str,
    mechanism: str,
    mech_id: str,
    cost: dict[str, Any],
    risk: dict[str, Any],
    evidence: list[dict[str, str]],
    quality: int,
    actionability: dict[str, str],
    turn: str,
) -> dict[str, Any]:
    return {
        "idea_id": idea_id,
        "title": title,
        "mechanism": mechanism,
        "canonical_mechanism_id": mech_id,
        "cost": cost,
        "risk": risk,
        "evidence": evidence,
        "source": {"seat": "analyst", "turn_id": turn},
        "held_out_quality": quality,
        "actionability": actionability,
    }


def _immature(**kwargs: Any) -> dict[str, Any]:
    idea_id = kwargs["idea_id"]
    base: dict[str, Any] = {
        "idea_id": idea_id,
        "title": f"{idea_id} unripe slogan{LONG}",
        "mechanism": kwargs.get("mechanism", "be better"),
        "canonical_mechanism_id": kwargs.get("canonical_mechanism_id", f"MECH-{idea_id}"),
        "cost": kwargs.get("cost", {"estimate": 1.0, "unit": "engineering-days"}),
        "risk": kwargs.get(
            "risk",
            {
                "failure_mode": "unnamed regression ships undetected",
                "severity": "medium",
            },
        ),
        "evidence": kwargs.get("evidence", [{"kind": "file", "ref": ANCHOR_B}]),
        "source": {"seat": "observer", "turn_id": f"T-{idea_id}"},
        "held_out_quality": kwargs.get("held_out_quality", 18),
        "actionability": kwargs.get(
            "actionability",
            {"verification": "", "owner_role": "", "precondition": ""},
        ),
    }
    for key, value in kwargs.items():
        if key != "idea_id":
            base[key] = value
    if "title" not in kwargs:
        base["title"] = f"{idea_id} unripe slogan{LONG}"
    return base


def build_ideas() -> list[dict[str, Any]]:
    mature = [
        _mature(
            "IDEA-M01",
            "Partition-scoped eviction",
            "Assemble each participant prompt from its partition, role, history and evidence, "
            "and when the token budget binds drop lowest-priority history before any required "
            "evidence anchor the seat is contracted to weigh.",
            "MECH-evict-history-first",
            {"estimate": 4.0, "unit": "engineering-days"},
            {
                "failure_mode": "required evidence is evicted before filler history",
                "severity": "high",
            },
            [{"kind": "file", "ref": ANCHOR_A}],
            91,
            {
                "verification": "retention check fires when a required anchor is dropped",
                "owner_role": "kernel-implementer",
                "precondition": "per-seat token budget is declared",
            },
            "T-M01",
        ),
        _mature(
            "IDEA-M02",
            "Blind first-pass barrier",
            "Hold every first-pass submission behind a barrier that opens only after all "
            "seats have submitted or timed out, so an early submitter's text cannot reach a "
            "later prompt through retry or streaming paths.",
            "MECH-blind-barrier",
            {"estimate": 5.0, "unit": "engineering-days"},
            {
                "failure_mode": "peer text leaks into a later participant prompt",
                "severity": "critical",
            },
            [{"kind": "file", "ref": ANCHOR_B}],
            94,
            {
                "verification": "prompt scan finds zero peer content before the barrier timestamp",
                "owner_role": "protocol-implementer",
                "precondition": "submission timestamps are recorded",
            },
            "T-M02",
        ),
        _mature(
            "IDEA-M03",
            "Mechanism-canonical idea count",
            "Count unique ideas by canonical mechanism using two mechanically different "
            "similarity signals so paraphrases collapse while one-parameter forks stay distinct.",
            "MECH-dual-signal-dedup",
            {"estimate": 6.0, "unit": "engineering-days"},
            {
                "failure_mode": "two genuinely distinct ideas merge into one count",
                "severity": "high",
            },
            [{"kind": "claim", "ref": "CLAIM-unique-ideas-per-class-recall"}],
            86,
            {
                "verification": "per-class recall on a planted duplicate set, not a pooled score",
                "owner_role": "quota-implementer",
                "precondition": "hand-labelled duplicate classes exist",
            },
            "T-M03",
        ),
        _mature(
            "IDEA-M04",
            "Dissent conservation",
            "Capture every dissent with seat attribution and carry the same count through "
            "synthesis into the final artifact and any parent aggregation so a minority "
            "report cannot be summarised into non-existence.",
            "MECH-dissent-conservation",
            {"estimate": 3.5, "unit": "engineering-days"},
            {
                "failure_mode": "a dissent disappears during synthesis summarisation",
                "severity": "high",
            },
            [{"kind": "claim", "ref": "CLAIM-spec-11342-dissent-loss"}],
            84,
            {
                "verification": "conservation invariant fails when one dissent is dropped",
                "owner_role": "outcomes-implementer",
                "precondition": "dissent records carry seat ids",
            },
            "T-M04",
        ),
        _mature(
            "IDEA-M05",
            "Argument graph edges",
            "Extract typed SUPPORTS, ATTACKS and REBUTS edges from council turns so every "
            "emitted edge carries a turn id that resolves back to the transcript span.",
            "MECH-typed-argument-graph",
            {"estimate": 7.0, "unit": "staff-hours"},
            {
                "failure_mode": "the extractor invents an edge no turn actually supports",
                "severity": "medium",
            },
            [{"kind": "claim", "ref": "CLAIM-labelled-200-turn-transcript"}],
            79,
            {
                "verification": "precision and recall against a 200-turn labelled key",
                "owner_role": "artifacts-implementer",
                "precondition": "turns expose stable ids",
            },
            "T-M05",
        ),
        _mature(
            "IDEA-M06",
            "Circular citation detector",
            "Map every claim to its anchors and fire only on citation cycles where A cites B "
            "citing A for the same fact, not on two documents that legitimately cross-reference "
            "distinct facts.",
            "MECH-citation-cycle",
            {"estimate": 2.0, "unit": "engineering-days"},
            {
                "failure_mode": "legitimate cross-references are treated as cycles",
                "severity": "medium",
            },
            [{"kind": "file", "ref": ANCHOR_A}, {"kind": "file", "ref": ANCHOR_B}],
            77,
            {
                "verification": "false-positive rate on a legitimate cross-reference fixture",
                "owner_role": "artifacts-implementer",
                "precondition": "anchors are file paths or URLs",
            },
            "T-M06",
        ),
        _mature(
            "IDEA-M07",
            "Append-only event store",
            "Persist council activity as an append-only event log from which transcript, vote "
            "history and confidence trajectory are derived views, so pause, resume and replay "
            "rebuild the same final artifact byte for byte.",
            "MECH-event-sourced-council",
            {"estimate": 8.0, "unit": "engineering-days"},
            {
                "failure_mode": "hidden side state survives a process restart and diverges replay",
                "severity": "critical",
            },
            [{"kind": "claim", "ref": "CLAIM-rebuild-from-log"}],
            88,
            {
                "verification": "rebuild-from-log byte-compared against the original artifact",
                "owner_role": "store-implementer",
                "precondition": "no module attribute is required after restart",
            },
            "T-M07",
        ),
        _mature(
            "IDEA-M08",
            "Action-plan traceability",
            "Turn a council decision into typed owned sequenced actions with preconditions, "
            "and refuse any action that cannot be traced to a decision element the council "
            "actually agreed to.",
            "MECH-traced-action-plan",
            {"estimate": 3.0, "unit": "engineering-days"},
            {
                "failure_mode": "the plan contains an action the council never agreed to",
                "severity": "high",
            },
            [{"kind": "claim", "ref": "CLAIM-unagreed-action-injection"}],
            82,
            {
                "verification": "traceability fires on an injected unagreed action",
                "owner_role": "outcomes-implementer",
                "precondition": "decision elements carry stable ids",
            },
            "T-M08",
        ),
    ]
    immature = [
        _immature(
            idea_id="IDEA-X01",
            mechanism="be better",
            held_out_quality=12,
        ),
        _immature(
            idea_id="IDEA-X02",
            cost=None,
            mechanism=(
                "Ship a dashboard that looks complete while omitting the cost object "
                "the card schema requires so promotion cannot fill a numeric estimate."
            ),
            held_out_quality=21,
        ),
        _immature(
            idea_id="IDEA-X03",
            cost={"estimate": "TBD", "unit": "engineering-days"},
            mechanism=(
                "Record the cost as a spoken TBD token rather than a number so the "
                "bar cannot tell whether the idea is cheap or unbounded."
            ),
            held_out_quality=19,
        ),
        _immature(
            idea_id="IDEA-X04",
            risk={"failure_mode": "unknown", "severity": "high"},
            mechanism=(
                "Name risk as unknown while still claiming a high severity so the "
                "failure mode the council must weigh is never actually stated."
            ),
            held_out_quality=16,
        ),
        _immature(
            idea_id="IDEA-X05",
            evidence=[],
            mechanism=(
                "Assert a mechanism with cost and risk but attach zero evidence items "
                "so the card would promote folklore as if it were anchored."
            ),
            held_out_quality=14,
        ),
        _immature(
            idea_id="IDEA-X06",
            title=f"IDEA-X06 title equals mechanism{LONG}",
            mechanism=f"IDEA-X06 title equals mechanism{LONG}",
            held_out_quality=22,
        ),
        _immature(
            idea_id="IDEA-X07",
            risk=None,
            mechanism=(
                "Describe a mechanism and a cost while leaving the risk object absent "
                "so no named failure mode can be carried onto the option card."
            ),
            held_out_quality=18,
        ),
        _immature(
            idea_id="IDEA-X08",
            cost={"estimate": 2.0, "unit": "vibes"},
            mechanism=(
                "Quote cost in an open-ended vibes unit that is not in the closed set "
                "so two cards cannot be compared on the same scale."
            ),
            held_out_quality=25,
        ),
        _immature(
            idea_id="IDEA-X09",
            risk={
                "failure_mode": "something vague might happen later",
                "severity": "extreme",
            },
            mechanism=(
                "Use a severity token outside the closed set while keeping a long "
                "failure-mode sentence so the bar cannot grade the risk."
            ),
            held_out_quality=20,
        ),
        _immature(
            idea_id="IDEA-X10",
            evidence=[{"kind": "file", "ref": ""}],
            mechanism=(
                "Attach an evidence object whose ref is blank so the card looks like "
                "it cites a source while pointing at nothing."
            ),
            held_out_quality=11,
        ),
        _immature(
            idea_id="IDEA-X11",
            mechanism=None,
            held_out_quality=9,
        ),
        _immature(
            idea_id="IDEA-X12",
            mechanism="   ",
            held_out_quality=10,
        ),
    ]
    decoys = [
        _immature(
            idea_id="IDEA-D01",
            title=f"IDEA-D01 high-quality decoy missing cost{LONG}",
            mechanism=(
                "This decoy has a fully specified mechanism a council could act on "
                "but omits cost so a bar that read held-out quality would wrongly promote it."
            ),
            cost=None,
            held_out_quality=89,
            actionability={
                "verification": "would be testable if cost existed",
                "owner_role": "implementer",
                "precondition": "budget declared",
            },
        ),
        _immature(
            idea_id="IDEA-D02",
            title=f"IDEA-D02 high-quality decoy slogan mechanism{LONG}",
            mechanism="innovate faster",
            held_out_quality=91,
            actionability={
                "verification": "downstream owners already want this",
                "owner_role": "sponsor",
                "precondition": "none stated",
            },
        ),
        _immature(
            idea_id="IDEA-D03",
            title=f"IDEA-D03 high-quality decoy empty evidence{LONG}",
            mechanism=(
                "Specify a concrete replay path for council state reconstruction "
                "while attaching no evidence so quality labels cannot substitute for anchors."
            ),
            evidence=[],
            held_out_quality=85,
            actionability={
                "verification": "byte-compare replay",
                "owner_role": "store-implementer",
                "precondition": "event log exists",
            },
        ),
        _immature(
            idea_id="IDEA-D04",
            title=f"IDEA-D04 high-quality decoy unknown risk{LONG}",
            mechanism=(
                "Describe an owned sequenced action plan derived from a decision "
                "while marking risk unknown so the bar cannot treat a label as a failure mode."
            ),
            risk={"failure_mode": "unknown", "severity": "high"},
            held_out_quality=87,
            actionability={
                "verification": "traceability on injected actions",
                "owner_role": "outcomes-implementer",
                "precondition": "decision ids exist",
            },
        ),
    ]
    ideas = mature + immature + decoys
    ids = [i["idea_id"] for i in ideas]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate idea_id in planted ledger")
    return ideas


def build_ledger() -> dict[str, Any]:
    ideas = build_ideas()
    return {
        "ledger_id": "imp-0339-planted",
        "n_ideas": len(ideas),
        "expected_promoted": list(EXPECTED_PROMOTED),
        "ideas": ideas,
    }
