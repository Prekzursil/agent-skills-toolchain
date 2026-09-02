"""Tournament engine: pairwise matrix, transitivity, schedulers and the FDR family (TST-0299, TST-0300).

Two units share this module.

TST-0300 - scheduling and transitivity.  :func:`evaluate_field` turns raw per-case scores
into a pairwise result matrix (who beats whom on the cases both attempted, with the win
margin as effect size), enumerates every cycle of the beats-graph and runs the round-robin
and Swiss schedulers.  A field with a cycle is a partial order: no leaderboard and no top
entry are bound and the owner action is ``REPORT_FIELD_FINDING``.  When round-robin and
Swiss disagree on the top entry, the disagreement is published as a ``schedule-disagreement``
finding about the *field*; the engine never resolves it by picking a scheduler.
:func:`select_format` chooses round-robin for small fields, Swiss for large ones and
elimination only when the pair budget cannot afford Swiss.

TST-0299 - the comparison family.  :func:`null_identical_tournament`,
:func:`null_iid_tournament` and :func:`mixed_tournament` run forty candidates against one
baseline on matched cases, compute a paired-t p-value per candidate, correct the whole
family with BH and Holm and feed the Holm verdict to the certification gate.  The mixed
tournament is the iid null field with a real effect planted on two candidates, so every
other uncorrected winner it shows is one of the null tournament's chance winners.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from .certification import (
    certification_gate,
    lucky_uncorrected_only,
    mutant_reads_uncorrected,
)
from .multiple_comparison import correct_family
from .paired_test import paired_mean_greater_p

# ranking kinds
PARTIAL_ORDER = "PARTIAL_ORDER"
TOTAL_ORDER = "TOTAL_ORDER"
# schedule formats
ROUND_ROBIN = "round-robin"
SWISS = "swiss"
ELIMINATION = "elimination"
INSUFFICIENT_BUDGET = "insufficient-budget"
SMALL_FIELD_MAX = 8
# owner actions and finding kinds
REPORT_FIELD_FINDING = "REPORT_FIELD_FINDING"
PUBLISH_LEADERBOARD = "PUBLISH_LEADERBOARD"
PICK_ROUND_ROBIN = "PICK_ROUND_ROBIN"
PICK_SWISS = "PICK_SWISS"
PICK_ACTIONS = frozenset({PICK_ROUND_ROBIN, PICK_SWISS})
SCHEDULE_DISAGREEMENT = "schedule-disagreement"
NON_TRANSITIVE = "non-transitive"
INCOMPLETE_MATRIX = "incomplete-matrix"

# TST-0299 family design
UNIT_ID = "TST-0299"
FAMILY_SIZE = 40
N_CASES = 30
ALPHA = 0.05
BASELINE_MEAN = 0.55
BASELINE_SD = 0.12
NOISE_SD = 0.08
TRUE_EFFECT = 0.12
N_TRUE = 2
# One seed for both fields: the mixed tournament is the null field plus a planted effect,
# which is what makes its chance winners the null tournament's chance winners.
NULL_SEED = 4
MIXED_SEED = 4
KIND_NULL_IDENTICAL = "null-identical"
KIND_NULL_IID = "null-iid"
KIND_MIXED = "mixed"

CASES_REL = Path("command-center") / "bench" / "cases"


class TournamentError(ValueError):
    """Raised for malformed scores, fixtures or field sizes."""


# --------------------------------------------------------------------------- scores
@dataclass(frozen=True)
class CaseScore:
    """One candidate's score on one benchmark case."""

    candidate_id: str
    case_id: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "score": self.score,
        }


def pair_key(a: str, b: str) -> str:
    """Canonical matrix key ``"<lower>|<higher>"`` for a candidate pair."""
    x, y = sorted((a, b))
    return f"{x}|{y}"


def _score_table(scores: Sequence[CaseScore]) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    for idx, row in enumerate(scores):
        if not isinstance(row, CaseScore):
            raise TournamentError(f"row {idx} is not a CaseScore: {row!r}")
        value = float(row.score)
        if not math.isfinite(value):
            raise TournamentError(
                f"{row.candidate_id}/{row.case_id}: non-finite score {row.score!r}"
            )
        by_case = table.setdefault(row.candidate_id, {})
        if row.case_id in by_case:
            raise TournamentError(
                f"duplicate score for {row.candidate_id} on {row.case_id}"
            )
        by_case[row.case_id] = value
    if len(table) < 2:
        raise TournamentError("a tournament needs at least two candidates")
    return table


# --------------------------------------------------------------------------- pairwise matrix
@dataclass
class PairCell:
    """Head-to-head record of two candidates on the cases both attempted."""

    a: str
    b: str
    a_wins: int
    b_wins: int
    ties: int
    n_cases: int
    winner: str | None
    margin: float

    @property
    def effect_size(self) -> float:
        """Win margin ``(a_wins - b_wins) / n_cases``; positive favours ``a``."""
        return self.margin

    @property
    def key(self) -> str:
        return f"{self.a}|{self.b}"

    @property
    def decided(self) -> bool:
        return self.winner is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "a": self.a,
            "b": self.b,
            "a_wins": self.a_wins,
            "b_wins": self.b_wins,
            "ties": self.ties,
            "n_cases": self.n_cases,
            "winner": self.winner,
            "margin": self.margin,
            "effect_size": self.effect_size,
        }


def pairwise_matrix(scores: Sequence[CaseScore]) -> dict[str, PairCell]:
    """Head-to-head cell for every candidate pair, counted only on the cases both attempted."""
    table = _score_table(scores)
    cells: dict[str, PairCell] = {}
    for a, b in combinations(sorted(table), 2):
        shared = sorted(set(table[a]) & set(table[b]))
        a_wins = b_wins = ties = 0
        for case_id in shared:
            sa, sb = table[a][case_id], table[b][case_id]
            if sa > sb:
                a_wins += 1
            elif sb > sa:
                b_wins += 1
            else:
                ties += 1
        n = len(shared)
        winner = a if a_wins > b_wins else b if b_wins > a_wins else None
        margin = 0.0 if n == 0 else (a_wins - b_wins) / n
        cells[f"{a}|{b}"] = PairCell(a, b, a_wins, b_wins, ties, n, winner, margin)
    return cells


def beats_graph(matrix: Mapping[str, PairCell]) -> dict[str, list[str]]:
    """Directed graph winner -> loser; undecided pairs contribute no edge."""
    graph: dict[str, list[str]] = {}
    for cell in matrix.values():
        graph.setdefault(cell.a, [])
        graph.setdefault(cell.b, [])
        if cell.winner == cell.a:
            graph[cell.a].append(cell.b)
        elif cell.winner == cell.b:
            graph[cell.b].append(cell.a)
    return {node: sorted(graph[node]) for node in sorted(graph)}


def enumerate_cycles(matrix: Mapping[str, PairCell]) -> list[list[str]]:
    """Every elementary cycle of the beats-graph, listed once from its smallest member.

    A cycle ``[a, b, c]`` reads ``a beats b, b beats c, c beats a``.  Restricting the walk to
    members larger than the start node makes each cycle appear exactly once.
    """
    graph = beats_graph(matrix)
    found: list[list[str]] = []

    def walk(start: str, node: str, path: list[str], on_path: set[str]) -> None:
        for nxt in graph[node]:
            if nxt == start:
                found.append(list(path))
            elif nxt > start and nxt not in on_path:
                path.append(nxt)
                on_path.add(nxt)
                walk(start, nxt, path, on_path)
                path.pop()
                on_path.discard(nxt)

    for start in graph:
        walk(start, start, [start], {start})
    return sorted(found, key=lambda cyc: (len(cyc), cyc))


def copeland_scores(matrix: Mapping[str, PairCell]) -> dict[str, float]:
    """Copeland points: 1 per pairwise win, 0.5 per tied pair, nothing for an unplayed pair."""
    points: dict[str, float] = {}
    for cell in matrix.values():
        points.setdefault(cell.a, 0.0)
        points.setdefault(cell.b, 0.0)
        if cell.winner == cell.a:
            points[cell.a] += 1.0
        elif cell.winner == cell.b:
            points[cell.b] += 1.0
        elif cell.n_cases > 0:
            points[cell.a] += 0.5
            points[cell.b] += 0.5
    return dict(sorted(points.items()))


# --------------------------------------------------------------------------- schedulers
@dataclass
class ScheduleResult:
    """Standings produced by one tournament format."""

    format: str
    rounds: int
    pairings: list[dict[str, Any]]
    points: dict[str, float]
    order: list[str]
    top: str | None
    tied_tops: list[str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "rounds": self.rounds,
            "pairings": list(self.pairings),
            "points": dict(self.points),
            "order": list(self.order),
            "top": self.top,
            "tied_tops": self.tied_tops,
        }


def _standings(
    fmt: str, rounds: int, points: Mapping[str, float], pairings: list[dict[str, Any]]
) -> ScheduleResult:
    order = sorted(points, key=lambda c: (-points[c], c))
    best = points[order[0]]
    tops = [c for c in order if points[c] == best]
    return ScheduleResult(
        format=fmt,
        rounds=rounds,
        pairings=pairings,
        points=dict(points),
        order=order,
        top=tops[0] if len(tops) == 1 else None,
        tied_tops=tops if len(tops) > 1 else None,
    )


def _play(cell: PairCell, points: dict[str, float]) -> dict[str, Any]:
    if cell.winner is not None:
        points[cell.winner] += 1.0
    elif cell.n_cases > 0:
        points[cell.a] += 0.5
        points[cell.b] += 0.5
    return {"a": cell.a, "b": cell.b, "winner": cell.winner, "n_cases": cell.n_cases}


def round_robin(matrix: Mapping[str, PairCell]) -> ScheduleResult:
    """Every pair meets once; standings are the Copeland points."""
    names = sorted({c for cell in matrix.values() for c in (cell.a, cell.b)})
    points = {c: 0.0 for c in names}
    pairings = [
        dict(_play(matrix[pair_key(a, b)], points), round=None)
        for a, b in combinations(names, 2)
    ]
    rounds = len(names) - 1 if len(names) % 2 == 0 else len(names)
    return _standings(ROUND_ROBIN, rounds, points, pairings)


def swiss_rounds(n: int) -> int:
    """ceil(log2(n)) rounds: enough to separate a unique undefeated entry."""
    if n < 2:
        raise TournamentError(
            f"a Swiss schedule needs at least two candidates, got {n}"
        )
    return (n - 1).bit_length()


def swiss(matrix: Mapping[str, PairCell], rounds: int | None = None) -> ScheduleResult:
    """Swiss system: seed by name, then pair neighbours in the standings who have not met.

    Each round walks the standings (points descending, name ascending) and pairs every entry
    with the nearest lower entry it has not played; an odd entry receives a full-point bye.
    The result of a pairing is read from the pairwise matrix, so the schedule never invents a
    result - it only decides which cells are consulted.
    """
    names = sorted({c for cell in matrix.values() for c in (cell.a, cell.b)})
    n_rounds = swiss_rounds(len(names)) if rounds is None else int(rounds)
    if n_rounds < 1:
        raise TournamentError(f"rounds must be >= 1, got {rounds!r}")
    points = {c: 0.0 for c in names}
    played: dict[str, set[str]] = {c: set() for c in names}
    pairings: list[dict[str, Any]] = []
    for rnd in range(1, n_rounds + 1):
        unpaired = sorted(names, key=lambda c: (-points[c], c))
        while len(unpaired) >= 2:
            a = unpaired.pop(0)
            idx = next((i for i, b in enumerate(unpaired) if b not in played[a]), 0)
            b = unpaired.pop(idx)
            record = _play(matrix[pair_key(a, b)], points)
            played[a].add(b)
            played[b].add(a)
            pairings.append(dict(record, round=rnd, rematch=len(played[a] & {b}) > 1))
        if unpaired:
            bye = unpaired[0]
            points[bye] += 1.0
            pairings.append(
                {
                    "a": bye,
                    "b": None,
                    "winner": bye,
                    "n_cases": 0,
                    "round": rnd,
                    "bye": True,
                }
            )
    return _standings(SWISS, n_rounds, points, pairings)


def schedules_agree(rr: ScheduleResult | None, sw: ScheduleResult | None) -> bool:
    """True only when both schedulers name the same unique top entry."""
    return rr is not None and sw is not None and rr.top is not None and rr.top == sw.top


def compare_schedulers(
    rr: ScheduleResult, sw: ScheduleResult
) -> tuple[bool, dict[str, Any] | None]:
    """Compare the round-robin and Swiss outcomes of one field.

    Returns ``(agreement, finding)``.  Agreement is a unique top entry shared by both
    schedulers.  Anything else - different tops, or a tie at the top of either table - is a
    ``schedule-disagreement`` finding that names both tops and both tie sets.  The finding is a
    statement about the field; no scheduler is preferred and nothing is resolved here.
    """
    if schedules_agree(rr, sw):
        return True, None
    finding = {
        "kind": SCHEDULE_DISAGREEMENT,
        "round_robin_top": rr.top,
        "round_robin_tied_tops": rr.tied_tops,
        "swiss_top": sw.top,
        "swiss_tied_tops": sw.tied_tops,
        "note": (
            "round-robin and Swiss name different top entries; that is a property of the "
            "field, not of a scheduler, and is not resolved by picking one"
        ),
    }
    return False, finding


# --------------------------------------------------------------------------- field report
@dataclass
class FieldReport:
    """What the engine publishes for one field of candidates."""

    candidates: list[str]
    n_cases: int
    matrix: dict[str, PairCell]
    cycles: list[list[str]]
    copeland: dict[str, float]
    ranking_kind: str
    binding_leaderboard: list[str] | None
    binding_top: str | None
    round_robin: ScheduleResult | None
    swiss: ScheduleResult | None
    schedule_agreement: bool | None
    schedule_finding: dict[str, Any] | None
    owner_action: str
    findings: list[dict[str, Any]]
    mutant: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": list(self.candidates),
            "n_cases": self.n_cases,
            "matrix": {k: v.to_dict() for k, v in self.matrix.items()},
            "cycles": [list(c) for c in self.cycles],
            "copeland": dict(self.copeland),
            "ranking_kind": self.ranking_kind,
            "binding_leaderboard": None
            if self.binding_leaderboard is None
            else list(self.binding_leaderboard),
            "binding_top": self.binding_top,
            "round_robin": None
            if self.round_robin is None
            else self.round_robin.to_dict(),
            "swiss": None if self.swiss is None else self.swiss.to_dict(),
            "schedule_agreement": self.schedule_agreement,
            "schedule_finding": self.schedule_finding,
            "owner_action": self.owner_action,
            "findings": list(self.findings),
            "mutant": self.mutant,
        }


def evaluate_field(scores: Sequence[CaseScore]) -> FieldReport:
    """Pairwise matrix, cycle enumeration, both schedulers and the binding decision."""
    table = _score_table(scores)
    candidates = sorted(table)
    n_cases = len({case for by_case in table.values() for case in by_case})
    matrix = pairwise_matrix(scores)
    cycles = enumerate_cycles(matrix)
    copeland = copeland_scores(matrix)
    undecided = sorted(k for k, cell in matrix.items() if not cell.decided)
    rr = round_robin(matrix)
    sw = swiss(matrix)
    agreement, schedule_finding = compare_schedulers(rr, sw)

    findings: list[dict[str, Any]] = []
    if cycles:
        findings.append(
            {
                "kind": NON_TRANSITIVE,
                "cycles": cycles,
                "note": "pairwise preferences form a cycle; a single-number ranking is fiction",
            }
        )
    if undecided:
        findings.append(
            {
                "kind": INCOMPLETE_MATRIX,
                "pairs": undecided,
                "note": "tied or unplayed pairs leave the order undecided",
            }
        )
    if schedule_finding is not None:
        findings.append(schedule_finding)

    total_order = not cycles and not undecided
    ranking_kind = TOTAL_ORDER if total_order else PARTIAL_ORDER
    if total_order and agreement:
        leaderboard: list[str] | None = list(rr.order)
        top: str | None = rr.top
        action = PUBLISH_LEADERBOARD
    else:
        leaderboard = None
        top = None
        action = REPORT_FIELD_FINDING
    return FieldReport(
        candidates=candidates,
        n_cases=n_cases,
        matrix=matrix,
        cycles=cycles,
        copeland=copeland,
        ranking_kind=ranking_kind,
        binding_leaderboard=leaderboard,
        binding_top=top,
        round_robin=rr,
        swiss=sw,
        schedule_agreement=agreement,
        schedule_finding=schedule_finding,
        owner_action=action,
        findings=findings,
    )


# --------------------------------------------------------------------------- detectors + mutants
def hides_nontransitivity(report: FieldReport) -> bool:
    """Fires when a field with a cycle is published as a total order, leaderboard or top entry."""
    if not report.cycles:
        return False
    return (
        report.ranking_kind == TOTAL_ORDER
        or report.binding_leaderboard is not None
        or report.binding_top is not None
    )


def mutant_hide_cycle(report: FieldReport) -> FieldReport:
    """Negative control: bind a Copeland leaderboard (name tie-break) over a cyclic field."""
    order = sorted(report.candidates, key=lambda c: (-report.copeland.get(c, 0.0), c))
    return replace(
        report,
        ranking_kind=TOTAL_ORDER,
        binding_leaderboard=list(order),
        binding_top=order[0],
        owner_action=PUBLISH_LEADERBOARD,
        mutant="hide-cycle-as-total-order",
    )


def silently_resolves_schedule(report: FieldReport) -> bool:
    """Fires when the schedulers disagree yet the report claims agreement or binds a top.

    The disagreement is recomputed from the scheduler results carried by the report, not
    read from its ``schedule_agreement`` flag, so a report that lies about agreement fires.
    """
    if schedules_agree(report.round_robin, report.swiss):
        return False
    return (
        report.schedule_agreement is True
        or report.binding_top is not None
        or report.owner_action in PICK_ACTIONS
    )


def mutant_pick_round_robin(report: FieldReport) -> FieldReport:
    """Negative control: resolve a scheduler disagreement by declaring round-robin binding."""
    rr = report.round_robin
    if rr is None:
        raise TournamentError("report carries no round-robin result to pick")
    top = rr.top if rr.top is not None else (rr.tied_tops or rr.order)[0]
    return replace(
        report,
        schedule_agreement=True,
        schedule_finding=None,
        binding_leaderboard=list(rr.order),
        binding_top=top,
        owner_action=PICK_ROUND_ROBIN,
        mutant="pick-scheduler-on-disagreement",
    )


# --------------------------------------------------------------------------- format selection
def pair_budget_requirements(n: int) -> dict[str, int]:
    """Pairings each format needs for ``n`` candidates."""
    if n < 2:
        raise TournamentError(f"a tournament needs at least two candidates, got {n}")
    return {
        ROUND_ROBIN: n * (n - 1) // 2,
        SWISS: swiss_rounds(n) * (n // 2),
        ELIMINATION: n - 1,
    }


def select_format(n: int, budget: int | None = None) -> str:
    """Round-robin for small fields, Swiss for large ones, elimination only when budget forces it.

    ``budget`` is the number of pairings the run can afford.  Without one, fields of at most
    ``SMALL_FIELD_MAX`` play round-robin and larger fields play Swiss.  With one, round-robin
    needs the full pair count, Swiss ``ceil(log2 n) * floor(n / 2)`` and elimination ``n - 1``;
    a budget below elimination is reported as ``INSUFFICIENT_BUDGET`` rather than silently
    shrinking the field.
    """
    need = pair_budget_requirements(int(n))
    if budget is None:
        return ROUND_ROBIN if n <= SMALL_FIELD_MAX else SWISS
    if int(budget) < 0:
        raise TournamentError(f"budget must be non-negative, got {budget!r}")
    if n <= SMALL_FIELD_MAX and need[ROUND_ROBIN] <= budget:
        return ROUND_ROBIN
    if need[SWISS] <= budget:
        return SWISS
    if need[ELIMINATION] <= budget:
        return ELIMINATION
    return INSUFFICIENT_BUDGET


# --------------------------------------------------------------------------- TST-0300 fixtures
CYCLE_CANDIDATES: tuple[str, ...] = ("wf-cycle-a", "wf-cycle-b", "wf-cycle-c")
CYCLE_CASES: dict[str, tuple[float, ...]] = {
    "case-1": (3.0, 2.0, 1.0),
    "case-2": (1.0, 3.0, 2.0),
    "case-3": (2.0, 1.0, 3.0),
}
FIELD_CANDIDATES: tuple[str, ...] = ("wf-apex", "wf-bold", "wf-cite", "wf-dash")
TRANSITIVE_CASES: dict[str, tuple[float, ...]] = {
    "case-1": (0.90, 0.70, 0.50, 0.30),
    "case-2": (0.80, 0.85, 0.60, 0.20),
    "case-3": (0.95, 0.60, 0.65, 0.40),
    "case-4": (0.85, 0.75, 0.55, 0.60),
}
# (a, b, winner): one dedicated 1-0 case per pair; apex > bold > cite > apex, dash loses to all.
UNSTABLE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("wf-apex", "wf-bold", "wf-apex"),
    ("wf-apex", "wf-cite", "wf-cite"),
    ("wf-apex", "wf-dash", "wf-apex"),
    ("wf-bold", "wf-cite", "wf-bold"),
    ("wf-bold", "wf-dash", "wf-bold"),
    ("wf-cite", "wf-dash", "wf-cite"),
)


def _matched(
    candidates: Sequence[str], cases: Mapping[str, Sequence[float]]
) -> list[CaseScore]:
    rows: list[CaseScore] = []
    for case_id, values in cases.items():
        if len(values) != len(candidates):
            raise TournamentError(
                f"{case_id}: {len(values)} scores for {len(candidates)} candidates"
            )
        rows.extend(
            CaseScore(cand, case_id, float(v)) for cand, v in zip(candidates, values)
        )
    return rows


def planted_cycle_scores() -> list[CaseScore]:
    """Three candidates that beat each other in a ring, each 2-1 on three matched cases."""
    return _matched(CYCLE_CANDIDATES, CYCLE_CASES)


def transitive_scores() -> list[CaseScore]:
    """Four candidates with a clean order apex > bold > cite > dash on four matched cases."""
    return _matched(FIELD_CANDIDATES, TRANSITIVE_CASES)


def schedule_unstable_scores() -> list[CaseScore]:
    """Four candidates, one dedicated 1-0 case per pair, with a 3-cycle among the top three."""
    rows: list[CaseScore] = []
    for a, b, winner in UNSTABLE_PAIRS:
        case_id = f"pair-{a.removeprefix('wf-')}-{b.removeprefix('wf-')}"
        rows.append(CaseScore(a, case_id, 1.0 if winner == a else 0.0))
        rows.append(CaseScore(b, case_id, 1.0 if winner == b else 0.0))
    return rows


FIXTURES: dict[str, tuple[str, Any, str]] = {
    "planted-cycle": (
        "tst-0300-planted-cycle.json",
        planted_cycle_scores,
        "Three candidates beat each other in a ring (A>B, B>C, C>A, each 2-1 on three matched "
        "cases); the correct report is a partial order with no leaderboard.",
    ),
    "transitive": (
        "tst-0300-transitive.json",
        transitive_scores,
        "Four candidates in a clean order apex > bold > cite > dash; round-robin and Swiss "
        "must agree on wf-apex.",
    ),
    "schedule-unstable": (
        "tst-0300-schedule-unstable.json",
        schedule_unstable_scores,
        "One dedicated 1-0 case per pair with a 3-cycle among apex, bold and cite; round-robin "
        "ties them while Swiss names wf-cite, so the disagreement is a field finding.",
    ),
}
FIXTURE_ORDER: tuple[str, ...] = ("planted-cycle", "transitive", "schedule-unstable")


def fixture_doc(kind: str) -> dict[str, Any]:
    """Serializable case document for one fixture kind."""
    if kind not in FIXTURES:
        raise TournamentError(
            f"unknown fixture {kind!r}; expected one of {list(FIXTURES)}"
        )
    filename, maker, note = FIXTURES[kind]
    scores = maker()
    return {
        "id": filename.removesuffix(".json"),
        "unit_id": "TST-0300",
        "kind": kind,
        "note": note,
        "candidates": sorted({s.candidate_id for s in scores}),
        "cases": sorted({s.case_id for s in scores}),
        "scores": [s.to_dict() for s in scores],
    }


def scores_from_fixture_doc(doc: Mapping[str, Any]) -> list[CaseScore]:
    """Rebuild the CaseScore rows of a fixture document, preserving their order."""
    rows = doc.get("scores") if isinstance(doc, Mapping) else None
    if not isinstance(rows, list) or not rows:
        raise TournamentError("fixture document has no 'scores' rows")
    out: list[CaseScore] = []
    for idx, row in enumerate(rows):
        try:
            out.append(
                CaseScore(
                    str(row["candidate_id"]), str(row["case_id"]), float(row["score"])
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TournamentError(f"fixture row {idx} is malformed: {row!r}") from exc
    return out


def repo_root() -> Path:
    """The ast-integrate tree this module lives in (tools/bench/tournament.py)."""
    return Path(__file__).resolve().parents[2]


def write_case_corpus(root: Path | None = None) -> list[str]:
    """Write the three TST-0300 fixtures under ``command-center/bench/cases``; return their paths."""
    base = Path(root) if root is not None else repo_root()
    out_dir = base / CASES_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for kind in FIXTURE_ORDER:
        filename = FIXTURES[kind][0]
        text = json.dumps(fixture_doc(kind), indent=1, sort_keys=True) + "\n"
        target = out_dir / filename
        try:
            current: str | None = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            current = None
        if current != text:
            target.write_text(text, encoding="utf-8")
        written.append((CASES_REL / filename).as_posix())
    return written


# --------------------------------------------------------------------------- TST-0299 families
def candidate_id(index: int) -> str:
    return f"wf-{index:02d}"


def null_field(
    seed: int, n_cases: int = N_CASES, family_size: int = FAMILY_SIZE
) -> tuple[list[float], list[dict[str, Any]]]:
    """Baseline scores plus ``family_size`` candidates that differ from it by paired noise only."""
    if n_cases < 2 or family_size < 1:
        raise TournamentError(
            f"need n_cases >= 2 and family_size >= 1, got {n_cases}, {family_size}"
        )
    rng = random.Random(seed)
    baseline = [round(rng.gauss(BASELINE_MEAN, BASELINE_SD), 6) for _ in range(n_cases)]
    candidates: list[dict[str, Any]] = []
    for j in range(family_size):
        scores = [round(b + rng.gauss(0.0, NOISE_SD), 6) for b in baseline]
        candidates.append(
            {"id": candidate_id(j), "scores": scores, "planted_effect": 0.0}
        )
    return baseline, candidates


def run_tournament(
    kind: str,
    seed: int,
    baseline: Sequence[float],
    candidates: Sequence[Mapping[str, Any]],
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """Paired-t p-value per candidate, then BH + Holm over the whole family."""
    ids = [str(c["id"]) for c in candidates]
    ps = [paired_mean_greater_p(baseline, c["scores"]) for c in candidates]
    family = correct_family(ps, ids=ids, alpha=alpha)
    return {
        "unit_id": UNIT_ID,
        "kind": kind,
        "seed": seed,
        "alpha": float(alpha),
        "n_cases": len(baseline),
        "family_size": family["family_size"],
        "baseline": list(baseline),
        "candidates": [dict(c) for c in candidates],
        "family": family,
    }


def null_identical_tournament(seed: int = NULL_SEED) -> dict[str, Any]:
    """Forty candidates scored identically to the baseline: every p is 1, nothing is discovered."""
    baseline, _ = null_field(seed)
    candidates = [
        {"id": candidate_id(j), "scores": list(baseline), "planted_effect": 0.0}
        for j in range(FAMILY_SIZE)
    ]
    return run_tournament(KIND_NULL_IDENTICAL, seed, baseline, candidates)


def null_iid_tournament(seed: int = NULL_SEED) -> dict[str, Any]:
    """Forty iid null candidates: a few uncorrected winners by chance, none after BH or Holm."""
    baseline, candidates = null_field(seed)
    return run_tournament(KIND_NULL_IID, seed, baseline, candidates)


def mixed_tournament(seed: int = MIXED_SEED) -> dict[str, Any]:
    """The null field with ``TRUE_EFFECT`` planted on the first ``N_TRUE`` candidates.

    Returns the family plus the live (Holm-consuming) and mutant (uncorrected-consuming)
    certification gates, the planted ids, the chance winners and the shrink after correction.
    """
    baseline, candidates = null_field(seed)
    true_ids: list[str] = []
    for cand in candidates[:N_TRUE]:
        cand["scores"] = [round(s + TRUE_EFFECT, 6) for s in cand["scores"]]
        cand["planted_effect"] = TRUE_EFFECT
        true_ids.append(str(cand["id"]))
    run = run_tournament(KIND_MIXED, seed, baseline, candidates)
    rows = run["family"]["comparisons"]
    live = certification_gate(rows, consume="corrected")
    mutant = mutant_reads_uncorrected(rows)
    run.update(
        {
            "true_ids": true_ids,
            "true_effect": TRUE_EFFECT,
            "live_gate": live,
            "mutant_gate": mutant,
            "uncorrected_certified_ids": list(mutant["certified_ids"]),
            "holm_certified_ids": list(live["certified_ids"]),
            "lucky_uncorrected_only_ids": lucky_uncorrected_only(rows),
            "shrink_delta": mutant["certified_count"] - live["certified_count"],
            "certification_list_shrinks": mutant["certified_count"]
            > live["certified_count"],
        }
    )
    return run


def ledger_row(run: Mapping[str, Any]) -> dict[str, Any]:
    """Append-only ledger entry: raw per-case scores plus the family verdicts to recompute them."""
    family = run["family"]
    return {
        "unit_id": UNIT_ID,
        "kind": run["kind"],
        "seed": run["seed"],
        "alpha": run["alpha"],
        "n_cases": run["n_cases"],
        "family_size": family["family_size"],
        "correction_methods": list(family["correction_methods"]),
        "baseline": list(run["baseline"]),
        "candidates": [
            {
                "id": c["id"],
                "scores": list(c["scores"]),
                "planted_effect": c.get("planted_effect", 0.0),
            }
            for c in run["candidates"]
        ],
        "comparisons": family["comparisons"],
        "uncorrected_discovery_count": family["uncorrected_discovery_count"],
        "bh_discovery_count": family["bh_discovery_count"],
        "holm_certified_count": family["holm_certified_count"],
        "true_ids": list(run.get("true_ids") or []),
    }


def main() -> int:
    report = evaluate_field(planted_cycle_scores())
    print(
        json.dumps(
            {
                "cycles": report.cycles,
                "ranking_kind": report.ranking_kind,
                "binding_leaderboard": report.binding_leaderboard,
                "matrix": {k: v.to_dict() for k, v in report.matrix.items()},
            }
        )
    )
    return 0


__all__ = [
    "ALPHA",
    "CaseScore",
    "ELIMINATION",
    "FAMILY_SIZE",
    "FieldReport",
    "INSUFFICIENT_BUDGET",
    "MIXED_SEED",
    "NULL_SEED",
    "N_CASES",
    "PARTIAL_ORDER",
    "PICK_ROUND_ROBIN",
    "PairCell",
    "PUBLISH_LEADERBOARD",
    "REPORT_FIELD_FINDING",
    "ROUND_ROBIN",
    "SCHEDULE_DISAGREEMENT",
    "SMALL_FIELD_MAX",
    "SWISS",
    "ScheduleResult",
    "TOTAL_ORDER",
    "TRUE_EFFECT",
    "TournamentError",
    "beats_graph",
    "compare_schedulers",
    "copeland_scores",
    "enumerate_cycles",
    "evaluate_field",
    "fixture_doc",
    "hides_nontransitivity",
    "ledger_row",
    "mixed_tournament",
    "mutant_hide_cycle",
    "mutant_pick_round_robin",
    "null_field",
    "null_identical_tournament",
    "null_iid_tournament",
    "pair_budget_requirements",
    "pair_key",
    "pairwise_matrix",
    "planted_cycle_scores",
    "round_robin",
    "run_tournament",
    "schedule_unstable_scores",
    "schedules_agree",
    "scores_from_fixture_doc",
    "select_format",
    "silently_resolves_schedule",
    "swiss",
    "swiss_rounds",
    "transitive_scores",
    "write_case_corpus",
]


if __name__ == "__main__":
    raise SystemExit(main())
