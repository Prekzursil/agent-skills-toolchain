#!/usr/bin/env python3
"""Probe 1: revocation representability (revoked retained, distinct from deleted).

Author-side: three intended fixtures validate; revoked ≠ deleted; a revoked
row without a revocation object is rejected. Live contract must embed the
same registry_entry_schema digest as schema.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import schema as S  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0079.json"
RAW = HERE / "probe1-revocation.raw.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_contract() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:ARC-0079-probe1 artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:ARC-0079-probe1 artifact not an object")
    return doc


def main() -> int:
    errs: list[str] = []
    doc = load_contract()
    text = json.dumps(doc, sort_keys=True)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        errs.append(f"contract-state={st}")
    if "SUCCESS:ARC-0079" not in text:
        errs.append("sentinel-absent")
    if doc.get("unit_id") != "ARC-0079":
        errs.append("unit-id")

    embedded = doc.get("registry_entry_schema")
    if not isinstance(embedded, dict):
        errs.append("embedded-schema-absent")
        embedded = {}
    live_digest = S.schema_digest(embedded) if embedded else ""
    author_digest = S.schema_digest(S.SCHEMA)
    if embedded and live_digest != author_digest:
        errs.append("schema-digest-mismatch")

    rows: dict[str, dict] = {}
    for name, factory in (
        ("published", F.published),
        ("deprecated", F.deprecated),
        ("revoked", F.revoked),
        ("deleted", F.deleted),
    ):
        inst = factory()
        ok, messages = S.validate_entry(inst, embedded or S.SCHEMA)
        kind = S.classify_version(S.first_version(inst))
        rows[name] = {"ok": ok, "kind": kind, "errors": messages[:6]}
        if not ok:
            errs.append(f"{name}-rejected")
        if kind != name:
            errs.append(f"{name}-kind={kind}")

    rev_kind = rows.get("revoked", {}).get("kind")
    del_kind = rows.get("deleted", {}).get("kind")
    distinguishable = rev_kind == "revoked" and del_kind == "deleted" and rev_kind != del_kind
    if not distinguishable:
        errs.append("revoked-not-distinct-from-deleted")

    rev_ver = S.first_version(F.revoked())
    if rev_ver.get("presence") != "retained":
        errs.append("revoked-not-retained")
    if not isinstance(rev_ver.get("revocation"), dict):
        errs.append("revoked-missing-revocation-object")

    del_ver = S.first_version(F.deleted())
    if del_ver.get("presence") != "tombstone":
        errs.append("deleted-not-tombstone")
    if "revocation" in del_ver:
        errs.append("deleted-has-revocation")

    bad_ok, bad_msgs = S.validate_entry(F.revoked_without_revocation_object(), embedded or S.SCHEMA)
    if bad_ok:
        errs.append("revoked-without-object-accepted")
    confuse_ok, _ = S.validate_entry(F.revoked_as_deleted_confusion(), embedded or S.SCHEMA)
    if confuse_ok:
        errs.append("revocation-on-tombstone-accepted")

    fired_on_bad = (not bad_ok) and (not confuse_ok)
    silent_on_good = all(rows[n]["ok"] for n in ("published", "deprecated", "revoked", "deleted"))

    payload = {
        "probe": "probe1-revocation-representability",
        "unit_id": "ARC-0079",
        "schema_digest": live_digest,
        "author_digest": author_digest,
        "rows": rows,
        "distinguishable": distinguishable,
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "bad_without_revocation": {"ok": bad_ok, "errors": bad_msgs[:6]},
        "errors": errs,
        "pass": not errs,
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"published={rows.get('published', {}).get('ok')} "
        f"deprecated={rows.get('deprecated', {}).get('ok')} "
        f"revoked={rows.get('revoked', {}).get('ok')} "
        f"deleted={rows.get('deleted', {}).get('ok')}"
    )
    print(
        f"distinguishable={distinguishable} "
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"digest_match={live_digest == author_digest}"
    )
    if errs:
        print("FAILED:ARC-0079-probe1 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0079-probe1 revocation retained and distinct from deletion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
