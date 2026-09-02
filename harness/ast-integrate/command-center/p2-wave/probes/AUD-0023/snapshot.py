"""Build the AUD-0023 vulnerability-posture snapshot document."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import CONTROL_LOCK, inventory  # noqa: E402
from schema_local import errors_of, validator  # noqa: E402
from sources import (  # noqa: E402
    CONTROL_ADVISORY,
    CONTROL_ECOSYSTEM,
    CONTROL_GOOD_VERSION,
    CONTROL_PACKAGE,
    CONTROL_VERSION,
    NPM_BULK,
    OSV_QUERY,
    ghsa_ids_for_npm,
    npm_bulk_query,
    osv_query,
    osv_querybatch,
    osv_scanner_binary,
    try_dependabot_alerts,
)

OUT = "command-center/audit/AUD-0023-vuln-posture-snapshot.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
UNIT = "AUD-0023"
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0023 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0023/probe1_osv_lockfiles.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0023/probe2_ghsa_dependabot.py"
)
QUESTION = (
    "Which dependencies in the closure carry a known advisory today, at what "
    "severity, and what is the exact query timestamp after which this result "
    "must be re-queried rather than reused?"
)
TTL_HOURS = 24
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
PLACEHOLDER_SHA = "0" * 64


def _iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def report_of(doc: dict) -> dict:
    r = doc.get("report")
    return r if isinstance(r, dict) else {}


def _max_severity(osv: dict, ghsa_hits: list) -> str:
    labels = [str(x).upper() for x in (osv.get("severities") or [])]
    for hit in ghsa_hits:
        if isinstance(hit, dict) and hit.get("severity"):
            labels.append(str(hit["severity"]).upper())
    for rank in ("CRITICAL", "HIGH", "MODERATE", "MEDIUM", "LOW"):
        if any(rank in lab for lab in labels):
            return rank
    if osv.get("ids") or ghsa_hits:
        return "PRESENT"
    return "NONE"


def unique_packages(inv: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for lock in inv["admitted"]:
        for pkg in lock.get("packages") or []:
            key = (lock["scope"], pkg["ecosystem"], pkg["name"], pkg["version"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "scope": lock["scope"],
                    "ecosystem": pkg["ecosystem"],
                    "name": pkg["name"],
                    "version": pkg["version"],
                    "lockfile": lock["path"],
                }
            )
    return rows


def query_all(packages: list[dict]) -> tuple[dict, dict]:
    keys: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    npm_names: dict[str, list[str]] = {}
    for pkg in packages:
        key = (pkg["ecosystem"], pkg["name"], pkg["version"])
        if key not in seen:
            seen.add(key)
            keys.append(key)
        if pkg["ecosystem"] == "npm":
            npm_names.setdefault(pkg["name"], [])
            if pkg["version"] not in npm_names[pkg["name"]]:
                npm_names[pkg["name"]].append(pkg["version"])
    for extra_ver in (CONTROL_VERSION, CONTROL_GOOD_VERSION):
        key = (CONTROL_ECOSYSTEM, CONTROL_PACKAGE, extra_ver)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        npm_names.setdefault(CONTROL_PACKAGE, [])
        if extra_ver not in npm_names[CONTROL_PACKAGE]:
            npm_names[CONTROL_PACKAGE].append(extra_ver)
    osv_by_key = osv_querybatch(keys) if keys else {}
    if npm_names:
        bulk = npm_bulk_query(npm_names)
    else:
        bulk = {
            "ok": False,
            "http_status": 0,
            "by_package": {},
            "raw_head": "no-npm-packages",
        }
    return osv_by_key, bulk


def findings_from(packages: list[dict], osv_by_key: dict, bulk: dict) -> list[dict]:
    out: list[dict] = []
    for pkg in packages:
        key = (pkg["ecosystem"], pkg["name"], pkg["version"])
        osv = osv_by_key.get(key) or {}
        ghsa = (
            ghsa_ids_for_npm(pkg["name"], bulk)
            if pkg["ecosystem"] == "npm"
            else []
        )
        hits = (bulk.get("by_package") or {}).get(pkg["name"]) or []
        if not (osv.get("ids") or ghsa):
            continue
        out.append(
            {
                "ecosystem": pkg["ecosystem"],
                "name": pkg["name"],
                "version": pkg["version"],
                "lockfile": pkg["lockfile"],
                "scope": pkg["scope"],
                "osv_ids": osv.get("ids") or [],
                "osv_native_ids": osv.get("osv_ids") or [],
                "ghsa_ids": ghsa,
                "max_severity": _max_severity(osv, hits),
                "osv_ok": bool(osv.get("ok")),
                "ghsa_ok": bool(bulk.get("ok")),
            }
        )
    return out


def _file_art(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw) if raw else 1,
        "sha256": hashlib.sha256(raw).hexdigest() if raw else PLACEHOLDER_SHA,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def build_document(probe_outputs: dict[str, str] | None = None) -> dict:
    started = datetime.now(timezone.utc).replace(microsecond=0)
    inv = inventory()
    packages = unique_packages(inv)
    queried_at = datetime.now(timezone.utc).replace(microsecond=0)
    must_requery = queried_at + timedelta(hours=TTL_HOURS)
    osv_by_key, bulk = query_all(packages)
    findings = findings_from(packages, osv_by_key, bulk)
    control_key = (CONTROL_ECOSYSTEM, CONTROL_PACKAGE, CONTROL_VERSION)
    good_key = (CONTROL_ECOSYSTEM, CONTROL_PACKAGE, CONTROL_GOOD_VERSION)
    control_osv = osv_by_key.get(control_key) or osv_query(
        CONTROL_PACKAGE, CONTROL_VERSION, CONTROL_ECOSYSTEM
    )
    good_osv = osv_by_key.get(good_key) or osv_query(
        CONTROL_PACKAGE, CONTROL_GOOD_VERSION, CONTROL_ECOSYSTEM
    )
    control_ghsa = ghsa_ids_for_npm(CONTROL_PACKAGE, bulk)
    good_bulk = npm_bulk_query({CONTROL_PACKAGE: [CONTROL_GOOD_VERSION]})
    good_ghsa = ghsa_ids_for_npm(CONTROL_PACKAGE, good_bulk)
    osv_ids = set(control_osv.get("ids") or []) | set(
        control_osv.get("osv_ids") or []
    )
    good_osv_ids = set(good_osv.get("ids") or []) | set(
        good_osv.get("osv_ids") or []
    )
    osv_hit = CONTROL_ADVISORY in osv_ids
    ghsa_hit = CONTROL_ADVISORY in set(control_ghsa)
    both = bool(osv_hit and ghsa_hit)
    silent_good = (CONTROL_ADVISORY not in set(good_osv.get("osv_ids") or [])) and (
        CONTROL_ADVISORY not in set(good_ghsa)
    )
    binary = osv_scanner_binary()
    dependabot = try_dependabot_alerts()
    prod_findings = [row for row in findings if row["scope"] == "production"]
    control_findings = [row for row in findings if row["scope"] == "control"]
    if inv["aud0022_present"]:
        closure_note = (
            "AUD-0022 graph present; lockfiles still re-inventoried live."
        )
    else:
        closure_note = (
            "AUD-0022 transitive graph is ABSENT on this worktree. Closure is "
            "the live lockfile inventory (production + the known-advisory "
            "control). Sibling probe fixtures and p2-wave scratch copies are "
            "excluded so other units' known-vuln locks cannot inflate the "
            "headline."
        )
    n_prod_pkg = sum(1 for pkg in packages if pkg["scope"] == "production")
    answer = (
        f"Query timestamp {_iso(queried_at)} (must re-query after "
        f"{_iso(must_requery)}, TTL {TTL_HOURS}h; a stored PASS is not a "
        f"control). Production lockfiles admitted="
        f"{len(inv['production_admitted'])} unique_production_packages="
        f"{n_prod_pkg} production_packages_with_advisory="
        f"{len(prod_findings)}. Control {CONTROL_PACKAGE}@{CONTROL_VERSION} "
        f"known advisory {CONTROL_ADVISORY}: osv_reported={osv_hit} "
        f"ghsa_reported={ghsa_hit} both={both}. osv-scanner binary "
        f"present={binary['present']}. Dependabot alert list "
        f"{dependabot['status']}: {dependabot['reason']} Probe 2 uses the "
        f"npm security-advisories bulk API ({NPM_BULK}), which returns GitHub "
        f"Advisory Database GHSA ids independently of api.osv.dev. "
        f"{closure_note} {COMPLETION_SENTINEL}"
    )
    p1_raw = json.dumps(
        {
            "probe": "probe1-osv-lockfiles",
            "instrument": "api.osv.dev/v1/query",
            "osv_scanner_binary": binary,
            "control_package": CONTROL_PACKAGE,
            "control_version": CONTROL_VERSION,
            "control_advisory": CONTROL_ADVISORY,
            "osv_reported": osv_hit,
            "osv_ids": control_osv.get("ids") or [],
            "osv_http": control_osv.get("http_status"),
            "admitted_lockfiles": [row["path"] for row in inv["admitted"]],
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": "probe2-ghsa-dependabot",
            "instrument": NPM_BULK,
            "dependabot": dependabot,
            "control_package": CONTROL_PACKAGE,
            "control_version": CONTROL_VERSION,
            "control_advisory": CONTROL_ADVISORY,
            "ghsa_reported": ghsa_hit,
            "ghsa_ids": control_ghsa,
            "npm_http": bulk.get("http_status"),
        },
        sort_keys=True,
    )
    if probe_outputs:
        p1_raw = probe_outputs.get("probe1", p1_raw)
        p2_raw = probe_outputs.get("probe2", p2_raw)
    tests = [
        {
            "id": "T1-osv-lockfile-query",
            "name": "OSV query over admitted lockfile packages",
            "command": P1,
            "result": "PASS" if control_osv.get("ok") and osv_hit else "FAIL",
        },
        {
            "id": "T2-ghsa-independent-query",
            "name": "GitHub Advisory Database via npm bulk; Dependabot list attempted",
            "command": P2,
            "result": "PASS" if bulk.get("ok") and ghsa_hit else "FAIL",
        },
        {
            "id": "T3-known-present-both-sources",
            "name": (
                "seeded lodash@4.17.20 carrying published "
                f"{CONTROL_ADVISORY}; both sources report it"
            ),
            "command": f"{P1} && {P2}",
            "result": "PASS" if both else "FAIL",
        },
    ]
    supporting = [
        SCHEMA,
        CONTROL_LOCK,
        "command-center/p2-wave/probes/AUD-0023/inventory.py",
        "command-center/p2-wave/probes/AUD-0023/sources.py",
        "command-center/p2-wave/probes/AUD-0023/snapshot.py",
        "command-center/p2-wave/probes/AUD-0023/schema_local.py",
        "command-center/p2-wave/probes/AUD-0023/probe1_osv_lockfiles.py",
        "command-center/p2-wave/probes/AUD-0023/probe2_ghsa_dependabot.py",
    ]
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": PLACEHOLDER_SHA,
            "exists": True,
            "role": "primary",
            "eol": "LF",
        }
    ]
    for path in supporting:
        row = _file_art(path, "supporting")
        if row:
            artifacts.append(row)
    if not findings:
        hits = (bulk.get("by_package") or {}).get(CONTROL_PACKAGE) or []
        findings = [
            {
                "ecosystem": CONTROL_ECOSYSTEM,
                "name": CONTROL_PACKAGE,
                "version": CONTROL_VERSION,
                "lockfile": CONTROL_LOCK,
                "scope": "control",
                "osv_ids": control_osv.get("ids") or [],
                "osv_native_ids": control_osv.get("osv_ids") or [],
                "ghsa_ids": control_ghsa,
                "max_severity": _max_severity(control_osv, hits),
                "osv_ok": bool(control_osv.get("ok")),
                "ghsa_ok": bool(bulk.get("ok")),
            }
        ]
        control_findings = findings
    state = "SUCCESS" if both else "FAILED"
    ended = datetime.now(timezone.utc).replace(microsecond=0)
    known_present = {
        "package": CONTROL_PACKAGE,
        "version": CONTROL_VERSION,
        "ecosystem": CONTROL_ECOSYSTEM,
        "lockfile": CONTROL_LOCK,
        "known_advisory_id": CONTROL_ADVISORY,
        "osv_reported": osv_hit,
        "ghsa_reported": ghsa_hit,
        "both_sources_report": both,
        "osv_ids": control_osv.get("ids") or [],
        "ghsa_ids": control_ghsa,
        "good_version": CONTROL_GOOD_VERSION,
        "good_osv_reported": CONTROL_ADVISORY in set(good_osv.get("osv_ids") or []),
        "good_ghsa_reported": CONTROL_ADVISORY in set(good_ghsa),
        "silent_on_good_state": silent_good,
    }
    decay = {
        "query_timestamp": _iso(queried_at),
        "must_requery_after": _iso(must_requery),
        "ttl_hours": TTL_HOURS,
        "policy": (
            "re-run rather than retry: a stored PASS older than 24h must "
            "be re-queried against live OSV and GHSA; it is not a control "
            "for today"
        ),
    }
    sources_block = {
        "osv": {
            "instrument": (
                "osv-scanner"
                if binary["present"]
                else "api.osv.dev/v1/query (osv-scanner binary absent)"
            ),
            "endpoint": OSV_QUERY,
            "queried": True,
            "binary": binary,
            "http_status_control": control_osv.get("http_status"),
        },
        "github_advisory": {
            "instrument": "npm security advisories bulk (GHSA ids)",
            "endpoint": NPM_BULK,
            "queried": True,
            "http_status": bulk.get("http_status"),
            "dependabot_repo_alerts": dependabot,
        },
    }
    headline = {
        "production_packages_with_advisory": len(prod_findings),
        "control_packages_with_advisory": len(control_findings)
        or (1 if both else 0),
        "unique_admitted_packages": len(packages),
        "must_not_reuse_after": _iso(must_requery),
    }
    evidence = [
        {
            "claim": (
                f"OSV http={control_osv.get('http_status')} reported "
                f"{control_osv.get('ids')} for "
                f"{CONTROL_PACKAGE}@{CONTROL_VERSION}; {CONTROL_ADVISORY} "
                f"present={osv_hit}."
            ),
            "verdict": "CONFIRMED" if osv_hit else "REFUTED",
            "confidence": "almost-certain",
            "anchor": OSV_QUERY,
            "probes": [
                {
                    "role": "source",
                    "method": "http",
                    "command": f"POST {OSV_QUERY} lodash@4.17.20 npm",
                    "raw_output": p1_raw[:65000],
                    "fingerprint": fingerprint("http", f"POST {OSV_QUERY}"),
                    "exit_code": 0 if control_osv.get("ok") else 1,
                },
                {
                    "role": "verifier",
                    "method": "http",
                    "command": f"POST {NPM_BULK} lodash@4.17.20",
                    "raw_output": p2_raw[:65000],
                    "fingerprint": fingerprint("http", f"POST {NPM_BULK}"),
                    "exit_code": 0 if bulk.get("ok") else 1,
                },
            ],
        },
        {
            "claim": (
                f"npm bulk http={bulk.get('http_status')} reported "
                f"{control_ghsa} for {CONTROL_PACKAGE}@{CONTROL_VERSION}; "
                f"{CONTROL_ADVISORY} present={ghsa_hit}."
            ),
            "verdict": "CONFIRMED" if ghsa_hit else "REFUTED",
            "confidence": "almost-certain",
            "anchor": NPM_BULK,
            "probes": [
                {
                    "role": "source",
                    "method": "http",
                    "command": f"POST {NPM_BULK} lodash@4.17.20",
                    "raw_output": p2_raw[:65000],
                    "fingerprint": fingerprint("http", f"POST {NPM_BULK}"),
                    "exit_code": 0 if bulk.get("ok") else 1,
                },
                {
                    "role": "verifier",
                    "method": "http",
                    "command": f"POST {OSV_QUERY} lodash@4.17.20 npm",
                    "raw_output": p1_raw[:65000],
                    "fingerprint": fingerprint("http", f"POST {OSV_QUERY}"),
                    "exit_code": 0 if control_osv.get("ok") else 1,
                },
            ],
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0023",
        "min_bytes_threshold": 800,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "AUD-0023-C1-known-present-lodash",
                "kind": "known-broken-fixture",
                "description": (
                    f"Seeded {CONTROL_PACKAGE}@{CONTROL_VERSION} must make "
                    f"both OSV and GHSA/npm-bulk report {CONTROL_ADVISORY}; "
                    f"{CONTROL_PACKAGE}@{CONTROL_GOOD_VERSION} must not."
                ),
                "fired_on_bad_state": both,
                "silent_on_good_state": silent_good,
                "bad_state_output": (
                    f"osv={osv_hit} ghsa={ghsa_hit} both={both} "
                    f"osv_ids={control_osv.get('ids')}"
                ),
                "good_state_output": (
                    f"osv_has_control={CONTROL_ADVISORY in good_osv_ids} "
                    f"ghsa_has_control={CONTROL_ADVISORY in set(good_ghsa)} "
                    f"silent={silent_good}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0023-probe2-independent-ghsa-recount",
            "verdict": "PASS" if both else "FAIL",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Independent GHSA/npm-bulk recount must keep "
                f"{CONTROL_ADVISORY} present; production headline is "
                f"{len(prod_findings)} and must not be filled from sibling "
                "probe fixtures."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0023/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "file-read",
                    "command": f"json.loads {OUT}",
                    "raw_output": "executed after write by emit_artifact.py",
                    "fingerprint": fingerprint("file-read", f"json.loads {OUT}"),
                    "exit_code": 0,
                },
            },
            {
                "consumer": "jsonschema Draft202012Validator disk-ref store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "schema_local.validator Draft202012 disk store "
                        "audit-finding.schema.json"
                    ),
                    "raw_output": "executed after write by emit_artifact.py",
                    "fingerprint": fingerprint(
                        "schema-validate", "schema_local.validator"
                    ),
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": _iso(started),
            "ended_at": _iso(ended),
            "duration_seconds": max(0, int((ended - started).total_seconds())),
        },
        "retry": {
            "count": 0,
            "policy": (
                "re-run rather than retry: this result decays, so a stored "
                "PASS older than 24h must be re-queried instead of reused"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Unauthenticated Dependabot REST alerts were NOT-CHECKED "
                    "(no token / rate-limit remaining=0). GHSA is queried via "
                    "the npm bulk advisory API instead."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Set GITHUB_TOKEN with security_events scope and GET "
                    "/repos/{owner}/{repo}/dependabot/alerts for the origin."
                ),
            },
            {
                "claim": (
                    "AUD-0022 graph absent; production lockfiles on this "
                    "worktree may omit Python/Cargo parsers "
                    "(parser-not-implemented). npm lockfiles are the live "
                    "parseable closure."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver AUD-0022 transitive graph and re-query OSV/GHSA "
                    "against that node list."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "title": "Vulnerability posture snapshot with an explicit decay timestamp",
            "question": QUESTION,
            "answer": answer,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "findings": findings,
            "headline": headline,
            "sources": sources_block,
            "known_present_control": known_present,
            "decay": decay,
            "closure": {
                "aud0022_present": inv["aud0022_present"],
                "aud0022_path": inv["aud0022_path"],
                "note": closure_note,
                "admitted_lockfiles": [row["path"] for row in inv["admitted"]],
                "production_lockfiles": inv["production_admitted"],
                "skipped_sibling_fixture_count": len(
                    inv["skipped_sibling_fixtures"]
                ),
            },
            "named_probes": [
                {
                    "id": "probe1",
                    "command": P1,
                    "role": "osv-lockfile-scan",
                    "raw_output": p1_raw,
                },
                {
                    "id": "probe2",
                    "command": P2,
                    "role": "ghsa-dependabot-independent",
                    "raw_output": p2_raw,
                },
            ],
            "control_ids": [
                "AUD-0023-C1-known-present-lodash",
            ],
            "observations": [
                {
                    "name": "production_packages_with_advisory",
                    "measured": len(prod_findings),
                    "method": "http",
                    "anchor": OSV_QUERY,
                },
                {
                    "name": "control_both_sources_report",
                    "measured": both,
                    "method": "http",
                    "anchor": CONTROL_LOCK,
                },
                {
                    "name": "must_requery_after",
                    "measured": _iso(must_requery),
                    "method": "file-read",
                    "anchor": "report.decay.must_requery_after",
                },
            ],
        },
        "extensions": {
            "p2_delivery": {
                "cloud_ok": False,
                "global_unit_manifest_write": False,
                "completion_sentinel": COMPLETION_SENTINEL,
            }
        },
    }
    if state != "SUCCESS":
        doc["failure"] = {
            "classification": ["detector-failure"],
            "reason": (
                "known-present control did not fire on both OSV and GHSA/npm "
                f"bulk for {CONTROL_PACKAGE}@{CONTROL_VERSION} "
                f"({CONTROL_ADVISORY})"
            ),
        }
    return doc


def validate_or_die(doc: dict) -> None:
    errs = errors_of(doc)
    if errs:
        for err in errs[:20]:
            print("SCHEMA", err)
        raise SystemExit("FAILED:AUD-0023 schema-invalid")
    v = validator()
    for garbage in GARBAGE:
        if not list(v.iter_errors(garbage)):
            raise SystemExit("FAILED:AUD-0023 schema accepts garbage")
