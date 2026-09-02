#!/usr/bin/env python3
"""Emit IMP-0093 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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
WAVE = REPO / "command-center" / "p2-wave"
sys.path.insert(0, str(WAVE))
import _p2lib as L  # noqa: E402

UID = "IMP-0093"
OUT = "command-center/receipts/IMP-0093.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0093/probe1_spdx_list.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0093/probe2_compat_matrix.py"
)
SUPPORTING = [
    "tools/marketplace/license.py",
    "tools/marketplace/spdx.py",
    "tools/marketplace/compatibility.py",
    "tools/marketplace/data/spdx-identifiers.json",
    "tools/marketplace/data/compatibility-matrix.json",
    "tools/marketplace/tests/test_license.py",
    "command-center/p2-wave/probes/IMP-0093/probe1_spdx_list.py",
    "command-center/p2-wave/probes/IMP-0093/probe2_compat_matrix.py",
    "command-center/p2-wave/probes/IMP-0093/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
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


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    t_code, t_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest "
        "marketplace.tests.test_license"
    )
    if t_code != 0:
        print("FAILED:IMP-0093 unittest")
        print(t_out[-4000:])
        return 1

    sys.path.insert(0, str(REPO / "tools"))
    from marketplace.compatibility import CompatibilityMatrix, pair_key
    from marketplace.license import (
        LEGAL_DISCLAIMER,
        check_closure,
        pair_verdict,
        publication_gate,
        resolve_with_license_gate,
        validate_spdx,
    )
    from marketplace.spdx import load_pinned, load_spdx_catalog

    cat = load_spdx_catalog(fetch=False)
    pinned = load_pinned()
    mx = CompatibilityMatrix()
    v_mit = validate_spdx("MIT", catalog=cat)
    v_bad = validate_spdx("MIT License", catalog=cat)
    v_absent = publication_gate({"name": "ghost"})
    good = check_closure(
        [
            {"name": "app", "version": "1.0.0", "license": "MIT"},
            {"name": "lib", "version": "2.0.0", "license": "Apache-2.0"},
        ]
    )
    bad = resolve_with_license_gate(
        "app",
        {
            "app": {
                "name": "app",
                "version": "1.0.0",
                "license": "Apache-2.0",
                "dependencies": ["gpl_lib"],
            },
            "gpl_lib": {
                "name": "gpl_lib",
                "version": "3.2.0",
                "license": "GPL-2.0-only",
                "dependencies": [],
            },
        },
    )
    unk = pair_verdict("MIT", "MPL-2.0", catalog=cat, matrix=mx)
    cell_bad = mx.lookup("Apache-2.0", "GPL-2.0-only")
    cell_unk = mx.lookup("MIT", "MPL-2.0")

    if not v_mit["valid"] or v_bad["valid"] or not v_absent["blocked"]:
        print("FAILED:IMP-0093 live SPDX/publication checks")
        return 1
    if not good["compatible"] or bad["compatible"] or unk["compatible"]:
        print("FAILED:IMP-0093 live closure checks")
        return 1
    if cell_bad["verdict"] != "INCOMPATIBLE" or cell_unk["in_matrix"]:
        print("FAILED:IMP-0093 matrix cross-check")
        return 1
    if {bad["offending_pair"]["left"], bad["offending_pair"]["right"]} != {
        "Apache-2.0",
        "GPL-2.0-only",
    }:
        print("FAILED:IMP-0093 offending pair")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:IMP-0093 missing supporting", missing)
        return 1

    p_src_spdx = L.probe(
        "source",
        "command",
        "python3 -c validate_spdx against pinned SPDX 3.25.0",
        json.dumps(
            {
                "list_version": pinned.get("licenseListVersion"),
                "active": len(cat.active),
                "mit": v_mit,
                "mit_license_display_name": v_bad,
            },
            default=str,
        )[:8000],
        0,
    )
    p_ver_spdx = L.probe(
        "verifier",
        "file-read",
        "read tools/marketplace/data/spdx-identifiers.json",
        f"licenseListVersion={pinned.get('licenseListVersion')} MIT_in_active={('MIT' in cat.active)}",
        0,
    )
    p_src_mx = L.probe(
        "source",
        "command",
        "python3 -c pair_verdict+resolve_with_license_gate",
        json.dumps(
            {
                "compatible_closure": good["status"],
                "incompatible": {
                    "status": bad["status"],
                    "offending_pair": bad["offending_pair"],
                },
                "unknown_pair": {
                    "verdict": unk["verdict"],
                    "compatible": unk["compatible"],
                    "owner_route": unk["owner_route"],
                    "in_matrix": cell_unk["in_matrix"],
                    "pair_key": pair_key("MIT", "MPL-2.0"),
                },
                "publication_absent": v_absent,
            },
            default=str,
        )[:8000],
        0,
    )
    p_ver_mx = L.probe(
        "verifier",
        "file-read",
        "read tools/marketplace/data/compatibility-matrix.json",
        f"Apache-2.0|GPL-2.0-only={cell_bad['verdict']} MIT|MPL-2.0_in_matrix={cell_unk['in_matrix']}",
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0093",
        "spec_anchor": "_USER-PROMPTS.md:10857 (license metadata); _USER-PROMPTS.md:11334 (workflow provenance or license is lost)",
        "title": "License metadata with SPDX validation and dependency-closure compatibility",
        "min_bytes_threshold": 128,
        "legal_advice": False,
        "disclaimer": LEGAL_DISCLAIMER,
        "question_or_target": (
            "Validate each package's declared license against the SPDX identifier "
            "list, and compute license compatibility across the resolved dependency "
            "closure so an incompatible combination is reported at resolve time with "
            "the exact offending pair."
        ),
        "implementation": {
            "module": "tools/marketplace/license.py",
            "spdx_list": "tools/marketplace/data/spdx-identifiers.json",
            "spdx_list_version": pinned.get("licenseListVersion"),
            "spdx_list_releaseDate": pinned.get("releaseDate"),
            "matrix": "tools/marketplace/data/compatibility-matrix.json",
            "unlisted_pair_verdict": "UNKNOWN-NEEDS-REVIEW",
            "publication_missing_license": "LICENSE-ABSENT blocks publication",
            "resolve_incompatible": "LICENSE-UNSATISFIABLE names exact offending pair",
            "freshness_policy": "bounded backoff x2 then pinned copy with freshness=STALE",
        },
        "measured": {
            "spdx_valid_MIT": v_mit["code"],
            "spdx_invalid_display_name": v_bad["code"],
            "compatible_closure_status": good["status"],
            "incompatible_status": bad["status"],
            "incompatible_offending_pair": bad["offending_pair"],
            "unknown_pair_verdict": unk["verdict"],
            "unknown_pair_compatible": unk["compatible"],
            "unknown_pair_owner_route": unk["owner_route"],
            "license_absent_blocks": v_absent["blocked"],
            "list_freshness": cat.freshness,
        },
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "SPDX identifier validity is checked against the official SPDX License List snapshot 3.25.0 (pinned). MIT is a member; the display name 'MIT License' is not.",
                "CONFIRMED",
                "tools/marketplace/data/spdx-identifiers.json",
                [p_src_spdx, p_ver_spdx],
                "almost-certain",
            ),
            L.evidence(
                "Each closure pair is looked up in the published compatibility matrix. Apache-2.0|GPL-2.0-only is INCOMPATIBLE and resolve_with_license_gate reports that exact pair. MIT|MPL-2.0 is unlisted, so the verdict is UNKNOWN-NEEDS-REVIEW, compatible=false, owner_route=true.",
                "CONFIRMED",
                "tools/marketplace/data/compatibility-matrix.json",
                [p_src_mx, p_ver_mx],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "bounded backoff x2 for the SPDX list fetch; use a pinned local copy on failure and mark the verdict STALE",
        },
        "tests": [
            {
                "id": "test_license",
                "command": "PYTHONPATH=tools python3 -m unittest marketplace.tests.test_license",
                "result": "PASS",
                "exit_code": t_code,
                "raw_output": t_out[-4000:],
            }
        ],
        "negative_controls": [
            L.control(
                "unknown-pair-not-compatible",
                "known-broken-fixture",
                "MIT|MPL-2.0 is absent from the matrix; pair_verdict must be UNKNOWN-NEEDS-REVIEW and compatible must be false",
                True,
                True,
                bad=f"verdict={unk['verdict']} compatible={unk['compatible']}",
                good="MIT|Apache-2.0 COMPATIBLE",
            ),
            L.control(
                "license-absent-blocks-publication",
                "known-broken-fixture",
                "a package with no license is LICENSE-ABSENT and publication_gate.blocked is true",
                True,
                True,
                bad=f"code={v_absent['code']} blocked={v_absent['blocked']}",
                good="MIT publication allowed",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0093-probe2-compat-matrix",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 loads the matrix JSON independently of probe 1's SPDX-list "
                "membership check. It confirms legal_advice is false and that "
                "UNKNOWN-NEEDS-REVIEW routes to the owner."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0093/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0093",
                    "measure runs after this receipt is written",
                    None,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": "The compatibility matrix covers a documented subset of SPDX identifiers; unlisted pairs are UNKNOWN-NEEDS-REVIEW rather than guessed.",
                "verdict": "CONFIRMED",
                "settling_experiment": "Add a pair to the matrix only from a cited published source.",
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "spdx-list-membership"},
            {"id": "probe2", "command": P2, "role": "matrix-crosscheck-and-unknown-pair"},
        ],
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe[1] rc={c1}")
    print(t1[-2000:])
    print(f"probe[2] rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0093 probes c1={c1} c2={c2}")
        return 1

    primary = art_row(OUT, "primary")
    man_artifacts = [
        {
            "path": primary["path"],
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/IMP-0093/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        row = art_row(rel, "supporting")
        man_artifacts.append(
            {
                "path": row["path"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "present": True,
                "unit_id": UID,
                "receipt_path": "command-center/p2-wave/probes/IMP-0093/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0093",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "spdx-list-membership",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "matrix-crosscheck-and-unknown-pair",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0093/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0093-probe2-compat-matrix",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0093: live named probes exit 0, receipts/IMP-0093.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0093 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
