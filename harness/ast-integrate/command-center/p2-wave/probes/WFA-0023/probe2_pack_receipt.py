#!/usr/bin/env python3
"""Probe 2: pack contents vs index claims (evidence B).

Does not re-run marketplace schema validation. Compares fetched plugin.json /
mcp.json bytes to index rows. Both-states: planted match stays quiet; planted
mismatch and excessive permissions go red; nothing is installed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0023-sweep-public-marketplaces.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0023-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state {doc.get('state')}")
    if "SUCCESS:WFA-0023" not in text:
        return fail("sentinel-absent")

    match = E.compare_claim_to_receipt(
        E.load_json(HERE / "fixtures" / "pack_match" / "index_entry.json"),
        E.load_json(HERE / "fixtures" / "pack_match" / "plugin.json"),
    )
    if match["verdict"] != "CLAIMS-MATCH-RECEIPT":
        return fail(f"planted match verdict {match['verdict']}")

    mismatch = E.compare_claim_to_receipt(
        E.load_json(HERE / "fixtures" / "pack_mismatch" / "index_entry.json"),
        E.load_json(HERE / "fixtures" / "pack_mismatch" / "plugin.json"),
    )
    if mismatch["verdict"] != "CLAIM-NOT-RECEIPT":
        return fail(f"planted mismatch stayed green: {mismatch}")
    fields = {m["field"] for m in mismatch["material_mismatches"]}
    if not {"name", "version", "license"} <= fields:
        return fail(f"planted mismatch missed fields {fields}")

    excessive = E.permission_surface(
        E.load_json(HERE / "fixtures" / "pack_excessive" / "plugin.json")
    )
    if not excessive["excessive"]:
        return fail(f"planted excessive not flagged {excessive}")
    if excessive["installed"] or excessive["auto_loaded"]:
        return fail("planted excessive was marked installed/auto_loaded")

    live = E.run_evidence_b()
    samples = {row["pack_id"]: row for row in live["live_samples"]}
    zx = samples.get("0x")
    if not zx:
        return fail("missing 0x live sample")
    if zx["comparison"]["verdict"] != "CLAIM-NOT-RECEIPT":
        return fail(f"0x index name vs plugin.json name should mismatch: {zx['comparison']}")
    if zx["installed"]:
        return fail("0x marked installed")

    gh = samples.get("github")
    if not gh:
        return fail("missing github live sample")
    if not gh["permission_surface"]["excessive"]:
        return fail(f"github MCP PAT not flagged {gh['permission_surface']}")
    if "mcp.json" not in gh["permission_surface"]["bundled_agent_config"]:
        return fail("github bundled mcp.json not reported")
    if gh["installed"]:
        return fail("github marked installed")

    crunch = samples.get("42crunch-api-security-testing")
    if not crunch:
        return fail("missing 42crunch live sample")
    if crunch["receipt_license"] == E.UNDECLARED:
        return fail("42crunch plugin.json license missing from receipt")
    silent_license = [
        n
        for n in crunch["comparison"]["all_field_notes"]
        if n["field"] == "license" and n["kind"] == "index-silent-receipt-present"
    ]
    if not silent_license:
        return fail("42crunch license should be undeclared on index, present on receipt")

    inst = live["install"]
    if inst["packages_installed"] or inst["install_attempts"] or inst["live_client_modified"]:
        return fail(f"install side effects {inst}")

    try:
        E.record_install_attempt("claude plugin install github")
    except RuntimeError:
        pass
    else:
        return fail("record_install_attempt did not raise")
    if not E.install_attempts():
        return fail("install attempt log empty after guard fire")

    evb = doc.get("evidence_b") or {}
    if not evb.get("live_samples"):
        return fail("artifact evidence_b missing live samples")
    if (evb.get("install") or {}).get("packages_installed") not in ([], None):
        return fail("artifact claims an install")

    out = {
        "probe": "probe2-pack-receipt",
        "unit_id": "WFA-0023",
        "planted_match": match["verdict"],
        "planted_mismatch": mismatch["verdict"],
        "planted_excessive": True,
        "live_0x_claim_not_receipt": True,
        "live_github_excessive_not_installed": True,
        "live_42crunch_license_receipt_not_index": True,
        "packages_installed": [],
        "independence": "plugin.json/mcp.json receipts; no marketplace schema re-validate",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0023-probe2 pack-receipt both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
