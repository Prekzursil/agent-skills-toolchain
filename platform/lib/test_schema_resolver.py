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


#: The ONLY delta to receipt.schema.json this suite authorizes: the DEFECT D1 vendor-identity
#: layer (platform/lib/vendor_schema_sync.py). Kept as data so the permitted surface is auditable.
_D1_ADDED_DEFS = ("vendor_id", "vendor_id_canonical")
_D1_PREFIX_VENDOR_FIELD = {"type": "string", "maxLength": 64}


def _head_blob(rel: str) -> bytes | None:
    """The committed bytes, or None when the path is not in HEAD.

    'git cat-file -p' on purpose, never 'git archive': archive re-applies EOL conversion and
    returns CRLF on this box, so it would compare against the wrong bytes.
    """
    import subprocess

    p = subprocess.run(
        ["git", "cat-file", "-p", f"HEAD:{rel}"], capture_output=True, cwd=str(REPO)
    )
    if p.returncode != 0:
        return None
    return p.stdout.replace(b"\r\n", b"\n")


def _strip_d1_delta(schema: dict) -> dict:
    """Reverse the authorized D1 additions, so what remains should equal HEAD."""
    out = json.loads(json.dumps(schema))
    for name in _D1_ADDED_DEFS:
        out.get("$defs", {}).pop(name, None)
    reviewer = out.get("$defs", {}).get("reviewer", {}).get("properties", {})
    if "vendor" in reviewer:
        reviewer["vendor"] = dict(_D1_PREFIX_VENDOR_FIELD)
    produced = (
        out.get("$defs", {})
        .get("receipt_core", {})
        .get("properties", {})
        .get("produced_by", {})
        .get("properties", {})
    )
    if "vendor" in produced:
        produced["vendor"] = dict(_D1_PREFIX_VENDOR_FIELD)
    return out


def test_catalog_contract_this_unit_depends_on_is_unchanged():
    """The catalog surface the RESOLVER depends on must be identical to committed HEAD.

    This replaces a byte-equality assertion on the whole 2,007-unit catalog. That invariant is
    not measurable in a shared working tree: it claims "no unit modified this file", but many
    units legitimately extend it, and byte equality cannot tell an authorized field addition from
    a destructive edit. Measured 2026-08-10 - it went red because a sibling unit added
    `tool_policy` blocks, which the resolver does not read at all. (Same defect class as
    rules/common/single-signal-verification.md's pinned-SHA corollary: an invariant that cannot
    survive concurrent authorized work manufactures false alarms.)

    What this unit actually depends on, and therefore what is asserted here:
      * the unit COUNT and the ordered list of unit ids (2,007);
      * the ordered list of `output_schema` values - the resolver's entire input;
      * the separate `items[]` register (103 entries, different schema, different purpose).
    An added or changed field the resolver never reads cannot break it and must not red it; a
    deleted unit, a renamed id or a rewritten `output_schema` still does.
    """
    rel = "command-center/WORK-UNIT-CATALOG.json"
    committed = _head_blob(rel)
    if committed is None:
        pytest.skip(f"{rel} is not in HEAD; cannot verify (NOT-CHECKED)")
    head = json.loads(committed.decode("utf-8"))
    working = json.loads((REPO / rel).read_bytes().decode("utf-8"))
    hw, ww = head["work_units"], working["work_units"]
    assert len(ww) == len(hw) == 2007, f"unit count changed: {len(hw)} -> {len(ww)}"
    assert [u["id"] for u in ww] == [u["id"] for u in hw], "unit ids changed"
    assert [u["output_schema"] for u in ww] == [u["output_schema"] for u in hw], (
        "a declared output_schema changed; the substrate may no longer resolve"
    )
    assert len(working.get("items", [])) == len(head.get("items", [])) == 103, (
        "the items[] register changed size"
    )


def test_catalog_contract_guard_fires_on_a_destructive_edit():
    """BOTH-STATES CONTROL: the narrowed catalog guard must still catch what matters."""
    rel = "command-center/WORK-UNIT-CATALOG.json"
    committed = _head_blob(rel)
    if committed is None:
        pytest.skip(f"{rel} is not in HEAD; cannot verify (NOT-CHECKED)")
    head = json.loads(committed.decode("utf-8"))
    hw = head["work_units"]

    def broken(fn):
        m = json.loads(json.dumps(head))
        fn(m)
        mw = m["work_units"]
        return not (
            len(mw) == len(hw) == 2007
            and [u["id"] for u in mw] == [u["id"] for u in hw]
            and [u["output_schema"] for u in mw] == [u["output_schema"] for u in hw]
            and len(m.get("items", [])) == len(head.get("items", [])) == 103
        )

    assert broken(lambda m: m["work_units"].pop()), "a deleted unit slipped past"
    assert broken(lambda m: m["work_units"][0].__setitem__("id", "ZZZ-9999")), (
        "a renamed unit id slipped past"
    )
    assert broken(
        lambda m: m["work_units"][0].__setitem__("output_schema", "elsewhere.json")
    ), "a rewritten output_schema slipped past"
    assert broken(lambda m: m["items"].pop()), "a dropped items[] entry slipped past"
    # ...and a field the resolver does not read must NOT red it (the whole point).
    assert not broken(
        lambda m: m["work_units"][0].__setitem__("tool_policy", {"default": "deny"})
    ), "an unrelated field addition still reds the guard; it is still too strict"


def test_receipt_schema_differs_from_head_ONLY_by_the_authorized_d1_delta():
    """receipt.schema.json may differ from HEAD ONLY by the DEFECT D1 vendor-identity layer.

    This REPLACES a plain byte-equality assertion ("this unit must not modify it"). That
    invariant was self-falsifying: equality to a pinned blob cannot distinguish an unauthorized
    edit from legitimate authorized work, and it fired on exactly that - the D1 unit was
    instructed to add a vendor enum to this file, so the guard went red while nothing was wrong.
    (rules/common/single-signal-verification.md records the same defect class: a pinned-SHA
    invariant raised three false alarms against legitimate commits.)

    The guard keeps its teeth by NAMING the permitted delta rather than freezing the bytes:
    strip the two generated $defs and restore the two vendor fields to their pre-D1 declaration,
    and the result must still equal HEAD. Any OTHER edit - a new $def, a changed description, a
    relaxed pattern, a removed required field - still fails.

    Scope stated so it is not over-read: the comparison is on PARSED structure, so a pure
    reformat or key reorder would pass. That is deliberate (formatting is not a soundness
    property); every semantic addition, removal or value change anywhere in the document is
    still caught.
    """
    rel = "platform/schema/receipt.schema.json"
    committed = _head_blob(rel)
    if committed is None:
        pytest.skip(f"{rel} is not in HEAD; cannot verify (NOT-CHECKED)")
    head = json.loads(committed.decode("utf-8"))
    working = json.loads((REPO / rel).read_bytes().decode("utf-8"))
    assert _strip_d1_delta(working) == head, (
        f"{rel} differs from HEAD by more than the authorized D1 vendor-identity delta"
    )
    # Assert the POSITIVE too: the D1 layer must actually be PRESENT, or this test would
    # silently pass on a tree where the fix was reverted.
    for name in _D1_ADDED_DEFS:
        assert name in working["$defs"], f"the D1 delta is missing: $defs.{name}"


def test_the_authorized_delta_guard_fires_on_an_unauthorized_edit():
    """BOTH-STATES CONTROL for the guard above: it must go RED on any other change.

    A guard that permits a named delta is worthless if it also permits everything else. Four
    mutations, each applied to the WORKING document, must each break the equality.
    """
    rel = "platform/schema/receipt.schema.json"
    committed = _head_blob(rel)
    if committed is None:
        pytest.skip(f"{rel} is not in HEAD; cannot verify (NOT-CHECKED)")
    head = json.loads(committed.decode("utf-8"))
    working = json.loads((REPO / rel).read_bytes().decode("utf-8"))
    assert _strip_d1_delta(working) == head  # control: the good state is silent

    def mutate(fn):
        m = json.loads(json.dumps(working))
        fn(m)
        return _strip_d1_delta(m) != head

    assert mutate(lambda m: m["$defs"].__setitem__("smuggled", {"type": "string"})), (
        "an extra $def slipped past the guard"
    )
    assert mutate(lambda m: m["$defs"]["sha256"].__setitem__("pattern", ".*")), (
        "a relaxed pattern slipped past the guard"
    )
    assert mutate(lambda m: m["$defs"]["receipt_core"]["required"].pop()), (
        "a removed required field slipped past the guard"
    )
    assert mutate(lambda m: m.__setitem__("description", "changed")), (
        "a changed top-level description slipped past the guard"
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


# --------------------------------------------------------------------------- #
# the generator: reproducible, and NEVER regenerated over the tree under test
# --------------------------------------------------------------------------- #
#
# DEFECT D3 (platform/DEFECT-D3-TEST-MUTATES-TREE.md). The previous version of this
# section ran the generator with cwd=REPO and snapshotted 4 paths against 236 outputs
# (1.7%), so running the suite REGENERATED the real tree: a hand-edit to any of the 232
# unsampled outputs was silently reverted and the test still reported green. Measured:
# a planted edit to command-center/schema/abstraction-leak.schema.json came back
# byte-identical to HEAD after one pytest node, exit 0, "1 passed".
#
# Two things changed. The generator grew an --out-root seam (cwd was never the seam --
# nothing in it reads cwd, REPO was a hardcoded absolute path, so cwd=REPO was
# decorative and cwd=tmp_path would NOT have redirected a single write). And these tests
# generate into tmp_path and DIFF, covering all 236 outputs instead of 4.

GENERATOR = "platform/lib/_gen_schema_substrate.py"


def _run_generator(out_root) -> dict[str, bytes]:
    """Generate the whole substrate into out_root and return {relpath: bytes}."""
    import subprocess
    import sys

    p = subprocess.run(
        [sys.executable, str(REPO / GENERATOR), "--out-root", str(out_root)],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    produced = {}
    for path in sorted(Path(out_root).rglob("*.json")):
        rel = path.relative_to(out_root).as_posix()
        produced[rel] = path.read_bytes()
    assert produced, "generator produced nothing -- detector is broken, not the tree"
    return produced


def _generated_tree_digest() -> dict[str, str]:
    """LF-normalised sha256 of every file the generator owns, read off the real tree."""
    import hashlib

    digest = {}
    for rel in json.loads(
        (REPO / "platform" / "schema" / "ARTIFACT-CLASS-REGISTRY.json")
        .read_bytes()
        .decode("utf-8")
    )["entries"]:
        p = REPO / rel
        if p.is_file():
            digest[rel] = hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
    return digest


def test_generator_output_matches_every_committed_file(tmp_path):
    """ALL generated outputs must equal the tree -- not a 4-path, 1.7% sample.

    Generated into tmp_path, so a hand-edit to any output makes this go RED instead of
    being silently repaired. Compares LF-normalised bytes: a CRLF checkout is a legal
    working-tree state, not a defect, and the generator's own LF contract is asserted
    separately below.
    """
    produced = _run_generator(tmp_path)
    assert len(produced) == 236, f"expected 236 generated files, got {len(produced)}"

    missing, differing = [], []
    for rel, body in produced.items():
        target = REPO / rel
        if not target.is_file():
            missing.append(rel)
        elif target.read_bytes().replace(b"\r\n", b"\n") != body.replace(
            b"\r\n", b"\n"
        ):
            differing.append(rel)
    assert missing == [], (
        f"{len(missing)} generated files absent from the tree: {missing[:5]}"
    )
    assert differing == [], (
        f"{len(differing)} of {len(produced)} committed files differ from generator output "
        f"(hand-edit a generated file and it shows up here): {differing[:5]}"
    )


def test_generator_emits_lf_only(tmp_path):
    """The generator's stated contract: LF only, so its output is platform-independent."""
    produced = _run_generator(tmp_path)
    crlf = sorted(rel for rel, body in produced.items() if b"\r\n" in body)
    assert crlf == [], f"{len(crlf)} generated files carry CRLF: {crlf[:5]}"


def test_generator_is_deterministic(tmp_path):
    """Two independent runs must be byte-identical, or the tree is not reproducible.

    Compares run-to-run, NOT run-to-tree: determinism is a property of the generator and
    must be measurable without the committed tree as the oracle.
    """
    first = _run_generator(tmp_path / "a")
    second = _run_generator(tmp_path / "b")
    diff = sorted(k for k in set(first) | set(second) if first.get(k) != second.get(k))
    assert diff == [], f"generator is non-deterministic for: {diff[:5]}"


def test_running_the_generator_under_test_leaves_the_real_tree_untouched(tmp_path):
    """The D3 regression guard: exercising the generator must not write to the repo.

    This is the assertion whose absence let the suite act as a repair job. It asserts the
    POSITIVE (every one of the N tracked digests is unchanged), never merely "nothing
    looked broken".
    """
    before = _generated_tree_digest()
    assert len(before) >= 234, f"digest too small to mean anything: {len(before)}"
    _run_generator(tmp_path)
    after = _generated_tree_digest()
    changed = sorted(
        k for k in set(before) | set(after) if before.get(k) != after.get(k)
    )
    assert changed == [], f"the generator wrote into the real tree: {changed[:5]}"
    assert after == before and len(after) == len(before)


# --------------------------------------------------------------------------- #
# source-level guard: no test may invoke the generator without --out-root
# --------------------------------------------------------------------------- #


_SPAWNERS = {"run", "call", "check_call", "check_output", "Popen"}


def _generator_spawns(source: str) -> list[tuple[int, bool]]:
    """(lineno, passes_--out-root) for every subprocess call that runs the generator.

    Gated on the CALLEE being a subprocess spawner, not merely on the path string
    appearing somewhere in the call. Two false positives were measured without that gate:
    the nested ``str(REPO / ... / "_gen_schema_substrate.py")`` argument (reported the
    same call twice), and this module's own ``s.endswith("_gen_schema_substrate.py")``
    predicate -- the checker flagging a MENTION of the path inside its own source as a
    USE of it. Both were caught by the both-states control in the caller.
    """
    import ast

    tree = ast.parse(source)
    # Module-level NAME = "str" bindings, so a path hoisted into a constant is still
    # seen. Without this the scan reported 0 spawns against a file that plainly has one
    # (this module hoists the path into GENERATOR) -- a fail-closed control caught it.
    consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        consts[tgt.id] = node.value.value

    def strings(call: ast.Call) -> list[str]:
        found = []
        for n in ast.walk(call):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                found.append(n.value)
            elif isinstance(n, ast.Name) and n.id in consts:
                found.append(consts[n.id])
        return found

    spawns: list[tuple[int, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name not in _SPAWNERS:
            continue
        literals = strings(node)
        if any(s.endswith("_gen_schema_substrate.py") for s in literals):
            spawns.append((node.lineno, "--out-root" in literals))
    return sorted(spawns)


def test_no_platform_test_invokes_the_generator_against_the_real_tree():
    """Every generator invocation in the platform test suite must pass --out-root.

    This is the guard that keeps D3 from coming back by a different route: any future
    test that shells the generator with default args regenerates the repo under test.

    The detector is controlled first (both states) and then required to find a
    KNOWN-PRESENT invocation. A scan that cannot go red, or that scans the wrong files,
    measures nothing -- an all-pass from it would be indistinguishable from a no-op.
    """
    broken = (
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, str(R / 'lib' / '_gen_schema_substrate.py')])\n"
    )
    good = (
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, str(R / 'lib' / '_gen_schema_substrate.py'),"
        " '--out-root', str(tmp)])\n"
    )
    # Same two states again, but with the path hoisted into a module constant, which is
    # how this very module spells it. Both spellings must read the same.
    hoisted_bad = "import subprocess, sys\nG = 'lib/_gen_schema_substrate.py'\nsubprocess.run([sys.executable, str(R / G)])\n"
    hoisted_ok = "import subprocess, sys\nG = 'lib/_gen_schema_substrate.py'\nsubprocess.run([sys.executable, str(R / G), '--out-root', str(tmp)])\n"
    assert _generator_spawns(broken) == [(2, False)], "checker cannot detect the defect"
    assert _generator_spawns(good) == [(2, True)], "checker mis-reads a fixed call"
    assert _generator_spawns(hoisted_bad) == [(3, False)], (
        "hoisted path evades the check"
    )
    assert _generator_spawns(hoisted_ok) == [(3, True)], "hoisted path mis-read"
    # A mere MENTION of the path (not a spawn) must not register at all.
    assert _generator_spawns("x = f.endswith('_gen_schema_substrate.py')\n") == []

    spawns, offenders = 0, {}
    for test_file in sorted((REPO / "platform").rglob("test_*.py")):
        src = test_file.read_bytes().decode("utf-8")
        for lineno, has_flag in _generator_spawns(src):
            spawns += 1
            if not has_flag:
                offenders.setdefault(test_file.relative_to(REPO).as_posix(), []).append(
                    lineno
                )
    assert spawns >= 1, (
        "scan found no generator invocation at all -- wrong files scanned"
    )
    assert offenders == {}, f"tests regenerate over the real tree (D3): {offenders}"
