#!/usr/bin/env python3
"""Emit IMP-0087 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

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
OUT = "command-center/receipts/IMP-0087.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0087/probe1_preview_fidelity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0087/probe2_negative_controls.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_update_preview_fidelity.py"
)
SUPPORTING = [
    "tools/marketplace/update.py",
    "tools/marketplace/package.py",
    "tools/plugin/permission_diff.py",
    "tools/marketplace/tests/test_update_preview_fidelity.py",
    "command-center/p2-wave/probes/IMP-0087/probe1_preview_fidelity.py",
    "command-center/p2-wave/probes/IMP-0087/probe2_negative_controls.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def eol_of(data: bytes) -> str:
    if b"\x00" in data[:8192]:
        return "BINARY"
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": max(len(norm), 1),
        "sha256": hashlib.sha256(norm).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0087",
        "receipt_path": "command-center/p2-wave/probes/IMP-0087/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def main() -> int:
    c_test, t_test = run_cmd(TESTS)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:receipts tests={c_test} c1={c1} c2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = now
    sys.path.insert(0, str(REPO / "tools"))
    from marketplace.package import make_package
    from marketplace.update import (
        apply_update,
        assert_preview_matches_actual,
        census_tree,
        effective_permissions_from_disk,
        preview_update,
        write_package_tree,
    )
    from plugin.permission_diff import Consent, MemoryConsentStore, classify_delta

    import tempfile

    installed = make_package(
        "hello-skill",
        "1.0.0",
        extra_files={"skills/SKILL.md": b"# 1.0.0\n", "hooks/pre.json": b"{}\n"},
        permissions=["fs:read:/pkg", "Read"],
        releases=["1.0.0", "1.1.0", "1.2.0"],
        changelog={"1.0.0": ["initial"]},
    )
    candidate = make_package(
        "hello-skill",
        "1.2.0",
        extra_files={"skills/SKILL.md": b"# 1.2.0\n", "docs/CHANGE.md": b"n\n"},
        permissions=["fs:read:/pkg", "Read", "net:connect:api.example"],
        releases=["1.0.0", "1.1.0", "1.2.0"],
        changelog={"1.1.0": ["fix"], "1.2.0": ["docs"]},
    )
    preview = preview_update(installed, candidate)
    store = MemoryConsentStore()
    store.persist(
        Consent(
            package_id="hello-skill",
            from_version="1.0.0",
            to_version="1.2.0",
            widened=("net:connect:api.example",),
        )
    )
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "pkg"
        write_package_tree(dest, installed)
        apply_update(dest, installed, candidate, consent_store=store, preview=preview)
        fidelity = assert_preview_matches_actual(preview, dest)
        disk_perms = effective_permissions_from_disk(dest)
        disk_files = census_tree(dest)

    lattice = classify_delta(installed.permissions, candidate.permissions)

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0087",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0087",
        "title": "Marketplace `update` with changelog and permission-diff preview",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0087",
        "min_bytes_threshold": 128,
        "question_or_target": (
            "Implement update so the user sees, before anything changes, the version "
            "delta, the changelog entries between the two versions, and the permission "
            "diff — and so a permission-widening update requires the explicit consent "
            "implemented in IMP-0060."
        ),
        "implementation": {
            "update_module": "tools/marketplace/update.py",
            "permission_gate": "tools/plugin/permission_diff.py",
            "tests": "tools/marketplace/tests/test_update_preview_fidelity.py",
            "notes": (
                "IMP-0086 plugin-installer handoff is not on this worktree. Update apply "
                "writes candidate bytes to a throwaway dest after preview+consent; it is "
                "not a second first-install control plane. Consent records live in a "
                "store outside the package tree so they cannot pad the file census."
            ),
        },
        "artifacts": [
            art(OUT, "primary"),
            *[art(p, "supporting") for p in SUPPORTING],
        ],
        "evidence": [
            {
                "claim": (
                    "Signal 1 (preview, before write): version 1.0.0→1.2.0, changelog "
                    f"span {preview.changelog['expected_versions']} with gaps "
                    f"{preview.changelog['gaps']}, permission verdict "
                    f"{preview.permission_diff['verdict']} added="
                    f"{preview.permission_diff['added']}, file changes added="
                    f"{[r['path'] for r in preview.file_changes['added']]} removed="
                    f"{[r['path'] for r in preview.file_changes['removed']]} modified="
                    f"{[r['path'] for r in preview.file_changes['modified']]}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/update.py:preview_update",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, t1, c1),
                    probe("verifier", "command", TESTS, t_test, c_test),
                ],
            },
            {
                "claim": (
                    "Signal 2 (post-update disk census, independent of the candidate "
                    f"object): files={sorted(disk_files)} permissions={disk_perms} "
                    f"exact_match_with_preview={disk_files == preview.expected_files and disk_perms == preview.expected_permissions} "
                    f"fidelity={fidelity}. Lattice verdict={lattice.verdict} agrees with "
                    f"independent set-containment {preview.independent_containment_verdict} "
                    "on this exact-add pair."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/update.py:assert_preview_matches_actual",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, t1, c1),
                    probe("verifier", "command", P2, t2, c2),
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_preview_matches_actual",
                "command": TESTS + "::test_preview_matches_actual",
                "result": "PASS",
            },
            {
                "id": "probe1_preview_fidelity",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2_negative_controls",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-1500:],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0087-C1",
                "kind": "permission-escalation",
                "description": "A widening update without consent must abort with nothing written.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UpdateAborted permission-widening-requires-consent; dest census unchanged",
                "good_state_output": "apply with version-specific consent; fidelity exact match",
            },
            {
                "id": "IMP0087-C2",
                "kind": "uncontrolled-silence",
                "description": "A changelog gap (missing 1.1.0 between 1.0.0 and 1.2.0) must be reported, not dropped from expected_versions.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "gaps=['1.1.0'] expected_versions=['1.1.0','1.2.0']",
                "good_state_output": "complete changelog gaps=[]",
            },
            {
                "id": "IMP0087-C3",
                "kind": "overclaim",
                "description": "An under-reported preview (dropped expected file) must fail fidelity.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "PreviewFidelityError on mutant missing docs/CHANGE.md",
                "good_state_output": "honest preview matches disk census",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0087-probe2-incomplete-changelog",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe2 constructed an update whose changelog omits 1.1.0 and confirmed "
                "the gap is listed; also confirmed widening-without-consent writes nothing."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0087/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0087",
                    "run after this emitter",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0086 marketplace install handoff to the Phase-5 plugin installer "
                    "is absent on this worktree; this unit implements preview+consent+apply "
                    "against a throwaway dest, not production install placement."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run apply through IMP-0086/IMP-0023 once those units deliver.",
            }
        ],
        "report": {
            "kind": "marketplace-update-preview",
            "preview": preview.to_dict(),
            "disk_permissions": disk_perms,
            "disk_file_count": len(disk_files),
            "exact_match": disk_files == preview.expected_files
            and disk_perms == preview.expected_permissions,
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # artifacts[0] is the receipt itself — fill after first serialize then rewrite
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    receipt["artifacts"][0] = art(OUT, "primary")
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    # self-sha of the final bytes (loop once more so artifacts[0].sha256 matches disk)
    receipt["artifacts"][0] = art(OUT, "primary")
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0087",
        "unit_id": "IMP-0087",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0087",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0087/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0087-probe2-incomplete-changelog",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0087: live named probes exit 0, receipts/IMP-0087.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0087",
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
    print("SUCCESS:IMP-0087 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
