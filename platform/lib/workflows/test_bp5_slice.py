"""Slice-wide tests for the bp-5 blueprints (library cards 49-60), read from disk.

Covers all 12 documents. Per-flagship mechanism tests live in the eight
``test_crv_*.py`` / ``test_tst_*.py`` files alongside this one.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

CATALOG = kit.REPO / "command-center" / "WORK-UNIT-CATALOG.json"
DISTINCTNESS_KEY = ("subject", "oracle", "comparison_axis", "output_type")


@pytest.fixture(scope="module")
def docs() -> dict[str, dict]:
    return {slug: kit.load(slug) for slug in kit.SLUGS}


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_blueprint_on_disk_validates(slug: str) -> None:
    """Layer 1+2: the DELIVERABLE validates, not just the builder's in-memory object."""
    kit.assert_accepted(kit.load(slug))


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_declared_id_matches_filename(slug: str) -> None:
    doc = kit.load(slug)
    assert doc["id"] == slug
    assert doc["dsl_version"] == "1.0.0"
    assert doc["version"] == "1.0.0"


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_worked_example_gates_evaluate_true(slug: str) -> None:
    """Layer 3: the worked example is a MEASUREMENT - its gates really evaluate true."""
    doc = kit.load(slug)
    ex = kit.worked_example(doc)
    expected = ex.get("expected_gate_pass") or []
    assert expected, f"{slug}: worked example claims no passing gate"
    for gate_id in expected:
        assert kit.evaluate_gate(doc, gate_id) is True, f"{slug}: gate {gate_id} did not evaluate true"


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_worked_example_stopping_rules_fire_with_their_floor(slug: str) -> None:
    doc = kit.load(slug)
    ex = kit.worked_example(doc)
    rules = {r["id"]: r for r in doc.get("stopping_rules") or []}
    expected = ex.get("expected_stop") or []
    assert expected, f"{slug}: worked example claims no stopping rule fires"
    for rid in expected:
        assert kit.evaluate_stop(doc, rid) is True, f"{slug}: stopping rule {rid} did not fire"
        floor = rules[rid].get("minimum_conditions")
        if floor is not None:
            assert _expr.evaluate(floor, kit.worked_context(doc), strict=True) is True, (
                f"{slug}: the deliberation floor for {rid} does not hold, so the rule may not fire"
            )


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_negative_control_flips_its_gate_false(slug: str) -> None:
    """Both-states on the EXPRESSION layer: every blueprint names one state its gate rejects."""
    doc = kit.load(slug)
    neg = kit.worked_example(doc).get("negative_control")
    assert isinstance(neg, dict) and neg.get("gate"), f"{slug}: no negative control declared"
    assert neg.get("overrides"), f"{slug}: negative control overrides nothing, so it cannot flip anything"
    assert neg.get("why"), f"{slug}: negative control does not say what failure it models"
    assert kit.evaluate_gate(doc, neg["gate"]) is True, (
        f"{slug}: gate {neg['gate']} is not true in the healthy state, so a false result proves nothing"
    )
    assert kit.evaluate_gate(doc, neg["gate"], neg["overrides"]) is False, (
        f"{slug}: gate {neg['gate']} stayed TRUE under {neg['overrides']} - the control does not fire"
    )


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_every_expression_parses_and_is_covered_by_the_worked_context(slug: str) -> None:
    """A rule that cannot parse can never fire; an identifier absent from the context is
    unmeasured, and under strict evaluation an unmeasured metric raises rather than reading false."""
    doc = kit.load(slug)
    ctx = kit.worked_context(doc)
    problems: list[str] = []
    for path, e in _collect(doc):
        try:
            _expr.to_ast(e).evaluate(ctx, strict=True)
        except _expr.ExpressionError as exc:
            problems.append(f"{path}: {exc}")
    assert not problems, f"{slug}: {problems}"


def _collect(node, path: str = "") -> list[tuple[str, object]]:
    keys = {"when", "expression", "converged_when", "minimum_conditions"}
    out: list[tuple[str, object]] = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}/{k}"
            if k in keys and isinstance(v, (str, dict)):
                out.append((p, v))
            else:
                out.extend(_collect(v, p))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(_collect(v, f"{path}/{i}"))
    return out


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_dropping_a_gate_stage_is_rejected(slug: str) -> None:
    """Both-states on the DOCUMENT layer: deleting any gate stage that a later stage depends on
    must be caught by DSL-SEM-002, so a blueprint cannot be quietly edited to skip its control."""
    doc = kit.load(slug)
    gate_stages = [
        s["id"]
        for s in doc["stages"]
        if s.get("kind") == "gate"
        and any(s["id"] in (o.get("depends_on") or []) for o in doc["stages"])
    ]
    assert gate_stages, f"{slug}: no gate stage is depended upon, so no control is load-bearing"
    kit.assert_rejected(kit.drop_stage(doc, gate_stages[0]), f"dropped gate stage {gate_stages[0]}")


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_no_gate_is_silently_deletable(slug: str) -> None:
    """REGRESSION GUARD for a defect this slice's own mutation control found.

    A gate stage that nothing depends on is deletable with no schema error and no DSL-SEM-002
    violation - and it gates nothing, because the workflow's artifact was already emitted
    upstream of it. Six of these twelve blueprints originally ended in such a gate. Every gate
    must now have a downstream dependent, so dropping ANY of them breaks the graph.
    """
    doc = kit.load(slug)
    depended = {str(d) for s in doc["stages"] for d in (s.get("depends_on") or [])}
    terminal = [
        str(s["id"]) for s in doc["stages"] if s.get("kind") == "gate" and str(s["id"]) not in depended
    ]
    assert not terminal, f"{slug}: gate(s) with no downstream dependent, so silently deletable: {terminal}"


@pytest.mark.parametrize("slug", kit.SLUGS)
def test_dropping_any_single_gate_stage_is_rejected(slug: str) -> None:
    """The strong form: EVERY gate, not just the first one that happens to be depended upon."""
    doc = kit.load(slug)
    gates = [str(s["id"]) for s in doc["stages"] if s.get("kind") == "gate"]
    assert gates, f"{slug}: no gate stages at all"
    for gid in gates:
        kit.assert_rejected(kit.drop_stage(doc, gid), f"{slug}: dropped gate {gid}")


def test_mechanism_fingerprints_are_pairwise_distinct(docs: dict[str, dict]) -> None:
    """Exact set comparison, not judgement: a mechanical question gets a mechanical answer."""
    keys: dict[tuple, list[str]] = {}
    for slug, doc in docs.items():
        fp = doc["x_extensions"]["mechanism_fingerprint"]
        for field in DISTINCTNESS_KEY:
            assert field in fp, f"{slug}: fingerprint missing {field}"
        keys.setdefault(tuple(fp[f] for f in DISTINCTNESS_KEY), []).append(slug)
    dupes = {k: v for k, v in keys.items() if len(v) > 1}
    assert not dupes, f"blueprints share a mechanism key: {dupes}"
    assert len(keys) == len(kit.SLUGS)


def test_closest_pair_still_differs_on_a_majority_of_fingerprint_fields(docs: dict[str, dict]) -> None:
    """Residual disclosure as an assertion: near-duplicates by mechanism are the real risk, and
    an exact-key check alone would not see two blueprints agreeing on 6 of 7 axes."""
    prints = {s: d["x_extensions"]["mechanism_fingerprint"] for s, d in docs.items()}
    fields = sorted({f for fp in prints.values() for f in fp})
    worst = 0.0
    worst_pair = ("", "")
    slugs = sorted(prints)
    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            agree = sum(1 for f in fields if prints[a].get(f) == prints[b].get(f)) / len(fields)
            if agree > worst:
                worst, worst_pair = agree, (a, b)
    assert worst < 0.75, f"{worst_pair} agree on {worst:.0%} of fingerprint fields - too close"


def test_every_work_unit_ref_resolves_to_a_real_catalog_unit(docs: dict[str, dict]) -> None:
    real = {u["id"] for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]}
    refs = {r for doc in docs.values() for r in _walk_key(doc, "work_unit_ref")}
    assert refs, "no catalogued unit is referenced at all"
    assert not (refs - real), f"dangling work_unit_ref: {sorted(refs - real)}"


def test_inline_unit_ids_cannot_be_mistaken_for_catalog_units(docs: dict[str, dict]) -> None:
    """MEASURED rather than trusted: the catalog's prefix set is recomputed here, so a future
    catalog that adds a CRV or QLT prefix turns this test red instead of silently colliding."""
    real = {u["id"] for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]}
    prefixes = {m.group(1) for i in real if (m := re.match(r"^([A-Z]+)-", i))}
    inline = {
        u["id"]
        for doc in docs.values()
        for u in _walk_key(doc, "work_unit")
        if isinstance(u, dict) and "id" in u
    }
    assert inline, "no inline work unit was minted"
    assert not (inline & real), f"inline id collides with a catalog id: {sorted(inline & real)}"
    bad = {i for i in inline if (m := re.match(r"^([A-Z]+)-", i)) and m.group(1) in prefixes}
    assert not bad, f"inline id sits in a catalog prefix namespace: {sorted(bad)}"


def test_inline_completion_sentinels_name_their_own_unit(docs: dict[str, dict]) -> None:
    """One of the four measured catalog defects is 96 sentinels that do not name their own unit;
    this slice does not add to that debt."""
    bad: list[str] = []
    for doc in docs.values():
        for u in _walk_key(doc, "work_unit"):
            if isinstance(u, dict) and "completion_sentinel" in u:
                if not u["completion_sentinel"].startswith(f"SUCCESS:{u['id']}"):
                    bad.append(f"{doc['id']}:{u['id']}")
    assert not bad, f"sentinels not naming their own unit: {bad}"


def test_flagship_count_clears_the_pro_rata_floor(docs: dict[str, dict]) -> None:
    """The spec wants >=40 of 96 flagship; pro rata over a 12-card slice is 5."""
    flagships = [s for s, d in docs.items() if d.get("flagship")]
    assert len(flagships) >= 5, f"only {len(flagships)} flagship in this slice"


def test_flagship_blueprints_each_have_a_dedicated_test_file(docs: dict[str, dict]) -> None:
    """A flagship claim without a dedicated end-to-end test is an overclaim about coverage."""
    present = {p.name for p in kit.HERE.glob("test_*.py")}
    missing = []
    for slug, doc in docs.items():
        if not doc.get("flagship"):
            continue
        stem = slug.replace(".", "_").replace("-", "_")
        if f"test_{stem}.py" not in present:
            missing.append(f"test_{stem}.py")
    assert not missing, f"flagship blueprints without a dedicated test file: {missing}"


def test_every_blueprint_declares_contraindications_and_a_non_duplicate_argument(
    docs: dict[str, dict],
) -> None:
    for slug, doc in docs.items():
        x = doc["x_extensions"]
        assert len(x.get("contraindications") or []) >= 2, f"{slug}: too few contraindications"
        assert x.get("why_not_a_duplicate"), f"{slug}: no non-duplicate argument"
        assert len(x.get("benchmark_cases") or []) >= 2, f"{slug}: fewer than two benchmark cases"
        assert x.get("library_card"), f"{slug}: no library card anchor"
        assert 49 <= x["card_index"] <= 60, f"{slug}: card index outside this slice's range"


def test_no_estimate_claims_a_measured_basis_without_a_measurement(docs: dict[str, dict]) -> None:
    """None of these has been RUN, so a historical-measured basis would be a measured label on a
    guess. The schema only enforces measurement_source when the basis claims to be measured;
    this asserts the honest basis for this slice."""
    for slug, doc in docs.items():
        est = doc["estimate"]
        assert est["basis"] == "static-declared", f"{slug}: basis={est['basis']} on an unrun blueprint"
        assert est["confidence"] in {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}


#: Credential-SHAPED literals: a prefix at a token boundary followed by a high-entropy tail.
#: A bare-substring check here was a real false positive - "risk-classification" contains
#: "sk-" - so the pattern requires the boundary AND the tail length. The detector is proved
#: on a known-present sample below; a matcher whose silence has not been earned measures nothing.
_SECRET_SHAPES = (
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])ghp_[A-Za-z0-9]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])hf_[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def test_the_secret_shape_detector_fires_on_a_known_present_sample() -> None:
    """Detector control (both-states, KNOWN-PRESENT half). Runs BEFORE the absence claim below
    is worth anything: a pattern that cannot find a planted credential shape cannot certify a
    document as clean. The planted values are synthetic literals, not credentials."""
    # PLACEHOLDER / EXAMPLE ONLY - every shape is ASSEMBLED at run time from inert fragments so
    # this source file contains no complete credential-shaped literal for any scanner to flag.
    dash5 = "-" * 5
    tail = "PLACEHOLDERNOTAKEY"
    planted = json.dumps(
        {
            "a": "sk" + "-" + tail,
            "b": "ghp" + "_" + tail,
            "c": "hf" + "_" + tail,
            "d": f"{dash5}BEGIN OPENSSH PRIVATE KEY{dash5}",
        }
    )
    fired = [p.pattern for p in _SECRET_SHAPES if p.search(planted)]
    assert len(fired) == len(_SECRET_SHAPES), f"detector missed a planted shape; fired={fired}"
    # and the measured false positive must NOT fire
    assert not any(p.search('{"output_type": "risk-classification"}') for p in _SECRET_SHAPES)


def test_deny_by_default_tool_policy_and_no_secret_values(docs: dict[str, dict]) -> None:
    for slug, doc in docs.items():
        assert doc["tool_policy"]["default"] == "deny", f"{slug}: tool policy is not deny-by-default"
        assert doc["portability"]["export"]["redact_secrets"] is True
        assert doc["failure_policy"]["terminal_state_required"] is True
        assert doc["failure_policy"]["never_silent"] is True
        assert doc["dry_run"]["supported"] is True
        blob = json.dumps(doc)
        for pat in _SECRET_SHAPES:
            hit = pat.search(blob)
            assert hit is None, f"{slug}: credential-shaped literal matching {pat.pattern!r}"


def test_fanout_and_barrier_bounds_are_present_everywhere(docs: dict[str, dict]) -> None:
    """An unbounded fan-out is how a local box freezes, and a barrier with no partial policy
    silently drops every straggler's work."""
    for slug, doc in docs.items():
        for _, st in __import__("wfdsl.semantics", fromlist=["x"]).iter_stages(doc):
            if st.get("kind") == "fanout":
                assert st.get("max_concurrency"), f"{slug}/{st['id']}: unbounded fan-out"
                bar = st.get("barrier")
                assert bar and bar.get("on_partial"), f"{slug}/{st['id']}: barrier without on_partial"
            if st.get("kind") == "loop":
                assert st["convergence"].get("max_iterations"), f"{slug}/{st['id']}: unbounded loop"


def _walk_key(node, key: str) -> list:
    out: list = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                out.append(v)
            out.extend(_walk_key(v, key))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk_key(v, key))
    return out
