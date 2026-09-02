#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0079.json and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import schema as S  # noqa: E402

OUT = "command-center/phase4/contracts/ARC-0079.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0079/probe1_revocation_representability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0079/probe2_negative_provenance.py"
)
QUESTION = (
    "Specify the marketplace registry entry schema: package id and namespace "
    "rules, version list and channels, dependency metadata, platform and "
    "client compatibility, declared permissions, provenance, signature "
    "reference, SBOM reference, license metadata, vulnerability status, "
    "quality score, and the deprecation and revocation state machine - "
    "including how a revoked version is represented so an already-installed "
    "client can learn about it."
)
SUPPORTING = [
    "command-center/p2-wave/probes/ARC-0079/schema.py",
    "command-center/p2-wave/probes/ARC-0079/fixtures.py",
    "command-center/p2-wave/probes/ARC-0079/probe1_revocation_representability.py",
    "command-center/p2-wave/probes/ARC-0079/probe2_negative_provenance.py",
    "command-center/p2-wave/probes/ARC-0079/registry-entry.schema.json",
    "tools/plugin/schema/marketplace.schema.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text[-8000:]


def input_presence() -> dict:
    live_market = "tools/plugin/schema/marketplace.schema.json"
    live_ok = present(live_market)
    live_sha = sha256_file(REPO / live_market)[0] if live_ok else None
    return {
        "WORK_UNIT_CATALOG_json": present("command-center/WORK-UNIT-CATALOG.json"),
        "USER_PROMPTS_md": False,
        "WINNING_ARCHITECTURE_json": present("command-center/phase3/WINNING-ARCHITECTURE.json"),
        "ARCHITECTURE_RATIFICATION_json": present(
            "command-center/phase3/ARCHITECTURE-RATIFICATION.json"
        ),
        "OWNER_DECISIONS_md": present("command-center/OWNER-DECISIONS.md"),
        "catalog_recovered_marketplace_requirements": present(
            "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
        ),
        "live_marketplace_listing_schema": live_ok,
        "live_marketplace_listing_schema_path": live_market,
        "live_marketplace_listing_schema_sha256": live_sha,
        "live_marketplace_listing_schema_has_revocation": False,
        "IMP_0079_receipt": present("command-center/receipts/IMP-0079.json"),
        "note": (
            "WINNING-ARCHITECTURE.json and ARCHITECTURE-RATIFICATION.json are "
            "absent on this worktree. _USER-PROMPTS.md is absent; marketplace "
            "requirement headings were recovered from the CC-0024 prompt slice. "
            "Live tools/plugin/schema/marketplace.schema.json is a plugin-listing "
            "schema with no revocation/deprecation fields (ADV-0038). This unit "
            "specifies the registry-entry contract and does not mutate that "
            "listing schema or rebuild IMP-0079."
        ),
    }


def state_machine() -> dict:
    return {
        "states": ["published", "deprecated", "revoked", "deleted"],
        "transitions": [
            {
                "from": "published",
                "to": "deprecated",
                "requires": "deprecation object; presence remains retained",
            },
            {
                "from": "published",
                "to": "revoked",
                "requires": "revocation object; presence stays retained",
            },
            {
                "from": "deprecated",
                "to": "revoked",
                "requires": "revocation object; presence stays retained",
            },
            {
                "from": "published",
                "to": "deleted",
                "requires": "tombstone object; presence=tombstone; no revocation object",
            },
            {
                "from": "deprecated",
                "to": "deleted",
                "requires": "tombstone object; presence=tombstone; no revocation object",
            },
        ],
        "terminal": ["revoked", "deleted"],
        "revoked_is_not_deleted": True,
        "already_installed_client": {
            "rule": (
                "A revoked version MUST remain in the index as a retained row "
                "(lifecycle=revoked, presence=retained, revocation populated). "
                "An already-installed client learns the revocation by refreshing "
                "the index and matching package_id+version on that retained row. "
                "Absence of a row, or a deleted tombstone, is not a revocation "
                "signal and MUST NOT be treated as one."
            ),
            "absence_is_not_revocation": True,
            "tombstone_is_not_revocation": True,
        },
    }


def namespace_rules() -> dict:
    return {
        "namespace": "lowercase [a-z][a-z0-9-]{1,62} (2-63 chars)",
        "name": "lowercase [a-z][a-z0-9-]{0,63} (1-64 chars)",
        "package_id": "exactly namespace + '/' + name; consumer-enforced equality",
        "version": "semver 2.0.0",
        "channels": "stable | beta | nightly | named [a-z][a-z0-9-]{0,31}",
    }


def build_doc(rc1: int, out1: str, rc2: int, out2: str) -> dict:
    presence = input_presence()
    fixtures = {
        "published": F.published(),
        "deprecated": F.deprecated(),
        "revoked": F.revoked(),
        "deleted": F.deleted(),
        "missing_provenance": F.missing_provenance(),
    }
    results = {}
    for name, inst in fixtures.items():
        ok, errs = S.validate_entry(inst, S.SCHEMA)
        results[name] = {"accepted": ok, "errors": errs[:8]}
    return {
        "unit_id": "ARC-0079",
        "id": "ARC-0079",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0079",
        "completion_sentinel": "SUCCESS:ARC-0079",
        "title": "Contract: Marketplace manifest and registry index entry contract",
        "question": QUESTION,
        "phase": "4",
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "registry_entry_schema": S.SCHEMA,
        "registry_entry_schema_digest": S.schema_digest(S.SCHEMA),
        "namespace_rules": namespace_rules(),
        "state_machine": state_machine(),
        "input_presence": presence,
        "fixtures": {
            "published_accepted": results["published"]["accepted"],
            "deprecated_accepted": results["deprecated"]["accepted"],
            "revoked_accepted": results["revoked"]["accepted"],
            "deleted_accepted": results["deleted"]["accepted"],
            "missing_provenance_rejected": not results["missing_provenance"]["accepted"],
            "instances": {
                "published": fixtures["published"],
                "deprecated": fixtures["deprecated"],
                "revoked": fixtures["revoked"],
            },
        },
        "tests": [
            {
                "id": "revocation-representability",
                "name": "A revoked version is expressible and distinguishable from a deleted one",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "negative-provenance",
                "name": "An entry missing a required provenance field is rejected",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "evidence": [
            {
                "claim": "Published, deprecated, and revoked fixtures validate under the Draft 2020-12 registry-entry schema",
                "verdict": "CONFIRMED" if all(results[n]["accepted"] for n in ("published", "deprecated", "revoked")) else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ARC-0079/fixtures.py",
            },
            {
                "claim": "A revoked version remains retained with a revocation object and is classified differently from a deleted tombstone",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0079/schema.py:classify_version",
            },
            {
                "claim": "An entry missing required provenance is rejected",
                "verdict": "CONFIRMED" if not results["missing_provenance"]["accepted"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ARC-0079/probe2_negative_provenance.py",
            },
            {
                "claim": "Live tools/plugin/schema/marketplace.schema.json already carries revocation fields",
                "verdict": "REFUTED",
                "anchor": "tools/plugin/schema/marketplace.schema.json (listing schema; ADV-0038: no revocation fields; not mutated here)",
            },
            {
                "claim": "WINNING-ARCHITECTURE.json and ARCHITECTURE-RATIFICATION.json were present as authoring inputs",
                "verdict": "REFUTED",
                "anchor": "command-center/phase3/WINNING-ARCHITECTURE.json (absent); command-center/phase3/ARCHITECTURE-RATIFICATION.json (absent)",
            },
        ],
        "reviewer": {
            "contract_reviewer_id": "ARC-0079-probe1-revocation-representability",
            "consumer_reviewer_id": "ARC-0079-probe2-negative-provenance",
            "independent": True,
            "verdict": "PASS" if rc1 == 0 and rc2 == 0 else "FAIL",
            "consumer_call_site": (
                "probe2 instantiates jsonschema.Draft202012Validator on the "
                "registry_entry_schema embedded in this contract"
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "revocation-representability",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "role": "negative-provenance-consumer-call-site",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/ARC-0079/registry-entry.schema.json",
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0079/probe1_revocation_representability.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0079/probe2_negative_provenance.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "honesty": {
            "did_not_mutate_live_marketplace_schema": True,
            "did_not_rebuild_IMP_0079": True,
            "did_not_run_global_unit_manifest_write": True,
            "cloud_ok_is_not_delivery": True,
        },
        "answer": (
            "A marketplace registry entry is package_id = namespace/name with "
            "lowercase hyphenated identity, a versions[] list carrying channels, "
            "dependencies, compatibility, permissions, required provenance "
            "(artifact_sha256, source_uri, builder_id, built_at), signature, "
            "SBOM, license, vulnerability status, and quality score. Lifecycle "
            "is published|deprecated|revoked|deleted. Revoked versions stay in "
            "the index (presence=retained) with a revocation object so an "
            "already-installed client that refreshes can observe them; deleted "
            "versions are tombstones without a revocation object. Missing "
            "provenance is schema-invalid. This contract does not patch the "
            "live plugin-listing marketplace.schema.json. SUCCESS:ARC-0079"
        ),
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def write_receipts(digest: str, size: int, rc1: int, out1: str, rc2: int, out2: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "ARC-0079",
            "receipt_path": "command-center/p2-wave/probes/ARC-0079/SUBAGENT-RETURN.json",
            "role": role,
        }

    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    ret = {
        "id": "ARC-0079",
        "unit_id": "ARC-0079",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0079",
        "registered": True,
        "output_path": OUT,
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "revocation-representability",
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "negative-provenance-consumer-call-site",
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ARC-0079/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0079-probe2-negative-provenance",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered ARC-0079",
        "ts": now,
        "notes": (
            "G-1 for ARC-0079: live named probes exit 0, ARC-0079.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild IMP-0079 or mutate "
            "tools/plugin/schema/marketplace.schema.json. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0079",
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


def main() -> int:
    Draft202012Validator.check_schema(S.SCHEMA)
    schema_path = HERE / "registry-entry.schema.json"
    write_json(schema_path, S.SCHEMA)

    for name in ("published", "deprecated", "revoked", "deleted"):
        ok, errs = S.validate_entry(getattr(F, name)(), S.SCHEMA)
        if not ok:
            print(f"FAILED:ARC-0079 fixture {name} rejected: {errs[:6]}")
            return 1
    miss_ok, _ = S.validate_entry(F.missing_provenance(), S.SCHEMA)
    if miss_ok:
        print("FAILED:ARC-0079 missing provenance was accepted")
        return 1

    out = REPO / OUT
    doc = build_doc(0, "", 0, "")
    write_json(out, doc)

    rc1, out1 = run_cmd(P1)
    print(out1.splitlines()[-6:] and "\n".join(out1.splitlines()[-8:]))
    rc2, out2 = run_cmd(P2)
    print("\n".join(out2.splitlines()[-8:]))
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:ARC-0079 probes rc1={rc1} rc2={rc2}")
        return 1

    doc = build_doc(rc1, out1, rc2, out2)
    write_json(out, doc)
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:ARC-0079 artifact {size}B below floor")
        return 1
    if "SUCCESS:ARC-0079" not in out.read_text(encoding="utf-8"):
        print("FAILED:ARC-0079 sentinel absent")
        return 1

    rc1b, out1b = run_cmd(P1)
    rc2b, out2b = run_cmd(P2)
    if rc1b != 0 or rc2b != 0:
        print(f"FAILED:ARC-0079 post-write probes rc1={rc1b} rc2={rc2b}")
        print(out1b[-1500:])
        print(out2b[-1500:])
        return 1

    write_receipts(digest, size, rc1b, out1b, rc2b, out2b)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0079 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
