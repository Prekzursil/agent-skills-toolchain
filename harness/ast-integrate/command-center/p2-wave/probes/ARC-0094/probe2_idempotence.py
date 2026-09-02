#!/usr/bin/env python3
"""Named probe 2: idempotence of a successful rollback.

Restore version, configuration, deployed tree, and curated MCP enable/disable
from the pre-change backup. Proof-of-restore is a content hash per protected
path. Rolling back a second time must not change the first result. A complete
record with second_pass_digest_equals_first=false must be schema-invalid.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit_contract as C  # noqa: E402
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

RESTORE_RELS = (
    S.VERSION_REL,
    S.CONFIG_REL,
    S.DEPLOY_PLUGIN_REL,
    S.DEPLOY_HOOK_REL,
    S.MCP_REL,
)
PRESERVE_RELS = (S.OWNER_REL, S.USERDATA_REL, S.CRED_REL)


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0094-probe2 {msg}")
    return 1


def main() -> int:
    C.write_schema()
    schema = json.loads((REPO / C.OUT_REL).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    with tempfile.TemporaryDirectory(prefix="arc0094-p2-") as tmp:
        root = Path(tmp)
        live = root / "live"
        backup_root = root / "backup"
        S.write_previous_tree(live)
        E.copy_tree(live, backup_root)
        backup = E.snapshot(backup_root)
        backup_hashes = dict(backup["files"])
        S.apply_upgrade(live)

        if E.sha256_file(live / S.VERSION_REL) == backup_hashes[S.VERSION_REL]:
            return fail("upgrade did not mutate version.json")
        if E.sha256_file(live / S.MCP_REL) == backup_hashes[S.MCP_REL]:
            return fail("upgrade did not mutate MCP enable/disable")
        extra = live / "deploy/upgrade-only.json"
        if not extra.is_file():
            return fail("upgrade extra deploy file missing")

        result = E.rollback_twice(live, backup_root, backup)
        if not result.complete:
            return fail(f"rollback not complete: {result.outcome} {result.reason}")
        if result.outcome != "COMPLETE":
            return fail(f"outcome {result.outcome}")
        if result.first_tree_digest != result.second_tree_digest:
            return fail("second rollback changed first tree digest")
        if extra.is_file():
            return fail("upgrade-only deploy file survived rollback")

        for rel in RESTORE_RELS:
            got = E.sha256_file(live / rel)
            want = backup_hashes[rel]
            if got != want:
                return fail(f"restore hash mismatch {rel}")
        for rel in PRESERVE_RELS:
            if not (live / rel).is_file():
                return fail(f"preserve path missing {rel}")
            if E.sha256_file(live / rel) != backup_hashes[rel]:
                return fail(f"preserve hash changed {rel}")

        proofs = {p["path"]: p for p in result.path_proofs}
        for rel in RESTORE_RELS:
            item = proofs.get(rel)
            if not item or not item.get("matched"):
                return fail(f"proof missing/unmatched {rel}")
            if item["pre_change_sha256"] != item["post_rollback_sha256"]:
                return fail(f"proof hash mismatch {rel}")

        record = E.record_from_result(result)
        rec_errs = list(validator.iter_errors(record))
        if rec_errs:
            return fail(f"complete record schema-invalid: {rec_errs[0].message}")
        if not record["idempotence"]["second_pass_digest_equals_first"]:
            return fail("record idempotence flag false")
        if not record["post_restore_verification"]["passed"]:
            return fail("record verification not passed")

        forged = json.loads(json.dumps(record))
        forged["idempotence"]["second_pass_digest_equals_first"] = False
        if not list(validator.iter_errors(forged)):
            return fail("schema accepted complete record with non-idempotent second pass")

        unverified = json.loads(json.dumps(record))
        unverified["post_restore_verification"]["passed"] = False
        if not list(validator.iter_errors(unverified)):
            return fail("schema accepted complete=true with verification.passed=false")

    out = {
        "probe": "probe2-idempotence",
        "unit_id": "ARC-0094",
        "complete": True,
        "restored_version": True,
        "restored_configuration": True,
        "restored_deployed_tree": True,
        "restored_mcp_enable_disable": True,
        "preserved_owner_user_credentials": True,
        "proof_of_restore_per_path": True,
        "second_pass_digest_equals_first": True,
        "schema_rejects_non_idempotent_complete": True,
        "schema_rejects_unverified_complete": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "first_digest="
        f"{result.first_tree_digest[:16]} second_equal=True "
        "upgrade_extra_removed=True"
    )
    print("SUCCESS:ARC-0094-probe2 rollback twice is a no-op")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
