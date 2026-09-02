#!/usr/bin/env python3
"""Probe 2: over-broad list must encode on every client; schema discriminates.

If this probe accepted an always-cannot encoder, the real-list test would be
vacuous. Over-broad '*' must be can everywhere. Garbage documents and
adjective verdicts must be schema-rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import encoder as E  # noqa: E402
import evidence as EV  # noqa: E402
import schema_lib as S  # noqa: E402

ART = REPO / "command-center/research/RES-0040.json"
SCHEMA = REPO / "command-center/schema/compatibility-matrix.schema.json"
SENTINEL = (
    "SUCCESS:RES-0040 in the receipt AND a per-client encoding attempt "
    "for one real tool_permissions list with an explicit can/cannot verdict"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0040-probe2 {msg}")
    return 1


def main() -> int:
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return fail("jsonschema not installed")

    over = E.overbroad_list()
    live = {row["client_id"]: row for row in E.encode_all(over)}
    for cid, row in live.items():
        print(f"overbroad {cid} verdict={row['verdict']}")
        if row["verdict"] != "can":
            return fail(f"over-broad list not encodable on {cid}")
        if row["per_entry"][0]["verdict"] != "can":
            return fail(f"over-broad entry not can on {cid}")

    if not ART.is_file():
        return fail("artifact missing")
    if not SCHEMA.is_file():
        return fail("schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))

    garbage_rejected = 0
    for g in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "RES-0040", "state": "SUCCESS", "verdict": "expressive"},
    ):
        if S.schema_errors(g):
            garbage_rejected += 1
    print(f"schema_garbage_rejected={garbage_rejected}/3")
    if garbage_rejected != 3:
        return fail("schema accepts garbage")

    catalog_errs = S.schema_errors(doc)
    if catalog_errs:
        return fail(f"artifact fails schema: {catalog_errs[0]}")
    print("schema_accepts_artifact=True")

    encodings = S.domain_get(doc, "encodings_real") or []
    if not encodings:
        return fail("artifact encodings_real missing")
    mutant = copy.deepcopy(doc)
    report = mutant.get("report") if isinstance(mutant.get("report"), dict) else mutant
    report["encodings_real"][0]["verdict"] = "expressive"
    adjective_rejected = bool(S.schema_errors(mutant, S.bound_verdict_schema()))
    print(f"adjective_verdict_rejected={adjective_rejected}")
    if not adjective_rejected:
        return fail("schema accepted adjective verdict")

    art_over = {r["client_id"]: r for r in S.domain_get(doc, "encodings_overbroad") or []}
    if set(art_over) != set(live):
        return fail("artifact overbroad clients mismatch")
    for cid, row in live.items():
        if art_over[cid].get("verdict") != "can":
            return fail(f"artifact overbroad {cid} not can")

    ranking = S.domain_get(doc, "least_privilege_ranking") or []
    if not ranking or ranking[0].get("client_id") != "claude-code":
        return fail("least-privilege rank-1 must be claude-code for this catalog list")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer is not independent")
    if rev.get("verdict") != "PASS":
        return fail("reviewer verdict is not PASS")

    evidence = S.domain_get(doc, "captured_rails") or []
    if len(evidence) < 4:
        return fail("fewer than four evidence rails")
    for i, row in enumerate(evidence):
        sha = str(row.get("sha256") or "")
        if len(sha) != 64:
            return fail(f"evidence[{i}] sha256 missing")
        if int(row.get("http_status") or 0) != 200:
            return fail(f"evidence[{i}] http_status not 200")
        if not row.get("permalink"):
            return fail(f"evidence[{i}] permalink missing")
        if not row.get("fetched_at"):
            return fail(f"evidence[{i}] fetched_at missing")

    # Two rails per declared plugin client, resolved from live captures.
    for cid in ("claude-code", "codex"):
        rails = EV.require_two_rails(cid)
        print(f"rails[{cid}]={[r['id'] for r in rails]}")

    claims = S.domain_get(doc, "claims") or []
    e3 = [c for c in claims if c.get("grade") == "E3"]
    cited_e3 = [c for c in e3 if c.get("cited_as_measured_fact") is True]
    if cited_e3:
        return fail("E3 claim cited as measured fact")
    for c in claims:
        if c.get("grade") in {"E1", "E2"} and len(c.get("rails") or []) < 2:
            return fail(f"{c.get('id')} graded {c.get('grade')} with <2 rails")

    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("completion sentinel absent")
    print("SUCCESS:RES-0040-probe2 overbroad-control schema reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
