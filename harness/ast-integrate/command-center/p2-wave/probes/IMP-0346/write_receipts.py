#!/usr/bin/env python3
"""Write IMP-0346 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0346"
OUT = "command-center/receipts/IMP-0346.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0346/probe1_commit_reveal_tally.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0346/probe2_deanonymisation.py"
)
SUPPORTING = [
    "tools/council/vote/secret.py",
    "tools/council/vote/__init__.py",
    "command-center/p2-wave/probes/IMP-0346/probe1_commit_reveal_tally.py",
    "command-center/p2-wave/probes/IMP-0346/probe2_deanonymisation.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json_object(text: str) -> dict | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return None


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0346/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    ev1 = first_json_object(t1) or {}
    ev2 = first_json_object(t2) or {}
    secret_rel = "tools/council/vote/secret.py"
    secret_sha, secret_bytes = digest(REPO / secret_rel)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "artifact_paths": [
            OUT,
            secret_rel,
            "command-center/p2-wave/probes/IMP-0346/probe1_commit_reveal_tally.py",
            "command-center/p2-wave/probes/IMP-0346/probe2_deanonymisation.py",
        ],
        "completion_sentinel": "SUCCESS:IMP-0346",
        "evidence": [
            {
                "id": "E1-independent-tally-recompute",
                "kind": "live-probe",
                "summary": (
                    "Third party recomputed the published tally from the "
                    "commitment set plus openings; no voter roster used."
                ),
                "probe": "probe1_commit_reveal_tally",
                "measured": ev1,
            },
            {
                "id": "E2-deanonymisation-vs-chance",
                "kind": "live-probe",
                "summary": (
                    "Positional linkage on the public bulletin stayed near "
                    "chance under canonical commitment order; the same attack "
                    "on submission order rose to 1.0."
                ),
                "probe": "probe2_deanonymisation",
                "measured": ev2,
            },
        ],
        "generated_at": now,
        "id": UID,
        "negative_control_ids": [
            "NC-ordered-publication-attack-rises",
            "NC-mutant-nonce-refused",
            "NC-partial-openings-refused",
        ],
        "owner_signoff": {
            "block": (
                "Owner sign-off is a separate half of the dual-control. The "
                "adversarial reviewer must not grant it."
            ),
            "granted": False,
            "granted_by_reviewer": False,
            "required": False,
            "status": "NOT-GRANTED",
        },
        "profile": "council-runtime-module",
        "question": (
            "Can a third party recompute the published tally from the "
            "committed ballots WITHOUT learning who cast which ballot?"
        ),
        "residual_unknowns": [
            (
                "IMP-0302 tools/council/vote/tally.py is absent; this module's "
                "tally is a bijection-checked count of opened choices, not "
                "quorum/abstention composition."
            ),
            (
                "IMP-0276 tools/council/integrity/anonymity.py is absent; "
                "unlinkability here is publication-order + no voter id on the "
                "bulletin, not per-round pseudonyms."
            ),
            (
                "11-COUNCIL-SPECIFICATION.md is not in this worktree; "
                "spec_anchor is the catalog unit text."
            ),
            (
                "Anonymity is computational unlinkability of openings to the "
                "submission roster. Unique opened choices plus an external "
                "preference map would still identify voters; that channel is "
                "outside the positional-order test."
            ),
        ],
        "reviewer": {
            "grants_owner_signoff": False,
            "independent": True,
            "reviewer_id": "IMP-0346-probe2-deanonymisation",
            "scope": (
                "Starts from the public bulletin and a known submission roster "
                "side-channel; does not take the implementer summary as evidence."
            ),
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "sentinel": "SUCCESS:IMP-0346",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0346] "
            "question_or_target + tests_required (commit/reveal/tally; "
            "de-anonymisation at chance; ordered-publication negative control)"
        ),
        "state": "SUCCESS",
        "test_ids": [
            "unit:commit-reveal-tally-verification",
            "security:deanonymisation-at-chance",
            "negative-control:submission-order-attack-rises",
        ],
        "tests": [
            {
                "id": "probe1_commit_reveal_tally",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "probe2_deanonymisation",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "title": "Secret ballot with a verifiable tally",
        "unit_id": UID,
        "secret_module": {
            "path": secret_rel,
            "sha256": secret_sha,
            "bytes": secret_bytes,
        },
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/IMP-0346/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "notes": (
            "G-1 for IMP-0346: live named probes exit 0, receipts/IMP-0346.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0346-probe2-deanonymisation",
            "verdict": "PASS",
            "grants_owner_signoff": False,
        },
        "sentinel": "SUCCESS:IMP-0346",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0346 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
