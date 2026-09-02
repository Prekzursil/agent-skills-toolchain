"""Brainstorming engine with a structured, append-only idea ledger (P26, IMP-0291).

The ledger answers one falsifiable question: does the "unique ideas" count
reflect distinct *mechanisms* or merely distinct *strings*?  Spec 11339 is the
attack it must survive - a 100-idea brainstorm that satisfies ``unique_ideas
>= 100`` with trivial wording variants of one idea.  The ledger therefore keeps
two counters side by side and stops on the second one only:

* ``string_distinct`` - distinct :func:`string_key` values (case/whitespace
  normalised text).  This is the counter a count-gaming brainstorm inflates.
* ``mechanism_distinct`` - distinct :func:`canonicalize_mechanism` values.
  Known mechanism families are recognised through a cue lexicon (``circuit
  breaker`` in any hedge is still ``mech:circuit-breaker``); wording that
  matches no family is grouped by Jaccard overlap of its content tokens
  against mechanisms already in the ledger (``JACCARD_MERGE``), so two
  paraphrases of a novel idea share one mechanism while a genuinely different
  idea still opens a new one.

Every row records author, round, text, both keys, a logical submission tick and
a SHA-256 digest of its canonical fields.  The ledger is append-only: the
mutation entry points (:meth:`IdeaLedger.replace`, ``delete``, ``clear``,
``rewrite_text``) exist so callers get a typed :class:`LedgerMutationError`
instead of a silent no-op.  A JSONL dump is re-verified on load - digest,
string key, canonical mechanism and sequence are recomputed and any
disagreement is a :class:`LedgerTamperError`.  Appends are executed as kernel
turns through :class:`RecordingKernel` (execute-and-record invariant of
IMP-0264); ``require_kernel=True`` turns a kernel-less append into a
:class:`KernelBypass`.  The module never opens a write handle on participant
output; persistence goes through :meth:`IdeaLedger.dump_jsonl` only.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

__all__ = [
    "PROTOCOL_ID",
    "UNIQUE_IDEA_TARGET",
    "JACCARD_MERGE",
    "COUNT_GAMING_INFLATION",
    "COUNT_GAMING_MIN_EXCESS",
    "GROUPING_PASS_F1",
    "MECHANISM_LEXICON",
    "BrainstormError",
    "EmptyIdea",
    "KernelBypass",
    "LedgerMutationError",
    "LedgerTamperError",
    "RecordingKernel",
    "Idea",
    "IdeaLedger",
    "string_key",
    "tokens",
    "content_tokens",
    "jaccard",
    "classify_family",
    "canonicalize_mechanism",
    "unique_ideas",
    "pairwise_grouping_score",
]

PROTOCOL_ID = "P26-brainstorm"
UNIQUE_IDEA_TARGET = 100
JACCARD_MERGE = 0.62
COUNT_GAMING_INFLATION = 2.0
COUNT_GAMING_MIN_EXCESS = 5
GROUPING_PASS_F1 = 0.9
MECH_PREFIX = "mech:"
NOVEL_PREFIX = "mech:novel-"

# family -> ((cue phrase, weight), ...).  A cue phrase is matched on the
# hyphen-normalised token stream with every cue word a *prefix* of the token it
# lands on, so ``compensat`` covers compensating/compensation/compensations and
# ``event sourc`` covers event-sourced/event sourcing.  ``circuit break`` is the
# only circuit-breaker cue on purpose: "instead of a breaker" must not score.
MECHANISM_LEXICON: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = (
    ("circuit-breaker", (("circuit break", 3),)),
    (
        "exponential-backoff",
        (("exponential", 3), ("backoff", 3), ("back off", 3), ("retr", 1), ("jitter", 1)),
    ),
    ("bulkhead-isolation", (("bulkhead", 3), ("isolat", 1))),
    ("cache-aside", (("cache aside", 3), ("cache", 1))),
    ("saga-compensation", (("saga", 3), ("compensat", 2))),
    ("event-sourcing", (("event sourc", 3), ("replay", 1), ("projection", 1), ("append only", 1))),
    ("request-hedging", (("hedg", 3), ("tail latency", 1))),
    ("lease-fencing", (("fenc", 3), ("lease", 2))),
)

_STOPWORDS = frozenset(
    """
    a an the and or but so if then than that this these those it its is are was were be been
    being to of on in for with by from at as into onto over under out up down off per via
    we our us i you your they them their he she his her one ones
    do does did not no cannot can could should would will shall may might must
    have has had having let please simply maybe perhaps recommend consider proposal idea
    think team every each all any some same rather instead also just
    """.split()
)
_WORD_RE = re.compile(r"[a-z0-9]+")


class BrainstormError(ValueError):
    """Base class for ledger refusals."""


class EmptyIdea(BrainstormError):
    """An idea with no content (blank text) was offered to the ledger."""


class KernelBypass(BrainstormError):
    """A turn would have run outside the kernel's execute-and-record loop."""


class LedgerMutationError(BrainstormError):
    """The append-only ledger refused a replace/delete/clear/rewrite."""


class LedgerTamperError(BrainstormError):
    """A persisted row disagrees with its recomputed keys or digest."""


# --------------------------------------------------------------------------- text
def _normalise(text: str) -> str:
    return " ".join(str(text).lower().replace("-", " ").replace("_", " ").split())


def string_key(text: str) -> str:
    """Case/whitespace-normalised text with trailing sentence punctuation removed.

    Two ideas with the same string key are the same *string*; nothing more.
    Digits are kept so ``after 1 failure`` and ``after 10 failures`` stay distinct.
    """
    key = " ".join(str(text).lower().split())
    return key.rstrip(" .!?;:")


def tokens(text: str) -> list[str]:
    """Lower-case alphanumeric tokens of the hyphen-normalised text (order kept)."""
    return _WORD_RE.findall(_normalise(text))


def _stem(tok: str) -> str:
    if len(tok) > 5 and tok.endswith("ing"):
        tok = tok[:-3]
    elif len(tok) > 4 and tok.endswith("ed"):
        tok = tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    return tok


def content_tokens(text: str) -> frozenset[str]:
    """Stemmed tokens minus stopwords and hedges - the skeleton Jaccard compares."""
    return frozenset(_stem(t) for t in tokens(text) if t not in _STOPWORDS)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity of two token collections (1.0 for two empty sets)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _cue_hits(toks: Sequence[str], cue: str) -> int:
    words = cue.split()
    n = len(words)
    hits = 0
    for i in range(len(toks) - n + 1):
        if all(toks[i + j].startswith(words[j]) for j in range(n)):
            hits += 1
    return hits


def classify_family(text: str) -> tuple[str | None, dict[str, int]]:
    """Score every lexicon family; return ``(best_family or None, scores)``.

    A family needs a positive score to win; ties keep lexicon order.  Scores
    are per-cue weights multiplied by the number of cue occurrences.
    """
    toks = tokens(text)
    scores: dict[str, int] = {}
    for family, cues in MECHANISM_LEXICON:
        total = 0
        for cue, weight in cues:
            total += weight * _cue_hits(toks, cue)
        scores[family] = total
    best: str | None = None
    best_score = 0
    for family, _cues in MECHANISM_LEXICON:
        if scores[family] > best_score:
            best, best_score = family, scores[family]
    return best, scores


def _novel_id(toks: frozenset[str], text: str) -> str:
    basis = " ".join(sorted(toks)) if toks else string_key(text)
    return NOVEL_PREFIX + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]


def canonicalize_mechanism(
    text: str, prior: Mapping[str, frozenset[str]] | None = None
) -> str:
    """Canonical mechanism id of ``text``.

    Lexicon families win first (``mech:<family>``).  Otherwise the content
    skeleton is compared with the novel mechanisms in ``prior`` (mechanism id
    -> anchor token set); the best match at or above ``JACCARD_MERGE`` is
    reused, else a new content-addressed ``mech:novel-<hash>`` id is minted.
    """
    family, _scores = classify_family(text)
    if family is not None:
        return MECH_PREFIX + family
    toks = content_tokens(text)
    if prior:
        best_id: str | None = None
        best_j = 0.0
        for mech_id, anchor in prior.items():
            j = jaccard(toks, anchor)
            if j > best_j:
                best_id, best_j = mech_id, j
        if best_id is not None and best_j >= JACCARD_MERGE:
            return best_id
    return _novel_id(toks, text)


# -------------------------------------------------------------------------- kernel
class RecordingKernel:
    """Minimal execute-and-record kernel (the IMP-0264 loop invariant).

    Every executed turn is recorded as one event; ``turns_executed`` and
    ``turns_recorded`` therefore move together and :attr:`invariant_ok` is the
    ledger's evidence that no idea entered outside the kernel.
    """

    def __init__(self, council_id: str = "brainstorm") -> None:
        self.council_id = council_id
        self.turns_executed = 0
        self.turns_recorded = 0
        self.events: list[dict[str, Any]] = []

    def execute_turn(
        self,
        participant_id: str,
        output: str,
        fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.turns_executed += 1
        return self._record(participant_id, output, dict(fields or {}))

    def _record(self, participant_id: str, output: str, fields: dict[str, Any]) -> dict[str, Any]:
        event = {
            "kind": "TURN",
            "seq": self.turns_recorded + 1,
            "participant_id": participant_id,
            "status": "ok",
            "output": output,
            "fields": fields,
        }
        self.events.append(event)
        self.turns_recorded += 1
        return event

    @property
    def invariant_ok(self) -> bool:
        return self.turns_executed == self.turns_recorded


# -------------------------------------------------------------------------- ledger
_ROW_FIELDS = (
    "idea_id",
    "sequence",
    "author",
    "round",
    "text",
    "string_key",
    "canonical_mechanism",
    "submitted_at",
)


@dataclass(frozen=True)
class Idea:
    """One immutable ledger row."""

    idea_id: str
    sequence: int
    author: str
    round: int
    text: str
    string_key: str
    canonical_mechanism: str
    submitted_at: int
    digest: str

    @staticmethod
    def compute_digest(fields: Mapping[str, Any]) -> str:
        canonical = {name: fields[name] for name in _ROW_FIELDS}
        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea_id": self.idea_id,
            "sequence": self.sequence,
            "author": self.author,
            "round": self.round,
            "text": self.text,
            "string_key": self.string_key,
            "canonical_mechanism": self.canonical_mechanism,
            "submitted_at": self.submitted_at,
            "digest": self.digest,
        }

    @property
    def is_novel(self) -> bool:
        return self.canonical_mechanism.startswith(NOVEL_PREFIX)


class IdeaLedger:
    """Append-only idea ledger with side-by-side string/mechanism counters."""

    def __init__(
        self,
        kernel: Any | None = None,
        *,
        target: int = UNIQUE_IDEA_TARGET,
        protocol_id: str = PROTOCOL_ID,
    ) -> None:
        self.kernel = kernel
        self.target = int(target)
        self.protocol_id = protocol_id
        self._ideas: list[Idea] = []
        self._ids: set[str] = set()
        self._novel: dict[str, frozenset[str]] = {}
        self._clock = 0
        self.refused_mutations: list[str] = []

    # -- read side ---------------------------------------------------------
    @property
    def ideas(self) -> tuple[Idea, ...]:
        return tuple(self._ideas)

    def __len__(self) -> int:
        return len(self._ideas)

    def __iter__(self) -> Iterator[Idea]:
        return iter(tuple(self._ideas))

    def mechanisms(self) -> dict[str, list[str]]:
        """Canonical mechanism -> idea ids, in first-seen order."""
        out: dict[str, list[str]] = {}
        for idea in self._ideas:
            out.setdefault(idea.canonical_mechanism, []).append(idea.idea_id)
        return out

    def string_distinct(self) -> int:
        return len({idea.string_key for idea in self._ideas})

    def unique_ideas(self) -> int:
        """The stopping counter: mechanism-distinct ideas."""
        return len({idea.canonical_mechanism for idea in self._ideas})

    def unique_counts(self) -> dict[str, int]:
        """``appended`` / ``string_distinct`` / ``mechanism_distinct`` side by side."""
        return {
            "appended": len(self._ideas),
            "string_distinct": self.string_distinct(),
            "mechanism_distinct": self.unique_ideas(),
        }

    def target_met(self) -> bool:
        return self.unique_ideas() >= self.target

    def count_gaming_detected(self) -> bool:
        """True when the string counter inflates the mechanism counter.

        Inflation means at least ``COUNT_GAMING_MIN_EXCESS`` more strings than
        mechanisms *and* a string/mechanism ratio of ``COUNT_GAMING_INFLATION``
        or more - the signature of one idea worded many ways.
        """
        counts = self.unique_counts()
        mech = counts["mechanism_distinct"]
        strings = counts["string_distinct"]
        if mech == 0 or strings - mech < COUNT_GAMING_MIN_EXCESS:
            return False
        return strings >= COUNT_GAMING_INFLATION * mech

    def summary(self) -> dict[str, Any]:
        counts = self.unique_counts()
        return {
            "protocol_id": self.protocol_id,
            **counts,
            "target": self.target,
            "stopping_counter": "mechanism_distinct",
            "target_met": self.target_met(),
            "count_gaming_detected": self.count_gaming_detected(),
            "mechanisms": self.mechanisms(),
        }

    # -- append ------------------------------------------------------------
    def append(
        self,
        author: str,
        round: int,
        text: str,
        idea_id: str | None = None,
        require_kernel: bool = False,
    ) -> Idea:
        """Append one idea; returns the immutable row.

        Raises :class:`EmptyIdea` for blank text, :class:`KernelBypass` when
        ``require_kernel`` is set without a kernel (or the kernel executed the
        turn without recording it) and :class:`BrainstormError` for a reused
        idea id, a blank author or a negative round.
        """
        if not isinstance(text, str) or not text.strip():
            raise EmptyIdea("idea text is blank")
        author_id = str(author).strip()
        if not author_id:
            raise BrainstormError("idea author is blank")
        round_index = int(round)
        if round_index < 0:
            raise BrainstormError(f"negative round {round_index}")
        if require_kernel and self.kernel is None:
            raise KernelBypass("append requires a kernel turn but no kernel is bound")
        sequence = len(self._ideas) + 1
        if idea_id is None:
            idea_id = f"IDEA-{sequence:04d}"
        idea_id = str(idea_id)
        if idea_id in self._ids:
            raise BrainstormError(f"duplicate idea id {idea_id}")
        mechanism = canonicalize_mechanism(text, prior=self._novel)
        self._clock += 1
        fields = {
            "idea_id": idea_id,
            "sequence": sequence,
            "author": author_id,
            "round": round_index,
            "text": text,
            "string_key": string_key(text),
            "canonical_mechanism": mechanism,
            "submitted_at": self._clock,
        }
        idea = Idea(digest=Idea.compute_digest(fields), **fields)
        if self.kernel is not None:
            self._execute_as_turn(idea)
        self._admit(idea)
        return idea

    def _execute_as_turn(self, idea: Idea) -> None:
        kernel = self.kernel
        executed_before = getattr(kernel, "turns_executed", None)
        recorded_before = getattr(kernel, "turns_recorded", None)
        kernel.execute_turn(
            idea.author,
            idea.text,
            {
                "idea_id": idea.idea_id,
                "round": idea.round,
                "canonical_mechanism": idea.canonical_mechanism,
                "protocol_id": self.protocol_id,
            },
        )
        executed = getattr(kernel, "turns_executed", None)
        recorded = getattr(kernel, "turns_recorded", None)
        if executed is not None and recorded is not None:
            if executed != recorded or executed != (executed_before or 0) + 1:
                raise KernelBypass("kernel executed a turn it did not record")
        if recorded is not None and recorded_before is not None and recorded == recorded_before:
            raise KernelBypass("kernel recorded nothing for the idea turn")

    def _admit(self, idea: Idea) -> None:
        self._ideas.append(idea)
        self._ids.add(idea.idea_id)
        if idea.is_novel and idea.canonical_mechanism not in self._novel:
            self._novel[idea.canonical_mechanism] = content_tokens(idea.text)

    # -- refused mutations -------------------------------------------------
    def _refuse(self, what: str) -> None:
        self.refused_mutations.append(what)
        raise LedgerMutationError(f"ledger is append-only: {what} refused")

    def replace(self, idea_id: str, **changes: Any) -> None:
        self._refuse(f"replace({idea_id!r}, {sorted(changes)})")

    def delete(self, idea_id: str) -> None:
        self._refuse(f"delete({idea_id!r})")

    def clear(self) -> None:
        self._refuse("clear()")

    def rewrite_text(self, idea_id: str, text: str) -> None:
        self._refuse(f"rewrite_text({idea_id!r})")

    def __setitem__(self, key: Any, value: Any) -> None:
        self._refuse(f"__setitem__({key!r})")

    def __delitem__(self, key: Any) -> None:
        self._refuse(f"__delitem__({key!r})")

    # -- persistence -------------------------------------------------------
    def dump_jsonl(self, path: str | Path) -> Path:
        """Write one JSON object per row (sorted keys, LF) via ``Path.write_text``."""
        target = Path(path)
        body = "".join(json.dumps(idea.to_dict(), sort_keys=True) + "\n" for idea in self._ideas)
        target.write_text(body, encoding="utf-8")
        return target

    @classmethod
    def load_jsonl(cls, path: str | Path, kernel: Any | None = None) -> "IdeaLedger":
        """Rebuild a ledger from JSONL, re-verifying every row.

        Each row's digest, string key, canonical mechanism (recomputed with the
        rows loaded before it as prior) and sequence must agree with the stored
        values; any disagreement raises :class:`LedgerTamperError`.
        """
        ledger = cls(kernel=kernel)
        text = Path(path).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerTamperError(f"line {lineno}: not JSON ({exc.msg})") from None
            if not isinstance(rec, dict):
                raise LedgerTamperError(f"line {lineno}: row is not an object")
            missing = [name for name in (*_ROW_FIELDS, "digest") if name not in rec]
            if missing:
                raise LedgerTamperError(f"line {lineno}: missing {missing}")
            if Idea.compute_digest(rec) != rec["digest"]:
                raise LedgerTamperError(f"line {lineno}: digest mismatch")
            if string_key(rec["text"]) != rec["string_key"]:
                raise LedgerTamperError(f"line {lineno}: string_key mismatch")
            recomputed = canonicalize_mechanism(rec["text"], prior=ledger._novel)
            if recomputed != rec["canonical_mechanism"]:
                raise LedgerTamperError(
                    f"line {lineno}: canonical_mechanism {rec['canonical_mechanism']!r} "
                    f"!= recomputed {recomputed!r}"
                )
            if int(rec["sequence"]) != len(ledger._ideas) + 1:
                raise LedgerTamperError(f"line {lineno}: sequence gap")
            if rec["idea_id"] in ledger._ids:
                raise LedgerTamperError(f"line {lineno}: duplicate idea id")
            idea = Idea(
                idea_id=str(rec["idea_id"]),
                sequence=int(rec["sequence"]),
                author=str(rec["author"]),
                round=int(rec["round"]),
                text=str(rec["text"]),
                string_key=str(rec["string_key"]),
                canonical_mechanism=str(rec["canonical_mechanism"]),
                submitted_at=int(rec["submitted_at"]),
                digest=str(rec["digest"]),
            )
            ledger._admit(idea)
            ledger._clock = max(ledger._clock, idea.submitted_at)
        return ledger


def unique_ideas(source: IdeaLedger | Iterable[str]) -> int:
    """Mechanism-distinct count of a ledger or of raw idea texts."""
    if isinstance(source, IdeaLedger):
        return source.unique_ideas()
    ledger = IdeaLedger()
    for i, text in enumerate(source):
        ledger.append(author="anon", round=0, text=text, idea_id=f"TXT-{i + 1:04d}")
    return ledger.unique_ideas()


# ------------------------------------------------------------------------- scoring
def pairwise_grouping_score(
    gold: Sequence[str],
    predicted: Sequence[str],
    pass_f1: float = GROUPING_PASS_F1,
) -> dict[str, Any]:
    """Pairwise precision/recall/F1 of a predicted grouping against gold labels.

    Every unordered pair of items is a decision: same-group or not.  A pair
    predicted together that is gold-together is a true positive; predicted
    together but gold-apart a false positive; gold-together but predicted apart
    a false negative.  ``exact_family_collapse`` is True when the gold->
    predicted label map is a bijection (each family collapsed to exactly one
    mechanism and no mechanism absorbed two families).
    """
    if len(gold) != len(predicted):
        raise BrainstormError(f"gold has {len(gold)} labels, predicted {len(predicted)}")
    n = len(gold)
    tp = fp = fn = tn = 0
    for i, j in combinations(range(n), 2):
        same_gold = gold[i] == gold[j]
        same_pred = predicted[i] == predicted[j]
        if same_gold and same_pred:
            tp += 1
        elif same_pred:
            fp += 1
        elif same_gold:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    image: dict[str, set[str]] = {}
    for g, p in zip(gold, predicted):
        image.setdefault(g, set()).add(p)
    one_each = all(len(v) == 1 for v in image.values())
    exact = one_each and len({next(iter(v)) for v in image.values()}) == len(image)
    return {
        "items": n,
        "pairs": n * (n - 1) // 2,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "gold_clusters": len(set(gold)),
        "predicted_clusters": len(set(predicted)),
        "exact_family_collapse": exact,
        "pass_f1": pass_f1,
        "pass": f1 >= pass_f1,
    }
