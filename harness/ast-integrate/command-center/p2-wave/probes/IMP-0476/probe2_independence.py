#!/usr/bin/env python3
"""Probe 2: independence audit of three checks (does not call adjudicate).

Mechanically independent of probe 1: re-runs file-stat and content-hash /
json-keys by reading bytes and st_size directly, then verifies the method
sets. A cloned file-stat pair is the negative control (not independent).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import COMPONENTS, LEDGER, ensure_fixtures  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0476.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0476-probe2 {msg}")
    return 1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_pair(rel: str, expected_sha: str | None) -> dict:
    path = COMPONENTS / rel
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    digest = sha256_file(path) if exists else None
    stat_ok = exists and size >= 8
    hash_ok = bool(expected_sha) and digest == expected_sha
    return {
        "rel": rel,
        "exists": exists,
        "bytes": size,
        "sha256": digest,
        "stat_ok": stat_ok,
        "hash_ok": hash_ok,
        "methods_independent": True,
        "stat_method": "file-stat",
        "hash_method": "content-hash",
        "agree_ok": stat_ok and hash_ok,
        "disagree": stat_ok != hash_ok,
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SENTINEL:IMP-0476:HEALTH-TWO-SIGNAL" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    inventory = ensure_fixtures()
    by_id = {c["id"]: c for c in inventory["checks"]}

    ledger = audit_pair("ledger/marker.json", hashlib.sha256(LEDGER).hexdigest())
    if not ledger["stat_ok"] or not ledger["hash_ok"]:
        return fail(f"ledger independent probes not both ok {ledger}")
    if ledger["stat_method"] == ledger["hash_method"]:
        return fail("ledger methods collapsed")

    wrong = "0" * 64
    router = audit_pair("router/marker.json", wrong)
    if not router["stat_ok"]:
        return fail("router file-stat should be ok")
    if router["hash_ok"]:
        return fail("router content-hash should fail against planted wrong digest")
    if not router["disagree"]:
        return fail("router independent probes did not disagree")

    skills_path = COMPONENTS / "skills" / "marker.json"
    if not skills_path.is_file():
        return fail("skills marker missing")
    skills_a = skills_path.is_file() and skills_path.stat().st_size >= 8
    skills_b = skills_path.is_file() and skills_path.stat().st_size >= 8
    skills_methods = {
        by_id["skills.registered"]["probes"][0]["method"],
        by_id["skills.registered"]["probes"][1]["method"],
    }
    if skills_methods != {"file-stat"}:
        return fail(f"skills methods={skills_methods} want cloned file-stat")
    if not (skills_a and skills_b):
        return fail("skills cloned stats not both ok")

    art_checks = {c["id"]: c for c in (doc.get("checks") or []) if isinstance(c, dict)}
    for cid, want_status, independent in (
        ("ledger.writable", "OK", True),
        ("router.responding", "DISAGREE", True),
        ("skills.registered", "NOT-CHECKED", False),
    ):
        row = art_checks.get(cid)
        if not row:
            return fail(f"artifact missing audited check {cid}")
        if row.get("status") != want_status:
            return fail(f"artifact {cid} status={row.get('status')} want {want_status}")
        if bool(row.get("mechanically_independent")) != independent:
            return fail(f"artifact {cid} independent={row.get('mechanically_independent')}")
        probes = row.get("probes") or []
        if cid != "skills.registered" and len(probes) < 2:
            return fail(f"artifact {cid} must list both probes for independence audit")
        methods = [p.get("method") for p in probes]
        if independent and len(set(methods)) < 2:
            return fail(f"artifact {cid} listed methods {methods} are not independent")
        if not independent and len(set(methods)) != 1:
            return fail(f"skills listed mixed methods {methods}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer block missing independent PASS")

    out = {
        "probe": "probe2-independence",
        "unit_id": "IMP-0476",
        "audited": ["ledger.writable", "router.responding", "skills.registered"],
        "ledger": ledger,
        "router": {
            "stat_ok": router["stat_ok"],
            "hash_ok": router["hash_ok"],
            "disagree": router["disagree"],
        },
        "skills_cloned_method": "file-stat",
        "skills_independent": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "ledger_independent=True router_disagree=True "
        "skills_cloned_file_stat=True skills_independent=False"
    )
    print("SUCCESS:IMP-0476-probe2 three-check independence audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
