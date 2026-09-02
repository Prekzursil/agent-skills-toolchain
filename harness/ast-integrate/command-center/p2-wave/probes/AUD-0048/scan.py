#!/usr/bin/env python3
"""Scan workflow YAML for uses: refs and permissions blocks."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from classify import classify_uses, permissions_scope

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
USES_KEY = re.compile(r"^(\s*)(?:-\s+)?uses:\s*(.+?)\s*$")
COMMENT_ONLY = re.compile(r"^\s*#")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def strip_inline_comment(value: str) -> str:
    in_s = None
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if in_s:
            out.append(ch)
            if ch == in_s and value[i - 1 : i] != "\\":
                in_s = None
        elif ch in {"'", '"'}:
            in_s = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def syntactic_uses_lines(text: str, path: str) -> list[dict[str, Any]]:
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if COMMENT_ONLY.match(line):
            continue
        m = USES_KEY.match(line)
        if not m:
            continue
        raw = strip_inline_comment(m.group(2))
        if not raw:
            continue
        rec = classify_uses(raw)
        rec.update({"file": path, "line": n, "source": "syntactic-line"})
        rows.append(rec)
    return rows


def walk_yaml_uses(obj: Any, path: str, loc: list[Any], acc: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        uses = obj.get("uses")
        if isinstance(uses, str):
            rec = classify_uses(uses)
            rec.update(
                {
                    "file": path,
                    "line": None,
                    "source": "yaml-walk",
                    "loc": ".".join(str(x) for x in loc + ["uses"]),
                }
            )
            acc.append(rec)
        for k, v in obj.items():
            walk_yaml_uses(v, path, loc + [k], acc)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_yaml_uses(v, path, loc + [i], acc)


def load_yaml(text: str) -> Any:
    return yaml.safe_load(text) or {}


def workflow_permissions(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {
            "workflow": permissions_scope(None),
            "jobs": {},
            "any_declared": False,
        }
    wf = permissions_scope(doc.get("permissions"))
    jobs_out = {}
    jobs = doc.get("jobs") or {}
    if isinstance(jobs, dict):
        for jid, job in jobs.items():
            if isinstance(job, dict):
                jobs_out[str(jid)] = permissions_scope(job.get("permissions"))
    any_declared = bool(wf["present"] or any(j["present"] for j in jobs_out.values()))
    return {"workflow": wf, "jobs": jobs_out, "any_declared": any_declared}


def scan_file(path: Path, *, origin: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    rel_path = rel(path) if path.is_absolute() or REPO in path.resolve().parents else path.as_posix()
    if path.exists():
        try:
            rel_path = rel(path)
        except Exception:
            rel_path = path.as_posix()
    syn = syntactic_uses_lines(text, rel_path)
    doc = None
    yaml_err = None
    yaml_uses: list[dict[str, Any]] = []
    try:
        doc = load_yaml(text)
        walk_yaml_uses(doc, rel_path, [], yaml_uses)
    except yaml.YAMLError as exc:
        yaml_err = str(exc)
    perms = workflow_permissions(doc if isinstance(doc, dict) else {})
    # Prefer syntactic rows (line numbers); yaml-walk is a coverage cross-check.
    syn_raw = {r["raw"] for r in syn}
    yaml_only = [r for r in yaml_uses if r["raw"] not in syn_raw]
    return {
        "file": rel_path,
        "origin": origin,
        "uses": syn,
        "yaml_only_uses": yaml_only,
        "yaml_error": yaml_err,
        "permissions": perms,
        "permissions_flagged": (not perms["any_declared"]) or perms["workflow"]["flagged"],
    }


SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "probes",
        "site-packages",
        ".tox",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "htmlcov",
        "coverage",
        "wheels",
        "_work",
        "seed-stage",
    }
)


def _is_workflow_yaml(name: str) -> bool:
    return name.lower().endswith((".yml", ".yaml"))


def iter_workflow_yaml() -> list[Path]:
    """Pruned walk: every .github/workflows/*.yml except probe/node_modules/.git trees."""
    found: list[Path] = []
    repo = REPO.resolve()
    for root, dirs, files in os.walk(repo):
        dirs[:] = [
            d
            for d in dirs
            if d not in SKIP_DIR_NAMES and (d == ".github" or not d.startswith("."))
        ]
        base = Path(root).name
        parent = Path(root).parent.name
        if base == "workflows" and parent == ".github":
            for name in files:
                if _is_workflow_yaml(name):
                    found.append(Path(root) / name)
    return sorted(found, key=lambda p: p.as_posix())


def live_workflow_files() -> list[Path]:
    """This repo's GitHub Actions identity: <repo>/.github/workflows only."""
    root = REPO / ".github" / "workflows"
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_file() and _is_workflow_yaml(p.name)
    )


def nested_workflow_files() -> list[Path]:
    """Vendored / nested workflow YAML that is not this repo's Actions identity."""
    live = {p.resolve() for p in live_workflow_files()}
    return [p for p in iter_workflow_yaml() if p.resolve() not in live]


def fixture_files() -> list[Path]:
    fx = HERE / "fixtures"
    return sorted(
        p
        for p in fx.glob("*.yml")
        if p.is_file()
    )


def harvest_uses_from_aud0041() -> list[dict[str, Any]]:
    inv = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    if not inv.is_file():
        return []
    data = json.loads(inv.read_text(encoding="utf-8"))
    rows = []
    for wf in data.get("workflows") or []:
        wf_file = wf.get("file") or ""
        for job in wf.get("jobs") or []:
            for step in job.get("steps") or []:
                cmd = str(step.get("command") or "")
                if not cmd.startswith("uses:"):
                    continue
                payload = cmd[len("uses:") :]
                raw = payload.split(" with[", 1)[0].strip()
                rec = classify_uses(raw)
                rec.update(
                    {
                        "file": wf_file,
                        "line": None,
                        "source": "harvest-AUD-0041",
                        "origin": "harvest-AUD-0041",
                        "job_id": job.get("job_id"),
                    }
                )
                rows.append(rec)
    return rows


def scan_all() -> dict[str, Any]:
    live_files = live_workflow_files()
    nested_files = nested_workflow_files()
    fx_files = fixture_files()
    live = [scan_file(p, origin="live") for p in live_files]
    nested = [scan_file(p, origin="nested") for p in nested_files]
    fixtures = [scan_file(p, origin="fixture") for p in fx_files]
    harvest = harvest_uses_from_aud0041()
    return {
        "live_files": [rel(p) for p in live_files],
        "live": live,
        "nested_files": [rel(p) for p in nested_files],
        "nested": nested,
        "fixtures": fixtures,
        "harvest_aud0041": harvest,
        "live_workflow_count": len(live_files),
        "nested_workflow_count": len(nested_files),
    }
