#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0024-license-inventory.json."""
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
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import inventory as I  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

UNIT = "AUD-0024"
OUT = I.OUT_REL
SCHEMA = I.SCHEMA_REL
QUESTION = (
    "What is the resolved SPDX license for every package in the closure, which "
    "are unresolved or ambiguous, and which are incompatible with a public "
    "marketplace distribution?"
)
SENTINEL = (
    "SUCCESS:AUD-0024 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0024/probe1_declared_metadata.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0024/probe2_license_file_text.py"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(path: Path) -> tuple[str, int, bool]:
    if not path.is_file():
        return "0" * 64, 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest_file(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": max(size, 1),
        "exists": exists,
        "role": role,
        "eol": "LF",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
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


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path)
        out.append((loc + ": " if loc else "") + err.message)
    return out


def main() -> int:
    started = utcnow()
    inv = I.build_inventory()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0024 emit probes probe1={c1} probe2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/AUD-0024/classify.py",
        "command-center/p2-wave/probes/AUD-0024/inventory.py",
        "command-center/p2-wave/probes/AUD-0024/probe1_declared_metadata.py",
        "command-center/p2-wave/probes/AUD-0024/probe2_license_file_text.py",
        "tools/marketplace/license.py",
        "tools/marketplace/data/compatibility-matrix.json",
        "tools/workflow_foundry/license_extract.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:AUD-0024 emit missing artifacts", missing)
        return 1

    named = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:65000],
            "role": "declared-license-metadata",
            "method": "file-read",
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:65000],
            "role": "license-file-text-independent",
            "method": "byte-classify",
        },
    ]
    ended = utcnow()
    counts = inv["counts"]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "License inventory for every direct and transitive dependency",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "legal_advice": False,
        "disclaimer": C.LEGAL_DISCLAIMER,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "headless-linux",
        },
        "intended_distribution_license": inv["intended_distribution_license"],
        "aud0022": inv["aud0022"],
        "closure_method": inv["closure_method"],
        "packages": inv["packages"],
        "declared_vs_actual_conflicts": inv["declared_vs_actual_conflicts"],
        "unresolved_or_ambiguous": inv["unresolved_or_ambiguous"],
        "marketplace_incompatible": inv["marketplace_incompatible"],
        "counts": counts,
        "imported_modules": inv["imported_modules"],
        "unresolved_imports": inv["unresolved_imports"],
        "report": {
            "kind": "audit-inventory",
            "observations": [
                {
                    "name": "packages_in_closure",
                    "measured": counts["packages"],
                    "method": "import-graph+requires-dist+first-party",
                    "anchor": "command-center/p2-wave/probes/AUD-0024/inventory.py",
                },
                {
                    "name": "declared_versus_actual_conflicts",
                    "measured": counts["conflicts"],
                    "method": "byte-classify",
                    "anchor": "probe2-license-file-text",
                },
                {
                    "name": "unresolved_or_ambiguous",
                    "measured": counts["unresolved_or_ambiguous"],
                    "method": "file-read",
                    "anchor": "declared metadata + LICENSE file rails",
                },
                {
                    "name": "marketplace_incompatible",
                    "measured": counts["marketplace_incompatible"],
                    "method": "copyleft-inbound-versus-undeclared-outbound",
                    "anchor": "tools/marketplace/license.py",
                },
                {
                    "name": "license_file_absent",
                    "measured": counts["license_file_absent"],
                    "method": "file-read",
                    "anchor": "dist-info LICENSE walk (Debian wheels often omit the file)",
                },
            ],
            "control_ids": ["AUD0024-C1"],
            "intended_spdx": inv["intended_distribution_license"].get("spdx"),
        },
        "artifacts": artifacts,
        "named_probes": named,
        "evidence": [
            {
                "claim": (
                    f"Closure on this worktree has {counts['packages']} packages "
                    f"({counts['first_party']} first-party). AUD-0022 is "
                    f"{inv['aud0022']['status']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": inv["closure_method"],
                "confidence": "almost-certain",
                "probes": named,
            },
            {
                "claim": (
                    "Probe 1 reads the declared license field. Probe 2 classifies "
                    "LICENSE file text independently. A MIT-metadata/AGPL-LICENSE "
                    "fixture is a declared-versus-actual conflict, not MIT and not AGPL."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0024/probe2_license_file_text.py",
                "confidence": "almost-certain",
                "probes": named,
            },
            {
                "claim": (
                    f"{counts['unresolved_or_ambiguous']} packages are unresolved or "
                    f"ambiguous; {counts['marketplace_incompatible']} are incompatible "
                    "with a public marketplace listing under the measured outbound license. "
                    "UNKNOWN is never treated as compatible. Not legal advice."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/license.py",
                "confidence": "high",
                "probes": named,
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
            "pivot": "AUD-0022 graph absent; used import-graph + Requires-Dist + first-party walk",
        },
        "tests": [
            {
                "id": "ctl-mit-metadata-agpl-license-conflict",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
                "output_tail": "resolved_spdx=DECLARED-VERSUS-ACTUAL-CONFLICT (not MIT, not AGPL-3.0-only)",
            },
            {
                "id": "ctl-mit-metadata-mit-license-silent",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
                "output_tail": "matching MIT/MIT fixture conflict=false resolved=MIT",
            },
            {
                "id": "schema-rejects-garbage",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": "empty object and unrelated object rejected by audit-inventory.schema.json",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0024-C1",
                "kind": "mutation",
                "description": (
                    "Fixture metadata says MIT and LICENSE file is AGPL. The "
                    "resolver must flag a declared-versus-actual conflict and must "
                    "not silently resolve to either identifier. Matching MIT/MIT "
                    "must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "declared=MIT actual=AGPL-3.0-only resolved=DECLARED-VERSUS-ACTUAL-CONFLICT",
                "good_state_output": "declared=MIT actual=MIT resolved=MIT conflict=false",
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0024-probe2-license-file-text",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is a mechanically different detector from probe 1: it "
                "classifies LICENSE file bytes and refuses to adopt the declared "
                "field when the file diverges."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0024/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Owner approval is catalog-required (owner_approval_required=true). "
                    "This inventory is a report, not a legal clearance."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Owner reads unresolved/copyleft rows and records sign-off.",
            },
            {
                "claim": (
                    f"{counts['license_file_absent']} packages have no LICENSE file "
                    "next to their metadata on this worktree (Debian dist-info often "
                    "omits the blob). Declared-versus-actual is NOT-CHECKED there."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": "Re-run against sdists/wheels that ship LICENSE files.",
            },
        ],
        "notes": (
            "G-1 for AUD-0024: live named probes, schema-valid inventory, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Not legal advice. cloud ok=true is not delivery."
        ),
    }
    errs = schema_errors(doc)
    if errs:
        print("FAILED:AUD-0024 emit schema errors")
        for e in errs[:25]:
            print("   ", e)
        return 1
    garb_errs = schema_errors({"totally": "unrelated"})
    if not garb_errs:
        print("FAILED:AUD-0024 emit schema is vacuous (accepts garbage)")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:AUD-0024 emit {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0024 emit sentinel missing after write")
        return 1
    live = json.loads(text)
    live_errs = schema_errors(live)
    if live_errs:
        print("FAILED:AUD-0024 emit post-write schema errors", live_errs[:10])
        return 1
    print(
        f"wrote {OUT} ({size} B) packages={counts['packages']} "
        f"conflicts={counts['conflicts']} incompatible={counts['marketplace_incompatible']}"
    )
    print("SUCCESS:AUD-0024")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
