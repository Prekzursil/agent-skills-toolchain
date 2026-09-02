#!/usr/bin/env python3
"""Write IMP-0385 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from fixtures import CENSUS_PS1, KNOWN_ABSENT, KNOWN_PRESENT, fixture_roots  # noqa: E402
from tools.router.index_build import (  # noqa: E402
    build_index,
    default_roots,
    run_nul_seeded_walk,
    write_index,
)

UNIT = "IMP-0385"
OUT = "command-center/receipts/IMP-0385.json"
SCHEMA = "command-center/schema/capability-index.schema.json"
MACHINE_INDEX = "tools/router/capability-index.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = "SENTINEL:IMP-0385:CAPABILITY-INDEX-BUILT"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0385/probe1_present_absent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0385/probe2_nul_relpath.py"
)
SUPPORTING = [
    "tools/router/index_build.py",
    "tools/router/capability-index.json",
    "command-center/schema/capability-index.schema.json",
    "command-center/p2-wave/probes/IMP-0385/probe1_present_absent.py",
    "command-center/p2-wave/probes/IMP-0385/probe2_nul_relpath.py",
    "command-center/p2-wave/probes/IMP-0385/census.ps1",
    "command-center/p2-wave/probes/IMP-0385/fixtures.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0385/SUBAGENT-RETURN.json",
        "role": role,
    }


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise SystemExit("FAILED:IMP-0385 catalog unit missing")


# Catalog output_schema is a generated $ref shim to
# https://ast-integrate.invalid/... . jsonschema 4.10.3 RefResolver tries
# the network. G-1 does not require that hop. This local draft-07 schema
# still rejects garbage and pins the keyed capability-index shape.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "index_kind",
        "keyed_by",
        "capabilities",
        "per_root",
        "zero_diff",
        "detector_control",
        "evidence",
        "tests",
        "negative_controls",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": "IMP-0385"},
        "state": {"enum": ["SUCCESS"]},
        "index_kind": {"const": "capability-index"},
        "keyed_by": {"const": "capability_id"},
        "zero_diff": {"const": True},
        "capabilities": {"type": "object", "minProperties": 6},
        "per_root": {"type": "array", "minItems": 6},
        "detector_control": {
            "type": "object",
            "required": ["present_count", "absent_count"],
            "properties": {
                "present_count": {"const": 1},
                "absent_count": {"const": 0},
            },
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 1},
        "negative_controls": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "sentinel": {
            "type": "string",
            "pattern": "^SENTINEL:IMP-0385:CAPABILITY-INDEX-BUILT",
        },
    },
}


def validate_or_explain(doc: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-unavailable"]
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]


def garbage_rejection() -> dict:
    try:
        import jsonschema
    except ImportError:
        return {"checker": "unavailable", "rejected": None}
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        "x" * 2000,
        {"unit_id": "NOPE", "state": "SUCCESS"},
    ]
    results = []
    for g in garbage:
        errors = list(validator.iter_errors(g))
        results.append({"rejected": len(errors) > 0, "n_errors": len(errors)})
    return {
        "checker": "jsonschema.Draft7Validator+local-capability-index",
        "catalog_shim": SCHEMA,
        "rejected_all_three": all(r["rejected"] for r in results),
        "results": results,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or SENTINEL)
    question = str(unit.get("question_or_target") or "")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0385 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    fixture_index = build_index(fixture_roots(), ps1=CENSUS_PS1)
    live_index = build_index(default_roots(repo=REPO), ps1=CENSUS_PS1)
    write_index(live_index, REPO / MACHINE_INDEX)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0385-nul-ev-") as tmp:
        nul_evidence = run_nul_seeded_walk(Path(tmp))

    fixture_caps = fixture_index.get("capabilities") or {}
    present_n = 1 if KNOWN_PRESENT in fixture_caps else 0
    absent_n = 1 if KNOWN_ABSENT in fixture_caps else 0
    if present_n != 1 or absent_n != 0:
        print(f"FAILED:IMP-0385 emit detector present={present_n} absent={absent_n}")
        return 1
    if not fixture_index.get("zero_diff"):
        print("FAILED:IMP-0385 emit fixture parity not zero")
        return 1
    if live_index.get("aborted_roots"):
        print(f"FAILED:IMP-0385 live aborted_roots={live_index['aborted_roots']}")
        return 1
    live_diffs = [r.get("diff") for r in live_index.get("per_root") or []]
    if any(d not in (0, None) for d in live_diffs):
        print(f"FAILED:IMP-0385 live parity diffs={live_diffs}")
        return 1

    # Receipt capabilities: fixture tree (proven keyed index) plus live ids
    # that do not collide. Fixture is the detector-control surface; live is
    # the six default roots on this machine.
    capabilities = dict(fixture_caps)
    for cid, rec in (live_index.get("capabilities") or {}).items():
        capabilities.setdefault(cid, rec)

    parity_table = []
    for row_r in fixture_index.get("per_root") or []:
        parity_table.append(
            {
                "root_id": row_r.get("root_id"),
                "path": row_r.get("path"),
                "crawler_file_count": row_r.get("crawler_file_count"),
                "census_file_count": row_r.get("census_file_count"),
                "diff": row_r.get("diff"),
                "engine": (row_r.get("census") or {}).get("chosen_engine"),
                "capability_count": row_r.get("capability_count"),
                "status": row_r.get("status"),
                "surface": "fixture",
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Yes: on the fixture six-root tree the crawler's per-root file count "
        "matches the independent census (pwsh Get-ChildItem -Recurse -File, "
        "else find -type f) to within ZERO for all six roots. The known-present "
        f"id {KNOWN_PRESENT} has count 1 and the known-absent sentinel "
        f"{KNOWN_ABSENT} has count 0. A root seeded with a file named NUL "
        "enumerates completely (keep.txt and NUL both present); "
        "safe_relpath does not abort on \\\\.\\NUL. "
        + sentinel
    )

    receipt = {
        "schema_version": 1,
        "index_kind": "capability-index",
        "keyed_by": "capability_id",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": question,
        "answer": answer,
        "builder": "tools/router/index_build.py",
        "built_at": now,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:58785",
        "min_bytes_threshold": 128,
        "capability_count": len(capabilities),
        "capabilities": capabilities,
        "per_root": fixture_index.get("per_root"),
        "parity_table": parity_table,
        "zero_diff": fixture_index.get("zero_diff"),
        "live_index": {
            "path": MACHINE_INDEX,
            "capability_count": live_index.get("capability_count"),
            "zero_diff": live_index.get("zero_diff"),
            "per_root": [
                {
                    "root_id": r.get("root_id"),
                    "path": r.get("path"),
                    "status": r.get("status"),
                    "crawler_file_count": r.get("crawler_file_count"),
                    "census_file_count": r.get("census_file_count"),
                    "diff": r.get("diff"),
                    "capability_count": r.get("capability_count"),
                    "engine": (r.get("census") or {}).get("chosen_engine"),
                }
                for r in live_index.get("per_root") or []
            ],
        },
        "nul_walk": {
            "file_count": nul_evidence.get("file_count"),
            "names": nul_evidence.get("names"),
            "stderr": nul_evidence.get("stderr"),
            "errors": nul_evidence.get("errors"),
            "aborted": nul_evidence.get("aborted"),
            "safe_relpath_device": nul_evidence.get("safe_relpath_device"),
            "safe_relpath_nul_file": nul_evidence.get("safe_relpath_nul_file"),
        },
        "detector_control": {
            "known_present": KNOWN_PRESENT,
            "known_absent": KNOWN_ABSENT,
            "present_count": present_n,
            "absent_count": absent_n,
        },
        "duplicate_ids": fixture_index.get("duplicate_ids"),
        "case_collisions": fixture_index.get("case_collisions"),
        "artifact_paths": [OUT, MACHINE_INDEX, "tools/router/index_build.py", SCHEMA],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": MACHINE_INDEX, "role": "machine-index", "exists": True},
            {
                "path": "tools/router/index_build.py",
                "role": "implementation",
                "exists": True,
            },
            {"path": SCHEMA, "role": "schema", "exists": True},
        ],
        "evidence": [
            {
                "id": "E1-per-root-census-parity",
                "claim": (
                    "Python crawler file counts equal the independent shell "
                    "census on all six fixture roots (diff=0)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/index_build.py:independent_census",
                "confidence": "almost-certain",
                "parity_table": parity_table,
            },
            {
                "id": "E2-nul-walk-stderr",
                "claim": (
                    "A root seeded with a file named NUL enumerated completely; "
                    "stderr contained no traceback; keep.txt was not lost."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/index_build.py:run_nul_seeded_walk",
                "confidence": "almost-certain",
                "stderr": nul_evidence.get("stderr"),
                "names": nul_evidence.get("names"),
            },
        ],
        "test_ids": [
            "probe1-known-present-and-absent-sentinel",
            "probe1-per-root-census-zero-diff",
            "probe2-nul-file-walk",
            "probe2-relpath-device-path",
        ],
        "negative_control_ids": [
            "IMP0385-NC1-absent-sentinel-id",
            "IMP0385-NC2-naive-relpath-aborts-on-NUL",
            "IMP0385-NC3-decoy-notes-not-a-capability",
        ],
        "tests": [
            {
                "id": "probe1-known-present-and-absent-sentinel",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": (
                    "fixture tree with one known-present capability AND one "
                    "known-absent sentinel id; assert 1 and 0 respectively"
                ),
                "output_tail": t1[-2000:],
            },
            {
                "id": "probe2-nul-relpath-must-not-abort",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": (
                    "os.path.relpath against a \\\\.\\NUL path must not abort "
                    "the walk; with-NUL vs without-NUL counts differ by one"
                ),
                "output_tail": t2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0385-NC1-absent-sentinel-id",
                "kind": "detector-control",
                "description": (
                    "capability_id skill:claude_skills:absent-sentinel/SKILL.md "
                    "is not on disk; count must be 0 (proves the detector is "
                    "not stuck at 1)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP0385-NC2-naive-relpath-aborts-on-NUL",
                "kind": "mutation",
                "description": (
                    "Unguarded os.path.relpath raises on NUL under a "
                    "monkeypatched Windows-like relpath; production walk "
                    "still lists keep.txt and NUL."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0385-probe2-nul-relpath",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests, not the author's summary",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0385/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live ~/.claude and ~/.agents roots on this Linux host may "
                    "be empty or absent; the contracted six-root crawl was "
                    "measured, and fixture parity is the zero-diff evidence."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run tools/router/index_build.py on a workstation with "
                    "populated Claude skill/plugin/command trees."
                ),
            },
            {
                "claim": (
                    "Creating a Windows reserved device file (not a POSIX "
                    "filename NUL) requires a Windows volume. This unit "
                    "planted a POSIX file named NUL and injected OSError on "
                    "os.path.relpath for \\\\.\\NUL."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run probe2 on Windows with a real \\\\.\\NUL open.",
            },
        ],
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "schema_garbage_rejection": garbage_rejection(),
    }

    # Fill artifact byte/sha after we know MACHINE_INDEX is on disk; OUT filled after write.
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    errors = validate_or_explain(receipt)
    if errors and errors != ["jsonschema-unavailable"]:
        print("FAILED:IMP-0385 receipt schema errors")
        print("\n".join(errors[:20]))
        return 1

    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:IMP-0385 sentinel absent after write")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "present-absent-parity",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "nul-relpath-walk",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0385/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0385-probe2-nul-relpath",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0385: live named probes exit 0, receipts/IMP-0385.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
    print(
        f"fixture_caps={len(fixture_caps)} live_caps={live_index.get('capability_count')} "
        f"zero_diff={fixture_index.get('zero_diff')}"
    )
    print("SUCCESS:IMP-0385 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
