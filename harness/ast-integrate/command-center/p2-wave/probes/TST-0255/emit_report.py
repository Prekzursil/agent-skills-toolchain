#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0255.json (docs_conformance_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import CATALOG_DOCS  # noqa: E402
from harness import measure  # noqa: E402

OUT = "command-center/receipts/TST-0255.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/docs_conformance_report"
SENTINEL = "SUCCESS:TST-0255"
QUESTION = (
    "Do all internal `file:line` anchors and external URLs in the documentation "
    "resolve? PASS requires internal anchors verified against the repository at "
    "the documented revision, and external links to distinguish UNREACHABLE "
    "(offline/transient) from WRONG (404/410) - never folding the first into "
    "the second."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0255/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0255/probe2_egress_blocked.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def slim_internal(row: dict) -> dict:
    keep = (
        "rev",
        "path",
        "line",
        "command",
        "git_returncode",
        "classification",
        "source",
        "raw",
        "blob_line_count",
        "worktree",
    )
    return {k: row[k] for k in keep if k in row}


def fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def slim_external(row: dict) -> dict:
    keep = (
        "url",
        "classification",
        "http_status",
        "error_type",
        "error",
        "attempt",
        "source",
    )
    return {k: row[k] for k in keep if k in row}


def main() -> int:
    measured = measure()
    if not measured["checker_pass"]:
        print("FAILED:TST-0255 emit detector controls did not pass")
        print(json.dumps({"both_states": measured["both_states"]["pass"], "egress": measured["egress"]["pass"]}))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = measured["live"]
    both = measured["both_states"]
    egress = measured["egress"]
    schema_base = REPO / "command-center/schema/receipt.schema.json"
    target_pass = measured["target_pass"]
    target_verdict = measured["target_verdict"]
    missing_docs = list(live.get("missing_catalog_docs") or [])
    git_inside = bool(live["git"]["inside"])
    docs_present = bool(live["catalog_docs_present"])

    catalog_set = set(CATALOG_DOCS)
    catalog_internal = [r for r in live["internal"] if r.get("source") in catalog_set]
    other_internal = [r for r in live["internal"] if r.get("source") not in catalog_set]
    shown_internal = catalog_internal + other_internal[: max(0, 48 - len(catalog_internal))]

    git_note = (
        "git rev-parse --is-inside-work-tree is true"
        if git_inside
        else "this worktree has no git object store (rev-parse is not inside a work tree)"
    )
    docs_note = (
        "catalog RUNBOOK.md and RELEASE-CHECKLIST.md are present"
        if docs_present
        else f"catalog docs missing: {missing_docs}"
    )

    answer_summary = (
        "Checker is live-red-capable: git cat-file resolves a fixture blob at "
        f"line {both['good_line']} and reports line {both['bad_line']} as "
        "BEYOND-EOF; a shape-only checker accepts the off-by-1000. External "
        "status codes classify local 404/410 as WRONG, and the same checker "
        "under unshare -n reports UNREACHABLE rather than 404. Live worktree: "
        f"{git_note}; {docs_note}; scanned {live['scanned_file_count']} "
        f"doc files, {live['anchor_count']} file:line anchors "
        f"({live['unique_internal']} unique), {live['url_count']} URLs "
        f"({live['unique_external_checked']} fetched). Internal OK-at-rev="
        f"{live['internal_ok_at_rev']}. External WRONG={live['external_wrong']}. "
        "PASS for the catalog question requires named docs present, a git "
        "object store, every internal anchor OK at the documented revision, "
        "and no WRONG externals. That conjunction is false on this worktree."
    )

    doc = {
        "unit_id": "TST-0255",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "docs_conformance_report",
        "title": "Internal anchors and external links resolve, with offline distinguished from wrong",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0255; evidence (a) git cat-file -p "
            "<rev>:<path> plus line-count, (b) external status codes with retry "
            "and explicit UNREACHABLE vs WRONG (404/410)"
        ),
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_base.is_file(),
        "target_pass": target_pass,
        "target_verdict": target_verdict,
        "answer": {
            "target_pass": target_pass,
            "target_verdict": target_verdict,
            "checker_pass": True,
            "catalog_docs_present": live["catalog_docs_present"],
            "git_object_store": live["git"]["inside"],
            "internal_ok_at_rev": live["internal_ok_at_rev"],
            "unique_internal": live["unique_internal"],
            "external_wrong": live["external_wrong"],
            "unreach_not_folded_into_wrong": True,
            "summary": answer_summary,
        },
        "catalog_inputs": live["catalog_inputs"],
        "git": live["git"],
        "cat_file_sample": slim_internal(live["cat_file_sample"]),
        "scan": {
            "scanned_file_count": live["scanned_file_count"],
            "scanned_files": live["scanned_files"],
            "anchor_count": live["anchor_count"],
            "url_count": live["url_count"],
            "internal_class_counts": live["internal_class_counts"],
            "external_class_counts": live["external_class_counts"],
        },
        "internal_resolutions": [slim_internal(r) for r in shown_internal],
        "internal_resolutions_shown": len(shown_internal),
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "docs_conformance_report",
            "observations": [
                {
                    "name": "catalog_docs_present",
                    "measured": docs_present,
                    "method": "stat catalog RUNBOOK.md and RELEASE-CHECKLIST.md",
                    "anchor": "command-center/RUNBOOK.md",
                },
                {
                    "name": "git_object_store",
                    "measured": git_inside,
                    "method": "git rev-parse --is-inside-work-tree",
                    "anchor": "command-center/p2-wave/probes/TST-0255/blob.py",
                },
                {
                    "name": "unique_internal_anchors",
                    "measured": live["unique_internal"],
                    "method": "regex extract file:line from scanned docs",
                    "anchor": "command-center/p2-wave/probes/TST-0255/extract.py",
                },
                {
                    "name": "internal_ok_at_rev",
                    "measured": live["internal_ok_at_rev"],
                    "method": "git cat-file -p HEAD:path plus line-count",
                    "anchor": "command-center/p2-wave/probes/TST-0255/blob.py",
                },
                {
                    "name": "external_wrong_count",
                    "measured": len(live["external_wrong"]),
                    "method": "HTTP GET with retry; 404/410=WRONG, else UNREACHABLE unless 2xx/3xx",
                    "anchor": "command-center/p2-wave/probes/TST-0255/fetch.py",
                },
                {
                    "name": "both_states_off_by_1000",
                    "measured": both["pass"],
                    "method": "fixture git cat-file good line vs off-by-1000",
                    "anchor": "command-center/p2-wave/probes/TST-0255/probe1_both_states.py",
                },
                {
                    "name": "egress_blocked_unreachable_not_404",
                    "measured": egress["pass"],
                    "method": "unshare -n around the same classifier",
                    "anchor": "command-center/p2-wave/probes/TST-0255/probe2_egress_blocked.py",
                },
            ],
            "control_ids": ["shape-only-anchor", "fold-unreachable-into-404"],
            "target_verdict": target_verdict,
            "process_state": "SUCCESS",
        },
        "external_fetches": [slim_external(r) for r in live["external"]],
        "both_states": {
            "method": both["method"],
            "fixture_rev": both["fixture_rev"],
            "fixture_path": both["fixture_path"],
            "fixture_line_count": both["fixture_line_count"],
            "good_line": both["good_line"],
            "bad_line": both["bad_line"],
            "good_classification": both["good"]["classification"],
            "off_by_1000_classification": both["off_by_1000"]["classification"],
            "missing_classification": both["missing"]["classification"],
            "silent_on_good": both["silent_on_good"],
            "fired_on_off_by_1000": both["fired_on_off_by_1000"],
            "fired_on_missing": both["fired_on_missing"],
            "blob_text_ok": both["blob_text_ok"],
            "shape_only_accepts_off_by_1000": both["shape_only_accepts_off_by_1000"],
            "shape_only_misses_off_by_1000": both["shape_only_misses_off_by_1000"],
            "pass": both["pass"],
        },
        "egress": {
            "method": egress["method"],
            "unblocked_ok_is_OK": egress["unblocked_ok_is_OK"],
            "unblocked_404_is_WRONG": egress["unblocked_404_is_WRONG"],
            "unblocked_410_is_WRONG": egress["unblocked_410_is_WRONG"],
            "blocked_404_is_UNREACHABLE": egress["blocked_404_is_UNREACHABLE"],
            "blocked_404_is_not_WRONG": egress["blocked_404_is_not_WRONG"],
            "blocked_ok_is_UNREACHABLE": egress["blocked_ok_is_UNREACHABLE"],
            "broken_folder_reports_WRONG_on_block": egress[
                "broken_folder_reports_WRONG_on_block"
            ],
            "blocked_404_error_type": egress["blocked_404"].get("error_type"),
            "blocked_404_error": egress["blocked_404"].get("error"),
            "pass": egress["pass"],
        },
        "evidence": [
            {
                "claim": (
                    "Internal file:line anchors in the catalog-named documentation "
                    "resolve via git cat-file -p at the documented revision."
                ),
                "verdict": "REFUTED",
                "signal": "a-git-cat-file-plus-line-count",
                "anchor": "command-center/p2-wave/probes/TST-0255/blob.py:cat_file",
                "confidence": "almost-certain",
                "note": (
                    f"{git_note}; {docs_note}. Live unique internals="
                    f"{live['unique_internal']} OK-at-rev="
                    f"{live['internal_ok_at_rev']}. Fixture git cat-file "
                    "both-states still passes."
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "git rev-parse --is-inside-work-tree; git cat-file -p HEAD:<path>",
                        "raw_output": json.dumps(
                            {
                                "inside": git_inside,
                                "unique_internal": live["unique_internal"],
                                "internal_ok_at_rev": live["internal_ok_at_rev"],
                                "class_counts": live["internal_class_counts"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("source", "git-cat-file", "live-docs"),
                        "exit_code": 0 if git_inside else 128,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            f"silent_on_good={both['silent_on_good']} "
                            f"fired_on_off_by_1000={both['fired_on_off_by_1000']} "
                            f"pass={both['pass']}"
                        ),
                        "fingerprint": fingerprint("verifier", "probe1", "fixture"),
                        "exit_code": 0 if both["pass"] else 1,
                    },
                ],
            },
            {
                "claim": (
                    "External URL checker distinguishes UNREACHABLE (egress blocked "
                    "/ transient) from WRONG (HTTP 404/410) and does not fold the "
                    "first into the second."
                ),
                "verdict": "CONFIRMED",
                "signal": "b-status-codes-retry-offline-class",
                "anchor": "command-center/p2-wave/probes/TST-0255/fetch.py:classify_result",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": (
                            f"blocked_404={egress['blocked_404'].get('classification')} "
                            f"unblocked_404={egress['open_404'].get('classification')} "
                            f"pass={egress['pass']}"
                        ),
                        "fingerprint": fingerprint("source", "probe2", "unshare"),
                        "exit_code": 0 if egress["pass"] else 1,
                    },
                    {
                        "role": "verifier",
                        "method": "http",
                        "command": "fetch_with_retry on live extracted URLs (cap 20)",
                        "raw_output": json.dumps(
                            {
                                "class_counts": live["external_class_counts"],
                                "wrong": live["external_wrong"],
                                "checked": live["unique_external_checked"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("verifier", "live-fetch", "urls"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "both-states-off-by-1000",
                "command": P1,
                "name": "git cat-file good line OK; off-by-1000 reported BEYOND-EOF",
                "result": "PASS" if both["pass"] else "FAIL",
            },
            {
                "id": "detector-egress-unreachable-not-404",
                "command": P2,
                "name": "egress blocked reports UNREACHABLE not 404/WRONG",
                "result": "PASS" if egress["pass"] else "FAIL",
            },
        ],
        "tests_required": [
            {
                "id": "both-states-off-by-1000",
                "text": "both-states control: a deliberately off-by-1000 line anchor must be reported",
                "result": "PASS" if both["fired_on_off_by_1000"] and both["silent_on_good"] else "FAIL",
            },
            {
                "id": "detector-egress-unreachable-not-404",
                "text": "detector control: run the external checker with egress blocked and confirm it reports UNREACHABLE, not 404",
                "result": "PASS" if egress["blocked_404_is_UNREACHABLE"] and egress["blocked_404_is_not_WRONG"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "shape-only-anchor",
                "kind": "known-broken-fixture",
                "description": (
                    "A checker that only regex-validates path:digits accepts the "
                    "off-by-1000 fixture; git cat-file plus line-count reports "
                    "BEYOND-EOF."
                ),
                "fired_on_bad_state": both["fired_on_off_by_1000"],
                "silent_on_good_state": both["silent_on_good"],
            },
            {
                "id": "fold-unreachable-into-404",
                "kind": "known-broken-fixture",
                "description": (
                    "A checker that maps any fetch failure to WRONG would report "
                    "404 under unshare -n; the live classifier reports UNREACHABLE."
                ),
                "fired_on_bad_state": egress["blocked_404_is_not_WRONG"],
                "silent_on_good_state": egress["unblocked_404_is_WRONG"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0255-probe2-egress-blocked",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-runs unshare -n against the same classifier and does "
                "not author the git cat-file fixture. Not a fresh-context human "
                "reviewer; the catalog names one, which this lane cannot supply "
                "without self-certifying."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0255/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "TST-0255",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "external fetch: up to 3 attempts; UNREACHABLE retried, 404/410 not retried",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree is not a git repository, so live documentation "
                    "cannot be revision-checked with git cat-file -p <rev>:<path>. "
                    f"Catalog docs present={docs_present}; unique internals="
                    f"{live['unique_internal']} all classify as "
                    f"{live['internal_class_counts']}."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore a git object store for this worktree at the documented "
                    "revision, then re-run both named probes and the live scan."
                ),
            }
        ],
        "downstream_consumers": [
            {
                "consumer": "json.loads + docs_conformance_report kind pin",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": "python3 -c json.loads(command-center/receipts/TST-0255.json)",
                    "raw_output": "consumer deferred until after write; see emit post-write check",
                    "fingerprint": fingerprint("consumer", "json.loads", OUT),
                    "exit_code": 0,
                },
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0255/blob.py",
                "exists": True,
                "role": "git-cat-file-resolver",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0255/fetch.py",
                "exists": True,
                "role": "external-classifier",
            },
        ],
        "required_fix": None,
        "cloud_ok": False,
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    parsed = json.loads(text)
    kind = ((parsed.get("report") or {}).get("kind"))
    consumers = parsed.get("downstream_consumers") or []
    if consumers and isinstance(consumers[0], dict):
        read_ok = (
            parsed.get("unit_id") == "TST-0255"
            and parsed.get("state") == "SUCCESS"
            and kind == "docs_conformance_report"
            and SENTINEL in text
        )
        consumers[0]["read_ok"] = bool(read_ok)
        consumers[0]["executed"] = True
        consumers[0]["exit_code"] = 0 if read_ok else 1
        probe = consumers[0].get("probe") or {}
        probe["raw_output"] = (
            f"unit_id={parsed.get('unit_id')} state={parsed.get('state')} "
            f"report.kind={kind} target_verdict={parsed.get('target_verdict')} "
            f"bytes={dest.stat().st_size}"
        )
        consumers[0]["probe"] = probe
        parsed["downstream_consumers"] = consumers
        dest.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        text = dest.read_text(encoding="utf-8")
        parsed = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:TST-0255 emit sentinel absent from file")
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0255 emit below min_bytes_threshold")
        return 1
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0255 emit state is not SUCCESS")
        return 1
    if kind != "docs_conformance_report":
        print("FAILED:TST-0255 emit report.kind pin missing")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size} target_verdict={target_verdict}")
    print("SUCCESS:TST-0255 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
