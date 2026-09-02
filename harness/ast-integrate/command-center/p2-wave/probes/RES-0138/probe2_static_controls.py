#!/usr/bin/env python3
"""Probe 2: static audit, mechanically different from the runtime probe.

Does not call Stage.request. Inspects the committed control table and the
kernel source. A prohibition mapped only to a prompt is the failure mode.
A planted prompt-only mapping for 'transact' must fire. Default-off and
the single egress allowlist are read from source, not from a live fetch.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    CATALOG_PROHIBITIONS,
    DEFAULT_OWNER_OPT_IN,
    EGRESS_ALLOWLIST,
    METHOD_ALLOWLIST,
    PROMPT_ONLY,
    TECHNICAL_CONTROLS,
    missing_technical_enforcement,
    prompt_only_not_enforced,
)

OUT = HERE / "probe2-static-controls.raw.json"
STAGE = HERE / "stage.py"
CONTROLS = HERE / "controls.py"

NETWORK_IMPORTS = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "http.client",
        "urllib",
        "urllib.request",
        "urllib.error",
        "requests",
        "aiohttp",
        "torsocks",
    }
)
REQUIRED_FUNCS = {
    "method_gate",
    "egress_gate",
    "header_gate",
    "isolation_gate",
    "credential_lookup",
    "transcript_append",
}


def parse_imports_and_funcs(src: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(src)
    imported: set[str] = set()
    funcs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
        elif isinstance(node, ast.FunctionDef):
            funcs.add(node.name)
    return imported, funcs


def count_assign(src: str, name: str) -> int:
    tree = ast.parse(src)
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    n += 1
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                n += 1
    return n


def main() -> int:
    stage_src = STAGE.read_text(encoding="utf-8")
    controls_src = CONTROLS.read_text(encoding="utf-8")
    imported, funcs = parse_imports_and_funcs(stage_src)
    network_hits = sorted(imported & NETWORK_IMPORTS)
    missing_funcs = sorted(REQUIRED_FUNCS - funcs)

    good_missing = missing_technical_enforcement()
    mutant = [
        dict(r)
        for r in TECHNICAL_CONTROLS
        if r["prohibition"] != "transact"
    ]
    mutant.append(
        {
            "prohibition": "transact",
            "kind": "prompt",
            "enforcement_point": "system-prompt",
            "enforcement_status": "NOT ENFORCED",
            "how": "planted prompt-only mapping",
        }
    )
    mutant_missing = missing_technical_enforcement(mutant)

    prompt_ok = prompt_only_not_enforced()
    prompt_statuses = sorted({p["enforcement_status"] for p in PROMPT_ONLY})

    egress_assigns = count_assign(controls_src, "EGRESS_ALLOWLIST")
    method_ok = METHOD_ALLOWLIST == frozenset({"GET", "HEAD"})
    default_off = DEFAULT_OWNER_OPT_IN is False
    single_egress = egress_assigns == 1
    no_network = network_hits == []
    funcs_present = missing_funcs == []
    table_complete = good_missing == []
    mutant_fires = mutant_missing == ["transact"]
    no_socket_import = "import socket" not in stage_src and "import torsocks" not in stage_src
    no_connect_call = "socket.connect" not in stage_src

    points = {r["enforcement_point"] for r in TECHNICAL_CONTROLS}
    points_exist = points <= REQUIRED_FUNCS

    report = {
        "probe": "probe2-static-controls",
        "unit_id": "RES-0138",
        "default_owner_opt_in": DEFAULT_OWNER_OPT_IN,
        "method_allowlist": sorted(METHOD_ALLOWLIST),
        "egress_allowlist_size": len(EGRESS_ALLOWLIST),
        "egress_assign_count": egress_assigns,
        "network_imports": network_hits,
        "missing_enforcement_functions": missing_funcs,
        "catalog_prohibitions": list(CATALOG_PROHIBITIONS),
        "good_missing_technical": good_missing,
        "mutant_missing_technical": mutant_missing,
        "prompt_only_statuses": prompt_statuses,
        "enforcement_points": sorted(points),
        "flags": {
            "default_off": default_off,
            "method_ok": method_ok,
            "single_egress": single_egress,
            "no_network": no_network,
            "funcs_present": funcs_present,
            "table_complete": table_complete,
            "mutant_fires": mutant_fires,
            "prompt_ok": prompt_ok,
            "points_exist": points_exist,
            "no_socket_import": no_socket_import,
            "no_connect_call": no_connect_call,
        },
        "pass": False,
    }

    ok = (
        default_off
        and method_ok
        and single_egress
        and no_network
        and funcs_present
        and table_complete
        and mutant_fires
        and prompt_ok
        and points_exist
        and no_socket_import
        and no_connect_call
        and len(EGRESS_ALLOWLIST) == 1
        and prompt_statuses == ["NOT ENFORCED"]
    )
    report["pass"] = bool(ok)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "default_off="
        + str(default_off)
        + " methods="
        + ",".join(sorted(METHOD_ALLOWLIST))
        + " egress_assigns="
        + str(egress_assigns)
        + " network="
        + str(network_hits)
        + " table_complete="
        + str(table_complete)
        + " mutant_fires="
        + str(mutant_fires)
        + " prompts="
        + str(prompt_statuses)
    )
    if not ok:
        print("FAILED:RES-0138-probe2 static control audit did not pass")
        print(json.dumps(report, indent=2)[:4000])
        return 1
    print(
        "SUCCESS:RES-0138-probe2 default-off, single egress allowlist, "
        "prompt-only NOT ENFORCED, planted prompt mapping fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
