"""Claim-ledger resume: intact terminal claims are skipped, truncated claims re-dispatched.

A claim record is one JSON file per work unit under ``<ledger>/claims/<unit>.json``; a unit's
receipt lives under ``<ledger>/receipts/<unit>.json``. On resume the planner reads every claim
record back from disk (never from memory) and classifies it:

* ``skip``        - the record parses and names a terminal state (SUCCESS/FAILED/BLOCKED/...)
* ``redispatch``  - the record is missing, does not parse (truncated / corrupt), or names a
                    non-terminal state; the unit is run again and its receipt rewritten

The skip-corrupt MUTANT treats any existing claim file as terminal without parsing it, so a
truncated record is silently skipped and the unit's stale receipt survives. Signal (b) is a
sha256 over the receipt directory that does not consult the plan lists at all: an honest resume
changes the truncated unit's receipt hash, the mutant leaves it untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

TERMINAL_STATES: frozenset[str] = frozenset(
    {"SUCCESS", "COMPLETED", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT"}
)
UNITS: tuple[str, ...] = ("U-0001", "U-0002", "U-0003")
TRUNCATE_UNIT = "U-0002"


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def claim_path(ledger: Path, unit: str) -> Path:
    return Path(ledger) / "claims" / f"{unit}.json"


def receipt_path(ledger: Path, unit: str) -> Path:
    return Path(ledger) / "receipts" / f"{unit}.json"


def receipt_dir_sha256(ledger: Path) -> str:
    """Independent signal: hash of every receipt's name and bytes, plan lists not consulted."""
    root = Path(ledger) / "receipts"
    h = hashlib.sha256()
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(root).as_posix().encode("utf-8"))
                h.update(b"\0")
                h.update(p.read_bytes())
                h.update(b"\0")
    return h.hexdigest()


def read_claim(path: Path) -> dict[str, Any]:
    """Classify one claim record from its bytes on disk."""
    if not path.is_file():
        return {"present": False, "parses": False, "state": None, "terminal": False, "reason": "missing"}
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "parses": False,
            "state": None,
            "terminal": False,
            "bytes": len(raw),
            "reason": f"unparseable: {type(exc).__name__}",
        }
    if not isinstance(doc, dict):
        return {"present": True, "parses": True, "state": None, "terminal": False, "bytes": len(raw), "reason": "not an object"}
    state = str(doc.get("state") or "").upper()
    terminal = state in TERMINAL_STATES
    return {
        "present": True,
        "parses": True,
        "state": state or None,
        "terminal": terminal,
        "bytes": len(raw),
        "reason": "terminal" if terminal else "non-terminal",
    }


def plan_resume(ledger: Path, units: list[str] | tuple[str, ...] = UNITS, *, skip_corrupt: bool = False) -> dict[str, Any]:
    """Honest planner (default) or the skip-corrupt mutant (``skip_corrupt=True``)."""
    skip: list[str] = []
    redispatch: list[str] = []
    rows: dict[str, Any] = {}
    for unit in units:
        path = claim_path(ledger, unit)
        if skip_corrupt:
            # Mutant: existence of the file is taken as proof of a terminal claim.
            row = {"present": path.is_file(), "parses": None, "state": None, "terminal": path.is_file(), "reason": "mutant: file exists"}
        else:
            row = read_claim(path)
        rows[unit] = row
        (skip if row["terminal"] else redispatch).append(unit)
    return {"skip": skip, "redispatch": redispatch, "claims": rows, "planner": "skip-corrupt-mutant" if skip_corrupt else "honest"}


def run_unit(ledger: Path, unit: str, attempt: int) -> None:
    """Execute a unit: write its receipt, then its terminal claim record."""
    _write(receipt_path(ledger, unit), {"unit_id": unit, "state": "SUCCESS", "attempt": attempt, "sentinel": f"SUCCESS:{unit}"})
    _write(claim_path(ledger, unit), {"unit_id": unit, "state": "SUCCESS", "attempt": attempt, "terminal": True})


def first_run(ledger: Path, units: list[str] | tuple[str, ...] = UNITS) -> None:
    for unit in units:
        run_unit(ledger, unit, attempt=1)


def truncate_claim(ledger: Path, unit: str) -> dict[str, Any]:
    """Simulate a crash mid-write: keep the first third of the claim record's bytes."""
    path = claim_path(ledger, unit)
    raw = path.read_bytes()
    kept = raw[: max(8, len(raw) // 3)]
    path.write_bytes(kept)
    return {"unit": unit, "path": str(path), "bytes_before": len(raw), "bytes_after": len(kept)}


def resume(ledger: Path, units: list[str] | tuple[str, ...] = UNITS, *, skip_corrupt: bool = False) -> dict[str, Any]:
    before = receipt_dir_sha256(ledger)
    plan = plan_resume(ledger, units, skip_corrupt=skip_corrupt)
    for unit in plan["redispatch"]:
        run_unit(ledger, unit, attempt=2)
    after = receipt_dir_sha256(ledger)
    return {"plan": plan, "receipt_dir_sha256_before": before, "receipt_dir_sha256_after": after, "receipt_dir_changed": before != after}


def run_both_states(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Intact ledger: everything skips, receipts untouched. Truncated claim: re-dispatched."""
    work = Path(work)
    intact_ledger = work / "intact"
    first_run(intact_ledger)
    intact = resume(intact_ledger)
    intact_skip = intact["plan"]["skip"] == list(UNITS) and not intact["plan"]["redispatch"]
    intact_unchanged = not intact["receipt_dir_changed"]

    corrupt_ledger = work / "corrupt"
    first_run(corrupt_ledger)
    trunc = truncate_claim(corrupt_ledger, TRUNCATE_UNIT)
    corrupt = resume(corrupt_ledger)
    others = [u for u in UNITS if u != TRUNCATE_UNIT]
    redispatch = corrupt["plan"]["redispatch"] == [TRUNCATE_UNIT] and corrupt["plan"]["skip"] == others
    independent_changed = corrupt["receipt_dir_changed"]
    repaired = read_claim(claim_path(corrupt_ledger, TRUNCATE_UNIT))["terminal"]

    passed = bool(intact_skip and intact_unchanged and redispatch and independent_changed and repaired)
    return {
        "pass": passed,
        "units": list(UNITS),
        "truncated_unit": TRUNCATE_UNIT,
        "both_states": {
            "intact_claims_skip": intact_skip,
            "intact_receipts_unchanged": intact_unchanged,
            "corrupted_claims_redispatch": redispatch,
            "corrupted_claim_repaired": repaired,
        },
        "intact": {"plan": {"skip": intact_skip, "redispatch": not intact_skip, "lists": intact["plan"]}, "path": str(intact_ledger), "independent_receipt_changed": intact["receipt_dir_changed"]},
        "corrupt": {
            "plan": {"skip": False if redispatch else True, "redispatch": redispatch, "lists": corrupt["plan"]},
            "independent_receipt_changed": independent_changed,
            "path": str(corrupt_ledger),
            "truncation": trunc,
        },
        "signals": {
            "a_plan_lists": {"intact": intact["plan"], "corrupt": corrupt["plan"]},
            "b_independent_receipt_diff": {
                "method": "sha256 over receipts/ names+bytes, plan lists not read",
                "intact": intact["receipt_dir_changed"],
                "after_truncate": independent_changed,
            },
        },
    }


def run_mutation_truncate(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Honest planner re-dispatches the truncated claim; the skip-corrupt mutant silently skips."""
    work = Path(work)
    honest_ledger = work / "honest"
    first_run(honest_ledger)
    trunc_h = truncate_claim(honest_ledger, TRUNCATE_UNIT)
    honest = resume(honest_ledger)
    honest_redispatch = TRUNCATE_UNIT in honest["plan"]["redispatch"]

    mutant_ledger = work / "mutant"
    first_run(mutant_ledger)
    trunc_m = truncate_claim(mutant_ledger, TRUNCATE_UNIT)
    mutant = resume(mutant_ledger, skip_corrupt=True)
    mutant_skip = TRUNCATE_UNIT in mutant["plan"]["skip"] and not mutant["plan"]["redispatch"]
    mutant_still_corrupt = not read_claim(claim_path(mutant_ledger, TRUNCATE_UNIT))["parses"]

    both = {
        "honest_truncate_redispatches": bool(honest_redispatch and honest["receipt_dir_changed"]),
        "mutant_silently_skips": bool(mutant_skip and not mutant["receipt_dir_changed"] and mutant_still_corrupt),
        "intact_claims_skip": all(u in honest["plan"]["skip"] for u in UNITS if u != TRUNCATE_UNIT),
        "corrupted_claims_redispatch": honest_redispatch,
    }
    return {
        "pass": bool(both["honest_truncate_redispatches"] and both["mutant_silently_skips"]),
        "mutation": "truncate",
        "truncated_unit": TRUNCATE_UNIT,
        "both_states": both,
        "honest": {"plan_redispatch": honest["plan"]["redispatch"], "plan_skip": honest["plan"]["skip"], "receipt_dir_changed": honest["receipt_dir_changed"], "truncation": trunc_h, "path": str(honest_ledger)},
        "mutant_skip_corrupt": {"plan_skip": mutant["plan"]["skip"], "plan_redispatch": mutant["plan"]["redispatch"], "receipt_dir_changed": mutant["receipt_dir_changed"], "claim_still_corrupt": mutant_still_corrupt, "truncation": trunc_m, "path": str(mutant_ledger)},
        "corrupt": {"plan": {"skip": not honest_redispatch, "redispatch": honest_redispatch, "lists": honest["plan"]}, "independent_receipt_changed": honest["receipt_dir_changed"]},
        "signals": {
            "a_plan_lists": {"honest": honest["plan"], "mutant": mutant["plan"]},
            "b_independent_receipt_diff": {
                "method": "sha256 over receipts/ names+bytes, plan lists not read",
                "honest": honest["receipt_dir_changed"],
                "mutant": mutant["receipt_dir_changed"],
            },
        },
    }
