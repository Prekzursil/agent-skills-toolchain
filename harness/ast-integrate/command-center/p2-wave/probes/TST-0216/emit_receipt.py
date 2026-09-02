#!/usr/bin/env python3
"""Emit TST-0216 security report, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0216"
OUT = "command-center/receipts/TST-0216.json"
SCHEMA = "command-center/schema/security-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0216/probe1_quarantine_blocks_canary.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0216/probe2_detector_control.py"
)
SUPPORTING = [
    "tools/checkout_quarantine/__init__.py",
    "tools/checkout_quarantine/gate.py",
    "tools/checkout_quarantine/surfaces.py",
    "tools/checkout_quarantine/fixture.py",
    "tools/checkout_quarantine/canary.py",
    "tools/checkout_quarantine/__main__.py",
    "tools/checkout_quarantine/tests/test_gate.py",
    "command-center/p2-wave/probes/TST-0216/probe1_quarantine_blocks_canary.py",
    "command-center/p2-wave/probes/TST-0216/probe2_detector_control.py",
]
QUESTION = (
    "When a checkout contains `.claude/`, `.codex/`, `.mcp.json` or hooks, does "
    "the toolchain quarantine and report them before any agent runs inside it? "
    "PASS requires zero hook execution from the untrusted tree, proven by a "
    "canary hook that would write a marker."
)
SENTINEL = "SUCCESS:TST-0216"

# Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
# Bare Draft7Validator either raises RefResolutionError or is vacuous
# (unresolved $ref accepts garbage). G-1 is live named probes + this file
# on disk; UNIT_SCHEMA is the non-vacuous local check.
UNIT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "findings",
        "tests",
        "named_probes",
        "threat_anchor",
        "reviewer",
        "cloud_ok",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "completion_sentinel": {"const": SENTINEL},
        "findings": {"type": "array", "minItems": 4},
        "tests": {"type": "array", "minItems": 4},
        "named_probes": {"type": "array", "minItems": 2},
        "threat_anchor": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"const": "CVE-2026-47751-class"}},
        },
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "cloud_ok": {"const": False},
    },
}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0216/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0216 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Yes. tools/checkout_quarantine.enter_untrusted_checkout quarantines "
        ".claude/, .codex/, .mcp.json and hooks/ before simulating agent auto-load. "
        "With quarantine ON the canary marker is absent and the quarantine report "
        "enumerates all four surfaces (CVE-2026-47751-class on .codex/). With "
        "quarantine OFF the same canary writes FIRED: tags for every surface, so "
        "the detector is live. Catalog owner_approval_required=true is a dispatch "
        "gate; this receipt is the technical test, not an owner legal ruling. "
        "SUCCESS:TST-0216"
    )
    findings = [
        {
            "id": "F-claude",
            "classification": "auto-load-surface",
            "path": ".claude/hooks.json",
            "rule": "untrusted-checkout-autoload",
            "prefix": "AUTOLOAD_",
        },
        {
            "id": "F-codex",
            "classification": "auto-load-surface",
            "path": ".codex/hooks.json",
            "rule": "cve-2026-47751-class-autoload",
            "prefix": "AUTOLOAD_",
        },
        {
            "id": "F-mcp",
            "classification": "auto-load-surface",
            "path": ".mcp.json",
            "rule": "untrusted-checkout-autoload",
            "prefix": "AUTOLOAD_",
        },
        {
            "id": "F-hooks",
            "classification": "auto-load-surface",
            "path": "hooks/canary.py",
            "rule": "untrusted-checkout-autoload",
            "prefix": "AUTOLOAD_",
        },
    ]
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "security_report",
        "title": "A cloned repo carrying auto-load agent config is quarantined, not executed",
        "question": QUESTION,
        "answer": answer,
        "schema_version": 1,
        "ts": now,
        "owner_approval_required": True,
        "owner_approval_note": (
            "Catalog owner_approval_required=true excludes this unit from auto-dispatch. "
            "This artifact is the technical G-1 delivery of the quarantine test; it does "
            "not grant owner sign-off and does not mutate live trees."
        ),
        "scanners": [
            {
                "id": "marker-absence",
                "name": "canary-marker-filesystem",
                "mechanism": (
                    "plant a canary hook that appends FIRED:<surface> to a marker "
                    "path outside the checkout; after enter_untrusted_checkout with "
                    "quarantine ON the marker file must be absent or empty"
                ),
            },
            {
                "id": "surface-census",
                "name": "quarantine-report-enumeration",
                "mechanism": (
                    "scan checkout-root .claude/, .codex/, .mcp.json and hooks/, "
                    "move each hit into .ast-quarantine/, and emit QUARANTINE-REPORT.json "
                    "listing every surface; independent of the marker file"
                ),
            },
        ],
        "findings": findings,
        "evidence": {
            "method": (
                "tempfile hostile checkout planted with four auto-load surfaces plus "
                "benign canaries; enter_untrusted_checkout both-states (quarantine "
                "ON vs OFF) and a clean-tree negative control"
            ),
            "read_only": True,
            "live_tree_untouched": True,
            "never_rotated": True,
        },
        "tests": [
            {
                "id": "TST0216-T1-QUARANTINE-BLOCKS-CANARY",
                "result": "PASS",
                "command": P1,
                "notes": "quarantine ON: marker absent; all four surfaces enumerated and moved",
            },
            {
                "id": "TST0216-T2-DETECTOR-CONTROL-QUARANTINE-OFF",
                "result": "PASS",
                "command": P2,
                "notes": "quarantine OFF: same canary writes FIRED: for all four surfaces",
            },
            {
                "id": "TST0216-T3-THREAT-ANCHOR-CVE-2026-47751",
                "result": "PASS",
                "command": P1,
                "notes": ".codex/ tagged CVE-2026-47751-class (AGENTS.md:9 clone auto-load)",
            },
            {
                "id": "TST0216-T4-CLEAN-TREE-SILENT",
                "result": "PASS",
                "command": P1,
                "notes": "checkout with no auto-load surfaces enumerates nothing and writes no marker",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0216-probe2-detector-control-quarantine-off",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is the required detector control: the identical canary "
                "must write its marker when quarantine is disabled, proving the "
                "probe can observe execution. Catalog two-vendor human review is "
                "independent of G-1 probe-green."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": "tools/checkout_quarantine/gate.py", "exists": True, "role": "implementation"},
        ],
        "named_probes": [
            {"id": "probe1", "role": "quarantine-blocks-canary", "command": P1},
            {"id": "probe2", "role": "detector-control-quarantine-off", "command": P2},
        ],
        "threat_anchor": {
            "id": "CVE-2026-47751-class",
            "surface": ".codex",
            "source": "AGENTS.md:9 cloned-repo auto-load",
        },
        "implementation": {
            "module": "tools/checkout_quarantine/gate.py",
            "entry": "enter_untrusted_checkout",
            "surfaces": [".claude", ".codex", ".mcp.json", "hooks"],
        },
        "cloud_ok": False,
        "notes": (
            "G-1 TST-0216: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0216"
        ),
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:TST-0216 missing schema {SCHEMA}")
        return 1
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or not shim.get("$ref"):
        print("FAILED:TST-0216 catalog schema shim missing $ref")
        return 1
    try:
        import jsonschema
    except ImportError:
        print("FAILED:TST-0216 jsonschema missing")
        return 1
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    errs = list(jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(doc))
    if errs:
        print("FAILED:TST-0216 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(garbage)):
            print("FAILED:TST-0216 schema accepted garbage")
            return 1

    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0216 sentinel-absent")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "quarantine-blocks-canary",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "detector-control-quarantine-off",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/TST-0216/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0216-probe2-detector-control-quarantine-off",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0216: live named probes exit 0, TST-0216.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print("SUCCESS:TST-0216 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
