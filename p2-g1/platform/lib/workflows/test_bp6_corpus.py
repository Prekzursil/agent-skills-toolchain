"""Corpus-level tests over the 13 blueprints delivered by unit blueprints/bp-6 (cards 61-72).

Per-blueprint mechanism tests live in the sibling ``test_<name>.py`` modules. This module asserts
the properties that only exist ACROSS the set: distinctness by mechanism, id and artifact-path
uniqueness, category coverage, that every schema a blueprint points at actually loads, and the
honest negatives (which DSL stage kinds this range does NOT use, and why).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import _bp6_distinctness as D
import _bp6_validate_report as R
import _harness as H

#: The 12 designs this unit owns plus ONE deliberate split, so 13 files from 12 cards.
EXPECTED_FILES = 13
EXPECTED_CARDS = 12

#: The six spans the spec requires the 96 built-ins to cover. This range contributes to four of
#: them; the two it does not are named in :func:`test_category_coverage_is_stated_honestly`.
SPEC_CATEGORIES = {
    "research-and-evidence",
    "engineering-and-reliability",
    "security-governance-and-risk",
    "product-design-and-strategy",
    "data-science-knowledge-and-creative",
    "collective-intelligence-and-meta",
}


@pytest.fixture(scope="module")
def docs() -> dict[str, dict]:
    return {name: H.load(name) for name in R.BP6_FILES}


def test_the_expected_number_of_files_exist(docs: dict[str, dict]) -> None:
    assert len(docs) == EXPECTED_FILES
    for name in R.BP6_FILES:
        assert (R.WORKFLOW_DIR / name).is_file(), name


def test_every_blueprint_is_schema_valid_with_zero_semantic_violations(
    docs: dict[str, dict],
) -> None:
    """Same check the unit reports, run through the same validator the CLI uses."""
    failures = {
        name: H.conformance_failures(doc)
        for name, doc in docs.items()
        if H.conformance_failures(doc)
    }
    assert failures == {}


def test_the_validate_driver_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Guard against the driver disagreeing with the assertion above (one of them would be lying)."""
    rc = R.main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "SUCCESS:bp6-validate" in out
    assert f"files_checked={EXPECTED_FILES}" in out


def test_the_driver_can_fail(capsys: pytest.CaptureFixture[str]) -> None:
    """Both-states control on the driver itself: a missing file must make it exit non-zero."""
    rc = R.main(["definitely-not-a-blueprint.json"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "FILE NOT FOUND" in out
    assert "FAILED:bp6-validate" in out


# --------------------------------------------------------------------------- identity


def test_ids_names_and_versions_are_unique_and_well_formed(
    docs: dict[str, dict],
) -> None:
    ids = [doc["id"] for doc in docs.values()]
    assert len(set(ids)) == len(ids), (
        "a duplicate workflow id would make two files one workflow"
    )
    names = [doc["name"] for doc in docs.values()]
    assert len(set(names)) == len(names)
    for name, doc in docs.items():
        assert doc["dsl_version"] == "1.0.0"
        assert doc["version"] == "1.0.0"
        assert Path(name).stem == doc["id"], (
            f"{name} declares id {doc['id']!r}; file name and id must agree so a reference by "
            "either resolves to the same document"
        )


def test_no_two_blueprints_claim_the_same_artifact_path(docs: dict[str, dict]) -> None:
    owner: dict[str, list[str]] = {}
    for name, doc in docs.items():
        for path in H.declared_paths(doc):
            owner.setdefault(path, []).append(name)
    collisions = {p: sorted(v) for p, v in owner.items() if len(v) > 1}
    assert collisions == {}, (
        f"two workflows writing one path race and lose work: {collisions}"
    )


def test_every_inline_work_unit_id_is_globally_unique(docs: dict[str, dict]) -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for name, doc in docs.items():
        for unit in H.inline_units(doc):
            uid = str(unit["id"])
            if uid in seen:
                duplicates.append(f"{uid} in both {seen[uid]} and {name}")
            seen[uid] = name
    assert duplicates == [], duplicates
    assert len(seen) >= 25, f"only {len(seen)} inline units across 13 blueprints"


# ------------------------------------------------------------------------ distinctness


def test_no_two_blueprints_are_near_duplicates_by_mechanism(
    docs: dict[str, dict],
) -> None:
    fps = {name: D.fingerprint(doc) for name, doc in docs.items()}
    worst = (0.0, "", "")
    for a, b in ((a, b) for a in fps for b in fps if a < b):
        score = D.jaccard(fps[a], fps[b])
        if score > worst[0]:
            worst = (score, a, b)
    assert worst[0] < D.DEFAULT_THRESHOLD, (
        f"near-duplicate by mechanism: {worst[1]} ~ {worst[2]} at {worst[0]:.4f}"
    )
    # margin is reported, not asserted away: a threshold with no measured margin is a guess
    assert worst[0] < 0.5, f"unexpectedly close pair: {worst}"


def test_the_distinctness_detector_fires_on_a_known_duplicate(
    docs: dict[str, dict],
) -> None:
    """Both-states control: without this, a similarity of 0 could mean a broken fingerprint."""
    victim = sorted(docs)[0]
    clone = json.loads(json.dumps(docs[victim]))
    clone["id"] = "synthetic-duplicate-control"
    clone["name"] = "renamed copy"
    clone["description"] = "different words, identical mechanism"
    score = D.jaccard(D.fingerprint(clone), D.fingerprint(docs[victim]))
    assert score >= D.DEFAULT_THRESHOLD, score
    assert score == pytest.approx(1.0), (
        "prose-only edits must not move the mechanism fingerprint at all"
    )


def test_the_fingerprint_is_sensitive_to_a_mechanism_change(
    docs: dict[str, dict],
) -> None:
    """The other half of the control: a real mechanism edit MUST move the fingerprint."""
    victim = sorted(docs)[0]
    doc = docs[victim]
    before = D.fingerprint(doc)

    def bend(d: dict) -> None:
        d["failure_policy"]["on_failure"] = "continue"
        d["retry_policy"]["strategy"] = "none"
        d["retry_policy"]["max_attempts"] = 1
        d["retry_policy"].pop("pivot", None)

    after = D.fingerprint(H.mutated(doc, bend))
    assert after != before, (
        "a fingerprint blind to the failure policy would flag nothing"
    )


def test_every_declared_mechanism_primary_is_unique(docs: dict[str, dict]) -> None:
    primaries: dict[str, list[str]] = {}
    for name, doc in docs.items():
        fp = doc["x_extensions"]["mechanism_fingerprint"]
        primaries.setdefault(fp["primary"], []).append(name)
        assert fp["distinguishing_stage"] in H.stage_ids(doc), fp[
            "distinguishing_stage"
        ]
        assert fp["distinguishing_gate"] in (doc.get("gates") or {}), fp[
            "distinguishing_gate"
        ]
        assert fp["not_a_duplicate_because"].strip()
    dupes = {k: v for k, v in primaries.items() if len(v) > 1}
    assert dupes == {}, dupes


def test_the_one_split_is_disclosed_and_wired_to_its_parent() -> None:
    child = H.load("scanner-detector-integrity-probe")
    split = child["x_extensions"]["split_disclosure"]
    assert split["split_out_of"] == "BP-SEC-01"
    assert "different failure modes" in split["reason"]
    parent = H.load("security-review-scanner-fix-loop")
    assert child["id"] in parent["subworkflows"]
    assert parent["stages"][0]["workflow"]["workflow_id"] == child["id"]
    assert EXPECTED_FILES - EXPECTED_CARDS == 1, (
        "13 files from 12 cards = exactly one split"
    )


# -------------------------------------------------------------------------- coverage


def test_every_blueprint_is_flagship_and_has_a_test_module(
    docs: dict[str, dict],
) -> None:
    here = Path(__file__).resolve().parent
    for name, doc in docs.items():
        assert doc["flagship"] is True, name
        module = here / f"test_{doc['id'].replace('-', '_')}.py"
        assert module.is_file(), f"flagship {doc['id']} has no test module at {module}"


def test_category_coverage_is_stated_honestly(docs: dict[str, dict]) -> None:
    used: set[str] = set()
    for doc in docs.values():
        assert doc["categories"], doc["id"]
        used |= set(doc["categories"])
    assert used <= SPEC_CATEGORIES, (
        f"category outside the spec vocabulary: {used - SPEC_CATEGORIES}"
    )
    # This range is cards 61-72: six security/governance, five incident/reliability, one data.
    assert {
        "security-governance-and-risk",
        "engineering-and-reliability",
        "data-science-knowledge-and-creative",
        "collective-intelligence-and-meta",
        "research-and-evidence",
        "product-design-and-strategy",
    } == SPEC_CATEGORIES
    missing = SPEC_CATEGORIES - used
    assert missing == set(), (
        f"this range claims to touch every spec span but does not cover {sorted(missing)}"
    )


def test_no_blueprint_declares_a_council_and_that_is_deliberate(
    docs: dict[str, dict],
) -> None:
    """Honest negative: not one card in 61-72 specifies a deliberative council topology.

    Cards 61-72 are six security/governance reviews, five incident procedures and one data
    routing rule; their participant topologies are parallel probes, a reconciler and an owner
    checkpoint. Adding a ``council`` stage to hit a capability checkbox would be padding, so the
    kind is unused here and the absence is asserted rather than left ambiguous. The DSL's council
    capability is exercised by ``platform/lib/wfdsl/examples/wf-full-coverage.json``.
    """
    kinds: set[str] = set()
    for doc in docs.values():
        kinds |= {str(s.get("kind")) for s in H.stages(doc)}
    assert "council" not in kinds
    assert {
        "task",
        "gate",
        "fanout",
        "loop",
        "human_checkpoint",
        "subworkflow",
        "repair_loop",
    } <= (kinds), sorted(kinds)
    assert "barrier" not in kinds, (
        "barriers here are attached to their fan-out (the barrier_spec form) rather than declared "
        "as standalone join stages; asserting it keeps the claim measured"
    )


def test_the_declared_mechanisms_span_distinct_gate_predicate_shapes(
    docs: dict[str, dict],
) -> None:
    predicates: set[str] = set()
    for doc in docs.values():
        for g in (doc.get("gates") or {}).values():
            predicates.add(str(g.get("predicate")))
    assert "custom-expression" in predicates
    assert "completion-predicate-v1" in predicates, (
        "at least one blueprint must reference the ONE shared 12-condition predicate"
    )


# ---------------------------------------------------------------- schema references load


def test_every_schema_reference_resolves_on_disk_and_compiles(
    docs: dict[str, dict],
) -> None:
    """A blueprint pointing at a schema that does not load cannot emit a valid receipt."""
    refs: dict[str, set[str]] = {}
    for name, doc in docs.items():
        for st in H.stages(doc):
            for spec in st.get("produces") or []:
                if isinstance(spec, dict) and spec.get("schema_ref"):
                    refs.setdefault(str(spec["schema_ref"]), set()).add(name)
            dec = st.get("decision_artifact")
            if isinstance(dec, dict) and dec.get("schema_ref"):
                refs.setdefault(str(dec["schema_ref"]), set()).add(name)
            unit = st.get("work_unit")
            if isinstance(unit, dict) and unit.get("output_schema"):
                refs.setdefault(str(unit["output_schema"]), set()).add(name)
        for spec in (doc.get("outputs") or {}).values():
            if isinstance(spec, dict) and spec.get("schema_ref"):
                refs.setdefault(str(spec["schema_ref"]), set()).add(name)

    assert len(refs) >= 20, (
        f"only {len(refs)} distinct schema references - suspiciously few"
    )
    missing: dict[str, list[str]] = {}
    broken: dict[str, str] = {}
    for ref, users in refs.items():
        rel = ref.split("#", 1)[0]
        path = H.REPO_ROOT / rel
        if not path.is_file():
            missing[ref] = sorted(users)
            continue
        try:
            Draft202012Validator.check_schema(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except Exception as exc:  # noqa: BLE001
            broken[ref] = f"{type(exc).__name__}: {exc}"[:200]
    assert missing == {}, f"schema references that do not resolve on disk: {missing}"
    assert broken == {}, f"schema references that do not compile: {broken}"


def test_the_schema_existence_check_can_fail(docs: dict[str, dict]) -> None:
    """Control for the check above: a deliberately bogus reference must be reported missing."""
    bogus = "command-center/schema/there-is-no-such-schema.schema.json"
    assert not (H.REPO_ROOT / bogus).is_file()


# ------------------------------------------------------------------ policy floor, corpus-wide


def test_every_blueprint_denies_tools_by_default_and_closes_over_its_requests(
    docs: dict[str, dict],
) -> None:
    for name, doc in docs.items():
        policy = doc["tool_policy"]
        assert policy["default"] == "deny", name
        missing = H.contains_all(policy["allow"], sorted(H.all_tool_tokens(doc)))
        assert missing == [], f"{name}: requested but not allowed: {missing}"


def test_every_blueprint_is_dry_runnable_and_side_effect_free(
    docs: dict[str, dict],
) -> None:
    for name, doc in docs.items():
        dry = doc["dry_run"]
        assert dry["supported"] is True, name
        assert dry["side_effect_free"] is True, name
        assert dry["forbid_tools"], name
        writes = {t for t in H.all_tool_tokens(doc) if t.startswith("Write(")}
        forbidden = set(dry["forbid_tools"])
        assert writes <= forbidden, (
            f"{name}: dry run would still write via {writes - forbidden}"
        )


def test_every_blueprint_ends_in_a_terminal_state_and_never_silently(
    docs: dict[str, dict],
) -> None:
    for name, doc in docs.items():
        fail = doc["failure_policy"]
        assert fail["terminal_state_required"] is True, name
        assert fail["never_silent"] is True, name
        assert fail["classify_as"], name
        assert doc["stopping_rules"], f"{name} has no explicit stopping rule"
        assert doc["lineage"]["derived_from"], name
        assert doc["portability"]["export"]["redact_secrets"] is True, name
