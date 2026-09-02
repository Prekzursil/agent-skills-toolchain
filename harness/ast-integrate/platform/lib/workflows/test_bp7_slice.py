"""Slice-wide tests for unit blueprints/bp-7 - cards 73-84 of the blueprint library.

These are the properties no single blueprint can assert about itself: id disjointness from the
2,007-unit catalog, output-path uniqueness across the slice, category span, the flagship floor,
schema-reference resolvability, builder/artifact byte-identity, and MATERIAL DISTINCTNESS.

Distinctness is computed, not asserted. Two mechanical fingerprints are compared pairwise across
all 66 pairs, and :func:`test_control_the_distinctness_detector_fires_on_a_planted_duplicate`
proves the comparison can actually fail - a distinctness check that has never gone red is
indistinguishable from a no-op.
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp7_checks as C  # noqa: E402
import bp7_schema_ref_check as R  # noqa: E402
import bp7_testkit as K  # noqa: E402
from bp7_build import (  # noqa: E402 - same sys.path plumbing as the three imports above
    EXPECTED_IDS,
    assert_dry_run_forbids_every_mutating_tool,
    assert_tools_permitted,
    build_all,
)  # noqa: E402
from bp7_common import ALL_CATEGORIES, UNIT_PREFIXES  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG = REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"

#: spec 10898: at least 40 of the 96 built-ins are flagship. Pro-rata over a 12-card slice that
#: is ceil(40/96 * 12) = 5. This slice ships 7.
FLAGSHIP_FLOOR = 5


def docs() -> list[dict[str, Any]]:
    return [K.load(i) for i in EXPECTED_IDS]


# ------------------------------------------------------------------ delivery and contract


def test_all_twelve_documents_are_on_disk_with_the_expected_ids() -> None:
    assert len(EXPECTED_IDS) == 12
    assert [d["id"] for d in docs()] == list(EXPECTED_IDS)


def test_every_document_is_schema_valid_with_zero_semantic_findings() -> None:
    """A blueprint that does not validate is not delivered. Advisories count too: DSL-SEM-014 is
    advisory and it is the rule that caught the council expression the DSL tokenizer rejects."""
    validator = schemas.workflow_validator()
    problems: dict[str, Any] = {}
    for d in docs():
        errs = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'} [{e.validator}]"
            for e in validator.iter_errors(d)
        ]
        sem = [r.to_json() for r in semantics.check_workflow(d) if r.violations]
        if errs or sem:
            problems[d["id"]] = {"schema": errs[:4], "semantic": sem[:3]}
    assert problems == {}, problems


def test_every_blueprint_carries_the_mandated_sections() -> None:
    """The brief requires typed parameters, stages, roles, gates, tools, explicit stopping rules
    and a failure policy on every blueprint - plus the DSL's own resumability contract."""
    required = (
        "params",
        "roles",
        "gates",
        "tool_policy",
        "model_routing",
        "stages",
        "stopping_rules",
        "retry_policy",
        "failure_policy",
        "resume",
        "replay",
        "cache",
        "dry_run",
        "estimate",
        "portability",
        "lineage",
        "outputs",
    )
    missing = {d["id"]: [k for k in required if k not in d] for d in docs()}
    assert {k: v for k, v in missing.items() if v} == {}, missing


def test_every_blueprint_has_at_least_one_typed_param_role_gate_and_stopping_rule() -> (
    None
):
    thin = {}
    for d in docs():
        counts = {
            "params": len(d["params"]),
            "roles": len(d["roles"]),
            "gates": len(d["gates"]),
            "stages": len(d["stages"]),
            "stopping_rules": len(d["stopping_rules"]),
        }
        if min(counts.values()) < 1 or counts["stopping_rules"] < 2:
            thin[d["id"]] = counts
    assert thin == {}, thin


def test_the_tool_policy_allowlist_is_authored_not_derived() -> None:
    """Every tool a role, stage or work unit requests must appear in the hand-authored allowlist.
    A policy computed from its own requests could never deny anything."""
    problems = [p for d in docs() for p in assert_tools_permitted(d)]
    problems += [
        p for d in docs() for p in assert_dry_run_forbids_every_mutating_tool(d)
    ]
    assert problems == [], problems


# --------------------------------------------------------------------- id / path hygiene


def test_inline_unit_ids_are_unique_and_well_formed_across_the_slice() -> None:
    seen: dict[str, str] = {}
    bad: list[str] = []
    for d in docs():
        for u in C.work_units(d):
            uid = u["id"]
            m = re.fullmatch(r"([A-Z]{2,4})-(\d{2})(\d{2})", uid)
            if not m:
                bad.append(f"{uid} is not <PREFIX>-<card><ordinal>")
                continue
            prefix, card, _ordinal = m.group(1), int(m.group(2)), m.group(3)
            if prefix not in UNIT_PREFIXES:
                bad.append(f"{uid} uses prefix {prefix!r} outside {UNIT_PREFIXES}")
            if not 73 <= card <= 84:
                bad.append(
                    f"{uid} encodes card {card}, outside this unit's range 73-84"
                )
            if uid in seen:
                bad.append(f"{uid} appears in both {seen[uid]} and {d['id']}")
            seen[uid] = d["id"]
    assert bad == [], bad
    assert len(seen) == 71, (
        f"expected 71 inline units across the slice, found {len(seen)}"
    )


def test_no_inline_unit_id_collides_with_the_real_catalog() -> None:
    """Measured against the live catalog rather than trusting the 13 documented prefixes: a
    collision would mean two different definitions for one id."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = {u["id"] for u in catalog["work_units"]}
    assert len(catalog_ids) == 2007, f"catalog shape changed: {len(catalog_ids)} units"
    mine = {u["id"] for d in docs() for u in C.work_units(d)}
    assert mine & catalog_ids == set(), sorted(mine & catalog_ids)


def test_no_two_units_in_the_slice_claim_the_same_output_path() -> None:
    """SEM-004's property applied to this slice: two units writing one path race and lose work."""
    owners: dict[str, list[str]] = {}
    for d in docs():
        for u in C.work_units(d):
            owners.setdefault(u["output_path"], []).append(f"{d['id']}:{u['id']}")
    clashes = {p: o for p, o in owners.items() if len(o) > 1}
    assert clashes == {}, clashes


def test_every_completion_sentinel_names_its_own_unit_id() -> None:
    """SEM-002's property: a sentinel naming a different unit is a terminal state for someone else."""
    bad = []
    for d in docs():
        for u in C.work_units(d):
            if not u["completion_sentinel"].startswith(f"SUCCESS:{u['id']} "):
                bad.append(f"{d['id']}:{u['id']} -> {u['completion_sentinel'][:70]}")
    assert bad == [], bad


def test_every_schema_reference_resolves_and_compiles() -> None:
    """192 references across 12 documents. The DSL validator does not open these files, so a
    dangling schema_ref would otherwise ship as 'schema-valid'."""
    report = R.check_all([K.WORKFLOW_DIR / f"{i}.json" for i in EXPECTED_IDS])
    assert report["failures"] == [], report["failures"][:6]
    assert report["resolved"] == report["references"] > 150, report


def test_the_reference_resolver_fires_on_known_broken_input() -> None:
    """Control for the check above: a resolver silent in both states measures nothing."""
    report = R.self_check(_HERE / "_tmp_refcheck")
    assert report["ok"], [r for r in report["rows"] if not r["ok"]]
    assert report["passed"] == report["cases"] >= 8


# ------------------------------------------------------------------- category and span


def test_every_category_is_one_of_the_six_spec_spans() -> None:
    unknown = {
        d["id"]: [c for c in d["categories"] if c not in ALL_CATEGORIES] for d in docs()
    }
    assert {k: v for k, v in unknown.items() if v} == {}, unknown


def test_the_slice_spans_the_three_axes_it_claims_and_says_which() -> None:
    """This slice is data/knowledge + product/design + meta. It does NOT claim to cover research,
    security or engineering as a PRIMARY axis, and the count is asserted so the claim stays honest."""
    primaries = [d["x_extensions"]["bp7"]["primary_category"] for d in docs()]
    counts = {c: primaries.count(c) for c in set(primaries)}
    assert counts == {
        "data-science-knowledge-and-creative": 6,
        "product-design-and-strategy": 5,
        "collective-intelligence-and-meta": 1,
    }, counts
    # engineering-and-reliability appears as a SECONDARY axis on the reliability-bearing cards
    secondary = {
        d["id"] for d in docs() if "engineering-and-reliability" in d["categories"]
    }
    assert secondary == {
        "measurement-instrument-validation",
        "hermetic-eval-registry-run",
        "per-surface-usability-source-audit",
        "pre-pr-knowledge-capture",
    }, secondary


def test_the_slice_uses_more_than_one_workflow_kind() -> None:
    kinds = {d["id"]: d["kind"] for d in docs()}
    assert set(kinds.values()) == {"workflow", "subworkflow", "meta-workflow"}, kinds


# ------------------------------------------------------------------------- flagship floor


def test_the_flagship_count_clears_the_pro_rata_floor() -> None:
    flagships = [d["id"] for d in docs() if d["flagship"]]
    assert len(flagships) >= FLAGSHIP_FLOOR, flagships
    assert len(flagships) == 7, flagships


def test_every_flagship_declares_a_test_file_that_exists() -> None:
    missing = []
    for d in docs():
        ext = d["x_extensions"]["bp7"]
        if d["flagship"]:
            rel = ext.get("flagship_test")
            assert rel, f"{d['id']} is flagship but names no test file"
            if not (REPO_ROOT / rel).is_file():
                missing.append(rel)
        else:
            assert ext.get("flagship_test") is None, d["id"]
            assert ext.get("flagship_rationale"), (
                f"{d['id']} is not flagship and gives no reason - an unexplained omission reads as an oversight"
            )
    assert missing == [], missing


def test_every_blueprint_carries_a_worked_example_and_an_inline_unverified_with_a_probe() -> (
    None
):
    bad = []
    for d in docs():
        ext = d["x_extensions"]["bp7"]
        ex = ext.get("worked_example") or {}
        if not ex.get("params") or len(ex.get("expected_trace") or []) < 4:
            bad.append(f"{d['id']}: worked example is too thin to be a walkthrough")
        if not ex.get("expected_terminal_state", "").startswith(
            ("SUCCESS:", "FAILED:")
        ):
            bad.append(f"{d['id']}: worked example has no terminal state")
        unv = ext.get("unverified") or ""
        if "UNVERIFIED" not in unv or "settling experiment" not in unv.lower():
            bad.append(
                f"{d['id']}: UNVERIFIED tag missing or names no settling experiment"
            )
    assert bad == [], bad


# --------------------------------------------------------------- MATERIAL DISTINCTNESS


def mechanism_signature(doc: dict[str, Any]) -> set[str]:
    return set(doc["x_extensions"]["bp7"]["mechanism_signature"])


def structural_fingerprint(doc: dict[str, Any]) -> tuple[Any, ...]:
    """Stage-kind multiset plus the set of gate expressions - what the workflow DOES, not what it
    is called. Two renamed copies would collide here even with different prose."""
    kinds = tuple(sorted(s["kind"] for s in C.all_stages(doc)))
    gate_exprs = tuple(
        sorted(
            str((g or {}).get("expression") or "")
            for g in (doc.get("gates") or {}).values()
        )
    )
    return (kinds, gate_exprs)


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


def pairwise_overlaps(documents: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    out = []
    for x, y in itertools.combinations(documents, 2):
        out.append(
            (x["id"], y["id"], jaccard(mechanism_signature(x), mechanism_signature(y)))
        )
    return out


def test_no_two_blueprints_share_a_mechanism_signature() -> None:
    seen: dict[frozenset[str], str] = {}
    for d in docs():
        key = frozenset(mechanism_signature(d))
        assert len(key) >= 4, f"{d['id']} declares only {len(key)} mechanism tokens"
        assert key not in seen, (
            f"{d['id']} has the same mechanism signature as {seen[key]}"
        )
        seen[key] = d["id"]


def test_pairwise_mechanism_overlap_stays_below_a_third() -> None:
    """A catalog of near-duplicates is worse than a short one because it manufactures false
    coverage, so the bar is mechanical: no pair may share more than a third of its mechanism
    tokens. All 66 pairs are measured, and the worst is reported on failure.

    HONEST LIMIT of this particular metric: the token strings are AUTHORED, so an author who
    names every mechanism differently gets a low overlap for free. Measured here: 66/66 pairs at
    0.000, which is therefore weaker evidence than it looks. The load-bearing distinctness check
    is :func:`test_no_two_blueprints_share_a_structural_fingerprint`, which compares what the
    workflows DO (stage-kind multiset plus gate expressions) and cannot be satisfied by renaming.
    Both are kept because the planted-clone control below fires on both.
    """
    overlaps = pairwise_overlaps(docs())
    assert len(overlaps) == 66, len(overlaps)
    worst = sorted(overlaps, key=lambda t: -t[2])[:5]
    assert worst[0][2] < 0.34, f"near-duplicate pair(s): {worst}"


def test_no_two_blueprints_share_a_structural_fingerprint() -> None:
    seen: dict[tuple[Any, ...], str] = {}
    for d in docs():
        fp = structural_fingerprint(d)
        assert fp not in seen, f"{d['id']} is structurally identical to {seen[fp]}"
        seen[fp] = d["id"]


def test_every_blueprint_states_what_it_is_not_a_duplicate_of() -> None:
    bad = []
    for d in docs():
        distinct = d["x_extensions"]["bp7"].get("distinct_from") or {}
        if len(distinct) < 2:
            bad.append(
                f"{d['id']} distinguishes itself from only {len(distinct)} neighbours"
            )
        for other, reason in distinct.items():
            if len(reason) < 25:
                bad.append(
                    f"{d['id']} vs {other}: the distinction is too thin to check"
                )
    assert bad == [], bad


def test_control_the_distinctness_detector_fires_on_a_planted_duplicate() -> None:
    """Both-states control for the three distinctness checks above. A planted pair - one document
    copied with a new id, which is exactly the 'renamed copy' the spec forbids - must trip the
    signature check, the overlap check AND the structural fingerprint. If it trips none of them,
    the distinctness bar in this file is decorative."""
    original = K.load("bounded-corpus-distillation")
    clone = json.loads(json.dumps(original))
    clone["id"] = "bounded-corpus-distillation-renamed"
    clone["name"] = "A renamed copy that changes no mechanism"
    planted = [original, clone]

    # 1. identical mechanism signatures
    assert mechanism_signature(original) == mechanism_signature(clone)
    # 2. the overlap check sees a Jaccard of 1.0, far above the 0.34 bar
    overlaps = pairwise_overlaps(planted)
    assert overlaps and overlaps[0][2] == 1.0, overlaps
    assert overlaps[0][2] >= 0.34, (
        "the overlap threshold would not have caught a verbatim clone"
    )
    # 3. the structural fingerprint collides
    assert structural_fingerprint(original) == structural_fingerprint(clone)

    # and a genuinely different blueprint does NOT collide with it - so the detector discriminates
    other = K.load("ssot-documentation-reconcile")
    assert mechanism_signature(other) != mechanism_signature(original)
    assert structural_fingerprint(other) != structural_fingerprint(original)
    assert jaccard(mechanism_signature(other), mechanism_signature(original)) < 0.34


# ------------------------------------------------------------------------ artifact drift


def test_the_committed_json_is_byte_identical_to_the_builder_output() -> None:
    """The JSON files are the deliverable and the builder is their source. If they drift, a test
    that passes against the builder is measuring bytes nobody ships."""
    drift = []
    for d in build_all():
        path = K.WORKFLOW_DIR / f"{d['id']}.json"
        want = json.dumps(d, indent=2, ensure_ascii=True) + "\n"
        if not path.is_file():
            drift.append(f"{path.name}: MISSING")
        elif path.read_text(encoding="utf-8") != want:
            drift.append(f"{path.name}: DIFFERS")
    assert drift == [], drift


def test_the_status_artifacts_counts_match_the_measured_reality() -> None:
    """The status artifact is a CLAIM until something re-measures it. An earlier draft of it stated
    21 mutation controls; the measured value is 34, because 21 was an estimate nobody counted. This
    test is the drift check that keeps every number in its counts block honest - the same
    discipline blueprint 84 prescribes for a fact stated in more than one place.
    """
    status = json.loads(
        (K.WORKFLOW_DIR / "BLUEPRINTS-73-84-STATUS.json").read_text(encoding="utf-8")
    )
    counts = status["counts"]
    documents = docs()

    mine = sorted(_HERE.glob("test_*.py"))
    my_files = [
        p
        for p in mine
        if p.name == "test_bp7_slice.py"
        or p.stem.replace("test_", "")
        in {
            "bounded_corpus_distillation",
            "measurement_instrument_validation",
            "hermetic_eval_registry_run",
            "design_studio_eight_gate_loop",
            "two_track_ui_audit",
            "design_first_ui_intake",
            "ssot_documentation_reconcile",
        }
    ]
    test_fns = controls = 0
    for path in my_files:
        text = path.read_text(encoding="utf-8")
        test_fns += len(re.findall(r"^def test_", text, re.M))
        controls += len(re.findall(r"^def test_control_", text, re.M))

    measured = {
        "blueprints": len(documents),
        "flagship": sum(1 for d in documents if d["flagship"]),
        "stages_total": sum(len(d["stages"]) for d in documents),
        "stages_total_including_fanout_loop_and_repair_bodies": sum(
            len(C.all_stages(d)) for d in documents
        ),
        "inline_work_units": sum(len(C.work_units(d)) for d in documents),
        "my_tests": test_fns,
        "mutation_controls": controls,
        "distinctness_pairs_measured": len(pairwise_overlaps(documents)),
    }
    mismatches = {
        k: {"claimed": counts.get(k), "measured": v}
        for k, v in measured.items()
        if counts.get(k) != v
    }
    assert mismatches == {}, mismatches
    assert len(my_files) == 8, [p.name for p in my_files]


def test_no_secret_value_travels_in_any_document() -> None:
    """secret_ref params carry a NAME. If a document ever carried a value, the export bundle and
    the replay journal would carry it too."""
    for d in docs():
        for name, spec in d["params"].items():
            if spec.get("type") == "secret_ref" or spec.get("secret"):
                assert spec.get("secret") is True, f"{d['id']}:{name}"
                assert "default" not in spec, (
                    f"{d['id']}:{name} carries a literal default"
                )
                assert d["portability"]["export"]["redact_secrets"] is True, d["id"]
        blob = json.dumps(d)
        for marker in ("sk-", "ghp_", "hf_", "-----BEGIN"):
            assert marker not in blob, (
                f"{d['id']} contains a credential-shaped literal {marker!r}"
            )
