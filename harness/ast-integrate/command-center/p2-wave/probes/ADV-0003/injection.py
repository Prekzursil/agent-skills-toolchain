#!/usr/bin/env python3
"""ADV-0003 live injection: exit-0 workers against every fan-in barrier.

Probe 1 runs mock workers through each production consider() and records
the barrier verdict plus filesystem state. Probe 2 takes an independent
os.scandir listing of the same trees so a barrier that reports the file
exists can be contradicted by the directory listing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0003"
KINDS = ("missing", "case-miss", "trailing-space", "backslash", "valid")
NEAR_MISS = ("case-miss", "trailing-space", "backslash")
EXPECTED_ARTIFACT = "output.json"
EXPECTED_RECEIPT = "receipt.json"
FANIN_DIR_REL = "tools/agentspec/agentspec/fanin"


class MutantVerdict:
    def __init__(self, ok: bool, reason: str) -> None:
        self.ok = ok
        self.reason = reason
        self.details: tuple[str, ...] = ()


def mutant_consider(
    receipt_path: Path, *, root: Path | None = None, worker_exit_code: int = 0
) -> MutantVerdict:
    """Exit-zero-is-complete mutant. Ignores the filesystem on purpose."""
    del receipt_path, root
    if worker_exit_code == 0:
        return MutantVerdict(True, "exit-zero-is-complete")
    return MutantVerdict(False, "nonzero-exit")


def mutant_claims_artifact_exists(_root: Path) -> bool:
    """Always reports the expected artifact exists. Probe 2 must contradict this."""
    return True


def _agentspec_on_path() -> None:
    root = str(REPO / "tools" / "agentspec")
    if root not in sys.path:
        sys.path.insert(0, root)


def load_barriers() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _agentspec_on_path()
    from agentspec.fanin import CONSIDER_FNS, EXPECTED_ROLES  # noqa: WPS433

    fanin_dir = REPO / FANIN_DIR_REL
    py_files = sorted(
        p for p in fanin_dir.glob("*.py") if p.name != "__init__.py" and p.is_file()
    )
    rows: list[dict[str, Any]] = []
    for fn in CONSIDER_FNS:
        mod = sys.modules[fn.__module__]
        role = str(getattr(mod, "FANIN_ROLE", "") or "")
        path = Path(getattr(mod, "__file__", "") or "")
        rel = path.relative_to(REPO).as_posix() if path.is_file() else fn.__module__
        rows.append(
            {
                "role": role,
                "module": fn.__module__,
                "path": rel,
                "fn": fn,
            }
        )
    meta = {
        "roles_expected": sorted(EXPECTED_ROLES),
        "roles_loaded": sorted(r["role"] for r in rows),
        "py_file_count": len(py_files),
        "py_files": [p.relative_to(REPO).as_posix() for p in py_files],
        "consider_count": len(rows),
    }
    return meta, rows


def spawn_worker(kind: str, root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ADV0003_KIND"] = kind
    env["ADV0003_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "workers.py")],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "kind": kind,
        "exit_code": int(proc.returncode),
        "stdout": (proc.stdout or "")[-400:],
        "stderr": (proc.stderr or "")[-400:],
    }


def scandir_listing(root: Path) -> list[dict[str, Any]]:
    """Independent directory oracle. Uses os.scandir, not the barrier."""
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    stack = [root]
    while stack:
        current = stack.pop()
        with os.scandir(current) as it:
            for ent in it:
                rel = Path(ent.path).relative_to(root).as_posix()
                is_file = ent.is_file(follow_symlinks=False)
                is_dir = ent.is_dir(follow_symlinks=False)
                rows.append(
                    {
                        "name": ent.name,
                        "repr_name": repr(ent.name),
                        "rel": rel,
                        "is_file": is_file,
                        "is_dir": is_dir,
                    }
                )
                if is_dir:
                    stack.append(Path(ent.path))
    rows.sort(key=lambda r: r["rel"])
    return rows


def expected_artifact_present(listing: list[dict[str, Any]]) -> bool:
    return any(
        r.get("name") == EXPECTED_ARTIFACT and r.get("is_file") is True for r in listing
    )


def expected_receipt_present(listing: list[dict[str, Any]]) -> bool:
    return any(
        r.get("name") == EXPECTED_RECEIPT and r.get("is_file") is True for r in listing
    )


def verdict_dict(v: Any) -> dict[str, Any]:
    details = getattr(v, "details", ()) or ()
    return {
        "ok": bool(getattr(v, "ok", False)),
        "reason": str(getattr(v, "reason", "")),
        "details": list(details),
    }


def classify_case_collision() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0003-case-") as td:
        root = Path(td)
        upper = root / "Output.json"
        lower = root / "output.json"
        upper.write_text("UPPER", encoding="utf-8")
        collided = False
        try:
            collided = lower.exists() and os.path.samefile(upper, lower)
        except OSError:
            collided = bool(lower.exists())
        distinct = False
        if not collided:
            lower.write_text("LOWER", encoding="utf-8")
            distinct = (
                upper.read_text(encoding="utf-8") == "UPPER"
                and lower.read_text(encoding="utf-8") == "LOWER"
            )
        classification = (
            "windows-style-case-collision"
            if collided
            else "distinct-paths-on-case-sensitive-fs"
        )
        return {
            "platform": sys.platform,
            "case_sensitive_filesystem": bool(distinct and not collided),
            "Output_json_collides_with_output_json": collided,
            "classification": classification,
            "silently_accepted": False,
            "note": (
                "Filesystem collapsed Output.json onto output.json. Classified "
                "as case-collision, not silently accepted as a write of the "
                "expected name."
                if collided
                else "On this Linux worktree Output.json and output.json are "
                "distinct paths. The case-miss worker is a near-miss, not a "
                "Windows collision, and is not accepted as output.json."
            ),
        }


def run_campaign() -> dict[str, Any]:
    meta, barriers = load_barriers()
    trees: dict[str, dict[str, Any]] = {}
    barrier_rows: list[dict[str, Any]] = []
    mutant_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="adv0003-camp-") as td:
        base = Path(td)
        for kind in KINDS:
            root = base / kind
            root.mkdir()
            worker = spawn_worker(kind, root)
            listing = scandir_listing(root)
            receipt = root / EXPECTED_RECEIPT
            art_present = expected_artifact_present(listing)
            rec_present = expected_receipt_present(listing)
            trees[kind] = {
                "kind": kind,
                "worker": worker,
                "listing": listing,
                "expected_artifact_present": art_present,
                "expected_receipt_present": rec_present,
                "file_reprs": [row["repr_name"] for row in listing if row["is_file"]],
            }
            for barrier in barriers:
                fn: Callable[..., Any] = barrier["fn"]
                verdict = fn(receipt, root=root)
                vd = verdict_dict(verdict)
                barrier_rows.append(
                    {
                        "kind": kind,
                        "who": "production",
                        "role": barrier["role"],
                        "module": barrier["module"],
                        "path": barrier["path"],
                        "worker_exit_code": worker["exit_code"],
                        "barrier": vd,
                        "recorded_complete": vd["ok"] is True,
                        "expected_artifact_present": art_present,
                    }
                )
            mv = verdict_dict(
                mutant_consider(
                    receipt, root=root, worker_exit_code=worker["exit_code"]
                )
            )
            mutant_rows.append(
                {
                    "kind": kind,
                    "who": "mutant-exit-zero-is-complete",
                    "worker_exit_code": worker["exit_code"],
                    "barrier": mv,
                    "recorded_complete": mv["ok"] is True,
                    "expected_artifact_present": art_present,
                    "claims_artifact_exists": mutant_claims_artifact_exists(root),
                    "scandir_contradicts_exists_claim": (
                        mutant_claims_artifact_exists(root) and not art_present
                    ),
                }
            )

        case = classify_case_collision()

        def _prod(kind: str) -> list[dict[str, Any]]:
            return [r for r in barrier_rows if r["kind"] == kind]

        missing_prod = _prod("missing")
        valid_prod = _prod("valid")
        near_prod = [r for r in barrier_rows if r["kind"] in NEAR_MISS]
        mutant_missing = next(r for r in mutant_rows if r["kind"] == "missing")
        mutant_valid = next(r for r in mutant_rows if r["kind"] == "valid")

        workers_exit_zero = all(trees[k]["worker"]["exit_code"] == 0 for k in KINDS)
        seven_barriers = (
            meta["consider_count"] == 7
            and meta["py_file_count"] == 7
            and set(meta["roles_loaded"]) == set(meta["roles_expected"])
            and len(meta["roles_loaded"]) == 7
        )
        missing_rejected = bool(missing_prod) and all(
            r["recorded_complete"] is False for r in missing_prod
        )
        near_rejected = bool(near_prod) and all(
            r["recorded_complete"] is False for r in near_prod
        )
        valid_accepted = bool(valid_prod) and all(
            r["recorded_complete"] is True for r in valid_prod
        )
        mutant_accepts_missing = mutant_missing["recorded_complete"] is True
        mutant_exists_contradicted = (
            mutant_missing["scandir_contradicts_exists_claim"] is True
        )
        missing_scandir_empty_artifact = (
            trees["missing"]["expected_artifact_present"] is False
        )
        valid_scandir_has_artifact = trees["valid"]["expected_artifact_present"] is True
        case_classified = (
            isinstance(case.get("classification"), str)
            and case.get("silently_accepted") is False
        )
        production_agrees_scandir = all(
            (
                r["recorded_complete"] is True
                and r["expected_artifact_present"] is True
            )
            if r["kind"] == "valid"
            else (
                r["recorded_complete"] is False
                and r["expected_artifact_present"] is False
            )
            for r in barrier_rows
        )

        checks = {
            "seven_production_barriers": seven_barriers,
            "workers_all_exit_zero": workers_exit_zero,
            "missing_rejected_by_production": missing_rejected,
            "near_miss_rejected_by_production": near_rejected,
            "valid_accepted_by_production": valid_accepted,
            "mutant_accepts_missing": mutant_accepts_missing,
            "mutant_exists_claim_contradicted_by_scandir": mutant_exists_contradicted,
            "missing_scandir_lacks_expected_artifact": missing_scandir_empty_artifact,
            "valid_scandir_has_expected_artifact": valid_scandir_has_artifact,
            "case_collision_classified_explicitly": case_classified,
            "production_agrees_with_scandir": production_agrees_scandir,
            "mutant_silent_on_valid": mutant_valid["recorded_complete"] is True,
        }
        passed = all(checks.values())
        inventory = {
            "roles_expected": meta["roles_expected"],
            "roles_loaded": meta["roles_loaded"],
            "py_file_count": meta["py_file_count"],
            "py_files": meta["py_files"],
            "consider_count": meta["consider_count"],
            "barriers": [
                {"role": b["role"], "module": b["module"], "path": b["path"]}
                for b in barriers
            ],
        }
        return {
            "unit_id": UNIT,
            "method_probe1": "live-mock-workers-through-each-fan-in-consider",
            "method_probe2": "os.scandir-independent-filesystem-oracle",
            "inventory": inventory,
            "trees": trees,
            "barrier_rows": barrier_rows,
            "mutant_rows": mutant_rows,
            "case_collision": case,
            "checks": checks,
            "pass": passed,
        }


if __name__ == "__main__":
    doc = run_campaign()
    print(json.dumps(doc, sort_keys=True, default=str))
    raise SystemExit(0 if doc.get("pass") else 1)
