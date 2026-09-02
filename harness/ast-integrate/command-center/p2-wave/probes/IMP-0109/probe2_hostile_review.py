#!/usr/bin/env python3
"""Probe 2 (independent reviewer): hostile bundle + digest collision.

Crafts a bundle with a path-traversal member and a symlink member, then
reports the outcome. Separately, a locally existing name@version whose
incoming digest differs is surfaced as COLLISION and never overwritten.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.canon import dumps, loads  # noqa: E402
from tools.marketplace.offline import (  # noqa: E402
    empty_registry,
    export_offline_bundle,
    import_offline_bundle,
    inspect_archive_members,
    plant_hostile_tar,
    registry_census,
    sign_mutated_payload,
)
from tools.marketplace.storage import read_json, registry_dir, write_json  # noqa: E402

UNIT = "IMP-0109"
HELLO = "hello-skill@1.0.0"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    src = registry_dir(REPO)
    archive = export_offline_bundle(src, [HELLO])
    hostile = plant_hostile_tar(archive)
    inspect = inspect_archive_members(hostile)
    inspect_text = " ".join(inspect)
    if "PATH_TRAVERSAL" not in inspect_text:
        return fail(f"path traversal not flagged: {inspect}")
    if "SYMLINK_OR_HARDLINK" not in inspect_text:
        return fail(f"symlink not flagged: {inspect}")

    with tempfile.TemporaryDirectory(prefix="imp0109-p2-") as td:
        root = Path(td)
        hostile_dest = empty_registry(root / "hostile-dest")
        before_h = registry_census(hostile_dest)
        hostile_result = import_offline_bundle(hostile_dest, hostile)
        after_h = registry_census(hostile_dest)
        escaped = (root / "escape.json").exists() or (
            hostile_dest / "escape.json"
        ).exists()

        dest = root / "collision-dest"
        mutated = root / "collision-src"
        shutil.copytree(src, dest)
        shutil.copytree(src, mutated)
        blob_path = mutated / "blobs" / "hello-skill-1.0.0.json"
        payload = loads(blob_path.read_bytes())
        payload["description"] = str(payload.get("description") or "") + " [reviewer]"
        digest, sig = sign_mutated_payload(payload)
        blob_path.write_bytes(dumps(payload))
        index = read_json(mutated / "index.json")
        for pkg in index["packages"]:
            if pkg["id"] == HELLO:
                pkg["digest"] = digest
                pkg["signature"] = sig
        write_json(mutated / "index.json", index, pretty=True)
        coll_archive = export_offline_bundle(mutated, [HELLO])
        before_c = registry_census(dest)
        orig_blob = (dest / "blobs" / "hello-skill-1.0.0.json").read_bytes()
        coll_result = import_offline_bundle(dest, coll_archive)
        after_c = registry_census(dest)
        still_orig = (dest / "blobs" / "hello-skill-1.0.0.json").read_bytes() == orig_blob

    if hostile_result.ok:
        return fail("hostile bundle was accepted")
    codes_h = {e.get("code") for e in hostile_result.errors}
    if "HOSTILE_MEMBER" not in codes_h:
        return fail(f"expected HOSTILE_MEMBER, got {hostile_result.errors}")
    if before_h != after_h:
        return fail("hostile import mutated dest census")
    if escaped:
        return fail("path-traversal member escaped the destination tree")
    if coll_result.ok:
        return fail("colliding digest was accepted")
    codes_c = {e.get("code") for e in coll_result.errors}
    if "COLLISION" not in codes_c:
        return fail(f"expected COLLISION, got {coll_result.errors}")
    if coll_result.named_entry != HELLO:
        return fail(f"collision named_entry={coll_result.named_entry!r}")
    if before_c != after_c:
        return fail("collision import mutated dest census")
    if not still_orig:
        return fail("local blob was overwritten on collision")

    out = {
        "pass": True,
        "probe": "probe2-hostile-review",
        "unit_id": UNIT,
        "inspect": inspect,
        "hostile_codes": sorted(codes_h),
        "hostile_named_entry": hostile_result.named_entry,
        "hostile_census_unchanged": before_h == after_h,
        "path_traversal_escaped": escaped,
        "collision_codes": sorted(codes_c),
        "collision_named_entry": coll_result.named_entry,
        "collision_blob_unchanged": still_orig,
        "reviewer_independent": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"hostile={sorted(codes_h)} inspect={inspect} "
        f"collision={sorted(codes_c)} blob_unchanged={still_orig}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 hostile traversal+symlink refused; "
        "collision surfaced, no overwrite"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
