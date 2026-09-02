#!/usr/bin/env python3
"""Probe 1: pass/fail delta + blocked egress log naming destination hosts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / C.OUTPUT_REL
SCHEMA = REPO / C.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0133-probe1 {msg}")
    return 1


def main() -> int:
    m = H.measure()
    try:
        H.require_contract(m)
    except SystemExit as exc:
        return fail(str(exc))
    pre, post = m["pre"], m["post"]
    delta = pre["undeclared"]
    log = [row for row in m["blocked_egress_log"] if row.get("run") == "blocked"]
    print(f"pre_undeclared={[x['id'] for x in delta]}")
    print(f"post_undeclared={[x['id'] for x in post['undeclared']]}")
    print(f"blocked_egress_hosts={sorted({r['host'] for r in log})}")
    print(f"blocked_egress_n={len(log)}")
    if len(delta) < 1:
        return fail("pass/fail delta empty on pre-remediation tree")
    if not log:
        return fail("blocked egress log empty")
    if any(not r.get("host") for r in log):
        return fail("egress log row missing destination host")
    if post["undeclared"]:
        return fail("post-remediation undeclared list not empty")
    if not post["identical_for_undeclared"]:
        return fail("undeclared tests still diverge after remediation")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if not doc.get("blocked_run_completed") or not doc.get("allowed_run_completed"):
        return fail("artifact missing completed-run flags")
    art_delta = (doc.get("pass_fail_delta") or {}).get("pre_remediation_undeclared") or []
    if len(art_delta) < 1:
        return fail("artifact pass_fail_delta empty")
    art_log = doc.get("blocked_egress_log") or []
    if len(art_log) < 1 or any(not r.get("host") for r in art_log):
        return fail("artifact blocked_egress_log missing hosts")
    import fragment as F  # noqa: WPS433 — restore $defs if another unit dropped it

    F.ensure_shared()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    frag = (schema.get("$defs") or {}).get(C.SCHEMA_DEF)
    if not isinstance(frag, dict):
        return fail("schema $defs.fault_injection_report missing")
    jsonschema.Draft7Validator(frag).validate(doc)
    print("SUCCESS:TST-0133-probe1 pass/fail delta and egress log attached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
