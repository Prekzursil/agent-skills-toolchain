#!/usr/bin/env python3
"""Shell-idiom lint for silent counting bugs in test and gate scripts.

Flags four idioms that silently produce wrong counts:

* ``grep -c ... || echo 0`` — grep -c prints 0 AND exits 1 on no match, so
  both fire and the captured count becomes ``0\\n0``.
* Unquoted ``$(...)`` in a numeric ``test``/``[``/``[[`` comparison.
* ``wc -l`` on a possibly-empty stream (pipe / stdin redirect).
* ``[ -n $x ]`` without quotes (empty x becomes ``[ -n ]``, which is true).

Does not flag the corrected forms: ``grep -c ... || true``, quoted
``"$(...)"``, non-stream ``wc -l file``, and ``[ -n "$x" ]``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv", ".tox"}
SHELL_SUFFIXES = {".sh", ".bash", ".zsh", ".ksh"}
WORKFLOW_SUFFIXES = {".yml", ".yaml"}

RE_GREP_C_OR_ECHO = re.compile(
    r"grep(?:\s+-[A-Za-z0-9]*)*\s+(?:-c|--count)\b[^|\n]*\|\|\s*echo\s+0\b"
    r"|grep(?:\s+-[A-Za-z0-9]*c[A-Za-z0-9]*)\b[^|\n]*\|\|\s*echo\s+0\b",
    re.IGNORECASE,
)
RE_UNQUOTED_SUBST = re.compile(
    r"(?:(?<!\[)\[|\[\[|\btest)\s+\$\((?!\()[^)\n]+\)\s+"
    r"-(?:eq|ne|gt|ge|lt|le)\b"
)
RE_WC_L_PIPE = re.compile(r"\|\s*wc\s+(?:-[a-zA-Z]*l[a-zA-Z]*|--lines)\b")
RE_WC_L_STDIN = re.compile(
    r"\bwc\s+(?:-[a-zA-Z]*l[a-zA-Z]*|--lines)\b\s*(?:<<|<|<<<)"
)
RE_UNQUOTED_N = re.compile(
    r"(?:(?<!\[)\[|\[\[|\btest)\s+-n\s+"
    r"(?:\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\})"
    r"(?!\s*\")"
)

IDIOM_GREP = "grep-c-or-echo-zero"
IDIOM_SUBST = "unquoted-subst-numeric"
IDIOM_WC = "wc-l-empty-stream"
IDIOM_N = "unquoted-n-test"


def _is_comment_line(line: str) -> bool:
    return line.lstrip().startswith("#")


def lint_text(text: str, path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    posix = path.replace("\\", "/")
    for idx, raw in enumerate(text.splitlines(), start=1):
        if _is_comment_line(raw):
            continue
        snippet = raw.strip()
        if not snippet:
            continue
        hits: list[str] = []
        if RE_GREP_C_OR_ECHO.search(raw):
            hits.append(IDIOM_GREP)
        if RE_UNQUOTED_SUBST.search(raw):
            hits.append(IDIOM_SUBST)
        if RE_WC_L_PIPE.search(raw) or RE_WC_L_STDIN.search(raw):
            hits.append(IDIOM_WC)
        if RE_UNQUOTED_N.search(raw):
            hits.append(IDIOM_N)
        for idiom in hits:
            findings.append(
                {
                    "path": posix,
                    "line": idx,
                    "idiom": idiom,
                    "snippet": snippet[:400],
                    "quoted": f"{posix}:{idx}: {snippet[:240]}",
                }
            )
    return findings


def lint_path(path: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    root = repo or REPO
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return lint_text(text, rel)


def is_live_gate_rel(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    if posix.startswith("command-center/p2-wave/probes/TST-0021/"):
        return False
    name = Path(posix).name.lower()
    suffix = Path(posix).suffix.lower()
    if posix.startswith(".github/workflows/") and suffix in WORKFLOW_SUFFIXES:
        return True
    if name in {"quality.yml", "quality.yaml"}:
        return True
    if suffix in SHELL_SUFFIXES:
        lowered = posix.lower()
        if (
            posix.startswith("scripts/")
            or posix.startswith("tools/")
            or posix.startswith("hooks/")
            or "/hooks/" in posix
            or "gate" in lowered
        ):
            return True
    return False


def iter_live_gate_paths(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if is_live_gate_rel(rel):
            found.append(path)
    return sorted(found)


def lint_live(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    paths = iter_live_gate_paths(root)
    findings: list[dict[str, Any]] = []
    per_script: dict[str, int] = {}
    scanned: list[str] = []
    for path in paths:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        scanned.append(rel)
        hits = lint_path(path, root)
        findings.extend(hits)
        if hits:
            per_script[rel] = len(hits)
    n = len(scanned)
    n_hit = len(per_script)
    if n == 0:
        status = "ABSENT"
    elif n_hit == 0:
        status = "GENUINE_ZERO"
    else:
        status = "FINDINGS"
    named = {
        ".github/workflows/quality.yml": (
            "present"
            if (root / ".github/workflows/quality.yml").is_file()
            else "absent"
        ),
        "rules/common/single-signal-verification.md": (
            "present"
            if (root / "rules/common/single-signal-verification.md").is_file()
            else "absent"
        ),
    }
    definition = (
        ".github/workflows/*.{yml,yaml}; quality.yml anywhere; "
        "*.sh/*.bash/*.zsh under scripts/, tools/, hooks/, or with 'gate' "
        "in the path; excluding this unit's probe fixtures"
    )
    return {
        "population_definition": definition,
        "population_status": status,
        "scripts_scanned": n,
        "scripts_with_at_least_one_idiom": n_hit,
        "scanned_paths": scanned,
        "hits_per_script": per_script,
        "findings": findings,
        "named_inputs": named,
        "population_definition": definition,
        "scripts_scanned": n,
        "scripts_with_at_least_one_idiom": n_hit,
        "scanned_paths": scanned,
        "hits_per_script": per_script,
        "named_inputs": named,
    }


def lint_fixtures(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    base = HERE / "fixtures"
    out: dict[str, Any] = {"bad": [], "good": []}
    for label, sub in (("bad", "bad"), ("good", "good")):
        folder = base / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.resolve().relative_to(root.resolve()).as_posix()
            hits = lint_path(path, root)
            out[label].append({"path": rel, "findings": hits, "count": len(hits)})
    return out


def reproduce_grep_c_or_echo_zero() -> dict[str, Any]:
    """Two-line proof: grep -c prints 0 and || echo 0 also fires."""
    bad = subprocess.run(
        "printf 'a\\n' | grep -c '^b$' || echo 0",
        shell=True,
        capture_output=True,
        text=True,
        executable="/bin/bash",
    )
    good = subprocess.run(
        'n=$(printf \'a\\n\' | grep -c \'^b$\' || true); printf \'%s\\n\' "$n"',
        shell=True,
        capture_output=True,
        text=True,
        executable="/bin/bash",
    )
    bad_lines = [ln for ln in (bad.stdout or "").splitlines() if ln != ""]
    good_lines = [ln for ln in (good.stdout or "").splitlines() if ln != ""]
    proven = bad_lines == ["0", "0"] and good_lines == ["0"]
    payload = {
        "bad_command": "printf 'a\\n' | grep -c '^b$' || echo 0",
        "bad_stdout_lines": bad_lines,
        "bad_double_zero": bad_lines == ["0", "0"],
        "good_command": (
            "n=$(printf 'a\\n' | grep -c '^b$' || true); printf '%s\\n' \"$n\""
        ),
        "good_stdout_lines": good_lines,
        "good_single_zero": good_lines == ["0"],
        "miscount_proven": proven,
        "bad_command": "printf 'a\\n' | grep -c '^b$' || echo 0",
        "bad_stdout_lines": bad_lines,
        "bad_double_zero": bad_lines == ["0", "0"],
        "good_command": (
            "n=$(printf 'a\\n' | grep -c '^b$' || true); printf '%s\\n' \"$n\""
        ),
        "good_stdout_lines": good_lines,
        "good_single_zero": good_lines == ["0"],
        "miscount_proven": proven,
    }
    return payload


def main() -> int:
    census = lint_live()
    planted = lint_fixtures()
    repro = reproduce_grep_c_or_echo_zero()
    print(json.dumps({"live": census, "fixtures": planted, "reproduction": repro}, indent=2, sort_keys=True))
    if not repro["miscount_proven"]:
        print("FAILED:TST-0021-lint reproduction did not prove the miscount")
        return 1
    return 0


# Import aliases used by emit_receipt.py / probes.
IDIOM_GREP = IDIOM_GREP
IDIOM_SUBST = IDIOM_SUBST
IDIOM_WC = IDIOM_WC
IDIOM_N = IDIOM_N
lint_path = lint_path
lint_fixtures = lint_fixtures
lint_live = lint_live


if __name__ == "__main__":
    raise SystemExit(main())
