"""AUD-0046 detector-control sweep: isolated scratch trees, never the live checkout.

Probe 1 = unmodified scratch (must exit 0).
Probe 2 = planted mutation (must be non-zero) then revert (must return to 0).

CI workflow YAML is absent on this worktree. Gate *commands* that can be
reproduced locally are run against throwaway fixtures. Every other inventoried
CI job is NOT-CHECKED with the blocking reason.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
VALIDATE = CC_TOOLS / "validate.py"
AUD41 = HERE.parent / "AUD-0041" / "probe1-yaml-inventory.json"
AUD45 = REPO / "command-center" / "audit" / "AUD-0045-fail-open-gate-census.json"
QUALITY_YML = REPO / ".github" / "workflows" / "quality.yml"

sys.path.insert(0, str(CC_TOOLS))
import blob  # noqa: E402
import catalog as cat  # noqa: E402

# Captured from AUD-0041 no-runtime-junk.yml (full-path-segment match, not substring).
BAD_DIR_SEGMENTS = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
BAD_BASENAMES = {"installed.json"}

CI_VALIDATE_ARGV: list[str] = []  # quality.yml invokes validate.py with no flags
ARMING_FLAG = "--require-complete"


def _run(cmd: list[str], cwd: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str((cwd or REPO) / ".pycache-aud46")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "tail": "\n".join(out.splitlines()[-8:]),
        "cmd": cmd,
    }


def _good_item() -> dict[str, Any]:
    return {
        "id": "R-1",
        "title": "AUD-0046 isolated fixture",
        "phase": "0",
        "target": "throwaway detector-control catalog",
        "inputs": ["scratch"],
        "dependencies": [],
        "assignment": {"model": "none", "role": "fixture", "vendor": "none"},
        "tool_permissions": ["Read"],
        "execution_substrate": "local",
        "timeout_seconds": 60,
        "output_path": "scratch/out.json",
        "output_schema": "none",
        "evidence_requirement": "both-states",
        "tests_required": ["both-states"],
        "reviewer_requirement": "probe2",
        "completion_sentinel": "SUCCESS:R-1",
        "retry_policy": "none",
        "failure_classification": ["detector-failure"],
        "owner_approval_required": False,
        "program": "A",
        "section": "OUTSTANDING",
        "status": "OPEN",
        "disposition": None,
        "disposition_evidence": "",
        "effort": "S",
        "evidence": "fixture",
        "sources": ["AUD-0046"],
        "reverse_dependencies": [],
        "owner_gate": [],
        "security_class": "none",
        "next_smallest_action": "run the fixture",
        "defer": None,
        "history": [],
    }


def _write_tree(tmp: Path, catalog: dict[str, Any]) -> tuple[Path, Path, Path]:
    tmp.mkdir(parents=True, exist_ok=True)
    register = tmp / "REGISTER.md"
    register.write_text(
        "# REGISTER\n\n## 1. OUTSTANDING\n\n- R-1 fixture\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = blob.sha256_hex(blob.lf_normalise(register.read_bytes()))
    catalog = json.loads(json.dumps(catalog))
    catalog.setdefault("provenance", {})
    catalog["provenance"]["register"] = str(register)
    catalog["provenance"]["register_sha256"] = digest
    catalog.setdefault("defaults", {})
    catalog.setdefault("owner_questions", [])
    cat_path = tmp / "catalog.json"
    graph_path = tmp / "graph.json"
    cat.save(catalog, cat_path)
    loaded = cat.load(cat_path)
    graph_path.write_text(
        json.dumps(cat.build_graph(loaded), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return cat_path, graph_path, register


def _validate(
    cat_path: Path, graph_path: Path, register: Path, extra: list[str] | None = None
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(VALIDATE),
        "--catalog",
        str(cat_path),
        "--graph",
        str(graph_path),
        "--register",
        str(register),
        *(extra or []),
    ]
    return _run(cmd)


def _status(*, good: int, bad: int, reverted: int) -> str:
    if good == 0 and bad != 0 and reverted == 0:
        return "FIRED"
    if good != 0 and bad != 0:
        return "FIRES-IN-BOTH"
    if good == 0 and bad == 0:
        return "SILENT-IN-BOTH"
    return "SILENT-IN-BOTH"


def measure_validate_empty() -> dict[str, Any]:
    """V-EMPTY: items=[] must fail closed under the bare CI argv."""
    with tempfile.TemporaryDirectory(prefix="aud46-empty-") as raw:
        tmp = Path(raw)
        good_cat = {"schema_version": 1, "items": [_good_item()]}
        cat_path, graph_path, register = _write_tree(tmp / "good", good_cat)
        good = _validate(cat_path, graph_path, register, CI_VALIDATE_ARGV)
        empty = {"schema_version": 1, "items": []}
        e_cat, e_graph, e_reg = _write_tree(tmp / "bad", empty)
        bad = _validate(e_cat, e_graph, e_reg, CI_VALIDATE_ARGV)
        # Revert: rewrite the bad tree with the good catalog (same tmp root).
        r_cat, r_graph, r_reg = _write_tree(tmp / "reverted", good_cat)
        reverted = _validate(r_cat, r_graph, r_reg, CI_VALIDATE_ARGV)
    status = _status(
        good=good["exit_code"], bad=bad["exit_code"], reverted=reverted["exit_code"]
    )
    return {
        "id": "cc-validate-V-EMPTY",
        "gate": "gate-tests-coverage command-center / validate.py",
        "claim": "an empty catalog must fail closed (V-EMPTY)",
        "mutation": "items=[]",
        "ci_argv_flags": CI_VALIDATE_ARGV,
        "arming_flag": None,
        "good_exit": good["exit_code"],
        "bad_exit": bad["exit_code"],
        "reverted_exit": reverted["exit_code"],
        "good_tail": good["tail"],
        "bad_tail": bad["tail"],
        "reverted_tail": reverted["tail"],
        "fired_on_bad_state": bad["exit_code"] != 0,
        "silent_on_good_state": good["exit_code"] == 0,
        "revert_restores_green": reverted["exit_code"] == 0,
        "status": status,
    }


def measure_validate_reach1() -> dict[str, Any]:
    """REACH-1: a dangling dependency must turn the gate red."""
    with tempfile.TemporaryDirectory(prefix="aud46-r1-") as raw:
        tmp = Path(raw)
        good_cat = {"schema_version": 1, "items": [_good_item()]}
        cat_path, graph_path, register = _write_tree(tmp / "good", good_cat)
        good = _validate(cat_path, graph_path, register, CI_VALIDATE_ARGV)
        mutant = json.loads(json.dumps(good_cat))
        mutant["items"][0]["dependencies"] = ["R-999"]
        b_cat, b_graph, b_reg = _write_tree(tmp / "bad", mutant)
        bad = _validate(b_cat, b_graph, b_reg, CI_VALIDATE_ARGV)
        r_cat, r_graph, r_reg = _write_tree(tmp / "reverted", good_cat)
        reverted = _validate(r_cat, r_graph, r_reg, CI_VALIDATE_ARGV)
    status = _status(
        good=good["exit_code"], bad=bad["exit_code"], reverted=reverted["exit_code"]
    )
    return {
        "id": "cc-validate-REACH-1",
        "gate": "gate-tests-coverage command-center / validate.py",
        "claim": "a dangling dependency must fire REACH-1",
        "mutation": "R-1.dependencies=['R-999']",
        "ci_argv_flags": CI_VALIDATE_ARGV,
        "arming_flag": None,
        "good_exit": good["exit_code"],
        "bad_exit": bad["exit_code"],
        "reverted_exit": reverted["exit_code"],
        "good_tail": good["tail"],
        "bad_tail": bad["tail"],
        "reverted_tail": reverted["tail"],
        "fired_on_bad_state": bad["exit_code"] != 0,
        "silent_on_good_state": good["exit_code"] == 0,
        "revert_restores_green": reverted["exit_code"] == 0,
        "status": status,
    }


def measure_validate_vfields() -> dict[str, Any]:
    """V-FIELDS is DISARMED under the shipped CI argv (no --require-complete)."""
    with tempfile.TemporaryDirectory(prefix="aud46-vf-") as raw:
        tmp = Path(raw)
        good_cat = {"schema_version": 1, "items": [_good_item()]}
        cat_path, graph_path, register = _write_tree(tmp / "good", good_cat)
        good = _validate(cat_path, graph_path, register, CI_VALIDATE_ARGV)
        mutant = json.loads(json.dumps(good_cat))
        mutant["items"][0]["completion_sentinel"] = ""
        b_cat, b_graph, b_reg = _write_tree(tmp / "bad", mutant)
        ci = _validate(b_cat, b_graph, b_reg, CI_VALIDATE_ARGV)
        armed = _validate(b_cat, b_graph, b_reg, [ARMING_FLAG])
        r_cat, r_graph, r_reg = _write_tree(tmp / "reverted", good_cat)
        reverted = _validate(r_cat, r_graph, r_reg, CI_VALIDATE_ARGV)
    if ci["exit_code"] == 0 and armed["exit_code"] != 0 and good["exit_code"] == 0:
        status = "DISARMED"
    else:
        status = _status(
            good=good["exit_code"], bad=ci["exit_code"], reverted=reverted["exit_code"]
        )
    return {
        "id": "cc-validate-V-FIELDS",
        "gate": "gate-tests-coverage command-center / validate.py",
        "claim": "blank completion_sentinel must fire V-FIELDS",
        "mutation": "R-1.completion_sentinel=''",
        "ci_argv_flags": CI_VALIDATE_ARGV,
        "arming_flag": ARMING_FLAG,
        "good_exit": good["exit_code"],
        "bad_exit": ci["exit_code"],
        "armed_exit": armed["exit_code"],
        "reverted_exit": reverted["exit_code"],
        "good_tail": good["tail"],
        "bad_tail": ci["tail"],
        "armed_tail": armed["tail"],
        "reverted_tail": reverted["tail"],
        "fired_on_bad_state": ci["exit_code"] != 0,
        "silent_on_good_state": good["exit_code"] == 0,
        "revert_restores_green": reverted["exit_code"] == 0,
        "status": status,
    }


def _junk_hits(paths: list[str]) -> list[str]:
    hits: list[str] = []
    for rel in paths:
        parts = rel.replace("\\", "/").split("/")
        if any(seg in BAD_DIR_SEGMENTS for seg in parts):
            hits.append(rel)
        elif parts and parts[-1] in BAD_BASENAMES:
            hits.append(rel)
    return hits


def measure_no_runtime_junk() -> dict[str, Any]:
    """Reproduce the AUD-0041 no-runtime-junk detector against a synthetic index."""
    good_paths = ["src/foo.py", "docs/prevent/venv-notes.md", "README.md"]
    bad_paths = good_paths + ["venv/lib/site.py", "pkg/__pycache__/x.pyc"]
    good_hits = _junk_hits(good_paths)
    bad_hits = _junk_hits(bad_paths)
    reverted_hits = _junk_hits(good_paths)
    good_exit = 1 if good_hits else 0
    bad_exit = 1 if bad_hits else 0
    reverted_exit = 1 if reverted_hits else 0
    status = _status(good=good_exit, bad=bad_exit, reverted=reverted_exit)
    return {
        "id": "gate-no-runtime-junk",
        "gate": "gate-no-runtime-junk",
        "claim": "tracked venv/__pycache__/node_modules segments must fail the junk gate",
        "mutation": "add venv/lib/site.py and pkg/__pycache__/x.pyc to the synthetic index",
        "ci_argv_flags": [],
        "arming_flag": None,
        "good_exit": good_exit,
        "bad_exit": bad_exit,
        "reverted_exit": reverted_exit,
        "good_hits": good_hits,
        "bad_hits": bad_hits,
        "substring_control_kept": "docs/prevent/venv-notes.md" not in bad_hits,
        "fired_on_bad_state": bad_exit != 0,
        "silent_on_good_state": good_exit == 0,
        "revert_restores_green": reverted_exit == 0,
        "status": status,
        "note": (
            "Workflow YAML is absent; detector logic reconstructed from AUD-0041 "
            "captured step (full path-segment match, not substring)."
        ),
    }


def measure_unittest_gate() -> dict[str, Any]:
    """stdlib unittest as the test-runner gate (pytest is not installed here)."""
    with tempfile.TemporaryDirectory(prefix="aud46-ut-") as raw:
        tmp = Path(raw)
        footer = "\nif __name__ == '__main__':\n    unittest.main()\n"
        good_py = (
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
            "        self.assertEqual(1+1, 2)\n" + footer
        )
        bad_py = (
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
            "        self.assertEqual(1+1, 3)\n" + footer
        )
        good_path = tmp / "test_good.py"
        bad_path = tmp / "test_bad.py"
        rev_path = tmp / "test_reverted.py"
        good_path.write_text(good_py, encoding="utf-8", newline="\n")
        bad_path.write_text(bad_py, encoding="utf-8", newline="\n")
        rev_path.write_text(good_py, encoding="utf-8", newline="\n")
        good = _run([sys.executable, str(good_path)], cwd=tmp)
        bad = _run([sys.executable, str(bad_path)], cwd=tmp)
        reverted = _run([sys.executable, str(rev_path)], cwd=tmp)
    status = _status(
        good=good["exit_code"], bad=bad["exit_code"], reverted=reverted["exit_code"]
    )
    return {
        "id": "unittest-as-test-gate",
        "gate": "gate-tests-coverage command-center / pytest (stdlib unittest stand-in)",
        "claim": "a failing test must make the test runner exit non-zero",
        "mutation": "assertEqual(1+1, 3)",
        "ci_argv_flags": ["python", "-m", "unittest"],
        "arming_flag": None,
        "good_exit": good["exit_code"],
        "bad_exit": bad["exit_code"],
        "reverted_exit": reverted["exit_code"],
        "good_tail": good["tail"],
        "bad_tail": bad["tail"],
        "reverted_tail": reverted["tail"],
        "fired_on_bad_state": bad["exit_code"] != 0,
        "silent_on_good_state": good["exit_code"] == 0,
        "revert_restores_green": reverted["exit_code"] == 0,
        "status": status,
        "note": "pytest is not installed on this worktree; unittest is the live runner.",
    }


def measure_true_negative_control() -> dict[str, Any]:
    """A command that never inspects the tree stays green on a planted defect."""
    with tempfile.TemporaryDirectory(prefix="aud46-true-") as raw:
        tmp = Path(raw)
        (tmp / "src").mkdir()
        (tmp / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
        good = _run([sys.executable, "-c", "raise SystemExit(0)"], cwd=tmp)
        (tmp / "venv").mkdir()
        (tmp / "venv" / "junk.py").write_text("SECRET=1\n", encoding="utf-8")
        bad = _run([sys.executable, "-c", "raise SystemExit(0)"], cwd=tmp)
        shutil.rmtree(tmp / "venv")
        reverted = _run([sys.executable, "-c", "raise SystemExit(0)"], cwd=tmp)
    return {
        "id": "always-zero-ignores-tree",
        "gate": "negative-control /bin/true analog",
        "claim": "a gate that never reads the tree cannot detect a planted defect",
        "mutation": "add venv/junk.py",
        "ci_argv_flags": ["python", "-c", "raise SystemExit(0)"],
        "arming_flag": None,
        "good_exit": good["exit_code"],
        "bad_exit": bad["exit_code"],
        "reverted_exit": reverted["exit_code"],
        "fired_on_bad_state": False,
        "silent_on_good_state": good["exit_code"] == 0,
        "revert_restores_green": reverted["exit_code"] == 0,
        "status": "SILENT-IN-BOTH",
    }


def inventory_from_aud41() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not AUD41.is_file():
        return [
            {
                "workflow": "(missing)",
                "job_id": "(missing)",
                "name": "(AUD-0041 inventory absent)",
                "workflow_on_disk": False,
                "status": "NOT-CHECKED",
                "reason": "AUD-0041 probe1-yaml-inventory.json is not on disk",
            }
        ]
    doc = json.loads(AUD41.read_text(encoding="utf-8"))
    for wf in doc.get("workflows") or []:
        rel = str(wf.get("file") or "")
        on_disk = (REPO / rel.replace("\\", "/")).is_file() if rel else False
        for job in wf.get("jobs") or []:
            name = job.get("name") or job.get("job_id") or "?"
            rows.append(
                {
                    "workflow": rel,
                    "job_id": job.get("job_id"),
                    "name": name,
                    "step_count": job.get("step_count"),
                    "workflow_on_disk": on_disk,
                    "status": "NOT-CHECKED" if not on_disk else "present-on-disk",
                    "reason": (
                        None
                        if on_disk
                        else "workflow YAML absent on this worktree; job not executed"
                    ),
                }
            )
    return rows


def run_report() -> dict[str, Any]:
    measured = [
        measure_validate_empty(),
        measure_validate_reach1(),
        measure_validate_vfields(),
        measure_no_runtime_junk(),
        measure_unittest_gate(),
        measure_true_negative_control(),
    ]
    inventory = inventory_from_aud41()
    fired = [m for m in measured if m["status"] == "FIRED"]
    disarmed = [m for m in measured if m["status"] == "DISARMED"]
    silent = [m for m in measured if m["status"] == "SILENT-IN-BOTH"]
    revert_ok = all(
        m.get("revert_restores_green")
        for m in measured
        if m["status"] in {"FIRED", "DISARMED"}
    )
    return {
        "aud41_inventory_present": AUD41.is_file(),
        "aud45_artifact_present": AUD45.is_file(),
        "quality_yml_present": QUALITY_YML.is_file(),
        "validate_present": VALIDATE.is_file(),
        "ruff_present": shutil.which("ruff") is not None,
        "pytest_present": shutil.which("pytest") is not None,
        "inventory": inventory,
        "inventory_jobs": len(inventory),
        "inventory_on_disk": sum(1 for r in inventory if r.get("workflow_on_disk")),
        "measured": measured,
        "n_fired": len(fired),
        "n_disarmed": len(disarmed),
        "n_silent": len(silent),
        "revert_ok": revert_ok,
        "baseline_green": all(
            m.get("silent_on_good_state") for m in measured if m["status"] != "NOT-CHECKED"
        ),
    }
