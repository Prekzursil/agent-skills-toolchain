"""``monitorcore.report_doc`` — the generic document-IR primitives are plain frozen
dataclasses; this smoke test instantiates each (defaults + overrides) so the field
declarations are exercised and the ``Block`` union stays importable."""

from __future__ import annotations

from monitorcore.report_doc import (
    Block,
    Code,
    Heading,
    KV,
    ReportDoc,
    Section,
    Table,
    Text,
)
from monitorcore.timeline import TimelineEvent


def test_primitives_construct_with_defaults():
    assert Heading("h").level == 2
    assert Heading("h").anchor == ""
    assert Text("t").variant == "" and Text("t").redact is False
    assert Code("c").redact is True and Code("c").label == ""
    assert KV().pairs == ()
    assert Table().headers == () and Table().rows == ()
    sec = Section("s")
    assert sec.card is False and sec.children == () and sec.timeline == ()
    assert sec.attempt == 1 and sec.tokens == 0


def test_card_and_group_sections():
    card = Section(
        title="a",
        anchor="agent-a",
        card=True,
        badge="done",
        timeline=(TimelineEvent(kind="text", seq=0, text="hi"),),
    )
    group = Section(title="P", anchor="phase-1", index=1, children=(card,))
    assert group.children[0].card is True
    assert isinstance(group.children[0], Block)  # union membership


def test_report_doc_shape():
    doc = ReportDoc(
        title="t",
        generated_at="2026-01-01T00:00:00+00:00",
        blocks=(Heading("x"),),
        subtitle="sub",
        meta=(("k", "v"),),
        rollup=(("total", 1),),
        active=True,
        redaction_mode="strict",
    )
    assert doc.title == "t" and doc.active is True
    assert doc.rollup == (("total", 1),)
    # defaults
    bare = ReportDoc(title="t", generated_at="g")
    assert (
        bare.blocks == () and bare.redaction_mode == "strict" and bare.active is False
    )
