#!/usr/bin/env python3
"""Probe 2: forward/back migration on real pre-freeze catalog bytes; independent reject."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "freeze"))
import lib as F  # noqa: E402
import scenario as S  # noqa: E402

PROOF_DIR = REPO / F.PROOF_REL


def fail(msg: str) -> int:
    print(f"FAILED:CC-0012-probe2 {msg}")
    return 1


def main() -> int:
    ledger = F.activate(REPO)
    fixture = REPO / F.FIXTURE_REL
    if not fixture.is_file():
        return fail("pre-freeze catalog slice missing")
    migs = {m.id: m for m in F.load_migrations(REPO)}
    mig = migs.get("m0001_catalog_v2_v3")
    if mig is None:
        return fail(f"m0001_catalog_v2_v3 not loaded; have {sorted(migs)}")

    before = PROOF_DIR / "before.json"
    after = PROOF_DIR / "after.json"
    restored = PROOF_DIR / "restored.json"
    summary = PROOF_DIR / "roundtrip.json"
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    before.write_bytes(fixture.read_bytes())

    result = F.apply_migration_to_file(mig, before, after, restored)
    F.write_json(summary, result)
    print(
        f"roundtrip identical={result.get('byte_identical')} "
        f"up_changed={result.get('up_changed')} "
        f"after_schema_version={result.get('after_schema_version')} "
        f"after_sha={result.get('after_sha256')} "
        f"restored_sha={result.get('restored_sha256')}"
    )
    if not result.get("up_changed"):
        return fail("up() was a no-op on real catalog slice")
    if not result.get("byte_identical"):
        return fail("down(up(slice)) was not byte-identical to canonical original")
    if int(result.get("after_schema_version") or 0) != 3:
        return fail("post-migration artifact did not read schema_version=3 off disk")

    on_disk = F.loads_json(after)
    epoch = on_disk.get("cc0012_freeze_epoch") or {}
    if epoch.get("unit_id") != "CC-0012":
        return fail("post-migration disk artifact missing freeze epoch marker")
    wu = on_disk.get("work_unit_CC-0012") or {}
    if wu.get("id") != "CC-0012":
        return fail("real CC-0012 work unit lost during migration")

    schema_rel = S.first_schema(ledger)
    with tempfile.TemporaryDirectory(prefix="cc0012-p2-") as tmp:
        scratch = Path(tmp)
        S.copy_freeze_tree(REPO, scratch)
        S.mutate_schema_text(scratch / schema_rel, "INDEPENDENT-REVIEWER")
        review = F.evaluate_gate(scratch)
        reasons = [r.get("reason") for r in (review.get("rejections") or [])]
        print(f"reviewer ok={review.get('ok')} reasons={reasons}")
        if review.get("ok") or "no-version-bump" not in reasons:
            return fail(
                f"independent reviewer unversioned edit not rejected: {reasons}"
            )

    print(
        json.dumps(
            {
                "probe": "probe2-roundtrip",
                "unit_id": "CC-0012",
                "activation_commit": ledger.get("activation_commit"),
                "activation_timestamp": ledger.get("activation_timestamp"),
                "byte_identical": True,
                "independent_reviewer_rejected": True,
                "after_path": "command-center/freeze/proof/after.json",
                "restored_path": "command-center/freeze/proof/restored.json",
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0012-probe2 catalog round-trip and independent unversioned reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
