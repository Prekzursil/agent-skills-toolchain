#!/usr/bin/env python3
"""AUD-0045 Probe 1: static census of fail-open patterns in CI/local gate scripts.

Looks for early-return-on-empty, default-off flags, swallowed exceptions, and
skipped-tool paths. Does not weaken any gate.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent

# Gates named by CI workflows + catalog-measured cases
GATE_CANDIDATES = [
    "tools/command-center/validate.py",
    "tools/measure-guard/unitgate.py",
    "tools/measure-guard/suitefloor.py",
    "tools/measure-guard/refcheck.py",
    "command-center/ci/interpreter_floor_gate.py",
    "command-center/mcp-audit/ci_gate.py",
    "command-center/hook-audit/check_citations.py",
    "command-center/hook-audit/hook_predeploy_gate.py",
    "command-center/p2-next/rail_count_gate.py",
    "command-center/p2-next/split_review_gate.py",
    "command-center/p2-next/vendor_satisfiability.py",
    "command-center/slop-report/check_published_commands.py",
    "command-center/ssot/ssot_drift_gate.py",
    "docs/rule-audit/ci_gate.py",
    "ci/check_skill_description_ratchet.py",
    "ci/check_skill_dual_write.py",
    "ci/check_skill_render_traps.py",
    "ci/gen_skill_index.py",
    "ci/gen_skills_manifest.py",
    ".agents/skills/claim-verify-gate/scripts/claim_gate.py",
    "hooks/harness-bench/gate.py",
]


def discover_from_workflows() -> list[str]:
    found = set(GATE_CANDIDATES)
    wf = REPO / ".github" / "workflows"
    if wf.is_dir():
        for p in wf.glob("*.yml"):
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(
                r"(?:python(?:3)?\s+(?:-B\s+)?(?:-m\s+)?)([\w./_-]+\.py)", text
            ):
                rel = m.group(1)
                if any(
                    k in rel
                    for k in (
                        "gate",
                        "validate",
                        "check_",
                        "unitgate",
                        "suitefloor",
                        "refcheck",
                        "ci_gate",
                    )
                ):
                    found.add(rel)
    return sorted(found)


class FailOpenVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings: list[dict] = []
        self._func = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self._func
        self._func = node.name
        # default-off kwargs
        for d in node.args.defaults:
            pass
        # kw-only defaults
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if default is None:
                continue
            if isinstance(default, ast.Constant) and default.value is False:
                self.findings.append(
                    {
                        "kind": "default-off-flag",
                        "func": node.name,
                        "flag": arg.arg,
                        "lineno": arg.lineno,
                    }
                )
        # positional defaults aligned from the end
        positional = node.args.args
        defaults = node.args.defaults
        if defaults:
            for arg, default in zip(positional[-len(defaults) :], defaults):
                if isinstance(default, ast.Constant) and default.value is False:
                    self.findings.append(
                        {
                            "kind": "default-off-flag",
                            "func": node.name,
                            "flag": arg.arg,
                            "lineno": arg.lineno,
                        }
                    )
        self.generic_visit(node)
        self._func = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        body = node.body
        if body and all(
            isinstance(s, ast.Pass)
            or (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Constant)
                and s.value.value is Ellipsis
            )
            for s in body
        ):
            self.findings.append(
                {
                    "kind": "swallowed-exception",
                    "func": self._func,
                    "lineno": node.lineno,
                    "type": ast.unparse(node.type) if node.type else "bare",
                }
            )
        # return 0 inside except
        for s in body:
            if isinstance(s, ast.Return) and isinstance(s.value, ast.Constant) and s.value.value == 0:
                self.findings.append(
                    {
                        "kind": "except-return-zero",
                        "func": self._func,
                        "lineno": s.lineno,
                    }
                )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        # if not items / if not args / empty early return 0
        test_src = ast.unparse(node.test)
        emptyish = bool(
            re.search(
                r"not\s+\w+|len\(\w+\)\s*==\s*0|\w+\s*==\s*\[\]|\w+\s*==\s*\{\}|\w+\s*is\s+None",
                test_src,
            )
        )
        for s in node.body:
            if isinstance(s, ast.Return) and isinstance(s.value, ast.Constant):
                if s.value.value in (0, True, None, "ok", "OK"):
                    if emptyish:
                        self.findings.append(
                            {
                                "kind": "early-return-on-empty",
                                "func": self._func,
                                "lineno": s.lineno,
                                "test": test_src[:120],
                                "returns": repr(s.value.value),
                            }
                        )
            if (
                isinstance(s, ast.Return)
                and s.value is None
                and emptyish
                and self._func in {"main", "validate", "check", "run"}
            ):
                self.findings.append(
                    {
                        "kind": "early-return-on-empty",
                        "func": self._func,
                        "lineno": s.lineno,
                        "test": test_src[:120],
                        "returns": "None",
                    }
                )
        self.generic_visit(node)


def analyze_file(rel: str) -> dict:
    path = REPO / rel
    row = {
        "path": rel,
        "exists": path.is_file(),
        "findings": [],
        "parse_error": None,
    }
    if not path.is_file():
        return row
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
    except SyntaxError as e:
        row["parse_error"] = str(e)
        return row
    v = FailOpenVisitor()
    v.visit(tree)
    row["findings"] = v.findings
    row["finding_count"] = len(v.findings)
    return row


def main() -> int:
    gates = discover_from_workflows()
    rows = [analyze_file(g) for g in gates]
    present = [r for r in rows if r["exists"]]
    absent = [r["path"] for r in rows if not r["exists"]]
    by_kind: dict[str, int] = {}
    suspects = []
    for r in present:
        for f in r["findings"]:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        if r["findings"]:
            suspects.append(
                {
                    "path": r["path"],
                    "finding_count": len(r["findings"]),
                    "kinds": sorted({f["kind"] for f in r["findings"]}),
                    "samples": r["findings"][:8],
                }
            )

    # Catalog-named case: validate.py require_complete default False
    validate_row = next((r for r in present if r["path"].endswith("validate.py")), None)
    require_complete_default_off = False
    if validate_row:
        require_complete_default_off = any(
            f.get("flag") == "require_complete" and f["kind"] == "default-off-flag"
            for f in validate_row["findings"]
        )

    result = {
        "unit": "AUD-0045",
        "stage": "linux-local-remeasure",
        "gates_considered": len(gates),
        "gates_present": len(present),
        "gates_absent": absent,
        "finding_counts_by_kind": by_kind,
        "suspect_gates": suspects,
        "suspect_count": len(suspects),
        "validate_require_complete_default_off": require_complete_default_off,
        "rows": rows,
        "ok": len(present) > 0,
    }
    (OUT_DIR / "probe1-static-findings.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "AUD-0045 NAMED PROBE 1: static fail-open pattern census",
        f"unit=AUD-0045",
        f"gates_considered={len(gates)}",
        f"gates_present={len(present)}",
        f"gates_absent={len(absent)}",
        f"finding_counts_by_kind={json.dumps(by_kind)}",
        f"suspect_count={len(suspects)}",
        f"validate_require_complete_default_off={require_complete_default_off}",
        "SUSPECTS:",
    ]
    for s in suspects[:25]:
        lines.append(f"  {s['path']} kinds={s['kinds']} n={s['finding_count']}")
    lines.append("SUCCESS:AUD-0045-probe1" if result["ok"] else "FAILED:AUD-0045-probe1")
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe1-static.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
