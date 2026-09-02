#!/usr/bin/env python3
"""BLD-0047 armed-versus-present gate census.

Enumerates validator/linter/test entry points under tools/, scripts/, platform/,
hooks/, and command-center/*.py; diffs them against CI run: blocks; and classifies
each as ARMED, DISARMED (invoked without its arming flag), NOT-INVOKED, or
NOT-ARMED (only inside a disabled workflow).
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
VALIDATE = REPO / "tools" / "command-center" / "validate.py"
REGISTER_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/REGISTER.md"
ORPHAN_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/orphan_lint.py"
ARMED_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/armed_gate.py"
CI_ARMED_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/ci_armed.yml"
BROKEN_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/broken.json"
GOOD_REL = "command-center/p2-wave/probes/BLD-0047/fixtures/good.json"

SCAN_DIRS = ("tools", "scripts", "platform", "hooks")
CI_DIRS = (
    Path(".github") / "workflows",
    Path("ci") / "workflows",
)
SKIP_PARTS = {
    "__pycache__",
    "p2-wave",
    "node_modules",
    ".git",
    "site-packages",
}
MODE_FLAGS = {
    "json",
    "verbose",
    "quiet",
    "help",
    "version",
    "force",
    "dry-run",
    "dry_run",
    "write",
    "out",
    "report",
    "self-test",
    "self_test",
}


def posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _has_main(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            continue
        if not isinstance(test.ops[0], ast.Eq):
            continue
        left, comps = test.left, test.comparators
        names = set()
        for expr in (left, comps[0] if comps else None):
            if isinstance(expr, ast.Name):
                names.add(expr.id)
            elif isinstance(expr, ast.Constant) and expr.value == "__main__":
                names.add("__main__")
        if "__name__" in names and "__main__" in names:
            return True
    return False


def extract_store_true_flags(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    flags: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else ""
        if attr != "add_argument":
            continue
        names: list[str] = []
        action = None
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.append(arg.value)
        for kw in node.keywords:
            if kw.arg == "action" and isinstance(kw.value, ast.Constant):
                action = kw.value.value
        if action != "store_true":
            continue
        for name in names:
            if name.startswith("--"):
                flags.append(name)
    # Preserve order, drop dupes.
    seen: set[str] = set()
    out: list[str] = []
    for flag in flags:
        if flag not in seen:
            seen.add(flag)
            out.append(flag)
    return out


def arming_flags_for(path: Path, all_store_true: list[str]) -> list[str]:
    rel = posix(path.relative_to(REPO)) if path.is_absolute() else posix(path)
    # Known arming flags that actually enable a named check.
    known = {
        "tools/command-center/validate.py": ["--require-complete"],
        "tools/command-center/render.py": ["--check"],
        "tools/command-center/unit_manifest.py": ["--check"],
        "tools/command-center/eol_policy.py": ["--check"],
        "command-center/p2-wave/probes/BLD-0047/fixtures/armed_gate.py": ["--strict"],
        "command-center/p2-wave/probes/BLD-0047/fixtures/orphan_lint.py": ["--strict"],
    }
    if rel in known:
        return list(known[rel])
    out = []
    for flag in all_store_true:
        key = flag.lstrip("-").replace("-", "_")
        if key in MODE_FLAGS:
            continue
        if any(
            token in flag
            for token in ("require", "strict", "check", "complete", "enforce", "arm")
        ):
            out.append(flag)
    return out


def discover_gates(repo: Path | None = None) -> list[dict[str, Any]]:
    root = repo or REPO
    gates: dict[str, dict[str, Any]] = {}

    def add(path: Path, kind: str) -> None:
        if not path.is_file() or is_skipped(path):
            return
        try:
            rel = posix(path.relative_to(root))
        except ValueError:
            return
        if rel in gates:
            return
        flags = extract_store_true_flags(path) if path.suffix == ".py" else []
        gates[rel] = {
            "path": rel,
            "kind": kind,
            "store_true_flags": flags,
            "arming_flags": arming_flags_for(path, flags),
            "bytes": path.stat().st_size,
        }

    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if is_skipped(path):
                continue
            rel_parts = path.relative_to(base).parts
            is_test = (
                "tests" in rel_parts
                or path.name.startswith("test_")
                or path.name.endswith("_test.py")
            )
            if is_test:
                if path.name.startswith("test_") or path.name.endswith("_test.py"):
                    add(path, "test-entry")
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            if _has_main(tree):
                add(path, "cli-gate")

    cc = root / "command-center"
    if cc.is_dir():
        for path in cc.iterdir():
            if path.suffix == ".py" and path.is_file():
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, SyntaxError):
                    continue
                if _has_main(tree):
                    add(path, "cli-gate")

    return [gates[k] for k in sorted(gates)]


def _workflow_disabled(text: str) -> bool:
    # Whole-file disable: top-level `if: false` before jobs, or filename handled by caller.
    lines = [ln.rstrip() for ln in text.splitlines()]
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("if:") and stripped.split(":", 1)[1].strip() in {
            "false",
            "False",
        }:
            return True
        if stripped.startswith("jobs:"):
            break
    return False


def _job_disabled_blocks(text: str) -> bool:
    """True when EVERY job carries `if: false` (workflow is present but not armed)."""
    jobs = re.findall(
        r"(?m)^  [A-Za-z0-9_-]+:\n((?:    .*\n)+)",
        text if text.endswith("\n") else text + "\n",
    )
    if not jobs:
        return False
    return all(re.search(r"(?m)^    if:\s*false\s*$", block) for block in jobs)


def parse_ci_file(path: Path, repo: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = posix(path.relative_to(repo))
    disabled = (
        path.name.endswith(".disabled.yml")
        or path.name.endswith(".disabled.yaml")
        or _workflow_disabled(text)
        or _job_disabled_blocks(text)
    )
    invocations: list[dict[str, Any]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        m = re.match(r"^(\s*)run:\s*(.*)$", raw)
        if not m:
            i += 1
            continue
        indent, rest = m.group(1), m.group(2).strip()
        block: list[str] = []
        if rest in {"|", "|-", "|+", ">"} or rest == "":
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    i += 1
                    continue
                if len(nxt) - len(nxt.lstrip(" ")) <= len(indent):
                    break
                block.append(nxt.strip())
                i += 1
        else:
            block.append(rest)
            i += 1
        cmd = "\n".join(block)
        if cmd:
            invocations.append(
                {
                    "workflow": rel,
                    "command": cmd,
                    "line": raw.strip(),
                    "disabled": disabled,
                }
            )
    return invocations


_PY_PATH = re.compile(
    r"(?:^|[\s'\"])((?:tools|command-center|platform|scripts|hooks)/[A-Za-z0-9_./-]+\.py)"
)


def python_paths_in_command(command: str) -> list[str]:
    found: list[str] = []
    for match in _PY_PATH.finditer(posix(command)):
        rel = match.group(1)
        if rel not in found:
            found.append(rel)
    return found


def discover_ci(repo: Path | None = None) -> list[dict[str, Any]]:
    root = repo or REPO
    out: list[dict[str, Any]] = []
    for rel in CI_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.yml")) + sorted(base.glob("*.yaml")):
            out.extend(parse_ci_file(path, root))
    return out


def command_hits_gate(command: str, gate_rel: str) -> bool:
    cmd = posix(command)
    rel = posix(gate_rel)
    if rel in cmd:
        return True
    name = Path(rel).name
    pat = r"(?:^|[\s'\"/=])" + re.escape(name) + r"(?:$|[\s'\"])"
    return re.search(pat, cmd) is not None


def invocation_line(inv: dict[str, Any]) -> str:
    line = (inv.get("line") or "").strip()
    if line in {"run: |", "run: |-", "run: |+", "run: >", "run:"}:
        return " ".join((inv.get("command") or "").split())
    return line or (inv.get("command") or "")


def classify_gate(gate: dict[str, Any], invocations: list[dict[str, Any]]) -> dict[str, Any]:
    hits = [inv for inv in invocations if command_hits_gate(inv["command"], gate["path"])]
    enabled = [inv for inv in hits if not inv.get("disabled")]
    disabled_only = [inv for inv in hits if inv.get("disabled")]
    arming = list(gate.get("arming_flags") or [])
    row = {
        "path": gate["path"],
        "kind": gate.get("kind"),
        "arming_flags": arming,
        "store_true_flags": list(gate.get("store_true_flags") or []),
        "ci_hits": len(hits),
        "ci_invocation_line": None,
        "missing_arming_flags": [],
        "classification": "NOT-INVOKED",
    }
    if enabled:
        inv = enabled[0]
        row["ci_invocation_line"] = invocation_line(inv)
        row["ci_workflow"] = inv.get("workflow")
        missing = [flag for flag in arming if flag not in inv["command"]]
        fully = [
            item
            for item in enabled
            if all(flag in item["command"] for flag in arming)
        ]
        if fully or not arming:
            chosen = fully[0] if fully else inv
            row["ci_invocation_line"] = invocation_line(chosen)
            row["ci_workflow"] = chosen.get("workflow")
            row["missing_arming_flags"] = []
            row["classification"] = "ARMED"
        else:
            row["missing_arming_flags"] = missing
            row["classification"] = "DISARMED"
        return row
    if disabled_only:
        inv = disabled_only[0]
        row["ci_invocation_line"] = invocation_line(inv)
        row["ci_workflow"] = inv.get("workflow")
        row["classification"] = "NOT-ARMED"
        return row
    row["ci_invocation_line"] = "ABSENT from every CI workflow"
    return row


def is_finding(row: dict[str, Any]) -> bool:
    return row.get("classification") in {"DISARMED", "NOT-INVOKED", "NOT-ARMED"}


def finding_from(row: dict[str, Any]) -> dict[str, Any]:
    flags = row.get("missing_arming_flags") or row.get("arming_flags") or []
    flag = flags[0] if flags else "none-declared"
    return {
        "path": row["path"],
        "classification": row["classification"],
        "ci_invocation_line": row.get("ci_invocation_line") or "ABSENT from every CI workflow",
        "arming_flag": flag,
        "missing_arming_flags": list(row.get("missing_arming_flags") or []),
        "ci_workflow": row.get("ci_workflow"),
        "kind": row.get("kind"),
    }


def classify_all(
    gates: list[dict[str, Any]],
    invocations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [classify_gate(g, invocations) for g in gates]
    findings = [finding_from(r) for r in rows if is_finding(r)]
    return rows, findings


def live_census() -> dict[str, Any]:
    gates = discover_gates()
    invocations = discover_ci()
    known = {g["path"] for g in gates}
    for inv in invocations:
        for rel in python_paths_in_command(inv["command"]):
            path = REPO / rel
            if rel in known or not path.is_file():
                continue
            gates.append(extra_gate(rel, kind="ci-invoked"))
            known.add(rel)
    rows, findings = classify_all(gates, invocations)
    quality = REPO / ".github" / "workflows" / "quality.yml"
    return {
        "gate_count": len(rows),
        "finding_count": len(findings),
        "by_class": {
            label: sum(1 for r in rows if r["classification"] == label)
            for label in ("ARMED", "DISARMED", "NOT-INVOKED", "NOT-ARMED")
        },
        "quality_yml_present": quality.is_file(),
        "ci_invocation_count": len(invocations),
        "gates": rows,
        "findings": findings,
        "ci_invocations": [
            {
                "workflow": inv["workflow"],
                "command": inv["command"],
                "disabled": inv["disabled"],
            }
            for inv in invocations
        ],
    }


def extra_gate(rel: str, kind: str = "cli-gate") -> dict[str, Any]:
    path = REPO / rel
    flags = extract_store_true_flags(path)
    return {
        "path": rel,
        "kind": kind,
        "store_true_flags": flags,
        "arming_flags": arming_flags_for(path, flags),
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def control_not_invoked() -> dict[str, Any]:
    """A gate present in the tree but absent from every live CI workflow is NOT-INVOKED."""
    gates = discover_gates() + [extra_gate(ORPHAN_REL)]
    invocations = discover_ci()
    rows, findings = classify_all(gates, invocations)
    orphan = next(r for r in rows if r["path"] == ORPHAN_REL)
    reported = any(f["path"] == ORPHAN_REL for f in findings)
    return {
        "id": "not-invoked-present-gate",
        "classification": orphan["classification"],
        "reported": reported,
        "pass": orphan["classification"] == "NOT-INVOKED" and reported,
    }


def control_armed_not_reported() -> dict[str, Any]:
    """A gate invoked WITH its arming flag must not be reported as a hole."""
    gates = discover_gates() + [extra_gate(ARMED_REL)]
    invocations = discover_ci() + parse_ci_file(REPO / CI_ARMED_REL, REPO)
    rows, findings = classify_all(gates, invocations)
    armed = next(r for r in rows if r["path"] == ARMED_REL)
    reported = any(f["path"] == ARMED_REL for f in findings)
    return {
        "id": "armed-with-flag-not-reported",
        "classification": armed["classification"],
        "reported": reported,
        "ci_invocation_line": armed.get("ci_invocation_line"),
        "pass": armed["classification"] == "ARMED" and not reported,
    }


def _min_catalog(register_sha: str) -> dict[str, Any]:
    return {
        "defaults": {
            "assignment": {
                "basis": "BLD-0047 fixture",
                "model": "opus",
                "role": "implementer",
                "vendor": "anthropic",
            },
            "execution_substrate": "local",
            "failure_classification": ["green-not-live"],
            "output_schema": "command-center/schema/receipt.schema.json",
            "retry_policy": "two strikes",
            "reviewer_requirement": "one independent reviewer",
            "tests_required": ["both-states control"],
            "timeout_seconds": 1800,
            "tool_permissions": ["Read"],
        },
        "items": [
            {
                "id": "R-A01",
                "title": "Fixture item for validate.py defaults-deletion hole",
                "phase": "0",
                "target": "Reproduce V-FIELDS disarming when require_complete defaults False",
                "inputs": ["command-center/p2-wave/probes/BLD-0047/fixtures/REGISTER.md"],
                "dependencies": [],
                "output_path": "command-center/receipts/R-A01.json",
                "evidence_requirement": "exit codes from the same CLI with and without --require-complete",
                "completion_sentinel": "SUCCESS:R-A01",
                "owner_approval_required": False,
                "next_smallest_action": "Run the defaults-deletion mutation against this fixture.",
                "disposition": None,
                "status": "OPEN",
                "program": "A-toolchain",
            }
        ],
        "owner_questions": [],
        "provenance": {
            "register": REGISTER_REL,
            "register_sha256": register_sha,
        },
    }


def reproduce_known_hole() -> dict[str, Any]:
    """Deleting the defaults block exits 0 bare, and exits non-zero with --require-complete."""
    sys.path.insert(0, str(REPO / "tools" / "command-center"))
    import catalog as cat  # noqa: WPS433

    register = REPO / REGISTER_REL
    sha = digest_bytes(register.read_bytes())
    catalog = _min_catalog(sha)
    graph = cat.build_graph(catalog)
    with tempfile.TemporaryDirectory(prefix="bld0047-hole-") as tmp:
        tmp_path = Path(tmp)
        cat_path = tmp_path / "catalog.json"
        mutated = tmp_path / "catalog-no-defaults.json"
        graph_path = tmp_path / "graph.json"
        cat.save(catalog, cat_path)
        stripped = json.loads(cat_path.read_text(encoding="utf-8"))
        stripped.pop("defaults", None)
        cat.save(stripped, mutated)
        cat.save(graph, graph_path)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        base = [
            sys.executable,
            "-B",
            str(VALIDATE),
            "--catalog",
            str(mutated),
            "--graph",
            str(graph_path),
            "--register",
            str(register),
        ]
        bare = subprocess.run(
            base, cwd=str(REPO), capture_output=True, text=True, env=env, check=False
        )
        armed = subprocess.run(
            base + ["--require-complete"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    return {
        "id": "known-bare-invocation-hole",
        "gate": "tools/command-center/validate.py",
        "arming_flag": "--require-complete",
        "mutation": "delete catalog defaults block",
        "bare_exit": bare.returncode,
        "armed_exit": armed.returncode,
        "bare_tail": ((bare.stdout or "") + (bare.stderr or "")).strip()[-400:],
        "armed_tail": ((armed.stdout or "") + (armed.stderr or "")).strip()[-400:],
        "pass": bare.returncode == 0 and armed.returncode != 0,
    }


def reviewer_execute() -> dict[str, Any]:
    """Independent of the classifier: run two gates with and without arming flags."""
    hole = reproduce_known_hole()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    gate = REPO / ARMED_REL
    broken = REPO / BROKEN_REL
    good = REPO / GOOD_REL

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(gate), *args],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    bare_broken = run([str(broken)])
    strict_broken = run(["--strict", str(broken)])
    strict_good = run(["--strict", str(good)])
    ok = (
        hole["pass"]
        and bare_broken.returncode == 0
        and strict_broken.returncode != 0
        and strict_good.returncode == 0
    )
    return {
        "reviewer_id": "BLD-0047-flag-executor",
        "independent": True,
        "verdict": "PASS" if ok else "FAIL",
        "gates": [
            {
                "path": "tools/command-center/validate.py",
                "flag": "--require-complete",
                "without_flag_exit": hole["bare_exit"],
                "with_flag_exit": hole["armed_exit"],
                "behaviour_differs": hole["bare_exit"] != hole["armed_exit"],
            },
            {
                "path": ARMED_REL,
                "flag": "--strict",
                "without_flag_exit": bare_broken.returncode,
                "with_flag_exit": strict_broken.returncode,
                "good_with_flag_exit": strict_good.returncode,
                "behaviour_differs": bare_broken.returncode != strict_broken.returncode,
            },
        ],
        "pass": ok,
    }


def dependency_receipts() -> dict[str, str]:
    out = {}
    for uid in ("IMP-0437", "TST-0076"):
        path = REPO / "command-center" / "receipts" / f"{uid}.json"
        out[uid] = "PRESENT" if path.is_file() and path.stat().st_size > 0 else "ABSENT"
    return out


def row_for(path: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("path") == path:
            return row
    return None
