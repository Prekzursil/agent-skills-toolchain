#!/usr/bin/env python3
"""Pack AUD-0023 vulnerability posture snapshot receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline count is on disk (catalog `reviewer_requirement`).
SUCCESS further requires the real Dependabot alert list (not Advisory-DB
fallback). After falsify PASS with Dependabot 403, stay BLOCKED (AUD-0060
pattern). Never stubs SUCCESS. Never invents independent-review.json.

This unit's catalog question explicitly asks for a decay timestamp: "what is
the exact query timestamp after which this result must be re-queried rather
than reused?" The retry_policy says a stored PASS older than 24h must be
re-queried, not reused -- so `report.query_timestamp` / `report.valid_until`
(now + 24h) are load-bearing fields here, not decoration.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0023"
OUT = "command-center/audit/AUD-0023-vuln-posture-snapshot.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0023/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0023/probe1-osv-scan.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0023/probe2-dependabot-alerts.json"
CTL_JSON = "command-center/p2-wave/probes/AUD-0023/control-detector.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0023/probe1-osv-scan.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0023/probe2-dependabot-alerts.raw.txt"
CTL_RAW = "command-center/p2-wave/probes/AUD-0023/control-detector.raw.txt"
FREEZE_SNAPSHOT = "command-center/p2-wave/probes/AUD-0023/pip-freeze-snapshot.txt"
DECAY_HOURS = 24


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline count is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((L.REPO / P1_JSON).read_text(encoding="utf-8"))
    p2 = json.loads((L.REPO / P2_JSON).read_text(encoding="utf-8"))
    ctl = json.loads((L.REPO / CTL_JSON).read_text(encoding="utf-8"))
    raw1 = (L.REPO / P1_RAW).read_text(encoding="utf-8")
    raw2 = (L.REPO / P2_RAW).read_text(encoding="utf-8")
    raw_ctl = (L.REPO / CTL_RAW).read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = p1.get("started_at") or "2026-09-07T22:38:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- decay timestamp: the load-bearing answer to this unit's question ---
    query_timestamp = started
    query_dt = datetime.strptime(query_timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    valid_until = (query_dt + timedelta(hours=DECAY_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    p1_ok = bool(p1.get("ok"))
    p2_fallback_ok = bool(p2.get("advisory_db_cross_check_ok"))
    dependabot_real_ok = bool(p2.get("dependabot_alert_ok"))
    ctl_ok = bool(ctl.get("ok"))

    distinct_vuln_count = int(p1.get("distinct_vuln_id_count") or 0)
    affected_pkg_count = int(p1.get("affected_package_count") or 0)
    severity_hist = p1.get("severity_histogram") or {}
    high_count = int(severity_hist.get("HIGH") or 0)
    moderate_count = int(severity_hist.get("MODERATE") or 0)
    low_count = int(severity_hist.get("LOW") or 0)
    lockfile_target_count = len((p1.get("targets") or {}).get("lockfiles") or [])
    requirements_target_count = len((p1.get("targets") or {}).get("requirements") or [])
    pip_freeze_pkg_count = int(p1.get("pip_freeze_package_count") or 0)

    real_dependabot = p2.get("real_dependabot_alert_probe") or {}
    real_http_status = real_dependabot.get("http_status")
    corroborated_count = int(p2.get("advisory_db_corroborated_package_count") or 0)
    cross_check_sample = int(p2.get("advisory_db_cross_check_sample_size") or 0)

    common_ghsa = list(ctl.get("common_ghsa_ids_bad") or [])

    residual_dependabot = not dependabot_real_ok

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(P1_JSON, "supporting"),
        L.art(P2_JSON, "supporting"),
        L.art(CTL_JSON, "control"),
        L.art(P1_RAW, "log"),
        L.art(P2_RAW, "log"),
        L.art(CTL_RAW, "log"),
        L.art(FREEZE_SNAPSHOT, "supporting"),
        L.art(
            "command-center/p2-wave/probes/AUD-0023/probe1_osv_scan.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0023/probe2_dependabot_alerts.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0023/detector_control.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0023/fixtures/known-vulnerable-requirements.txt",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0023/fixtures/clean-requirements.txt",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0023/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which dependencies in the closure carry a known advisory today, at "
        "what severity, and what is the exact query timestamp after which "
        "this result must be re-queried rather than reused?"
    )
    headline = (
        f"osv-scanner over {lockfile_target_count} committed lockfile(s), "
        f"{requirements_target_count} committed requirements*.txt manifest(s), "
        f"and a {pip_freeze_pkg_count}-package pip-freeze snapshot of the "
        f"AUD-0022 installed Python closure: {distinct_vuln_count} distinct "
        f"advisory id(s) across {affected_pkg_count} affected package(s) "
        f"(severity histogram HIGH={high_count} MODERATE={moderate_count} "
        f"LOW={low_count}). Real per-repo Dependabot alert list "
        f"(GET /repos/.../dependabot/alerts) returned HTTP "
        f"{real_http_status} dependabot_real_ok={dependabot_real_ok}; as a "
        "labeled FALLBACK, the public GitHub Security Advisories API "
        f"corroborated {corroborated_count}/{cross_check_sample} sampled "
        f"affected packages. query_timestamp={query_timestamp}; per "
        f"retry_policy this snapshot decays and must be re-queried, not "
        f"reused, after valid_until={valid_until} ({DECAY_HOURS}h)."
    )

    # audit-finding SUCCESS forbids open P0/P1 defects. Catalog evidence names
    # the real per-repo Dependabot alert list as probe 2. After falsify PASS
    # that confirms the 403, keep BLOCKED (AUD-0060/AUD-0056 pattern) rather
    # than inventing SUCCESS with an Advisory-DB fallback standing in for the
    # literal alert list. SUCCESS only when review PASS + dependabot_real_ok.
    dependabot_defect = {
        "id": "AUD-0023-D-DEPENDABOT-403",
        "severity": "P1",
        "status": "open" if residual_dependabot else "resolved",
        "summary": (
            f"Real GET repos/.../dependabot/alerts returned HTTP "
            f"{real_http_status} ('Resource not accessible by integration'); "
            "second independent source for the real repo closure is unresolved "
            "-- the Advisory-DB API was used only as a labeled fallback and "
            f"only for the {cross_check_sample}-package sample and the fixture "
            "control, never invented as the literal alert list."
            if residual_dependabot
            else "Real Dependabot alert list answered."
        ),
    }
    scope_defect = {
        "id": "AUD-0023-D-SCOPE",
        "severity": "P3",
        "status": "open",
        "summary": (
            "Python closure has no committed lockfile in this repo "
            "(no poetry.lock/Pipfile.lock); probe1 substitutes a live "
            "pip-freeze snapshot of the interpreter that ran AUD-0022's "
            "probe2. This is the same closure, not a narrower one, but it "
            "is an environment snapshot rather than a committed artifact -- "
            "re-running on a different machine could measure a different set."
        ),
    }

    if success and not residual_dependabot:
        reviewer = {
            "reviewer_id": rev.get("reviewer_id")
            or "fresh-context-claude-independent-reviewer-AUD-0023",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0023 distinct_vuln_id_count={distinct_vuln_count} "
            f"affected_package_count={affected_pkg_count} "
            f"query_timestamp={query_timestamp} valid_until={valid_until}"
        )
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0023-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0023/independent-review.json"
                ),
            },
            dependabot_defect,
            scope_defect,
        ]
    elif success and residual_dependabot:
        # Review PASSed and confirmed Dependabot 403. Do not invent SUCCESS
        # (schema + catalog probe-2 gate). Record reviewer PASS; stay BLOCKED.
        reviewer = {
            "reviewer_id": rev.get("reviewer_id")
            or "fresh-context-claude-independent-reviewer-AUD-0023",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0023 vuln-posture snapshot measured "
            f"distinct_vuln_id_count={distinct_vuln_count} "
            f"affected_package_count={affected_pkg_count} "
            f"severity(HIGH={high_count},MODERATE={moderate_count},LOW={low_count}) "
            f"dependabot_real_ok={dependabot_real_ok} "
            f"advisory_db_fallback_ok={p2_fallback_ok} control_ok={ctl_ok} "
            f"query_timestamp={query_timestamp} valid_until={valid_until}; "
            "blocked-on-dependabot-alerts-403"
        )
        failure = {
            "classification": [
                "egress-blocked",
                "detector-failure",
                "credential-absent",
            ],
            "reason": (
                "Independent fresh-context Claude falsify review PASS confirmed "
                f"headline counts (distinct_vuln_id_count={distinct_vuln_count}, "
                f"affected_package_count={affected_pkg_count}, severity "
                f"HIGH={high_count}/MODERATE={moderate_count}/LOW={low_count}) "
                f"and Dependabot HTTP {real_http_status}. Catalog evidence "
                "names the real per-repo Dependabot alert list as probe 2; "
                "the Advisory-DB fallback is not that list. Receipt stays "
                "BLOCKED (no stub SUCCESS)."
            ),
            "diagnostic_tail": (
                f"distinct_vuln_id_count={distinct_vuln_count} "
                f"affected_package_count={affected_pkg_count} "
                f"dependabot_real_ok={dependabot_real_ok} "
                f"http_status={real_http_status} "
                f"advisory_db_fallback_ok={p2_fallback_ok} control_ok={ctl_ok} "
                f"query_timestamp={query_timestamp} valid_until={valid_until} "
                "reviewer=PASS"
            ),
            "blocked_on": (
                "Grant the executing token security_events (or Dependabot "
                "alerts) read scope so probe2 can query the real per-repo "
                "alert list, then re-pack; do not invent SUCCESS while "
                f"dependabot_real_ok={dependabot_real_ok}."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0023/probe1_osv_scan.py",
                    f"distinct_vuln_id_count={distinct_vuln_count} "
                    f"affected_package_count={affected_pkg_count}",
                    0 if p1_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "PASS",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-after-falsify-PASS-dependabot-403"
        defects = [
            {
                "id": "AUD-0023-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded; "
                    "receipt left BLOCKED on Dependabot 403"
                ),
            },
            dependabot_defect,
            scope_defect,
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not "
                "seen this unit's transcript; the reviewer must try to FALSIFY "
                "the headline count before PASS, not re-read the artifact. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0023 vuln-posture snapshot measured "
            f"distinct_vuln_id_count={distinct_vuln_count} "
            f"affected_package_count={affected_pkg_count} "
            f"severity(HIGH={high_count},MODERATE={moderate_count},LOW={low_count}) "
            f"dependabot_real_ok={dependabot_real_ok} "
            f"advisory_db_fallback_ok={p2_fallback_ok} control_ok={ctl_ok} "
            f"query_timestamp={query_timestamp} valid_until={valid_until}; "
            "blocked-on-independent-review"
        )
        classifications = ["blocked-on-independent-review", "detector-failure"]
        if residual_dependabot:
            classifications.append("egress-blocked")
        failure = {
            "classification": classifications,
            "reason": (
                f"Named probes completed (probe1 osv-scanner ok={p1_ok} over "
                f"{lockfile_target_count + requirements_target_count} real "
                f"manifests + a {pip_freeze_pkg_count}-package pip-freeze "
                f"snapshot; probe2 advisory-DB fallback ok={p2_fallback_ok}; "
                f"detector control ok={ctl_ok}), but catalog "
                "reviewer_requirement is unmet."
                + (
                    " Residual: the real per-repo Dependabot alert list "
                    f"returned HTTP {real_http_status} ('Resource not "
                    "accessible by integration'); this token lacks the "
                    "security_events scope. The headline's second source is "
                    "therefore the public GitHub Security Advisories API "
                    "fallback (same underlying database), not the literal "
                    "per-repo alert list the catalog names -- not invented "
                    "as if it were."
                    if residual_dependabot
                    else ""
                )
            ),
            "diagnostic_tail": (
                f"distinct_vuln_id_count={distinct_vuln_count} "
                f"affected_package_count={affected_pkg_count} "
                f"dependabot_real_ok={dependabot_real_ok} "
                f"http_status={real_http_status} "
                f"advisory_db_fallback_ok={p2_fallback_ok} control_ok={ctl_ok} "
                f"query_timestamp={query_timestamp} valid_until={valid_until} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "(1) Dispatch one fresh-context Claude reviewer who has not "
                "seen this transcript to try to FALSIFY the headline "
                "distinct_vuln_id_count / affected_package_count / severity "
                "histogram before PASS. (2) Grant the executing token "
                "security_events (or Dependabot alerts) read scope so probe2 "
                "can query the real per-repo alert list instead of the "
                "Advisory-DB fallback."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0023/probe1_osv_scan.py",
                    f"distinct_vuln_id_count={distinct_vuln_count} "
                    f"affected_package_count={affected_pkg_count}",
                    0 if p1_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0023-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            dependabot_defect,
            scope_defect,
        ]

    # Seed non-empty downstream_consumers before first schema validate.
    seeded_consumers = [
        {
            "consumer": "json.loads + schema resolver",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": L.probe(
                "source",
                "schema-validate",
                "python3 -B command-center/p2-wave/probes/AUD-0023/_pack_receipt.py",
                f"state={state}",
                0,
            ),
        }
    ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0023",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Probe 1 osv-scanner over the repo's real committed "
                    f"lockfiles/manifests ({lockfile_target_count} "
                    f"package-lock.json + {requirements_target_count} "
                    f"requirements*.txt, excluding other units' fixture "
                    f"dirs) plus a {pip_freeze_pkg_count}-package pip-freeze "
                    "snapshot of the AUD-0022 installed Python closure "
                    f"(no committed Python lockfile exists in this repo): "
                    f"{distinct_vuln_count} distinct advisory id(s) across "
                    f"{affected_pkg_count} affected package(s); severity "
                    f"histogram={severity_hist}. probe1_ok={p1_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0023/"
                        "probe1_osv_scan.py",
                        raw1[-8000:],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-osv-scan.json",
                        json.dumps(
                            {
                                "distinct_vuln_id_count": distinct_vuln_count,
                                "affected_package_count": affected_pkg_count,
                                "severity_histogram": severity_hist,
                                "ok": p1_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 GitHub Dependabot alert list: real endpoint "
                    f"GET repos/.../dependabot/alerts returned HTTP "
                    f"{real_http_status} dependabot_real_ok={dependabot_real_ok} "
                    "(never retried into a fake success). As a labeled "
                    "FALLBACK (same underlying advisory database, different "
                    "scope requirement), the public GitHub Security "
                    f"Advisories API corroborated {corroborated_count}/"
                    f"{cross_check_sample} sampled probe1-flagged packages. "
                    f"advisory_db_fallback_ok={p2_fallback_ok}."
                ),
                "CONFIRMED" if p2_fallback_ok else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0023/"
                        "probe2_dependabot_alerts.py",
                        raw2[-8000:],
                        0 if p2_fallback_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-dependabot-alerts.json",
                        json.dumps(
                            {
                                "dependabot_real_ok": dependabot_real_ok,
                                "http_status": real_http_status,
                                "advisory_db_fallback_ok": p2_fallback_ok,
                                "corroborated_count": corroborated_count,
                                "sample_size": cross_check_sample,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain" if p2_fallback_ok else "refuted",
            ),
            L.evidence(
                (
                    "Detector control (tests_required): fixture "
                    "urllib3==1.24.1 (known-bad, multiple published GHSAs) "
                    "vs six==1.16.0 (clean) run through BOTH sources -- "
                    f"source A (osv-scanner) fires_on_bad="
                    f"{ctl.get('a_fires_on_bad')} silent_on_good="
                    f"{ctl.get('a_silent_on_good')}; source B (GitHub "
                    f"Advisory DB) fires_on_bad={ctl.get('b_fires_on_bad')} "
                    f"silent_on_good={ctl.get('b_silent_on_good')}; "
                    f"{len(common_ghsa)} GHSA id(s) common to both sources "
                    f"on the known-bad case (cross_source_corroborated="
                    f"{ctl.get('cross_source_corroborated')}). control_ok={ctl_ok}. "
                    "No live lockfile in the repo was mutated."
                ),
                "CONFIRMED" if ctl_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0023/"
                        "detector_control.py",
                        raw_ctl,
                        0 if ctl_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read control-detector.json",
                        json.dumps(
                            {
                                "common_ghsa_ids_bad": common_ghsa,
                                "cross_source_corroborated": ctl.get(
                                    "cross_source_corroborated"
                                ),
                                "ok": ctl_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0023-detector-fires-on-known-bad",
                "name": (
                    "tests_required: both sources report the known-published "
                    "advisory on urllib3==1.24.1"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0023/"
                    "detector_control.py"
                ),
                "result": "PASS"
                if ctl.get("a_fires_on_bad") and ctl.get("b_fires_on_bad")
                else "FAIL",
                "assertions": 2,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0023-detector-silent-on-clean",
                "name": (
                    "control precondition: both sources are silent on the "
                    "clean six==1.16.0 fixture (not always-fires)"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0023/"
                    "detector_control.py"
                ),
                "result": "PASS"
                if ctl.get("a_silent_on_good") and ctl.get("b_silent_on_good")
                else "FAIL",
                "assertions": 2,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0023-cross-source-corroboration",
                "name": (
                    "the two sources agree on at least one GHSA id for the "
                    "known-bad fixture (not just 'both found something')"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0023/"
                    "detector_control.py"
                ),
                "result": "PASS" if common_ghsa else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0023-C1",
                "known-broken-fixture",
                (
                    "A pinned package version with a known published "
                    "advisory (urllib3==1.24.1) must make BOTH osv-scanner "
                    "and the GitHub Advisory DB fire; a silent source "
                    "measures nothing."
                ),
                True,
                True,
                bad=f"a_bad_count={ctl.get('source_a_osv_scanner', {}).get('bad', {}).get('advisory_count')} "
                f"b_bad_count={ctl.get('source_b_advisory_db', {}).get('bad', {}).get('advisory_count')}",
                good="both sources silent on six==1.16.0",
            ),
            L.control(
                "AUD0023-C2",
                "other",
                (
                    "A clean, currently-unflagged pinned version "
                    "(six==1.16.0) must report zero advisories from both "
                    "sources (proves the detector is not always-fires)."
                ),
                True,
                True,
                bad="would be >0 if detector always fires",
                good=f"a_good_count={ctl.get('source_a_osv_scanner', {}).get('good', {}).get('advisory_count')} "
                f"b_good_count={ctl.get('source_b_advisory_db', {}).get('good', {}).get('advisory_count')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": seeded_consumers,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                f"re-run rather than retry: this result decays after "
                f"{DECAY_HOURS}h ({valid_until}); a stored PASS older than "
                f"that must be re-queried, not reused. Retrying against a "
                "missing input is a detector failure, not a transient."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether the real per-repo Dependabot alert list "
                    f"(HTTP {real_http_status} this run) would report a "
                    "different vulnerability set than the "
                    f"{distinct_vuln_count} osv-scanner findings once the "
                    "executing token is granted security_events scope."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Grant Dependabot alert read scope to the token, re-run "
                    "probe2_dependabot_alerts.py, and byte-compare its "
                    "alert_count and package list against probe1's "
                    f"{affected_pkg_count} affected packages."
                ),
            },
            {
                "claim": (
                    "Whether the pip-freeze snapshot of THIS interpreter "
                    "matches the exact closure any other execution "
                    "substrate would install for the same repo (no "
                    "committed Python lockfile exists to pin it)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Commit a poetry.lock/Pipfile.lock (or pip-compile "
                    "output) for the Python surfaces, re-run probe1 against "
                    "the committed lockfile instead of a live freeze, and "
                    "diff package versions."
                ),
            },
            {
                "claim": (
                    f"Whether the {affected_pkg_count} affected packages "
                    "found are all reachable at runtime (vs. dev-only or "
                    "unused transitive deps) -- severity here is per-CVE, "
                    "not per-exploitability-in-this-repo."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Cross-reference each affected package against "
                    "AUD-0022's installed-use edge graph to confirm it is "
                    "actually imported by a running surface, not merely "
                    "installed."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0023-C1", "AUD0023-C2"],
            "query_timestamp": query_timestamp,
            "valid_until": valid_until,
            "decay_hours": DECAY_HOURS,
            "observations": [
                {
                    "name": "distinct_vuln_id_count",
                    "measured": distinct_vuln_count,
                    "method": "osv-scanner over real lockfiles + pip-freeze closure",
                    "anchor": P1_JSON,
                },
                {
                    "name": "affected_package_count",
                    "measured": affected_pkg_count,
                    "method": "osv-scanner packages with >=1 vulnerability",
                    "anchor": P1_JSON,
                },
                {
                    "name": "severity_high_count",
                    "measured": high_count,
                    "method": "osv-scanner database_specific.severity==HIGH",
                    "anchor": P1_JSON,
                },
                {
                    "name": "severity_moderate_count",
                    "measured": moderate_count,
                    "method": "osv-scanner database_specific.severity==MODERATE",
                    "anchor": P1_JSON,
                },
                {
                    "name": "severity_low_count",
                    "measured": low_count,
                    "method": "osv-scanner database_specific.severity==LOW",
                    "anchor": P1_JSON,
                },
                {
                    "name": "dependabot_real_endpoint_http_status",
                    "measured": real_http_status,
                    "method": "gh api repos/.../dependabot/alerts",
                    "anchor": P2_RAW,
                },
                {
                    "name": "advisory_db_fallback_corroborated_count",
                    "measured": corroborated_count,
                    "method": (
                        f"GitHub Advisory DB cross-check on "
                        f"{cross_check_sample}-package sample of probe1's "
                        "affected packages"
                    ),
                    "anchor": P2_JSON,
                },
                {
                    "name": "detector_control_cross_source_ghsa_overlap",
                    "measured": len(common_ghsa),
                    "method": "GHSA ids common to both sources on urllib3==1.24.1",
                    "anchor": CTL_JSON,
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "query_timestamp": query_timestamp,
            "valid_until": valid_until,
            "decay_hours": DECAY_HOURS,
            "headline_counts": {
                "distinct_vuln_id_count": distinct_vuln_count,
                "affected_package_count": affected_pkg_count,
                "severity_histogram": severity_hist,
            },
            "probe1_summary": {
                "lockfile_target_count": lockfile_target_count,
                "requirements_target_count": requirements_target_count,
                "pip_freeze_package_count": pip_freeze_pkg_count,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "dependabot_real_ok": dependabot_real_ok,
                "dependabot_real_http_status": real_http_status,
                "advisory_db_fallback_ok": p2_fallback_ok,
                "advisory_db_corroborated_count": corroborated_count,
                "advisory_db_sample_size": cross_check_sample,
            },
            "control": {
                "common_ghsa_ids_bad": common_ghsa,
                "ok": ctl_ok,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        L.REPO / P1_JSON,
        L.REPO / P2_JSON,
        L.REPO / CTL_JSON,
        L.REPO / P1_RAW,
        L.REPO / P2_RAW,
        L.REPO / CTL_RAW,
        L.REPO / FREEZE_SNAPSHOT,
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0023 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
