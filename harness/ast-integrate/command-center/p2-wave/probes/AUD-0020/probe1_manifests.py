#!/usr/bin/env python3
"""Probe 1: parse every pyproject.toml, setup.cfg, and requirements*.txt.

A lockfile is not consulted here. That is probe 2's job: a well-formed
manifest cannot see an out-of-range pin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

ART = REPO / "command-center/audit/AUD-0020-python-dep-inventory.json"
RAW = HERE / "probe1-manifests.json"
SENTINEL = (
    "SUCCESS:AUD-0020 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0020-probe1 {msg}")
    return 1


def main() -> int:
    packages = I.scan_packages()
    head = I.headline(packages)
    tables = []
    for pkg in packages:
        for man in pkg["manifests"]:
            tables.append(
                {
                    "package_dir": pkg["package_dir"],
                    "manifest": man["manifest"],
                    "declared": man["declared"],
                    "declared_dep_count": man["declared_dep_count"],
                    "manifest_error": man["manifest_error"],
                    "lockfile": pkg["lockfile"],
                    "lockfile_kind": pkg["lockfile_kind"],
                }
            )
    parse_errors = [t for t in tables if t["manifest_error"]]
    payload = {
        "ok": False,
        "python_packages": head["python_packages"],
        "python_manifests": head["python_manifests"],
        "declared_direct_dependencies": head["declared_direct_dependencies"],
        "setup_cfg_files": head["setup_cfg_files"],
        "parse_error_count": len(parse_errors),
        "tables": tables,
    }
    if head["python_manifests"] < 1:
        I.dump_json(RAW, payload)
        return fail("zero manifests found")
    if parse_errors:
        I.dump_json(RAW, payload)
        return fail(f"manifest parse errors {len(parse_errors)}")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            I.dump_json(RAW, payload)
            return fail("artifact missing completion sentinel")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            I.dump_json(RAW, payload)
            return fail(f"self-declared {doc.get('state')}")
        report = doc.get("report") or {}
        if int(report.get("python_manifests") or 0) != head["python_manifests"]:
            I.dump_json(RAW, payload)
            return fail(
                f"artifact manifests {report.get('python_manifests')} "
                f"!= live {head['python_manifests']}"
            )

    payload["ok"] = True
    I.dump_json(RAW, payload)
    print(
        json.dumps(
            {
                "python_packages": head["python_packages"],
                "python_manifests": head["python_manifests"],
                "declared_direct_dependencies": head["declared_direct_dependencies"],
                "setup_cfg_files": head["setup_cfg_files"],
                "parse_error_count": 0,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0020-probe1 parsed each manifest into a normalized "
        "name/constraint table; lockfile not consulted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
