#!/usr/bin/env python3
"""Probe 2: static audit, mechanically different from the dry-run probe.

Does not call Stage.request. Inspects the committed kernel: default-off,
mandatory log sink, TOR-DERIVED labelling, no network imports, and the
control table versus the ADV-0054 never-list. A planted prompt-only
mapping for 'transact' must fire. Runtime refusal is worthless if the
capability can be enabled without logging.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import COLLAPSE_IDS, NEVER_LIST_IDS  # noqa: E402
from sut import (  # noqa: E402
    CATALOG_PROHIBITIONS,
    DEFAULT_OWNER_OPT_IN,
    EGRESS_ALLOWLIST,
    LABEL_TOR_DERIVED,
    METHOD_ALLOWLIST,
    PROMPT_ONLY,
    STAGE_PY,
    TECHNICAL_CONTROLS,
    missing_technical_enforcement,
    prompt_only_not_enforced,
)

OUT = HERE / "probe2-static-default-off-logged.raw.json"

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
    "enable",
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


def enable_requires_sink(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "enable":
            continue
        none_check = False
        raises_sink = False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Compare):
                names = []
                if isinstance(sub.left, ast.Name):
                    names.append(sub.left.id)
                names.extend(
                    c.id for c in sub.comparators if isinstance(c, ast.Name)
                )
                if "transcript" in names and any(
                    isinstance(c, ast.Constant) and c.value is None
                    for c in [sub.left, *sub.comparators]
                ):
                    none_check = True
            if isinstance(sub, ast.Raise) and sub.exc is not None:
                exc = sub.exc
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    if exc.func.id == "LogSinkRequired":
                        raises_sink = True
                elif isinstance(exc, ast.Name) and exc.id == "LogSinkRequired":
                    raises_sink = True
        return none_check and raises_sink
    return False


def allowed_assigns_tor_derived(src: str) -> bool:
    """LABEL_TOR_DERIVED is assigned on the ALLOWED path."""
    if 'LABEL_TOR_DERIVED = "TOR-DERIVED"' not in src:
        return False
    if "decision.label = LABEL_TOR_DERIVED" not in src:
        return False
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare):
            continue
        left_ok = (
            isinstance(test.left, ast.Attribute)
            and test.left.attr == "action"
        )
        right_ok = any(
            isinstance(c, ast.Constant) and c.value == "ALLOWED"
            for c in test.comparators
        )
        if not (left_ok and right_ok):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Assign)
                and sub.targets
                and isinstance(sub.targets[0], ast.Attribute)
                and sub.targets[0].attr == "label"
            ):
                return True
    return False


def main() -> int:
    stage_src = STAGE_PY.read_text(encoding="utf-8")
    imported, funcs = parse_imports_and_funcs(stage_src)
    network_hits = sorted(imported & NETWORK_IMPORTS)
    missing_funcs = sorted(REQUIRED_FUNCS - funcs)

    good_missing = missing_technical_enforcement()
    mutant = [dict(r) for r in TECHNICAL_CONTROLS if r["prohibition"] != "transact"]
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

    named_in_table = {r["prohibition"] for r in TECHNICAL_CONTROLS}
    extra_absent_from_table = sorted(
        i for i in NEVER_LIST_IDS if i in COLLAPSE_IDS and i not in named_in_table
    )
    catalog_named_present = all(
        p in named_in_table for p in CATALOG_PROHIBITIONS
    )

    default_off = DEFAULT_OWNER_OPT_IN is False
    method_ok = METHOD_ALLOWLIST == frozenset({"GET", "HEAD"})
    no_network = network_hits == []
    funcs_present = missing_funcs == []
    table_complete = good_missing == []
    mutant_fires = mutant_missing == ["transact"]
    sink_required = enable_requires_sink(stage_src)
    labeled = allowed_assigns_tor_derived(stage_src)
    label_const = LABEL_TOR_DERIVED == "TOR-DERIVED"
    no_socket_import = (
        "import socket" not in stage_src and "import torsocks" not in stage_src
    )
    no_connect_call = "socket.connect" not in stage_src
    points = {r["enforcement_point"] for r in TECHNICAL_CONTROLS}
    points_exist = points <= (REQUIRED_FUNCS | {"transcript_append"})
    single_egress = len(EGRESS_ALLOWLIST) == 1
    extra_four_absent = extra_absent_from_table == sorted(COLLAPSE_IDS)

    report = {
        "probe": "probe2-static-default-off-logged",
        "unit_id": "ADV-0054",
        "live_onion_connection": False,
        "called_stage_request": False,
        "default_owner_opt_in": DEFAULT_OWNER_OPT_IN,
        "label_tor_derived": LABEL_TOR_DERIVED,
        "method_allowlist": sorted(METHOD_ALLOWLIST),
        "egress_allowlist_size": len(EGRESS_ALLOWLIST),
        "network_imports": network_hits,
        "missing_enforcement_functions": missing_funcs,
        "catalog_prohibitions": list(CATALOG_PROHIBITIONS),
        "adv0054_never_list": list(NEVER_LIST_IDS),
        "good_missing_technical": good_missing,
        "mutant_missing_technical": mutant_missing,
        "prompt_only_statuses": prompt_statuses,
        "extra_neverlist_absent_from_table": extra_absent_from_table,
        "enforcement_points": sorted(points),
        "stage_path": "command-center/p2-wave/probes/RES-0138/stage.py",
        "controls_path": "command-center/p2-wave/probes/RES-0138/controls.py",
        "flags": {
            "default_off": default_off,
            "method_ok": method_ok,
            "no_network": no_network,
            "funcs_present": funcs_present,
            "table_complete": table_complete,
            "mutant_fires": mutant_fires,
            "prompt_ok": prompt_ok,
            "points_exist": points_exist,
            "no_socket_import": no_socket_import,
            "no_connect_call": no_connect_call,
            "sink_required": sink_required,
            "labeled": labeled,
            "label_const": label_const,
            "single_egress": single_egress,
            "catalog_named_present": catalog_named_present,
            "extra_four_absent": extra_four_absent,
        },
        "pass": False,
    }

    ok = (
        default_off
        and method_ok
        and no_network
        and funcs_present
        and table_complete
        and mutant_fires
        and prompt_ok
        and points_exist
        and no_socket_import
        and no_connect_call
        and sink_required
        and labeled
        and label_const
        and single_egress
        and catalog_named_present
        and extra_four_absent
        and prompt_statuses == ["NOT ENFORCED"]
    )
    report["pass"] = bool(ok)
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "default_off="
        + str(default_off)
        + " sink_required="
        + str(sink_required)
        + " labeled="
        + str(labeled)
        + " methods="
        + ",".join(sorted(METHOD_ALLOWLIST))
        + " network="
        + str(network_hits)
        + " extra_absent="
        + str(extra_absent_from_table)
        + " mutant_fires="
        + str(mutant_fires)
    )
    if not ok:
        print("FAILED:ADV-0054-probe2 static default-off/logged/labelled audit")
        print(json.dumps(report["flags"], indent=2))
        return 1
    print(
        "SUCCESS:ADV-0054-probe2 default-off, mandatory log sink, "
        "TOR-DERIVED label, planted prompt mapping fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
