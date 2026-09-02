"""Evidence retrieval under context overflow (IMP-0349).

Question: on a council whose prompt overflows the token budget, does a
participant still cite evidence that was introduced in early rounds?  Measured
as the *early-round citation rate* over the late turns, with retrieval on and
off, on the same planted council.

Everything here is deterministic and local:

* tokenizer: whitespace split (no vendor BPE);
* the participant is a *citer bound to prompt contents*: it cites an early
  anchor only when that anchor's marker ``[ANCHOR:<id>]`` is present in the
  prompt it was actually handed (:func:`cite_early_anchors`);
* the assembler is a local budgeted one (IMP-0338 ``context.py`` is not
  claimed): protected header first, then retrieved anchors, then the evidence
  bodies that survived eviction, then the most recent transcript that fits;
* eviction: the oldest evidence *rounds* leave the prompt first; the
  transcript is trimmed newest-first after that.

Retrieval scores the evicted anchors against the turn's query tags and puts
the best-scoring ones back within the remaining budget.  With retrieval off
the late turns never see an early anchor marker again, so the rate collapses
to zero on the planted council -- that is the negative control.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIX = REPO / "command-center" / "p2-wave" / "probes" / "IMP-0349" / "fixtures" / "overflow_council.json"

TOKENIZER = "whitespace-split"
CITER = "marker-in-prompt"
TAG_WEIGHT = 10.0
BODY_WEIGHT = 1.0


def count_tokens(text: str) -> int:
    """Whitespace tokenizer: one token per non-empty run of non-space chars."""
    return len((text or "").split())


def marker(anchor_id: str) -> str:
    return f"[ANCHOR:{anchor_id}]"


# --------------------------------------------------------------------------- #
# council model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Anchor:
    id: str
    body: str
    round_introduced: int
    tags: tuple[str, ...] = ()

    def tokens(self) -> int:
        return count_tokens(self.body)

    def body_words(self) -> set[str]:
        return {w.lower() for w in self.body.split() if not w.startswith("[ANCHOR:")}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "body": self.body,
            "round_introduced": self.round_introduced,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, rec: Mapping[str, Any]) -> "Anchor":
        return cls(
            id=str(rec["id"]),
            body=str(rec.get("body") or ""),
            round_introduced=int(rec.get("round_introduced") or 1),
            tags=tuple(str(t) for t in (rec.get("tags") or ())),
        )


@dataclass(frozen=True)
class TurnSpec:
    round: int
    participant_id: str
    role: str
    query_tags: tuple[str, ...]
    introduced_anchor_ids: tuple[str, ...]
    utterance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "participant_id": self.participant_id,
            "role": self.role,
            "query_tags": list(self.query_tags),
            "introduced_anchor_ids": list(self.introduced_anchor_ids),
            "utterance": self.utterance,
        }

    @classmethod
    def from_dict(cls, rec: Mapping[str, Any]) -> "TurnSpec":
        return cls(
            round=int(rec["round"]),
            participant_id=str(rec.get("participant_id") or "seat-0"),
            role=str(rec.get("role") or "participant"),
            query_tags=tuple(str(t) for t in (rec.get("query_tags") or ())),
            introduced_anchor_ids=tuple(str(a) for a in (rec.get("introduced_anchor_ids") or ())),
            utterance=str(rec.get("utterance") or ""),
        )


@dataclass
class Council:
    id: str
    anchors: list[Anchor]
    turns: list[TurnSpec]
    early_round_max: int = 2
    late_round_min: int = 7

    def anchor(self, anchor_id: str) -> Anchor:
        for a in self.anchors:
            if a.id == anchor_id:
                return a
        raise KeyError(anchor_id)

    def early_anchors(self) -> list[Anchor]:
        return [a for a in self.anchors if a.round_introduced <= self.early_round_max]

    def late_turn_specs(self) -> list[TurnSpec]:
        return [t for t in self.turns if t.round >= self.late_round_min]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "early_round_max": self.early_round_max,
            "late_round_min": self.late_round_min,
            "anchors": [a.to_dict() for a in self.anchors],
            "turns": [t.to_dict() for t in self.turns],
        }

    def fingerprint(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def from_dict(cls, rec: Mapping[str, Any]) -> "Council":
        anchors = [Anchor.from_dict(a) for a in (rec.get("anchors") or [])]
        turns = [TurnSpec.from_dict(t) for t in (rec.get("turns") or [])]
        turns.sort(key=lambda t: t.round)
        return cls(
            id=str(rec.get("id") or "council"),
            anchors=anchors,
            turns=turns,
            early_round_max=int(rec.get("early_round_max") or 2),
            late_round_min=int(rec.get("late_round_min") or 7),
        )


def _as_council(council: Any) -> Council:
    if isinstance(council, Council):
        return council
    if isinstance(council, Mapping):
        return Council.from_dict(council)
    raise TypeError(f"council must be a Council or a mapping, got {type(council).__name__}")


# --------------------------------------------------------------------------- #
# planted overflowing council
# --------------------------------------------------------------------------- #
ANCHOR_TOKENS = 24
OVERFLOW_COUNCIL_ID = "overflow-early-evidence-v1"


def _padded(base: str, slug: str, total: int = ANCHOR_TOKENS) -> str:
    """Pad ``base`` with inert tokens so every anchor body costs ``total`` tokens."""
    need = total - count_tokens(base)
    if need < 0:
        raise ValueError(f"anchor base for {slug} already exceeds {total} tokens")
    return " ".join([base, *(f"{slug}_t{i}" for i in range(need))]).strip()


def _utterance(round_no: int, n_tokens: int) -> str:
    return " ".join(f"r{round_no}_{i}" for i in range(n_tokens))


def build_overflow_council() -> Council:
    """Two early rounds introduce four 24-token anchors; the budget (48) fits two.

    Rounds 3-6 are 36-token filler turns that push the transcript far past the
    budget, so by the late rounds (7, 8) every early anchor has been evicted.
    Round 7 asks about freshness/dates (E-ALPHA), round 8 about cycle/citation
    (E-DELTA); only retrieval can put those bodies back in front of the citer.
    """
    anchors = [
        Anchor(
            "E-ALPHA",
            _padded(
                f"{marker('E-ALPHA')} freshness dates as-of dates revalidate at the source not the cache",
                "e-alpha",
            ),
            1,
            ("freshness", "dates"),
        ),
        Anchor(
            "E-BETA",
            _padded(
                f"{marker('E-BETA')} quorum seats binding votes require a live quorum of seated participants",
                "e-beta",
            ),
            1,
            ("quorum", "seats"),
        ),
        Anchor(
            "E-GAMMA",
            _padded(
                f"{marker('E-GAMMA')} eviction budget oldest evidence bodies leave the prompt first under budget",
                "e-gamma",
            ),
            2,
            ("eviction", "budget"),
        ),
        Anchor(
            "E-DELTA",
            _padded(
                f"{marker('E-DELTA')} cycle citation a citation cycle is A cites B cites A on the same claim",
                "e-delta",
            ),
            2,
            ("cycle", "citation"),
        ),
    ]
    plan: list[tuple[int, tuple[str, ...], tuple[str, ...], int]] = [
        (1, ("freshness", "quorum"), ("E-ALPHA", "E-BETA"), 8),
        (2, ("eviction", "cycle"), ("E-GAMMA", "E-DELTA"), 8),
        (3, ("filler",), (), 36),
        (4, ("filler",), (), 36),
        (5, ("filler",), (), 36),
        (6, ("filler",), (), 36),
        (7, ("freshness", "dates"), (), 10),
        (8, ("cycle", "citation"), (), 10),
    ]
    turns = [
        TurnSpec(
            round=r,
            participant_id="seat-0",
            role="skeptic",
            query_tags=tags,
            introduced_anchor_ids=intro,
            utterance=_utterance(r, n),
        )
        for r, tags, intro, n in plan
    ]
    return Council(OVERFLOW_COUNCIL_ID, anchors, turns, early_round_max=2, late_round_min=7)


def dump_fixture(path: Path | None = None) -> Path:
    """Write the planted council as the unit fixture (sorted keys, LF, trailing newline)."""
    out = Path(path) if path is not None else FIX
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(build_overflow_council().to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out


def load_fixture(path: Path | None = None) -> Council:
    src = Path(path) if path is not None else FIX
    return Council.from_dict(json.loads(src.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# citer, scoring, assembly
# --------------------------------------------------------------------------- #
def _anchor_id(a: Any) -> str:
    if isinstance(a, Mapping):
        return str(a.get("id") or "")
    return str(getattr(a, "id", "") or "")


def cite_early_anchors(prompt: str, early: Iterable[Any]) -> tuple[str, ...]:
    """Cite an early anchor only if its marker is in the prompt actually handed over.

    This is the whole measurement: the citer never reads the durable store, so
    an evicted anchor that retrieval did not bring back cannot be cited.
    """
    text = prompt or ""
    hits: list[str] = []
    for a in early:
        aid = _anchor_id(a)
        if aid and marker(aid) in text and aid not in hits:
            hits.append(aid)
    return tuple(hits)


def score_anchor(anchor: Anchor, query_tags: Iterable[str]) -> float:
    """Tag overlap dominates; a query word that also appears in the body adds one."""
    query = [str(q).lower() for q in query_tags]
    tag_hits = len(set(query) & {t.lower() for t in anchor.tags})
    words = anchor.body_words()
    body_hits = len({q for q in query if q in words})
    return TAG_WEIGHT * tag_hits + BODY_WEIGHT * body_hits


@dataclass
class RetrieveConfig:
    token_budget: int = 48
    retrieval_on: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.enabled is False:
            self.retrieval_on = False
        if self.retrieval_on is False:
            self.enabled = False
        if int(self.token_budget) <= 0:
            raise ValueError("token_budget must be positive")

    @property
    def active(self) -> bool:
        return bool(self.enabled and self.retrieval_on)


@dataclass
class TurnResult:
    round: int
    participant_id: str
    query_tags: tuple[str, ...]
    budget: int
    remaining_after_protected: int
    overflowed: bool
    evicted_anchor_ids: tuple[str, ...]
    kept_anchor_ids: tuple[str, ...]
    scores: dict[str, float]
    fetched_anchor_ids: tuple[str, ...]
    reason: str
    cited_early_ids: tuple[str, ...]
    prompt: str
    prompt_tokens: int

    @property
    def turn(self) -> int:
        return self.round

    def log_row(self) -> dict[str, Any]:
        return {
            "turn": self.round,
            "participant_id": self.participant_id,
            "query_tags": list(self.query_tags),
            "budget": self.budget,
            "remaining_after_protected": self.remaining_after_protected,
            "overflowed": self.overflowed,
            "evicted_anchor_ids": list(self.evicted_anchor_ids),
            "scores": dict(self.scores),
            "fetched_anchor_ids": list(self.fetched_anchor_ids),
            "reason": self.reason,
            "cited_early_ids": list(self.cited_early_ids),
            "prompt_tokens": self.prompt_tokens,
        }


def _protected_header(spec: TurnSpec) -> str:
    return f"ROLE {spec.role} {spec.participant_id}\nQUERY {' '.join(spec.query_tags)}"


def assemble_turn(council: Council, spec: TurnSpec, cfg: RetrieveConfig) -> TurnResult:
    budget = int(cfg.token_budget)
    header = _protected_header(spec)
    remaining = budget - count_tokens(header)
    if remaining < 0:
        raise ValueError(f"token_budget {budget} cannot hold the protected header")

    introduced = [a for a in council.anchors if a.round_introduced <= spec.round]
    transcript = [t.utterance for t in council.turns if t.round < spec.round]
    transcript_tokens = sum(count_tokens(u) for u in transcript)
    evidence_tokens = sum(a.tokens() for a in introduced)
    overflowed = evidence_tokens + transcript_tokens > remaining

    # Oldest evidence rounds leave first, until evidence + transcript fits.
    kept = list(introduced)
    evicted: list[Anchor] = []
    while kept and sum(a.tokens() for a in kept) + transcript_tokens > remaining:
        oldest = kept[0].round_introduced
        evicted.extend(a for a in kept if a.round_introduced == oldest)
        kept = [a for a in kept if a.round_introduced != oldest]

    free = remaining - sum(a.tokens() for a in kept)
    fetched: list[Anchor] = []
    scores: dict[str, float] = {}
    if cfg.active:
        scores = {a.id: score_anchor(a, spec.query_tags) for a in evicted}
        for cand in sorted(evicted, key=lambda a: (-scores[a.id], a.id)):
            if scores[cand.id] <= 0:
                break
            if cand.tokens() <= free:
                fetched.append(cand)
                free -= cand.tokens()
        if fetched:
            reason = "fetched"
        elif not evicted:
            reason = "nothing_evicted"
        else:
            reason = "no_fit_or_no_score"
    else:
        reason = "retrieval_disabled"

    # Transcript: newest utterances first; the newest one that does not fit is
    # trimmed to its tail so the leftover budget is not wasted.
    history: list[str] = []
    for utt in reversed(transcript):
        n = count_tokens(utt)
        if n <= free:
            history.insert(0, utt)
            free -= n
            continue
        if free > 0:
            history.insert(0, " ".join(utt.split()[-free:]))
            free = 0
        break

    sections = [header]
    sections.extend(f"RETRIEVED {a.body}" for a in fetched)
    sections.extend(f"EVIDENCE {a.body}" for a in kept)
    sections.append("HISTORY " + (" | ".join(history) if history else "(evicted)"))
    prompt = "\n".join(sections)
    cited = cite_early_anchors(prompt, council.early_anchors())

    return TurnResult(
        round=spec.round,
        participant_id=spec.participant_id,
        query_tags=tuple(spec.query_tags),
        budget=budget,
        remaining_after_protected=remaining,
        overflowed=overflowed,
        evicted_anchor_ids=tuple(a.id for a in evicted),
        kept_anchor_ids=tuple(a.id for a in kept),
        scores=scores,
        fetched_anchor_ids=tuple(a.id for a in fetched),
        reason=reason,
        cited_early_ids=cited,
        prompt=prompt,
        prompt_tokens=count_tokens(prompt),
    )


# --------------------------------------------------------------------------- #
# runs
# --------------------------------------------------------------------------- #
@dataclass
class CouncilRun:
    council_id: str
    council_fingerprint: str
    retrieval_enabled: bool
    token_budget: int
    late_round_min: int
    turns: list[TurnResult] = field(default_factory=list)

    def late_turns(self) -> list[TurnResult]:
        return [t for t in self.turns if t.round >= self.late_round_min]

    def rate(self) -> dict[str, Any]:
        """Early-round citation rate over the late turns (turns that cite >= 1 early anchor)."""
        late = self.late_turns()
        per_turn = [
            {
                "turn": t.round,
                "cited_early_ids": list(t.cited_early_ids),
                "hit": bool(t.cited_early_ids),
                "fetched_anchor_ids": list(t.fetched_anchor_ids),
                "overflowed": t.overflowed,
            }
            for t in late
        ]
        hits = sum(1 for row in per_turn if row["hit"])
        return {
            "rate": (hits / len(late)) if late else 0.0,
            "hits": hits,
            "late_turns": len(late),
            "retrieval_enabled": self.retrieval_enabled,
            "per_turn": per_turn,
        }

    def retrieval_log(self) -> list[dict[str, Any]]:
        return [t.log_row() for t in self.turns]

    def late_fetches(self) -> list[dict[str, Any]]:
        return [t.log_row() for t in self.late_turns()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "council_id": self.council_id,
            "council_fingerprint": self.council_fingerprint,
            "retrieval_enabled": self.retrieval_enabled,
            "token_budget": self.token_budget,
            "late_round_min": self.late_round_min,
            "rate": self.rate(),
            "per_turn": self.retrieval_log(),
        }


def run_council(council: Any, cfg: RetrieveConfig | None = None) -> CouncilRun:
    """Replay the planted council turn by turn under one retrieval configuration."""
    c = _as_council(council)
    cfg = cfg or RetrieveConfig()
    run = CouncilRun(
        council_id=c.id,
        council_fingerprint=c.fingerprint(),
        retrieval_enabled=cfg.active,
        token_budget=int(cfg.token_budget),
        late_round_min=c.late_round_min,
    )
    for spec in c.turns:
        run.turns.append(assemble_turn(c, spec, cfg))
    return run


def run_both_configurations(council: Any, token_budget: int = 48) -> dict[str, Any]:
    """Retrieval on and off on the *same* council; rates are computed, not asserted."""
    c = _as_council(council)
    on = run_council(c, RetrieveConfig(enabled=True, token_budget=token_budget))
    off = run_council(c, RetrieveConfig(enabled=False, token_budget=token_budget))
    rate_on = on.rate()
    rate_off = off.rate()
    late_on = on.late_turns()
    late_off = off.late_turns()
    overflow_late_on = bool(late_on) and all(t.overflowed for t in late_on)
    overflow_late_off = bool(late_off) and all(t.overflowed for t in late_off)
    same_council = (
        on.council_id == off.council_id
        and on.council_fingerprint == off.council_fingerprint
        and on.token_budget == off.token_budget
    )
    pass_experiment = (
        same_council
        and overflow_late_on
        and overflow_late_off
        and rate_on["late_turns"] == rate_off["late_turns"] > 0
        and rate_on["rate"] > rate_off["rate"]
    )
    pass_negative_control = (
        overflow_late_off
        and rate_off["rate"] == 0.0
        and not any(t.fetched_anchor_ids for t in late_off)
        and not any(t.cited_early_ids for t in late_off)
        and rate_on["rate"] > 0.0
    )
    return {
        "council_id": c.id,
        "council_fingerprint": c.fingerprint(),
        "same_council": same_council,
        "token_budget": int(token_budget),
        "tokenizer": TOKENIZER,
        "citer": CITER,
        "early_round_max": c.early_round_max,
        "late_round_min": c.late_round_min,
        "early_anchor_ids": [a.id for a in c.early_anchors()],
        "overflow_late_on": overflow_late_on,
        "overflow_late_off": overflow_late_off,
        "rate_on": rate_on,
        "rate_off": rate_off,
        "late_fetches_on": on.late_fetches(),
        "late_fetches_off": off.late_fetches(),
        "retrieval_log_on": on.retrieval_log(),
        "retrieval_log_off": off.retrieval_log(),
        "pass_experiment": pass_experiment,
        "pass_negative_control": pass_negative_control,
    }


def main() -> int:
    result = run_both_configurations(build_overflow_council(), token_budget=48)
    print(json.dumps(result, indent=2, sort_keys=True))
    ok = result["pass_experiment"] and result["pass_negative_control"]
    print(
        f"rate_on={result['rate_on']['rate']} rate_off={result['rate_off']['rate']} "
        f"late_fetches={[e['fetched_anchor_ids'] for e in result['late_fetches_on']]}"
    )
    print("SUCCESS:IMP-0349 retrieve" if ok else "FAILED:IMP-0349 retrieve")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
