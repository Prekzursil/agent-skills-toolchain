"""Evidence gate for council votes: a ballot that cites no resolvable evidence does not count.

Rule (scheme ``council.vote.evidence-gate.non-counting-unbacked-v1``): agreement is not
proof.  A ballot is *backed* only when it cites at least one evidence anchor and every cited
anchor resolves.  Unbacked ballots are recorded and annotated but are **non-counting**: the
binding outcome is the unique maximum of the tally over backed ballots only.  A numerically
superior but evidence-free majority is therefore blocked, while a well-anchored minority
binds.  When every ballot is backed the gate reduces to the ordinary unique-max tally, so it
never silently inverts a fully-evidenced vote (the "both states" property).

Two resolution back-ends share the same gate:

* an in-memory :class:`CouncilGraph` of :class:`EvidenceNode` objects (``resolves`` flag),
  used by :func:`decide` and the TST-0262 controls;
* an anchor registry ``{evidence_id: path}`` scoped to an evidence ``root`` directory, used
  by :func:`evaluate_gate` / :func:`anchor_resolution_pass` (IMP-0307).  Anchors are checked
  with ``os.stat``; ``file://`` URIs are stat'ed after URI decoding; ``http(s)://`` and DOI
  citations are **never fetched** (hermetic) and stay unresolved.

The plausibility heuristic :func:`citation_looks_plausible` exists only for reporting.  The
gate never consults it: a citation that merely *looks* like evidence is still unbacked.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlparse

SCHEME_ID = "council.vote.evidence-gate.non-counting-unbacked-v1"

# Choices used by the required controls (TST-0262).
MAJORITY_CHOICE = "keep-legacy-heuristic"
MINORITY_CHOICE = "require-executable-evidence"
REAL_EVIDENCE_ID = "EV-EXECUTABLE-COUNTEREXAMPLE"
FABRICATED_EVIDENCE_ID = "EV-FABRICATED-MAJORITY-STUDY"

# Gate reasons.
BIND_BACKED_TALLY = "BIND_BACKED_TALLY"
BLOCK_EVIDENCE_FREE_MAJORITY = "BLOCK_EVIDENCE_FREE_MAJORITY"
NO_BACKED_BALLOTS = "NO_BACKED_BALLOTS"

# Resolution reasons.
REASON_RESOLVES = "resolves"
REASON_NO_CITATION = "no-citation"
REASON_UNKNOWN_ID = "unknown-id"
REASON_DOES_NOT_RESOLVE = "does-not-resolve"
REASON_ANCHOR_MISSING = "anchor-missing"
REASON_OUTSIDE_ROOT = "outside-root"
REASON_NO_FETCH = "no-fetch-hermetic"
REASON_NOT_A_FILE = "not-a-file"

STATUS_BACKED = "backed-counting"
STATUS_UNBACKED = "unbacked-non-counting"

POLICY: Mapping[str, Any] = MappingProxyType(
    {
        "scheme": SCHEME_ID,
        "agreement_is_not_proof": True,
        "unbacked_ballots_are_non_counting": True,
        "well_anchored_minority_binds": True,
        "fully_backed_vote_follows_plurality": True,
        "plausibility_heuristic_may_gate": False,
        "network_fetch": "never",
        "anchor_check": "os.stat within the evidence root; file:// decoded then stat",
    }
)

_PLAUSIBILITY_CALLS = 0

_ID_RE = re.compile(r"^[A-Za-z]{1,12}-[A-Za-z0-9][A-Za-z0-9._:-]*$")
_DOI_RE = re.compile(r"(?:^|/)10\.\d{4,9}/\S+$")
_REMOTE_SCHEMES = frozenset({"http", "https", "doi", "ftp", "ftps"})


# --------------------------------------------------------------------------- data model


@dataclass(frozen=True)
class Ballot:
    """One vote: who, for which position, citing which evidence anchors.

    Constructed positionally (``Ballot("v", "choice", ("EV-1",))``) or by keyword
    (``Ballot(voter_id=..., position=..., citations=...)``).  ``citations`` is normalised to
    a tuple of stripped strings; empty entries are dropped.
    """

    voter_id: str
    position: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.voter_id, str) or not self.voter_id.strip():
            raise ValueError("Ballot.voter_id must be a non-empty string")
        if not isinstance(self.position, str) or not self.position.strip():
            raise ValueError("Ballot.position must be a non-empty string")
        if isinstance(self.citations, str):
            raw: Iterable[Any] = (self.citations,)
        else:
            raw = tuple(self.citations or ())
        cleaned = tuple(str(c).strip() for c in raw if str(c).strip())
        object.__setattr__(self, "citations", cleaned)

    @property
    def choice(self) -> str:
        """Alias for :attr:`position` (TST-0262 vocabulary)."""
        return self.position

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """Alias for :attr:`citations` (TST-0262 vocabulary)."""
        return self.citations

    def to_dict(self) -> dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "position": self.position,
            "citations": list(self.citations),
        }


@dataclass(frozen=True)
class EvidenceNode:
    """An evidence node in a :class:`CouncilGraph`; ``resolves`` says whether its anchor holds."""

    id: str
    kind: str = "citation"
    body: str = ""
    resolves: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("EvidenceNode.id must be a non-empty string")


class CouncilGraph:
    """Insertion-ordered map of evidence id -> :class:`EvidenceNode`; duplicate ids are refused."""

    def __init__(self, nodes: Iterable[EvidenceNode] = ()) -> None:
        self._nodes: dict[str, EvidenceNode] = {}
        for node in nodes:
            self.add(node)

    def add(self, node: EvidenceNode) -> EvidenceNode:
        if not isinstance(node, EvidenceNode):
            raise TypeError(f"CouncilGraph.add expects EvidenceNode, got {type(node).__name__}")
        if node.id in self._nodes:
            raise ValueError(f"duplicate evidence id {node.id!r}")
        self._nodes[node.id] = node
        return node

    def get(self, node_id: str, default: Any = None) -> EvidenceNode | Any:
        return self._nodes.get(node_id, default)

    def ids(self) -> list[str]:
        return list(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self):
        return iter(self._nodes.values())

    def resolve(self, evidence_id: str) -> Resolution:
        """Resolve one id against the graph: unknown-id / does-not-resolve / resolves."""
        if not evidence_id:
            return Resolution(evidence_id, False, "graph-node", REASON_NO_CITATION, "empty citation")
        node = self._nodes.get(evidence_id)
        if node is None:
            return Resolution(evidence_id, False, "graph-node", REASON_UNKNOWN_ID, "id not in graph")
        if not node.resolves:
            return Resolution(
                evidence_id, False, "graph-node", REASON_DOES_NOT_RESOLVE, "node anchor does not resolve"
            )
        return Resolution(evidence_id, True, "graph-node", REASON_RESOLVES, None, anchor=node.id)


@dataclass(frozen=True)
class Resolution:
    """Outcome of resolving one citation."""

    citation: str
    resolved: bool
    method: str
    reason: str
    error: str | None = None
    anchor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- plausibility


def citation_looks_plausible(citation: Any) -> bool:
    """Heuristic only: does the string *look* like a citation (id, URL, DOI or file path)?

    Every call is counted so the gate can prove it never consulted this heuristic.
    """
    global _PLAUSIBILITY_CALLS
    _PLAUSIBILITY_CALLS += 1
    if not isinstance(citation, str):
        return False
    text = citation.strip()
    if not text or any(ch.isspace() for ch in text):
        return False
    if _ID_RE.match(text):
        return True
    parsed = urlparse(text)
    if parsed.scheme and (parsed.netloc or parsed.path):
        return parsed.scheme.lower() in _REMOTE_SCHEMES | {"file"}
    if _DOI_RE.search(text):
        return True
    path = Path(text)
    return ("/" in text or os.sep in text) and bool(path.suffix)


def plausibility_calls() -> int:
    """Number of times :func:`citation_looks_plausible` has been invoked in this process."""
    return _PLAUSIBILITY_CALLS


# --------------------------------------------------------------------------- anchor resolution


def _stat_anchor(path: Path, method: str, citation: str, root: Path | None) -> Resolution:
    try:
        st = os.stat(path)
    except OSError as exc:
        return Resolution(citation, False, method, REASON_ANCHOR_MISSING, f"{type(exc).__name__}: {exc}")
    if not path.is_file():
        return Resolution(citation, False, method, REASON_NOT_A_FILE, "anchor is not a regular file")
    if root is not None:
        try:
            path.resolve().relative_to(Path(root).resolve())
        except ValueError:
            return Resolution(
                citation, False, method, REASON_OUTSIDE_ROOT, "anchor lies outside the evidence root"
            )
    if st.st_size <= 0:
        return Resolution(citation, False, method, REASON_ANCHOR_MISSING, "anchor file is empty")
    return Resolution(citation, True, method, REASON_RESOLVES, None, anchor=str(path))


def resolve_citation(
    citation: str,
    graph: Mapping[str, str] | CouncilGraph | None,
    root: str | os.PathLike[str] | None = None,
) -> Resolution:
    """Resolve one citation without any network access.

    * :class:`CouncilGraph` -> node lookup (``unknown-id`` / ``does-not-resolve`` / ``resolves``).
    * Registry mapping ``id -> path`` -> the registered path is ``os.stat``-ed (``registry-stat``).
      A registered id whose path is absent is a planted lie and stays unresolved.
    * ``file://`` URI -> decoded path is ``os.stat``-ed (``file-uri-stat``).
    * ``http(s)://``, ``doi:``, ``ftp://`` or bare DOI -> ``no-fetch-hermetic``, never resolved.
    * anything else -> treated as a path under ``root`` (``path-stat``).

    Path anchors must exist, be non-empty regular files and lie inside ``root`` when a root is
    given.
    """
    if citation is None or not str(citation).strip():
        return Resolution(str(citation or ""), False, "none", REASON_NO_CITATION, "empty citation")
    cite = str(citation).strip()
    root_path = Path(root) if root is not None else None
    if isinstance(graph, CouncilGraph):
        return graph.resolve(cite)
    registry = graph or {}
    if cite in registry:
        target = Path(str(registry[cite]))
        if not target.is_absolute() and root_path is not None:
            target = root_path / target
        return _stat_anchor(target, "registry-stat", cite, root_path)
    parsed = urlparse(cite)
    scheme = parsed.scheme.lower()
    if scheme == "file":
        target = Path(unquote(parsed.path))
        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            return Resolution(cite, False, "file-uri-stat", REASON_NO_FETCH, "remote file host is not fetched")
        return _stat_anchor(target, "file-uri-stat", cite, root_path)
    if scheme in _REMOTE_SCHEMES or _DOI_RE.search(cite):
        return Resolution(cite, False, "no-fetch-hermetic", REASON_NO_FETCH, "network fetch disabled")
    if _ID_RE.match(cite) and "/" not in cite and os.sep not in cite and not Path(cite).suffix:
        return Resolution(cite, False, "registry-lookup", REASON_UNKNOWN_ID, "id not registered")
    target = Path(cite)
    if not target.is_absolute() and root_path is not None:
        target = root_path / target
    return _stat_anchor(target, "path-stat", cite, root_path)


def resolve_ballot(
    ballot: Ballot,
    graph: Mapping[str, str] | CouncilGraph | None,
    root: str | os.PathLike[str] | None = None,
) -> list[Resolution]:
    """Resolve every citation of a ballot; a ballot with no citations yields one ``no-citation`` row."""
    if not ballot.citations:
        return [Resolution("", False, "none", REASON_NO_CITATION, "ballot cites nothing")]
    return [resolve_citation(cite, graph, root) for cite in ballot.citations]


def is_backed(resolutions: Iterable[Resolution]) -> bool:
    """Backed = at least one citation and every citation resolved."""
    rows = list(resolutions)
    return bool(rows) and all(r.resolved and r.reason != REASON_NO_CITATION for r in rows)


def anchor_resolution_pass(
    ballots: Iterable[Ballot],
    graph: Mapping[str, str] | CouncilGraph | None,
    root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Census of every citation across the ballots.

    Returns ``cited_count`` (citations offered), ``resolved_count``, ``unresolved`` (unresolved
    citations plus one ``no-citation:<voter>`` marker per ballot that cites nothing),
    ``unresolved_count``, ``resolved`` and a ``per_ballot`` breakdown, in ballot order.
    """
    cited = 0
    resolved: list[str] = []
    unresolved: list[str] = []
    per_ballot: list[dict[str, Any]] = []
    for ballot in ballots:
        rows = resolve_ballot(ballot, graph, root)
        for res in rows:
            if res.reason == REASON_NO_CITATION:
                unresolved.append(f"no-citation:{ballot.voter_id}")
                continue
            cited += 1
            (resolved if res.resolved else unresolved).append(res.citation)
        per_ballot.append(
            {
                "voter_id": ballot.voter_id,
                "position": ballot.position,
                "citations": list(ballot.citations),
                "backed": is_backed(rows),
                "resolutions": [r.to_dict() for r in rows],
            }
        )
    return {
        "cited_count": cited,
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolved": resolved,
        "unresolved": unresolved,
        "per_ballot": per_ballot,
    }


# --------------------------------------------------------------------------- tallies


def _unique_max(tally: Mapping[str, int]) -> str | None:
    """The single position with the highest count, or ``None`` when empty or tied."""
    if not tally:
        return None
    top = max(tally.values())
    leaders = [pos for pos, n in tally.items() if n == top]
    return leaders[0] if len(leaders) == 1 else None


def _sorted_tally(counter: Counter[str]) -> dict[str, int]:
    return {pos: counter[pos] for pos in sorted(counter)}


def counting_tally(
    ballots: Iterable[Ballot],
    graph: Mapping[str, str] | CouncilGraph | None,
    root: str | os.PathLike[str] | None = None,
) -> dict[str, int]:
    """Tally over backed ballots only (the counting tally)."""
    counter: Counter[str] = Counter()
    for ballot in ballots:
        if is_backed(resolve_ballot(ballot, graph, root)):
            counter[ballot.position] += 1
    return _sorted_tally(counter)


@dataclass
class GateResult:
    """Result of :func:`evaluate_gate`."""

    raw_tally: dict[str, int]
    raw_winner: str | None
    backed_tally: dict[str, int]
    gated_tally: dict[str, int]
    gated_winner: str | None
    well_anchored_positions: list[str]
    evidence_free_positions: list[str]
    evidence_free_majority_blocked: bool
    well_anchored_minority_blocked: bool
    binding: bool
    reason: str
    n_ballots: int
    n_backed: int
    n_unbacked: int
    cited_count: int
    resolved_count: int
    unresolved: list[str]
    fabricated_caught: list[str]
    plausible_heuristic_consulted: bool
    policy: dict[str, Any] = field(default_factory=lambda: dict(POLICY))
    scheme: str = SCHEME_ID

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_gate(
    ballots: Iterable[Ballot],
    graph: Mapping[str, str] | CouncilGraph | None,
    root: str | os.PathLike[str] | None = None,
) -> GateResult:
    """Apply the evidence gate to ``ballots`` against an anchor registry or graph.

    The raw tally counts every ballot; the backed (gated) tally counts only ballots whose
    every citation resolves.  The gated winner is the unique maximum of the backed tally.
    ``evidence_free_majority_blocked`` is true when the raw winner has zero backed ballots;
    ``reason`` is then :data:`BLOCK_EVIDENCE_FREE_MAJORITY`, otherwise
    :data:`BIND_BACKED_TALLY` (or :data:`NO_BACKED_BALLOTS` when nothing is backed).
    """
    calls_before = _PLAUSIBILITY_CALLS
    rows = list(ballots)
    census = anchor_resolution_pass(rows, graph, root)
    raw: Counter[str] = Counter(b.position for b in rows)
    backed: Counter[str] = Counter(
        entry["position"] for entry in census["per_ballot"] if entry["backed"]
    )
    raw_tally = _sorted_tally(raw)
    backed_tally = _sorted_tally(backed)
    raw_winner = _unique_max(raw_tally)
    gated_winner = _unique_max(backed_tally)
    well_anchored = sorted(pos for pos, n in backed_tally.items() if n > 0)
    evidence_free = sorted(pos for pos in raw_tally if backed_tally.get(pos, 0) == 0)
    evidence_free_majority_blocked = raw_winner is not None and raw_winner in evidence_free
    minority_blocked = any(pos not in backed_tally for pos in well_anchored)
    n_backed = sum(backed_tally.values())
    if n_backed == 0:
        reason = NO_BACKED_BALLOTS
    elif evidence_free_majority_blocked:
        reason = BLOCK_EVIDENCE_FREE_MAJORITY
    else:
        reason = BIND_BACKED_TALLY
    fabricated = [c for c in census["unresolved"] if not c.startswith("no-citation:")]
    return GateResult(
        raw_tally=raw_tally,
        raw_winner=raw_winner,
        backed_tally=backed_tally,
        gated_tally=dict(backed_tally),
        gated_winner=gated_winner,
        well_anchored_positions=well_anchored,
        evidence_free_positions=evidence_free,
        evidence_free_majority_blocked=evidence_free_majority_blocked,
        well_anchored_minority_blocked=minority_blocked,
        binding=gated_winner is not None,
        reason=reason,
        n_ballots=len(rows),
        n_backed=n_backed,
        n_unbacked=len(rows) - n_backed,
        cited_count=census["cited_count"],
        resolved_count=census["resolved_count"],
        unresolved=list(census["unresolved"]),
        fabricated_caught=fabricated,
        plausible_heuristic_consulted=_PLAUSIBILITY_CALLS != calls_before,
    )


# --------------------------------------------------------------------------- decision records


def _ballot_row(ballot: Ballot, graph: CouncilGraph) -> dict[str, Any]:
    resolutions = resolve_ballot(ballot, graph)
    backed = is_backed(resolutions)
    return {
        "voter_id": ballot.voter_id,
        "choice": ballot.position,
        "evidence_ids": list(ballot.citations),
        "backed": backed,
        "counts": backed,
        "status": STATUS_BACKED if backed else STATUS_UNBACKED,
        "resolving_ids": [r.citation for r in resolutions if r.resolved],
        "resolutions": [
            {"evidence_id": r.citation or None, "resolved": r.resolved, "reason": r.reason}
            for r in resolutions
        ],
    }


def _why(
    n_unbacked: int,
    counting: Mapping[str, int],
    raw: Mapping[str, int],
    outcome: str | None,
    raw_winner: str | None,
    annotated_winner: str | None,
) -> list[str]:
    why: list[str] = []
    if n_unbacked:
        why.append(f"{n_unbacked} unbacked ballot(s) are non-counting (not merely annotated).")
    if outcome is None:
        if not counting:
            why.append("No ballot is evidence-backed; the counting tally is empty and nothing binds.")
        else:
            why.append("Counting tally has no unique maximum; the outcome is a non-binding tie.")
    else:
        why.append(
            f"Counting tally unique-max is {outcome} with {counting[outcome]} evidence-backed vote(s)."
        )
        if raw_winner is not None and raw_winner != outcome:
            why.append(
                f"Backed position {outcome} was numerically outvoted "
                f"({raw.get(outcome, 0)} raw vs {raw.get(raw_winner, 0)} raw for {raw_winner}); "
                "the gate outranks popularity."
            )
        elif raw_winner is None and any(raw.get(p, 0) > raw.get(outcome, 0) for p in raw):
            why.append(f"Backed position {outcome} was outvoted in the raw tally; the gate outranks popularity.")
    if n_unbacked == 0 and counting:
        why.append(
            "Every counting ballot is backed; ordinary unique-max tally decides "
            "(the gate does not silently invert a fully-backed vote)."
        )
    elif n_unbacked and annotated_winner != outcome:
        why.append(
            "Annotation-only tally disagrees with the counting tally; prove-by-contrast that the "
            "gate does not count unbacked ballots."
        )
    return why


def decide(graph: CouncilGraph, ballots: Iterable[Ballot], election_id: str) -> dict[str, Any]:
    """Run one election under the gate and return the full decision record.

    ``raw_tally`` counts every ballot, ``counting_tally`` only backed ballots, and
    ``annotated_only_tally`` shows what a gate that merely annotated unbacked ballots would
    have counted (identical to the raw tally).  ``outcome`` is the unique maximum of the
    counting tally (``None`` when empty or tied, in which case ``binding`` is false).
    """
    if not isinstance(graph, CouncilGraph):
        raise TypeError("decide() requires a CouncilGraph")
    if not isinstance(election_id, str) or not election_id.strip():
        raise ValueError("election_id must be a non-empty string")
    rows = [_ballot_row(b, graph) for b in ballots]
    raw_counter: Counter[str] = Counter(r["choice"] for r in rows)
    counting_counter: Counter[str] = Counter(r["choice"] for r in rows if r["counts"])
    raw_tally = _sorted_tally(raw_counter)
    counting = _sorted_tally(counting_counter)
    annotated_only = dict(raw_tally)
    raw_winner = _unique_max(raw_tally)
    annotated_winner = _unique_max(annotated_only)
    outcome = _unique_max(counting)
    n_backed = sum(1 for r in rows if r["backed"])
    n_unbacked = len(rows) - n_backed
    why = _why(n_unbacked, counting, raw_tally, outcome, raw_winner, annotated_winner)
    return {
        "scheme": SCHEME_ID,
        "election_id": election_id,
        "n_ballots": len(rows),
        "n_backed": n_backed,
        "n_unbacked": n_unbacked,
        "raw_tally": raw_tally,
        "counting_tally": counting,
        "annotated_only_tally": annotated_only,
        "raw_winner": {"outcome": raw_winner, "tally": raw_tally, "unique_max": raw_winner is not None},
        "annotated_only_winner": {
            "outcome": annotated_winner,
            "tally": annotated_only,
            "unique_max": annotated_winner is not None,
        },
        "outcome": outcome,
        "binding": outcome is not None,
        "gate_outranks_popularity": outcome is not None and raw_winner != outcome,
        "why": why,
        "why_text": " ".join(why),
        "ballots": rows,
    }


# --------------------------------------------------------------------------- required controls


def _real_graph() -> CouncilGraph:
    return CouncilGraph(
        [
            EvidenceNode(
                id=REAL_EVIDENCE_ID,
                kind="executable-counterexample",
                body="pytest -q tests/test_heuristic_counterexample.py::test_legacy_heuristic_misfires",
                resolves=True,
            )
        ]
    )


def majority_unbacked_fixture() -> tuple[CouncilGraph, list[Ballot]]:
    """7 unbacked majority ballots versus 2 minority ballots backed by the real node."""
    graph = _real_graph()
    ballots = [Ballot(f"unbacked-{i:02d}", MAJORITY_CHOICE, ()) for i in range(1, 8)]
    ballots += [
        Ballot("backed-min-01", MINORITY_CHOICE, (REAL_EVIDENCE_ID,)),
        Ballot("backed-min-02", MINORITY_CHOICE, (REAL_EVIDENCE_ID,)),
    ]
    return graph, ballots


def both_states_all_backed_fixture() -> tuple[CouncilGraph, list[Ballot]]:
    """The same 7-2 split with every ballot backed: ordinary plurality must decide."""
    graph = _real_graph()
    ballots = [Ballot(f"backed-maj-{i:02d}", MAJORITY_CHOICE, (REAL_EVIDENCE_ID,)) for i in range(1, 8)]
    ballots += [
        Ballot("backed-min-01", MINORITY_CHOICE, (REAL_EVIDENCE_ID,)),
        Ballot("backed-min-02", MINORITY_CHOICE, (REAL_EVIDENCE_ID,)),
    ]
    return graph, ballots


def fabricated_citation_fixture() -> tuple[CouncilGraph, list[Ballot]]:
    """One ballot citing an id absent from the graph versus one backed ballot."""
    graph = _real_graph()
    ballots = [
        Ballot("fabricator", MAJORITY_CHOICE, (FABRICATED_EVIDENCE_ID,)),
        Ballot("backed-minority", MINORITY_CHOICE, (REAL_EVIDENCE_ID,)),
    ]
    return graph, ballots


def run_required_controls() -> dict[str, Any]:
    """Run the three required controls and return a report with their decision records."""
    g1, b1 = majority_unbacked_fixture()
    g2, b2 = both_states_all_backed_fixture()
    g3, b3 = fabricated_citation_fixture()
    rec1 = decide(g1, b1, election_id="TST-0262-7v2-unbacked-majority")
    rec2 = decide(g2, b2, election_id="TST-0262-both-states-all-backed")
    rec3 = decide(g3, b3, election_id="TST-0262-fabricated-citation")
    controls = [
        {"id": "minority-wins", "pass": rec1["outcome"] == MINORITY_CHOICE},
        {"id": "both-states-does-not-invert", "pass": rec2["outcome"] == MAJORITY_CHOICE},
        {"id": "evidence-required", "pass": rec3["outcome"] == MINORITY_CHOICE},
    ]
    report = {
        "scheme": SCHEME_ID,
        "minority_vs_unbacked_majority": rec1,
        "both_states_all_backed": rec2,
        "fabricated_citation": rec3,
        "raw_majority_votes": rec1["raw_tally"].get(MAJORITY_CHOICE, 0),
        "raw_minority_votes": rec1["raw_tally"].get(MINORITY_CHOICE, 0),
        "counting_majority_votes": rec1["counting_tally"].get(MAJORITY_CHOICE, 0),
        "backed_minority_votes": rec1["counting_tally"].get(MINORITY_CHOICE, 0),
        "gated_outcome": rec1["outcome"],
        "both_states_outcome": rec2["outcome"],
        "fabricated_outcome": rec3["outcome"],
        "controls": controls,
        "minority_wins": rec1["outcome"] == MINORITY_CHOICE,
    }
    report["pass"] = report["ok"] = not assertions(report)
    return report


def assertions(report: Mapping[str, Any]) -> list[str]:
    """Check a :func:`run_required_controls` report; returns the list of violated assertions."""
    fails: list[str] = []
    rec1 = report.get("minority_vs_unbacked_majority") or {}
    rec2 = report.get("both_states_all_backed") or {}
    rec3 = report.get("fabricated_citation") or {}
    if rec1.get("outcome") != MINORITY_CHOICE:
        fails.append(f"7v2: gated outcome {rec1.get('outcome')!r} != {MINORITY_CHOICE}")
    if (rec1.get("raw_tally") or {}).get(MAJORITY_CHOICE) != 7 or (rec1.get("raw_tally") or {}).get(MINORITY_CHOICE) != 2:
        fails.append(f"7v2: raw tally {rec1.get('raw_tally')} is not 7 vs 2")
    if (rec1.get("counting_tally") or {}).get(MAJORITY_CHOICE, 0) != 0:
        fails.append("7v2: unbacked majority leaked into the counting tally")
    if (rec1.get("counting_tally") or {}).get(MINORITY_CHOICE) != 2:
        fails.append("7v2: backed minority not fully counted")
    if (rec1.get("annotated_only_winner") or {}).get("outcome") != MAJORITY_CHOICE:
        fails.append("7v2: annotation-only contrast lost the majority")
    if not rec1.get("binding"):
        fails.append("7v2: backed minority did not bind")
    if rec2.get("outcome") != MAJORITY_CHOICE:
        fails.append(f"both-states: fully backed vote inverted to {rec2.get('outcome')!r}")
    if rec2.get("gate_outranks_popularity"):
        fails.append("both-states: gate claimed to outrank a fully backed tally")
    fabricator = next((b for b in rec3.get("ballots") or [] if b.get("voter_id") == "fabricator"), None)
    if fabricator is None:
        fails.append("fabricated: fabricator ballot missing")
    else:
        if fabricator.get("backed") or fabricator.get("counts"):
            fails.append("fabricated: ballot citing an unknown id was counted")
        if {r.get("reason") for r in fabricator.get("resolutions") or []} != {REASON_UNKNOWN_ID}:
            fails.append("fabricated: resolution reason is not unknown-id")
    if rec3.get("outcome") != MINORITY_CHOICE:
        fails.append(f"fabricated: outcome {rec3.get('outcome')!r} != {MINORITY_CHOICE}")
    return fails


__all__ = [
    "BIND_BACKED_TALLY",
    "BLOCK_EVIDENCE_FREE_MAJORITY",
    "Ballot",
    "CouncilGraph",
    "EvidenceNode",
    "FABRICATED_EVIDENCE_ID",
    "GateResult",
    "MAJORITY_CHOICE",
    "MINORITY_CHOICE",
    "NO_BACKED_BALLOTS",
    "POLICY",
    "REAL_EVIDENCE_ID",
    "Resolution",
    "SCHEME_ID",
    "anchor_resolution_pass",
    "assertions",
    "both_states_all_backed_fixture",
    "citation_looks_plausible",
    "counting_tally",
    "decide",
    "evaluate_gate",
    "fabricated_citation_fixture",
    "is_backed",
    "majority_unbacked_fixture",
    "plausibility_calls",
    "resolve_ballot",
    "resolve_citation",
    "run_required_controls",
]
