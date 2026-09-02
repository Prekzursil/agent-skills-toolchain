"""Synthesize one schema-valid reference artifact per command-center schema."""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.validators import validator_for

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from common import PADDING_BLOB, PADDING_KEY  # noqa: E402

HEX64 = "a" * 64
ISO_T = "2026-08-24T00:00:00Z"
QUESTION40 = "x" * 40
TITLE16 = "reference-artifact"
LONG80 = "SUCCESS:CNF-0026 " + ("n" * 64)

PATTERN_EXACT = {
    r"^[A-Z]{2,5}-[0-9]{4}$": "ADV-0004",
    r"^[A-Z]{3}-[0-9]{4}$": "CNF-0004",
    r"^AUD-[0-9]{4}$": "AUD-0004",
    r"^TST-[0-9]{4}$": "TST-0004",
    r"^RES-[0-9]{4}$": "RES-0004",
    r"^CNF-[0-9]{4}$": "CNF-0004",
    r"^CNL-[0-9]{4}$": "CNL-0004",
    r"^ARC-[0-9]{4}$": "ARC-0004",
    r"^ADV-[0-9]{4}$": "ADV-0004",
    r"^IMP-0443$": "IMP-0443",
    r"^ADV-0130$": "ADV-0130",
    r"^SYN-0036$": "SYN-0036",
    r"^SUCCESS:CNL-0110$": "SUCCESS:CNL-0110",
    r"^SUCCESS:CNF-0026 ": LONG80,
    r"^SUCCESS:CNF-0053": "SUCCESS:CNF-0053 truncation-reference",
    r"^SUCCESS:ARC-0007": "SUCCESS:ARC-0007 truncation-reference",
    r"^SUCCESS:ARC-0014": "SUCCESS:ARC-0014 truncation-reference",
    r"^SUCCESS:ARC-0063": "SUCCESS:ARC-0063 truncation-reference",
    r"^(SUCCESS|FAILED|BLOCKED|PARTIAL|TIMEOUT|SEVERED):TST-[0-9]{4}": (
        "SUCCESS:TST-0004"
    ),
    r"^(SUCCESS|FAILED|BLOCKED):CNF-[0-9]{4}": "SUCCESS:CNF-0004",
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T": ISO_T,
    r"^[a-f0-9]{64}$": HEX64,
    r"^GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}$": "GHSA-abcd-efgh-ijkl",
    r"^[0-9]+/[0-9]+$": "1/2",
    r"^A B A B": "A B A B interleaved",
    r"^S[1-9]$": "S1",
    r"\\S": "x",
}

SUBSTRING_NEEDLES = (
    "SENTINEL:IMP-0443:LEDGER-RESUME-IDEMPOTENT",
    "git cat-file -p",
    "git archive",
)


def _validator(schema: dict, root: dict | None = None) -> Any:
    root = root or schema
    cls = validator_for(root)
    try:
        cls.check_schema(root)
    except jsonschema.exceptions.SchemaError:
        pass
    resolver = jsonschema.RefResolver.from_schema(root)
    return cls(schema, resolver=resolver)


def _deref(schema: dict, root: dict) -> dict:
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    cur: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return schema
    if isinstance(cur, dict):
        merged = copy.deepcopy(cur)
        for k, v in schema.items():
            if k != "$ref":
                merged[k] = v
        return merged
    return schema


def _fill_pattern(pattern: str, min_len: int) -> str:
    if pattern in PATTERN_EXACT:
        s = PATTERN_EXACT[pattern]
        if len(s) < min_len:
            if pattern.startswith("^") and pattern.endswith("$"):
                # anchored exact samples already match; pad only if the
                # pattern allows extra (those entries are fully anchored).
                s = s
            else:
                s = s + ("p" * (min_len - len(s)))
        if len(s) < min_len and not pattern.endswith("$"):
            s = s + ("p" * (min_len - len(s)))
        if len(s) < min_len:
            # SUCCESS:CNF-0026  is prefix-anchored; pad after the prefix.
            s = s + ("n" * (min_len - len(s)))
        return s
    for needle in SUBSTRING_NEEDLES:
        if needle in pattern:
            s = needle
            if len(s) < min_len:
                s = s + ("p" * (min_len - len(s)))
            return s
    if re.fullmatch(r"\^SUCCESS:[A-Z]+-[0-9]{4}.*", pattern):
        body = pattern[1:]
        if body.endswith("$"):
            body = body[:-1]
        if ".*" in body or body.endswith(" "):
            s = body.replace(".*", " ref") + "n" * 40
        else:
            s = body
        if len(s) < min_len:
            s = s + ("n" * (min_len - len(s)))
        return s
    # Last resort: strip anchors and character classes crudely.
    s = pattern
    s = s.replace("^", "").replace("$", "")
    s = re.sub(r"\[A-Z\]\{2,5\}", "ADV", s)
    s = re.sub(r"\[0-9\]\{4\}", "0004", s)
    s = re.sub(r"\[a-f0-9\]\{64\}", HEX64, s)
    s = re.sub(r"\\d", "0", s)
    s = re.sub(r"\\S", "x", s)
    s = re.sub(r"\\s", " ", s)
    s = re.sub(r"\{[0-9,]+\}", "", s)
    s = re.sub(r"[()*+?|]", "", s)
    if len(s) < min_len:
        s = s + ("x" * (min_len - len(s)))
    return s or ("x" * max(min_len, 1))


def _string(schema: dict) -> str:
    if "const" in schema:
        return str(schema["const"])
    if "enum" in schema and schema["enum"]:
        v = schema["enum"][0]
        return str(v)
    min_len = int(schema.get("minLength") or 0)
    max_len = schema.get("maxLength")
    pattern = schema.get("pattern")
    if isinstance(pattern, str):
        s = _fill_pattern(pattern, min_len)
    else:
        s = "x" * max(min_len, 8)
        if min_len >= 40:
            s = QUESTION40 if min_len <= 40 else ("Q" * min_len)
        elif min_len >= 16:
            s = TITLE16 if min_len <= 16 else ("T" * min_len)
        elif min_len >= 8:
            s = "sentinel8" if min_len <= 9 else ("s" * min_len)
    if max_len is not None and len(s) > int(max_len):
        s = s[: int(max_len)]
    if len(s) < min_len:
        s = s + ("n" * (min_len - len(s)))
        if max_len is not None:
            s = s[: int(max_len)]
    return s


def _number(schema: dict, integer: bool) -> int | float:
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    minimum = schema.get("minimum")
    exclusive = schema.get("exclusiveMinimum")
    n = 1
    if minimum is not None:
        n = int(minimum) if integer else float(minimum)
        if schema.get("exclusiveMinimum") is True:
            n = n + (1 if integer else 0.1)
    if isinstance(exclusive, (int, float)):
        n = exclusive + (1 if integer else 0.1)
    return int(n) if integer else float(n)


def _type_list(schema: dict) -> list[str]:
    t = schema.get("type")
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        return [t]
    if "properties" in schema or "required" in schema or "additionalProperties" in schema:
        return ["object"]
    if "items" in schema or "minItems" in schema:
        return ["array"]
    if "pattern" in schema or "minLength" in schema:
        return ["string"]
    if "oneOf" in schema or "anyOf" in schema or "allOf" in schema:
        return ["object"]
    if "$ref" in schema:
        return ["object"]
    return ["object"]


class Synthesizer:
    def __init__(self, root: dict) -> None:
        self.root = root
        self.depth = 0
        self.enum_cursor: dict[int, int] = {}

    def build(self, schema: Any) -> Any:
        self.depth += 1
        try:
            if self.depth > 40:
                return "depth-cap"
            return self._build(schema)
        finally:
            self.depth -= 1

    def _build(self, schema: Any) -> Any:
        if schema is True:
            return {"k": "v"}
        if schema is False:
            return None
        if not isinstance(schema, dict):
            return schema
        schema = _deref(schema, self.root)
        if "const" in schema:
            return copy.deepcopy(schema["const"])
        if "enum" in schema and schema["enum"]:
            vals = schema["enum"]
            k = id(vals)
            i = self.enum_cursor.get(k, 0)
            self.enum_cursor[k] = i + 1
            return copy.deepcopy(vals[i % len(vals)])
        if "allOf" in schema:
            merged: dict[str, Any] = {}
            for part in schema["allOf"]:
                if isinstance(part, dict) and ("if" in part or "then" in part):
                    continue
                piece = self.build(part)
                if isinstance(piece, dict) and isinstance(merged, dict):
                    merged.update(piece)
                elif not merged:
                    merged = piece if isinstance(piece, dict) else merged
            rest = {k: v for k, v in schema.items() if k != "allOf"}
            if rest:
                extra = self._build_plain(rest)
                if isinstance(extra, dict):
                    merged.update(extra)
            return merged
        if "oneOf" in schema:
            return self._first_valid_branch(schema["oneOf"])
        if "anyOf" in schema:
            return self._first_valid_branch(schema["anyOf"])
        return self._build_plain(schema)

    def _first_valid_branch(self, branches: list[Any]) -> Any:
        errors: list[str] = []
        for branch in branches:
            try:
                inst = self.build(branch)
            except Exception as exc:  # synthesis of this branch failed
                errors.append(str(exc))
                continue
            sub = branch if isinstance(branch, dict) else {}
            # Validate against the branch using the root for $ref.
            check = copy.deepcopy(sub) if isinstance(sub, dict) else True
            try:
                if isinstance(check, dict) and "$ref" in check:
                    check = _deref(check, self.root)
                _validator(check, self.root).validate(inst)
                return inst
            except (
                jsonschema.exceptions.ValidationError,
                jsonschema.exceptions.RefResolutionError,
            ) as exc:
                errors.append(str(exc))
                continue
        if branches:
            return self.build(branches[0])
        return {}

    def _build_plain(self, schema: dict) -> Any:
        types = _type_list(schema)
        if "null" in types and len(types) == 1:
            return None
        if "object" in types or "properties" in schema or "required" in schema:
            return self._object(schema)
        if "array" in types or "items" in schema:
            return self._array(schema)
        if "string" in types:
            return _string(schema)
        if "integer" in types:
            return _number(schema, True)
        if "number" in types:
            return _number(schema, False)
        if "boolean" in types:
            if "const" in schema:
                return bool(schema["const"])
            return True
        if "null" in types:
            return None
        return self._object(schema)

    def _object(self, schema: dict) -> dict[str, Any]:
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        required = schema.get("required") or []
        if not isinstance(required, list):
            required = []
        out: dict[str, Any] = {}
        for key in required:
            sub = props.get(key, True)
            out[key] = self.build(sub if isinstance(sub, dict) or sub is True else True)
        # Include optional properties that are cheap; skip huge optional trees.
        for key, sub in props.items():
            if key in out:
                continue
            if key in {PADDING_KEY, "diagnostic_tail"}:
                continue
            if isinstance(sub, dict) and (
                "const" in sub
                or "enum" in sub
                or any(
                    t in {"string", "boolean", "integer", "number"}
                    for t in _type_list(sub)
                )
            ):
                out[key] = self.build(sub)
        addp = schema.get("additionalProperties", True)
        minp = int(schema.get("minProperties") or 0)
        if len(out) < minp:
            for key, sub in props.items():
                if len(out) >= minp:
                    break
                if key not in out:
                    out[key] = self.build(sub if isinstance(sub, dict) else True)
        if len(out) < minp and addp is not False:
            i = 0
            while len(out) < minp:
                out[f"_k{i}"] = "v"
                i += 1
        if addp is False:
            extra = [k for k in out if k not in props]
            for k in extra:
                out.pop(k, None)
        return out

    def _array(self, schema: dict) -> list[Any]:
        items = schema.get("items", True)
        min_items = int(schema.get("minItems") or 0)
        prefix = schema.get("prefixItems")
        out: list[Any] = []
        if isinstance(items, list):
            for sub in items:
                out.append(self.build(sub))
            while len(out) < min_items:
                out.append(self.build(items[-1] if items else True))
            return out
        if isinstance(prefix, list):
            for sub in prefix:
                out.append(self.build(sub))
        n = max(min_items, 1 if min_items == 0 and schema.get("items") else min_items)
        if n == 0:
            n = min_items
        target = max(n, min_items)
        unique = bool(schema.get("uniqueItems"))
        guard = 0
        while len(out) < target and guard < 32:
            guard += 1
            item = self.build(items)
            if unique and item in out:
                if isinstance(item, dict):
                    item = dict(item)
                    item["_u"] = str(guard)
                    if isinstance(items, dict) and items.get("additionalProperties") is False:
                        # mutate a string field instead
                        for k, v in list(item.items()):
                            if isinstance(v, str):
                                item[k] = v + str(guard)
                                break
                elif isinstance(item, str):
                    item = item + str(guard)
                elif isinstance(item, int):
                    item = item + guard
            out.append(item)
        return out


def _apply_not(inst: Any, schema: dict) -> Any:
    not_s = schema.get("not")
    if not isinstance(not_s, dict):
        return inst
    if "const" in not_s and inst == not_s["const"]:
        if isinstance(inst, str):
            return inst + "-x"
        if isinstance(inst, (int, float)):
            return inst + 1
    return inst


def repair(inst: Any, schema: dict, root: dict, rounds: int = 24) -> Any:
    validator = _validator(schema, root)
    syn = Synthesizer(root)
    for _ in range(rounds):
        errors = sorted(validator.iter_errors(inst), key=lambda e: len(list(e.path)))
        if not errors:
            return inst
        err = errors[0]
        inst = _patch(inst, err, syn)
    return inst


def _patch(inst: Any, err: jsonschema.exceptions.ValidationError, syn: Synthesizer) -> Any:
    path = list(err.absolute_path)
    validator = err.validator
    schema = err.schema if isinstance(err.schema, dict) else {}
    parent, key = _walk_parent(inst, path)
    if validator == "required" and isinstance(parent, dict):
        missing = err.message.split("'")[1] if "'" in err.message else None
        if missing:
            sub = (schema.get("properties") or {}).get(missing, True)
            parent[missing] = syn.build(sub)
        return inst
    if validator == "const":
        _assign(inst, path, copy.deepcopy(schema.get("const")))
        return inst
    if validator == "enum" and schema.get("enum"):
        _assign(inst, path, copy.deepcopy(schema["enum"][0]))
        return inst
    if validator == "minLength":
        cur = _get(inst, path)
        if isinstance(cur, str):
            need = int(schema.get("minLength") or 0)
            _assign(inst, path, cur + ("n" * max(0, need - len(cur))))
        return inst
    if validator == "pattern" and isinstance(schema.get("pattern"), str):
        _assign(inst, path, _string(schema))
        return inst
    if validator == "type":
        _assign(inst, path, syn.build(schema))
        return inst
    if validator == "minItems" and isinstance(parent, list):
        items = schema.get("items", True)
        while len(parent) < int(schema.get("minItems") or 0):
            parent.append(syn.build(items))
        return inst
    if validator == "minItems":
        cur = _get(inst, path)
        if isinstance(cur, list):
            items = schema.get("items", True)
            while len(cur) < int(schema.get("minItems") or 0):
                cur.append(syn.build(items))
        return inst
    if validator == "minimum":
        _assign(inst, path, _number(schema, schema.get("type") == "integer"))
        return inst
    if validator == "additionalProperties" and isinstance(parent, dict):
        extra = [k for k in parent if k not in (schema.get("properties") or {})]
        for k in extra:
            parent.pop(k, None)
        return inst
    if validator == "minProperties":
        cur = parent if isinstance(parent, dict) and not path else _get(inst, path)
        if isinstance(cur, dict):
            need = int(schema.get("minProperties") or 1)
            i = 0
            while len(cur) < need:
                cur[f"_k{i}"] = "v"
                i += 1
        return inst
        for i, item in enumerate(parent):
            if isinstance(item, dict):
                item["_u"] = str(i)
            elif isinstance(item, str):
                parent[i] = item + str(i)
        return inst
    if validator == "oneOf" or validator == "anyOf":
        branches = schema.get(validator) or []
        if branches:
            _assign(inst, path, syn.build({validator: branches}))
        return inst
    if path:
        _assign(inst, path, syn.build(schema))
    return inst


def _walk_parent(inst: Any, path: list[Any]) -> tuple[Any, Any]:
    if not path:
        return inst, None
    cur = inst
    for p in path[:-1]:
        if isinstance(cur, dict):
            cur = cur[p]
        elif isinstance(cur, list):
            cur = cur[int(p)]
        else:
            return cur, path[-1]
    return cur, path[-1]


def _get(inst: Any, path: list[Any]) -> Any:
    cur = inst
    for p in path:
        if isinstance(cur, dict):
            cur = cur[p]
        elif isinstance(cur, list):
            cur = cur[int(p)]
        else:
            return cur
    return cur


def _assign(inst: Any, path: list[Any], value: Any) -> None:
    if not path:
        if isinstance(inst, dict) and isinstance(value, dict):
            inst.clear()
            inst.update(value)
        return
    parent, key = _walk_parent(inst, path)
    if isinstance(parent, dict):
        parent[key] = value
    elif isinstance(parent, list):
        idx = int(key)
        while len(parent) <= idx:
            parent.append(None)
        parent[idx] = value


def add_padding(inst: dict[str, Any], schema: dict) -> dict[str, Any]:
    if not isinstance(inst, dict):
        return inst
    addp = schema.get("additionalProperties", True)
    if addp is False:
        # Inflate the longest unconstrained string field.
        for key, sub in (schema.get("properties") or {}).items():
            if not isinstance(sub, dict):
                continue
            if sub.get("type") == "string" and "const" not in sub and "enum" not in sub:
                if "maxLength" in sub:
                    continue
                cur = inst.get(key)
                if isinstance(cur, str) and PADDING_KEY not in inst:
                    inst[key] = cur + "\n" + PADDING_BLOB
                    return inst
        return inst
    inst[PADDING_KEY] = PADDING_BLOB
    return inst


def encode_sentinel_first(inst: dict[str, Any]) -> bytes:
    """Serialize with sentinel (if present) first and padding last."""
    if not isinstance(inst, dict):
        return (json.dumps(inst, ensure_ascii=True) + "\n").encode("utf-8")
    keys = list(inst.keys())
    head: list[str] = []
    if "sentinel" in inst:
        head.append("sentinel")
    mid = [k for k in keys if k not in head and k != PADDING_KEY]
    tail = [PADDING_KEY] if PADDING_KEY in inst else []
    ordered = {k: inst[k] for k in head + mid + tail}
    text = json.dumps(ordered, indent=2, ensure_ascii=True) + "\n"
    return text.encode("utf-8")


def synthesize_schema(schema: dict) -> dict[str, Any]:
    syn = Synthesizer(schema)
    inst = syn.build(schema)
    if not isinstance(inst, dict):
        inst = {"value": inst}
    inst = repair(inst, schema, schema)
    inst = add_padding(inst, schema)
    inst = repair(inst, schema, schema)
    return inst


def validate_instance(schema: dict, inst: Any) -> list[str]:
    try:
        _validator(schema, schema).validate(inst)
        return []
    except jsonschema.exceptions.ValidationError as exc:
        return [exc.message]
    except jsonschema.exceptions.RefResolutionError as exc:
        return [f"RefResolutionError:{exc}"]


def main() -> int:
    from common import SCHEMA_DIR_REL, schema_paths

    failed = []
    ok = 0
    for path in schema_paths():
        schema = json.loads(path.read_text(encoding="utf-8"))
        try:
            inst = synthesize_schema(schema)
            errs = validate_instance(schema, inst)
        except Exception as exc:  # synthesis crash is a failed schema
            failed.append((path.name, [f"{type(exc).__name__}:{exc}"]))
            continue
        if errs:
            failed.append((path.name, errs[:3]))
        else:
            ok += 1
            raw = encode_sentinel_first(inst)
            print(f"OK {path.name} bytes={len(raw)}")
    print(f"ok={ok} failed={len(failed)} dir={SCHEMA_DIR_REL}")
    for name, errs in failed:
        print(f"FAIL {name}: {errs}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
