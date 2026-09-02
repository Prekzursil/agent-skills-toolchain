"""The D4 close: a workflow id must resolve to EXACTLY ONE path under platform/workflows/.

Relationship to the gate that already shipped
---------------------------------------------
``platform/lib/foundry/test_foundry.py::test_no_workflow_id_resolves_to_two_different_documents``
asserts ``divergent_ids == {}`` -- one id must not resolve to two documents whose CONTENT differs.
That gate is correct and stays. It is also, by construction, blind to the case the corpus actually
shipped: ``forge fuse --strategy best-of-breed`` and ``forge tournament`` over the same source pair
both emitted the winning document, so two paths held ONE byte-identical document under ONE
content-addressed id. Equal content means ``divergent_ids`` is empty, so the shipped gate reported
clean while the collision was live.

``test_the_shipped_gate_is_blind_to_an_identical_content_duplicate`` below pins that blind spot as
a measured fact rather than an assertion about it, so if the foundry gate is ever widened this
module's reason for existing is re-litigated instead of silently duplicated.

Every gate here is proved in BOTH states: it must fire on a seeded collision and be silent on a
clean tree. A probe that is silent in both measures nothing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import workflow_id_index as W

WORKFLOWS_DIR = W.DEFAULT_ROOT


# --------------------------------------------------------------------------- fixtures


def _minimal_workflow(wid: str) -> dict:
    """The smallest document ``is_workflow_doc`` accepts -- id + the two DSL-mandatory keys."""
    return {
        "id": wid,
        "dsl_version": "1.0.0",
        "kind": "workflow",
        "stages": [{"id": "s0", "kind": "task", "work_unit_ref": "AAA-0001"}],
    }


@pytest.fixture
def clean_tree(tmp_path: Path) -> Path:
    """Two documents, two distinct ids, one of them in a subdirectory."""
    (tmp_path / "alpha.json").write_text(
        json.dumps(_minimal_workflow("wf.alpha")), encoding="utf-8"
    )
    (tmp_path / "forged").mkdir()
    (tmp_path / "forged" / "beta.json").write_text(
        json.dumps(_minimal_workflow("wf.beta")), encoding="utf-8"
    )
    return tmp_path


# ------------------------------------------------------- the gate over the real corpus


@pytest.fixture(scope="module")
def corpus_report() -> dict:
    if not WORKFLOWS_DIR.is_dir():
        pytest.skip(f"platform/workflows is not present at {WORKFLOWS_DIR}")
    return W.scan_workflow_ids(WORKFLOWS_DIR)


def test_the_walk_actually_found_the_corpus(corpus_report: dict):
    """Fail-closed floor. Asserted separately so an empty walk cannot masquerade as a pass."""
    assert corpus_report["unparsable"] == [], corpus_report["unparsable"]
    assert corpus_report["workflow_documents"] > 50, (
        "the walk matched suspiciously few workflow documents; the corpus holds ~100, so a small "
        f"number means the scan is looking in the wrong place: {corpus_report}"
    )


def test_every_workflow_id_resolves_to_exactly_one_path(corpus_report: dict):
    """The D4 invariant, stated as an exact N-of-N positive rather than 'nothing blocking'."""
    assert W.violations(corpus_report) == [], (
        "workflow id uniqueness is violated under platform/workflows/. Two paths for one id make "
        "id -> path resolution ambiguous, and platform/routing/index.py silently drops the second "
        f"one: {json.dumps(corpus_report['ids_at_multiple_paths'], indent=2)}"
    )
    assert corpus_report["distinct_ids"] == corpus_report["workflow_documents"], (
        f"{corpus_report['workflow_documents']} documents carry only "
        f"{corpus_report['distinct_ids']} distinct ids"
    )


def test_the_certified_fusion_is_on_disk_exactly_once(corpus_report: dict):
    """Named regression for the closed D4 pair.

    The generic gate above already covers this, but the specific failure -- re-running
    ``forge tournament --out <corpus path>`` beside ``forge fuse`` for the same pair -- is worth a
    test that names it, so a reintroduction reads as "the D4 duplicate is back" rather than as a
    generic uniqueness failure. The id is READ off the kept document, never hardcoded: the id is
    content-addressed, so pinning its digest suffix here would make this test fail on any
    legitimate change to the fusion.
    """
    kept = WORKFLOWS_DIR / "forged" / "fused.cnc07-arc05.workflow.json"
    if not kept.is_file():
        pytest.skip("the certified fusion has not been emitted")
    wid = json.loads(kept.read_text(encoding="utf-8"))["id"]
    paths = [
        e["path"]
        for entries in [corpus_report["ids_at_multiple_paths"].get(wid, [])]
        for e in entries
    ]
    assert paths == [], (
        f"the certified fusion id {wid!r} is on disk at more than one path again: {paths}. "
        "forge tournament and forge fuse emit the SAME document when the tournament winner is "
        "the fused strategy, so both must not be written into the indexed corpus."
    )


# ------------------------------------------------------------- both-states controls


def test_the_gate_is_silent_on_a_clean_tree(clean_tree: Path):
    """Control half 1. Without this, a green from the corpus gate is unfalsifiable."""
    report = W.scan_workflow_ids(clean_tree)
    assert report["workflow_documents"] == 2
    assert report["distinct_ids"] == 2
    assert report["ids_at_multiple_paths"] == {}
    assert W.violations(report) == []


def test_the_gate_fires_on_a_seeded_IDENTICAL_content_duplicate(clean_tree: Path):
    """Control half 2 -- the EXACT shape D4 shipped: same id, same bytes, two paths.

    This is the case the content-level foundry gate cannot see, so if this test does not fire the
    close is worthless.
    """
    original = json.loads((clean_tree / "alpha.json").read_text(encoding="utf-8"))
    (clean_tree / "forged" / "alpha.TOURNAMENT-WINNER.json").write_text(
        json.dumps(original), encoding="utf-8"
    )
    report = W.scan_workflow_ids(clean_tree)
    assert report["workflow_documents"] == 3
    assert report["distinct_ids"] == 2
    entries = report["ids_at_multiple_paths"]["wf.alpha"]
    assert sorted(e["path"] for e in entries) == [
        "alpha.json",
        "forged/alpha.TOURNAMENT-WINNER.json",
    ]
    assert len({e["digest"] for e in entries}) == 1, (
        "the seeded duplicate must be byte-identical"
    )
    bad = W.violations(report)
    assert bad, (
        "the gate did NOT fire on an identical-content duplicate, so it measures nothing"
    )
    assert "byte-identical copies" in bad[0]


def test_the_gate_fires_on_a_seeded_DIVERGENT_duplicate(clean_tree: Path):
    """Control half 3: the same id on two paths with DIFFERENT content is the worse case."""
    diverged = json.loads((clean_tree / "alpha.json").read_text(encoding="utf-8"))
    diverged["stages"] = [
        *diverged["stages"],
        {"id": "extra", "kind": "task", "work_unit_ref": "AAA-0002"},
    ]
    (clean_tree / "forged" / "alpha.divergent.json").write_text(
        json.dumps(diverged), encoding="utf-8"
    )
    report = W.scan_workflow_ids(clean_tree)
    entries = report["ids_at_multiple_paths"]["wf.alpha"]
    assert len({e["digest"] for e in entries}) == 2
    bad = W.violations(report)
    assert bad
    assert "GENUINELY DIFFERENT documents" in bad[0]


def test_the_shipped_gate_is_blind_to_an_identical_content_duplicate(clean_tree: Path):
    """Measure the foundry gate's blind spot instead of asserting it in prose.

    Imports the shipped scanner and runs it on the same seeded tree. It must report a CLEAN
    ``divergent_ids`` while this module's gate fires -- that gap is the whole reason this module
    exists. If this test ever fails because the foundry gate was widened, delete the redundancy
    rather than keeping two gates for one invariant.
    """
    foundry_test = WORKFLOWS_DIR.parent / "lib" / "foundry" / "test_foundry.py"
    if not foundry_test.is_file():
        pytest.skip("the foundry test module is not present")
    import importlib.util

    spec = importlib.util.spec_from_file_location("_d4_foundry_ref", foundry_test)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    original = json.loads((clean_tree / "alpha.json").read_text(encoding="utf-8"))
    (clean_tree / "forged" / "alpha.copy.json").write_text(
        json.dumps(original), encoding="utf-8"
    )

    shipped = mod._scan_workflow_ids(clean_tree)
    mine = W.scan_workflow_ids(clean_tree)
    assert shipped["divergent_ids"] == {}, (
        "the shipped content-level gate now catches identical-content duplicates; this module is "
        "redundant and should be reduced to the parts the foundry gate still does not cover"
    )
    assert mine["ids_at_multiple_paths"], (
        "this module's gate must catch what the shipped one cannot"
    )


# --------------------------------------------------------------- detector-failure modes


def test_an_empty_tree_is_a_violation_not_a_pass(tmp_path: Path):
    report = W.scan_workflow_ids(tmp_path)
    assert report["workflow_documents"] == 0
    bad = W.violations(report)
    assert bad, "an empty walk must fail closed"
    assert "measured nothing" in bad[0]


def test_unparsable_json_is_a_violation_not_a_skip(clean_tree: Path):
    (clean_tree / "broken.json").write_text("{not json", encoding="utf-8")
    report = W.scan_workflow_ids(clean_tree)
    assert report["unparsable"], (
        "a malformed file must be reported, not silently skipped"
    )
    assert any("unparsable" in v for v in W.violations(report))


def test_sidecar_reports_are_excluded_by_shape_not_by_name(tmp_path: Path):
    """A renamed sidecar must still be excluded, and a document must not be excluded by name."""
    (tmp_path / "innocuous-name.json").write_text(
        json.dumps({"id": "rep", "certification": {"verdict": "CERTIFIED"}}),
        encoding="utf-8",
    )
    (tmp_path / "SOMETHING-STATUS.json").write_text(
        json.dumps(_minimal_workflow("wf.named.like.a.sidecar")), encoding="utf-8"
    )
    report = W.scan_workflow_ids(tmp_path)
    assert report["workflow_documents"] == 1, (
        "shape must decide: the sidecar without dsl_version/stages is out, the document named "
        f"like a sidecar is in. {report}"
    )
    assert report["distinct_ids"] == 1


def test_the_scan_recurses_into_subdirectories(tmp_path: Path):
    """Pins the rglob. A depth-1 walk reports clean while a forged/ collision is live."""
    nested = tmp_path / "forged" / "deeper"
    nested.mkdir(parents=True)
    (nested / "x.json").write_text(
        json.dumps(_minimal_workflow("wf.nested")), encoding="utf-8"
    )
    report = W.scan_workflow_ids(tmp_path)
    assert report["workflow_documents"] == 1, "the scan did not recurse"
    assert list(report["ids_at_multiple_paths"]) == []
    assert len(list(tmp_path.glob("*.json"))) == 0, (
        "control: a depth-1 glob finds nothing here, so this test would pass vacuously without "
        "the rglob"
    )


def test_digest_is_computed_over_parsed_json_not_raw_bytes(tmp_path: Path):
    """Line endings must not change the digest: git stores LF, Windows checks out CRLF."""
    doc = _minimal_workflow("wf.eol")
    lf = json.dumps(doc, indent=2).replace("\r\n", "\n")
    crlf = lf.replace("\n", "\r\n")
    assert lf.encode() != crlf.encode(), "control: the two encodings must really differ"
    (tmp_path / "lf.json").write_bytes(lf.encode("utf-8"))
    (tmp_path / "crlf.json").write_bytes(crlf.encode("utf-8"))
    report = W.scan_workflow_ids(tmp_path)
    entries = report["ids_at_multiple_paths"]["wf.eol"]
    assert len({e["digest"] for e in entries}) == 1, (
        "the digest is line-ending sensitive, so it would report a phantom divergence between a "
        "git blob and a Windows checkout of the same document"
    )


# ------------------------------------------------------------------------ the CLI gate


def test_cli_gate_exits_zero_on_a_clean_tree(clean_tree: Path, capsys):
    rc = W.main([str(clean_tree)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "SUCCESS:workflow-id-uniqueness" in out


def test_cli_gate_exits_nonzero_on_a_seeded_collision(clean_tree: Path, capsys):
    original = json.loads((clean_tree / "alpha.json").read_text(encoding="utf-8"))
    (clean_tree / "dup.json").write_text(json.dumps(original), encoding="utf-8")
    rc = W.main([str(clean_tree)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "FAILED:workflow-id-uniqueness" in out
    assert "VIOLATION:" in out


def test_cli_gate_fails_closed_on_a_missing_root(tmp_path: Path, capsys):
    rc = W.main([str(tmp_path / "does-not-exist")])
    assert rc == 1
    assert "FAILED:workflow-id-uniqueness" in capsys.readouterr().out


def test_is_workflow_doc_rejects_non_documents():
    assert not W.is_workflow_doc(None)
    assert not W.is_workflow_doc([])
    assert not W.is_workflow_doc({"dsl_version": "1.0.0", "stages": []})
    assert not W.is_workflow_doc({"id": "", "dsl_version": "1.0.0", "stages": []})
    assert not W.is_workflow_doc({"id": 7, "dsl_version": "1.0.0", "stages": []})
    assert not W.is_workflow_doc({"id": "x", "stages": []})
    assert not W.is_workflow_doc({"id": "x", "dsl_version": "1.0.0"})
    assert W.is_workflow_doc(_minimal_workflow("wf.ok"))


def test_canonical_digest_is_key_order_independent():
    a = _minimal_workflow("wf.k")
    b = copy.deepcopy(a)
    b_reordered = {k: b[k] for k in reversed(list(b))}
    assert list(a) != list(b_reordered), "control: the key order must really differ"
    assert W.canonical_digest(a) == W.canonical_digest(b_reordered)
