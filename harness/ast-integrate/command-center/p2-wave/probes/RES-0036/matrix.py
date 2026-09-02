"""Rebuild the revision-by-capability matrix from frozen MCP JSON Schemas.

Every cell carries spec_revision_id equal to the schema directory name.
Presence is derived from the schema (property on ServerCapabilities /
ClientCapabilities, or JSON-RPC method const), not from prose memory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROBE = Path(__file__).resolve().parent
SPEC_ROOT = PROBE / "fixtures" / "spec"
REVISIONS = [
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
    "2026-07-28",
]
DEPRECATED_OPTIONAL_2026 = frozenset(
    {"server.logging", "client.roots", "client.sampling"}
)
PRESENCES = frozenset(
    {"absent", "optional", "mandatory", "deprecated-optional"}
)


def definitions(schema: dict) -> dict:
    return schema.get("definitions") or schema.get("$defs") or {}


def def_bucket(schema: dict) -> str:
    return "definitions" if "definitions" in schema else "$defs"


def resolve(schema: dict, node: dict) -> dict:
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    cur: Any = schema
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(cur, dict) or part not in cur:
            return node
        cur = cur[part]
    return cur if isinstance(cur, dict) else node


def collect_methods(schema: dict) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            meth = node.get("method")
            if isinstance(meth, dict) and "const" in meth:
                found.add(str(meth["const"]))
            elif isinstance(meth, dict) and "enum" in meth:
                found.update(str(x) for x in meth["enum"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return found


def cap_props(schema: dict, type_name: str) -> tuple[dict, set[str]]:
    obj = definitions(schema).get(type_name) or {}
    return obj.get("properties") or {}, set(obj.get("required") or [])


def nested_props(schema: dict, cap_node: dict) -> tuple[dict, set[str]]:
    node = resolve(schema, cap_node)
    return node.get("properties") or {}, set(node.get("required") or [])


def load_schema(rev: str) -> dict:
    return json.loads((SPEC_ROOT / rev / "schema.json").read_text(encoding="utf-8"))


def cap_presence(prop: str, required: set[str], rev: str, cap_id: str) -> str:
    if cap_id in DEPRECATED_OPTIONAL_2026 and rev == "2026-07-28":
        return "deprecated-optional"
    if prop in required:
        return "mandatory"
    return "optional"


def cell(
    *,
    capability: str,
    rev: str,
    presence: str,
    pointer: str,
    methods: list[str],
    nested: list[str],
    notes: str = "",
) -> dict:
    return {
        "capability": capability,
        "spec_revision_id": rev,
        "presence": presence,
        "json_schema_required": presence == "mandatory",
        "schema_pointer": pointer,
        "methods_in_schema": methods,
        "nested_flags": nested,
        "notes": notes,
    }


def revision_cells(rev: str, schema: dict) -> list[dict]:
    methods = collect_methods(schema)
    server_props, server_req = cap_props(schema, "ServerCapabilities")
    client_props, client_req = cap_props(schema, "ClientCapabilities")
    bucket = def_bucket(schema)
    out: list[dict] = []

    def add_method(cap_id: str, method: str, when_present: str, note: str) -> None:
        present = method in methods
        out.append(
            cell(
                capability=cap_id,
                rev=rev,
                presence=when_present if present else "absent",
                pointer=f"method:{method}",
                methods=[method] if present else [],
                nested=[],
                notes=note if present else "method const absent from this schema",
            )
        )

    add_method(
        "session.initialize",
        "initialize",
        "mandatory",
        "Handshake-era session bootstrap. Lifecycle prose requires this RPC to start a session in this revision.",
    )
    add_method(
        "session.notifications/initialized",
        "notifications/initialized",
        "mandatory",
        "Handshake-era completion notification paired with initialize.",
    )
    add_method(
        "session.ping",
        "ping",
        "optional",
        "Keepalive RPC. Present in handshake-era schemas; removed in 2026-07-28.",
    )
    add_method(
        "session.server/discover",
        "server/discover",
        "mandatory",
        "Modern-era server RPC. Spec prose: servers MUST implement server/discover; clients MAY call it.",
    )

    feature_rows = [
        ("server.tools", "ServerCapabilities", server_props, server_req, ["tools/list", "tools/call"], "tools"),
        ("server.resources", "ServerCapabilities", server_props, server_req, ["resources/list", "resources/read", "resources/templates/list"], "resources"),
        ("server.prompts", "ServerCapabilities", server_props, server_req, ["prompts/list", "prompts/get"], "prompts"),
        ("server.logging", "ServerCapabilities", server_props, server_req, ["logging/setLevel", "notifications/message"], "logging"),
        ("server.completions", "ServerCapabilities", server_props, server_req, ["completion/complete"], "completions"),
        ("server.experimental", "ServerCapabilities", server_props, server_req, [], "experimental"),
        ("server.tasks", "ServerCapabilities", server_props, server_req, ["tasks/cancel", "tasks/get", "tasks/list", "tasks/result"], "tasks"),
        ("server.extensions", "ServerCapabilities", server_props, server_req, [], "extensions"),
        ("client.roots", "ClientCapabilities", client_props, client_req, ["roots/list"], "roots"),
        ("client.sampling", "ClientCapabilities", client_props, client_req, ["sampling/createMessage"], "sampling"),
        ("client.experimental", "ClientCapabilities", client_props, client_req, [], "experimental"),
        ("client.elicitation", "ClientCapabilities", client_props, client_req, ["elicitation/create"], "elicitation"),
        ("client.tasks", "ClientCapabilities", client_props, client_req, ["tasks/cancel", "tasks/get", "tasks/list", "tasks/result"], "tasks"),
        ("client.extensions", "ClientCapabilities", client_props, client_req, [], "extensions"),
    ]
    for cap_id, type_name, props, req, meths, prop in feature_rows:
        pointer = f"#/{bucket}/{type_name}/properties/{prop}"
        node = props.get(prop)
        if node is None:
            extra = ""
            if cap_id == "server.completions" and "completion/complete" in methods:
                extra = (
                    "completion/complete method exists in this schema, but "
                    "ServerCapabilities.completions is absent (capability flag added 2025-03-26)."
                )
            out.append(
                cell(
                    capability=cap_id,
                    rev=rev,
                    presence="absent",
                    pointer=pointer,
                    methods=sorted(m for m in meths if m in methods),
                    nested=[],
                    notes=extra or "property absent from capabilities object",
                )
            )
            continue
        nprops, nreq = nested_props(schema, node)
        out.append(
            cell(
                capability=cap_id,
                rev=rev,
                presence=cap_presence(prop, req, rev, cap_id),
                pointer=pointer,
                methods=sorted(m for m in meths if m in methods),
                nested=sorted(nprops.keys()),
                notes=(
                    "JSON Schema does not list this property in required[]; advertising it is optional."
                    + (f" Nested required: {sorted(nreq)}." if nreq else "")
                ),
            )
        )

    res_node = server_props.get("resources")
    if res_node is None:
        out.append(
            cell(
                capability="server.resources.subscribe",
                rev=rev,
                presence="absent",
                pointer=f"#/{bucket}/ServerCapabilities/properties/resources/properties/subscribe",
                methods=sorted(m for m in ("resources/subscribe", "resources/unsubscribe") if m in methods),
                nested=[],
                notes="parent resources capability absent",
            )
        )
    else:
        nprops, nreq = nested_props(schema, res_node)
        sub = nprops.get("subscribe")
        out.append(
            cell(
                capability="server.resources.subscribe",
                rev=rev,
                presence="optional" if sub is not None else "absent",
                pointer=f"#/{bucket}/ServerCapabilities/properties/resources/properties/subscribe",
                methods=sorted(m for m in ("resources/subscribe", "resources/unsubscribe") if m in methods),
                nested=[],
                notes=(
                    "nested flag; required=" + str("subscribe" in nreq)
                    if sub is not None
                    else "subscribe flag absent"
                ),
            )
        )

    el_node = client_props.get("elicitation")
    if el_node is None:
        out.append(
            cell(
                capability="client.elicitation.url",
                rev=rev,
                presence="absent",
                pointer=f"#/{bucket}/ClientCapabilities/properties/elicitation/properties/url",
                methods=[],
                nested=[],
                notes="parent elicitation capability absent",
            )
        )
    else:
        nprops, nreq = nested_props(schema, el_node)
        url = nprops.get("url")
        out.append(
            cell(
                capability="client.elicitation.url",
                rev=rev,
                presence="optional" if url is not None else "absent",
                pointer=f"#/{bucket}/ClientCapabilities/properties/elicitation/properties/url",
                methods=[],
                nested=sorted(nprops.keys()),
                notes=(
                    "URL-mode elicitation nested flag; required=" + str("url" in nreq)
                    if url is not None
                    else "elicitation present as empty object; url flag not yet in schema"
                ),
            )
        )
    return out


def cap_sort_key(cid: str) -> tuple:
    side = cid.split(".", 1)[0]
    return {"session": 0, "server": 1, "client": 2}.get(side, 9), cid


def build_matrix() -> dict:
    columns = []
    cells: list[dict] = []
    for rev in REVISIONS:
        schema = load_schema(rev)
        defs = definitions(schema)
        columns.append(
            {
                "spec_revision_id": rev,
                "schema_path": f"command-center/p2-wave/probes/RES-0036/fixtures/spec/{rev}/schema.json",
                "has_server_capabilities": "ServerCapabilities" in defs,
                "has_client_capabilities": "ClientCapabilities" in defs,
                "method_count": len(collect_methods(schema)),
            }
        )
        cells.extend(revision_cells(rev, schema))
    capabilities = sorted({c["capability"] for c in cells}, key=cap_sort_key)
    cells.sort(key=lambda c: (cap_sort_key(c["capability"]), c["spec_revision_id"]))
    return {
        "spec_revision_ids": list(REVISIONS),
        "capability_ids": capabilities,
        "columns": columns,
        "cells": cells,
    }


def assert_every_cell_cites_revision(matrix: dict) -> None:
    allowed = set(REVISIONS)
    cells = matrix["cells"]
    if not cells:
        raise SystemExit("FAILED:RES-0036 empty matrix")
    expected = len(matrix["capability_ids"]) * len(REVISIONS)
    if len(cells) != expected:
        raise SystemExit(
            f"FAILED:RES-0036 expected {expected} cells, got {len(cells)}"
        )
    for item in cells:
        if item.get("spec_revision_id") not in allowed:
            raise SystemExit(f"FAILED:RES-0036 cell missing/invalid spec_revision_id: {item}")
        if not item.get("capability"):
            raise SystemExit(f"FAILED:RES-0036 cell missing capability: {item}")
        if item.get("presence") not in PRESENCES:
            raise SystemExit(f"FAILED:RES-0036 bad presence: {item}")


if __name__ == "__main__":
    matrix = build_matrix()
    assert_every_cell_cites_revision(matrix)
    print(
        json.dumps(
            {
                "revisions": matrix["spec_revision_ids"],
                "capabilities": matrix["capability_ids"],
                "cells": len(matrix["cells"]),
            },
            indent=2,
        )
    )
