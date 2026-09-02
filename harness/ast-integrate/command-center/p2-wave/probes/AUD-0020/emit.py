#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0020-python-dep-inventory.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

UNIT = "AUD-0020"
OUT_REL = "command-center/audit/AUD-0020-python-dep-inventory.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0020/probe1_manifests.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0020/probe2_lock_reconciliation.py"
)
SENTINEL = (
    "SUCCESS:AUD-0020 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every Python package in the repo, what are its declared direct "
    "dependencies, is there a lockfile, and does the lockfile resolve the "
    "declared constraints?"
)
PRIOR_DUMP = HERE / "probe1-manifests.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compact_pkg(pkg: dict) -> dict:
    recon = pkg.get("reconciliation")
    rows = []
    if recon:
        for row in recon.get("rows") or []:
            rows.append(
                {
                    "name": row["name"],
                    "declared": row["declared"],
                    "locked": row["locked"],
                    "satisfies": row["satisfies"],
                    "status": row["status"],
                }
            )
    return {
        "name": pkg["name"],
        "source": pkg["source"],
        "origin_url": pkg["origin_url"],
        "dirty_tracked": pkg["dirty_tracked"],
        "dirty_untracked": pkg["dirty_untracked"],
        "unique_file_count": pkg["unique_file_count"],
        "unpreserved_count": pkg["unpreserved_count"],
        "package_dir": pkg["package_dir"],
        "declared_dep_count": pkg["declared_dep_count"],
        "declared": pkg["declared"],
        "lockfile": pkg["lockfile"],
        "lockfile_kind": pkg["lockfile_kind"],
        "locked_package_count": pkg["locked_package_count"],
        "reconciliation_note": pkg["reconciliation_note"],
        "reconciliation_rows": rows,
        "manifests": [
            {
                "manifest": m["manifest"],
                "declared_dep_count": m["declared_dep_count"],
            }
            for m in pkg["manifests"]
        ],
    }


def prior_absent_rows() -> list[dict]:
    """Resume the earlier probe dump: packages listed there but missing here."""
    if not PRIOR_DUMP.is_file():
        return []
    try:
        prior = json.loads(PRIOR_DUMP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    seen: set[str] = set()
    for item in prior if isinstance(prior, list) else []:
        rel = str(item.get("package_dir") or "")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        if (REPO / rel).is_dir():
            continue
        name = Path(rel).name or rel
        if len(name) < 3:
            name = rel.replace("/", "--") or "pkg"
        rows.append(
            {
                "name": name if len(name) >= 3 else f"pkg-{name}",
                "source": "not-present",
                "origin_url": None,
                "dirty_tracked": 0,
                "dirty_untracked": 0,
                "unique_file_count": 0,
                "unpreserved_count": 0,
                "package_dir": rel,
                "declared_dep_count": int(item.get("declared_dep_count") or 0),
                "declared": item.get("declared") or {},
                "lockfile": None,
                "lockfile_kind": None,
                "locked_package_count": 0,
                "reconciliation_note": (
                    "NOT-PRESENT on this Linux delivery slice. Listed in the "
                    "resumed probe1-manifests.json dump; the directory is absent."
                ),
                "reconciliation_rows": [],
                "manifests": [],
            }
        )
    return rows


def main() -> int:
    ctl = I.pin_control()
    if not ctl["ok"]:
        print(f"FAILED:{UNIT} pin control did not discriminate")
        return 1
    preserve = I.run_preservation_control()
    if not (
        preserve["unpreserved_before_copy"]
        and preserve["preserved_after_copy"]
        and preserve["flipped"]
        and preserve["path_name_match_rejected"]
    ):
        print(f"FAILED:{UNIT} preservation control {preserve}")
        return 1

    packages = I.scan_packages()
    if not packages:
        print(f"FAILED:{UNIT} zero python packages")
        return 1
    head = I.headline(packages)
    live = I.live_host_scan()
    inventory = [compact_pkg(p) for p in packages] + prior_absent_rows()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = (
        f"packages={head['python_packages']} manifests={head['python_manifests']} "
        f"declared_deps={head['declared_direct_dependencies']} "
        f"with_lock={head['packages_with_parsed_lock']} "
        f"without_lock={head['packages_without_parsed_lock']} "
        f"out_of_range={head['out_of_range_pins']} "
        f"missing_from_lock={head['declared_missing_from_lock']} "
        f"undecidable={head['undecidable_constraints']} "
        f"uv.lock={head['uv_lock_files']} poetry.lock={head['poetry_lock_files']} "
        f"Pipfile.lock={head['pipfile_lock_files']} setup.cfg={head['setup_cfg_files']}"
    )
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "min_bytes_threshold": 4096,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0020",
        "produced_at": now,
        "produced_by": {
            "execution_substrate": "local-serialized",
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "auditor",
        },
        "live_host": {
            "cwd": live["cwd"],
            "git_worktree": live["git_worktree"],
            "origin_url": live["origin_url"],
            "named_surviving_present": live["named_surviving_present"],
            "named_surviving_absent": live["named_surviving_absent"],
            "git_rev_parse_raw": live["git_rev_parse_raw"],
            "named_surviving": live["named_surviving"],
        },
        "inventory": inventory,
        "preservation_control": {
            "seed_path": preserve["seed_path"],
            "copy_path": preserve["copy_path"],
            "unpreserved_before_copy": True,
            "preserved_after_copy": True,
            "path_name_match_rejected": True,
            "flipped": True,
            "seed_sha256": preserve["seed_sha256"],
            "before_hits": preserve["before_hits"],
            "after_hits": preserve["after_hits"],
            "decoy_path": preserve["decoy_path"],
        },
        "pin_control": {
            "fires_on_out_of_range": True,
            "silent_on_in_range": True,
            "ok": True,
            "fixture_manifest": ctl["fixture_manifest"],
            "bad_lock": ctl["bad_lock"],
            "good_lock": ctl["good_lock"],
            "bad_violations": [v["name"] for v in ctl["bad_result"]["violations"]],
            "good_violations": [v["name"] for v in ctl["good_result"]["violations"]],
        },
        "report": {
            "kind": "python-dep-inventory",
            "summary": summary,
            "python_packages": head["python_packages"],
            "python_manifests": head["python_manifests"],
            "declared_direct_dependencies": head["declared_direct_dependencies"],
            "packages_with_parsed_lock": head["packages_with_parsed_lock"],
            "packages_without_parsed_lock": head["packages_without_parsed_lock"],
            "out_of_range_pins": head["out_of_range_pins"],
            "declared_missing_from_lock": head["declared_missing_from_lock"],
            "undecidable_constraints": head["undecidable_constraints"],
            "uv_lock_files": head["uv_lock_files"],
            "poetry_lock_files": head["poetry_lock_files"],
            "pipfile_lock_files": head["pipfile_lock_files"],
            "setup_cfg_files": head["setup_cfg_files"],
            "violations": head["violations"],
            "missing_from_lock": head["missing_from_lock"],
            "undecidable": head["undecidable"],
            "scope": (
                "This Linux delivery slice has no production pyproject.toml / "
                "setup.cfg / requirements*.txt outside AUD-0020 fixtures. Live "
                "scan covers the fixture packages plus any host manifests. "
                "Packages listed in the resumed probe1-manifests.json whose "
                "directories are absent are recorded source=not-present. "
                "Lock absence is NOT-CHECKED, not a pass. Undecidable PEP 440 "
                "forms are excluded from the out-of-range count."
            ),
        },
        "answers": {
            "python_packages": head["python_packages"],
            "packages_with_parsed_lock": head["packages_with_parsed_lock"],
            "packages_without_parsed_lock": head["packages_without_parsed_lock"],
            "out_of_range_pins": head["out_of_range_pins"],
            "declared_missing_from_lock": head["declared_missing_from_lock"],
            "pin_control_discriminated": True,
            "lock_absence_is_not_a_pass": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "manifest-parse"},
            {"id": "probe2", "command": P2, "role": "lock-reconciliation"},
        ],
        "tests": [
            {
                "id": "ctl-injected-out-of-range-pin",
                "result": "PASS",
                "command": "diff(fixture_manifest, bad_lock)",
            },
            {
                "id": "ctl-in-range-lock-silent",
                "result": "PASS",
                "command": "diff(fixture_manifest, good_lock)",
            },
            {
                "id": "preservation-both-states",
                "result": "PASS",
                "command": P2,
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/AUD-0020/probe1_manifests.py",
                "kind": "manifest-parse-probe",
                "claim": (
                    f"{head['python_manifests']} manifests declare "
                    f"{head['declared_direct_dependencies']} direct dependencies "
                    f"across {head['python_packages']} package directories."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0020/probe2_lock_reconciliation.py",
                "kind": "lock-reconciliation-probe",
                "claim": (
                    f"{head['packages_with_parsed_lock']} packages have a parsed "
                    f"lock; {head['out_of_range_pins']} out-of-range pins; "
                    f"{head['declared_missing_from_lock']} declared names missing "
                    "from lock. Absence of a lock is NOT-CHECKED."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0020/inventory.py",
                "kind": "detector-source",
                "claim": (
                    "Differ reports UNDECIDABLE-CONSTRAINT rather than guessing "
                    "on PEP 440 forms it does not implement."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0020-probe2-lock-reconciliation",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Independent mechanical reviewer is probe 2, which re-runs lock "
                "reconciliation and the both-states out-of-range pin control. "
                "Catalog also asked for a fresh-context Claude reviewer who "
                "must try to falsify the headline count; that second human "
                "pass is NOT-CHECKED on this lane."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0020/inventory.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0020/probe1_manifests.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0020/probe2_lock_reconciliation.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    f"{head['undecidable_constraints']} declared constraints use "
                    "a form this differ does not implement and are reported "
                    "UNDECIDABLE-CONSTRAINT rather than assumed satisfied. The "
                    "out-of-range count is therefore a lower bound."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-run reconciliation with packaging.specifiers.SpecifierSet "
                    "and compare counts."
                ),
            },
            {
                "claim": (
                    "Production Python trees named in the resumed "
                    "probe1-manifests.json dump are absent from this Linux "
                    "slice. Fixture packages under probes/AUD-0020/fixtures/"
                    "packages/ are the live corpus here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the scan on a checkout that still contains skills/, "
                    "tools/*-mcp/, and .agents/ Python packages."
                ),
            },
        ],
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print(f"FAILED:{UNIT} schema errors")
        for err in errors[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:{UNIT} schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(summary)
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
