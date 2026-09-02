#!/usr/bin/env python3
"""Second-control-plane gate (WFA-0056).

Fails when an acquired or fused workflow introduces a second orchestration
control plane: a torn-down runtime imported wholesale, declared as a new
dependency that owns execution order, vendored without a manifest line, or
spawned as a scheduler/state-store process.

Mechanisms may be extracted and reimplemented on this estate's plane.
The seven torn-down runtimes may not be imported wholesale.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

CHOSEN_PLANE_ID = "ast-integrate-command-center"
CHOSEN_PLANE_NAME = "ast-integrate command-center / Claude-Code workflow plane"

# Import prefixes and process basenames are exact top-level tokens, not substrings.
RUNTIMES: tuple[dict, ...] = (
    {
        "id": "langgraph",
        "name": "LangGraph",
        "import_prefixes": ("langgraph",),
        "pypi": ("langgraph",),
        "npm": ("langgraph", "@langchain/langgraph"),
        "process_names": ("langgraph",),
        "owns": "execution_order",
        "second_plane_if": (
            "imported wholesale as the graph executor rather than reimplemented "
            "as IR stages on the chosen plane"
        ),
    },
    {
        "id": "crewai",
        "name": "CrewAI",
        "import_prefixes": ("crewai",),
        "pypi": ("crewai", "crewai-tools"),
        "npm": ("crewai",),
        "process_names": ("crewai",),
        "owns": "execution_order",
        "second_plane_if": (
            "imported wholesale as a crew/process runtime rather than mapped to "
            "IR roles and barriers"
        ),
    },
    {
        "id": "autogen",
        "name": "AutoGen",
        "import_prefixes": (
            "autogen",
            "autogen_agentchat",
            "autogen_core",
            "autogen_ext",
            "pyautogen",
            "ag2",
        ),
        "pypi": (
            "pyautogen",
            "autogen",
            "autogen-agentchat",
            "ag2",
            "ag2-agentchat",
        ),
        "npm": ("autogen", "@autogen/core"),
        "process_names": ("autogen",),
        "owns": "execution_order",
        "second_plane_if": (
            "imported wholesale as a conversable-agent runtime rather than "
            "reimplemented as IR turn policy"
        ),
    },
    {
        "id": "temporal",
        "name": "Temporal",
        "import_prefixes": ("temporalio", "temporal"),
        "pypi": ("temporalio", "temporal-sdk"),
        "npm": ("@temporalio/client", "@temporalio/worker", "temporalio"),
        "process_names": ("temporal", "temporal-server", "temporalio"),
        "owns": "scheduler_process",
        "second_plane_if": (
            "a Temporal server/worker process or SDK that owns workflow history "
            "and execution order"
        ),
    },
    {
        "id": "airflow",
        "name": "Airflow",
        "import_prefixes": ("airflow",),
        "pypi": ("apache-airflow", "airflow"),
        "npm": ("apache-airflow",),
        "process_names": (
            "airflow",
            "airflow-scheduler",
            "airflow-webserver",
            "airflow-worker",
        ),
        "owns": "scheduler_process",
        "second_plane_if": (
            "an Airflow scheduler/webserver/worker process or apache-airflow "
            "dependency that owns DAG execution order"
        ),
    },
    {
        "id": "prefect",
        "name": "Prefect",
        "import_prefixes": ("prefect",),
        "pypi": ("prefect",),
        "npm": ("@prefecthq/prefect", "prefect"),
        "process_names": ("prefect", "prefect-server"),
        "owns": "scheduler_process",
        "second_plane_if": (
            "a Prefect server/agent process or prefect package that owns flow "
            "execution order"
        ),
    },
    {
        "id": "dagster",
        "name": "Dagster",
        "import_prefixes": ("dagster", "dagster_graphql", "dagster_webserver"),
        "pypi": ("dagster", "dagster-webserver", "dagit"),
        "npm": ("dagster",),
        "process_names": (
            "dagster",
            "dagster-webserver",
            "dagster-daemon",
            "dagit",
        ),
        "owns": "state_store",
        "second_plane_if": (
            "a Dagster daemon/webserver process or dagster package that owns "
            "run storage and execution order"
        ),
    },
)

def _norm_pkg(name: str) -> str:
    return name.strip().lower().replace("_", "-")


SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)
PY_SUFFIXES = frozenset({".py", ".pyi"})
JS_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx"})
MANIFEST_NAMES = frozenset(
    {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements.in",
        "pyproject.toml",
        "setup.cfg",
        "Pipfile",
        "package.json",
        "environment.yml",
        "environment.yaml",
        "go.mod",
        "Cargo.toml",
    }
)

_IMPORT_INDEX = {
    prefix: rt for rt in RUNTIMES for prefix in rt["import_prefixes"]
}
_PYPI_INDEX = {
    _norm_pkg(name): rt for rt in RUNTIMES for name in rt["pypi"]
}
_NPM_INDEX = {name.lower(): rt for rt in RUNTIMES for name in rt["npm"]}
_PROC_INDEX = {
    name.lower(): rt for rt in RUNTIMES for name in rt["process_names"]
}


def runtime_ids() -> list[str]:
    return [rt["id"] for rt in RUNTIMES]


def runtime_by_id(runtime_id: str) -> dict:
    for rt in RUNTIMES:
        if rt["id"] == runtime_id:
            return rt
    raise KeyError(runtime_id)


@dataclass
class Finding:
    runtime_id: str
    control_plane: str
    channel: str
    kind: str
    path: str
    detail: str
    allowlisted: bool = False
    approval_id: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class GateResult:
    fired: bool
    silent: bool
    named_planes: list[str]
    findings: list[Finding] = field(default_factory=list)
    allowlist_hits: list[dict] = field(default_factory=list)
    chosen_plane_id: str = CHOSEN_PLANE_ID
    chosen_plane_name: str = CHOSEN_PLANE_NAME

    def as_dict(self) -> dict:
        return {
            "fired": self.fired,
            "silent": self.silent,
            "gate_failed": self.fired,
            "named_planes": list(self.named_planes),
            "named_plane_count": len(self.named_planes),
            "findings": [f.as_dict() for f in self.findings],
            "allowlist_hits": list(self.allowlist_hits),
            "chosen_plane_id": self.chosen_plane_id,
            "chosen_plane_name": self.chosen_plane_name,
        }


def load_allowlist(source: Path | dict | None) -> dict[str, dict]:
    if source is None:
        return {}
    if isinstance(source, dict):
        doc = source
    else:
        doc = json.loads(Path(source).read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in doc.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        rid = str(entry.get("runtime_id") or "").strip()
        approval = str(entry.get("approval_id") or "").strip()
        if not rid or not approval:
            continue
        out[rid] = {
            "runtime_id": rid,
            "approval_id": approval,
            "approver": str(entry.get("approver") or ""),
            "recorded_at": str(entry.get("recorded_at") or ""),
            "scope": str(entry.get("scope") or ""),
            "rationale": str(entry.get("rationale") or ""),
        }
    return out


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def _match_import(module: str) -> dict | None:
    if not module:
        return None
    top = module.lstrip(".").split(".")[0].replace("-", "_")
    return _IMPORT_INDEX.get(top)


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: list[tuple[dict, int, str]] = []

    def _record(self, module: str, lineno: int, how: str) -> None:
        rt = _match_import(module)
        if rt:
            self.hits.append((rt, lineno, f"{how}:{module}"))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name, node.lineno, "import")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._record(node.module, node.lineno, "from")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        if name in {"__import__", "import_module", "importlib.import_module"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                self._record(node.args[0].value, node.lineno, name)
        if name in {"Popen", "run", "call", "check_call", "check_output", "execl", "execv", "execve"}:
            for token in _string_args(node):
                base = Path(token).name.lower()
                rt = _PROC_INDEX.get(base)
                if rt:
                    self.hits.append(
                        (rt, node.lineno, f"subprocess:{token}")
                    )
        self.generic_visit(node)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _string_args(node: ast.Call) -> list[str]:
    out: list[str] = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
        elif isinstance(arg, ast.List):
            for elt in arg.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.append(elt.value)
    return out


_JS_REQUIRE = re.compile(
    r"""(?:require\s*\(\s*|from\s+|import\s+)['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def scan_imports(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_files(root):
        suffix = path.suffix.lower()
        if suffix in PY_SUFFIXES:
            findings.extend(_scan_python(root, path))
        elif suffix in JS_SUFFIXES:
            findings.extend(_scan_js(root, path))
    return findings


def _scan_python(root: Path, path: Path) -> list[Finding]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    visitor = _ImportVisitor()
    visitor.visit(tree)
    out: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for rt, lineno, detail in visitor.hits:
        key = (rt["id"], lineno, detail)
        if key in seen:
            continue
        seen.add(key)
        channel = "subprocess_source" if detail.startswith("subprocess:") else "import"
        kind = str(rt["owns"])
        out.append(
            Finding(
                runtime_id=rt["id"],
                control_plane=rt["name"],
                channel=channel,
                kind=kind,
                path=f"{_rel(root, path)}:{lineno}",
                detail=detail,
            )
        )
    return out


def _scan_js(root: Path, path: Path) -> list[Finding]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[Finding] = []
    for match in _JS_REQUIRE.finditer(src):
        spec = match.group(1)
        rt = _NPM_INDEX.get(spec.lower()) or _match_import(spec.split("/")[-1])
        if spec.startswith("@"):
            rt = _NPM_INDEX.get(spec.lower())
        if not rt:
            continue
        line = src.count("\n", 0, match.start()) + 1
        out.append(
            Finding(
                runtime_id=rt["id"],
                control_plane=rt["name"],
                channel="import",
                kind=str(rt["owns"]),
                path=f"{_rel(root, path)}:{line}",
                detail=f"js:{spec}",
            )
        )
    return out


def scan_vendored(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if root.is_file():
        return findings
    markers = ("__init__.py", "pyproject.toml", "package.json", "setup.py")
    for rt in RUNTIMES:
        names = {rt["id"], *rt["import_prefixes"], *rt["pypi"]}
        names = {n.replace("-", "_") for n in names} | {n.replace("_", "-") for n in names}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            base = Path(dirpath)
            for d in list(dirnames):
                if d not in names and d.replace("-", "_") not in {
                    n.replace("-", "_") for n in names
                }:
                    continue
                pkg = base / d
                if not any((pkg / m).exists() for m in markers):
                    continue
                findings.append(
                    Finding(
                        runtime_id=rt["id"],
                        control_plane=rt["name"],
                        channel="vendored",
                        kind=str(rt["owns"]),
                        path=_rel(root, pkg),
                        detail="vendored-package-dir",
                    )
                )
    return findings


def _split_req_name(line: str) -> str | None:
    raw = line.split("#", 1)[0].strip()
    if not raw or raw.startswith(("-", ".", "/")):
        return None
    if raw.startswith("git+") or "://" in raw:
        return None
    token = re.split(r"[=<>!~\[]", raw, maxsplit=1)[0].strip()
    token = token.split(";")[0].strip()
    if not token:
        return None
    return _norm_pkg(token)


def _parse_requirements(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        name = _split_req_name(line)
        if name:
            names.append(name)
    return names


def _parse_pyproject(text: str) -> list[str]:
    names: list[str] = []
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception:
            data = None
        if isinstance(data, dict):
            project = data.get("project") or {}
            for item in project.get("dependencies") or []:
                if isinstance(item, str):
                    parsed = _split_req_name(item)
                    if parsed:
                        names.append(parsed)
            poetry = ((data.get("tool") or {}).get("poetry") or {}).get(
                "dependencies"
            ) or {}
            if isinstance(poetry, dict):
                for key in poetry:
                    if str(key) == "python":
                        continue
                    names.append(_norm_pkg(str(key)))
            return names
    for match in re.finditer(
        r'^\s*["\']([A-Za-z0-9_.-]+)["\']\s*([<>=!~]|$)',
        text,
        re.MULTILINE,
    ):
        names.append(_norm_pkg(match.group(1)))
    return names


def _parse_package_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = data.get(key) or {}
        if isinstance(block, dict):
            names.extend(str(k) for k in block)
    return names


def _parse_pipfile(text: str) -> list[str]:
    names: list[str] = []
    current = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped.lower() in {"[packages]", "[dev-packages]"}
            continue
        if current and "=" in stripped:
            name = stripped.split("=", 1)[0].strip().strip("\"'")
            if name:
                names.append(_norm_pkg(name))
    return names


def _parse_setup_cfg(text: str) -> list[str]:
    names: list[str] = []
    in_install = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() == "install_requires =":
            in_install = True
            continue
        if in_install:
            if stripped.startswith("[") or (stripped.endswith("=") and " " not in stripped):
                in_install = False
                continue
            parsed = _split_req_name(stripped)
            if parsed:
                names.append(parsed)
    return names


def _parse_environment_yml(text: str) -> list[str]:
    names: list[str] = []
    in_deps = False
    for line in text.splitlines():
        if re.match(r"^dependencies:\s*$", line):
            in_deps = True
            continue
        if in_deps:
            if line and not line.startswith((" ", "-", "\t")):
                in_deps = False
                continue
            stripped = line.strip().lstrip("- ")
            if stripped.startswith("pip:"):
                continue
            parsed = _split_req_name(stripped)
            if parsed:
                names.append(parsed)
    return names


def _parse_go_mod(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require "):
            parts = stripped.split()
            if len(parts) >= 2:
                names.append(parts[1].lower())
    return names


def _parse_cargo(text: str) -> list[str]:
    names: list[str] = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "dependencies" in stripped.lower():
            in_deps = True
            continue
        if stripped.startswith("["):
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            name = stripped.split("=", 1)[0].strip().strip("\"'")
            if name:
                names.append(_norm_pkg(name))
    return names


def parse_manifest_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    name = path.name.lower()
    if name.startswith("requirements") and name.endswith((".txt", ".in")):
        return _parse_requirements(text)
    if name == "pyproject.toml":
        return _parse_pyproject(text)
    if name == "package.json":
        return _parse_package_json(text)
    if name == "pipfile":
        return _parse_pipfile(text)
    if name == "setup.cfg":
        return _parse_setup_cfg(text)
    if name in {"environment.yml", "environment.yaml"}:
        return _parse_environment_yml(text)
    if name == "go.mod":
        return _parse_go_mod(text)
    if name == "cargo.toml":
        return _parse_cargo(text)
    return []


def collect_declared_packages(root: Path) -> dict[str, list[str]]:
    """Map normalized package name -> originating relative paths."""
    found: dict[str, list[str]] = {}
    for path in _iter_files(root):
        if path.name.lower() == "pipfile" or path.name in MANIFEST_NAMES or (
            path.name.lower().startswith("requirements")
            and path.suffix.lower() in {".txt", ".in"}
        ):
            rel = _rel(root, path)
            for pkg in parse_manifest_file(path):
                found.setdefault(pkg, []).append(rel)
            if path.name.lower() == "package.json":
                for pkg in parse_manifest_file(path):
                    found.setdefault(pkg.lower(), []).append(rel)
    return found


def _runtime_for_declared(pkg: str) -> dict | None:
    lowered = pkg.lower()
    if lowered in _NPM_INDEX:
        return _NPM_INDEX[lowered]
    return _PYPI_INDEX.get(_norm_pkg(pkg))


def scan_manifests(root: Path, baseline: Path | None = None) -> list[Finding]:
    target = collect_declared_packages(root)
    base_pkgs: set[str] = set()
    if baseline is not None:
        base_pkgs = set(collect_declared_packages(baseline))
    findings: list[Finding] = []
    for pkg, paths in sorted(target.items()):
        if pkg in base_pkgs:
            continue
        rt = _runtime_for_declared(pkg)
        if not rt:
            continue
        findings.append(
            Finding(
                runtime_id=rt["id"],
                control_plane=rt["name"],
                channel="manifest",
                kind=str(rt["owns"]),
                path=paths[0],
                detail=f"declared:{pkg}",
            )
        )
    return findings


def _cmdline_tokens(raw: bytes) -> list[str]:
    parts = raw.split(b"\x00")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        out.append(part.decode("utf-8", "replace"))
    return out


_INTERPRETER_NAMES = frozenset(
    {
        "env",
        "python",
        "python3",
        "python3.11",
        "python3.12",
        "python3.13",
        "bash",
        "sh",
        "dash",
    }
)


def _runtime_from_process(comm: str, exe: str, tokens: list[str]) -> dict | None:
    candidates = {comm.lower(), Path(exe).name.lower()}
    if tokens:
        candidates.add(Path(tokens[0]).name.lower())
        i = 0
        while i < len(tokens):
            base = Path(tokens[i]).name.lower()
            if base in _INTERPRETER_NAMES or base.startswith("python"):
                i += 1
                continue
            if tokens[i] == "-m" and i + 1 < len(tokens):
                candidates.add(tokens[i + 1].split(".")[0].lower())
                break
            if tokens[i].startswith("-"):
                i += 1
                continue
            candidates.add(base)
            break
    for cand in candidates:
        rt = _PROC_INDEX.get(cand)
        if rt:
            return rt
        rt = _IMPORT_INDEX.get(cand.replace("-", "_"))
        if rt:
            return rt
    return None


def scan_processes(restrict_pids: Iterable[int] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return findings
    allowed = set(restrict_pids) if restrict_pids is not None else None
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if allowed is not None and pid not in allowed:
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            cmdline = _cmdline_tokens((entry / "cmdline").read_bytes())
            try:
                exe = os.readlink(entry / "exe")
            except OSError:
                exe = cmdline[0] if cmdline else comm
        except (OSError, UnicodeDecodeError):
            continue
        rt = _runtime_from_process(comm, exe, cmdline)
        if not rt:
            continue
        findings.append(
            Finding(
                runtime_id=rt["id"],
                control_plane=rt["name"],
                channel="process_table",
                kind=str(rt["owns"]),
                path=f"/proc/{pid}",
                detail=f"pid={pid} comm={comm} exe={Path(exe).name}",
            )
        )
    return findings


def evaluate(
    root: Path,
    *,
    baseline: Path | None = None,
    allowlist: Path | dict | None = None,
    observe_processes: bool = False,
    restrict_pids: Iterable[int] | None = None,
) -> GateResult:
    root = Path(root)
    findings: list[Finding] = []
    findings.extend(scan_imports(root))
    findings.extend(scan_vendored(root))
    findings.extend(scan_manifests(root, baseline=baseline))
    if observe_processes:
        findings.extend(scan_processes(restrict_pids=restrict_pids))

    allow = load_allowlist(allowlist)
    hits: list[dict] = []
    blocking: list[Finding] = []
    named: list[str] = []
    seen_names: set[str] = set()
    for finding in findings:
        entry = allow.get(finding.runtime_id)
        if entry:
            finding.allowlisted = True
            finding.approval_id = entry["approval_id"]
            hits.append(dict(entry))
        else:
            blocking.append(finding)
        if finding.control_plane not in seen_names:
            seen_names.add(finding.control_plane)
            named.append(finding.control_plane)

    # Deduplicate allowlist hits by approval_id.
    uniq_hits: list[dict] = []
    seen_ids: set[str] = set()
    for hit in hits:
        key = hit["approval_id"]
        if key in seen_ids:
            continue
        seen_ids.add(key)
        uniq_hits.append(hit)

    fired = bool(blocking)
    return GateResult(
        fired=fired,
        silent=not fired,
        named_planes=named,
        findings=findings,
        allowlist_hits=uniq_hits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WFA-0056 second-control-plane gate")
    parser.add_argument("--root", required=True, help="acquired/fused tree to inspect")
    parser.add_argument("--baseline", help="estate manifest tree to diff against")
    parser.add_argument("--allowlist", help="owner-approval allowlist JSON")
    parser.add_argument(
        "--observe-processes",
        action="store_true",
        help="also read /proc for torn-down runtime processes",
    )
    parser.add_argument("--json", action="store_true", help="print GateResult JSON")
    args = parser.parse_args(argv)
    result = evaluate(
        Path(args.root),
        baseline=Path(args.baseline) if args.baseline else None,
        allowlist=Path(args.allowlist) if args.allowlist else None,
        observe_processes=args.observe_processes,
    )
    payload = result.as_dict()
    if args.json or True:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if result.fired:
        planes = ", ".join(result.named_planes) or "(unnamed)"
        print(f"GATE-FAIL: second control plane detected: {planes}", file=sys.stderr)
        return 2
    print("GATE-OK: silent", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
