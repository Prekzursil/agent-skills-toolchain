"""Twenty control families D1-D20 for WFA-0101.

The live 09-WORKFLOW-BLUEPRINT-LIBRARY.json is not on this worktree.
These reconstructions exercise recomposition, empty intersection,
degeneracy (one-stage LCS, family of seven), and licence union.
They are not a 108-blueprint library scan.
"""
from __future__ import annotations

from dataclasses import dataclass

from workflow_foundry.workflow_ir import Stage, Workflow


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    title: str
    members: tuple[Workflow, ...]
    notes: str


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


def ingest(sid: str = "ingest") -> Stage:
    return _st(sid, "ingest", roles=("importer",), tool="fs", inn="files", out="bundle")


def lint(sid: str = "lint") -> Stage:
    return _st(
        sid, "lint", roles=("static-analyzer",), tool="linter", inn="bundle", out="bundle"
    )


def review(sid: str = "review") -> Stage:
    return _st(
        sid,
        "review",
        roles=("adversary", "author"),
        gate={"unanimity": True, "min_reviewers": 2, "stop_rule": "unanimous"},
        tool="council",
        inn="bundle",
        out="verdict",
    )


def ship(sid: str = "ship") -> Stage:
    return _st(
        sid, "ship", roles=("releaser",), tool="registry", inn="verdict", out="release"
    )


def test(sid: str = "test") -> Stage:
    return _st(
        sid,
        "test",
        roles=("tester",),
        gate={"coverage_min": 80},
        tool="pytest",
        inn="bundle",
        out="bundle",
    )


def tick(sid: str = "tick") -> Stage:
    return _st(sid, "tick", roles=(), tool="", inn="", out="")


def unique(kind: str, i: int) -> Stage:
    return _st(
        f"{kind}-{i}",
        kind,
        roles=(f"role-{i}",),
        gate={"i": i, "stop_rule": f"stop-{i}"},
        tool=f"tool-{i}",
        inn=f"in-{i}",
        out=f"out-{i}",
    )


def _wf(wid: str, stages: list[Stage], licences: tuple[str, ...]) -> Workflow:
    return Workflow(id=wid, stages=stages, edges=[], licences=licences)


def _review_triple(
    prefix: str, licences: tuple[tuple[str, ...], ...]
) -> tuple[Workflow, ...]:
    a = _wf(
        f"{prefix}-alpha",
        [ingest(f"{prefix}-a-in"), lint(f"{prefix}-a-li"), review(f"{prefix}-a-rv"), unique("patch", 1), ship(f"{prefix}-a-sh")],
        licences[0],
    )
    b = _wf(
        f"{prefix}-beta",
        [ingest(f"{prefix}-b-in"), lint(f"{prefix}-b-li"), test(f"{prefix}-b-te"), review(f"{prefix}-b-rv"), ship(f"{prefix}-b-sh")],
        licences[1],
    )
    c = _wf(
        f"{prefix}-gamma",
        [ingest(f"{prefix}-c-in"), lint(f"{prefix}-c-li"), review(f"{prefix}-c-rv"), unique("security", 3), ship(f"{prefix}-c-sh")],
        licences[2],
    )
    return (a, b, c)


def _seven_tick(prefix: str, licences: tuple[str, ...] = ("MIT",)) -> tuple[Workflow, ...]:
    members: list[Workflow] = []
    for i in range(7):
        members.append(
            _wf(
                f"{prefix}-m{i}",
                [tick(f"{prefix}-tick-{i}"), unique(f"work{i}", i), unique(f"tail{i}", i + 10)],
                licences,
            )
        )
    return tuple(members)


def _seven_spine(prefix: str) -> tuple[Workflow, ...]:
    lics = ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MPL-2.0", "MIT", "Apache-2.0")
    members: list[Workflow] = []
    for i in range(7):
        stages = [
            ingest(f"{prefix}-{i}-in"),
            lint(f"{prefix}-{i}-li"),
            review(f"{prefix}-{i}-rv"),
            ship(f"{prefix}-{i}-sh"),
            unique(f"extra{i}", i),
        ]
        members.append(_wf(f"{prefix}-m{i}", stages, (lics[i],)))
    return tuple(members)


def compile_link() -> Workflow:
    return _wf(
        "compile-link",
        [
            _st("compile", "compile", roles=("builder",), tool="cc", inn="src", out="obj"),
            _st("link", "link", roles=("builder",), tool="ld", inn="obj", out="bin"),
        ],
        ("GPL-3.0-only",),
    )


def fetch_render() -> Workflow:
    return _wf(
        "fetch-render",
        [
            _st("fetch", "fetch", roles=("net",), tool="http", inn="url", out="html"),
            _st("render", "render", roles=("ui",), tool="browser", inn="html", out="png"),
        ],
        ("MIT",),
    )


def all_families() -> list[FamilySpec]:
    d1 = _review_triple("D1", (("MIT",), ("Apache-2.0",), ("BSD-3-Clause",)))
    d2_clone = _wf(
        "D2-clone",
        [s.with_id(f"c-{s.id}") for s in d1[0].stages],
        d1[0].licences,
    )
    ci_a = _wf(
        "D5-a",
        [ingest("d5a-in"), lint("d5a-li"), test("d5a-te"), unique("deploy", 5)],
        ("MIT",),
    )
    ci_b = _wf(
        "D5-b",
        [ingest("d5b-in"), lint("d5b-li"), test("d5b-te"), unique("package", 6)],
        ("Apache-2.0",),
    )
    release: list[Workflow] = []
    for i, lic in enumerate(("MIT", "Apache-2.0", "BSD-3-Clause", "ISC")):
        release.append(
            _wf(
                f"D6-m{i}",
                [
                    ingest(f"d6-{i}-in"),
                    test(f"d6-{i}-te"),
                    _st(
                        f"d6-{i}-sign",
                        "sign",
                        roles=("signer",),
                        tool="cosign",
                        inn="bundle",
                        out="sig",
                    ),
                    ship(f"d6-{i}-sh"),
                    unique(f"rel{i}", i),
                ],
                (lic,),
            )
        )
    disjoint_triple = (
        compile_link(),
        fetch_render(),
        _wf(
            "D7-train",
            [
                _st("fit", "fit", roles=("trainer",), tool="torch", inn="data", out="weights"),
                _st("eval", "eval", roles=("eval",), tool="metrics", inn="weights", out="score"),
            ],
            ("Apache-2.0",),
        ),
    )
    d8 = (
        _wf("D8-mit", [ingest("d8m-in"), lint("d8m-li"), ship("d8m-sh")], ("MIT",)),
        _wf("D8-apache", [ingest("d8a-in"), lint("d8a-li"), ship("d8a-sh")], ("Apache-2.0",)),
        _wf("D8-gpl", [ingest("d8g-in"), lint("d8g-li"), ship("d8g-sh")], ("GPL-3.0-only",)),
    )
    d9 = _review_triple("D9", (("MIT",), ("MIT",), ("MIT",)))
    pair_one = (
        _wf("D11-a", [ingest("d11a-in"), unique("alpha-work", 11)], ("MIT",)),
        _wf("D11-b", [ingest("d11b-in"), unique("beta-work", 12)], ("Apache-2.0",)),
    )
    gate_b = review("d12b-rv").with_gate(
        {"unanimity": False, "min_reviewers": 1, "stop_rule": "majority"}
    )
    d12 = (
        _wf("D12-a", [ingest("d12a-in"), review("d12a-rv"), ship("d12a-sh")], ("MIT",)),
        _wf("D12-b", [ingest("d12b-in"), gate_b, ship("d12b-sh")], ("MIT",)),
    )
    role_b = _st(
        "d13b-li",
        "lint",
        roles=("security-reviewer",),
        tool="linter",
        inn="bundle",
        out="bundle",
    )
    d13 = (
        _wf("D13-a", [ingest("d13a-in"), lint("d13a-li"), ship("d13a-sh")], ("MIT",)),
        _wf("D13-b", [ingest("d13b-in"), role_b, ship("d13b-sh")], ("MIT",)),
    )
    tool_b = _st(
        "d14b-li",
        "lint",
        roles=("static-analyzer",),
        tool="ruff",
        inn="bundle",
        out="bundle",
    )
    d14 = (
        _wf("D14-a", [ingest("d14a-in"), lint("d14a-li"), ship("d14a-sh")], ("MIT",)),
        _wf("D14-b", [ingest("d14b-in"), tool_b, ship("d14b-sh")], ("MIT",)),
    )
    d15 = (
        _wf(
            "D15-a",
            [ingest("d15a-in"), lint("d15a-li"), unique("patch", 15), ship("d15a-sh")],
            ("MIT",),
        ),
        _wf(
            "D15-b",
            [ingest("d15b-in"), lint("d15b-li"), unique("testx", 16), ship("d15b-sh")],
            ("MIT",),
        ),
        _wf(
            "D15-c",
            [ingest("d15c-in"), lint("d15c-li"), unique("sec", 17), ship("d15c-sh")],
            ("BSD-3-Clause",),
        ),
    )
    spine4 = [ingest(), lint(), review(), ship()]
    d16 = (
        _wf("D16-mit", [s.with_id(f"m-{s.id}") for s in spine4], ("MIT",)),
        _wf("D16-apache", [s.with_id(f"a-{s.id}") for s in spine4], ("Apache-2.0",)),
    )
    d17 = (
        _wf(
            "D17-index",
            [
                _st("parse", "parse", roles=("parser",), tool="tree", inn="src", out="ast"),
                _st("index", "index", roles=("indexer",), tool="db", inn="ast", out="idx"),
            ],
            ("MIT",),
        ),
        _wf(
            "D17-paint",
            [
                _st("layout", "layout", roles=("ui",), tool="box", inn="tree", out="frame"),
                _st("paint", "paint", roles=("ui",), tool="gpu", inn="frame", out="px"),
            ],
            ("Apache-2.0",),
        ),
    )
    d18: list[Workflow] = []
    for i, lic in enumerate(("MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MPL-2.0")):
        d18.append(
            _wf(
                f"D18-m{i}",
                [
                    ingest(f"d18-{i}-in"),
                    lint(f"d18-{i}-li"),
                    ship(f"d18-{i}-sh"),
                    unique(f"slot{i}", i),
                ],
                (lic,),
            )
        )
    d20: list[Workflow] = []
    for i, lic in enumerate(("MIT", "Apache-2.0", "BSD-3-Clause", "ISC")):
        d20.append(
            _wf(
                f"D20-m{i}",
                [ingest(f"d20-{i}-in"), ship(f"d20-{i}-sh"), unique(f"mid{i}", 20 + i)],
                (lic,),
            )
        )
    return [
        FamilySpec("D1", "review-spine-three", d1, "shared ingest/lint/review/ship plus one extra each"),
        FamilySpec("D2", "identical-pair", (d1[0], d2_clone), "clone with renamed ids"),
        FamilySpec("D3", "disjoint-pair", (compile_link(), fetch_render()), "empty intersection"),
        FamilySpec("D4", "degenerate-seven-tick", _seven_tick("D4"), "family of seven, LCS of one tick"),
        FamilySpec("D5", "ci-pair", (ci_a, ci_b), "shared ingest/lint/test"),
        FamilySpec("D6", "four-release", tuple(release), "shared ingest/test/sign/ship"),
        FamilySpec("D7", "triple-disjoint", disjoint_triple, "three pairwise-disjoint pipelines"),
        FamilySpec("D8", "licence-union-spine", d8, "identical spine, three SPDX licences"),
        FamilySpec("D9", "renamed-review-siblings", d9, "same spine as D1, MIT throughout"),
        FamilySpec("D10", "seven-large-core", _seven_spine("D10"), "family of seven, four-stage spine"),
        FamilySpec("D11", "pair-one-shared", pair_one, "family of two, one-stage core is allowed"),
        FamilySpec("D12", "gate-fork", d12, "review gates differ so review drops out of LCS"),
        FamilySpec("D13", "role-fork", d13, "lint roles differ so lint drops out of LCS"),
        FamilySpec("D14", "tool-fork", d14, "lint tools differ so lint drops out of LCS"),
        FamilySpec("D15", "insert-middle", d15, "shared ingest/lint/ship, unique middles"),
        FamilySpec("D16", "licence-only-delta", d16, "structure identical, licences differ"),
        FamilySpec("D17", "empty-pair-index-paint", d17, "second empty pair"),
        FamilySpec("D18", "five-member-core3", tuple(d18), "five members, three-stage spine"),
        FamilySpec("D19", "degenerate-seven-tick-b", _seven_tick("D19", ("Apache-2.0",)), "second degenerate seven"),
        FamilySpec("D20", "four-ingest-ship", tuple(d20), "shared ingest+ship only"),
    ]
