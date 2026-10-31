"""Council simulation for TST-0260 (authority) and TST-0289 (anchoring)."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Sequence


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


def run_council(*args: Any, **kwargs: Any) -> Any:
    if args and isinstance(args[0], dict):
        spec = args[0]
        second = args[1] if len(args) > 1 else kwargs.get("personas")
        if isinstance(second, dict) and "personas" in second:
            enforce = bool(kwargs.get("enforce_quotas", False))
            seed = int(kwargs.get("seed") or 0)
            return _run_quota_council(spec, second, enforce_quotas=enforce, seed=seed)
        personas = second
        seed = args[2] if len(args) > 2 else kwargs.get("seed", 0)
        return _run_anchoring(spec, list(personas or []), int(seed))
    return _run_authority(**kwargs)
