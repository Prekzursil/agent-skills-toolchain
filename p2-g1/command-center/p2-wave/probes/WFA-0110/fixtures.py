"""Control workflows for WFA-0110 lineage + rollback rehearsals.

Each operator gets a dedicated source pair (common-core: a two-member family)
with distinct credit strings and mixed licences so the strictest-licence rule
is observable. Anchors are stamped from workflow ids.
"""
from __future__ import annotations

from dataclasses import replace

from workflow_foundry.workflow_ir import Stage, Workflow


def _st(
    sid: str,
    kind: str,
    *,
    inn: str = "bundle",
    out: str = "bundle",
    gate: dict | None = None,
    tool: str = "op",
) -> Stage:
    return Stage(
        id=sid,
        kind=kind,
        in_contract=inn,
        out_contract=out,
        gate=gate,
        tool_class=tool,
    )


def _wf(wid: str, stages: list[Stage], licences: tuple[str, ...], credit: str) -> Workflow:
    stamped = [replace(s, anchors=(wid,)) for s in stages]
    return Workflow(
        id=wid,
        stages=stamped,
        edges=[],
        licences=licences,
        credits=(credit,),
    )


def splice_pair() -> tuple[Workflow, Workflow]:
    host = _wf(
        "splice-host",
        [
            _st("ingest", "ingest", inn="files", out="bundle"),
            _st("scale", "scale", gate={"factor": 2}),
            _st("ship", "ship", inn="bundle", out="release"),
        ],
        ("MIT",),
        "Copyright 2024 Ada Host <ada@example.test>",
    )
    donor = _wf(
        "splice-donor",
        [
            _st("ingest", "ingest", inn="files", out="bundle"),
            _st("tag", "tag", gate={"label": "donor"}),
            _st("ship", "ship", inn="bundle", out="release"),
        ],
        ("GPL-3.0-only",),
        "Copyright 2024 Don Donor <don@example.test>",
    )
    return host, donor


def splice_mismatch_donor() -> Workflow:
    return _wf(
        "splice-bad-donor",
        [
            _st("ingest", "ingest", inn="files", out="bundle"),
            _st("tag", "tag", inn="html", out="png", gate={"label": "bad"}),
            _st("ship", "ship", inn="bundle", out="release"),
        ],
        ("MIT",),
        "Copyright 2024 Bad Donor <bad@example.test>",
    )


def common_core_family() -> list[Workflow]:
    spine = [
        _st("ingest", "ingest", inn="files", out="bundle"),
        _st("scale", "scale", gate={"factor": 2}),
        _st("ship", "ship", inn="bundle", out="release"),
    ]
    a = _wf(
        "core-alpha",
        spine[:2] + [_st("patch", "patch")] + spine[2:],
        ("Apache-2.0",),
        "Copyright 2021 Core Alpha <alpha@example.test>",
    )
    b = _wf(
        "core-beta",
        spine[:2] + [_st("inc", "inc")] + spine[2:],
        ("MIT",),
        "Copyright 2021 Core Beta <beta@example.test>",
    )
    return [a, b]


def union_pair() -> tuple[Workflow, Workflow]:
    left = _wf(
        "union-left",
        [_st("ingest", "ingest", inn="files"), _st("scale", "scale", gate={"factor": 2})],
        ("BSD-3-Clause",),
        "Copyright 2020 Union Left <uleft@example.test>",
    )
    right = _wf(
        "union-right",
        [_st("ingest", "ingest", inn="files"), _st("tag", "tag", gate={"label": "right"})],
        ("MIT",),
        "Copyright 2020 Union Right <uright@example.test>",
    )
    return left, right


def best_of_breed_pair() -> tuple[Workflow, Workflow, dict]:
    left = _wf(
        "bob-left",
        [
            _st("ingest", "ingest", inn="files"),
            _st("scale", "scale", gate={"factor": 2}),
        ],
        ("MPL-2.0",),
        "Copyright 2019 Breed Left <bleft@example.test>",
    )
    right = _wf(
        "bob-right",
        [
            _st("ingest", "ingest", inn="files"),
            _st("inc", "inc"),
        ],
        ("MIT",),
        "Copyright 2019 Breed Right <bright@example.test>",
    )
    scores = {
        "bob-left": {"ingest": 0.9, "scale": 0.1},
        "bob-right": {"ingest": 0.2, "inc": 0.8},
    }
    return left, right, scores


def hybrid_pair() -> tuple[Workflow, Workflow]:
    left = _wf(
        "hybrid-left",
        [_st("ingest", "ingest", inn="files"), _st("filter_even", "filter_even")],
        ("LGPL-3.0-only",),
        "Copyright 2018 Hybrid Left <hleft@example.test>",
    )
    right = _wf(
        "hybrid-right",
        [_st("ingest", "ingest", inn="files"), _st("tag", "tag", gate={"label": "hy"})],
        ("MIT",),
        "Copyright 2018 Hybrid Right <hright@example.test>",
    )
    return left, right


def ensemble_pair() -> tuple[Workflow, Workflow]:
    left = _wf(
        "ens-left",
        [_st("ingest", "ingest", inn="files"), _st("scale", "scale", gate={"factor": 3})],
        ("AGPL-3.0-only",),
        "Copyright 2017 Ensemble Left <eleft@example.test>",
    )
    right = _wf(
        "ens-right",
        [_st("ingest", "ingest", inn="files"), _st("inc", "inc")],
        ("Apache-2.0",),
        "Copyright 2017 Ensemble Right <eright@example.test>",
    )
    return left, right


def progressive_pair() -> tuple[Workflow, Workflow]:
    cheap = _wf(
        "prog-cheap",
        [_st("ingest", "ingest", inn="files"), _st("tag", "tag", gate={"label": "cheap"})],
        ("GPL-2.0-only",),
        "Copyright 2016 Progressive Cheap <pcheap@example.test>",
    )
    expensive = _wf(
        "prog-exp",
        [_st("ingest", "ingest", inn="files"), _st("scale", "scale", gate={"factor": 4})],
        ("MIT",),
        "Copyright 2016 Progressive Exp <pexp@example.test>",
    )
    return cheap, expensive
