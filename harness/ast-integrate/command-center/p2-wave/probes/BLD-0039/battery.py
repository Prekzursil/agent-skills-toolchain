"""The 16-mutation control set against tools/command-center/validate.py.

Catalog mutations, run through the BARE CLI (no --require-complete) — the
invocation CI uses. Known rate: 15 killed / 1 survivor (V-FIELDS, defaults
block deleted). Isolation: every mutation is a tempfile copy.
"""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Any, Callable

import sys
from pathlib import Path as _P

_HERE = _P(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from isolate import (
    CC_TOOLS,
    REPO,
    find_item,
    fingerprint_shared,
    materialise_clean,
    run_validate_cli,
    write_json,
)

UNKNOWN = "UNKNOWN - not yet determined"

ApplyFn = Callable[[dict[str, Any], dict[str, Any]], None]


def _set_deps(catalog: dict[str, Any], item_id: str, deps: list[str]) -> None:
    find_item(catalog, item_id)["dependencies"] = deps


def _m01_dangling(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    _set_deps(catalog, "R-M01", ["R-DOES-NOT-EXIST"])
    ctx["diff"] = (
        "items[R-M01].dependencies: [] -> [\"R-DOES-NOT-EXIST\"]"
    )


def _m02_closed_on_open(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    target = find_item(catalog, "R-M01")
    target["status"] = "OPEN"
    target["disposition"] = None
    find_item(catalog, "T-01")["dependencies"] = ["R-M01"]
    ctx["diff"] = (
        "items[R-M01].disposition=null (force OPEN); "
        "items[T-01].dependencies -> [\"R-M01\"] (closed depends on open)"
    )


def _m03_cycle(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    _set_deps(catalog, "R-M01", ["R-M04"])
    ctx["diff"] = (
        "items[R-M01].dependencies -> [\"R-M04\"] "
        "(R-M04 already depends on R-M01)"
    )


def _m04_dead_end(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    find_item(catalog, "R-M08")["next_smallest_action"] = UNKNOWN
    ctx["diff"] = "items[R-M08].next_smallest_action -> UNKNOWN (no gate, no deps)"


def _m05_bad_gate(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    find_item(catalog, "R-B08")["owner_gate"] = ["OQ-999"]
    ctx["diff"] = "items[R-B08].owner_gate -> [\"OQ-999\"] (no such question)"


def _m06_no_evidence(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    find_item(catalog, "T-05")["disposition_evidence"] = "   "
    ctx["diff"] = "items[T-05].disposition_evidence -> whitespace-only"


def _m07_non_terminal(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    find_item(catalog, "T-05")["disposition"] = "PROBABLY-FINE"
    ctx["diff"] = "items[T-05].disposition -> \"PROBABLY-FINE\" (not terminal)"


def _m08_drop_item(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    catalog["items"] = [it for it in catalog["items"] if it.get("id") != "R-B06"]
    ctx["diff"] = "delete items[R-B06] (still present in isolated REGISTER.md)"


def _m09_tampered_register(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    ctx["register_text"] = "# not the register\n"
    ctx["diff"] = "REGISTER.md body replaced with \"# not the register\\n\" (sha256 mismatch)"


def _m10_missing_register(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    ctx["register_missing"] = True
    ctx["diff"] = "--register points at an absent file"


def _m11_blank_digest(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    catalog["provenance"]["register_sha256"] = ""
    ctx["diff"] = "provenance.register_sha256 -> \"\" (historical fail-open)"


def _m12_deleted_digest(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    del catalog["provenance"]["register_sha256"]
    ctx["diff"] = "delete provenance.register_sha256"


def _m13_stale_graph(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    graph = copy.deepcopy(ctx["base_graph"])
    graph["edge_count"] = 999
    ctx["graph"] = graph
    ctx["diff"] = "DEPENDENCY-GRAPH.json edge_count -> 999 (V-GRAPH)"


def _m14_dup_ids(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    catalog["items"].append(copy.deepcopy(find_item(catalog, "R-M01")))
    catalog["items"].append({"id": "R-", "title": "garbage"})
    ctx["diff"] = "append duplicate R-M01 and malformed id \"R-\""


def _m15_empty(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    catalog["items"] = []
    ctx["diff"] = "items -> [] (V-EMPTY fail-closed)"


def _m16_defaults(catalog: dict[str, Any], ctx: dict[str, Any]) -> None:
    catalog.pop("defaults", None)
    ctx["diff"] = (
        "delete catalog.defaults (V-FIELDS / require_complete=False under "
        "bare CLI; 0 of 103 items carry the nine defaulted fields)"
    )
    ctx["known_survivor"] = True


MUTATIONS: list[dict[str, Any]] = [
    {
        "id": "M01-REACH-1-dangling",
        "expect": "KILLED",
        "check": "REACH-1",
        "apply": _m01_dangling,
    },
    {
        "id": "M02-REACH-1-closed-on-open",
        "expect": "KILLED",
        "check": "REACH-1",
        "apply": _m02_closed_on_open,
    },
    {
        "id": "M03-REACH-2-cycle",
        "expect": "KILLED",
        "check": "REACH-2",
        "apply": _m03_cycle,
    },
    {
        "id": "M04-REACH-3-dead-end",
        "expect": "KILLED",
        "check": "REACH-3",
        "apply": _m04_dead_end,
    },
    {
        "id": "M05-REACH-4-missing-question",
        "expect": "KILLED",
        "check": "REACH-4",
        "apply": _m05_bad_gate,
    },
    {
        "id": "M06-REACH-5-no-evidence",
        "expect": "KILLED",
        "check": "REACH-5",
        "apply": _m06_no_evidence,
    },
    {
        "id": "M07-REACH-5-non-terminal",
        "expect": "KILLED",
        "check": "REACH-5",
        "apply": _m07_non_terminal,
    },
    {
        "id": "M08-REACH-6-dropped-item",
        "expect": "KILLED",
        "check": "REACH-6",
        "apply": _m08_drop_item,
    },
    {
        "id": "M09-REACH-6-tampered-register",
        "expect": "KILLED",
        "check": "REACH-6",
        "apply": _m09_tampered_register,
    },
    {
        "id": "M10-REACH-6-missing-register",
        "expect": "KILLED",
        "check": "REACH-6",
        "apply": _m10_missing_register,
    },
    {
        "id": "M11-REACH-6-blank-digest",
        "expect": "KILLED",
        "check": "REACH-6",
        "apply": _m11_blank_digest,
    },
    {
        "id": "M12-REACH-6-deleted-digest",
        "expect": "KILLED",
        "check": "REACH-6",
        "apply": _m12_deleted_digest,
    },
    {
        "id": "M13-V-GRAPH-stale",
        "expect": "KILLED",
        "check": "V-GRAPH",
        "apply": _m13_stale_graph,
    },
    {
        "id": "M14-V-ID-duplicate",
        "expect": "KILLED",
        "check": "V-ID",
        "apply": _m14_dup_ids,
    },
    {
        "id": "M15-V-EMPTY",
        "expect": "KILLED",
        "check": "V-EMPTY",
        "apply": _m15_empty,
    },
    {
        "id": "M16-V-FIELDS-defaults-deleted",
        "expect": "SURVIVED",
        "check": "V-FIELDS",
        "apply": _m16_defaults,
        "survivor_reason": (
            "require_complete defaults to False; bare CLI omits "
            "--require-complete; deleting defaults therefore exits 0"
        ),
    },
]


def _derive_graph(catalog: dict[str, Any]) -> dict[str, Any]:
    import sys

    sys.path.insert(0, str(CC_TOOLS))
    import catalog as cat  # noqa: WPS433

    return cat.build_graph(catalog)


def run_one(spec: dict[str, Any], tmp: Path, base: dict[str, Any]) -> dict[str, Any]:
    work = tmp / spec["id"]
    work.mkdir(parents=True, exist_ok=True)
    catalog = copy.deepcopy(base["catalog"])
    ctx: dict[str, Any] = {
        "base_graph": base["graph"],
        "register_text": base["register_text"],
        "graph": None,
        "register_missing": False,
        "diff": "",
        "known_survivor": False,
    }
    spec["apply"](catalog, ctx)
    if ctx["graph"] is None:
        ctx["graph"] = _derive_graph(catalog)
    cat_path = work / "catalog.json"
    graph_path = work / "graph.json"
    write_json(cat_path, catalog)
    write_json(graph_path, ctx["graph"])
    if ctx["register_missing"]:
        reg_path = work / "ABSENT-REGISTER.md"
    else:
        reg_path = work / "REGISTER.md"
        reg_path.write_text(ctx["register_text"], encoding="utf-8", newline="\n")
    cli = run_validate_cli(
        cat_path,
        graph_path,
        None if ctx["register_missing"] else reg_path,
        require_complete=False,
    )
    killed = cli["exit_code"] != 0
    verdict = "KILLED" if killed else "SURVIVED"
    return {
        "id": spec["id"],
        "expect": spec["expect"],
        "check": spec["check"],
        "verdict": verdict,
        "expect_matched": verdict == spec["expect"],
        "isolated_dir": str(work),
        "diff": ctx["diff"],
        "exit_code": cli["exit_code"],
        "command": " ".join(str(c) for c in cli["command"]),
        "verbatim_output": (cli["output"] or "")[-4000:],
        "known_survivor": bool(ctx["known_survivor"] or spec["expect"] == "SURVIVED"),
        "survivor_reason": spec.get("survivor_reason"),
        "suite": "tools/command-center/validate.py bare CLI (no --require-complete)",
    }


def run_control_set() -> dict[str, Any]:
    before = fingerprint_shared()
    with tempfile.TemporaryDirectory(prefix="bld0039-battery-") as raw:
        tmp = Path(raw)
        base = materialise_clean(tmp / "_clean")
        clean_cli = run_validate_cli(
            base["catalog_path"],
            base["graph_path"],
            base["register_path"],
            require_complete=False,
        )
        rows = [run_one(spec, tmp, base) for spec in MUTATIONS]
        after_inside = fingerprint_shared()
    after = fingerprint_shared()
    killed = [r for r in rows if r["verdict"] == "KILLED"]
    survived = [r for r in rows if r["verdict"] == "SURVIVED"]
    mismatches = [r["id"] for r in rows if not r["expect_matched"]]
    return {
        "n": len(rows),
        "killed": len(killed),
        "survived": len(survived),
        "firing_rate": f"{len(killed)}/{len(rows)}",
        "expected_killed": 15,
        "expected_survived": 1,
        "rate_matched": len(killed) == 15 and len(survived) == 1 and not mismatches,
        "mismatches": mismatches,
        "survivor_ids": [r["id"] for r in survived],
        "killed_ids": [r["id"] for r in killed],
        "clean_baseline_exit": clean_cli["exit_code"],
        "clean_baseline_output": (clean_cli["output"] or "")[-2000:],
        "rows": rows,
        "isolation": {
            "before": before["aggregate_sha256"],
            "after_during": after_inside["aggregate_sha256"],
            "after": after["aggregate_sha256"],
            "shared_tree_unchanged": (
                before["aggregate_sha256"] == after["aggregate_sha256"]
                and before["aggregate_sha256"] == after_inside["aggregate_sha256"]
            ),
            "files": before["files"],
        },
        "b08_mutation_runs": {
            "present": (REPO / "tools" / "mutation-gate").is_dir(),
            "note": (
                "B08 mutation-gate tree is absent on this worktree; the catalog "
                "control set is filled from the 16 deliberate validate.py mutations."
            ),
        },
    }


def assert_control_green(result: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if result.get("n") != 16:
        errs.append(f"n={result.get('n')} want=16")
    if result.get("killed") != 15 or result.get("survived") != 1:
        errs.append(f"rate {result.get('firing_rate')} want=15/16")
    if result.get("clean_baseline_exit") != 0:
        errs.append(
            f"clean baseline exit {result.get('clean_baseline_exit')} want=0"
        )
    if result.get("survivor_ids") != ["M16-V-FIELDS-defaults-deleted"]:
        errs.append(f"survivor {result.get('survivor_ids')}")
    if not result.get("isolation", {}).get("shared_tree_unchanged"):
        errs.append("shared tree changed during control set")
    if result.get("mismatches"):
        errs.append(f"expect mismatches {result['mismatches']}")
    killed_row = next(
        (r for r in result["rows"] if r["id"] == "M01-REACH-1-dangling"), None
    )
    if not killed_row or killed_row["verdict"] != "KILLED":
        errs.append("positive control M01 was not KILLED")
    return errs
