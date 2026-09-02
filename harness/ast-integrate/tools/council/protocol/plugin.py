"""Protocol-as-data plugin: the 58 catalog records behind a kernel-primitive gate.

IMP-0297: a council protocol is *data* (a record with phases, speaking orders,
obligations and gates), and the linear IMP-0264 kernel runs any record whose
requirements are covered by :data:`KERNEL_PRIMITIVES`.  A record that needs a
primitive the kernel lacks (state forks, nested event loops, a hidden
parallel loop, multi-runtime mirroring, a human gate) is classified
``needs-kernel-change`` and :func:`execute` *refuses* it with
:class:`NeedsKernelChange` instead of flattening it into a linear run.

The records come from :mod:`tools.council.protocol.catalog`, the validated
registry of P01..P58 (``load_protocols()`` returns deep copies, so callers may
mutate them to build negative controls).  :func:`execute` walks a record's
phases through the real kernel (``tools/council/kernel.py``) on a
role-distinct standard cast, one :class:`ExecutionPlan` per phase, and checks
the kernel's own ``turns_executed == turns_recorded`` invariant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import catalog

KERNEL_PRIMITIVES = frozenset(
    {
        "round_robin",
        "all_roles_spoke",
        "nonempty",
        "linear",
    }
)
STRUCTURAL_TO_PRIMITIVE = {
    "forks_state": "state_fork",
    "nests_councils": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror_runtimes": "multi_runtime_mirror",
    "requires_owner": "human_gate",
}
COMPOSITION_TO_PRIMITIVE = {
    "fork": "state_fork",
    "nested": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror": "multi_runtime_mirror",
    "human_gate": "human_gate",
}
BLOCKED_IDS = ("P32", "P34", "P48", "P52", "P54", "P55", "P58")
EXECUTE_SAMPLE = tuple(f"P{i:02d}" for i in range(1, 13))
LIBRARY_FILE = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CAST = ("chair", "advocate", "skeptic")

# Role-distinct standard cast per speaking order: a judge never sits on the
# jury, a proposition never speaks for the opposition.
_CAST_BY_ORDER: dict[str, tuple[str, ...]] = {
    "round_robin": DEFAULT_CAST,
    "all": DEFAULT_CAST,
    "": DEFAULT_CAST,
    "chair_then_round_robin": DEFAULT_CAST,
    "rotating_chair": DEFAULT_CAST,
    "prop_then_opp": ("proposition", "opposition"),
    "red_only": ("red_team",),
    "blue_only": ("blue_team",),
    "thesis_side": ("thesis",),
    "antithesis_side": ("antithesis",),
    "named_inner": ("inner_a", "inner_b"),
    "named_outer": ("outer_a", "outer_b"),
    "advocate_must_speak": ("devil",),
    "team_a": ("team_a",),
    "team_b": ("team_b",),
    "examiner_then_witness": ("examiner", "witness"),
    "advocates": ("advocate_a", "advocate_b"),
    "jury": ("juror_1", "juror_2"),
    "judge_only": ("judge",),
    "clerk_then_jury": ("clerk", "juror_1"),
    "key_a_then_key_b": ("key_a", "key_b"),
    "facilitator_only": ("facilitator",),
    "scorer_only": ("scorer",),
    "reviewers": ("reviewer_a", "reviewer_b"),
    "authors": ("author",),
    "author_then_board": ("author", "board"),
    "board": ("board",),
    "asker_then_addressee": ("asker", "addressee"),
    "clerk_then_floor": ("clerk", "floor"),
}
_HATS = ("white", "red", "black", "yellow", "green", "blue")


class NeedsKernelChange(Exception):
    """Raised by :func:`execute` for a record the linear kernel cannot express."""

    def __init__(self, extra_primitives: list[str] | str, record_id: str | None = None) -> None:
        if isinstance(extra_primitives, str):
            extra_primitives = [p for p in extra_primitives.split(",") if p]
        self.extra_primitives = sorted(extra_primitives)
        self.record_id = record_id
        super().__init__(",".join(self.extra_primitives))


class ProtocolRecordError(ValueError):
    """Raised for a record that is not a well-formed protocol blueprint."""


@dataclass
class Classification:
    """Kernel-expressibility verdict for one protocol record."""

    status: str
    extra_primitives: list[str]
    id: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def expressible(self) -> bool:
        return self.status == "expressible"

    def as_dict(self) -> dict[str, Any]:
        """Census row: ``{"id", "status", "extra_primitives", "reasons"}``."""
        return {
            "id": self.id,
            "status": self.status,
            "extra_primitives": list(self.extra_primitives),
            "reasons": list(self.reasons),
        }

    def as_row(self) -> dict[str, Any]:
        return self.as_dict()


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #
def load_protocols() -> list[dict[str, Any]]:
    """All 58 catalog records (P01..P58) in id order, as deep copies."""
    return catalog.records()


def get_protocol(pid: str) -> dict[str, Any]:
    """One catalog record by id (deep copy); raises ``catalog.UnknownProtocol``."""
    return catalog.by_id(pid)


def validate_record(record: Mapping[str, Any]) -> list[str]:
    """Structural problems with ``record`` (empty when it is a runnable blueprint)."""
    problems: list[str] = []
    if not str(record.get("id") or "").strip():
        problems.append("id missing")
    phases = record.get("phases")
    if not isinstance(phases, list) or not phases:
        problems.append("phases missing or empty")
        return problems
    seen: set[str] = set()
    for i, phase in enumerate(phases):
        if not isinstance(phase, Mapping):
            problems.append(f"phase[{i}] is not an object")
            continue
        pid = str(phase.get("id") or "")
        if not pid:
            problems.append(f"phase[{i}] id missing")
        elif pid in seen:
            problems.append(f"phase id {pid!r} repeated")
        seen.add(pid)
        rounds = phase.get("rounds", 1)
        if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
            problems.append(f"phase {pid!r} rounds must be a positive int")
        for ob in phase.get("obligations") or []:
            if not isinstance(ob, Mapping) or not str(ob.get("id") or ""):
                problems.append(f"phase {pid!r} has an obligation without an id")
    return problems


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #
def extra_primitives(record: Mapping[str, Any]) -> list[str]:
    """Primitives ``record`` needs beyond :data:`KERNEL_PRIMITIVES` (sorted).

    Three independent signals are unioned so a record cannot slip through by
    declaring one and omitting another: structural flags (``forks_state`` ...),
    the ``composition`` token, and any ``required_kernel_primitives`` entry
    the kernel does not implement.
    """
    found: set[str] = set()
    for key, prim in STRUCTURAL_TO_PRIMITIVE.items():
        if record.get(key):
            found.add(prim)
    comp = str(record.get("composition") or "linear")
    if comp in COMPOSITION_TO_PRIMITIVE:
        found.add(COMPOSITION_TO_PRIMITIVE[comp])
    for item in record.get("required_kernel_primitives") or []:
        name = str(item)
        if name and name not in KERNEL_PRIMITIVES:
            found.add(name)
    return sorted(found)


def gap_reasons(record: Mapping[str, Any], extra: list[str]) -> list[str]:
    """One human-readable reason per missing primitive.

    Prefers the catalog's recorded ``kernel_gap`` reason when the record's own
    gap names the same primitive, then the catalog's per-primitive reason
    table, then a generic ``requires <primitive>``.
    """
    recorded: dict[str, str] = {}
    gap = record.get("kernel_gap")
    if isinstance(gap, Mapping):
        prims = [str(p) for p in gap.get("extra_primitives") or []]
        texts = [str(r) for r in gap.get("reasons") or []]
        for prim, text in zip(prims, texts):
            recorded[prim] = text
    table = getattr(catalog, "GAP_REASON", {})
    reasons: list[str] = []
    for prim in extra:
        if prim in recorded:
            reasons.append(recorded[prim])
        elif prim in table:
            reasons.append(str(table[prim]))
        else:
            reasons.append(f"requires {prim}")
    return reasons


def classify(record: Mapping[str, Any]) -> Classification:
    """``expressible`` on the linear kernel, else ``needs-kernel-change`` with reasons."""
    extra = extra_primitives(record)
    rid = str(record.get("id")) if record.get("id") is not None else None
    if extra:
        return Classification(
            status="needs-kernel-change",
            extra_primitives=extra,
            id=rid,
            reasons=gap_reasons(record, extra),
        )
    return Classification(status="expressible", extra_primitives=[], id=rid, reasons=[])


def census() -> dict[str, Any]:
    """Classify every catalog record; name each inexpressible one with reasons."""
    rows = load_protocols()
    blocked = [classify(rec).as_dict() for rec in rows if extra_primitives(rec)]
    library_present = (REPO_ROOT / LIBRARY_FILE).is_file()
    return {
        "n": len(rows),
        "ids": [r["id"] for r in rows],
        "expressible_n": len(rows) - len(blocked),
        "needs_kernel_change_n": len(blocked),
        "needs_kernel_change": blocked,
        "kernel_primitives": sorted(KERNEL_PRIMITIVES),
        "library_file": LIBRARY_FILE,
        "library_file_present": library_present,
        # Full coverage would mean the original library is on disk and every
        # record in it runs on the kernel; neither holds while records are
        # reconstructed and seven of them need kernel primitives.
        "full_coverage_claim": bool(library_present and not blocked),
        "blueprint_source": "tools/council/protocol/catalog.py",
    }


# --------------------------------------------------------------------------- #
# execution on the kernel
# --------------------------------------------------------------------------- #
def cast_for(order: str, round_index: int = 0) -> list[str]:
    """Seats that speak in a round of ``order`` (role-distinct, deterministic)."""
    key = str(order or "round_robin")
    if key == "hat_rotation":
        return [_HATS[round_index % len(_HATS)]]
    if key == "rotating_chair":
        chair = DEFAULT_CAST[round_index % len(DEFAULT_CAST)]
        return [chair] + [s for s in DEFAULT_CAST if s != chair]
    if key in _CAST_BY_ORDER:
        return list(_CAST_BY_ORDER[key])
    if "then" in key:
        return ["lead", "second"]
    if key.endswith("_only"):
        return ["lead"]
    return list(DEFAULT_CAST)


def _kernel_modules() -> tuple[Any, Any, Any, Any]:
    from ..kernel import ExecutionPlan, Kernel, ScriptedAdapter, TurnResponse  # noqa: WPS433

    return ExecutionPlan, Kernel, ScriptedAdapter, TurnResponse


def execute(record: Mapping[str, Any]) -> dict[str, Any]:
    """Run ``record`` on the kernel; refuse (never flatten) inexpressible records.

    Each phase becomes one kernel :class:`ExecutionPlan` (roster = the phase's
    cast, ``n_rounds`` = its rounds, obligations = its obligation ids,
    ``max_chars`` = its turn length).  Scripted adapters discharge every
    obligation so the run exercises the kernel's scheduling and turn
    recording; ``ok`` is the conjunction of the kernel's own
    ``turns_executed == turns_recorded`` invariant and an all-``ok`` status
    roll-up.  Raises :class:`NeedsKernelChange` before touching the kernel
    when :func:`classify` says the record needs a primitive it lacks, and
    :class:`ProtocolRecordError` for a malformed record.
    """
    decision = classify(record)
    if not decision.expressible:
        raise NeedsKernelChange(decision.extra_primitives, decision.id)
    problems = validate_record(record)
    if problems:
        raise ProtocolRecordError("; ".join(problems))
    ExecutionPlan, Kernel, ScriptedAdapter, TurnResponse = _kernel_modules()

    rid = str(record.get("id"))
    events: list[dict[str, Any]] = []
    phase_runs: list[dict[str, Any]] = []
    rounds = 0
    turns_executed = 0
    turns_recorded = 0
    statuses: list[str] = []
    invariant_ok = True
    last_gate = "all_phases_complete"
    for phase in record["phases"]:
        # The kernel's invariant counters are per instance, so each phase gets
        # its own kernel and the totals are summed here.
        kernel = Kernel(council_id=f"{rid}:{phase.get('id')}")
        n_rounds = int(phase.get("rounds") or 1)
        order = str(phase.get("speaking_order") or "round_robin")
        obligations = [str(o.get("id") or "speak") for o in (phase.get("obligations") or [])]
        gates = [str(g.get("kind") or "") for g in (phase.get("gates") or []) if g.get("kind")]
        if gates:
            last_gate = gates[-1]
        # Per-round rosters can rotate (hat rotation, rotating chair): build
        # the full order explicitly and hand it to the kernel as one plan.
        roster: list[str] = []
        for r_i in range(n_rounds):
            roster.extend(cast_for(order, r_i))
        plan = ExecutionPlan(
            council_id=rid,
            roster=tuple(roster),
            n_rounds=1,
            timeout_ms=0,
            max_chars=int(phase.get("turn_length") or 0),
            obligations=tuple(obligations),
        )
        adapters = {
            seat: ScriptedAdapter(
                TurnResponse(
                    text=f"{seat} discharges {', '.join(obligations) or 'speak'} in {phase.get('id')}",
                    fields={ob: f"{seat}:{ob}" for ob in obligations},
                )
            )
            for seat in set(roster)
        }
        result = kernel.run(plan, None, adapters)
        rounds += n_rounds
        turns_executed += int(result.turns_executed)
        turns_recorded += int(result.turns_recorded)
        statuses.extend(result.statuses)
        invariant_ok = invariant_ok and bool(result.invariant_ok) and result.turns_executed == len(roster)
        for ev in result.events:
            row = ev.as_dict()
            row["phase_id"] = str(phase.get("id"))
            row["speaking_order"] = order
            events.append(row)
        phase_runs.append(
            {
                "phase_id": str(phase.get("id")),
                "speaking_order": order,
                "rounds": n_rounds,
                "roster": roster,
                "obligations": obligations,
                "turns_executed": result.turns_executed,
                "turns_recorded": result.turns_recorded,
                "invariant_ok": bool(result.invariant_ok),
                "statuses": list(result.statuses),
            }
        )
    ok = invariant_ok and bool(statuses) and all(s == "ok" for s in statuses)
    return {
        "id": rid,
        "ok": ok,
        "status": "expressible",
        "terminal_state": "DONE" if ok else "FAILED",
        "stopping_term": str(record.get("stopping_term") or last_gate),
        "turns_executed": turns_executed,
        "turns_recorded": turns_recorded,
        "turns": turns_executed,
        "rounds": rounds,
        "kernel_invariant_ok": invariant_ok,
        "statuses": statuses,
        "phases": phase_runs,
        "events": events,
        "flattened": False,
    }


def execute_sample() -> dict[str, Any]:
    """Execute :data:`EXECUTE_SAMPLE` (P01..P12) end to end on the kernel."""
    by_id = {r["id"]: r for r in load_protocols()}
    runs = []
    for pid in EXECUTE_SAMPLE:
        out = execute(by_id[pid])
        runs.append(
            {
                "id": pid,
                "status": out["status"],
                "ok": out["ok"],
                "turns": out["turns_executed"],
                "rounds": out["rounds"],
                "stopping_term": out["stopping_term"],
            }
        )
    return {"n": len(runs), "ids": list(EXECUTE_SAMPLE), "runs": runs}


def refuse_kernel_required(pid: str) -> dict[str, Any]:
    """Show that ``pid`` is refused (not flattened) when it needs a kernel primitive."""
    rec = get_protocol(pid)
    decision = classify(rec)
    refused = False
    error: str | None = None
    if not decision.expressible:
        try:
            execute(rec)
        except NeedsKernelChange as exc:
            refused = True
            error = str(exc)
    return {
        "id": rec["id"],
        "refused": refused,
        "flattened": False,
        "status": decision.status,
        "extra_primitives": list(decision.extra_primitives),
        "reasons": list(decision.reasons),
        "error": error,
    }


def classification_table() -> dict[str, dict[str, Any]]:
    """``{pid: classify(record).as_dict()}`` for every catalog record."""
    return {r["id"]: classify(r).as_dict() for r in load_protocols()}


__all__ = [
    "BLOCKED_IDS",
    "COMPOSITION_TO_PRIMITIVE",
    "Classification",
    "DEFAULT_CAST",
    "EXECUTE_SAMPLE",
    "KERNEL_PRIMITIVES",
    "LIBRARY_FILE",
    "NeedsKernelChange",
    "ProtocolRecordError",
    "STRUCTURAL_TO_PRIMITIVE",
    "cast_for",
    "census",
    "classification_table",
    "classify",
    "execute",
    "execute_sample",
    "extra_primitives",
    "gap_reasons",
    "get_protocol",
    "load_protocols",
    "refuse_kernel_required",
    "validate_record",
]
