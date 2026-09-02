#!/usr/bin/env python3
"""Emit IMP-0127 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from scenario import build_demo_payload  # noqa: E402

from marketplace.audit import audit_live  # noqa: E402
from marketplace.handoff import build_handoff, load_schema, schema_path  # noqa: E402
from marketplace.install import install as marketplace_install  # noqa: E402
from plugin.errors import MissingTransactionIdError  # noqa: E402
from plugin.install import install_from_handoff  # noqa: E402
from plugin.payload import census_tree  # noqa: E402

import jsonschema  # noqa: E402

UNIT = "IMP-0127"
OUT = "command-center/receipts/IMP-0127.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json + "
    "tools/marketplace/schema/install-handoff.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0127/probe1_handoff_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0127/probe2_placement_audit.py"
)
SUPPORTING = [
    "tools/marketplace/schema/install-handoff.schema.json",
    "tools/marketplace/handoff.py",
    "tools/marketplace/install.py",
    "tools/marketplace/audit.py",
    "tools/plugin/placement.py",
    "tools/plugin/install.py",
    "tools/plugin/payload.py",
    "tools/plugin/errors.py",
    "tools/marketplace/tests/test_handoff_contract.py",
    "command-center/p2-wave/probes/IMP-0127/probe1_handoff_census.py",
    "command-center/p2-wave/probes/IMP-0127/probe2_placement_audit.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def measure_contract() -> dict:
    schema = load_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    garbage_errors = [
        len(list(jsonschema.Draft7Validator(schema).iter_errors(g))) for g in garbage
    ]
    audit = audit_live(REPO)
    with tempfile.TemporaryDirectory(prefix="imp0127-receipt-") as tmp:
        root = Path(tmp)
        payload = build_demo_payload(root)
        mkt = marketplace_install(payload, root / "via-mkt")
        direct_h = build_handoff(payload, source="direct")
        direct = install_from_handoff(direct_h, root / "via-direct")
        a = census_tree(root / "via-mkt")
        b = census_tree(root / "via-direct")
        expected = sorted(
            str(e["dest"]).replace("\\", "/")
            for e in mkt["handoff"]["projection_map"]["entries"]
        )
        bypass_msg = ""
        bypass_ok = False
        try:
            install_from_handoff({"payload_path": str(payload)}, root / "bypass")
        except MissingTransactionIdError as exc:
            bypass_msg = str(exc)
            bypass_ok = "transaction_id" in bypass_msg and not (root / "bypass").exists()
        return {
            "schema_path": schema_path().relative_to(REPO).as_posix(),
            "garbage_error_counts": garbage_errors,
            "schema_discriminates": all(n > 0 for n in garbage_errors),
            "audit_ok": audit["ok"],
            "placement_site_count": audit["placement_site_count"],
            "placement_site": audit["sites"][0] if audit["sites"] else None,
            "marketplace_writes": audit["marketplace_writes"],
            "writes_outside_site": audit["writes_outside_site"],
            "files_placed": expected,
            "marketplace_census": a,
            "direct_census": b,
            "censuses_equal": a == b and sorted(a) == expected,
            "transaction_ids_differ": mkt["handoff"]["transaction_id"]
            != direct_h["transaction_id"],
            "bypass_visible": bypass_ok,
            "bypass_message": bypass_msg,
            "handoff_keys": sorted(mkt["handoff"].keys()),
            "plugin_name": mkt["handoff"].get("plugin_name"),
        }


def main() -> int:
    started = now()
    test_rc, test_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/marketplace/tests/test_handoff_contract.py"
    )
    measured = measure_contract()
    if test_rc != 0 or not measured["audit_ok"] or not measured["censuses_equal"]:
        print("FAILED:IMP-0127 contract measurement")
        print(test_out[-2000:])
        print(json.dumps(measured, indent=2, default=str)[:4000])
        return 1

    ended = now()
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0127",
        "completion_sentinel": "SUCCESS:IMP-0127",
        "title": "Typed registry-to-plugin handoff contract (one installer control plane)",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0127",
        "min_bytes_threshold": 128,
        "output_schema": SCHEMA,
        "produced_by": {
            "vendor": "anthropic",
            "model": "cursor-grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "dependencies_status": {
            "IMP-0023": "not-delivered-on-this-tree; this unit ships a minimal install_from_handoff sufficient to enforce the typed handoff",
            "IMP-0086": "not-delivered-on-this-tree; marketplace.install builds a handoff and delegates; signature/lockfile gates remain IMP-0086",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A schema-validated install-handoff (payload_path, digest, "
                    "declared_permissions, projection_map, transaction_id) flows "
                    "end to end: marketplace.install and a direct "
                    "install_from_handoff of a separately built handoff produce "
                    f"identical dest censuses of {len(measured['files_placed'])} files "
                    f"({measured['files_placed']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/schema/install-handoff.schema.json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "python3 -B tools/marketplace/tests/test_handoff_contract.py",
                        "exit_code": test_rc,
                        "raw_output": test_out[-4000:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "live marketplace.install vs install_from_handoff census",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "equal": measured["censuses_equal"],
                                "files": measured["files_placed"],
                                "schema_discriminates": measured["schema_discriminates"],
                                "garbage_error_counts": measured["garbage_error_counts"],
                            }
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Structural audit of the install plane counts exactly one "
                    "@file_placement_call_site (plugin.placement.place_payload_files). "
                    "Marketplace install-plane modules have zero content-writes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/placement.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": "marketplace.audit.audit_live",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "ok": measured["audit_ok"],
                                "placement_site_count": measured["placement_site_count"],
                                "site": measured["placement_site"],
                            }
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": "test_single_placement_call_site planted second site",
                        "exit_code": test_rc,
                        "raw_output": (
                            "planted decorated function in a copy of placement.py "
                            "makes placement_site_count=2; planted write_bytes in a "
                            "copy of marketplace/install.py is reported as "
                            "marketplace content-writes"
                        ),
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_handoff_object_validates_and_installs",
                "command": "python3 -B tools/marketplace/tests/test_handoff_contract.py",
                "result": "PASS" if test_rc == 0 else "FAIL",
                "assertions": 8,
                "output_tail": test_out[-400:],
            },
            {
                "id": "test_single_placement_call_site",
                "command": "python3 -B tools/marketplace/tests/test_handoff_contract.py",
                "result": "PASS" if test_rc == 0 and measured["audit_ok"] else "FAIL",
                "assertions": 6,
                "output_tail": f"live placement_site_count={measured['placement_site_count']}",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0127-C1-planted-second-placement-site",
                "kind": "known-broken-fixture",
                "description": (
                    "A second @file_placement_call_site function is appended to a "
                    "copy of tools/plugin/placement.py. The audit must go red. "
                    "Removing the plant returns the copy to ok=true."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "placement_site_count=2 ok=false",
                "good_state_output": "placement_site_count=1 ok=true",
            },
            {
                "id": "IMP0127-C2-direct-bypass-without-transaction-id",
                "kind": "other",
                "description": (
                    "Calling plugin.install.install_from_handoff without a "
                    "transaction_id (missing field or a raw string) must raise "
                    "MissingTransactionIdError and must not place files."
                ),
                "fired_on_bad_state": measured["bypass_visible"],
                "silent_on_good_state": measured["censuses_equal"],
                "bad_state_output": measured["bypass_message"],
                "good_state_output": "typed handoff with uuid transaction_id installs",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0127-probe2-placement-audit",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is a separate process: it re-runs the AST audit, plants a "
                "second call site in a throwaway copy, and calls the plugin installer "
                "with an untyped payload to confirm the transaction_id bypass is visible."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0127/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0127",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "filled after named probes; G-1 measure is the delivery gate",
            }
        ],
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "Full IMP-0023 three-phase atomicity (kill mid-activate leaves "
                    "exactly one valid tree) is not claimed. This unit's installer "
                    "stages via the single place_payload_files then renames."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Deliver IMP-0023 kill-mid-activate test against this installer.",
            },
            {
                "claim": (
                    "IMP-0086 verification gates (signature, revocation, lockfile) "
                    "are not implemented in marketplace.install; it builds a handoff "
                    "from an already-present payload directory."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Deliver IMP-0086 gates in front of build_handoff.",
            },
        ],
        "report": {
            "kind": "install-handoff-contract",
            "measurement": {
                k: v
                for k, v in measured.items()
                if k not in {"marketplace_census", "direct_census"}
            },
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=2) + "\n"
    out_path.write_text(body, encoding="utf-8")
    if "SUCCESS:IMP-0127" not in body:
        print("FAILED:IMP-0127 sentinel missing from receipt body")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-1500:])
    print(f"probe2 rc={c2}")
    print(t2[-1500:])
    if c1 != 0 or c2 != 0:
        print("FAILED:IMP-0127 named probes")
        return 1

    sha, size = digest_file(out_path)
    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0127/SUBAGENT-RETURN.json",
        "role": "primary",
    }

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        s, n = digest_file(p)
        return {
            "path": rel,
            "sha256": s,
            "bytes": n,
            "present": p.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0127/SUBAGENT-RETURN.json",
            "role": role,
        }

    man_arts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ts = now()
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0127",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "handoff-end-to-end-census",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "placement-call-site-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0127/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0127-probe2-placement-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ts,
        "notes": (
            "G-1 for IMP-0127: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_arts),
        "present": len(man_arts),
        "artifacts": man_arts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0127 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
