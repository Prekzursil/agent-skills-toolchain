"""Conformance tests for the canonical vendor identity plane - the DEFECT D1 fix.

D1 was a FALSE GREEN in the strongest gate on the platform. ``completion_predicate.py``
enforced cross-vendor review with ``rev_vendor == exec_vendor`` over an unvalidated free-text
field, and ``receipt.schema.json`` typed that field as a bare string with no enum. Measured on
the pre-fix tree by ``platform/architecture/_probe_crossvendor_alias_hole.py``:
**10 of 10 same-vendor alias pairs were accepted as cross-vendor.**

The matrix in ``PAIRS`` below is DATA, not a wall of ``if`` statements, so it can be audited and
extended by editing one table. Every row declares its own expectation:

  ``SAME``       the two strings name ONE vendor -> condition 9 must be UNSATISFIED
  ``CROSS``      genuinely distinct vendors      -> condition 9 must be SATISFIED
  ``REJECTED``   unknown, blank, a hosting plane or a placeholder -> condition 9 must be
                 NOT-CHECKED, which BLOCKS completion. Never SATISFIED: "it differs, therefore
                 it is a different vendor" is precisely the inference D1 records.

THE BOTH-STATES CONTROL is ``test_prefix_gate_leaks_every_alias_pair``. It reimplements the
pre-fix comparison verbatim and asserts it ACCEPTS the same-vendor alias rows this suite now
rejects. Without it, the green rows below would not prove the suite can go red - a probe that is
silent in both states measures nothing.

Run:
    python -m pytest platform/lib/test_vendor_identity.py -q
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vendor_identity as vi  # noqa: E402
import vendor_schema_sync as vss  # noqa: E402
from completion_predicate import (  # noqa: E402
    Outcome,
    PredicateOptions,
    _c9_reviewer,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COUNCILSPEC_SCHEMA = REPO_ROOT / "platform" / "schema" / "councilspec.schema.json"

SAME = "SAME"
CROSS = "CROSS"
REJECTED = "REJECTED"

#: (executor_vendor, reviewer_vendor, expectation, why). 63 rows (29 SAME / 13 CROSS /
#: 21 REJECTED); the task floor is 20. Counts are asserted by
#: test_matrix_covers_every_expectation_and_meets_the_floor rather than trusted from this comment.
PAIRS: tuple[tuple[Any, Any, str, str], ...] = (
    # ---------------------------------------------------------------- SAME VENDOR (must block)
    (
        "anthropic",
        "anthropic",
        SAME,
        "identical spelling - the pre-fix gate caught only this",
    ),
    ("anthropic", "Anthropic", SAME, "case alone is not identity"),
    ("anthropic", "ANTHROPIC", SAME, "upper case"),
    ("anthropic", "anthropic ", SAME, "trailing space"),
    (" anthropic", "anthropic", SAME, "leading space"),
    ("anthropic", "anthropic\t", SAME, "trailing tab"),
    (
        "anthropic",
        "anthropic\x00",
        SAME,
        "embedded control byte must not create a new identity",
    ),
    ("anthropic", "claude", SAME, "vendor vs its product line"),
    ("anthropic", "claude-code", SAME, "vendor vs its CLI"),
    ("anthropic", "Claude_Code", SAME, "case and separator variation together"),
    ("anthropic", "opus", SAME, "model family written into the vendor field"),
    ("anthropic", "sonnet", SAME, "model family"),
    ("anthropic", "anthropic.com", SAME, "domain suffix"),
    ("anthropic", "fable", SAME, "internal codename used in this estate's own docs"),
    ("openai", "OpenAI", SAME, "case"),
    (
        "openai",
        "codex",
        SAME,
        "the load-bearing alias: every cross-vendor unit names Codex",
    ),
    ("codex", "openai", SAME, "same pair, reversed - the relation is symmetric"),
    ("openai", "codex-cli", SAME, "CLI spelling"),
    ("openai", "gpt", SAME, "model family"),
    ("openai", "chatgpt", SAME, "product"),
    ("openai", "open ai", SAME, "internal whitespace"),
    ("google", "Google", SAME, "case"),
    ("google", "gemini", SAME, "vendor vs its model line"),
    ("google", "deepmind", SAME, "Google DeepMind is Google"),
    ("mistral", "mistralai", SAME, "vendor spelling variant"),
    ("xai", "grok", SAME, "vendor vs its model line"),
    ("xai", "x.ai", SAME, "dotted vendor domain must not become a bare 'x'"),
    ("meta", "llama", SAME, "vendor vs its model line"),
    ("human", "owner", SAME, "both name the human reviewer"),
    # ---------------------------------------------------------------- CROSS VENDOR (must pass)
    ("anthropic", "openai", CROSS, "the canonical cross-vendor pair"),
    ("anthropic", "codex", CROSS, "canonical vs alias, still distinct vendors"),
    ("claude", "codex", CROSS, "alias vs alias, still distinct vendors"),
    ("openai", "gemini", CROSS, "distinct"),
    ("anthropic", "google", CROSS, "distinct"),
    ("google", "openai", CROSS, "distinct"),
    ("meta", "mistral", CROSS, "distinct"),
    ("xai", "anthropic", CROSS, "distinct"),
    (
        "anthropic",
        "human",
        CROSS,
        "a human reviewer inherits no model vendor's blind spots",
    ),
    (
        "Anthropic",
        "OpenAI",
        CROSS,
        "case on both sides must not defeat a VALID pair either",
    ),
    (
        "anthropic ",
        " codex",
        CROSS,
        "whitespace on both sides must not defeat a VALID pair",
    ),
    ("opus", "gpt-5", CROSS, "two model families, two vendors"),
    (
        "microsoft",
        "openai",
        CROSS,
        "Phi is Microsoft's own line; Azure is not an alias of it",
    ),
    # ---------------------------------------------------------------- REJECTED (must NOT-CHECK)
    (
        "anthropic",
        "acme-ai",
        REJECTED,
        "unknown vendor is rejected, not assumed distinct",
    ),
    ("acme-ai", "anthropic", REJECTED, "unknown on the executor side"),
    ("xxxxxxxx", "yyyyyyyy", REJECTED, "both unknown"),
    ("anthropic", "openai-ish", REJECTED, "near-miss garbage must not resolve"),
    ("anthropic", "!!!", REJECTED, "punctuation garbage"),
    ("anthropic", "", REJECTED, "empty string"),
    ("", "anthropic", REJECTED, "empty executor"),
    ("anthropic", "   ", REJECTED, "whitespace only"),
    ("anthropic", None, REJECTED, "absent field"),
    ("anthropic", 42, REJECTED, "wrong type"),
    (
        "anthropic",
        "bedrock",
        REJECTED,
        "hosting plane: Bedrock also serves Anthropic models",
    ),
    ("bedrock", "anthropic", REJECTED, "hosting plane on the executor side"),
    ("anthropic", "azure", REJECTED, "hosting plane: Azure serves OpenAI models"),
    (
        "anthropic",
        "vertex",
        REJECTED,
        "hosting plane: Vertex also serves Anthropic models",
    ),
    ("anthropic", "local", REJECTED, "substrate, not a vendor"),
    ("anthropic", "openrouter", REJECTED, "router serves many vendors"),
    ("anthropic", "any", REJECTED, "placeholder wildcard is not an identity"),
    (
        "anthropic",
        "mixed",
        REJECTED,
        "a SET is neither equal to nor distinct from one vendor",
    ),
    ("unassigned", "anthropic", REJECTED, "the shipped receipt example's own pair"),
    ("anthropic", "other", REJECTED, "the councilspec escape hatch is not an identity"),
    ("other", "other", REJECTED, "two 'other' seats may be the same vendor"),
)

_EXPECTED_OUTCOME = {
    SAME: Outcome.UNSATISFIED,
    CROSS: Outcome.SATISFIED,
    REJECTED: Outcome.NOT_CHECKED,
}
_EXPECTED_COMPARISON = {
    SAME: vi.Comparison.SAME_VENDOR,
    CROSS: vi.Comparison.CROSS_VENDOR,
    REJECTED: vi.Comparison.NOT_COMPUTABLE,
}


def _ids() -> list[str]:
    return [f"{exp}:{ex!r}-vs-{rv!r}" for ex, rv, exp, _ in PAIRS]


def _receipt(executor_vendor: Any, reviewer_vendor: Any) -> dict[str, Any]:
    """A receipt whose ONLY variable is the vendor pair. Every other c9 input is valid."""
    produced: dict[str, Any] = {"model": "m", "role": "implementer"}
    reviewer: dict[str, Any] = {
        "reviewer_id": "reviewer-1",
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
    }
    if executor_vendor is not None:
        produced["vendor"] = executor_vendor
    if reviewer_vendor is not None:
        reviewer["vendor"] = reviewer_vendor
    return {"produced_by": produced, "reviewer": reviewer}


def _c9(
    executor_vendor: Any, reviewer_vendor: Any
) -> tuple[Outcome, str, dict[str, Any]]:
    """Condition 9 in isolation, cross-vendor required.

    Calls the private helper on purpose: it isolates the one condition under test from the
    eleven filesystem/schema conditions. ``test_end_to_end_*`` proves the public ``evaluate``
    path is wired to the same code.
    """
    opts = PredicateOptions(repo_root=REPO_ROOT, require_cross_vendor_review=True)
    return _c9_reviewer(_receipt(executor_vendor, reviewer_vendor), opts)


# ====================================================================== the matrix


@pytest.mark.parametrize(
    ("executor", "reviewer", "expectation", "why"), PAIRS, ids=_ids()
)
def test_pair_matrix_predicate_outcome(
    executor: Any, reviewer: Any, expectation: str, why: str
) -> None:
    outcome, reason, detail = _c9(executor, reviewer)
    assert outcome is _EXPECTED_OUTCOME[expectation], (
        f"{executor!r} vs {reviewer!r} ({why}): expected {_EXPECTED_OUTCOME[expectation].value}, "
        f"got {outcome.value} - {reason}"
    )
    assert detail["vendor_comparison"] == _EXPECTED_COMPARISON[expectation].value
    # A REJECTED row must never be reported as a pass by any route.
    if expectation == REJECTED:
        assert outcome is not Outcome.SATISFIED


@pytest.mark.parametrize(
    ("executor", "reviewer", "expectation", "why"), PAIRS, ids=_ids()
)
def test_pair_matrix_resolver_comparison(
    executor: Any, reviewer: Any, expectation: str, why: str
) -> None:
    """The resolver alone must agree with the predicate - one identity plane, not two."""
    comparison, reason, _detail = vi.compare(executor, reviewer)
    assert comparison is _EXPECTED_COMPARISON[expectation], f"{why}: {reason}"


def test_matrix_covers_every_expectation_and_meets_the_floor() -> None:
    """A matrix that lost a whole class would still be 'all green'. Assert the POSITIVE."""
    counts: dict[str, int] = {SAME: 0, CROSS: 0, REJECTED: 0}
    for _ex, _rv, exp, _why in PAIRS:
        counts[exp] += 1
    assert len(PAIRS) >= 20, f"the task floor is 20 pairs; matrix has {len(PAIRS)}"
    assert counts[SAME] >= 10 and counts[CROSS] >= 5 and counts[REJECTED] >= 5, counts
    assert sum(counts.values()) == len(PAIRS)


def test_relation_is_symmetric() -> None:
    """compare(a, b) and compare(b, a) must agree, or the gate depends on argument order."""
    for ex, rv, _exp, why in PAIRS:
        fwd, _r1, _d1 = vi.compare(ex, rv)
        rev, _r2, _d2 = vi.compare(rv, ex)
        assert fwd is rev, f"asymmetric for {ex!r}/{rv!r} ({why}): {fwd} vs {rev}"


# ====================================================================== both-states control


def _prefix_gate(executor_vendor: Any, reviewer_vendor: Any) -> str:
    """The PRE-FIX comparison, verbatim from completion_predicate.py before this fix.

    Reproduced here so the suite can prove it goes red against the broken implementation.
    """
    exec_vendor = str(executor_vendor or "")
    rev_vendor = str(reviewer_vendor or "")
    if not rev_vendor or not exec_vendor:
        return "NOT-CHECKED"
    if rev_vendor == exec_vendor:
        return "UNSATISFIED"
    return "SATISFIED"


def test_prefix_gate_leaks_every_alias_pair() -> None:
    """BOTH-STATES CONTROL: the pre-fix gate must ACCEPT the same-vendor rows we now reject.

    Scope stated so it cannot be over-read: only SAME rows whose two raw strings are not
    byte-equal are leaks. ``anthropic``/``anthropic`` was already caught pre-fix, which is why
    the panel's controls looked valid while the gate was permissive.
    """
    leaked, caught = [], []
    for ex, rv, exp, _why in PAIRS:
        if exp != SAME:
            continue
        if isinstance(ex, str) and isinstance(rv, str) and ex == rv:
            caught.append((ex, rv))
            continue
        (leaked if _prefix_gate(ex, rv) == "SATISFIED" else caught).append((ex, rv))
    assert len(leaked) >= 10, (
        "the control did not reproduce D1: the pre-fix gate should leak every non-identical "
        f"same-vendor alias pair, but only {len(leaked)} leaked"
    )
    assert caught == [("anthropic", "anthropic")], (
        "exactly one SAME row (identical spelling) should have been caught pre-fix; "
        f"got {caught}"
    )
    # And the fixed gate must reject every one of those leaks.
    for ex, rv in leaked:
        assert _c9(ex, rv)[0] is Outcome.UNSATISFIED, f"{ex!r}/{rv!r} still leaks"


def test_prefix_gate_would_also_have_passed_the_rejected_rows() -> None:
    """The other half of D1: an UNKNOWN string used to satisfy the gate merely by differing."""
    promoted = [
        (ex, rv)
        for ex, rv, exp, _w in PAIRS
        if exp == REJECTED and _prefix_gate(ex, rv) == "SATISFIED"
    ]
    assert len(promoted) >= 10, (
        f"control weak: expected the pre-fix gate to promote many REJECTED rows, got {promoted}"
    )
    for ex, rv in promoted:
        assert _c9(ex, rv)[0] is Outcome.NOT_CHECKED


# ====================================================================== end-to-end wiring


def test_end_to_end_alias_pair_blocks_completion(tmp_path: Path) -> None:
    """Proves the public evaluate() path uses the canonical comparison, not just the helper."""
    from test_completion_predicate import Case  # noqa: PLC0415 - fixture reuse

    case = Case(tmp_path)
    assert case.receipt["produced_by"]["vendor"] == "anthropic"
    case.receipt["reviewer"]["vendor"] = "claude"  # an ALIAS of anthropic
    from completion_predicate import evaluate  # noqa: PLC0415

    result = evaluate(case.receipt, case.options(require_cross_vendor_review=True))
    assert result.unsatisfied == [9], result.condition(9).basis
    assert not result.is_complete


def test_end_to_end_unknown_vendor_is_not_checked(tmp_path: Path) -> None:
    from test_completion_predicate import Case  # noqa: PLC0415
    from completion_predicate import evaluate  # noqa: PLC0415

    case = Case(tmp_path)
    case.receipt["reviewer"]["vendor"] = "acme-ai"
    result = evaluate(case.receipt, case.options(require_cross_vendor_review=True))
    assert result.not_checked == [9]
    assert not result.is_complete


def test_cross_vendor_rule_stays_a_unit_class_property(tmp_path: Path) -> None:
    """Regression guard: an alias pair must NOT block a unit that never required cross-vendor."""
    from test_completion_predicate import Case  # noqa: PLC0415
    from completion_predicate import evaluate  # noqa: PLC0415

    case = Case(tmp_path)
    case.receipt["reviewer"]["vendor"] = "claude"
    assert evaluate(
        case.receipt, case.options(require_cross_vendor_review=False)
    ).is_complete


# ====================================================================== resolver unit behaviour


@pytest.mark.parametrize(
    ("raw", "canonical", "resolution"),
    [
        ("anthropic", "anthropic", vi.Resolution.KNOWN),
        ("  CLAUDE\t", "anthropic", vi.Resolution.KNOWN),
        ("anthropic.com", "anthropic", vi.Resolution.KNOWN),
        ("x.ai", "xai", vi.Resolution.KNOWN),
        ("open_ai", "openai", vi.Resolution.KNOWN),
        ("bedrock", "bedrock", vi.Resolution.NOT_AN_IDENTITY),
        ("unassigned", "unassigned", vi.Resolution.NOT_AN_IDENTITY),
        ("acme-ai", None, vi.Resolution.UNKNOWN),
        ("", None, vi.Resolution.EMPTY),
        ("   ", None, vi.Resolution.EMPTY),
        (None, None, vi.Resolution.EMPTY),
        (42, None, vi.Resolution.MALFORMED),
        ({"a": 1}, None, vi.Resolution.MALFORMED),
    ],
)
def test_resolve(raw: Any, canonical: str | None, resolution: vi.Resolution) -> None:
    ident = vi.resolve(raw)
    assert ident.resolution is resolution
    assert ident.canonical_id == canonical
    assert ident.establishes_distinctness is (resolution is vi.Resolution.KNOWN)


def test_only_known_identities_establish_distinctness() -> None:
    """A hosting plane or placeholder must never be usable as half of a cross-vendor pair."""
    reg = vi.load_registry()
    for cid, entry in reg.entries.items():
        capable = bool(entry["establishes_distinctness"])
        expected = entry["kind"] in ("model_vendor", "human")
        assert capable is expected, f"{cid}: kind={entry['kind']} capable={capable}"
        if not capable:
            comparison, _reason, _d = vi.compare("anthropic", cid)
            assert comparison is vi.Comparison.NOT_COMPUTABLE, cid


def test_hosting_planes_are_not_folded_into_any_vendor() -> None:
    """Over-folding is the OTHER direction of wrongness: it would block a valid completion."""
    reg = vi.load_registry()
    for token in ("azure", "bedrock", "vertex", "openrouter", "local", "ollama", "aws"):
        ident = vi.resolve(token, reg)
        assert ident.kind is vi.IdentityKind.HOSTING_SUBSTRATE, token
        assert ident.establishes_distinctness is False, token


def test_resolver_rejects_an_ambiguous_alias_table(tmp_path: Path) -> None:
    """A table where one alias maps to two vendors cannot ground a verdict - it must raise."""
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "identities": [
                    {
                        "id": "a",
                        "kind": "model_vendor",
                        "establishes_distinctness": True,
                        "aliases": ["shared"],
                    },
                    {
                        "id": "b",
                        "kind": "model_vendor",
                        "establishes_distinctness": True,
                        "aliases": ["shared"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="maps to both"):
        vi.load_registry(bad)


def test_resolver_rejects_an_empty_registry(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"identities": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no identities"):
        vi.load_registry(empty)


def test_resolver_rejects_a_duplicate_canonical_id(tmp_path: Path) -> None:
    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps(
            {
                "identities": [
                    {
                        "id": "a",
                        "kind": "model_vendor",
                        "establishes_distinctness": True,
                    },
                    {
                        "id": "a",
                        "kind": "model_vendor",
                        "establishes_distinctness": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate canonical"):
        vi.load_registry(dup)


def test_resolver_rejects_a_blank_alias(tmp_path: Path) -> None:
    blank = tmp_path / "blank.json"
    blank.write_text(
        json.dumps(
            {
                "identities": [
                    {
                        "id": "a",
                        "kind": "model_vendor",
                        "establishes_distinctness": True,
                        "aliases": ["  "],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty alias"):
        vi.load_registry(blank)


# ====================================================================== schema layer (layer 2)


def test_receipt_schema_matches_the_registry() -> None:
    """The generated enum must equal the registry. Two hand-kept copies would drift."""
    assert vss.check() == []


def test_every_enum_member_matches_the_pattern() -> None:
    """An enum member that fails the sibling pattern is an unsatisfiable branch."""
    schema = json.loads(vss.RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    for name in ("vendor_id", "vendor_id_canonical"):
        block = schema["$defs"][name]
        rx = re.compile(block["pattern"])
        for member in block["enum"]:
            assert rx.match(member), (
                f"{name}: {member!r} cannot satisfy {block['pattern']}"
            )
            assert len(member) <= block["maxLength"], member


def test_both_receipt_vendor_fields_are_constrained() -> None:
    """The exact D1 site: a bare {'type':'string','maxLength':64} here is the defect."""
    schema = json.loads(vss.RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    reviewer = schema["$defs"]["reviewer"]["properties"]["vendor"]
    produced = schema["$defs"]["receipt_core"]["properties"]["produced_by"][
        "properties"
    ]["vendor"]
    assert reviewer == {"$ref": "#/$defs/vendor_id"}
    assert produced == {"$ref": "#/$defs/vendor_id"}


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("anthropic", True),
        ("openai", True),
        ("unassigned", True),
        ("human", True),
        ("claude", True),
        ("codex", True),
        ("acme-ai", False),
        ("Anthropic", False),
        ("anthropic ", False),
        ("", False),
        ("!!!", False),
        ("anthropic\x00", False),
        (42, False),
    ],
)
def test_schema_rejects_unrecognized_vendor_strings(value: Any, valid: bool) -> None:
    """LAYER 2 of the fix: an unknown vendor string cannot even be a structurally valid receipt."""
    import receipt_schema_gate as rg  # noqa: PLC0415

    errors = rg.validate_receipt(value, fragment="#/$defs/vendor_id")
    assert (errors == []) is valid, f"{value!r}: {errors}"


def test_prefix_schema_would_have_accepted_the_garbage() -> None:
    """BOTH-STATES CONTROL for layer 2: the pre-fix declaration accepted every string."""
    from jsonschema import Draft202012Validator  # noqa: PLC0415

    prefix = Draft202012Validator({"type": "string", "maxLength": 64})
    for garbage in ("acme-ai", "Anthropic", "anthropic ", "!!!", "anthropic\x00"):
        assert list(prefix.iter_errors(garbage)) == [], (
            f"control invalid: the pre-fix schema should have accepted {garbage!r}"
        )


def test_councilspec_vendor_enum_is_a_subset_of_the_registry() -> None:
    """councilspec.schema.json:442-444 already had a 9-value enum. One identity plane, not two."""
    cs = json.loads(COUNCILSPEC_SCHEMA.read_text(encoding="utf-8"))
    found: list[list[str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if (
                    key == "vendor"
                    and isinstance(val, dict)
                    and isinstance(val.get("enum"), list)
                ):
                    found.append(val["enum"])
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(cs)
    assert found, (
        "the councilspec vendor enum disappeared; this test's premise is stale"
    )
    recognized = set(vi.recognized_tokens())
    for enum in found:
        missing = sorted(set(enum) - recognized)
        assert not missing, (
            f"councilspec vendor values absent from the vendor registry: {missing}. "
            "Register them in platform/registry/VENDOR-REGISTRY.json so the council plane and "
            "the receipt plane share ONE identity plane."
        )


def test_sync_check_detects_drift(tmp_path: Path) -> None:
    """BOTH-STATES CONTROL for the parity gate: it must FIRE on a mutated schema."""
    live = json.loads(vss.RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    mutated = tmp_path / "receipt.schema.json"

    # mutation 1: revert the reviewer field to the pre-fix bare string
    broken = json.loads(json.dumps(live))
    broken["$defs"]["reviewer"]["properties"]["vendor"] = {
        "type": "string",
        "maxLength": 64,
    }
    mutated.write_text(json.dumps(broken), encoding="utf-8")
    problems = vss.check(mutated)
    assert any("DEFECT D1" in p for p in problems), problems

    # mutation 2: silently add a vendor to the enum that the registry does not know
    broken2 = json.loads(json.dumps(live))
    broken2["$defs"]["vendor_id"]["enum"].append("acme-ai")
    mutated.write_text(json.dumps(broken2), encoding="utf-8")
    assert vss.check(mutated) != []

    # and the UNMUTATED file must be clean, or the detector fires in both states
    clean = tmp_path / "clean.schema.json"
    clean.write_text(json.dumps(live), encoding="utf-8")
    assert vss.check(clean) == []


def test_emit_is_parseable_and_matches_check() -> None:
    blocks = json.loads(vss.emit())
    assert set(blocks) == {"vendor_id", "vendor_id_canonical"}
    live = json.loads(vss.RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    for name, block in blocks.items():
        assert live["$defs"][name] == block


def test_registry_documents_the_exclusion_rule() -> None:
    """The hosting-plane exclusion is the finding most likely to be undone by a future edit."""
    reg = json.loads(vi.REGISTRY_PATH.read_text(encoding="utf-8"))
    excluded = set(reg["alias_exclusions"]["excluded_from_every_vendor_alias_set"])
    assert {"azure", "bedrock", "vertex"} <= excluded
    for entry in reg["identities"]:
        if entry["kind"] in ("model_vendor", "human"):
            overlap = excluded & {a.lower() for a in entry.get("aliases", [])}
            assert not overlap, f"{entry['id']} claims a hosting-plane alias: {overlap}"
