#!/usr/bin/env python3
"""Named probe 2: deletion of a referenced workflow is refused.

Mechanically independent of probe 1 (this probe reads delete() refusal and
post-attempt resolvability; probe 1 reads resolve successor + pin execute).

Both-states:
  GOOD  — public delete() raises DeleteRefused; workflow still resolves;
          the retirement record is untouched.
  BAD   — force_drop_for_probe (silent deletion mutant) makes resolve fail.
          The public API must not take that path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "workflows"))

from retirement import Catalog, DeleteRefused, NotFound  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0204.json"
OLD = "wf.catalog-class.discovery-only"
NEW = "wf.catalog-class.typed-restore"
PIN = "consumer.pinned-to-discovery-only"
AT = "2026-08-24T18:00:00Z"


def _catalog() -> Catalog:
    cat = Catalog()
    cat.publish({"id": OLD, "body": "discover-then-record", "version": "1"})
    cat.publish({"id": NEW, "body": "typed-restore-then-record", "version": "2"})
    cat.pin_consumer(PIN, OLD)
    cat.supersede(
        OLD,
        NEW,
        {"path": "migrations/discovery-only-to-typed-restore.md"},
        retired_at=AT,
    )
    return cat


def _receipt_ok() -> bool:
    if not ART.is_file() or ART.stat().st_size < 200:
        return False
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    return (
        doc.get("unit_id") == "IMP-0204"
        and "SUCCESS:IMP-0204" in text
        and str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    )


def _good_delete_refused() -> dict:
    cat = _catalog()
    refs = cat.references(OLD)
    refused = False
    payload = None
    try:
        cat.delete(OLD)
    except DeleteRefused as exc:
        refused = True
        payload = exc.as_dict()
    still = cat.resolve(OLD)
    successor_still = cat.resolve(NEW)
    # Successor is referenced by the retirement record; delete it too.
    successor_refused = False
    try:
        cat.delete(NEW)
    except DeleteRefused:
        successor_refused = True
    return {
        "delete_refused": refused,
        "code": (payload or {}).get("code"),
        "references": refs,
        "still_resolves": still["present"] and still["successor_id"] == NEW,
        "successor_still_present": successor_still["present"],
        "successor_delete_refused": successor_refused,
        "consumer_pin_intact": PIN in cat.snapshot()["pins"],
    }


def _bad_force_drop() -> dict:
    cat = _catalog()
    cat.force_drop_for_probe(OLD)
    broke = False
    try:
        cat.resolve(OLD)
    except NotFound:
        broke = True
    pin_broke = False
    try:
        cat.execute_consumer(PIN)
    except NotFound:
        pin_broke = True
    return {
        "force_drop_resolve_broke": broke,
        "force_drop_pin_broke": pin_broke,
        "detector_fired": broke and pin_broke,
    }


def main() -> int:
    if not _receipt_ok():
        print("FAILED:IMP-0204-probe2 receipt missing sentinel or self-declared failure")
        return 1
    good = _good_delete_refused()
    bad = _bad_force_drop()
    want = (
        good["delete_refused"]
        and good["code"] == "DELETE_REFUSED"
        and good["still_resolves"]
        and good["successor_still_present"]
        and good["successor_delete_refused"]
        and any(r.get("kind") == "consumer_pin" for r in good["references"])
        and any(r.get("kind") == "retirement_record" for r in good["references"])
    )
    payload = {
        "probe": "probe2-refuse-delete",
        "unit_id": "IMP-0204",
        "good": good,
        "bad": bad,
        "both_states": bool(want) and bool(bad["detector_fired"]),
        "pass": bool(want) and bool(bad["detector_fired"]),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:IMP-0204-probe2 referenced delete not refused")
        return 1
    print(
        f"GOOD delete_refused={good['delete_refused']} still_resolves={good['still_resolves']} "
        f"refs={len(good['references'])}"
    )
    print(f"BAD force_drop detector_fired={bad['detector_fired']}")
    print("SUCCESS:IMP-0204-probe2 deletion of referenced workflow refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
