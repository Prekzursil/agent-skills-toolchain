"""IMP-0074 registry API clients: lenient reference + strict third-party.

Both validate responses against schema/registry-api.schema.json with a
dependency-free contract walker (no jsonschema import: the workspace has a
platform/ directory that shadows the stdlib platform module when the REPO
root is on sys.path). The reference client tolerates undocumented extra
fields; the strict client rejects any response carrying a field the contract
does not declare.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "registry-api.schema.json"


def load_contract() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class ClientError(Exception):
    def __init__(self, status, code, message):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def resolve_ref(schema, defs):
    while isinstance(schema, dict) and "$ref" in schema:
        schema = defs[schema["$ref"].rsplit("/", 1)[-1]]
    return schema if isinstance(schema, dict) else {}


def validate_against_def(schema_name, body, defs, strict=False, path=()):
    """Validate a document against one named $def. Returns error strings."""
    defn = resolve_ref(defs.get(schema_name, {}), defs)
    return _walk(def_name=schema_name, node=body, defn=defn, defs=defs,
                 strict=strict, path=tuple(path))


def _join(path, fallback):
    return "/".join(path) or fallback


def _walk(def_name, node, defn, defs, strict, path):
    errs = []
    if "anyOf" in defn:
        for sub in defn["anyOf"]:
            name = sub["$ref"].rsplit("/", 1)[-1] if "$ref" in sub else def_name
            branch = _walk(name, node, resolve_ref(sub, defs), defs, strict, path)
            if not branch:
                return []
        return ["value matches no contract response def"]
    t = defn.get("type")
    if t == "object":
        if not isinstance(node, dict):
            return [_join(path, def_name) + ": expected object"]
        props = defn.get("properties", {})
        for req in defn.get("required", []):
            if req not in node:
                errs.append(_join(path, def_name) + ": missing required field " + req)
        extra = [k for k in node if props and k not in props]
        if extra and strict:
            errs.append(_join(path, def_name) + ": undocumented field(s) "
                        + ",".join(sorted(extra)))
        for k, v in node.items():
            if k in props:
                sub = props[k]
                errs.extend(_walk(def_name, v, resolve_ref(sub, defs), defs,
                                  strict, path + (k,)))
    elif t == "array":
        if not isinstance(node, list):
            return [_join(path, def_name) + ": expected array"]
        items = defn.get("items")
        for i, item in enumerate(node):
            errs.extend(_walk(def_name, item, resolve_ref(items or {}, defs),
                              defs, strict, path + (str(i),)))
    elif t == "string":
        if not isinstance(node, str):
            errs.append(_join(path, def_name) + ": expected string")
        else:
            if len(node) < defn.get("minLength", 0):
                errs.append(_join(path, def_name) + ": shorter than minLength")
            if "pattern" in defn and not re.fullmatch(defn["pattern"], node):
                errs.append(_join(path, def_name) + ": fails pattern")
            if "enum" in defn and node not in defn["enum"]:
                errs.append(_join(path, def_name) + ": not in enum")
    elif t == "integer":
        if isinstance(node, bool) or not isinstance(node, int):
            errs.append(_join(path, def_name) + ": expected integer")
        elif "minimum" in defn and node < defn["minimum"]:
            errs.append(_join(path, def_name) + ": below minimum")
    return errs


def _subschema_for(defn, key, defs):
    if not isinstance(defn, dict):
        return None
    props = defn.get("properties", {})
    if key in props:
        tgt = props[key]
        if isinstance(tgt, dict) and "$ref" in tgt:
            name = tgt["$ref"].rsplit("/", 1)[-1]
            return name
        return None
    items = defn.get("items")
    if isinstance(items, dict) and "$ref" in items:
        return items["$ref"].rsplit("/", 1)[-1]
    return None


class RegistryClient:
    """Reference (lenient) client: contract-validated, unknown fields OK."""

    strict = False

    def __init__(self, api):
        self._api = api
        contract = load_contract()
        self._defs = contract["$defs"]

    def _call(self, schema_name, result):
        status, got_name, body = result
        if status != 200:
            errs = validate_against_def("error_response", body, self._defs, True)
            if errs:
                raise ClientError(0, "contract-violating-error", "; ".join(errs[:4]))
            raise ClientError(status, body["error"]["code"], body["error"]["message"])
        errs = validate_against_def(schema_name, body, self._defs, self.strict)
        if errs:
            raise ClientError(0, schema_name + "-contract-violation", "; ".join(errs[:5]))
        return body

    def index(self):
        return self._call("index_response", self._api.index())

    def list_plugins(self, query=None):
        return self._call("plugin_list_response", self._api.list_plugins(query))

    def get_plugin(self, name):
        return self._call("plugin_response", self._api.get_plugin(name))

    def search(self, query=None):
        return self._call("search_response", self._api.search(query))


class StrictRegistryClient(RegistryClient):
    """Third-party strict client: rejects undocumented fields."""

    strict = True
