#!/usr/bin/env python3
"""TST-0004: exit-0 with a missing artifact is FAILED at condition 2.

Condition 2 of the shared completion predicate is "expected artifact exists".
Exit code 0 is never success by itself (_USER-PROMPTS.md:10646; failure class
:11311). This harness:

  * classifies a dispatched worker from (exit_code, artifact path) and never
    returns SUCCESS when the contracted artifact is absent
  * actually spawns a worker that exits 0 and writes nothing
  * censuses every ``returncode == 0`` / ``$LASTEXITCODE -eq 0`` site in the
    runner tree and verdicts whether it short-circuits unit success before
    the artifact check
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONDITION_2_ID = 2
CONDITION_2_TEXT = "expected artifact exists"
RUNNER_REL_PATHS = (
    "command-center/p2-wave/seed-stage",
    "command-center/p2-wave/_measure_one_delivered.py",
    "tools/command-center",
)
PS_EQ0 = re.compile(r"\$LASTEXITCODE\s+-eq\s+0", re.IGNORECASE)
PLANTED_SHORT_CIRCUIT = (
    "def treat_exit_zero_as_success(proc):\n"
    "    if proc.returncode == 0:\n"
    "        return 'SUCCESS'\n"
    "    return 'FAILED'\n"
)


def artifact_exists(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def classify(
    *,
    exit_code: int,
    artifact_path: Path | str,
    unit_id: str = "INJECTED",
) -> dict[str, Any]:
    """Fan-in classifier: missing artifact => FAILED at condition 2, even if rc=0."""
    path = Path(artifact_path)
    exists = artifact_exists(path)
    size = int(path.stat().st_size) if exists else 0
    if not exists:
        return {
            "unit_id": unit_id,
            "verdict": "FAILED",
            "exit_code": int(exit_code),
            "artifact_path": path.as_posix(),
            "artifact_exists": False,
            "artifact_bytes": 0,
            "failing_condition_id": CONDITION_2_ID,
            "condition_2": {
                "id": CONDITION_2_ID,
                "outcome": "FALSE",
                "text": CONDITION_2_TEXT,
            },
            "reason": (
                f"condition 2 FALSE: expected artifact missing "
                f"path={path.as_posix()} exit_code={exit_code} "
                "(exit 0 is not success)"
            ),
            "exit_zero_alone_never_success": True,
        }
    return {
        "unit_id": unit_id,
        "verdict": "SUCCESS",
        "exit_code": int(exit_code),
        "artifact_path": path.as_posix(),
        "artifact_exists": True,
        "artifact_bytes": size,
        "failing_condition_id": None,
        "condition_2": {
            "id": CONDITION_2_ID,
            "outcome": "TRUE",
            "text": CONDITION_2_TEXT,
        },
        "reason": (
            f"condition 2 TRUE: artifact exists bytes={size} "
            f"exit_code={exit_code}"
        ),
        "exit_zero_alone_never_success": True,
    }


def measure_artifact_gate(path: Path) -> dict[str, Any]:
    """Replay of `_measure_one_delivered.py` existence gate (predicate:absent)."""
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "source": "command-center/p2-wave/_measure_one_delivered.py",
            "gate": "predicate:absent",
            "verdict": "FAILED",
            "failing_condition_id": CONDITION_2_ID,
            "artifact_exists": False,
        }
    return {
        "source": "command-center/p2-wave/_measure_one_delivered.py",
        "gate": "artifact-present",
        "verdict": "CONTINUE",
        "failing_condition_id": None,
        "artifact_exists": True,
    }


def spawn_exit0_worker(artifact: Path, write_artifact: bool) -> dict[str, Any]:
    """Dispatch a worker that exits 0. Optionally writes the contracted artifact."""
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if artifact.exists():
        artifact.unlink()
    if write_artifact:
        worker = (
            "import json, pathlib, sys\n"
            f"p = pathlib.Path({str(artifact)!r})\n"
            "p.write_text(json.dumps({'ok': True, 'sentinel': "
            "'SUCCESS:INJECTED-VALID-ARTIFACT'}) + '\\n', encoding='utf-8')\n"
            "sys.exit(0)\n"
        )
        payload = {"ok": True, "sentinel": "SUCCESS:INJECTED-VALID-ARTIFACT"}
    else:
        worker = (
            "import sys\n"
            "# contracted artifact deliberately not written\n"
            "sys.exit(0)\n"
        )
        payload = None
    proc = subprocess.run(
        [sys.executable, "-c", worker],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    classification = classify(
        exit_code=proc.returncode,
        artifact_path=artifact,
        unit_id="INJECTED-EXIT0",
    )
    gate = measure_artifact_gate(artifact)
    return {
        "wrote_artifact": write_artifact,
        "worker_exit_code": proc.returncode,
        "worker_stdout": (proc.stdout or "")[-500:],
        "worker_stderr": (proc.stderr or "")[-500:],
        "payload_planned": payload,
        "classification": classification,
        "measure_gate": gate,
        "never_success_on_missing": (
            classification["verdict"] != "SUCCESS" if not write_artifact else True
        ),
    }


def run_injection_pair(scratch: Path | None = None) -> dict[str, Any]:
    root = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="tst0004-inj-"))
    missing_path = root / "absent" / "contracted.json"
    present_path = root / "present" / "contracted.json"
    missing = spawn_exit0_worker(missing_path, write_artifact=False)
    present = spawn_exit0_worker(present_path, write_artifact=True)
    miss_cls = missing["classification"]
    pres_cls = present["classification"]
    ok_missing = (
        miss_cls["verdict"] == "FAILED"
        and miss_cls["failing_condition_id"] == CONDITION_2_ID
        and miss_cls["exit_code"] == 0
        and missing["worker_exit_code"] == 0
        and missing["measure_gate"]["verdict"] == "FAILED"
        and missing["measure_gate"]["failing_condition_id"] == CONDITION_2_ID
    )
    ok_present = (
        pres_cls["verdict"] == "SUCCESS"
        and pres_cls["failing_condition_id"] is None
        and pres_cls["condition_2"]["outcome"] == "TRUE"
        and present["worker_exit_code"] == 0
        and present["measure_gate"]["verdict"] == "CONTINUE"
    )
    return {
        "scratch": root.as_posix(),
        "missing": missing,
        "present": present,
        "test_exit0_no_artifact_is_failed": ok_missing,
        "test_exit0_with_valid_artifact_is_success": ok_present,
        "both_states_pair": ok_missing and ok_present,
    }


def _snippet(source: str, lineno: int, radius: int = 2) -> str:
    lines = source.splitlines()
    i = lineno - 1
    lo = max(0, i - radius)
    hi = min(len(lines), i + radius + 1)
    return "\n".join(lines[lo:hi])


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_returncode_eq_zero(node: ast.Compare) -> bool:
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    if len(node.comparators) != 1:
        return False
    names = {_name_of(node.left), _name_of(node.comparators[0])}
    if "returncode" not in names and "return_code" not in names:
        return False
    other = (
        node.comparators[0]
        if _name_of(node.left) in {"returncode", "return_code"}
        else node.left
    )
    return isinstance(other, ast.Constant) and other.value == 0


def _function_source(source: str, fn: ast.AST) -> str:
    try:
        return ast.get_source_segment(source, fn) or ""
    except (TypeError, ValueError):
        return ""


def _verdict_for_python_site(fn_src: str, rel: str) -> tuple[str, str]:
    low = fn_src.lower()
    posix = rel.replace("\\", "/")
    if "predicate:absent" in low or (
        "is_file" in low and ("st_size" in low or "output_path" in low)
    ):
        return (
            "AFTER-ARTIFACT",
            "returncode==0 is evaluated with or after an artifact existence gate",
        )
    if posix.endswith("_measure_one_delivered.py"):
        return (
            "AFTER-ARTIFACT",
            "G-1 measure checks the contracted artifact before treating rc==0 as delivery",
        )
    if posix.endswith("dispatch_cursor.py"):
        return (
            "AFTER-ARTIFACT",
            "supervisor uses measure rc (artifact-gated), not worker returncode, for ok",
        )
    has_artifact = any(
        tok in low
        for tok in (
            "is_file",
            "st_size",
            "predicate:absent",
            "output_path",
            "artifact",
            "exists",
            "manifest",
        )
    )
    talks_success = any(
        tok in low
        for tok in (
            "success",
            "delivered",
            "complete",
            "ok =",
            "is_green",
            "measure_ok",
        )
    )
    if has_artifact and talks_success:
        return (
            "CONJOINED",
            "same function mentions both returncode==0 and an artifact/existence check",
        )
    if talks_success and not has_artifact:
        return (
            "SHORT-CIRCUIT",
            "returncode==0 used as success/delivery without an artifact existence check",
        )
    return (
        "INCIDENTAL",
        "returncode==0 is not used as unit-success; incidental subprocess check",
    )


def _iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    if not root.is_dir():
        return
    for path in root.rglob("*.py"):
        if path.is_file():
            yield path


def _iter_ps_files(root: Path) -> Iterable[Path]:
    suffixes = {".ps1", ".psm1"}
    if root.is_file() and root.suffix.lower() in suffixes:
        yield root
        return
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def census_python(path: Path) -> list[dict[str, Any]]:
    rel = path.relative_to(REPO).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            {
                "path": rel,
                "line": 1,
                "kind": "python-returncode==0",
                "verdict": "UNREADABLE",
                "reason": type(exc).__name__,
                "snippet": "",
                "function": None,
            }
        ]
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            {
                "path": rel,
                "line": int(exc.lineno or 1),
                "kind": "python-returncode==0",
                "verdict": "PARSE-FAIL",
                "reason": exc.msg,
                "snippet": "",
                "function": None,
            }
        ]
    rows: list[dict[str, Any]] = []
    fn_stack: list[ast.AST] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            fn_stack.append(node)
            self.generic_visit(node)
            fn_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            fn_stack.append(node)
            self.generic_visit(node)
            fn_stack.pop()

        def visit_Compare(self, node: ast.Compare) -> None:
            if _is_returncode_eq_zero(node):
                fn = fn_stack[-1] if fn_stack else None
                fn_src = _function_source(source, fn) if fn is not None else source
                verdict, reason = _verdict_for_python_site(fn_src, rel)
                rows.append(
                    {
                        "path": rel,
                        "line": int(getattr(node, "lineno", 1) or 1),
                        "kind": "python-returncode==0",
                        "verdict": verdict,
                        "reason": reason,
                        "snippet": _snippet(source, int(getattr(node, "lineno", 1) or 1)),
                        "function": getattr(fn, "name", None),
                    }
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    return rows


def census_powershell(path: Path) -> list[dict[str, Any]]:
    rel = path.relative_to(REPO).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for i, line in enumerate(source.splitlines(), 1):
        if PS_EQ0.search(line):
            rows.append(
                {
                    "path": rel,
                    "line": i,
                    "kind": "powershell-LASTEXITCODE-eq-0",
                    "verdict": "NEEDS-REVIEW",
                    "reason": "PowerShell LASTEXITCODE -eq 0 site in runner tree",
                    "snippet": line.strip(),
                    "function": None,
                }
            )
    return rows


def census_planted_control() -> dict[str, Any]:
    """Detector control: a known short-circuit snippet must be flagged."""
    tree = ast.parse(PLANTED_SHORT_CIRCUIT)
    hits = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and _is_returncode_eq_zero(node):
            hits += 1
    verdict, reason = _verdict_for_python_site(
        PLANTED_SHORT_CIRCUIT, "planted://short-circuit.py"
    )
    fired = hits >= 1 and verdict == "SHORT-CIRCUIT"
    return {
        "planted": True,
        "hits": hits,
        "verdict": verdict,
        "reason": reason,
        "fired_on_known_short_circuit": fired,
        "silent_on_plant_is_detector_failure": True,
    }


def run_census() -> dict[str, Any]:
    sites: list[dict[str, Any]] = []
    missing_roots: list[str] = []
    for rel in RUNNER_REL_PATHS:
        root = REPO / rel
        if not root.exists():
            missing_roots.append(rel)
            continue
        for py in _iter_python_files(root):
            sites.extend(census_python(py))
        for ps in _iter_ps_files(root):
            sites.extend(census_powershell(ps))
    planted = census_planted_control()
    short = [s for s in sites if s["verdict"] == "SHORT-CIRCUIT"]
    after = [s for s in sites if s["verdict"] in {"AFTER-ARTIFACT", "CONJOINED"}]
    incidental = [s for s in sites if s["verdict"] == "INCIDENTAL"]
    return {
        "runner_roots": list(RUNNER_REL_PATHS),
        "missing_roots": missing_roots,
        "site_count": len(sites),
        "sites": sites,
        "short_circuit_count": len(short),
        "short_circuit_sites": short,
        "after_artifact_count": len(after),
        "incidental_count": len(incidental),
        "powershell_eq0_count": sum(
            1 for s in sites if str(s["kind"]).startswith("powershell")
        ),
        "planted_control": planted,
        "any_runner_short_circuits_rc0_before_artifact": len(short) > 0,
    }


def independent_oracle_c2(missing_path: Path, present_path: Path) -> dict[str, Any]:
    """Second signal: IMP-0241 shared oracle.judge, if present."""
    oracle_dir = REPO / "command-center/p2-wave/probes/IMP-0241"
    oracle_py = oracle_dir / "oracle.py"
    if not oracle_py.is_file():
        return {"available": False, "reason": "IMP-0241/oracle.py absent"}
    sys.path.insert(0, str(oracle_dir))
    try:
        import oracle as ora  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"import-failed:{type(exc).__name__}"}
    missing_v = ora.judge(
        {
            "exit_code": 0,
            "artifact_path": str(missing_path),
            "repo": str(REPO),
        }
    )
    present_v = ora.judge(
        {
            "exit_code": 0,
            "artifact_path": str(present_path),
            "repo": str(REPO),
        }
    )

    def c2(verdict: dict[str, Any]) -> dict[str, Any] | None:
        for row in verdict.get("conditions") or []:
            if str(row.get("id")) == "c2":
                return row
        return None

    miss_c2 = c2(missing_v)
    pres_c2 = c2(present_v)
    miss_ok = (
        miss_c2 is not None
        and miss_c2.get("outcome") == "FALSE"
        and missing_v.get("result") != "COMPLETE"
    )
    pres_ok = pres_c2 is not None and pres_c2.get("outcome") == "TRUE"
    return {
        "available": True,
        "reducer": "oracle.judge",
        "missing_result": missing_v.get("result"),
        "missing_c2": miss_c2,
        "present_result": present_v.get("result"),
        "present_c2": pres_c2,
        "missing_c2_false_and_not_complete": miss_ok,
        "present_c2_true": pres_ok,
        "exit_code_ignored_for_complete": True,
    }


def fake_exit0_success_classifier(exit_code: int, _artifact_path: Path) -> str:
    """Negative control: the forbidden short-circuit this unit exists to catch."""
    return "SUCCESS" if exit_code == 0 else "FAILED"


def negative_control_rejects_rc0_short_circuit() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0004-nc-") as tmp:
        missing = Path(tmp) / "nope.json"
        fake = fake_exit0_success_classifier(0, missing)
        honest = classify(exit_code=0, artifact_path=missing)
        fired = fake == "SUCCESS" and honest["verdict"] == "FAILED"
        return {
            "fake_verdict": fake,
            "honest_verdict": honest["verdict"],
            "honest_failing_condition_id": honest["failing_condition_id"],
            "fired_on_bad_classifier": fired,
            "silent_on_good_state": honest["verdict"] == "FAILED",
        }


def run_all() -> dict[str, Any]:
    pair = run_injection_pair()
    census = run_census()
    oracle = independent_oracle_c2(
        Path(pair["missing"]["classification"]["artifact_path"]),
        Path(pair["present"]["classification"]["artifact_path"]),
    )
    nc = negative_control_rejects_rc0_short_circuit()
    planted_ok = census["planted_control"]["fired_on_known_short_circuit"] is True
    return {
        "pair": pair,
        "census": census,
        "oracle": oracle,
        "negative_control": nc,
        "planted_ok": planted_ok,
    }


if __name__ == "__main__":
    doc = run_all()
    print(json.dumps(doc, indent=2, sort_keys=True, default=str))
    if not doc["pair"]["both_states_pair"]:
        print("FAILED:TST-0004 harness both-states pair")
        raise SystemExit(1)
    if not doc["negative_control"]["fired_on_bad_classifier"]:
        print("FAILED:TST-0004 harness negative control")
        raise SystemExit(1)
    if not doc["planted_ok"]:
        print("FAILED:TST-0004 harness planted short-circuit not detected")
        raise SystemExit(1)
    print("SUCCESS:TST-0004 harness")
    raise SystemExit(0)
