#!/usr/bin/env python3
"""AST census of datetime / sort / console / timestamped-filename sites in tools/."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIPPED_ROOT = REPO / "tools"
ABSENT_SURFACES = (
    "scripts/",
    "platform/",
    "command-center/schema/coverage-matrix.schema.json",
)

DATETIME_ATTRS = frozenset(
    {
        "now",
        "utcnow",
        "today",
        "strftime",
        "strptime",
        "fromisoformat",
        "isoformat",
        "astimezone",
        "fromtimestamp",
        "utcfromtimestamp",
        "combine",
    }
)
DATETIME_NAMES = frozenset(
    {"datetime", "date", "time", "timezone", "timedelta", "ZoneInfo", "tzset"}
)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _has_key(call: ast.Call) -> bool:
    return any(k.arg == "key" for k in call.keywords if k.arg)


def _key_repr(call: ast.Call) -> str | None:
    for k in call.keywords:
        if k.arg == "key":
            return ast.dump(k.value, include_attributes=False)[:800]
    return None


def _const_strings(node: ast.AST) -> list[str]:
    out: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append(child.value)
    return out


def _looks_like_filename_stamp(text: str) -> bool:
    markers = ("%Y", "%m", "%d", "%H", "%M", "%S", "%Y%m%d", "%Y-%m-%d")
    return any(m in text for m in markers) and (
        "/" in text or "\\" in text or text.endswith((".log", ".json", ".txt", ".bak"))
    )


def iter_shipped_py() -> list[Path]:
    paths: list[Path] = []
    for path in SHIPPED_ROOT.rglob("*.py"):
        parts = set(path.parts)
        if "__pycache__" in parts:
            continue
        if "tests" in parts:
            continue
        paths.append(path)
    return sorted(paths)


def census() -> dict[str, Any]:
    sites: list[dict[str, Any]] = []
    for path in iter_shipped_py():
        rel = path.relative_to(REPO).as_posix()
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            sites.append(
                {
                    "kind": "datetime",
                    "path": rel,
                    "lineno": 1,
                    "detail": f"unparseable:{exc.msg}",
                    "classification": "EMPTY",
                }
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in DATETIME_ATTRS or name in DATETIME_NAMES:
                    sites.append(
                        {
                            "kind": "datetime",
                            "path": rel,
                            "lineno": getattr(node, "lineno", 0),
                            "detail": name,
                            "classification": "EVIDENCED",
                        }
                    )
                if name in {"sorted", "sort"}:
                    sites.append(
                        {
                            "kind": "sort",
                            "path": rel,
                            "lineno": getattr(node, "lineno", 0),
                            "detail": name,
                            "has_explicit_key": _has_key(node),
                            "key_repr": _key_repr(node),
                            "key_uses_nfc": "NFC" in (_key_repr(node) or "")
                            or "unicodedata" in (_key_repr(node) or ""),
                            "classification": "EVIDENCED",
                        }
                    )
                if name == "print":
                    lits = _const_strings(node)
                    sites.append(
                        {
                            "kind": "console",
                            "path": rel,
                            "lineno": getattr(node, "lineno", 0),
                            "detail": "print",
                            "literals": lits[:6],
                            "classification": "EVIDENCED",
                        }
                    )
                joined = " ".join(_const_strings(node))
                if name in {"Path", "open"} and _looks_like_filename_stamp(joined):
                    sites.append(
                        {
                            "kind": "timestamped-filename",
                            "path": rel,
                            "lineno": getattr(node, "lineno", 0),
                            "detail": joined[:120],
                            "classification": "EVIDENCED",
                        }
                    )
            if isinstance(node, ast.Attribute) and node.attr in {"stdout", "stderr"}:
                parent_line = getattr(node, "lineno", 0)
                if not any(
                    s["kind"] == "console"
                    and s["path"] == rel
                    and s["lineno"] == parent_line
                    for s in sites
                ):
                    sites.append(
                        {
                            "kind": "console",
                            "path": rel,
                            "lineno": parent_line,
                            "detail": f"sys.{node.attr}",
                            "classification": "EVIDENCED",
                        }
                    )

    counts = {
        "datetime": sum(1 for s in sites if s["kind"] == "datetime"),
        "sort": sum(1 for s in sites if s["kind"] == "sort"),
        "console": sum(1 for s in sites if s["kind"] == "console"),
        "timestamped-filename": sum(
            1 for s in sites if s["kind"] == "timestamped-filename"
        ),
        "files_scanned": len(iter_shipped_py()),
    }
    return {
        "scanned_root": "tools/",
        "absent_surfaces": [
            {"path": p, "exists": (REPO / p).exists()} for p in ABSENT_SURFACES
        ],
        "counts": counts,
        "sites": sites,
        "sorts_without_key": [
            s for s in sites if s["kind"] == "sort" and not s.get("has_explicit_key")
        ],
        "sorts_with_key": [
            s for s in sites if s["kind"] == "sort" and s.get("has_explicit_key")
        ],
    }


def main() -> int:
    doc = census()
    print(json.dumps({"counts": doc["counts"], "n_sites": len(doc["sites"])}, indent=2))
    print("SUCCESS:BLD-0010-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
