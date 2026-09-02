"""Minimum vendor/model diversity as a hard constraint with an explicit waiver (IMP-0272).

The solver seats a council from a pool of participants so that the seated
roster reaches the requested number of distinct vendors and distinct models.
When the reachable pool cannot satisfy the request the council still runs --
a single-vendor council is better than no council -- but the seating artifact
must say so out loud: it carries a waiver record and reports that its
independence assumption is ``void``.  :func:`check_artifact` is the reviewer's
gate: a diversity shortfall whose waiver was suppressed (or stripped after the
fact) fails with ``diversity_shortfall_without_waiver``.

Falsifiable question the unit answers: when only one vendor is reachable, does
the council run anyway while REPORTING that its independence assumption is
void?  :func:`run_matrix` case ``I1-one-vendor-reachable`` is that experiment.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

VOID = "void"
INTACT = "intact"

CHECK_OK = "ok"
SHORTFALL_WITHOUT_WAIVER = "diversity_shortfall_without_waiver"
STRAY_WAIVER = "waiver_without_shortfall"
INDEPENDENCE_MISREPORTED = "independence_assumption_misreported"
WAIVER_DOES_NOT_VOID = "waiver_does_not_void_independence"
COUNCIL_DID_NOT_RUN = "council_did_not_run"

WAIVER_KIND = "diversity-shortfall-waiver"
DEFAULT_MIN_VENDORS = 2
DEFAULT_MIN_MODELS = 2


@dataclass
class SeatingArtifact:
    """What the diversity solver hands to the council runtime and the reviewer."""

    seats: list[dict[str, Any]]
    requested: dict[str, int]
    observed: dict[str, int]
    vendors: list[str]
    models: list[str]
    vendor_diverse: bool
    model_diverse: bool
    seats_filled: bool
    feasible: bool
    independence_assumption: str
    council_ran: bool
    waiver: dict[str, Any] | None = None
    shortfall: dict[str, int] = field(default_factory=dict)
    unreachable: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:  # dict-style access for probes and JSON views
        return getattr(self, key)


def _get(art: Any, key: str, default: Any = None) -> Any:
    if isinstance(art, Mapping):
        return art.get(key, default)
    return getattr(art, key, default)


def _reachable(pool: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    reachable: list[dict[str, Any]] = []
    unreachable: list[str] = []
    for p in pool:
        row = dict(p)
        if row.get("reachable", True):
            reachable.append(row)
        else:
            unreachable.append(str(row.get("id")))
    return reachable, unreachable


def _normalise_constraint(constraint: Mapping[str, Any] | None, pool_size: int) -> dict[str, int]:
    c = dict(constraint or {})
    seat_count = int(c.get("seat_count") or pool_size)
    return {
        "min_vendors": int(c.get("min_vendors", DEFAULT_MIN_VENDORS)),
        "min_models": int(c.get("min_models", DEFAULT_MIN_MODELS)),
        "seat_count": max(seat_count, 0),
    }


def pick_seats(reachable: list[dict[str, Any]], seat_count: int) -> list[dict[str, Any]]:
    """Greedy, deterministic seating that maximises vendor then model spread.

    Each pass takes the first pool entry (in pool order) that adds a vendor not
    yet seated; when no vendor is new it takes one adding a new model; when
    nothing new is left it fills remaining seats in pool order.  Pool order is
    the only tie-break, so the same pool always yields the same roster.
    """
    seats: list[dict[str, Any]] = []
    remaining = list(reachable)
    while remaining and len(seats) < seat_count:
        vendors = {s.get("vendor") for s in seats}
        models = {(s.get("vendor"), s.get("model")) for s in seats}
        choice = next((p for p in remaining if p.get("vendor") not in vendors), None)
        if choice is None:
            choice = next(
                (p for p in remaining if (p.get("vendor"), p.get("model")) not in models), None
            )
        if choice is None:
            choice = remaining[0]
        seats.append(choice)
        remaining.remove(choice)
    return seats


def make_waiver(requested: Mapping[str, int], observed: Mapping[str, int], shortfall: Mapping[str, int]) -> dict[str, Any]:
    """The explicit record that the diversity floor was not met."""
    return {
        "kind": WAIVER_KIND,
        "requested": dict(requested),
        "observed": dict(observed),
        "shortfall": dict(shortfall),
        "independence_assumption": VOID,
        "statement": (
            "Council ran below the requested vendor/model diversity floor; "
            "seat outputs may share training data, vendor policy and failure "
            "modes, so the independence assumption behind the vote is void."
        ),
    }


def solve(
    pool: Iterable[Mapping[str, Any]],
    constraint: Mapping[str, Any] | None = None,
    *,
    emit_waiver: bool = True,
) -> SeatingArtifact:
    """Seat a council under the diversity constraint and report honestly.

    ``emit_waiver=False`` is the negative-control knob: it models a caller that
    silences the waiver.  The solver still seats and still runs the council,
    which is exactly the artifact :func:`check_artifact` must reject.
    """
    reachable, unreachable = _reachable(pool)
    requested = _normalise_constraint(constraint, len(reachable))
    seats = pick_seats(reachable, requested["seat_count"])

    vendors = sorted({str(s.get("vendor")) for s in seats})
    models = sorted({f"{s.get('vendor')}/{s.get('model')}" for s in seats})
    observed = {"vendors": len(vendors), "models": len(models), "seats": len(seats)}

    vendor_diverse = observed["vendors"] >= requested["min_vendors"]
    model_diverse = observed["models"] >= requested["min_models"]
    seats_filled = observed["seats"] >= requested["seat_count"]
    feasible = vendor_diverse and model_diverse and seats_filled

    shortfall = {
        key: max(requested[req] - observed[key], 0)
        for key, req in (("vendors", "min_vendors"), ("models", "min_models"), ("seats", "seat_count"))
        if observed[key] < requested[req]
    }

    council_ran = True  # the council runs regardless; infeasibility is reported, never hidden
    waiver = None
    if not feasible and emit_waiver:
        waiver = make_waiver(requested, observed, shortfall)

    return SeatingArtifact(
        seats=seats,
        requested=requested,
        observed=observed,
        vendors=vendors,
        models=models,
        vendor_diverse=vendor_diverse,
        model_diverse=model_diverse,
        seats_filled=seats_filled,
        feasible=feasible,
        independence_assumption=INTACT if feasible else VOID,
        council_ran=council_ran,
        waiver=waiver,
        shortfall=shortfall,
        unreachable=unreachable,
    )


def check_artifact(art: Any) -> tuple[bool, str]:
    """Reviewer gate over a seating artifact (dataclass or its dict view).

    Infeasible seatings need a waiver that itself reports independence void,
    and the artifact must report the same; feasible seatings must carry no
    waiver and report independence intact.  Every failure names its reason.
    """
    feasible = bool(_get(art, "feasible"))
    waiver = _get(art, "waiver")
    assumption = _get(art, "independence_assumption")
    if not _get(art, "council_ran", False):
        return False, COUNCIL_DID_NOT_RUN
    if not feasible:
        if waiver is None:
            return False, SHORTFALL_WITHOUT_WAIVER
        if _get(waiver, "independence_assumption") != VOID:
            return False, WAIVER_DOES_NOT_VOID
        if assumption != VOID:
            return False, INDEPENDENCE_MISREPORTED
        return True, CHECK_OK
    if waiver is not None:
        return False, STRAY_WAIVER
    if assumption != INTACT:
        return False, INDEPENDENCE_MISREPORTED
    return True, CHECK_OK


def without_waiver(art: Any) -> Any:
    """Post-hoc waiver strip (negative control); the result must fail :func:`check_artifact`."""
    if isinstance(art, SeatingArtifact):
        clone = copy.deepcopy(art)
        clone.waiver = None
        return clone
    clone = copy.deepcopy(dict(art))
    clone["waiver"] = None
    return clone


def _p(pid: str, vendor: str, model: str, reachable: bool = True) -> dict[str, Any]:
    return {"id": pid, "vendor": vendor, "model": model, "reachable": reachable}


MATRIX: list[dict[str, Any]] = [
    {
        "id": "F1-two-vendors-two-models",
        "pool": [_p("a1", "anthropic", "opus"), _p("o1", "openai", "gpt-5")],
        "constraint": {"min_vendors": 2, "min_models": 2, "seat_count": 2},
        "expected_feasible": True,
    },
    {
        "id": "F2-three-vendors-three-seats",
        "pool": [
            _p("a1", "anthropic", "opus"),
            _p("o1", "openai", "gpt-5"),
            _p("g1", "google", "gemini"),
        ],
        "constraint": {"min_vendors": 3, "min_models": 3, "seat_count": 3},
        "expected_feasible": True,
    },
    {
        "id": "F3-single-vendor-floor-one",
        "pool": [_p("a1", "anthropic", "opus"), _p("a2", "anthropic", "sonnet")],
        "constraint": {"min_vendors": 1, "min_models": 2, "seat_count": 2},
        "expected_feasible": True,
    },
    {
        "id": "F4-unreachable-seat-skipped-still-diverse",
        "pool": [
            _p("a1", "anthropic", "opus"),
            _p("o1", "openai", "gpt-5", reachable=False),
            _p("o2", "openai", "gpt-5-mini"),
            _p("g1", "google", "gemini"),
        ],
        "constraint": {"min_vendors": 2, "min_models": 2, "seat_count": 2},
        "expected_feasible": True,
    },
    {
        "id": "I1-one-vendor-reachable",
        "pool": [
            _p("a1", "anthropic", "opus"),
            _p("a2", "anthropic", "sonnet"),
            _p("o1", "openai", "gpt-5", reachable=False),
        ],
        "constraint": {"min_vendors": 2, "min_models": 2, "seat_count": 2},
        "expected_feasible": False,
    },
    {
        "id": "I2-same-vendor-twice-not-vendor-diverse",
        "pool": [_p("a1", "anthropic", "opus"), _p("a2", "anthropic", "sonnet")],
        "constraint": {"min_vendors": 2, "min_models": 2, "seat_count": 2},
        "expected_feasible": False,
    },
    {
        "id": "I3-three-vendors-requested-two-reachable",
        "pool": [
            _p("a1", "anthropic", "opus"),
            _p("o1", "openai", "gpt-5"),
            _p("g1", "google", "gemini", reachable=False),
        ],
        "constraint": {"min_vendors": 3, "min_models": 3, "seat_count": 3},
        "expected_feasible": False,
    },
    {
        "id": "I4-model-floor-unmet-with-vendor-floor-met",
        "pool": [
            _p("a1", "anthropic", "opus"),
            _p("a2", "anthropic", "opus"),
            _p("o1", "openai", "gpt-5"),
        ],
        "constraint": {"min_vendors": 2, "min_models": 3, "seat_count": 3},
        "expected_feasible": False,
    },
]


def _row_passes(case: Mapping[str, Any], art: SeatingArtifact) -> bool:
    ok, _why = check_artifact(art)
    if not ok or art.feasible != bool(case["expected_feasible"]) or not art.council_ran:
        return False
    if art.feasible:
        return art.waiver is None and art.independence_assumption == INTACT
    stripped_ok, stripped_why = check_artifact(without_waiver(art))
    return (
        art.waiver is not None
        and art.independence_assumption == VOID
        and not stripped_ok
        and stripped_why == SHORTFALL_WITHOUT_WAIVER
    )


def run_matrix(cases: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Solve every matrix case and score it against its expected feasibility."""
    rows: list[dict[str, Any]] = []
    for case in cases or MATRIX:
        art = solve(case["pool"], case["constraint"], emit_waiver=True)
        ok, why = check_artifact(art)
        rows.append(
            {
                "id": case["id"],
                "constraint": dict(case["constraint"]),
                "pool": [dict(p) for p in case["pool"]],
                "expected_feasible": bool(case["expected_feasible"]),
                "artifact": art.as_dict(),
                "check": why,
                "check_ok": ok,
                "council_ran": art.council_ran,
                "independence_assumption": art.independence_assumption,
                "passed": _row_passes(case, art),
            }
        )
    return rows


__all__ = [
    "CHECK_OK",
    "INTACT",
    "MATRIX",
    "SHORTFALL_WITHOUT_WAIVER",
    "SeatingArtifact",
    "VOID",
    "check_artifact",
    "make_waiver",
    "pick_seats",
    "run_matrix",
    "solve",
    "without_waiver",
]
