"""Shared checks for IMP-0335 fishbowl probes."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from tools.council.topology.fishbowl import (  # noqa: E402
    MIXED,
    DemotionTrigger,
    Fishbowl,
    ObserverSpoke,
    PromotionRefused,
    PromotionTrigger,
    RecordingKernel,
    Ring,
    measure_corpus,
    observer_contribution_rate,
)

RECEIPT = REPO / "command-center/receipts/IMP-0335.json"
SENTINEL = "SUCCESS:IMP-0335"


def check_ring_membership() -> list[str]:
    fails: list[str] = []
    k = RecordingKernel()
    bowl = Fishbowl(
        ["A", "B"],
        ["X", "Y"],
        kernel=k,
        inner_capacity=3,
        chair_id="A",
    )
    if bowl.inner_members() != ("A", "B"):
        fails.append(f"inner {bowl.inner_members()}")
    if bowl.outer_members() != ("X", "Y"):
        fails.append(f"outer {bowl.outer_members()}")
    if bowl.ring_of("A") is not Ring.INNER:
        fails.append("A not inner")
    if bowl.ring_of("X") is not Ring.OUTER:
        fails.append("X not outer")
    try:
        bowl.speak("X", "should-fail")
        fails.append("observer speak did not raise")
    except ObserverSpoke:
        pass
    note = bowl.submit_observer_note("X", "obs-note")
    if note.origin != "observer":
        fails.append("observer note origin")
    ev = bowl.promote("X", PromotionTrigger.EMPTY_SEAT)
    if not ev.ok or "X" not in bowl.inner_members() or "X" in bowl.outer_members():
        fails.append(f"promote failed {ev} {bowl.inner_members()}")
    spoken = bowl.speak("X", "now-inner")
    if spoken.origin != "speaker":
        fails.append("promoted speak origin")
    dem = bowl.demote("X", DemotionTrigger.YIELD)
    if not dem.ok or "X" not in bowl.outer_members() or "X" in bowl.inner_members():
        fails.append(f"demote failed {bowl.inner_members()} {bowl.outer_members()}")
    if k.turns_executed != k.turns_recorded:
        fails.append("kernel invariant after membership")
    return fails


def check_promotion_both_states() -> list[str]:
    fails: list[str] = []
    k = RecordingKernel()
    bowl = Fishbowl(
        ["A", "B"],
        ["X"],
        kernel=k,
        inner_capacity=2,
        chair_id="A",
    )
    try:
        bowl.promote("X", PromotionTrigger.EMPTY_SEAT)
        fails.append("full inner empty_seat did not refuse")
    except PromotionRefused as exc:
        if "inner-full" not in str(exc):
            fails.append(f"full-inner reason {exc}")
    k2 = RecordingKernel()
    bowl2 = Fishbowl(
        ["A"],
        ["X"],
        kernel=k2,
        inner_capacity=2,
        chair_id="A",
    )
    ev = bowl2.promote("X", PromotionTrigger.EMPTY_SEAT)
    if not ev.ok:
        fails.append("empty seat should succeed")
    k3 = RecordingKernel()
    bowl3 = Fishbowl(
        ["A"],
        ["X"],
        kernel=k3,
        inner_capacity=2,
        chair_id="A",
        floor_author_ids=["X"],
    )
    try:
        bowl3.promote("X", PromotionTrigger.EMPTY_SEAT)
        fails.append("COI self-judge did not refuse")
    except PromotionRefused as exc:
        if "coi-self-judge" not in str(exc):
            fails.append(f"coi reason {exc}")
    k4 = RecordingKernel()
    bowl4 = Fishbowl(
        ["A"],
        ["X"],
        kernel=k4,
        inner_capacity=2,
        chair_id="A",
    )
    try:
        bowl4.promote("X", PromotionTrigger.CHAIR_INVITE, chair_id="Z")
        fails.append("chair mismatch did not refuse")
    except PromotionRefused as exc:
        if "chair-mismatch" not in str(exc):
            fails.append(f"chair reason {exc}")
    ev4 = bowl4.promote("X", PromotionTrigger.CHAIR_INVITE, chair_id="A")
    if not ev4.ok:
        fails.append("matching chair invite should succeed")
    return fails


def check_rate_published_when_zero() -> list[str]:
    fails: list[str] = []
    k = RecordingKernel()
    bowl = Fishbowl(["A"], [], kernel=k, inner_capacity=1, chair_id="A")
    spoken = bowl.speak("A", "solo")
    bowl.decide("D1", [spoken.point_id], "solo-decision")
    rate = bowl.contribution_rate()
    if rate != 0.0:
        fails.append(f"expected 0.0 got {rate}")
    if observer_contribution_rate(bowl.decisions, bowl.points()) != 0.0:
        fails.append("helper omitted zero")
    return fails


def check_corpus() -> tuple[list[str], dict]:
    fails: list[str] = []
    m = measure_corpus()
    if m["n_runs"] != 15:
        fails.append(f"n_runs {m['n_runs']}")
    if not m["rate_published_even_if_near_zero"]:
        fails.append("rate not published")
    if m["observer_contribution_rate"] != 0.5:
        fails.append(f"rate {m['observer_contribution_rate']}")
    if m["vanity_note_presence_rate"] != 1.0:
        fails.append(f"vanity {m['vanity_note_presence_rate']}")
    if not m["metric_diverges_from_vanity"]:
        fails.append("published metric collapsed onto vanity")
    if not m["did_not_retune_metric"]:
        fails.append("metric was retuned")
    if m["classification"] != MIXED:
        fails.append(f"classification {m['classification']}")
    nc = m["negative_control"]
    expected_cost = {f"cost_only-{i:02d}" for i in range(5)}
    if set(nc["unchanged_runs"]) != expected_cost:
        fails.append(f"unchanged {nc['unchanged_runs']}")
    if len(nc["changed_runs"]) != 10:
        fails.append(f"changed {nc['changed_runs']}")
    if not nc["cost_only_instances"]:
        fails.append("cost-only instances empty")
    if not m["promotion_audit"]["all_match_declared_trigger"]:
        fails.append("promotion audit mismatch")
    if m["promotion_audit"]["n_events"] < 1:
        fails.append("promotion audit empty")
    if not m["kernel_invariant_all_runs"]:
        fails.append("kernel invariant")
    return fails, m


def check_receipt() -> list[str]:
    fails: list[str] = []
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        fails.append("receipt missing")
        return fails
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        fails.append("sentinel absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        fails.append(f"self-declared {st}")
    if doc.get("unit_id") != "IMP-0335":
        fails.append("unit_id")
    for key in (
        "artifact_paths",
        "spec_anchor",
        "evidence",
        "test_ids",
        "negative_control_ids",
        "reviewer_verdict",
        "residual_unknowns",
    ):
        if key not in doc:
            fails.append(f"missing {key}")
    return fails
