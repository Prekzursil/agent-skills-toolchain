#!/usr/bin/env python3
"""AUD-0042 shared inventory, pytest-summary parser, and step runner."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0042"
OUT_REL = "command-center/audit/AUD-0042-close-baseline-ci-gap.json"
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
INV_REL = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
API_REL = "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
RUNS = HERE / "runs"
RAW = RUNS / "raw"
STEPS_JSON = RUNS / "steps.json"
SENTINEL = (
    "SUCCESS:AUD-0042 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Run the 32 of 60 CI-declared test steps that the Phase-0 baseline never "
    "executed, and record each outcome verbatim so the baseline covers 60 of 60 "
    "rather than 28 of 60."
)
ISOLATION_NAME = "vendored-tree import isolation (shared interpreter stays clean)"
LOCAL_GAP = [
    ("tools/agentspec/tests", "worktree-never-ci agentspec"),
    ("tools/agentrail/tests", "worktree-never-ci agentrail"),
    ("tools/detectors/tests", "worktree-never-ci detectors"),
    ("tools/council/tests", "worktree-never-ci council"),
    ("tools/completion/tests", "worktree-never-ci completion"),
    ("tools/artifact_boundary/tests", "worktree-never-ci artifact_boundary"),
    ("tools/checkout_quarantine/tests", "worktree-never-ci checkout_quarantine"),
    ("tools/fuzz_triage/tests", "worktree-never-ci fuzz_triage"),
    ("tools/selfimprove/tests", "worktree-never-ci selfimprove"),
    ("tools/bench/tests", "worktree-never-ci bench"),
]
PATH_TOKEN = re.compile(r"(?:^|[\s\\'\"])((?:[\w.-]+/){1,}[\w.-]+)")
COLLECTED_RE = re.compile(r"(?m)^(?:.*? )?(\d+) tests collected\b|collected (\d+) item")
NO_TESTS_RE = re.compile(r"no tests ran", re.I)
NOT_FOUND_RE = re.compile(r"file or directory not found", re.I)
PASSED_RE = re.compile(r"\b(\d+) passed\b")
FAILED_RE = re.compile(r"\b(\d+) failed\b")
ERROR_RE = re.compile(r"\b(\d+) error(?:s|ed)?\b")
SKIPPED_RE = re.compile(r"\b(\d+) skipped\b")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "sha256": sha,
        "bytes": size,
    }


def load_python_test_steps() -> list[dict]:
    inv = json.loads((REPO / INV_REL).read_text(encoding="utf-8"))
    rows: list[dict] = []
    for wf in inv.get("workflows") or []:
        for job in wf.get("jobs") or []:
            if job.get("job_id") != "test-python":
                continue
            for s in job.get("steps") or []:
                if s.get("index") in (0, 1, 60):
                    continue
                cmd = s.get("command") or ""
                if cmd.startswith("uses:"):
                    continue
                rows.append(
                    {
                        "index": int(s["index"]),
                        "name": s.get("name") or f"unnamed-{s['index']}",
                        "command": cmd,
                        "shell": s.get("shell"),
                    }
                )
    if len(rows) != 60:
        raise SystemExit(f"FAILED:{UNIT} expected 60 CI test steps, got {len(rows)}")
    return rows


def split_28_32(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    return rows[:28], rows[28:]


def extract_paths(command: str) -> list[str]:
    found: list[str] = []
    for m in PATH_TOKEN.finditer(command):
        tok = m.group(1).rstrip("\\").strip()
        if tok.startswith("$") or tok.startswith("http"):
            continue
        if tok not in found:
            found.append(tok)
    return found


def parse_summary(text: str) -> dict:
    """Parse pytest (or isolation-check) output. Exit 0 + collected 0 is never test-success."""
    collected = 0
    m = COLLECTED_RE.search(text or "")
    if m:
        collected = int(m.group(1) or m.group(2) or 0)
    passed = int(PASSED_RE.search(text or "").group(1)) if PASSED_RE.search(text or "") else 0
    failed = int(FAILED_RE.search(text or "").group(1)) if FAILED_RE.search(text or "") else 0
    errored = int(ERROR_RE.search(text or "").group(1)) if ERROR_RE.search(text or "") else 0
    skipped = int(SKIPPED_RE.search(text or "").group(1)) if SKIPPED_RE.search(text or "") else 0
    not_found = bool(NOT_FOUND_RE.search(text or ""))
    no_tests = bool(NO_TESTS_RE.search(text or ""))
    if not_found or no_tests:
        collected = 0
    elif collected == 0 and (passed or failed or errored or skipped):
        # pytest -q omits the "collected N items" line; the tally is the collection.
        collected = passed + failed + errored + skipped
    counted_as_test_success = collected > 0 and failed == 0 and errored == 0
    return {
        "collected": collected,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "skipped": skipped,
        "not_found": not_found,
        "no_tests_ran": no_tests,
        "counted_as_test_success": counted_as_test_success,
    }


def run_cmd(argv: list[str], timeout: int = 45, cwd: Path | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    try:
        p = subprocess.run(
            argv,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(argv)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"


def isolation_argv() -> list[str]:
    script = (
        "import importlib.util, sys\n"
        "GENERIC = ('index', 'engines', 'evaluation')\n"
        "leaked = []\n"
        "for name in GENERIC:\n"
        "    spec = importlib.util.find_spec(name)\n"
        "    if spec is not None:\n"
        "        leaked.append(f'{name} -> {spec.origin}')\n"
        "if leaked:\n"
        "    print('Vendored generic top-level modules leaked into the SHARED interpreter:')\n"
        "    for entry in leaked:\n"
        "        print(f' {entry}')\n"
        "    sys.exit(1)\n"
        "print(f'OK: shared interpreter is clean of {GENERIC}.')\n"
    )
    return [sys.executable, "-c", script]


def pytest_argv(target: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]


def classify_gap(name: str, exit_code: int, summary: dict, present: list[str]) -> str:
    if name == ISOLATION_NAME:
        return "isolation-ran" if exit_code == 0 else "isolation-leaked"
    if not present:
        return "target-absent"
    if summary["not_found"] or summary["no_tests_ran"] or summary["collected"] == 0:
        return "collected-zero"
    return "tests-ran"


def run_gap_step(step: dict) -> dict:
    name = step["name"]
    command = step["command"]
    paths = extract_paths(command)
    present = [p for p in paths if (REPO / p).exists()]
    if name == ISOLATION_NAME:
        argv = isolation_argv()
        code, out = run_cmd(argv, timeout=20)
        summary = parse_summary(out)
        summary["collected"] = 0
        summary["counted_as_test_success"] = False
        classification = classify_gap(name, code, summary, present)
    elif present:
        argv = pytest_argv(present[0])
        code, out = run_cmd(argv, timeout=45)
        summary = parse_summary(out)
        classification = classify_gap(name, code, summary, present)
    else:
        target = paths[0] if paths else f"<no-path-in-command:{name}>"
        argv = pytest_argv(target) if paths else [sys.executable, "-c", "raise SystemExit(127)"]
        code, out = run_cmd(argv, timeout=20)
        summary = parse_summary(out)
        if not paths:
            summary["not_found"] = True
            summary["collected"] = 0
            summary["counted_as_test_success"] = False
            if code == 0:
                code = 127
        classification = classify_gap(name, code, summary, present)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]
    raw_rel = f"command-center/p2-wave/probes/AUD-0042/runs/raw/{step['index']:02d}-{slug}.txt"
    (REPO / raw_rel).parent.mkdir(parents=True, exist_ok=True)
    (REPO / raw_rel).write_text(out[-16000:], encoding="utf-8")
    return {
        "cohort": "catalog-gap-32",
        "index": step["index"],
        "name": name,
        "ci_command": command,
        "argv": argv,
        "extracted_paths": paths,
        "present_paths": present,
        "exit_code": code,
        "classification": classification,
        "raw_rel": raw_rel,
        **summary,
    }


def run_local_step(rel: str, name: str) -> dict:
    argv = pytest_argv(rel)
    code, out = run_cmd(argv, timeout=60)
    summary = parse_summary(out)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]
    raw_rel = f"command-center/p2-wave/probes/AUD-0042/runs/raw/local-{slug}.txt"
    (REPO / raw_rel).parent.mkdir(parents=True, exist_ok=True)
    (REPO / raw_rel).write_text(out[-16000:], encoding="utf-8")
    return {
        "cohort": "worktree-never-ci",
        "index": None,
        "name": name,
        "ci_command": f"python3 -m pytest {rel} -q",
        "argv": argv,
        "extracted_paths": [rel],
        "present_paths": [rel] if (REPO / rel).exists() else [],
        "exit_code": code,
        "classification": "tests-ran" if summary["collected"] > 0 else "collected-zero",
        "raw_rel": raw_rel,
        **summary,
    }


def execute_all() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = load_python_test_steps()
    executed, gap = split_28_32(rows)
    gap_runs = [run_gap_step(s) for s in gap]
    local_runs = [run_local_step(rel, name) for rel, name in LOCAL_GAP]
    doc = {
        "catalog_test_steps": 60,
        "phase0_claimed_executed": 28,
        "phase0_claimed_never_executed": 32,
        "executed_28_names": [s["name"] for s in executed],
        "gap_32": gap_runs,
        "worktree_never_ci": local_runs,
    }
    STEPS_JSON.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return doc


def runs_complete(doc: dict) -> bool:
    gap = doc.get("gap_32") or []
    local = doc.get("worktree_never_ci") or []
    if len(gap) != 32 or len(local) != len(LOCAL_GAP):
        return False
    for s in gap + local:
        rel = s.get("raw_rel")
        if not rel or not (REPO / rel).is_file():
            return False
        if not isinstance(s.get("exit_code"), int):
            return False
        if not isinstance(s.get("collected"), int):
            return False
    return True


def fill_missing_runs(doc: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = load_python_test_steps()
    _, gap_defs = split_28_32(rows)
    recorded_gap = list(doc.get("gap_32") or [])
    new_gap = []
    if len(recorded_gap) == 32:
        for recorded, step in zip(recorded_gap, gap_defs):
            raw = REPO / (recorded.get("raw_rel") or "")
            new_gap.append(recorded if raw.is_file() else run_gap_step(step))
    else:
        new_gap = [run_gap_step(s) for s in gap_defs]
    recorded_local = list(doc.get("worktree_never_ci") or [])
    new_local = []
    if len(recorded_local) == len(LOCAL_GAP):
        for recorded, (rel, name) in zip(recorded_local, LOCAL_GAP):
            raw = REPO / (recorded.get("raw_rel") or "")
            new_local.append(recorded if raw.is_file() else run_local_step(rel, name))
    else:
        new_local = [run_local_step(rel, name) for rel, name in LOCAL_GAP]
    out = {
        "catalog_test_steps": 60,
        "phase0_claimed_executed": 28,
        "phase0_claimed_never_executed": 32,
        "executed_28_names": doc.get("executed_28_names")
        or [s["name"] for s in split_28_32(rows)[0]],
        "gap_32": new_gap,
        "worktree_never_ci": new_local,
    }
    STEPS_JSON.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def ensure_runs() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    if STEPS_JSON.is_file():
        doc = json.loads(STEPS_JSON.read_text(encoding="utf-8"))
        if runs_complete(doc):
            return doc
        return fill_missing_runs(doc)
    return execute_all()


def load_runs() -> dict:
    return ensure_runs()
