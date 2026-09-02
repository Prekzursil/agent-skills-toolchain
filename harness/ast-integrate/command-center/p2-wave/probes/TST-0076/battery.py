#!/usr/bin/env python3
"""Mutation battery for tools/command-center/validate.py under the CI argv.

CI (AUD-0041 quality.yml gate-tests-coverage command-center) invokes
`python tools/command-center/validate.py` with no flags. --require-complete is
the arming flag for V-FIELDS. Mutations run against isolated catalog+graph
copies so a missing live DEPENDENCY-GRAPH.json cannot mask a disarmed rule.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VALIDATE = REPO / "tools" / "command-center" / "validate.py"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
QUALITY_YML = REPO / ".github" / "workflows" / "quality.yml"
GRAPH_LIVE = REPO / "command-center" / "DEPENDENCY-GRAPH.json"
REGISTER_LIVE = REPO / "command-center" / "sources" / "REGISTER.md"
AUD_INV = (
    REPO / "command-center" / "p2-wave" / "probes" / "AUD-0041" / "probe1-yaml-inventory.json"
)
CHECK_RE = re.compile(r'Violation\(\s*"([A-Z][A-Z0-9-]*)"')
OUT_CHECK_RE = re.compile(r"^\s+(REACH-\d+|V-[A-Z0-9-]+)\b", re.M)
ARMING_FLAG = "--require-complete"
CI_ARGV = ["python", "tools/command-center/validate.py"]

sys.path.insert(0, str(REPO / "tools" / "command-center"))
import catalog as cat  # noqa: E402


def claimed_checks(source: Path | None = None) -> list[str]:
    text = (source or VALIDATE).read_text(encoding="utf-8")
    seen: list[str] = []
    for name in CHECK_RE.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def reconstruct_ci_argv() -> dict[str, Any]:
    found = None
    if QUALITY_YML.is_file():
        for raw in QUALITY_YML.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#"):
                continue
            if "tools/command-center/validate.py" in line:
                found = {
                    "workflow": ".github/workflows/quality.yml",
                    "job_id": "test-python",
                    "step_name": "gate-tests-coverage command-center",
                    "command": line,
                }
                break
    if found is None and AUD_INV.is_file():
        inv = json.loads(AUD_INV.read_text(encoding="utf-8"))
        for wf in inv.get("workflows") or []:
            if str(wf.get("file") or "").replace("\\", "/").endswith(
                ".github/workflows/quality.yml"
            ):
                for job in wf.get("jobs") or []:
                    for step in job.get("steps") or []:
                        cmd = str(step.get("command") or "")
                        if "tools/command-center/validate.py" in cmd:
                            found = {
                                "workflow": wf.get("file"),
                                "job_id": job.get("job_id"),
                                "step_name": step.get("name"),
                                "command": cmd,
                            }
                            break
                    if found:
                        break
            if found:
                break
    cmd = str((found or {}).get("command") or " ".join(CI_ARGV))
    return {
        "workflow_path": ".github/workflows/quality.yml",
        "workflow_present": QUALITY_YML.is_file(),
        "inventory": str(AUD_INV.relative_to(REPO).as_posix()) if AUD_INV.is_file() else None,
        "inventory_hit": found,
        "argv": list(CI_ARGV),
        "require_complete_passed": ARMING_FLAG in cmd,
        "arming_flag": ARMING_FLAG,
        "note": (
            "CI invokes `python tools/command-center/validate.py` with no "
            f"{ARMING_FLAG}; V-FIELDS is gated on that flag defaulting False."
        ),
    }


def artifact_kind(doc: dict[str, Any]) -> str:
    if isinstance(doc.get("kind"), str) and doc["kind"]:
        return str(doc["kind"])
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return str(report.get("kind") or "")


def artifact_mutation_table(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for blob in (
        doc.get("mutation_table"),
        (doc.get("report") or {}).get("mutation_table")
        if isinstance(doc.get("report"), dict)
        else None,
        (doc.get("extensions") or {}).get("mutation_table")
        if isinstance(doc.get("extensions"), dict)
        else None,
    ):
        if isinstance(blob, list) and blob:
            return [r for r in blob if isinstance(r, dict)]
    return []


def slim_catalog(live: dict[str, Any]) -> dict[str, Any]:
    skip = {"work_units", "work_units_meta"}
    return {k: copy.deepcopy(v) for k, v in live.items() if k not in skip}


def _find(catalog: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in catalog.get("items") or []:
        if item.get("id") == item_id:
            return item
    raise KeyError(item_id)


def register_markdown(items: list[dict[str, Any]]) -> str:
    section_h = {
        "OUTSTANDING": "## 1. OUTSTANDING",
        "DELIBERATELY-SKIPPED": "## 2. DELIBERATELY-SKIPPED",
        "SUPERSEDED": "## 3. SUPERSEDED",
        "SETTLED": "## 4. SETTLED",
    }
    prog_h = {
        "A-toolchain": "### 1A. Program A",
        "HARNESS": "### 1B. Harness",
        "MONITOR": "### 1C. Monitor",
        "B-workflow_design": "### 1D. Program B",
    }
    by_section: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_section.setdefault(str(item.get("section") or "OUTSTANDING"), []).append(item)
    lines = ["# REGISTER", ""]
    for section, heading in section_h.items():
        lines += [heading, ""]
        rows = by_section.get(section, [])
        if section == "OUTSTANDING":
            by_prog: dict[str, list[dict[str, Any]]] = {}
            for item in rows:
                by_prog.setdefault(str(item.get("program") or "A-toolchain"), []).append(
                    item
                )
            for prog, ph in prog_h.items():
                lines += [ph, "", "| id | title |", "| --- | --- |"]
                for item in by_prog.get(prog, []):
                    title = (
                        str(item.get("title") or "x")
                        .replace("|", "/")
                        .replace("\n", " ")[:40]
                    )
                    lines.append(f"| {item['id']} | {title} |")
                leftover = [p for p in by_prog if p not in prog_h]
                if leftover and prog == "A-toolchain":
                    for p in leftover:
                        for item in by_prog[p]:
                            title = (
                                str(item.get("title") or "x")
                                .replace("|", "/")
                                .replace("\n", " ")[:40]
                            )
                            lines.append(f"| {item['id']} | {title} |")
                lines.append("")
        else:
            lines += ["| id | title |", "| --- | --- |"]
            for item in rows:
                title = (
                    str(item.get("title") or "x").replace("|", "/").replace("\n", " ")[:40]
                )
                lines.append(f"| {item['id']} | {title} |")
            lines.append("")
    return "\n".join(lines) + "\n"


def _invoke(catalog_path: Path, graph_path: Path, *, armed: bool) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(VALIDATE),
        "--catalog",
        str(catalog_path),
        "--graph",
        str(graph_path),
    ]
    if armed:
        cmd.append(ARMING_FLAG)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    checks = list(dict.fromkeys(OUT_CHECK_RE.findall(out)))
    return {
        "exit_code": proc.returncode,
        "checks": checks,
        "success_marker": "SUCCESS:cc-validate" in out,
        "failed_marker": "FAILED:cc-validate" in out,
        "tail": "\n".join(out.splitlines()[-8:]),
        "armed": armed,
        "argv_flags": [ARMING_FLAG] if armed else [],
    }


def _write_tree(
    tmp: Path, catalog: dict[str, Any], graph: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    cat_path = tmp / "WORK-UNIT-CATALOG.json"
    graph_path = tmp / "DEPENDENCY-GRAPH.json"
    cat_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if graph is None:
        graph = cat.build_graph(catalog)
    graph_path.write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return cat_path, graph_path


def _prepare_base(tmp: Path, live: dict[str, Any]) -> dict[str, Any]:
    catalog = slim_catalog(live)
    items = list(catalog.get("items") or [])
    if len(items) != 103:
        raise RuntimeError(f"expected 103 backlog items, got {len(items)}")
    reg_path = tmp / "REGISTER.md"
    text = register_markdown(items)
    reg_path.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    catalog["provenance"] = {
        "register": str(reg_path),
        "register_sha256": digest,
        "seeded_by": "TST-0076-isolated-fixture",
    }
    return catalog


Mutator = Callable[[dict[str, Any], Path], dict[str, Any] | None]


def _mut_empty(catalog: dict[str, Any], _tmp: Path) -> None:
    catalog["items"] = []


def _mut_id(catalog: dict[str, Any], _tmp: Path) -> None:
    catalog["items"].append(copy.deepcopy(_find(catalog, "R-M01")))
    catalog["items"].append({"id": "R-", "title": "garbage"})


def _mut_reach1(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "R-M01")["dependencies"] = ["R-DOES-NOT-EXIST"]


def _mut_reach2(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "R-M01")["dependencies"] = ["R-M04"]


def _mut_reach3(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "R-M08")["next_smallest_action"] = cat.UNKNOWN


def _mut_reach4(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "R-B08")["owner_gate"] = ["OQ-999"]


def _mut_reach5(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "T-05")["disposition_evidence"] = "   "


def _mut_reach6_drop(catalog: dict[str, Any], _tmp: Path) -> None:
    catalog["items"] = [i for i in catalog["items"] if i.get("id") != "R-B06"]


def _mut_reach6_blank(catalog: dict[str, Any], _tmp: Path) -> None:
    catalog.setdefault("provenance", {})["register_sha256"] = ""


def _mut_vgraph(catalog: dict[str, Any], _tmp: Path) -> dict[str, Any]:
    graph = cat.build_graph(catalog)
    graph["edge_count"] = 999
    return graph


def _mut_vfields_defaults(catalog: dict[str, Any], _tmp: Path) -> None:
    catalog.pop("defaults", None)


def _mut_vfields_blank(catalog: dict[str, Any], _tmp: Path) -> None:
    _find(catalog, "R-M01")["completion_sentinel"] = ""


MUTATIONS: list[dict[str, Any]] = [
    {
        "id": "V-EMPTY-zero-items",
        "check": "V-EMPTY",
        "mutation": "items=[]",
        "apply": _mut_empty,
    },
    {
        "id": "V-ID-duplicate-and-malformed",
        "check": "V-ID",
        "mutation": "duplicate R-M01 plus id='R-'",
        "apply": _mut_id,
    },
    {
        "id": "REACH-1-dangling-dependency",
        "check": "REACH-1",
        "mutation": "R-M01.dependencies=['R-DOES-NOT-EXIST']",
        "apply": _mut_reach1,
    },
    {
        "id": "REACH-2-cycle",
        "check": "REACH-2",
        "mutation": "R-M01.dependencies=['R-M04'] (R-M04 already depends on R-M01)",
        "apply": _mut_reach2,
    },
    {
        "id": "REACH-3-dead-end",
        "check": "REACH-3",
        "mutation": "R-M08.next_smallest_action=UNKNOWN",
        "apply": _mut_reach3,
    },
    {
        "id": "REACH-4-unknown-owner-gate",
        "check": "REACH-4",
        "mutation": "R-B08.owner_gate=['OQ-999']",
        "apply": _mut_reach4,
    },
    {
        "id": "REACH-5-disposition-without-evidence",
        "check": "REACH-5",
        "mutation": "T-05.disposition_evidence blank",
        "apply": _mut_reach5,
    },
    {
        "id": "REACH-6-dropped-register-row",
        "check": "REACH-6",
        "mutation": "delete R-B06 from catalog, keep register snapshot",
        "apply": _mut_reach6_drop,
    },
    {
        "id": "REACH-6-blank-digest",
        "check": "REACH-6",
        "mutation": "provenance.register_sha256=''",
        "apply": _mut_reach6_blank,
    },
    {
        "id": "V-GRAPH-stale-edge-count",
        "check": "V-GRAPH",
        "mutation": "DEPENDENCY-GRAPH.json edge_count=999",
        "apply": _mut_vgraph,
    },
    {
        "id": "V-FIELDS-defaults-block-deleted",
        "check": "V-FIELDS",
        "mutation": "delete entire catalog['defaults'] block",
        "apply": _mut_vfields_defaults,
    },
    {
        "id": "V-FIELDS-blank-item-field",
        "check": "V-FIELDS",
        "mutation": "R-M01.completion_sentinel=''",
        "apply": _mut_vfields_blank,
    },
]


def _classify(check: str, ci: dict[str, Any], armed: dict[str, Any]) -> dict[str, Any]:
    ci_has = check in ci["checks"]
    armed_has = check in armed["checks"]
    if ci_has:
        status = "FIRED"
        flag = None
    elif armed_has and ci["exit_code"] == 0:
        status = "DISARMED"
        flag = ARMING_FLAG
    elif (not ci_has) and (not armed_has):
        status = "SILENT-IN-BOTH"
        flag = ARMING_FLAG if check == "V-FIELDS" else None
    else:
        status = "CONTAMINATED"
        flag = None
    return {
        "status": status,
        "arming_flag": flag,
        "ci_fired": ci_has,
        "armed_fired": armed_has,
        "fired_on_bad_state": ci_has or armed_has,
        "silent_on_good_state": True,
        "ci_exit": ci["exit_code"],
        "armed_exit": armed["exit_code"],
        "ci_checks": ci["checks"],
        "armed_checks": armed["checks"],
        "ci_success_marker": ci["success_marker"],
        "armed_failed_marker": armed["failed_marker"],
        "ci_tail": ci["tail"],
        "armed_tail": armed["tail"],
    }


def live_bare_ci() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "graph_present": GRAPH_LIVE.is_file(),
        "register_present": REGISTER_LIVE.is_file(),
        "quality_yml_present": QUALITY_YML.is_file(),
        "tail": "\n".join(out.splitlines()[-6:]),
    }


def run_report() -> dict[str, Any]:
    live = cat.load()
    checks = claimed_checks()
    ci_meta = reconstruct_ci_argv()
    bare = live_bare_ci()
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tst0076-") as raw:
        tmp = Path(raw)
        base = _prepare_base(tmp, live)
        cat_path, graph_path = _write_tree(tmp, base)
        baseline = _invoke(cat_path, graph_path, armed=False)
        baseline_armed = _invoke(cat_path, graph_path, armed=True)
        if baseline["exit_code"] != 0 or baseline_armed["exit_code"] != 0:
            raise RuntimeError(
                "isolated baseline is not clean: "
                f"ci={baseline['exit_code']} armed={baseline_armed['exit_code']} "
                f"ci_tail={baseline['tail']!r}"
            )
        for spec in MUTATIONS:
            mutated = copy.deepcopy(base)
            extra = spec["apply"](mutated, tmp)
            graph = extra if isinstance(extra, dict) else None
            c_path, g_path = _write_tree(tmp, mutated, graph)
            ci = _invoke(c_path, g_path, armed=False)
            armed = _invoke(c_path, g_path, armed=True)
            classified = _classify(spec["check"], ci, armed)
            rows.append(
                {
                    "id": spec["id"],
                    "check": spec["check"],
                    "mutation": spec["mutation"],
                    "ci_argv_arming": [],
                    "armed_argv_arming": [ARMING_FLAG],
                    **classified,
                }
            )
    by_check: dict[str, list[str]] = {}
    for row in rows:
        by_check.setdefault(row["check"], []).append(row["status"])
    missing = [c for c in checks if c not in by_check]
    return {
        "claimed_checks": checks,
        "ci_invocation": ci_meta,
        "live_bare": bare,
        "baseline": {
            "ci_exit": baseline["exit_code"],
            "armed_exit": baseline_armed["exit_code"],
            "silent_on_good_state": baseline["exit_code"] == 0,
        },
        "rows": rows,
        "missing_claimed_checks": missing,
        "defaults_deleted": next(
            r for r in rows if r["id"] == "V-FIELDS-defaults-block-deleted"
        ),
    }


def table_is_sound(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("missing_claimed_checks"):
        errors.append(f"no mutation for {report['missing_claimed_checks']}")
    if not report.get("baseline", {}).get("silent_on_good_state"):
        errors.append("baseline not silent under CI-equivalent argv")
    allowed = {"FIRED", "DISARMED"}
    for row in report.get("rows") or []:
        if row.get("status") not in allowed:
            errors.append(f"{row.get('id')} status={row.get('status')}")
        if row.get("status") == "DISARMED" and row.get("arming_flag") != ARMING_FLAG:
            errors.append(f"{row.get('id')} DISARMED without {ARMING_FLAG}")
        if row.get("status") == "FIRED" and not row.get("ci_fired"):
            errors.append(f"{row.get('id')} FIRED but check absent from CI output")
        if row.get("check") != "V-FIELDS" and row.get("status") != "FIRED":
            errors.append(f"{row.get('id')} expected FIRED under CI, got {row.get('status')}")
        if row.get("check") == "V-FIELDS" and row.get("status") not in allowed:
            errors.append(f"{row.get('id')} V-FIELDS not measured")
    dd = report.get("defaults_deleted") or {}
    if dd.get("status") == "DISARMED":
        if dd.get("ci_exit") != 0:
            errors.append("defaults-deleted DISARMED but CI exit != 0")
        if dd.get("armed_exit") == 0 or not dd.get("armed_fired"):
            errors.append("defaults-deleted not caught with --require-complete")
    elif dd.get("status") == "FIRED":
        if dd.get("ci_exit") == 0:
            errors.append("defaults-deleted FIRED but CI exit 0")
    else:
        errors.append(f"defaults-deleted status={dd.get('status')}")
    return errors


if __name__ == "__main__":
    doc = run_report()
    errs = table_is_sound(doc)
    print(json.dumps({"errors": errs, "n_rows": len(doc["rows"])}, indent=2))
    for row in doc["rows"]:
        print(
            f"{row['id']:34} {row['status']:12} ci={row['ci_exit']} "
            f"armed={row['armed_exit']} checks_ci={row['ci_checks']}"
        )
    raise SystemExit(1 if errs else 0)
