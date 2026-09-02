#!/usr/bin/env python3
"""Property-based JSON Schema instance generator, typed mutators, mutation oracle."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

import schemas as S

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_DIR = REPO / "command-center" / "phase4" / "contracts"
FIX_DIR = HERE / "fixtures" / "contracts"
FREEZE_DIR = HERE / "fixtures" / "campaign"
TIGHTEN_FIELD = "tighten_token_live_loop"
AXES = (
    "drop_required_field",
    "widen_type",
    "break_enum",
    "exceed_bound",
    "inject_unknown_field",
)
TYPE_WIDEN: dict[str, Any] = {
    "string": 424242,
    "integer": "WIDENED-TO-STRING",
    "number": "WIDENED-TO-STRING",
    "boolean": "WIDENED-TO-STRING",
    "array": {"widened": True},
    "object": ["widened"],
}
REASON_BY_AXIS = {
    "drop_required_field": {"required"},
    "widen_type": {"type"},
    "break_enum": {"enum", "const"},
    "exceed_bound": {
        "maximum",
        "minimum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "maxLength",
        "minLength",
        "maxItems",
        "minItems",
        "maxProperties",
        "minProperties",
        "multipleOf",
        "uniqueItems",
        "pattern",
    },
    "inject_unknown_field": {"additionalProperties", "unevaluatedProperties"},
}


def looks_like_schema(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if any(k in doc for k in ("$schema", "$id", "properties", "type", "required")):
        return True
    return False


def extract_schema(doc: Any) -> dict[str, Any] | None:
    if looks_like_schema(doc) and (
        "properties" in doc or doc.get("type") == "object" or "$schema" in doc
    ):
        if "properties" in doc or "required" in doc or doc.get("type") == "object":
            return doc
    if isinstance(doc, dict):
        for key in ("schema", "json_schema", "contract", "body"):
            inner = doc.get(key)
            if looks_like_schema(inner) and isinstance(inner, dict):
                return inner
    return None


def discover_contract(uid: str) -> tuple[dict[str, Any], str, str]:
    """Resolve a contract without the campaign freeze (live, then fixture, then module)."""
    live = LIVE_DIR / f"{uid}.json"
    if live.is_file() and live.stat().st_size > 0:
        try:
            raw = json.loads(live.read_text(encoding="utf-8"))
            sch = extract_schema(raw)
            if sch is not None:
                rel = live.relative_to(REPO).as_posix()
                return sch, "live", rel
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    fix = FIX_DIR / f"{uid}.json"
    if fix.is_file() and fix.stat().st_size > 0:
        raw = json.loads(fix.read_text(encoding="utf-8"))
        sch = extract_schema(raw) or raw
        return sch, "fixture", fix.relative_to(REPO).as_posix()
    sch = S.fixture_schema(uid)
    return sch, "fixture-module", f"command-center/p2-wave/probes/ARC-0109/schemas.py#{uid}"


def load_contract(uid: str) -> tuple[dict[str, Any], str, str]:
    frozen = FREEZE_DIR / f"{uid}.json"
    if frozen.is_file() and frozen.stat().st_size > 0:
        raw = json.loads(frozen.read_text(encoding="utf-8"))
        sch = extract_schema(raw) or raw
        origin = "frozen"
        idx = FREEZE_DIR / "INDEX.json"
        if idx.is_file():
            try:
                meta = json.loads(idx.read_text(encoding="utf-8"))
                for row in meta.get("contracts") or []:
                    if isinstance(row, dict) and row.get("id") == uid:
                        origin = str(row.get("source") or "frozen")
                        break
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        return sch, origin, frozen.relative_to(REPO).as_posix()
    return discover_contract(uid)


def rebuild_freeze() -> list[dict[str, Any]]:
    """Snapshot the corpus used by this campaign so probes cannot drift mid-wave."""
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for uid in S.CONTRACT_IDS:
        schema, source, origin = discover_contract(uid)
        dest = FREEZE_DIR / f"{uid}.json"
        text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        dest.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows.append(
            {
                "id": uid,
                "source": source,
                "origin": origin,
                "frozen": dest.relative_to(REPO).as_posix(),
                "sha256": digest,
                "bytes": len(text.encode("utf-8")),
            }
        )
    index = {
        "unit_id": "ARC-0109",
        "n": len(rows),
        "contracts": rows,
    }
    (FREEZE_DIR / "INDEX.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return rows


def dump_fixtures() -> list[str]:
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for uid in S.CONTRACT_IDS:
        path = FIX_DIR / f"{uid}.json"
        path.write_text(
            json.dumps(S.fixture_schema(uid), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path.relative_to(REPO).as_posix())
    return written


def _defs(schema: dict[str, Any]) -> dict[str, Any]:
    return dict(schema.get("$defs") or schema.get("definitions") or {})


def resolve(schema: Any, defs: dict[str, Any], root: dict[str, Any]) -> Any:
    if schema is True:
        return True
    if schema is False:
        return False
    if not isinstance(schema, dict):
        return {"const": schema}
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            return resolve(defs[name], defs, root)
        if ref.startswith("#/definitions/"):
            name = ref.split("/")[-1]
            return resolve((root.get("definitions") or {})[name], defs, root)
        if ref == "#":
            return root
    if "allOf" in schema:
        merged: dict[str, Any] = {k: v for k, v in schema.items() if k != "allOf"}
        props: dict[str, Any] = dict(merged.get("properties") or {})
        req: list[str] = list(merged.get("required") or [])
        contains_all: list[Any] = []
        if "contains" in merged:
            contains_all.append(merged["contains"])
        ifs: list[dict[str, Any]] = []
        for part in schema["allOf"]:
            p = resolve(part, defs, root)
            if p is True:
                continue
            if not isinstance(p, dict):
                continue
            props.update(p.get("properties") or {})
            for r in p.get("required") or []:
                if r not in req:
                    req.append(r)
            if "contains" in p:
                contains_all.append(p["contains"])
            if p.get("contains_all"):
                contains_all.extend(p["contains_all"])
            if "if" in p:
                ifs.append(p)
            for k, v in p.items():
                if k in {"properties", "required", "contains", "contains_all", "if", "then"}:
                    continue
                if k not in merged:
                    merged[k] = v
        merged["properties"] = props
        merged["required"] = req
        if contains_all:
            merged["contains_all"] = contains_all
        if ifs:
            merged["if_then"] = ifs
        return merged
    return schema


def validator_for(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def errors_for(schema: dict[str, Any], instance: Any) -> list[jsonschema.ValidationError]:
    v = validator_for(schema)
    return sorted(v.iter_errors(instance), key=lambda e: list(e.path))


def accepted(schema: dict[str, Any], instance: Any) -> bool:
    return not errors_for(schema, instance)


def _string(schema: dict[str, Any]) -> str:
    if "const" in schema:
        return str(schema["const"])
    if "enum" in schema:
        return str(schema["enum"][0])
    if isinstance(schema.get("default"), str):
        s = schema["default"]
    else:
        pat = str(schema.get("pattern") or "")
        if re.fullmatch(r"\^\[0-9\]\+\\.\.\[0-9\]\+\\.\.\[0-9\]\+\$", pat.replace("\\\\", "\\")):
            s = "1.0.0"
        elif "^[0-9]+\\.[0-9]+\\.[0-9]+$" in pat or pat == "^[0-9]+\\.[0-9]+\\.[0-9]+$":
            s = "1.0.0"
        elif "SUCCESS|FAILED" in pat or "SEVERED|TIMEOUT" in pat:
            s = "SUCCESS:ARC-0109"
        elif "[A-Z]{2,5}-[0-9]{4}" in pat:
            s = "ARC-0109"
        elif pat == "^[a-f0-9]{64}$":
            s = "a" * 64
        elif "a-z" in pat:
            s = "example-item"
        elif pat.startswith("^[0-9]{4}-"):
            s = "2026-08-24T18:00:00Z"
        else:
            s = "sample-value"
    minl = int(schema.get("minLength") or 0)
    maxl = int(schema.get("maxLength") or max(minl, len(s)))
    if len(s) < minl:
        s = s + ("x" * (minl - len(s)))
    if len(s) > maxl:
        s = s[:maxl]
        if len(s) < minl:
            s = ("x" * minl)[:maxl]
    return s


def _apply_then(obj: dict[str, Any], then: dict[str, Any], root: dict[str, Any], props: dict[str, Any]) -> None:
    for key in then.get("required") or []:
        if key not in obj:
            sub = (then.get("properties") or {}).get(key, props.get(key, {"type": "string"}))
            obj[key] = generate(sub, root)
    for key, vs in (then.get("properties") or {}).items():
        if vs is True:
            obj.setdefault(key, True)
            continue
        if not isinstance(vs, dict):
            continue
        if "const" in vs:
            if key in obj and isinstance(obj[key], dict) and isinstance(vs.get("properties"), dict):
                pass
            else:
                obj[key] = copy.deepcopy(vs["const"])
        if isinstance(vs.get("properties"), dict) and isinstance(obj.get(key), dict):
            _apply_then(obj[key], vs, root, vs.get("properties") or {})


def generate(schema: Any, root: dict[str, Any] | None = None) -> Any:
    if schema is True:
        return True
    if schema is False:
        return None
    root = root or (schema if isinstance(schema, dict) else {})
    defs = _defs(root)
    s = resolve(schema, defs, root)
    if s is True:
        return True
    if s is False:
        return None
    if not isinstance(s, dict):
        return s
    if "const" in s:
        return copy.deepcopy(s["const"])
    if "enum" in s:
        return copy.deepcopy(s["enum"][0])
    if "oneOf" in s and s["oneOf"]:
        return generate(s["oneOf"][0], root)
    if "anyOf" in s and s["anyOf"]:
        return generate(s["anyOf"][0], root)
    types = s.get("type")
    if isinstance(types, list):
        types = types[0] if types else "string"
    if types is None:
        if "properties" in s or "required" in s:
            types = "object"
        elif "items" in s or "contains" in s or "contains_all" in s:
            types = "array"
        else:
            types = "string"
    if types == "null":
        return None
    if types == "boolean":
        if "const" in s:
            return s["const"]
        return bool(s.get("default", True))
    if types == "integer":
        lo = s.get("minimum", 0)
        hi = s.get("maximum", lo)
        n = int(lo)
        if n > hi:
            n = int(hi)
        return n
    if types == "number":
        lo = float(s.get("minimum", 0))
        return lo
    if types == "string":
        return _string(s)
    if types == "array":
        items = s.get("items", {"type": "string"})
        min_items = int(s.get("minItems") or 0)
        max_items = s.get("maxItems")
        contains_all = list(s.get("contains_all") or [])
        if "contains" in s and s["contains"] not in contains_all:
            contains_all.insert(0, s["contains"])
        min_contains = int(s.get("minContains") or (1 if contains_all else 0))
        n = max(min_items, min_contains, len(contains_all))
        if n == 0 and max_items != 0:
            n = 1 if max_items is None or max_items >= 1 else 0
        if max_items is not None:
            n = min(max(n, min_items), int(max_items))
        out: list[Any] = []
        unique = bool(s.get("uniqueItems"))
        items_r = resolve(items, defs, root) if isinstance(items, dict) else items
        enum_vals = items_r.get("enum") if isinstance(items_r, dict) else None
        if isinstance(enum_vals, list) and n <= len(enum_vals):
            return [copy.deepcopy(v) for v in enum_vals[:n]]
        if unique and isinstance(enum_vals, list):
            return [copy.deepcopy(v) for v in enum_vals[:n]]
        guard = 0
        while len(out) < n and guard < 64:
            guard += 1
            item = generate(items, root) if not isinstance(items, bool) else items
            if unique and item in out:
                if isinstance(item, str):
                    item = f"{item}-{len(out)}"
                elif isinstance(item, (int, float)) and not isinstance(item, bool):
                    item = item + len(out) + 1
                else:
                    continue
            out.append(item)
        for i, constraint in enumerate(contains_all):
            if not out:
                out.append(generate(constraint, root))
                continue
            idx = i if i < len(out) else len(out) - 1
            piece = generate(constraint, root)
            if isinstance(out[idx], dict) and isinstance(piece, dict):
                out[idx].update(piece)
            else:
                out[idx] = piece
        return out
    props = s.get("properties") or {}
    required = list(s.get("required") or [])
    obj: dict[str, Any] = {}
    for key in required:
        sub = props.get(key, {"type": "string"})
        obj[key] = generate(sub, root)
    for key, sub in props.items():
        if key in obj:
            continue
        if sub is True:
            obj[key] = True
            continue
        if isinstance(sub, dict) and "const" in sub:
            obj[key] = copy.deepcopy(sub["const"])
    for part in s.get("if_then") or []:
        if not isinstance(part, dict) or "if" not in part or "then" not in part:
            continue
        if_schema = part["if"]
        try:
            if accepted(if_schema, obj):
                then = part["then"] if isinstance(part["then"], dict) else {}
                _apply_then(obj, then, root, props)
        except Exception:
            continue
    if "if" in s and "then" in s:
        try:
            if accepted(s["if"], obj):
                then = s["then"] if isinstance(s["then"], dict) else {}
                _apply_then(obj, then, root, props)
        except Exception:
            pass
    _fill_min_properties(obj, s, root)
    return obj


def _fill_min_properties(obj: dict[str, Any], s: dict[str, Any], root: dict[str, Any]) -> None:
    need = int(s.get("minProperties") or 0)
    maxp = s.get("maxProperties")
    if maxp is not None:
        need = min(need, int(maxp))
    addl = s.get("additionalProperties", True)
    props = s.get("properties") or {}
    for key, sub in props.items():
        if len(obj) >= need:
            break
        if key in obj:
            continue
        obj[key] = generate(sub, root) if sub is not True else True
    i = 0
    while len(obj) < need:
        if addl is False:
            break
        key = f"filled_{i}"
        i += 1
        if key in obj:
            continue
        if addl is True:
            obj[key] = "sample-value"
        elif isinstance(addl, dict):
            obj[key] = generate(addl, root)
        else:
            break


def _get_in(doc: Any, path: list[Any]) -> Any:
    cur = doc
    for p in path:
        cur = cur[p]
    return cur


def _set_in(doc: Any, path: list[Any], value: Any) -> bool:
    if not path:
        return False
    cur = doc
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value
    return True


def repair(inst: Any, err: jsonschema.ValidationError, root_schema: dict[str, Any]) -> bool:
    path = list(err.absolute_path)
    v = err.validator
    schema = err.schema if isinstance(err.schema, dict) else {}
    if v == "required":
        m = re.search(r"'([^']+)' is a required property", err.message)
        if not m:
            return False
        name = m.group(1)
        target = inst if not path else _get_in(inst, path)
        if not isinstance(target, dict):
            return False
        props = schema.get("properties") or {}
        target[name] = generate(props.get(name, {"type": "string"}), root_schema)
        return True
    if v == "const":
        return _set_in(inst, path, copy.deepcopy(err.validator_value))
    if v == "enum" and err.validator_value:
        return _set_in(inst, path, copy.deepcopy(err.validator_value[0]))
    if v == "type":
        return _set_in(inst, path, generate(schema, root_schema))
    if v in {"contains", "minContains"}:
        arr = inst if not path else _get_in(inst, path)
        if not isinstance(arr, list):
            return False
        piece_schema = err.validator_value if v == "contains" else schema.get("contains", True)
        piece = generate(piece_schema, root_schema)
        max_items = schema.get("maxItems")
        for i, el in enumerate(arr):
            try:
                ok = accepted(piece_schema, el) if piece_schema is not True else True
            except Exception:
                ok = False
            if not ok:
                if isinstance(el, dict) and isinstance(piece, dict):
                    el.update(piece)
                    return True
                arr[i] = piece
                return True
        if max_items is None or len(arr) < int(max_items):
            arr.append(piece)
            return True
        if arr:
            if isinstance(arr[-1], dict) and isinstance(piece, dict):
                arr[-1].update(piece)
            else:
                arr[-1] = piece
            return True
        arr.append(piece)
        return True
    if v == "minItems":
        arr = inst if not path else _get_in(inst, path)
        items = schema.get("items", {"type": "string"})
        need = int(err.validator_value)
        while isinstance(arr, list) and len(arr) < need:
            arr.append(generate(items, root_schema))
        return True
    if v == "maxItems":
        arr = inst if not path else _get_in(inst, path)
        if isinstance(arr, list):
            del arr[int(err.validator_value) :]
            return True
        return False
    if v == "minLength" and path:
        cur = _get_in(inst, path)
        if isinstance(cur, str):
            need = int(err.validator_value)
            return _set_in(inst, path, cur + ("x" * max(0, need - len(cur))))
        return False
    if v == "maxLength" and path:
        cur = _get_in(inst, path)
        if isinstance(cur, str):
            return _set_in(inst, path, cur[: int(err.validator_value)])
        return False
    if v == "minimum" and path:
        return _set_in(inst, path, err.validator_value)
    if v == "maximum" and path:
        return _set_in(inst, path, err.validator_value)
    if v == "minProperties":
        target = inst if not path else _get_in(inst, path)
        if not isinstance(target, dict):
            return False
        _fill_min_properties(target, schema, root_schema)
        return len(target) >= int(err.validator_value)
    if v == "maxProperties":
        target = inst if not path else _get_in(inst, path)
        if not isinstance(target, dict):
            return False
        cap = int(err.validator_value)
        while len(target) > cap:
            target.pop(next(iter(target)))
        return True
    if v == "pattern" and path:
        return _set_in(inst, path, _string({"pattern": err.validator_value, "type": "string"}))
    if v in {"additionalProperties", "unevaluatedProperties"} and path:
        parent = inst if len(path) == 1 else _get_in(inst, path[:-1])
        if isinstance(parent, dict):
            parent.pop(path[-1], None)
            return True
        return False
    return False


def generate_valid(schema: dict[str, Any], rounds: int = 48) -> Any:
    inst = generate(schema)
    for _ in range(rounds):
        errs = errors_for(schema, inst)
        if not errs:
            return inst
        progressed = False
        for e in errs:
            if repair(inst, e, schema):
                progressed = True
        if not progressed:
            break
    return inst


def _set_path(root: Any, parts: list[Any], value: Any) -> Any:
    doc = copy.deepcopy(root)
    cur = doc
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value
    return doc


def _del_path(root: Any, parts: list[Any]) -> Any:
    doc = copy.deepcopy(root)
    cur = doc
    for p in parts[:-1]:
        cur = cur[p]
    del cur[parts[-1]]
    return doc


def _mut(axis: str, path: str, instance: Any, expected: str, detail: str) -> dict[str, Any]:
    return {
        "axis": axis,
        "path": path or "$",
        "instance": instance,
        "expected_reason": expected,
        "detail": detail,
    }


def collect_mutants(schema: dict[str, Any], instance: Any) -> list[dict[str, Any]]:
    root = schema
    defs = _defs(root)
    out: list[dict[str, Any]] = []

    def walk(sub: Any, inst: Any, parts: list[Any]) -> None:
        s = resolve(sub, defs, root)
        if s is True or s is False or not isinstance(s, dict):
            return
        path = ".".join(str(p) for p in parts) if parts else "$"
        types = s.get("type")
        if isinstance(types, list):
            t0 = types[0] if types else None
        else:
            t0 = types
        if isinstance(inst, dict):
            addl = s.get("additionalProperties", True)
            if addl is False:
                mutated = copy.deepcopy(inst)
                mutated["__mutant_unknown__"] = True
                if parts:
                    whole = _set_path(instance, parts, mutated)
                else:
                    whole = mutated
                out.append(
                    _mut(
                        "inject_unknown_field",
                        path,
                        whole,
                        "additionalProperties",
                        "inject __mutant_unknown__",
                    )
                )
            for req in s.get("required") or []:
                if req in inst:
                    dropped = copy.deepcopy(inst)
                    del dropped[req]
                    if parts:
                        whole = _set_path(instance, parts, dropped)
                    else:
                        whole = dropped
                    out.append(
                        _mut(
                            "drop_required_field",
                            f"{path}.{req}" if path != "$" else req,
                            whole,
                            "required",
                            f"drop required {req}",
                        )
                    )
            props = s.get("properties") or {}
            for key, val in list(inst.items()):
                subsch = props.get(key)
                if subsch is None:
                    continue
                ss = resolve(subsch, defs, root)
                if ss is True or ss is False or not isinstance(ss, dict):
                    continue
                child_parts = parts + [key]
                child_path = ".".join(str(p) for p in child_parts)
                if "enum" in ss and val in (ss.get("enum") or []):
                    broken = _set_path(instance, child_parts, "NOT-IN-ENUM")
                    out.append(
                        _mut("break_enum", child_path, broken, "enum", f"break enum at {key}")
                    )
                if "const" in ss:
                    broken = _set_path(instance, child_parts, "NOT-THE-CONST")
                    out.append(
                        _mut("break_enum", child_path, broken, "const", f"break const at {key}")
                    )
                st = ss.get("type")
                if isinstance(st, list):
                    st = st[0] if st else None
                if isinstance(st, str) and st in TYPE_WIDEN:
                    broken = _set_path(instance, child_parts, copy.deepcopy(TYPE_WIDEN[st]))
                    out.append(
                        _mut("widen_type", child_path, broken, "type", f"widen {st} at {key}")
                    )
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if "maximum" in ss:
                        broken = _set_path(instance, child_parts, int(ss["maximum"]) + 1)
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "maximum",
                                f"exceed maximum at {key}",
                            )
                        )
                    if "minimum" in ss:
                        broken = _set_path(instance, child_parts, int(ss["minimum"]) - 1)
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "minimum",
                                f"below minimum at {key}",
                            )
                        )
                if isinstance(val, str):
                    if "maxLength" in ss:
                        broken = _set_path(
                            instance, child_parts, "x" * (int(ss["maxLength"]) + 1)
                        )
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "maxLength",
                                f"exceed maxLength at {key}",
                            )
                        )
                    if int(ss.get("minLength") or 0) > 0:
                        broken = _set_path(
                            instance, child_parts, "x" * (int(ss["minLength"]) - 1)
                        )
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "minLength",
                                f"below minLength at {key}",
                            )
                        )
                    if ss.get("pattern"):
                        broken = _set_path(instance, child_parts, "!!!not-a-match!!!")
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "pattern",
                                f"break pattern at {key}",
                            )
                        )
                if isinstance(val, list):
                    if "maxItems" in ss:
                        extra = list(val) + [copy.deepcopy(val[0]) if val else "extra"]
                        while len(extra) <= int(ss["maxItems"]):
                            extra.append("extra")
                        extra = extra[: int(ss["maxItems"]) + 1]
                        broken = _set_path(instance, child_parts, extra)
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "maxItems",
                                f"exceed maxItems at {key}",
                            )
                        )
                    if int(ss.get("minItems") or 0) > 0:
                        broken = _set_path(instance, child_parts, [])
                        out.append(
                            _mut(
                                "exceed_bound",
                                child_path,
                                broken,
                                "minItems",
                                f"below minItems at {key}",
                            )
                        )
                walk(ss, val, child_parts)
        if isinstance(inst, list) and isinstance(s.get("items"), dict):
            item_schema = s["items"]
            for i, el in enumerate(inst):
                walk(item_schema, el, parts + [i])

    walk(schema, instance, [])
    return out


def classify_mutant(schema: dict[str, Any], mutant: dict[str, Any]) -> dict[str, Any]:
    errs = errors_for(schema, mutant["instance"])
    expected = REASON_BY_AXIS.get(mutant["axis"], set())
    actual = [e.validator for e in errs]
    if not errs:
        verdict = "SURVIVED"
        matched = False
    else:
        matched = any(v in expected for v in actual)
        verdict = "KILLED" if matched else "KILLED-WRONG-REASON"
    rec = {
        "axis": mutant["axis"],
        "path": mutant["path"],
        "detail": mutant["detail"],
        "expected_reason": mutant["expected_reason"],
        "actual_reasons": actual[:8],
        "verdict": verdict,
        "matched_expected_reason": matched,
    }
    if verdict != "KILLED":
        rec["instance_excerpt"] = _excerpt(mutant["instance"])
    return rec


def _excerpt(inst: Any, limit: int = 400) -> Any:
    text = json.dumps(inst, sort_keys=True, default=str)
    if len(text) <= limit:
        return inst
    return text[:limit] + "…"


def tighten(schema: dict[str, Any]) -> dict[str, Any]:
    tight = copy.deepcopy(schema)
    props = tight.setdefault("properties", {})
    req = list(tight.get("required") or [])
    props[TIGHTEN_FIELD] = {"type": "string", "const": "LIVE-LOOP"}
    if TIGHTEN_FIELD not in req:
        req.append(TIGHTEN_FIELD)
    tight["required"] = req
    tight["additionalProperties"] = False
    return tight


def generator_sanity(schema: dict[str, Any]) -> dict[str, Any]:
    inst = generate_valid(schema)
    orig_ok = accepted(schema, inst)
    tight = tighten(schema)
    tight_errs = errors_for(tight, inst)
    tight_reject = bool(tight_errs)
    reasons = [e.validator for e in tight_errs]
    live = bool(orig_ok and tight_reject and "required" in reasons)
    return {
        "original_accepted": orig_ok,
        "tightened_rejected": tight_reject,
        "tightened_reasons": reasons[:8],
        "tighten_op": f"add required const field {TIGHTEN_FIELD}",
        "live": live,
        "instance_keys": sorted(inst.keys()) if isinstance(inst, dict) else [],
    }


def percentage_only_report() -> dict[str, Any]:
    return {
        "unit_id": "ARC-0109",
        "acceptance_rate": 1.0,
        "rejection_rate": 1.0,
        "kill_rate": 0.97,
        "per_schema": [{"id": "ARC-0078", "acceptance_rate": 1.0, "rejection_rate": 1.0}],
    }


def enumeration_ok(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    if "surviving_mutants" not in doc:
        return False, "percentage-only:surviving_mutants-absent"
    mutants = doc.get("surviving_mutants")
    if not isinstance(mutants, list):
        return False, "surviving_mutants-not-list"
    for i, row in enumerate(mutants):
        if not isinstance(row, dict):
            return False, f"surviving_mutants[{i}]-not-object"
        if not row.get("schema_id") or not row.get("axis") or not row.get("path"):
            return False, f"surviving_mutants[{i}]-incomplete"
        if not row.get("mutation_applied"):
            return False, f"surviving_mutants[{i}]-missing-mutation"
    n = int((doc.get("mutations") or {}).get("applied") or -1)
    if n < 0:
        return False, "mutations.applied-absent"
    if mutants:
        return True, f"enumerated:{len(mutants)}"
    return True, f"none-survived-after-{n}-operators"


def run_campaign() -> dict[str, Any]:
    dump_fixtures()
    per_schema: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    accept_ok = 0
    accept_fail = 0
    applied = 0
    killed = 0
    wrong = 0
    survived = 0
    corpus: list[dict[str, Any]] = []
    sanity_rows: list[dict[str, Any]] = []
    first_schema: dict[str, Any] | None = None
    for uid in S.CONTRACT_IDS:
        schema, source, path = load_contract(uid)
        if first_schema is None:
            first_schema = schema
        corpus.append(
            {
                "id": uid,
                "source": source,
                "path": path,
                "live_present": source == "live",
            }
        )
        inst = generate_valid(schema)
        ok = accepted(schema, inst)
        if ok:
            accept_ok += 1
        else:
            accept_fail += 1
            errs = errors_for(schema, inst)[:5]
            accept_fail_detail = [f"{e.validator}:{e.message}" for e in errs]
        mutants = collect_mutants(schema, inst)
        axis_counts: dict[str, dict[str, int]] = {
            a: {"applied": 0, "killed": 0, "survived": 0, "wrong_reason": 0} for a in AXES
        }
        schema_survived = 0
        schema_killed = 0
        schema_wrong = 0
        for m in mutants:
            rec = classify_mutant(schema, m)
            applied += 1
            axis_counts[m["axis"]]["applied"] += 1
            if rec["verdict"] == "KILLED":
                killed += 1
                schema_killed += 1
                axis_counts[m["axis"]]["killed"] += 1
            elif rec["verdict"] == "SURVIVED":
                survived += 1
                schema_survived += 1
                axis_counts[m["axis"]]["survived"] += 1
                survivors.append(
                    {
                        "schema_id": uid,
                        "axis": rec["axis"],
                        "path": rec["path"],
                        "mutation_applied": rec["detail"],
                        "expected_reason": rec["expected_reason"],
                        "actual_reasons": rec["actual_reasons"],
                        "verdict": rec["verdict"],
                        "instance_excerpt": rec.get("instance_excerpt"),
                    }
                )
            else:
                wrong += 1
                schema_wrong += 1
                axis_counts[m["axis"]]["wrong_reason"] += 1
                survivors.append(
                    {
                        "schema_id": uid,
                        "axis": rec["axis"],
                        "path": rec["path"],
                        "mutation_applied": rec["detail"],
                        "expected_reason": rec["expected_reason"],
                        "actual_reasons": rec["actual_reasons"],
                        "verdict": rec["verdict"],
                        "instance_excerpt": rec.get("instance_excerpt"),
                    }
                )
        row: dict[str, Any] = {
            "id": uid,
            "source": source,
            "accepted_instances": 1 if ok else 0,
            "rejected_instances": 0 if ok else 1,
            "acceptance_rate": 1.0 if ok else 0.0,
            "mutations_applied": len(mutants),
            "mutations_killed": schema_killed,
            "mutations_survived": schema_survived,
            "mutations_wrong_reason": schema_wrong,
            "rejection_rate": (schema_killed / len(mutants)) if mutants else 0.0,
            "axes": axis_counts,
        }
        if not ok:
            row["generator_errors"] = accept_fail_detail
        per_schema.append(row)
        sanity_rows.append({"id": uid, **generator_sanity(schema)})

    sanity = generator_sanity(first_schema or S.fixture_schema("ARC-0078"))
    live_n = sum(1 for c in corpus if c["live_present"])
    return {
        "corpus": corpus,
        "live_contracts_present": live_n,
        "fixture_schemas_used": len(corpus) - live_n,
        "generator": {
            "accepted": accept_ok,
            "rejected": accept_fail,
            "acceptance_rate": accept_ok / max(1, accept_ok + accept_fail),
        },
        "mutations": {
            "applied": applied,
            "killed": killed,
            "survived": survived,
            "wrong_reason": wrong,
            "rejection_rate": killed / applied if applied else 0.0,
        },
        "per_schema": per_schema,
        "surviving_mutants": survivors,
        "generator_sanity": sanity,
        "generator_sanity_per_schema": sanity_rows,
        "axes": list(AXES),
    }
