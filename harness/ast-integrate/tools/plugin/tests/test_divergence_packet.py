"""Divergence-packet unit tests imported by IMP-0036 probe2.

Each test builds its own two-directional pair inline, so the suite does not
depend on the probe fixtures.  Tests raise ``AssertionError`` on failure and
return a small dict of what they observed, like the other ``plugin.tests``
suites.
"""
from __future__ import annotations

import copy

from plugin.classifier import DIVERGED, REPO_AHEAD, classify_texts, unique_lines
from plugin.gate import (
    REFUSE_DECISION_MISMATCH,
    REFUSE_NO_DECISION,
    act,
    has_recorded_decision,
)
from plugin.independent_differ import unique_line_sets_via_hash
from plugin.packet import emit_packet, packet_has_both_unique_sets, record_decision

SHARED = ("# rules/common/example.md", "", "- keep receipts", "- never guess")
REPO_ONLY = ("- repo added: cite the commit", "- repo added: run the gate")
LIVE_ONLY = ("- live added: owner note", "- live added: local override")

REPO_TEXT = "\n".join(SHARED + REPO_ONLY) + "\n"
LIVE_TEXT = "\n".join(SHARED + LIVE_ONLY) + "\n"
PATH = "rules/common/example.md"


def _diverged_packet() -> dict:
    return emit_packet(path=PATH, repo_text=REPO_TEXT, live_text=LIVE_TEXT)


def test_packet_contains_both_unique_sets() -> dict:
    """A DIVERGED packet carries the repo-only AND the live-only line sets.

    Both sets are cross-checked against two mechanically different differs:
    the classifier's str-set differ and the blake2s line-hash differ.
    """
    pkt = _diverged_packet()
    if pkt["classification"] != DIVERGED:
        raise AssertionError(f"expected DIVERGED got {pkt['classification']}")
    if not packet_has_both_unique_sets(pkt):
        raise AssertionError("DIVERGED packet lacks a unique-line set")
    pkt_ru, pkt_lu = set(pkt["repo_unique_lines"]), set(pkt["live_unique_lines"])
    if pkt_ru != set(REPO_ONLY) or pkt_lu != set(LIVE_ONLY):
        raise AssertionError(f"unique sets wrong: repo={sorted(pkt_ru)} live={sorted(pkt_lu)}")
    cls_ru, cls_lu = unique_lines(REPO_TEXT, LIVE_TEXT)
    hash_ru, hash_lu = unique_line_sets_via_hash(REPO_TEXT, LIVE_TEXT)
    if (cls_ru, cls_lu) != (pkt_ru, pkt_lu) or (hash_ru, hash_lu) != (pkt_ru, pkt_lu):
        raise AssertionError("packet differ disagrees with independent differs")
    if pkt_ru & pkt_lu:
        raise AssertionError("a line cannot be unique to both sides")
    # Order inside the packet is first-seen file order, not sorted.
    if pkt["repo_unique_lines"] != list(REPO_ONLY) or pkt["live_unique_lines"] != list(LIVE_ONLY):
        raise AssertionError("unique lines not in first-seen order")
    # Same shared text with one side unchanged is one-sided, never DIVERGED.
    one_sided = emit_packet(path=PATH, repo_text=REPO_TEXT, live_text="\n".join(SHARED) + "\n")
    if one_sided["classification"] != REPO_AHEAD or packet_has_both_unique_sets(one_sided):
        raise AssertionError("one-sided pair reported as two-sided")
    return {
        "classification": pkt["classification"],
        "repo_unique": sorted(pkt_ru),
        "live_unique": sorted(pkt_lu),
        "ok": True,
    }


def test_refuse_act_without_recorded_decision() -> dict:
    """Acting on DIVERGED is refused until an owner decision is recorded.

    Recording ``KEEP-BOTH`` then allows exactly ``KEEP-BOTH``; a different
    action is still refused, and recording never mutates the source packet.
    """
    pkt = _diverged_packet()
    before = copy.deepcopy(pkt)
    if has_recorded_decision(pkt) or pkt["decision"]["status"] != "UNRECORDED":
        raise AssertionError("fresh packet already carries a recorded decision")
    for action in ("TAKE-LIVE", "TAKE-REPO", "KEEP-BOTH", "NO-OP"):
        denied = act(pkt, action)
        if denied["refused"] is not True or denied["ok"] is not False:
            raise AssertionError(f"{action} on DIVERGED was not refused")
        if denied["reason"] != REFUSE_NO_DECISION:
            raise AssertionError(f"wrong refusal reason {denied['reason']!r}")
    recorded = record_decision(pkt, "KEEP-BOTH")
    if not has_recorded_decision(recorded):
        raise AssertionError("record_decision did not record")
    allowed = act(recorded, "KEEP-BOTH")
    if allowed["ok"] is not True or allowed["refused"] is not False or allowed["reason"] is not None:
        raise AssertionError("recorded decision not honoured")
    if allowed["recorded_choice"] != "KEEP-BOTH":
        raise AssertionError("verdict does not cite the recorded choice")
    mismatch = act(recorded, "TAKE-LIVE")
    if mismatch["refused"] is not True or mismatch["reason"] != REFUSE_DECISION_MISMATCH:
        raise AssertionError("action other than the recorded choice was allowed")
    if pkt != before:
        raise AssertionError("record_decision/act mutated the source packet")
    return {"refused_without_decision": 4, "allowed_after_record": 1, "ok": True}


def test_recommendation_is_advisory_not_decision() -> dict:
    """The recommendation block is advisory and distinguishable from a decision.

    Even a recommendation that names the requested action authorises nothing:
    the gate ignores it and still demands a recorded decision.
    """
    pkt = _diverged_packet()
    rec, dec = pkt["recommendation"], pkt["decision"]
    if rec["kind"] != "advisory" or rec["may_authorize_act"] is not False:
        raise AssertionError("recommendation is not advisory")
    if rec["action"] != "HOLD-FOR-RECORDED-DECISION":
        raise AssertionError(f"DIVERGED auto-resolved to {rec['action']!r}")
    if rec["kind"] == dec["kind"] or dec["status"] != "UNRECORDED":
        raise AssertionError("recommendation and decision are not distinguishable")
    if pkt["mtime_is_authorship_signal"] is not False or pkt["size_is_authorship_signal"] is not False:
        raise AssertionError("mtime/size used as an authorship signal")
    if pkt["facts"]["used_as_authorship"] is not False:
        raise AssertionError("facts used as authorship")
    suggestive = copy.deepcopy(pkt)
    suggestive["recommendation"]["action"] = "TAKE-LIVE"
    denied = act(suggestive, "TAKE-LIVE")
    if denied["refused"] is not True or denied["reason"] != REFUSE_NO_DECISION:
        raise AssertionError("a recommendation authorised an act")
    if denied["recommendation_consulted"] is not False:
        raise AssertionError("gate consulted the recommendation")
    if classify_texts(REPO_TEXT, LIVE_TEXT) != DIVERGED:
        raise AssertionError("classifier and packet disagree")
    return {"recommendation_kind": rec["kind"], "decision_status": dec["status"], "ok": True}


__all__ = [
    "test_packet_contains_both_unique_sets",
    "test_recommendation_is_advisory_not_decision",
    "test_refuse_act_without_recorded_decision",
]
