#!/usr/bin/env python3
"""Probe 1: known-advisory FLAG and clean NOT-FLAG, both live, before trusting CLEAN.

Mechanically independent of probe 2 (pin/fallback recount).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import CLEAN_CONTROL_ID, KNOWN_CVE, UNREACHABLE_CONTROL_ID, VULN_CONTROL_ID  # noqa: E402
from resolver import osv_query  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0151-supply-chain-map-for-the-105-external-dependencies-o.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0151-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0151":
        return fail(f"unit_id {doc.get('unit_id')}")
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0151" not in blob:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    vuln_live = osv_query("lodash", "npm", "4.17.20")
    clean_live = osv_query("ms", "npm", "2.1.3")
    if not vuln_live.get("ok"):
        return fail("live OSV lodash query failed")
    if KNOWN_CVE not in (vuln_live.get("ids") or []):
        return fail(f"{KNOWN_CVE} absent from live lodash ids={vuln_live.get('ids')[:12]}")
    if not clean_live.get("ok"):
        return fail("live OSV ms query failed")
    if KNOWN_CVE in (clean_live.get("ids") or []):
        return fail("clean control unexpectedly contains known CVE")
    if clean_live.get("ids"):
        return fail(f"clean control not empty ids={clean_live.get('ids')[:12]}")

    rows = {r["id"]: r for r in (doc.get("rows") or []) if isinstance(r, dict)}
    if len(doc.get("rows") or []) != 105:
        return fail(f"row count {len(doc.get('rows') or [])}")
    vuln = rows.get(VULN_CONTROL_ID) or {}
    clean = rows.get(CLEAN_CONTROL_ID) or {}
    unr = rows.get(UNREACHABLE_CONTROL_ID) or {}
    if vuln.get("advisory_status") != "FLAGGED":
        return fail(f"lodash status={vuln.get('advisory_status')}")
    if KNOWN_CVE not in (vuln.get("advisory_ids") or []):
        return fail("artifact lodash missing known CVE")
    if clean.get("advisory_status") != "CLEAN":
        return fail(f"ms status={clean.get('advisory_status')} (CLEAN required after both-states)")
    if clean.get("advisory_ids"):
        return fail("artifact ms not empty advisory_ids")

    gate = doc.get("both_states_gate") or {}
    if not gate.get("passed"):
        return fail("both_states_gate.passed is not true")
    if not gate.get("vuln_queried_first"):
        return fail("vuln control was not recorded as queried first")
    if not gate.get("vuln_flagged") or gate.get("clean_has_known_cve"):
        return fail("gate flags inconsistent")

    if unr.get("resolution") != "UNRESOLVED":
        return fail(f"unreachable resolution={unr.get('resolution')}")
    if unr.get("advisory_status") == "CLEAN":
        return fail("unreachable assumed CLEAN")
    if (unr.get("upstream") or {}).get("http_status") != 404:
        return fail(f"unreachable http_status={(unr.get('upstream') or {}).get('http_status')}")
    attempts = (unr.get("upstream") or {}).get("attempts")
    if not isinstance(attempts, int) or attempts < 1:
        return fail(f"unreachable attempts={attempts}")
    # 404 is non-transient: must not keep retrying up to the transient cap as if it were 429.
    if (unr.get("upstream") or {}).get("nontransient") is not True:
        return fail("404 was not classified nontransient")
    if attempts > 1:
        return fail(f"404 was retried attempts={attempts}")

    print(
        json.dumps(
            {
                "clean_empty": True,
                "known_cve": KNOWN_CVE,
                "pass": True,
                "probe": "probe1-advisory-both-states",
                "unit_id": "WFA-0151",
                "vuln_flagged": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"vuln={VULN_CONTROL_ID} FLAGGED {KNOWN_CVE} clean={CLEAN_CONTROL_ID} CLEAN "
        f"unreachable=UNRESOLVED gate=passed"
    )
    print("SUCCESS:WFA-0151-probe1 advisory both-states FLAG/CLEAN before trusting clean rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
