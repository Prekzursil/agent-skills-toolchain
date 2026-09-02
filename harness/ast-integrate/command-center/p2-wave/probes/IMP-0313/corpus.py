"""Deterministic 200-turn labelled transcript for IMP-0313.

Gold edges are recorded from generation intent, not by running the extractor.
Every turn carries a poisoned `_label` field the extractor must ignore.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
TRANSCRIPT = FIX / "transcript_200.json"
GOLD = FIX / "gold_edges.json"

SPEAKERS = ("alice", "bob", "carol", "dave", "eve")

CLAIM_BODIES = [
    "The kernel owns the event loop.",
    "Every topology must record a turn event.",
    "Direct writes to the artifact store are forbidden.",
    "Dissent must survive synthesis verbatim or by resolvable id.",
    "A round cannot advance without a recorded obligation.",
    "Stopping before an independent brief exists is illegal.",
    "Votes are derived views of the append-only log.",
    "Claim nodes must be typed, not free text blobs.",
    "SUPPORTS, ATTACKS and REBUTS are the only legal edge types.",
    "An edge without a resolvable turn id is invalid.",
    "The charter lists required outputs including the argument graph.",
    "Empty sections do not satisfy completeness.",
    "Replacement is an escalation, not a silent drop.",
    "Owner intervention is requested only after protocol change fails.",
    "Slow progress is not a deadlock.",
    "A converging run must not be escalated.",
    "NO-DECISION is a first-class outcome kind.",
    "CONDITIONAL outcomes require their condition fields.",
    "PROOF-OF-IMPOSSIBILITY is not coerced into FAIL.",
    "Downstream consumers must not map NO-DECISION to FAIL.",
    "Minority reports are counted in and out of synthesis.",
    "A distinctive dissent string must remain recoverable.",
    "The extractor must not invent edges no turn supports.",
    "Precision and recall are reported separately.",
    "A single accuracy figure is not the contracted metric.",
    "Hand-labelled keys live in a file the extractor does not read.",
    "Turn identifiers are stable across pause and resume.",
    "Replay of the same log is byte-identical.",
    "Side state that survives process restart is a defect.",
    "Citation cycles that manufacture support must fire.",
    "Legitimate cross-references are not cycles.",
    "Option cards require mechanism, cost, risk and evidence.",
    "A random subset must not match promoted quality.",
    "The idea ledger is append-only.",
    "Unknowns remain first-class in the final artifact.",
    "Experiments are listed even when they fail.",
    "Calibration statements are not optional decoration.",
    "The synthesizer may not drop an unanswered obligation.",
    "Rebuttals target a claim, not a speaker.",
    "Attacks are directed edges, not unordered pairs.",
    "Support does not flow through an attack.",
    "A rebuttal of an attack is not automatic support of the original.",
    "Claim ids are assigned at introduction and never reused.",
    "Speakers may introduce at most one new claim per turn in this corpus.",
    "Relation turns cite claims that already exist.",
    "Distractor language uses support/attack/rebut without claim ids.",
    "Poison labels on turns are not extraction input.",
    "The event store is the source of derived views.",
    "Topologies plug into the kernel; they do not bypass it.",
    "Turn length limits are kernel-enforced.",
    "Response obligations are recorded before the next speaker.",
    "A brief that merely exists empty is not independent.",
    "Deadlock detection reports TPR and FPR separately.",
    "False-positive deadlock on slow convergence is a defect.",
    "The argument graph is a required charter output.",
    "Invented edges fail the precision control.",
    "Missed labelled edges fail the recall control.",
    "Unresolvable turn ids fail validation, not scoring.",
    "Grounding is optional; turn resolution is not.",
    "Claim text is taken from the introducing turn.",
    "Subsequent mentions do not rewrite claim identity.",
    "Multiple relations may appear in one turn.",
    "Self-loops are not legal edges.",
    "c999 is reserved for poison labels.",
    "c998 is reserved for poison labels.",
    "Gold matching uses source, target, relation and turn_id.",
    "The corpus seed is 313.",
    "Two hundred turns is the contracted labelled size.",
    "At least fifty gold edges are required for a non-vacuous key.",
    "Discussion padding must not emit edges.",
]


DISTRACTORS = [
    "I support taking a break after this round.",
    "The support vector in this diagram is orthogonal to the claim axis.",
    "Please rebut that later when we have numbers.",
    "This attacks a straw man, not a numbered claim.",
    "We should support the team without tagging a claim id.",
    "Attacks on the idea are welcome in ordinary language.",
    "SUPPORTS our morale, not a typed edge.",
    "I will rebut speculation off the record.",
    "No CLAIM identifiers belong in this status check.",
    "Noted. Moving the agenda along.",
    "The chair asks for a shorter turn.",
    "Coffee, then we continue.",
    "This is process, not an argument edge.",
    "Silence is not dissent.",
    "A nod is not SUPPORTS.",
]


def _poison(turn_id: str) -> dict:
    return {
        "poison": True,
        "note": "extractor must ignore this field",
        "edges": [
            {
                "source": "c999",
                "target": "c998",
                "relation": "SUPPORTS",
                "turn_id": turn_id,
            }
        ],
    }


def _turn(turn_id: str, speaker: str, text: str, **extra: object) -> dict:
    row = {
        "turn_id": turn_id,
        "speaker": speaker,
        "text": text,
        "_label": _poison(turn_id),
    }
    row.update(extra)
    return row


def _gold(src: str, tgt: str, rel: str, turn_id: str) -> dict:
    return {
        "source": src,
        "target": tgt,
        "relation": rel,
        "turn_id": turn_id,
        "edge_type": rel,
    }


def build_corpus(n: int = 200, seed: int = 313) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    turns: list[dict] = []
    gold: list[dict] = []
    n_claims = 40
    claim_ids = [f"c{i:03d}" for i in range(1, n_claims + 1)]

    def next_tid() -> str:
        return f"t{len(turns) + 1:03d}"

    def speaker() -> str:
        return SPEAKERS[len(turns) % len(SPEAKERS)]

    for i, cid in enumerate(claim_ids):
        body = CLAIM_BODIES[i % len(CLAIM_BODIES)]
        turns.append(_turn(next_tid(), speaker(), f"CLAIM-{cid}: {body}"))

    def pair(offset: int) -> tuple[str, str]:
        src = claim_ids[offset % n_claims]
        tgt = claim_ids[(offset + 1 + (offset % 3)) % n_claims]
        if src == tgt:
            tgt = claim_ids[(offset + 2) % n_claims]
        return src, tgt

    support_forms = (
        lambda s, t, r: f"CLAIM-{s} SUPPORTS CLAIM-{t}: {r}",
        lambda s, t, r: f"CLAIM-{s} supports CLAIM-{t} because {r}",
        lambda s, t, r: f"I offer CLAIM-{s} in support of CLAIM-{t}. {r}",
    )
    for i in range(50):
        src, tgt = pair(i)
        reason = CLAIM_BODIES[(i + 7) % len(CLAIM_BODIES)]
        text = support_forms[i % 3](src, tgt, reason)
        turn_id = next_tid()
        turns.append(_turn(turn_id, speaker(), text))
        gold.append(_gold(src, tgt, "SUPPORTS", turn_id))

    attack_forms = (
        lambda s, t, r: f"CLAIM-{s} ATTACKS CLAIM-{t}: {r}",
        lambda s, t, r: f"CLAIM-{s} is incompatible with CLAIM-{t}. {r}",
        lambda s, t, r: f"CLAIM-{s} undermines CLAIM-{t}. {r}",
    )
    for i in range(40):
        src, tgt = pair(i + 17)
        reason = CLAIM_BODIES[(i + 11) % len(CLAIM_BODIES)]
        text = attack_forms[i % 3](src, tgt, reason)
        turn_id = next_tid()
        turns.append(_turn(turn_id, speaker(), text))
        gold.append(_gold(src, tgt, "ATTACKS", turn_id))

    rebut_forms = (
        lambda s, t, r: f"CLAIM-{s} REBUTS CLAIM-{t}: {r}",
        lambda s, t, r: f"CLAIM-{s} rebuts CLAIM-{t} by showing {r}",
        lambda s, t, r: f"CLAIM-{s} rebuts the attack in CLAIM-{t}. {r}",
    )
    for i in range(30):
        src, tgt = pair(i + 29)
        reason = CLAIM_BODIES[(i + 19) % len(CLAIM_BODIES)]
        text = rebut_forms[i % 3](src, tgt, reason)
        turn_id = next_tid()
        turns.append(_turn(turn_id, speaker(), text))
        gold.append(_gold(src, tgt, "REBUTS", turn_id))

    for i in range(5):
        s1, t1 = pair(i + 5)
        s2, t2 = pair(i + 9)
        turn_id = next_tid()
        text = (
            f"CLAIM-{s1} SUPPORTS CLAIM-{t1}. "
            f"CLAIM-{s2} ATTACKS CLAIM-{t2}."
        )
        turns.append(_turn(turn_id, speaker(), text))
        gold.append(_gold(s1, t1, "SUPPORTS", turn_id))
        gold.append(_gold(s2, t2, "ATTACKS", turn_id))

    incomplete = [
        "ATTACKS CLAIM-c001 but names no source claim.",
        "SUPPORTS the motion without claim identifiers.",
        "c014 -> c007 has an arrow and no relation type.",
        "CLAIM-c003 stands alone with no edge.",
        "I support CLAIM-c004 in general, without a target id.",
        "Please ATTACKS later.",
        "REBUTS nothing in particular.",
        "CLAIM-c010 SUPPORTS our schedule, not a claim.",
    ]
    for text in incomplete:
        turns.append(_turn(next_tid(), speaker(), text))

    pad_i = 0
    while len(turns) < n:
        if pad_i % 2 == 0:
            text = DISTRACTORS[pad_i % len(DISTRACTORS)]
        else:
            text = (
                f"{rng.choice(SPEAKERS)} notes the round is still open. "
                f"{DISTRACTORS[(pad_i + 3) % len(DISTRACTORS)]}"
            )
        turns.append(_turn(next_tid(), speaker(), text))
        pad_i += 1

    if len(turns) != n:
        raise RuntimeError(f"generated {len(turns)} turns, want {n}")
    if len(gold) < 50:
        raise RuntimeError(f"gold too small: {len(gold)}")
    return turns, gold


def ensure_fixtures(n: int = 200, seed: int = 313) -> tuple[Path, Path]:
    turns, gold = build_corpus(n=n, seed=seed)
    FIX.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT.write_text(
        json.dumps({"n_turns": len(turns), "turns": turns}, indent=2) + "\n",
        encoding="utf-8",
    )
    GOLD.write_text(
        json.dumps({"n_gold": len(gold), "edges": gold}, indent=2) + "\n",
        encoding="utf-8",
    )
    return TRANSCRIPT, GOLD


def load_fixtures() -> tuple[list[dict], list[dict]]:
    if not TRANSCRIPT.is_file() or not GOLD.is_file():
        ensure_fixtures()
    turns_doc = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    return list(turns_doc["turns"]), list(gold_doc["edges"])


if __name__ == "__main__":
    t_path, g_path = ensure_fixtures()
    turns, gold = load_fixtures()
    print(f"wrote {t_path} turns={len(turns)}")
    print(f"wrote {g_path} gold_edges={len(gold)}")
