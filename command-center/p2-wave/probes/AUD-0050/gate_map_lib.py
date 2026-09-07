"""Shared helpers for AUD-0050 test-gate coverage mapping."""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
PLANTED_ORPHAN = (
    "command-center/p2-wave/probes/AUD-0050/fixtures/orphan-control/"
    "test_deliberately_ungated.py"
)

SKIP_DIR_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".pytest_cache",
    "site-packages",
}

# Standalone `python path/to/test_*.py` (not pytest).
_PY_TEST_FILE = re.compile(
    r"(?:^|[;&|]|\n)\s*(?:python3?|\$\{[^}]+\}|\S+/python3?)\s+([^\s|&;]+\.py)"
)
_PYTEST_START = re.compile(
    r"(?:^|[;&|]|\n)\s*"
    r"(?:"
    r"(?:python3?|\$\{[^}]+\}|\S+/python3?)\s+-m\s+pytest"
    r"|pytest"
    r")\b"
)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def load_workflow(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        return {}
    # PyYAML parses bare `on:` as True.
    if True in doc and "on" not in doc:
        doc["on"] = doc.pop(True)
    return doc


def inventory_test_files() -> list[str]:
    """Every pytest-shaped test module in the tree, plus the planted control."""
    found: set[str] = set()
    for p in REPO.rglob("*.py"):
        if should_skip(p):
            continue
        name = p.name
        if not (name.startswith("test_") or name.endswith("_test.py")):
            continue
        found.add(rel(p))
    found.add(PLANTED_ORPHAN)
    return sorted(found)


def _split_shell_lines(script: str) -> list[str]:
    lines: list[str] = []
    buf: list[str] = []
    for line in script.splitlines():
        stripped = line.rstrip()
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        if stripped.endswith("\\"):
            buf.append(stripped[:-1])
            continue
        buf.append(stripped)
        lines.append(" ".join(x.strip() for x in buf))
        buf = []
    if buf:
        lines.append(" ".join(x.strip() for x in buf))
    return lines


def _tokenize(cmd: str) -> list[str]:
    # Expand simple "$PWD" / "${PWD}" so path args stay meaningful.
    cmd = cmd.replace('"$PWD"', ".").replace("$PWD", ".")
    cmd = cmd.replace('"${PWD}"', ".").replace("${PWD}", ".")
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def _strip_env_prefix(tokens: list[str]) -> list[str]:
    out = list(tokens)
    while out and "=" in out[0] and not out[0].startswith("-"):
        out = out[1:]
    return out


def parse_pytest_invocation(line: str, working_directory: str) -> dict[str, Any] | None:
    """Return selector model for one pytest (or python test_*.py) line."""
    line = line.strip()
    if not line:
        return None

    # Direct python test_file.py execution
    m_direct = None
    for m in _PY_TEST_FILE.finditer(line):
        candidate = m.group(1)
        base = Path(candidate).name
        if base.startswith("test_") or base.endswith("_test.py"):
            # skip if this is `python -m pytest ...`
            before = line[: m.start()].rstrip()
            if before.endswith("-m"):
                continue
            m_direct = m
            break
    if m_direct and "pytest" not in line:
        path_arg = m_direct.group(1)
        repo_paths = [_resolve_selector_path(path_arg, working_directory)]
        return {
            "kind": "python-script",
            "raw_line": line,
            "working_directory": working_directory,
            "paths": [p for p in repo_paths if p],
            "ignores": [],
            "marker_expr": None,
            "collect_argv": ["--collect-only", "-q", path_arg],
        }

    if "pytest" not in line:
        return None

    # Find pytest argv start. Do NOT treat `pip install pytest` as an invocation —
    # that false-positive collapses the selector model to bare `.` and vacuously
    # covers every test file (including the planted orphan control).
    tokens = _strip_env_prefix(_tokenize(line))
    idx = None
    for i, tok in enumerate(tokens):
        if tok in {"pip", "pip3", "uv", "poetry"} and i + 1 < len(tokens):
            # skip package-manager install lines that merely name the pytest package
            if tokens[i + 1] in {"install", "add"}:
                return None
        if tok == "-m" and i + 1 < len(tokens) and tokens[i + 1] == "pytest":
            idx = i + 2
            break
        if tok == "pytest" or tok.endswith("/pytest"):
            # executable form only when it is argv0 (after env) or an absolute/relative bin path
            if i == 0 or tok.endswith("/pytest"):
                idx = i + 1
                break
            # also allow `command pytest ...` / `time pytest ...`
            if i > 0 and tokens[i - 1] in {"command", "time", "nice", "stdbuf"}:
                idx = i + 1
                break
    if idx is None:
        return None

    args = tokens[idx:]
    paths: list[str] = []
    ignores: list[str] = []
    marker_expr: str | None = None
    collect_argv: list[str] = ["--collect-only", "-q"]
    i = 0
    while i < len(args):
        a = args[i]
        if a in {"\\", "|", "||", "&&", ";"}:
            break
        if a.startswith("--cov") or a.startswith("--cov-"):
            # drop coverage flags (+ value when separate)
            if "=" not in a and i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue
        if a == "--cov-fail-under" or a.startswith("--cov-fail-under="):
            if "=" not in a:
                i += 2
            else:
                i += 1
            continue
        if a == "--cov-report" or a.startswith("--cov-report="):
            if "=" not in a:
                i += 2
            else:
                i += 1
            continue
        if a == "--cov-branch":
            i += 1
            continue
        if a == "-q" or a == "--quiet" or a == "-v" or a == "--verbose":
            i += 1
            continue
        if a == "--collect-only":
            i += 1
            continue
        if a == "--ignore" or a.startswith("--ignore="):
            val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else "")
            if "=" not in a:
                i += 2
            else:
                i += 1
            if val:
                ignores.append(_resolve_selector_path(val, working_directory) or val)
                collect_argv.extend(["--ignore", val])
            continue
        if a == "-m" or a.startswith("-m"):
            if a == "-m":
                marker_expr = args[i + 1] if i + 1 < len(args) else ""
                collect_argv.extend(["-m", marker_expr])
                i += 2
            else:
                marker_expr = a[2:]
                collect_argv.append(a)
                i += 1
            continue
        if a == "-k" or a.startswith("-k"):
            if a == "-k":
                collect_argv.extend(["-k", args[i + 1] if i + 1 < len(args) else ""])
                i += 2
            else:
                collect_argv.append(a)
                i += 1
            continue
        if a == "-p" or a.startswith("-p"):
            if a == "-p":
                collect_argv.extend(["-p", args[i + 1] if i + 1 < len(args) else ""])
                i += 2
            else:
                collect_argv.append(a)
                i += 1
            continue
        if a == "-o" or a.startswith("-o"):
            if a == "-o":
                collect_argv.extend(["-o", args[i + 1] if i + 1 < len(args) else ""])
                i += 2
            else:
                collect_argv.append(a)
                i += 1
            continue
        if a == "--import-mode" or a.startswith("--import-mode="):
            if "=" not in a:
                collect_argv.extend(["--import-mode", args[i + 1] if i + 1 < len(args) else ""])
                i += 2
            else:
                collect_argv.append(a)
                i += 1
            continue
        if a.startswith("-"):
            # unknown flag: keep for collect fidelity when it has no value, else skip value
            collect_argv.append(a)
            if (
                "=" not in a
                and i + 1 < len(args)
                and not args[i + 1].startswith("-")
                and a
                in {
                    "--maxfail",
                    "--tb",
                    "--rootdir",
                    "--confcutdir",
                    "--basetemp",
                    "-c",
                }
            ):
                collect_argv.append(args[i + 1])
                i += 2
            else:
                i += 1
            continue
        # positional path / node id
        paths.append(_resolve_selector_path(a, working_directory) or a)
        collect_argv.append(a)
        i += 1

    if not paths:
        # bare `pytest` → collection root is working_directory
        root = working_directory if working_directory not in {".", ""} else "."
        paths = [root if root != "." else "."]

    return {
        "kind": "pytest",
        "raw_line": line,
        "working_directory": working_directory,
        "paths": paths,
        "ignores": ignores,
        "marker_expr": marker_expr,
        "collect_argv": collect_argv,
    }


def _resolve_selector_path(path_arg: str, working_directory: str) -> str | None:
    path_arg = path_arg.strip().strip("\"'")
    if not path_arg or path_arg == "::" or "::" in path_arg and not path_arg.endswith(".py"):
        # node id fragments — keep file portion if present
        if "::" in path_arg:
            path_arg = path_arg.split("::", 1)[0]
        else:
            return None
    wd = REPO if working_directory in {".", ""} else (REPO / working_directory)
    p = Path(path_arg)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            return None
    try:
        return str((wd / path_arg).resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return path_arg.replace("\\", "/")


def path_covered_by_selector(test_rel: str, selector: dict[str, Any]) -> bool:
    """True when the selector model would collect tests from test_rel."""
    for ign in selector.get("ignores") or []:
        if _path_under(test_rel, ign):
            return False
    paths = selector.get("paths") or []
    for sel in paths:
        if sel in {".", ""}:
            # bare pytest at repo root — collects everywhere pytest would; treat as full-tree
            return True
        if _path_under(test_rel, sel) or _path_under(sel, test_rel):
            # file matches directory selector, or selector is exact file / parent
            return True
        # selector may be a single file equal to test
        if test_rel == sel:
            return True
    return False


def _path_under(child: str, parent: str) -> bool:
    child = child.replace("\\", "/").rstrip("/")
    parent = parent.replace("\\", "/").rstrip("/")
    if parent in {".", ""}:
        return True
    if child == parent:
        return True
    return child.startswith(parent + "/")


def extract_ci_pytest_steps() -> list[dict[str, Any]]:
    """Enumerate CI run steps that invoke pytest / python test_*.py."""
    wf_dir = REPO / ".github" / "workflows"
    steps: list[dict[str, Any]] = []
    for yml in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        doc = load_workflow(yml)
        jobs = doc.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        wf_rel = rel(yml)
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            defaults = (job.get("defaults") or {}).get("run") or {}
            default_wd = defaults.get("working-directory") or "."
            for idx, step in enumerate(job.get("steps") or []):
                if not isinstance(step, dict):
                    continue
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                if "pytest" not in run and not _PY_TEST_FILE.search(run):
                    continue
                wd = step.get("working-directory") or default_wd or "."
                invocations: list[dict[str, Any]] = []
                for line in _split_shell_lines(run):
                    inv = parse_pytest_invocation(line, wd)
                    if inv:
                        invocations.append(inv)
                if not invocations:
                    continue
                step_id = f"{wf_rel}::{job_id}::step{idx}"
                steps.append(
                    {
                        "step_id": step_id,
                        "workflow": wf_rel,
                        "job": job_id,
                        "step_index": idx,
                        "name": step.get("name"),
                        "working_directory": wd,
                        "invocations": invocations,
                        "raw_run": run,
                    }
                )
    return steps


def node_id_to_file(node_id: str, working_directory: str) -> str | None:
    """Map a pytest node id to a repo-relative file path."""
    node_id = node_id.strip()
    if not node_id or node_id.startswith("=") or " error" in node_id.lower():
        return None
    # skip summary lines
    if re.match(r"^\d+ (tests?|items?) collected", node_id):
        return None
    if re.match(r"^\d+ (passed|failed|error|skipped)", node_id):
        return None
    file_part = node_id.split("::", 1)[0].strip()
    if not file_part.endswith(".py"):
        return None
    return _resolve_selector_path(file_part, working_directory)


def parse_collect_only_output(text: str, working_directory: str) -> list[str]:
    files: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # pytest -q collect-only prints node ids one per line, then summary
        f = node_id_to_file(line, working_directory)
        if f:
            files.add(f)
    return sorted(files)


def ast_selfcheck() -> None:
    """Cheap sanity: planted orphan path parses as a module with one test."""
    src = (REPO / PLANTED_ORPHAN).read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert any(
        isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in tree.body
    )
