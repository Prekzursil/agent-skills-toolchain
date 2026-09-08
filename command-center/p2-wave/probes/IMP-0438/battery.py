#!/usr/bin/env python3
"""validate.py mutation battery for IMP-0438.

Sixteen catalog/CLI mutations, each aimed at a check the tool claims. Caught ==
process exit != 0 under the bare CI invocation
(`python tools/command-center/validate.py`).

Historical survivor (named before the fix): M16 delete-entire-defaults-block.
Pre-IMP-0436/0437, V-FIELDS only appended violations when require_complete was
True and that flag defaulted False, so bare CI printed SUCCESS while Prompt Two
fields were unresolved. On this tip:

- IMP-0436 landed always-on V-DEFAULTS, so M16 exits nonzero even under
  `--no-require-complete` (the historical "disarmed sole survivor" claim is
  REFUTED here; recorded verbatim, never invented as exit 0).
- IMP-0437 armed require_complete by default (CLI BooleanOptionalAction).

The seventeenth mutation slot is reserved for an adversarial refuter: a novel
mutant the battery has never seen. Historical M17 (delete defaults.timeout_seconds)
is retained only as a known expansion / regression control — it is NOT a
substitute for the adversarial review gate. SUCCESS is withheld until that
review lands (see _pack_receipt.py).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools" / "command-center"
VALIDATE = TOOLS / "validate.py"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
GRAPH = REPO / "command-center" / "DEPENDENCY-GRAPH.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import catalog as cat  # noqa: E402

UNKNOWN = cat.UNKNOWN


def find(catalog: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in catalog["items"]:
        if item["id"] == item_id:
            return item
    raise KeyError(item_id)


def load_slim() -> dict[str, Any]:
    """Load the catalog without the 2007-row work_units overlay.

    validate.py grades `items` (the 103-row register), not `work_units`.
    Stripping the overlay is a fixture shrink, not a mutation under test.
    """
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    data.pop("work_units", None)
    return data


def dump_json(path: Path, doc: Any) -> None:
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


_SECTION_H2 = (
    ("OUTSTANDING", "## 1. OUTSTANDING"),
    ("DELIBERATELY-SKIPPED", "## 2. DELIBERATELY-SKIPPED"),
    ("SUPERSEDED", "## 3. SUPERSEDED"),
    ("SETTLED", "## 4. SETTLED"),
)


def synthesize_register(items: list[dict[str, Any]]) -> str:
    """Minimal REGISTER.md the parser accepts, one row per catalog item.

    This worktree has no command-center/sources/REGISTER.md. REACH-6 would then
    fail every run (including CONTROL and M16), which is a confounder: a missing
    snapshot is not the V-FIELDS hole. The fixture is generated from the same
    `items` the mutation is about to edit, then hashed into provenance.
    """
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in _SECTION_H2}
    for item in items:
        section = str(item.get("section") or "OUTSTANDING")
        if section not in buckets:
            section = "OUTSTANDING"
        buckets[section].append(item)
    parts = ["# REGISTER (IMP-0438 battery fixture)", ""]
    for name, heading in _SECTION_H2:
        parts.append(heading)
        parts.append("")
        parts.append("| id | title |")
        parts.append("| --- | --- |")
        for item in buckets[name]:
            title = str(item.get("title") or item["id"]).replace("|", "/")
            parts.append(f"| {item['id']} | {title} |")
        parts.append("")
    return "\n".join(parts) + "\n"


def attach_register(catalog: dict[str, Any], tmp: Path) -> Path:
    path = tmp / "REGISTER.md"
    text = synthesize_register(list(catalog.get("items") or []))
    path.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    provenance = catalog.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
        catalog["provenance"] = provenance
    provenance["register"] = "command-center/sources/REGISTER.md"
    provenance["register_sha256"] = digest
    return path


ApplyFn = Callable[[dict[str, Any], Path], dict[str, Any]]


def _noop_apply(_catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    return {}


def _dangling(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "R-M01")["dependencies"] = ["R-DOES-NOT-EXIST"]
    return {}


def _closed_on_open(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    target = find(catalog, "R-M01")
    target["status"] = "OPEN"
    target["disposition"] = None
    find(catalog, "T-01")["dependencies"] = ["R-M01"]
    return {}


def _cycle(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "R-M01")["dependencies"] = ["R-M04"]
    return {}


def _dead_end(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "R-M08")["next_smallest_action"] = UNKNOWN
    return {}


def _gate_missing(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "R-B08")["owner_gate"] = ["OQ-999"]
    return {}


def _gate_answered(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    for question in catalog["owner_questions"]:
        if question["id"] == "OQ-6":
            question["state"] = "ANSWERED"
    find(catalog, "R-B08")["next_smallest_action"] = UNKNOWN
    return {}


def _no_evidence(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "T-05")["disposition_evidence"] = "   "
    return {}


def _non_terminal(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "T-05")["disposition"] = "PROBABLY-FINE"
    return {}


def _dropped_item(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    catalog["items"] = [item for item in catalog["items"] if item["id"] != "R-B06"]
    return {}


def _tampered_register(catalog: dict[str, Any], tmp: Path) -> dict[str, Any]:
    bogus = tmp / "REGISTER.md"
    bogus.write_text("# not the register\n", encoding="utf-8", newline="\n")
    return {"extra_args": ["--register", str(bogus)], "rebuild_graph": False}


def _missing_register(_catalog: dict[str, Any], tmp: Path) -> dict[str, Any]:
    return {
        "extra_args": ["--register", str(tmp / "nope.md")],
        "rebuild_graph": False,
    }


def _blank_digest(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    catalog["provenance"]["register_sha256"] = ""
    return {"rebuild_graph": False}


def _deleted_digest(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    del catalog["provenance"]["register_sha256"]
    return {"rebuild_graph": False}


def _stale_graph(catalog: dict[str, Any], tmp: Path) -> dict[str, Any]:
    stale = copy.deepcopy(cat.build_graph(catalog))
    stale["edge_count"] = 999
    path = tmp / "stale-graph.json"
    dump_json(path, stale)
    return {"graph_path": path, "rebuild_graph": False}


def _bad_ids(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    catalog["items"].append(copy.deepcopy(find(catalog, "R-M01")))
    catalog["items"].append({"id": "R-", "title": "garbage"})
    return {}


def _delete_defaults(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    del catalog["defaults"]
    return {"rebuild_graph": False}


def _delete_one_default(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    del catalog["defaults"]["timeout_seconds"]
    return {"rebuild_graph": False}


def _empty_catalog(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    catalog["items"] = []
    return {}


def _blank_item_sentinel(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    find(catalog, "R-M01")["completion_sentinel"] = ""
    return {"rebuild_graph": False}


def _defaults_empty_object(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    catalog["defaults"] = {}
    return {"rebuild_graph": False}


MUTATIONS: list[dict[str, Any]] = [
    {
        "id": "M01",
        "name": "dangling-dependency",
        "claimed_check": "REACH-1",
        "unprotected_if_survives": "A dependency id that names no item is accepted.",
        "apply": _dangling,
    },
    {
        "id": "M02",
        "name": "closed-depends-on-open",
        "claimed_check": "REACH-1",
        "unprotected_if_survives": "A closed item may depend on a still-open item.",
        "apply": _closed_on_open,
    },
    {
        "id": "M03",
        "name": "dependency-cycle",
        "claimed_check": "REACH-2",
        "unprotected_if_survives": "A two-node cycle is treated as a legal plan.",
        "apply": _cycle,
    },
    {
        "id": "M04",
        "name": "dead-end-open-item",
        "claimed_check": "REACH-3",
        "unprotected_if_survives": "An open item with no action, gate, or open dep is silent.",
        "apply": _dead_end,
    },
    {
        "id": "M05",
        "name": "owner-gate-missing-question",
        "claimed_check": "REACH-4",
        "unprotected_if_survives": "An owner_gate may name a question that does not exist.",
        "apply": _gate_missing,
    },
    {
        "id": "M06",
        "name": "answered-gate-plus-no-action",
        "claimed_check": "REACH-4",
        "unprotected_if_survives": "An already-answered gate still counts as a live blocker.",
        "apply": _gate_answered,
    },
    {
        "id": "M07",
        "name": "disposition-without-evidence",
        "claimed_check": "REACH-5",
        "unprotected_if_survives": "DONE with a blank evidence field is accepted.",
        "apply": _no_evidence,
    },
    {
        "id": "M08",
        "name": "non-terminal-disposition",
        "claimed_check": "REACH-5",
        "unprotected_if_survives": "A made-up disposition string is treated as terminal.",
        "apply": _non_terminal,
    },
    {
        "id": "M09",
        "name": "silently-dropped-item",
        "claimed_check": "REACH-6",
        "unprotected_if_survives": "Deleting a register row from the catalog is silent.",
        "apply": _dropped_item,
    },
    {
        "id": "M10",
        "name": "tampered-register-snapshot",
        "claimed_check": "REACH-6",
        "unprotected_if_survives": "A substituted REGISTER.md still satisfies the digest.",
        "apply": _tampered_register,
    },
    {
        "id": "M11",
        "name": "missing-register-snapshot",
        "claimed_check": "REACH-6",
        "unprotected_if_survives": "A missing snapshot path is treated as nothing-to-check.",
        "apply": _missing_register,
    },
    {
        "id": "M12",
        "name": "blank-register-digest",
        "claimed_check": "REACH-6",
        "unprotected_if_survives": "Empty provenance.register_sha256 skip-checks the digest.",
        "apply": _blank_digest,
    },
    {
        "id": "M13",
        "name": "deleted-register-digest",
        "claimed_check": "REACH-6",
        "unprotected_if_survives": "Deleting provenance.register_sha256 skip-checks the digest.",
        "apply": _deleted_digest,
    },
    {
        "id": "M14",
        "name": "stale-dependency-graph",
        "claimed_check": "V-GRAPH",
        "unprotected_if_survives": "A committed graph may drift from build_graph(catalog).",
        "apply": _stale_graph,
    },
    {
        "id": "M15",
        "name": "duplicate-and-malformed-ids",
        "claimed_check": "V-ID",
        "unprotected_if_survives": "Duplicate and malformed ids are admitted.",
        "apply": _bad_ids,
    },
    {
        "id": "M16",
        "name": "delete-entire-defaults-block",
        "claimed_check": "V-DEFAULTS",
        "alt_checks": ("V-FIELDS",),
        "unprotected_if_survives": (
            "HISTORICAL hole (pre-IMP-0436): deleting catalog.defaults left Prompt "
            "Two fields unresolved while V-FIELDS stayed silent under bare CI "
            "(require_complete defaulted False). On this tip V-DEFAULTS is always "
            "on, so the same edit must exit nonzero even when disarmed."
        ),
        "apply": _delete_defaults,
        "historical_survivor": True,
    },
]

# Known expansion / regression control — NOT the adversarial novel 17th.
# Adversarial review must plant a mutant whose id is absent from MUTATIONS and
# from this known-control id.
SEVENTEENTH = {
    "id": "M17",
    "name": "delete-single-default-field-timeout_seconds",
    "claimed_check": "V-DEFAULTS",
    "alt_checks": ("V-FIELDS",),
    "unprotected_if_survives": (
        "Surgical deletion of one defaults-only field (timeout_seconds) with no "
        "item override is a different edit than wiping the whole block; a battery "
        "that only plants the coarse mutation can still miss the hurried fix."
    ),
    "apply": _delete_one_default,
    "role": "known-expansion-control",
}

EXPANSIONS = [
    {
        "id": "M18",
        "name": "empty-item-list",
        "claimed_check": "V-EMPTY",
        "unprotected_if_survives": "An empty item list is reported as a clean catalog.",
        "apply": _empty_catalog,
    },
    {
        "id": "M19",
        "name": "blank-item-completion-sentinel",
        "claimed_check": "V-FIELDS",
        "unprotected_if_survives": "An item may blank a mandatory field while defaults remain.",
        "apply": _blank_item_sentinel,
    },
    {
        "id": "M20",
        "name": "defaults-replaced-with-empty-object",
        "claimed_check": "V-FIELDS",
        "unprotected_if_survives": "defaults:{} is treated differently from deleting the key.",
        "apply": _defaults_empty_object,
    },
]


def invoke(
    catalog_path: Path,
    graph_path: Path,
    extra_args: list[str] | None = None,
    *,
    disarm: bool = False,
    timeout: int = 60,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str(VALIDATE),
        "--catalog",
        str(catalog_path),
        "--graph",
        str(graph_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    if disarm:
        cmd.append("--no-require-complete")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(TOOLS) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": "TIMEOUT",
            "caught": True,
            "command": cmd,
        }
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "stdout": out[-4000:],
        "stderr": "",
        "caught": proc.returncode != 0,
        "command": [str(c) for c in cmd],
    }


def run_one(
    base: dict[str, Any],
    spec: dict[str, Any],
    *,
    disarm: bool = False,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"imp0438-{spec['id']}-") as raw:
        tmp = Path(raw)
        catalog = copy.deepcopy(base)
        fixture = attach_register(catalog, tmp)
        meta = spec["apply"](catalog, tmp) or {}
        cat_path = tmp / "catalog.json"
        dump_json(cat_path, catalog)
        if meta.get("rebuild_graph", True):
            graph_path = tmp / "graph.json"
            dump_json(graph_path, cat.build_graph(catalog))
        elif "graph_path" in meta:
            graph_path = Path(meta["graph_path"])
        else:
            graph_path = tmp / "graph.json"
            dump_json(graph_path, cat.build_graph(base))
        extra = list(meta.get("extra_args") or ["--register", str(fixture)])
        result = invoke(
            cat_path,
            graph_path,
            extra,
            disarm=disarm,
        )
        claimed = spec["claimed_check"]
        alt = tuple(spec.get("alt_checks") or ())
        text = result["stdout"]
        check_hit = claimed in text or any(a in text for a in alt)
        return {
            "id": spec["id"],
            "name": spec["name"],
            "claimed_check": claimed,
            "alt_checks": list(alt),
            "unprotected_if_survives": spec["unprotected_if_survives"],
            "exit_code": result["exit_code"],
            "caught": result["caught"],
            "claimed_check_in_output": check_hit,
            "success_marker": "SUCCESS:cc-validate" in text,
            "failed_marker": "FAILED:cc-validate" in text,
            "output_tail": text[-800:],
            "disarm": disarm,
            "historical_survivor": bool(spec.get("historical_survivor")),
        }


def run_control(base: dict[str, Any], *, disarm: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="imp0438-control-") as raw:
        tmp = Path(raw)
        catalog = copy.deepcopy(base)
        fixture = attach_register(catalog, tmp)
        cat_path = tmp / "catalog.json"
        graph_path = tmp / "graph.json"
        dump_json(cat_path, catalog)
        dump_json(graph_path, cat.build_graph(catalog))
        result = invoke(
            cat_path, graph_path, ["--register", str(fixture)], disarm=disarm
        )
        return {
            "id": "CONTROL",
            "name": "unmutated-slim-catalog",
            "exit_code": result["exit_code"],
            "caught": result["caught"],
            "success_marker": "SUCCESS:cc-validate" in result["stdout"],
            "output_tail": result["stdout"][-800:],
            "disarm": disarm,
        }


def run_battery(
    specs: list[dict[str, Any]] | None = None,
    *,
    disarm: bool = False,
    include_control: bool = True,
) -> dict[str, Any]:
    base = load_slim()
    rows = [run_one(base, spec, disarm=disarm) for spec in (specs or MUTATIONS)]
    caught = [row for row in rows if row["caught"]]
    survivors = [row for row in rows if not row["caught"]]
    out: dict[str, Any] = {
        "disarm": disarm,
        "mode": "disarmed-no-require-complete" if disarm else "bare-ci-invocation",
        "n": len(rows),
        "caught": len(caught),
        "survived": len(survivors),
        "rows": rows,
        "survivor_ids": [row["id"] for row in survivors],
    }
    if include_control:
        out["control"] = run_control(base, disarm=disarm)
    return out


def supports_disarm_flag() -> bool:
    """True once validate.py advertises --no-require-complete (post-fix)."""
    text = VALIDATE.read_text(encoding="utf-8")
    return "--no-require-complete" in text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMP-0438 validate.py mutation battery")
    parser.add_argument(
        "--mode",
        choices=("armed", "disarmed", "both", "seventeenth", "expansions"),
        default="armed",
    )
    args = parser.parse_args(argv)
    if args.mode == "armed":
        report = run_battery(MUTATIONS, disarm=False)
    elif args.mode == "disarmed":
        if not supports_disarm_flag():
            # Pre-fix tree: the default already is the disarmed surface.
            report = run_battery(MUTATIONS, disarm=False)
            report["mode"] = "pre-fix-default-is-disarmed"
        else:
            report = run_battery(MUTATIONS, disarm=True)
    elif args.mode == "seventeenth":
        report = run_battery([SEVENTEENTH], disarm=False)
    elif args.mode == "expansions":
        report = run_battery(EXPANSIONS, disarm=False)
    else:
        armed = run_battery(MUTATIONS, disarm=False)
        if supports_disarm_flag():
            disarmed = run_battery(MUTATIONS, disarm=True)
        else:
            disarmed = copy.deepcopy(armed)
            disarmed["mode"] = "pre-fix-default-is-disarmed"
        report = {"armed": armed, "disarmed": disarmed}
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if args.mode in {"armed", "disarmed", "seventeenth", "expansions"}:
        survivors = report.get("survivor_ids") or []
        control = report.get("control") or {}
        if args.mode == "armed":
            ok = report["caught"] == report["n"] and control.get("exit_code") == 0
        elif args.mode == "disarmed":
            ok = True
        else:
            ok = report["caught"] == report["n"]
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
