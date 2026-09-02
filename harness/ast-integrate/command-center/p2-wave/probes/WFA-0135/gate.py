"""Quality-tier evidence gate: claimed tier -> on-disk test + run resolution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from library import BLUEPRINT_SCHEMA, FLAGSHIP_FLOOR

# Markers the foundry evidence block cites. Do not rename without emit.py.
DEMOTE_MARKER = "DEMOTE_WHEN_TEST_MISSING"
UNPROVEN_MARKER = "UNPROVEN_WHEN_PATH_WITHOUT_RUN"

MIN_DOC_CHARS = 80


def rel_to(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def first_line_with(path: Path, needle: str) -> int | None:
    if not path.is_file():
        return None
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return None


def load_library(estate: Path) -> list[dict[str, Any]]:
    doc = json.loads((estate / "library.json").read_text(encoding="utf-8"))
    rows = doc.get("blueprints") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise ValueError("library.json missing blueprints")
    return rows


def load_runs(estate: Path) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    runs = estate / "runs"
    if not runs.is_dir():
        return index
    for path in sorted(runs.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rec, dict):
            continue
        key = (str(rec.get("blueprint_id") or ""), str(rec.get("kind") or ""))
        rec["_receipt_path"] = path
        index[key] = rec
    return index


def schema_valid(bp: dict[str, Any]) -> tuple[bool, str]:
    try:
        jsonschema.validate(bp, BLUEPRINT_SCHEMA)
        return True, ""
    except jsonschema.ValidationError as exc:
        return False, exc.message


def remainder_bits(estate: Path, bp: dict[str, Any], runs: dict) -> dict[str, Any]:
    bid = bp["id"]
    bp_file = estate / "blueprints" / f"{bid}.json"
    doc_file = estate / "docs" / f"{bid}.md"
    smoke_file = estate / "tests" / "smoke" / f"{bid}.py"
    executable = False
    on_disk: dict[str, Any] | None = None
    if bp_file.is_file():
        try:
            loaded = json.loads(bp_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                on_disk = loaded
                executable = bool(on_disk.get("stages")) and on_disk.get("id") == bid
        except (OSError, json.JSONDecodeError):
            executable = False
    valid, why = schema_valid(on_disk if on_disk is not None else bp)
    documented = False
    if doc_file.is_file():
        text = doc_file.read_text(encoding="utf-8")
        documented = len(text) >= MIN_DOC_CHARS and bid in text
    smoke_run = runs.get((bid, "smoke"))
    smoke_ok = (
        smoke_file.is_file()
        and isinstance(smoke_run, dict)
        and smoke_run.get("exit_code") == 0
        and bool(smoke_run.get("run_id"))
    )
    return {
        "executable": executable,
        "schema_valid": valid,
        "schema_error": why,
        "documented": documented,
        "smoke_test_present": smoke_file.is_file(),
        "smoke_tested": smoke_ok,
        "smoke_run_id": (smoke_run or {}).get("run_id"),
        "blueprint_path": bp_file.as_posix() if bp_file.is_file() else None,
        "doc_path": doc_file.as_posix() if doc_file.is_file() else None,
        "smoke_test_path": smoke_file.as_posix() if smoke_file.is_file() else None,
    }


def resolve_row(estate: Path, bp: dict[str, Any], runs: dict, repo: Path | None = None) -> dict[str, Any]:
    bid = bp["id"]
    claimed = bp["claimed_tier"]
    rem = remainder_bits(estate, bp, runs)
    e2e_path = estate / "tests" / "e2e" / f"{bid}.py"
    e2e_run = runs.get((bid, "e2e"))
    test_line = first_line_with(e2e_path, "FLAGSHIP_E2E_ANCHOR")
    e2e_cite = None
    if e2e_path.is_file() and test_line:
        path_s = rel_to(repo, e2e_path) if repo else e2e_path.as_posix()
        e2e_cite = {"path": path_s, "line": test_line, "symbol": "test_end_to_end"}

    reasons: list[str] = []
    run_id = None
    run_receipt = None
    outcome = "FAIL"
    resolved = "unresolved"

    if claimed == "flagship":
        test_exists = e2e_path.is_file()
        run_ok = (
            isinstance(e2e_run, dict)
            and e2e_run.get("exit_code") == 0
            and bool(e2e_run.get("run_id"))
        )
        if test_exists and run_ok and e2e_cite:
            outcome = "PROVEN"
            resolved = "flagship"
            run_id = e2e_run["run_id"]
            rp = e2e_run.get("_receipt_path")
            run_receipt = rel_to(repo, rp) if repo and isinstance(rp, Path) else (
                rp.as_posix() if isinstance(rp, Path) else None
            )
        elif test_exists and not run_ok:
            # UNPROVEN_WHEN_PATH_WITHOUT_RUN
            outcome = "UNPROVEN"
            resolved = "unproven"
            reasons.append("path-without-run")
        elif not test_exists:
            # DEMOTE_WHEN_TEST_MISSING
            outcome = "DEMOTE"
            resolved = "not-flagship"
            reasons.append("flagship-test-missing")
            if not run_ok:
                reasons.append("resolves-to-nothing")
        else:
            outcome = "UNPROVEN"
            resolved = "unproven"
            reasons.append("e2e-anchor-missing")
    else:
        needed = (
            rem["executable"],
            rem["schema_valid"],
            rem["documented"],
            rem["smoke_tested"],
        )
        if all(needed):
            outcome = "PROVEN"
            resolved = "remainder"
            run_id = rem.get("smoke_run_id")
        elif rem["smoke_test_present"] and not rem["smoke_tested"]:
            outcome = "UNPROVEN"
            resolved = "unproven"
            reasons.append("path-without-run")
        else:
            outcome = "FAIL"
            resolved = "remainder-unmet"
            if not rem["executable"]:
                reasons.append("not-executable")
            if not rem["schema_valid"]:
                reasons.append("schema-invalid")
            if not rem["documented"]:
                reasons.append("undocumented")
            if not rem["smoke_tested"]:
                reasons.append("smoke-missing")
            if not any(
                [
                    rem["executable"],
                    rem["schema_valid"],
                    rem["documented"],
                    rem["smoke_test_present"],
                    bool(rem.get("smoke_run_id")),
                ]
            ):
                reasons.append("resolves-to-nothing")

    return {
        "blueprint_id": bid,
        "claimed_tier": claimed,
        "resolved_tier": resolved,
        "outcome": outcome,
        "mechanism": bp["mechanism"],
        "family": bp["family"],
        "variant": bp["variant"],
        "e2e_test": e2e_cite,
        "run_id": run_id,
        "run_receipt": run_receipt,
        "remainder_evidence": rem,
        "reasons": reasons,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    proven_flagship = sum(
        1
        for r in rows
        if r["claimed_tier"] == "flagship"
        and r["outcome"] == "PROVEN"
        and r["resolved_tier"] == "flagship"
    )
    proven_remainder = sum(
        1
        for r in rows
        if r["claimed_tier"] == "remainder" and r["outcome"] == "PROVEN"
    )
    unproven = sum(1 for r in rows if r["outcome"] == "UNPROVEN")
    demoted = sum(1 for r in rows if r["outcome"] == "DEMOTE")
    failed = sum(1 for r in rows if r["outcome"] == "FAIL")
    nothing = [r["blueprint_id"] for r in rows if "resolves-to-nothing" in r["reasons"]]
    claimed_flagship = sum(1 for r in rows if r["claimed_tier"] == "flagship")
    claimed_remainder = sum(1 for r in rows if r["claimed_tier"] == "remainder")
    return {
        "blueprints": len(rows),
        "claimed_flagship": claimed_flagship,
        "proven_flagship": proven_flagship,
        "claimed_remainder": claimed_remainder,
        "proven_remainder": proven_remainder,
        "unproven": unproven,
        "demoted": demoted,
        "failed": failed,
        "claims_resolving_to_nothing": len(nothing),
        "flagship_floor_met": proven_flagship >= FLAGSHIP_FLOOR,
        "nothing_ids": nothing,
    }


def gate(estate: Path, repo: Path | None = None) -> dict[str, Any]:
    library = load_library(estate)
    runs = load_runs(estate)
    rows = [resolve_row(estate, bp, runs, repo=repo) for bp in library]
    counts = summarize(rows)
    nothing = counts.pop("nothing_ids")
    return {
        "rows": rows,
        "counts": counts,
        "claims_resolving_to_nothing": nothing,
    }
