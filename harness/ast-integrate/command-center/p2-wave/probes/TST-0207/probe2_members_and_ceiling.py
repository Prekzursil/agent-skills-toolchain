#!/usr/bin/env python3
"""Probe 2: two independent signals on a live pack.

(a) zipfile member list vs an independent allowlist expansion of the tree.
(b) uncompressed payload bytes vs the declared size ceiling; an oversize
    allowlisted file fails the build. The packer's own member list is not
    the second enumerator.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

import pack as packer  # noqa: E402
from staging import FIXTURE_ALLOWLIST, write_clean  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0207-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0207-p2-") as tmp:
        tmp_path = Path(tmp)
        clean = tmp_path / "clean"
        oversize = tmp_path / "oversize"
        clean.mkdir()
        oversize.mkdir()
        write_clean(clean)
        write_clean(oversize)
        (oversize / "payload.bin").write_bytes(
            b"X" * (int(FIXTURE_ALLOWLIST["size_ceiling_bytes"]) + 64)
        )

        clean_zip = tmp_path / "clean.zip"
        over_zip = tmp_path / "over.zip"
        good = packer.pack(clean, dest=clean_zip, allowlist=FIXTURE_ALLOWLIST)
        over = packer.pack(oversize, dest=over_zip, allowlist=FIXTURE_ALLOWLIST)

        if not good.ok or not clean_zip.is_file():
            return _fail(f"clean pack failed: {good.reasons}")
        if over.ok:
            return _fail("oversize allowlisted payload did not fail the ceiling")
        if over_zip.exists():
            return _fail("oversize pack emitted an archive")
        if not over.ceiling_exceeded:
            return _fail(f"ceiling_exceeded was false: {over.reasons}")

        zip_rows = packer.independent_zip_members(clean_zip)
        zip_names = [r["path"] for r in zip_rows]
        zip_bytes = sum(int(r["uncompressed_bytes"]) for r in zip_rows)
        expanded = packer.independent_allowlist_expansion(
            clean, FIXTURE_ALLOWLIST["globs"]
        )
        # Deliberately do not compare against good.members as the oracle.
        if zip_names != expanded:
            return _fail(f"zip members {zip_names} != independent expansion {expanded}")
        if zip_bytes != good.uncompressed_bytes:
            return _fail("independent zip uncompressed total disagrees with pack report")
        ceiling = int(FIXTURE_ALLOWLIST["size_ceiling_bytes"])
        if zip_bytes > ceiling:
            return _fail("clean payload already over ceiling")
        if zip_bytes <= 0:
            return _fail("clean payload had zero uncompressed bytes")
        if set(zip_names) != {"plugin.json", "README.md", "src/app.py"}:
            return _fail(f"unexpected members {zip_names}")

        # Mutation control: a ** glob is refused (would make the allowlist a denylist).
        try:
            packer.pack(
                clean,
                allowlist={
                    **FIXTURE_ALLOWLIST,
                    "globs": ["**"],
                },
            )
            return _fail("unbounded glob ** was accepted")
        except packer.PackError as exc:
            if "unbounded" not in str(exc).lower() and "allowlist" not in str(exc).lower():
                return _fail(f"unexpected error for ** glob: {exc}")

        payload = {
            "probe": "probe2-members-and-ceiling",
            "unit_id": "TST-0207",
            "pass": True,
            "independent_zip_members": zip_names,
            "independent_allowlist_expansion": expanded,
            "members_agree": True,
            "independent_uncompressed_bytes": zip_bytes,
            "size_ceiling_bytes": ceiling,
            "clean_under_ceiling": zip_bytes <= ceiling,
            "oversize_fails": True,
            "oversize_ceiling_exceeded": True,
            "oversize_uncompressed_bytes": over.uncompressed_bytes,
            "oversize_reasons": over.reasons,
            "unbounded_glob_refused": True,
            "packer_member_list_not_used_as_oracle": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"members={zip_names} bytes={zip_bytes} "
            f"ceiling={ceiling} oversize=FAIL"
        )
        print("SUCCESS:TST-0207-probe2 independent zip listing matches allowlist; ceiling fails")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
