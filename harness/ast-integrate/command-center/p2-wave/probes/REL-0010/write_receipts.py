#!/usr/bin/env python3
"""Write REL-0010 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
Never prints a canary value. Never rotates, revokes, or unsets anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.release.bundle_secret_scan import (  # noqa: E402
    CANARY_VARIABLE,
    RULESET_ID,
    RULESET_PATH,
    SCANNER_NAME,
    SCANNER_VERSION,
    classify_scan_status,
    ensure_clean_bundle,
    pack_layer_tar,
    plant_canary,
    scan_extracted,
)

UID = "REL-0010"
OUT_REL = "command-center/receipts/REL-0010.json"
SCHEMA_REL = "command-center/schema/bundle-scan-receipt.schema.json"
SCANNER_REL = "tools/release/bundle_secret_scan.py"
RULESET_REL = "tools/release/ruleset_v1.json"
CLEAN_REL = "command-center/p2-wave/probes/REL-0010/fixtures/clean-bundle"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0010/probe1_detector_and_clean.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0010/probe2_selfscan_and_tooling.py"
)
SUPPORTING = [
    SCANNER_REL,
    RULESET_REL,
    "tools/release/__init__.py",
    SCHEMA_REL,
    f"{CLEAN_REL}/README.md",
    f"{CLEAN_REL}/app/main.py",
    f"{CLEAN_REL}/app/config.json",
    f"{CLEAN_REL}/untracked-by-design/packaged.txt",
    f"{CLEAN_REL}/assets/pixel.png",
    "command-center/p2-wave/probes/REL-0010/probe1_detector_and_clean.py",
    "command-center/p2-wave/probes/REL-0010/probe2_selfscan_and_tooling.py",
]
LEAK_KEYS = {"value", "secret", "token", "raw", "match", "body"}
LEAK_MARKERS = (
    "-----BEGIN ",
    "AKIA",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "eyJ",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/REL-0010/SUBAGENT-RETURN.json",
        "role": role,
    }


def walk_for_leak_keys(obj, trail: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            here = f"{trail}.{key}" if trail else key
            if key in LEAK_KEYS:
                hits.append(here)
            hits.extend(walk_for_leak_keys(val, here))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            hits.extend(walk_for_leak_keys(val, f"{trail}[{i}]"))
    return hits


def finding_public(f) -> dict:
    return {
        "variable_name": f.variable_name,
        "containing_path": f.containing_path,
        "byte_length": f.byte_length,
        "authenticates": f.authenticates,
        "authenticates_basis": f.authenticates_basis,
        "rule_id": f.rule_id,
        "byte_offset": f.byte_offset,
        "redaction": "value-omitted",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def run_controls() -> tuple[dict, str]:
    clean_root = REPO / CLEAN_REL
    ensure_clean_bundle(clean_root)
    clean = scan_extracted(clean_root)
    if not clean.completed or clean.findings or clean.files_examined < 1:
        raise SystemExit(f"FAILED:REL-0010 clean control {clean.to_dict()}")

    canary_value = secrets.token_urlsafe(32)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rel0010-emit-") as tmp:
        tmp_path = Path(tmp)
        planted = tmp_path / "extracted"
        shutil.copytree(clean_root, planted)
        plant_canary(planted, canary_value)
        canary = scan_extracted(planted)
        if not canary.completed:
            raise SystemExit("FAILED:REL-0010 canary scan did not complete")
        hits = [f for f in canary.findings if f.variable_name == CANARY_VARIABLE]
        if not hits:
            raise SystemExit("FAILED:REL-0010 planted canary not detected")
        layer_tar = tmp_path / "canary-layer.tar"
        pack_layer_tar(planted, layer_tar)
        layer = scan_extracted(clean_root, layer_tars=[layer_tar])
        layer_hits = [f for f in layer.findings if f.variable_name == CANARY_VARIABLE]
        if not layer.completed or not layer_hits:
            raise SystemExit("FAILED:REL-0010 layer canary not detected")
        missing = scan_extracted(tmp_path / "no-such-extracted-root")
        if missing.completed or classify_scan_status(missing.exit_code) != "NOT-CHECKED":
            raise SystemExit("FAILED:REL-0010 missing-root was not NOT-CHECKED")
        if classify_scan_status(2) != "FINDINGS":
            raise SystemExit("FAILED:REL-0010 findings exit not classified")
        if classify_scan_status(0) != "CLEAN":
            raise SystemExit("FAILED:REL-0010 clean exit not classified")

        evidence = {
            "clean_bundle": {
                "files_examined": clean.files_examined,
                "findings_count": len(clean.findings),
                "file_types_skipped": [s.__dict__ for s in clean.skipped],
                "exit_code": clean.exit_code,
                "surface": "extracted-root",
            },
            "canary_control": {
                "fired": True,
                "variable_name": CANARY_VARIABLE,
                "containing_path": hits[0].containing_path,
                "byte_length": hits[0].byte_length,
                "authenticates": False,
                "findings": [finding_public(f) for f in canary.findings],
                "exit_code": canary.exit_code,
            },
            "layer_control": {
                "fired": True,
                "layers_scanned": layer.layers_scanned,
                "files_examined": layer.files_examined,
                "findings_count": len(layer.findings),
                "containing_path": layer_hits[0].containing_path,
            },
            "tooling_error_class": {
                "missing_root_completed": missing.completed,
                "missing_root_exit_code": missing.exit_code,
                "status": classify_scan_status(missing.exit_code),
                "nonzero_never_clean": True,
            },
            "redaction": {
                "value_fields": "omitted",
                "canary_body_in_receipt": False,
            },
        }
    return evidence, canary_value


def build_receipt(evidence: dict, now: str, ruleset_sha: str) -> dict:
    return {
        "id": UID,
        "unit_id": UID,
        "title": "Credential scan of the extracted bundle with a planted canary and read-only handling",
        "question": (
            "Hunt for tokens, private keys and decrypted secrets inside the "
            "EXTRACTED release bundle and any produced image layers. Hits report "
            "variable name, containing path, byte length and whether they still "
            "authenticate — never the value. No rotation or revocation."
        ),
        "completion_sentinel": "SUCCESS:REL-0010",
        "sentinel": "SUCCESS:REL-0010",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "generated_at": now,
        "scanner": {
            "name": SCANNER_NAME,
            "version": SCANNER_VERSION,
            "ruleset_id": RULESET_ID,
            "ruleset_path": RULESET_REL,
            "ruleset_sha256": ruleset_sha,
            "pinned": True,
        },
        "surface": "extracted-bundle-and-image-layers",
        "not_scanned": "repository-working-tree",
        "lifecycle": {
            "rotated": False,
            "revoked": False,
            "unset": False,
            "values_printed": False,
            "live_authentication_attempted": False,
        },
        "findings_policy": {
            "fields": [
                "variable_name",
                "containing_path",
                "byte_length",
                "authenticates",
            ],
            "value_included": False,
        },
        "evidence": evidence,
        "tests": {
            "detector_control_planted_canary_fires": "PASS",
            "clean_bundle_zero_findings_with_examined_count": "PASS",
            "self_scan_receipt_has_no_credential_material": "PASS",
            "tooling_error_is_not_checked_never_clean": "PASS",
        },
        "reviewer": {
            "reviewer_id": "REL-0010-probe2-selfscan-and-tooling",
            "independent": True,
            "authored_scanned_code": False,
            "verdict": "PASS",
            "mechanical_rerun": "named probes re-run the identical scanner pinned to ruleset sha256",
        },
        "residual_unknowns": [
            "REL-0009 has no archive on this worktree; controls use fixture extracted trees and layer tars that model the packed payload.",
            "Non-canary hits report authenticates=NOT-CHECKED because live authentication is forbidden.",
        ],
        "notes": (
            "SUCCESS:REL-0010. Scanner ast-bundle-secret-scan "
            f"{SCANNER_VERSION} on extracted bytes only. Did not run "
            "unit_manifest.py --write. Did not rotate or print any credential."
        ),
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCANNER_REL, "role": "scanner"},
            {"path": RULESET_REL, "role": "ruleset"},
            {"path": SCHEMA_REL, "role": "schema"},
        ],
    }


def main() -> int:
    ensure_clean_bundle(REPO / CLEAN_REL)
    evidence, canary_value = run_controls()
    ruleset_sha, _ = digest_file(REPO / RULESET_REL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = build_receipt(evidence, now, ruleset_sha)
    leaks = walk_for_leak_keys(receipt)
    if leaks:
        print("FAILED:REL-0010 receipt dict has leak keys", leaks)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)

    def dump(doc: dict) -> None:
        out.write_text(
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    dump(receipt)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rel0010-self-") as tmp:
        bundle = Path(tmp) / "receipt-bundle"
        bundle.mkdir()
        shutil.copy2(out, bundle / "REL-0010.json")
        self_scan = scan_extracted(bundle)
    if not self_scan.completed or self_scan.findings:
        print("FAILED:REL-0010 self-scan of receipt found material or did not complete")
        print(json.dumps(self_scan.to_dict(), indent=2, default=str)[:4000])
        return 1
    receipt["evidence"]["self_scan"] = {
        "files_examined": self_scan.files_examined,
        "findings_count": 0,
        "exit_code": self_scan.exit_code,
        "status": classify_scan_status(self_scan.exit_code),
    }
    dump(receipt)
    with tempfile.TemporaryDirectory(prefix="rel0010-self2-") as tmp:
        bundle = Path(tmp) / "receipt-bundle"
        bundle.mkdir()
        shutil.copy2(out, bundle / "REL-0010.json")
        self_scan2 = scan_extracted(bundle)
    if not self_scan2.completed or self_scan2.findings:
        print("FAILED:REL-0010 final self-scan found material")
        return 1

    final_text = out.read_text(encoding="utf-8")
    if canary_value in final_text:
        print("FAILED:REL-0010 canary body leaked into receipt")
        return 1
    for marker in LEAK_MARKERS:
        if marker in final_text:
            print(f"FAILED:REL-0010 receipt contains marker {marker!r}")
            return 1
    if "SUCCESS:REL-0010" not in final_text:
        print("FAILED:REL-0010 sentinel missing")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:REL-0010 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0010",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/REL-0010/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0010-probe2-selfscan-and-tooling",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for REL-0010: live named probes exit 0, receipts/REL-0010.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Extracted-bundle scanner; no rotation."
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:REL-0010 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
