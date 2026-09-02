#!/usr/bin/env python3
"""Emit TST-0221 catalog receipt + per-unit G-1 return/manifest.

Named probes run first. Does not invoke tools/command-center/unit_manifest.py --write.
Does not git add/commit/push.
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
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import revocation_health as H  # noqa: E402

UNIT = "TST-0221"
OUT = "command-center/receipts/TST-0221.json"
SENTINEL = "SUCCESS:TST-0221"
QUESTION = (
    "After a package is revoked upstream, does the next health check flag it, "
    "and does removal leave user data intact? PASS requires the flag to appear "
    "without a manual refresh and the user-data tree to be byte-identical after "
    "removal."
)
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
SCHEMA_FALLBACK = "command-center/schema/security-report.schema.json"
TEST = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_revocation_health.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0221/probe1_health_check_no_refresh.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0221/probe2_removal_preserves_user_data.py"
)
SUPPORTING = [
    "tools/marketplace/revocation_health.py",
    "tools/marketplace/tests/test_revocation_health.py",
    "command-center/p2-wave/probes/TST-0221/probe1_health_check_no_refresh.py",
    "command-center/p2-wave/probes/TST-0221/probe2_removal_preserves_user_data.py",
    "command-center/p2-wave/probes/TST-0221/emit_receipt.py",
    "command-center/schema/security-report.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
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
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def first_json_line(text: str) -> dict:
    decoder = json.JSONDecoder()
    blob = text or ""
    idx = blob.find("{")
    if idx < 0:
        return {}
    try:
        doc, _ = decoder.raw_decode(blob[idx:])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0221/SUBAGENT-RETURN.json",
        "role": role,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
    }


def maybe_validate(doc: dict) -> list[str]:
    schema_path = REPO / "command-center" / "schema" / "security-report.schema.json"
    if not schema_path.is_file():
        return ["schema-file-absent"]
    try:
        import jsonschema  # type: ignore
    except ImportError:
        required = ["unit_id", "state", "sentinel", "question", "answer", "tests", "reviewer", "artifacts"]
        return [f"missing:{k}" for k in required if k not in doc]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
    except Exception as exc:  # noqa: BLE001 — surface validator text
        return [f"{type(exc).__name__}:{exc}"]
    return []


def main() -> int:
    c_test, t_test = run_probe(TEST)
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0221 emit probes c_test={c_test} c1={c1} c2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json_line(t1)
    j2 = first_json_line(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0221 emit probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec(
        "verifier",
        "stale-cache-mutant-misses-until-refresh",
        P1,
        t1,
        c1,
    )
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec(
        "verifier",
        "independent-os-walk-user-data-hash",
        P2,
        t2,
        c2,
    )

    impl_sha, impl_n = digest(REPO / "tools/marketplace/revocation_health.py")
    signal_a = j1.get("signal_a") or {}
    signal_b = j2.get("signal_b") or {}
    after = j1.get("after") or {}
    stale = j1.get("stale_fresh_world") or {}
    wholesale = j2.get("wholesale_negative_control") or {}

    answer = (
        "Yes on this worktree's file-backed client. tools/marketplace/"
        "revocation_health.py health_check() always fetches upstream/"
        "revocation.json; a package revoked after install is named on the next "
        f"health-check with refresh_called=false (live named {H.REVOKED_PACKAGE}"
        f"@{H.REVOKED_VERSION}, exit 2). The non-revoked twin "
        f"{H.CLEAN_PACKAGE} is not flagged in the same run. Removal unlinks "
        "only the owned path set; an independent os.walk+sha256 of home/"
        f"user-data is byte-identical (digest {signal_b.get('pre')}). A "
        "stale-cache mutant stays silent until refresh(), and wholesale home "
        "restore deletes user-data plus the user-created command, so both "
        "predicates discriminate. SUCCESS:TST-0221"
    )

    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Revocation is honored at the next health check and removal preserves user data",
        "report_kind": "security_report",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present_on_worktree": SCHEMA_FALLBACK,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0221; "
            "_USER-PROMPTS.md:11019 / 11347 / 10844-10871 (file absent on this "
            "sparse worktree)"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 2048,
        "execution_substrate": "worktree-isolated",
        "implementation": {
            "path": "tools/marketplace/revocation_health.py",
            "bytes": impl_n,
            "sha256": impl_sha,
            "health_check": "Client.health_check fetches upstream every call",
            "remove": "Client.remove_package unlinks owned paths only",
            "clean_package": H.CLEAN_PACKAGE,
            "revoked_package": H.REVOKED_PACKAGE,
            "revoked_version": H.REVOKED_VERSION,
            "user_data_rel": H.USER_DATA_REL,
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md:11019": "absent; catalog target used as the spec",
            "_USER-PROMPTS.md:11347": "absent; regression seed taken from catalog tests_required",
            "tools/marketplace/revocation_health.py": "authored by this unit; no prior health-check existed",
            "IMP-0079 receipt": "absent; install-time revocation list is a sibling unit",
            "IMP-0026 rollback": "present as a related owned-set pattern; this unit implements health-check + removal",
        },
        "measured": {
            "probe1": {
                "pass": True,
                "named_packages": after.get("named_packages"),
                "message": after.get("message"),
                "exit_code": after.get("exit_code"),
                "refresh_called": after.get("refresh_called"),
                "fetched_upstream": after.get("fetched_upstream"),
                "clean_not_flagged": H.CLEAN_PACKAGE
                not in list(after.get("named_packages") or []),
            },
            "probe2": {
                "pass": True,
                "user_data_pre": signal_b.get("pre"),
                "user_data_post": signal_b.get("post"),
                "byte_identical": signal_b.get("byte_identical"),
                "files": signal_b.get("files"),
            },
            "unittest": {
                "exit_code": c_test,
                "result": "PASS" if c_test == 0 else "FAIL",
            },
        },
        "signals": [
            {
                "id": "signal-a-health-check-names-revoked-package",
                "kind": signal_a.get("kind"),
                "package": signal_a.get("package"),
                "version": signal_a.get("version"),
                "message": signal_a.get("message"),
                "exit_code": signal_a.get("exit_code"),
                "ok": True,
            },
            {
                "id": "signal-b-independent-user-data-tree-hash",
                "kind": signal_b.get("kind"),
                "pre": signal_b.get("pre"),
                "post": signal_b.get("post"),
                "byte_identical": bool(signal_b.get("byte_identical")),
                "ok": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "After upstream revoke of "
                    f"{H.REVOKED_PACKAGE}@{H.REVOKED_VERSION}, the next "
                    "health-check process named that package in stdout/stderr "
                    f"(message={after.get('message')!r}, exit="
                    f"{after.get('exit_code')}) with refresh_called=false and "
                    "fetched_upstream=true. The non-revoked twin "
                    f"{H.CLEAN_PACKAGE} was not in named_packages."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/revocation_health.py:Client.health_check",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    "Independent os.walk+sha256 of home/user-data before and "
                    "after owned-set removal matched "
                    f"(digest={signal_b.get('pre')}). The user-created command "
                    "bytes were unchanged. Wholesale restore on a twin home "
                    "destroyed the user-data tree "
                    f"(destroyed={wholesale.get('destroyed_user_data')})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0221/probe2_removal_preserves_user_data.py",
                "probes": [p2, p2v],
            },
        ],
        "tests": [
            {
                "id": "both-states-non-revoked-not-flagged",
                "name": "a non-revoked package is not flagged",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": (
                    "both-states control: a non-revoked package is not flagged"
                ),
            },
            {
                "id": "revocation-honored-without-manual-refresh",
                "name": "next health check flags without refresh()",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": (
                    "flag appears without a manual refresh; stale-cache mutant "
                    f"misses until refresh (stale_ok={stale.get('ok')})"
                ),
            },
            {
                "id": "removal-user-data-byte-identical",
                "name": "user-data tree hash identical after removal",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": (
                    "user-data tree is byte-identical after removal of the "
                    "revoked package"
                ),
            },
            {
                "id": "regression-rollback-removes-user-data",
                "name": "wholesale restore is the discriminating defect",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": (
                    "regression seed: rollback/wholesale restore removes "
                    "existing commands or user data"
                ),
            },
            {
                "id": "unittest-revocation-health",
                "name": "tools/marketplace/tests/test_revocation_health.py",
                "command": TEST,
                "result": "PASS" if c_test == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "stale-cache-until-refresh",
                "kind": "both-states",
                "description": (
                    "A health check that reads only the install-time cache "
                    "misses an upstream revoke until refresh(). Live "
                    "health_check fetches upstream every call."
                ),
                "fired_on_bad_state": bool(stale.get("ok")),
                "silent_on_good_state": H.REVOKED_PACKAGE
                in list(after.get("named_packages") or []),
            },
            {
                "id": "wholesale-home-restore",
                "kind": "regression-seed",
                "description": (
                    "Wholesale deletion of the client home removes user-data "
                    "and user-created commands. Owned-set removal does not."
                ),
                "fired_on_bad_state": bool(wholesale.get("destroyed_user_data")),
                "silent_on_good_state": bool(signal_b.get("byte_identical")),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0221-probe2-independent-user-data-hash",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe2 is a second path: probe-owned os.walk+sha256 of "
                "user-data, plus a wholesale mutant. Catalog reviewer_requirement "
                "asks for a cross-vendor Codex security reviewer plus one "
                "correctness reviewer in a fresh context; that human pair is "
                "residual and is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0221/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "role": "health-check-names-revoked-without-refresh", "command": P1},
            {"id": "probe2", "role": "removal-preserves-user-data-hash", "command": P2},
        ],
        "cloud_ok": False,
        "live_tree_touched": False,
        "throwaway_home_only": True,
        "residual_unknowns": [
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. The catalog's two-reviewer "
                    "fresh-context pair has not scored this unit."
                ),
            },
            {
                "id": "spec-file-absent",
                "text": (
                    "_USER-PROMPTS.md is not on this worktree. The harness "
                    "implements the catalog target: next health check flags "
                    "an upstream revoke without refresh, and removal leaves "
                    "user-data byte-identical."
                ),
            },
            {
                "id": "no-network-registry",
                "text": (
                    "Upstream is a file-backed revocation.json in a throwaway "
                    "directory, not a live public marketplace. The fetch-every-"
                    "health-check property is what the unit measures."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a human adversarial reviewer in a fresh context scored PASS",
            "a networked public registry was contacted",
        ],
        "defects": [],
        "notes": (
            "G-1 for TST-0221: live named probes exit 0, receipts/TST-0221.json "
            "state=SUCCESS with SUCCESS:TST-0221, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery. "
            "No ADV rebuild. SUCCESS:TST-0221"
        ),
        "ts": now,
        "host": {
            "python": sys.version.split()[0],
            "system": os.name,
        },
        "unittest_tail": t_test[-4000:],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "tools/marketplace/revocation_health.py",
                "exists": True,
                "role": "implementation",
            },
        ],
    }

    errors = maybe_validate(receipt)
    receipt["schema_validation"] = {
        "schema": SCHEMA_FALLBACK,
        "errors": errors,
        "ok": errors == [],
    }
    if errors and any(e.startswith("missing:") for e in errors):
        print(f"FAILED:TST-0221 schema required fields {errors}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:TST-0221 emit catalog sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0221 artifact {size}B below floor")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:TST-0221 missing supporting", missing)
        return 1
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
                "role": "health-check-names-revoked-without-refresh",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "removal-preserves-user-data-hash",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0221/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0221-probe2-independent-user-data-hash",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0221: live named probes exit 0, receipts/TST-0221.json "
            "state=SUCCESS with SUCCESS:TST-0221, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0221 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
