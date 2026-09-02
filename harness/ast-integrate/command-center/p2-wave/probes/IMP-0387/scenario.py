#!/usr/bin/env python3
"""Shared IMP-0387 fixtures, both-states texts, and predicted-vs-measured census."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESOLVER_PATH = REPO / "tools" / "router" / "load_semantics.py"
INSTRUMENT_PATH = REPO / "tools" / "router" / "inspect_load.py"
FIXTURE_RULES = HERE / "fixtures" / "rules"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0387.json"
SENTINEL = "SENTINEL:IMP-0387:LOAD-SEMANTICS-RESOLVED"
UNIT = "IMP-0387"
BODY = "# shared body\nKeep this payload identical across both states.\n"

NO_FRONTMATTER = BODY
WITH_PATHS_GLOBSTAR = "---\npaths:\n  - \"**/*\"\n---\n" + BODY
WITH_OTHER_KEYS = "---\ndescription: not-the-load-switch\n---\n" + BODY

ALWAYS_ON = "ALWAYS-ON"
LAZY = "LAZY"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_resolver():
    return _load(RESOLVER_PATH, "imp0387_load_semantics")


def load_instrument():
    return _load(INSTRUMENT_PATH, "imp0387_inspect_load")


def grok_on_path() -> dict[str, Any]:
    exe = shutil.which("grok")
    return {
        "which": exe,
        "present": exe is not None,
        "note": (
            "grok inspect --json is a catalog input. It is ABSENT on this host; "
            "tools/router/inspect_load.py is the equivalent instrument."
        ),
    }


def live_roots() -> dict[str, Path]:
    return {
        "claude_rules": Path.home() / ".claude" / "rules",
        "repo_rules": REPO / "rules",
        "fixture_rules": FIXTURE_RULES,
        "capability_index": REPO / "capability-index.json",
    }


def rel_or_abs(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def both_states(resolver=None, instrument=None) -> dict[str, Any]:
    R = resolver or load_resolver()
    I = instrument or load_instrument()
    pred_off = R.resolve_load_mode(NO_FRONTMATTER)
    pred_on = R.resolve_load_mode(WITH_PATHS_GLOBSTAR)
    pred_other = R.resolve_load_mode(WITH_OTHER_KEYS)
    meas_off = I.inspect_load_mode(NO_FRONTMATTER)
    meas_on = I.inspect_load_mode(WITH_PATHS_GLOBSTAR)
    meas_other = I.inspect_load_mode(WITH_OTHER_KEYS)
    inversion = pred_off == ALWAYS_ON and pred_on == LAZY and pred_off != pred_on
    instrument_agrees = (
        meas_off == ALWAYS_ON and meas_on == LAZY and meas_other == ALWAYS_ON
    )
    return {
        "no_frontmatter": {
            "predicted": pred_off,
            "measured": meas_off,
            "want": ALWAYS_ON,
        },
        "with_paths_globstar": {
            "predicted": pred_on,
            "measured": meas_on,
            "want": LAZY,
        },
        "frontmatter_without_paths": {
            "predicted": pred_other,
            "measured": meas_other,
            "want": ALWAYS_ON,
        },
        "inversion_holds": inversion,
        "instrument_agrees": instrument_agrees,
        "other_keys_do_not_demote": pred_other == ALWAYS_ON,
        "same_answer_for_both_states": pred_off == pred_on,
    }


def census_tree(root: Path, label: str, resolver=None, instrument=None) -> dict[str, Any]:
    R = resolver or load_resolver()
    I = instrument or load_instrument()
    exists = root.is_dir()
    rows = []
    disagreements = []
    if exists:
        for path in R.iter_rule_files(root):
            text = path.read_text(encoding="utf-8")
            predicted = R.resolve_load_mode(text)
            measured = I.inspect_load_mode(text)
            rec = R.resolve_file(path)
            # tools/router/load_semantics.resolve_file stopped returning
            # has_paths_key; recompute it here with the resolver's own
            # frontmatter parser (paths key present <=> resolver says LAZY).
            has_paths_key = rec.get("has_paths_key")
            if has_paths_key is None:
                if hasattr(R, "_frontmatter"):
                    has_paths_key = "paths" in R._frontmatter(text)
                else:
                    has_paths_key = predicted == LAZY
            row = {
                "path": rel_or_abs(path),
                "label": label,
                "predicted_load_mode": predicted,
                "measured_load_mode": measured,
                "load_mode": measured if predicted != measured else predicted,
                "instrument_wins": predicted != measured,
                "agree": predicted == measured,
                "has_frontmatter": rec["has_frontmatter"],
                "has_paths_key": has_paths_key,
            }
            rows.append(row)
            if predicted != measured:
                disagreements.append(row)
    always = sum(1 for r in rows if r["load_mode"] == ALWAYS_ON)
    lazy = sum(1 for r in rows if r["load_mode"] == LAZY)
    return {
        "label": label,
        "root": str(root),
        "exists": exists,
        "n_files": len(rows),
        "n_always_on": always,
        "n_lazy": lazy,
        "n_disagree": len(disagreements),
        "rows": rows,
        "disagreements": disagreements,
    }


def inspect_via_subprocess(path: Path) -> str:
    """Measured column via a separate process (not the in-process YAML resolver)."""
    proc = subprocess.run(
        ["python3", "-B", str(INSTRUMENT_PATH), "--json", str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "inspect_load failed")
    doc = json.loads(proc.stdout)
    return str(doc["load_mode"])


def full_census(resolver=None, instrument=None) -> dict[str, Any]:
    R = resolver or load_resolver()
    I = instrument or load_instrument()
    roots = live_roots()
    trees = [
        census_tree(roots["claude_rules"], "claude_rules", R, I),
        census_tree(roots["repo_rules"], "repo_rules", R, I),
        census_tree(roots["fixture_rules"], "fixture_rules", R, I),
    ]
    extra = (
        REPO
        / "command-center"
        / "p2-wave"
        / "probes"
        / "ARC-0005"
        / "fixtures"
        / "census"
        / "repo"
        / "rules"
    )
    if extra.is_dir():
        trees.append(
            census_tree(extra, "supplemental_arc0005_census_repo_rules", R, I)
        )
    table: list[dict[str, Any]] = []
    for tree in trees:
        table.extend(tree["rows"])
    cap_idx = roots["capability_index"]
    return {
        "trees": [
            {k: v for k, v in t.items() if k not in {"rows", "disagreements"}}
            | {"disagreements": t["disagreements"]}
            for t in trees
        ],
        "table": table,
        "capability_index": {
            "path": "capability-index.json",
            "present": cap_idx.is_file(),
        },
        "n_rows": len(table),
        "n_always_on": sum(1 for r in table if r["load_mode"] == ALWAYS_ON),
        "n_lazy": sum(1 for r in table if r["load_mode"] == LAZY),
        "n_disagree": sum(1 for r in table if not r["agree"]),
        "grok": grok_on_path(),
    }


load_instrument = load_instrument
full_census = full_census
live_roots = live_roots
inspect_via_subprocess = inspect_via_subprocess
