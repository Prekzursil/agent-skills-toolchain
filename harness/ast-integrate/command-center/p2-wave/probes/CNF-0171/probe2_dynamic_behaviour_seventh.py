#!/usr/bin/env python3
"""Probe 2 (mechanically different): dynamic import, corpus, seventh-site grep.

Dynamic-import control: a site that binds judge via importlib.import_module
must still resolve to the library object; live declared sites have no string
imports, so that live case is NOT-CHECKED rather than assumed.

Behavioural corpus is a SECOND signal only.

Reviewer: grep for a seventh call site not in the declared six.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools"))

import corpus as C  # noqa: E402
import identity as I  # noqa: E402
from completion.sites import load_site  # noqa: E402


def _check(site_id: str, payload: dict) -> dict:
    return load_site(site_id).check_unit(payload)


def main() -> int:
    live = I.resolve_declared_sites()
    live_dynamic = [
        dyn for row in live for dyn in (row.get("ast") or {}).get("dynamic_imports") or []
    ]
    live_unresolved = [
        dyn for row in live for dyn in (row.get("ast") or {}).get("dynamic_unresolved") or []
    ]

    fixture = HERE / "fixtures" / "dynamic_import_site.py"
    dyn_mod = I.load_path_as_module(fixture, "cnf0171_dynamic_import_site")
    dyn_row = I.resolve_site_file(fixture, site_id="dynamic_fixture", module=dyn_mod)
    dyn_ok = (
        dyn_row["identity_status"] == "SHARED"
        and dyn_row["bound_judge"].get("same_object_as_library") is True
        and not dyn_row["static_import_graph_ok"]
        and bool((dyn_row.get("ast") or {}).get("dynamic_imports"))
    )

    live_dynamic_status = "NOT-CHECKED"
    live_dynamic_reason = (
        "none of the six declared live sites import judge by string name; "
        "static ImportFrom was resolved instead of assumed. The string-name "
        "resolver is demonstrated on fixtures/dynamic_import_site.py."
    )
    if live_unresolved:
        live_dynamic_status = "NOT-CHECKED"
        live_dynamic_reason = "live site has a non-literal dynamic import"
        dyn_ok = False
    elif live_dynamic:
        live_dynamic_status = "RESOLVED"
        live_dynamic_reason = "a declared site uses a string-name import; see live_rows"

    behaviour = C.run_corpus(_check, list(I.DECLARED_SITE_IDS), I.SITE_ALIASES)

    undeclared = I.find_undeclared_reducer_importers()
    on_disk = I.site_files_on_disk()
    seventh = [h for h in undeclared if I.SEVENTH_SITE_ID in h["path"]]
    seventh_mod = I.load_site_module(I.SEVENTH_SITE_ID)
    seventh_row = I.resolve_site_file(
        I.REPO / I.SITE_FILES[I.SEVENTH_SITE_ID],
        site_id=I.SEVENTH_SITE_ID,
        module=seventh_mod,
    )

    reviewer_ok = bool(seventh) and seventh_row["identity_status"] == "SHARED"
    ok = bool(dyn_ok and behaviour["all_sites_agree"] and reviewer_ok and not live_unresolved)

    payload = {
        "probe": "probe2-dynamic-behaviour-seventh",
        "unit_id": "CNF-0171",
        "pass": ok,
        "dynamic_import_control": {
            "live_declared_sites": live_dynamic_status,
            "live_reason": live_dynamic_reason,
            "live_dynamic_imports": live_dynamic,
            "live_unresolved": live_unresolved,
            "fixture_path": "command-center/p2-wave/probes/CNF-0171/fixtures/dynamic_import_site.py",
            "fixture_resolved_to_library": dyn_ok,
            "fixture_identity_status": dyn_row["identity_status"],
            "fixture_static_import_graph_ok": dyn_row["static_import_graph_ok"],
            "fixture_dynamic_imports": (dyn_row.get("ast") or {}).get("dynamic_imports"),
            "fixture_object_id": dyn_row.get("object_id"),
            "fixture_resolved_import_path": dyn_row.get("resolved_import_path"),
        },
        "behavioural_cross_check": behaviour,
        "behavioural_is_second_signal": True,
        "reviewer_seventh_site": {
            "declared_list": list(I.DECLARED_SITE_IDS),
            "site_py_files_on_disk": on_disk,
            "grep_hits_outside_declared_six": undeclared,
            "seventh_found": [h["path"] for h in seventh],
            "seventh_identity": seventh_row["identity_status"],
            "seventh_same_object_as_library": seventh_row["bound_judge"].get(
                "same_object_as_library"
            ),
            "seventh_object_id": seventh_row.get("object_id"),
            "seventh_resolved_import_path": seventh_row.get("resolved_import_path"),
            "note": (
                "CNF-0171's declared list is the six named in the unit question. "
                "final_synthesis.py is the seventh production site; it binds the "
                "same library object, so it is undeclared-list completeness, not "
                "a sixth lookalike."
            ),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not dyn_ok:
        print("FAILED:CNF-0171-probe2 dynamic-import fixture did not resolve to library judge")
        return 1
    if not behaviour["all_sites_agree"]:
        print("FAILED:CNF-0171-probe2 behavioural corpus disagreement")
        return 1
    if not reviewer_ok:
        print("FAILED:CNF-0171-probe2 seventh call site grep/identity")
        return 1
    print(
        "dynamic_fixture=SHARED live_dynamic="
        f"{live_dynamic_status} corpus_agree=True seventh={seventh[0]['path']}"
    )
    print("SUCCESS:CNF-0171-probe2 dynamic import, corpus, seventh-site reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
