"""CC-0015 encoding of the 21 program stopping conditions.

CC-0015's catalog artifact is absent on this tree. TST-0347 hosts the working
encoding derived from catalog-cited condition text (and, where the spec file
is absent, from adjacent catalog anchors). TST-0347 attacks THIS encoding; it
does not invent a second parallel encoding.

Each predicate returns exactly one of TRUE | FALSE | NOT-CHECKED plus evidence.
NOT-CHECKED is never a pass. A predicate no mutation can flip is DECORATIVE.
Condition 13 under binding PR-ONLY is PERMANENTLY-UNSATISFIABLE-AS-WRITTEN:
FALSE, never NOT-CHECKED, never silently skipped.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

Value = Literal["TRUE", "FALSE", "NOT-CHECKED"]
CLOSED = ("IMPLEMENTED", "SUPERSEDED", "REJECTED-WITH-OWNER-REASONING")
REQ_CLOSED = ("VERIFIED", "INFERRED", "UNVERIFIED", "REJECTED", "DEFERRED")
TEST_OK = ("GREEN",)
COMPAT_OK = ("SUPPORTED", "NOT-CHECKED", "INFERRED")


@dataclass
class Verdict:
    value: Value
    evidence: str
    pathology: str | None = None
    owner_decision_required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "evidence": self.evidence,
            "pathology": self.pathology,
            "owner_decision_required": self.owner_decision_required,
        }


@dataclass
class World:
    """Isolated program state the predicates read. Mutations copy this object."""

    option_states: dict[str, str] = field(default_factory=dict)
    requirement_dispositions: dict[str, str] = field(default_factory=dict)
    rerun_until_green: bool = False
    cited_green_attempts: dict[str, int] = field(default_factory=dict)
    required_tests: dict[str, str] = field(default_factory=dict)
    suites: dict[str, dict[str, Any]] = field(default_factory=dict)
    secret_in_artifacts: bool = False
    compat_cells: dict[str, str] = field(default_factory=dict)
    bench_run_ids: list[str] = field(default_factory=list)
    primary_delta: float | None = 0.0
    secondary_delta: float | None = 0.0
    noninferiority_margin: float | None = 0.05
    telemetry_egress: bool = False
    telemetry_opt_in_recorded: bool = False
    negative_evidence_dropped: bool = False
    unaccepted_blind_spots: list[str] = field(default_factory=list)
    docs_code_agree: bool = True
    release_mode: str = "PR-ONLY"
    release_channel: str | None = None
    channel_success: dict[str, bool | None] = field(default_factory=dict)
    owner_amendment_13: str | None = None
    rollback_tested: bool = True
    unknowns: dict[str, dict[str, Any]] = field(default_factory=dict)
    workflow_candidates_qualified: int = 160
    blueprints_executable: int = 96
    council_protocols: int = 48
    presets: int = 64
    work_units: int = 2048
    platform_options: int = 160
    flagship_e2e: int = 40
    test_layers: int = 36


def satisfying_world() -> World:
    """A world in which every *satisfiable* predicate reads TRUE.

    Condition 13 stays FALSE/UNSATISFIABLE because release_mode is PR-ONLY and
    no owner amendment has bound a substitute channel. That is the binding
    world, not a test skip.
    """
    return World(
        option_states={"OPT-A": "IMPLEMENTED", "OPT-B": "SUPERSEDED", "OPT-C": "REJECTED-WITH-OWNER-REASONING"},
        requirement_dispositions={"REQ-1": "VERIFIED", "REQ-2": "DEFERRED"},
        rerun_until_green=False,
        cited_green_attempts={"sha-stable": 1},
        required_tests={"suite.required": "GREEN"},
        suites={
            "suite.required": {
                "control_path": "fixtures/neg_control.py",
                "control_observed_fail": True,
            }
        },
        secret_in_artifacts=False,
        compat_cells={"linux-bash": "SUPPORTED", "macos-zsh": "NOT-CHECKED"},
        bench_run_ids=["run-1", "run-2"],
        primary_delta=0.12,
        secondary_delta=-0.01,
        noninferiority_margin=0.05,
        telemetry_egress=False,
        telemetry_opt_in_recorded=False,
        negative_evidence_dropped=False,
        unaccepted_blind_spots=[],
        docs_code_agree=True,
        release_mode="PR-ONLY",
        release_channel=None,
        channel_success={},
        owner_amendment_13=None,
        rollback_tested=True,
        unknowns={"UNK-1": {"experiment": "run-probe-X", "owner_impact": "blocks-release"}},
        workflow_candidates_qualified=160,
        blueprints_executable=96,
        council_protocols=48,
        presets=64,
        work_units=2048,
        platform_options=160,
        flagship_e2e=40,
        test_layers=36,
    )


def canary_satisfying_world() -> World:
    """Forbidden (non-binding) world where condition 13 can read TRUE."""
    w = satisfying_world()
    w.release_mode = "CANARY"
    w.release_channel = "canary"
    w.channel_success = {"canary": True}
    return w


def _true(ev: str) -> Verdict:
    return Verdict("TRUE", ev)


def _false(ev: str, pathology: str | None = None, owner: bool = False) -> Verdict:
    return Verdict("FALSE", ev, pathology=pathology, owner_decision_required=owner)


def _nc(ev: str) -> Verdict:
    return Verdict("NOT-CHECKED", ev)


def eval_01(w: World) -> Verdict:
    if not w.option_states:
        return _nc("no selected-option set supplied")
    open_ids = [i for i, s in w.option_states.items() if s not in CLOSED]
    if open_ids:
        return _false(f"selected options not terminal: {open_ids}")
    return _true(f"{len(w.option_states)} selected options in closed states")


def eval_02(w: World) -> Verdict:
    if not w.requirement_dispositions:
        return _nc("no requirement register supplied")
    missing = [i for i, s in w.requirement_dispositions.items() if s not in REQ_CLOSED]
    if missing:
        return _false(f"requirements without disposition: {missing}")
    return _true(f"{len(w.requirement_dispositions)} requirements have dispositions")


def eval_03(w: World) -> Verdict:
    if w.rerun_until_green:
        return _false("rerun-until-green is enabled; cited greens may be laundered")
    dirty = [s for s, n in w.cited_green_attempts.items() if n > 1]
    if dirty:
        return _false(f"cited greens required >1 attempt: {dirty}")
    if not w.cited_green_attempts:
        return _nc("no cited-green attempt ledger")
    return _true("cited greens are single-attempt at their SHA")


def eval_04(w: World) -> Verdict:
    if not w.required_tests:
        return _nc("no required-test ledger")
    red = [i for i, s in w.required_tests.items() if s == "RED"]
    if red:
        return _false(f"required tests red: {red}")
    unchecked = [i for i, s in w.required_tests.items() if s not in TEST_OK and s != "RED"]
    if unchecked:
        return _nc(f"required tests not green and not red: {unchecked}")
    return _true("no required test is red")


def eval_05(w: World) -> Verdict:
    if not w.suites:
        return _nc("no suite control census")
    holes = []
    for name, row in w.suites.items():
        if not row.get("control_path") or not row.get("control_observed_fail"):
            holes.append(name)
    if holes:
        return _false(f"suites without an observed-failing negative control: {holes}")
    return _true("every suite has a control that has been observed to fail")


def eval_06(w: World) -> Verdict:
    if w.secret_in_artifacts:
        return _false("live secret detected in an artifact bundle")
    return _true("no live secret in artifacts")


def eval_07(w: World) -> Verdict:
    if not w.compat_cells:
        return _nc("no compatibility matrix")
    fake = [c for c, s in w.compat_cells.items() if s == "UNTESTED-AS-SUPPORTED"]
    if fake:
        return _false(f"untested cells read as supported: {fake}")
    bad = [c for c, s in w.compat_cells.items() if s not in COMPAT_OK]
    if bad:
        return _false(f"illegal cell marks: {bad}")
    return _true("untested cells are NOT-CHECKED, never SUPPORTED")


def eval_08(w: World) -> Verdict:
    if not w.bench_run_ids or w.primary_delta is None or w.noninferiority_margin is None:
        return _nc("benchmark ledger, primary delta or margin missing")
    if w.primary_delta <= 0:
        return _false(f"primary delta {w.primary_delta} is not an improvement")
    if w.secondary_delta is None:
        return _nc("secondary delta missing; cannot judge material regression")
    if w.secondary_delta < -w.noninferiority_margin:
        return _false(
            f"material regression: secondary {w.secondary_delta} beyond margin "
            f"{w.noninferiority_margin}; run_ids={w.bench_run_ids}"
        )
    return _true(f"improvement within margin; run_ids={w.bench_run_ids}")


def eval_09(w: World) -> Verdict:
    if w.telemetry_egress and not w.telemetry_opt_in_recorded:
        return _false("telemetry left the machine without a recorded owner opt-in")
    return _true("no unauthorised telemetry egress")


def eval_10(w: World) -> Verdict:
    if w.negative_evidence_dropped:
        return _false("negative or contradictory evidence was dropped from the synthesis")
    return _true("negative evidence retained")


def eval_11(w: World) -> Verdict:
    if w.unaccepted_blind_spots:
        return _false(f"blind spots neither unitised nor accepted: {w.unaccepted_blind_spots}")
    return _true("every material blind spot is a unit or an accepted residual")


def eval_12(w: World) -> Verdict:
    if not w.docs_code_agree:
        return _false("docs and code diverge")
    return _true("docs and code agree")


def eval_13(w: World) -> Verdict:
    """Release/canary succeeds.

    The evaluator has no special case: it reads release_channel and
    channel_success. Under binding PR-ONLY the channel is absent, so the
    as-written referent is unsatisfiable. An owner amendment binds a
    substitute channel (pr-merge-plus-rollback-rehearsal) in the same fields.
    """
    if w.owner_amendment_13:
        channel = w.owner_amendment_13
        if w.release_channel and w.release_channel != channel:
            channel = w.release_channel
    else:
        channel = w.release_channel
    if not channel:
        return _false(
            "PR-ONLY has no canary channel; as-written 'release/canary succeeds' "
            "has no satisfiable referent. Owner must amend to a PR-merge-plus-"
            "rollback-rehearsal equivalent or accept the program cannot stop.",
            pathology="PERMANENTLY-UNSATISFIABLE-AS-WRITTEN",
            owner=True,
        )
    ok = w.channel_success.get(channel)
    if ok is None:
        return _nc(f"release channel {channel} has no success observation")
    if ok:
        return _true(f"release channel {channel} succeeded")
    return _false(f"release channel {channel} failed")


def eval_14(w: World) -> Verdict:
    if not w.rollback_tested:
        return _false("rollback has not been tested")
    return _true("rollback is tested")


def eval_15(w: World) -> Verdict:
    if not w.unknowns:
        return _nc("no unknowns register")
    holes = [
        i
        for i, row in w.unknowns.items()
        if not row.get("experiment") or not row.get("owner_impact")
    ]
    if holes:
        return _false(f"unknowns missing experiment or owner impact: {holes}")
    return _true("every residual unknown has a named experiment and impact")


def eval_16(w: World) -> Verdict:
    n = w.workflow_candidates_qualified
    if n < 0:
        return _nc("candidate count not supplied")
    if n < 160:
        return _false(f"qualified workflow candidates {n} < 160")
    return _true(f"qualified workflow candidates {n} >= 160")


def eval_17(w: World) -> Verdict:
    n = w.blueprints_executable
    if n < 0:
        return _nc("blueprint count not supplied")
    if n < 96:
        return _false(f"executable blueprints {n} < 96")
    return _true(f"executable blueprints {n} >= 96")


def eval_18(w: World) -> Verdict:
    if w.council_protocols < 0 or w.presets < 0:
        return _nc("protocol or preset count not supplied")
    if w.council_protocols < 48:
        return _false(f"council protocols {w.council_protocols} < 48")
    if w.presets < 64:
        return _false(f"presets {w.presets} < 64")
    return _true(f"protocols {w.council_protocols} >= 48 and presets {w.presets} >= 64")


def eval_19(w: World) -> Verdict:
    if w.work_units < 0 or w.platform_options < 0:
        return _nc("work-unit or platform-option count not supplied")
    if w.work_units < 2048:
        return _false(f"work units {w.work_units} < 2048")
    if w.platform_options < 160:
        return _false(f"platform options {w.platform_options} < 160")
    return _true(f"work units {w.work_units} >= 2048 and platform options {w.platform_options} >= 160")


def eval_20(w: World) -> Verdict:
    if w.flagship_e2e < 0:
        return _nc("flagship count not supplied")
    if w.flagship_e2e < 40:
        return _false(f"flagship e2e workflows {w.flagship_e2e} < 40")
    return _true(f"flagship e2e workflows {w.flagship_e2e} >= 40")


def eval_21(w: World) -> Verdict:
    if w.test_layers < 0:
        return _nc("test-layer count not supplied")
    if w.test_layers < 36:
        return _false(f"test layers {w.test_layers} < 36")
    return _true(f"test layers {w.test_layers} >= 36")


PREDICATES: list[dict[str, Any]] = [
    {
        "id": 1,
        "spec_line": 11378,
        "citation": "catalog",
        "text": "every selected option is IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING",
        "eval": eval_01,
    },
    {
        "id": 2,
        "spec_line": 11379,
        "citation": "reconstructed-adjacent",
        "text": "every extracted owner requirement has a recorded disposition (none DISAPPEARED)",
        "eval": eval_02,
    },
    {
        "id": 3,
        "spec_line": 11380,
        "citation": "catalog",
        "text": "cited greens are single-attempt at their SHA (no rerun-until-green)",
        "eval": eval_03,
    },
    {
        "id": 4,
        "spec_line": 11381,
        "citation": "catalog",
        "text": "no required test is red",
        "eval": eval_04,
    },
    {
        "id": 5,
        "spec_line": 11382,
        "citation": "catalog",
        "text": "mutation and negative-control coverage demonstrate detector validity",
        "eval": eval_05,
    },
    {
        "id": 6,
        "spec_line": 11383,
        "citation": "reconstructed-adjacent",
        "text": "artifact corpus contains no live secrets",
        "eval": eval_06,
    },
    {
        "id": 7,
        "spec_line": 11384,
        "citation": "catalog",
        "text": "compatibility matrix: an untested cell is NOT-CHECKED, never SUPPORTED",
        "eval": eval_07,
    },
    {
        "id": 8,
        "spec_line": 11385,
        "citation": "catalog",
        "text": "benchmark results show the intended improvement without material regression",
        "eval": eval_08,
    },
    {
        "id": 9,
        "spec_line": 11386,
        "citation": "reconstructed-adjacent",
        "text": "no telemetry egress without a recorded owner opt-in",
        "eval": eval_09,
    },
    {
        "id": 10,
        "spec_line": 11387,
        "citation": "reconstructed-adjacent",
        "text": "negative and contradictory evidence is preserved into the synthesis",
        "eval": eval_10,
    },
    {
        "id": 11,
        "spec_line": 11388,
        "citation": "reconstructed-adjacent",
        "text": "every material blind spot is a work unit or an explicitly accepted residual",
        "eval": eval_11,
    },
    {
        "id": 12,
        "spec_line": 11389,
        "citation": "catalog",
        "text": "docs and code agree",
        "eval": eval_12,
    },
    {
        "id": 13,
        "spec_line": 11390,
        "citation": "catalog",
        "text": "release/canary succeeds",
        "eval": eval_13,
    },
    {
        "id": 14,
        "spec_line": 11391,
        "citation": "catalog",
        "text": "rollback is tested",
        "eval": eval_14,
    },
    {
        "id": 15,
        "spec_line": 11392,
        "citation": "catalog",
        "text": "every residual unknown has a named settling experiment and owner-visible impact",
        "eval": eval_15,
    },
    {
        "id": 16,
        "spec_line": 11393,
        "citation": "catalog",
        "text": ">=160 workflow candidates classified with provenance and licence",
        "eval": eval_16,
    },
    {
        "id": 17,
        "spec_line": 11394,
        "citation": "catalog",
        "text": ">=96 materially distinct workflow blueprints executable under the selected tiers",
        "eval": eval_17,
    },
    {
        "id": 18,
        "spec_line": 11395,
        "citation": "catalog",
        "text": ">=48 council protocols and >=64 presets",
        "eval": eval_18,
    },
    {
        "id": 19,
        "spec_line": 11396,
        "citation": "catalog",
        "text": ">=2048 work units and >=160 platform options",
        "eval": eval_19,
    },
    {
        "id": 20,
        "spec_line": 11397,
        "citation": "reconstructed-floor",
        "text": ">=40 flagship workflows with end-to-end tests",
        "eval": eval_20,
    },
    {
        "id": 21,
        "spec_line": 11398,
        "citation": "reconstructed-floor",
        "text": ">=36 test layers present",
        "eval": eval_21,
    },
]


def evaluate_all(w: World) -> list[dict[str, Any]]:
    rows = []
    for spec in PREDICATES:
        v = spec["eval"](w)
        rows.append(
            {
                "id": spec["id"],
                "spec_line": spec["spec_line"],
                "citation": spec["citation"],
                "text": spec["text"],
                **v.as_dict(),
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Program-complete requires 21 TRUE. NOT-CHECKED blocks as hard as FALSE.

    A DECORATIVE (unfalsifiable) predicate is never counted TRUE even if it
    currently reads TRUE.
    """
    values = []
    for r in rows:
        val = r["value"]
        if r.get("pathology") == "DECORATIVE":
            val = "FALSE"
        values.append(val)
    counts = {
        "TRUE": values.count("TRUE"),
        "FALSE": values.count("FALSE"),
        "NOT-CHECKED": values.count("NOT-CHECKED"),
    }
    complete = counts["TRUE"] == 21 and counts["FALSE"] == 0 and counts["NOT-CHECKED"] == 0
    return {
        "counts": counts,
        "program_complete": complete,
        "verdict": "PROGRAM-COMPLETE" if complete else "PROGRAM-INCOMPLETE",
    }


def decorative_control(eval_fn: Callable[[World], Verdict], w: World, mutate: Callable[[World], World]) -> bool:
    """True when eval_fn reads TRUE on both w and mutate(w) — unfalsifiable."""
    before = eval_fn(w).value
    after = eval_fn(mutate(deepcopy(w))).value
    return before == "TRUE" and after == "TRUE"
