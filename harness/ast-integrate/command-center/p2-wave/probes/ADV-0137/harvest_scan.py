"""Harvest B: string-aware scan of the work_units array.

Does not json.loads the catalog. Finds each work-unit object by brace
matching, then reads top-level "id", "inputs", and "dependencies" with a
depth-1 lexer. Independently written from harvest_json.py.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from counting_rule import UID, passages_from_inputs, sources_from_inputs

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def _skip_ws(s: str, i: int) -> int:
    n = len(s)
    while i < n and s[i] in " \t\r\n":
        i += 1
    return i


def _scan_string(s: str, i: int) -> int:
    if s[i] != '"':
        raise ValueError(f"expected string at {i}")
    i += 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        i += 1
    raise ValueError("unterminated string")


def _scan_value(s: str, i: int) -> int:
    i = _skip_ws(s, i)
    if i >= len(s):
        raise ValueError("eof in value")
    c = s[i]
    if c == '"':
        return _scan_string(s, i)
    if c == "{":
        return _scan_container(s, i, "{", "}")
    if c == "[":
        return _scan_container(s, i, "[", "]")
    if s.startswith("true", i):
        return i + 4
    if s.startswith("false", i):
        return i + 5
    if s.startswith("null", i):
        return i + 4
    if c == "-" or c.isdigit():
        n = len(s)
        j = i + 1
        while j < n and s[j] in "0123456789.eE+-":
            j += 1
        return j
    raise ValueError(f"bad value at {i}: {s[i:i+20]!r}")


def _scan_container(s: str, i: int, open_c: str, close_c: str) -> int:
    if s[i] != open_c:
        raise ValueError("container mismatch")
    i += 1
    n = len(s)
    while True:
        i = _skip_ws(s, i)
        if i >= n:
            raise ValueError("unterminated container")
        if s[i] == close_c:
            return i + 1
        if s[i] == '"':
            i = _scan_string(s, i)
            i = _skip_ws(s, i)
            if i < n and s[i] == ":":
                i = _scan_value(s, i + 1)
        else:
            i = _scan_value(s, i)
        i = _skip_ws(s, i)
        if i < n and s[i] == ",":
            i += 1
            continue
        if i < n and s[i] == close_c:
            return i + 1
        raise ValueError(f"expected comma or close at {i}")


def _decode_json_string(raw: str) -> str:
    return json_string_decode(raw)


def json_string_decode(quoted: str) -> str:
    if not (quoted.startswith('"') and quoted.endswith('"')):
        raise ValueError("not a quoted string")
    body = quoted[1:-1]
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            break
        nxt = body[i + 1]
        mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
        if nxt in mapping:
            out.append(mapping[nxt])
            i += 2
            continue
        if nxt == "u" and i + 5 < n:
            out.append(chr(int(body[i + 2 : i + 6], 16)))
            i += 6
            continue
        out.append(nxt)
        i += 2
    return "".join(out)


def _top_level_fields(obj: str) -> dict[str, str]:
    """Map depth-1 keys to the raw value substring (including delimiters)."""
    i = _skip_ws(obj, 0)
    if obj[i] != "{":
        raise ValueError("not an object")
    i += 1
    fields: dict[str, str] = {}
    n = len(obj)
    while True:
        i = _skip_ws(obj, i)
        if i < n and obj[i] == "}":
            return fields
        if obj[i] != '"':
            raise ValueError(f"expected key at {i}")
        ks = i
        ke = _scan_string(obj, i)
        key = json_string_decode(obj[ks:ke])
        i = _skip_ws(obj, ke)
        if i >= n or obj[i] != ":":
            raise ValueError("expected colon")
        vs = _skip_ws(obj, i + 1)
        ve = _scan_value(obj, vs)
        fields[key] = obj[vs:ve]
        i = _skip_ws(obj, ve)
        if i < n and obj[i] == ",":
            i += 1
            continue
        if i < n and obj[i] == "}":
            return fields
        raise ValueError("expected comma or end of object")


def _parse_string_array(raw: str) -> list[str]:
    i = _skip_ws(raw, 0)
    if raw[i] != "[":
        return []
    i += 1
    out: list[str] = []
    n = len(raw)
    while True:
        i = _skip_ws(raw, i)
        if i < n and raw[i] == "]":
            return out
        if raw[i] == '"':
            vs = i
            ve = _scan_string(raw, i)
            out.append(json_string_decode(raw[vs:ve]))
            i = _skip_ws(raw, ve)
        else:
            i = _scan_value(raw, i)
            i = _skip_ws(raw, i)
        if i < n and raw[i] == ",":
            i += 1
            continue
        if i < n and raw[i] == "]":
            return out
        raise ValueError("bad array")


def _find_work_units_array(raw: str) -> int:
    needle = '"work_units"'
    idx = raw.find(needle)
    if idx < 0:
        raise ValueError("work_units key missing")
    i = idx + len(needle)
    i = _skip_ws(raw, i)
    if i >= len(raw) or raw[i] != ":":
        raise ValueError("work_units missing colon")
    i = _skip_ws(raw, i + 1)
    if i >= len(raw) or raw[i] != "[":
        raise ValueError("work_units is not an array")
    return i


def iter_work_unit_objects(raw: str) -> list[str]:
    i = _find_work_units_array(raw)
    i += 1
    objs: list[str] = []
    n = len(raw)
    while True:
        i = _skip_ws(raw, i)
        if i < n and raw[i] == "]":
            return objs
        if raw[i] != "{":
            raise ValueError(f"expected object in work_units at {i}")
        end = _scan_value(raw, i)
        objs.append(raw[i:end])
        i = _skip_ws(raw, end)
        if i < n and raw[i] == ",":
            i += 1
            continue
        if i < n and raw[i] == "]":
            return objs
        raise ValueError("expected comma or end of work_units")


def harvest_from_text(raw: str) -> dict:
    unit_sources: dict[str, list[str]] = {}
    unit_passages: dict[str, list[str]] = {}
    deps: dict[str, list[str]] = {}
    hist: Counter[str] = Counter()
    prose_only: list[str] = []
    for obj in iter_work_unit_objects(raw):
        fields = _top_level_fields(obj)
        id_raw = fields.get("id")
        if not id_raw:
            continue
        uid = json_string_decode(id_raw) if id_raw.startswith('"') else id_raw
        if not UID.match(uid):
            continue
        inputs = _parse_string_array(fields.get("inputs") or "[]")
        src = sources_from_inputs(inputs)
        pas = passages_from_inputs(inputs)
        unit_sources[uid] = sorted(src)
        unit_passages[uid] = sorted(pas)
        if not src:
            prose_only.append(uid)
        for s in src:
            hist[s] += 1
        dlist = _parse_string_array(fields.get("dependencies") or "[]")
        deps[uid] = dlist
    return {
        "n_units": len(unit_sources),
        "unit_sources": unit_sources,
        "unit_passages": unit_passages,
        "histogram": dict(hist),
        "prose_only": prose_only,
        "dependencies": deps,
        "family": "string-aware-work-units-scan",
        "catalog_rel": CATALOG_REL,
    }


def harvest(repo: Path) -> dict:
    raw = (repo / CATALOG_REL).read_text(encoding="utf-8")
    return harvest_from_text(raw)
