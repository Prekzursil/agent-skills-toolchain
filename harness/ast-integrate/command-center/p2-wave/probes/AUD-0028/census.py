"""AUD-0028 external CLI census and cross-shell resolvers.

Probe 1 implements PowerShell 7 Get-Command *Source* lookup (PATHEXT, .cmd/.bat/.exe).
This Linux host has no pwsh binary; the algorithm is the instrument, and that
absence is recorded rather than forged.

Probe 2 runs live Git-Bash-equivalent `command -v` via bash --noprofile --norc.

The finding is a resolved-PATH divergence, not a presence bit. The required
both-states control plants WSL-shaped and MSYS-shaped `bash` binaries on two
different PATHs so the pair cannot agree unless one probe is not actually using
its claimed resolver.

Invocation scan deliberately excludes `command-center/p2-wave/probes/` (and
other G-1 output trees). Those files are concurrent unit-delivery churn; a
full-tree walk makes tool_count a moving target and fails remesure.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "AUD-0028"
OUT_REL = "command-center/audit/AUD-0028-external-cli-tool-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0028 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which external command-line tools does the codebase invoke, is each "
    "present, at what version, and does PowerShell resolve it to a different "
    "binary than Git Bash does?"
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "dist",
        "build",
        "site-packages",
        "wheelhouse",
        "_deps",
        "source-mirror.git",
        # Directory name `probes` is the G-1 per-unit factory
        # (command-center/p2-wave/probes/<UID>/). Prune at walk time.
        "probes",
    }
)
SOURCE_SUFFIXES = frozenset(
    {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".ps1"}
)
SELF_PREFIX = "command-center/p2-wave/probes/AUD-0028/"
SELF_OUT = OUT_REL
# Volatile G-1 / unit-output trees. Sibling probe scripts keep appearing
# during the wave; counting them is what failed remesure (17 vs 18 tools).
SKIP_REL_PREFIXES = (
    "command-center/p2-wave/probes/",
    "command-center/audit/",
    "command-center/research/",
    "command-center/adversarial/",
    "command-center/receipts/",
    "command-center/confirmation/",
    "command-center/events/",
)
SCAN_SCOPE_NOTE = (
    "Product-tree census (tools/, docs/, command-center/ minus G-1 probe "
    "factory and unit output trees). Sibling probe scripts are concurrent "
    "delivery churn; including them makes tool_count non-reproducible."
)
MAX_FILE_BYTES = 1_000_000
SITES_PER_TOOL = 8
VERSION_TIMEOUT_S = 3.0
# Windows Get-Command default PATHEXT (application lookup).
PATHEXT_DEFAULT = (".COM", ".EXE", ".BAT", ".CMD", ".VBS", ".JS", ".MSC")
SUBPROCESS_ATTRS = frozenset(
    {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
)
OS_SPAWN_ATTRS = frozenset(
    {"system", "popen", "execv", "execve", "execvp", "execvpe", "spawnv", "spawnve", "spawnvp"}
)
TOOL_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._+-]*$")
CMDLET_RE = re.compile(r"^[A-Z][A-Za-z]+-[A-Z][A-Za-z]+$")
JS_SPAWN_RE = re.compile(
    r"""(?:spawn(?:Sync)?|exec(?:File|Sync)?)\(\s*['"]([A-Za-z][A-Za-z0-9._+-]*)['"]"""
)
PS_GET_RE = re.compile(
    r"""Get-Command\s+(?:-Name\s+)?['"]([A-Za-z][A-Za-z0-9._+-]*)['"]"""
)
PS_AMP_RE = re.compile(
    r"""(?:^|[\s;])&\s+['"]?([A-Za-z][A-Za-z0-9._+-]*)"""
)
# Captured once from the real host PATH so planted bash shims cannot hijack
# the command -v interpreter.
_HOST_BASH = shutil.which("bash") or "/usr/bin/bash"
SH_FIRST_RE = re.compile(
    r"""^\s*(?:(?:sudo|command|env|nohup|nice|time)\s+)*([A-Za-z][A-Za-z0-9._+-]*)\b"""
)
SHELL_BUILTINS = frozenset(
    {
        "alias",
        "bg",
        "bind",
        "break",
        "builtin",
        "caller",
        "cd",
        "command",
        "compgen",
        "complete",
        "continue",
        "declare",
        "dirs",
        "disown",
        "echo",
        "enable",
        "eval",
        "exec",
        "exit",
        "export",
        "false",
        "fc",
        "fg",
        "getopts",
        "hash",
        "help",
        "history",
        "jobs",
        "kill",
        "let",
        "local",
        "logout",
        "mapfile",
        "popd",
        "printf",
        "pushd",
        "pwd",
        "read",
        "readarray",
        "readonly",
        "return",
        "set",
        "shift",
        "shopt",
        "source",
        "suspend",
        "test",
        "times",
        "trap",
        "true",
        "type",
        "typeset",
        "ulimit",
        "umask",
        "unalias",
        "unset",
        "wait",
        "[",
    }
)
SKIP_TOOLS = frozenset(
    {
        "None",
        "True",
        "False",
        "self",
        "cls",
        "this",
        "cmd",
        "args",
        "argv",
        "kwargs",
        "executable",
        "shell",
        "check",
        "capture_output",
        "text",
        "cwd",
        "env",
        "timeout",
        "input",
        "encoding",
        "errors",
        "universal_newlines",
        "start_new_session",
        "close_fds",
        "bufsize",
        "preexec_fn",
        "pass_fds",
        "user",
        "group",
        "extra_groups",
        "umask",
        "pipesize",
        "process_group",
        "startupinfo",
        "creationflags",
        "restore_signals",
    }
)


def posix(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def rel_to_repo(path: Path, repo: Path) -> str:
    try:
        return posix(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return posix(path)


def skip_rel(rel: str) -> bool:
    rel_n = posix(rel).lstrip("./")
    if rel_n.startswith(SELF_PREFIX) or rel_n == SELF_OUT:
        return True
    for prefix in SKIP_REL_PREFIXES:
        p = prefix.rstrip("/")
        if rel_n == p or rel_n.startswith(p + "/"):
            return True
    parts = [p for p in rel_n.split("/") if p]
    return any(p in SKIP_DIR_NAMES for p in parts)


def normalize_tool(raw: str) -> str | None:
    text = (raw or "").strip().strip("\"'")
    if not text or text.startswith("$") or text.startswith("{") or text.startswith("-"):
        return None
    text = text.replace("\\", "/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if text.lower().endswith(".exe"):
        text = text[:-4]
    text = text.rstrip(".")
    if not TOOL_NAME_RE.match(text):
        return None
    if text in SKIP_TOOLS or text in SHELL_BUILTINS:
        return None
    if text.startswith("__"):
        return None
    if CMDLET_RE.match(text):
        return None
    if text[0].isupper() and text.lower() != text:
        # English / PowerShell prose, not an argv0.
        return None
    return text


def split_path(path_str: str | None) -> list[str]:
    if not path_str:
        return []
    return [p for p in path_str.split(os.pathsep) if p]


def which_pwsh() -> str | None:
    for name in ("pwsh", "pwsh.exe", "powershell", "powershell.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def get_command_source(
    name: str,
    path_str: str,
    *,
    pathext: Iterable[str] = PATHEXT_DEFAULT,
) -> str | None:
    """Windows PowerShell Get-Command application Source lookup.

    Per directory: extensionless executable first (PowerShell Core / Unix), then
    each PATHEXT candidate so a lone `git.cmd` shim wins that directory before
    Git Bash `command -v` can fall through to a later POSIX binary.
    """
    tool = normalize_tool(name) or (name or "").strip()
    if not tool:
        return None
    exts = []
    for ext in pathext:
        e = ext if str(ext).startswith(".") else f".{ext}"
        exts.append(e.upper() if e.startswith(".") else e)
    has_ext = os.path.splitext(tool)[1] != ""
    for directory in split_path(path_str):
        try:
            entries = {e.name: e for e in Path(directory).iterdir() if e.is_file()}
        except OSError:
            continue
        if has_ext:
            hit = entries.get(tool) or entries.get(tool.lower())
            if hit is not None:
                return str(hit.resolve()) if hit.exists() else str(hit)
            continue
        exact = entries.get(tool)
        if exact is not None and os.access(exact, os.X_OK):
            return str(exact.resolve())
        lower_map = {k.lower(): v for k, v in entries.items()}
        for ext in PATHEXT_DEFAULT:
            cand = lower_map.get((tool + ext).lower())
            if cand is not None:
                return str(cand.resolve())
    return None


def command_v_bash(name: str, path_str: str) -> dict[str, Any]:
    """Live `command -v` in a clean bash (Git Bash analogue on this host).

    The interpreter is always the host bash binary. PATH is the lookup space
    only — a planted `bash` shim must not become the process that runs
    `command -v`.
    """
    env = os.environ.copy()
    env["PATH"] = path_str
    env.pop("BASH_ENV", None)
    env.pop("ENV", None)
    interpreter = _HOST_BASH if os.path.isfile(_HOST_BASH) else "/usr/bin/bash"
    try:
        proc = subprocess.run(
            [interpreter, "--noprofile", "--norc", "-c", 'command -v "$1"', "_", name],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "path": None,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}:{exc}",
            "instrument": f"{interpreter} --noprofile --norc -c 'command -v \"$1\"'",
        }
    stdout = (proc.stdout or "").strip()
    line = stdout.splitlines()[0].strip() if stdout else ""
    path = None
    if line and not line.startswith("alias ") and ("/" in line or "\\" in line):
        path = line
    return {
        "ok": proc.returncode == 0 and bool(path),
        "path": path,
        "returncode": proc.returncode,
        "stdout": stdout[:400],
        "stderr": ((proc.stderr or "").strip())[:200],
        "instrument": f"{interpreter} --noprofile --norc -c 'command -v \"$1\"'",
        "interpreter": interpreter,
    }


def probe_version(resolved: str | None) -> dict[str, Any]:
    if not resolved or not os.path.isfile(resolved):
        return {"ok": False, "text": None, "reason": "unresolved"}
    last_err = "no-flag"
    for flag in ("--version", "-V", "-v"):
        try:
            proc = subprocess.run(
                [resolved, flag],
                capture_output=True,
                text=True,
                timeout=VERSION_TIMEOUT_S,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_err = f"{type(exc).__name__}"
            continue
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if text:
            first = text.splitlines()[0].strip()[:240]
            return {"ok": True, "text": first, "flag": flag, "returncode": proc.returncode}
        last_err = f"empty:{flag}:rc={proc.returncode}"
    return {"ok": False, "text": None, "reason": last_err}


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        if left:
            return f"{left}.{node.attr}"
    return None


def _first_from_list(node: ast.AST, names: dict[str, str]) -> str | None:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        raw = _const_str(node.elts[0])
        if raw:
            return raw
        first = node.elts[0]
        if isinstance(first, ast.Name) and first.id in names:
            return names[first.id]
        if isinstance(first, ast.Name) and first.id == "sys":
            return None
        dotted = _dotted(first)
        if dotted in {"sys.executable", "sys.prefix"}:
            return "python3"
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    return _const_str(node)


class _PyExtract(ast.NodeVisitor):
    def __init__(self) -> None:
        self.str_names: dict[str, str] = {}
        self.list_names: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.hits: list[tuple[int, str, str]] = []

    def _bind(self, target: ast.AST, value: ast.AST) -> None:
        if not isinstance(target, ast.Name):
            return
        raw = _const_str(value)
        if raw:
            self.str_names[target.id] = raw
            return
        if isinstance(value, (ast.List, ast.Tuple)) and value.elts:
            first = _const_str(value.elts[0])
            if first:
                self.list_names[target.id] = first

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            self._bind(t, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._bind(node.target, node.value)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.aliases[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            self.aliases[local] = f"{mod}.{alias.name}" if mod else alias.name
        self.generic_visit(node)

    def _record(self, lineno: int, raw: str | None, kind: str) -> None:
        tool = normalize_tool(raw or "")
        if tool:
            self.hits.append((lineno, tool, kind))

    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func) or ""
        resolved = self.aliases.get(dotted.split(".")[0], "")
        if dotted.startswith("shutil.which") or dotted == "which":
            if node.args:
                self._record(node.lineno, _const_str(node.args[0]), "shutil.which")
        attr = dotted.split(".")[-1] if dotted else ""
        is_sub = dotted.startswith("subprocess.") and attr in SUBPROCESS_ATTRS
        is_os = dotted.startswith("os.") and attr in OS_SPAWN_ATTRS
        alias_full = self.aliases.get(dotted, dotted)
        if alias_full.startswith("subprocess.") and alias_full.split(".")[-1] in SUBPROCESS_ATTRS:
            is_sub = True
        if alias_full.startswith("os.") and alias_full.split(".")[-1] in OS_SPAWN_ATTRS:
            is_os = True
        if is_sub or is_os:
            raw = None
            kind = "subprocess" if is_sub else "os-spawn"
            if node.args:
                arg0 = node.args[0]
                raw = _first_from_list(arg0, {**self.str_names, **self.list_names})
                if raw is None:
                    raw = _const_str(arg0)
                    if raw and (" " in raw or "\t" in raw):
                        token = raw.strip().split()[0]
                        raw = token
                        kind = kind + "+shell-string"
            for kw in node.keywords:
                if kw.arg == "executable":
                    self._record(node.lineno, _const_str(kw.value), "executable=")
            if isinstance(node.func, ast.Name) and node.func.id in self.aliases:
                pass
            self._record(node.lineno, raw, kind)
        self.generic_visit(node)


def extract_python(path: Path) -> list[tuple[int, str, str]]:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    visitor = _PyExtract()
    visitor.visit(tree)
    return visitor.hits


def extract_js(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        for match in JS_SPAWN_RE.finditer(line):
            tool = normalize_tool(match.group(1))
            if tool:
                hits.append((i, tool, "js-spawn"))
    return hits


def extract_shell(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = SH_FIRST_RE.match(stripped)
        if not match:
            continue
        tool = normalize_tool(match.group(1))
        if tool:
            hits.append((i, tool, "shell"))
    return hits


def extract_ps1(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        for match in PS_GET_RE.finditer(line):
            tool = normalize_tool(match.group(1))
            if tool:
                hits.append((i, tool, "ps-get-command"))
        if "Get-Command" in line:
            continue
        for match in PS_AMP_RE.finditer(line):
            tool = normalize_tool(match.group(1))
            if tool and tool.lower() not in {"if", "foreach", "function", "param", "switch"}:
                hits.append((i, tool, "ps-call"))
    return hits


def iter_source_files(repo: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(repo):
        base = Path(dirpath)
        rel_dir = rel_to_repo(base, repo)
        if skip_rel(rel_dir):
            dirnames[:] = []
            continue
        if rel_dir in {".", ""}:
            child_prefix = ""
        else:
            child_prefix = rel_dir.rstrip("/") + "/"
        kept: list[str] = []
        for d in dirnames:
            if d in SKIP_DIR_NAMES or d.startswith("."):
                continue
            if skip_rel(child_prefix + d):
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            path = base / name
            rel = rel_to_repo(path, repo)
            if skip_rel(rel):
                continue
            suffix = path.suffix.lower()
            if suffix not in SOURCE_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def scan_invocations(repo: Path) -> dict[str, Any]:
    by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    files = 0
    raw_hits = 0
    for path in iter_source_files(repo):
        files += 1
        rel = rel_to_repo(path, repo)
        suffix = path.suffix.lower()
        if suffix == ".py":
            hits = extract_python(path)
        elif suffix in {".js", ".mjs", ".cjs", ".ts"}:
            hits = extract_js(path)
        elif suffix == ".ps1":
            hits = extract_ps1(path)
        else:
            hits = extract_shell(path)
        for lineno, tool, kind in hits:
            if tool in SHELL_BUILTINS:
                continue
            raw_hits += 1
            bucket = by_tool[tool]
            if len(bucket) < SITES_PER_TOOL:
                bucket.append({"path": rel, "line": lineno, "kind": kind})
            elif not any(s.get("truncated") for s in bucket):
                bucket.append({"truncated": True, "extra": 1})
            else:
                for s in bucket:
                    if s.get("truncated"):
                        s["extra"] = int(s.get("extra") or 0) + 1
                        break
    tools = []
    for name in sorted(by_tool):
        sites = [s for s in by_tool[name] if not s.get("truncated")]
        extra = sum(int(s.get("extra") or 0) for s in by_tool[name] if s.get("truncated"))
        tools.append(
            {
                "tool": name,
                "site_count": len(sites) + extra,
                "sites": sites,
                "sites_truncated": extra,
            }
        )
    return {
        "files_scanned": files,
        "hit_count": raw_hits,
        "tool_count": len(tools),
        "tools": tools,
        "scan_scope": {
            "exclude_prefixes": list(SKIP_REL_PREFIXES),
            "note": SCAN_SCOPE_NOTE,
        },
    }


def host_path() -> str:
    return os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin"


def resolve_pair(tool: str, path_str: str) -> dict[str, Any]:
    gc = get_command_source(tool, path_str)
    cv = command_v_bash(tool, path_str)
    cv_path = cv.get("path")
    lexical_div = bool(gc and cv_path and posix(gc) != posix(str(cv_path)))
    real_gc = os.path.realpath(gc) if gc else None
    real_cv = os.path.realpath(str(cv_path)) if cv_path else None
    real_same = bool(real_gc and real_cv and real_gc == real_cv)
    presence = (gc is not None, bool(cv_path))
    return {
        "tool": tool,
        "get_command_source": gc,
        "command_v": cv_path,
        "command_v_meta": {
            "ok": cv.get("ok"),
            "returncode": cv.get("returncode"),
            "instrument": cv.get("instrument"),
            "stderr": cv.get("stderr"),
        },
        "present_get_command": gc is not None,
        "present_command_v": bool(cv_path),
        "presence_disagreement": presence[0] != presence[1],
        "path_divergence": lexical_div,
        "realpath_same": real_same,
        "version": probe_version(gc or (str(cv_path) if cv_path else None)),
    }


def write_shim(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def plant_shells(tmpdir: Path) -> dict[str, str]:
    wsl_bash = tmpdir / "wsl" / "usr" / "bin" / "bash"
    msys_bash = tmpdir / "msys" / "usr" / "bin" / "bash"
    shim_git = tmpdir / "shim" / "git.cmd"
    write_shim(
        wsl_bash,
        "#!/bin/sh\n# AUD-0028 planted WSL-shaped bash (distinct inode/path)\n"
        "echo AUD-0028-wsl-bash\nexit 0\n",
    )
    write_shim(
        msys_bash,
        "#!/bin/sh\n# AUD-0028 planted MSYS-shaped bash (distinct inode/path)\n"
        "echo AUD-0028-msys-bash\nexit 0\n",
    )
    shim_git.parent.mkdir(parents=True, exist_ok=True)
    shim_git.write_text(
        "@echo off\r\nREM AUD-0028 PATHEXT git.cmd shim — command -v misses this name\r\n"
        "echo AUD-0028-git-cmd-shim\r\n",
        encoding="utf-8",
    )
    wsl_bin = str(wsl_bash.parent)
    msys_bin = str(msys_bash.parent)
    shim_dir = str(shim_git.parent)
    host = host_path()
    return {
        "wsl_bash": str(wsl_bash.resolve()),
        "msys_bash": str(msys_bash.resolve()),
        "git_cmd": str(shim_git.resolve()),
        "wsl_bin": wsl_bin,
        "msys_bin": msys_bin,
        "shim_dir": shim_dir,
        "probe1_path": os.pathsep.join([wsl_bin, shim_dir, host]),
        "probe2_path": os.pathsep.join([msys_bin, shim_dir, host]),
        "same_path": os.pathsep.join([wsl_bin, shim_dir, host]),
    }


def both_states_control() -> dict[str, Any]:
    """Plant WSL vs MSYS bash and a .cmd shim; require PATH divergence.

    Naive same-resolver/same-PATH pair must AGREE on bash (the known-bad
    state). Production pair must DISAGREE.
    """
    with tempfile.TemporaryDirectory(prefix="aud0028-") as td:
        planted = plant_shells(Path(td))
        p1_bash = get_command_source("bash", planted["probe1_path"])
        p2_bash = command_v_bash("bash", planted["probe2_path"]).get("path")
        naive_a = command_v_bash("bash", planted["same_path"]).get("path")
        naive_b = command_v_bash("bash", planted["same_path"]).get("path")
        git_gc = get_command_source("git", planted["probe1_path"])
        git_cv = command_v_bash("git", planted["probe2_path"]).get("path")
        bash_div = bool(p1_bash and p2_bash and posix(p1_bash) != posix(str(p2_bash)))
        naive_agree = bool(naive_a and naive_b and posix(str(naive_a)) == posix(str(naive_b)))
        git_div = bool(git_gc and git_cv and posix(git_gc) != posix(str(git_cv)))
        git_cmd_hit = bool(git_gc and git_gc.lower().endswith(".cmd"))
        git_cv_not_cmd = bool(git_cv and not str(git_cv).lower().endswith(".cmd"))
        passed = bash_div and naive_agree and git_div and git_cmd_hit and git_cv_not_cmd
        return {
            "pass": passed,
            "planted": {
                "wsl_bash": planted["wsl_bash"],
                "msys_bash": planted["msys_bash"],
                "git_cmd": planted["git_cmd"],
            },
            "production": {
                "probe1_get_command_bash": p1_bash,
                "probe2_command_v_bash": p2_bash,
                "bash_paths_differ": bash_div,
                "probe1_get_command_git": git_gc,
                "probe2_command_v_git": git_cv,
                "git_paths_differ": git_div,
                "git_cmd_shim_won_get_command": git_cmd_hit,
                "git_bash_resolved_non_cmd": git_cv_not_cmd,
            },
            "naive_same_path_command_v": {
                "a": naive_a,
                "b": naive_b,
                "agree": naive_agree,
                "note": (
                    "Both lookups used command -v on the same PATH. Agreement "
                    "proves a same-shell pair cannot satisfy the WSL-versus-MSYS "
                    "bash control."
                ),
            },
        }


def live_host_resolutions(tools: list[str]) -> list[dict[str, Any]]:
    path = host_path()
    rows = [resolve_pair(tool, path) for tool in tools]
    rows.sort(key=lambda r: r["tool"])
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    div = [r for r in rows if r.get("path_divergence")]
    presence = [r for r in rows if r.get("presence_disagreement")]
    present_both = [
        r for r in rows if r.get("present_get_command") and r.get("present_command_v")
    ]
    missing_both = [
        r
        for r in rows
        if not r.get("present_get_command") and not r.get("present_command_v")
    ]
    return {
        "resolved_tool_count": len(rows),
        "present_both": len(present_both),
        "missing_both": len(missing_both),
        "path_divergence_count": len(div),
        "presence_disagreement_count": len(presence),
        "path_divergences": [
            {
                "tool": r["tool"],
                "get_command_source": r.get("get_command_source"),
                "command_v": r.get("command_v"),
                "realpath_same": r.get("realpath_same"),
            }
            for r in div[:40]
        ],
        "presence_disagreements": [
            {
                "tool": r["tool"],
                "get_command_source": r.get("get_command_source"),
                "command_v": r.get("command_v"),
            }
            for r in presence[:40]
        ],
    }


def probe1_live(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    scan = scan_invocations(repo)
    names = [t["tool"] for t in scan["tools"]]
    if "bash" not in names:
        names.append("bash")
    if "git" not in names:
        names.append("git")
    rows = live_host_resolutions(sorted(set(names)))
    control = both_states_control()
    pwsh = which_pwsh()
    summary = summarize_rows(rows)
    passed = bool(control.get("pass")) and int(scan.get("tool_count") or 0) > 0
    return {
        "probe": "probe1-pwsh-get-command-source",
        "unit_id": UID,
        "pass": passed,
        "pwsh": {"present": pwsh is not None, "path": pwsh},
        "instrument": (
            "Get-Command Source lookup with Windows PATHEXT "
            f"{list(PATHEXT_DEFAULT)}; pwsh binary "
            f"{'at ' + pwsh if pwsh else 'absent on this Linux host'}"
        ),
        "scan": {
            "files_scanned": scan["files_scanned"],
            "hit_count": scan["hit_count"],
            "tool_count": scan["tool_count"],
            "scan_scope": scan.get("scan_scope"),
        },
        "summary": summary,
        "control": {
            "pass": control.get("pass"),
            "bash_paths_differ": control["production"]["bash_paths_differ"],
            "git_paths_differ": control["production"]["git_paths_differ"],
            "naive_agree": control["naive_same_path_command_v"]["agree"],
            "git_cmd_shim_won_get_command": control["production"][
                "git_cmd_shim_won_get_command"
            ],
        },
        "control_detail": control,
        "resolutions": rows,
    }


def probe2_live(repo: Path | None = None) -> dict[str, Any]:
    """Independent of probe 1: re-scan and resolve only via bash command -v."""
    repo = repo or REPO
    scan = scan_invocations(repo)
    names = [t["tool"] for t in scan["tools"]]
    if "bash" not in names:
        names.append("bash")
    if "git" not in names:
        names.append("git")
    path = host_path()
    rows = []
    for tool in sorted(set(names)):
        cv = command_v_bash(tool, path)
        rows.append(
            {
                "tool": tool,
                "command_v": cv.get("path"),
                "present": bool(cv.get("path")),
                "returncode": cv.get("returncode"),
                "version": probe_version(cv.get("path")),
            }
        )
    control = both_states_control()
    bash_row = next((r for r in rows if r["tool"] == "bash"), None)
    passed = bool(control.get("pass")) and int(scan.get("tool_count") or 0) > 0
    return {
        "probe": "probe2-gitbash-command-v",
        "unit_id": UID,
        "pass": passed,
        "instrument": "bash --noprofile --norc -c 'command -v \"$1\"'",
        "scan": {
            "files_scanned": scan["files_scanned"],
            "hit_count": scan["hit_count"],
            "tool_count": scan["tool_count"],
            "tools": scan["tools"],
            "scan_scope": scan.get("scan_scope"),
        },
        "host_bash_command_v": (bash_row or {}).get("command_v"),
        "summary": {
            "resolved_tool_count": len(rows),
            "present": sum(1 for r in rows if r.get("present")),
            "absent": sum(1 for r in rows if not r.get("present")),
        },
        "control": {
            "pass": control.get("pass"),
            "bash_paths_differ": control["production"]["bash_paths_differ"],
            "git_paths_differ": control["production"]["git_paths_differ"],
            "naive_agree": control["naive_same_path_command_v"]["agree"],
            "git_bash_resolved_non_cmd": control["production"]["git_bash_resolved_non_cmd"],
        },
        "control_detail": control,
        "resolutions": rows,
    }


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True)
