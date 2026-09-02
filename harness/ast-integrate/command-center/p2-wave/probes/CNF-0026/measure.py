#!/usr/bin/env python3
"""Live measurements for CNF-0026 (no cached narrative)."""
from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
LEFTOVER_GLOB = "command-center/p2-wave/P2-CLOUD-LEFTOVER_*.json"
UPSTREAM = ("CNF-0016", "CNF-0017", "CNF-0018", "CNF-0024")
NAMED_DOCS = (
    "07-OPTION-UNIVERSE.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
)
SNAPSHOT_RELS = (
    "command-center/BASELINE-SNAPSHOT.json",
    "command-center/BASELINE-SNAPSHOT.md",
)
RISK_REL = "command-center/RISK-REGISTER.md"
REGISTER_REL = "command-center/sources/REGISTER.md"
QUALITY_YML = ".github/workflows/quality.yml"
QUALITY_RUN_ID = 31525279780
AUD_API_REL = "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    "scw-pull",
    "ovh-monitor",
}
_CATALOG_CACHE: dict | None = None


def load_catalog() -> dict:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        _CATALOG_CACHE = json.loads(CATALOG.read_text(encoding="utf-8"))
    return _CATALOG_CACHE


def unit_by_id(uid: str) -> dict:
    for u in load_catalog().get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def leftover_ids() -> tuple[Path | None, set[str]]:
    matches = sorted((REPO / "command-center/p2-wave").glob("P2-CLOUD-LEFTOVER_*.json"))
    if not matches:
        return None, set()
    path = matches[-1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = {str(x) for x in (doc.get("remaining_ids") or [])}
    return path, ids


def rel_stat(rel: str) -> dict:
    path = REPO / rel
    return {
        "rel": rel,
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def walk_names(root: Path, needle: str) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return hits
    needle_l = needle.lower()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in dirnames + filenames:
            if needle_l in name.lower():
                p = Path(dirpath) / name
                try:
                    hits.append(str(p.relative_to(REPO)))
                except ValueError:
                    hits.append(str(p))
                if len(hits) >= 20:
                    return hits
    return hits


def phase15_direct_deps(remainder_ids: set[str]) -> list[dict]:
    hits: list[dict] = []
    for u in load_catalog().get("work_units") or []:
        if not isinstance(u, dict):
            continue
        if str(u.get("phase")) != "15":
            continue
        deps = {str(x) for x in (u.get("dependencies") or [])}
        via = sorted(deps & remainder_ids)
        if via:
            hits.append({"id": u["id"], "via": via})
    return hits


def crlf_count(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"rel": rel, "is_file": False, "crlf_count": 0, "bytes": 0}
    raw = path.read_bytes()
    return {
        "rel": rel,
        "is_file": True,
        "crlf_count": raw.count(b"\r\n"),
        "bytes": len(raw),
    }


def risk_register_recipes() -> dict:
    path = REPO / RISK_REL
    if not path.is_file():
        return {"is_file": False, "p0_hits": 0, "repro_step_hits": 0, "bytes": 0}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "is_file": True,
        "bytes": path.stat().st_size,
        "p0_hits": text.count("P0"),
        "repro_step_hits": text.lower().count("repro_steps")
        + text.lower().count("repro steps"),
    }


def snapshot_triage() -> dict:
    rel = SNAPSHOT_RELS[0]
    path = REPO / rel
    if not path.is_file():
        return {"is_file": False, "failures_triaged": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    tb = doc.get("test_baseline") or {}
    rows = []
    for item in tb.get("failures_triaged") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "suite": item.get("suite"),
                "verdict": item.get("verdict"),
                "failed": item.get("failed") or [],
                "root_cause": item.get("root_cause"),
            }
        )
    return {
        "is_file": True,
        "bytes": path.stat().st_size,
        "headline": (tb.get("HEADLINE") or "")[:400],
        "failures_triaged": rows,
        "crlf_failed": next(
            (r.get("failed") or [] for r in rows if r.get("suite") == "command-center"),
            [],
        ),
    }


def quality_api_failures() -> dict:
    path = REPO / AUD_API_REL
    if not path.is_file():
        return {"api_present": False, "failing_jobs": [], "run_id": QUALITY_RUN_ID}
    doc = json.loads(path.read_text(encoding="utf-8"))
    failing: list[str] = []
    for run in doc.get("runs") or []:
        if run.get("run_id") != QUALITY_RUN_ID:
            continue
        for job in run.get("jobs") or []:
            if job.get("conclusion") == "failure":
                failing.append(str(job.get("name") or ""))
    log_rel = f"command-center/p2-wave/probes/CNF-0024/logs/{QUALITY_RUN_ID}.log"
    return {
        "api_present": True,
        "api_rel": AUD_API_REL,
        "run_id": QUALITY_RUN_ID,
        "failing_jobs": failing,
        "log_rel": log_rel,
        "log_is_file": (REPO / log_rel).is_file(),
    }


def collect() -> dict:
    leftover_path, leftover = leftover_ids()
    self = unit_by_id("CNF-0026")
    upstream = {}
    for uid in UPSTREAM:
        u = unit_by_id(uid)
        out = str(u.get("output_path") or "")
        upstream[uid] = {
            "output_path": out,
            "output_stat": rel_stat(out) if out else None,
            "in_leftover": uid in leftover,
            "title": u.get("title"),
        }
    docker_sock = Path("/var/run/docker.sock")
    github = REPO / ".github" / "workflows"
    confirmation = REPO / "command-center" / "confirmation"
    confirmation_listing = (
        sorted(p.name for p in confirmation.iterdir()) if confirmation.is_dir() else []
    )
    named_docs = {name: rel_stat(name) for name in NAMED_DOCS}
    glob_option = walk_names(REPO, "OPTION-UNIVERSE")
    glob_arch = walk_names(REPO, "ARCHITECTURE-CANDIDATES")
    glob_baseline = walk_names(REPO / "command-center", "BASELINE")
    glob_risk = walk_names(REPO / "command-center", "RISK-REGISTER")
    remainder_ids = set(UPSTREAM) | {"CNF-0026", "CNF-0015"}
    try:
        u05 = unit_by_id("CNF-0005")
        cnf0005 = {
            "output_path": str(u05.get("output_path") or ""),
            "output_stat": rel_stat(str(u05.get("output_path") or "")),
        }
    except KeyError:
        cnf0005 = {"output_path": None, "output_stat": None}
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "which": {
            "docker": shutil.which("docker"),
            "podman": shutil.which("podman"),
            "wine": shutil.which("wine"),
            "gh": shutil.which("gh"),
        },
        "docker_sock_exists": docker_sock.exists(),
        "github_workflows_is_dir": github.is_dir(),
        "github_workflows_listing": (
            sorted(p.name for p in github.iterdir()) if github.is_dir() else []
        ),
        "snapshots": {rel: rel_stat(rel) for rel in SNAPSHOT_RELS},
        "risk_register": rel_stat(RISK_REL),
        "named_docs": named_docs,
        "glob_option_universe": glob_option,
        "glob_architecture_candidates": glob_arch,
        "glob_baseline": glob_baseline,
        "glob_risk_register": glob_risk,
        "confirmation_dir_is_dir": confirmation.is_dir(),
        "confirmation_listing": confirmation_listing,
        "leftover_path": (
            str(leftover_path.relative_to(REPO)) if leftover_path else None
        ),
        "leftover_has": {uid: uid in leftover for uid in UPSTREAM},
        "upstream": upstream,
        "catalog_sentinel": str(self.get("completion_sentinel") or ""),
        "catalog_question": str(self.get("question_or_target") or ""),
        "catalog_output_path": str(self.get("output_path") or ""),
        "catalog_schema": str(self.get("output_schema") or ""),
        "phase15_direct_deps": phase15_direct_deps(remainder_ids),
        "control_rel": (
            "command-center/p2-wave/probes/CNF-0026/fixtures/"
            "control_reproducible_crlf.txt"
        ),
        "git_dir_exists": (REPO / ".git").exists(),
        "register_md": crlf_count(REGISTER_REL),
        "quality_yml": rel_stat(QUALITY_YML),
        "risk_register_recipes": risk_register_recipes(),
        "snapshot_triage": snapshot_triage(),
        "quality_api": quality_api_failures(),
        "cnf0005": cnf0005,
    }
