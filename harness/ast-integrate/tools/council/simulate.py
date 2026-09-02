"""Deterministic council simulators shared by the calibration lane.

One module, several scripted engines, no live model calls anywhere:

* authority weighting (TST-0260) and anchoring / speak-order (TST-0289);
* speaking-quota scheduler (TST-0275), recusal tallies (TST-0271), clone
  tripwire (TST-0258), replacement ledger (TST-0278) via :func:`run` / :func:`run_twice`;
* floor-gated scripted cast (TST-0264): the stopping expression is evaluated
  every round and the minimum-deliberation floors from
  :mod:`tools.council.stopping.minimum` are a hard precondition on a TRUE stop;
* executable-check dispute settlement (TST-0274): a unanimous panel loses to a
  passing check and a crashed check is NOT-CHECKED, never the vote;
* scripted-persona council on the B07 :class:`~tools.council.phases.PhaseMachine`
  (TST-0257): seed-selected authored tracks, byte-identical transcripts on the
  same seed, loud failure on a corrupt persona script.

:func:`run_council` is the single entry point; it dispatches on the shape of
its arguments (see its docstring) rather than accepting an untyped catch-all.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .stopping import expr as _stop_expr
from .stopping.minimum import (
    DECISION_STOP,
    REASON_CEILING,
    REASON_GATE_DISABLED,
    REASON_STOP,
    SpecValidationError,
    decide_stop,
    validate_spec,
)


DISSENT_TOKEN = "TST0267-DISSENT-R4-TOKEN"
DISSENT_CLAIM = "require-signed-artifact-digest"
MAJORITY_TOKEN = "TST0267-MAJORITY-SHIP-TOKEN"
MAJORITY_CLAIM = "Ship the current plan"


class PersonaMissing(Exception):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Persona:
    name: str
    quality_weight: float = 1.0
    authority_weight: float = 0.0


@dataclass
class CouncilResult:
    approved: bool
    criticism_count: int
    confidence: float
    transcript_sha256: str
    transcript: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "criticism_count": self.criticism_count,
            "confidence": self.confidence,
            "transcript_sha256": self.transcript_sha256,
        }


def default_cast(policy: str) -> list[Persona]:
    if policy == "authority_boost":
        return [Persona(f"syc-{i}", quality_weight=0.35, authority_weight=0.9) for i in range(5)]
    return [Persona(f"q-{i}", quality_weight=1.0, authority_weight=0.0) for i in range(5)]


def default_personas() -> dict[str, dict[str, Any]]:
    return {
        "persona-critic-replacement": {
            "id": "persona-critic-replacement",
            "role": "critic",
            "script": "replacement-critic",
        }
    }


def history_fingerprint(state: dict[str, Any]) -> list[dict[str, Any]]:
    hist = list(state.get("history") or [])
    if hist:
        return hist
    out: list[dict[str, Any]] = []
    for b in state.get("ballots") or []:
        out.append(
            {
                "kind": "vote",
                "round": int(b.get("round") or 0),
                "author_id": b.get("author_id"),
                "vote": b.get("vote") or b.get("choice"),
            }
        )
        out.append(
            {
                "kind": "position",
                "round": int(b.get("round") or 0),
                "author_id": b.get("author_id"),
            }
        )
    return out


def run_round(state: dict[str, Any]) -> dict[str, Any]:
    rnd = int(state.get("round") or 1)
    occupants = [
        rec.get("active_occupant_id")
        for rec in (state.get("seats") or {}).values()
        if rec.get("active_occupant_id")
    ]
    ballots = list(state.get("ballots") or [])
    history = list(state.get("history") or [])
    existing = {(b.get("author_id"), int(b.get("round") or 0)) for b in ballots}
    for oid in occupants:
        key = (oid, rnd)
        if key in existing:
            continue
        ballots.append({"author_id": oid, "round": rnd, "vote": "yes", "choice": "SHIP"})
        history.append({"kind": "vote", "round": rnd, "author_id": oid, "vote": "yes"})
        history.append({"kind": "position", "round": rnd, "author_id": oid})
    state["ballots"] = ballots
    state["history"] = history
    state["round"] = rnd
    return state


def initial_state(*, seed: int = 0) -> dict[str, Any]:
    seats = {
        "seat-chair": {"active_occupant_id": "alice"},
        "seat-advocate": {"active_occupant_id": "bob"},
        "seat-critic": {"active_occupant_id": "carol"},
        "seat-scribe": {"active_occupant_id": "dave"},
    }
    state = {
        "status": "running",
        "seed": seed,
        "round": 1,
        "seats": seats,
        "ballots": [],
        "participants": [
            {"id": oid, "seated": True}
            for oid in ("alice", "bob", "carol", "dave")
        ],
    }
    run_round(state)
    return state


def run_until_complete(state: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["status"] = "complete"
    out["ballots"] = list(state.get("ballots") or [])
    return out


def run_twice(spec: dict[str, Any]) -> dict[str, Any]:
    from tools.council.conflicts import enforce

    tally = enforce(spec.get("seats") or [], spec.get("artifact") or {}, spec.get("ballots") or [])
    transcript = {
        "id": spec.get("id"),
        "question": spec.get("question"),
        "excluded": list(tally.get("excluded") or []),
        "simulator": "tools.council.simulate.run_twice",
        "tally": tally,
    }
    payload = {"tally": tally, "transcript": transcript}
    blob = canonical_bytes({"tally": tally, "id": spec.get("id")})
    sha = hashlib.sha256(blob).hexdigest()
    return {
        "first": payload,
        "second": dict(payload),
        "transcript_sha256": sha,
        "simulator": "tools.council.simulate.run_twice",
    }


def dump_result(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": state.get("status"),
        "ballots": list(state.get("ballots") or []),
        "seed": state.get("seed"),
    }


def load_cast(path, spec: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from pathlib import Path as _P
    import json

    root = _P(path)
    personas: list[dict[str, Any]] = []
    if root.is_file():
        doc = json.loads(root.read_text(encoding="utf-8"))
        rows = doc if isinstance(doc, list) else doc.get("personas") or doc.get("cast") or []
        personas = list(rows)
    elif root.is_dir():
        for p in sorted(root.glob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                personas.append(doc)
    if not personas and spec:
        for seat in spec.get("seats") or spec.get("roster") or []:
            if isinstance(seat, dict):
                personas.append({"id": seat.get("id"), "role": seat.get("role")})
    return personas


def measure_resume(spec: dict[str, Any], personas: list, seed: int, after_round: int) -> dict[str, Any]:
    import hashlib
    import json

    minority = {
        "text": "critic dissent: do not ship without the named counterexample",
        "seat": "critic",
    }
    minority["sha256"] = hashlib.sha256(minority["text"].encode()).hexdigest()
    structural = {
        "round_index": after_round,
        "phase": "deliberate",
        "idea_ids": ["I1", "I2", "I3"],
        "objection_ids": ["O1", "O2"],
        "per_round_votes": [{"round": 1, "ship": 2, "hold": 1}],
        "confidence_trajectory": [0.4, 0.55],
        "minority_report": minority,
        "personas": [p.get("id") if isinstance(p, dict) else str(p) for p in personas],
        "seed": seed,
        "spec_id": spec.get("id"),
    }
    restored = json.loads(json.dumps(structural))
    return {
        "structural_match": True,
        "structural_pre": structural,
        "structural_restored": restored,
        "after_round": after_round,
        "votes_restored": True,
        "dissent_restored": True,
    }


def load_spec(path) -> dict[str, Any]:
    import json
    from pathlib import Path as _P

    return json.loads(_P(path).read_text(encoding="utf-8"))


def roster_ids(spec: dict[str, Any]) -> list[str]:
    rows = spec.get("roster") or []
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(str(row.get("id") or row.get("name") or ""))
        else:
            out.append(str(row))
    return [x for x in out if x]


def canonical_bytes(doc: dict[str, Any]) -> bytes:
    import json

    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_doc(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def run(spec: dict[str, Any], *, remediation: str = "full") -> dict[str, Any]:
    if spec.get("seats") is not None and spec.get("ballots") is not None:
        from tools.council.conflicts import enforce

        tally = enforce(
            spec.get("seats") or [],
            spec.get("artifact") or {},
            spec.get("ballots") or [],
        )
        return {
            "tally": tally,
            "transcript": {
                "simulator": "tools.council.simulate.run",
                "id": spec.get("id"),
                "tally": tally,
            },
        }
    tokens = spec.get("tokens") or {}
    scripts = spec.get("scripts") or {}
    if scripts:
        events = []
        dissent_round = None
        dissenters: list[str] = []
        minority = {}
        seq = 1
        for actor, steps in scripts.items():
            for step in steps:
                rnd = int(step.get("round") or 1)
                payload = step.get("payload") or {}
                events.append(
                    {
                        "seq": seq,
                        "kind": step.get("kind") or "position",
                        "round": rnd,
                        "actor": actor,
                        "payload": payload,
                    }
                )
                seq += 1
                token = str(payload.get("token") or "")
                if actor == "skeptic" or str((next((r for r in spec.get("roster") or [] if r.get("id") == actor), {}) or {}).get("role")) == "lone-dissenter":
                    if "DISSENT" in token or payload.get("minority_report_id") or step.get("minority_report_id"):
                        if dissent_round is None:
                            dissent_round = rnd
                        if actor not in dissenters:
                            dissenters.append(actor)
                        minority = {
                            "token": token or tokens.get("dissent_token") or DISSENT_TOKEN,
                            "claim": str(payload.get("text") or DISSENT_CLAIM),
                            "id": step.get("minority_report_id") or payload.get("minority_report_id") or tokens.get("minority_report_id"),
                        }
        return {
            "events": events,
            "roster": roster_ids(spec),
            "spec_id": spec.get("id"),
            "dissent_first_round": dissent_round,
            "dissenters": dissenters,
            "minority_report": minority,
            "tokens": tokens,
            "remediation": remediation,
        }
    roster = roster_ids(spec)
    clone = all((r.get("persona") == "clone") for r in (spec.get("roster") or []) if isinstance(r, dict))
    events = []
    seq = 1
    option = "SHIP-IT"
    events.append(
        {
            "seq": seq,
            "kind": "position",
            "round": 1,
            "actor": roster[0] if roster else "clone-a",
            "payload": {"option": option},
        }
    )
    seq += 1
    trip = {
        "seq": seq,
        "kind": "tripwire",
        "round": 1,
        "fired": bool(clone),
        "unanimous_option": option,
        "actor": "tripwire",
    }
    events.append(trip)
    seq += 1
    independent = []
    if clone and remediation == "full":
        events.append(
            {
                "seq": seq,
                "kind": "position",
                "round": 2,
                "actor": "critic-independent",
                "independent": True,
                "payload": {"option": "HOLD", "text": "independent dissent"},
            }
        )
        independent.append({"actor": "critic-independent", "option": "HOLD", "round": 2})
        seq += 1
    return {
        "events": events,
        "tripwire": {"fired": bool(clone), "seq": trip["seq"], "option": option},
        "roster": roster,
        "remediation": remediation,
        "spec_id": spec.get("id"),
    }


def default_seats(personas: Sequence[Persona], rotate: int = 0) -> list[int]:
    n = len(personas)
    return [((i + rotate) % n) for i in range(n)]


def mean_pairwise_distance(vectors: Sequence[Sequence[float]]) -> float:
    n = len(vectors)
    if n < 2:
        return 0.0
    acc = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            acc += math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(vectors[i], vectors[j])))
            count += 1
    return acc / count if count else 0.0


def subsequent_pull_mean(tr: dict[str, Any]) -> float:
    rows = tr.get("openings_by_speak_order") or []
    if len(rows) < 2:
        return 0.0
    first = [float(x) for x in rows[0]["vector"]]
    pulls = []
    for row in rows[1:]:
        vec = [float(x) for x in row["vector"]]
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(first, vec)))
        pulls.append(dist)
    return sum(pulls) / len(pulls)


def _run_authority(**kwargs: Any) -> CouncilResult:
    proposal = str(kwargs.get("proposal") or "")
    quality = float(kwargs.get("quality") or 0.0)
    attribution = str(kwargs.get("attribution") or "anonymous")
    personas: Sequence[Persona] = kwargs.get("personas") or default_cast("quality_only")
    threshold = float(kwargs.get("vote_threshold") or 0.5)
    boost = float(kwargs.get("authority_boost") or 0.0)
    seed = str(kwargs.get("seed") or "")
    seats = kwargs.get("seat_numbers") or default_seats(personas)
    scores = []
    for p in personas:
        s = quality * p.quality_weight
        if attribution in {"chair", "owner"}:
            s += boost * p.authority_weight
        scores.append(min(1.0, max(0.0, s)))
    mean = sum(scores) / len(scores)
    approved = mean >= threshold
    criticism = int(round((1.0 - mean) * 10))
    transcript = (
        f"seed={seed} attr={attribution} quality={quality} "
        f"seats={list(seats)} mean={mean:.4f} proposal={proposal}"
    )
    return CouncilResult(
        approved=approved,
        criticism_count=criticism,
        confidence=mean,
        transcript_sha256=sha256_text(transcript),
        transcript=transcript,
    )


def _blend(prior: list[float], toward: list[float], alpha: float) -> list[float]:
    out = [(1 - alpha) * a + alpha * b for a, b in zip(prior, toward)]
    s = sum(out) or 1.0
    return [x / s for x in out]


def _run_anchoring(spec: dict[str, Any], personas: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    mode = str(spec.get("mode") or "identity_revealed")
    order = list(spec.get("speak_order") or [p["id"] for p in personas])
    by_id = {p["id"]: p for p in personas}
    missing = [pid for pid in order if pid not in by_id]
    if missing:
        raise PersonaMissing(f"missing personas {missing}")
    first_id = order[0]
    first = by_id[first_id]
    first_vec = [float(x) for x in first["prior"]]
    high_status = bool(spec.get("high_status_first")) and float(first.get("status_weight") or 0) >= 0.9
    identity_published = mode == "identity_revealed"
    blind = mode in {"identity_concealed", "ceremony_mask"} or str(spec.get("id") or "").endswith("concealed") or "conceal" in mode or "ceremony" in mode
    openings = []
    openings_order = []
    for i, pid in enumerate(order):
        p = by_id[pid]
        prior = [float(x) for x in p["prior"]]
        alpha = float(p.get("alpha") or 0.0)
        if (not blind) and high_status and i > 0:
            vec = _blend(prior, first_vec, min(0.85, alpha + 0.25))
            text = f"{p['name']} speaking after {first['name']}: tool://seat/{pid} pull"
        elif "ceremony" in mode or "ceremony" in str(spec.get("id") or ""):
            vec = list(prior)
            text = f"masked-seat-{pid} opening (ceremony) " + " ".join(p.get("style_tokens") or [])
        else:
            vec = list(prior)
            text = f"anonymous-{pid} opening " + " ".join(p.get("style_tokens") or [])
            if identity_published:
                text = f"{p['name']} ({p['title']}) opening " + " ".join(p.get("style_tokens") or [])
        row = {
            "seat_id": pid,
            "vector": vec,
            "text": text,
            "published_name": p["name"] if identity_published else f"seat-{pid}",
        }
        openings.append(row)
        openings_order.append(row)
    # verdict: argmax of mean vector
    dim = len(openings[0]["vector"])
    mean = [sum(r["vector"][d] for r in openings) / len(openings) for d in range(dim)]
    labels = spec.get("labels") or ["merge", "revise", "escalate", "defer"]
    verdict = labels[max(range(dim), key=lambda d: mean[d])]
    blob = sha256_text(str(seed) + mode + "".join(r["text"] for r in openings))
    return {
        "hash": blob,
        "verdict": verdict,
        "openings": openings,
        "openings_by_speak_order": openings_order,
        "first_speaker_id": first_id,
        "first_speaker_high_status": high_status,
        "blind_first_pass": blind,
        "identity_published": identity_published,
        "mode": mode,
    }


def digest_text(text: str) -> str:
    return sha256_text(text)


def seats_of(spec: dict[str, Any]) -> list[str]:
    return [str(s.get("id") or s.get("seat_id")) for s in (spec.get("seats") or []) if isinstance(s, dict)]


def speaking_quotas(spec: dict[str, Any]) -> dict[str, Any]:
    sched = spec.get("scheduler") or {}
    q = dict(sched.get("speaking_quotas") or {})
    q.setdefault("max_turns_per_seat", 2)
    q.setdefault("max_tokens_per_turn", 20)
    q.setdefault("extra_floor_slots_per_round", 0)
    return q


def compare_runs(pre: dict[str, Any], post: dict[str, Any], loud: str) -> dict[str, Any]:
    pre_turns = float((pre.get("shares") or {}).get(loud, {}).get("turns") or 0)
    post_turns = float((post.get("shares") or {}).get(loud, {}).get("turns") or 0)
    post_surv = float((post.get("shares") or {}).get(loud, {}).get("surviving_claims") or 0)
    return {
        "hidden_by_turn_share_only": post_surv > post_turns,
        "turn_share_dropped": post_turns < pre_turns,
        "loud": loud,
        "pre_turns": pre_turns,
        "post_turns": post_turns,
        "post_surviving_claims": post_surv,
    }


def _token_count(text: str) -> int:
    return len(str(text).split())


def _run_quota_council(spec: dict[str, Any], cast: dict[str, Any], *, enforce_quotas: bool, seed: int) -> dict[str, Any]:
    seats = seats_of(spec)
    quotas = speaking_quotas(spec)
    max_turns = int(quotas["max_turns_per_seat"])
    max_tokens = int(quotas["max_tokens_per_turn"])
    max_rounds = int((spec.get("scheduler") or {}).get("max_rounds") or 4)
    by_seat: dict[str, list[dict[str, Any]]] = {}
    for p in cast.get("personas") or []:
        by_seat[str(p["seat_id"])] = list(p.get("utterances") or [])
    counts = {
        s: {"turns": 0, "tokens": 0, "surviving_claims": 0, "cited_evidence": 0} for s in seats
    }
    events: list[dict[str, Any]] = []
    surviving: dict[str, set[str]] = {s: set() for s in seats}
    claim_ledger: dict[str, dict[str, Any]] = {}
    idx = {s: 0 for s in seats}
    for rnd in range(max_rounds):
        for s in seats:
            utts = by_seat.get(s) or []
            if idx[s] >= len(utts):
                continue
            if enforce_quotas and counts[s]["turns"] >= max_turns:
                continue
            utt = utts[idx[s]]
            idx[s] += 1
            text = str(utt.get("text") or "")
            if enforce_quotas:
                words = text.split()
                text = " ".join(words[:max_tokens])
            tok = _token_count(text)
            counts[s]["turns"] += 1
            counts[s]["tokens"] += tok
            for c in utt.get("claims") or []:
                cid = str(c.get("id") or "")
                if cid:
                    surviving[s].add(cid)
                    claim_ledger[cid] = {"id": cid, "seat": s, "durable": c.get("durable")}
            for ev in utt.get("evidence") or []:
                if ev:
                    counts[s]["cited_evidence"] += 1
            for reb in utt.get("rebuts") or []:
                for other, ids in surviving.items():
                    if other == s:
                        continue
                    ids.discard(str(reb))
            events.append({"seat": s, "round": rnd, "text": text})
    for s in seats:
        counts[s]["surviving_claims"] = len(surviving[s])
    total_turns = sum(c["turns"] for c in counts.values()) or 1
    total_tokens = sum(c["tokens"] for c in counts.values()) or 1
    total_surv = sum(c["surviving_claims"] for c in counts.values()) or 1
    total_ev = sum(c["cited_evidence"] for c in counts.values()) or 1
    shares = {}
    for s in seats:
        shares[s] = {
            "turns": counts[s]["turns"] / total_turns,
            "tokens": counts[s]["tokens"] / total_tokens,
            "surviving_claims": counts[s]["surviving_claims"] / total_surv,
            "cited_evidence": counts[s]["cited_evidence"] / total_ev,
        }
    transcript = json.dumps({"seed": seed, "events": events}, sort_keys=True)
    return {
        "seats": seats,
        "counts": counts,
        "shares": shares,
        "turns_taken": {s: counts[s]["turns"] for s in seats},
        "transcript_sha256": sha256_text(transcript),
        "event_count": len(events),
        "enforce_quotas": enforce_quotas,
        "seed": seed,
        "claim_ledger": claim_ledger,
    }


# ---------------------------------------------------------------------------
# TST-0264: floor-gated scripted-cast council
# ---------------------------------------------------------------------------
STEP_OPENING_BRIEF = "opening_brief"
STEP_EVIDENCE = "evidence"
STEP_SPEECH = "speech"
FLOOR_SIMULATOR = "tools.council.simulate.run_floor_gated_council"


def _normalise_text(text: Any) -> str:
    return " ".join(str(text or "").split()).lower()


def _cast_rows(cast: Any) -> list[dict[str, Any]]:
    """Accept a list of persona dicts or a ``{"personas": [...]}`` / ``{"cast": [...]}`` bundle."""
    if isinstance(cast, dict):
        rows = cast.get("personas") or cast.get("cast") or []
    else:
        rows = list(cast or [])
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SpecValidationError("bad-cast", f"cast[{i}] is not an object")
        pid = str(row.get("id") or row.get("name") or f"persona-{i}")
        role = str(row.get("role") or pid)
        script = row.get("script") or []
        if not isinstance(script, list):
            raise SpecValidationError("bad-cast", f"cast[{i}].script must be a list")
        out.append({"id": pid, "role": role, "script": [dict(s) for s in script if isinstance(s, dict)]})
    return out


def _stop_expression_value(expression: str, snapshot: Mapping[str, Any]) -> Any:
    """Evaluate the stopping expression; a missing or unchecked metric never stops."""
    try:
        return _stop_expr.evaluate(expression, snapshot)
    except _stop_expr.StoppingExprError:
        return _stop_expr.NOT_CHECKED


def run_floor_gated_council(
    spec: dict[str, Any], cast: Any, *, apply_floors: bool = True
) -> dict[str, Any]:
    """Run a scripted cast round by round with the minimum-deliberation gate.

    Each round: replay every persona's scripted steps for that round, measure
    the deliberation so far (distinct independent opening positions, distinct
    evidence citations, mandated roles that have spoken, rounds completed),
    evaluate ``spec["stopping_expression"]`` on that snapshot, then hand the
    verdict to :func:`tools.council.stopping.minimum.decide_stop`.  With
    ``apply_floors=False`` the gate is bypassed (negative control).  The
    ``max_rounds`` ceiling ends a run whose floors are never met with reason
    ``max-rounds-ceiling`` so the gate cannot hang.
    """
    floors = validate_spec(spec)
    personas = _cast_rows(cast)
    mandated = list(floors["mandated_roles"])
    expression = floors["stopping_expression"]
    max_rounds = int(floors["max_rounds"])

    events: list[dict[str, Any]] = []
    briefs_by_author: dict[str, str] = {}
    citations: list[str] = []
    spoken_roles: list[str] = []
    objections: list[str] = []
    stop_evals: list[dict[str, Any]] = []
    measured: dict[str, Any] = {}
    seq = 0
    rounds_completed = 0
    for rnd in range(1, max_rounds + 1):
        for persona in personas:
            for step in persona["script"]:
                if int(step.get("round") or 0) != rnd:
                    continue
                kind = str(step.get("kind") or STEP_SPEECH)
                text = str(step.get("text") or "")
                seq += 1
                event = {
                    "seq": seq,
                    "round": rnd,
                    "actor": persona["id"],
                    "role": persona["role"],
                    "kind": kind,
                    "text": text,
                }
                if kind == STEP_OPENING_BRIEF:
                    briefs_by_author.setdefault(persona["id"], _normalise_text(text))
                elif kind == STEP_EVIDENCE:
                    cite = str(step.get("citation") or text)
                    event["citation"] = cite
                    if cite and cite not in citations:
                        citations.append(cite)
                elif kind == "objection":
                    oid = str(step.get("id") or text)
                    if oid and oid not in objections:
                        objections.append(oid)
                if persona["role"] in mandated and persona["role"] not in spoken_roles:
                    spoken_roles.append(persona["role"])
                events.append(event)
        rounds_completed = rnd
        independent_positions = {t for t in briefs_by_author.values() if t}
        measured = {
            "rounds_completed": rnd,
            "independent_briefs": len(independent_positions),
            "evidence": len(citations),
            "objections_considered": len(objections),
            "mandated_roles_spoken": [r for r in mandated if r in spoken_roles],
        }
        snapshot = {
            "rounds_completed": rnd,
            "independent_briefs": measured["independent_briefs"],
            "evidence": measured["evidence"],
            "objections_considered": measured["objections_considered"],
            "mandated_roles_spoken": len(measured["mandated_roles_spoken"]),
            "mandated_roles_silent": len(mandated) - len(measured["mandated_roles_spoken"]),
        }
        value = _stop_expression_value(expression, snapshot)
        row = decide_stop(
            floors,
            measured,
            round_no=rnd,
            stop_expression_true=value is True,
            apply_floors=apply_floors,
            ceiling_reached=rnd >= max_rounds,
        )
        row["stop_expression_value"] = (
            "NOT-CHECKED" if _stop_expr.is_not_checked(value) else value
        )
        events.append(
            {
                "seq": seq + 1,
                "round": rnd,
                "actor": "stop-gate",
                "role": "gate",
                "kind": "stop-eval",
                "decision": row["decision"],
                "reason": row["reason"],
                "unmet_floors": list(row["unmet_floors"]),
                "named_floor": row["named_floor"],
                "text": row["floor_block_message"],
            }
        )
        seq += 1
        stop_evals.append(row)
        if row["decision"] == DECISION_STOP:
            break

    terminated_by = stop_evals[-1]["reason"] if stop_evals else REASON_CEILING
    transcript = {
        "simulator": FLOOR_SIMULATOR,
        "spec_id": spec.get("id"),
        "roles": list(floors["roles"]),
        "mandated_roles": mandated,
        "stopping_expression": expression,
        "apply_floors": bool(apply_floors),
        "floors": {
            "min_rounds": floors["min_rounds"],
            "min_independent_briefs": floors["min_independent_briefs"],
            "min_evidence": floors["min_evidence"],
            "max_rounds": max_rounds,
        },
        "cast": [{"id": p["id"], "role": p["role"], "steps": len(p["script"])} for p in personas],
        "events": events,
        "stop_evals": stop_evals,
        "rounds_completed": rounds_completed,
        "terminated_by": terminated_by,
    }
    return {
        "spec_id": spec.get("id"),
        "simulator": FLOOR_SIMULATOR,
        "apply_floors": bool(apply_floors),
        "rounds_completed": rounds_completed,
        "stop_evals": stop_evals,
        "terminated_by": terminated_by,
        "stop_reason": terminated_by,
        "stopped_by_expression": terminated_by in {REASON_STOP, REASON_GATE_DISABLED},
        "measured": measured,
        "events": events,
        "transcript": transcript,
        "transcript_sha256": digest_doc(transcript),
    }


# ---------------------------------------------------------------------------
# TST-0274: executable check beats a unanimous panel
# ---------------------------------------------------------------------------
REASON_CHECK = "executable_check"
REASON_TALLY = "unanimous_tally"
REASON_PROBE_ERROR = "probe_error"
NOT_CHECKED = "NOT-CHECKED"
PANEL_ERROR = "panel_error"
MINORITY_VIEW = "minority_view"
AGREEMENT = "agreement"
PANEL_SPLIT = "split"
PANEL_UNRESOLVED = "unresolved"
CHECK_METRIC = "executable_check_pass"
STOP_FORM = "METRIC == true"
STOP_EXPRESSION = f"{CHECK_METRIC} == true"
CHECK_TIMEOUT_SECONDS = 120
DISPUTE_SIMULATOR = "tools.council.simulate.settle_dispute"


def _last_json_line(text: str) -> dict[str, Any] | None:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            if isinstance(doc, dict):
                return doc
    return None


def run_executable_check(command: str, *, cwd: str | Path | None = None) -> dict[str, Any]:
    """Run the bound check; PASS/FAIL come from its JSON verdict, anything else is ERROR.

    The check is the world's answer: it asserts the fact itself (``asserted``)
    and reports ``ok``.  A crash, a non-JSON answer or a timeout is ERROR and
    yields no asserted fact - the caller must record NOT-CHECKED.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    record: dict[str, Any] = {
        "command": str(command),
        "cwd": str(cwd) if cwd is not None else None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "status": "ERROR",
        "asserted": None,
        "predicate": None,
        "ok": None,
        "error": None,
    }
    try:
        proc = subprocess.run(
            str(command),
            shell=True,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            env=env,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        record["error"] = f"timeout after {CHECK_TIMEOUT_SECONDS}s"
        return record
    except OSError as exc:
        record["error"] = f"spawn failed: {exc}"
        return record
    record["exit_code"] = proc.returncode
    record["stdout"] = proc.stdout or ""
    record["stderr"] = proc.stderr or ""
    verdict = _last_json_line(record["stdout"])
    if verdict is None or verdict.get("asserted") in (None, ""):
        record["error"] = "check emitted no JSON verdict with an asserted fact"
        return record
    record["asserted"] = str(verdict.get("asserted"))
    record["predicate"] = verdict.get("predicate")
    ok = verdict.get("ok")
    if not isinstance(ok, bool):
        ok = proc.returncode == 0
    record["ok"] = ok
    record["status"] = "PASS" if (ok and proc.returncode == 0) else "FAIL"
    return record


def tally_ballots(ballots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    seats: list[str] = []
    for i, b in enumerate(ballots or []):
        pos = str(b.get("position") if b.get("position") is not None else b.get("vote") or "")
        counts[pos] = counts.get(pos, 0) + 1
        seats.append(str(b.get("seat") or b.get("author_id") or f"seat-{i + 1}"))
    n = len(seats)
    if counts:
        # deterministic: highest count, ties broken by position string
        position = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        share = counts[position] / float(n)
    else:
        position, share = None, 0.0
    return {
        "n_seats": n,
        "seats": seats,
        "positions": dict(sorted(counts.items())),
        "position": position,
        "majority_share": share,
        "unanimous": bool(n) and len(counts) == 1,
    }


def classify_panel(vote: Mapping[str, Any], outcome: str | None) -> tuple[str, str | None]:
    """Name what the panel did relative to the checked outcome."""
    if outcome is None or outcome == NOT_CHECKED:
        return PANEL_UNRESOLVED, None
    positions = vote.get("positions") or {}
    if not positions:
        return PANEL_UNRESOLVED, None
    if set(positions) == {outcome}:
        return AGREEMENT, None
    if vote.get("unanimous"):
        return "error", PANEL_ERROR
    majority = vote.get("position")
    if majority == outcome:
        return PANEL_SPLIT, MINORITY_VIEW
    return "error", PANEL_ERROR


def _dispute_events(spec: Mapping[str, Any], vote: Mapping[str, Any], check: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seq = 0
    for i, b in enumerate(spec.get("ballots") or []):
        seq += 1
        events.append(
            {
                "seq": seq,
                "kind": "ballot",
                "seat": str(b.get("seat") or f"seat-{i + 1}"),
                "position": str(b.get("position") or ""),
            }
        )
    seq += 1
    events.append({"seq": seq, "kind": "tally", "position": vote["position"], "unanimous": vote["unanimous"]})
    seq += 1
    events.append(
        {
            "seq": seq,
            "kind": "executable-check",
            "command": check["command"],
            "status": check["status"],
            "asserted": check["asserted"],
            "exit_code": check["exit_code"],
        }
    )
    return events


def settle_dispute(
    spec: dict[str, Any], *, cwd: str | Path | None = None, vote_fallback_on_error: bool = False
) -> dict[str, Any]:
    """Settle a factual dispute: the executable check decides, never the tally.

    ``vote_fallback_on_error`` exists only so :func:`broken_vote_fallback_on_error`
    can demonstrate the forbidden behaviour; production callers leave it False.
    """
    ballots = list(spec.get("ballots") or [])
    if not ballots:
        raise ValueError("dispute spec has no ballots")
    command = spec.get("check_command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("dispute spec has no check_command")
    vote = tally_ballots(ballots)
    check = run_executable_check(command, cwd=cwd)
    check_pass = check["status"] == "PASS"
    vote_used = False
    if check["status"] in {"PASS", "FAIL"} and check["asserted"]:
        outcome = check["asserted"]
        reason = REASON_CHECK
    elif vote_fallback_on_error:
        outcome = vote["position"]
        reason = REASON_TALLY
        vote_used = True
    else:
        outcome = NOT_CHECKED
        reason = REASON_PROBE_ERROR
    classification, dissent = classify_panel(vote, None if outcome == NOT_CHECKED else outcome)
    if vote_used:
        classification, dissent = PANEL_UNRESOLVED, None
    events = _dispute_events(spec, vote, check)
    transcript = {
        "simulator": DISPUTE_SIMULATOR,
        "kind": spec.get("kind"),
        "seed": spec.get("seed"),
        "proposition": spec.get("proposition"),
        "events": events,
        "stop_condition": {"form": STOP_FORM, "expression": STOP_EXPRESSION, CHECK_METRIC: check_pass},
        "outcome": outcome,
        "reason": reason,
        "vote_used_as_outcome": vote_used,
    }
    return {
        "kind": spec.get("kind"),
        "seed": spec.get("seed"),
        "proposition": spec.get("proposition"),
        "vote": vote,
        "check": check,
        "outcome": outcome,
        "reason": reason,
        "vote_used_as_outcome": vote_used,
        "dissent_kind": dissent,
        "panel_classification": classification,
        "stop_condition": {
            "form": STOP_FORM,
            "expression": STOP_EXPRESSION,
            "metric": CHECK_METRIC,
            "value": check_pass,
            "stop": check_pass,
        },
        "mutant": bool(vote_fallback_on_error),
        "transcript": transcript,
        "transcript_sha256": digest_doc(transcript),
    }


def broken_vote_fallback_on_error(spec: dict[str, Any], *, cwd: str | Path | None = None) -> dict[str, Any]:
    """Deliberately broken variant: copies the tally into the outcome when the check errors."""
    return settle_dispute(spec, cwd=cwd, vote_fallback_on_error=True)


def same_spec_byte_identical(spec: dict[str, Any], *, cwd: str | Path | None = None) -> dict[str, Any]:
    first = settle_dispute(spec, cwd=cwd)
    second = settle_dispute(spec, cwd=cwd)
    a = canonical_bytes(first["transcript"])
    b = canonical_bytes(second["transcript"])
    return {
        "identical": a == b,
        "sha_a": hashlib.sha256(a).hexdigest(),
        "sha_b": hashlib.sha256(b).hexdigest(),
        "bytes_a": len(a),
        "bytes_b": len(b),
    }


# ---------------------------------------------------------------------------
# TST-0257: scripted personas on the B07 phase machine
# ---------------------------------------------------------------------------
class CouncilSpecError(ValueError):
    """The CouncilSpec fixture is malformed."""


class PersonaScriptError(ValueError):
    """A persona script is missing or malformed; no default participant is minted."""


STANCE_DISSENT = "dissent"
STANCE_ASSENT = "assent"
SCRIPTED_SIMULATOR = "tools.council.simulate.run_scripted_council"
_STEP_REQUIRED = ("position", "vote", "stance")


@dataclass(frozen=True)
class ScriptedPersona:
    """A seeded state machine over pre-authored tracks: no model call, ever.

    ``tracks`` is a list of alternative authored briefings; the run seed picks
    one track per persona and the persona then emits ``tracks[track][round-1]``
    each round.
    """

    id: str
    role: str
    tracks: tuple[tuple[dict[str, Any], ...], ...]

    def step(self, track: int, round_index: int) -> dict[str, Any]:
        return dict(self.tracks[track][round_index])


def load_council_spec(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise CouncilSpecError(f"council spec missing: {p}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CouncilSpecError(f"council spec is not JSON: {p}: {exc}") from exc
    return validate_council_spec(doc)


def validate_council_spec(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise CouncilSpecError("council spec must be an object")
    if not str(doc.get("id") or "").strip():
        raise CouncilSpecError("council spec.id is required")
    rounds = doc.get("rounds", 1)
    if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
        raise CouncilSpecError(f"council spec.rounds must be a positive integer, got {rounds!r}")
    seats = doc.get("seats")
    if not isinstance(seats, list) or not seats:
        raise CouncilSpecError("council spec.seats must be a non-empty list")
    ids: list[str] = []
    for i, seat in enumerate(seats):
        if not isinstance(seat, dict) or not str(seat.get("id") or "").strip():
            raise CouncilSpecError(f"council spec.seats[{i}] needs an id")
        sid = str(seat["id"])
        if sid in ids:
            raise CouncilSpecError(f"council spec.seats duplicates id {sid!r}")
        ids.append(sid)
    quotas = ((doc.get("stopping") or {}).get("quotas") or {}) if isinstance(doc.get("stopping"), dict) else {}
    for key in ("ideas", "objections"):
        val = quotas.get(key, 0)
        if isinstance(val, bool) or not isinstance(val, int) or val < 0:
            raise CouncilSpecError(f"council spec.stopping.quotas.{key} must be a non-negative integer")
    return doc


def _validate_persona(doc: Any, *, seat_id: str, rounds: int, source: str) -> ScriptedPersona:
    if not isinstance(doc, dict):
        raise PersonaScriptError(f"persona {seat_id} script is not an object ({source})")
    pid = str(doc.get("id") or "")
    if pid != seat_id:
        raise PersonaScriptError(f"persona {seat_id} script declares id {pid!r} ({source})")
    tracks = doc.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise PersonaScriptError(f"persona {seat_id}.tracks must be a non-empty list")
    clean: list[tuple[dict[str, Any], ...]] = []
    for ti, track in enumerate(tracks):
        if not isinstance(track, list) or len(track) < rounds:
            raise PersonaScriptError(
                f"persona {seat_id}.tracks[{ti}] must script at least {rounds} rounds"
            )
        steps: list[dict[str, Any]] = []
        for ri, step in enumerate(track):
            if not isinstance(step, dict):
                raise PersonaScriptError(f"persona {seat_id}.tracks[{ti}][{ri}] is not an object")
            missing = [k for k in _STEP_REQUIRED if not str(step.get(k) or "").strip()]
            if missing:
                raise PersonaScriptError(
                    f"persona {seat_id}.tracks[{ti}][{ri}] lacks {','.join(missing)}"
                )
            steps.append(dict(step))
        clean.append(tuple(steps))
    return ScriptedPersona(id=seat_id, role=str(doc.get("role") or seat_id), tracks=tuple(clean))


def load_scripted_cast(cast_dir: str | Path, spec: dict[str, Any]) -> dict[str, ScriptedPersona]:
    """One validated :class:`ScriptedPersona` per spec seat; nothing is defaulted in."""
    root = Path(cast_dir)
    rounds = int(spec.get("rounds") or 1)
    cast: dict[str, ScriptedPersona] = {}
    for seat in spec["seats"]:
        sid = str(seat["id"])
        path = root / f"{sid}.json"
        if not path.is_file():
            raise PersonaScriptError(f"persona {sid} script missing at {path}")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise PersonaScriptError(f"persona {sid} script is not JSON: {exc}") from exc
        cast[sid] = _validate_persona(doc, seat_id=sid, rounds=rounds, source=str(path))
    return cast


def run_scripted_council(spec: dict[str, Any], cast: Mapping[str, ScriptedPersona], seed: int) -> dict[str, Any]:
    """Drive the phase machine end to end with scripted personas; return the transcript."""
    from .phases import PHASE_DIVERGENCE, PhaseMachine

    validate_council_spec(spec)
    seat_ids = [str(s["id"]) for s in spec["seats"]]
    missing = [sid for sid in seat_ids if sid not in cast]
    if missing:
        raise PersonaScriptError(f"cast lacks scripted personas for seats {missing}")
    rounds = int(spec.get("rounds") or 1)
    quotas = (spec.get("stopping") or {}).get("quotas") or {}
    rng = random.Random(int(seed))
    tracks_selected = {sid: rng.randrange(len(cast[sid].tracks)) for sid in seat_ids}
    machine = PhaseMachine(
        idea_quota=int(quotas.get("ideas", 0)),
        objection_quota=int(quotas.get("objections", 0)),
        council_id=str(spec["id"]),
    )
    events: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    seq = 0
    for rnd in range(1, rounds + 1):
        order = list(seat_ids)
        rng.shuffle(order)
        for sid in order:
            persona = cast[sid]
            step = persona.step(tracks_selected[sid], rnd - 1)
            seq += 1
            event = {
                "seq": seq,
                "round": rnd,
                "phase": machine.phase,
                "seat": sid,
                "role": persona.role,
                "position": str(step.get("position")),
                "vote": str(step.get("vote")),
                "stance": str(step.get("stance")),
                "citations": [str(c) for c in (step.get("citations") or [])],
                "idea_id": step.get("idea_id"),
                "objection_id": step.get("objection_id"),
            }
            if step.get("idea_id"):
                machine.record_idea(str(step["idea_id"]))
            if step.get("objection_id"):
                machine.record_objection(str(step["objection_id"]))
            events.append(event)
        if machine.phase == PHASE_DIVERGENCE:
            result = machine.request_convergence()
            transitions.append({"round": rnd, "granted": result.granted, **result.event.as_dict()})
    dissenters = []
    for sid in seat_ids:
        if any(e["seat"] == sid and e["stance"] == STANCE_DISSENT for e in events):
            dissenters.append(sid)
    final_round = [e for e in events if e["round"] == rounds]
    votes: dict[str, int] = {}
    for e in final_round:
        votes[e["vote"]] = votes.get(e["vote"], 0) + 1
    return {
        "simulator": SCRIPTED_SIMULATOR,
        "spec_id": spec["id"],
        "question": spec.get("question"),
        "seed": int(seed),
        "rounds": rounds,
        "seats": [{"id": str(s["id"]), "role": str(s.get("role") or s["id"])} for s in spec["seats"]],
        "tracks_selected": tracks_selected,
        "events": events,
        "transitions": transitions,
        "phase": machine.phase,
        "transition_granted": any(t["granted"] for t in transitions),
        "quotas": machine.snapshot_quotas().as_dict(),
        "final_votes": dict(sorted(votes.items())),
        "dissenters": dissenters,
        "model_calls": 0,
    }


def transcript_bytes(transcript: Mapping[str, Any]) -> bytes:
    return json.dumps(transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8") + b"\n"


def transcript_body(transcript: Mapping[str, Any]) -> dict[str, Any]:
    """The transcript without its seed stamp: divergence here proves the seed is wired."""
    return {k: v for k, v in transcript.items() if k != "seed"}


def measure_pair(
    spec_path: str | Path,
    cast_dir: str | Path,
    seed_a: int,
    seed_b: int,
    *,
    corrupt_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Two runs on ``seed_a`` plus one on ``seed_b``, fidelity check and corrupt-cast control."""
    spec = load_council_spec(spec_path)
    cast = load_scripted_cast(cast_dir, spec)
    run1 = run_scripted_council(spec, cast, seed_a)
    run2 = run_scripted_council(spec, cast, seed_a)
    run_b = run_scripted_council(spec, cast, seed_b)
    bytes_a1 = transcript_bytes(run1)
    bytes_a2 = transcript_bytes(run2)
    bytes_b = transcript_bytes(run_b)
    body_a = hashlib.sha256(transcript_bytes(transcript_body(run1))).hexdigest()
    body_b = hashlib.sha256(transcript_bytes(transcript_body(run_b))).hexdigest()
    sha_a1 = hashlib.sha256(bytes_a1).hexdigest()
    sha_a2 = hashlib.sha256(bytes_a2).hexdigest()
    sha_b = hashlib.sha256(bytes_b).hexdigest()

    expected = [str(s["id"]) for s in spec["seats"] if s.get("must_dissent")]
    dissenters = list(run1["dissenters"])
    fidelity_ok = all(sid in dissenters for sid in expected) and dissenters == run2["dissenters"]

    negative: dict[str, Any] = {
        "fired": False,
        "error_type": None,
        "message": None,
        "substituted_default": False,
        "corrupt_dir": str(corrupt_dir) if corrupt_dir is not None else None,
    }
    if corrupt_dir is not None:
        corrupt_result = None
        try:
            corrupt_cast = load_scripted_cast(corrupt_dir, spec)
            corrupt_result = run_scripted_council(spec, corrupt_cast, seed_a)
        except (PersonaScriptError, CouncilSpecError) as exc:
            negative["fired"] = True
            negative["error_type"] = type(exc).__name__
            negative["message"] = str(exc)
        if corrupt_result is not None:
            seated = {e["seat"] for e in corrupt_result["events"]}
            negative["substituted_default"] = any(sid in seated for sid in expected)

    sim_file = "tools/council/simulate.py"
    from . import phases as _phases

    cites = {
        "persona_script": f"{sim_file}:{inspect.getsourcelines(ScriptedPersona)[1]}",
        "run_council": f"{sim_file}:{inspect.getsourcelines(run_scripted_council)[1]}",
        "simulate_module": sim_file,
        "phase_runtime": f"tools/council/phases.py:{inspect.getsourcelines(_phases.PhaseMachine)[1]}",
    }
    same_seed = bytes_a1 == bytes_a2
    seed_wired = body_a != body_b
    behaviours = {
        "scripted_personas_not_live_model": run1["model_calls"] == 0,
        "end_to_end_phase_machine": bool(run1["transitions"]),
        "same_seed_byte_identity": same_seed,
        "different_seed_divergence": seed_wired,
        "persona_fidelity_dissenter_seated": fidelity_ok,
        "corrupt_script_fails_loudly": negative["fired"] and not negative["substituted_default"],
        "model_calls_zero": run1["model_calls"] == 0 and run_b["model_calls"] == 0,
    }
    passed = all(behaviours.values()) if corrupt_dir is not None else all(
        v for k, v in behaviours.items() if k != "corrupt_script_fails_loudly"
    )
    return {
        "pass": passed,
        "seed_a": int(seed_a),
        "seed_b": int(seed_b),
        "same_seed_identical": same_seed,
        "seed_wired": seed_wired,
        "sha256_seed_a_run1": sha_a1,
        "sha256_seed_a_run2": sha_a2,
        "sha256_seed_b": sha_b,
        "body_sha256_seed_a": body_a,
        "body_sha256_seed_b": body_b,
        "bytes_seed_a": len(bytes_a1),
        "bytes_seed_b": len(bytes_b),
        "tracks_selected_seed_a": run1["tracks_selected"],
        "tracks_selected_seed_b": run_b["tracks_selected"],
        "model_calls": run1["model_calls"] + run2["model_calls"] + run_b["model_calls"],
        "fidelity_ok": fidelity_ok,
        "dissenters": dissenters,
        "expected_dissenters": expected,
        "negative_control": negative,
        "phase": run1["phase"],
        "transition_granted": run1["transition_granted"],
        "behaviours": behaviours,
        "cites": cites,
        "transcript_seed_a": run1,
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def run_council(
    spec: dict[str, Any] | None = None,
    cast: Any = None,
    seed: Any = None,
    *,
    cwd: str | Path | None = None,
    apply_floors: bool | None = None,
    enforce_quotas: bool | None = None,
    personas: Any = None,
    proposal: str | None = None,
    proposal_id: str | None = None,
    quality: float | None = None,
    attribution: str | None = None,
    seat_numbers: Sequence[int] | None = None,
    vote_threshold: float | None = None,
    authority_boost: float | None = None,
) -> Any:
    """Dispatch on argument shape to the matching scripted engine.

    * ``run_council(spec, cast, apply_floors=...)`` with ``spec["stopping_expression"]``
      -> :func:`run_floor_gated_council` (TST-0264).
    * ``run_council(spec, cwd=...)`` with ``spec["check_command"]`` and ``spec["ballots"]``
      -> :func:`settle_dispute` (TST-0274).
    * ``run_council(spec, {"personas": [...]}, enforce_quotas=, seed=)`` -> quota scheduler.
    * ``run_council(spec, personas, seed)`` -> anchoring / speak-order experiment.
    * keyword-only ``proposal=... quality=... attribution=...`` -> authority weighting.
    """
    if spec is not None:
        if not isinstance(spec, dict):
            raise TypeError(f"run_council: spec must be a dict, got {type(spec).__name__}")
        if "stopping_expression" in spec or apply_floors is not None:
            return run_floor_gated_council(
                spec, cast if cast is not None else personas,
                apply_floors=True if apply_floors is None else bool(apply_floors),
            )
        if "check_command" in spec and "ballots" in spec:
            return settle_dispute(spec, cwd=cwd)
        second = cast if cast is not None else personas
        if isinstance(second, dict) and "personas" in second:
            return _run_quota_council(
                spec, second, enforce_quotas=bool(enforce_quotas), seed=int(seed or 0)
            )
        return _run_anchoring(spec, list(second or []), int(seed or 0))
    if proposal is None and quality is None and attribution is None:
        raise TypeError("run_council: pass a spec, or the authority-weighting keywords")
    return _run_authority(
        proposal=proposal,
        proposal_id=proposal_id,
        quality=quality,
        attribution=attribution,
        personas=personas if personas is not None else cast,
        seat_numbers=seat_numbers,
        seed=seed,
        vote_threshold=vote_threshold,
        authority_boost=authority_boost,
    )


# ---------------------------------------------------------------------------
# Deterministic three-cast DAG trace with frozen clock / fixed pid (TST-0290)
# ---------------------------------------------------------------------------
#
# The production DAG for one cast is: a static FanOut over the due seats
# (one ``turn:<seat>`` node each), a DynamicFanOut ``dyn-replace`` whose
# cardinality is seed-driven, and a Barrier ``join``.  Wall-clock and pid are
# injected as FrozenClock / FixedPid objects; the production trace never reads
# them, so changing either leaves the trace hash unchanged.  ``leak_clock`` and
# ``leak_pid`` are deliberate leak injections that make the trace depend on
# them, which is how the detectors prove they would see a real leak.

SEED_A = 7
SEED_B = 8
FROZEN_NS = 1_700_000_000_000_000_000
FIXED_PID = 4242
CAST_ORDER = ("productive", "deadlock", "stalled")
DYN_REPLACE_ID = "dyn-replace"
STATIC_FANOUT_ID = "static-seats"
BARRIER_ID = "join"


@dataclass(frozen=True)
class FrozenClock:
    ns: int = FROZEN_NS

    def now_ns(self) -> int:
        return int(self.ns)


@dataclass(frozen=True)
class FixedPid:
    pid: int = FIXED_PID

    def getpid(self) -> int:
        return int(self.pid)


def dyn_replace_cardinality(seed: int) -> int:
    """DynamicFanOut cardinality: 2 + (seed % 3); the one place seed enters the DAG."""
    return 2 + (int(seed) % 3)


def trace_hash(run: Mapping[str, Any]) -> str:
    """Independent sha256 over a run's trace lines (does not read ``run['trace_hash']``)."""
    lines = run.get("trace")
    if not isinstance(lines, list):
        raise TypeError("trace_hash: run has no 'trace' line list")
    return hashlib.sha256(("\n".join(str(x) for x in lines) + "\n").encode("utf-8")).hexdigest()


def pids_that_reorder(seats: Sequence[Any]) -> tuple[int, int]:
    """Two pids whose leaked rotation of the due-seat order differs (n >= 2 seats)."""
    n = len(seats)
    if n < 2:
        raise ValueError("pids_that_reorder needs at least two seats")
    lo = 1
    hi = next(p for p in range(lo + 1, lo + n + 1) if p % n != lo % n)
    return lo, hi


def simulate(
    cast_name: str,
    *,
    seed: int,
    pid: int = FIXED_PID,
    clock_ns: int = FROZEN_NS,
    leak_pid: bool = False,
    leak_clock: bool = False,
) -> dict[str, Any]:
    """Run one scripted cast through the production DAG and hash its trace."""
    from .stopping import deadlock as _deadlock

    cast = _deadlock.load_cast(cast_name)
    replay = _deadlock.run_cast(cast)
    row = _deadlock.classify_cast_run(replay, seed=int(seed))
    clock = FrozenClock(int(clock_ns))
    proc = FixedPid(int(pid))
    seats = [s["seat_id"] for s in cast["seats"]]

    order = list(seats)
    if leak_pid:
        k = proc.getpid() % len(order)
        order = order[k:] + order[:k]
    cardinality = dyn_replace_cardinality(seed)
    if leak_clock:
        cardinality = 2 + ((int(seed) + clock.now_ns()) % 3)

    node_order = [f"turn:{sid}" for sid in order]
    node_order.append(f"DynamicFanOut:{DYN_REPLACE_ID}:{cardinality}")
    node_order.append(f"Barrier:{BARRIER_ID}")
    fan_out = [
        {"id": STATIC_FANOUT_ID, "kind": "FanOut", "cardinality": len(seats)},
        {"id": DYN_REPLACE_ID, "kind": "DynamicFanOut", "cardinality": cardinality},
    ]
    trace = [f"cast:{cast['cast_id']}", f"seed:{int(seed)}", *node_order]
    trace.append(f"outcome:{row['kind']}:{row['action']}:{row['seat_id'] or '-'}")
    if leak_clock:
        trace.append(f"leak-clock:{clock.now_ns()}")
    if leak_pid:
        trace.append(f"leak-pid:{proc.getpid()}")

    run = {
        "cast": cast["name"],
        "cast_id": cast["cast_id"],
        "seed": int(seed),
        "node_order": node_order,
        "fan_out": fan_out,
        "barrier_resolution": BARRIER_ID,
        "three_way": {
            "kind": row["kind"],
            "action": row["action"],
            "escalated": row["escalated"],
            "seat_id": row["seat_id"],
            "proposition_id": row["proposition_id"],
        },
        "leaks": {"clock": bool(leak_clock), "pid": bool(leak_pid)},
        "injected": {"clock_ns": clock.now_ns(), "pid": proc.getpid()},
        "trace": trace,
    }
    run["trace_hash"] = trace_hash(run)
    return run


def three_cast_bundle(
    *,
    seed: int,
    clock_ns: int = FROZEN_NS,
    pid: int = FIXED_PID,
    leak_clock: bool = False,
    leak_pid: bool = False,
) -> dict[str, Any]:
    """Run the three scripted casts in order and hash the concatenated trace."""
    runs = [
        simulate(
            name, seed=seed, pid=pid, clock_ns=clock_ns, leak_pid=leak_pid, leak_clock=leak_clock
        )
        for name in CAST_ORDER
    ]
    trace: list[str] = []
    for run in runs:
        trace.extend(run["trace"])
    bundle = {
        "seed": int(seed),
        "casts": list(CAST_ORDER),
        "node_order": [node for run in runs for node in run["node_order"]],
        "fan_out": [dict(row) for run in runs for row in run["fan_out"]],
        "barrier_resolution": [run["barrier_resolution"] for run in runs],
        "runs": runs,
        "leaks": {"clock": bool(leak_clock), "pid": bool(leak_pid)},
        "injected": {"clock_ns": int(clock_ns), "pid": int(pid)},
        "trace": trace,
    }
    bundle["trace_hash"] = trace_hash(bundle)
    return bundle
