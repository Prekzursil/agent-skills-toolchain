"""Control workflows for IMP-0183 common-core fusion.

Three review-pipeline siblings share ingest/lint/review/ship and each carries
one unique stage. A disjoint pair has empty intersection. An identical pair
factorises to a core equal to both parents.
"""
from __future__ import annotations

from workflow_foundry.workflow_ir import Stage, Workflow


def _st(
    sid: str,
    kind: str,
    *,
    roles: tuple[str, ...] = (),
    gate: dict | None = None,
    tool: str = "",
    inn: str = "artifact",
    out: str = "artifact",
) -> Stage:
    return Stage(
        id=sid,
        kind=kind,
        roles=roles,
        gate=gate,
        tool_class=tool,
        in_contract=inn,
        out_contract=out,
    )


def ingest() -> Stage:
    return _st("ingest", "ingest", roles=("importer",), tool="fs", inn="files", out="bundle")


def lint() -> Stage:
    return _st("lint", "lint", roles=("static-analyzer",), tool="linter", inn="bundle", out="bundle")


def review() -> Stage:
    return _st(
        "review",
        "review",
        roles=("adversary", "author"),
        gate={"unanimity": True, "min_reviewers": 2},
        tool="council",
        inn="bundle",
        out="verdict",
    )


def ship() -> Stage:
    return _st("ship", "ship", roles=("releaser",), tool="registry", inn="verdict", out="release")


def patch() -> Stage:
    return _st("patch", "patch", roles=("repairer",), tool="editor", inn="verdict", out="bundle")


def unit_test() -> Stage:
    return _st(
        "test",
        "test",
        roles=("tester",),
        gate={"coverage_min": 80},
        tool="pytest",
        inn="bundle",
        out="bundle",
    )


def security() -> Stage:
    return _st("security", "security", roles=("sast",), tool="scanner", inn="verdict", out="verdict")


def workflow_alpha() -> Workflow:
    # ingest -> lint -> review -> patch -> ship
    stages = [ingest(), lint(), review(), patch(), ship()]
    return Workflow(id="alpha", stages=stages, edges=[], licences=("MIT",))


def workflow_beta() -> Workflow:
    # ingest -> lint -> test -> review -> ship  (ids renamed vs alpha)
    stages = [
        ingest().with_id("pull"),
        lint().with_id("static"),
        unit_test(),
        review().with_id("critique"),
        ship().with_id("publish"),
    ]
    return Workflow(id="beta", stages=stages, edges=[], licences=("Apache-2.0",))


def workflow_gamma() -> Workflow:
    # ingest -> lint -> review -> security -> ship
    stages = [
        ingest().with_id("load"),
        lint().with_id("check"),
        review().with_id("red-team"),
        security(),
        ship().with_id("cut"),
    ]
    return Workflow(id="gamma", stages=stages, edges=[], licences=("MIT", "BSD-3-Clause"))


def review_family() -> list[Workflow]:
    return [workflow_alpha(), workflow_beta(), workflow_gamma()]


def disjoint_pair() -> list[Workflow]:
    a = Workflow(
        id="compile-link",
        stages=[
            _st("compile", "compile", roles=("builder",), tool="cc", inn="src", out="obj"),
            _st("link", "link", roles=("builder",), tool="ld", inn="obj", out="bin"),
        ],
        licences=("GPL-3.0-only",),
    )
    b = Workflow(
        id="fetch-render",
        stages=[
            _st("fetch", "fetch", roles=("net",), tool="http", inn="url", out="html"),
            _st("render", "render", roles=("ui",), tool="browser", inn="html", out="png"),
        ],
        licences=("MIT",),
    )
    return [a, b]


def identical_pair() -> list[Workflow]:
    w = workflow_alpha()
    clone = Workflow(
        id="alpha-clone",
        stages=[s.with_id(f"c-{s.id}") for s in w.stages],
        edges=[],
        licences=w.licences,
    )
    return [w, clone]
