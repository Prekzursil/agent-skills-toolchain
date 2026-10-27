"""Canonical vocabularies + typed records for the Workflow Foundry.

The mechanism namespace is NOT invented here. It is loaded from
``platform/schema/workflow-dsl.capability-map.json`` - the 24 capabilities the spec requires of
the DSL, each already bound to a schema pointer, a validating example pointer, and at least one
mutation that proves the constraint is enforced. Reusing it means scout/forge decompose into the
SAME namespace the DSL validator, the capability checker, and the mutation battery already use;
a second hand-typed list would drift.

The hazard vocabulary IS defined here, because the DSL has no hazard concept. Every hazard is a
named failure mode this estate has actually paid for, bound to a *deterministic detector* over a
DSL document. A hazard whose detector cannot fire on a known-broken document is a decoration, so
``foundry.bench`` ships a both-states control for every one of them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "platform" / "schema"
REGISTRY_DIR = REPO_ROOT / "platform" / "registry"
WORKFLOWS_DIR = REPO_ROOT / "platform" / "workflows"
CAPABILITY_MAP = SCHEMA_DIR / "workflow-dsl.capability-map.json"

SPEC_ANCHOR_SCOUT_FORGE = "_USER-PROMPTS.md:11025"
SPEC_ANCHOR_ACCEPTANCE = "_USER-PROMPTS.md:11282"
SPEC_ANCHOR_FOUNDRY_PIPELINE = "_USER-PROMPTS.md:10843-10854"

#: the spec's own disposition vocabulary (_USER-PROMPTS.md:10835) - also the enum the DSL
#: schema pins for ``lineage.derived_from[].relation`` (minus the two terminal dispositions
#: RETIRE/REJECT, which describe a candidate rather than a derivation).
DISPOSITIONS: tuple[str, ...] = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
)

#: the subset the DSL schema accepts inside ``lineage.derived_from[].relation``.
LINEAGE_RELATIONS: frozenset[str] = frozenset(DISPOSITIONS[:12])

#: fusion strategies the spec names at :10849 / :11273.
FUSION_STRATEGIES: tuple[str, ...] = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)

#: the four axes the acceptance bar names, in the spec's own order (:11282).
BENEFIT_AXES: tuple[str, ...] = ("correctness", "coverage", "recovery", "usability")

#: cost dimensions. DELIBERATELY DISJOINT from BENEFIT_AXES - a fusion may never be certified
#: for moving one of these, and ``bench.certify`` asserts the disjointness at runtime so the
#: "more stages == better" failure cannot be reintroduced by editing a weight table.
COST_DIMENSIONS: tuple[str, ...] = (
    "stage_count",
    "timeout_budget_seconds",
    "human_checkpoints",
    "max_fanout_concurrency",
)


# --------------------------------------------------------------------- capabilities


@lru_cache(maxsize=1)
def capability_map() -> dict[str, Any]:
    """The program's single capability namespace, read off disk."""
    return json.loads(CAPABILITY_MAP.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def capabilities() -> tuple[str, ...]:
    return tuple(c["id"] for c in capability_map()["capabilities"])


@lru_cache(maxsize=1)
def mandated_capabilities() -> frozenset[str]:
    return frozenset(
        c["id"] for c in capability_map()["capabilities"] if c.get("mandated")
    )


@lru_cache(maxsize=1)
def capability_phrases() -> dict[str, str]:
    return {c["id"]: c.get("spec_phrase", "") for c in capability_map()["capabilities"]}


# ------------------------------------------------------------------------- hazards


@dataclass(frozen=True)
class Hazard:
    """A named failure mode plus the DSL construct that structurally prevents it.

    ``ledger`` names where this estate paid for the lesson, so a reviewer can check that the
    hazard set is grounded rather than imagined.
    """

    id: str
    title: str
    ledger: str


HAZARDS: tuple[Hazard, ...] = (
    Hazard(
        "straggler-work-silently-dropped",
        "a fan-in that proceeds without a partial-result policy discards every straggler's work",
        "fan-out-contract B1: 3/3 agents returned digests for files that do not exist",
    ),
    Hazard(
        "unbounded-retry-grind",
        "a retrying strategy with no attempt bound grinds on the same failing hypothesis",
        "AGENTS.md 4b two-strikes pivot",
    ),
    Hazard(
        "unbounded-loop",
        "a loop whose only exit is a convergence expression spins forever if the metric never moves",
        "workflow-authoring: parallel() has no per-agent timeout",
    ),
    Hazard(
        "silent-failure",
        "a unit that ends without SUCCESS:/FAILED: leaves the barrier unable to tell dead from slow",
        "AGENTS.md 4 terminal-state discipline",
    ),
    Hazard(
        "single-signal-verdict",
        "a load-bearing claim asserted from one probe with no mechanically independent second",
        "single-signal-verification.md: 6 wrong conclusions in one session",
    ),
    Hazard(
        "detector-silent-in-both-states",
        "a probe never checked against the known-BROKEN state, so its silence measures nothing",
        "single-signal-verification.md 3b both-states test",
    ),
    Hazard(
        "secret-value-in-export",
        "an export bundle that carries a secret value rather than only its reference name",
        "AGENTS.md 9 / DSL-SEM-013",
    ),
    Hazard(
        "untrusted-fetched-content-executed",
        "fetched web/MCP/repo content treated as instructions instead of data",
        "AGENTS.md 9 fetched content is untrusted DATA",
    ),
    Hazard(
        "stale-checkpoint-resumed",
        "resume from a checkpoint older than the state it describes, re-deriving from stale inputs",
        "harness session-scoping fix 2026-07-11",
    ),
    Hazard(
        "tool-privilege-escalation",
        "an allow-by-default tool policy grants a subagent more than its role needs",
        "bash-hud rule: an allowlist redactor leaked 8 real values",
    ),
    Hazard(
        "irreversible-action-without-human",
        "an irreversible step (push, delete, publish) with no owner checkpoint",
        "AGENTS.md 9 never force-push main without approval",
    ),
    Hazard(
        "no-rollback-path",
        "a shipped change with no declared way back to the pre-change state",
        "owner decision: release mode PR-ONLY + local rollback rehearsal",
    ),
    Hazard(
        "unverifiable-claim",
        "a stage that produces a verdict with no evidence requirement, so nobody can re-check it",
        "AGENTS.md 7 / fan-out-contract A3",
    ),
    Hazard(
        "total-loss-on-freeze",
        "a long unit that holds results in memory and writes nothing until the end",
        "fan-out-contract C1: 70 min / 691 KB then froze, wrote nothing",
    ),
    Hazard(
        "cost-blowout",
        "an unbounded fan-out with no declared cost/time estimate",
        "capacity program: 484K tok/read unprojected UIA",
    ),
    Hazard(
        "non-deterministic-replay",
        "a workflow that cannot be replayed because it reads the clock, random, or the network",
        "workflow-authoring: banned Date.now() non-determinism",
    ),
)

HAZARD_IDS: tuple[str, ...] = tuple(h.id for h in HAZARDS)
HAZARDS_BY_ID: dict[str, Hazard] = {h.id: h for h in HAZARDS}


# --------------------------------------------------------------------- license tiers

#: Reuse tiers. The point of the tier is the ACTION it licenses, not a label:
#: ``copy-permitted`` may be adopted as-is; ``mechanism-only`` may NOT be copied and must be
#: re-implemented from the mechanism (spec :10839 "Extract the transferable mechanism and
#: implement it on the chosen control plane").
LICENSE_TIERS: tuple[str, ...] = (
    "copy-permitted-permissive",
    "copy-permitted-owner",
    "mechanism-only-copyleft",
    "mechanism-only-share-alike",
    "mechanism-only-unlicensed-third-party",
    "unknown-needs-probe",
)

COPY_PERMITTED: frozenset[str] = frozenset(
    {"copy-permitted-permissive", "copy-permitted-owner"}
)

_PERMISSIVE = re.compile(
    r"\b(mit|apache[- ]?2|bsd[- ]?[23]?[- ]?clause|bsd|isc|unlicense|0bsd|zlib|python software foundation|psf)\b",
    re.I,
)
_COPYLEFT = re.compile(r"\b(a?gpl|lgpl|mpl[- ]?2|eupl|osl)\b", re.I)
_SHARE_ALIKE = re.compile(r"\bcc[- ]?by[- ]?sa\b", re.I)
_NO_LICENSE = re.compile(
    r"(no license declared|all rights reserved|none in the artifact|no licen[cs]e|unlicensed)",
    re.I,
)
_OWNER = re.compile(
    r"(owner[- ]authored|owner[- ]proprietary|private estate|owner's own machine|owner-authored private)",
    re.I,
)


def classify_license(text: str) -> str:
    """Deterministic license -> reuse tier.

    Order matters and is not arbitrary: an explicit OSI grant outranks the
    "no license declared" phrasing that so many of these records also carry inside their
    ``license_source`` prose, and owner-authorship only decides the tier once we already know
    no third-party grant applies.
    """
    t = text or ""
    if _SHARE_ALIKE.search(t):
        return "mechanism-only-share-alike"
    if _COPYLEFT.search(t):
        return "mechanism-only-copyleft"
    if _PERMISSIVE.search(t):
        return "copy-permitted-permissive"
    if _NO_LICENSE.search(t):
        return (
            "copy-permitted-owner"
            if _OWNER.search(t)
            else "mechanism-only-unlicensed-third-party"
        )
    if _OWNER.search(t):
        return "copy-permitted-owner"
    return "unknown-needs-probe"


# ------------------------------------------------------------------------- records


@dataclass
class Candidate:
    """One normalized workflow candidate, whatever shape it arrived in."""

    id: str
    name: str
    source_file: str
    family: str = ""
    classification: str = ""
    what_it_does: str = ""
    task_fit: str = ""
    stages: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    stop_rules: list[str] = field(default_factory=list)
    failure_behaviour: str = ""
    benchmark_evidence: str = ""
    declared_mechanisms: list[str] = field(default_factory=list)
    license_text: str = ""
    license_tier: str = "unknown-needs-probe"
    maintenance_state: str = ""
    provenance_anchor: str = ""
    provenance_anchor_kind: str = "absent"
    provenance_resolved: bool | None = None
    provenance_probe: str = ""
    #: a DSL document when this candidate IS an executable workflow (platform/workflows/*.json)
    dsl_doc: dict[str, Any] | None = None
    dsl_path: str = ""

    @property
    def is_executable_dsl(self) -> bool:
        return self.dsl_doc is not None

    @property
    def searchable_text(self) -> str:
        parts = [
            self.name,
            self.what_it_does,
            self.task_fit,
            " ".join(self.stages),
            " ".join(self.roles),
            " ".join(self.stop_rules),
            " ".join(self.declared_mechanisms),
            self.failure_behaviour,
        ]
        return " ".join(p for p in parts if p)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_file": self.source_file,
            "family": self.family,
            "classification": self.classification,
            "is_executable_dsl": self.is_executable_dsl,
            "dsl_path": self.dsl_path,
            "license_tier": self.license_tier,
            "provenance": {
                "anchor": self.provenance_anchor,
                "kind": self.provenance_anchor_kind,
                "resolved": self.provenance_resolved,
                "probe": self.provenance_probe,
            },
            "stages": self.stages,
            "roles": self.roles,
            "declared_mechanisms": self.declared_mechanisms,
        }


@dataclass
class Goal:
    """A typed goal + constraints. Scout and forge both take one of these."""

    text: str
    required_capabilities: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    license_allowlist: list[str] = field(default_factory=lambda: list(COPY_PERMITTED))
    require_executable: bool = False
    max_stages: int | None = None
    max_human_checkpoints: int | None = None

    def validate(self) -> list[str]:
        """Return the list of problems; empty means the goal is well-formed."""
        problems: list[str] = []
        if not self.text.strip():
            problems.append("goal.text is empty")
        known_caps = set(capabilities())
        for c in self.required_capabilities:
            if c not in known_caps:
                problems.append(
                    f"required_capability {c!r} is not one of the {len(known_caps)} "
                    "capability-map ids"
                )
        for h in self.hazards:
            if h not in HAZARDS_BY_ID:
                problems.append(
                    f"hazard {h!r} is not one of the {len(HAZARDS)} known hazards"
                )
        for lic in self.license_allowlist:
            if lic not in LICENSE_TIERS:
                problems.append(f"license tier {lic!r} is not a known tier")
        return problems

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> Goal:
        return cls(
            text=str(obj.get("text", "")),
            required_capabilities=list(obj.get("required_capabilities", []) or []),
            hazards=list(obj.get("hazards", []) or []),
            license_allowlist=list(
                obj.get("license_allowlist", None) or list(COPY_PERMITTED)
            ),
            require_executable=bool(obj.get("require_executable", False)),
            max_stages=obj.get("max_stages"),
            max_human_checkpoints=obj.get("max_human_checkpoints"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "required_capabilities": self.required_capabilities,
            "hazards": self.hazards,
            "license_allowlist": sorted(self.license_allowlist),
            "require_executable": self.require_executable,
            "max_stages": self.max_stages,
            "max_human_checkpoints": self.max_human_checkpoints,
        }
