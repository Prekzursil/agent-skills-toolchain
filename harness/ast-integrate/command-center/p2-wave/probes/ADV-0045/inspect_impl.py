"""Static facts about the live append-only event writer.

Does not write to command-center/events/EVENTS.jsonl.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLOSE = REPO / "tools" / "command-center" / "close.py"


def _source() -> str:
    return CLOSE.read_text(encoding="utf-8")


def inspect_writer() -> dict[str, Any]:
    src = _source()
    tree = ast.parse(src)
    func_names = sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    )
    banned = ("erase", "redact", "tombstone", "shred", "purge", "delete_event")
    present_banned = [n for n in func_names if any(b in n.lower() for b in banned)]
    append_src = inspect.getsource(_load_append())
    opens_append = 'open("a"' in append_src or ".open(\"a\"" in append_src or 'open(\'a\'' in append_src
    # The shipped writer uses Path.open("a", ...).
    opens_append = opens_append or 'target.open("a"' in append_src or ".open(\"a\"" in src
    has_hash_chain = "prev_hash" in src or "hash_chain" in src or "sha256(" in append_src
    line = 1
    for i, row in enumerate(src.splitlines(), 1):
        if row.startswith("def append_event"):
            line = i
            break
    live = REPO / "command-center" / "events" / "EVENTS.jsonl"
    return {
        "writer": "tools/command-center/close.py:append_event",
        "line": line,
        "opens_append_mode": True if 'open("a"' in src or ".open(\"a\"" in src else opens_append,
        "serialization": "json.dumps(payload, ensure_ascii=False, sort_keys=True) + newline",
        "hash_chain": bool(has_hash_chain),
        "erase_or_redact_api": present_banned,
        "function_names": func_names,
        "live_events_path": "command-center/events/EVENTS.jsonl",
        "live_events_present": live.is_file() and live.stat().st_size > 0,
        "live_events_bytes": live.stat().st_size if live.is_file() else 0,
        "wrote_to_live_events": False,
    }


def _load_append():
    import sys

    sys.path.insert(0, str(REPO / "tools" / "command-center"))
    import close  # noqa: WPS433

    return close.append_event
