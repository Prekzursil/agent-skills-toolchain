"""The mandated assertion-density lint (anti-coverage-theatre layer 2).

An assertion-free test function executes lines and asserts nothing: it lifts coverage without
protecting behaviour. Discharging this requirement with prose was a MEASURED overclaim — a
whole-file mutation guard cannot see one empty function sitting beside strong siblings, because
the file still exits non-zero on every mutant. So it is a real AST check with both-states
fixtures, run over this package's own test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentspec.testlint import scan_test_source, scan_tests

TESTS_ROOT = Path(__file__).resolve().parent


def test_this_suite_has_no_assertion_free_test_function() -> None:
    """The load-bearing assertion, trustworthy only because of the controls below."""
    findings = scan_tests(TESTS_ROOT)
    assert findings == (), [f"{f.path}:{f.line} {f.detail}" for f in findings]


def test_the_scan_actually_visited_the_suite() -> None:
    """Guard against a vacuous green: an empty walk also reports zero findings."""
    from agentspec.testlint import test_files

    visited = test_files(TESTS_ROOT)
    assert len(visited) >= 8
    assert any(p.name == "test_oracle.py" for p in visited)


def test_the_lint_fires_on_an_assertion_free_test() -> None:
    source = "def test_nothing():\n    x = 1 + 1\n"
    findings = scan_test_source(source, "t.py")
    assert [(f.code, f.line, f.detail) for f in findings] == [
        ("no-assertion", 1, "test_nothing has no assertion")
    ]


def test_the_lint_is_silent_when_an_assert_is_present() -> None:
    assert scan_test_source("def test_x():\n    assert 1 == 1\n", "t.py") == ()


def test_an_assertion_free_function_BESIDE_a_strong_sibling_is_still_caught() -> None:
    """The exact case the whole-file mutation guard cannot see."""
    source = (
        "def test_strong():\n"
        "    assert 2 == 2\n"
        "def test_empty():\n"
        "    helper()\n"
        "def test_also_strong():\n"
        "    assert 3 == 3\n"
    )
    assert [f.detail for f in scan_test_source(source, "t.py")] == [
        "test_empty has no assertion"
    ]


@pytest.mark.parametrize(
    "body",
    [
        "    with pytest.raises(ValueError):\n        f()\n",
        "    with pytest.warns(UserWarning):\n        f()\n",
        "    assert_frame_equal(a, b)\n",
        "    obj.assertEqual(1, 1)\n",
    ],
)
def test_non_assert_assertion_forms_count(body: str) -> None:
    assert scan_test_source(f"def test_x():\n{body}", "t.py") == ()


def test_a_plain_call_does_NOT_count_as_an_assertion() -> None:
    """Detector control against over-acceptance."""
    assert scan_test_source("def test_x():\n    verify(1)\n", "t.py") != ()


def test_a_class_based_test_method_is_checked() -> None:
    source = "class TestThing:\n    def test_empty(self):\n        pass\n"
    assert [f.line for f in scan_test_source(source, "t.py")] == [2]


def test_an_async_test_is_checked() -> None:
    assert scan_test_source("async def test_x():\n    await f()\n", "t.py") != ()


def test_a_non_test_helper_without_an_assert_is_ignored() -> None:
    assert scan_test_source("def _helper():\n    return 1\n", "t.py") == ()


def test_a_nested_helper_inside_a_test_does_not_launder_the_assertion() -> None:
    """The assert must be reachable from the test body, not merely defined inside it.

    A nested `def` that contains the only assert is never called by the checker's reckoning,
    so the enclosing test still counts as assertion-free.
    """
    source = "def test_x():\n    def inner():\n        assert False\n    inner\n"
    assert scan_test_source(source, "t.py") != ()


def test_a_with_block_that_is_not_a_raises_helper_does_not_count() -> None:
    """`with open(...)` is plumbing, not an assertion."""
    source = "def test_x():\n    with open('f') as handle:\n        handle.read()\n"
    assert [f.detail for f in scan_test_source(source, "t.py")] == ["test_x has no assertion"]


def test_a_with_block_whose_context_is_a_bare_name_does_not_count() -> None:
    source = "def test_x():\n    with ctx:\n        pass\n"
    assert scan_test_source(source, "t.py") != ()


def test_a_call_through_a_subscript_is_not_mistaken_for_an_assertion() -> None:
    """The callee is neither a Name nor an Attribute, so the classifier must fall through."""
    source = "def test_x():\n    checks[0](1)\n"
    assert scan_test_source(source, "t.py") != ()


def test_an_immediately_invoked_lambda_is_not_an_assertion() -> None:
    assert scan_test_source("def test_x():\n    (lambda: 1)()\n", "t.py") != ()


def test_an_unparseable_test_module_is_reported_not_skipped() -> None:
    assert [f.code for f in scan_test_source("def test_(:\n", "t.py")] == ["unparseable"]


def test_scan_tests_reports_relative_paths_and_is_ordered(tmp_path: Path) -> None:
    (tmp_path / "test_b.py").write_text("def test_b():\n    pass\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (tmp_path / "helper.py").write_text("def test_ignored():\n    pass\n", encoding="utf-8")
    findings = scan_tests(tmp_path)
    assert [f.path for f in findings] == ["sub/test_a.py", "test_b.py"]


def test_scan_tests_reports_an_undecodable_module_as_a_read_error(tmp_path: Path) -> None:
    (tmp_path / "test_raw.py").write_bytes(b"\xff\xfe\x00bad")
    assert [f.code for f in scan_tests(tmp_path)] == ["read-error"]


def test_scan_tests_on_an_empty_tree_is_empty(tmp_path: Path) -> None:
    from agentspec.testlint import test_files

    assert scan_tests(tmp_path) == ()
    assert test_files(tmp_path) == ()
