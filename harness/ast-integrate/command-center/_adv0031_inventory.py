"""ADV-0031 step 1 - mechanical inventory of shell/argv/here-string adapter call sites.

Classifies every call site as ARGV-ARRAY (list passed to CreateProcess/execve, no shell
interpretation) or STRING-COMMAND (a single string handed to a shell / interpolated into a
shell line / a here-string body). The unit's tests_required demands these be reported
SEPARATELY, because a program that is safe only because one adapter happens to use argv
must say so.

Deterministic AST-based for Python (not regex): regex over source text cannot tell
subprocess.run([a,b]) from subprocess.run(f"{a} {b}"). For PowerShell / bash / JS there is no
AST available so those use anchored line patterns and are reported with a lower-confidence tag.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Directories that are NOT this program's own code.
EXCLUDE_PARTS = {
    "node_modules",
    "__pycache__",
    ".git",
    ".ruff_cache",
    ".pytest_cache",
    "harness-sota-2026-07-18-corpus",
    "apktool_mcp_server_workspace",
    "release",
}

SPAWN_FUNCS = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
    "getoutput",
    "getstatusoutput",
    "system",
    "popen",
    "spawnv",
    "spawnl",
    "execv",
    "execvp",
    "exec",
}


def included(p: Path) -> bool:
    return not (set(p.parts) & EXCLUDE_PARTS)


def qual(node: ast.AST) -> str:
    """Dotted name of a Call func, best-effort."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def literalness(node: ast.AST) -> str:
    """How dynamic is this expression? const / interpolated / dynamic."""
    if isinstance(node, ast.Constant):
        return "const"
    if isinstance(node, ast.JoinedStr):
        return "interpolated"  # f-string
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return "interpolated"
    if isinstance(node, ast.Call) and qual(node.func).endswith((".format", ".join")):
        return "interpolated"
    if isinstance(node, (ast.List, ast.Tuple)):
        return "argv-list"
    return "dynamic"


def scan_python(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [{"file": rel(path), "line": getattr(exc, "lineno", 0) or 0,
                 "lang": "python", "shape": "PARSE-ERROR", "detail": str(exc)}]
    lines = src.splitlines()
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = qual(node.func)
        leaf = name.split(".")[-1]
        if leaf not in SPAWN_FUNCS:
            continue
        # Only count things that look like process spawns.
        if leaf in {"exec"} and "subprocess" not in name and "os" not in name:
            continue
        if not any(tok in name for tok in ("subprocess", "os.", "sp.", "commands")):
            # bare run(...)/call(...) in a module that imported them directly
            if leaf not in {"run", "Popen", "check_output", "check_call", "call"}:
                continue
            if not re.search(
                r"from\s+subprocess\s+import|import\s+subprocess", src
            ):
                continue
        shell_true = any(
            kw.arg == "shell"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
        first = node.args[0] if node.args else None
        lit = literalness(first) if first is not None else "no-args"
        if leaf in {"system", "popen", "getoutput", "getstatusoutput"}:
            shape = "STRING-COMMAND"
            reason = f"os.{leaf} always routes through a shell"
        elif shell_true:
            shape = "STRING-COMMAND"
            reason = "shell=True"
        elif lit == "argv-list":
            shape = "ARGV-ARRAY"
            reason = "list literal, shell=False"
        elif lit in {"const", "interpolated", "dynamic"} and leaf in {
            "run", "Popen", "call", "check_call", "check_output"
        }:
            shape = "ARGV-ARRAY-DYNAMIC"
            reason = f"non-literal argv ({lit}), shell not True"
        else:
            shape = "OTHER"
            reason = lit
        out.append({
            "file": rel(path),
            "line": node.lineno,
            "lang": "python",
            "callee": name,
            "shape": shape,
            "reason": reason,
            "arg0_form": lit,
            "src": (lines[node.lineno - 1].strip()[:200] if node.lineno - 1 < len(lines) else ""),
        })
    return out


PS_STRING_CMD = [
    (r"Invoke-Expression|(?<![\w-])iex(?![\w-])", "Invoke-Expression (eval)"),
    (r"cmd(\.exe)?\s+/[ck]\s", "cmd /c string command"),
    (r"(powershell|pwsh)(\.exe)?\s+.*-(Command|c)\s", "powershell -Command string"),
    (r"-EncodedCommand", "powershell -EncodedCommand"),
    (r"Start-Process\s+.*-ArgumentList\s+[\"'][^\"']*\$", "Start-Process -ArgumentList interpolated string"),
]
PS_HERESTRING = [(r"@[\"']\s*$", "here-string open"), (r"^\s*[\"']@", "here-string close")]

SH_STRING_CMD = [
    (r"(?<![\w-])eval\s", "eval"),
    (r"(sh|bash|zsh)\s+-c\s", "sh -c string command"),
    (r"\$\(\s*[^)]*\$[{(]?[A-Za-z_]", "command substitution containing a variable"),
]

JS_STRING_CMD = [
    (r"child_process\.(exec|execSync)\s*\(", "child_process.exec/execSync (string command)"),
    (r"(?<![\w.])exec(Sync)?\s*\(\s*[`\"']", "exec/execSync with a template/string literal"),
]
JS_ARGV = [
    (r"(spawn|spawnSync|execFile|execFileSync)\s*\(", "spawn/execFile (argv array)"),
]


def scan_text(path: Path, lang: str, string_pats, argv_pats=(), extra=()) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if lang == "powershell" and stripped.startswith("#"):
            continue
        if lang in {"bash", "javascript"} and stripped.startswith(("#", "//")):
            continue
        for pat, why in string_pats:
            if re.search(pat, line):
                out.append({"file": rel(path), "line": i, "lang": lang,
                            "shape": "STRING-COMMAND", "reason": why,
                            "src": stripped[:200]})
        for pat, why in argv_pats:
            if re.search(pat, line):
                out.append({"file": rel(path), "line": i, "lang": lang,
                            "shape": "ARGV-ARRAY", "reason": why,
                            "src": stripped[:200]})
        for pat, why in extra:
            if re.search(pat, line):
                out.append({"file": rel(path), "line": i, "lang": lang,
                            "shape": "HERE-STRING", "reason": why,
                            "src": stripped[:200]})
    return out


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def main() -> int:
    findings: list[dict] = []
    counts = {"python": 0, "powershell": 0, "bash": 0, "javascript": 0}
    for path in REPO.rglob("*"):
        if not path.is_file() or not included(path):
            continue
        suf = path.suffix.lower()
        if suf == ".py":
            counts["python"] += 1
            findings += scan_python(path)
        elif suf in {".ps1", ".psm1"}:
            counts["powershell"] += 1
            findings += scan_text(path, "powershell", PS_STRING_CMD, extra=PS_HERESTRING)
        elif suf == ".sh":
            counts["bash"] += 1
            findings += scan_text(path, "bash", SH_STRING_CMD)
        elif suf in {".js", ".mjs", ".cjs"}:
            counts["javascript"] += 1
            findings += scan_text(path, "javascript", JS_STRING_CMD, JS_ARGV)

    by_shape: dict[str, int] = {}
    for f in findings:
        by_shape[f["shape"]] = by_shape.get(f["shape"], 0) + 1

    result = {
        "repo": str(REPO),
        "files_scanned": counts,
        "total_call_sites": len(findings),
        "by_shape": by_shape,
        "string_command_sites": [f for f in findings if f["shape"] == "STRING-COMMAND"],
        "here_string_sites": [f for f in findings if f["shape"] == "HERE-STRING"],
        "argv_array_sites_count": by_shape.get("ARGV-ARRAY", 0) + by_shape.get("ARGV-ARRAY-DYNAMIC", 0),
        "argv_dynamic_sites": [f for f in findings if f["shape"] == "ARGV-ARRAY-DYNAMIC"],
    }
    out = REPO / "command-center" / "_adv0031_inventory_out.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in
                      ("string_command_sites", "here_string_sites", "argv_dynamic_sites")}, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
