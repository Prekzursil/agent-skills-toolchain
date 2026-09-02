#!/usr/bin/env python3
"""Fail-open gate census for AUD-0045.

Probe 1: AST/command read of early-return and default-off paths.
Probe 2: execute each gate against empty/absent input and a known-bad input.

A gate that exits 0 on empty input and prints no measured count is fail-open.
A gate that exits 0 on both empty and known-bad is measuring nothing.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
CI_INV = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"

COUNT_RE = re.compile(
    r"(?i)\b(?:count|items|violations|silent|admitted|rejections|"
    r"checked|measured|found|nodes|edges)=?\s*(\d+)"
)
GATE_NAME_RE = re.compile(
    r"(?i)(gate-|validate|lint|coverage|charter|unitgate|require_|check)"
)

STATIC_TARGETS = [
    "tools/command-center/validate.py",
    "command-center/freeze/gate.py",
    "command-center/freeze/lib.py",
    "tools/command-center/unit_manifest.py",
    "command-center/ready_units.py",
    "tools/command-center/render.py",
    ".agents/skills/claim-verify-gate/scripts/claim_gate.py",
    "command-center/p2-wave/_measure_one_delivered.py",
]


def run_cmd(
    argv: list[str],
    *,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    timeout: int = 45,
) -> dict[str, Any]:
    merged = os.environ.copy()
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        merged.update(extra_env)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {"argv": list(argv), "exit_code": proc.returncode, "output": out[-4000:]}
    except subprocess.TimeoutExpired:
        return {"argv": list(argv), "exit_code": 124, "output": "TIMEOUT"}
    except OSError as exc:
        return {
            "argv": list(argv),
            "exit_code": 127,
            "output": f"{type(exc).__name__}:{exc}",
        }


def py_cmd(rel: str) -> list[str]:
    return [sys.executable, "-B", str(REPO / rel)]


def printed_count(text: str) -> int | None:
    nums = [int(m) for m in COUNT_RE.findall(text or "")]
    if not nums:
        return None
    return max(nums)


def no_measured_count(text: str) -> bool:
    n = printed_count(text)
    return n is None or n == 0


def classify(empty: dict[str, Any], bad: dict[str, Any]) -> str:
    e, b = int(empty["exit_code"]), int(bad["exit_code"])
    if e == 0 and b == 0:
        return "measures-nothing"
    if e == 0 and no_measured_count(empty.get("output") or ""):
        return "fail-open-empty"
    if e == 0:
        return "empty-exits-0-with-count"
    if b == 0:
        return "known-bad-exits-0"
    return "fail-closed"


def static_scan_file(rel: str) -> dict[str, Any]:
    path = REPO / rel
    row: dict[str, Any] = {
        "path": rel,
        "exists": path.is_file(),
        "early_return_zero": [],
        "swallowed_exception": [],
        "default_off_flags": [],
    }
    if not path.is_file() or path.suffix != ".py":
        return row
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        row["parse_error"] = f"{type(exc).__name__}:{exc}"
        return row

    class Walk(ast.NodeVisitor):
        def visit_Return(self, node: ast.Return) -> None:
            val = node.value
            if isinstance(val, ast.Constant) and val.value == 0:
                row["early_return_zero"].append(getattr(node, "lineno", 0))
            self.generic_visit(node)

        def visit_Raise(self, node: ast.Raise) -> None:
            exc = node.exc
            if (
                isinstance(exc, ast.Call)
                and isinstance(exc.func, ast.Name)
                and exc.func.id == "SystemExit"
                and exc.args
                and isinstance(exc.args[0], ast.Constant)
                and exc.args[0].value == 0
            ):
                row["early_return_zero"].append(getattr(node, "lineno", 0))
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            body = node.body
            if body and all(isinstance(s, ast.Pass) for s in body):
                row["swallowed_exception"].append(getattr(node, "lineno", 0))
            if body and len(body) == 1 and isinstance(body[0], ast.Return):
                val = body[0].value
                if isinstance(val, ast.Constant) and val.value in (0, None):
                    row["swallowed_exception"].append(getattr(node, "lineno", 0))
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            names = [a.arg for a in node.args.args]
            defaults = node.args.defaults
            if defaults:
                bound = names[-len(defaults) :]
                for name, default in zip(bound, defaults):
                    if re.search(r"(require|strict|complete|check|armed)", name, re.I):
                        if isinstance(default, ast.Constant) and default.value is False:
                            row["default_off_flags"].append(
                                {
                                    "function": node.name,
                                    "arg": name,
                                    "lineno": getattr(node, "lineno", 0),
                                }
                            )
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

    Walk().visit(tree)
    return row


def ci_static_fail_open() -> dict[str, Any]:
    if not CI_INV.is_file():
        return {
            "status": "NOT-CHECKED",
            "reason": "AUD-0041 yaml inventory absent",
            "fail_open_steps": [],
            "fail_open_step_count": 0,
        }
    doc = json.loads(CI_INV.read_text(encoding="utf-8"))
    hits: list[dict[str, Any]] = []
    for wf in doc.get("workflows") or []:
        if not isinstance(wf, dict):
            continue
        wf_file = wf.get("file") or wf.get("path") or ""
        for job in wf.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            job_id = job.get("job_id") or job.get("id") or ""
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                cmd = str(step.get("command") or "")
                name = str(step.get("name") or "")
                coe = step.get("continue_on_error")
                gateish = bool(GATE_NAME_RE.search(name) or GATE_NAME_RE.search(cmd))
                reasons: list[str] = []
                if coe is True and gateish:
                    reasons.append("continue_on_error=true")
                if coe is True and re.search(r"(?i)probe|gate|regress", name):
                    reasons.append("continue_on_error=true-on-named-probe")
                if gateish and re.search(r"\|\|\s*true\b", cmd):
                    reasons.append("pipe-true-swallows-failure")
                if re.search(r"if\s+\[\s*!\s+-s\b", cmd) and "exit 0" in cmd:
                    reasons.append("empty-file-exits-0")
                if "exit 0" in cmd and re.search(
                    r"no patch|nothing to|no_changes|skipping", cmd, re.I
                ):
                    reasons.append("empty-result-exits-0")
                if reasons:
                    hits.append(
                        {
                            "workflow": wf_file,
                            "job": job_id,
                            "step": name or f"index-{step.get('index')}",
                            "reasons": reasons,
                            "continue_on_error": coe,
                            "command_head": cmd[:240],
                        }
                    )
    return {
        "status": "STATIC-FROM-AUD-0041",
        "workflow_files_on_this_tree": (REPO / ".github/workflows").is_dir(),
        "fail_open_step_count": len(hits),
        "fail_open_steps": hits,
        "note": (
            ".github/workflows is absent on this worktree; CI execution is "
            "NOT-CHECKED. Fail-open labels are from AUD-0041's YAML parse."
        ),
    }


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_fixtures(tmp: Path) -> dict[str, Path]:
    sys.path.insert(0, str(REPO / "tools/command-center"))
    import catalog as cat  # noqa: WPS433

    register = tmp / "REGISTER.md"
    register.write_text("# AUD-0045 fixture\n## 1. OUTSTANDING\n\n", encoding="utf-8")
    digest = hashlib.sha256(register.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    item = {
        "id": "R-M01",
        "title": "fixture item",
        "program": "P1",
        "status": "OPEN",
        "section": "s",
        "dependencies": [],
        "next_smallest_action": "measure fail-open",
    }
    empty_cat = {
        "items": [],
        "provenance": {"register": str(register), "register_sha256": digest},
    }
    m16_cat = {
        "items": [item],
        "provenance": {"register": str(register), "register_sha256": digest},
    }
    empty_path = tmp / "empty-catalog.json"
    m16_path = tmp / "m16-catalog.json"
    empty_graph = tmp / "empty-graph.json"
    m16_graph = tmp / "m16-graph.json"
    _write_json(empty_path, empty_cat)
    _write_json(m16_path, m16_cat)
    _write_json(empty_graph, cat.build_graph(empty_cat))
    _write_json(m16_graph, cat.build_graph(m16_cat))
    return {
        "register": register,
        "empty_catalog": empty_path,
        "empty_graph": empty_graph,
        "m16_catalog": m16_path,
        "m16_graph": m16_graph,
        "missing_catalog": tmp / "does-not-exist.json",
    }


def _freeze_repo(tmp: Path, *, active: bool, paths: list[dict[str, Any]]) -> Path:
    repo = tmp / "repo"
    _write_json(
        repo / "command-center/freeze/FREEZE.json",
        {
            "freeze_id": "AUD-0045-fixture",
            "freeze_active": active,
            "frozen_paths": paths,
        },
    )
    return repo


def execute_gates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aud0045-") as raw:
        tmp = Path(raw)
        fx = _validate_fixtures(tmp)
        validate = "tools/command-center/validate.py"

        v_empty = run_cmd(
            py_cmd(validate)
            + [
                "--catalog",
                str(fx["empty_catalog"]),
                "--graph",
                str(fx["empty_graph"]),
                "--register",
                str(fx["register"]),
            ]
        )
        v_missing = run_cmd(
            py_cmd(validate)
            + [
                "--catalog",
                str(fx["missing_catalog"]),
                "--graph",
                str(fx["empty_graph"]),
                "--register",
                str(fx["register"]),
            ]
        )
        rows.append(
            {
                "id": "cc-validate-empty-catalog",
                "gate": validate,
                "named_case": None,
                "empty": v_empty,
                "known_bad": v_missing,
                "class": classify(v_empty, v_missing),
            }
        )

        v_m16_off = run_cmd(
            py_cmd(validate)
            + [
                "--catalog",
                str(fx["m16_catalog"]),
                "--graph",
                str(fx["m16_graph"]),
                "--register",
                str(fx["register"]),
                "--no-require-complete",
            ]
        )
        v_m16_on = run_cmd(
            py_cmd(validate)
            + [
                "--catalog",
                str(fx["m16_catalog"]),
                "--graph",
                str(fx["m16_graph"]),
                "--register",
                str(fx["register"]),
            ]
        )
        rows.append(
            {
                "id": "cc-validate-m16-disarmed-surface",
                "gate": validate + " --no-require-complete",
                "named_case": "validate.py require_complete defaulting to False",
                "empty": v_m16_off,
                "known_bad": v_m16_on,
                "class": classify(v_m16_off, v_m16_on),
                "note": (
                    "Historical CI invoked validate.py bare while "
                    "require_complete defaulted to False. Live default is True; "
                    "--no-require-complete is the surviving disarmed surface. "
                    "empty=disarmed unresolved fields, known_bad=armed same catalog."
                ),
            }
        )

        schema_src = REPO / "command-center/schema/artifact.schema.json"
        schema_bytes = schema_src.read_bytes() if schema_src.is_file() else b"{}\n"
        bad_hash = "ab" * 32
        rel = "command-center/schema/artifact.schema.json"
        freeze = "command-center/freeze/gate.py"

        off_repo = _freeze_repo(
            tmp / "nf",
            active=False,
            paths=[
                {
                    "path": rel,
                    "kind": "schema",
                    "sha256": bad_hash,
                    "schema_version": 1,
                }
            ],
        )
        (off_repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (off_repo / rel).write_bytes(schema_bytes)
        f_off = run_cmd(py_cmd(freeze) + ["--repo", str(off_repo)])
        rows.append(
            {
                "id": "freeze-gate-not-frozen",
                "gate": freeze,
                "named_case": None,
                "empty": f_off,
                "known_bad": f_off,
                "class": classify(f_off, f_off),
                "note": (
                    "freeze_active=false short-circuits to ok=True. A planted "
                    "sha mismatch is not examined."
                ),
            }
        )

        none_repo = _freeze_repo(tmp / "none", active=True, paths=[])
        f_none = run_cmd(py_cmd(freeze) + ["--repo", str(none_repo)])
        armed_repo = _freeze_repo(
            tmp / "armed",
            active=True,
            paths=[
                {
                    "path": rel,
                    "kind": "schema",
                    "sha256": bad_hash,
                    "schema_version": 1,
                }
            ],
        )
        (armed_repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (armed_repo / rel).write_bytes(schema_bytes)
        f_armed = run_cmd(py_cmd(freeze) + ["--repo", str(armed_repo)])
        rows.append(
            {
                "id": "freeze-gate-clean-plus-checks-none",
                "gate": freeze,
                "named_case": "CLEAN plus checks:NONE gate",
                "empty": f_none,
                "known_bad": f_armed,
                "class": classify(f_none, f_armed),
                "note": (
                    "freeze_active=true with frozen_paths=[] exits 0 with "
                    "reason=clean and silent=0. A sha-mismatched frozen path "
                    "is the known-bad control."
                ),
            }
        )

        empty_root = tmp / "manifest-empty"
        (empty_root / "command-center").mkdir(parents=True)
        manifest = "tools/command-center/unit_manifest.py"
        m_empty = run_cmd(py_cmd(manifest) + ["--check", "--root", str(empty_root)])
        missing_root = tmp / "manifest-missing"
        rec_dir = missing_root / "command-center/receipts"
        rec_dir.mkdir(parents=True)
        (rec_dir / "TST-MISS.json").write_text(
            json.dumps({"unit_id": "TST-MISS", "artifacts": [{"path": "nope.bin"}]})
            + "\n",
            encoding="utf-8",
        )
        m_bad = run_cmd(py_cmd(manifest) + ["--check", "--root", str(missing_root)])
        rows.append(
            {
                "id": "unit-manifest-empty-walk",
                "gate": manifest + " --check",
                "named_case": None,
                "empty": m_empty,
                "known_bad": m_bad,
                "class": classify(m_empty, m_bad),
            }
        )

        cg = ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
        c_empty = run_cmd(py_cmd(cg))
        bad_claim = tmp / "bad-claim.json"
        _write_json(
            bad_claim,
            {"claims": [{"id": "c1", "text": "x", "verdict": "CONFIRMED"}]},
        )
        c_bad = run_cmd(py_cmd(cg) + [str(bad_claim)])
        rows.append(
            {
                "id": "claim-gate-empty-and-no-source-probe",
                "gate": cg,
                "named_case": None,
                "empty": c_empty,
                "known_bad": c_bad,
                "class": classify(c_empty, c_bad),
            }
        )

        meas = "command-center/p2-wave/_measure_one_delivered.py"
        meas_empty = run_cmd(py_cmd(meas))
        meas_bad = run_cmd(py_cmd(meas) + ["ZZZ-9999"])
        rows.append(
            {
                "id": "measure-one-delivered-empty-argv",
                "gate": meas,
                "named_case": None,
                "empty": meas_empty,
                "known_bad": meas_bad,
                "class": classify(meas_empty, meas_bad),
            }
        )

        silent = FIXTURES / "silent_always.py"
        s_empty = run_cmd([sys.executable, "-B", str(silent), "empty"])
        s_bad = run_cmd([sys.executable, "-B", str(silent), "known-bad"])
        rows.append(
            {
                "id": "control-silent-always",
                "gate": str(silent.relative_to(REPO)),
                "named_case": None,
                "role": "negative-control-must-be-classified-measures-nothing",
                "empty": s_empty,
                "known_bad": s_bad,
                "class": classify(s_empty, s_bad),
            }
        )

        closed = FIXTURES / "closed_always.py"
        cl_empty = run_cmd([sys.executable, "-B", str(closed), "empty"])
        cl_bad = run_cmd([sys.executable, "-B", str(closed), "known-bad"])
        rows.append(
            {
                "id": "control-closed-always",
                "gate": str(closed.relative_to(REPO)),
                "named_case": None,
                "role": "positive-control-must-be-classified-fail-closed",
                "empty": cl_empty,
                "known_bad": cl_bad,
                "class": classify(cl_empty, cl_bad),
            }
        )

        none = FIXTURES / "clean_none_checks.py"
        n_empty = run_cmd(
            [sys.executable, "-B", str(none)], extra_env={"CHECKS": "NONE"}
        )
        n_bad = run_cmd(
            [sys.executable, "-B", str(none)], extra_env={"CHECKS": "fail"}
        )
        rows.append(
            {
                "id": "control-clean-none-checks",
                "gate": str(none.relative_to(REPO)),
                "named_case": "CLEAN plus checks:NONE gate",
                "role": "named-case-model",
                "empty": n_empty,
                "known_bad": n_bad,
                "class": classify(n_empty, n_bad),
            }
        )
    return rows


def static_scan() -> list[dict[str, Any]]:
    return [static_scan_file(rel) for rel in STATIC_TARGETS]


def compact_exec_row(row: dict[str, Any]) -> dict[str, Any]:
    def side(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "exit_code": s.get("exit_code"),
            "printed_count": printed_count(s.get("output") or ""),
            "no_measured_count": no_measured_count(s.get("output") or ""),
            "output_tail": (s.get("output") or "")[-400:],
        }

    out = {
        "id": row["id"],
        "gate": row["gate"],
        "named_case": row.get("named_case"),
        "class": row["class"],
        "empty": side(row["empty"]),
        "known_bad": side(row["known_bad"]),
    }
    if row.get("note"):
        out["note"] = row["note"]
    if row.get("role"):
        out["role"] = row["role"]
    return out


def snapshot() -> dict[str, Any]:
    static = static_scan()
    executed = [compact_exec_row(r) for r in execute_gates()]
    ci = ci_static_fail_open()
    class_counts: dict[str, int] = {}
    for row in executed:
        class_counts[row["class"]] = class_counts.get(row["class"], 0) + 1
    fail_open_ids = [
        r["id"]
        for r in executed
        if r["class"] in {"fail-open-empty", "measures-nothing"}
    ]
    measures_nothing_ids = [r["id"] for r in executed if r["class"] == "measures-nothing"]
    named = [r for r in executed if r.get("named_case")]
    default_off = []
    for s in static:
        for flag in s.get("default_off_flags") or []:
            default_off.append({"path": s["path"], **flag})
    return {
        "static": static,
        "executed": executed,
        "ci": ci,
        "class_counts": class_counts,
        "fail_open_ids": fail_open_ids,
        "measures_nothing_ids": measures_nothing_ids,
        "named_cases": named,
        "default_off_flags": default_off,
        "gate_count_executed": len(executed),
        "gate_count_static": len(static),
    }


def main() -> int:
    snap = snapshot()
    print(
        json.dumps(
            {
                k: snap[k]
                for k in (
                    "class_counts",
                    "fail_open_ids",
                    "measures_nothing_ids",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"executed={snap['gate_count_executed']} "
        f"fail_open={len(snap['fail_open_ids'])} "
        f"measures_nothing={len(snap['measures_nothing_ids'])} "
        f"ci_fail_open_steps={snap['ci'].get('fail_open_step_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
