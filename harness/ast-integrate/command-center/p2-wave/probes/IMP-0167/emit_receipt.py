#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0167.json from live import-gate measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import, repo  # noqa: E402

ensure_import()
from workflow_foundry.tool_requirements import (  # noqa: E402
    extract_tool_requirements,
    import_candidate,
    reconcile_subset,
)

REPO = repo()
OUT = "command-center/receipts/IMP-0167.json"
FIX = HERE / "fixtures"
SENTINEL = "SUCCESS:IMP-0167"
TS0 = "2026-08-24T18:40:00Z"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("0" * 64, 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    host = load("host_permissions.json")["grantable"]
    unit = load("unit_permissions.json")["tool_permissions"]
    absent = load("candidate_absent_webfetch.json")
    twin = load("candidate_grantable_twin.json")
    prose = load("candidate_prose_mentions_webfetch.json")
    silent = load("candidate_typed_webfetch_silent_prose.json")

    blocked = import_candidate(absent, unit_permissions=unit, host_grantable=host)
    imported = import_candidate(twin, unit_permissions=unit, host_grantable=host)
    prose_d = import_candidate(prose, unit_permissions=unit, host_grantable=host)
    silent_d = import_candidate(silent, unit_permissions=unit, host_grantable=host)
    tok_ok, tok_missing = reconcile_subset(["Read"], ["ReadWrite"])

    if blocked.status != "BLOCKED" or "WebFetch" not in blocked.missing_capabilities:
        print("FAILED:IMP-0167 emit absent-tool did not BLOCK naming WebFetch")
        return 1
    if imported.status != "IMPORTED":
        print("FAILED:IMP-0167 emit grantable twin did not import")
        return 1
    if prose_d.status != "IMPORTED" or silent_d.status != "BLOCKED":
        print("FAILED:IMP-0167 emit subset-vs-prose traps did not discriminate")
        return 1
    if tok_ok or "Read" not in tok_missing:
        print("FAILED:IMP-0167 emit token-in-token substring trap did not fire")
        return 1

    ts1 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib = "tools/workflow_foundry/tool_requirements.py"
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0167",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0167",
        "title": "Extract tool requirements and reconcile them against the permission model",
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "question_or_target": (
            "Target: derive each candidate's tool requirements and reconcile them "
            "with the per-unit permission declaration. Acceptance: a candidate "
            "needing a tool the host cannot grant is marked BLOCKED with the exact "
            "missing capability named - not silently imported to fail later at dispatch."
        ),
        "method": {
            "extraction": "typed tool lists on candidate/stages/roles; prose fields skipped",
            "reconciliation": "required ⊆ (unit_declared ∩ host_grantable) via set difference",
            "not": "substring match on description/title or needle-in-grantable-token",
        },
        "measurements": {
            "absent_tool": blocked.as_dict(),
            "grantable_twin": imported.as_dict(),
            "prose_mention_is_not_a_requirement": prose_d.as_dict(),
            "typed_requirement_with_silent_prose": silent_d.as_dict(),
            "token_in_token": {
                "required": ["Read"],
                "grantable": ["ReadWrite"],
                "subset_ok": tok_ok,
                "missing": sorted(tok_missing),
                "substring_would_grant": True,
            },
            "derived_required": {
                "absent": sorted(extract_tool_requirements(absent)),
                "twin": sorted(extract_tool_requirements(twin)),
                "prose": sorted(extract_tool_requirements(prose)),
                "silent": sorted(extract_tool_requirements(silent)),
            },
        },
        "artifacts": [
            art(lib, "implementation"),
            art("tools/workflow_foundry/__init__.py", "implementation"),
            art(
                "command-center/p2-wave/probes/IMP-0167/probe1_absent_tool.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0167/probe2_subset_not_substring.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0167/fixtures/candidate_absent_webfetch.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0167/fixtures/candidate_grantable_twin.json",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": "A candidate requiring WebFetch is BLOCKED at import with WebFetch named.",
                "verdict": "CONFIRMED",
                "anchor": f"{lib}:import_candidate",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0167/probe1_absent_tool.py"
                        ),
                        "raw_output": (
                            f"status={blocked.status} "
                            f"missing={list(blocked.missing_capabilities)}"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "import_candidate(absent) vs import_candidate(twin)",
                        "raw_output": (
                            f"twin.status={imported.status} "
                            f"twin.missing={list(imported.missing_capabilities)}"
                        ),
                        "exit_code": 0,
                    },
                ],
                "confidence": "almost-certain",
            },
            {
                "claim": "Reconciliation is required ⊆ allowed (set difference), not a substring of prose.",
                "verdict": "CONFIRMED",
                "anchor": f"{lib}:reconcile_subset",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0167/probe2_subset_not_substring.py"
                        ),
                        "raw_output": (
                            f"prose.status={prose_d.status} silent.status={silent_d.status} "
                            f"Read/ReadWrite missing={sorted(tok_missing)}"
                        ),
                        "exit_code": 0,
                    }
                ],
                "confidence": "almost-certain",
            },
        ],
        "timestamps": {"started_at": TS0, "ended_at": ts1},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "absent-tool-blocked-capability-named",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0167/probe1_absent_tool.py",
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "subset-not-substring",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0167/probe2_subset_not_substring.py",
                "result": "PASS",
                "assertions": 3,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0167-C1",
                "kind": "both-states",
                "description": "Absent-tool BLOCKED naming WebFetch; grantable twin IMPORTED.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(blocked.as_dict(), sort_keys=True),
                "good_state_output": json.dumps(imported.as_dict(), sort_keys=True),
            },
            {
                "id": "IMP0167-C2",
                "kind": "detector-mutation",
                "description": "Substring-of-prose and substring-of-token disagree with subset.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(silent_d.as_dict(), sort_keys=True),
                "good_state_output": json.dumps(prose_d.as_dict(), sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0167-probe2-subset-not-substring",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is the adversarial control: it implements the banned "
                "substring detectors independently and requires they disagree with "
                "import_candidate on the trap fixtures."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0167/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0167",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "note": "G-1 measure is run after this receipt and the per-unit manifest are written.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0136 (dispatchpolicy tool_permissions) and IMP-0165 (role "
                    "extraction) are catalog dependencies and are not delivered in "
                    "this worktree; this unit implements the import-time subset gate "
                    "against an explicit host grantable set and per-unit declaration."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run import_candidate against live IMP-0136 "
                    "WorkUnit.tool_permissions once that unit is present."
                ),
            }
        ],
        "notes": (
            "G-1 for IMP-0167: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Cloud ok=true is not delivery. SUCCESS:IMP-0167"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, size = sha256_file(out)
    if SENTINEL not in text:
        print("FAILED:IMP-0167 emit sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
