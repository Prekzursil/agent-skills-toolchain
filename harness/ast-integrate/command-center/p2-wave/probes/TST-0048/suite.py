#!/usr/bin/env python3
"""Conformance suite: one negative per rule, both-states control, live inventory."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from contract import RULE_IDS, RULES
from engine import RunResult, run_mutant, run_prepared
from ledger import Ledger, default_ledger


def _missing(paths: frozenset[str], after: dict[str, str]) -> list[str]:
    return sorted(p for p in paths if p not in after)


def _changed(
    paths: frozenset[str], before: dict[str, str], after: dict[str, str]
) -> list[str]:
    out: list[str] = []
    for p in sorted(paths):
        if p not in before:
            continue
        if after.get(p) != before[p]:
            out.append(p)
    return out


def _backup_mismatch(
    paths: frozenset[str], backup_sha: dict[str, str | None], after: dict[str, str]
) -> list[str]:
    bad: list[str] = []
    for p in sorted(paths):
        want = backup_sha.get(p)
        if want is None:
            continue
        if after.get(p) != want:
            bad.append(p)
    return bad


def evaluate_result(result: RunResult, ledger: Ledger | None = None) -> dict[str, Any]:
    """Return per-rule pass/fail against a live rollback result."""
    ledger = ledger or default_ledger()
    t = result.trace
    before, after, backup = result.before, result.after, result.backup_sha
    rows: list[dict[str, Any]] = []

    def add(rid: str, ok: bool, detail: str) -> None:
        rows.append({"id": rid, "pass": ok, "detail": detail})

    v_bad = _backup_mismatch(ledger.version, backup, after)
    add(
        "R1-RESTORE-VERSION",
        not v_bad,
        "ok" if not v_bad else "version mismatch: " + ",".join(v_bad),
    )
    c_bad = _backup_mismatch(ledger.config, backup, after)
    add(
        "R2-RESTORE-CONFIG",
        not c_bad,
        "ok" if not c_bad else "config mismatch: " + ",".join(c_bad),
    )
    created = set(ledger.creation.paths)
    tree_bad: list[str] = []
    for p in sorted(created):
        want = backup.get(p)
        if want is None:
            if p in after:
                tree_bad.append(p + ":still-present")
        else:
            if after.get(p) != want:
                tree_bad.append(p)
    add(
        "R3-RESTORE-DEPLOYED-TREE",
        not tree_bad,
        "ok" if not tree_bad else "deployed-tree mismatch: " + ",".join(tree_bad),
    )
    owner_miss = _missing(ledger.owner_authored, after)
    owner_chg = _changed(ledger.owner_authored, before, after)
    add(
        "R4-PRESERVE-OWNER-EDITS",
        not owner_miss and not owner_chg,
        "ok"
        if not owner_miss and not owner_chg
        else f"missing={owner_miss} changed={owner_chg}",
    )
    user_miss = _missing(ledger.user_data, after)
    user_chg = _changed(ledger.user_data, before, after)
    add(
        "R5-PRESERVE-USER-DATA",
        not user_miss and not user_chg,
        "ok"
        if not user_miss and not user_chg
        else f"missing={user_miss} changed={user_chg}",
    )
    mcp_miss = _missing(ledger.mcp, after)
    mcp_chg = _changed(ledger.mcp, before, after)
    add(
        "R6-PRESERVE-MCP-CURATION",
        not mcp_miss and not mcp_chg,
        "ok" if not mcp_miss and not mcp_chg else f"missing={mcp_miss} changed={mcp_chg}",
    )
    cred_miss = _missing(ledger.credentials, after)
    cred_chg = _changed(ledger.credentials, before, after)
    add(
        "R7-PRESERVE-CREDENTIALS",
        not cred_miss and not cred_chg,
        "ok"
        if not cred_miss and not cred_chg
        else f"missing={cred_miss} changed={cred_chg}",
    )
    add(
        "R8-PRE-CHANGE-BACKUP",
        bool(t.backup_before_first_write),
        "backup recorded before first write"
        if t.backup_before_first_write
        else "write without prior backup",
    )
    restored_need_hash = [p for p in t.restored if p not in t.verification]
    unlinked_need = [
        p
        for p in t.unlinked
        if p in created and p not in t.verification and p not in t.extra_unlinks
    ]
    add(
        "R9-PROOF-OF-RESTORE",
        not restored_need_hash and not unlinked_need and bool(t.verification),
        "ok"
        if t.verification and not restored_need_hash
        else f"missing hashes restored={restored_need_hash} unlinked={unlinked_need}",
    )
    verify_mismatch = False
    for p, want in backup.items():
        if want is None:
            continue
        got = t.verification.get(p)
        if got is not None and got != want:
            verify_mismatch = True
    add(
        "R10-COMPLETE-ONLY-AFTER-VERIFY",
        not (t.claimed_complete and verify_mismatch),
        "ok"
        if not (t.claimed_complete and verify_mismatch)
        else "complete=true despite verification mismatch",
    )
    extra = [p for p in t.unlinked if p not in created]
    extra += [p for p in t.extra_unlinks if p not in created]
    extra = sorted(set(extra))
    add(
        "R11-INVERSE-CREATION-SET",
        not extra and t.construction_used,
        "ok"
        if not extra and t.construction_used
        else f"unlinked-outside-creation={extra} construction_used={t.construction_used}",
    )
    pre_miss = _missing(ledger.preexisting, after)
    add(
        "R12-INVERSE-PREEXISTING",
        not pre_miss,
        "ok" if not pre_miss else "pre-existing removed: " + ",".join(pre_miss),
    )

    failed = [r["id"] for r in rows if not r["pass"]]
    return {
        "engine": result.engine,
        "complete": result.complete,
        "rules": rows,
        "failed": failed,
        "pass": not failed,
        "user_owned_before": sorted(p for p in ledger.preserve if p in before),
        "user_owned_after": sorted(p for p in ledger.preserve if p in after),
        "user_owned_deleted": sorted(
            p for p in ledger.preserve if p in before and p not in after
        ),
        "user_owned_changed": _changed(ledger.preserve, before, after),
    }


def inventory_proof(eval_row: dict[str, Any]) -> dict[str, Any]:
    deleted = list(eval_row.get("user_owned_deleted") or [])
    changed = list(eval_row.get("user_owned_changed") or [])
    return {
        "before": eval_row.get("user_owned_before") or [],
        "after": eval_row.get("user_owned_after") or [],
        "deleted": deleted,
        "changed": changed,
        "zero_loss": not deleted and not changed,
    }


def run_both_states(tmp_parent: Path) -> dict[str, Any]:
    good_dir = tmp_parent / "conforming"
    bad_dir = tmp_parent / "naive"
    good = run_prepared("conforming", good_dir)
    bad = run_prepared("naive", bad_dir)
    good_ev = evaluate_result(good)
    bad_ev = evaluate_result(bad)
    vacuous = bool(good_ev["pass"] and bad_ev["pass"])
    detector_ok = bool(good_ev["pass"] and not bad_ev["pass"])
    return {
        "conforming": good_ev,
        "nonconforming": bad_ev,
        "conforming_pass": good_ev["pass"],
        "nonconforming_pass": bad_ev["pass"],
        "nonconforming_fails": not bad_ev["pass"],
        "vacuous_suite": vacuous,
        "detector_ok": detector_ok,
        "naive_deleted_user_owned": bad_ev["user_owned_deleted"],
        "conforming_deleted_user_owned": good_ev["user_owned_deleted"],
        "conforming_run": good.as_dict(),
        "naive_run": bad.as_dict(),
    }


def run_negatives(tmp_parent: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rid in RULE_IDS:
        d = tmp_parent / rid.replace("/", "_")
        result = run_mutant(rid, d)
        ev = evaluate_result(result)
        fired = rid in ev["failed"]
        rows.append(
            {
                "rule": rid,
                "negative": next(r["negative"] for r in RULES if r["id"] == rid),
                "fired_on_bad_state": fired,
                "failed_rules": ev["failed"],
                "pass_means_detector_silent": ev["pass"],
            }
        )
    return rows


def run_suite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0048-suite-") as tmp:
        root = Path(tmp)
        both = run_both_states(root / "both")
        negatives = run_negatives(root / "neg")
        # Idempotence: conforming rollback twice must leave installer hashes stable.
        idemp_dir = root / "idemp"
        first = run_prepared("conforming", idemp_dir)
        from engine import conforming_rollback, snapshot_creation  # local
        from ledger import default_ledger as _led

        led = _led()
        backup = snapshot_creation(idemp_dir, led.creation)
        # After first rollback, installer files match v1; second rollback uses new backup of v1.
        second = conforming_rollback(idemp_dir, backup, led)
        second_ev = evaluate_result(second)
        idempotent = first.after == second.after and second_ev["pass"]

        all_neg_fired = all(n["fired_on_bad_state"] for n in negatives)
        proof = inventory_proof(both["conforming"])
        ok = (
            both["detector_ok"]
            and all_neg_fired
            and proof["zero_loss"]
            and idempotent
            and not both["vacuous_suite"]
        )
        return {
            "pass": ok,
            "both_states": {
                "conforming_pass": both["conforming_pass"],
                "nonconforming_pass": both["nonconforming_pass"],
                "nonconforming_fails": both["nonconforming_fails"],
                "vacuous_suite": both["vacuous_suite"],
                "detector_ok": both["detector_ok"],
                "naive_deleted_user_owned": both["naive_deleted_user_owned"],
                "conforming_deleted_user_owned": both["conforming_deleted_user_owned"],
                "conforming_failed": both["conforming"]["failed"],
                "nonconforming_failed": both["nonconforming"]["failed"],
            },
            "negatives": negatives,
            "all_negatives_fired": all_neg_fired,
            "inventory": proof,
            "idempotent_second_rollback": idempotent,
            "rule_count": len(RULE_IDS),
            "conforming_rules": both["conforming"]["rules"],
            "nonconforming_rules": both["nonconforming"]["rules"],
            "conforming_run": both["conforming_run"],
            "naive_run": both["naive_run"],
        }


if __name__ == "__main__":
    import json
    import sys

    doc = run_suite()
    print(json.dumps({k: doc[k] for k in ("pass", "both_states", "all_negatives_fired", "inventory", "idempotent_second_rollback")}, indent=2))
    raise SystemExit(0 if doc["pass"] else 1)
