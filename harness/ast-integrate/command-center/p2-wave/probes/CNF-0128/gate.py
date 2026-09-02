#!/usr/bin/env python3
"""Mechanical Phase 11 exit gate. Verdicts come from receipts on disk.

Empty inventory, absent registry, and missing required receipts are FAIL,
never a vacuous pass. Disclosed residuals with a named settling experiment
do not block; missing settling experiments and failed conditions do.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OWN_OUTPUT = "command-center/confirmation/CNF-0128-phase11-exit-gate.json"
CLAIMS_REL = "command-center/CLAIM-REGISTRY.json"
CONFIRM_DIR = "command-center/confirmation"

REQUIRED_RECEIPTS: tuple[tuple[str, str, str], ...] = (
    (
        "CNF-0004",
        "command-center/confirmation/CNF-0004-escalation-policy.json",
        "escalation-policy",
    ),
    (
        "CNF-0014",
        "command-center/confirmation/CNF-0014-coverage-board.json",
        "coverage-board",
    ),
    (
        "CNF-0118",
        "command-center/confirmation/CNF-0118-second-order-sample.json",
        "second-order-sample",
    ),
    (
        "CNF-0120",
        "command-center/confirmation/CNF-0120-not-checked-integrity.json",
        "not-checked-integrity",
    ),
    (
        "CNF-0124",
        "command-center/confirmation/CNF-0124-authorship-audit.json",
        "authorship-audit",
    ),
    (
        "CNF-0125",
        "command-center/confirmation/CNF-0125-stale-premise-sweep.json",
        "stale-premise-sweep",
    ),
)

REQUIRED_PATHS = {rel for _, rel, _ in REQUIRED_RECEIPTS}
ACCEPT_VERDICTS = frozenset({"CONFIRMED", "BLOCKED"})
NOT_USABLE = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def probe_fp(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("fingerprint", "sha256", "id", "digest"):
            got = value.get(key)
            if got:
                return str(got).strip()
        return ""
    return str(value or "").strip()


def two_signals(receipt: dict) -> bool:
    src = probe_fp(receipt.get("source_probe"))
    ver = probe_fp(receipt.get("verifier_probe"))
    return bool(src) and bool(ver) and src != ver


def usable_doc(doc: Any) -> bool:
    if not isinstance(doc, dict) or not doc:
        return False
    st = str(doc.get("state") or "").upper()
    return st not in NOT_USABLE


def is_p0p1(claim: dict) -> bool:
    sev = str(claim.get("severity") or claim.get("priority") or "").upper()
    return sev in {"P0", "P1"}


def load_claims(root: Path) -> dict:
    path = root / CLAIMS_REL
    rel = CLAIMS_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "state": "ABSENT",
            "present": False,
            "path": rel,
            "claims": [],
            "p0p1": [],
        }
    doc = load_json(path)
    claims: list = []
    if isinstance(doc, dict):
        raw = doc.get("claims")
        if isinstance(raw, list):
            claims = [c for c in raw if isinstance(c, dict)]
    elif isinstance(doc, list):
        claims = [c for c in doc if isinstance(c, dict)]
    p0p1 = [c for c in claims if is_p0p1(c) and c.get("id")]
    inventory = "EMPTY" if not claims else "PRESENT"
    if claims and not p0p1:
        inventory = "EMPTY-P0P1"
    return {
        "state": inventory,
        "present": True,
        "path": rel,
        "claims": claims,
        "p0p1": p0p1,
    }


def is_claim_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if not doc.get("claim_id"):
        return False
    if not doc.get("verdict"):
        return False
    if doc.get("unit_id") == "CNF-0128":
        return False
    return True


def harvest_claim_receipts(root: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    base = root / CONFIRM_DIR
    if not base.is_dir():
        return found
    for path in sorted(base.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if rel == OWN_OUTPUT or rel in REQUIRED_PATHS:
            continue
        doc = load_json(path)
        if not is_claim_receipt(doc):
            continue
        cid = str(doc["claim_id"])
        rec = dict(doc)
        rec["_path"] = rel
        found[cid] = rec
    return found


def load_required(root: Path) -> list[dict]:
    rows = []
    for uid, rel, role in REQUIRED_RECEIPTS:
        path = root / rel
        present = path.is_file() and path.stat().st_size > 0
        doc = load_json(path) if present else None
        rows.append(
            {
                "unit_id": uid,
                "path": rel,
                "role": role,
                "present": present,
                "usable": bool(present and usable_doc(doc)),
                "doc": doc if isinstance(doc, dict) else None,
            }
        )
    return rows


def row_receipt(path: str, present: bool, role: str) -> dict:
    return {"path": path, "present": present, "role": role}


def settling_for_missing(kind: str, name: str) -> str:
    return (
        f"Write {name} from the catalog contract for {kind}, then re-run "
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0128/gate.py --live and require "
        "the matching condition computed_state=PASS."
    )


def census_condition(claims: dict, receipts: dict[str, dict]) -> tuple[dict, list[dict]]:
    residuals: list[dict] = []
    backing = [
        row_receipt(CLAIMS_REL, claims["present"], "claim-inventory"),
        row_receipt(
            f"{CONFIRM_DIR}/ (claim receipts)",
            bool(receipts),
            "confirmation-receipts",
        ),
    ]
    if claims["state"] == "ABSENT":
        residuals.append(
            {
                "id": "R-ABSENT-CLAIM-REGISTRY",
                "statement": (
                    "CLAIM-REGISTRY.json is absent, so the P0/P1 census "
                    "cannot be evaluated. Absent is not empty and not zero."
                ),
                "settling_experiment": settling_for_missing(
                    "claim inventory", CLAIMS_REL
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-CENSUS",
            "title": "Every P0 and P1 claim is CONFIRMED or BLOCKED with two signals",
            "computed_state": "NOT-CHECKED",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "inventory=ABSENT (directory/file missing); 0 of 0 is not a pass",
            "p0p1_count": 0,
            "satisfied": 0,
            "unsatisfied": [],
        }
        return cond, residuals
    p0p1 = claims["p0p1"]
    if not p0p1:
        residuals.append(
            {
                "id": "R-EMPTY-P0P1-CENSUS",
                "statement": (
                    f"Claim registry state={claims['state']} with zero P0/P1 "
                    "ids. An empty census is not 'every P0/P1 confirmed'."
                ),
                "settling_experiment": (
                    "Populate CLAIM-REGISTRY.json with the program P0/P1 "
                    "claims, emit one confirmation receipt per id, then re-run "
                    "gate.py --live and require C-CENSUS PASS with p0p1_count>0."
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-CENSUS",
            "title": "Every P0 and P1 claim is CONFIRMED or BLOCKED with two signals",
            "computed_state": "FAIL",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "empty-set-read-as-pass refused: p0p1_count=0",
            "p0p1_count": 0,
            "satisfied": 0,
            "unsatisfied": [],
        }
        return cond, residuals

    unsatisfied: list[dict] = []
    satisfied = 0
    for claim in sorted(p0p1, key=lambda c: str(c.get("id"))):
        cid = str(claim["id"])
        rec = receipts.get(cid)
        if rec is None:
            unsatisfied.append({"claim_id": cid, "reason": "receipt-absent"})
            residuals.append(
                {
                    "id": f"R-MISSING-RECEIPT:{cid}",
                    "statement": (
                        f"P0/P1 claim {cid} has no confirmation receipt on disk."
                    ),
                    "settling_experiment": (
                        f"Emit command-center/confirmation/receipts/{cid}.json "
                        "with verdict CONFIRMED or BLOCKED, distinct source_probe "
                        "and verifier_probe fingerprints, then re-run gate.py --live."
                    ),
                    "blocks_exit": True,
                }
            )
            continue
        backing.append(row_receipt(rec["_path"], True, "claim-receipt"))
        verdict = str(rec.get("verdict") or "").upper()
        if verdict not in ACCEPT_VERDICTS:
            unsatisfied.append(
                {"claim_id": cid, "reason": f"verdict={verdict}"}
            )
            residuals.append(
                {
                    "id": f"R-UNSETTLED-VERDICT:{cid}",
                    "statement": (
                        f"Claim {cid} receipt verdict={verdict}; exit requires "
                        "CONFIRMED or explicitly BLOCKED."
                    ),
                    "settling_experiment": (
                        f"Re-confirm {cid} to CONFIRMED or file BLOCKED with two "
                        "signals; re-run gate.py --live and require C-CENSUS PASS."
                    ),
                    "blocks_exit": True,
                }
            )
            continue
        if not two_signals(rec):
            unsatisfied.append({"claim_id": cid, "reason": "single-signal"})
            residuals.append(
                {
                    "id": f"R-SINGLE-SIGNAL:{cid}",
                    "statement": (
                        f"Claim {cid} verdict={verdict} but source_probe and "
                        "verifier_probe are missing or identical."
                    ),
                    "settling_experiment": (
                        f"Replace {rec['_path']} so source_probe fingerprint "
                        "differs from verifier_probe, then re-run gate.py --live."
                    ),
                    "blocks_exit": True,
                }
            )
            continue
        satisfied += 1
        residual = rec.get("residual") or rec.get("residual_caveat")
        if isinstance(residual, str) and residual.strip():
            residuals.append(
                {
                    "id": f"R-DISCLOSED:{cid}",
                    "statement": residual.strip(),
                    "settling_experiment": str(
                        rec.get("settling_experiment")
                        or rec.get("residual_settling_experiment")
                        or ""
                    ).strip(),
                    "blocks_exit": False,
                    "claim_id": cid,
                }
            )
        elif isinstance(residual, dict):
            residuals.append(
                {
                    "id": str(residual.get("id") or f"R-DISCLOSED:{cid}"),
                    "statement": str(
                        residual.get("statement") or residual.get("text") or ""
                    ).strip(),
                    "settling_experiment": str(
                        residual.get("settling_experiment") or ""
                    ).strip(),
                    "blocks_exit": False,
                    "claim_id": cid,
                }
            )

    ok = not unsatisfied
    cond = {
        "id": "C-CENSUS",
        "title": "Every P0 and P1 claim is CONFIRMED or BLOCKED with two signals",
        "computed_state": "PASS" if ok else "FAIL",
        "receipts": backing,
        "blocks_exit": not ok,
        "detail": (
            f"p0p1={len(p0p1)} satisfied={satisfied} unsatisfied={len(unsatisfied)}"
        ),
        "p0p1_count": len(p0p1),
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
    }
    return cond, residuals


def error_rate_condition(required: list[dict]) -> tuple[dict, list[dict]]:
    residuals: list[dict] = []
    policy_row = next(r for r in required if r["unit_id"] == "CNF-0004")
    sample_row = next(r for r in required if r["unit_id"] == "CNF-0118")
    backing = [
        row_receipt(policy_row["path"], policy_row["present"], policy_row["role"]),
        row_receipt(sample_row["path"], sample_row["present"], sample_row["role"]),
    ]
    if not policy_row["usable"]:
        residuals.append(
            {
                "id": "R-ABSENT-ESCALATION-POLICY",
                "statement": (
                    "CNF-0004 escalation policy is absent or unusable, so the "
                    "pre-fixed discrepancy threshold cannot be read."
                ),
                "settling_experiment": settling_for_missing(
                    "CNF-0004", policy_row["path"]
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ERROR-RATE",
            "title": "Sampled error rate is below the pre-fixed threshold",
            "computed_state": "NOT-CHECKED",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "threshold receipt missing; rate not compared after the fact",
            "threshold": None,
            "error_rate": None,
            "sample_size": None,
        }
        return cond, residuals

    policy = policy_row["doc"] or {}
    threshold = policy.get("discrepancy_rate_threshold")
    if threshold is None:
        threshold = policy.get("threshold")
    try:
        threshold_f = float(threshold)
    except (TypeError, ValueError):
        threshold_f = None
    fixed = policy.get("threshold_fixed_before_confirmations")
    if fixed is False:
        residuals.append(
            {
                "id": "R-THRESHOLD-AFTER-THE-FACT",
                "statement": (
                    "CNF-0004 records the discrepancy threshold as not fixed "
                    "before confirmations; that is not a threshold."
                ),
                "settling_experiment": (
                    "Re-issue CNF-0004 with threshold_fixed_before_confirmations "
                    "true and a committed_at earlier than the first confirmation "
                    "receipt, then re-run gate.py --live."
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ERROR-RATE",
            "title": "Sampled error rate is below the pre-fixed threshold",
            "computed_state": "FAIL",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "policy-set-after-the-fact",
            "threshold": threshold_f,
            "error_rate": None,
            "sample_size": None,
        }
        return cond, residuals
    if threshold_f is None:
        residuals.append(
            {
                "id": "R-THRESHOLD-UNREADABLE",
                "statement": "CNF-0004 is present but names no numeric threshold.",
                "settling_experiment": settling_for_missing(
                    "numeric threshold in CNF-0004", policy_row["path"]
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ERROR-RATE",
            "title": "Sampled error rate is below the pre-fixed threshold",
            "computed_state": "NOT-CHECKED",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "threshold field missing",
            "threshold": None,
            "error_rate": None,
            "sample_size": None,
        }
        return cond, residuals

    if not sample_row["usable"]:
        residuals.append(
            {
                "id": "R-ABSENT-SECOND-ORDER-SAMPLE",
                "statement": (
                    "CNF-0118 second-order sample is absent or unusable, so "
                    "the confirmer error rate is not measured."
                ),
                "settling_experiment": settling_for_missing(
                    "CNF-0118", sample_row["path"]
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ERROR-RATE",
            "title": "Sampled error rate is below the pre-fixed threshold",
            "computed_state": "NOT-CHECKED",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "sample receipt missing",
            "threshold": threshold_f,
            "error_rate": None,
            "sample_size": None,
        }
        return cond, residuals

    sample = sample_row["doc"] or {}
    items = sample.get("items") if isinstance(sample.get("items"), list) else []
    n = sample.get("sample_size")
    if n is None:
        n = len(items)
    try:
        n_i = int(n)
    except (TypeError, ValueError):
        n_i = 0
    disagreements = sample.get("disagreements")
    if disagreements is None:
        disagreements = sum(
            1
            for it in items
            if isinstance(it, dict)
            and (
                it.get("disagreement") is True
                or str(it.get("disagreement_flag") or "").lower() in {"true", "1"}
            )
        )
    try:
        d_i = int(disagreements)
    except (TypeError, ValueError):
        d_i = 0
    if n_i <= 0:
        residuals.append(
            {
                "id": "R-EMPTY-SECOND-ORDER-SAMPLE",
                "statement": (
                    "CNF-0118 sample_size=0. A genuine zero error rate requires "
                    "n>0; empty is not zero."
                ),
                "settling_experiment": (
                    "Draw the seeded CNF-0118 sample with n>0, record "
                    "disagreements, then re-run gate.py --live."
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ERROR-RATE",
            "title": "Sampled error rate is below the pre-fixed threshold",
            "computed_state": "FAIL",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "empty-set-read-as-pass refused: sample_size=0",
            "threshold": threshold_f,
            "error_rate": None,
            "sample_size": 0,
        }
        return cond, residuals

    rate = d_i / n_i
    ok = rate < threshold_f
    if not ok:
        residuals.append(
            {
                "id": "R-ERROR-RATE-EXCEEDS-THRESHOLD",
                "statement": (
                    f"Sampled confirmer disagreement rate {rate:.4f} "
                    f"(disagreements={d_i}/n={n_i}) is not below threshold "
                    f"{threshold_f}."
                ),
                "settling_experiment": (
                    "Escalate the failing stratum to census confirmation per "
                    "CNF-0004, re-run CNF-0118, then re-run gate.py --live."
                ),
                "blocks_exit": True,
            }
        )
    cond = {
        "id": "C-ERROR-RATE",
        "title": "Sampled error rate is below the pre-fixed threshold",
        "computed_state": "PASS" if ok else "FAIL",
        "receipts": backing,
        "blocks_exit": not ok,
        "detail": (
            f"disagreements={d_i}/{n_i} rate={rate:.4f} threshold={threshold_f} "
            f"below={ok}"
        ),
        "threshold": threshold_f,
        "error_rate": rate,
        "sample_size": n_i,
        "disagreements": d_i,
    }
    return cond, residuals


def escalation_condition(required: list[dict]) -> tuple[dict, list[dict]]:
    residuals: list[dict] = []
    policy_row = next(r for r in required if r["unit_id"] == "CNF-0004")
    backing = [
        row_receipt(policy_row["path"], policy_row["present"], policy_row["role"])
    ]
    if not policy_row["usable"]:
        residuals.append(
            {
                "id": "R-ESCALATION-STATE-UNKNOWN",
                "statement": (
                    "Class-wide escalation state cannot be read because "
                    "CNF-0004 is absent or unusable. Unknown is treated as open."
                ),
                "settling_experiment": settling_for_missing(
                    "CNF-0004", policy_row["path"]
                ),
                "blocks_exit": True,
            }
        )
        cond = {
            "id": "C-ESCALATION",
            "title": "No class-wide escalation is still open",
            "computed_state": "NOT-CHECKED",
            "receipts": backing,
            "blocks_exit": True,
            "detail": "escalation state unknown; open-escalation blocks regardless of pass rate",
            "open_escalations": [],
        }
        return cond, residuals

    policy = policy_row["doc"] or {}
    open_esc = policy.get("open_escalations")
    if not isinstance(open_esc, list):
        open_esc = []
    flag = policy.get("class_wide_escalation_open")
    if flag is None:
        flag = bool(open_esc)
    open_bool = bool(flag) or bool(open_esc)
    if open_bool:
        residuals.append(
            {
                "id": "R-OPEN-CLASS-WIDE-ESCALATION",
                "statement": (
                    "A class-wide escalation is still open. This blocks the "
                    "Phase 11 exit gate regardless of aggregate pass rate."
                ),
                "settling_experiment": (
                    "Close or complete the census re-queue named in CNF-0004 "
                    "open_escalations, set class_wide_escalation_open=false, "
                    "then re-run gate.py --live."
                ),
                "blocks_exit": True,
            }
        )
    cond = {
        "id": "C-ESCALATION",
        "title": "No class-wide escalation is still open",
        "computed_state": "FAIL" if open_bool else "PASS",
        "receipts": backing,
        "blocks_exit": open_bool,
        "detail": (
            f"class_wide_escalation_open={open_bool} "
            f"open_count={len(open_esc)}"
        ),
        "open_escalations": open_esc,
    }
    return cond, residuals


def required_receipts_condition(required: list[dict]) -> tuple[dict, list[dict]]:
    residuals: list[dict] = []
    backing = [row_receipt(r["path"], r["present"], r["role"]) for r in required]
    missing = [r for r in required if not r["usable"]]
    for r in missing:
        residuals.append(
            {
                "id": f"R-MISSING-REQUIRED:{r['unit_id']}",
                "statement": (
                    f"Required Phase 11 receipt {r['unit_id']} at {r['path']} "
                    "is absent, empty, unparseable, or self-declared failed."
                ),
                "settling_experiment": settling_for_missing(
                    r["unit_id"], r["path"]
                ),
                "blocks_exit": True,
            }
        )
    ok = not missing
    cond = {
        "id": "C-REQUIRED-RECEIPTS",
        "title": "Every named dependency receipt is present and usable on disk",
        "computed_state": "PASS" if ok else "FAIL",
        "receipts": backing,
        "blocks_exit": not ok,
        "detail": (
            f"required={len(required)} usable={len(required) - len(missing)} "
            f"missing={[m['unit_id'] for m in missing]}"
        ),
        "missing_unit_ids": [m["unit_id"] for m in missing],
    }
    return cond, residuals


def residuals_condition(residuals: list[dict]) -> dict:
    incomplete = [
        r
        for r in residuals
        if not str(r.get("settling_experiment") or "").strip()
        or not str(r.get("statement") or "").strip()
    ]
    ok = not incomplete
    backing = [
        row_receipt(OWN_OUTPUT, False, "gate-residual-list"),
        row_receipt(
            f"{CONFIRM_DIR}/ (claim receipts residual fields)",
            True,
            "receipt-residual-fields",
        ),
    ]
    return {
        "id": "C-RESIDUALS",
        "title": "Every residual has a named settling experiment",
        "computed_state": "PASS" if ok else "FAIL",
        "receipts": backing,
        "blocks_exit": not ok,
        "detail": (
            f"residuals={len(residuals)} missing_settling={len(incomplete)} "
            "(disclosed residuals do not block; undisclosed/unsettled do)"
        ),
        "incomplete_ids": [r.get("id") for r in incomplete],
    }


def compute(root: Path) -> dict:
    """Return the mechanical gate dict (no sentinel / narrative)."""
    claims = load_claims(root)
    receipts = harvest_claim_receipts(root)
    required = load_required(root)

    residuals: list[dict] = []
    conditions: list[dict] = []

    c_census, r1 = census_condition(claims, receipts)
    conditions.append(c_census)
    residuals.extend(r1)

    c_rate, r2 = error_rate_condition(required)
    conditions.append(c_rate)
    residuals.extend(r2)

    c_esc, r3 = escalation_condition(required)
    conditions.append(c_esc)
    residuals.extend(r3)

    c_req, r4 = required_receipts_condition(required)
    conditions.append(c_req)
    residuals.extend(r4)

    # Dedup residual ids while keeping first statement.
    seen: set[str] = set()
    uniq: list[dict] = []
    for r in residuals:
        rid = str(r.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        uniq.append(r)
    residuals = uniq

    c_res = residuals_condition(residuals)
    conditions.append(c_res)
    if c_res["computed_state"] != "PASS":
        residuals.append(
            {
                "id": "R-UNSETTLED-RESIDUAL-LIST",
                "statement": (
                    "At least one residual lacks a statement or named "
                    "settling experiment (undisclosed residual)."
                ),
                "settling_experiment": (
                    "Add a concrete command, expected observation, and "
                    "discriminating outcome to every residual, then re-run "
                    "gate.py --live and require C-RESIDUALS PASS."
                ),
                "blocks_exit": True,
            }
        )
        c_res = residuals_condition(residuals)
        conditions[-1] = c_res

    blocking = [c for c in conditions if c.get("blocks_exit")]
    green = not blocking
    return {
        "gate_verdict": "GREEN" if green else "RED",
        "phase_finished": bool(green),
        "computed_from_receipts": True,
        "inventory": {
            "claims_path": CLAIMS_REL,
            "claims_state": claims["state"],
            "claims_present": claims["present"],
            "p0p1_count": len(claims["p0p1"]),
            "claim_receipt_count": len(receipts),
        },
        "conditions": conditions,
        "residuals": residuals,
        "blocking_condition_ids": [c["id"] for c in blocking],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gate.py --live | --root PATH", file=sys.stderr)
        return 2
    if sys.argv[1] == "--live":
        here = Path(__file__).resolve()
        root = here.parents[3]
    elif sys.argv[1] == "--root" and len(sys.argv) >= 3:
        root = Path(sys.argv[2]).resolve()
    else:
        print("usage: gate.py --live | --root PATH", file=sys.stderr)
        return 2
    doc = compute(root)
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 0 if doc["gate_verdict"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
