#!/usr/bin/env python3
"""Negative-control census for registered test suites (TST-0327).

For each suite, resolve every declared negative control (or mutation) to an
on-disk executable artifact and a results-ledger run id, or mark it
unresolved. Coverage is only the third count: a control that has been
observed to FAIL. A declared-but-never-run control is equivalent to no
control for coverage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"
LIVE_LEDGER_CANDIDATES = (
    REPO / "command-center" / "results-ledger.json",
    REPO / "command-center" / "bench" / "results" / "ledger.json",
    REPO / "command-center" / "bench" / "RESULTS-LEDGER.json",
)
FIXTURE_REGISTRY = HERE / "fixtures" / "registry.json"
FIXTURE_LEDGER = HERE / "fixtures" / "ledger.json"

NO_DECLARED = "no_declared_control"
PATH_MISSING = "path_missing"
NEVER_OBSERVED = "never_observed"
NEVER_FAILED = "never_failed"
OBSERVED_FAILING = "observed_failing"

FAIL_OUTCOMES = frozenset({"FAIL", "FAILED", "FIRE", "FIRED", "ERROR"})
PASS_OUTCOMES = frozenset({"PASS", "PASSED", "OK", "SILENT", "SUCCESS"})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def declarations_of(suite: dict) -> list[dict]:
    """Pull declared negative controls / mutations from a suite record."""
    out: list[dict] = []
    raw: list[Any] = []
    for key in ("negative_control", "negative_controls", "mutation", "mutations"):
        if key in suite and suite[key] not in (None, "", []):
            raw.extend(_as_list(suite[key]))
    for i, item in enumerate(raw):
        if isinstance(item, str):
            path = item.strip()
            if not path:
                continue
            out.append({"id": f"{suite.get('id') or 'suite'}-nc-{i}", "path": path})
            continue
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("artifact") or "").strip()
        cid = str(item.get("id") or item.get("control_id") or "").strip()
        if not path and not cid:
            continue
        if not cid:
            cid = f"{suite.get('id') or 'suite'}-nc-{i}"
        rec = {"id": cid, "path": path}
        if item.get("invocation"):
            rec["invocation"] = str(item["invocation"])
        out.append(rec)
    return out


def resolve_artifact(repo: Path, declared_path: str) -> dict:
    """Resolve a declared path to a file inside repo, or mark missing."""
    if not declared_path:
        return {
            "declared_path": declared_path,
            "resolved_path": None,
            "present": False,
            "reason": "empty-path",
        }
    raw = declared_path.replace("\\", "/")
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
            repo_res = repo.resolve()
            resolved.relative_to(repo_res)
        except (OSError, ValueError):
            return {
                "declared_path": declared_path,
                "resolved_path": None,
                "present": False,
                "reason": "outside-repo-or-missing",
            }
    else:
        resolved = (repo / raw).resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError:
            return {
                "declared_path": declared_path,
                "resolved_path": None,
                "present": False,
                "reason": "path-escape",
            }
    if not resolved.is_file() or resolved.stat().st_size < 0:
        return {
            "declared_path": declared_path,
            "resolved_path": None,
            "present": False,
            "reason": "missing-file",
        }
    rel = resolved.relative_to(repo.resolve()).as_posix()
    return {
        "declared_path": declared_path,
        "resolved_path": rel,
        "present": True,
        "reason": "ok",
        "bytes": resolved.stat().st_size,
    }


def _runs(ledger: dict) -> list[dict]:
    if not isinstance(ledger, dict):
        return []
    for key in ("runs", "history", "observations", "results"):
        rows = ledger.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def observations_for(
    ledger: dict, *, suite_id: str, control_id: str, control_path: str
) -> list[dict]:
    hits = []
    for row in _runs(ledger):
        sid = str(row.get("suite_id") or row.get("suite") or "")
        cid = str(row.get("control_id") or row.get("id") or "")
        cpath = str(row.get("control_path") or row.get("path") or "").replace("\\", "/")
        want_path = (control_path or "").replace("\\", "/")
        suite_ok = sid == suite_id or sid == ""
        id_ok = bool(control_id) and cid == control_id
        path_ok = bool(want_path) and cpath == want_path
        if not suite_ok:
            continue
        if not (id_ok or path_ok):
            continue
        hits.append(row)
    return hits


def _outcome(row: dict) -> str:
    return str(row.get("outcome") or row.get("result") or row.get("status") or "").upper()


def classify_declaration(
    suite: dict, decl: dict, ledger: dict, repo: Path
) -> dict:
    suite_id = str(suite.get("id") or suite.get("path") or "")
    art = resolve_artifact(repo, str(decl.get("path") or ""))
    obs = observations_for(
        ledger,
        suite_id=suite_id,
        control_id=str(decl.get("id") or ""),
        control_path=str(art.get("resolved_path") or decl.get("path") or ""),
    )
    fail_rows = [r for r in obs if _outcome(r) in FAIL_OUTCOMES]
    pass_rows = [r for r in obs if _outcome(r) in PASS_OUTCOMES]
    run_id = None
    if fail_rows:
        run_id = str(fail_rows[0].get("run_id") or fail_rows[0].get("id") or "")
    elif obs:
        run_id = str(obs[0].get("run_id") or obs[0].get("id") or "") or None

    if not art["present"]:
        status = PATH_MISSING
    elif not obs or not run_id:
        status = NEVER_OBSERVED
    elif not fail_rows:
        status = NEVER_FAILED
    else:
        status = OBSERVED_FAILING

    fully_resolved = bool(art["present"] and run_id)
    return {
        "suite_id": suite_id,
        "control_id": decl.get("id"),
        "declared_path": decl.get("path"),
        "resolved_path": art.get("resolved_path"),
        "path_present": bool(art["present"]),
        "path_reason": art.get("reason"),
        "run_id": run_id or None,
        "fully_resolved": fully_resolved,
        "unresolved": not fully_resolved,
        "observation_count": len(obs),
        "fail_count": len(fail_rows),
        "pass_count": len(pass_rows),
        "status": status,
        "counts_as_covered": status == OBSERVED_FAILING,
    }


def classify_suite(suite: dict, ledger: dict, repo: Path) -> dict:
    suite_id = str(suite.get("id") or suite.get("path") or "")
    decls = declarations_of(suite)
    if not decls:
        return {
            "suite_id": suite_id,
            "suite_path": suite.get("path"),
            "declared": False,
            "declarations": [],
            "bucket": NO_DECLARED,
            "counts_as_covered": False,
            "unresolved_flags": [],
            "covered_controls": [],
        }
    rows = [classify_declaration(suite, d, ledger, repo) for d in decls]
    covered = [r for r in rows if r["counts_as_covered"]]
    unresolved = [r for r in rows if r["unresolved"]]
    if covered:
        bucket = OBSERVED_FAILING
    else:
        # Declared but never observed failing (missing path, never run, or only PASS).
        bucket = "declared_never_failed"
    return {
        "suite_id": suite_id,
        "suite_path": suite.get("path"),
        "declared": True,
        "declarations": rows,
        "bucket": bucket,
        "counts_as_covered": bucket == OBSERVED_FAILING,
        "unresolved_flags": unresolved,
        "covered_controls": covered,
        "planted_path_missing": any(r["status"] == PATH_MISSING for r in rows),
    }


def three_counts(rows: list[dict]) -> dict:
    no_decl = sum(1 for r in rows if r["bucket"] == NO_DECLARED)
    never_fail = sum(1 for r in rows if r["bucket"] == "declared_never_failed")
    failing = sum(1 for r in rows if r["bucket"] == OBSERVED_FAILING)
    return {
        "no_declared_control": no_decl,
        "declared_never_failed": never_fail,
        "observed_failing": failing,
        "covered": failing,
        "n_suites": len(rows),
        "sum_equals_n": (no_decl + never_fail + failing) == len(rows),
    }


def census(*, registry: dict, ledger: dict, repo: Path | None = None) -> dict:
    root = repo or REPO
    suites = [s for s in (registry.get("suites") or []) if isinstance(s, dict)]
    rows = [classify_suite(s, ledger, root) for s in suites]
    counts = three_counts(rows)
    return {
        "rows": rows,
        "counts": counts,
        "only_observed_failing_counts_as_covered": True,
        "registry_suite_ids": [r["suite_id"] for r in rows],
    }


def census_from_paths(
    registry_path: Path, ledger_path: Path, repo: Path | None = None
) -> dict:
    root = repo or REPO
    registry = load_json(registry_path) if registry_path.is_file() else {"suites": []}
    ledger = load_json(ledger_path) if ledger_path.is_file() else {"runs": []}
    report = census(registry=registry, ledger=ledger, repo=root)
    report["registry_path"] = str(registry_path)
    report["ledger_path"] = str(ledger_path)
    report["registry_present"] = registry_path.is_file()
    report["ledger_present"] = ledger_path.is_file()
    return report


def fixture_census(repo: Path | None = None) -> dict:
    return census_from_paths(FIXTURE_REGISTRY, FIXTURE_LEDGER, repo or REPO)


def find_live_ledger() -> Path | None:
    for path in LIVE_LEDGER_CANDIDATES:
        if path.is_file():
            return path
    return None


def live_registry_census(repo: Path | None = None) -> dict:
    root = repo or REPO
    ledger_path = find_live_ledger()
    present = LIVE_REGISTRY.is_file()
    if not present:
        return {
            "registry_path": "command-center/TEST-REGISTRY.json",
            "registry_present": False,
            "ledger_path": None if ledger_path is None else ledger_path.as_posix(),
            "ledger_present": ledger_path is not None,
            "rows": [],
            "counts": {
                "no_declared_control": 0,
                "declared_never_failed": 0,
                "observed_failing": 0,
                "covered": 0,
                "n_suites": 0,
                "sum_equals_n": True,
            },
            "note": "command-center/TEST-REGISTRY.json is absent on this worktree",
        }
    ledger = load_json(ledger_path) if ledger_path and ledger_path.is_file() else {"runs": []}
    report = census(registry=load_json(LIVE_REGISTRY), ledger=ledger, repo=root)
    report["registry_path"] = "command-center/TEST-REGISTRY.json"
    report["registry_present"] = True
    report["ledger_path"] = None if ledger_path is None else str(ledger_path)
    report["ledger_present"] = ledger_path is not None
    if ledger_path is None:
        report["note"] = (
            "results ledger absent; declared controls cannot be observed-failing"
        )
    return report


def live_receipt_controls(repo: Path | None = None) -> dict:
    """Advisory overlay: receipts that declare negative_controls.

    Not mixed into TEST-REGISTRY three-counts. A receipt claiming
    fired_on_bad_state is an observation, not a registered-suite census row.
    """
    root = repo or REPO
    receipts = root / "command-center" / "receipts"
    rows = []
    if receipts.is_dir():
        for path in sorted(receipts.glob("*.json")):
            try:
                doc = load_json(path)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            controls = doc.get("negative_controls")
            if not isinstance(controls, list) or not controls:
                continue
            fired = [
                c
                for c in controls
                if isinstance(c, dict) and c.get("fired_on_bad_state") is True
            ]
            rows.append(
                {
                    "unit_id": doc.get("unit_id") or path.stem,
                    "path": path.relative_to(root).as_posix(),
                    "declared_n": len([c for c in controls if isinstance(c, dict)]),
                    "fired_on_bad_n": len(fired),
                }
            )
    return {
        "population": "receipts-with-negative_controls",
        "n_receipts_with_declaration": len(rows),
        "n_with_fired_on_bad": sum(1 for r in rows if r["fired_on_bad_n"] > 0),
        "rows": rows,
        "mixed_into_suite_counts": False,
    }


def every_declaration_resolved_or_unresolved(report: dict) -> bool:
    for suite in report.get("rows") or []:
        for decl in suite.get("declarations") or []:
            ok = bool(decl.get("fully_resolved")) or bool(decl.get("unresolved"))
            if not ok:
                return False
            if decl.get("fully_resolved"):
                if not decl.get("resolved_path") or not decl.get("run_id"):
                    return False
            else:
                if decl.get("resolved_path") and decl.get("run_id"):
                    return False
    return True
