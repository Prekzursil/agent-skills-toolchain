#!/usr/bin/env python3
"""Named probe 1: retired id resolves to successor; pinned consumer still runs.

Both-states:
  GOOD  — SUPERSESSION record kept; resolve returns successor; pin executes
          with a typed warning (no hard break). DEPRECATION path also warned.
  BAD   — silent drop of the retired body (the 11347 failure); resolve and
          pin execution hard-break. The detector must fire on BAD and stay
          silent on GOOD.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "workflows"))

from retirement import (  # noqa: E402
    Catalog,
    NotFound,
    SchemaError,
    KIND_DEPRECATION,
    KIND_SUPERSESSION,
    WARN_DEPRECATED,
    WARN_SUPERSEDED,
)

ART = REPO / "command-center/receipts/IMP-0204.json"
OLD = "wf.catalog-class.discovery-only"
NEW = "wf.catalog-class.typed-restore"
DEP = "wf.legacy-scout"
DEP_SUCC = "wf.scout-v2"
PIN = "consumer.pinned-to-discovery-only"
AT = "2026-08-24T18:00:00Z"


def _catalog() -> Catalog:
    cat = Catalog()
    cat.publish({"id": OLD, "body": "discover-then-record", "version": "1"})
    cat.publish({"id": NEW, "body": "typed-restore-then-record", "version": "2"})
    cat.publish({"id": DEP, "body": "legacy-scout-body", "version": "1"})
    cat.publish({"id": DEP_SUCC, "body": "scout-v2-body", "version": "2"})
    cat.pin_consumer(PIN, OLD)
    cat.supersede(
        OLD,
        NEW,
        {"path": "migrations/discovery-only-to-typed-restore.md", "steps": ["retarget pin"]},
        retired_at=AT,
        reason="typed restore supersedes discovery-only hatch",
    )
    cat.deprecate(
        DEP,
        reason="scout corpus moved to hashed partitions",
        removal_date="2027-02-01",
        successor_id=DEP_SUCC,
        retired_at=AT,
    )
    return cat


def _schema_rejects() -> dict:
    cat = Catalog()
    cat.publish({"id": "wf.a", "body": "a"})
    cat.publish({"id": "wf.b", "body": "b"})
    cases = []

    def expect_schema(label: str, fn) -> None:
        try:
            fn()
            cases.append({"label": label, "rejected": False})
        except SchemaError:
            cases.append({"label": label, "rejected": True})

    expect_schema(
        "supersession-without-successor",
        lambda: cat.retire(
            {
                "kind": KIND_SUPERSESSION,
                "retired_id": "wf.a",
                "migration": {"path": "m.md"},
            }
        ),
    )
    expect_schema(
        "supersession-without-migration",
        lambda: cat.supersede("wf.a", "wf.b", {}),
    )
    expect_schema(
        "deprecation-without-reason",
        lambda: cat.retire(
            {
                "kind": KIND_DEPRECATION,
                "retired_id": "wf.a",
                "removal_date": "2027-01-01",
            }
        ),
    )
    expect_schema(
        "deprecation-without-removal-date",
        lambda: cat.deprecate("wf.a", reason="gone", removal_date=""),
    )
    expect_schema(
        "dangling-successor",
        lambda: cat.supersede("wf.a", "wf.does-not-exist", {"path": "m.md"}),
    )
    expect_schema(
        "deletion-kind",
        lambda: cat.retire({"kind": "DELETION", "retired_id": "wf.a"}),
    )
    return {"all_rejected": all(c["rejected"] for c in cases), "cases": cases}


def _good(cat: Catalog) -> dict:
    resolved = cat.resolve(OLD)
    ran = cat.execute_consumer(PIN)
    dep = cat.resolve(DEP)
    dep_run = cat.execute_workflow(DEP)
    warn = (ran.get("warnings") or [None])[0] or {}
    return {
        "retired_resolves": resolved["present"] and resolved["retired"],
        "successor_id": resolved.get("successor_id"),
        "successor_body": (resolved.get("successor") or {}).get("body"),
        "pin_ok": ran.get("ok") is True and ran.get("hard_break") is False,
        "pin_executed_retired_id": ran.get("executed_id") == OLD,
        "pin_warning_code": warn.get("code"),
        "pin_warning_successor": warn.get("successor_id"),
        "deprecation_resolves": dep["present"] and dep["kind"] == KIND_DEPRECATION,
        "deprecation_runs": dep_run.get("ok") is True,
        "deprecation_warning_code": (dep_run.get("warnings") or [{}])[0].get("code"),
        "deprecation_removal_date": (dep_run.get("warnings") or [{}])[0].get(
            "removal_date"
        ),
    }


def _bad_silent_delete() -> dict:
    cat = _catalog()
    cat.force_drop_for_probe(OLD)
    resolve_broke = False
    pin_hard_break = False
    try:
        cat.resolve(OLD)
    except NotFound:
        resolve_broke = True
    try:
        cat.execute_consumer(PIN)
    except NotFound:
        pin_hard_break = True
    return {
        "silent_delete_resolve_broke": resolve_broke,
        "silent_delete_pin_hard_broke": pin_hard_break,
        "detector_fired": resolve_broke and pin_hard_break,
    }


def _receipt_ok() -> bool:
    if not ART.is_file() or ART.stat().st_size < 200:
        return False
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    return (
        doc.get("unit_id") == "IMP-0204"
        and "SUCCESS:IMP-0204" in text
        and str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    )


def main() -> int:
    if not _receipt_ok():
        print("FAILED:IMP-0204-probe1 receipt missing sentinel or self-declared failure")
        return 1
    schema = _schema_rejects()
    if not schema["all_rejected"]:
        print("FAILED:IMP-0204-probe1 schema did not reject malformed retirement")
        print(json.dumps(schema, indent=2))
        return 1
    good = _good(_catalog())
    want = (
        good["retired_resolves"]
        and good["successor_id"] == NEW
        and good["successor_body"] == "typed-restore-then-record"
        and good["pin_ok"]
        and good["pin_executed_retired_id"]
        and good["pin_warning_code"] == WARN_SUPERSEDED
        and good["pin_warning_successor"] == NEW
        and good["deprecation_resolves"]
        and good["deprecation_runs"]
        and good["deprecation_warning_code"] == WARN_DEPRECATED
        and good["deprecation_removal_date"] == "2027-02-01"
    )
    bad = _bad_silent_delete()
    payload = {
        "probe": "probe1-resolve-and-pin",
        "unit_id": "IMP-0204",
        "good": good,
        "bad": bad,
        "schema_rejects": schema,
        "both_states": bool(want) and bool(bad["detector_fired"]),
        "pass": bool(want) and bool(bad["detector_fired"]),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0204-probe1 both-states resolve/pin")
        return 1
    print(
        f"GOOD resolve successor={good['successor_id']} pin_ok={good['pin_ok']} "
        f"warn={good['pin_warning_code']}"
    )
    print(
        f"BAD silent-delete detector_fired={bad['detector_fired']} "
        f"schema_rejects={schema['all_rejected']}"
    )
    print("SUCCESS:IMP-0204-probe1 retired id resolves; pinned consumer still runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
