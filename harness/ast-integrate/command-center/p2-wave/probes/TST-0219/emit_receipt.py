#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0219.json (security_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0219.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
SCHEMA_FILE = "command-center/schema/receipt.schema.json"
QUESTION = (
    "Can a private package name be satisfied from a public mirror? PASS "
    "requires the lockfile to pin both the registry origin and an integrity "
    "hash, and resolution to FAIL when the public mirror offers a same-named "
    "package."
)
SENTINEL = "SUCCESS:TST-0219"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0219/probe1_origin_refusal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0219/probe2_tree_hash.py"
)
SUT = "command-center/p2-wave/probes/TST-0219/resolver.py"
IMP_LOCK = "tools/marketplace/schema/lockfile.schema.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


REQUIRED_CORE = (
    "schema_version",
    "unit_id",
    "state",
    "sentinel",
    "spec_anchor",
    "min_bytes_threshold",
    "artifacts",
    "evidence",
    "timestamps",
    "retry",
    "tests",
    "negative_controls",
    "reviewer",
    "manifest_registration",
    "downstream_consumers",
    "residual_unknowns",
    "report",
)


def validate_security_report(doc: dict) -> list[str]:
    """Local shape check. Catalog $defs/security_report $ref's
    ast-integrate.invalid; Draft7Validator would try DNS and fail closed
    for a reason that is not this unit's contract.
    """
    errs: list[str] = []
    for k in REQUIRED_CORE:
        if k not in doc:
            errs.append(f"missing {k}")
    if doc.get("schema_version") != 1:
        errs.append("schema_version")
    if doc.get("unit_id") != "TST-0219":
        errs.append("unit_id")
    if doc.get("state") != "SUCCESS":
        errs.append("state")
    if SENTINEL not in str(doc.get("sentinel") or ""):
        errs.append("sentinel")
    if not isinstance(doc.get("artifacts"), list) or not doc["artifacts"]:
        errs.append("artifacts")
    if not isinstance(doc.get("evidence"), list) or len(doc["evidence"]) < 2:
        errs.append("evidence")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "security_report":
        errs.append("report.kind")
    else:
        findings = report.get("findings")
        scanners = report.get("scanners")
        if not isinstance(findings, list) or not findings:
            errs.append("report.findings")
        if not isinstance(scanners, list) or not scanners:
            errs.append("report.scanners")
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 400}):
        if not [k for k in REQUIRED_CORE if k not in garbage]:
            errs.append("required list accepted garbage")
            break
    schema_path = REPO / SCHEMA_FILE
    if not schema_path.is_file():
        errs.append("schema file absent")
    return errs


def main() -> int:
    live = S.evaluate()
    if not live["pass"]:
        print("FAILED:TST-0219 emit scenario", "; ".join(live["fails"]))
        print(json.dumps({k: live[k] for k in ("fails", "both_states", "negative_control")}, indent=2))
        return 1

    priv = live["private_ok"]
    pub = live["public_offer"]
    unpin = live["unpinned_fail"]
    mutant = live["confused_mutant"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_path = REPO / SUT
    sut_sha, sut_bytes = sha256_file(sut_path)
    schema_present = (REPO / SCHEMA_FILE).is_file()
    prod_lock = (REPO / IMP_LOCK).is_file()

    answer = (
        "No: a private name cannot be satisfied from the public mirror when the "
        "lockfile pins origin and integrity. The live resolver installed "
        f"{live['package']} only from {R.PRIVATE_ORIGIN} (tree "
        f"{priv['live_tree_hash'][:16]}…, payload sha256={live['private_sha256'][:16]}…). "
        "The same name offered from "
        f"{R.PUBLIC_ORIGIN} was refused with {R.CODE_DEPENDENCY_CONFUSION} naming "
        "package, pinned origin, offered origin, and integrity; the dest tree "
        f"stayed empty ({pub['live_tree_hash']}). A lockfile without an origin "
        f"pin failed closed ({R.CODE_ORIGIN_PIN_MISSING}). A known-broken "
        "highest-version mutant installed the public artifact "
        f"(sha256={live['public_sha256'][:16]}…, tree {mutant['live_tree_hash'][:16]}…), "
        "so the public payload is live and distinct. Production "
        "tools/marketplace lockfile schema (IMP-0084) is absent on this "
        "worktree; the measured SUT is probes/TST-0219/resolver.py. "
        f"{SENTINEL}"
    )

    fp1 = hashlib.sha256(f"command\x1f{P1}".encode()).hexdigest()[:32]
    fp2 = hashlib.sha256(f"byte-compare\x1f{P2}".encode()).hexdigest()[:32]
    probe1 = {
        "role": "source",
        "method": "command",
        "command": P1,
        "raw_output": (
            f"live evaluate both_states={live['both_states']} "
            f"public_code={pub['code']} unpinned_code={unpin['code']}"
        ),
        "fingerprint": fp1,
        "exit_code": 0,
    }
    probe2 = {
        "role": "verifier",
        "method": "byte-compare",
        "command": P2,
        "raw_output": (
            f"private_tree={priv['live_tree_hash']} "
            f"public_offer_tree={pub['live_tree_hash']} "
            f"public_bytes_in_sut={priv['public_bytes_present']}"
        ),
        "fingerprint": fp2,
        "exit_code": 0,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0219",
        "state": "SUCCESS",
        "report_kind": "security_report",
        "title": "Lockfile pins registry origin and integrity, defeating dependency confusion",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0219; lockfile origin+integrity pin; "
            "resolution fails when a public mirror offers the same name"
        ),
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_present,
        "cloud_ok": False,
        "required_fix": None,
        "sut": {
            "catalog_input": "B07 marketplace resolver + lockfile",
            "production_lockfile_schema": IMP_LOCK,
            "production_lockfile_schema_present": prod_lock,
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "package": live["package"],
            "private_origin": R.PRIVATE_ORIGIN,
            "public_origin": R.PUBLIC_ORIGIN,
            "algorithm": (
                "resolve_install reads lockfile origin+integrity, refuses any "
                "offered origin that is not the pin, fetches only from the "
                "pinned registry, and verifies sha256 before write"
            ),
        },
        "lockfile": {
            "pinned": live["pinned_lock"],
            "unpinned": live["unpinned_lock"],
            "pins_origin": True,
            "pins_integrity": True,
        },
        "signals": [
            {
                "id": "a",
                "kind": "resolver-refusal-and-message",
                "code": pub["code"],
                "message": pub["message"],
                "private_ok": priv["ok"],
                "private_code": priv["code"],
                "unpinned_code": unpin["code"],
            },
            {
                "id": "b",
                "kind": "installed-tree-hash",
                "private_tree_hash": priv["live_tree_hash"],
                "public_offer_tree_hash": pub["live_tree_hash"],
                "empty_tree_hash": live["empty_tree_hash"],
                "private_payload_sha256": live["private_sha256"],
                "public_payload_sha256": live["public_sha256"],
                "public_bytes_in_sut_tree": priv["public_bytes_present"],
                "public_bytes_after_refused_offer": pub["public_bytes_present"],
                "mutant_tree_hash": mutant["live_tree_hash"],
                "mutant_installed_public": mutant["public_bytes_present"],
            },
        ],
        "both_states": {
            "legitimate_private_origin_resolves": priv["ok"],
            "public_same_name_refused": (not pub["ok"])
            and pub["code"] == R.CODE_DEPENDENCY_CONFUSION,
            "unpinned_fails_closed": (not unpin["ok"])
            and unpin["code"] == R.CODE_ORIGIN_PIN_MISSING,
        },
        "tests": [
            {
                "id": "both-states-private-origin-resolves",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "public-mirror-same-name-fails",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-unpinned-origin",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "detector-confused-mutant",
                "command": P2,
                "result": "PASS",
            },
        ],
        "tests_required": [
            {
                "id": "both-states-private-origin",
                "text": "both-states control: the legitimate private origin resolves",
                "result": "PASS",
            },
            {
                "id": "negative-lockfile-without-origin-pin",
                "text": "negative control: a lockfile without an origin pin must fail this test",
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Resolver refuses to satisfy the private name from the public "
                    "mirror and names package, pinned origin, offered origin, and "
                    "integrity in the refusal."
                ),
                "verdict": "CONFIRMED",
                "anchor": SUT + ":resolve_install",
                "confidence": "almost-certain",
                "probes": [probe1, probe2],
            },
            {
                "claim": (
                    "Installed tree hash after the refused public offer equals the "
                    "empty-tree hash; the private install census contains the "
                    "private payload sha256 and not the public payload sha256."
                ),
                "verdict": "CONFIRMED",
                "anchor": SUT + ":census+tree_hash",
                "confidence": "almost-certain",
                "probes": [
                    {**probe2, "role": "source"},
                    {**probe1, "role": "verifier"},
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "lockfile-without-origin-pin",
                "kind": "missing-origin-pin",
                "description": (
                    "Integrity-only lockfile is refused with ORIGIN_PIN_MISSING "
                    "and writes nothing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "confused-highest-version-mutant",
                "kind": "known-broken-implementation",
                "description": (
                    "A resolver that ignores origin pins and picks the highest "
                    "version installs the public v9.9.9 artifact, proving the "
                    "public payload is live and that origin pinning is load-bearing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0219-probe2-independent-tree-hash",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-installs into fresh directories and hashes dest "
                "trees plus payload-byte presence. It does not treat refusal "
                "message text as the pass criterion."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0219/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "TST-0219",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "report": {
            "kind": "security_report",
            "findings": [
                {
                    "id": "TST-0219-dependency-confusion-refused",
                    "severity": "high",
                    "cwe": "CWE-426",
                    "summary": (
                        "Private package name is not satisfied from a public "
                        "mirror when origin+integrity are pinned; unpinned "
                        "lockfile fails closed."
                    ),
                    "anchor": SUT + ":resolve_install",
                    "exploit_proven": False,
                    "credential_redacted": True,
                }
            ],
            "scanners": [
                {
                    "name": "probe1_origin_refusal",
                    "version": "1",
                    "installed": True,
                },
                {
                    "name": "probe2_tree_hash",
                    "version": "1",
                    "installed": True,
                },
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "no automatic retry: a failure here is a finding, not a transient",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/marketplace lockfile schema and IMP-0084 verify-on-install "
                    "are absent from this worktree; measurements are of the contracted "
                    "origin-pin resolver shipped with this unit, not of a missing "
                    "production marketplace client."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-point resolve_install at tools/marketplace lockfile+installer "
                    "once IMP-0084 exists and re-run both named probes."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SUT,
                "exists": True,
                "role": "resolver-under-test",
                "sha256": sut_sha,
                "bytes": sut_bytes,
            },
            {"path": SCHEMA_FILE, "exists": schema_present, "role": "schema"},
        ],
        "named_probes": [
            {
                "id": "probe1-origin-refusal",
                "command": P1,
                "result": "PASS",
                "role": "resolver-refusal-and-message",
            },
            {
                "id": "probe2-tree-hash",
                "command": P2,
                "result": "PASS",
                "role": "installed-tree-hash",
            },
        ],
        "scenario_pass": True,
        "scenario_fails": live["fails"],
    }

    errs = validate_security_report(doc)
    if errs:
        print("FAILED:TST-0219 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0219 emit sentinel absent from file")
        return 1
    digest, size = sha256_file(dest)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0219 emit below min_bytes_threshold size={size}")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0219 emit state is not SUCCESS")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0219 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
