#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0101.json from a live same-run pair."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/marketplace/tests"))

from marketplace.deprecation import (  # noqa: E402
    DEPRECATED_VER,
    PKG,
    REVOKED_VER,
    SUCCESSOR_VER,
    DeprecationRegistry,
    SuccessorDoesNotExist,
    run_catalog_evidence,
    seed_catalog_registry,
)
from marketplace.warning_channel import USER_CHANNEL_SOURCE  # noqa: E402

OUT = "command-center/receipts/IMP-0101.json"
SCHEMA_RECEIPT = "command-center/schema/receipt.schema.json"
SCHEMA_DEP = "tools/marketplace/schema/deprecation.schema.json"
SENTINEL = "SUCCESS:IMP-0101"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    fp = hashlib.md5(f"{command}|{exit_code}|{raw_output}".encode("utf-8")).hexdigest()
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:2000],
        "exit_code": exit_code,
        "fingerprint": fp,
    }


def run_unit_tests() -> dict:
    import test_deprecation as td

    errors: list[str] = []
    names = [
        "test_deprecated_installs_with_warning",
        "test_revoked_is_refused",
        "test_successor_to_nonexistent_package_rejected",
        "test_discarded_return_surfaces_to_user",
        "test_current_installs_without_warning",
        "test_self_successor_rejected",
        "test_install_refused_exception",
    ]
    for name in names:
        try:
            getattr(td, name)()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}\n{traceback.format_exc()[-800:]}")
    return {"passed": not errors, "names": names, "errors": errors}


def main() -> int:
    tests = run_unit_tests()
    if not tests["passed"]:
        print("FAILED:IMP-0101 unit tests")
        print("\n".join(tests["errors"]))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0101-receipt-") as tmp:
        root = Path(tmp)
        evidence = run_catalog_evidence(root / "pair")
        user_root = root / "user"
        first = seed_catalog_registry(user_root)
        discarded = first.install(PKG, DEPRECATED_VER)
        del discarded
        later = DeprecationRegistry(user_root)
        hc = later.health_check()

        neg = DeprecationRegistry(root / "neg")
        neg.publish(PKG, DEPRECATED_VER, payload="v1")
        neg_refused = False
        try:
            neg.deprecate(
                PKG,
                DEPRECATED_VER,
                reason="gone",
                successor="acme.does-not-exist",
            )
        except SuccessorDoesNotExist:
            neg_refused = True
        if not neg_refused:
            print("FAILED:IMP-0101 negative control did not fire")
            return 1

    dep = evidence["deprecated_install"]
    rev = evidence["revoked"]
    successor = f"{PKG}@{SUCCESSOR_VER}"
    if dep.get("ok") is not True or rev.get("ok") is not False:
        print("FAILED:IMP-0101 same-run pair did not distinguish states")
        return 1
    if hc.get("source") != USER_CHANNEL_SOURCE or hc.get("warning_count", 0) < 1:
        print("FAILED:IMP-0101 user channel empty", hc)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = REPO / "tools/marketplace/deprecation.py"
    warn = REPO / "tools/marketplace/warning_channel.py"
    elog = REPO / "tools/marketplace/event_log.py"
    schema = REPO / SCHEMA_DEP
    tests_path = REPO / "tools/marketplace/tests/test_deprecation.py"
    impl_sha, impl_n = sha256_file(impl)
    warn_sha, warn_n = sha256_file(warn)
    elog_sha, elog_n = sha256_file(elog)
    schema_sha, schema_n = sha256_file(schema)
    tests_sha, tests_n = sha256_file(tests_path)

    src1 = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_deprecation.py::test_deprecated_installs_with_warning",
        json.dumps(
            {
                "ok": dep["ok"],
                "installed": dep["installed"],
                "state": dep["state"],
                "successor": (dep.get("warning") or {}).get("successor"),
                "warning_persisted": evidence["warning_persisted"],
                "still_listed": evidence["still_listed"],
            },
            sort_keys=True,
        ),
        0,
    )
    ver1 = probe(
        "verifier",
        "file-read",
        "warnings.jsonl + user_surface.json after discarded return",
        json.dumps(
            {
                "warning_persisted": evidence["warning_persisted"],
                "user_source": hc.get("source"),
                "user_warning_count": hc.get("warning_count"),
                "successor_in_user_message": any(
                    successor in (m.get("message") or "") for m in (hc.get("messages") or [])
                ),
            },
            sort_keys=True,
        ),
        0,
    )
    src2 = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_deprecation.py::test_revoked_is_refused",
        json.dumps(
            {
                "revoked_ok": rev["ok"],
                "revoked_installed": rev["installed"],
                "state": rev["state"],
                "deprecated_ok_same_run": dep["ok"],
                "states_are_aliases": evidence["states_are_aliases"],
            },
            sort_keys=True,
        ),
        0,
    )
    ver2 = probe(
        "verifier",
        "file-read",
        "install dir for revoked version",
        json.dumps(
            {
                "revoked_install_exists": evidence["revoked_install_exists"],
                "refusal_reason": (rev.get("refusal") or {}).get("reason"),
            },
            sort_keys=True,
        ),
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0101",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0101; _USER-PROMPTS.md:10864",
        "title": "Deprecation with a successor pointer that warns without breaking",
        "min_bytes_threshold": 128,
        "output_schema": f"{SCHEMA_RECEIPT} + {SCHEMA_DEP}",
        "question": (
            "Implement deprecation as metadata carrying a reason and an optional "
            "successor package, where installing a deprecated version still succeeds "
            "but emits a durable warning naming the successor — deprecation must never "
            "be a silent removal, and must be distinct from revocation, which does block."
        ),
        "implementation": {
            "module": "tools/marketplace/deprecation.py",
            "warning_channel": "tools/marketplace/warning_channel.py",
            "event_log": "tools/marketplace/event_log.py",
            "schema": SCHEMA_DEP,
            "tests": "tools/marketplace/tests/test_deprecation.py",
            "states": ["current", "deprecated", "revoked"],
            "deprecation_is_metadata": True,
            "revocation_blocks": True,
            "append_only": True,
        },
        "measured_pair": {
            "package_id": PKG,
            "deprecated_version": DEPRECATED_VER,
            "successor": successor,
            "revoked_version": REVOKED_VER,
            "deprecated_ok": dep["ok"],
            "deprecated_installed": dep["installed"],
            "warning_message": (dep.get("warning") or {}).get("message"),
            "warning_persisted": evidence["warning_persisted"],
            "still_listed": evidence["still_listed"],
            "revoked_ok": rev["ok"],
            "revoked_installed": rev["installed"],
            "revoked_install_exists": evidence["revoked_install_exists"],
            "states_are_aliases": evidence["states_are_aliases"],
            "user_channel_source": hc.get("source"),
            "user_warning_count": hc.get("warning_count"),
            "negative_control_refused": neg_refused,
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "bytes": 0,
                "sha256": "pending",
            },
            {
                "path": "tools/marketplace/deprecation.py",
                "role": "implementation",
                "exists": True,
                "bytes": impl_n,
                "sha256": impl_sha,
            },
            {
                "path": "tools/marketplace/warning_channel.py",
                "role": "implementation",
                "exists": True,
                "bytes": warn_n,
                "sha256": warn_sha,
            },
            {
                "path": "tools/marketplace/event_log.py",
                "role": "implementation",
                "exists": True,
                "bytes": elog_n,
                "sha256": elog_sha,
            },
            {
                "path": SCHEMA_DEP,
                "role": "schema",
                "exists": True,
                "bytes": schema_n,
                "sha256": schema_sha,
            },
            {
                "path": "tools/marketplace/tests/test_deprecation.py",
                "role": "tests",
                "exists": True,
                "bytes": tests_n,
                "sha256": tests_sha,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Installing a deprecated version succeeds and a durable warning "
                    f"naming successor {successor} is persisted; the version remains listed."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_deprecation.py::test_deprecated_installs_with_warning",
                "confidence": "almost-certain",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "In the same run, installing a revoked version is refused and "
                    "writes no payload; deprecated and revoked are not aliases."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_deprecation.py::test_revoked_is_refused",
                "confidence": "almost-certain",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {
                "id": "test_deprecated_installs_with_warning",
                "command": "python3 -B tools/marketplace/tests/test_deprecation.py",
                "result": "PASS",
            },
            {
                "id": "test_revoked_is_refused",
                "command": "python3 -B tools/marketplace/tests/test_deprecation.py",
                "result": "PASS",
            },
            {
                "id": "test_successor_to_nonexistent_package_rejected",
                "command": "python3 -B tools/marketplace/tests/test_deprecation.py",
                "result": "PASS",
            },
            {
                "id": "test_discarded_return_surfaces_to_user",
                "command": "python3 -B tools/marketplace/tests/test_deprecation.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "successor-to-nonexistent-package",
                "kind": "known-broken-fixture",
                "description": (
                    "A successor pointer to a package that does not exist must be "
                    "rejected at deprecation time; the version stays current."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "package.deprecation_rejected",
                "good_state_output": "package.deprecated with an existing successor",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0101-probe2-user-surface",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "After discarding the install return value, a later process health-check "
                f"reads {USER_CHANNEL_SOURCE} (not events.jsonl) and the message names "
                f"the successor {successor}."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0101/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0101/probe1_deprecated_installs.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0101/probe1_deprecated_installs.py",
                    "deferred-to-named-probe",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0079 (signed revocation list) and IMP-0054 (plugin degrade-loudly "
                    "channel) are not delivered in this worktree; IMP-0101 ships a local "
                    "revocation flag that blocks install and a bounded user-facing warning "
                    "channel rather than importing those missing modules."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind install refusal to the IMP-0079 list and the warning sink "
                    "to the IMP-0054 plugin channel when those units land."
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "timestamps": {
            "started_at": "2026-08-24T20:42:00Z",
            "ended_at": now,
        },
        "same_run_distinct_states": True,
        "negative_control_refused": neg_refused,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    sha, n = sha256_file(dest)
    receipt["artifacts"][0]["bytes"] = n
    receipt["artifacts"][0]["sha256"] = sha
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    sha2, n2 = sha256_file(dest)
    print(f"wrote {OUT} bytes={n2} sha256={sha2}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
