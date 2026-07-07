#!/usr/bin/env python3
"""Tests for mutation_check — the empirical test-STRENGTH gate.

Two layers, mirroring the tool's two claims:
  * Pure core (fast, deterministic): AST mutation-site detection, apply/restore
    correctness, scoping, exit-classification via a stubbed runner.
  * Real end-to-end (spawns pytest): a WEAK suite lets a mutation SURVIVE (exit 1),
    a STRONG suite KILLS every mutation (exit 0), and the source file is left
    byte-identical either way (the safety guarantee).
"""

from __future__ import annotations

import ast
import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "mutation_check", _HERE / "mutation_check.py"
)
assert _spec and _spec.loader
mc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mc  # so @dataclass can resolve the module during exec
_spec.loader.exec_module(mc)

_MUT = _HERE / "mutation_check.py"


# --------------------------------------------------------------------------- #
# find_mutations — AST mutation-site detection
# --------------------------------------------------------------------------- #
def test_find_mutations_detects_each_kind():
    src = "def f(a, b):\n    if a == b:\n        return True\n    return a + 1\n"
    muts, _ = mc.find_mutations(src, None, 0)
    kinds = {m.kind for m in muts}
    assert "comparison-swap" in kinds  # a == b
    assert "boolean-flip" in kinds  # True
    assert "return-value" in kinds  # return True / return a + 1
    assert "arithmetic-swap" in kinds  # a + 1
    assert "boundary" in kinds  # the literal 1


def test_comparison_swap_is_negation():
    muts, _ = mc.find_mutations("def f(x):\n    return x >= 18\n", None, 0)
    cmp = next(m for m in muts if m.kind == "comparison-swap")
    assert cmp.before == "x >= 18"
    assert cmp.after == "x < 18"


def test_bool_constant_is_flip_not_boundary():
    # bool is an int subclass; it must be a boolean-flip, never a numeric bump.
    muts, _ = mc.find_mutations("def f():\n    return True\n", None, 0)
    kinds = [m.kind for m in muts]
    assert "boolean-flip" in kinds
    assert "boundary" not in kinds


def test_return_none_and_string_return_not_mutated_as_return_value():
    # `return None` and a bare `return` yield no return-value mutation.
    muts, _ = mc.find_mutations(
        "def f(x):\n    if x:\n        return None\n    return\n",
        None,
        0,
    )
    assert not any(m.kind == "return-value" for m in muts)


def test_no_mutable_sites_returns_empty():
    muts, _ = mc.find_mutations("def noop():\n    pass\n", None, 0)
    assert muts == []


def test_module_level_code_ignored_only_functions_mutated():
    # A comparison at module scope is not "the function under test".
    src = "TOP = 1 == 2\n\ndef f(x):\n    return x + 1\n"
    muts, _ = mc.find_mutations(src, None, 0)
    assert all(m.lineno >= 3 for m in muts)  # nothing from the module-level line 1


def test_max_mutations_caps_in_source_order():
    src = "def f(a, b, c):\n    return a + b - c + 1\n"
    all_muts, trunc_all = mc.find_mutations(src, None, 0)
    assert trunc_all is False
    assert len(all_muts) > 2
    capped, truncated = mc.find_mutations(src, None, 2)
    assert truncated is True
    assert len(capped) == 2
    assert [m.index for m in capped] == [0, 1]


# --------------------------------------------------------------------------- #
# scoping to a named function
# --------------------------------------------------------------------------- #
def test_scoping_to_named_function():
    src = "def a(x):\n    return x + 1\n\n\ndef b(y):\n    return y - 2\n"
    muts_a, _ = mc.find_mutations(src, {"a"}, 0)
    assert muts_a  # a has sites
    assert all(m.lineno <= 2 for m in muts_a)  # none from b (lines 5-6)
    muts_b, _ = mc.find_mutations(src, {"b"}, 0)
    assert all(m.lineno >= 5 for m in muts_b)


def test_scoping_includes_nested_helper():
    src = (
        "def outer(x):\n    def inner(y):\n        return y > 0\n    return inner(x)\n"
    )
    muts, _ = mc.find_mutations(src, {"outer"}, 0)
    # inner's comparison is part of outer's behaviour and must be found.
    assert any(m.kind == "comparison-swap" for m in muts)


# --------------------------------------------------------------------------- #
# apply_mutation — single change, purity, still-valid
# --------------------------------------------------------------------------- #
def test_apply_mutation_makes_the_expected_single_change():
    src = "def f(x):\n    return x >= 18\n"
    muts, _ = mc.find_mutations(src, None, 0)
    idx = next(m.index for m in muts if m.kind == "comparison-swap")
    mutated = mc.apply_mutation(src, idx, None)
    assert mutated != src
    assert "x < 18" in mutated
    ast.parse(mutated)  # result is still syntactically valid Python


def test_apply_mutation_is_pure_source_unchanged():
    src = "def f(x):\n    return x + 1\n"
    before_labels = [m.label() for m in mc.find_mutations(src, None, 0)[0]]
    mc.apply_mutation(src, 0, None)
    after_labels = [m.label() for m in mc.find_mutations(src, None, 0)[0]]
    assert before_labels == after_labels  # enumeration stable => src untouched


def test_apply_each_index_distinct_and_valid():
    src = "def f(a, b):\n    return a == b\n"
    muts, _ = mc.find_mutations(src, None, 0)
    outputs = {mc.apply_mutation(src, m.index, None) for m in muts}
    assert len(outputs) == len(muts)  # every index yields a distinct mutation
    for text in outputs:
        ast.parse(text)


def test_apply_mutation_out_of_range_raises():
    with pytest.raises(IndexError):
        mc.apply_mutation("def f():\n    return 1\n", 99, None)


# --------------------------------------------------------------------------- #
# run_tests — exit-code plumbing
# --------------------------------------------------------------------------- #
def test_run_tests_exit_codes():
    assert (
        mc.run_tests([sys.executable, "-c", "import sys; sys.exit(0)"], None, 30) == 0
    )
    assert (
        mc.run_tests([sys.executable, "-c", "import sys; sys.exit(3)"], None, 30) == 3
    )


def test_run_tests_timeout_is_124():
    slow = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert mc.run_tests(slow, None, 0.2) == 124


def test_run_tests_missing_command_is_127():
    assert mc.run_tests(["__definitely_not_a_real_exe__"], None, 5) == 127


# --------------------------------------------------------------------------- #
# run_check — classification + safety, with a stubbed runner (fast, hermetic)
# --------------------------------------------------------------------------- #
_SRC = "def f(x):\n    return x >= 1\n"


def _seq_runner(codes):
    it = iter(codes)
    return lambda command, cwd, timeout: next(it)


def test_baseline_red_exits_error_and_never_mutates(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text(_SRC, encoding="utf-8")
    original = src.read_bytes()
    monkeypatch.setattr(mc, "run_tests", lambda *a, **k: 1)  # baseline is red
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, out=out)
    assert rc == mc.EXIT_ERROR
    assert "baseline is RED" in out.getvalue()
    assert src.read_bytes() == original


def test_roundtrip_red_exits_error(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text(_SRC, encoding="utf-8")
    original = src.read_bytes()
    monkeypatch.setattr(mc, "run_tests", _seq_runner([0, 1]))  # baseline green, rt red
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, out=out)
    assert rc == mc.EXIT_ERROR
    assert "round-trip changed behaviour" in out.getvalue()
    assert src.read_bytes() == original


def test_no_mutable_sites_exits_error(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text("def noop():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(mc, "run_tests", lambda *a, **k: 0)
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, out=out)
    assert rc == mc.EXIT_ERROR
    assert "no mutable sites" in out.getvalue()


def test_all_killed_exits_zero(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text(_SRC, encoding="utf-8")
    original = src.read_bytes()
    # baseline + roundtrip green, then every mutation is caught (red).
    monkeypatch.setattr(mc, "run_tests", _seq_runner([0, 0] + [1] * 50))
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, out=out)
    text = out.getvalue()
    assert rc == mc.EXIT_ALL_KILLED
    assert "SUCCESS" in text
    assert "survived" in text and "0 survived" in text
    assert src.read_bytes() == original


def test_survivor_exits_one_with_content_sensing_stub(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text(_SRC, encoding="utf-8")
    original = src.read_bytes()

    # Simulate a WEAK suite: it only notices the return-value mutation (return None),
    # letting the comparison-swap and boundary mutations slip through green.
    def weak_suite(command, cwd, timeout):
        return 1 if "return None" in src.read_text(encoding="utf-8") else 0

    monkeypatch.setattr(mc, "run_tests", weak_suite)
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, out=out)
    text = out.getvalue()
    assert rc == mc.EXIT_SURVIVOR
    assert "SURVIVED" in text
    assert "FAILED" in text and "Goodhart-green gap" in text
    assert src.read_bytes() == original  # restored despite survivors


def test_restore_on_exception(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text(_SRC, encoding="utf-8")
    original = src.read_bytes()
    calls = {"n": 0}

    def boom(command, cwd, timeout):
        calls["n"] += 1
        if calls["n"] <= 2:  # baseline + roundtrip pass
            return 0
        raise RuntimeError("simulated crash mid-mutation")

    monkeypatch.setattr(mc, "run_tests", boom)
    with pytest.raises(RuntimeError):
        mc.run_check(str(src), ["x"], None, out=io.StringIO())
    assert src.read_bytes() == original  # finally-restored even on crash


def test_max_mutations_note_emitted(tmp_path, monkeypatch):
    src = tmp_path / "m.py"
    src.write_text("def f(a, b, c):\n    return a + b - c + 1\n", encoding="utf-8")
    monkeypatch.setattr(
        mc, "run_tests", lambda *a, **k: 1
    )  # baseline red short-circuits
    # baseline red exits before the loop, so drive the note path directly instead:
    monkeypatch.setattr(mc, "run_tests", _seq_runner([0, 0] + [1] * 50))
    out = io.StringIO()
    rc = mc.run_check(str(src), ["x"], None, max_mutations=2, out=out)
    assert rc == mc.EXIT_ALL_KILLED
    assert "--max-mutations=2" in out.getvalue()


# --------------------------------------------------------------------------- #
# parse_args + main
# --------------------------------------------------------------------------- #
def test_parse_args_splits_on_double_dash():
    ns = mc.parse_args(["src.py", "--function", "f", "--", "pytest", "-q"])
    assert ns.source == "src.py"
    assert ns.function == ["f"]
    assert ns.command == ["pytest", "-q"]


def test_parse_args_list_needs_no_command():
    ns = mc.parse_args(["src.py", "--list"])
    assert ns.list is True
    assert ns.command == []


def test_main_requires_command(tmp_path, capsys):
    src = tmp_path / "s.py"
    src.write_text("def f():\n    return 1\n", encoding="utf-8")
    rc = mc.main([str(src)])
    assert rc == mc.EXIT_ERROR
    assert "needs a test command" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# End-to-end via the real CLI + a real pytest run (the headline proof)
# --------------------------------------------------------------------------- #
_CALC = "def is_adult(age):\n    return age >= 18\n"

_STRONG_TEST = (
    "from calc import is_adult\n\n\n"
    "def test_is_adult_boundary():\n"
    "    assert is_adult(18) is True\n"
    "    assert is_adult(17) is False\n"
    "    assert is_adult(100) is True\n"
)

# The weak suite never probes the 17/18 boundary, so `18 -> 19` stays green.
_WEAK_TEST = (
    "from calc import is_adult\n\n\n"
    "def test_is_adult_smoke():\n"
    "    assert is_adult(100) is True\n"
    "    assert is_adult(5) is False\n"
)


def _run_cli(source: Path, cwd: Path, testfile: Path, *opts: str):
    argv = [
        sys.executable,
        str(_MUT),
        str(source),
        *opts,
        "--",
        sys.executable,
        "-m",
        "pytest",
        str(testfile),
        "-q",
    ]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd))


def test_e2e_strong_suite_kills_every_mutation(tmp_path):
    calc = tmp_path / "calc.py"
    calc.write_text(_CALC, encoding="utf-8")
    testfile = tmp_path / "test_calc.py"
    testfile.write_text(_STRONG_TEST, encoding="utf-8")
    before = calc.read_bytes()

    r = _run_cli(calc, tmp_path, testfile, "--cwd", str(tmp_path))

    assert r.returncode == mc.EXIT_ALL_KILLED, r.stdout + r.stderr
    assert "SUCCESS" in r.stdout
    assert "SURVIVED" not in r.stdout
    assert calc.read_bytes() == before  # SAFETY: byte-identical after the run


def test_e2e_weak_suite_lets_a_mutation_survive(tmp_path):
    calc = tmp_path / "calc.py"
    calc.write_text(_CALC, encoding="utf-8")
    testfile = tmp_path / "test_calc.py"
    testfile.write_text(_WEAK_TEST, encoding="utf-8")
    before = calc.read_bytes()

    r = _run_cli(calc, tmp_path, testfile, "--cwd", str(tmp_path))

    assert r.returncode == mc.EXIT_SURVIVOR, r.stdout + r.stderr
    assert "SURVIVED" in r.stdout
    assert "boundary" in r.stdout  # the 18 -> 19 off-by-one is the gap
    assert "Goodhart-green gap" in r.stdout
    assert calc.read_bytes() == before  # SAFETY: byte-identical after the run


def test_e2e_list_only_enumerates_scoped_sites(tmp_path):
    src = tmp_path / "m.py"
    src.write_text(
        "def a(x):\n    return x > 0\n\n\ndef b(y):\n    return y + 1\n",
        encoding="utf-8",
    )
    argv = [sys.executable, str(_MUT), str(src), "--list", "--function", "a"]
    r = subprocess.run(argv, capture_output=True, text=True)
    assert r.returncode == mc.EXIT_ALL_KILLED, r.stdout + r.stderr
    assert "comparison-swap" in r.stdout  # from a
    assert "arithmetic-swap" not in r.stdout  # b's `y + 1` is out of scope
