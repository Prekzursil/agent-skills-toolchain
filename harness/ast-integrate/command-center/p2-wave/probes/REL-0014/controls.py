#!/usr/bin/env python3
"""Four catalog controls for REL-0014, independent of the written receipt."""
from __future__ import annotations

from typing import Any

import gate
import scanner
import scenario as S


def _artifact(rel: str) -> tuple[bytes, str]:
    data = S.artifact_bytes(rel)
    return data, scanner.sha256_bytes(data)


def stale_stored_result() -> dict[str, Any]:
    """Feed a stored green older than the window -> refuse and force re-scan."""
    data, sha = _artifact(S.CLEAN_LOCK)
    db = gate.pull_advisory_db(S.load_advisories(), pulled_at=S.T_PROMOTE)
    stored = {
        "artifact_sha256": sha,
        "scan_timestamp": gate.format_ts(S.T_STORED),
        "snapshot_id": "cached-last-week",
        "verdict": "PASS",
        "window_length_seconds": S.WINDOW_SECONDS,
    }
    result = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db,
        now=S.T_PROMOTE,
        stored=stored,
        window_seconds=S.WINDOW_SECONDS,
    )
    refused = gate.log_has_refusal(result["promotion_log"], "stale-green")
    forced = any(
        row.get("event") == "forced-rescan" and row.get("reason") == "stale-green"
        for row in result["promotion_log"]
    )
    presented = any(
        row.get("event") == "stored-result-presented" for row in result["promotion_log"]
    )
    ok = (
        refused
        and forced
        and presented
        and result["rescanned"] is True
        and result["consumed_stored"] is False
        and result["artifact_sha256"] == sha
        and result["verdict"] == "PASS"
        and not result["findings"]
    )
    return {
        "pass": ok,
        "summary": (
            "stored green aged "
            f"{int((S.T_PROMOTE - S.T_STORED).total_seconds())}s against "
            f"window {S.WINDOW_SECONDS}s; refusal logged; live re-scan of {sha[:12]}"
        ),
        "refused": refused,
        "forced_rescan": forced,
        "consumed_stored": result["consumed_stored"],
        "rescanned": result["rescanned"],
        "verdict": result["verdict"],
        "age_seconds": int((S.T_PROMOTE - S.T_STORED).total_seconds()),
        "window_length_seconds": S.WINDOW_SECONDS,
        "artifact_sha256": sha,
        "snapshot_id": result["snapshot_id"],
        "scan_timestamp": result["scan_timestamp"],
        "promotion_log": result["promotion_log"],
        "result": {
            k: result[k]
            for k in (
                "verdict",
                "consumed_stored",
                "rescanned",
                "stored_refused",
                "artifact_sha256",
                "snapshot_id",
                "scan_timestamp",
                "window_length_seconds",
                "exit_code",
                "findings",
            )
        },
    }


def detector_known_advisory() -> dict[str, Any]:
    """Pin lodash@4.17.20; scanner must report CVE-2021-23337 and not CVE-2017-16021."""
    data, sha = _artifact(S.VULN_LOCK)
    db = gate.pull_advisory_db(S.load_advisories(), pulled_at=S.T_PROMOTE)
    result = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db,
        now=S.T_PROMOTE,
        window_seconds=S.WINDOW_SECONDS,
    )
    ids = [f["id"] for f in result["findings"]]
    ok = (
        result["verdict"] == "FAIL"
        and result["exit_code"] == 1
        and S.KNOWN_ADVISORY in ids
        and S.UNRELATED_ADVISORY not in ids
        and any(
            f["package"] == S.KNOWN_PACKAGE and f["version"] == S.VULN_VERSION
            for f in result["findings"]
        )
    )
    clean_data, clean_sha = _artifact(S.CLEAN_LOCK)
    clean = gate.promote(
        artifact_bytes=clean_data,
        artifact_sha256=clean_sha,
        db=db,
        now=S.T_PROMOTE,
        window_seconds=S.WINDOW_SECONDS,
    )
    ok = ok and clean["verdict"] == "PASS" and clean["exit_code"] == 0 and not clean["findings"]
    return {
        "pass": ok,
        "summary": (
            f"lodash@{S.VULN_VERSION} reports {S.KNOWN_ADVISORY}; "
            f"lodash@{S.FIXED_VERSION} is clean; {S.UNRELATED_ADVISORY} does not fire"
        ),
        "vulnerable_findings": result["findings"],
        "vulnerable_verdict": result["verdict"],
        "clean_verdict": clean["verdict"],
        "clean_findings": clean["findings"],
        "artifact_sha256": sha,
    }


def tooling_exit_not_checked() -> dict[str, Any]:
    """Exit 127 classifies NOT-CHECKED. The buggy 127-as-clean classifier is the negative."""
    data, sha = _artifact(S.CLEAN_LOCK)
    db = gate.pull_advisory_db(S.load_advisories(), pulled_at=S.T_PROMOTE)
    result = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db,
        now=S.T_PROMOTE,
        window_seconds=S.WINDOW_SECONDS,
        missing_tool=True,
    )
    honest = scanner.classify_exit(127)
    buggy = scanner.classify_exit_buggy_127_as_clean(127)
    ok = (
        result["exit_code"] == 127
        and result["verdict"] == "NOT-CHECKED"
        and honest == "NOT-CHECKED"
        and buggy == "PASS"
        and honest != buggy
        and result["consumed_stored"] is False
    )
    return {
        "pass": ok,
        "summary": (
            "exit 127 classifies NOT-CHECKED; buggy estate classifier would have "
            "called it PASS"
        ),
        "exit_code": result["exit_code"],
        "honest_classification": honest,
        "buggy_classification": buggy,
        "verdict": result["verdict"],
        "error": result.get("error"),
    }


def distinct_snapshot_ids() -> dict[str, Any]:
    """Two pulls minutes apart get distinct snapshot ids; reuse fails freshness."""
    data, sha = _artifact(S.CLEAN_LOCK)
    ads = S.load_advisories()
    db_a = gate.pull_advisory_db(ads, pulled_at=S.T_PROMOTE)
    db_b = gate.pull_advisory_db(ads, pulled_at=S.T_PULL_B)
    run_a = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db_a,
        now=S.T_PROMOTE,
        window_seconds=S.WINDOW_SECONDS,
    )
    run_b = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db_b,
        now=S.T_PULL_B,
        window_seconds=S.WINDOW_SECONDS,
        previous_snapshot_id=run_a["snapshot_id"],
    )
    reused = gate.promote(
        artifact_bytes=data,
        artifact_sha256=sha,
        db=db_a,
        now=S.T_PULL_B,
        window_seconds=S.WINDOW_SECONDS,
        previous_snapshot_id=run_a["snapshot_id"],
    )
    distinct = (
        run_a["snapshot_id"] != run_b["snapshot_id"]
        and run_a["freshness_ok"] is True
        and run_b["freshness_ok"] is True
        and run_a["verdict"] == "PASS"
        and run_b["verdict"] == "PASS"
    )
    reuse_failed = (
        reused["freshness_ok"] is False
        and reused["verdict"] == "REFUSED"
        and gate.log_has_refusal(reused["promotion_log"], "reused-snapshot-id")
        and reused["snapshot_id"] == run_a["snapshot_id"]
    )
    ok = distinct and reuse_failed
    return {
        "pass": ok,
        "summary": (
            "pull at T and T+7m record distinct snapshot ids; reusing T's id "
            "fails the freshness check"
        ),
        "snapshot_id_a": run_a["snapshot_id"],
        "snapshot_id_b": run_b["snapshot_id"],
        "scan_timestamp_a": run_a["scan_timestamp"],
        "scan_timestamp_b": run_b["scan_timestamp"],
        "reuse_freshness_ok": reused["freshness_ok"],
        "reuse_verdict": reused["verdict"],
        "minutes_apart": 7,
    }


def run_all() -> dict[str, Any]:
    return {
        "stale_stored_result": stale_stored_result(),
        "detector_known_advisory": detector_known_advisory(),
        "tooling_exit_not_checked": tooling_exit_not_checked(),
        "distinct_snapshot_ids": distinct_snapshot_ids(),
    }
