"""Canonical registry of the 58 council deliberation protocols (P01-P58) as data.

Every protocol the council kernel (``tools/council/kernel.py``, IMP-0264) can be
asked to run is described here as a *protocol-as-data* record: an ordered list of
phases, each with a speaking order, a round count, the response obligations a seat
must discharge in its turn and the gate that closes the phase.  The last gate of
the last phase is the protocol's stopping term.  ``tools/council/protocol/plugin.py``
reads the structural flags (``forks_state``, ``nests_councils``, ``hidden_parallel``,
``mirror_runtimes``, ``requires_owner``, ``composition``,
``required_kernel_primitives``) to decide whether a record is expressible on the
linear kernel; seven records are not, and :func:`kernel_gap` names the missing
primitive for each.

Two sources feed a record:

* the static blueprint table below (id, slug, family, engine module, kernel phases
  and kernel flags) - the authority for every field a probe or the kernel walks;
* the councilspec file ``platform/council/protocols/<pNN-slug>.councilspec.json``
  where one exists (P01-P48), which contributes the spec's own title, topology,
  roster size and stage sequence under ``record["spec"]``.  P49-P58 have no spec
  file in this tree (``12-COUNCIL-PROTOCOLS-AND-PRESETS.json`` is absent); their
  ids and names are reconstructed from ``command-center/research/RES-0116.json``
  and carry ``spec.provenance == "reconstructed"``.

The registry is validated once, on first use (:func:`validate`): 58 contiguous
ids, unique kebab-case slugs, every record walkable (at least one phase with at
least one obligation), pairwise-distinct phase signatures, kernel flags consistent
with the declared kernel gap, every engine module present on disk, and every
present councilspec agreeing with the table's id and slug.  Any inconsistency
raises :class:`CatalogError` rather than serving a record that disagrees with its
source.
"""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "CatalogError",
    "UnknownProtocol",
    "FAMILIES",
    "KERNEL_PRIMITIVES",
    "KERNEL_GAPS",
    "GAP_REASON",
    "ENGINES",
    "STAGE_ENGINES",
    "SPEC_DIR_REL",
    "by_id",
    "get",
    "by_slug",
    "records",
    "ids",
    "slugs",
    "families",
    "expressible_ids",
    "inexpressible_ids",
    "extra_primitives",
    "kernel_status",
    "kernel_gap",
    "engine_for",
    "engine_for_stage",
    "validate",
]


class CatalogError(ValueError):
    """The registry disagrees with itself or with a councilspec on disk."""


class UnknownProtocol(KeyError):
    """No protocol record carries the requested id or slug."""


# --------------------------------------------------------------------------- constants

FAMILIES: tuple[str, ...] = (
    "DELIBERATIVE",
    "ADVERSARIAL",
    "JUDICIAL",
    "ANONYMOUS",
    "GENERATIVE",
    "FORECASTING",
    "TRADECRAFT",
    "ENGINEERING-REVIEW",
    "META-COMPOSITION",
)

#: Primitives the IMP-0264 kernel implements.  Anything else a record needs is a
#: kernel gap (same set as ``plugin.KERNEL_PRIMITIVES``).
KERNEL_PRIMITIVES: frozenset[str] = frozenset(
    {"round_robin", "all_roles_spoke", "nonempty", "linear"}
)

#: Structural flag on a record -> kernel primitive it demands.
FLAG_PRIMITIVE: dict[str, str] = {
    "forks_state": "state_fork",
    "nests_councils": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror_runtimes": "multi_runtime_mirror",
    "requires_owner": "human_gate",
}
STRUCTURAL_FLAGS: tuple[str, ...] = tuple(FLAG_PRIMITIVE)
PRIMITIVE_FLAG: dict[str, str] = {prim: flag for flag, prim in FLAG_PRIMITIVE.items()}

#: ``composition`` token on a META-COMPOSITION record -> kernel primitive.
COMPOSITION_PRIMITIVE: dict[str, str] = {
    "fork": "state_fork",
    "nested": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror": "multi_runtime_mirror",
    "human_gate": "human_gate",
}
PRIMITIVE_COMPOSITION: dict[str, str] = {
    prim: token for token, prim in COMPOSITION_PRIMITIVE.items()
}

#: Why the linear kernel cannot host a record that needs the primitive.
GAP_REASON: dict[str, str] = {
    "state_fork": (
        "record forks independent council state; linear kernel has one event loop"
    ),
    "hidden_parallel_loop": (
        "record runs a hidden parallel loop; kernel is exclusive-floor"
    ),
    "nested_event_loop": (
        "record nests a child council; kernel has no nested_event_loop primitive"
    ),
    "multi_runtime_mirror": (
        "record mirrors across runtimes; kernel is single-runtime"
    ),
    "human_gate": (
        "record requires an owner/human gate between steps; kernel has none"
    ),
}

#: The seven records the linear kernel cannot express, and the primitive each needs.
#: P32 forks a failed/succeeded hindsight pair, P34 forks four futures, P48 and P55
#: run a hidden parallel (red / shadow) loop, P52 nests child councils, P54 mirrors
#: runtimes across vendors, P58 puts an owner gate between steps.
KERNEL_GAPS: dict[str, str] = {
    "P32": "state_fork",
    "P34": "state_fork",
    "P48": "hidden_parallel_loop",
    "P52": "nested_event_loop",
    "P54": "multi_runtime_mirror",
    "P55": "hidden_parallel_loop",
    "P58": "human_gate",
}

#: Protocol id -> module in this package that implements the protocol's engine.
ENGINES: dict[str, str] = {
    "P06": "ngt",
    "P07": "oxford",
    "P12": "negotiate",
    "P13": "crossexam",
    "P26": "brainstorm",
    "P30": "hats",
    "P33": "betting",
    "P34": "scenario",
    "P43": "premortem",
    "P49": "socratic",
}

#: councilspec stage ``kind`` -> module in this package that runs that stage kind.
STAGE_ENGINES: dict[str, str] = {
    "blind_independent_first_pass": "blind_first",
    "brainstorm": "brainstorm",
    "cross_examination": "crossexam",
    "mediation": "negotiate",
    "negotiation": "negotiate",
    "nominal_group": "ngt",
    "oxford": "oxford",
    "prediction_confidence": "betting",
    "premortem": "premortem",
    "scenario": "scenario",
    "six_hats": "hats",
    "socratic": "socratic",
    "steelman_before_rebuttal": "steelman",
}

#: Kernel default turn budget carried on every blueprint phase.
DEFAULT_TURN_LENGTH = 80

SPEC_DIR_REL = "platform/council/protocols"
_SPEC_SUFFIX = ".councilspec.json"
_PID_RE = re.compile(r"^P(\d{2})$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# --------------------------------------------------------------------------- blueprint

#: (id, slug, family, open_rounds, close).  ``open_rounds`` is the number of
#: round-robin deliberation rounds in the kernel blueprint's ``open`` phase and
#: ``close`` adds one closing round-robin round.  P07 and P14 have bespoke phase
#: lists (see :func:`_oxford_phases`, :func:`_jury_phases`) and carry ``0, False``.
_BLUEPRINT: tuple[tuple[str, str, str, int, bool], ...] = (
    ("P01", "free-form-moderated-panel", "DELIBERATIVE", 2, False),
    ("P02", "round-robin", "DELIBERATIVE", 3, True),
    ("P03", "fishbowl", "DELIBERATIVE", 1, False),
    ("P04", "consensus-conference", "DELIBERATIVE", 2, True),
    ("P05", "rotating-chair", "DELIBERATIVE", 3, False),
    ("P06", "nominal-group-technique", "DELIBERATIVE", 1, True),
    ("P07", "oxford-debate", "ADVERSARIAL", 0, False),
    ("P08", "red-blue-team", "ADVERSARIAL", 3, True),
    ("P09", "dialectical-inquiry", "ADVERSARIAL", 1, False),
    ("P10", "mandated-devils-advocate", "ADVERSARIAL", 2, True),
    ("P11", "team-b-competitive-estimate", "ADVERSARIAL", 3, False),
    ("P12", "adversarial-collaboration", "ADVERSARIAL", 1, True),
    ("P13", "hostile-cross-examination", "ADVERSARIAL", 2, False),
    ("P14", "judge-and-jury", "JUDICIAL", 0, False),
    ("P15", "claim-by-claim-adjudication", "JUDICIAL", 1, False),
    ("P16", "grand-jury-threshold", "JUDICIAL", 2, True),
    ("P17", "jury-with-allowed-hung", "JUDICIAL", 3, False),
    ("P18", "two-key-dual-control", "JUDICIAL", 1, True),
    ("P19", "rfc-last-call", "JUDICIAL", 2, False),
    ("P20", "delphi-anonymous-rounds", "ANONYMOUS", 3, True),
    ("P21", "wideband-delphi-estimation", "ANONYMOUS", 1, False),
    ("P22", "brainwriting-635", "ANONYMOUS", 2, True),
    ("P23", "silent-start-pooling", "ANONYMOUS", 3, False),
    ("P24", "surprisingly-popular-bts", "ANONYMOUS", 1, True),
    ("P25", "blind-reevaluation", "ANONYMOUS", 2, False),
    ("P26", "brainstorming-swarm", "GENERATIVE", 3, True),
    ("P27", "design-charrette", "GENERATIVE", 1, False),
    ("P28", "morphological-analysis", "GENERATIVE", 2, True),
    ("P29", "triz-contradiction", "GENERATIVE", 3, False),
    ("P30", "six-hats-rotation", "GENERATIVE", 1, True),
    ("P31", "constraint-relaxation", "GENERATIVE", 2, False),
    ("P32", "counterfactual-council", "GENERATIVE", 3, True),
    ("P33", "prediction-tournament", "FORECASTING", 1, False),
    ("P34", "scenario-planning", "FORECASTING", 2, True),
    ("P35", "reference-class-planning-poker", "FORECASTING", 3, False),
    ("P36", "calibration-tournament", "FORECASTING", 1, True),
    ("P37", "pairwise-comparison", "FORECASTING", 2, False),
    ("P38", "analysis-of-competing-hypotheses", "TRADECRAFT", 3, True),
    ("P39", "key-assumptions-check", "TRADECRAFT", 1, False),
    ("P40", "quality-of-information-check", "TRADECRAFT", 2, True),
    ("P41", "deception-detection", "TRADECRAFT", 3, False),
    ("P42", "argument-mapping", "TRADECRAFT", 1, True),
    ("P43", "premortem", "TRADECRAFT", 2, False),
    ("P44", "postmortem-5whys-causal", "TRADECRAFT", 3, True),
    ("P45", "scientific-peer-review", "ENGINEERING-REVIEW", 1, False),
    ("P46", "architecture-review-board", "ENGINEERING-REVIEW", 2, True),
    ("P47", "incident-war-room", "ENGINEERING-REVIEW", 3, False),
    ("P48", "kill-the-company", "ENGINEERING-REVIEW", 1, True),
    ("P49", "socratic-interrogation", "ENGINEERING-REVIEW", 2, False),
    ("P50", "evidence-clerk-led", "ENGINEERING-REVIEW", 3, True),
    ("P51", "timeboxed-spike-council", "ENGINEERING-REVIEW", 1, False),
    ("P52", "nested-subcouncils-meta-council", "META-COMPOSITION", 2, True),
    ("P53", "escalation-ladder", "META-COMPOSITION", 3, False),
    ("P54", "cross-vendor-mirrored", "META-COMPOSITION", 1, True),
    ("P55", "shadow-council", "META-COMPOSITION", 2, False),
    ("P56", "minority-report-mandatory", "META-COMPOSITION", 3, True),
    ("P57", "stopping-rule-tournament", "META-COMPOSITION", 1, False),
    ("P58", "owner-in-the-loop-stepwise", "META-COMPOSITION", 2, True),
)

#: One-line descriptions for the records that have no councilspec in this tree.
_RECONSTRUCTED_NOTES: dict[str, str] = {
    "P49": (
        "Socratic interrogation: a directed question creates a tracked answer "
        "obligation the addressee must discharge within a bounded number of turns."
    ),
    "P50": (
        "Evidence-clerk-led review: a clerk reads the evidence into the record "
        "before any seat is allowed to argue from it."
    ),
    "P51": (
        "Timeboxed spike council: a bounded investigation spike followed by a "
        "go/no-go read-out."
    ),
    "P52": (
        "Nested sub-councils: a parent council delegates sub-questions to child "
        "councils and adjudicates their read-outs."
    ),
    "P53": (
        "Escalation ladder: an unresolved question climbs a fixed ladder of tiers, "
        "each tier with a stricter cast and stopping rule."
    ),
    "P54": (
        "Cross-vendor mirrored councils: the same question runs on mirrored "
        "runtimes and the mirrors are reconciled afterwards."
    ),
    "P55": (
        "Shadow council: a hidden parallel council deliberates alongside the "
        "primary; the two verdicts are compared only after both close."
    ),
    "P56": (
        "Minority report mandatory: every dissent is written up as a public "
        "minority report delivered alongside the majority product."
    ),
    "P57": (
        "Stopping-rule tournament: competing stopping rules run side by side and "
        "are scored on the same transcript."
    ),
    "P58": (
        "Owner-in-the-loop stepwise: an owner/human gate must clear each step "
        "before the next one begins."
    ),
}


def _phase(
    phase_id: str,
    kind: str,
    rounds: int,
    speaking_order: str,
    obligations: list[str],
    gate_id: str,
    gate_kind: str,
) -> dict[str, Any]:
    """Build one kernel blueprint phase.

    ``rounds`` full passes over the cast named by ``speaking_order``; in every turn
    the speaker must discharge each obligation with a non-empty contribution; the
    single gate closes the phase and, on the last phase, is the stopping term.
    """
    if rounds < 1:
        raise CatalogError(f"phase {phase_id!r}: rounds must be >= 1, got {rounds}")
    if not obligations:
        raise CatalogError(f"phase {phase_id!r}: at least one obligation is required")
    return {
        "id": phase_id,
        "kind": kind,
        "rounds": int(rounds),
        "speaking_order": speaking_order,
        "obligations": [{"id": ob, "discharge": "nonempty"} for ob in obligations],
        "gates": [{"id": gate_id, "kind": gate_kind}],
        "visibility": "all",
        "redact_speaker": False,
        "turn_length": DEFAULT_TURN_LENGTH,
    }


def _generic_phases(pid: str, open_rounds: int, close: bool) -> list[dict[str, Any]]:
    """Round-robin floor: ``open_rounds`` deliberation rounds, optional closing round."""
    tag = pid.lower()
    phases = [
        _phase(
            "open",
            "round_robin",
            open_rounds,
            "round_robin",
            [f"{tag}-open-nonempty"],
            "spoke",
            "all_roles_spoke",
        )
    ]
    if close:
        phases.append(
            _phase(
                "close",
                "synthesis",
                1,
                "round_robin",
                [f"{tag}-close-nonempty"],
                "spoke",
                "all_roles_spoke",
            )
        )
    return phases


def _oxford_phases() -> list[dict[str, Any]]:
    """P07: proposition then opposition speak in opening, rebuttal and closing."""
    return [
        _phase(
            "opening",
            "oxford",
            1,
            "prop_then_opp",
            ["opening"],
            "opening-discharged",
            "obligation_discharged",
        ),
        _phase(
            "rebuttal",
            "cross_examination",
            1,
            "prop_then_opp",
            ["rebuttal"],
            "rebuttal-discharged",
            "obligation_discharged",
        ),
        _phase(
            "closing",
            "oxford",
            1,
            "prop_then_opp",
            ["closing"],
            "closing-discharged",
            "obligation_discharged",
        ),
    ]


def _jury_phases() -> list[dict[str, Any]]:
    """P14: the judge instructs, the jury deliberates without the judge, a verdict."""
    return [
        _phase(
            "judge_instruct",
            "custom",
            1,
            "judge_only",
            ["instruct"],
            "instructed",
            "obligation_discharged",
        ),
        _phase("jury", "jury", 1, "jury", ["deliberate"], "jury-spoke", "all_roles_spoke"),
        _phase(
            "verdict",
            "synthesis",
            1,
            "clerk_then_jury",
            ["announce"],
            "verdict",
            "vote_threshold_or_hung",
        ),
    ]


_CUSTOM_PHASES = {"P07": _oxford_phases, "P14": _jury_phases}


# --------------------------------------------------------------------------- kernel gate


def _kernel_primitives_used(phases: list[dict[str, Any]]) -> list[str]:
    """Kernel primitives a blueprint actually relies on (always ``linear``)."""
    used = {"linear"}
    for phase in phases:
        if phase["speaking_order"] == "round_robin":
            used.add("round_robin")
        if any(ob["discharge"] == "nonempty" for ob in phase["obligations"]):
            used.add("nonempty")
        if any(gate["kind"] == "all_roles_spoke" for gate in phase["gates"]):
            used.add("all_roles_spoke")
    return sorted(used)


def extra_primitives(record: dict[str, Any]) -> list[str]:
    """Primitives ``record`` needs beyond :data:`KERNEL_PRIMITIVES` (sorted).

    Same gate as ``plugin.extra_primitives``: structural flags, the composition
    token and any required primitive the kernel does not implement.
    """
    found: set[str] = set()
    for flag, prim in FLAG_PRIMITIVE.items():
        if record.get(flag):
            found.add(prim)
    composition = str(record.get("composition") or "linear")
    if composition in COMPOSITION_PRIMITIVE:
        found.add(COMPOSITION_PRIMITIVE[composition])
    for item in record.get("required_kernel_primitives") or []:
        name = str(item)
        if name and name not in KERNEL_PRIMITIVES:
            found.add(name)
    return sorted(found)


def kernel_status(record: dict[str, Any]) -> str:
    """``"expressible"`` on the linear kernel, else ``"needs-kernel-change"``."""
    return "needs-kernel-change" if extra_primitives(record) else "expressible"


def _kernel_flags(pid: str, family: str, phases: list[dict[str, Any]]) -> dict[str, Any]:
    flags: dict[str, Any] = {flag: False for flag in STRUCTURAL_FLAGS}
    composition = "linear"
    required = _kernel_primitives_used(phases)
    gap = KERNEL_GAPS.get(pid)
    if gap is not None:
        flags[PRIMITIVE_FLAG[gap]] = True
        if family == "META-COMPOSITION":
            composition = PRIMITIVE_COMPOSITION[gap]
        required.append(gap)
    flags["composition"] = composition
    flags["required_kernel_primitives"] = required
    flags["kernel_gap"] = {
        "extra_primitives": [gap] if gap else [],
        "reasons": [GAP_REASON[gap]] if gap else [],
    }
    return flags


# --------------------------------------------------------------------------- councilspecs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _spec_index() -> dict[str, Path]:
    """``"p01" -> path`` for every councilspec present under :data:`SPEC_DIR_REL`."""
    spec_dir = _repo_root() / SPEC_DIR_REL
    index: dict[str, Path] = {}
    if not spec_dir.is_dir():
        return index
    for path in sorted(spec_dir.glob(f"*{_SPEC_SUFFIX}"), key=lambda p: p.name.lower()):
        head = path.name.lower().split("-", 1)[0]
        if re.fullmatch(r"p\d{2}", head):
            if head in index:
                raise CatalogError(
                    f"two councilspecs claim {head.upper()}: {index[head].name}, {path.name}"
                )
            index[head] = path
    return index


def _compact_stage(stage: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "stage_id": str(stage.get("stage_id") or ""),
        "kind": str(stage.get("kind") or ""),
        "rounds": int(stage.get("rounds") or 1),
        "independent": bool(stage.get("independent")),
        "anonymous": bool(stage.get("anonymous")),
    }
    exit_when = stage.get("exit_when")
    if isinstance(exit_when, dict) and exit_when.get("metric"):
        out["exit_metric"] = str(exit_when["metric"])
    return out


def _spec_block(pid: str, slug: str) -> dict[str, Any]:
    """The councilspec-derived block of a record, or a reconstructed marker."""
    path = _spec_index().get(pid.lower())
    if path is None:
        return {
            "present": False,
            "provenance": "reconstructed",
            "path": None,
            "council_id": f"{pid.lower()}-{slug}",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogError(f"{pid}: unreadable councilspec {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"{pid}: councilspec {path.name} is not an object")
    council_id = str(data.get("council_id") or "").lower()
    expected = f"{pid.lower()}-{slug}"
    if council_id != expected:
        raise CatalogError(
            f"{pid}: spec drift - table says {expected!r}, "
            f"{path.name} says council_id={council_id!r}"
        )
    protocol = data.get("protocol") if isinstance(data.get("protocol"), dict) else {}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    topology = data.get("topology") if isinstance(data.get("topology"), dict) else {}
    participants = (
        data.get("participants") if isinstance(data.get("participants"), dict) else {}
    )
    count = participants.get("count") if isinstance(participants.get("count"), dict) else {}
    rounds = protocol.get("rounds") if isinstance(protocol.get("rounds"), dict) else {}
    sequence = protocol.get("sequence") if isinstance(protocol.get("sequence"), list) else []
    return {
        "present": True,
        "provenance": "councilspec",
        "path": path.relative_to(_repo_root()).as_posix(),
        "council_id": council_id,
        "title": str(metadata.get("title") or ""),
        "topology": str(topology.get("kind") or ""),
        "roster_size": count.get("exact_n"),
        "speaking_order": str(protocol.get("speaking_order") or ""),
        "rounds": {"min": rounds.get("min"), "max": rounds.get("max")},
        "stages": [_compact_stage(s) for s in sequence if isinstance(s, dict)],
    }


# --------------------------------------------------------------------------- registry


def _build_record(pid: str, slug: str, family: str, open_rounds: int, close: bool) -> dict:
    custom = _CUSTOM_PHASES.get(pid)
    phases = custom() if custom is not None else _generic_phases(pid, open_rounds, close)
    spec = _spec_block(pid, slug)
    if spec["present"]:
        title = spec["title"] or f"{pid} {slug.replace('-', ' ')}"
        source = spec["path"]
        notes = (
            f"{family}: councilspec-backed; spec.stages carries the protocol's own "
            f"{len(spec['stages'])}-stage sequence, phases the kernel blueprint."
        )
    else:
        title = f"{pid} {slug.replace('-', ' ')}"
        source = (
            "reconstructed: 12-COUNCIL-PROTOCOLS-AND-PRESETS.json absent; id and "
            "name from command-center/research/RES-0116.json"
        )
        notes = _RECONSTRUCTED_NOTES.get(pid, f"{family}: reconstructed record")
    record: dict[str, Any] = {
        "id": pid,
        "slug": slug,
        "family": family,
        "title": title,
        "engine": ENGINES.get(pid),
        "phases": phases,
        "stopping_term": phases[-1]["gates"][-1]["kind"],
    }
    record.update(_kernel_flags(pid, family, phases))
    record["spec"] = spec
    record["source"] = source
    record["notes"] = notes
    return record


def _signature(record: dict[str, Any]) -> tuple:
    return tuple(
        (
            phase["id"],
            tuple(ob["id"] for ob in phase["obligations"]),
            phase["speaking_order"],
            phase["rounds"],
        )
        for phase in record["phases"]
    )


def _check(registry: dict[str, dict[str, Any]]) -> None:
    """Refuse to serve a registry that is not internally consistent."""
    expected_ids = [f"P{i:02d}" for i in range(1, 59)]
    if list(registry) != expected_ids:
        raise CatalogError("registry must hold exactly P01..P58 in order")
    seen_slugs: dict[str, str] = {}
    seen_sigs: dict[tuple, str] = {}
    for pid, rec in registry.items():
        slug = rec["slug"]
        if not _SLUG_RE.match(slug):
            raise CatalogError(f"{pid}: slug {slug!r} is not lower kebab-case")
        if slug in seen_slugs:
            raise CatalogError(f"{pid}: slug {slug!r} already used by {seen_slugs[slug]}")
        seen_slugs[slug] = pid
        if rec["family"] not in FAMILIES:
            raise CatalogError(f"{pid}: unknown family {rec['family']!r}")
        phases = rec["phases"]
        if not phases:
            raise CatalogError(f"{pid}: a record needs at least one phase")
        phase_ids = [p["id"] for p in phases]
        if len(set(phase_ids)) != len(phase_ids):
            raise CatalogError(f"{pid}: duplicate phase ids {phase_ids}")
        for phase in phases:
            if not phase["obligations"] or not phase["gates"]:
                raise CatalogError(f"{pid}/{phase['id']}: needs an obligation and a gate")
        sig = _signature(rec)
        if sig in seen_sigs:
            raise CatalogError(f"{pid}: phase signature collides with {seen_sigs[sig]}")
        seen_sigs[sig] = pid
        gap = KERNEL_GAPS.get(pid)
        want = [gap] if gap else []
        got = extra_primitives(rec)
        if got != want:
            raise CatalogError(f"{pid}: kernel gate yields {got}, table declares {want}")
        if rec["kernel_gap"]["extra_primitives"] != want:
            raise CatalogError(f"{pid}: kernel_gap block disagrees with KERNEL_GAPS")
        engine = rec["engine"]
        if engine is not None and not (_package_dir() / f"{engine}.py").is_file():
            raise CatalogError(f"{pid}: engine module {engine!r} is not in the package")
    for kind, module in STAGE_ENGINES.items():
        if not (_package_dir() / f"{module}.py").is_file():
            raise CatalogError(f"stage kind {kind!r}: engine {module!r} is not in the package")


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict[str, Any]]:
    registry = {
        pid: _build_record(pid, slug, family, open_rounds, close)
        for pid, slug, family, open_rounds, close in _BLUEPRINT
    }
    _check(registry)
    return registry


def _normalise_pid(pid: str) -> str:
    text = str(pid).strip().upper()
    match = re.fullmatch(r"P0*(\d{1,2})", text)
    if match is None:
        raise UnknownProtocol(pid)
    return f"P{int(match.group(1)):02d}"


# --------------------------------------------------------------------------- public API


def by_id(pid: str | None = None) -> dict[str, Any]:
    """Protocol records keyed by id, or one record when ``pid`` is given.

    ``by_id()`` returns ``{"P01": record, ..., "P58": record}`` in id order;
    ``by_id("P07")`` returns the P07 record.  Records are deep copies, so callers
    may mutate them (e.g. to build negative controls) without touching the
    registry.  Raises :class:`UnknownProtocol` for an unknown id.
    """
    registry = _registry()
    if pid is None:
        return copy.deepcopy(registry)
    key = _normalise_pid(pid)
    if key not in registry:
        raise UnknownProtocol(pid)
    return copy.deepcopy(registry[key])


def get(pid: str) -> dict[str, Any]:
    """The record with id ``pid`` (``"P07"``, ``"p7"`` and ``"P07"`` all resolve)."""
    return by_id(pid)


def by_slug(slug: str) -> dict[str, Any]:
    """The record whose slug is ``slug``; raises :class:`UnknownProtocol`."""
    wanted = str(slug).strip().lower()
    for rec in _registry().values():
        if rec["slug"] == wanted:
            return copy.deepcopy(rec)
    raise UnknownProtocol(slug)


def records() -> list[dict[str, Any]]:
    """All 58 records as a list in id order (deep copies)."""
    return [copy.deepcopy(rec) for rec in _registry().values()]


def ids() -> list[str]:
    """``["P01", ..., "P58"]``."""
    return list(_registry())


def slugs() -> list[str]:
    """Slugs in id order."""
    return [rec["slug"] for rec in _registry().values()]


def families() -> dict[str, list[str]]:
    """Family -> ids in that family, families in declaration order."""
    out: dict[str, list[str]] = {family: [] for family in FAMILIES}
    for pid, rec in _registry().items():
        out[rec["family"]].append(pid)
    return out


def expressible_ids() -> list[str]:
    """Ids the linear kernel can run (51 of 58)."""
    return [pid for pid, rec in _registry().items() if not extra_primitives(rec)]


def inexpressible_ids() -> list[str]:
    """Ids that need a kernel primitive the linear kernel lacks (7 of 58)."""
    return [pid for pid, rec in _registry().items() if extra_primitives(rec)]


def kernel_gap(pid: str) -> dict[str, Any]:
    """Census row for ``pid``: id, status, extra_primitives, reasons."""
    rec = by_id(pid)
    extra = extra_primitives(rec)
    return {
        "id": rec["id"],
        "status": kernel_status(rec),
        "extra_primitives": extra,
        "reasons": [GAP_REASON.get(prim, f"requires {prim}") for prim in extra],
    }


def engine_for(pid: str) -> str | None:
    """Module name in this package implementing ``pid``'s engine, if any."""
    return by_id(pid)["engine"]


def engine_for_stage(kind: str) -> str | None:
    """Module name in this package that runs councilspec stage ``kind``, if any."""
    return STAGE_ENGINES.get(str(kind))


def validate() -> dict[str, Any]:
    """Build (or reuse) the registry, re-run every consistency check, summarise.

    Raises :class:`CatalogError` on the first inconsistency.
    """
    registry = _registry()
    _check(registry)
    return {
        "n": len(registry),
        "expressible_n": len(expressible_ids()),
        "needs_kernel_change_n": len(inexpressible_ids()),
        "needs_kernel_change": inexpressible_ids(),
        "specs_present": sum(1 for rec in registry.values() if rec["spec"]["present"]),
        "reconstructed": [
            pid for pid, rec in registry.items() if not rec["spec"]["present"]
        ],
        "families": {family: len(members) for family, members in families().items()},
        "engines": {pid: rec["engine"] for pid, rec in registry.items() if rec["engine"]},
    }
