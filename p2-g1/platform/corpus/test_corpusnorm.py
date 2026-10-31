"""Tests for the Phase-1 corpus normalizer.

The load-bearing tests are the MUTATION tests, not the smoke tests:

  test_repetition_has_zero_weight   -- clones a cluster's supporting records 10x and requires
                                       the composite score to be bit-identical.  This is the
                                       ONLY thing that turns "we do not rank by repetition"
                                       from an intention into a claim.
  test_complete_linkage_blocks_chaining
                                    -- builds a chain a~b, b~c where a!~c and requires TWO
                                       clusters.  Single linkage produced a 461-member cluster
                                       on the real corpus while every pairwise edge was inside
                                       the audited budget.
  test_thin_signature_cannot_d3_merge
                                    -- the measured false-merge class (15 records collapsed on
                                       the single word "gate").
  test_d3_detector_fires_in_both_states
                                    -- a detector silent in both states measures nothing.
  test_d5_needs_both_signals        -- D5 must not degrade into a filename-similarity rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpusnorm import extract as E  # noqa: E402
from corpusnorm import mechanism as M  # noqa: E402
from corpusnorm import rank as R  # noqa: E402
from corpusnorm.controls import intra_document_control  # noqa: E402
from corpusnorm.dedup import (  # noqa: E402
    DEFAULT_T,
    Thresholds,
    d3_signature_match,
    d4_veto,
    d5_verify_same_target,
    dedup,
    parse_authored_ledger,
    signature_is_rich,
    to_nodes,
    validate,
    verify_topic_slug,
)

CORPUS = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
corpus_present = pytest.mark.skipif(
    not CORPUS.exists(), reason="corpus root absent on this box"
)


@pytest.fixture(scope="module")
def records():
    return E.extract_corpus(CORPUS)


@pytest.fixture(scope="module")
def nodes(records):
    return to_nodes(records)


@pytest.fixture(scope="module")
def ledger():
    return parse_authored_ledger(CORPUS)


# ======================================================================================
# extractor: agreement with counts the corpus declares about itself (detector control)
# ======================================================================================


@corpus_present
@pytest.mark.parametrize(
    ("record_class", "declared"),
    [
        ("option_lane", 341),  # "Pre-dedup total across the five lanes: 341"
        ("option_universe", 283),  # "Final distinct options: 283"
        ("preset", 72),
        ("protocol", 58),
        ("mechanism_card", 38),
        ("blueprint", 108),  # doc 09 by_family histogram sums to 108
    ],
)
def test_extracted_count_matches_corpus_self_declaration(
    records, record_class, declared
):
    n = sum(1 for r in records if r.record_class == record_class)
    assert n == declared, f"{record_class}: extracted {n}, document declares {declared}"


@corpus_present
def test_authored_ledger_parses_to_declared_totals(ledger):
    # "50 canonical options absorbed 55 sibling cards."
    assert len(ledger) == 50
    assert sum(len(a) for _, a, _ in ledger) == 55


@corpus_present
def test_extractor_finds_a_known_present_record(records):
    """Detector control: the extractor must find a record we know exists."""
    hits = [
        r
        for r in records
        if r.local_id == "A-01" and r.source_file == "07-OPTION-UNIVERSE.md"
    ]
    assert len(hits) == 1
    assert "merge" in hits[0].mechanism_text.lower()
    assert hits[0].source_line > 1


@corpus_present
def test_extractor_does_not_invent_a_record_that_is_absent(records):
    assert not [r for r in records if r.local_id == "ZZ-999"]


# ======================================================================================
# mechanism signature
# ======================================================================================


def test_signature_separates_verb_from_locus_from_artifact():
    s = M.signature(
        "replace the whole-key assignment in install.py with a per-event, per-group merge",
        "Merge-not-replace hook installer",
    )
    assert "MERGE" in s.verbs
    assert s.locus == "installer"
    assert "install.py" in s.hard


def test_problem_text_does_not_contribute_verbs():
    """A problem statement describes the DEFECT; folding its verbs in would merge a repair
    with the thing it repairs."""
    a = M.signature(
        "emit a receipt", "x", problem_text="the installer DELETES 21 registrations"
    )
    assert "DELETE" not in a.verbs


def test_same_mechanism_different_wording_merges_when_two_artifacts_agree():
    a = M.signature(
        "install.py performs a per-event, per-group merge of the settings.json hooks key; "
        "harness-owned groups are replaced and every other group is carried through untouched, "
        "then a receipt is recorded",
        "merge-not-replace installer",
    )
    b = M.signature(
        "instead of overwriting the settings.json hooks key, install.py carries every "
        "non-harness group through unchanged, merging group by group and recording what it "
        "replaced",
        "additive registration merge",
    )
    ok, detail = d3_signature_match(a, b)
    assert ok, detail


def test_paraphrase_sharing_ONE_artifact_is_a_KNOWN_MISS_not_a_capability():
    """Pins the measured limitation instead of pretending it is not there.

    Two paraphrases of one mechanism that name only a SINGLE shared artifact are rejected,
    because min_referents=2 / min_hard_intersection=2 are what hold the intra-document
    false-merge rate at 12/17399. This is the concrete shape of the 75% recall miss reported
    in DEDUP-VALIDATION.json. Loosening it to pass this case moved NEG2 above its ceiling in
    the sweep, so the miss is accepted deliberately, not overlooked.

    Settling experiment: if an independent reviewer adjudicates the 41 D3-missed ledger pairs
    as genuine paraphrase merges, the residual is semantic and not closable lexically -- the
    fix would be an embedding or an LLM adjudicator, not a threshold change.
    """
    a = M.signature(
        "per-event, per-group merge of settings.json hook groups; harness-owned groups replaced",
        "merge installer",
    )
    b = M.signature(
        "carry every non-harness group in settings.json through unchanged instead of "
        "overwriting the hooks key",
        "additive registration merge",
    )
    ok, detail = d3_signature_match(a, b)
    assert not ok
    assert detail["hard_overlap"] == 1, detail


def test_same_wording_different_mechanism_is_not_merged():
    """Shared vocabulary, different mechanism -> must NOT merge."""
    a = M.signature(
        "gate the run: block a Write whose path is under a deployed harness copy, using the "
        "settings.json deny list and a PreToolUse check",
        "deployed-copy write guard",
    )
    b = M.signature(
        "gate the council: block a verdict until every seat has cited evidence, using the "
        "quorum and round counters",
        "evidence-before-opinion gate",
    )
    ok, _ = d3_signature_match(a, b)
    assert not ok


def test_jaccard_of_two_empty_sets_is_one_and_is_why_richness_floors_exist():
    assert M.jaccard(frozenset(), frozenset()) == 1.0
    thin = M.signature("gate", "Governance Decision Gate")
    assert not signature_is_rich(thin, DEFAULT_T)


# ======================================================================================
# dedup rules
# ======================================================================================


def test_thin_signature_cannot_d3_merge():
    """The measured false-merge class: 15 records collapsed on the single word 'gate'."""
    a = M.signature("", "Governance Decision Gate")
    b = M.signature("", "Release Readiness Gate")
    ok, detail = d3_signature_match(a, b)
    assert not ok
    assert "richness" in detail["blocked_by"]


def test_single_shared_word_does_not_merge():
    a = M.signature("", "recall index staleness")
    b = M.signature("", "a deterministic per-index delay")
    ok, _ = d3_signature_match(a, b)
    assert not ok


@corpus_present
def test_d3_detector_fires_in_both_states(nodes, ledger):
    """A probe silent in both states measures nothing."""
    impossible = Thresholds(
        verb_jaccard_min=1.01, min_verbs=99, min_verb_intersection=99
    )
    permissive = Thresholds(
        verb_jaccard_min=0.0,
        verb_overlap_min=0,
        hard_jaccard_min=0.0,
        hard_overlap_min=0,
        soft_jaccard_min=0.0,
        locus_top_k=3,
        min_verbs=0,
        min_referents=0,
        min_soft_referents=0,
        min_verb_intersection=0,
        min_hard_intersection=0,
        min_soft_intersection=0,
    )
    lo = validate(nodes, ledger, impossible)["positive_control"]["d3_fired"]
    hi = validate(nodes, ledger, permissive)["positive_control"]["d3_fired"]
    assert lo == 0, "impossible thresholds must fire on nothing"
    assert hi > lo, "permissive thresholds must fire on something"


@corpus_present
def test_measured_operating_point_holds(nodes, ledger):
    """Pin the published numbers so a future edit cannot silently move them."""
    v = validate(nodes, ledger, DEFAULT_T)
    assert v["positive_control"]["pairs"] == 55
    assert v["positive_control"]["d3_fired"] == 14
    assert v["negative_control"]["pairs"] == 616
    assert v["negative_control"]["d3_fired_falsely"] == 11
    n2 = intra_document_control(nodes, d3_signature_match, DEFAULT_T)
    assert n2["pairs"] == 17399
    assert n2["d3_fired_falsely"] == 12
    assert n2["false_merge_rate"] <= 0.002


@corpus_present
def test_negative_control_2_covers_the_thin_signature_classes(nodes):
    """The reason NEG2 exists: NEG1's population excluded the failure mode."""
    n2 = intra_document_control(nodes, d3_signature_match, DEFAULT_T)
    groups = set(n2["per_group"])
    assert any("blueprint" in g for g in groups)
    assert any("preset" in g for g in groups)
    assert any("protocol" in g for g in groups)


def test_d4_veto_blocks_an_authored_distinction():
    from corpusnorm.dedup import Node

    sig = M.signature("merge settings.json hook groups per group", "merge installer")
    a = Node(
        "f#A-01",
        "A-01",
        "option_lane",
        "f",
        1,
        "t",
        "m",
        "p",
        sig,
        distinct_from=["A-02"],
    )
    b = Node(
        "f#A-02", "A-02", "option_lane", "f", 2, "t", "m", "p", sig, distinct_from=[]
    )
    assert d4_veto(a, b)
    assert d4_veto(b, a), "the veto is symmetric"
    c = Node("f#A-09", "A-09", "option_lane", "f", 3, "t", "m", "p", sig)
    assert not d4_veto(a, c)


def test_complete_linkage_blocks_chaining():
    """a~b and b~c but a!~c must yield TWO clusters, never one.

    Single linkage on the real corpus produced a 461-member cluster from 427 pairwise edges,
    every one of which was inside the audited pairwise false-merge budget, because chaining
    a-b, b-c never has to justify a-c.
    """
    from corpusnorm.dedup import Node

    def sig(paths):
        """Built directly, so the test exercises the LINKAGE logic and not the vocabulary
        tables -- a fixture phrased in prose was silently not a chain and skipped this test."""
        return M.Signature(
            verbs=frozenset({"MERGE", "OBSERVE"}),
            locus="installer",
            locus_top=frozenset({"installer"}),
            hard=frozenset(paths),
            soft=frozenset({"receipt", "registration group"}),
        )

    def node(rid, paths):
        return Node(rid, rid, "option_lane", "f", 1, rid, "m", "", sig(paths))

    a = node("X-1", ["p1.py", "p2.py", "p3.py", "p4.py"])
    b = node("X-2", ["p3.py", "p4.py", "p5.py", "p6.py"])
    c = node("X-3", ["p5.py", "p6.py", "p7.py", "p8.py"])

    ab, _ = d3_signature_match(a.sig, b.sig)
    bc, _ = d3_signature_match(b.sig, c.sig)
    ac, dac = d3_signature_match(a.sig, c.sig)
    assert ab and bc, "fixture must be a chain"
    assert not ac, f"fixture ends must NOT match directly: {dac}"

    res = dedup([a, b, c], [], DEFAULT_T)
    assert len(res.clusters) == 2, f"chaining leaked: {res.clusters}"
    assert any(v["rule"] == "D3-complete-linkage-refused" for v in res.vetoed), (
        "the refusal must be recorded, not silent"
    )


def test_single_linkage_would_have_chained_the_same_fixture():
    """The both-states half of the previous test: prove the KNOWN-BROKEN behaviour chains.

    Without this, 'complete linkage prevents chaining' is unfalsifiable -- a fixture that
    never chains under either policy would pass the previous test while measuring nothing.
    """
    from corpusnorm.dedup import DSU

    edges = [("X-1", "X-2"), ("X-2", "X-3")]  # exactly the pairwise D3 hits above
    dsu = DSU(["X-1", "X-2", "X-3"])
    for x, y in edges:
        dsu.union(x, y)
    roots = {dsu.find(k) for k in ("X-1", "X-2", "X-3")}
    assert len(roots) == 1, (
        "single linkage must collapse the chain -- that is the defect"
    )


# ======================================================================================
# D5 -- verify-document target identity
# ======================================================================================


def test_verify_topic_slug_strips_pass_scaffolding_only():
    assert verify_topic_slug("ADV-V9-VERIFY-ledger-mojibake") == frozenset(
        {"ledger", "mojibake"}
    )
    assert verify_topic_slug("ADV-VERIFY-ledger-mojibake") == frozenset(
        {"ledger", "mojibake"}
    )
    # a side qualifier is NOT stripped; the 0.6 jaccard tolerates it
    assert "main" in verify_topic_slug("ADV-VERIFY-ledger-mojibake-main")


def test_d5_needs_both_signals():
    """D5 must not degrade into a filename-similarity rule."""
    from corpusnorm.dedup import Node

    sig = M.signature("x", "y")
    body_a = "Target finding: `hooks/event-ledger/ledger.py` diverged"
    body_b = "Target finding: `hooks/event-ledger/ledger.py` mojibake"
    same_topic_same_path = (
        Node(
            "a",
            "ADV-VERIFY-ledger-mojibake",
            "verify_doc",
            "a",
            1,
            "t",
            "",
            "",
            sig,
            body=body_a,
        ),
        Node(
            "b",
            "ADV-V9-VERIFY-ledger-mojibake",
            "verify_doc",
            "b",
            1,
            "t",
            "",
            "",
            sig,
            body=body_b,
        ),
    )
    ok, detail = d5_verify_same_target(*same_topic_same_path)
    assert ok, detail

    # same filename topic, DIFFERENT artifact -> name signal alone must not merge
    other = Node(
        "c",
        "ADV-V2-VERIFY-ledger-mojibake",
        "verify_doc",
        "c",
        1,
        "t",
        "",
        "",
        sig,
        body="Target finding: `hooks/dup-guard/guard.py` mojibake",
    )
    ok2, d2 = d5_verify_same_target(same_topic_same_path[0], other)
    assert not ok2
    assert d2["name_signal"] and not d2["body_signal"]

    # same artifact, DIFFERENT topic -> body signal alone must not merge
    diff_topic = Node(
        "d",
        "ADV-VERIFY-recall-maxage-race",
        "verify_doc",
        "d",
        1,
        "t",
        "",
        "",
        sig,
        body=body_a,
    )
    ok3, d3d = d5_verify_same_target(same_topic_same_path[0], diff_topic)
    assert not ok3
    assert d3d["body_signal"] and not d3d["name_signal"]


def test_d5_only_applies_to_verify_docs():
    from corpusnorm.dedup import Node

    sig = M.signature("x", "y")
    body = "Target finding: `a/b.py`"
    a = Node("a", "ADV-VERIFY-x", "option_lane", "a", 1, "t", "", "", sig, body=body)
    b = Node("b", "ADV-VERIFY-x", "verify_doc", "b", 1, "t", "", "", sig, body=body)
    ok, detail = d5_verify_same_target(a, b)
    assert not ok
    assert detail["skipped"] == "not-both-verify-docs"


# ======================================================================================
# RANKING -- the anti-repetition mutation test
# ======================================================================================


def _axes_for(texts, lineages, sev_raw, in_degree, classes):
    ev, _ = R.score_independent_evidence(texts)
    imp, _ = R.score_decision_impact(texts, in_degree, classes)
    sev, _ = R.score_severity(sev_raw, texts)
    return {
        "independent_evidence": ev,
        "cross_domain_convergence": R.score_convergence(lineages),
        "severity": sev,
        "decision_impact": imp,
    }


def test_repetition_has_zero_weight():
    """THE test that makes the ranking rule a claim rather than an intention.

    Clone a cluster's supporting records 10x -- same text, same lineage, same severity -- and
    require the composite score to be bit-identical.  Repetition across agents that read the
    same input is ONE signal, not N.
    """
    texts = ["$ python probe.py\npassed", "see hooks/x.py:42"]
    lineages = {"option_lane@07-OPTIONS-lanes", "verify_doc@ADV-VERIFY-x.md"}
    base = _axes_for(texts, lineages, ["high"], 1, {"option_lane", "verify_doc"})
    cloned = _axes_for(
        texts * 10, lineages, ["high"] * 10, 1, {"option_lane", "verify_doc"}
    )
    assert base == cloned
    assert R.composite(base) == R.composite(cloned)
    assert R.REPETITION_WEIGHT == 0
    assert "repetition_count" not in R.WEIGHTS


def test_convergence_ignores_a_declared_consolidation_of_the_same_lineage():
    """Restating an option in the consolidated universe is the same authors re-reading their
    own output -- it must NOT count as a second lineage."""
    a = R.lineage_of(
        "07-OPTIONS-AB.md",
        "option_lane",
        "07-OPTION-UNIVERSE.md",
        ("07-OPTIONS-AB.md",),
    )
    b = R.lineage_of(
        "07-OPTION-UNIVERSE.md",
        "option_lane",
        "07-OPTION-UNIVERSE.md",
        ("07-OPTIONS-AB.md",),
    )
    assert a == b
    assert R.score_convergence({a, b}) == 1


def test_convergence_counts_a_genuinely_independent_lineage():
    a = R.lineage_of(
        "07-OPTIONS-AB.md",
        "option_lane",
        "07-OPTION-UNIVERSE.md",
        ("07-OPTIONS-AB.md",),
    )
    b = R.lineage_of(
        "ADV-VERIFY-x.md", "verify_doc", "07-OPTION-UNIVERSE.md", ("07-OPTIONS-AB.md",)
    )
    assert R.score_convergence({a, b}) == 2


def test_evidence_counted_per_kind_not_per_record():
    one = ["$ python p.py\npassed"]
    forty = ["$ python p.py\npassed"] * 40
    assert R.score_independent_evidence(one) == R.score_independent_evidence(forty)


def test_evidence_rewards_distinct_kinds():
    a, _ = R.score_independent_evidence(["$ python p.py\npassed"])
    b, kinds = R.score_independent_evidence(
        [
            "$ python p.py\npassed",
            "hooks/x.py:42",
            "both-states control fires in the broken state",
        ]
    )
    assert b > a
    assert len(kinds) >= 3


def test_severity_unrated_is_not_silently_low():
    score, label = R.score_severity([], ["a neutral sentence about a preset dial"])
    assert score == 0
    assert label == "unrated"


def test_refuted_beats_confirmed_in_a_mixed_cluster():
    assert (
        R.normalise_verification(["CONFIRMED", "REFUTED"], {"verify_doc"}) == "REFUTED"
    )


def test_design_only_never_reports_confirmed():
    assert R.normalise_verification(["CONFIRMED"], {"blueprint"}) == "DESIGN-ONLY"
    assert R.normalise_verification([], {"preset"}) == "DESIGN-ONLY"


@pytest.mark.parametrize(
    ("raw", "band"),
    [
        ("likely 70-85", "likely"),
        ("almost-certain 90-99", "almost-certain"),
        ("even 45-60", "even"),
        ("", "unstated"),
        ("no band here", "unstated"),
    ],
)
def test_confidence_normalisation_never_invents_a_band(raw, band):
    assert R.normalise_confidence(raw)["band"] == band


def test_confidence_prefers_the_stated_numeric_range_over_the_default():
    c = R.normalise_confidence("likely 60-75")
    assert (c["low"], c["high"]) == (60, 75)


# ======================================================================================
# end-to-end
# ======================================================================================


@corpus_present
def test_build_is_deterministic(tmp_path):
    from corpusnorm.build import build

    a = build(CORPUS, tmp_path / "a")
    b = build(CORPUS, tmp_path / "b")
    assert a["counts"] == b["counts"]
    assert [c["claim_id"] for c in a["claims"]] == [c["claim_id"] for c in b["claims"]]


@corpus_present
def test_every_claim_carries_the_contracted_fields(tmp_path):
    from corpusnorm.build import build

    p = build(CORPUS, tmp_path / "o")
    required = (
        "claim_id",
        "canonical_mechanism",
        "duplicate_of_edges",
        "support_edges",
        "contradiction_edges",
        "source_lineage",
        "confidence",
        "verification_status",
        "implementation_impact",
        "settling_probe",
        "rank_composite",
        "repetition_count",
    )
    assert p["claims"]
    for c in p["claims"]:
        for f in required:
            assert f in c, f"{c['claim_id']} missing {f}"
        assert c["claim_id"].startswith("CLM-")
        assert c["canonical_mechanism"].strip()


@corpus_present
def test_no_d3_merged_cluster_has_a_thin_signature(tmp_path):
    from corpusnorm.build import build

    p = build(CORPUS, tmp_path / "o")
    assert p["cluster_quality"]["thin_signature_count"] == 0


@corpus_present
def test_cluster_sizes_stay_bounded(tmp_path):
    """Guards the 461-member single-linkage blob from coming back."""
    from corpusnorm.build import build

    p = build(CORPUS, tmp_path / "o")
    assert p["cluster_quality"]["max_cluster_size"] <= 12


def test_build_fails_closed_on_an_absent_corpus():
    from corpusnorm.build import main

    assert main([str(HERE / "definitely-not-a-corpus")]) == 1
