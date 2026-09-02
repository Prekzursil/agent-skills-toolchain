#!/usr/bin/env python3
"""AUD-0038 TEST-REGISTRY resolver: collectible node IDs vs planted controls."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = "command-center/TEST-REGISTRY.json"
CONTROL_DIR = HERE / "fixtures" / "control"
CC_FIXTURES = REPO / "command-center/p2-wave/probes/CC-0014/fixtures"
GHOST_TEST_ID = "test_aud0038_ghost_does_not_exist"
GHOST_PATH = (
    "command-center/p2-wave/probes/AUD-0038/fixtures/control/test_ghost_absent.py"
)
SETUP_TEST_ID = "test_aud0038_collectible_setup_error"
SETUP_PATH = (
    "command-center/p2-wave/probes/AUD-0038/fixtures/control/test_setup_error.py"
)
MENTION_PATH = (
    "command-center/p2-wave/probes/AUD-0038/fixtures/control/test_mention_trap.py"
)
MENTION_TEST_ID = "test_aud0038_mention_trap_is_collectible"


def _pythonpath() -> str:
    return os.pathsep.join(
        [str(CC_FIXTURES), str(CONTROL_DIR), os.environ.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)


def run_pytest(args: list[str], timeout: int = 60) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = _pythonpath()
    cmd = [sys.executable, "-m", "pytest", "--noconftest", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    raw = ((proc.stdout or "") + (proc.stderr or "")).replace("\r\n", "\n")
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "raw": raw,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def parse_nodeids(collect_text: str) -> list[str]:
    nodeids: list[str] = []
    seen = set()
    for line in collect_text.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        token = token.replace("\\", "/")
        if "::" not in token:
            continue
        if token.startswith("=") or token.startswith("["):
            continue
        if token in seen:
            continue
        seen.add(token)
        nodeids.append(token)
    return nodeids


def load_registry() -> dict:
    path = REPO / REGISTRY
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:AUD-0038 TEST-REGISTRY.json is not an object")
    entries = [e for e in (doc.get("entries") or []) if isinstance(e, dict)]
    return {
        "path": REGISTRY,
        "schema": doc.get("schema"),
        "unit_id": doc.get("unit_id"),
        "entries": entries,
        "suites": doc.get("suites") or [],
        "bytes": path.stat().st_size,
    }


def ghost_entry() -> dict:
    return {
        "test_id": GHOST_TEST_ID,
        "path": GHOST_PATH,
        "claim_id": "CL-AUD-0038-GHOST-ABSENT",
        "unit_id": "AUD-0038",
        "status": "CONTROL-GHOST",
        "role": "nonexistent-node-control",
        "source": "planted-control",
    }


def collect_targets(reg: dict) -> list[str]:
    paths: list[str] = []
    seen = set()
    for entry in reg["entries"]:
        p = str(entry.get("path") or "").replace("\\", "/")
        if p and p not in seen:
            seen.add(p)
            paths.append(p)
    for extra in (SETUP_PATH, MENTION_PATH):
        if extra not in seen:
            paths.append(extra)
    return paths


def match_entry(entry: dict, nodeids: list[str]) -> dict:
    test_id = str(entry.get("test_id") or "")
    path = str(entry.get("path") or "").replace("\\", "/")
    matches = []
    for nid in nodeids:
        file_part, _, rest = nid.partition("::")
        file_part = file_part.replace("\\", "/")
        names = [p for p in rest.split("::") if p]
        func = names[-1] if names else ""
        path_ok = file_part == path or file_part.endswith("/" + path) or path.endswith(
            file_part
        )
        name_ok = func == test_id
        if path_ok and name_ok:
            matches.append(nid)
    present = len(matches) > 0
    return {
        "test_id": test_id,
        "path": path,
        "claim_id": entry.get("claim_id"),
        "unit_id": entry.get("unit_id"),
        "status": entry.get("status"),
        "role": entry.get("role"),
        "source": entry.get("source") or "live",
        "collectible": present,
        "matched_nodeids": matches,
        "string_match_nodeid_component": f"::{test_id}",
    }


def always_present_mutant(entries: list[dict]) -> list[dict]:
    """Broken detector: every registry row is present, collect output unused."""
    return [
        {
            "test_id": e.get("test_id"),
            "path": e.get("path"),
            "collectible": True,
            "mutant": "always-present",
        }
        for e in entries
    ]


def grep_would_false_positive() -> dict:
    mention = REPO / MENTION_PATH
    text = mention.read_text(encoding="utf-8") if mention.is_file() else ""
    return {
        "path": MENTION_PATH,
        "ghost_test_id_in_file_text": GHOST_TEST_ID in text,
        "ghost_file_exists": (REPO / GHOST_PATH).is_file(),
    }


def classify_execute(raw: str, rc: int) -> str:
    low = raw.lower()
    if rc == 0:
        return "PASSED"
    if "error" in low and ("setup" in low or "fixture" in low):
        return "SETUP-ERROR"
    if "error at setup" in low or "error during setup" in low:
        return "SETUP-ERROR"
    if rc != 0 and "error" in low and SETUP_TEST_ID in raw:
        return "SETUP-ERROR"
    if rc != 0:
        return "FAILED"
    return "UNKNOWN"


def execute_node(nodeid: str, timeout: int = 45) -> dict:
    result = run_pytest(["-q", "--tb=short", nodeid], timeout=timeout)
    outcome = classify_execute(result["raw"], result["returncode"])
    return {
        "nodeid": nodeid,
        "command": result["command"],
        "returncode": result["returncode"],
        "outcome": outcome,
        "executable_ok": outcome == "PASSED",
        "raw_tail": result["raw"][-1500:],
    }


def other_runner_registries() -> dict:
    found = []
    for rel in (
        "command-center/TEST-REGISTRY.json",
        "package.json",
        "jest.config.js",
        "vitest.config.ts",
        "phpunit.xml",
        "Cargo.toml",
        "go.mod",
    ):
        p = REPO / rel
        found.append({"path": rel, "exists": p.is_file()})
    extra = []
    cc = REPO / "command-center"
    if cc.is_dir():
        for p in sorted(cc.glob("*REGISTRY*.json")):
            extra.append(p.relative_to(REPO).as_posix())
    return {
        "known_markers": found,
        "command_center_registry_json": extra,
        "non_pytest_runner_declared_in_test_registry": False,
    }


def resolve() -> dict:
    reg = load_registry()
    live_entries = []
    for e in reg["entries"]:
        row = dict(e)
        row["source"] = "live"
        live_entries.append(row)
    ghost = ghost_entry()
    targets = collect_targets(reg)
    collect = run_pytest(["--collect-only", "-q", *targets], timeout=90)
    nodeids = parse_nodeids(collect["raw"])
    live_resolved = [match_entry(e, nodeids) for e in live_entries]
    ghost_resolved = match_entry(ghost, nodeids)
    setup_resolved = match_entry(
        {
            "test_id": SETUP_TEST_ID,
            "path": SETUP_PATH,
            "source": "planted-control",
            "status": "CONTROL-SETUP-ERROR",
            "role": "collectible-not-executable",
        },
        nodeids,
    )
    mention_resolved = match_entry(
        {
            "test_id": MENTION_TEST_ID,
            "path": MENTION_PATH,
            "source": "planted-control",
            "status": "CONTROL-MENTION-TRAP",
            "role": "mention-only-ghost-name",
        },
        nodeids,
    )
    ghost_collect = run_pytest(["--collect-only", "-q", GHOST_PATH], timeout=30)
    grep = grep_would_false_positive()
    mutant = always_present_mutant(live_entries + [ghost])
    mutant_ghost_present = any(
        m.get("test_id") == GHOST_TEST_ID and m.get("collectible") for m in mutant
    )
    live_missing = [r for r in live_resolved if not r["collectible"]]
    live_matched = [r for r in live_resolved if r["collectible"]]
    return {
        "registry": {
            "path": REGISTRY,
            "schema": reg["schema"],
            "unit_id": reg["unit_id"],
            "entry_count": len(live_entries),
            "suite_count": len(reg["suites"]),
            "bytes": reg["bytes"],
        },
        "pytest": {
            "module": "pytest",
            "version": _pytest_version(),
        },
        "collect": {
            "command": collect["command"],
            "returncode": collect["returncode"],
            "targets": targets,
            "nodeids": nodeids,
            "nodeid_count": len(nodeids),
            "raw": collect["raw"][-4000:],
            "scope": (
                "registry suite paths plus AUD-0038 planted controls; "
                "not whole-tree collect"
            ),
        },
        "live": live_resolved,
        "live_missing": live_missing,
        "live_matched": live_matched,
        "ghost": ghost_resolved,
        "ghost_collect_attempt": {
            "command": ghost_collect["command"],
            "returncode": ghost_collect["returncode"],
            "file_exists": (REPO / GHOST_PATH).is_file(),
            "raw_tail": ghost_collect["raw"][-800:],
        },
        "setup_error_control": setup_resolved,
        "mention_trap": mention_resolved,
        "grep_trap": grep,
        "always_present_mutant_counts_ghost": mutant_ghost_present,
        "other_runners": other_runner_registries(),
    }


def _pytest_version() -> str:
    try:
        import pytest

        return str(pytest.__version__)
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{type(exc).__name__}"


def stratified_execute(data: dict) -> dict:
    sample = []
    by_status: dict[str, list] = {}
    for row in data["live"]:
        st = str(row.get("status") or "UNKNOWN")
        by_status.setdefault(st, []).append(row)
    for st in ("PROTECTING", "HOLE", "UNPROVEN"):
        rows = by_status.get(st) or []
        if rows and rows[0].get("matched_nodeids"):
            sample.append(
                {
                    "stratum": st,
                    "test_id": rows[0]["test_id"],
                    "nodeid": rows[0]["matched_nodeids"][0],
                    "source": "live",
                }
            )
    if data["setup_error_control"].get("matched_nodeids"):
        sample.append(
            {
                "stratum": "CONTROL-SETUP-ERROR",
                "test_id": SETUP_TEST_ID,
                "nodeid": data["setup_error_control"]["matched_nodeids"][0],
                "source": "planted-control",
            }
        )
    runs = []
    for item in sample:
        exe = execute_node(item["nodeid"])
        exe.update(item)
        runs.append(exe)
    live_runs = [r for r in runs if r.get("source") == "live"]
    setup_runs = [r for r in runs if r.get("stratum") == "CONTROL-SETUP-ERROR"]
    return {
        "sample": sample,
        "runs": runs,
        "live_all_passed": bool(live_runs) and all(r["executable_ok"] for r in live_runs),
        "setup_error_not_counted_executable": bool(setup_runs)
        and not setup_runs[0]["executable_ok"]
        and setup_runs[0]["outcome"] == "SETUP-ERROR",
        "live_run_count": len(live_runs),
        "setup_run_count": len(setup_runs),
    }


def control_ok(data: dict, exe: dict | None = None) -> dict:
    ghost_missing = data["ghost"]["collectible"] is False
    grep = data["grep_trap"]
    mention_collectible = data["mention_trap"]["collectible"] is True
    mutant_rejected = data["always_present_mutant_counts_ghost"] is True and ghost_missing
    live_ok = len(data["live_missing"]) == 0 and len(data["live_matched"]) == len(
        data["live"]
    )
    setup_collectible = data["setup_error_control"]["collectible"] is True
    exe_ok = True
    if exe is not None:
        exe_ok = bool(exe.get("live_all_passed")) and bool(
            exe.get("setup_error_not_counted_executable")
        )
    return {
        "ghost_reported_missing": ghost_missing,
        "grep_of_mention_trap_would_false_positive": grep["ghost_test_id_in_file_text"],
        "mention_trap_collectible": mention_collectible,
        "always_present_mutant_rejected": mutant_rejected,
        "live_all_collectible": live_ok,
        "setup_error_collectible": setup_collectible,
        "execution_discriminates": exe_ok if exe is not None else None,
        "pass": ghost_missing
        and grep["ghost_test_id_in_file_text"]
        and mention_collectible
        and mutant_rejected
        and live_ok
        and setup_collectible
        and (exe_ok if exe is not None else True),
    }
