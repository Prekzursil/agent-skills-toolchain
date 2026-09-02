"""Generic declarative DAG adapter that preserves case-distinct keys.

Strict parser (IMP-0162): true duplicate keys and duplicate node ids are refused, and so is
any field the format does not declare -- an unknown field is rejected with
``AS-DAG-UNKNOWN-FIELD`` naming the field, never silently ignored.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AS_DAG_NOT_OBJECT = "AS-DAG-NOT-OBJECT"
AS_DAG_DUPLICATE_KEY = "AS-DAG-DUPLICATE-KEY"
AS_DAG_DUPLICATE_NODE_ID = "AS-DAG-DUPLICATE-NODE-ID"
AS_DAG_UNKNOWN_FIELD = "AS-DAG-UNKNOWN-FIELD"

# The closed set of ids this adapter can emit; ``agentspec.validate.CLOSED_VIOLATION_IDS``
# folds it into the package-wide closed set.
DAG_VIOLATION_IDS: tuple[str, ...] = (
    AS_DAG_NOT_OBJECT,
    AS_DAG_DUPLICATE_KEY,
    AS_DAG_DUPLICATE_NODE_ID,
    AS_DAG_UNKNOWN_FIELD,
)

# Declared fields of the generic DAG document and of one node. Anything else is unknown.
DOCUMENT_FIELDS: frozenset[str] = frozenset(
    {"id", "name", "description", "version", "nodes", "edges", "params"}
)
NODE_FIELDS: frozenset[str] = frozenset(
    {"kind", "params", "description", "depends_on", "needs", "inputs", "outputs"}
)


@dataclass
class Violation:
    id: str
    message: str = ""
    detail: str = ""


@dataclass
class UnitView:
    id: str
    params: dict[str, Any] = field(default_factory=dict)

    def param_keys(self) -> list[str]:
        return list(self.params.keys())


@dataclass
class WorkflowView:
    units: list[UnitView] = field(default_factory=list)

    def unit_ids(self) -> list[str]:
        return [u.id for u in self.units]


@dataclass
class ImportResult:
    ok: bool
    workflow: WorkflowView | None = None
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [v.id for v in self.violations],
            "unit_ids": self.workflow.unit_ids() if self.workflow else [],
        }


def _object_pairs(text: str, start: int) -> tuple[list[tuple[str, Any]], int]:
    """Parse a JSON object from start (index of '{'), preserving duplicate keys."""
    i = start
    assert text[i] == "{"
    i += 1
    pairs: list[tuple[str, Any]] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i < n and text[i] == "}":
            return pairs, i + 1
        if i >= n or text[i] != '"':
            raise ValueError("expected key")
        key, i = _string(text, i)
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n or text[i] != ":":
            raise ValueError("expected colon")
        i += 1
        while i < n and text[i] in " \t\r\n":
            i += 1
        val, i = _value(text, i)
        pairs.append((key, val))
    raise ValueError("unterminated object")


def _string(text: str, start: int) -> tuple[str, int]:
    i = start + 1
    out = []
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            out.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise ValueError("unterminated string")


def _value(text: str, i: int) -> tuple[Any, int]:
    if text[i] == "{":
        pairs, j = _object_pairs(text, i)
        return dict(pairs) if not _dup_keys(pairs) else ("__DUP__", pairs), j
    if text[i] == "[":
        return _array(text, i)
    if text[i] == '"':
        return _string(text, i)
    if text[i:i + 4] == "true":
        return True, i + 4
    if text[i:i + 5] == "false":
        return False, i + 5
    if text[i:i + 4] == "null":
        return None, i + 4
    m = re.match(r"-?\d+(\.\d+)?", text[i:])
    if m:
        raw = m.group(0)
        val: Any = float(raw) if "." in raw else int(raw)
        return val, i + len(raw)
    raise ValueError(f"bad value at {i}")


def _array(text: str, start: int) -> tuple[list[Any], int]:
    i = start + 1
    out: list[Any] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i < n and text[i] == "]":
            return out, i + 1
        val, i = _value(text, i)
        out.append(val)
    raise ValueError("unterminated array")


def _dup_keys(pairs: list[tuple[str, Any]]) -> bool:
    keys = [k for k, _ in pairs]
    return len(keys) != len(set(keys))


def _parse_json_preserve(text: str) -> Any:
    i = 0
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    val, _ = _value(text, i)
    return val


def _parse_yaml_simple(text: str) -> dict[str, Any]:
    """Tiny YAML subset: mappings + nested 2-space indent. Preserves key case."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(0, root)]
    i = 0
    while i < len(lines):
        ln = lines[i]
        indent = len(ln) - len(ln.lstrip(" "))
        content = ln.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        cur = stack[-1][1]
        if content.startswith("- "):
            item = content[2:]
            if isinstance(cur, list):
                if ":" in item:
                    k, v = item.split(":", 1)
                    cur.append({k.strip(): _scalar(v.strip())})
                else:
                    cur.append(_scalar(item))
            i += 1
            continue
        if ":" in content:
            k, rest = content.split(":", 1)
            key = k.strip()
            rest = rest.strip()
            if rest == "":
                # look ahead
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                nindent = len(nxt) - len(nxt.lstrip(" ")) if nxt else indent
                child: Any = [] if nxt.strip().startswith("- ") else {}
                if isinstance(cur, dict):
                    if key in cur:
                        cur[f"__dup__{key}"] = child
                    cur[key] = child
                stack.append((nindent if nindent > indent else indent + 2, child))
            else:
                if isinstance(cur, dict):
                    if key in cur:
                        cur[f"__dup__{key}"] = _scalar(rest)
                    cur[key] = _scalar(rest)
        i += 1
    return root


def _json_duplicate_keys(raw: str, object_key: str) -> bool:
    """True when an object keyed by object_key repeats an exact member name."""
    needle = f'"{object_key}"'
    i = 0
    while True:
        j = raw.find(needle, i)
        if j < 0:
            return False
        k = raw.find("{", j + len(needle))
        if k < 0:
            return False
        keys: list[str] = []
        depth = 0
        p = k
        n = len(raw)
        while p < n:
            ch = raw[p]
            if ch == '"':
                q = p + 1
                buf = []
                while q < n:
                    if raw[q] == "\\":
                        q += 2
                        continue
                    if raw[q] == '"':
                        break
                    buf.append(raw[q])
                    q += 1
                token = "".join(buf)
                # key if next non-space is colon at this object depth
                r = q + 1
                while r < n and raw[r] in " \t\r\n":
                    r += 1
                if r < n and raw[r] == ":" and depth == 1:
                    keys.append(token)
                p = q + 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    if len(keys) != len(set(keys)):
                        return True
                    break
            p += 1
        i = k + 1
    return False


def _scalar(v: str) -> Any:
    if v in {"{}", "null", "~", ""}:
        return {} if v == "{}" else None
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


class GenericDeclarativeDagAdapter:
    def import_path(self, path: Path | str) -> ImportResult:
        p = Path(path)
        raw = p.read_text(encoding="utf-8")
        violations: list[Violation] = []
        if p.suffix.lower() in {".yaml", ".yml"}:
            data = _parse_yaml_simple(raw)
        else:
            try:
                data = _parse_json_preserve(raw)
            except Exception:
                data = json.loads(raw)
        if not isinstance(data, dict):
            return ImportResult(ok=False, violations=[Violation("AS-DAG-NOT-OBJECT")])
        violations.extend(_unknown_fields(data))
        nodes = data.get("nodes")
        if isinstance(nodes, tuple) and nodes and nodes[0] == "__DUP__":
            violations.append(Violation("AS-DAG-DUPLICATE-NODE-ID"))
            nodes = dict(nodes[1])
        if not isinstance(nodes, dict):
            nodes = {}
        # detect duplicate node keys from __dup__
        if any(str(k).startswith("__dup__") for k in nodes):
            violations.append(Violation("AS-DAG-DUPLICATE-NODE-ID"))
        units: list[UnitView] = []
        for nid, body in nodes.items():
            if str(nid).startswith("__dup__"):
                continue
            params = {}
            if isinstance(body, dict):
                params = body.get("params") or {}
                if isinstance(params, tuple) and params and params[0] == "__DUP__":
                    violations.append(Violation("AS-DAG-DUPLICATE-KEY"))
                    params = dict(params[1])
                if isinstance(params, dict) and any(str(k).startswith("__dup__") for k in params):
                    violations.append(Violation("AS-DAG-DUPLICATE-KEY"))
            if not isinstance(params, dict):
                params = {}
            units.append(UnitView(id=str(nid), params=params))
        # JSON true-duplicate keys: parser keeps last; detect via raw text
        if p.suffix.lower() == ".json":
            if _json_duplicate_keys(raw, "nodes"):
                violations.append(Violation("AS-DAG-DUPLICATE-NODE-ID"))
            if _json_duplicate_keys(raw, "params"):
                violations.append(Violation("AS-DAG-DUPLICATE-KEY"))
        if any(v.id in DAG_VIOLATION_IDS for v in violations):
            return ImportResult(ok=False, workflow=None, violations=violations)
        return ImportResult(ok=True, workflow=WorkflowView(units=units), violations=[])


def _field_names(mapping: dict[str, Any]) -> list[str]:
    """Member names of a parsed object, with the parser's ``__dup__`` markers stripped."""
    names: list[str] = []
    for key in mapping:
        text = str(key)
        if text.startswith("__dup__"):
            text = text[len("__dup__"):]
        names.append(text)
    return names


def _unknown_fields(data: dict[str, Any]) -> list[Violation]:
    """Strict-parser refusals for document- and node-level fields the format never declared."""
    found: list[Violation] = []
    for name in _field_names(data):
        if name not in DOCUMENT_FIELDS:
            found.append(
                Violation(
                    AS_DAG_UNKNOWN_FIELD,
                    f"document field {name!r} is not declared by the generic DAG format",
                    detail=name,
                )
            )
    nodes = data.get("nodes")
    if isinstance(nodes, tuple) and nodes and nodes[0] == "__DUP__":
        nodes = dict(nodes[1])
    if isinstance(nodes, dict):
        for node_id, body in nodes.items():
            if not isinstance(body, dict):
                continue
            for name in _field_names(body):
                if name not in NODE_FIELDS:
                    found.append(
                        Violation(
                            AS_DAG_UNKNOWN_FIELD,
                            f"node {node_id!r} field {name!r} is not declared by the generic DAG format",
                            detail=name,
                        )
                    )
    return found
