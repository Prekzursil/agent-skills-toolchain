"""Source-construct inventory for the three IMP-0160..0162 adapter shapes.

Inventories are computed from fixture bytes (JS call scan / JSON key walk),
not from a hardcoded expected list. Spans are 1-indexed line/column.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ledger import SourceConstruct, SourceSpan

JS_CALL_KINDS = {
    "agent": "agent_call",
    "parallel": "parallel_fanout",
    "phase": "phase",
    "background": "background_fire_forget",
    "eval": "eval_call",
}

CODEX_KEY_KINDS = {
    "units": "work_unit",  # exploded per element
    "timeout_s": "timeout",
    "prompt_file": "prompt_file",
    "background": "background_fire_forget",
    "description": "description",
    "title": "title",
}

DAG_KNOWN_ROOT = {"nodes", "edges"}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def offset_to_linecol(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    col = offset - last_nl  # 1-indexed: char after newline is col 1; if no nl, offset+1
    return line, col


def _skip_js_junk(source: str, i: int) -> int:
    n = len(source)
    while i < n:
        if source.startswith("//", i):
            nl = source.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if source[i] in "'\"`":
            quote = source[i]
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        break
    return i


def _matching_paren(source: str, open_idx: int) -> int:
    """Return index of the closing paren matching source[open_idx] == '('."""
    depth = 0
    i = open_idx
    n = len(source)
    while i < n:
        i2 = _skip_js_junk(source, i)
        if i2 != i:
            i = i2
            continue
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1 if n else 0


def inventory_claude_mjs(path: Path) -> list[SourceConstruct]:
    source = path.read_text(encoding="utf-8")
    rel = path.as_posix()
    constructs: list[SourceConstruct] = []
    i = 0
    n = len(source)
    seq = 0
    while i < n:
        i2 = _skip_js_junk(source, i)
        if i2 != i:
            i = i2
            continue
        m = IDENT.match(source, i)
        if not m:
            i += 1
            continue
        name = m.group(0)
        j = m.end()
        while j < n and source[j] in " \t\n\r":
            j += 1
        if j < n and source[j] == "(" and name in JS_CALL_KINDS:
            close = _matching_paren(source, j)
            start_line, start_col = offset_to_linecol(source, m.start())
            end_line, end_col = offset_to_linecol(source, close)
            seq += 1
            snippet = source[m.start() : close + 1]
            constructs.append(
                SourceConstruct(
                    construct_id=f"{path.name}:{JS_CALL_KINDS[name]}:{seq}:{start_line}",
                    kind=JS_CALL_KINDS[name],
                    span=SourceSpan(rel, start_line, start_col, end_line, end_col),
                    payload=snippet[:240],
                )
            )
            i = close + 1
            continue
        i = m.end()
    return constructs


def _key_span(text: str, key: str, nth: int = 0) -> tuple[int, int, int, int]:
    needle = json.dumps(key)
    idx = -1
    for _ in range(nth + 1):
        idx = text.find(needle, idx + 1)
        if idx < 0:
            raise KeyError(key)
    start_line, start_col = offset_to_linecol(text, idx)
    end_line, end_col = offset_to_linecol(text, idx + len(needle) - 1)
    return start_line, start_col, end_line, end_col


def _value_span_after_key(text: str, key: str) -> tuple[int, int, int, int]:
    needle = json.dumps(key)
    idx = text.find(needle)
    if idx < 0:
        raise KeyError(key)
    colon = text.find(":", idx + len(needle))
    i = colon + 1
    while i < len(text) and text[i] in " \t\n\r":
        i += 1
    start = i
    if i < len(text) and text[i] in "[{":
        opener, closer = ("[", "]") if text[i] == "[" else ("{", "}")
        depth = 0
        while i < len(text):
            ch = text[i]
            if ch in "'\"":
                q = ch
                i += 1
                while i < len(text):
                    if text[i] == "\\":
                        i += 2
                        continue
                    if text[i] == q:
                        i += 1
                        break
                    i += 1
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        end = i - 1
    elif i < len(text) and text[i] in "'\"":
        q = text[i]
        i += 1
        while i < len(text) and text[i] != q:
            if text[i] == "\\":
                i += 2
                continue
            i += 1
        end = i
    else:
        while i < len(text) and text[i] not in ",}\n":
            i += 1
        end = i - 1
    sl, sc = offset_to_linecol(text, start)
    el, ec = offset_to_linecol(text, max(start, end))
    return sl, sc, el, ec


def inventory_codex_json(path: Path) -> list[SourceConstruct]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be object")
    rel = path.as_posix()
    constructs: list[SourceConstruct] = []
    seq = 0
    for key, value in data.items():
        kind = CODEX_KEY_KINDS.get(key, "unknown_field")
        if key == "units":
            if not isinstance(value, list):
                raise ValueError(f"{path}: units must be array")
            for unit in value:
                seq += 1
                sl, sc, el, ec = _key_span(text, "units")
                constructs.append(
                    SourceConstruct(
                        construct_id=f"{path.name}:work_unit:{seq}:{unit}",
                        kind="work_unit",
                        span=SourceSpan(rel, sl, sc, el, ec),
                        payload=str(unit),
                    )
                )
            continue
        seq += 1
        sl, sc, el, ec = _value_span_after_key(text, key)
        constructs.append(
            SourceConstruct(
                construct_id=f"{path.name}:{kind}:{seq}:{key}",
                kind=kind,
                span=SourceSpan(rel, sl, sc, el, ec),
                payload=value,
            )
        )
    return constructs


def inventory_dag_json(path: Path) -> list[SourceConstruct]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be object")
    rel = path.as_posix()
    constructs: list[SourceConstruct] = []
    seq = 0
    nodes = data.get("nodes") or []
    for node in nodes:
        nid = node.get("id") if isinstance(node, dict) else node
        seq += 1
        sl, sc, el, ec = _key_span(text, "nodes")
        constructs.append(
            SourceConstruct(
                construct_id=f"{path.name}:dag_node:{seq}:{nid}",
                kind="dag_node",
                span=SourceSpan(rel, sl, sc, el, ec),
                payload=nid,
            )
        )
    edges = data.get("edges") or []
    for edge in edges:
        seq += 1
        sl, sc, el, ec = _key_span(text, "edges")
        constructs.append(
            SourceConstruct(
                construct_id=f"{path.name}:dag_edge:{seq}:{edge}",
                kind="dag_edge",
                span=SourceSpan(rel, sl, sc, el, ec),
                payload=edge,
            )
        )
    for key, value in data.items():
        if key in DAG_KNOWN_ROOT:
            continue
        kind = "native_while" if key in {"native_while", "while", "unbounded_loop"} else "unknown_field"
        seq += 1
        sl, sc, el, ec = _value_span_after_key(text, key)
        constructs.append(
            SourceConstruct(
                construct_id=f"{path.name}:{kind}:{seq}:{key}",
                kind=kind,
                span=SourceSpan(rel, sl, sc, el, ec),
                payload=value,
            )
        )
    return constructs


ADAPTERS = {
    "claude_mjs": inventory_claude_mjs,
    "codex_json": inventory_codex_json,
    "dag_json": inventory_dag_json,
}


def inventory(path: Path, adapter: str) -> list[SourceConstruct]:
    fn = ADAPTERS.get(adapter)
    if fn is None:
        raise KeyError(adapter)
    return fn(path)
