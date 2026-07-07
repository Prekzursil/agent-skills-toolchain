#!/usr/bin/env python3
"""mutation_check — a cheap, execution-grounded test-STRENGTH gate.

The C3 gem of the agentic-perfection program (see
``docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md``). Coverage and a green
``pytest`` only prove the tests EXECUTE the code; they say nothing about whether
the tests ASSERT its behaviour. bFinder measured 17.5% of expected behaviours
untested even at >90% line+mutation coverage — the classic Goodhart-green gap:
tests that run the function but would not notice if it returned the wrong answer.

This tool measures test STRENGTH empirically. Given a changed source file and the
command that runs its tests, it applies a small, high-signal set of mutations to
the function(s) under test and, for each, re-runs the tests and asks: did at least
one test go RED? A mutation the whole suite lets stay green ("SURVIVED") is a
behaviour the tests never actually check — a proven weak spot to point at.

Design law (mirrors the hook gems): anchor to an EXTERNAL signal the implementer
can't fake. The signal here is "does a real test process exit non-zero when the
code is provably broken?" — not a self-report, an actual red run.

Mutation set (small on purpose — high kill-signal, low cost):
  * boolean-flip      ``True`` <-> ``False``
  * comparison-swap   ``==``->``!=``  ``<``->``>=``  ``<=``->``>``  ``>``->``<=``  ``>=``->``<``
  * arithmetic-swap   ``+``<->``-``   ``*``<->``/``
  * return-value      ``return X`` -> ``return None`` (X not already None)
  * boundary          numeric literal ``n`` -> ``n + 1`` (off-by-one probe)

Safety: the real source file must be mutated in place (so the tests import the
mutated module), but the original bytes are captured up front, a temp backup is
written, the file is restored after every single run, and a ``finally`` plus a
final byte-identical verification guarantee the file is left exactly as found —
even on exception or Ctrl-C. Fail-safe over fail-open: an operational problem
(unparseable source, no mutable sites, red baseline) exits 2, never a false green.

Exit codes (so it can gate a pipeline):
  0  every mutation was KILLED — tests assert behaviour at every mutated site
  1  at least one mutation SURVIVED — a Goodhart-green gap to fix
  2  operational error — could not assess (see the FAILED line for why)

Stdlib only. Requires Python 3.9+ (``ast.unparse``).

Usage:
    python mutation_check.py [options] SOURCE -- TEST COMMAND...

    python mutation_check.py src/calc.py -- python -m pytest tests/test_calc.py -q
    python mutation_check.py src/calc.py --function is_adult -- python -m pytest -q
    python mutation_check.py src/calc.py --list          # just enumerate sites

Everything after ``--`` is the test command, run verbatim (no shell). Prefer
``python -m pytest`` so it resolves without relying on PATH/PATHEXT.
"""

from __future__ import annotations

import argparse
import ast
import copy
import os
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass
from pathlib import Path

EXIT_ALL_KILLED = 0
EXIT_SURVIVOR = 1
EXIT_ERROR = 2

DEFAULT_MAX_MUTATIONS = 20
DEFAULT_TIMEOUT = 300.0
_SNIPPET_MAX = 48

# Comparison operators -> their single high-signal swap (negation / boundary).
_CMP_SWAP: dict[type, type] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
}
# Arithmetic operators -> their swap.
_ARITH_SWAP: dict[type, type] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
}


# --------------------------------------------------------------------------- #
# The mutation catalogue (pure — each entry mutates a node IN PLACE).
# --------------------------------------------------------------------------- #
def _flip_bool(node: ast.Constant) -> None:
    node.value = not node.value


def _bump_number(node: ast.Constant) -> None:
    node.value = node.value + 1


def _swap_compare(node: ast.Compare) -> None:
    node.ops[0] = _CMP_SWAP[type(node.ops[0])]()


def _swap_arith(node: ast.BinOp) -> None:
    node.op = _ARITH_SWAP[type(node.op)]()


def _nullify_return(node: ast.Return) -> None:
    node.value = ast.Constant(value=None)


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_plain_number(value: object) -> bool:
    """A real numeric literal we can bump — int/float but NOT bool or complex."""
    return isinstance(value, (int, float)) and not isinstance(value, (bool, complex))


def _mutations_for_node(node: ast.AST):
    """Yield ``(kind, apply_fn)`` for every mutation applicable to ``node``.

    Deterministic and side-effect free until an ``apply_fn`` is called. The same
    routine drives both enumeration (metadata) and application (in-place mutate),
    so their ordering is guaranteed identical.
    """
    if isinstance(node, ast.Constant):
        if node.value is True or node.value is False:
            yield "boolean-flip", _flip_bool
        elif _is_plain_number(node.value):
            yield "boundary", _bump_number
    elif isinstance(node, ast.Compare):
        if len(node.ops) == 1 and type(node.ops[0]) in _CMP_SWAP:
            yield "comparison-swap", _swap_compare
    elif isinstance(node, ast.BinOp):
        if type(node.op) in _ARITH_SWAP:
            yield "arithmetic-swap", _swap_arith
    elif isinstance(node, ast.Return):
        value = node.value
        if value is not None and not (
            isinstance(value, ast.Constant) and value.value is None
        ):
            yield "return-value", _nullify_return


# --------------------------------------------------------------------------- #
# Scoping: which nodes belong to the function(s) under test.
# --------------------------------------------------------------------------- #
def _target_functions(
    tree: ast.AST, names: set[str] | None
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Function/method defs to mutate — all of them, or those matching ``names``."""
    out: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if names is None or node.name in names:
                out.append(node)
    return out


def _scoped_nodes(tree: ast.AST, names: set[str] | None):
    """Yield every node inside the target functions' BODIES, deduped, in order.

    Only the function *body* is walked (never decorators, annotations, or default
    args), so mutations land on the logic under test. Nested helpers are included
    because they are part of that function's behaviour; a shared ``seen`` set keeps
    a node reached via two enclosing functions from being yielded twice, which
    keeps enumeration and application ordinals aligned.
    """
    seen: set[int] = set()
    for func in _target_functions(tree, names):
        for stmt in func.body:
            for node in ast.walk(stmt):
                if id(node) in seen:
                    continue
                seen.add(id(node))
                yield node


# --------------------------------------------------------------------------- #
# Mutation description + enumeration + application.
# --------------------------------------------------------------------------- #
@dataclass
class Mutation:
    """A single located mutation site (metadata only — no live AST references)."""

    index: int
    kind: str
    lineno: int
    col: int
    before: str
    after: str

    def label(self) -> str:
        return f"{self.kind} L{self.lineno} `{self.before}` -> `{self.after}`"


def _snippet(node: ast.AST) -> str:
    """A short, single-line source rendering of ``node`` (for human-readable diffs)."""
    try:
        text = ast.unparse(node)
    except Exception:  # noqa: BLE001 - description is cosmetic; never fail the run
        return "?"
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_MAX else text[: _SNIPPET_MAX - 1] + "…"


def find_mutations(
    source: str, names: set[str] | None, max_mutations: int
) -> tuple[list[Mutation], bool]:
    """Enumerate mutation sites in the target function(s). Pure; the testable core.

    Returns ``(mutations, truncated)``. ``truncated`` is True when more sites exist
    than ``max_mutations`` (0 = unlimited) and the list was capped in source order.
    """
    tree = ast.parse(source)
    muts: list[Mutation] = []
    index = 0
    for node in _scoped_nodes(tree, names):
        for kind, apply_fn in _mutations_for_node(node):
            before = _snippet(node)
            preview = copy.deepcopy(node)
            apply_fn(preview)
            muts.append(
                Mutation(
                    index=index,
                    kind=kind,
                    lineno=getattr(node, "lineno", 0),
                    col=getattr(node, "col_offset", 0),
                    before=before,
                    after=_snippet(preview),
                )
            )
            index += 1
    truncated = bool(max_mutations) and len(muts) > max_mutations
    if truncated:
        muts = muts[:max_mutations]
    return muts, truncated


def apply_mutation(source: str, target_index: int, names: set[str] | None) -> str:
    """Return ``source`` with exactly the ``target_index``-th mutation applied.

    Re-parses from scratch and walks with the SAME order as :func:`find_mutations`,
    mutating only the matching site, then unparses the whole module. The input
    string is never modified; the caller decides where to write the result.
    """
    tree = ast.parse(source)
    index = 0
    for node in _scoped_nodes(tree, names):
        for _kind, apply_fn in _mutations_for_node(node):
            if index == target_index:
                apply_fn(node)
                ast.fix_missing_locations(tree)
                return ast.unparse(tree)
            index += 1
    raise IndexError(f"no mutation at index {target_index}")


def _roundtrip(source: str) -> str:
    """``source`` parsed and unparsed with NO mutation (the unparse baseline)."""
    return ast.unparse(ast.parse(source))


# --------------------------------------------------------------------------- #
# Test runner.
# --------------------------------------------------------------------------- #
def run_tests(command: list[str], cwd: str | None, timeout: float) -> int:
    """Run the test command; return its exit code (124 on timeout). Never raises.

    ``PYTHONDONTWRITEBYTECODE`` is forced on so a mutated source can never be
    shadowed by a stale ``.pyc`` compiled from a previous run (each child always
    compiles the file it actually reads), and the tool leaves no cache litter.
    """
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
        return proc.returncode
    except subprocess.TimeoutExpired:
        return 124
    except (OSError, ValueError):
        # Command not found / bad argv: treat as a killing failure is wrong here —
        # this is an operational failure, surfaced by the caller's baseline check.
        return 127


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #
def _emit(out, line: str) -> None:
    out.write(line + "\n")


def run_check(
    source_path: str,
    command: list[str],
    names: set[str] | None,
    *,
    max_mutations: int = DEFAULT_MAX_MUTATIONS,
    timeout: float = DEFAULT_TIMEOUT,
    cwd: str | None = None,
    out=None,
) -> int:
    """Mutate → run tests → classify → restore. Returns a process exit code.

    Restores the source file to its exact original bytes after every run and again
    in a ``finally``; verifies byte-identity at the end and repairs from the temp
    backup if anything drifted. An operational failure returns EXIT_ERROR (2) — a
    tool that can't assess must never report a false green.
    """
    out = out or sys.stdout
    path = Path(source_path)

    try:
        original_bytes = path.read_bytes()
    except OSError as exc:
        _emit(out, f"FAILED: mutation-check cannot read {source_path}: {exc}")
        return EXIT_ERROR
    try:
        source_text = _read_source_text(path)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        _emit(out, f"FAILED: mutation-check cannot decode {source_path}: {exc}")
        return EXIT_ERROR

    try:
        muts, truncated = find_mutations(source_text, names, max_mutations)
    except SyntaxError as exc:
        _emit(out, f"FAILED: mutation-check cannot parse {source_path}: {exc}")
        return EXIT_ERROR

    scope = "the file" if names is None else "function(s) " + ", ".join(sorted(names))
    if not muts:
        _emit(
            out,
            f"FAILED: mutation-check found no mutable sites in {scope} of "
            f"{source_path} — nothing to assess (target correct?).",
        )
        return EXIT_ERROR

    # Two baselines BEFORE mutating: the real file must be green, and the plain
    # ast round-trip must also be green (else unparse itself changed behaviour and
    # every mutation would look killed for the wrong reason — an unreliable check).
    backup_path = _write_backup(original_bytes)
    try:
        baseline_rc = run_tests(command, cwd, timeout)
        if baseline_rc != 0:
            _emit(
                out,
                "FAILED: mutation-check baseline is RED (test command exited "
                f"{baseline_rc}) — fix the tests before checking their strength.",
            )
            return EXIT_ERROR

        path.write_text(_roundtrip(source_text), encoding="utf-8")
        roundtrip_rc = run_tests(command, cwd, timeout)
        path.write_bytes(original_bytes)
        if roundtrip_rc != 0:
            _emit(
                out,
                "FAILED: mutation-check ast round-trip changed behaviour (exit "
                f"{roundtrip_rc}) — cannot reliably mutation-check this file "
                "(formatting/comment-sensitive code?).",
            )
            return EXIT_ERROR

        survivors: list[Mutation] = []
        _emit(
            out, f"mutation-check: {len(muts)} mutation(s) in {scope} of {source_path}"
        )
        if truncated:
            _emit(
                out,
                f"NOTE: capped at --max-mutations={max_mutations} (more sites exist)",
            )
        for mut in muts:
            path.write_text(
                apply_mutation(source_text, mut.index, names), encoding="utf-8"
            )
            rc = run_tests(command, cwd, timeout)
            path.write_bytes(original_bytes)
            killed = rc != 0
            state = "KILLED  " if killed else "SURVIVED"
            _emit(out, f"{state} #{mut.index} {mut.label()}")
            if not killed:
                survivors.append(mut)
    finally:
        _restore(path, original_bytes, backup_path, out)

    killed_n = len(muts) - len(survivors)
    _emit(
        out,
        f"SUMMARY: {len(muts)} mutation(s), {killed_n} killed, {len(survivors)} survived",
    )
    if survivors:
        gaps = "; ".join(m.label() for m in survivors[:8])
        more = " …" if len(survivors) > 8 else ""
        _emit(
            out,
            f"FAILED: mutation-check {len(survivors)} surviving mutation(s) — a "
            f"Goodhart-green gap (code runs but its behaviour is unasserted): {gaps}{more}",
        )
        return EXIT_SURVIVOR
    _emit(
        out,
        f"SUCCESS: mutation-check {killed_n}/{len(muts)} mutations killed — "
        "tests assert behaviour at every mutated site.",
    )
    return EXIT_ALL_KILLED


def _read_source_text(path: Path) -> str:
    """Read source respecting a PEP 263 coding cookie / BOM (like the interpreter)."""
    with tokenize.open(str(path)) as handle:
        return handle.read()


def _write_backup(original_bytes: bytes) -> Path:
    """Persist original bytes to a temp file so restore survives even a hard crash."""
    fd, name = tempfile.mkstemp(prefix="mutation-check-", suffix=".bak")
    with os.fdopen(fd, "wb") as handle:
        handle.write(original_bytes)
    return Path(name)


def _restore(path: Path, original_bytes: bytes, backup_path: Path, out) -> None:
    """Guarantee the source file is byte-identical to its original; clean up backup."""
    try:
        if path.read_bytes() != original_bytes:
            path.write_bytes(original_bytes)
        if path.read_bytes() != original_bytes:  # last resort: copy the temp backup
            path.write_bytes(backup_path.read_bytes())
            _emit(out, f"WARNING: restored {path} from backup {backup_path}")
    except OSError as exc:  # pragma: no cover - only on a filesystem fault
        _emit(
            out,
            f"WARNING: could not verify restore of {path}: {exc} "
            f"(original bytes preserved at {backup_path})",
        )
        return
    try:
        backup_path.unlink()
    except OSError:  # pragma: no cover - best-effort cleanup
        pass


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    """Split ``argv`` at ``--`` (git-style) into options+SOURCE and the test command."""
    if "--" in argv:
        cut = argv.index("--")
        pre, command = argv[:cut], argv[cut + 1 :]
    else:
        pre, command = argv, []

    parser = argparse.ArgumentParser(
        prog="mutation_check.py",
        description="Empirically test test-STRENGTH: mutate the code, assert a test goes red.",
        epilog="Everything after `--` is the test command, run verbatim. "
        "Example: mutation_check.py src/calc.py -- python -m pytest -q",
    )
    parser.add_argument("source", help="the changed source file to mutate")
    parser.add_argument(
        "--function",
        "-f",
        action="append",
        metavar="NAME",
        help="restrict mutations to this function/method (repeatable; default: all)",
    )
    parser.add_argument(
        "--max-mutations",
        type=int,
        default=DEFAULT_MAX_MUTATIONS,
        metavar="N",
        help=f"cap mutations run, in source order (0 = unlimited; default {DEFAULT_MAX_MUTATIONS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SEC",
        help=f"per-test-run timeout in seconds (default {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        metavar="DIR",
        help="working directory for the test command (default: inherit)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="only enumerate mutation sites; do not run any tests",
    )
    ns = parser.parse_args(pre)
    ns.command = command
    return ns


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    names = set(args.function) if args.function else None

    if args.list:
        try:
            source_text = _read_source_text(Path(args.source))
            muts, truncated = find_mutations(source_text, names, args.max_mutations)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            print(f"FAILED: mutation-check --list: {exc}", file=sys.stderr)
            return EXIT_ERROR
        for mut in muts:
            print(f"#{mut.index} {mut.label()}")
        print(
            f"SUMMARY: {len(muts)} mutation site(s)"
            + (" (capped)" if truncated else "")
        )
        return EXIT_ALL_KILLED

    if not args.command:
        print(
            "FAILED: mutation-check needs a test command after `--`, e.g. "
            "`mutation_check.py src/calc.py -- python -m pytest -q`",
            file=sys.stderr,
        )
        return EXIT_ERROR

    return run_check(
        args.source,
        args.command,
        names,
        max_mutations=args.max_mutations,
        timeout=args.timeout,
        cwd=args.cwd,
    )


if __name__ == "__main__":
    sys.exit(main())
