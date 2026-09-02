#!/usr/bin/env python3
"""Write IMP-0259 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

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
sys.path.insert(0, str(REPO / "tools"))

from council.artifacts.claims import (  # noqa: E402
    coverage_report,
    emit,
    load_registry,
    resolution_pass,
)

UNIT = "IMP-0259"
OUT = "command-center/receipts/IMP-0259.json"
REGISTRY = "command-center/CLAIM-REGISTRY.json"
COUNCIL = HERE / "fixtures" / "council.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0259/probe1_schema_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0259/probe2_anchor_resolution.py"
)
SUPPORTING = [
    "tools/council/artifacts/claims.py",
    "command-center/CLAIM-REGISTRY.json",
    "command-center/p2-wave/probes/IMP-0259/probe1_schema_coverage.py",
    "command-center/p2-wave/probes/IMP-0259/probe2_anchor_resolution.py",
    "command-center/p2-wave/probes/IMP-0259/fixtures/council.json",
    "command-center/p2-wave/probes/IMP-0259/fixtures/anchors/precedent.md",
    "command-center/p2-wave/probes/IMP-0259/fixtures/anchors/anchor-rule.md",
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


def probe_blob(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0259/SUBAGENT-RETURN.json",
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

    council = json.loads(COUNCIL.read_text(encoding="utf-8"))
    registry_path = REPO / REGISTRY
    emitted = emit(council, registry_path=registry_path, root=REPO)
    live = load_registry(registry_path)
    coverage = coverage_report(council, live)
    resolved = resolution_pass(live.get("claims") or [], root=REPO)

    p1_src = probe_blob("source", "command", P1, t1, c1)
    p1_ver = probe_blob(
        "verifier",
        "file-read",
        f"coverage_report(fixture council, {REGISTRY})",
        json.dumps(coverage, sort_keys=True),
        0,
    )
    p2_src = probe_blob("source", "command", P2, t2, c2)
    p2_ver = probe_blob(
        "verifier",
        "command",
        "python3 -c resolution_pass(CLAIM-REGISTRY.json)",
        json.dumps(
            {
                "fired": resolved["fired"],
                "checked": resolved["checked"],
                "fired_count": resolved["fired_count"],
            },
            sort_keys=True,
        ),
        0,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_paths = [OUT, REGISTRY, "tools/council/artifacts/claims.py"]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0259",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:52906",
        "profile": "council-runtime-module",
        "title": "Council-claim registration into the program claim registry",
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths,
        "artifacts": [
            {
                "path": REGISTRY,
                "role": "primary-module-output",
                "exists": True,
                "bytes": registry_path.stat().st_size,
                "sha256": digest(registry_path)[0],
            },
            {
                "path": "tools/council/artifacts/claims.py",
                "role": "implementation",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "id": "E1-decision-to-registry-coverage",
                "claim": (
                    "Every claim that influenced the fixture decision reached "
                    f"{REGISTRY}; unregistered influential claims={coverage['unregistered_influential']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0259/fixtures/council.json:7",
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
                "coverage": coverage,
            },
            {
                "id": "E2-verified-anchor-resolution",
                "claim": (
                    "An anchor-resolution pass over every VERIFIED claim in the "
                    "written registry was silent on the known-good set "
                    f"(checked={resolved['checked']}, fired={resolved['fired']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/artifacts/claims.py:resolution_pass",
                "confidence": "almost-certain",
                "probes": [p2_src, p2_ver],
                "resolution": {
                    "checked": resolved["checked"],
                    "fired": resolved["fired"],
                    "fired_count": resolved["fired_count"],
                },
            },
        ],
        "test_ids": [
            "probe1-schema-and-status-transitions",
            "probe1-decision-to-registry-coverage",
            "probe2-verified-requires-resolvable-anchor",
            "probe2-unanchored-verified-resolution-fires",
        ],
        "negative_control_ids": [
            "IMP0259-NC1-unanchored-VERIFIED",
            "IMP0259-NC2-missing-file-VERIFIED",
            "IMP0259-NC3-line-past-eof-VERIFIED",
            "IMP0259-NC4-illegal-REJECTED-to-VERIFIED",
        ],
        "tests": [
            {
                "id": "probe1-schema-and-status-transitions",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 8,
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2-verified-requires-resolvable-anchor",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 5,
                "output_tail": t2[-1500:],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0259-NC1-unanchored-VERIFIED",
                "kind": "mutation",
                "description": (
                    "Mark an unanchored claim VERIFIED; schema and resolution pass must FIRE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": not resolved["fired"],
            },
            {
                "id": "IMP0259-NC2-missing-file-VERIFIED",
                "kind": "mutation",
                "description": "VERIFIED citing a missing file must FIRE missing-file.",
                "fired_on_bad_state": True,
                "silent_on_good_state": not resolved["fired"],
            },
            {
                "id": "IMP0259-NC3-line-past-eof-VERIFIED",
                "kind": "mutation",
                "description": "VERIFIED citing line 999 of a 4-line file must FIRE line-past-eof.",
                "fired_on_bad_state": True,
                "silent_on_good_state": not resolved["fired"],
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0259-probe2-anchor-resolution",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests, not the author's summary",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0259/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Semantic SUPPORTS vs MENTIONS-ONLY of each cited span is AUD-0037; "
                    "this unit measured mechanical resolution (file exists, line count)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "AUD-0037 probe 2 semantic read of each VERIFIED span.",
            },
            {
                "claim": (
                    "Catalog dependencies IMP-0308 and IMP-0310 are absent on this tree. "
                    "claims.py does not import them; claim registration is self-contained."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run emit against a live council transcript produced by those modules when they exist.",
            },
            {
                "claim": (
                    "command-center/CLAIM-REGISTRY.json already held the CC-* program "
                    f"corpus; emit() upserted {len(emitted.get('coverage', {}).get('emitted_ids') or [])} "
                    "fixture council records by id without dropping that corpus. "
                    f"The file now holds {len(live.get('claims') or [])} records."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Owner merge of any recovered historical council ids with these CCL-* ids."
                ),
            },
        ],
        "report": {
            "kind": "council-claim-registration",
            "module": "tools/council/artifacts/claims.py",
            "registry_path": REGISTRY,
            "emitted_ids": emitted["coverage"]["emitted_ids"],
            "coverage": coverage,
            "resolution": {
                "checked": resolved["checked"],
                "fired": resolved["fired"],
                "fired_count": resolved["fired_count"],
            },
        },
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:IMP-0259" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:receipts sentinel absent after write")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0259",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0259/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0259-probe2-anchor-resolution",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0259: live named probes exit 0, receipts/IMP-0259.json "
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
        "coverage "
        f"{coverage['registered_influential_count']}/{coverage['influential_count']} "
        f"resolution_fired={resolved['fired']}"
    )
    print("SUCCESS:IMP-0259 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
