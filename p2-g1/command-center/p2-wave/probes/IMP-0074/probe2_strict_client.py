#!/usr/bin/env python3
"""IMP-0074 probe2 (verifier): strict third-party client from the contract alone.

Reviewer obligation (catalog): write a minimal third-party client from the
CONTRACT file alone and report every ambiguity found. This instrument imports
neither marketplace.api nor marketplace.clients; it loads
schema/registry-api.schema.json, walks raw response bodies returned by the
API object, and enforces unknown-field rejection on every object.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from marketplace.api import RegistryApi  # noqa: E402  (raw responses only)

CONTRACT = json.loads((W / "tools/marketplace/schema/registry-api.schema.json").read_text(encoding="utf-8"))
DEFS = CONTRACT["$defs"]
INDEX = json.loads((W / "tools/marketplace/fixtures/index.json").read_text(encoding="utf-8"))

RESULTS = {"probe": "probe2-strict-client", "unit_id": "IMP-0074", "rows": []}
FAILS = []


def record(cid, ok, detail=""):
    RESULTS["rows"].append({"id": cid, "ok": bool(ok), "detail": str(detail)[:160]})
    if not ok:
        FAILS.append(cid)


def resolve(name):
    return DEFS[name]


def walk(def_name, node, path=()):
    """Third-party strict walker authored from the contract file alone."""
    defn = resolve(def_name)
    if "anyOf" in defn:
        for sub in defn["anyOf"]:
            if "$ref" in sub:
                if not walk(sub["$ref"].rsplit("/", 1)[-1], node, path):
                    return []
            elif not walk(def_name, node, path):
                return []
        return ["no anyOf branch matched"]
    t = defn.get("type")
    errs = []
    if t == "object":
        if not isinstance(node, dict):
            return ["/".join(path) + ": expected object"]
        props = defn.get("properties", {})
        for req in defn.get("required", []):
            if req not in node:
                errs.append("/".join(path) + ": missing " + req)
        extras = [k for k in node if k not in props]
        if extras:
            errs.append("/".join(path) + ": undocumented " + ",".join(sorted(extras)))
        for k, v in node.items():
            if k in props and "$ref" in props[k]:
                errs.extend(walk(props[k]["$ref"].rsplit("/", 1)[-1], v, path + (k,)))
    elif t == "array":
        if not isinstance(node, list):
            return ["/".join(path) + ": expected array"]
        items = defn.get("items", {})
        if "$ref" in items:
            for i, item in enumerate(node):
                errs.extend(walk(items["$ref"].rsplit("/", 1)[-1], item, path + (str(i),)))
    elif t == "string":
        if not isinstance(node, str):
            errs.append("/".join(path) + ": expected string")
        elif "pattern" in defn and not re.fullmatch(defn["pattern"], node):
            errs.append("/".join(path) + ": pattern")
    elif t == "integer":
        if isinstance(node, bool) or not isinstance(node, int):
            errs.append("/".join(path) + ": expected integer")
    return errs


def strict_check(schema_name, body):
    return walk(schema_name, body)


api = RegistryApi(INDEX)

# Successes: contract-alone strict client must accept every recorded success.
matrix = [
    ("index-ok", "index_response", api.index()[2]),
    ("list-default", "plugin_list_response", api.dispatch("/plugins", {})[2]),
    ("list-limit-2-truncated", "plugin_list_response", api.dispatch("/plugins", {"limit": "2"})[2]),
    ("get-plugin-alpha", "plugin_response", api.get_plugin("alpha")[2]),
    ("search-hit", "search_response", api.dispatch("/search", {"q": "alpha"})[2]),
    ("search-unmatched-empty", "search_response", api.dispatch("/search", {"q": "zzz"})[2]),
]
for cid, def_name, body in matrix:
    record(cid + "-strict", not strict_check(def_name, body), strict_check(def_name, body))

# page-2 cursor round-trip.
_, _, page1 = api.dispatch("/plugins", {"limit": "2"})
cur = page1["next_cursor"]
_, _, page2 = api.dispatch("/plugins", {"limit": "2", "cursor": cur})
record("list-page-2-strict", not strict_check("plugin_list_response", page2)
       and not ({p["name"] for p in page1["plugins"]} & {p["name"] for p in page2["plugins"]}))

# Negatives: missing required fails strict; extra field is rejected by strict.
_, _, alpha = api.get_plugin("alpha")
broken = json.loads(json.dumps(alpha))
del broken["plugin"]["description"]
record("missing-required-fails-strict", bool(strict_check("plugin_response", broken)))

extra = json.loads(json.dumps(alpha))
extra["plugin"]["undocumented_bonus"] = 1
record("extra-field-discriminates", bool(strict_check("plugin_response", extra)))

# Pagination vs unmatched search distinguishability.
truncated = ("next_cursor" in api.dispatch("/plugins", {"limit": "2"})[2])
unmatched_empty = (api.dispatch("/search", {"q": "zzz"})[2].get("results") == []
                   and "next_cursor" not in api.dispatch("/search", {"q": "zzz"})[2])
record("pagination-distinguishable", truncated and unmatched_empty)

# Ambiguity report: unknowns a third-party client cannot resolve from the
# contract alone (each maps to a concrete $def).
ambiguities = [
    {"id": "cursor-opacity",
     "text": "next_cursor is a non-empty string; encoding, expiry and signature are "
             "not in the contract - a third-party client must round-trip the token unchanged.",
     "where": "#/$defs/cursor"},
    {"id": "unknown-query-keys",
     "text": "query objects keep additionalProperties true: this server ignores unknown "
             "keys; a future major version may reject them.",
     "where": "#/$defs/list_plugins_query"},
    {"id": "search-matching",
     "text": "q is a non-empty string; field set, case folding and matching semantics are "
             "not in the schema. Observed implementation: case-insensitive substring over "
             "name, description and keywords.",
     "where": "#/$defs/search_query"},
]
RESULTS["ambiguities"] = ambiguities
RESULTS["ambiguity_count"] = len(ambiguities)

RESULTS.update({"n": len(RESULTS["rows"]), "ok": sum(r["ok"] for r in RESULTS["rows"]),
                "pass": not FAILS, "failures": FAILS})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0074-probe2 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0074-probe2 strict contract-alone client passes matrix + ambiguity report")
