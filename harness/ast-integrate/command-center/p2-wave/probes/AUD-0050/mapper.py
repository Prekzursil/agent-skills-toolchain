#!/usr/bin/env python3
"""AUD-0050 selector model + collect-only receipts.

Probe 1 claim: map each test path to CI steps whose selector would collect it.
Probe 2 receipt: run those steps with pytest --collect-only; union of node IDs.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INVENTORY = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
CONTROL_REL = (
    "command-center/p2-wave/probes/AUD-0050/fixtures/"
    "outside-every-selector/test_deliberately_ungated.py"
)
KNOWN_GATED_REL = "tools/command-center/tests/test_validate.py"
SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}
PR_TRIGGERS = frozenset({"pull_request"})
FLAG_VALUE = {
    "-k",
    "-m",
    "-o",
    "-p",
    "-c",
    "-n",
    "--cov",
    "--cov-report",
    "--cov-fail-under",
    "--ignore",
    "--import-mode",
    "--maxfail",
    "--tb",
    "--rootdir",
    "--override-ini",
    "--basetemp",
    "--confcutdir",
    "--durations",
    "--color",
    "--code-highlight",
    "--pythonpath",
    "--doctest-glob",
    "--ignore-glob",
}
STOP_TOKENS = {
    "pip",
    "npm",
    "echo",
    "set",
    "for",
    "git",
    "bash",
    "curl",
    "ruff",
    "true",
}


def posix(rel: str) -> str:
    return rel.replace("\\", "/").strip()


def load_inventory() -> dict:
    if not INVENTORY.is_file():
        raise FileNotFoundError(INVENTORY)
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def discover_test_files() -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        base = Path(dirpath)
        try:
            rel_dir = base.relative_to(REPO).as_posix()
        except ValueError:
            continue
        if rel_dir.startswith("command-center/p2-wave/probes/") and not rel_dir.startswith(
            "command-center/p2-wave/probes/AUD-0050/fixtures/"
        ):
            continue
        for name in filenames:
            if _is_test_name(name):
                rel = (base / name).relative_to(REPO).as_posix()
                found.append(rel)
    if CONTROL_REL not in found and (REPO / CONTROL_REL).is_file():
        found.append(CONTROL_REL)
    return sorted(set(found))


def _is_test_name(name: str) -> bool:
    if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
        return True
    return name.endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js"))


def _looks_like_selector_path(tok: str) -> bool:
    if not tok or tok.startswith("-"):
        return False
    if tok in {"pytest", "python", "python3", "pip", "install"}:
        return False
    if tok.startswith("$") or tok.startswith("${"):
        return False
    if "/" in tok or tok.endswith(".py") or tok in {"tests", "platform", "hooks", "ci"}:
        return True
    return False


def _normalize_cmd(cmd: str) -> str:
    return re.sub(r"\\+\s+", " ", cmd).replace("\\", " ")


def _tokens(cmd: str) -> list[str]:
    return [t for t in _normalize_cmd(cmd).split() if t]


def _parse_pytest_args(tokens: list[str], start: int) -> tuple[list[str], list[str], list[str], int]:
    paths: list[str] = []
    ignores: list[str] = []
    cov: list[str] = []
    i = start
    while i < len(tokens):
        t = tokens[i]
        if t in STOP_TOKENS and i > start:
            break
        if t in {"python", "python3"}:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt != "-m":
                break
        if t.startswith("--ignore="):
            ignores.append(posix(t.split("=", 1)[1]))
            i += 1
            continue
        if t == "--ignore" and i + 1 < len(tokens):
            ignores.append(posix(tokens[i + 1]))
            i += 2
            continue
        if t.startswith("--cov="):
            cov.append(t.split("=", 1)[1])
            i += 1
            continue
        if t == "--cov" and i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
            cov.append(tokens[i + 1])
            i += 2
            continue
        if t in FLAG_VALUE:
            i += 2 if i + 1 < len(tokens) else 1
            continue
        if t.startswith("-"):
            i += 1
            continue
        if _looks_like_selector_path(t):
            paths.append(posix(t.strip("'\"")))
        i += 1
    return paths, ignores, cov, i


def _extract_pytest_invocations(cmd: str) -> list[dict[str, Any]]:
    tokens = _tokens(cmd)
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in {"python", "python3"} and i + 2 < len(tokens) and tokens[i + 1] == "-m" and tokens[i + 2] == "pytest":
            paths, ignores, cov, end = _parse_pytest_args(tokens, i + 3)
            out.append({"kind": "pytest", "paths": paths, "ignores": ignores, "cov": cov})
            i = end
            continue
        if t == "pytest":
            prev = tokens[i - 1] if i else ""
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            nxt_runner = (not nxt) or nxt.startswith("-") or _looks_like_selector_path(nxt)
            # `pip install pytest` / `pip install pytest pytest-cov` are packages.
            # `pip install pytest pytest tests/foo.py` — second pytest is the runner.
            if prev == "install" or (
                prev in {"pytest", "pytest-cov"} and not nxt_runner
            ):
                i += 1
                continue
            paths, ignores, cov, end = _parse_pytest_args(tokens, i + 1)
            out.append({"kind": "pytest", "paths": paths, "ignores": ignores, "cov": cov})
            i = end
            continue
        if t in {"python", "python3"} and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if nxt.endswith(".py") and ("test_" in nxt or nxt.endswith("_test.py")):
                out.append(
                    {
                        "kind": "python-script",
                        "paths": [posix(nxt)],
                        "ignores": [],
                        "cov": [],
                    }
                )
                i += 2
                continue
        i += 1
    return out


def _cd_targets(cmd: str) -> list[str]:
    found = []
    for m in re.finditer(r'\bcd\s+"([^"]+)"', cmd):
        found.append(posix(m.group(1)))
    for m in re.finditer(r"\bcd\s+'([^']+)'", cmd):
        found.append(posix(m.group(1)))
    mloop = re.search(r"for p in ([^;]+);", _normalize_cmd(cmd))
    if mloop and "tools/mcp/$p" in cmd:
        pkgs = [p for p in mloop.group(1).replace("\\", " ").split() if p and p != "do"]
        found.extend(f"tools/mcp/{p}" for p in pkgs)
    return found


def _infer_pkg_dir(name: str | None, cov: list[str]) -> str | None:
    candidates: list[str] = []
    if name:
        suffix = re.sub(r"^gate-tests-coverage\s+", "", name).strip()
        suffix = re.split(r"\s+\(", suffix)[0].strip()
        if suffix:
            slug = suffix.split()[0].strip(",")
            slug = slug.replace("_", "-")
            candidates.append(slug)
            candidates.append(f"tools/{slug}")
            candidates.append(f"tools/{slug.replace('-', '_')}")
    for pkg in cov:
        if pkg and pkg != ".":
            candidates.append(f"tools/{pkg}")
            candidates.append(pkg)
    seen: set[str] = set()
    for c in candidates:
        c = posix(c)
        if not c or c in seen:
            continue
        seen.add(c)
        if (REPO / c).is_dir():
            return c
    return None


def extract_pr_steps(inv: dict) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    workflows = inv.get("workflows") if isinstance(inv, dict) else None
    if workflows is None and isinstance(inv, dict):
        workflows = [inv]
    for wf in workflows or []:
        if not isinstance(wf, dict):
            continue
        triggers = set(wf.get("triggers") or [])
        on_pr = bool(triggers & PR_TRIGGERS)
        wf_file = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("job_id") or "")
            for st in job.get("steps") or []:
                if not isinstance(st, dict):
                    continue
                cmd = str(st.get("command") or "")
                name = st.get("name")
                if cmd.startswith("uses:"):
                    continue
                invocs = _extract_pytest_invocations(cmd)
                cds = _cd_targets(cmd)
                if not invocs and "npm test" in cmd:
                    invocs = [{"kind": "npm-test", "paths": [], "ignores": [], "cov": []}]
                if not invocs:
                    continue
                paths: list[str] = []
                ignores: list[str] = []
                cov: list[str] = []
                kinds: list[str] = []
                for inv_one in invocs:
                    kinds.append(str(inv_one["kind"]))
                    paths.extend(inv_one["paths"])
                    ignores.extend(inv_one["ignores"])
                    cov.extend(inv_one["cov"])
                cwd = cds[0] if len(cds) == 1 else None
                multi_cwd = cds if len(cds) > 1 else []
                if not paths and not multi_cwd:
                    inferred = _infer_pkg_dir(name if isinstance(name, str) else None, cov)
                    if inferred:
                        cwd = inferred
                resolved: list[str] = []
                if multi_cwd:
                    resolved.extend(p for p in multi_cwd if "$" not in p)
                elif paths:
                    for p in paths:
                        resolved.append(posix(f"{cwd}/{p}") if cwd and not p.startswith("tools/") and not p.startswith("ci/") and not p.startswith("hooks/") and not p.startswith("platform") and not p.startswith("agent") and not p.startswith("skills/") and not p.startswith("command-center/") else p)
                elif cwd:
                    resolved.append(cwd)
                sid = f"{wf_file}:{job_id}:{st.get('index')}"
                steps.append(
                    {
                        "id": sid,
                        "workflow": wf_file,
                        "job_id": job_id,
                        "step_index": st.get("index"),
                        "name": name,
                        "on_pull_request": on_pr,
                        "command": cmd,
                        "command_truncated": len(cmd) >= 600,
                        "kinds": kinds,
                        "selector_paths": resolved,
                        "ignores": ignores,
                        "cwd_inferred": bool(cwd and not paths and not multi_cwd),
                        "selector_kind": (
                            "explicit-path"
                            if paths
                            else ("cd-loop" if multi_cwd else ("cwd-inferred" if cwd else "undeclared-cwd"))
                        ),
                    }
                )
    return steps


def _ignored(file_rel: str, ignores: list[str]) -> bool:
    f = posix(file_rel)
    for ig in ignores:
        igp = posix(ig).rstrip("/")
        if not igp:
            continue
        if f == igp or f.startswith(igp + "/"):
            return True
    return False


def _matches_selector(file_rel: str, selector: str) -> bool:
    f = posix(file_rel)
    s = posix(selector).rstrip("/")
    if not s:
        return False
    if f == s:
        return True
    if f.startswith(s + "/"):
        return True
    return False


def classify_files(files: list[str], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pr_steps = [s for s in steps if s.get("on_pull_request")]
    rows = []
    for f in files:
        gates = []
        for s in pr_steps:
            if s.get("selector_kind") == "undeclared-cwd":
                continue
            if _ignored(f, s.get("ignores") or []):
                continue
            if any(_matches_selector(f, p) for p in s.get("selector_paths") or []):
                gates.append(
                    {
                        "step_id": s["id"],
                        "name": s.get("name"),
                        "workflow": s.get("workflow"),
                        "job_id": s.get("job_id"),
                        "selector_kind": s.get("selector_kind"),
                    }
                )
        rows.append(
            {
                "path": f,
                "classification": "GATED" if gates else "ORPHAN",
                "gates": gates,
            }
        )
    return rows


def vacuous_orphan_list(_files: list[str]) -> list[str]:
    """Known-broken: treat every file as gated. Empty orphans hide the control."""
    return []


def collect_step(step: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    paths = [p for p in (step.get("selector_paths") or []) if (REPO / p).exists()]
    ignores = list(step.get("ignores") or [])
    if step.get("selector_kind") == "undeclared-cwd":
        return {
            "step_id": step["id"],
            "status": "cwd-undeclared",
            "paths_requested": step.get("selector_paths") or [],
            "paths_present": [],
            "nodeids": [],
            "exit_code": None,
        }
    if not paths:
        return {
            "step_id": step["id"],
            "status": "path-absent",
            "paths_requested": step.get("selector_paths") or [],
            "paths_present": [],
            "nodeids": [],
            "exit_code": None,
        }
    cmd = [
        "python3",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "--import-mode=importlib",
    ]
    for ig in ignores:
        cmd.extend(["--ignore", ig])
    cmd.extend(paths)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        nodeids = [
            ln.strip()
            for ln in text.splitlines()
            if "::" in ln and not ln.strip().startswith("=")
        ]
        return {
            "step_id": step["id"],
            "status": "collected" if proc.returncode in {0, 1, 2, 5} else "collect-error",
            "paths_requested": step.get("selector_paths") or [],
            "paths_present": paths,
            "nodeids": nodeids,
            "exit_code": proc.returncode,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "step_id": step["id"],
            "status": "timeout",
            "paths_requested": step.get("selector_paths") or [],
            "paths_present": paths,
            "nodeids": [],
            "exit_code": 124,
        }
    except OSError as exc:
        return {
            "step_id": step["id"],
            "status": f"oserror:{type(exc).__name__}",
            "paths_requested": step.get("selector_paths") or [],
            "paths_present": paths,
            "nodeids": [],
            "exit_code": 127,
        }


def nodeid_file(nodeid: str) -> str:
    return posix(nodeid.split("::", 1)[0])


def collect_union(receipts: list[dict[str, Any]]) -> list[str]:
    files: set[str] = set()
    for rec in receipts:
        for nid in rec.get("nodeids") or []:
            files.add(nodeid_file(nid))
    return sorted(files)


def collect_control_file_directly() -> bool:
    """Broken receipt: collect the planted file itself. Must NOT be how CI is modeled."""
    rec = collect_step(
        {
            "id": "control-broken-direct",
            "selector_paths": [CONTROL_REL],
            "ignores": [],
            "selector_kind": "explicit-path",
        }
    )
    files = collect_union([rec])
    return CONTROL_REL in files


def compute(include_collection: bool) -> dict[str, Any]:
    inv = load_inventory()
    files = discover_test_files()
    steps = extract_pr_steps(inv)
    pr_steps = [s for s in steps if s.get("on_pull_request")]
    rows = classify_files(files, steps)
    orphans = [r["path"] for r in rows if r["classification"] == "ORPHAN"]
    gated = [r["path"] for r in rows if r["classification"] == "GATED"]
    vacuous = vacuous_orphan_list(files)
    receipts: list[dict[str, Any]] = []
    union: list[str] = []
    if include_collection:
        for s in pr_steps:
            if not s.get("selector_paths") and s.get("selector_kind") == "undeclared-cwd":
                receipts.append(collect_step(s))
                continue
            if s.get("kinds") == ["npm-test"]:
                receipts.append(
                    {
                        "step_id": s["id"],
                        "status": "not-pytest",
                        "paths_requested": [],
                        "paths_present": [],
                        "nodeids": [],
                        "exit_code": None,
                    }
                )
                continue
            receipts.append(collect_step(s))
        union = collect_union(receipts)
    control_in_orphans = CONTROL_REL in orphans
    known_gated_ok = KNOWN_GATED_REL in gated and KNOWN_GATED_REL not in orphans
    collected_gated_miss = []
    collected_orphan_hit = []
    if include_collection:
        gated_set = set(gated)
        orphan_set = set(orphans)
        union_set = set(union)
        for p in gated:
            if (REPO / p).is_file() and p not in union_set:
                # Only a miss if some present selector claimed it.
                collected_gated_miss.append(p)
        for p in union:
            if p in orphan_set:
                collected_orphan_hit.append(p)
        # Collection of a gated file can miss when the selector path is absent
        # on this worktree; keep only misses whose selector path exists.
        present_claimed = set()
        for rec in receipts:
            if rec.get("status") == "collected":
                present_claimed.update(rec.get("paths_present") or [])
        collected_gated_miss = [
            p
            for p in collected_gated_miss
            if any(_matches_selector(p, root) and (REPO / root).exists() for root in present_claimed)
        ]
        _ = gated_set
    return {
        "test_files": files,
        "n_test_files": len(files),
        "n_pr_collectable_steps": len(pr_steps),
        "steps": [
            {
                "id": s["id"],
                "name": s.get("name"),
                "workflow": s.get("workflow"),
                "job_id": s.get("job_id"),
                "on_pull_request": s.get("on_pull_request"),
                "selector_kind": s.get("selector_kind"),
                "selector_paths": s.get("selector_paths"),
                "ignores": s.get("ignores"),
                "cwd_inferred": s.get("cwd_inferred"),
                "command_truncated": s.get("command_truncated"),
            }
            for s in pr_steps
        ],
        "gate_map": rows,
        "orphan_list": orphans,
        "gated_list": gated,
        "n_orphan": len(orphans),
        "n_gated": len(gated),
        "control": {
            "fixture": CONTROL_REL,
            "fixture_in_orphan_list": control_in_orphans,
            "known_gated": KNOWN_GATED_REL,
            "known_gated_classified_gated": known_gated_ok,
            "vacuous_orphan_list": vacuous,
            "vacuous_hides_fixture": CONTROL_REL not in vacuous,
        },
        "collection_receipts": receipts,
        "collection_union_files": union,
        "collection_gated_miss": collected_gated_miss,
        "collection_orphan_hit": collected_orphan_hit,
        "github_workflows_on_disk": (REPO / ".github/workflows").is_dir(),
        "inventory_path": INVENTORY.relative_to(REPO).as_posix(),
    }


def summary_sets(doc_or_live: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    orphans = tuple(doc_or_live.get("orphan_list") or [])
    gated = tuple(doc_or_live.get("gated_list") or [])
    union = tuple(doc_or_live.get("collection_union_files") or [])
    return orphans, gated, union
