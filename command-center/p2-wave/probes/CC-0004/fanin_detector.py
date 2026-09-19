#!/usr/bin/env python3
"""CC-0004 — AST/import-graph detector for local completion fan-in sites.

Enumerates Python sites under tools/, scripts/, and relevant command-center/
that produce a done/complete/pass verdict, and classifies each as either:

  * shared_import  — resolves to platform/lib/completion_predicate.py
  * local_predicate — computes completion locally (a fork of the CC-0003 reducer)

Prose / markdown that merely *mentions* the fork defect is never reported
(use-vs-mention). Detector controls live under fixtures/ and are proven in both
states by test_fanin_detector.py.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO = Path(__file__).resolve().parents[4]

SHARED_MODULE_STEMS = frozenset(
    {
        "completion_predicate",
    }
)
SHARED_IMPORT_SUFFIXES = (
    "completion_predicate",
    "platform.lib.completion_predicate",
)

#: Function names that, when defined locally with completion vocabulary and
#: without a shared-reducer import, are treated as fan-in forks.
LOCAL_FN_NAMES = frozenset(
    {
        "evaluate",
        "evaluate_completion",
        "evaluate_gate_a",
        "is_complete",
        "is_done",
        "artifact_ok",
        "artifact_text_ok",
        "check_completion",
        "completion_ok",
        "unit_complete",
        "reduce_claim",
    }
)

#: ``classify`` is overloaded across the tree (MCP providers, audits, gitcrypt).
#: Only treat it as a completion fan-in when the module also looks like a
#: completion contract (path/name, State/Verdict+DONE, or CONDITIONS table).
CLASSIFY_NEEDS_COMPLETION_CONTEXT = True

TERMINAL_VOCAB = frozenset(
    {
        "DONE",
        "COMPLETE",
        "COMPLETED",
        "SUCCESS",
        "PASS",
        "PASSED",
        "INCOMPLETE",
        "FAILED",
        "SEVERED",
        "UNKNOWN",
        "TERMINAL",
    }
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "vendor",
        "htmlcov",
        "coverage",
    }
)

#: Default live scan roots (catalog: tools/ + scripts/ + relevant command-center).
DEFAULT_ROOTS = (
    "tools",
    "scripts",
    "command-center",
    "platform/coordination",  # known legitimate re-export of the shared reducer
    "platform/lib",  # the reducer itself + twin gate; import resolution
)

#: Paths never treated as production fan-in (self, fixtures, giant generated trees).
DEFAULT_EXCLUDES = (
    "command-center/p2-wave/probes/CC-0004/fixtures",
    "command-center/p2-wave/probes/CC-0004/scratch",
    "command-center/p2-wave/probes/CC-0004/test_fanin_detector.py",
    "command-center/receipts",
    "command-center/audit",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/catalog-slices",
    "platform/lib/completion_predicate.py",  # the shared symbol itself is not a fork
    "platform/lib/test_completion_predicate.py",
    "platform/lib/_predicate_",
    "platform/lib/_mutation_",
    "platform/lib/_p12_",
)


@dataclass(frozen=True)
class Finding:
    kind: str  # "local_predicate" | "shared_import"
    path: str  # repo-relative posix
    line: int
    symbol: str
    detail: str

    @property
    def file_line(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class ScanReport:
    roots: list[str]
    files_scanned: int
    shared_imports: list[Finding] = field(default_factory=list)
    local_predicates: list[Finding] = field(default_factory=list)
    skipped_non_python: list[str] = field(default_factory=list)

    @property
    def ok_clean(self) -> bool:
        """True when at least one shared import was found and zero local forks."""
        return bool(self.shared_imports) and not self.local_predicates

    def to_dict(self) -> dict[str, Any]:
        return {
            "roots": self.roots,
            "files_scanned": self.files_scanned,
            "shared_import_count": len(self.shared_imports),
            "local_predicate_count": len(self.local_predicates),
            "shared_imports": [asdict(f) for f in self.shared_imports],
            "local_predicates": [asdict(f) for f in self.local_predicates],
            "skipped_non_python": self.skipped_non_python,
            "ok_clean": self.ok_clean,
        }


def _rel(path: Path, repo: Path = REPO) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _excluded(rel: str, excludes: Sequence[str]) -> bool:
    for ex in excludes:
        if rel == ex or rel.startswith(ex.rstrip("/") + "/"):
            return True
        if ex.endswith("/") and rel.startswith(ex):
            return True
        # prefix match for stem patterns like platform/lib/_predicate_
        if not ex.endswith((".py", "/")) and rel.startswith(ex):
            return True
    return False


def iter_python_files(
    roots: Iterable[str | Path],
    *,
    repo: Path = REPO,
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        p = Path(root)
        if not p.is_absolute():
            p = repo / p
        if not p.exists():
            continue
        if p.is_file() and p.suffix == ".py":
            rel = _rel(p, repo)
            if not _excluded(rel, excludes) and p not in seen:
                files.append(p)
                seen.add(p)
            continue
        for py in p.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in py.parts):
                continue
            rel = _rel(py, repo)
            if _excluded(rel, excludes):
                continue
            if py not in seen:
                files.append(py)
                seen.add(py)
    return sorted(files, key=lambda x: _rel(x, repo))


def _module_is_shared(mod: str | None) -> bool:
    if not mod:
        return False
    mod = mod.lstrip(".")
    stem = mod.rsplit(".", 1)[-1]
    if stem in SHARED_MODULE_STEMS:
        return True
    return any(mod == s or mod.endswith("." + s) for s in SHARED_IMPORT_SUFFIXES)


def _imports_shared(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return (lineno, bound_name, module) for shared-reducer imports."""
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _module_is_shared(alias.name):
                    bound = alias.asname or alias.name.split(".")[0]
                    hits.append((node.lineno, bound, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if _module_is_shared(node.module):
                for alias in node.names:
                    bound = alias.asname or alias.name
                    hits.append((node.lineno, bound, node.module or ""))
            # from platform.coordination.reducer import evaluate — re-export path
            if node.module and node.module.replace("\\", "/").endswith(
                ("coordination.reducer", "coordination.reducer")
            ):
                for alias in node.names:
                    if alias.name in {"evaluate", "load_receipt", "REDUCER_ID", "Verdict"}:
                        bound = alias.asname or alias.name
                        hits.append(
                            (node.lineno, bound, f"{node.module}:{alias.name}")
                        )
    return hits


def _node_has_terminal_vocab(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value in TERMINAL_VOCAB or child.value.upper() in TERMINAL_VOCAB:
                return True
        if isinstance(child, ast.Name) and child.id in TERMINAL_VOCAB:
            return True
        if isinstance(child, ast.Attribute) and child.attr in TERMINAL_VOCAB:
            return True
    return False


def _defines_conditions_table(tree: ast.Module) -> bool:
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if any(n in {"CONDITIONS", "CONDITION_TEXT", "NON_WAIVABLE"} for n in names):
            return True
    return False


def _module_looks_like_completion_contract(path: Path, tree: ast.Module) -> bool:
    """True when the file is a completion-plane candidate, not a generic classifier."""
    name = path.name.lower()
    rel = path.as_posix().lower()
    if "completion" in name or "completion" in rel.replace("\\", "/"):
        return True
    if name in {"receipt_schema_gate.py"}:
        return True
    if _defines_conditions_table(tree):
        return True
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name in {"Verdict", "State", "PredicateResult", "Completion"}:
            if _node_has_terminal_vocab(node):
                return True
    return False


def _aliased_from_shared(tree: ast.AST, shared_bounds: set[str]) -> set[str]:
    """Names bound as ``X = shared.attr`` re-exports (not local definitions)."""
    out: set[str] = set()
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Attribute) or not isinstance(value.value, ast.Name):
            continue
        if value.value.id not in shared_bounds:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if isinstance(t, ast.Name):
                out.add(t.id)
    return out


def analyze_module(path: Path, *, repo: Path = REPO) -> tuple[list[Finding], list[Finding]]:
    """Return (shared_imports, local_predicates) for one Python file."""
    rel = _rel(path, repo)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return [], []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return [], []

    shared_hits = _imports_shared(tree)
    shared_bounds = {bound for _, bound, _ in shared_hits}
    shared_findings = [
        Finding(
            kind="shared_import",
            path=rel,
            line=lineno,
            symbol=bound,
            detail=f"imports shared reducer via {mod}",
        )
        for lineno, bound, mod in shared_hits
    ]

    if shared_hits:
        # File already binds the shared reducer — re-exports are legitimate.
        # Still flag a *second* local evaluate/CONDITIONS that is not an alias.
        aliases = _aliased_from_shared(tree, shared_bounds) | shared_bounds
        local: list[Finding] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in LOCAL_FN_NAMES and node.name not in aliases:
                    if node.name == "evaluate" and _defines_conditions_table(tree):
                        local.append(
                            Finding(
                                kind="local_predicate",
                                path=rel,
                                line=node.lineno,
                                symbol=node.name,
                                detail=(
                                    "module imports the shared reducer but ALSO defines a "
                                    "local evaluate alongside a CONDITIONS table"
                                ),
                            )
                        )
                    elif node.name != "evaluate" and _node_has_terminal_vocab(node):
                        # Local helper that still rolls its own terminal check
                        if node.name in {
                            "is_complete",
                            "is_done",
                            "artifact_ok",
                            "artifact_text_ok",
                            "classify",
                            "evaluate_gate_a",
                            "evaluate_completion",
                        }:
                            local.append(
                                Finding(
                                    kind="local_predicate",
                                    path=rel,
                                    line=node.lineno,
                                    symbol=node.name,
                                    detail=(
                                        "local completion helper coexists with a shared "
                                        "import — possible shadow predicate"
                                    ),
                                )
                            )
        return shared_findings, local

    # No shared import — look for local completion planes.
    local_findings: list[Finding] = []
    has_conditions = _defines_conditions_table(tree)
    completion_ctx = _module_looks_like_completion_contract(path, tree)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            # classify only with completion-contract context
            if name == "classify":
                if not (
                    CLASSIFY_NEEDS_COMPLETION_CONTEXT
                    and completion_ctx
                    and _node_has_terminal_vocab(node)
                ):
                    continue
                local_findings.append(
                    Finding(
                        kind="local_predicate",
                        path=rel,
                        line=node.lineno,
                        symbol=name,
                        detail=(
                            "local classify() on a completion-contract module produces "
                            "done/complete/pass vocabulary without importing the shared "
                            "CC-0003 reducer"
                        ),
                    )
                )
                continue
            if name not in LOCAL_FN_NAMES:
                continue
            # evaluate without shared import is a fork only if it looks like a reducer
            if name == "evaluate":
                if has_conditions or _node_has_terminal_vocab(node):
                    local_findings.append(
                        Finding(
                            kind="local_predicate",
                            path=rel,
                            line=node.lineno,
                            symbol=name,
                            detail=(
                                "module-level evaluate computes a completion verdict "
                                "without importing completion_predicate"
                            ),
                        )
                    )
                continue
            if _node_has_terminal_vocab(node) or has_conditions:
                local_findings.append(
                    Finding(
                        kind="local_predicate",
                        path=rel,
                        line=node.lineno,
                        symbol=name,
                        detail=(
                            f"local {name}() produces done/complete/pass vocabulary "
                            "without importing the shared CC-0003 reducer"
                        ),
                    )
                )
        elif isinstance(node, ast.ClassDef):
            # Class Verdict/State with DONE + methods is_done / classify pattern
            if node.name not in {"Verdict", "State", "Completion", "PredicateResult"}:
                continue
            if not _node_has_terminal_vocab(node):
                continue
            # Prefer reporting the class line; methods may also match above when nested
            # — only module-level FunctionDefs are scanned above, so report the class.
            local_findings.append(
                Finding(
                    kind="local_predicate",
                    path=rel,
                    line=node.lineno,
                    symbol=node.name,
                    detail=(
                        f"local {node.name} type carries DONE/COMPLETE terminal states "
                        "without importing completion_predicate"
                    ),
                )
            )

    # Nested methods: ClassDef.body FunctionDef is_done / classify
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name not in {"is_done", "is_complete", "classify", "evaluate"}:
                continue
            if child.name == "evaluate" and not (
                has_conditions or _node_has_terminal_vocab(child)
            ):
                continue
            if not (_node_has_terminal_vocab(child) or _node_has_terminal_vocab(node)):
                continue
            # Avoid double-count if class already reported and method is trivial
            if any(
                f.symbol == node.name and f.path == rel for f in local_findings
            ):
                # still want method file:line for planted controls that define is_done
                if child.name in {"is_done", "is_complete", "classify"}:
                    local_findings.append(
                        Finding(
                            kind="local_predicate",
                            path=rel,
                            line=child.lineno,
                            symbol=f"{node.name}.{child.name}",
                            detail=(
                                f"method {node.name}.{child.name} computes completion "
                                "locally without the shared reducer"
                            ),
                        )
                    )
            else:
                local_findings.append(
                    Finding(
                        kind="local_predicate",
                        path=rel,
                        line=child.lineno,
                        symbol=f"{node.name}.{child.name}",
                        detail=(
                            f"method {node.name}.{child.name} computes completion "
                            "locally without the shared reducer"
                        ),
                    )
                )

    return shared_findings, local_findings


def scan(
    roots: Sequence[str | Path] | None = None,
    *,
    repo: Path = REPO,
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
) -> ScanReport:
    root_list = [str(r) for r in (roots if roots is not None else DEFAULT_ROOTS)]
    report = ScanReport(roots=root_list, files_scanned=0)
    files = iter_python_files(root_list, repo=repo, excludes=excludes)
    report.files_scanned = len(files)
    for py in files:
        shared, local = analyze_module(py, repo=repo)
        report.shared_imports.extend(shared)
        report.local_predicates.extend(local)
    return report


def scan_paths(
    paths: Sequence[str | Path],
    *,
    repo: Path = REPO,
) -> ScanReport:
    """Scan an explicit file list (fixtures / planted controls). Non-.py paths are skipped."""
    report = ScanReport(roots=[str(p) for p in paths], files_scanned=0)
    py_files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = repo / p
        if p.is_dir():
            py_files.extend(sorted(p.rglob("*.py")))
            for other in p.rglob("*"):
                if other.is_file() and other.suffix.lower() in {".md", ".txt", ".rst"}:
                    report.skipped_non_python.append(_rel(other, repo))
        elif p.suffix == ".py":
            py_files.append(p)
        elif p.is_file():
            report.skipped_non_python.append(_rel(p, repo))
    # de-dupe
    seen: set[Path] = set()
    uniq: list[Path] = []
    for py in py_files:
        if "__pycache__" in py.parts:
            continue
        rp = py.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(py)
    report.files_scanned = len(uniq)
    for py in uniq:
        shared, local = analyze_module(py, repo=repo)
        report.shared_imports.extend(shared)
        report.local_predicates.extend(local)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if args:
        report = scan_paths(args, repo=REPO)
    else:
        report = scan(repo=REPO)
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"files_scanned={report.files_scanned} "
            f"shared_imports={len(report.shared_imports)} "
            f"local_predicates={len(report.local_predicates)}"
        )
        for f in report.shared_imports:
            print(f"SHARED {f.file_line} {f.symbol} — {f.detail}")
        for f in report.local_predicates:
            print(f"LOCAL  {f.file_line} {f.symbol} — {f.detail}")
        for s in report.skipped_non_python:
            print(f"SKIP_PROSE {s}")
        print(
            "OK_CLEAN"
            if report.ok_clean
            else (
                "HAS_FORKS"
                if report.local_predicates
                else "NO_SHARED_IMPORT"
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
