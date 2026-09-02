#!/usr/bin/env python3
"""Probe 2: every fan-in in the import graph imports the shared reducer.

Mechanically different from probe 1: no plant, no copy. Walk the AST
import graph, itemize each FANIN_ROLE site, and show the resolved
module+symbol. A file that only mentions the name in prose is not a
call site (grep would have listed it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

TREE = HERE / "fixtures" / "tree"

EXPECTED_ROLES = {
    "local-runner",
    "cloud-dispatcher",
    "monitor",
    "harvester",
    "workflow-fan-in",
    "cross-vendor-adapter",
    "final-synthesis",
}


def main() -> int:
    scan = D.scan_tree(TREE)
    sites = scan["call_sites"]
    roles = {s["role"] for s in sites}
    itemized = []
    for site in sites:
        itemized.append(
            {
                "role": site["role"],
                "path": site["path"],
                "qualname": site["qualname"],
                "imports_shared_reducer": site["imports_shared_reducer"],
                "import_kind": site["import_kind"],
                "bound_name": site["bound_name"],
                "resolved_module": site["resolved_module"],
                "resolved_symbol": site["resolved_symbol"],
                "import_lineno": site["import_lineno"],
                "call_linenos": site["call_linenos"],
            }
        )

    mention_as_site = any("mention_only" in s["path"] for s in sites)
    alias_site = next((s for s in sites if s["role"] == "cloud-dispatcher"), None)
    relative_site = next((s for s in sites if s["role"] == "harvester"), None)
    attr_site = next((s for s in sites if s["role"] == "monitor"), None)
    parent_site = next((s for s in sites if s["role"] == "workflow-fan-in"), None)

    checks = [
        ("method_is_ast", scan.get("method") == "ast-import-graph"),
        ("used_grep_false", scan.get("used_grep") is False),
        ("canonical_present", scan.get("canonical_present") is True),
        ("seven_fan_in_sites", len(sites) == 7),
        ("roles_complete", roles == EXPECTED_ROLES),
        ("every_site_imports_reducer", all(s["imports_shared_reducer"] for s in sites)),
        ("every_site_resolves_module", all(s["resolved_module"] == D.CANONICAL_MODULE for s in sites)),
        ("every_site_has_call", all(s["call_linenos"] for s in sites)),
        ("missing_imports_empty", not scan["missing_imports"]),
        ("mention_only_not_a_call_site", not mention_as_site),
        (
            "mention_only_listed_as_prose",
            "docs/mention_only.py" in scan["mention_only_files"],
        ),
        ("alias_bound_name_is_rc", bool(alias_site and alias_site["bound_name"] == "rc")),
        (
            "relative_import_kind",
            bool(relative_site and relative_site["import_kind"] == "from-import"),
        ),
        (
            "relative_import_level_resolved",
            bool(relative_site and relative_site["resolved_module"] == D.CANONICAL_MODULE),
        ),
        (
            "module_attribute_call",
            bool(attr_site and attr_site["import_kind"] == "import"),
        ),
        (
            "from_parent_import",
            bool(parent_site and parent_site["import_kind"] == "from-parent"),
        ),
        ("no_second_impl_on_clean", scan["zero_duplicates"] is True),
        ("graph_has_edges", len(scan["import_graph_edges"]) >= 7),
    ]
    payload = {
        "probe": "probe2-callsite-imports",
        "unit_id": "ARC-0107",
        "method": scan.get("method"),
        "fan_in_count": len(sites),
        "itemized_call_sites": itemized,
        "mention_only_files": scan.get("mention_only_files"),
        "import_graph_edge_count": len(scan["import_graph_edges"]),
        "checks": {name: bool(ok) for name, ok in checks},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0107-probe2 {name}")
            return 1
    print("SUCCESS:ARC-0107-probe2 every fan-in imports shared reducer (AST import graph)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
