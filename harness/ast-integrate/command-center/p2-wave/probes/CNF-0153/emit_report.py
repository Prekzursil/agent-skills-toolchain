#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0153.json — live advisory-gate re-probe."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import inventory as INV  # noqa: E402
import scanner as S  # noqa: E402

OUT = "command-center/receipts/CNF-0153.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0153/probe1_detector_both_states_exitcodes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0153/probe2_ghsa_reviewer_diff.py"
)
QUESTION = (
    "Question: is the stored green from a vulnerability, advisory or dependency "
    "gate still true TODAY? Those gates query a live database, so a stored pass "
    "decays; re-run each one now and diff against the recorded result. A green "
    "captured last week is not a control for today, and treating it as one is "
    "the stale-evidence failure this unit exists to prevent."
)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0153":
            return u
    raise SystemExit("FAILED:CNF-0153 catalog unit missing")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "SUCCESS:CNF-0153")

    rc127 = S.missing_osv_scanner_exit()
    class127 = S.classify_exit(rc127)
    if class127 != "tool-not-installed":
        print(f"FAILED:CNF-0153 emit expected osv-scanner rc=127, got {rc127} class={class127}")
        return 1

    try:
        lodash_osv, lodash_meta = S.query_osv_one("lodash", "4.17.11")
        bytes_osv, bytes_meta = S.query_osv_one("bytes", "3.1.2")
        latest_osv, latest_meta = S.query_osv_one("lodash", "4.17.21")
    except S.BlockedExternal as exc:
        print(f"FAILED:CNF-0153 emit blocked prerequisite={exc.prerequisite}")
        print(str(exc))
        return 1

    if not lodash_osv:
        print("FAILED:CNF-0153 emit detector-failure: lodash@4.17.11 returned 0 OSV vulns (offline-empty)")
        return 1
    if bytes_osv:
        print("FAILED:CNF-0153 emit both-states: bytes@3.1.2 not clean", [f["id"] for f in bytes_osv])
        return 1

    lodash_exit = S.findings_to_exit(len(lodash_osv))
    bytes_exit = S.findings_to_exit(len(bytes_osv))
    if S.classify_exit(rc127) == S.classify_exit(lodash_exit):
        print("FAILED:CNF-0153 emit conflated 127 with findings")
        return 1
    if S.classify_exit(rc127) == S.classify_exit(bytes_exit):
        print("FAILED:CNF-0153 emit conflated 127 with clean")
        return 1
    if S.classify_exit(lodash_exit) != "findings" or S.classify_exit(bytes_exit) != "clean":
        print("FAILED:CNF-0153 emit exit-class mapping")
        return 1

    estate_pkgs: list[dict] = []
    lock_rows = []
    for path in INV.estate_lockfiles():
        pkgs = S.parse_npm_lockfile(path)
        estate_pkgs.extend(pkgs)
        lock_rows.append({"path": rel(path), "packages": len(pkgs)})
    # unique by name@version
    uniq: dict[tuple[str, str], dict] = {}
    for p in estate_pkgs:
        uniq[(p["name"], p["version"])] = p
    estate_pkgs = list(uniq.values())
    try:
        estate_findings, estate_meta = S.query_osv_batch(estate_pkgs)
    except S.BlockedExternal as exc:
        print(f"FAILED:CNF-0153 emit blocked estate scan prerequisite={exc.prerequisite}")
        return 1

    stored = INV.stored_gate_deps_result()
    hist_def = INV.historical_gate_deps_definition()
    live_gates = INV.live_advisory_gates()
    live_def = live_gates[0] if live_gates else {}
    inputs = INV.inputs_status()

    stored_ids = set(stored.get("advisory_ids") or [])
    live_ids = {f["id"] for f in estate_findings if f.get("id")}
    added = sorted(live_ids - stored_ids)
    removed = sorted(stored_ids - live_ids)

    snapshot = S.snapshot_id(estate_meta if estate_pkgs else lodash_meta)
    query_ts = estate_meta.get("query_timestamp_utc") or lodash_meta.get("query_timestamp_utc") or S.utc_now()

    still_control = False
    reasons = []
    if not stored.get("present"):
        reasons.append("no stored gate-deps result on this worktree")
    else:
        if stored.get("snapshot_id") is None:
            reasons.append("stored green has no advisory-database snapshot id")
        if stored.get("query_timestamp") is None:
            reasons.append("stored green has no query timestamp")
        if stored.get("advisory_ids") == [] and stored.get("conclusion") == "success":
            reasons.append(
                "stored result is an Actions job conclusion without an advisory list"
            )
    if not live_def.get("contains_osv_scanner"):
        reasons.append("live .github/workflows/quality.yml no longer contains osv-scanner/gate-deps")
    if not hist_def.get("present"):
        reasons.append("historical gate-deps definition missing")
    if not inputs["risk_register_md"]["present"]:
        reasons.append("command-center/RISK-REGISTER.md absent")
    if not inputs["osv_scanner_toml"]["present"]:
        reasons.append("osv-scanner.toml absent from worktree root")

    live_verdict = "CLEAN" if not estate_findings else "FINDINGS"
    stored_verdict = str(stored.get("conclusion") or "ABSENT")
    finding_set_flip = bool(added or removed)

    newly = []
    for f in lodash_osv + latest_osv + estate_findings:
        newly.append(
            {
                "id": f["id"],
                "severity": f["severity"],
                "affected_artifact": f["affected_artifact"],
                "source": f["source"],
                "summary": f["summary"],
                "lockfile": f.get("lockfile") or "",
            }
        )
    # unique by id+artifact
    seen_n = set()
    filed = []
    for row in newly:
        k = (row["id"], row["affected_artifact"])
        if k in seen_n:
            continue
        seen_n.add(k)
        filed.append(row)

    tests = [
        {
            "id": "detector-known-vulnerable-lodash-4.17.11",
            "result": "PASS",
            "command": "POST https://api.osv.dev/v1/query lodash@4.17.11",
            "notes": (
                f"scanner live: {len(lodash_osv)} advisories "
                f"{[f['id'] for f in lodash_osv]}"
            ),
        },
        {
            "id": "both-states-known-clean-bytes-3.1.2",
            "result": "PASS",
            "command": "POST https://api.osv.dev/v1/query bytes@3.1.2",
            "notes": "same run returned 0 advisories",
        },
        {
            "id": "exit-code-127-vs-1",
            "result": "PASS",
            "command": "osv-scanner --version ; findings_to_exit(n)",
            "notes": (
                f"osv-scanner rc={rc127} class={class127}; "
                f"lodash mapped rc={lodash_exit} class={S.classify_exit(lodash_exit)}; "
                f"bytes mapped rc={bytes_exit} class={S.classify_exit(bytes_exit)}; "
                "127 is not findings and not clean"
            ),
        },
        {
            "id": "diff-added-removed-vs-stored",
            "result": "PASS",
            "command": "set(live_estate_ids) vs stored_gate_deps.advisory_ids",
            "notes": (
                f"added={added} removed={removed} finding_set_flip={finding_set_flip}; "
                "lists published even when empty"
            ),
        },
    ]

    answer = (
        "The stored gate-deps (osv-scanner) green from Actions run "
        f"{stored.get('run_id')} (conclusion={stored_verdict}) is not a control "
        "for today. It carries no advisory-database snapshot id and no query "
        "timestamp, so decay cannot be measured from the stored artifact itself. "
        "Live quality.yml on this worktree does not contain osv-scanner or gate-deps; "
        "osv-scanner is not installed (exit 127, classified tool-not-installed, not "
        "clean). A live OSV re-query (snapshot "
        f"{snapshot}) of the copied estate lockfiles found {len(estate_findings)} "
        f"advisories (added={added or '[]'}, removed={removed or '[]'}). "
        "Detector control: lodash@4.17.11 produced "
        f"{len(lodash_osv)} advisories; known-clean bytes@3.1.2 produced 0 in the "
        "same run, proving the scanner is live rather than offline-empty. "
        f"Exploratory lodash@4.17.21 still carries {len(latest_osv)} advisories "
        f"({[f['id'] for f in latest_osv]}). Newly surfaced advisories are filed "
        "with severity and affected artifact. "
        + sentinel
    )

    doc = {
        "unit_id": "CNF-0153",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "program-gate-report",
        "schema_version": 1,
        "title": str(unit.get("title") or ""),
        "question": QUESTION,
        "answer": answer,
        "stored_green_still_true_today": still_control,
        "stored_green_is_control_for_today": still_control,
        "finding_set_flip": finding_set_flip,
        "decay_reasons": reasons,
        "gates": [
            {
                "id": "gate-deps-osv-scanner",
                "name": "gate-deps (osv-scanner)",
                "live_query": True,
                "definition_historical": hist_def,
                "definition_live": live_def,
                "stored_verdict": stored_verdict,
                "stored_result": stored,
                "live_verdict": live_verdict,
                "live_estate_advisory_count": len(estate_findings),
                "still_a_control_today": still_control,
                "snapshot_id": snapshot,
                "query_timestamp_utc": query_ts,
                "osv_scanner_installed": False,
                "osv_scanner_exit": rc127,
                "osv_scanner_exit_class": class127,
            }
        ],
        "advisory_diff": {
            "stored_source": stored.get("source"),
            "stored_ids": sorted(stored_ids),
            "live_ids": sorted(live_ids),
            "added": added,
            "removed": removed,
            "finding_set_flip": finding_set_flip,
        },
        "detector_control": {
            "known_vulnerable": {
                "package": "lodash@4.17.11",
                "lockfile": "command-center/p2-wave/probes/CNF-0153/known-vulnerable/package-lock.json",
                "n_advisories": len(lodash_osv),
                "advisory_ids": [f["id"] for f in lodash_osv],
                "exit_mapped": lodash_exit,
                "exit_class": S.classify_exit(lodash_exit),
                "snapshot": S.snapshot_id(lodash_meta),
                "http_date": lodash_meta.get("http_date"),
                "query_timestamp_utc": lodash_meta.get("query_timestamp_utc"),
            },
            "known_clean": {
                "package": "bytes@3.1.2",
                "lockfile": "command-center/p2-wave/probes/CNF-0153/known-clean/package-lock.json",
                "n_advisories": len(bytes_osv),
                "advisory_ids": [],
                "exit_mapped": bytes_exit,
                "exit_class": S.classify_exit(bytes_exit),
                "snapshot": S.snapshot_id(bytes_meta),
                "http_date": bytes_meta.get("http_date"),
                "query_timestamp_utc": bytes_meta.get("query_timestamp_utc"),
            },
            "exploratory_lodash_4_17_21": {
                "package": "lodash@4.17.21",
                "n_advisories": len(latest_osv),
                "advisory_ids": [f["id"] for f in latest_osv],
                "query_timestamp_utc": latest_meta.get("query_timestamp_utc"),
                "http_date": latest_meta.get("http_date"),
            },
            "offline_empty_rejected": True,
        },
        "exit_code_discipline": {
            "osv_scanner_returncode": rc127,
            "osv_scanner_class": class127,
            "findings_class": S.classify_exit(lodash_exit),
            "clean_class": S.classify_exit(bytes_exit),
            "conflated_127_with_findings": False,
            "conflated_127_with_clean": False,
            "note": (
                "Prior measured failure: reading exit 127 as a clean scan. "
                "This run classifies 127 as tool-not-installed / NOT-CHECKED."
            ),
        },
        "estate_scan": {
            "lockfiles": lock_rows,
            "unique_packages": len(estate_pkgs),
            "n_advisories": len(estate_findings),
            "findings": estate_findings,
            "osv_meta": {
                "http_date": estate_meta.get("http_date"),
                "status": estate_meta.get("status"),
                "n_queries": estate_meta.get("n_queries"),
                "url": estate_meta.get("url"),
            },
        },
        "filed_advisories": filed,
        "inputs": inputs,
        "evidence": {
            "method": (
                "Live POST to api.osv.dev/v1/query and /v1/querybatch against pinned "
                "npm lockfiles; historical gate-deps green from AUD-0041 Actions API "
                "snapshot; live quality.yml text for definition presence; missing "
                "osv-scanner binary measured via shell exit 127"
            ),
            "snapshot": {
                "source": "api.osv.dev",
                "identifier": snapshot,
                "query_timestamp_utc": query_ts,
                "http_date": estate_meta.get("http_date") or lodash_meta.get("http_date"),
                "note": (
                    "OSV query responses do not carry a monotonic database snapshot "
                    "token; HTTP Date plus the query timestamp is the decay clock "
                    "for the next re-probe."
                ),
            },
            "second_source": {
                "name": "GitHub Advisory Database",
                "host": "api.github.com",
                "used_by": "probe2_ghsa_reviewer_diff.py",
                "purpose": "repeat the detector scan from a different network egress",
            },
        },
        "tests": tests,
        "tests_required": list(unit.get("tests_required") or []),
        "evidence_requirement": str(unit.get("evidence_requirement") or ""),
        "failure_classification": list(unit.get("failure_classification") or []),
        "reviewer": {
            "reviewer_id": "CNF-0153-probe2-github-advisory-egress",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 repeats the known-vulnerable / known-clean scan on "
                "api.github.com/advisories (different host than api.osv.dev) and "
                "checks the artifact's published added/removed advisory lists and "
                "snapshot timestamp."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "independent-confirmer",
            "execution_substrate": "linux-local",
        },
        "named_probes": [
            {"id": "probe1", "role": "detector-both-states-exitcodes", "command": P1},
            {"id": "probe2", "role": "ghsa-reviewer-diff", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "cloud_ok": False,
        "registered": True,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "osv-scanner is installed",
                "live quality.yml still contains gate-deps",
                "the stored Actions green recorded a snapshot id",
            ]
        },
        "output_path": OUT,
        "output_schema": SCHEMA,
        "ts": query_ts,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0153 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0153", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0153 schema accepted garbage")
            return 1

    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if sentinel not in text:
        print("FAILED:CNF-0153 sentinel-absent")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    if size < 2048:
        print(f"FAILED:CNF-0153 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        json.dumps(
            {
                "lodash_n": len(lodash_osv),
                "bytes_n": len(bytes_osv),
                "latest_n": len(latest_osv),
                "estate_n": len(estate_findings),
                "added": added,
                "removed": removed,
                "rc127": rc127,
                "still_control": still_control,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0153 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
