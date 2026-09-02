"""Derive owner jobs-to-be-done from live evidence on this worktree.

Evidence sources (not personas):
  1. Shipped CLI verbs in tools/command-center (command-history analogue).
  2. Catalog item dispositions and history (decision-log analogue).
  3. Named catalog rows R-A08 / R-A09 / R-M03 (workflow, preset, cockpit).

Windows corpus paths (17-DECISION-LOG.md, OWNER-DECISIONS.md, shell history)
are absent here; those absences are recorded, not filled with invented jobs.

Two enumerators (AST vs text) must produce the same job id set.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SURFACES = ("command", "cockpit", "catalog")

# Architecture decision: each observed job binds to exactly one top-level surface.
SURFACE_MAP: dict[str, str] = {
    "close-item": "command",
    "open-item": "command",
    "defer-item": "command",
    "drop-item": "command",
    "supersede-item": "command",
    "note-item": "command",
    "seed-catalog": "command",
    "render-views": "command",
    "register-artifacts": "command",
    "list-open-work": "cockpit",
    "validate-register": "cockpit",
    "reconcile-delivery": "cockpit",
    "measure-prompt-rate": "cockpit",
    "measure-unit-delivered": "cockpit",
    "one-cockpit-window": "cockpit",
    "browse-workflows": "catalog",
    "browse-presets": "catalog",
}

CLOSE_FLAG_TO_JOB = {
    "--open": "open-item",
    "--list": "list-open-work",
    "--defer": "defer-item",
    "--dropped": "drop-item",
    "--superseded-by": "supersede-item",
    "--note": "note-item",
    "--evidence": "close-item",
}

SCRIPT_TO_JOB = {
    "tools/command-center/validate.py": "validate-register",
    "tools/command-center/render.py": "render-views",
    "tools/command-center/seed.py": "seed-catalog",
    "tools/command-center/measure_rate.py": "measure-prompt-rate",
    "tools/command-center/reconcile_delivery.py": "reconcile-delivery",
    "tools/command-center/unit_manifest.py": "register-artifacts",
    "command-center/p2-wave/_measure_one_delivered.py": "measure-unit-delivered",
}

CATALOG_ITEM_TO_JOB = {
    "R-A08": "browse-workflows",
    "R-A09": "browse-presets",
    "R-M03": "one-cockpit-window",
}

MISSING_CORPUS = (
    "command-center/OWNER-DECISIONS.md",
    "17-DECISION-LOG.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/phase3/ROSTER.json",
    "command-center/phase3/RUBRIC.json",
)

FLAG_RE = re.compile(r'add_argument\(\s*["\'](--[A-Za-z0-9-]+)')
MAIN_RE = re.compile(r"^def main\b", re.M)


def load_catalog(repo: Path) -> dict[str, Any]:
    path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    return json.loads(path.read_text(encoding="utf-8"))


def item_by_id(catalog: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    for item in catalog.get("items") or []:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def catalog_stats(catalog: dict[str, Any]) -> dict[str, Any]:
    items = [i for i in (catalog.get("items") or []) if isinstance(i, dict)]
    units = [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]
    status = Counter(
        str(i.get("disposition") or i.get("status") or "OPEN") for i in items
    )
    programs = Counter(str(i.get("program") or "?") for i in items)
    prefixes = Counter(
        str(u.get("id") or "").split("-")[0] for u in units if u.get("id")
    )
    history = sum(len(i.get("history") or []) for i in items)
    return {
        "items": len(items),
        "work_units": len(units),
        "item_status": dict(status),
        "item_program": dict(programs),
        "work_unit_prefix": dict(prefixes),
        "history_events": history,
        "deferred_items": sum(1 for i in items if i.get("defer")),
    }


def corpus_presence(repo: Path) -> dict[str, bool]:
    return {rel: (repo / rel).is_file() for rel in MISSING_CORPUS}


def _ast_flags(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name != "add_argument":
            continue
        if not node.args:
            continue
        arg0 = node.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            if arg0.value.startswith("--"):
                flags.add(arg0.value)
    return flags


def _text_flags(path: Path) -> set[str]:
    return set(FLAG_RE.findall(path.read_text(encoding="utf-8")))


def _has_main_ast(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return True
    return False


def _has_main_text(path: Path) -> bool:
    return bool(MAIN_RE.search(path.read_text(encoding="utf-8")))


def _job(
    job_id: str,
    *,
    source: str,
    evidence: str,
    count: int,
    notes: str = "",
) -> dict[str, Any]:
    surface = SURFACE_MAP[job_id]
    if surface not in SURFACES:
        raise ValueError(f"illegal surface {surface} for {job_id}")
    row = {
        "id": job_id,
        "surface": surface,
        "source": source,
        "evidence": evidence,
        "count": count,
    }
    if notes:
        row["notes"] = notes
    return row


def _enumerate(repo: Path, *, ast_mode: bool) -> list[dict[str, Any]]:
    catalog = load_catalog(repo)
    stats = catalog_stats(catalog)
    jobs: list[dict[str, Any]] = []

    close_path = repo / "tools/command-center/close.py"
    if not close_path.is_file():
        raise FileNotFoundError(close_path)
    flags = _ast_flags(close_path) if ast_mode else _text_flags(close_path)
    for flag, job_id in CLOSE_FLAG_TO_JOB.items():
        if flag not in flags:
            raise AssertionError(f"close.py missing expected verb flag {flag}")
        if job_id == "close-item":
            count = int(stats["item_status"].get("DONE-VERIFIED", 0))
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"catalog items disposition=DONE-VERIFIED count={count}"
            )
        elif job_id == "open-item":
            count = int(stats["items"])
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"catalog items total={count}"
            )
        elif job_id == "list-open-work":
            count = int(stats["item_status"].get("OPEN", 0)) + int(
                stats["item_status"].get("IN-FLIGHT", 0)
            )
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"OPEN+IN-FLIGHT={count}"
            )
        elif job_id == "defer-item":
            count = int(stats["deferred_items"])
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"items with defer={count}"
            )
        elif job_id == "drop-item":
            count = int(stats["item_status"].get("DROPPED-BY-OWNER", 0))
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"DROPPED-BY-OWNER={count}"
            )
        elif job_id == "supersede-item":
            count = int(stats["item_status"].get("SUPERSEDED", 0))
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"SUPERSEDED={count}"
            )
        elif job_id == "note-item":
            count = int(stats["history_events"])
            evidence = (
                f"{close_path.relative_to(repo).as_posix()} {flag}; "
                f"catalog history events={count}"
            )
        else:
            raise AssertionError(job_id)
        jobs.append(
            _job(
                job_id,
                source="cli-close-verb",
                evidence=evidence,
                count=count,
            )
        )

    for rel, job_id in SCRIPT_TO_JOB.items():
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        ok = _has_main_ast(path) if ast_mode else _has_main_text(path)
        if not ok:
            raise AssertionError(f"{rel} has no main()")
        if job_id == "measure-unit-delivered":
            count = int(stats["work_units"])
            evidence = f"{rel} def main; work_units={count}"
        else:
            count = 1
            evidence = f"{rel} def main"
        jobs.append(
            _job(job_id, source="cli-script", evidence=evidence, count=count)
        )

    ra08 = item_by_id(catalog, "R-A08")
    ra09 = item_by_id(catalog, "R-A09")
    rm03 = item_by_id(catalog, "R-M03")
    if ra08 is None or ra09 is None or rm03 is None:
        raise AssertionError("catalog missing R-A08, R-A09, or R-M03")

    jobs.append(
        _job(
            "browse-workflows",
            source="catalog-item",
            evidence=(
                "command-center/WORK-UNIT-CATALOG.json items[id=R-A08].evidence "
                "(108 blueprints cited; library file absent on this tree)"
            ),
            count=108,
            notes=str(ra08.get("title") or "")[:160],
        )
    )
    # R-A09 disposition_evidence: 69 presets (target >=64); discovery evidence 72.
    jobs.append(
        _job(
            "browse-presets",
            source="catalog-item",
            evidence=(
                "command-center/WORK-UNIT-CATALOG.json items[id=R-A09]"
                ".disposition_evidence (69 presets; target >=64); "
                "evidence field cites 72 discovery records"
            ),
            count=69,
            notes=str(ra09.get("title") or "")[:160],
        )
    )
    jobs.append(
        _job(
            "one-cockpit-window",
            source="catalog-item",
            evidence=(
                "command-center/WORK-UNIT-CATALOG.json items[id=R-M03].title "
                "(collapse three autolaunch registrations into exactly one cockpit window)"
            ),
            count=3,
            notes=str(rm03.get("title") or "")[:160],
        )
    )

    jobs.sort(key=lambda row: row["id"])
    ids = [row["id"] for row in jobs]
    if len(ids) != len(set(ids)):
        raise AssertionError(f"duplicate job ids: {ids}")
    missing_map = [i for i in ids if i not in SURFACE_MAP]
    extra_map = [i for i in SURFACE_MAP if i not in ids]
    if missing_map or extra_map:
        raise AssertionError(
            f"SURFACE_MAP drift missing={missing_map} extra={extra_map}"
        )
    return jobs


def enumerate_author(repo: Path) -> list[dict[str, Any]]:
    """AST walk of CLI + catalog item lookup."""
    return _enumerate(repo, ast_mode=True)


def enumerate_independent(repo: Path) -> list[dict[str, Any]]:
    """Text/regex walk of the same files (mechanically different)."""
    return _enumerate(repo, ast_mode=False)


def job_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [row["id"] for row in rows]


def same_ids(
    author: list[dict[str, Any]], independent: list[dict[str, Any]]
) -> tuple[bool, str]:
    a, b = job_ids(author), job_ids(independent)
    if a != b:
        return False, f"id-order-or-set author={a} independent={b}"
    for left, right in zip(author, independent):
        if left["surface"] != right["surface"]:
            return False, f"surface {left['id']}: {left['surface']} vs {right['surface']}"
        if left["count"] != right["count"]:
            return False, f"count {left['id']}: {left['count']} vs {right['count']}"
    return True, "ok"
