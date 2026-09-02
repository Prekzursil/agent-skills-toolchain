#!/usr/bin/env python3
"""Probe 1: mixed cohort both-states + planted digest-for-missing-file.

Evidence A: one valid, one null, one schema-invalid — repaired barrier completes,
reports the invalid, reports the null as missing, does not silently accept invalid.

Both-states: naive filter(Boolean) drops the null and accepts the invalid and
the planted missing-file digest; repaired rejects those.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fanin as F  # noqa: E402
import fixtures as FX  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0091-repair-schema-typed-fanin.json"
SENTINEL = "SUCCESS:WFA-0091"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0091-probe1 {msg}")
    return 1


def main() -> int:
    FX.assert_fixture_layout()
    contracts = FX.contracts()
    inbound = FX.inbound()
    ws = FX.workspace()

    naive = F.naive_fan_in(contracts, inbound, ws)
    repaired = F.repaired_fan_in(contracts, inbound, ws)
    ns, rs = F.summarize(naive), F.summarize(repaired)

    print(json.dumps({"naive": ns, "repaired": rs}, indent=2, sort_keys=True))

    if not repaired.get("completed"):
        return fail("repaired-did-not-complete")
    if "U-VALID" not in rs["accepted_ids"]:
        return fail("repaired-did-not-accept-valid")
    if "U-NULL" not in rs["missing_null"]:
        return fail("repaired-did-not-report-null-as-missing")
    if "U-ABSENT" not in rs["not_received"]:
        return fail("repaired-did-not-record-not-received")
    if "U-INVALID" not in rs["rejected_ids"]:
        return fail("repaired-did-not-reject-schema-invalid")
    if "schema-invalid" not in rs["rejected_reasons"]:
        return fail("repaired-invalid-reason")
    if "U-PLANTED" not in rs["rejected_ids"]:
        return fail("repaired-did-not-reject-planted-digest")
    planted = next(r for r in repaired["rejected"] if r["unit_id"] == "U-PLANTED")
    if planted.get("reason") != "no-receipt":
        return fail(f"planted-reason={planted.get('reason')}")
    if planted.get("digest_parsed") is not False:
        return fail("planted-digest-was-parsed")
    if "U-INVALID" in rs["accepted_ids"] or "U-PLANTED" in rs["accepted_ids"]:
        return fail("repaired-silently-accepted-bad")
    if "U-NULL" in rs["accepted_ids"]:
        return fail("repaired-accepted-null")

    # Naive both-states: the defects must actually fire on this fixture.
    if "U-NULL" not in ns["silently_dropped_nulls"]:
        return fail("naive-did-not-drop-null")
    if "U-INVALID" not in ns["silently_accepted_invalid"]:
        return fail("naive-did-not-accept-invalid")
    if "U-PLANTED" not in ns["silently_accepted_missing_file"]:
        return fail("naive-did-not-accept-planted-digest")
    if "U-VALID" not in ns["accepted_ids"]:
        return fail("naive-lost-valid")
    if ns["missing_null"] or ns["not_received"]:
        return fail("naive-unexpectedly-kept-a-ledger")

    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    both = doc.get("both_states") or {}
    if both.get("naive_accepts_planted") is not True:
        return fail("artifact-naive-planted")
    if both.get("repaired_rejects_planted") is not True:
        return fail("artifact-repaired-planted")
    mixed = doc.get("evidence_A_mixed_cohort") or {}
    if mixed.get("completed") is not True:
        return fail("artifact-A-completed")
    if mixed.get("invalid_reported") is not True:
        return fail("artifact-A-invalid-reported")
    if mixed.get("null_reported_as_missing") is not True:
        return fail("artifact-A-null")
    if mixed.get("invalid_silently_accepted") is True:
        return fail("artifact-A-silent-invalid")

    print(
        "both-states naive_drop_null=True naive_accept_invalid=True "
        "naive_accept_planted=True repaired_report_null=True "
        "repaired_reject_invalid=True repaired_reject_planted=True"
    )
    print("SUCCESS:WFA-0091-probe1 mixed-cohort both-states planted-digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
