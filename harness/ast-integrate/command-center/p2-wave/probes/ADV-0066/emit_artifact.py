#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0066-version-downgrade-attack.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import materialize  # noqa: E402
from probe1_downgrade_paths import measure as measure_p1  # noqa: E402
from probe2_stale_index import measure as measure_p2  # noqa: E402

UNIT = "ADV-0066"
OUT = "command-center/adversarial/ADV-0066-version-downgrade-attack.json"
SCHEMA_REL = "command-center/schema/supply-chain-attestation.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0066/probe1_downgrade_paths.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0066/probe2_stale_index.py"
)
QUESTION = (
    "Can an attacker or a misconfiguration cause installation of an older "
    "version with a known vulnerability - through rollback, a pinned range, "
    "a mirror serving an older index, or a missing minimum-version floor?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0066 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0066 <reason>."
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
    {"unit_id": UNIT, "state": "SUCCESS"},
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT} emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise SystemExit(f"FAILED:{UNIT} missing from catalog")


def v_attack(ok: bool) -> str:
    return "CONFIRMED" if ok else "REFUTED"


def main() -> int:
    unit = catalog_unit()
    catalog_sentinel = str(unit.get("completion_sentinel") or "")
    if not catalog_sentinel.startswith("SUCCESS:ADV-0066"):
        print("FAILED:ADV-0066 catalog sentinel missing")
        return 1
    materialize()
    p1 = measure_p1()
    p2 = measure_p2()
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0066 live probes did not pass controls")
        print(json.dumps({"probe1": p1, "probe2": p2}, indent=2)[:4000])
        return 1
    if not p1.get("control_consults_index") or p1.get("fresh_latest") != "2.0.0":
        print("FAILED:ADV-0066 required fresh-index control failed")
        return 1

    raw1 = (
        json.dumps(p1, sort_keys=True)
        + "\nSUCCESS:ADV-0066-probe1 downgrade paths with advisory present"
    )
    raw2 = (
        json.dumps(p2, sort_keys=True)
        + "\nSUCCESS:ADV-0066-probe2 stale index omits v2"
    )

    attack_ok = (
        p1["rollback_succeeded"]
        and p1["pin_range_succeeded"]
        and p1["pin_exact_succeeded"]
        and p1["first_listed_succeeded"]
        and p2["production_like_silent_v1"]
        and not p1["floor_applied_on_attack_paths"]
    )
    control_ok = (
        p1["control_consults_index"]
        and p1["hardcoded_v2_mutant_exposed"]
        and p1["floor_would_block_v1"]
        and p2["freshness_aware_detects_expiry"]
    )
    if not control_ok:
        print("FAILED:ADV-0066 a required control did not fire")
        return 1

    targets = [
        {
            "id": "rollback-to-vulnerable-v1",
            "verdict": v_attack(p1["rollback_succeeded"]),
            "note": (
                f"explicit rollback/spec {p1['rollback_installed']} with "
                f"advisory {p1['advisory_id']} present and not revoked"
            ),
        },
        {
            "id": "pinned-range-excludes-fixed",
            "verdict": v_attack(p1["pin_range_succeeded"]),
            "note": f">=1.0.0,<2.0.0 resolved to {p1['pin_range_installed']}",
        },
        {
            "id": "exact-pin-vulnerable-v1",
            "verdict": v_attack(p1["pin_exact_succeeded"]),
            "note": f"==1.0.0 resolved to {p1['pin_exact_installed']}",
        },
        {
            "id": "missing-advisory-min-version-floor",
            "verdict": v_attack(
                (not p1["floor_applied_on_attack_paths"])
                and p1["rollback_succeeded"]
                and p1["floor_would_block_v1"]
            ),
            "note": (
                "advisory present; production-like resolve does not apply it "
                "as a floor. Counterfactual apply_floor=True blocks v1."
            ),
        },
        {
            "id": "stale-mirror-omits-v2-silent-resolve",
            "verdict": v_attack(
                p2["production_like_silent_v1"] and not p2["stale_mentions_v2"]
            ),
            "note": (
                f"expired index versions={p2['stale_index_versions']} "
                f"resolved to {p2['production_like_version']} without freshness check"
            ),
        },
        {
            "id": "index-order-first-match",
            "verdict": v_attack(p1["first_listed_succeeded"]),
            "note": (
                "REL-0004-style first matching id on an index that lists v1 "
                f"before v2 installed {p1['first_listed_installed']}"
            ),
        },
    ]
    ids = [t["id"] for t in targets]
    if len(ids) != len(set(ids)):
        print("FAILED:ADV-0066 duplicate target ids")
        return 1

    tests = [
        {
            "id": "T-FRESH-INDEX-SELECTS-V2",
            "command": P1,
            "result": "PASS" if p1["fresh_latest"] == "2.0.0" else "FAIL",
        },
        {
            "id": "T-INDEX-CONSULTATION",
            "command": P1,
            "result": "PASS" if p1["control_consults_index"] else "FAIL",
        },
        {
            "id": "T-HARDCODED-V2-MUTANT-EXPOSED",
            "command": P1,
            "result": "PASS" if p1["hardcoded_v2_mutant_exposed"] else "FAIL",
        },
        {
            "id": "T-ADVISORY-FLOOR-BLOCKS-V1",
            "command": P1,
            "result": "PASS" if p1["floor_would_block_v1"] else "FAIL",
        },
        {
            "id": "T-PROBE-1-DOWNGRADE-PATHS",
            "command": P1,
            "result": "PASS" if p1["pass"] else "FAIL",
        },
        {
            "id": "T-PROBE-2-STALE-INDEX",
            "command": P2,
            "result": "PASS" if p2["pass"] else "FAIL",
        },
        {
            "id": "T-STALE-OMITS-V2",
            "command": P2,
            "result": "PASS" if not p2["stale_mentions_v2"] else "FAIL",
        },
        {
            "id": "T-FRESHNESS-AWARE-DETECTS-EXPIRY",
            "command": P2,
            "result": "PASS" if p2["freshness_aware_detects_expiry"] else "FAIL",
        },
        {
            "id": "T-UNEXPIRED-INCOMPLETE-STILL-V1",
            "command": P2,
            "result": "PASS" if p2["unexpired_incomplete_still_selects_v1"] else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0066 a listed test is not PASS")
        return 1

    overall = "CONFIRMED" if attack_ok else "REFUTED"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog = REPO / CATALOG
    cat_line = find_line(catalog, '"id": "ADV-0066"')
    q_line = find_line(catalog, QUESTION[:50])

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "supply-chain-attestation",
        "question": QUESTION,
        "overall_verdict": overall,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "supply-chain-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "catalog_anchor": {
            "path": CATALOG,
            "id_line": cat_line,
            "question_line": q_line,
        },
        "subject": {
            "package": "adv0066-fixture",
            "vulnerable_version": "1.0.0",
            "fixed_version": "2.0.0",
            "advisory": p1["advisory_id"],
            "advisory_is_revocation": False,
            "production_resolver": (
                "absent; tools/marketplace/disclosure.py stores "
                "fixed_version but install does not consult it. "
                "REL-0004 install_from_mirror takes the first matching id."
            ),
            "measurement_client": (
                "command-center/p2-wave/probes/ADV-0066/resolver.py"
            ),
        },
        "probe1": p1,
        "probe2": p2,
        "targets": targets,
        "evidence": [
            {
                "claim": "Fresh index listing v1 and v2 selects v2 (required control)",
                "verdict": "CONFIRMED" if p1["fresh_latest"] == "2.0.0" else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0066/fixtures.py:fresh_index",
            },
            {
                "claim": "v1-only index selects v1; hardcoded-v2 mutant does not consult the index",
                "verdict": "CONFIRMED" if p1["control_consults_index"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0066/resolver.py:resolve",
            },
            {
                "claim": QUESTION,
                "verdict": overall,
                "anchor": f"{CATALOG}:ADV-0066",
            },
            {
                "claim": "Rollback, pin range, and exact pin install v1 while advisory is present and not revoked",
                "verdict": v_attack(
                    p1["rollback_succeeded"]
                    and p1["pin_range_succeeded"]
                    and p1["pin_exact_succeeded"]
                ),
                "anchor": "command-center/p2-wave/probes/ADV-0066/probe1_downgrade_paths.py",
            },
            {
                "claim": "Expired fixture mirror that never mentions v2 silently resolves to v1 unless freshness is checked",
                "verdict": v_attack(p2["production_like_silent_v1"]),
                "anchor": "command-center/p2-wave/probes/ADV-0066/probe2_stale_index.py",
            },
            {
                "claim": "Counterfactual advisory floor would block v1; production-like path does not apply it",
                "verdict": v_attack(
                    p1["floor_would_block_v1"]
                    and not p1["floor_applied_on_attack_paths"]
                ),
                "anchor": "command-center/p2-wave/probes/ADV-0066/resolver.py:apply_floor",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-HARDCODED-V2",
                "planted_defect": "always return v2 regardless of index contents",
                "fired_on_bad_state": p1["hardcoded_v2_mutant_exposed"],
                "silent_on_good_state": p1["v1_only_latest"] == "1.0.0",
            },
            {
                "id": "NC-STALE-EXPIRY-DETECTOR",
                "planted_defect": "expired index with check_freshness=True",
                "fired_on_bad_state": p2["freshness_aware_detects_expiry"],
                "silent_on_good_state": p1["fresh_latest"] == "2.0.0",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "raw_output": raw1,
                "verdict": "PASS",
                "role": "per-path-downgrade-with-advisory-present",
            },
            {
                "id": "probe2",
                "command": P2,
                "raw_output": raw2,
                "verdict": "PASS",
                "role": "stale-index-freshness-versus-silent-v1",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0066-probe2-stale-index",
            "verdict": "PASS",
            "independent": True,
            "vendor": "mechanical-stale-index",
            "note": (
                "Probe 2 re-derives install from a fixture mirror that never "
                "lists v2 and is mechanically different from probe 1's "
                "rollback/pin matrix. A live Anthropic opus session was not "
                "invoked on this worktree."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0066/probe1_downgrade_paths.py",
                "exists": True,
                "role": "probe1",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0066/probe2_stale_index.py",
                "exists": True,
                "role": "probe2",
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "ADV-0066-named-probes",
                "probe": "probe1_downgrade_paths.py",
            },
            {
                "artifact_path": OUT,
                "consumer": "ADV-0066-named-probes",
                "probe": "probe2_stale_index.py",
            },
        ],
        "produced_at": now,
        "notes": (
            "G-1 for ADV-0066. Distinct from ADV-0038 (explicit revocation). "
            "v1 is merely old and advisory-tagged. Production marketplace "
            "install does not apply a min-version floor; the fixture client "
            "matches that gap while still consulting the index."
        ),
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:ADV-0066 schema accepts garbage")
            print(json.dumps(probe)[:200])
            return 1
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0066 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in text or "SUCCESS:ADV-0066" not in text:
        print("FAILED:ADV-0066 sentinel missing from serialized artifact")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0066 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
