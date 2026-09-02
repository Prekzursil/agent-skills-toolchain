"""Conformance suite for the package metadata contract (TST-0035).

Written against :mod:`plugin.package_metadata_contract` before the broad
implementation: conforming Python and Node fixtures must PASS the gate, every
rule (name, version, entry_points, engines, files) has a negative that FAILS
it, and the both-states control proves the suite can fail.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin import package_metadata_contract as M  # noqa: E402

REPO = TOOLS.parent


def _suite() -> dict:
    return M.run_conformance_suite()


def test_rules_are_the_five_contract_fields() -> None:
    assert M.RULES == ["name", "version", "entry_points", "engines", "files"]
    assert set(M.RULE_IDS) == set(M.RULES)


def test_conforming_fixtures_pass() -> None:
    suite = _suite()
    conforming = {c["id"]: c for c in suite["cases"] if c["state"] == "conforming"}
    assert set(conforming) == {"python-conforming", "node-conforming"}
    for case in conforming.values():
        assert case["gate_pass"], case["mismatches"]
        assert [r["field"] for r in case["comparison_table"]] == M.RULES
    assert suite["conforming_pass"] is True


def test_every_rule_has_a_failing_negative_per_kind() -> None:
    suite = _suite()
    for field in M.RULES:
        info = suite["per_rule"][field]
        assert info["negatives"] == [f"python-neg-{field}", f"node-neg-{field}"]
        assert info["ok"] is True
    negatives = [c for c in suite["cases"] if c["state"] == "nonconforming"]
    assert len(negatives) == 2 * len(M.RULES)
    for case in negatives:
        assert case["gate_pass"] is False
        assert case["target_field_inconsistent"] is True
        assert case["mismatches"] == [case["target_field"]]


def test_both_states_control() -> None:
    suite = _suite()
    assert suite["both_states"] is True
    assert suite["suite_ok"] is True


def test_mutation_only_moves_the_targeted_field() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pkg = M.make_node_fixture(tmp)
        declared = M.declared_node(pkg)
        built = M.inspect_node_tarball(M.build_node_tarball(pkg, Path(tmp) / "dist"))
    for field in M.RULES:
        result = M.compare_metadata(M.mutate_declared(declared, field), built)
        assert result["mismatches"] == [field]


def test_python_sdist_is_built_from_a_copy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pkg = M.make_python_fixture(tmp)
        before = sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file())
        artifact = M.build_python_sdist(pkg, Path(tmp) / "dist")
        after = sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file())
        built = M.inspect_python_sdist(artifact, ["tst0035fix"])
    assert before == after, "build must not write into the package under test"
    assert built["name"] == "tst0035fix"
    assert built["entry_points"] == {"console_scripts": {"tst0035fix": "tst0035fix:main"}}
    assert built["files"] == ["tst0035fix/__init__.py"]


def test_live_agentspec_declaration_matches_its_sdist() -> None:
    live = M.inspect_live_python(REPO)
    assert live is not None
    assert live["kind"] == "python"
    assert {r["field"] for r in live["comparison_table"]} == set(M.RULES)
    assert live["gate_pass"], live["mismatches"]


def test_parser_identity_names_the_real_stack() -> None:
    ident = M.parser_identity()
    assert ident["name"] == "package-metadata-contract"
    assert ident["version"].endswith("+setuptools.build_meta.build_sdist")
    assert ident["python"] in ident["version"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
