#!/usr/bin/env python3
"""Probe-local deterministic council for TST-0268.

Production tools/council/simulate.py is not on this worktree (TST-0257 is
unbuilt). This module is the measurement substrate: scripted personas, a
frozen transcript, judge-only and moderator-only swaps, speaking-time plus
objection-routing capture audits, and mechanical no-judge aggregation.

Nothing here calls a live model. Every function is a seeded state machine.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from typing import Any

UNIT = "TST-0268"
SEED = 268
PROTOCOL = "jury-deliberation-recorded-sweep"

PARTICIPANTS = ("architect", "skeptic", "pragmatist", "critic")
SUPPRESSED = "critic"

JUDGE_IDS = (
    "majority_ballot",
    "unanimity_or_dissent",
    "steelman_minority",
    "chair_echo",
    "citation_strict",
)

THEATRE_AGREEMENT_CEILING = 0.8
THEATRE_UNIQUE_FLOOR = 3

# Spec names the unit is contracted to test (catalog question cites these).
SPEC_MODERATOR_CAPTURE = ":11239"
SPEC_JUDGE_SINGLE_POINT = ":11342"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _speech(
    t: int,
    speaker: str,
    tokens: int,
    position: str,
    citations: list[str],
    text: str,
) -> dict:
    return {
        "t": t,
        "kind": "speech",
        "speaker": speaker,
        "tokens": tokens,
        "position": position,
        "citations": list(citations),
        "text": text,
    }


def _recognition(t: int, moderator: str, speaker: str) -> dict:
    return {
        "t": t,
        "kind": "recognition",
        "moderator": moderator,
        "speaker": speaker,
    }


def _objection(t: int, speaker: str, target: str, routed: bool, oid: str) -> dict:
    return {
        "t": t,
        "kind": "objection",
        "speaker": speaker,
        "target": target,
        "routed": routed,
        "id": oid,
    }


def _ballot(t: int, speaker: str, vote: str) -> dict:
    return {"t": t, "kind": "ballot", "speaker": speaker, "vote": vote}


def _chair_summary(t: int, verdict: str, text: str) -> dict:
    return {
        "t": t,
        "kind": "chair_summary",
        "speaker": "chair",
        "verdict": verdict,
        "text": text,
    }


def _round_events(start_t: int, moderator: str, capture: bool) -> tuple[list[dict], int]:
    """One deliberation round. Capture never recognizes critic and drops objections."""
    events: list[dict] = []
    t = start_t
    roster = list(PARTICIPANTS)
    if capture:
        roster = [p for p in roster if p != SUPPRESSED]

    scripts = {
        "architect": (
            42,
            "ACCEPT",
            ["c1", "c2"],
            "Typed SSOT should refuse opaque passthrough; the hatch reintroduces drift.",
        ),
        "skeptic": (
            38,
            "ACCEPT",
            ["c1"],
            "Agree on refuse-hatch. The generator blast radius is the file count, not one class.",
        ),
        "pragmatist": (
            31,
            "ACCEPT",
            [],
            "Ship refuse-hatch now; residual CouncilSpec policy is a later lane.",
        ),
        "critic": (
            55,
            "REJECT",
            ["c3", "c4", "c5"],
            "Refuse-hatch drops live-unique remainder. Keep a typed remainder queue, not a hatch.",
        ),
    }

    for speaker in roster:
        events.append(_recognition(t, moderator, speaker))
        t += 1
        tokens, pos, cites, text = scripts[speaker]
        events.append(_speech(t, speaker, tokens, pos, cites, text))
        t += 1

    # Critic always *files* an objection; capture drops routing.
    events.append(
        _objection(
            t,
            "critic",
            "architect",
            routed=not capture,
            oid=f"obj-critic-{start_t}",
        )
    )
    t += 1
    events.append(
        _objection(
            t,
            "skeptic",
            "critic",
            routed=True,
            oid=f"obj-skeptic-{start_t}",
        )
    )
    t += 1
    return events, t


def simulate(moderator: str) -> dict:
    """Run the scripted council. moderator is 'even' or 'capture'."""
    if moderator not in {"even", "capture"}:
        raise ValueError(f"unknown moderator {moderator!r}")
    capture = moderator == "capture"
    events: list[dict] = []
    t = 1
    for _round in range(3):
        chunk, t = _round_events(t, moderator, capture)
        events.extend(chunk)

    voters = list(PARTICIPANTS)
    if capture:
        voters = [p for p in voters if p != SUPPRESSED]
    votes = {
        "architect": "ACCEPT",
        "skeptic": "ACCEPT",
        "pragmatist": "ACCEPT",
        "critic": "REJECT",
    }
    for speaker in voters:
        events.append(_ballot(t, speaker, votes[speaker]))
        t += 1

    events.append(
        _chair_summary(
            t,
            "ACCEPT",
            "Chair closes: panel majority accepts refuse-hatch. Dissent noted if present.",
        )
    )
    return {
        "seed": SEED,
        "unit_id": UNIT,
        "protocol": PROTOCOL,
        "moderator": moderator,
        "participants": list(PARTICIPANTS),
        "events": events,
    }


def freeze_transcript(moderator: str = "even") -> tuple[dict, str]:
    """Transcript with no judge field. Judge swap must not mutate these bytes."""
    doc = simulate(moderator)
    # Strip anything a later judge might have attached.
    frozen = {
        "seed": doc["seed"],
        "unit_id": doc["unit_id"],
        "protocol": doc["protocol"],
        "moderator": doc["moderator"],
        "participants": list(doc["participants"]),
        "events": deepcopy(doc["events"]),
    }
    return frozen, sha256_obj(frozen)


def ballots(transcript: dict) -> list[str]:
    return [e["vote"] for e in transcript["events"] if e.get("kind") == "ballot"]


def speeches(transcript: dict) -> list[dict]:
    return [e for e in transcript["events"] if e.get("kind") == "speech"]


def objections(transcript: dict) -> list[dict]:
    return [e for e in transcript["events"] if e.get("kind") == "objection"]


def chair_verdict(transcript: dict) -> str:
    for e in reversed(transcript["events"]):
        if e.get("kind") == "chair_summary":
            return str(e["verdict"])
    raise ValueError("no chair_summary in transcript")


def mechanical_majority(transcript: dict) -> str:
    votes = ballots(transcript)
    if not votes:
        return "ABSTAIN"
    counts = Counter(votes)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "ABSTAIN"
    return top[0][0]


def invert_ballots(transcript: dict) -> dict:
    """Negative control: flip every ballot ACCEPT<->REJECT. Speeches unchanged."""
    out = deepcopy(transcript)
    flip = {"ACCEPT": "REJECT", "REJECT": "ACCEPT"}
    for e in out["events"]:
        if e.get("kind") == "ballot":
            e["vote"] = flip.get(e["vote"], e["vote"])
    return out


def _citation_tally(transcript: dict) -> dict[str, int]:
    tally: dict[str, int] = Counter()
    for e in speeches(transcript):
        tally[str(e["position"])] += len(e.get("citations") or [])
    return dict(tally)


def apply_judge(transcript: dict, judge_id: str) -> str:
    """Verdict from a frozen transcript. Judge must not mutate the transcript."""
    if judge_id == "majority_ballot":
        return mechanical_majority(transcript)
    if judge_id == "unanimity_or_dissent":
        votes = ballots(transcript)
        if votes and len(set(votes)) == 1:
            return votes[0]
        return "DISSENT"
    if judge_id == "steelman_minority":
        cites = _citation_tally(transcript)
        # Follow the citation-richer side; ties fall through to majority.
        if cites.get("REJECT", 0) > cites.get("ACCEPT", 0):
            return "REJECT"
        if cites.get("ACCEPT", 0) > cites.get("REJECT", 0):
            return "ACCEPT"
        return mechanical_majority(transcript)
    if judge_id == "chair_echo":
        return chair_verdict(transcript)
    if judge_id == "citation_strict":
        cites = _citation_tally(transcript)
        accept_n = cites.get("ACCEPT", 0)
        reject_n = cites.get("REJECT", 0)
        if accept_n == 0 and reject_n == 0:
            return "ABSTAIN"
        if accept_n == reject_n:
            return "ABSTAIN"
        return "ACCEPT" if accept_n > reject_n else "REJECT"
    raise ValueError(f"unknown judge {judge_id!r}")


def judge_swap(transcript: dict) -> dict:
    """Hold transcript fixed; swap only the judge persona. Requires >=5 judges."""
    frozen_sha = sha256_obj(transcript)
    rows = []
    for jid in JUDGE_IDS:
        before = sha256_obj(transcript)
        verdict = apply_judge(transcript, jid)
        after = sha256_obj(transcript)
        if before != after or after != frozen_sha:
            raise RuntimeError(f"judge {jid} mutated the frozen transcript")
        rows.append({"judge_id": jid, "verdict": verdict})
    dist = Counter(r["verdict"] for r in rows)
    n = len(rows)
    if n < 5:
        raise RuntimeError("a single swap is not a measurement of stability")
    mode_count = max(dist.values())
    agreement_rate = mode_count / n
    pairwise_agree = 0
    pairwise_total = 0
    for i in range(n):
        for k in range(i + 1, n):
            pairwise_total += 1
            if rows[i]["verdict"] == rows[k]["verdict"]:
                pairwise_agree += 1
    pairwise = pairwise_agree / pairwise_total if pairwise_total else 0.0
    unique = len(dist)
    theatre = unique >= THEATRE_UNIQUE_FLOOR or agreement_rate < THEATRE_AGREEMENT_CEILING
    return {
        "n_judges": n,
        "judge_ids": list(JUDGE_IDS),
        "rows": rows,
        "distribution": dict(dist),
        "agreement_rate": agreement_rate,
        "pairwise_agreement": pairwise,
        "unique_verdicts": unique,
        "modal_verdict": dist.most_common(1)[0][0],
        "modal_count": mode_count,
        "theatre": theatre,
        "theatre_rule": (
            f"theatre if unique_verdicts>={THEATRE_UNIQUE_FLOOR} "
            f"or agreement_rate<{THEATRE_AGREEMENT_CEILING}"
        ),
        "transcript_sha256": frozen_sha,
        "spec": SPEC_JUDGE_SINGLE_POINT,
    }


def speaking_time_audit(transcript: dict) -> dict:
    tokens: dict[str, int] = {p: 0 for p in PARTICIPANTS}
    for e in speeches(transcript):
        sp = str(e["speaker"])
        if sp in tokens:
            tokens[sp] += int(e["tokens"])
    others = [tokens[p] for p in PARTICIPANTS if p != SUPPRESSED]
    median_others = sorted(others)[len(others) // 2] if others else 0
    suppressed_tokens = tokens[SUPPRESSED]
    flagged = suppressed_tokens == 0 and median_others > 0
    return {
        "tokens_by_speaker": tokens,
        "suppressed": SUPPRESSED,
        "suppressed_tokens": suppressed_tokens,
        "median_others": median_others,
        "flagged": flagged,
    }


def objection_routing_audit(transcript: dict) -> dict:
    objs = objections(transcript)
    by = {}
    for e in objs:
        by.setdefault(e["speaker"], {"filed": 0, "routed": 0})
        by[e["speaker"]]["filed"] += 1
        if e.get("routed"):
            by[e["speaker"]]["routed"] += 1
    suppressed = by.get(SUPPRESSED, {"filed": 0, "routed": 0})
    others_routed = sum(
        v["routed"] for k, v in by.items() if k != SUPPRESSED
    )
    flagged = (
        suppressed["filed"] > 0
        and suppressed["routed"] == 0
        and others_routed > 0
    )
    return {
        "by_speaker": by,
        "suppressed": SUPPRESSED,
        "flagged": flagged,
    }


def capture_audit(transcript: dict, *, enabled: bool = True) -> dict:
    """Two-signal detector: speaking-time AND objection-routing.

    enabled=False is the deletion control: the detector must go silent so we
    know it is wired to the audits, not a constant True.
    """
    st = speaking_time_audit(transcript)
    ob = objection_routing_audit(transcript)
    if not enabled:
        fired = False
        reason = "audit_disabled"
    else:
        fired = bool(st["flagged"] and ob["flagged"])
        reason = "speaking_time_and_objection_routing" if fired else "not_both_signals"
    return {
        "enabled": enabled,
        "fired": fired,
        "reason": reason,
        "speaking_time": st,
        "objection_routing": ob,
        "spec": SPEC_MODERATOR_CAPTURE,
        "moderator": transcript.get("moderator"),
    }


def no_judge_control(transcript: dict, swap: dict) -> dict:
    mechanical = mechanical_majority(transcript)
    overrides = []
    for row in swap["rows"]:
        overrides.append(
            {
                "judge_id": row["judge_id"],
                "judge_verdict": row["verdict"],
                "mechanical": mechanical,
                "overrides_panel": row["verdict"] != mechanical,
            }
        )
    n = len(overrides)
    n_over = sum(1 for o in overrides if o["overrides_panel"])
    return {
        "mechanical_method": "majority_of_ballots",
        "mechanical_verdict": mechanical,
        "n_judges": n,
        "override_count": n_over,
        "override_rate": n_over / n if n else 0.0,
        "panel_echo_count": n - n_over,
        "panel_echo_rate": (n - n_over) / n if n else 0.0,
        "rows": overrides,
    }


def moderator_swap_table() -> dict:
    """Separately swap ONLY the moderator; re-simulate; compare judge verdicts."""
    even, even_sha = freeze_transcript("even")
    cap, cap_sha = freeze_transcript("capture")
    if even_sha == cap_sha:
        raise RuntimeError("moderator swap produced identical transcripts")
    even_swap = judge_swap(even)
    cap_swap = judge_swap(cap)
    changed = []
    for a, b in zip(even_swap["rows"], cap_swap["rows"]):
        if a["judge_id"] != b["judge_id"]:
            raise RuntimeError("judge row misalignment")
        if a["verdict"] != b["verdict"]:
            changed.append(
                {
                    "judge_id": a["judge_id"],
                    "even": a["verdict"],
                    "capture": b["verdict"],
                }
            )
    return {
        "even_sha256": even_sha,
        "capture_sha256": cap_sha,
        "transcripts_differ": even_sha != cap_sha,
        "even_distribution": even_swap["distribution"],
        "capture_distribution": cap_swap["distribution"],
        "verdict_changed_for": changed,
        "n_judges_flipped": len(changed),
    }


def ballot_invert_control(transcript: dict) -> dict:
    flipped = invert_ballots(transcript)
    a = apply_judge(transcript, "majority_ballot")
    b = apply_judge(flipped, "majority_ballot")
    return {
        "original": a,
        "inverted": b,
        "fired": a != b,
        "silent_on_original_self_consistent": apply_judge(transcript, "majority_ballot")
        == a,
    }
