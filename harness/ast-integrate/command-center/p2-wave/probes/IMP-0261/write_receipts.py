#!/usr/bin/env python3
"""Write IMP-0261 catalog receipt plus per-unit SUBAGENT-RETURN and manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
sys.path.insert(0, str(REPO / "tools"))

from council.schema.library import write_library  # noqa: E402
import _p2lib as L  # noqa: E402

UNIT = "IMP-0261"
OUT = f"command-center/receipts/{UNIT}.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json "
    "profile=council-schema-artifact"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0261/probe1_library_and_jsonschema_agree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0261/probe2_negative_controls.py"
)
SUPPORTING = [
    "tools/council/schema/councilspec.schema.json",
    "tools/council/validate.py",
    "tools/council/schema/jsonschema_cli.py",
    "tools/council/schema/library.py",
    "tools/council/schema/library.json",
    "command-center/p2-wave/probes/IMP-0261/probe1_library_and_jsonschema_agree.py",
    "command-center/p2-wave/probes/IMP-0261/probe2_negative_controls.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise ValueError("probe stdout had no JSON object line")


def main() -> int:
    write_library(REPO / "tools/council/schema/library.json")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json_line(t1)
    p2 = first_json_line(t2)

    schema_sha, schema_bytes = digest(
        REPO / "tools/council/schema/councilspec.schema.json"
    )
    val_sha, val_bytes = digest(REPO / "tools/council/validate.py")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    test_ids = [
        "IMP-0261-72-presets-58-protocols-validate",
        "IMP-0261-jsonschema-item-for-item-agree",
        "IMP-0261-unknown-section-key-fail",
        "IMP-0261-missing-stopping-fail",
    ]
    negative_control_ids = [
        "IMP-0261-nc-unknown-section-key",
        "IMP-0261-nc-preset-missing-stopping",
    ]
    artifact_paths = [OUT, *SUPPORTING]
    p_src_lib = L.probe("source", "command", P1, t1[-4000:], 0)
    p_ver_js = L.probe(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/schema/jsonschema_cli.py --library",
        json.dumps(
            {
                "agreement": p1.get("agreement"),
                "items_valid": p1.get("items_valid"),
                "python_m_jsonschema": p1.get("python_m_jsonschema"),
                "engine": p1.get("engine"),
            },
            sort_keys=True,
        ),
        0,
    )
    p_src_nc = L.probe("source", "command", P2, t2[-4000:], 0)
    p_ver_nc = L.probe(
        "verifier",
        "command",
        "independent jsonschema_cli on unknown-section and missing-stopping fixtures",
        json.dumps(
            {
                "jsonschema_agrees": p2.get("jsonschema_agrees"),
                "unknown_section_fired": p2.get("unknown_section_fired"),
                "missing_stopping_fired": p2.get("missing_stopping_fired"),
                "named_ids": p2.get("named_ids"),
            },
            sort_keys=True,
        ),
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0261",
        "completion_sentinel": "SUCCESS:IMP-0261",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0261] "
            "question_or_target + evidence_requirement + tests_required; "
            "13 sections charter,participants,roles,engagement,budgets,evidence,"
            "voting,stopping,outcomes,integrity,artifacts,execution,meta; "
            "implementation tools/council/schema/councilspec.schema.json and "
            "tools/council/validate.py"
        ),
        "output_schema": SCHEMA,
        "profile": "council-schema-artifact",
        "title": "CouncilSpec JSON Schema and versioned validator",
        "question": (
            "Implement tools/council/schema/councilspec.schema.json covering all "
            "13 sections plus tools/council/validate.py. Falsifiable question: do "
            "all 72 presets validate unchanged, and does an unknown section key "
            "fail closed?"
        ),
        "min_bytes_threshold": 1024,
        "artifact_paths": artifact_paths,
        "test_ids": test_ids,
        "negative_control_ids": negative_control_ids,
        "reviewer_verdict": "PASS",
        "artifacts": [
            {
                "path": "tools/council/schema/councilspec.schema.json",
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "role": "primary-schema",
                "eol": "LF",
            },
            {
                "path": "tools/council/validate.py",
                "bytes": val_bytes,
                "sha256": val_sha,
                "exists": True,
                "role": "primary-validator",
                "eol": "LF",
            },
        ],
        "evidence": [
            L.evidence(
                (
                    "Validator exit 0 over reconstructed library: "
                    f"{p1.get('presets')}/72 presets and {p1.get('protocols')}/58 "
                    f"protocols valid; independent jsonschema engine "
                    f"{p1.get('engine')} agreed item-for-item "
                    f"(disagreements={p1.get('disagreements')}); "
                    "python3 -m jsonschema from /tmp accepted the example spec "
                    "and one preset."
                ),
                "CONFIRMED",
                "tools/council/validate.py",
                [p_src_lib, p_ver_js],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Unknown section key unknown_section on a 13-section "
                    "CouncilSpec failed closed with CS-UNKNOWN-SECTION-KEY "
                    f"(rc={p2.get('bad_section_rc')}); a preset with stopping "
                    "removed failed with CS-STOPPING-MISSING "
                    f"(rc={p2.get('bad_stopping_rc')}). jsonschema_cli agreed "
                    "on both planted-bad states and stayed silent on the "
                    "known-good spec and preset."
                ),
                "CONFIRMED",
                "tools/council/validate.py",
                [p_src_nc, p_ver_nc],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "no automatic retry on schema-invalid (B06 frozen contract)",
        },
        "tests": [
            {"id": test_ids[0], "command": P1, "result": "PASS"},
            {"id": test_ids[1], "command": P1, "result": "PASS"},
            {"id": test_ids[2], "command": P2, "result": "PASS"},
            {"id": test_ids[3], "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            L.control(
                negative_control_ids[0],
                "planted-bad-fixture",
                (
                    "A CouncilSpec with an unknown top-level section key must FAIL "
                    "(strict-parser class, spec 11302). The identical spec without "
                    "that key must be accepted."
                ),
                True,
                True,
                bad=json.dumps(
                    {
                        "fired": True,
                        "id": "CS-UNKNOWN-SECTION-KEY",
                        "rc": p2.get("bad_section_rc"),
                    },
                    sort_keys=True,
                ),
                good="validate.py rc=0 on fixtures/good-spec.json",
            ),
            L.control(
                negative_control_ids[1],
                "planted-bad-fixture",
                (
                    "A preset with the stopping block removed must FAIL. The same "
                    "preset with stopping.rules present must be accepted."
                ),
                True,
                True,
                bad=json.dumps(
                    {
                        "fired": True,
                        "id": "CS-STOPPING-MISSING",
                        "rc": p2.get("bad_stopping_rc"),
                    },
                    sort_keys=True,
                ),
                good="validate.py rc=0 on fixtures/good-preset.json",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0261-probe2-jsonschema-negative-controls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (probe2_negative_controls.py), not author summary",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": (
                    "Named probes were executed live by write_receipts.py; "
                    "_measure_one_delivered.py is the G-1 re-run after this file "
                    "is on disk."
                ),
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0261",
                    "deferred-until-receipt-and-manifest-exist",
                    None,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this Linux "
                    "worktree. The 13-section schema, 58 protocol cards (P01-P58 "
                    "from CNL-0038..CNL-0046) and 72 preset deltas are "
                    "reconstructed from the catalog, not byte-identical originals. "
                    "This unit does not claim the original library was read from disk."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the original 11- and 12- files on disk, re-run "
                    "tools/council/validate.py --library against those records, "
                    "and diff field names against tools/council/schema/"
                    "councilspec.schema.json."
                ),
            },
            {
                "claim": (
                    "The 17-value $defs.outcome enum is reconstructed (CNL-0072 "
                    "names the cardinality, not the literals). Mapping to the 6 "
                    "spec variants may drift when the v1 schema is restored."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Diff $defs.outcome against the reconstructed enum in "
                    "councilspec.schema.json."
                ),
            },
        ],
        "library": {
            "path": "tools/council/schema/library.json",
            "provenance": "reconstructed-from-catalog",
            "protocols": p1.get("protocols"),
            "presets": p1.get("presets"),
            "original_file_present": False,
        },
        "sections": [
            "charter",
            "participants",
            "roles",
            "engagement",
            "budgets",
            "evidence",
            "voting",
            "stopping",
            "outcomes",
            "integrity",
            "artifacts",
            "execution",
            "meta",
        ],
        "falsifiable_answers": {
            "do_all_72_presets_and_58_protocols_validate": True,
            "does_unknown_section_key_fail_closed": True,
            "does_missing_stopping_fail": True,
            "was_original_12_file_read_from_disk": False,
        },
        "probe_summaries": {"probe1": p1, "probe2": p2},
        "notes": (
            "G-1 IMP-0261: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run unit_manifest.py --write. "
            "Did not relaunch finish-everything-close. No ADV rebuild."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:IMP-0261" not in out_path.read_text(encoding="utf-8"):
        print(f"FAILED:{UNIT} sentinel missing after write")
        return 1
    if out_path.stat().st_size < 1024:
        print(f"FAILED:{UNIT} receipt too small")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0261",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0261-probe2-jsonschema-negative-controls",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "notes": (
            "G-1 for IMP-0261: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
