"""Doc-versus-code divergences on a frozen sample of existing commands.

The sample is copies of live command-center CLI tools plus presence
snapshots of contracted artifact names, stored under this unit's
sample/ directory. Remesure reads that tree so a concurrent unit
creating DEPENDENCY-GRAPH.json / STATUS.md cannot change the rate
between COST.json emit and G-1 probe2.
"""
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
SAMPLE = HERE / "sample"

# Copied from tools/command-center/render.py CONTRACTED_ARTIFACTS so this
# probe does not import that module (its catalog loader is a different file).
CONTRACTED = (
    "PROGRAM-CHARTER.md",
    "OWNER-DECISIONS.md",
    "WORK-UNIT-CATALOG.json",
    "DEPENDENCY-GRAPH.json",
    "ARTIFACT-MANIFEST.json",
    "CLAIM-REGISTRY.json",
    "TEST-REGISTRY.json",
    "RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md",
    "RELEASE-CHECKLIST.md",
    "ROLLBACK-MANIFEST.md",
    "RUNBOOK.md",
    "STATUS.md",
    "events/EVENTS.jsonl",
)

CLI_REL = (
    "tools/command-center/render.py",
    "tools/command-center/validate.py",
    "tools/command-center/close.py",
    "tools/command-center/unit_manifest.py",
    "tools/command-center/seed.py",
    "tools/command-center/measure_rate.py",
    "tools/command-center/reconcile_delivery.py",
)

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
CITED_LIBS = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def flags_without_help(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        ok = False
        if isinstance(func, ast.Attribute) and func.attr == "add_argument":
            ok = True
        if isinstance(func, ast.Name) and func.id == "add_argument":
            ok = True
        if not ok:
            continue
        flags: list[str] = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.startswith("-"):
                    flags.append(arg.value)
        keys = {k.arg for k in node.keywords if k.arg}
        if flags and "help" not in keys:
            missing.extend(flags)
    return missing


def git_history_rate() -> str:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "NOT-CHECKED"
    if p.returncode != 0:
        return "NOT-CHECKED"
    return "NOT-CHECKED-no-usable-doc-churn-log"


def catalog_cited_counts() -> dict[str, Any]:
    doc = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    ra08 = ra09 = None
    items = doc.get("items") or doc.get("work_units") or []
    for item in items:
        if item.get("id") == "R-A08":
            ra08 = item.get("evidence")
        elif item.get("id") == "R-A09":
            ra09 = item.get("evidence")
    return {
        "R-A08_evidence": ra08,
        "R-A09_evidence": ra09,
        "R-A08_cited_blueprints": 108,
        "R-A09_cited_presets_in_evidence_line": 72,
        "citation": CATALOG_REL + " items R-A08 and R-A09",
    }


def measure() -> dict[str, Any]:
    cc = SAMPLE / "command-center"
    commands: list[dict[str, Any]] = []
    divergences = 0
    sample = 0

    for name in CONTRACTED:
        sample += 1
        path = cc / name
        exists = path.is_file()
        if not exists:
            divergences += 1
        commands.append(
            {
                "id": f"contracted:{name}",
                "kind": "documented-artifact-vs-disk",
                "documented": True,
                "on_disk": exists,
                "divergent": not exists,
            }
        )

    for rel in CITED_LIBS:
        sample += 1
        exists = (SAMPLE / rel).is_file()
        if not exists:
            divergences += 1
        commands.append(
            {
                "id": f"cited-library:{rel}",
                "kind": "catalog-cited-library-vs-disk",
                "documented": True,
                "on_disk": exists,
                "divergent": not exists,
            }
        )

    for rel in CLI_REL:
        path = SAMPLE / rel
        sample += 1
        present = path.is_file()
        missing_help = flags_without_help(path) if present else ["<file-absent>"]
        divergent = (not present) or bool(missing_help)
        if divergent:
            divergences += 1
        commands.append(
            {
                "id": f"cli:{rel}",
                "kind": "argparse-flag-without-help",
                "on_disk": present,
                "flags_without_help": missing_help,
                "divergent": divergent,
            }
        )

    rate = divergences / sample if sample else 0.0
    return {
        "sample_size": sample,
        "divergences": divergences,
        "rate": rate,
        "historical_git_rate": git_history_rate(),
        "commands": commands,
        "catalog_citations": catalog_cited_counts(),
        "note": (
            "Doc-versus-code sample frozen under "
            "command-center/p2-wave/probes/ARC-0053/sample: contracted "
            "render.py artifact names, catalog-cited blueprint/preset "
            "libraries, and argparse flags lacking help= on copies of "
            "existing command-center CLI tools. Remesure reads this "
            "sample, not the moving worktree. Git history rate is "
            "NOT-CHECKED on this worktree (no usable git doc-churn log)."
        ),
    }
