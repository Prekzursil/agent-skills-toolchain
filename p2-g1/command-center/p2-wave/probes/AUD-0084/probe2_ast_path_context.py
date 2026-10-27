#!/usr/bin/env python3
"""AUD-0084 probe 2 (verifier, AST-aware): distinguishes a path literal used in
a path context (open()/Path()/subprocess) from a regex or a documentation
string. A backslash in a regex is not a path separator; a docstring mentioning
C: is not a hardcoded path. use-vs-mention control asserted on one fixture."""
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "probe2_ast_path_context_out.json"

BS = chr(92)
PATH_FUNCS = {"open", "Path", "chdir", "listdir", "stat", "unlink", "mkdir",
              "makedirs", "remove", "run", "Popen", "check_output", "exec"}
ABS_SHAPES = ("C:" + BS, "D:" + BS, "/home/", "/Users/", "/etc/", "/var/", "/usr/")


def is_pathish(value: str) -> bool:
    return any(value.startswith(s) for s in ABS_SHAPES)


def scan_text(source: str) -> list:
    findings = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in PATH_FUNCS:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if is_pathish(arg.value):
                            findings.append({"line": node.lineno, "context": "call:" + str(name),
                                             "value": arg.value[:80]})
    return findings


def scan_file(p: Path) -> list:
    try:
        return scan_text(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


def build_fixture() -> str:
    doc3 = chr(39) * 3
    lines = [
        "import re",
        "DOC = " + doc3 + "docstring mentions C:" + BS + "temp but is not a path use" + doc3,
        'RX = re.compile("a' + BS + BS + 'd+' + BS + BS + 'b+")',
        "def uses(open):",
        '    return open(r"C:' + BS + 'temp' + BS + 'x.txt")',
        "",
    ]
    return chr(10).join(lines)


def fixture_control() -> dict:
    fixture = HERE / "fixture_ast_probe.py"
    fixture.write_text(build_fixture(), encoding="utf-8")
    hits = scan_file(fixture)
    flagged = [h for h in hits if h["context"].startswith("call:")]
    ok = len(flagged) == 1 and "x.txt" in flagged[0]["value"]
    return {"hits": hits, "flagged_calls": flagged, "pass": bool(ok)}


def corpus_scan() -> dict:
    per_file: dict = {}
    for scope in ["platform", "tools", "scripts", "hooks", "ci"]:
        base = REPO / scope
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in base.walk():
            dirnames[:] = [d for d in dirnames
                           if d not in {"node_modules", "__pycache__", ".git", "fixtures"}]
            for fn in filenames:
                if fn.endswith(".py"):
                    p = Path(dirpath) / fn
                    hits = scan_file(p)
                    if hits:
                        per_file[p.resolve().relative_to(REPO).as_posix()] = hits[:10]
    return per_file


def main() -> int:
    control = fixture_control()
    per_file = corpus_scan()
    total = sum(len(v) for v in per_file.values())
    result = {
        "probe": "probe2-ast-path-context",
        "files_with_path_context_hits": len(per_file),
        "total_call_context_hits": total,
        "top_files": sorted(per_file.items(), key=lambda kv: -len(kv[1]))[:25],
        "fixture_control": {"pass": control["pass"], "flagged": control["flagged_calls"]},
        "pass": bool(control["pass"]),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("corpus_hits=%d files=%d fixture_flagged=%s" % (total, len(per_file), control["pass"]))
    print("SUCCESS:AUD-0084-probe2 AST path-context census" if result["pass"]
          else "FAILED:AUD-0084-probe2 use-vs-mention control")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
