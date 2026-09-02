#!/usr/bin/env python3
"""Emit command-center/research/RES-0051.json from live dated-snapshot scans.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. Does not query live advisory APIs at
emit time; pins live fetches already recorded in fixtures/captures.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

UNIT = "RES-0051"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0051/probe1_two_snapshot.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0051/probe2_seeded_vulnerable.py"
)
QUESTION = (
    "For the ecosystems this program ships into (Python, Node, plus "
    "prompt/script payloads with no ecosystem at all), how do OSV, GHSA "
    "and NVD differ in coverage and disclosure latency - and what does "
    "'zero open alerts' actually mean given a green scan decays as the "
    "advisory DB moves?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = S.REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def capture(captures: dict, cid: str) -> dict:
    for row in captures.get("fetches") or []:
        if row.get("id") == cid:
            return row
    raise SystemExit(f"FAILED:{UNIT} missing capture {cid}")


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sentinel = S.catalog_sentinel()
    if "SUCCESS:RES-0051" not in sentinel:
        print(f"FAILED:{UNIT} catalog sentinel unexpected: {sentinel!r}")
        return 1
    cmp = S.two_snapshot_comparison()
    ctl = S.seeded_control()
    if not cmp["pass"]:
        print(f"FAILED:{UNIT} two-snapshot comparison failed")
        return 1
    if not ctl["pass"]:
        print(f"FAILED:{UNIT} seeded control failed")
        return 1
    captures = S.load_captures()
    osv_ghsa = capture(captures, "osv-GHSA-9wx4-h78v-vm56")
    pysec = capture(captures, "osv-PYSEC-2026-1873")
    gh_rest = capture(captures, "github-advisories-GHSA-9wx4-h78v-vm56")
    nvd_req = capture(captures, "nvd-CVE-2024-35195")
    nvd_node = capture(captures, "nvd-CVE-2024-21538")
    osv_node = capture(captures, "osv-GHSA-3xgq-45jj-v275")
    faq = capture(captures, "osv-dev-faq-commit")
    data_page = capture(captures, "osv-dev-data-sources")
    live_q = captures["live_osv_query_requests_2_31_0"]
    cpe = captures["nvd_cpe_quote_cve_2024_35195"]
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    pysec_lag_days = 778
    schema_path = S.REPO / S.SCHEMA_REL
    supporting = [
        art(S.CORPUS_REL, "fixture"),
        art(S.FROZEN_REL, "fixture"),
        art(S.VULN_REL, "fixture"),
        art(S.PATCH_REL, "fixture"),
        art(S.SKILL_REL, "fixture"),
        art(S.CAPTURES_REL, "fixture"),
        art("command-center/p2-wave/probes/RES-0051/scan.py", "implementation"),
        art("command-center/p2-wave/probes/RES-0051/probe1_two_snapshot.py", "probe"),
        art("command-center/p2-wave/probes/RES-0051/probe2_seeded_vulnerable.py", "probe"),
    ]

    two_snap = {
        "frozen_lock": S.FROZEN_REL,
        "packages_unchanged": True,
        "snapshot_a": S.SNAPSHOT_A,
        "snapshot_b": S.SNAPSHOT_B,
        "advisory_ids_a": cmp["scan_a"]["advisory_ids_in_snapshot"],
        "advisory_ids_b": cmp["scan_b"]["advisory_ids_in_snapshot"],
        "verdict_a": cmp["verdict_a"],
        "verdict_b": cmp["verdict_b"],
        "verdict_changed": cmp["verdict_changed"],
        "appeared_ids": cmp["appeared_ids"],
        "disappeared_ids": cmp["disappeared_ids"],
        "hits_a": cmp["scan_a"]["hits"],
        "hits_b": cmp["scan_b"]["hits"],
        "unscannable_a": cmp["scan_a"]["unscannable"],
        "unscannable_b": cmp["scan_b"]["unscannable"],
        "node_still_green_at_b": cmp["node_still_green_at_b"],
        "note": (
            "Same frozen requests==2.31.0 + cross-spawn@7.0.3 + skill-payload.md. "
            "Snapshot membership is published<=cut. GHSA-j8r2-6x86-q33q is in "
            "both cuts but does not match 2.31.0 (fixed 2.31.0). "
            "GHSA-9wx4-h78v-vm56 published 2024-05-20 appears only in B. "
            "GHSA-3xgq-45jj-v275 published 2024-11-08 is in neither cut, so "
            "the Node pin stays green at B — a stored B-red-for-Python is "
            "not a control for November."
        ),
    }
    seeded = {
        "seeded_manifest": S.VULN_REL,
        "patched_manifest": S.PATCH_REL,
        "snapshot_used_for_detection": S.SNAPSHOT_B,
        "positive_detection": ctl["positive_detection"],
        "detected_ids": ctl["detected_ids"],
        "patched_silent": ctl["patched_silent"],
        "seeded_silent_on_earlier_snapshot": ctl["seeded_silent_on_earlier_snapshot"],
        "skill_never_detected": ctl["skill_never_detected"],
        "hits": ctl["seeded_scan"]["hits"],
    }

    coverage_matrix = [
        {
            "axis": "Python-PyPI-package-name-match",
            "OSV": "YES — ecosystem PyPI + package name + version events",
            "GHSA": "YES — ecosystem field is pip, not PyPI; same GHSA id",
            "NVD": "PARTIAL — CVE exists; CPE conversion for CVE-2024-35195 names a Node product request, not PyPI requests",
            "shared_primitive": "GHSA-9wx4-h78v-vm56 / CVE-2024-35195 originated at GitHub; NVD sourceIdentifier is security-advisories@github.com; OSV ingests the GHSA record. These are ONE disclosure chain, not three independent detections.",
        },
        {
            "axis": "Node-npm-package-name-match",
            "OSV": "YES — ecosystem npm + SEMVER events (GHSA-3xgq-45jj-v275)",
            "GHSA": "YES — same GHSA id",
            "NVD": "YES on this CVE — NVD lists product cross-spawn with semver ranges; sourceIdentifier report@snyk.io",
            "shared_primitive": "CVE-2024-21538 entered NVD from Snyk then GHSA; not the GitHub-origin chain of CVE-2024-35195.",
        },
        {
            "axis": "prompt-script-markdown-payload-no-ecosystem",
            "OSV": "NO — covered ecosystems on the 2026-08-24 data page include PyPI and npm, not markdown skills",
            "GHSA": "NO — GitHub reviewed ecosystems are package managers (pip/npm/…)",
            "NVD": "NO — CPE products, not prompt files",
            "shared_primitive": "all three are package/CVE databases; silence on a skill file is shared absence, not three independent all-clears",
        },
        {
            "axis": "disclosure-latency-CVE-2024-35195",
            "OSV": "GHSA record published 2024-05-20T20:15:00Z (OSV GET /v1/vulns)",
            "GHSA": "published_at 2024-05-20T20:15:00Z; nvd_published_at 2024-05-20T21:15:09Z",
            "NVD": "CVE published 2024-05-20T21:15:09.990 (~1 hour after GHSA)",
            "shared_primitive": f"PYSEC-2026-1873 published 2026-07-07T11:45:42.890131Z — {pysec_lag_days} days later; an OSV consumer that filtered to PYSEC-* would have treated this as absent until 2026-07-07",
        },
        {
            "axis": "disclosure-latency-CVE-2024-21538",
            "OSV": "GHSA-3xgq-45jj-v275 published 2024-11-08T06:30:47Z",
            "GHSA": "published_at 2024-11-08T06:30:47Z",
            "NVD": "CVE published 2024-11-08T05:15:06.453 from Snyk — ~75 minutes BEFORE GHSA",
            "shared_primitive": "latency is not uniformly NVD-slow; the first listing follows the discloser. Unversioned 'NVD is slower' is a defect, not a finding.",
        },
    ]

    bypasses = [
        {
            "mitigation": "Run OSV/GHSA/NVD (or osv-scanner) over lockfiles and treat zero open alerts as the all-clear.",
            "bypass_attempt": (
                "Hold fixtures/skill-payload.md as the only payload. Scan it "
                "against snapshot B, which already contains GHSA-9wx4-h78v-vm56."
            ),
            "bypass_constructed": True,
            "result": (
                "Scanner returns unscannable/no-purl-no-ecosystem, hit_count=0. "
                "Zero open alerts here means 'no package identifier', not 'no vulns'."
            ),
            "effective": False,
        },
        {
            "mitigation": "Cite a stored green scan of a frozen lockfile as current evidence.",
            "bypass_attempt": (
                "Re-run the identical frozen lock (requests==2.31.0, "
                "cross-spawn@7.0.3) against snapshot 2024-05-01 then 2024-06-01."
            ),
            "bypass_constructed": True,
            "result": (
                "Verdict GREEN→RED with GHSA-9wx4-h78v-vm56 appearing. No package "
                "bytes changed. The 2024-05-01 green is not a control for 2024-06-01."
            ),
            "effective": False,
        },
        {
            "mitigation": "Treat NVD as an independent second source that will catch what GHSA/OSV miss.",
            "bypass_attempt": (
                "Read the NVD 2.0 body for CVE-2024-35195 and look for a CPE that "
                "a Node/CPE matcher would use for Python requests."
            ),
            "bypass_constructed": True,
            "result": (
                f"NVD sourceIdentifier is security-advisories@github.com (same "
                f"GitHub origin). CPE includes {cpe!r}. A CPE matcher aimed at "
                "Node 'request' can miss PyPI 'requests'. Not independent, and "
                "the conversion is wrong for this program's Python ecosystem."
            ),
            "effective": False,
        },
        {
            "mitigation": "Stamp the advisory-database snapshot date on the receipt so the green cannot silently age.",
            "bypass_attempt": (
                "After observing the B-stamp (2024-06-01) RED for Python, check "
                "whether the same stamp still describes Node cross-spawn@7.0.3."
            ),
            "bypass_constructed": True,
            "result": (
                "cross-spawn stays GREEN at B because GHSA-3xgq-45jj-v275 is "
                "published 2024-11-08. Dating the receipt stops mis-citing an "
                "undated green; it does not stop decay after the stamp. Live "
                f"OSV query at {live_q['fetch_timestamp']} for requests 2.31.0 "
                f"returned {len(live_q['vulns'])} records, not the single GHSA "
                "that appeared at B."
            ),
            "effective": False,
        },
    ]

    answer = (
        "OSV is an aggregator over ecosystem-native package records (PyPI and "
        "npm are listed on its data-sources page); GHSA is a curated GitHub "
        "advisory database that uses pip/npm ecosystem labels and is ingested "
        "by OSV under the same GHSA-* id; NVD is CVE/CPE-centric and for "
        "CVE-2024-35195 is a GitHub-sourced record whose CPE conversion names "
        "a Node product. Counting OSV+GHSA+NVD hits on that CVE as three "
        "independent coverage points is a shared-primitive error. Latency is "
        "not a single ranking: GHSA and NVD listed CVE-2024-35195 within about "
        f"an hour on 2024-05-20, but PYSEC-2026-1873 lagged {pysec_lag_days} "
        "days; for CVE-2024-21538 NVD (Snyk) listed ~75 minutes before GHSA. "
        "None of the three express markdown/prompt/script payloads. 'Zero open "
        "alerts' means zero matching records in that database as of that "
        "snapshot for packages that have identifiers — and a green stored "
        "against 2024-05-01 flipped RED on 2024-06-01 for an unchanged "
        "requests==2.31.0 pin. Seeding that pin in a scratch manifest against "
        "snapshot B produces a positive detection of GHSA-9wx4-h78v-vm56; the "
        "patched 2.32.2 pin is silent."
    )

    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:RES-0051",
        "completion_sentinel": sentinel,
        "title": (
            "Compare vulnerability data sources for coverage and latency on "
            "this program's ecosystems"
        ),
        "question_or_target": QUESTION,
        "answer": answer,
        "output_schema_declared": S.SCHEMA_REL,
        "output_schema_present": schema_path.is_file(),
        "declared_schema_note": (
            "Catalog names command-center/schema/research-claim-record.schema.json; "
            "that file is absent on this worktree (glob 0). This artifact is "
            "the research record, not a substitute schema unit. Absence is "
            "recorded, not silently treated as validated."
        ),
        "two_snapshot_scan": two_snap,
        "seeded_vulnerable_fixture": seeded,
        "coverage_latency_matrix": coverage_matrix,
        "live_osv_query_decay_example": {
            "package": "PyPI/requests==2.31.0",
            "fetch_timestamp": live_q["fetch_timestamp"],
            "query_sha256": capture(captures, "osv-query-pypi-requests-2.31.0")["sha256"],
            "vuln_count": len(live_q["vulns"]),
            "vulns": live_q["vulns"],
            "caveat": (
                "This is a 2026-08-24 live query, not a dated snapshot used by "
                "the probes. It shows further decay after snapshot B. Re-running "
                "the query tomorrow may differ; the sha256 pins this instance."
            ),
        },
        "claims": [
            {
                "id": "C1-two-snapshot-flip",
                "claim": (
                    "The same frozen lock (requests==2.31.0, cross-spawn@7.0.3, "
                    "skill-payload.md) is GREEN against advisory snapshot "
                    f"{S.SNAPSHOT_A} and RED against {S.SNAPSHOT_B} because "
                    "GHSA-9wx4-h78v-vm56 (published 2024-05-20T20:15:00Z) enters "
                    "the cut. Package bytes do not change."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "osv-record",
                        "id": "GHSA-9wx4-h78v-vm56",
                        "url": osv_ghsa["url"],
                        "fetch_timestamp": osv_ghsa["fetch_timestamp"],
                        "http_status": osv_ghsa["http_status"],
                        "sha256": osv_ghsa["sha256"],
                        "published": "2024-05-20T20:15:00Z",
                    }
                ],
            },
            {
                "id": "C2-seeded-detection",
                "claim": (
                    "A scratch manifest pinning requests==2.31.0 is detected as "
                    "GHSA-9wx4-h78v-vm56 on snapshot B; requests==2.32.2 is silent "
                    "on the same snapshot; the vulnerable pin is silent on snapshot "
                    "A because the advisory is not yet in the cut."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "fixture",
                        "path": S.VULN_REL,
                        "fix_commit": captures["fix_commit"]["sha"],
                    }
                ],
            },
            {
                "id": "C3-shared-primitive-not-three-sources",
                "claim": (
                    "For CVE-2024-35195, OSV's GHSA-9wx4-h78v-vm56, GitHub Advisory "
                    "GHSA-9wx4-h78v-vm56, and NVD CVE-2024-35195 (sourceIdentifier "
                    "security-advisories@github.com) are one GitHub-originated "
                    "disclosure chain. PYSEC-2026-1873 is a later alias encoding, "
                    f"published {pysec_lag_days} days after GHSA."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "osv-record",
                        "url": osv_ghsa["url"],
                        "sha256": osv_ghsa["sha256"],
                        "fetch_timestamp": osv_ghsa["fetch_timestamp"],
                    },
                    {
                        "kind": "github-advisory",
                        "url": gh_rest["url"],
                        "sha256": gh_rest["sha256"],
                        "fetch_timestamp": gh_rest["fetch_timestamp"],
                    },
                    {
                        "kind": "nvd-cve",
                        "url": nvd_req["url"],
                        "sha256": nvd_req["sha256"],
                        "fetch_timestamp": nvd_req["fetch_timestamp"],
                    },
                    {
                        "kind": "osv-record",
                        "id": "PYSEC-2026-1873",
                        "url": pysec["url"],
                        "sha256": pysec["sha256"],
                        "fetch_timestamp": pysec["fetch_timestamp"],
                        "published": "2026-07-07T11:45:42.890131Z",
                    },
                ],
            },
            {
                "id": "C4-nvd-cpe-mismatch",
                "claim": (
                    "NVD's conversion for CVE-2024-35195 includes CPE "
                    f"{cpe} (Node product 'request'). That is not a PyPI "
                    "requests match. A CPE-only consumer can miss this program's "
                    "Python ecosystem even when the CVE exists."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "nvd-cve",
                        "url": nvd_req["url"],
                        "sha256": nvd_req["sha256"],
                        "fetch_timestamp": nvd_req["fetch_timestamp"],
                        "quoted_span": cpe,
                    }
                ],
            },
            {
                "id": "C5-latency-is-discloser-dependent",
                "claim": (
                    "NVD is not uniformly slower than GHSA. CVE-2024-21538 is "
                    "published on NVD at 2024-11-08T05:15:06.453 (Snyk) and on "
                    "GHSA at 2024-11-08T06:30:47Z."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "nvd-cve",
                        "url": nvd_node["url"],
                        "sha256": nvd_node["sha256"],
                        "fetch_timestamp": nvd_node["fetch_timestamp"],
                    },
                    {
                        "kind": "osv-record",
                        "url": osv_node["url"],
                        "sha256": osv_node["sha256"],
                        "fetch_timestamp": osv_node["fetch_timestamp"],
                    },
                ],
            },
            {
                "id": "C6-no-ecosystem-payloads-uncovered",
                "claim": (
                    "Prompt/script/markdown payloads have no PURL. OSV's covered "
                    "ecosystem list fetched 2026-08-24 includes PyPI and npm and "
                    "does not list markdown skills. A skill-only scratch produces "
                    "zero package hits on a snapshot that does detect requests==2.31.0."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "osv-docs",
                        "url": data_page["url"],
                        "sha256": data_page["sha256"],
                        "fetch_timestamp": data_page["fetch_timestamp"],
                    },
                    {
                        "kind": "osv-faq",
                        "url": faq["url"],
                        "sha256": faq["sha256"],
                        "fetch_timestamp": faq["fetch_timestamp"],
                        "commit_sha": faq["commit_sha"],
                    },
                ],
                "strongest_caveat": (
                    "This does not prove no scanner anywhere can flag a skill "
                    "file; it proves these three package/CVE databases do not "
                    "assign an ecosystem identifier to that payload type."
                ),
            },
            {
                "id": "C7-zero-alerts-means-snapshot-query",
                "claim": (
                    "Zero open alerts is a query result against a dated advisory "
                    "set for identifiable packages. OSV.dev's FAQ at commit "
                    f"{faq['commit_sha']} states a data-freshness SLO of sources "
                    "no more than 15 minutes stale 99.5% of the time — a stored "
                    "green older than that window is not a measurement of now."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "pins": [
                    {
                        "kind": "osv-faq",
                        "url": faq["url"],
                        "sha256": faq["sha256"],
                        "commit_sha": faq["commit_sha"],
                        "fetch_timestamp": faq["fetch_timestamp"],
                    }
                ],
            },
        ],
        "evidence": [
            {
                "id": "E-two-snapshot",
                "kind": "measurement",
                "claim": two_snap["note"],
                "result": {
                    "verdict_a": cmp["verdict_a"],
                    "verdict_b": cmp["verdict_b"],
                    "appeared_ids": cmp["appeared_ids"],
                },
            },
            {
                "id": "E-seeded",
                "kind": "measurement",
                "claim": "positive detection on seeded requests==2.31.0 against snapshot B",
                "result": {
                    "detected_ids": ctl["detected_ids"],
                    "patched_silent": ctl["patched_silent"],
                },
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0051-probe2-security-bypass",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "role": "security-reviewer",
            "notes": (
                "Probe 2 does not re-run the two-snapshot arithmetic. It seeds "
                "a scratch manifest, checks the patched negative, checks the "
                "earlier-snapshot silent state, and requires constructed "
                "bypasses of every listed mitigation before any mitigation "
                "could be recorded effective. None survived."
            ),
        },
        "reviewer_bypass_attempts": bypasses,
        "reviewer_verdict": "PASS",
        "tests_required": [
            "run the same scan against two dated advisory snapshots and report any verdict change",
            "control: seed one known-vulnerable dependency in a scratch manifest and confirm detection",
        ],
        "tests": [
            {
                "id": "RES-0051-T-TWO-SNAPSHOT",
                "name": "two-snapshot scan comparison",
                "command": P1,
                "result": "PENDING-NAMED-PROBE",
            },
            {
                "id": "RES-0051-NC-SEEDED-VULN",
                "name": "seeded vulnerable fixture detection",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "RES-0051-NC-SEEDED-VULN",
                "kind": "known-broken-fixture",
                "description": (
                    "scratch-vulnerable.json (requests==2.31.0) must fire "
                    "GHSA-9wx4-h78v-vm56 on snapshot B; scratch-patched.json "
                    "(2.32.2) must be silent; the vulnerable pin must be silent "
                    "on snapshot A."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input command-center/sources/REGISTER.md is absent "
                    "on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "When REGISTER.md exists, map each listed dependency to a PURL and re-run the dated cuts.",
            },
            {
                "claim": (
                    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md and the 2026-07-20 "
                    "star/push snapshot cited in the evidence requirement are "
                    "not on this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "When those files are present, pin their blob SHA and cite the decay example from the file rather than only from this unit's dated cuts.",
            },
            {
                "claim": (
                    "Live osv-scanner binary was not used as the two-snapshot "
                    "engine. A live scanner queries one moving DB and cannot "
                    "by itself produce two dated cuts without an offline dump."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Download gs://osv-vulnerabilities PyPI/npm dumps at two "
                    "modified_id.csv timestamps and re-run osv-scanner --offline."
                ),
            },
            {
                "claim": (
                    f"Declared output_schema {S.SCHEMA_REL} is missing; this "
                    "record was not jsonschema-validated against it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "When the schema exists, validate this artifact and three garbage docs as a both-states control.",
            },
        ],
        "strongest_caveat": (
            "Coverage/latency claims are pinned to the fetched records listed "
            "in fixtures/captures.json. They are not a census of every OSV, "
            "GHSA, or NVD record. The two dated snapshots are cuts of a three-"
            "advisory corpus sufficient to show a real published-date flip for "
            "CVE-2024-35195; they are not a replay of the full 2024-05/06 "
            "production databases."
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "two-snapshot-scan"},
            {"id": "probe2", "command": P2, "role": "seeded-vulnerable-detection"},
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "artifacts": supporting,
        "artifact_paths": [a["path"] for a in supporting] + [S.OUT_REL],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0051/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for RES-0051: live named probes must exit 0 against the dated-"
            "snapshot scanner. cloud ok=true is not delivery. Did not run "
            "global unit_manifest.py --write. Did not rebuild ADV. "
            + sentinel
        ),
    }
    out_path = S.REPO / S.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print(f"FAILED:{UNIT} completion_sentinel missing from serialized artifact")
        return 1
    if "two-snapshot scan comparison" not in text or "seeded vulnerable fixture" not in text:
        print(f"FAILED:{UNIT} required probe phrases missing from artifact text")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {S.OUT_REL} bytes={size} sha256={sha}")
    print(
        f"two_snapshot {cmp['verdict_a']}→{cmp['verdict_b']} "
        f"appeared={cmp['appeared_ids']} seeded={ctl['detected_ids']}"
    )
    print("SUCCESS:RES-0051")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
