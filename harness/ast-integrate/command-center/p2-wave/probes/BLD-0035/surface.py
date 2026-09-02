"""Extract public surface from recovered deleted-file bytes."""
from __future__ import annotations

import json
import re
from pathlib import Path

EXPORT_FN = re.compile(
    r"export\s+(?:async\s+)?function\s+([A-Za-z_][\w]*)",
)
EXPORT_CONST = re.compile(r"export\s+const\s+([A-Za-z_][\w]*)")
EXPORT_CLASS = re.compile(r"export\s+class\s+([A-Za-z_][\w]*)")
EXPORT_NAMED = re.compile(r"export\s*\{([^}]+)\}")
SHEBANG = re.compile(r"^#!\s*/usr/bin/env\s+(\S+)", re.M)
TEST_CALL = re.compile(r"""(?:test|it)\s*\(\s*['"]([^'"]+)['"]""")
ASSERT_TOKEN = re.compile(
    r"""(?:assert\.\w+\([^;]+\)|expect\([^)]+\)[^\n;]*|BLD0035_[A-Z0-9_]+)"""
)
DOC_COMMAND = re.compile(r"^\$\s+(.+)$", re.M)
FENCE_CMD = re.compile(r"```(?:bash|sh|shell)?\n(\$[^\n]+)\n```")


def _named_exports(blob: str) -> list[str]:
    out: list[str] = []
    for m in EXPORT_NAMED.finditer(blob):
        for part in m.group(1).split(","):
            name = part.strip().split(" as ")[0].strip()
            if name:
                out.append(name)
    return out


def extract(path: str, data: bytes) -> list[dict]:
    text = data.decode("utf-8", "replace")
    kind_hint = Path(path).suffix.lower()
    name = Path(path).name
    rows: list[dict] = []

    if kind_hint in {".mjs", ".js", ".cjs", ".ts"}:
        for rx, kind in (
            (EXPORT_FN, "export"),
            (EXPORT_CONST, "export"),
            (EXPORT_CLASS, "export"),
        ):
            for m in rx.finditer(text):
                rows.append(
                    {
                        "path": path,
                        "kind": kind,
                        "symbol": m.group(1),
                        "token": m.group(1),
                    }
                )
        for sym in _named_exports(text):
            rows.append(
                {"path": path, "kind": "export", "symbol": sym, "token": sym}
            )
        sheb = SHEBANG.search(text)
        if sheb:
            rows.append(
                {
                    "path": path,
                    "kind": "cli",
                    "symbol": name,
                    "token": name,
                }
            )
        if name.startswith("test") or ".test." in name or "/tests/" in path.replace(
            "\\", "/"
        ):
            for m in TEST_CALL.finditer(text):
                rows.append(
                    {
                        "path": path,
                        "kind": "test",
                        "symbol": m.group(1),
                        "token": m.group(1),
                    }
                )
            for m in ASSERT_TOKEN.finditer(text):
                tok = m.group(0).strip()
                if tok.startswith("BLD0035_") or "assert." in tok or "expect(" in tok:
                    rows.append(
                        {
                            "path": path,
                            "kind": "test-assertion",
                            "symbol": tok[:120],
                            "token": tok,
                        }
                    )

    elif kind_hint == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, dict):
            cmd = doc.get("command") or doc.get("cmd")
            event = doc.get("event") or doc.get("hook")
            if cmd:
                rows.append(
                    {
                        "path": path,
                        "kind": "hook",
                        "symbol": str(event or "hook") + ":" + str(cmd),
                        "token": str(cmd),
                    }
                )

    elif kind_hint in {".md", ".txt"}:
        for m in DOC_COMMAND.finditer(text):
            rows.append(
                {
                    "path": path,
                    "kind": "documented-command",
                    "symbol": m.group(1).strip(),
                    "token": m.group(1).strip(),
                }
            )
        for m in FENCE_CMD.finditer(text):
            cmd = m.group(1).lstrip("$ ").strip()
            rows.append(
                {
                    "path": path,
                    "kind": "documented-command",
                    "symbol": cmd,
                    "token": cmd,
                }
            )

    if not rows:
        rows.append(
            {"path": path, "kind": "none", "symbol": "", "token": ""}
        )
    # de-dupe
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict] = []
    for r in rows:
        key = (r["kind"], r["symbol"], r["token"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq
