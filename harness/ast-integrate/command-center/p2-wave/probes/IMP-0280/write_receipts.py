#!/usr/bin/env python3
"""Write IMP-0280 receipt + per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
UID = "IMP-0280"
OUT = "command-center/receipts/IMP-0280.json"
SCHEMA = "command-center/schema/receipt.schema.json"
LIB = "tools/council/roles/mandate.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0280/probe1_rights_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0280/probe2_unenforced_audit.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/roles/__init__.py",
    "tools/council/roles/mandate.py",
    "command-center/p2-wave/probes/IMP-0280/probe1_rights_matrix.py",
    "command-center/p2-wave/probes/IMP-0280/probe2_unenforced_audit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str, dict]:
    env = os.environ.copy()
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
    doc: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                doc = parsed
    return p.returncode, text, doc


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0280/SUBAGENT-RETURN.json",
        "role": role,
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:{UID} emit missing anchor {needle!r} in {rel}")


def build_receipt(p1: dict, p2: dict) -> dict:
    sys.path.insert(0, str(REPO / "tools"))
    from council.roles.mandate import (  # noqa: E402
        RIGHTS,
        enforcement_sites,
        point_of_use_audit,
        rights_matrix,
    )

    audit = point_of_use_audit()
    cells = rights_matrix()
    sites = list(enforcement_sites())
    vote_fn = source_anchor(LIB, "def cast_vote(")
    refuse_fn = source_anchor(LIB, "def _refuse(")
    audit_fn = source_anchor(LIB, "def point_of_use_audit(")
    return {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0280",
        "completion_sentinel": "SUCCESS:IMP-0280",
        "title": "Role mandate model: permissions, speaking, vote and veto rights",
        "question_or_target": (
            "Implement tools/council/roles/mandate.py as typed role objects "
            "carrying tool access, source access, speaking rights, vote rights "
            "and veto rights. Falsifiable question: is every right checked at "
            "the point of use rather than merely declared at seat time?"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0280",
        "output_path": OUT,
        "output_schema": (
            SCHEMA
            + " profile=council-roles-module (required: unit_id, artifact_paths[], "
            "spec_anchor, evidence[], test_ids[], negative_control_ids[], "
            "reviewer_verdict, residual_unknowns[])"
        ),
        "implementation": {
            "module": LIB,
            "typed_object": "RoleMandate",
            "seat_time": "seat() records the mandate and does not gate use",
            "point_of_use": [
                "use_tool",
                "use_source",
                "speak",
                "cast_vote",
                "cast_veto",
            ],
            "refuse_helper": "_refuse",
            "audit": "point_of_use_audit walks each enforcement function AST",
        },
        "rights": list(RIGHTS),
        "enforcement_sites": sites,
        "point_of_use_audit": audit.to_dict(),
        "rights_matrix": cells,
        "artifact_paths": [OUT, LIB] + SUPPORTING[:2],
        "evidence": [
            {
                "id": "E1-point-of-use-audit",
                "claim": (
                    "Each of the five rights is enforced at a named function, "
                    "not at seat(). Live audit lists every right as enforced "
                    f"({list(audit.enforced_rights())})."
                ),
                "verdict": "CONFIRMED",
                "anchor": audit_fn,
                "sites": sites,
            },
            {
                "id": "E2-refusal-events",
                "claim": (
                    "Exercising each right without the grant yields a REFUSED "
                    "event; exercising it with the grant yields GRANTED. "
                    f"{sum(1 for c in cells if c['pass'])}/{len(cells)} cells pass."
                ),
                "verdict": "CONFIRMED",
                "anchor": refuse_fn,
                "cells": [
                    {
                        "right": c["right"],
                        "with_grant": c["with_grant"]["event"],
                        "without_grant": c["without_grant"]["event"],
                    }
                    for c in cells
                ],
            },
        ],
        "tests": [
            {
                "id": "IMP-0280-rights-matrix",
                "name": "each right exercised with and without the grant",
                "result": "PASS" if p1.get("pass") else "FAIL",
                "probe": "probe1_rights_matrix.py",
            },
            {
                "id": "IMP-0280-unenforced-audit",
                "name": "remove one enforcement call; audit reports it unenforced",
                "result": "PASS" if p2.get("pass") else "FAIL",
                "probe": "probe2_unenforced_audit.py",
                "mutant_right": p2.get("mutant_right"),
            },
        ],
        "test_ids": [
            "IMP-0280-rights-matrix",
            "IMP-0280-unenforced-audit",
        ],
        "negative_controls": [
            {
                "id": "IMP-0280-NC-STRIP-VOTE-ENFORCEMENT",
                "kind": "ast-strip-enforcement-if",
                "description": (
                    "strip_enforcement removes the vote If-gate that calls "
                    "_refuse; the audit must list vote as unenforced and the "
                    "mutant must allow a vote from an empty mandate."
                ),
                "fired_on_bad_state": p2.get("mutant_vote_without_grant_allowed")
                is True,
                "silent_on_good_state": p2.get("live_vote_without_grant_allowed")
                is False,
                "mutant_unenforced": p2.get("mutant_unenforced"),
            }
        ],
        "negative_control_ids": ["IMP-0280-NC-STRIP-VOTE-ENFORCEMENT"],
        "reviewer": {
            "reviewer_id": "IMP-0280-probe2-unenforced-audit",
            "verdict": "PASS" if p2.get("pass") else "FAIL",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not trust probe 1's printed matrix. It mutates "
                "cast_vote in-memory, re-runs point_of_use_audit on the mutant "
                "source, executes the mutant, and asserts the live file bytes "
                "did not change. A constant-True audit fails the mutant half; "
                "a constant-False audit fails the live half."
            ),
        },
        "reviewer_verdict": "PASS" if p2.get("pass") else "FAIL",
        "residual_unknowns": [
            (
                "No live multi-vendor council ran; enforcement is proven on "
                "the mandate module's own call sites, not on IMP-0264 kernel "
                "turns (that module is absent on this worktree)."
            )
        ],
        "scope": {
            "proof_surface": (
                "tools/council/roles/mandate.py gates and AST audit. Probes "
                "import the live module; the mutant is exec'd from a string "
                "and never written over the live file."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/kernel.py exists (IMP-0264)",
                "_USER-PROMPTS.md / 11-COUNCIL-SPECIFICATION.md are on this tree",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "rights-matrix", "command": P1},
            {"id": "probe2", "role": "unenforced-audit", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LIB, "exists": True, "role": "implementation"},
        ],
        "min_bytes_threshold": 2048,
        "notes": (
            "G-1 for IMP-0280: live named probes re-run the mandate gates. "
            "Did not run tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery. Did not rebuild ADV."
        ),
        "vote_enforcement_anchor": vote_fn,
    }


def main() -> int:
    c1, t1, p1 = run_probe(P1)
    c2, t2, p2 = run_probe(P2)
    if c1 != 0 or c2 != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_receipt(p1, p2)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0280" not in text:
        print(f"FAILED:{UID} sentinel absent after emit")
        return 1
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UID} artifact {size}B below floor")
        return 1
    primary = row(OUT, "primary")
    if primary["sha256"] != sha:
        print(f"FAILED:{UID} digest mismatch")
        return 1
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0280",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "rights-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unenforced-audit",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0280/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0280-probe2-unenforced-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0280: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0280 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
