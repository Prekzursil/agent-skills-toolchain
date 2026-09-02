"""Shared receipt corpus — SECOND identity signal only."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

SENTINEL = "SENTINEL:CNF-0171:SHARED-REDUCER"

COMPLETE_FLAGS: dict[str, Any] = {
    "state": "SUCCESS",
    "sentinel": SENTINEL,
    "schema_ok": True,
    "evidence_anchor_count": 2,
    "tests_passed": True,
    "negative_controls_ok": True,
    "reviewer_verdict": "PASS",
    "open_p0_p1": 0,
    "registered": True,
    "downstream_read_ok": True,
    "min_bytes": 8,
}


def _comparable(verdict: dict[str, Any]) -> dict[str, Any]:
    skip = {"site"}
    out = {k: v for k, v in verdict.items() if k not in skip}
    conds = out.get("conditions")
    if isinstance(conds, list):
        out["conditions"] = [
            {k: v for k, v in row.items() if k != "site"} if isinstance(row, dict) else row
            for row in conds
        ]
    return out


def site_payload(site_id: str, base: dict[str, Any], aliases: dict[str, tuple[str, str]]) -> dict[str, Any]:
    rc_key, path_key = aliases[site_id]
    payload = dict(base)
    if "exit_code" in payload:
        payload[rc_key] = payload["exit_code"]
    if "artifact_path" in payload:
        payload[path_key] = payload["artifact_path"]
    return payload


def run_corpus(
    check: Callable[[str, dict[str, Any]], dict[str, Any]],
    site_ids: list[str],
    aliases: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    agreed = True
    with tempfile.TemporaryDirectory(prefix="cnf0171-corpus-") as tmp:
        artifact = Path(tmp) / "unit.json"
        artifact.write_text('{"ok": true, "sentinel": "%s"}\n' % SENTINEL, encoding="utf-8")
        cases = [
            ("exit-zero-alone", {"exit_code": 0}, "INCOMPLETE"),
            (
                "digest-without-file",
                {
                    "exit_code": 0,
                    "state": "SUCCESS",
                    "claimed_digest": "a" * 64,
                    "artifact_path": "no-such-cnf0171-artifact.json",
                },
                "INCOMPLETE",
            ),
            (
                "complete-all-flags",
                {**COMPLETE_FLAGS, "exit_code": 0, "artifact_path": str(artifact)},
                "COMPLETE",
            ),
            (
                "negative-control-fail",
                {
                    **COMPLETE_FLAGS,
                    "exit_code": 0,
                    "artifact_path": str(artifact),
                    "negative_controls_ok": False,
                },
                "INCOMPLETE",
            ),
            (
                "schema-false",
                {
                    **COMPLETE_FLAGS,
                    "exit_code": 0,
                    "artifact_path": str(artifact),
                    "schema_ok": False,
                },
                "INCOMPLETE",
            ),
            (
                "sentinel-absent",
                {
                    **COMPLETE_FLAGS,
                    "exit_code": 0,
                    "artifact_path": str(artifact),
                    "sentinel": "SENTINEL:NOT-THIS-UNIT",
                },
                "INCOMPLETE",
            ),
        ]
        for case_id, base, expected in cases:
            by_site: dict[str, Any] = {}
            comps: list[str] = []
            for site_id in site_ids:
                got = check(site_id, site_payload(site_id, base, aliases))
                by_site[site_id] = {
                    "verdict": got.get("verdict"),
                    "library": got.get("library"),
                    "failing_condition_ids": got.get("failing_condition_ids"),
                    "not_checked_ids": got.get("not_checked_ids"),
                }
                comps.append(json.dumps(_comparable(got), sort_keys=True, separators=(",", ":")))
            same = len(set(comps)) == 1
            expected_ok = all(by_site[s]["verdict"] == expected for s in site_ids)
            if not same or not expected_ok:
                agreed = False
            rows.append(
                {
                    "case_id": case_id,
                    "expected": expected,
                    "sites_agree": same,
                    "expected_ok": expected_ok,
                    "by_site": by_site,
                }
            )
    return {"cases": rows, "all_sites_agree": agreed, "n_cases": len(rows)}
