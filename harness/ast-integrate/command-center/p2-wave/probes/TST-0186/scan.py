#!/usr/bin/env python3
"""Static scan of command-construction sites for inlined prose.

A hit is a string/template that puts commit/PR/prompt prose on a command
line (git commit -m, gh --body without --body-file, --prompt without
--prompt-file). File-flag forms are silent.

Both-states: fixtures/inline_sites.py must fire; production runner,
consumers, and tools/lib/codex-invocation.mjs must be silent.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Production SUT plus the catalog-named runner module.
PRODUCTION_PATHS = [
    HERE / "runner.py",
    HERE / "consumers.py",
    REPO / "tools" / "lib" / "codex-invocation.mjs",
]
MUTANT_PATH = HERE / "fixtures" / "inline_sites.py"
CLEAN_FIXTURE = HERE / "fixtures" / "file_sites.py"

COMMIT_DASH_M = re.compile(r"\bgit(?:\s+|['\"+])commit\b.*\s-m\b", re.DOTALL)
COMMIT_M_JOINED = re.compile(r"commit['\"\s]+-m\b")
BODY_INLINE = re.compile(r"--body(?!-file)\b")
PROMPT_INLINE = re.compile(r"--prompt(?!-file)\b")
BASH_C_INTERP = re.compile(r"bash\s+-c\s+.*\{(?:message|body|prompt|prose|payload)\}")


def _strings_from_python(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((getattr(node, "lineno", 1), node.value))
        elif isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                else:
                    parts.append("{expr}")
            out.append((getattr(node, "lineno", 1), "".join(parts)))
    return out


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        if "//" in line:
            line = line[: line.index("//")]
        lines.append(line)
    return "\n".join(lines)


def classify_blob(blob: str) -> list[str]:
    hits: list[str] = []
    if COMMIT_DASH_M.search(blob) or COMMIT_M_JOINED.search(blob):
        if "-F" not in blob and "--file" not in blob:
            hits.append("inline-commit-m")
        elif re.search(r"\s-m\b", blob):
            hits.append("inline-commit-m")
    if BODY_INLINE.search(blob):
        hits.append("inline-pr-body")
    if PROMPT_INLINE.search(blob):
        hits.append("inline-prompt")
    if BASH_C_INTERP.search(blob):
        hits.append("inline-bash-c-interpolation")
    return hits


def scan_file(path: Path) -> list[dict]:
    if not path.is_file():
        return [
            {
                "path": str(path),
                "line": 0,
                "hits": ["missing-file"],
                "snippet": "",
            }
        ]
    text = path.read_text(encoding="utf-8")
    findings: list[dict] = []
    rel = _rel(path)
    if path.suffix == ".py":
        for lineno, blob in _strings_from_python(text):
            hits = classify_blob(blob)
            if hits:
                findings.append(
                    {
                        "path": rel,
                        "line": lineno,
                        "hits": hits,
                        "snippet": blob[:160].replace("\n", "\\n"),
                    }
                )
        return findings
    # JS / shell / other: comment-stripped text, line-oriented plus whole-file.
    stripped = _strip_js_comments(text) if path.suffix in {".js", ".mjs"} else text
    for lineno, line in enumerate(stripped.splitlines(), 1):
        hits = classify_blob(line)
        if hits:
            findings.append(
                {
                    "path": rel,
                    "line": lineno,
                    "hits": hits,
                    "snippet": line.strip()[:160],
                }
            )
    return findings


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def scan_production() -> dict:
    findings = []
    for path in PRODUCTION_PATHS:
        findings.extend(scan_file(path))
    extra_tools = REPO / "tools"
    for path in extra_tools.rglob("*"):
        if path.suffix.lower() not in {".py", ".js", ".mjs", ".sh"}:
            continue
        if path.resolve() in {p.resolve() for p in PRODUCTION_PATHS if p.is_file()}:
            continue
        findings.extend(scan_file(path))
    return {
        "findings": findings,
        "n": len(findings),
        "ok": len(findings) == 0,
        "roots": [_rel(p) for p in PRODUCTION_PATHS] + ["tools/"],
    }


def scan_mutant() -> dict:
    findings = scan_file(MUTANT_PATH)
    kinds = {h for row in findings for h in row["hits"]}
    needed = {"inline-commit-m", "inline-pr-body", "inline-prompt"}
    return {
        "findings": findings,
        "n": len(findings),
        "kinds": sorted(kinds),
        "ok": needed <= kinds,
        "path": _rel(MUTANT_PATH),
    }


def scan_clean_fixture() -> dict:
    findings = scan_file(CLEAN_FIXTURE)
    return {
        "findings": findings,
        "n": len(findings),
        "ok": len(findings) == 0,
        "path": _rel(CLEAN_FIXTURE),
    }


def run_scan() -> dict:
    prod = scan_production()
    mutant = scan_mutant()
    clean = scan_clean_fixture()
    return {
        "production": prod,
        "mutant": mutant,
        "clean_fixture": clean,
        "both_states": bool(prod["ok"] and mutant["ok"] and clean["ok"]),
        "ok": bool(prod["ok"] and mutant["ok"] and clean["ok"]),
    }


def main() -> int:
    rec = run_scan()
    print(
        json.dumps(
            {
                "ok": rec["ok"],
                "production_n": rec["production"]["n"],
                "mutant_n": rec["mutant"]["n"],
                "mutant_kinds": rec["mutant"]["kinds"],
                "clean_n": rec["clean_fixture"]["n"],
            },
            sort_keys=True,
        )
    )
    if not rec["ok"]:
        print("FAILED:TST-0186-scan")
        if rec["production"]["findings"]:
            print(json.dumps(rec["production"]["findings"][:8], indent=2))
        return 1
    print("SUCCESS:TST-0186-scan production silent, mutant fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
