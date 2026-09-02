"""Live ADV-0094 council: CNL-0047 quota scheduler plus IMP-0299 engagement.

Token share, surviving-idea share, and synthesis attribution are three
different meters. Influence is a leave-one-out outcome delta, not airtime.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CNL_DIR = REPO / "command-center" / "p2-wave" / "probes" / "CNL-0047"
TOOLS = REPO / "tools"
ART_REL = "command-center/adversarial/ADV-0094-participant-dominance-airtime.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
UNIT_ID = "ADV-0094"

CATALOG_SENTINEL = (
    "SUCCESS:ADV-0094 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0094 <reason>."
)
QUESTION = (
    "Can one participant capture the deliberation - by volume, by speaking "
    "first, or by framing - and does the runtime's speaking-quota and "
    "minimum-engagement machinery actually redistribute influence?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0094/probe1_shares.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0094/probe2_loo.py"
)

sys.path.insert(0, str(CNL_DIR))
sys.path.insert(0, str(TOOLS))

from scheduler import (  # noqa: E402
    HALT,
    SPEAK,
    THROTTLE,
    YIELD,
    Scheduler,
    clone_seats,
)
from council.budget.engagement import (  # noqa: E402
    EngagementPolicy,
    EngagementTracker,
    score_text,
)

TURN_LENGTH = 20
QUOTA_ON = 40
QUOTA_OFF = 10_000
CAPTURE = 0.50
BALANCED_MAX = 0.40
LOO_DELTA_HIGH = 0.50


def claim(idea_id: str) -> str:
    return (
        f"Claim: {idea_id} is the binding recommendation because "
        f"scheduler.py remaining() and next_offer in CNL-0047 cap tokens "
        f"to min(turn_length, remaining quota) as spec.md requires."
    )


@dataclass
class ScriptedSpeaker:
    utterances: list[dict[str, Any]]
    i: int = 0
    last: dict[str, Any] | None = None
    emitted: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, cap: int) -> dict[str, Any]:
        self.last = None
        if self.i >= len(self.utterances) or int(cap) <= 0:
            return {"act": YIELD, "tokens": 0}
        u = dict(self.utterances[self.i])
        need = int(u["tokens"])
        used = min(need, int(cap))
        leftover = need - used
        if leftover > 0:
            self.utterances[self.i] = {**u, "tokens": leftover}
        else:
            self.i += 1
        rec = {
            "idea_id": u["idea_id"],
            "text": u["text"],
            "tokens": used,
            "kind": u.get("kind", "claim"),
        }
        self.last = rec
        self.emitted.append(rec)
        return {"act": SPEAK, "tokens": used}


def _utt(idea_id: str, *, kind: str = "claim", tokens: int = TURN_LENGTH) -> dict:
    if kind == "ack":
        return {"idea_id": idea_id, "text": idea_id, "tokens": 1, "kind": kind}
    return {
        "idea_id": idea_id,
        "text": claim(idea_id),
        "tokens": tokens,
        "kind": kind,
    }


def flood_rows(quota: int) -> list[dict]:
    return [
        {"id": "loud", "speaking_right": True, "quota_tokens": quota},
        {"id": "peer1", "speaking_right": True, "quota_tokens": quota},
        {"id": "peer2", "speaking_right": True, "quota_tokens": quota},
        {"id": "quiet", "speaking_right": True, "quota_tokens": quota},
    ]


def balanced_rows(quota: int) -> list[dict]:
    return [
        {"id": f"peer{i}", "speaking_right": True, "quota_tokens": quota}
        for i in range(1, 5)
    ]


def speakers_flood() -> dict[str, ScriptedSpeaker]:
    loud = [_utt(f"vol.{i:02d}") for i in range(1, 13)]
    return {
        "loud": ScriptedSpeaker(loud),
        "peer1": ScriptedSpeaker([_utt("p1.one"), _utt("p1.two")]),
        "peer2": ScriptedSpeaker([_utt("p2.one"), _utt("p2.two")]),
        "quiet": ScriptedSpeaker(
            [_utt("ok", kind="ack"), _utt("ack", kind="ack"), _utt("thanks", kind="ack")]
        ),
    }


def speakers_restate() -> dict[str, ScriptedSpeaker]:
    loud = [_utt("vol.capture") for _ in range(12)]
    return {
        "loud": ScriptedSpeaker(loud),
        "peer1": ScriptedSpeaker([_utt("p1.one"), _utt("p1.two")]),
        "peer2": ScriptedSpeaker([_utt("p2.one"), _utt("p2.two")]),
        "quiet": ScriptedSpeaker(
            [_utt("ok", kind="ack"), _utt("ack", kind="ack"), _utt("thanks", kind="ack")]
        ),
    }


def speakers_balanced() -> dict[str, ScriptedSpeaker]:
    return {
        f"peer{i}": ScriptedSpeaker([_utt("shared.one"), _utt("shared.two")])
        for i in range(1, 5)
    }


def pick_recommendation(
    unique_by_author: dict[str, list[str]],
    first_idea_by_author: dict[str, str],
) -> dict[str, Any]:
    counts = {a: len(ids) for a, ids in unique_by_author.items() if ids}
    if not counts:
        return {"idea_id": None, "author": None, "tied_authors": [], "top_unique": 0}
    top = max(counts.values())
    tied = sorted(a for a, n in counts.items() if n == top)
    candidates = [(first_idea_by_author[a], a) for a in tied if a in first_idea_by_author]
    idea_id, author = min(candidates, key=lambda x: (x[0], x[1]))
    return {
        "idea_id": idea_id,
        "author": author,
        "tied_authors": tied,
        "top_unique": top,
    }


def token_weighted_rec(tokens_by_idea: dict[str, int]) -> dict[str, Any]:
    if not tokens_by_idea:
        return {"idea_id": None, "tokens": 0}
    idea_id, n = max(tokens_by_idea.items(), key=lambda kv: (kv[1], kv[0]))
    return {"idea_id": idea_id, "tokens": n}


def _shares(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values()) or 1.0
    return {k: (v / total) for k, v in values.items()}


def run_council(
    *,
    name: str,
    rows: list[dict],
    speakers_factory: Callable[[], dict[str, ScriptedSpeaker]],
    drop: str | None = None,
    max_steps: int = 96,
) -> dict[str, Any]:
    seats_spec = [r for r in rows if r["id"] != drop]
    speakers = speakers_factory()
    if drop:
        speakers.pop(drop, None)
    sched = Scheduler(
        seats=clone_seats(seats_spec),
        turn_length_tokens=TURN_LENGTH,
    )
    policy = EngagementPolicy()
    seat_of = {r["id"]: r["id"] for r in seats_spec}
    tracker = EngagementTracker(policy, seat_of)
    sched.run(speakers, max_steps=max_steps)

    emit_i = {sid: 0 for sid in speakers}
    first_speaker = None
    turns: list[dict[str, Any]] = []
    for offer in sched.log:
        rec: dict[str, Any] = {
            "kind": offer.kind,
            "seat_id": offer.seat_id,
            "allowed_tokens": offer.allowed_tokens,
            "tokens_used": offer.tokens_used,
            "reason": offer.reason,
        }
        if offer.kind == SPEAK and offer.seat_id:
            if first_speaker is None:
                first_speaker = offer.seat_id
            uttered = speakers[offer.seat_id].emitted[emit_i[offer.seat_id]]
            emit_i[offer.seat_id] += 1
            scored = score_text(str(uttered.get("text") or ""))
            tr = tracker.record_turn(offer.seat_id, str(uttered.get("text") or ""))
            rec.update(
                {
                    "idea_id": uttered.get("idea_id"),
                    "text": uttered.get("text"),
                    "utterance_kind": uttered.get("kind"),
                    "content_units": int(scored["content_units"]),
                    "accepted": bool(tr.accepted),
                    "content_units_added": int(tr.content_units_added),
                }
            )
        turns.append(rec)

    spoken = sched.spoken()
    tokens_by_idea: dict[str, int] = {}
    unique_by_author: dict[str, list[str]] = {s.id: [] for s in sched.seats}
    first_idea_by_author: dict[str, str] = {}
    content_units = {s.id: 0 for s in sched.seats}
    messages = {s.id: 0 for s in sched.seats}
    accepted_claims = 0
    for t in turns:
        sid = t.get("seat_id")
        if t["kind"] != SPEAK or not sid:
            continue
        messages[sid] = messages.get(sid, 0) + 1
        idea = t.get("idea_id")
        if idea:
            tokens_by_idea[idea] = tokens_by_idea.get(idea, 0) + int(
                t.get("tokens_used") or 0
            )
        if t.get("accepted") and int(t.get("content_units_added") or 0) > 0 and idea:
            accepted_claims += 1
            content_units[sid] = content_units.get(sid, 0) + int(
                t["content_units_added"]
            )
            if idea not in unique_by_author[sid]:
                unique_by_author[sid].append(idea)
            first_idea_by_author.setdefault(sid, idea)

    census = tracker.census()
    unique_set = sorted({i for ids in unique_by_author.values() for i in ids})
    rec = pick_recommendation(unique_by_author, first_idea_by_author)
    naive = token_weighted_rec(tokens_by_idea)
    token_share = _shares({k: float(v) for k, v in spoken.items()})
    idea_share = _shares({k: float(len(v)) for k, v in unique_by_author.items()})
    attr_share = dict(idea_share)
    loudest_tokens = max(token_share, key=token_share.get) if token_share else None
    loudest_ideas = max(idea_share, key=idea_share.get) if idea_share else None
    return {
        "name": name,
        "drop": drop,
        "first_speaker": first_speaker,
        "spoken_tokens": spoken,
        "token_share": token_share,
        "idea_share": idea_share,
        "attribution_share": attr_share,
        "unique_by_author": unique_by_author,
        "unique_set": unique_set,
        "first_idea_by_author": first_idea_by_author,
        "content_units": content_units,
        "messages": messages,
        "recommendation": rec,
        "token_weighted_recommendation": naive,
        "throttles": sched.throttles(),
        "yields": sched.yields(),
        "census": census,
        "accepted_claims": accepted_claims,
        "n_turns": len(turns),
        "n_speak": sum(1 for t in turns if t["kind"] == SPEAK),
        "quota": seats_spec[0]["quota_tokens"] if seats_spec else None,
        "engagement_max_content_units": policy.max_content_units,
        "loudest_token_seat": loudest_tokens,
        "loudest_idea_seat": loudest_ideas,
        "scheduler": "command-center/p2-wave/probes/CNL-0047/scheduler.py",
        "engagement": "tools/council/budget/engagement.py",
    }


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def loo_report(base: dict[str, Any], removed: dict[str, Any]) -> dict[str, Any]:
    jac = jaccard(base["unique_set"], removed["unique_set"])
    rec_changed = (
        base["recommendation"]["idea_id"] != removed["recommendation"]["idea_id"]
    )
    return {
        "removed": removed["drop"],
        "base_rec": base["recommendation"]["idea_id"],
        "loo_rec": removed["recommendation"]["idea_id"],
        "rec_changed": rec_changed,
        "jaccard": jac,
        "outcome_delta": 1.0 - jac,
        "base_unique": base["unique_set"],
        "loo_unique": removed["unique_set"],
    }


def fixture_runs() -> dict[str, Any]:
    return {
        "flood_off": run_council(
            name="flood-quota-off",
            rows=flood_rows(QUOTA_OFF),
            speakers_factory=speakers_flood,
        ),
        "flood_on": run_council(
            name="flood-quota-on",
            rows=flood_rows(QUOTA_ON),
            speakers_factory=speakers_flood,
        ),
        "restate_off": run_council(
            name="restate-quota-off",
            rows=flood_rows(QUOTA_OFF),
            speakers_factory=speakers_restate,
        ),
        "restate_on": run_council(
            name="restate-quota-on",
            rows=flood_rows(QUOTA_ON),
            speakers_factory=speakers_restate,
        ),
        "balanced": run_council(
            name="balanced",
            rows=balanced_rows(QUOTA_ON),
            speakers_factory=speakers_balanced,
        ),
    }


def loo_runs() -> dict[str, Any]:
    fx = fixture_runs()
    flood_off_loo = run_council(
        name="flood-quota-off-drop-loud",
        rows=flood_rows(QUOTA_OFF),
        speakers_factory=speakers_flood,
        drop="loud",
    )
    flood_on_loo = run_council(
        name="flood-quota-on-drop-loud",
        rows=flood_rows(QUOTA_ON),
        speakers_factory=speakers_flood,
        drop="loud",
    )
    balanced_loos = []
    for seat in ("peer1", "peer2", "peer3", "peer4"):
        gone = run_council(
            name=f"balanced-drop-{seat}",
            rows=balanced_rows(QUOTA_ON),
            speakers_factory=speakers_balanced,
            drop=seat,
        )
        balanced_loos.append(loo_report(fx["balanced"], gone))
    return {
        "flood_off": loo_report(fx["flood_off"], flood_off_loo),
        "flood_on": loo_report(fx["flood_on"], flood_on_loo),
        "balanced": balanced_loos,
        "fixtures": fx,
        "flood_off_dropped": flood_off_loo,
        "flood_on_dropped": flood_on_loo,
    }


def share_invariants(fx: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    off, on, rest, bal = (
        fx["flood_off"],
        fx["flood_on"],
        fx["restate_off"],
        fx["balanced"],
    )
    if off["token_share"].get("loud", 0) < CAPTURE:
        fails.append(
            f"uncapped loud token share {off['token_share'].get('loud')} < {CAPTURE}"
        )
    if on["token_share"].get("loud", 0) >= CAPTURE:
        fails.append(
            f"capped loud token share {on['token_share'].get('loud')} still >= {CAPTURE}"
        )
    if off["idea_share"].get("loud", 0) < CAPTURE:
        fails.append(
            f"uncapped loud idea share {off['idea_share'].get('loud')} < {CAPTURE}"
        )
    if on["idea_share"].get("loud", 0) >= CAPTURE:
        fails.append(
            f"capped loud idea share {on['idea_share'].get('loud')} still >= {CAPTURE}"
        )
    if off["first_speaker"] != "loud" or on["first_speaker"] != "loud":
        fails.append(
            f"first speaker off={off['first_speaker']} on={on['first_speaker']}"
        )
    if max(bal["token_share"].values()) >= BALANCED_MAX:
        fails.append(f"balanced token share max {max(bal['token_share'].values())}")
    if rest["token_weighted_recommendation"]["idea_id"] != "vol.capture":
        fails.append("restate token-weighted rec is not vol.capture")
    if rest["recommendation"]["idea_id"] == "vol.capture" and rest["idea_share"].get(
        "loud", 0
    ) >= CAPTURE:
        fails.append(
            "restate unique-idea rec collapsed to volume; uniqueness gate failed"
        )
    quiet = off["census"].get("quiet") or {}
    if int(quiet.get("content_units") or 0) != 0:
        fails.append(f"quiet acks scored content_units={quiet.get('content_units')}")
    if quiet.get("meets_floor") is True:
        fails.append("quiet acks met engagement floor")
    if off["messages"].get("quiet", 0) < 1:
        fails.append("quiet posted no messages; message-count control has no bad state")
    ack = score_text("ok")
    claim_scored = score_text(claim("vol.01"))
    if int(ack["content_units"]) != 0:
        fails.append(f"ack scored {ack['content_units']}")
    if int(claim_scored["content_units"]) < 1:
        fails.append("live claim text scored 0 content units")
    return fails


def loo_invariants(loo: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if not loo["flood_off"]["rec_changed"]:
        fails.append("uncapped leave-one-out did not change the recommendation")
    if loo["flood_off"]["outcome_delta"] < LOO_DELTA_HIGH:
        fails.append(f"uncapped outcome delta {loo['flood_off']['outcome_delta']}")
    if loo["flood_on"]["rec_changed"]:
        fails.append(
            "capped leave-one-out changed the recommendation; quota did not pin the outcome"
        )
    for row in loo["balanced"]:
        if row["rec_changed"]:
            fails.append(f"balanced removal of {row['removed']} changed rec")
        if row["outcome_delta"] > 0.2:
            fails.append(f"balanced {row['removed']} delta {row['outcome_delta']}")
    return fails


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": run["name"],
        "drop": run["drop"],
        "first_speaker": run["first_speaker"],
        "spoken_tokens": run["spoken_tokens"],
        "token_share": run["token_share"],
        "idea_share": run["idea_share"],
        "attribution_share": run["attribution_share"],
        "unique_by_author": run["unique_by_author"],
        "unique_set": run["unique_set"],
        "recommendation": run["recommendation"],
        "token_weighted_recommendation": run["token_weighted_recommendation"],
        "throttles": run["throttles"],
        "content_units": run["content_units"],
        "messages": run["messages"],
        "census": {
            sid: {
                "content_units": row.get("content_units"),
                "message_count": row.get("message_count"),
                "meets_floor": row.get("meets_floor"),
            }
            for sid, row in (run.get("census") or {}).items()
        },
        "quota": run["quota"],
        "engagement_max_content_units": run["engagement_max_content_units"],
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
