"""knowledge-graph front - shared estate knowledge graph on an embedded Kuzu DB.

The store and engine live in D:/opt/knowledge-graph (KG_HOME env overrides):
  - kgcore.py   : schema (Host/Credential/Finding/Technique/Engagement nodes;
                  reached_from/authenticated_to/exploited_via/found_during
                  edges) + the six tools, one embedded Kuzu 0.11.3 database
  - kuzucapi.py : ctypes binding of the official prebuilt kuzu_shared.dll
  - db/         : the database directory (created on first use)

Exposes via harness_invoke (backend "knowledge-graph"):
  add_node {label,id,props}  add_edge {type,from_id,to_id,props}
  neighbors {id,label?,rel?,direction?,limit?}
  shortest_path {src,dst,src_label?,dst_label?,max_hops?}
  search {q,limit?}          cypher {query,max_rows?}

Import stays light (lazy kgcore load) so the gateway's availability probe is
just an import check; the DB opens on first tool call and stays open for the
gateway's lifetime - one process, one store, no watchdogs.
"""
from __future__ import annotations

import json
import os
import sys

KG_HOME = os.environ.get("KG_HOME", r"D:\opt\knowledge-graph")

_tools_desc = ("add_node(label,id,props) add_edge(type,from_id,to_id,props) "
               "neighbors(id,label?,rel?,direction?,limit?) "
               "shortest_path(src,dst,src_label?,dst_label?,max_hops?) "
               "search(q,limit?) cypher(query,max_rows?)")


def _kg():
    if KG_HOME not in sys.path:
        sys.path.insert(0, KG_HOME)
    import kgcore  # heavy import: loads kuzu_shared.dll
    return kgcore


def run(tool: str, args: dict) -> str:
    try:
        kg = _kg()
    except Exception as exc:  # noqa: BLE001 - availability data, not a crash
        return json.dumps({"ok": False,
                           "error": f"knowledge-graph store unavailable: "
                                    f"{type(exc).__name__}: {exc}",
                           "kg_home": KG_HOME})
    if tool == "__tools__":
        return json.dumps({"ok": True, "tools": sorted(kg.TOOLS), "kg_home": KG_HOME})
    return kg.run(tool, args)
