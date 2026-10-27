#!/usr/bin/env python3
"""Implementation census for TST-0330.

Counts live reducer implementations by the TST0330_REDUCER_ROLE marker.
Prose mentions (markdown, receipts) are not implementations. Production
tools/ and platform/ are scanned separately so a single shipped reducer
cannot be reported as a passing differential.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKER = "TST0330_REDUCER_ROLE"
ROLE_RE = re.compile(r'TST0330_REDUCER_ROLE\s*=\s*["\']([^"\']+)["\']')
CODE_SUFFIX = {".py", ".js", ".mjs", ".cjs", ".ts"}
PROD_ROOTS = ("tools", "platform", "command-center")
PROD_SKIP_PARTS = {
    "p2-wave",
    "receipts",
    "__pycache__",
    "node_modules",
    ".egg-info",
}


def _role_from_text(text: str) -> str | None:
    m = ROLE_RE.search(text)
    return m.group(1) if m else None


def scan_marked(root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CODE_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        role = _role_from_text(text)
        if not role:
            continue
        found.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "role": role,
                "bytes": path.stat().st_size,
                "marked": True,
            }
        )
    return found


def _is_skipped(rel: Path) -> bool:
    return any(part in PROD_SKIP_PARTS for part in rel.parts)


def _fn_names(path: Path) -> list[str]:
    if path.suffix != ".py":
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


INTERESTING = re.compile(
    r"(reduce_completion|completion_predicate|evaluate_completion|"
    r"judge_unit|gate_a_unit_completion)",
    re.I,
)


def scan_production() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for top in PROD_ROOTS:
        base = REPO / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIX:
                continue
            rel = path.relative_to(REPO)
            if _is_skipped(rel):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            names = _fn_names(path)
            interesting = [n for n in names if INTERESTING.search(n)]
            if MARKER in text or interesting:
                hits.append(
                    {
                        "path": rel.as_posix(),
                        "functions": interesting,
                        "marked": MARKER in text,
                    }
                )
    return hits


def mention_control() -> dict[str, Any]:
    md = HERE / "fixtures" / "mention-only.md"
    text = md.read_text(encoding="utf-8") if md.is_file() else ""
    counted = MARKER in text and md.suffix.lower() in CODE_SUFFIX
    return {
        "path": md.relative_to(REPO).as_posix() if md.is_file() else "missing",
        "exists": md.is_file(),
        "mentions_predicate_in_prose": "completion predicate" in text.lower(),
        "counted_as_implementation": counted,
    }


def census() -> dict[str, Any]:
    marked = scan_marked(HERE)
    production = scan_production()
    mention = mention_control()
    roles = sorted({m["role"] for m in marked})
    n = len(marked)
    if n < 2:
        status = "NOT-CHECKED"
        note = (
            "Fewer than two live reducer implementations; a differential "
            "would be vacuous."
        )
    else:
        status = "CHECKED"
        note = (
            f"{n} marked implementations in the TST-0330 harness "
            f"(roles={roles}). Production shipped reducers="
            f"{len(production)}."
        )
    return {
        "status": status,
        "note": note,
        "harness_implementations": marked,
        "harness_count": n,
        "roles": roles,
        "production_hits": production,
        "production_count": len(production),
        "mention_control": mention,
        "cc0003_on_disk": (REPO / "command-center" / "receipts" / "CC-0003.json").is_file(),
        "cloud_dispatcher_on_disk": False,
    }


if __name__ == "__main__":
    print(json.dumps(census(), sort_keys=True, indent=2))
