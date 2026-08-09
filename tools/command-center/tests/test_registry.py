"""Guard the two registries against becoming decoration.

TEST-REGISTRY.json records how many tests protect each invariant, and names the
test functions. Numbers and names nobody checks are exactly the rot this whole
lane exists to stop -- so they are checked here, by counting the real functions
in the real files.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import catalog as cat

REPO = cat.repo_root()
REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"
CLAIMS = REPO / "command-center" / "CLAIM-REGISTRY.json"


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _module_sequences(tree: ast.Module) -> dict[str, int]:
    """Module-level NAME -> length, for list/tuple literals.

    `@pytest.mark.parametrize("p", NEGATIVE_PROMPTS)` is a Name, not a literal.
    Ignoring it under-counts silently -- measured here: 46 counted vs 47
    collected, caught only because the count is asserted against reality."""
    sizes: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(
            node.value, (ast.List, ast.Tuple)
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                sizes[target.id] = len(node.value.elts)
    return sizes


def _parametrize_count(path: Path) -> int:
    """Collected count = test functions expanded by their @pytest.mark.parametrize
    argument lists. Computed statically so this guard needs no pytest plugin."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    sizes = _module_sequences(tree)
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        multiplier = 1
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = decorator.func
            name = getattr(target, "attr", None) or getattr(target, "id", None)
            if name != "parametrize" or len(decorator.args) < 2:
                continue
            values = decorator.args[1]
            if isinstance(values, (ast.List, ast.Tuple)):
                multiplier *= len(values.elts)
            elif isinstance(values, ast.Name) and values.id in sizes:
                multiplier *= sizes[values.id]
        total += multiplier
    return total


def test_every_recorded_suite_exists_and_has_the_recorded_count():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for suite in registry["suites"]:
        path = REPO / suite["path"]
        assert path.is_file(), f"{suite['path']} does not exist"
        actual = _parametrize_count(path)
        assert actual == suite["tests"], (
            f"{suite['path']} has {actual} tests, TEST-REGISTRY.json says {suite['tests']}"
        )


def test_every_named_invariant_test_actually_exists():
    """A registry naming a test that was renamed or deleted asserts nothing."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    known: set[str] = set()
    for suite in registry["suites"]:
        known |= _test_functions(REPO / suite["path"])
    known |= _test_functions(
        REPO / "agent-self" / "harness" / "tests" / "test_modules.py"
    )
    for invariant in registry["invariants"]:
        for name in invariant["tests"]:
            assert name in known, f"{invariant['id']} names a missing test: {name}"


def test_the_counting_guard_can_go_red(tmp_path: Path):
    """Control the control: the static counter must actually track reality."""
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "import pytest\n"
        "NAMES = ('a', 'b')\n"
        "def test_one():\n    pass\n"
        "@pytest.mark.parametrize('x', [1, 2, 3])\n"
        "def test_many(x):\n    pass\n"
        "@pytest.mark.parametrize('n', NAMES)\n"
        "def test_named(n):\n    pass\n"
        "def helper():\n    pass\n",
        encoding="utf-8",
    )
    # 1 + 3 + 2. The NAMES case is the one that was silently miscounted.
    assert _parametrize_count(sample) == 6
    assert _test_functions(sample) == {"test_one", "test_many", "test_named"}


def test_every_claim_declares_both_probes_or_is_typed_not_checked():
    """A CONFIRMED/REFUTED claim with no SOURCE probe is zero signals, not one --
    the gate-mechanising failure recorded in single-signal-verification.md rule 6."""
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    for claim in claims["claims"]:
        assert claim["verdict"] in claims["verdict_vocabulary"], claim["id"]
        if claim["verdict"] in ("CONFIRMED", "REFUTED"):
            assert claim.get("source_probe"), f"{claim['id']} has no source probe"
            assert claim.get("verifier_probe"), f"{claim['id']} has no verifier probe"
            assert claim["source_probe"] != claim["verifier_probe"], (
                f"{claim['id']} re-ran the same probe; that is one signal, not two"
            )
        if claim["verdict"] == "NOT-CHECKED":
            assert claim.get("settling_experiment"), (
                f"{claim['id']} is NOT-CHECKED with no named settling experiment"
            )
