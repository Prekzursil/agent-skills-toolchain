"""Executable primitives that the bp-3 blueprints DECLARE.

Every function here is the mechanical half of a gate written into one of the twelve
blueprints. They live in code rather than in prose for one reason: fan-out-contract C4 is
that a question answerable by an exact algorithm must be answered by the algorithm, not by
LLM judgement (measured 86% accuracy with 100% of errors pointing at data loss). A blueprint
whose gate says "compute the pairwise overlap matrix" and then leaves the computation to an
agent has not mechanised anything.

Nothing here touches the network, the clock, or the filesystem, so every function is
deterministic and replayable - which is what the blueprints' ``replay.deterministic`` claim
rests on.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------- overlap primitive
# Shared by bp-pln-02 (concurrency admission over PLANNED file sets) and bp-pln-03 (merge
# ordering over MEASURED changed-file sets). Factored out precisely so the two blueprints
# are not two copies of one mechanism.

#: sentinel for "this unit's file set could not be determined"
UNKNOWN_FILE_SET = None


def pairwise_overlap(
    sets: Mapping[str, Iterable[str] | None],
) -> dict[tuple[str, str], frozenset[str]]:
    """Every unordered pair -> the files both members touch. Pure arithmetic, no judgement.

    A ``None`` file set means UNKNOWN. Under adverse inference an unknown set is treated as
    overlapping EVERYTHING, so the caller can never optimistically parallelise it.
    """
    keys = sorted(sets)
    known = {k: (None if sets[k] is None else frozenset(sets[k])) for k in keys}
    out: dict[tuple[str, str], frozenset[str]] = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            fa, fb = known[a], known[b]
            if fa is None or fb is None:
                # unknown vs anything: assume conflict, and say WHY with a marker
                out[(a, b)] = frozenset({"<unknown-file-set>"})
            else:
                inter = fa & fb
                if inter:
                    out[(a, b)] = inter
    return out


def serial_groups(
    keys: Sequence[str], overlaps: Mapping[tuple[str, str], frozenset[str]]
) -> list[list[str]]:
    """Connected components of the overlap graph. Members of one group must NOT run concurrently."""
    parent = {k: k for k in keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in overlaps:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    groups: dict[str, list[str]] = {}
    for k in sorted(keys):
        groups.setdefault(find(k), []).append(k)
    return [sorted(v) for _, v in sorted(groups.items())]


def assign_isolation(sets: Mapping[str, Iterable[str] | None], mutating: Iterable[str]) -> dict[str, str]:
    """worktree for mutating units, scoped-add otherwise, serial for an UNKNOWN file set.

    Worktree isolation appears in 9 of 329 executed workflows (2.7%); making it the DEFAULT
    for mutating units is the gap bp-pln-02 closes.
    """
    mut = set(mutating)
    out: dict[str, str] = {}
    for k in sorted(sets):
        if sets[k] is None:
            out[k] = "serial"
        elif k in mut:
            out[k] = "worktree"
        else:
            out[k] = "scoped-add"
    return out


# ------------------------------------------------------------ byte identity / supersession


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def classify_overlap(
    a: Mapping[str, bytes], b: Mapping[str, bytes]
) -> tuple[frozenset[str], frozenset[str]]:
    """(byte_identical, true_conflict) over the paths both sides changed.

    fan-out-contract C3: 7 PRs whose ``mergeStateStatus`` was CLEAN looked mutually
    conflicting and were fully stackable, because the overlapping content was
    byte-identical - whichever merged second was a no-op.
    """
    shared = set(a) & set(b)
    identical = frozenset(p for p in shared if _digest(a[p]) == _digest(b[p]))
    return identical, frozenset(shared - identical)


def is_superset(commits_a: Iterable[str], commits_b: Iterable[str]) -> bool:
    """True when B contains A (``git log B..A`` would be empty), i.e. reconcile from B."""
    return set(commits_a) <= set(commits_b)


def merge_order(
    prs: Sequence[str],
    conflicts: Mapping[tuple[str, str], frozenset[str]],
    surface: Mapping[str, int],
) -> list[str]:
    """Order by measured conflict SURFACE (unmerged path count), never by diff line count.

    A +72k-line / 288-commit PR measured a FIVE-file conflict surface; line count is not a
    cost proxy. Ties break on the id so the order is deterministic and replayable.
    """
    del conflicts  # ordering is by surface; the conflict map is the caller's gate input
    return sorted(prs, key=lambda p: (surface.get(p, 0), p))


# ----------------------------------------------------------------------- EVPI clarification


@dataclass(frozen=True)
class Question:
    text: str
    #: option label -> the plan that answer would produce
    options: Mapping[str, str]


def evpi_questions(
    candidates: Sequence[Question],
    *,
    star_prefixed: bool,
    actions_elapsed: int,
    max_questions: int = 3,
) -> list[Question]:
    """Keep only questions whose answer would CHANGE the approach; hard-stop otherwise.

    Three separate prohibitions, each of which alone returns the empty list:
    a ``*``-prefixed prompt is already scoped; a question after the first two actions is a
    mid-task clarification, which is an injection surface, not etiquette; and a question
    whose every option leads to the same plan is permission theatre.
    """
    if star_prefixed:
        return []
    if actions_elapsed > 2:
        return []
    kept = [q for q in candidates if len({str(v) for v in q.options.values()}) > 1]
    return kept[:max_questions]


# ---------------------------------------------------------------------- assumption ledger

_BANDS = ("high", "medium", "low")


@dataclass(frozen=True)
class Assumption:
    text: str
    load_bearing: bool
    confidence: str
    verification_probe: str | None = None


def blank_field_default(declared: object, worst_case: object) -> object:
    """A required-but-blank field defaults to WORST case, never to 'probably fine'."""
    if declared is None or declared == "" or declared == []:
        return worst_case
    return declared


def unhandled_assumptions(rows: Sequence[Assumption]) -> list[Assumption]:
    """LOW-confidence AND load-bearing AND no probe = a silent bet. That is the violation."""
    bad = []
    for r in rows:
        if r.confidence not in _BANDS:
            raise ValueError(f"confidence {r.confidence!r} not in {_BANDS}")
        if r.load_bearing and r.confidence == "low" and not r.verification_probe:
            bad.append(r)
    return bad


# --------------------------------------------------------------- acceptance-criterion lint

_COMPARATOR = re.compile(
    r"(>=|<=|==|!=|<|>|\bat least\b|\bat most\b|\bno more than\b|\bexactly\b|\bwithin\b)",
    re.I,
)
_QUANTITY = re.compile(r"(\d|\btrue\b|\bfalse\b|\bPASS\b|\bFAIL\b)")
_VAGUE = re.compile(r"\b(fast|nice|clean|intuitive|robust|scalable|good|smooth|modern)\b", re.I)


def is_testable(criterion: str) -> bool:
    """A criterion is machine-checkable only with a comparator AND a quantity.

    'should feel fast' has neither and must be rejected at requirement time, which is where
    rewriting it is cheap.
    """
    if not criterion.strip():
        return False
    if _VAGUE.search(criterion) and not _COMPARATOR.search(criterion):
        return False
    return bool(_COMPARATOR.search(criterion)) and bool(_QUANTITY.search(criterion))


def orphan_requirements(
    requirements: Mapping[str, str | None], decision_ids: Iterable[str]
) -> list[str]:
    """A requirement with no decision-log ancestor is scope creep, not a requirement."""
    known = set(decision_ids)
    return sorted(r for r, anc in requirements.items() if anc is None or anc not in known)


# ------------------------------------------------------------------ tournament with override


@dataclass(frozen=True)
class Architecture:
    name: str
    #: rubric dimension -> score 0..4
    scores: Mapping[str, int]
    critical_errors: Sequence[str] = ()
    fingerprint: str = ""


def eliminate_critical(cands: Sequence[Architecture]) -> tuple[list[Architecture], list[str]]:
    """A critical error forces elimination in round 1 - it is never averaged away."""
    live = [c for c in cands if not c.critical_errors]
    return live, [c.name for c in cands if c.critical_errors]


def near_duplicates(cands: Sequence[Architecture]) -> list[tuple[str, str]]:
    """Two architects producing the same fingerprint is an INDEPENDENCE failure, not a consensus."""
    seen: dict[str, str] = {}
    dups: list[tuple[str, str]] = []
    for c in cands:
        fp = c.fingerprint or c.name
        if fp in seen:
            dups.append((seen[fp], c.name))
        else:
            seen[fp] = c.name
    return dups


def bracket(
    cands: Sequence[Architecture], weights: Mapping[str, float]
) -> tuple[str | None, list[dict[str, object]]]:
    """Pairwise bracket on a PRE-FIXED weighted rubric; a winner must name a deciding dimension."""
    live, _ = eliminate_critical(cands)
    if not live:
        return None, []
    rounds: list[dict[str, object]] = []
    field_: list[Architecture] = list(live)
    while len(field_) > 1:
        nxt: list[Architecture] = []
        for i in range(0, len(field_) - 1, 2):
            a, b = field_[i], field_[i + 1]
            sa = sum(weights.get(d, 0.0) * a.scores.get(d, 0) for d in weights)
            sb = sum(weights.get(d, 0.0) * b.scores.get(d, 0) for d in weights)
            win, lose = (a, b) if sa >= sb else (b, a)
            deciding = max(
                weights,
                key=lambda d: weights[d] * abs(a.scores.get(d, 0) - b.scores.get(d, 0)),
            )
            rounds.append(
                {
                    "pair": [a.name, b.name],
                    "winner": win.name,
                    "deciding_dimension": deciding,
                    "loser_better_at": sorted(
                        d for d in weights if lose.scores.get(d, 0) > win.scores.get(d, 0)
                    ),
                }
            )
            nxt.append(win)
        if len(field_) % 2:
            nxt.append(field_[-1])
        field_ = nxt
    return field_[0].name, rounds


def minority_report(rounds: Sequence[Mapping[str, object]]) -> list[str]:
    """What the losers did better. Discarding it wastes the divergence the tournament paid for."""
    out: set[str] = set()
    for r in rounds:
        for d in r.get("loser_better_at", []) or []:  # type: ignore[union-attr]
            out.add(str(d))
    return sorted(out)


# ------------------------------------------------------------------------- lint ladder / cap


def lint_ladder(attempt_results: Sequence[bool], cap: int = 3) -> tuple[str, int]:
    """('clean'|'escalate', attempts_used). The (cap+1)-th attempt must never happen."""
    if cap < 1:
        raise ValueError("cap must be >= 1")
    for i, ok in enumerate(attempt_results[:cap], start=1):
        if ok:
            return "clean", i
    return "escalate", min(len(attempt_results), cap)


# ------------------------------------------------------------------ failure-domain mapping

#: the ten failure classes this estate has actually exhibited, each with the trait that
#: triggers it. Not a generic taxonomy - a measured one.
FAILURE_CLASSES: dict[str, str] = {
    "registered-but-unreachable": "generated-registration",
    "fail-open-on-missing-dependency": "try-except-importerror",
    "deployed-copy-edit-invisible-to-git": "writes-deployed-copy",
    "shared-budget-verdict-drop": "shared-budget-dispatcher",
    "detector-truncation": "reports-a-floor-as-a-total",
    "green-task-dead-feed": "scheduled-task",
    "stale-pinned-ref": "pins-a-ref",
    "env-injected-below-explicit-env": "spawns-subprocess-with-env",
    "agent-death-at-orchestrator-boundary": "fans-out-subagents",
    "pipeline-first-stage-rerun": "wraps-a-resumable-boundary",
}


@dataclass
class Domain:
    failure_class: str
    applies: bool
    symptom: str = ""
    who_notices: str = ""
    blast_radius: str = ""
    detection_probe: str | None = None
    unmonitored: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.unmonitored = bool(self.applies) and (
            not self.detection_probe or self.who_notices.strip().lower() in {"", "nobody"}
        )


def failure_domain_walk(
    option_traits: Iterable[str], probes: Mapping[str, str] | None = None
) -> list[Domain]:
    """Walk the whole catalogue against one option. An option with ZERO domains is a red flag."""
    traits = set(option_traits)
    probes = probes or {}
    rows: list[Domain] = []
    for cls, trigger in FAILURE_CLASSES.items():
        applies = trigger in traits
        rows.append(
            Domain(
                failure_class=cls,
                applies=applies,
                symptom=f"{cls} manifests via {trigger}" if applies else "",
                who_notices=("owner" if probes.get(cls) else "nobody") if applies else "",
                blast_radius="declared-by-mapper" if applies else "",
                detection_probe=probes.get(cls),
            )
        )
    return rows


def unmonitored_domains(rows: Sequence[Domain]) -> list[str]:
    return [r.failure_class for r in rows if r.unmonitored]


# ------------------------------------------------------- write-as-you-go / resume postcondition

UNKNOWN_MARKER = "UNKNOWN - not yet measured"


def is_truthful_partial(text: str) -> bool:
    """A partial artifact is a SUCCESS only while it is HONEST about what it has not measured."""
    return bool(text.strip())


def unit_complete(text: str, min_bytes: int) -> bool:
    """A unit whose artifact still carries the UNKNOWN marker is NOT complete, however green."""
    if len(text.encode("utf-8")) < min_bytes:
        return False
    return UNKNOWN_MARKER not in text


def resume_plan(artifacts: Mapping[str, str], min_bytes: int) -> dict[str, list[str]]:
    """Skip units whose POSTCONDITION already passes; never trust 'the agent said done'."""
    complete, rerun = [], []
    for uid in sorted(artifacts):
        (complete if unit_complete(artifacts[uid], min_bytes) else rerun).append(uid)
    return {"skip": complete, "run": rerun}


# ---------------------------------------------------------------- vendor-neutral round trip


def topology(doc: Mapping[str, object]) -> list[tuple[str, str, tuple[str, ...]]]:
    """(stage id, kind, depends_on) in document order - the thing a round-trip must preserve."""
    out: list[tuple[str, str, tuple[str, ...]]] = []

    def walk(stages: object) -> None:
        if not isinstance(stages, list):
            return
        for s in stages:
            if not isinstance(s, Mapping):
                continue
            out.append(
                (
                    str(s.get("id")),
                    str(s.get("kind")),
                    tuple(str(d) for d in (s.get("depends_on") or [])),
                )
            )
            walk(s.get("body"))

    walk(doc.get("stages"))
    return out


def roundtrip_equal(source: Mapping[str, object], emitted: Mapping[str, object]) -> bool:
    """A spec that loses a stage or an edge is REJECTED, never patched to look right."""
    return topology(source) == topology(emitted)


def vendor_locked(
    stage_ids: Iterable[str], provider_map: Mapping[str, Mapping[str, str]]
) -> list[str]:
    """A stage with no mapping for a vendor is declared UNSUPPORTED, never silently dropped."""
    return sorted(s for s in stage_ids if not provider_map.get(s))


# ------------------------------------------------------------- disarmed vs unused (audit)


def classify_component(
    *, registered: bool, fired_recently: bool, fires_on_known_bad_state: bool | None
) -> str:
    """DISARMED is not UNUSED. 'Not exercised recently' is not evidence of deadness.

    ``fires_on_known_bad_state is None`` means the both-states probe was never run, so the
    honest classification is UNKNOWN - a component is never presumed dead by default.
    """
    if not registered:
        return "unregistered"
    if fires_on_known_bad_state is None:
        return "unknown-no-both-states-probe"
    if not fires_on_known_bad_state:
        return "disarmed"
    return "live-exercised" if fired_recently else "live-dormant"


def removable(classification: str, blast_radius_traced: bool, security_bearing: bool) -> bool:
    """No removal without a traced blast radius; a security-bearing removal is owner-only."""
    if not blast_radius_traced or security_bearing:
        return False
    return classification == "unregistered"
