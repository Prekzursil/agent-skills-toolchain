"""TG-2 diff-scoped mutation gate (agent-skills-toolchain harness gem).

Coverage proves a line *ran*; mutation proves a test would *notice* if that line's
logic were wrong. This gate runs a Python mutation tester (cosmic-ray, pinned) on
ONLY the files a diff touched (``git diff --name-only <base>...HEAD``) — the cost
control — and FAILS when any mutant SURVIVES, naming the surviving mutant and the
weak test suite that let it live. The motivating scar: a ``DEFAULT_MIN_BYTES``
default that stayed at 100% line coverage while no test actually asserted it.

Design notes
------------
* Tool = **cosmic-ray** (pinned ``COSMIC_RAY_VERSION``). It is the mutation tester
  that installs cleanly via ``uvx``/``pip`` AND runs natively on Windows, macOS and
  Linux (mutmut 3.x refuses to run on native Windows — boxed/mutmut#397 — so it
  cannot back a *locally*-runnable cross-platform gate). This gate is additive and
  opt-in: it touches none of the repo's existing quality gates; see README.md.
* Everything is stdlib + the pinned mutation tool. The pure helpers are exported
  and unit-tested to 100% line+branch; the subprocess seams (git, cosmic-ray) are
  injectable so the fast suite needs neither a git repo nor cosmic-ray. The real
  RED/GREEN proof lives in ``tests/test_mutation_gate_demo.py``.
"""

import argparse
import json
import os
import subprocess  # noqa: S404 — the gate orchestrates git + cosmic-ray by design.
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

COSMIC_RAY_VERSION = "8.4.6"
DEFAULT_BASE = "origin/main"
DEFAULT_TEST_COMMAND = "{python} -m pytest -x -q"
DEFAULT_TIMEOUT = 30.0
# Substring markers of paths that must never be mutated (vendored third-party
# trees + virtualenvs). ``vendor/`` covers the toolchain's committed vendored
# trees (e.g. tools/editor/ralph-orchestrator/vendor). Test files are handled
# separately by ``is_test_path``. Override with ``--exclude`` for a specific tree.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "vendor/",
    "node_modules/",
    ".venv/",
)


class GateError(RuntimeError):
    """A tool the gate shells out to (git / cosmic-ray) failed to run."""


@dataclass(frozen=True)
class Survivor:
    """One surviving mutant: a spot the tests ran over but did not assert."""

    file: str
    line: int
    column: int
    operator: str
    function: str
    diff: str


@dataclass(frozen=True)
class GateResult:
    """Outcome of a gate run: process exit code + the survivors that drove it."""

    exit_code: int
    scoped_files: tuple[str, ...]
    survivors: tuple[Survivor, ...]


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def _normalize(path: str) -> str:
    """Normalize OS path separators to forward slashes."""
    return path.replace("\\", "/")


def is_test_path(path: str) -> bool:
    """True when ``path`` looks like a test module (mutating tests is pointless)."""
    segments = _normalize(path).split("/")
    base = segments[-1]
    if any(seg in ("tests", "test") for seg in segments[:-1]):
        return True
    return base.startswith("test_") or base.endswith("_test.py")


def scope_changed_files(
    diff_output: str,
    includes: Sequence[str] = (),
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
    include_tests: bool = False,
) -> list[str]:
    """Reduce ``git diff --name-only`` output to the mutation-worthy Python files.

    This is the diff-scoping (cost control): only ``.py`` files that survive the
    include/exclude/test filters are mutated — never the whole tree.
    """
    scoped: list[str] = []
    seen: set[str] = set()
    for raw in diff_output.splitlines():
        path = _normalize(raw.strip())
        if not path:
            continue
        if not path.endswith(".py"):
            continue
        if includes and not any(_include_match(path, inc) for inc in includes):
            continue
        if any(marker in path for marker in excludes):
            continue
        if not include_tests and is_test_path(path):
            continue
        if path in seen:
            continue
        seen.add(path)
        scoped.append(path)
    return scoped


def _include_match(path: str, include: str) -> bool:
    """Match an include entry as either an exact file or a directory prefix."""
    prefix = include if include.endswith("/") else include + "/"
    return path == include or path.startswith(prefix)


def _toml_escape(value: str) -> str:
    """Escape a value for a TOML basic (double-quoted) string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_cosmic_ray_config(
    module_path: str,
    test_command: str,
    timeout: float,
    excluded_modules: Iterable[str] = (),
) -> str:
    """Render a cosmic-ray TOML config for a single module + a test command."""
    excludes_toml = ", ".join(f'"{_toml_escape(m)}"' for m in excluded_modules)
    return (
        "[cosmic-ray]\n"
        f'module-path = "{_toml_escape(module_path)}"\n'
        f"timeout = {timeout}\n"
        f"excluded-modules = [{excludes_toml}]\n"
        f'test-command = "{_toml_escape(test_command)}"\n'
        "\n"
        "[cosmic-ray.distributor]\n"
        'name = "local"\n'
    )


def _format_test_command(template: str, python_exe: str) -> str:
    """Substitute ``{python}`` with a quoted, forward-slashed interpreter path.

    The interpreter MUST be explicit: cosmic-ray's ``test-command`` runs in a fresh
    subprocess, and a bare ``python`` can resolve to an interpreter WITHOUT pytest,
    which makes every mutant read as falsely "killed" (a silent detector failure).
    """
    return template.format(python=f'"{_normalize(python_exe)}"')


def parse_dump(dump_text: str) -> list[dict]:
    """Parse ``cosmic-ray dump`` JSONL into flat per-mutant records.

    Each executed mutant is a 2-element JSON array ``[spec, result]``. Unexecuted
    entries (1-element), blank lines and any malformed line are skipped.
    """
    records: list[dict] = []
    for raw in dump_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        spec, result = entry[0], entry[1]
        mutations = spec.get("mutations") or []
        if not mutations:
            continue
        mutation = mutations[0]
        start = mutation.get("start_pos") or [0, 0]
        records.append(
            {
                "file": _normalize(mutation.get("module_path", "")),
                "line": start[0],
                "column": start[1],
                "operator": mutation.get("operator_name", ""),
                "function": mutation.get("definition_name") or "",
                "outcome": str(result.get("test_outcome", "")).lower(),
                "diff": result.get("diff", ""),
            }
        )
    return records


def extract_survivors(records: Iterable[dict]) -> list[Survivor]:
    """Keep only SURVIVED mutants (the weak spots) as ``Survivor`` records."""
    return [
        Survivor(
            file=r["file"],
            line=r["line"],
            column=r["column"],
            operator=r["operator"],
            function=r["function"],
            diff=r["diff"],
        )
        for r in records
        if r["outcome"] == "survived"
    ]


def format_report(result: GateResult, test_command: str) -> str:
    """Human-readable gate report naming each surviving mutant + the weak suite."""
    if result.survivors:
        header = (
            f"FAILED: {len(result.survivors)} surviving mutant(s) across "
            f"{len(result.scoped_files)} diff-scoped file(s). Coverage says these lines "
            f"ran; mutation says the test suite run by `{test_command}` does NOT assert "
            "them. Strengthen the weak test(s) below (never weaken an assertion):"
        )
        lines = [header]
        for s in result.survivors:
            where = f"{s.file}:{s.line}:{s.column}"
            in_fn = f" in {s.function}()" if s.function else ""
            last = (
                s.diff.strip().splitlines()[-1].strip()
                if s.diff.strip()
                else "(no diff)"
            )
            lines.append(f"  - {where} [{s.operator}]{in_fn}  -->  {last}")
        return "\n".join(lines)
    return f"SUCCESS: no surviving mutants across {len(result.scoped_files)} diff-scoped file(s)."


def summary_dict(result: GateResult) -> dict:
    """Machine-readable summary (for ``--json``)."""
    return {
        "exit_code": result.exit_code,
        "scoped_files": list(result.scoped_files),
        "survivors": [
            {
                "file": s.file,
                "line": s.line,
                "column": s.column,
                "operator": s.operator,
                "function": s.function,
                "diff": s.diff,
            }
            for s in result.survivors
        ],
    }


# --------------------------------------------------------------------------- #
# Subprocess seams (injectable: unit tests pass a fake ``run``)
# --------------------------------------------------------------------------- #
def _run_checked(run: Callable, argv: list[str], cwd: str, phase: str):
    """Run ``argv`` and raise ``GateError`` on a non-zero exit."""
    proc = run(argv, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise GateError(
            f"{phase} failed (rc={proc.returncode}): {proc.stderr.strip()[-500:]}"
        )
    return proc


def default_git_diff(
    base: str, repo_root: str, *, run: Callable = subprocess.run
) -> str:
    """Return ``git diff --name-only <base>...HEAD`` output for ``repo_root``.

    Uses the three-dot range (merge-base symmetric) so the scope is exactly what
    this branch adds relative to ``base``. Argv is a list (no shell), so the MSYS
    path-conversion / quoting footguns do not apply.
    """
    proc = _run_checked(
        run,
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{base}...HEAD"],
        repo_root,
        "git diff",
    )
    return proc.stdout


def default_mutation_run(
    module_path: str,
    repo_root: str,
    test_command: str,
    timeout: float,
    python_exe: str,
    *,
    run: Callable = subprocess.run,
) -> str:
    """Mutate ONE file with cosmic-ray and return its ``dump`` output (JSONL).

    cosmic-ray only ever sees this single ``module-path``, so the run is inherently
    diff-scoped: the rest of the tree is never mutated.
    """
    abs_module = _normalize(os.path.abspath(os.path.join(str(repo_root), module_path)))
    rendered = _format_test_command(test_command, python_exe)
    config = render_cosmic_ray_config(abs_module, rendered, timeout)
    cli = [python_exe, "-m", "cosmic_ray.cli"]
    with tempfile.TemporaryDirectory(prefix="tg2-mutation-") as workdir:
        cfg_path = os.path.join(workdir, "cosmic-ray.toml")
        db_path = os.path.join(workdir, "session.sqlite")
        with open(cfg_path, "w", encoding="utf-8") as handle:
            handle.write(config)
        _run_checked(
            run, [*cli, "init", cfg_path, db_path], repo_root, "cosmic-ray init"
        )
        _run_checked(
            run, [*cli, "exec", cfg_path, db_path], repo_root, "cosmic-ray exec"
        )
        dump = _run_checked(run, [*cli, "dump", db_path], repo_root, "cosmic-ray dump")
    return dump.stdout


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_gate(
    *,
    base: str = DEFAULT_BASE,
    repo_root: str = ".",
    test_command: str = DEFAULT_TEST_COMMAND,
    includes: Sequence[str] = (),
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
    include_tests: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    python_exe: str | None = None,
    files: Sequence[str] | None = None,
    diff_runner: Callable | None = None,
    mutation_runner: Callable | None = None,
    log: Callable[[str], None] = print,
) -> GateResult:
    """Run the diff-scoped mutation gate and return the ``GateResult``.

    ``files`` (explicit list) bypasses git; otherwise the changed set comes from
    ``diff_runner``. Exits non-zero iff any mutant survives in a scoped file.
    """
    python_exe = python_exe or sys.executable
    diff_runner = diff_runner or default_git_diff
    mutation_runner = mutation_runner or default_mutation_run

    diff_output = diff_runner(base, repo_root) if files is None else "\n".join(files)
    scoped = scope_changed_files(diff_output, includes, excludes, include_tests)

    survivors: list[Survivor] = []
    for changed in scoped:
        dump = mutation_runner(changed, repo_root, test_command, timeout, python_exe)
        survivors.extend(extract_survivors(parse_dump(dump)))

    result = GateResult(1 if survivors else 0, tuple(scoped), tuple(survivors))
    log(format_report(result, test_command))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="mutation_gate", description="TG-2 diff-scoped mutation gate."
    )
    parser.add_argument(
        "--base", default=DEFAULT_BASE, help="Diff base ref (default: origin/main)."
    )
    parser.add_argument(
        "--repo-root", default=".", help="Repository root to run git/cosmic-ray in."
    )
    parser.add_argument(
        "--test-command",
        default=DEFAULT_TEST_COMMAND,
        help="cosmic-ray test-command ({python} placeholder).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-mutant test timeout (seconds).",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Only mutate paths under this prefix/file (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Skip paths containing this marker (repeatable; replaces defaults).",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="Interpreter for the test-command (default: this interpreter).",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also mutate test files (off by default).",
    )
    parser.add_argument(
        "--files",
        action="append",
        help="Explicit file(s) to scope, bypassing git (repeatable).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="Write a machine-readable summary here.",
    )
    args = parser.parse_args(argv)

    includes = tuple(args.include) if args.include else ()
    excludes = tuple(args.exclude) if args.exclude else DEFAULT_EXCLUDES

    try:
        result = run_gate(
            base=args.base,
            repo_root=args.repo_root,
            test_command=args.test_command,
            includes=includes,
            excludes=excludes,
            include_tests=args.include_tests,
            timeout=args.timeout,
            python_exe=args.python,
            files=args.files,
        )
    except GateError as exc:
        print(f"FAILED:TG-2 {exc}")
        return 2

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(summary_dict(result), handle, indent=2)
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
