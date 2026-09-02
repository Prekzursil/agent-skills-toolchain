#!/usr/bin/env python3
"""Executable standing-watch engine for CNL-0115.

A standing council is asleep until a named trigger fires. Between wakings it
carries a settled-question ledger, not a paused transcript. A later event with
the same question fingerprint and no material-input delta is ACK-UNCHANGED —
including a re-ask six weeks later. A clock tick is not a trigger.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SLEEP = "SLEEP"
ACK_UNCHANGED = "ACK-UNCHANGED"
WAKE_NEW = "WAKE-NEW"
WAKE_DELTA = "WAKE-MATERIAL-DELTA"
WAKE_REOPEN = "WAKE-REOPEN"
BLOCKED_OPEN = "BLOCKED-OPEN"

COSMETIC_KEYS = frozenset(
    {
        "wall_clock",
        "asked_at",
        "asker_id",
        "etag",
        "ad_markup",
        "last_modified_header",
        "week_offset",
        "elapsed_days",
        "cosmetic_timestamp",
    }
)

SIBLING_SOURCE = (
    "catalog-cited reconstruction on this worktree; "
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json Path.is_file() is false"
)


def _canonical(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            str(k): _canonical(v)
            for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))
            if str(k) not in COSMETIC_KEYS
        }
    if isinstance(obj, list):
        return [_canonical(x) for x in obj]
    return obj


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def material_digest(material_inputs: dict | None) -> str:
    return _digest(_canonical(material_inputs or {}))


def question_fingerprint(question_id: str, material_inputs: dict | None) -> str:
    return _digest(
        {"question_id": question_id, "material_inputs": _canonical(material_inputs or {})}
    )


def lookup_settled(ledger: dict, question_id: str) -> dict | None:
    for row in ledger.get("settled") or []:
        if str(row.get("question_id") or "") == question_id:
            return dict(row)
    return None


def classify(*, event: dict, ledger: dict) -> dict[str, Any]:
    """Disposition of one incoming event against the sleep ledger.

    The vote/decision of a prior wake is an exhibit. It is never silently
    replaced. Clock ticks do not wake. Cosmetic field changes do not wake.
    """
    kind = str(event.get("kind") or "")
    question_id = str(event.get("question_id") or "")
    inputs = dict(event.get("material_inputs") or {})
    evidence = event.get("new_evidence_pointer")
    if evidence:
        inputs = {**inputs, "new_evidence_pointer": evidence}
    fp = question_fingerprint(question_id, inputs) if question_id else ""
    prior = lookup_settled(ledger, question_id) if question_id else None

    if kind == "clock":
        return {
            "disposition": SLEEP,
            "wake": False,
            "question_fingerprint": fp,
            "prior_decision_id": (prior or {}).get("decision_id"),
            "reason": "clock tick is not a trigger; a watcher that wakes on the clock is a poller",
            "new_decision_id": None,
        }

    if kind == "reopen":
        token = str(event.get("reopen_token") or "")
        if not token or not evidence:
            return {
                "disposition": ACK_UNCHANGED if prior else SLEEP,
                "wake": False,
                "question_fingerprint": fp,
                "prior_decision_id": (prior or {}).get("decision_id"),
                "reason": (
                    "re-ask without reopen_token AND new_evidence_pointer; "
                    "settled ledger stands"
                ),
                "new_decision_id": None,
            }
        return {
            "disposition": WAKE_REOPEN,
            "wake": True,
            "question_fingerprint": fp,
            "prior_decision_id": (prior or {}).get("decision_id"),
            "prior_as_exhibit": True,
            "reason": "authorized reopen with new evidence; prior decision is exhibit, not blank slate",
            "new_decision_id": None,
        }

    if kind != "trigger" or not question_id:
        return {
            "disposition": SLEEP,
            "wake": False,
            "question_fingerprint": fp,
            "prior_decision_id": (prior or {}).get("decision_id"),
            "reason": "no named trigger predicate fired",
            "new_decision_id": None,
        }

    if prior is None:
        return {
            "disposition": WAKE_NEW,
            "wake": True,
            "question_fingerprint": fp,
            "prior_decision_id": None,
            "reason": "no settled row for this question_id",
            "new_decision_id": None,
        }

    if str(prior.get("question_fingerprint") or "") == fp:
        return {
            "disposition": ACK_UNCHANGED,
            "wake": False,
            "question_fingerprint": fp,
            "prior_decision_id": prior.get("decision_id"),
            "reason": (
                "question fingerprint matches settled ledger; wall-clock and "
                "cosmetic fields are excluded from the fingerprint; no new decision"
            ),
            "new_decision_id": None,
        }

    return {
        "disposition": WAKE_DELTA,
        "wake": True,
        "question_fingerprint": fp,
        "prior_decision_id": prior.get("decision_id"),
        "prior_as_exhibit": True,
        "reason": "same question_id, material inputs digest changed; prior decision is exhibit",
        "new_decision_id": None,
    }


def record_decision(ledger: dict, *, question_id: str, material_inputs: dict, decision_id: str, lineage_root: str) -> dict:
    """Append or replace the settled row for question_id after a real wake."""
    fp = question_fingerprint(question_id, material_inputs)
    md = material_digest(material_inputs)
    row = {
        "question_id": question_id,
        "question_fingerprint": fp,
        "decision_id": decision_id,
        "lineage_root": lineage_root,
        "material_inputs_digest": md,
    }
    settled = [r for r in (ledger.get("settled") or []) if r.get("question_id") != question_id]
    settled.append(row)
    out = dict(ledger)
    out["settled"] = settled
    return out


def sleep_state(ledger: dict) -> dict[str, Any]:
    """Minimal inter-wake state. Not a CNL-0011 paused-transcript freeze."""
    return {
        "kind": "standing-watch-sleep-state",
        "watch_id": ledger.get("watch_id"),
        "settled": list(ledger.get("settled") or []),
        "bindings": list(ledger.get("bindings") or []),
        "replay_seeds": {},
        "not_carried": [
            "wall_clock",
            "full_transcripts",
            "participant_mood",
            "paused_mid_round_cursor",
        ],
        "cnl_0011_distinction": (
            "CNL-0011 serialises a paused mid-flight council so resume is "
            "byte-identical. Sleep is terminal-for-now: the next wake is a new "
            "session bound by the ledger, not a resume of the old transcript."
        ),
    }


def _role_ids(preset: dict) -> frozenset[str]:
    return frozenset(str(r["id"]) for r in preset.get("roles") or [])


def _protocol_ids(preset: dict) -> frozenset[str]:
    return frozenset(str(p["id"]) for p in preset.get("protocol_schedule") or [])


def profile(preset: dict) -> dict[str, Any]:
    watch = preset.get("watch") or {}
    stopping = preset.get("stopping") or {}
    voting = preset.get("voting") or {}
    return {
        "roles": sorted(_role_ids(preset)),
        "protocols": sorted(_protocol_ids(preset)),
        "voting_rule": str(voting.get("rule") or ""),
        "stopping_expression": str(stopping.get("expression") or ""),
        "max_rounds": int(stopping.get("max_rounds") or 0),
        "trigger_woken": bool(watch.get("trigger_woken")),
        "sleep_default": bool(watch.get("sleep_default")),
        "settled_ledger": bool(watch.get("settled_ledger_blocks_relitigation")),
        "intensity": str(watch.get("intensity") or ""),
        "anonymity": bool(preset.get("anonymity")),
        "rebuttal": bool(preset.get("rebuttal")),
    }


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def distance(pa: dict[str, Any], pb: dict[str, Any]) -> float:
    d_roles = 1.0 - jaccard(frozenset(pa["roles"]), frozenset(pb["roles"]))
    d_prot = 1.0 - jaccard(frozenset(pa["protocols"]), frozenset(pb["protocols"]))
    d_vote = 0.0 if pa["voting_rule"] == pb["voting_rule"] else 1.0
    d_stop = 0.0 if pa["stopping_expression"] == pb["stopping_expression"] else 1.0
    d_rounds = 0.0 if pa["max_rounds"] == pb["max_rounds"] else 1.0
    d_trig = 0.0 if pa["trigger_woken"] == pb["trigger_woken"] else 1.0
    d_sleep = 0.0 if pa["sleep_default"] == pb["sleep_default"] else 1.0
    d_led = 0.0 if pa["settled_ledger"] == pb["settled_ledger"] else 1.0
    d_int = 0.0 if pa["intensity"] == pb["intensity"] else 1.0
    d_anon = 0.0 if pa["anonymity"] == pb["anonymity"] else 1.0
    d_reb = 0.0 if pa["rebuttal"] == pb["rebuttal"] else 1.0
    return (
        d_roles
        + d_prot
        + d_vote
        + d_stop
        + d_rounds
        + d_trig
        + d_sleep
        + d_led
        + d_int
        + d_anon
        + d_reb
    )


def _field_diffs(pa: dict[str, Any], pb: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in (
        "roles",
        "protocols",
        "voting_rule",
        "stopping_expression",
        "max_rounds",
        "trigger_woken",
        "sleep_default",
        "settled_ledger",
        "intensity",
        "anonymity",
        "rebuttal",
    ):
        if pa.get(key) != pb.get(key):
            out.append({"field": key, "preset": pa.get(key), "sibling": pb.get(key)})
    return out


def nearest_sibling(preset: dict, siblings: list[dict]) -> dict[str, Any]:
    pp = profile(preset)
    ranked: list[tuple[float, str, dict]] = []
    for sib in siblings:
        if sib.get("id") == preset.get("id"):
            continue
        d = distance(pp, profile(sib))
        ranked.append((d, str(sib.get("id") or ""), sib))
    if not ranked:
        raise ValueError("no siblings to compare")
    ranked.sort(key=lambda t: (t[0], t[1]))
    best_d, best_id, best = ranked[0]
    return {
        "id": best_id,
        "distance": best_d,
        "ranked": [{"id": i, "distance": d} for d, i, _ in ranked],
        "measurable_diffs": _field_diffs(pp, profile(best)),
        "source": SIBLING_SOURCE,
        "named_explicitly": True,
        "sibling_profile": profile(best),
        "preset_profile": pp,
    }


def instantiate(preset: dict, task: dict) -> dict[str, Any]:
    """Apply preset + fixture event/ledger → roster, schedule, voting, stopping."""
    event = dict(task.get("event") or task)
    ledger = dict(task.get("ledger") or {})
    classified = classify(event=event, ledger=ledger)
    wake = bool(classified["wake"])
    phase = "wake" if wake else "sleep"

    seats: list[dict[str, Any]] = []
    for role in preset.get("roles") or []:
        when = str(role.get("seated_when") or "always")
        seated = when == "always" or when == phase
        if not seated:
            continue
        seats.append(
            {
                "role_id": role["id"],
                "title": role["title"],
                "voting": bool(role.get("voting")) and wake,
                "bind_triggers": bool(role.get("bind_triggers")),
            }
        )

    if wake:
        schedule = [
            {"id": "classify-trigger", "purpose": "WatchClerk classifies the event against the ledger"},
            {"id": "fingerprint-question", "purpose": "hash question_id + material inputs; drop cosmetic keys"},
            {"id": "settled-lookup", "purpose": "find prior decision_id if any; attach as exhibit on delta/reopen"},
            {"id": "wake-deliberate", "purpose": "low-intensity panel; max_rounds=2; prior decision is exhibit"},
            {"id": "lineage-bind", "purpose": "CNL-0075: idea→option→claim→vote→decision recorded on the new row"},
            {"id": "record-ledger", "purpose": "replace the settled row for this question_id; do not fork a second live decision"},
            {"id": "return-to-sleep", "purpose": "clear replay_seeds; persist sleep_state; unseat voting roles"},
        ]
    else:
        schedule = [
            {"id": "classify-trigger", "purpose": "WatchClerk classifies the event against the ledger"},
            {"id": "fingerprint-question", "purpose": "hash question_id + material inputs; drop cosmetic keys"},
            {"id": "settled-lookup", "purpose": "match fingerprint; ACK-UNCHANGED or stay SLEEP; no vote"},
            {"id": "return-to-sleep", "purpose": "persist unchanged ledger; do not seat the panel"},
        ]

    stopping = dict(preset.get("stopping") or {})
    voting = dict(preset.get("voting") or {})
    if not wake:
        voting = {
            **voting,
            "quorum_applies": False,
            "note": "sleep has no ballot; ACK-UNCHANGED is a clerk classification, not a vote",
        }

    return {
        "task_id": task.get("id"),
        "phase": phase,
        "classified": classified,
        "roster": seats,
        "voting_seats": [s["role_id"] for s in seats if s["voting"]],
        "protocol_schedule": schedule,
        "voting": voting,
        "stopping": stopping,
        "watch": dict(preset.get("watch") or {}),
        "sleep_state": sleep_state(ledger),
    }
