"""Tests for the output_schema resolver and the generated substrate.

The point of these tests is NOT that the resolver returns something -- it is that it
returns the RIGHT something and refuses to guess. Half of them are negative: an
unknown id must raise, a foreign report.kind must be rejected, a shim must not be
allowed to carry constraints, and a non-local $ref must not be fetched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import schema_resolver as sr
from receipt_schema_gate import evaluate_gate_a

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "platform" / "schema" / "examples" / "substrate"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def registry():
    return sr.load_registry()


@pytest.fixture(scope="module")
def declared_values():
    wus = json.loads(CATALOG.read_bytes().decode("utf-8"))["work_units"]
    return [w["output_schema"] for w in wus]


@pytest.fixture(scope="module")
def valid_receipt():
    return json.loads(
        (EXAMPLES / "RES-0005.receipt.valid.json").read_bytes().decode("utf-8")
    )


# --------------------------------------------------------------------------- #
# resolution coverage
# --------------------------------------------------------------------------- #


def test_every_catalog_declaration_resolves(declared_values):
    """No unit may be left without a schema. 2007/2007 or the substrate is unfinished."""
    unresolved = []
    for declared in declared_values:
        try:
            res = sr.resolve(declared)
        except sr.SchemaResolutionError as exc:
            unresolved.append((declared, str(exc)))
            continue
        if res.kind != "meta-schema-url" and not res.resolves:
            unresolved.append((declared, "declared path or physical target missing"))
    assert unresolved == [], f"{len(unresolved)} unresolved: {unresolved[:5]}"


def test_declared_paths_exist_on_disk(registry):
    """The literal contract: os.path.isfile(output_schema) must be true."""
    missing = [rel for rel in registry["entries"] if not (REPO / rel).is_file()]
    assert missing == [], f"{len(missing)} declared paths absent: {missing[:5]}"


def test_every_logical_id_compiles(registry):
    for logical in registry["entries"]:
        sr.validator_for(logical)  # raises on failure


def test_every_declared_fragment_compiles(registry):
    n = 0
    for logical, entry in registry["entries"].items():
        for frag in entry.get("fragments", {}):
            sr.validator_for(f"{logical}#/$defs/{frag}")
            n += 1
    assert n == 64, f"expected the 64 catalogued fragments, compiled {n}"


def test_decorated_forms_all_resolve_to_the_same_file():
    """A profile= annotation and a JSON pointer are decoration, not a different file."""
    bare = sr.resolve("command-center/schema/receipt.schema.json")
    annotated = sr.resolve(
        "command-center/schema/receipt.schema.json profile=council-runtime-module "
        "(required: unit_id, artifact_paths[], spec_anchor)"
    )
    pointer = sr.resolve(
        "command-center/schema/receipt.schema.json#/$defs/security_report"
    )
    assert bare.logical_id == annotated.logical_id == pointer.logical_id
    assert annotated.physical_fragment == bare.physical_fragment
    assert pointer.physical_fragment == "#/$defs/security_report"


# --------------------------------------------------------------------------- #
# fail-closed behaviour (the half that matters)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad",
    [
        "command-center/schema/totally-invented-class.schema.json",
        "command-center/schema/",
        "",
        "   ",
        "receipt.schema.json",
        "../../etc/passwd",
    ],
)
def test_unknown_id_raises_and_never_degrades(bad):
    with pytest.raises(sr.UnknownSchemaError):
        sr.validator_for(bad)


def test_unknown_fragment_raises():
    with pytest.raises(sr.UnknownSchemaError):
        sr.validator_for(
            "command-center/schema/receipt.schema.json#/$defs/no_such_fragment"
        )


def test_non_string_declaration_raises():
    for bad in (None, 42, [], {}):
        with pytest.raises(sr.UnknownSchemaError):
            sr.resolve(bad)  # type: ignore[arg-type]


def test_retrieval_refuses_the_network():
    with pytest.raises(sr.SchemaResolutionError):
        sr._retrieve("https://example.com/evil.schema.json")


def test_retrieval_refuses_path_escape():
    with pytest.raises(sr.SchemaResolutionError):
        sr._retrieve(sr.BASE_URI + "../../../../Windows/win.ini")


def test_meta_schema_url_is_offline_and_real():
    v = sr.validator_for("https://json-schema.org/draft/2020-12/schema")
    assert list(v.iter_errors({"type": "object"})) == []
    assert list(v.iter_errors({"type": 7})) != []


# --------------------------------------------------------------------------- #
# discrimination: classes must not be interchangeable
# --------------------------------------------------------------------------- #


def test_class_rejects_a_foreign_report_kind(valid_receipt):
    own = "command-center/schema/research-claim-record.schema.json"
    assert sr.validate_artifact(valid_receipt, own) == []
    foreign = json.loads(json.dumps(valid_receipt))
    foreign["report"]["kind"] = "audit-finding"
    assert sr.validate_artifact(foreign, own) != []


def test_preexisting_alias_fragments_are_pinned(valid_receipt):
    """Regression: the 11 bare generic_report aliases used to accept each other.

    Resolving a fragment straight to receipt.schema.json bypassed the pin; the
    fragment's own physical target must be the profiles file.
    """
    decl = "command-center/schema/receipt.schema.json#/$defs/fault_injection_report"
    res = sr.resolve(decl)
    assert res.physical_path == "platform/schema/artifact-class-profiles.schema.json"
    r = json.loads(json.dumps(valid_receipt))
    r["report"]["kind"] = "fault_injection_report"
    assert sr.validate_artifact(r, decl) == []
    r["report"]["kind"] = "shell_report"
    assert sr.validate_artifact(r, decl) != [], (
        "a shell_report must not pass as fault_injection"
    )


def test_every_pinned_class_rejects_a_foreign_kind(registry, valid_receipt):
    """Exact census, not a spot check: every kind-pinned class must reject a foreign kind."""
    probe = json.loads(json.dumps(valid_receipt))
    probe["report"] = {
        "kind": "__foreign_kind_no_class_uses__",
        "observations": [
            {"name": "n", "measured": 1, "method": "count", "anchor": "x:1"}
        ],
        "control_ids": ["NC-1"],
    }
    accepted = []
    checked = 0
    for logical, entry in registry["entries"].items():
        if entry["kind"] != "artifact-class":
            continue
        checked += 1
        if not sr.validate_artifact(probe, logical):
            accepted.append(logical)
    assert checked > 200, f"census too small to mean anything: {checked}"
    assert accepted == [], (
        f"{len(accepted)} classes accept a foreign kind: {accepted[:5]}"
    )


def test_canonical_receipt_is_deliberately_not_pinned(valid_receipt):
    """The general receipt carries 30 routing profiles and must stay unpinned.

    This is an intended exception, asserted so it cannot drift into an accident.
    """
    res = sr.resolve("command-center/schema/receipt.schema.json")
    assert res.report_kind_pinned is False
    assert res.physical_path == "platform/schema/receipt.schema.json"


# --------------------------------------------------------------------------- #
# the shim layer must stay pure delegation
# --------------------------------------------------------------------------- #


def test_shims_carry_no_constraints(registry):
    """A shim may only $ref. A constraint in a shim is a second control plane."""
    allowed = {
        "$schema",
        "$id",
        "title",
        "$comment",
        "$ref",
        "$defs",
        "x-generated-by",
        "x-artifact-class",
        "x-catalog-reference-count",
        "x-catalog-sample-units",
        "x-catalog-routing-profiles",
        "x-physical-definition",
        "x-alias-of",
    }
    offenders = {}
    for rel, entry in registry["entries"].items():
        if entry["kind"] == "meta-schema-mirror":
            continue
        doc = json.loads((REPO / rel).read_bytes().decode("utf-8"))
        extra = set(doc) - allowed
        if extra:
            offenders[rel] = sorted(extra)
        for frag_node in doc.get("$defs", {}).values():
            if set(frag_node) - {"$ref", "$comment"}:
                offenders.setdefault(rel, []).append(f"$defs node: {sorted(frag_node)}")
    assert offenders == {}, f"shims carrying constraints: {list(offenders.items())[:3]}"


def test_wave1_files_are_untouched():
    """receipt.schema.json and the catalog must be byte-identical to committed HEAD.

    git is the oracle: this unit claims it modified neither, and a claim with no
    probe is not evidence. Compares the working tree against the committed blob via
    'git cat-file -p' (never 'git archive', which re-applies CRLF on this box).
    """
    import subprocess

    for rel in (
        "platform/schema/receipt.schema.json",
        "command-center/WORK-UNIT-CATALOG.json",
    ):
        p = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            capture_output=True,
            cwd=str(REPO),
        )
        if p.returncode != 0:  # not committed here -> the claim is unverifiable, say so
            pytest.skip(f"{rel} is not in HEAD; cannot verify untouched (NOT-CHECKED)")
        committed = p.stdout.replace(b"\r\n", b"\n")
        working = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
        assert committed == working, (
            f"{rel} DIFFERS from HEAD; this unit must not modify it"
        )


# --------------------------------------------------------------------------- #
# end-to-end: the receipts on disk really do pass both layers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("unit", ["CC-0001", "TST-0129", "RES-0005", "WFA-0129"])
def test_example_receipts_pass_layer1_and_layer2(unit):
    wus = json.loads(CATALOG.read_bytes().decode("utf-8"))["work_units"]
    declared = next(w["output_schema"] for w in wus if w["id"] == unit)
    receipt = json.loads(
        (EXAMPLES / f"{unit}.receipt.valid.json").read_bytes().decode("utf-8")
    )
    assert sr.validate_artifact(receipt, declared) == []
    gd = evaluate_gate_a(receipt, repo_root=REPO, verify_filesystem=True).to_dict()
    conds = gd["conditions"]
    assert len(conds) == 12
    blocking = [
        (c["n"], c["outcome"], c["basis"]) for c in conds if c["outcome"] != "SATISFIED"
    ]
    assert blocking == [], f"{unit}: {blocking}"


@pytest.mark.parametrize("unit", ["CC-0001", "TST-0129", "RES-0005", "WFA-0129"])
def test_example_malformed_receipts_are_rejected(unit):
    wus = json.loads(CATALOG.read_bytes().decode("utf-8"))["work_units"]
    declared = next(w["output_schema"] for w in wus if w["id"] == unit)
    bad = json.loads(
        (EXAMPLES / f"{unit}.receipt.malformed.json").read_bytes().decode("utf-8")
    )
    assert sr.validate_artifact(bad, declared) != [], (
        f"{unit} malformed receipt was ACCEPTED"
    )


def test_generator_is_deterministic(tmp_path):
    """Re-running the generator must not change a byte, or the tree is not reproducible."""
    import subprocess
    import sys

    before = {
        rel: (REPO / rel).read_bytes()
        for rel in (
            "platform/schema/artifact-class-profiles.schema.json",
            "platform/schema/ARTIFACT-CLASS-REGISTRY.json",
            "command-center/schema/receipt.schema.json",
            "command-center/schema/audit-finding.schema.json",
        )
    }
    p = subprocess.run(
        [sys.executable, str(REPO / "platform" / "lib" / "_gen_schema_substrate.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert p.returncode == 0, p.stderr
    changed = [rel for rel, b in before.items() if (REPO / rel).read_bytes() != b]
    assert changed == [], f"generator is non-deterministic for: {changed}"
